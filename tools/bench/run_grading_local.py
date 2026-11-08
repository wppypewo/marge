#!/usr/bin/env python3
"""照第二輪的三則訊息流程，對 OpenAI 相容 API（例如本機 llama-server）跑一次批閱。

只用 Python 標準函式庫。

流程（和測試計畫 2.3 相同）：
    1. 第一則：貼 批閱prompts.md 的 C4-B1 原版 prompt
    2. 第二則：只傳學習單圖片，模型做 OCR
    3. 第三則：貼參考轉寫〈轉寫〉一節，模型做完整批閱

用法：
    python3 ../marge/tools/bench/run_grading_local.py --base-url http://127.0.0.1:18434/v1 \\
        --label "Qwen3.6-35B-A3B IQ3_S 思考關閉" --thinking off --out 回覆_本機_Qwen_思考關閉.txt

輸出：
    --out 指定的純文字檔，格式和 回覆_第二輪_*.txt 相同（第一則回覆、OCR、批閱），
    可以直接給 check_grading.py；另存同名 .json，放計時、token 數和思考內容。
    中途失敗（逾時、伺服器錯誤、Ctrl-C）時不寫 .txt，已完成的輪次存到同名 .partial.json。
"""

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
# 評測證據（prompt、學習單照片）放在 marge 旁邊的 local-first-ai，移動時用 MARGE_EVIDENCE 指定
ROOT = Path(os.environ.get("MARGE_EVIDENCE", Path(__file__).resolve().parents[3] / "local-first-ai"))
sys.path.insert(0, str(HERE))
from ocr_diff import load_reference  # noqa: E402

# Qwen3.6 模型卡建議的取樣參數（思考：一般任務；關閉：Instruct 模式）
SAMPLING = {
    "on": {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5},
    "off": {"temperature": 0.7, "top_p": 0.80, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5},
}


def load_prompt(section):
    """取出 批閱prompts.md 指定小節的第一個 ```text 區塊，原文不改。"""
    text = (ROOT / "批閱prompts.md").read_text(encoding="utf-8")
    m = re.search(rf"^## {re.escape(section)}\s*$.*?^```text\n(.*?)^```", text, re.S | re.M)
    if not m:
        sys.exit(f"批閱prompts.md 找不到「## {section}」的 text 區塊")
    return m.group(1).rstrip("\n")


def image_mime(path):
    """依副檔名判斷圖片 MIME；不是圖片回傳 None。"""
    mime, _ = mimetypes.guess_type(path.name)
    return mime if mime and mime.startswith("image/") else None


def image_part(path):
    data = base64.b64encode(path.read_bytes()).decode()
    mime = image_mime(path)
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}


def stream_chat(base_url, model, messages, thinking, max_tokens, timeout):
    """送出串流請求，回傳回答、思考內容與計時。"""
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
        "chat_template_kwargs": {"enable_thinking": thinking == "on"},
        **SAMPLING[thinking],
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    answer, reasoning, usage, timings, finish = [], [], None, None, None
    t0 = time.monotonic()
    first = None
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            chunk = json.loads(line[6:])
            # llama-server 生成途中出錯時會在串流裡送 {"error": …}，之後就結束；
            # 不擋下來的話，半截回答會被當成正常結果寫出去
            if chunk.get("error"):
                raise RuntimeError(f"伺服器在串流中回報錯誤：{chunk['error']}")
            usage = chunk.get("usage") or usage
            timings = chunk.get("timings") or timings
            for c in chunk.get("choices", []):
                d = c.get("delta", {})
                if d.get("content") or d.get("reasoning_content"):
                    first = first or time.monotonic()
                answer.append(d.get("content") or "")
                reasoning.append(d.get("reasoning_content") or "")
                finish = c.get("finish_reason") or finish
    t1 = time.monotonic()
    return {
        "answer": "".join(answer).strip(),
        "reasoning": "".join(reasoning).strip(),
        "seconds": round(t1 - t0, 1),
        "first_token_seconds": round(first - t0, 1) if first else None,
        "finish_reason": finish,
        "usage": usage,
        "timings": timings,
    }


