#!/usr/bin/env python3
"""產生盲評表：把幾個模型的批閱回覆打亂順序、改標成 A、B、C，排成給人判斷的表格。

只用 Python 標準函式庫，段落切法沿用 check_grading.py。

用法：
    python3 ../marge/tools/bench/make_blind_pack.py \\
        回覆_第二輪_Nemotron.txt 回覆_第二輪_Gemini_FlashLite.txt 回覆_第二輪_Gemini_Flash.txt \\
        --out 盲評表_第二輪.md --key 盲評對照_第二輪.md

對照檔（哪個字母是哪個模型）另外存，判斷完再打開。
輸出檔已經存在時不覆寫，直接結束。
這個腳本只排版，不判斷任何語言項目。
"""

import argparse
import random
import re
import string
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_grading import (CHECK, DONE, check_warnings, marked_text,  # noqa: E402
                           marker_segments, optimized_text, split_sections,
                           unmarked_changes)
from ocr_diff import load_reference, normalize  # noqa: E402


def cell(text):
    """表格儲存格：跳脫直線、去掉換行。"""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def reference_sentences():
    """參考轉寫依句號切句，回傳（段落編號, 句子）。"""
    sentences = []
    paragraphs = [p for p in load_reference().split("\n\n") if p.strip()]
    for number, paragraph in enumerate(paragraphs, 1):
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph.strip()):
            sentences.append((number, sentence))
    return sentences


def error_inventory():
    lines = [
        "## 1. 錯誤清單（先填，再看模型）",
        "",
        "這一節是答案卷：列出**學生作文本身寫錯的地方**（拼字、文法、性數配合、動詞變化等），"
        "不是檢查轉寫和原文一不一樣。「原句」欄是對照紙本核對過的參考轉寫，照學生原樣抄、錯字都保留，不用再比對；"
        "OCR 和原文的差異由 `marge/tools/bench/ocr_diff.py` 算，結果見測試計畫附錄 A.2。",
        "",
        "每句一列。每個錯誤寫成「錯的字 → 正確寫法」，多個錯誤用分號隔開，並在最前面編號（E1、E2……），"
        "後面各模型的表格用這個編號對應。整句都沒有學生的錯才填「全對」：填了「全對」的句子，"
        "模型在這句標的 ⚠️ 都會算成誤判。",
        "",
        "| 段 | 原句 | 學生寫錯的地方（編號：錯的字 → 正確寫法） |",
        "|---|---|---|",
    ]
    for number, sentence in reference_sentences():
        lines.append(f"| {number} | {cell(sentence)} |  |")
    lines.append("")
    return lines


