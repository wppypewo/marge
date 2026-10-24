#!/usr/bin/env python3
"""批閱橫評的程式判斷項目：OCR 逐字比對、字數計算。

只用 Python 標準函式庫。

用法：
    # 模型的 OCR 和參考轉寫逐字比對（可一次給多個檔案）
    python3 ../marge/tools/bench/ocr_diff.py OCR_Gemini.txt OCR_Gemma.txt

    # 只算字數（例如模型給的兩個優化版本）
    python3 ../marge/tools/bench/ocr_diff.py --count 優化版本.txt

文字檔只放轉錄或作文本身，模型前後加的說明（例如「Voici la transcription」）要刪掉。
"""

import argparse
import difflib
import os
import re
import sys
import unicodedata
from pathlib import Path

# 評測證據放在 marge 旁邊的 local-first-ai，移動時用 MARGE_EVIDENCE 指定
EVIDENCE = Path(os.environ.get("MARGE_EVIDENCE", Path(__file__).resolve().parents[3] / "local-first-ai"))
REFERENCE = EVIDENCE / "參考轉寫_IMG_2968.md"

# 模型常把撇號、引號換成印刷體，這不算 OCR 錯誤，比對前先統一
QUOTE_MAP = str.maketrans({"’": "'", "‘": "'", "ʼ": "'"})


def normalize(text):
    """統一 Unicode 組合方式與撇號。"""
    return unicodedata.normalize("NFC", text).translate(QUOTE_MAP)


def load_reference():
    """取出參考轉寫檔〈轉寫〉一節的內文。"""
    text = REFERENCE.read_text(encoding="utf-8")
    match = re.search(r"^## 轉寫\s*$(.*?)^## ", text, re.S | re.M)
    if not match:
        sys.exit(f"在 {REFERENCE.name} 找不到「## 轉寫」一節")
    return match.group(1).strip()


def count_words(text):
    """回傳（空白分隔字數, 撇號也拆開的字數），規則和參考轉寫檔相同。"""
    tokens = normalize(text).split()
    split_apostrophe = sum(len([p for p in t.split("'") if p]) for t in tokens)
    return len(tokens), split_apostrophe


def loose(token):
    """寬鬆比對：去掉標點、不分大小寫。"""
    return re.sub(r"[^\w']", "", token).lower()


def diff_tokens(ref, hyp):
    """逐字比對，回傳（不同的字數, 差異清單）。

    不同的字數：替換取兩邊較長者，刪除算參考轉寫的字數，插入算模型多出的字數。
    """
    matcher = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False)
    total = 0
    changes = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            continue
        total += max(i2 - i1, j2 - j1)
        changes.append((op, " ".join(ref[i1:i2]), " ".join(hyp[j1:j2])))
    return total, changes


def compare(path, ref_text):
    hyp_text = path.read_text(encoding="utf-8")
    ref = normalize(ref_text).split()
    hyp = normalize(hyp_text).split()

    strict_total, changes = diff_tokens(ref, hyp)
    loose_ref = [w for w in map(loose, ref) if w]
    loose_hyp = [w for w in map(loose, hyp) if w]
    loose_total, _ = diff_tokens(loose_ref, loose_hyp)

    labels = {"replace": "改", "delete": "漏", "insert": "多"}
    print(f"== {path.name}")
    print(f"字數：模型 {len(hyp)}，參考 {len(ref)}")
    print(f"不同的字數：{strict_total}（含標點、大小寫）；"
          f"{loose_total}（忽略標點、大小寫）")
    for op, ref_part, hyp_part in changes:
        print(f"  [{labels[op]}] 參考「{ref_part}」→ 模型「{hyp_part}」")
    print()


def main():
    parser = argparse.ArgumentParser(description="OCR 逐字比對與字數計算")
    parser.add_argument("files", nargs="+", type=Path, help="UTF-8 文字檔")
    parser.add_argument("--count", action="store_true",
                        help="只算字數，不和參考轉寫比對")
    args = parser.parse_args()

    ref_text = None if args.count else load_reference()
    for path in args.files:
        if args.count:
            by_space, by_apostrophe = count_words(path.read_text(encoding="utf-8"))
            print(f"{path.name}：{by_space} 字（空白分隔），"
                  f"{by_apostrophe} 字（撇號也拆開）")
        else:
            compare(path, ref_text)


if __name__ == "__main__":
    main()
