#!/usr/bin/env python3
"""用同一組題目測試 OpenAI 相容 API，記錄首字延遲、生成速度與回答內容。

只用標準函式庫，macOS 內建的 python3（3.9）就能執行。
LM Studio、Ollama、OpenRouter、Open WebUI 都提供這種 API。
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 常用端點的簡寫，省得每次打完整網址
PRESETS = {
    "lmstudio": "http://localhost:1234/v1",
    "ollama": "http://localhost:11434/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}

CSV_FIELDS = [
    "時間", "標籤", "模型", "題號", "首字秒數", "總秒數",
    "生成tokens", "tokens來源", "每秒tokens", "自動檢查", "錯誤",
]


def parse_args():
    p = argparse.ArgumentParser(description="對 OpenAI 相容 API 跑固定題目並記錄速度")
    p.add_argument("--base-url", required=True,
                   help="API 網址，或簡寫：" + "、".join(PRESETS))
    p.add_argument("--model", required=True, help="模型 ID，例如 qwen3.6-35b-a3b")
    p.add_argument("--label", help="這次測試的名稱，預設用模型 ID")
    p.add_argument("--key-env",
                   help="存放 API key 的環境變數名稱，例如 OPENROUTER_API_KEY")
    p.add_argument("--only", help="只跑指定題目，逗號分隔，例如 T1,T4")
    p.add_argument("--max-tokens", type=int, default=4096)
    p.add_argument("--timeout", type=int, default=600, help="單題逾時秒數")
    p.add_argument("--prompts", default=str(HERE / "prompts.json"))
    p.add_argument("--out", default=str(HERE / "results"))
    return p.parse_args()


def stream_chat(base_url, model, prompt, api_key, max_tokens, timeout):
    """送出串流請求，回傳回答、推理內容與計時資料。"""
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    content, reasoning = [], []
    usage = None
    chunks = 0
    first = None
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            # SSE 的註解行（例如 OpenRouter 的心跳）不是 data:，直接略過
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            event = json.loads(data)
            if event.get("error"):
                raise RuntimeError(json.dumps(event["error"], ensure_ascii=False))
            if event.get("usage"):
                usage = event["usage"]
            for choice in event.get("choices") or []:
                delta = choice.get("delta") or {}
                # LM Studio 把思考過程放在 reasoning_content，OpenRouter 放在 reasoning
                think = delta.get("reasoning_content") or delta.get("reasoning")
                text = delta.get("content")
                if think or text:
                    chunks += 1
                    if first is None:
                        first = time.monotonic()
                if think:
                    reasoning.append(think)
                if text:
                    content.append(text)
    end = time.monotonic()

    if usage and usage.get("completion_tokens"):
        tokens, source = usage["completion_tokens"], "API"
    else:
        # 沒有 usage 時用串流片段數估算，通常接近但不精確
        tokens, source = chunks, "估算"
    ttft = (first - start) if first else None
    gen_time = (end - first) if first else None
    tps = tokens / gen_time if gen_time and gen_time > 0 else None
    return {
        "answer": "".join(content),
        "reasoning": "".join(reasoning),
        "ttft": ttft,
        "total": end - start,
        "tokens": tokens,
        "source": source,
        "tps": tps,
    }


def auto_check(test_id, answer):
    """只檢查能機械判斷的題目，其餘留給人工對照 check 欄位。"""
    if test_id == "T6":
        try:
            json.loads(answer.strip())
            return "JSON 可解析"
        except ValueError:
            return "JSON 解析失敗"
    return ""


def fmt(value, digits=1):
    return "" if value is None else f"{value:.{digits}f}"


def main():
    args = parse_args()
    base_url = PRESETS.get(args.base_url, args.base_url)
    label = args.label or args.model

    api_key = None
    if args.key_env:
        api_key = os.environ.get(args.key_env)
        if not api_key:
            sys.exit(f"環境變數 {args.key_env} 是空的，請先設定再執行。")

    tests = json.loads(Path(args.prompts).read_text(encoding="utf-8"))
    if args.only:
        wanted = {t.strip().upper() for t in args.only.split(",")}
        tests = [t for t in tests if t["id"] in wanted]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_label = re.sub(r"[^\w.@-]+", "_", label)
    md_path = out_dir / f"{stamp}_{safe_label}.md"
    csv_path = out_dir / "summary.csv"

    md = [
        f"# {label}",
        "",
        f"- 模型：`{args.model}`",
        f"- 端點：`{base_url}`",
        f"- 時間：{datetime.now():%Y-%m-%d %H:%M}",
        "",
    ]
    rows = []
    for t in tests:
        print(f"[{t['id']}] {t['name']} ...", end=" ", flush=True)
        row = {
            "時間": f"{datetime.now():%Y-%m-%d %H:%M}",
            "標籤": label, "模型": args.model, "題號": t["id"],
        }
        try:
            r = stream_chat(base_url, args.model, t["prompt"], api_key,
                            args.max_tokens, args.timeout)
        except urllib.error.HTTPError as e:
            msg = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}"
            print(msg)
            row["錯誤"] = msg
            rows.append(row)
            md += [f"## {t['id']} {t['name']}", "", f"錯誤：{msg}", ""]
            continue
        except (urllib.error.URLError, RuntimeError, TimeoutError, OSError) as e:
            print(f"失敗：{e}")
            row["錯誤"] = str(e)
            rows.append(row)
            md += [f"## {t['id']} {t['name']}", "", f"錯誤：{e}", ""]
            continue

        check = auto_check(t["id"], r["answer"])
        print(f"首字 {fmt(r['ttft'])} 秒，{fmt(r['tps'])} tok/s {check}")
        row.update({
            "首字秒數": fmt(r["ttft"], 2), "總秒數": fmt(r["total"], 2),
            "生成tokens": r["tokens"], "tokens來源": r["source"],
            "每秒tokens": fmt(r["tps"]), "自動檢查": check,
        })
        rows.append(row)

        md += [
            f"## {t['id']} {t['name']}",
            "",
            f"檢查重點：{t['check']}",
            "",
            f"首字 {fmt(r['ttft'])} 秒｜總共 {fmt(r['total'])} 秒｜"
            f"{r['tokens']} tokens（{r['source']}）｜{fmt(r['tps'])} tok/s"
            + (f"｜{check}" if check else ""),
            "",
        ]
        if r["reasoning"]:
            md += [
                f"<details><summary>思考過程（{len(r['reasoning'])} 字）</summary>",
                "",
                r["reasoning"],
                "",
                "</details>",
                "",
            ]
        md += ["回答：", "", r["answer"], ""]

    md_path.write_text("\n".join(md), encoding="utf-8")
    new_file = not csv_path.exists()
    # utf-8-sig 讓 Excel / Numbers 打開時中文不會變亂碼
    with csv_path.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerows(rows)
    print(f"\n回答全文：{md_path}\n速度彙整：{csv_path}")


if __name__ == "__main__":
    main()
