#!/usr/bin/env python3
"""把 HTML 盲評表匯出的 JSON 填回盲評表 Markdown。

只填各模型區塊裡原本空白的格子與條列，第 1 節錯誤清單不動；
已經有內容的格子不覆寫，改列在 stderr。只用 Python 標準函式庫。

用法：
    python3 ../marge/tools/bench/fill_blind_md.py 盲評表_第二輪.md 盲評表_第二輪_結果.json --out 輸出.md

輸出檔已經存在時不覆寫；加 --force 才覆寫。
"""

import argparse
import json
import re
import sys
from pathlib import Path

MISREAD = "程式誤列"


def cells(line):
    """切開表格列，保留跳脫的 \\|。回傳（前綴, 格子列表）。"""
    parts = re.split(r"(?<!\\)\|", line.rstrip("\n"))
    return parts[1:-1]


def join_row(parts):
    return "|" + "|".join(parts) + "|"


def fill_cells(parts, start, values, where, conflicts):
    for k, v in enumerate(values):
        idx = start + k
        if parts[idx].strip():
            if parts[idx].strip() != v:
                conflicts.append(f"{where} 第 {idx + 1} 欄已有「{parts[idx].strip()}」，沒有改成「{v}」")
            continue
        parts[idx] = f" {v} "
    return parts


def errs_text(errs):
    return "、".join(errs)


def subtotal(m):
    s = m["summary"]
    missed = s["missed"]
    fixed = set(s["missedButFixed"])
    listed = "、".join(e + ("（沒標 ⚠️ 但有改）" if e in fixed else "") for e in missed)
    return {
        "誤判（把對的改錯）": str(s["misjudge"]),
        "漏掉的錯誤（錯誤清單裡沒被 ⚠️ 標到的編號）": f"{len(missed)} 個：{listed}" if missed else "0",
        "理由不合理的 ⚠️": str(s["badReason"]),
        "沒標 ⚠️ 的改動（真的改了學生的字的處數）":
            f"{s['silentReal']}（改錯 {s['silentWrong']}）",
        "格式（標題繁中、說明 B1 法文）": s["format"],
        "優化版本沿用學生用詞": f"B1：{s['keep']['B1'] or '未填'}；B2：{s['keep']['B2'] or '未填'}",
    }


def fill(md, data):
    lines = md.split("\n")
    models = {m["letter"]: m for m in data["models"]}
    conflicts = []
    letter = sub = None
    row = 0
    for n, line in enumerate(lines):
        if line.startswith("## "):
            mt = re.match(r"## 模型 (\S+)", line)
            letter = mt.group(1) if mt and mt.group(1) in models else None
            sub = None
            continue
        if letter is None:
            continue
        m = models[letter]
        if line.startswith("### "):
            sub, row = line[4:].strip(), -3  # 跳過標題列與分隔列（各 +1 後仍 < 0）
            continue
        where = f"模型 {letter}「{sub}」"
        if line.startswith("|"):
            row += 1
            if row < 0:
                continue
            parts = cells(line)
            if sub == "⚠️ 逐條判斷" and row < len(m["warn"]):
                w = m["warn"][row]
                parts = fill_cells(parts, 3, [w["ok"] or "", w["reason_ok"] or "", errs_text(w["errs"])],
                                   f"{where} 第 {row + 1} 列", conflicts)
            elif sub == "沒標 ⚠️ 就改掉的地方" and row < len(m["silent"]):
                c = m["silent"][row]
                errs = "（不計）" if c["ok"] == MISREAD else errs_text(c["errs"])
                parts = fill_cells(parts, 2, [c["ok"] or "", errs], f"{where} 第 {row + 1} 列", conflicts)
            elif sub == "☑️／✅ 標記" and row < len(m["marks"]):
                k = m["marks"][row]
                parts = fill_cells(parts, 2, [k["cat"] or "", k["use"] or ""], f"{where} 第 {row + 1} 列", conflicts)
            elif sub and sub.startswith("小計"):
                table = subtotal(m)
                key = parts[0].strip()
                if key in table:
                    parts = fill_cells(parts, 1, [table[key]], f"{where}「{key}」", conflicts)
            lines[n] = join_row(parts)
            continue
        bullets = {}
        if sub == "缺點":
            bullets = {"- 說錯的地方：": m["notes"]["說錯的地方"], "- 法文程度：": m["notes"]["法文程度"]}
        elif sub in ("B1 優化版本", "B2 優化版本"):
            o = m["optimized"][sub[:2]]
            bullets = {"- 沿用學生用詞（多數沿用／部分／大多換掉）：": o["keep"] or "",
                       "- 優化版本本身的錯誤：": o["errors"]}
        for prefix, value in bullets.items():
            if line.startswith(prefix):
                rest = line[len(prefix):].strip()
                if rest:
                    if rest != value:
                        conflicts.append(f"{where}「{prefix[2:]}」已有「{rest}」，沒有改成「{value}」")
                elif value:
                    lines[n] = prefix + value
    return "\n".join(lines), conflicts


def main():
    parser = argparse.ArgumentParser(description="HTML 盲評表的匯出 JSON → 填回 Markdown")
    parser.add_argument("pack", type=Path, help="盲評表 .md")
    parser.add_argument("results", type=Path, help="匯出的 JSON")
    parser.add_argument("--out", type=Path, required=True, help="輸出的 .md")
    parser.add_argument("--force", action="store_true", help="輸出檔已存在時覆寫")
    args = parser.parse_args()

    if args.out.exists() and not args.force:
        sys.exit(f"{args.out} 已經存在，不覆寫（確定要覆寫再加 --force）")
    data = json.loads(args.results.read_text(encoding="utf-8"))
    if data.get("source") != args.pack.name:
        print(f"注意：JSON 來源是 {data.get('source')}，不是 {args.pack.name}", file=sys.stderr)
    text, conflicts = fill(args.pack.read_text(encoding="utf-8"), data)
    args.out.write_text(text, encoding="utf-8")
    for c in conflicts:
        print("沒覆寫：" + c, file=sys.stderr)
    print(f"已寫入 {args.out}")


if __name__ == "__main__":
    main()
