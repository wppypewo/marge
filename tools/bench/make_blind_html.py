#!/usr/bin/env python3
"""把盲評表（Markdown）轉成可以直接點選填寫的單一 HTML 檔。

只讀盲評表本身，不讀對照檔；只用 Python 標準函式庫。

用法：
    python3 ../marge/tools/bench/make_blind_html.py 盲評表_第二輪.md --out 盲評表_第二輪.html

輸出檔已經存在時不覆寫，直接結束；加 --force 才覆寫（只用在重產自己的 HTML）。
填寫結果存在瀏覽器的 localStorage，也可以匯出成 JSON。
"""

import argparse
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

WARN = "⚠️"


def unescape(text):
    return text.replace("\\|", "|").strip()


def table(lines):
    """取出一段文字裡的表格資料列（略過標題列與分隔列）。"""
    rows = [l for l in lines if l.startswith("|")]
    return [[unescape(c) for c in re.split(r"(?<!\\)\|", l.strip())[1:-1]]
            for l in rows[2:]]


def quote(lines):
    return [l[2:].strip() for l in lines if l.startswith("> ")]


def split_by(lines, prefix):
    """依標題切段，回傳 {標題: 內容行}。"""
    parts, name = {}, None
    for line in lines:
        if line.startswith(prefix):
            name = line[len(prefix):].strip()
            parts[name] = []
        elif name is not None:
            parts[name].append(line)
    return parts


def parse_errors(cell):
    errors = []
    for item in cell.split("；"):
        m = re.match(r"\s*(E\d+)：(.+)", item)
        if m:
            errors.append({"id": m.group(1), "text": m.group(2).strip()})
    return errors


def clean_annotated(paragraphs, warnings):
    """去掉 ⚠️ 符號、理由括號和 ☑️／✅ 標記，回傳乾淨文字與每個 ⚠️ 在乾淨文字裡的位置。"""
    text = "\n".join(paragraphs)
    remove = [False] * len(text)
    spans, cursor = [], 0
    for w in warnings:
        start = text.find(WARN + w["target"], cursor)
        if start < 0:
            spans.append(None)
            continue
        t_start = start + len(WARN)
        t_end = t_start + len(w["target"])
        for k in range(start, t_start):
            remove[k] = True
        tail = f" ({w['reason']})"
        if text.startswith(tail, t_end):
            for k in range(t_end, t_end + len(tail)):
                remove[k] = True
            cursor = t_end + len(tail)
        else:
            cursor = t_end
        spans.append((t_start, t_end))
    for m in re.finditer(r"(?:☑️|✅) ?(\[)?", text):
        for k in range(m.start(), m.end()):
            remove[k] = True
        if m.group(1):
            close = text.find("]", m.end())
            if close >= 0:
                remove[close] = True
    # 舊位置 → 新位置
    mapping, out = [], []
    for k, ch in enumerate(text):
        mapping.append(len(out))
        if not remove[k]:
            out.append(ch)
    mapping.append(len(out))
    clean = "".join(out)
    new_spans = [None if s is None else (mapping[s[0]], mapping[s[1]]) for s in spans]
    return clean, new_spans


def sentence_ranges(text):
    """把乾淨文字切成句子，回傳 (起, 迄) 列表。"""
    ranges = []
    offset = 0
    for para in text.split("\n"):
        start = 0
        for m in re.finditer(r"(?<=[.!?])\s+", para):
            ranges.append((offset + start, offset + m.start()))
            start = m.end()
        if para[start:].strip():
            ranges.append((offset + start, offset + len(para)))
        offset += len(para) + 1
    return ranges


def best_sentence(text, sentences):
    scores = [difflib.SequenceMatcher(None, text, s["text"]).ratio() for s in sentences]
    best = max(range(len(scores)), key=scores.__getitem__)
    return best if scores[best] >= 0.4 else None