def model_block(letter, path):
    sections = split_sections(normalize(path.read_text(encoding="utf-8")))
    annotated = sections.get("annotated", [])
    lines = [f"## 模型 {letter}", "", "### 批改後的原文", ""]
    lines += [f"> {line.strip()}" for line in annotated if line.strip()]
    lines.append("")

    warnings, _ = check_warnings(annotated)
    lines += [
        "### ⚠️ 逐條判斷",
        "",
        "「改得對」：改完的寫法對不對。「理由合理」：括號裡的理由說得通嗎。"
        "「對應錯誤」：填錯誤清單的編號；學生原本沒錯、被改成別的寫法，填「誤判」。",
        "",
        "| # | 標記的字 | 理由 | 改得對（對／錯） | 理由合理（是／否） | 對應錯誤 |",
        "|---|---|---|---|---|---|",
    ]
    for i, (target, reason) in enumerate(warnings, 1):
        lines.append(f"| {i} | {cell(target)} | {cell(reason or '（無理由）')} |  |  |  |")
    lines.append("")

    silent = unmarked_changes(annotated, load_reference())
    lines += [
        "### 沒標 ⚠️ 就改掉的地方",
        "",
        "程式把批改後的原文和學生原文逐字比，列出不在任何 ⚠️ 範圍內的改動。"
        "比對會有誤差（可能漏列或多列），請對照上面的原文。",
        "",
        "| 學生原文 | 模型改成 | 改得對（對／錯） | 對應錯誤 |",
        "|---|---|---|---|",
    ]
    for ref_part, hyp_part in silent:
        lines.append(f"| {cell(ref_part) or '（無）'} | {cell(hyp_part) or '（刪掉）'} |  |  |")
    if not silent:
        lines.append("| （程式沒找到） |  |  |  |")
    lines.append("")

    lines += [
        "### ☑️／✅ 標記",
        "",
        "☑️ 應該只標 7 個必用句型，✅ 應該只標選用詞彙。沒有方括號的標記，"
        "這裡只取標記後面最多 4 個字，請對照上面的原文。",
        "",
        "| 標記 | 標的字 | 類別標對（是／否） | 用法對（是／否） |",
        "|---|---|---|---|",
    ]
    for label, marker in (("☑️", CHECK), ("✅", DONE)):
        for line in annotated:
            for segment in marker_segments(line, marker):
                word, bracketed = marked_text(segment)
                shown = word if bracketed else f"{word}…"
                lines.append(f"| {label} | {cell(shown)} |  |  |")
    lines.append("")

    for key, title in (("strengths", "優點"), ("weaknesses", "缺點")):
        body = [l.strip() for l in sections.get(key, []) if l.strip()]
        lines += [f"### {title}", ""] + [f"> {l}" for l in body] + [""]
    lines += [
        "優點、缺點講的對不對，以及說明是不是 B1 程度的法文（格式）：",
        "",
        "- 說錯的地方：",
        "- 法文程度：",
        "",
    ]

    for key, name in (("b1", "B1"), ("b2", "B2")):
        body, _ = optimized_text(sections.get(key, []))
        lines += [
            f"### {name} 優化版本",
            "",
            f"> {body}",
            "",
            "- 沿用學生用詞（多數沿用／部分／大多換掉）：",
            "- 優化版本本身的錯誤：",
            "",
        ]

    lines += [
        "### 小計（填完上面再算）",
        "",
        "| 項目 | 數字或判斷 |",
        "|---|---|",
        "| 誤判（把對的改錯） |  |",
        "| 漏掉的錯誤（錯誤清單裡沒被 ⚠️ 標到的編號） |  |",
        "| 理由不合理的 ⚠️ |  |",
        "| 沒標 ⚠️ 的改動（真的改了學生的字的處數） |  |",
        "| 格式（標題繁中、說明 B1 法文） |  |",
        "| 優化版本沿用學生用詞 |  |",
        "",
    ]
    return lines


def write_new(path, lines):
    if path.exists():
        sys.exit(f"{path} 已經存在，不覆寫；換一個檔名或先自己處理舊檔")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="產生盲評表與對照檔")
    parser.add_argument("files", nargs="+", type=Path, help="批閱回覆的純文字檔")
    parser.add_argument("--out", type=Path, required=True, help="盲評表檔名")
    parser.add_argument("--key", type=Path, required=True, help="對照檔檔名")
    args = parser.parse_args()

    if args.out.exists() or args.key.exists():
        sys.exit("輸出檔已經存在，不覆寫")
    files = list(args.files)
    random.SystemRandom().shuffle(files)
    letters = string.ascii_uppercase[:len(files)]

    pack = [
        f"# 盲評表（{date.today().isoformat()} 產生）",
        "",
        "用 `marge/tools/bench/make_blind_pack.py` 產生，模型順序隨機、只標字母。"
        "哪個字母是哪個模型寫在另一個對照檔，全部填完再打開。"
        "標記方式（例如有沒有方括號）可能讓你認出模型，這份表只能減少、不能完全排除模型名稱的影響。",
        "",
        "程式已經判斷過的項目（⚠️ 數量、字數、標題）不在這裡，見 `marge/tools/bench/check_grading.py` 的輸出。",
        "",
        "順序：先填錯誤清單（第 1 節），再逐個模型看。",
        "",
    ]
    pack += error_inventory()
    for letter, path in zip(letters, files):
        pack += model_block(letter, path)

    key = [f"# 盲評對照（{date.today().isoformat()} 產生）", "",
           "盲評表全部填完再看。", "", "| 字母 | 回覆檔 |", "|---|---|"]
    key += [f"| {letter} | {path.name} |" for letter, path in zip(letters, files)]
    key.append("")

    write_new(args.out, pack)
    write_new(args.key, key)
    print(f"已產生 {args.out} 和 {args.key}（{len(files)} 個模型）")


if __name__ == "__main__":
    main()