def main():
    p = argparse.ArgumentParser(description="用三則訊息流程跑一次批閱")
    p.add_argument("--base-url", default="http://127.0.0.1:18434/v1")
    p.add_argument("--model", default="local", help="送給伺服器的模型 ID（llama-server 不看）")
    p.add_argument("--label", required=True, help="寫進輸出檔開頭的名稱")
    p.add_argument("--thinking", choices=["on", "off"], required=True)
    p.add_argument("--section", default="C4-B1", help="批閱prompts.md 的小節名稱")
    p.add_argument("--image", type=Path, default=ROOT / "IMG_2968.jpg")
    p.add_argument("--max-tokens", type=int, default=16384)
    p.add_argument("--timeout", type=int, default=3600, help="單則逾時秒數")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    meta_path = args.out.with_suffix(".json")
    if meta_path == args.out:
        p.error("--out 不能是 .json：同名 .json 用來放計時與 token 數，會被覆蓋")
    if image_mime(args.image) is None:
        p.error(f"--image 看不出是圖片：{args.image.name}")

    turns = [
        load_prompt(args.section),
        [image_part(args.image)],
        load_reference(),
    ]
    messages, results = [], []
    meta = {
        "label": args.label, "thinking": args.thinking, "sampling": SAMPLING[args.thinking],
        "section": args.section, "image": args.image.name, "max_tokens": args.max_tokens,
        "turns": results,
    }
    try:
        for i, content in enumerate(turns, 1):
            messages.append({"role": "user", "content": content})
            print(f"第 {i} 則送出……", file=sys.stderr, flush=True)
            r = stream_chat(args.base_url, args.model, messages, args.thinking,
                            args.max_tokens, args.timeout)
            print(f"  {r['seconds']} 秒，結束原因 {r['finish_reason']}，usage {r['usage']}",
                  file=sys.stderr, flush=True)
            # 下一則只帶回答，不帶思考內容
            messages.append({"role": "assistant", "content": r["answer"]})
            results.append(r)
    except (OSError, RuntimeError, ValueError, KeyboardInterrupt) as e:
        # OSError 含 URLError、HTTPError、逾時；ValueError 含 JSON 解析失敗
        # 一則可能跑幾十分鐘，失敗時把已完成的輪次留下來，不必整組重跑才看得到
        partial = args.out.with_suffix(".partial.json")
        meta.update(complete=False, error=f"第 {len(results) + 1} 則：{type(e).__name__}: {e}")
        partial.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"失敗：{meta['error']}\n已完成 {len(results)} 則，存到 {partial}；沒有寫 {args.out.name}",
              file=sys.stderr)
        sys.exit(1)

    secs = "、".join(f"第{i}則 {r['seconds']} 秒" for i, r in enumerate(results, 1))
    header = [
        f"# 來源：marge/tools/bench/run_grading_local.py（{time.strftime('%Y-%m-%d %H:%M')}），{args.label}。",
        "# 第三則使用者訊息（貼參考轉寫）不在這裡。順序是第一則回覆、OCR（第二則回覆）、批閱（第三則回覆）。",
        "",
        f"{args.label}：{secs}；請求 3 次",
        "",
    ]
    body = "\n\n".join(r["answer"] for r in results)
    args.out.write_text("\n".join(header) + body + "\n", encoding="utf-8")
    meta["complete"] = True
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已寫入 {args.out} 與 {meta_path.name}", file=sys.stderr)
    # 被 max_tokens 截斷的回覆照樣寫出（可以看到截在哪），但要明講，免得當成完整批閱計分
    for i, r in enumerate(results, 1):
        if r["finish_reason"] == "length":
            print(f"警告：第 {i} 則被 --max-tokens {args.max_tokens} 截斷，回覆不完整",
                  file=sys.stderr)


if __name__ == "__main__":
    main()