def parse_model(letter, lines, sentences):
    subs = split_by(lines, "### ")
    annotated = quote(subs.get("批改後的原文", []))

    warn_rows = table(subs.get("⚠️ 逐條判斷", []))
    silent_rows = table(subs.get("沒標 ⚠️ 就改掉的地方", []))
    mark_rows = table(subs.get("☑️／✅ 標記", []))
    filled = any(any(r[3:]) for r in warn_rows) or any(any(r[2:]) for r in silent_rows) \
        or any(any(r[2:]) for r in mark_rows)
    if filled:
        print(f"注意：模型 {letter} 在 md 裡已有填寫內容，HTML 不會帶入，請自己對照", file=sys.stderr)

    warnings = [{"target": r[1], "reason": r[2]} for r in warn_rows]
    clean, spans = clean_annotated(annotated, warnings)
    ranges = sentence_ranges(clean)
    for w, span in zip(warnings, spans):
        w["pre"] = w["hl"] = w["post"] = ""
        w["sent"] = None
        if span is None:
            continue
        s_start, s_end = next(((a, b) for a, b in ranges if a <= span[0] < b), (span[0], span[1]))
        w["pre"] = clean[s_start:span[0]]
        w["hl"] = clean[span[0]:span[1]]
        w["post"] = clean[span[1]:max(s_end, span[1])]
        w["sent"] = best_sentence(clean[s_start:s_end], sentences)

    model_sentences = [clean[a:b] for a, b in ranges]
    silent = []
    for r in silent_rows:
        if r[0] == "（程式沒找到）":
            continue
        ref_part, hyp_part = r[0], r[1]
        cands = []
        if ref_part != "（無）":
            cands = [i for i, s in enumerate(sentences) if ref_part in s["text"]]
        if len(cands) != 1 and hyp_part != "（刪掉）":
            hits = [s for s in model_sentences if hyp_part in s]
            if len(hits) == 1:
                guess = best_sentence(hits[0], sentences)
                if guess is not None and (not cands or guess in cands):
                    cands = [guess]
        silent.append({"from": ref_part, "to": hyp_part, "sents": cands})

    marks = [{"label": r[0], "word": r[1]} for r in mark_rows]
    opt = {}
    for key in ("B1", "B2"):
        opt[key] = " ".join(quote(subs.get(f"{key} 優化版本", [])))
    return {
        "letter": letter,
        "annotated": annotated,
        "warn": warnings,
        "silent": silent,
        "marks": marks,
        "strengths": quote(subs.get("優點", [])),
        "weaknesses": quote(subs.get("缺點", [])),
        "b1": opt["B1"],
        "b2": opt["B2"],
    }


def parse_pack(md):
    lines = md.split("\n")
    title = lines[0].lstrip("# ").strip()
    tops = split_by(lines, "## ")
    inventory = next(v for k, v in tops.items() if k.startswith("1."))
    sentences = []
    for row in table(inventory):
        sentences.append({"para": row[0], "text": row[1], "errors": parse_errors(row[2])})
    models = [parse_model(k.split()[-1], v, sentences)
              for k, v in tops.items() if k.startswith("模型 ")]
    return {"title": title, "sentences": sentences, "models": models}


def main():
    parser = argparse.ArgumentParser(description="盲評表 Markdown → 可填寫的 HTML")
    parser.add_argument("pack", type=Path, help="盲評表 .md")
    parser.add_argument("--out", type=Path, required=True, help="輸出的 .html")
    parser.add_argument("--force", action="store_true", help="輸出檔已存在時覆寫")
    args = parser.parse_args()

    if args.out.exists() and not args.force:
        sys.exit(f"{args.out} 已經存在，不覆寫（確定要重產再加 --force）")
    data = parse_pack(args.pack.read_text(encoding="utf-8"))
    # 項目簽章：匯入 JSON 時用來確認是不是同一份盲評表
    items = [[w["target"] for w in m["warn"]] + [s["from"] for s in m["silent"]]
             + [k["word"] for k in m["marks"]] for m in data["models"]]
    data["sig"] = hashlib.sha256(json.dumps(items, ensure_ascii=False).encode()).hexdigest()[:12]
    data["source"] = args.pack.name

    template = (Path(__file__).resolve().parent / "blind_form_template.html").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = template.replace("/*__DATA__*/", payload).replace("__TITLE__", data["title"])
    args.out.write_text(html, encoding="utf-8")

    n_errors = sum(len(s["errors"]) for s in data["sentences"])
    print(f"已產生 {args.out}：錯誤 {n_errors} 個，模型 " + "、".join(
        f"{m['letter']}（⚠️ {len(m['warn'])}，沒標改動 {len(m['silent'])}，標記 {len(m['marks'])}）"
        for m in data["models"]))
    missing = [f"{m['letter']}#{i + 1}" for m in data["models"]
               for i, w in enumerate(m["warn"]) if not w["hl"]]
    if missing:
        print("這些 ⚠️ 在原文裡找不到位置，不顯示上下文：" + "、".join(missing))


if __name__ == "__main__":
    main()
