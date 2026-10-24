#!/usr/bin/env python3
"""批閱橫評的程式判斷項目：檢查模型第三則回覆（批閱）的格式與數字。

只用 Python 標準函式庫，字數規則沿用 ocr_diff.py。

用法：
    # 一次檢查多個回覆檔（整份對話存成的純文字檔即可）
    python3 ../marge/tools/bench/check_grading.py 回覆_第二輪_Nemotron.txt 回覆_第二輪_Gemini_Flash.txt

檢查的項目：
    1. C4-B1 要求的 7 個中文標題有沒有出現
    2. ⚠️ 的數量（prompt 要求少於 12）、模型自己報的數量、每個 ⚠️ 有沒有附理由，
       以及批改段落裡沒標 ⚠️ 就改掉的字
    3. ☑️／✅ 標了哪些字
    4. 字數統計段落的數字，和學生原文的實際字數比
    5. B1、B2 優化版本的字數（prompt 要求 120-140）

這個腳本只判斷格式與數字；⚠️ 改得對不對、理由合不合理由人判斷。
"""

import argparse
import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ocr_diff import count_words, load_reference, loose, normalize  # noqa: E402

# C4-B1 要求的標題，依出現順序；比對時只看行首
HEADINGS = [
    ("annotated", "原文轉錄與校對"),
    ("count", "字數統計"),
    ("vocab", "規定詞彙檢查"),
    ("strengths", "優點"),
    ("weaknesses", "缺點"),
    ("b1", "以 B1 檢定為目標的優化版本"),
    ("b2", "以 B2 檢定為目標的優化版本"),
]

WARN = "⚠️?"      # ⚠️（有些模型不帶 U+FE0F）
CHECK = "☑️?"     # ☑️
DONE = "✅"             # ✅
ANY_MARK = re.compile(f"{WARN}|{CHECK}|{DONE}")

TARGET_WORDS = 120          # prompt 規定的字數
UPPER_LIMIT = 132           # 120 + 10%
MAX_WARNINGS = 11           # prompt：« inférieur à 12 »
OPTIMIZED_RANGE = (120, 140)

# 模型在優化版本後面自己報的字數，例如「(129 mots)」
SELF_COUNT = re.compile(r"^\(\s*(\d+)\s*mots\s*\)$")


def heading_key(line):
    """如果這一行是標題，回傳它的代號；不是就回傳 None。"""
    stripped = line.strip().lstrip("-•#* ").strip()
    if len(stripped) > 40:
        return None
    for key, title in HEADINGS:
        if stripped.startswith(title):
            return key
    return None


def split_sections(text):
    """從第一個「原文轉錄與校對」標題開始，依標題把回覆切成段落。"""
    sections = {}
    current = None
    for line in text.splitlines():
        key = heading_key(line)
        if key == "annotated" and current is None:
            current = key
        elif current is None:
            continue
        elif key is not None:
            current = key
        if key is None:
            sections.setdefault(current, []).append(line)
        else:
            sections.setdefault(current, [])
    return sections


def is_self_report(line):
    """模型自己報 ⚠️ 數量的行（整行括號，或有 Nombre），不算進 ⚠️。"""
    stripped = line.strip()
    return (stripped.startswith("(") and stripped.endswith(")")) \
        or "Nombre" in stripped


def read_reason_span(segment):
    """回傳（標記的字, 理由或 None, 理由括號結束的位置）。"""
    open_at = segment.find("(")
    if open_at == -1:
        return segment.strip(), None, 0
    depth = 0
    for i in range(open_at, len(segment)):
        if segment[i] == "(":
            depth += 1
        elif segment[i] == ")":
            depth -= 1
            if depth == 0:
                return (segment[:open_at].strip(),
                        segment[open_at + 1:i].strip(), i + 1)
    return segment[:open_at].strip(), None, 0


def read_reason(segment):
    """segment 以 ⚠️ 後面的文字開頭；回傳（標記的字, 理由或 None）。"""
    target, reason, _ = read_reason_span(segment)
    return target, reason


def marker_segments(line, marker):
    """回傳這一行每個 marker 後面、到下一個任何標記為止的文字。"""
    segments = []
    for match in re.finditer(marker, line):
        rest = line[match.end():]
        nxt = ANY_MARK.search(rest)
        segments.append(rest[:nxt.start()] if nxt else rest)
    return segments


def check_warnings(lines):
    warnings = []
    self_reported = None
    for line in lines:
        if is_self_report(line):
            found = re.search(f"{WARN}\\s*:\\s*(\\d+)", line)
            if found:
                self_reported = int(found.group(1))
            continue
        for segment in marker_segments(line, WARN):
            warnings.append(read_reason(segment))
    return warnings, self_reported


def plain_tokens(lines):
    """去掉標記與理由，還原成模型改過的作文；回傳 [(字, 是否在 ⚠️ 標的範圍內)]。

    用字元位置記 ⚠️ 的範圍，這樣標記黏在字中間（例如 l'✅ [obsession]）也能還原成一個字。
    """
    tokens = []
    for line in lines:
        if is_self_report(line):
            continue
        pieces = ANY_MARK.split(line)
        marks = ANY_MARK.findall(line)
        plain = pieces[0]
        flagged = []
        for mark, segment in zip(marks, pieces[1:]):
            if re.fullmatch(WARN, mark):
                target, reason, end = read_reason_span(segment)
                if not plain or plain[-1].isspace():
                    plain += segment[:len(segment) - len(segment.lstrip())]
                flagged.append((len(plain), len(plain) + len(target)))
                plain += target
                plain += segment[end:] if reason is not None else ""
            else:
                if plain and not plain[-1].isspace():
                    segment = segment.lstrip()
                plain += re.sub(r"^(\s*)\[([^\]]*)\]", r"\1\2", segment)
        for match in re.finditer(r"\S+", plain):
            inside = any(a < match.end() and match.start() < b for a, b in flagged)
            tokens.append((match.group(), inside))
    return tokens


def unmarked_changes(lines, reference):
    """模型改過的作文和學生原文比，找出沒有 ⚠️ 的改動。

    插入、刪除只隔一個字時合併成一處（字序對調、搬位置會拆成這種組合），
    合併後只要有一部分在 ⚠️ 範圍內，就算有標。替換不合併。
    """
    tokens = [(w, f) for w, f in plain_tokens(lines) if loose(w)]
    hyp = [loose(w) for w, _ in tokens]
    ref_words = [w for w in normalize(reference).split() if loose(w)]
    ref = [loose(w) for w in ref_words]

    ops = [o for o in difflib.SequenceMatcher(
        a=ref, b=hyp, autojunk=False).get_opcodes() if o[0] != "equal"]
    blocks = []
    for op, i1, i2, j1, j2 in ops:
        prev = blocks[-1] if blocks else None
        if (prev and op != "replace" and prev[4] != "replace"
                and i1 - prev[1] <= 1 and j1 - prev[3] <= 1):
            prev[1], prev[3] = i2, j2
        else:
            blocks.append([i1, i2, j1, j2, op])
    changes = []
    for i1, i2, j1, j2, _ in blocks:
        if any(flag for _, flag in tokens[j1:j2]):
            continue
        # 純刪除：前後兩個字都在 ⚠️ 範圍內，代表刪除是那個 ⚠️ 的一部分
        if j1 == j2 and 0 < j1 < len(tokens) and tokens[j1 - 1][1] and tokens[j1][1]:
            continue
        changes.append((" ".join(ref_words[i1:i2]),
                        " ".join(w for w, _ in tokens[j1:j2])))
    return changes


def marked_text(segment):
    """☑️／✅ 標的字：有方括號取括號內，沒有就取後面最多 4 個字。"""
    segment = segment.strip()
    if segment.startswith("["):
        end = segment.find("]")
        if end != -1:
            return segment[1:end], True
    words = re.split(r"[,.;:(]", segment, maxsplit=1)[0].split()
    return " ".join(words[:4]), False


def check_count_section(lines, student_words):
    text = normalize(" ".join(lines))
    print("  原文：" + " / ".join(l.strip() for l in lines if l.strip()))
    over = re.search(r"Plus de (\d+) mots écrits \((\d+) mots de trop", text)
    under = re.search(r"Il manque (\d+) mots", text)
    # 修正版的句型：« Le texte compte [總數] mots, soit [x] mots de trop. »
    total = re.search(r"Le texte compte (\d+) mots, (?:soit (\d+) mots de trop"
                      r"|il manque (\d+) mots)", text)
    by_space, by_apostrophe = student_words
    if total:
        reported = int(total.group(1))
        diff = int(total.group(2) or total.group(3))
        expected = abs(reported - TARGET_WORDS)
        print(f"  修正版句型：總數 {reported}，差 {diff}"
              f"（和 120 比應為 {expected}，{'一致' if diff == expected else '不一致'}）")
        print(f"  報的總字數 {reported}，實際 {by_space}（空白分隔），差 {reported - by_space:+d}")
    elif over:
        first, second = int(over.group(1)), int(over.group(2))
        if first == second:
            reading = "兩個數字相同（照字面套範本）"
        elif first == UPPER_LIMIT:
            reading = f"第一個數字剛好是上限 {UPPER_LIMIT}，分不出是總字數還是上限"
        elif first - TARGET_WORDS == second:
            reading = "第一個數字是總字數，第二個是超過 120 的字數"
        else:
            reading = "兩個數字的關係對不上"
        print(f"  「Plus de」：{first}、{second}，{reading}")
        if first not in (second, UPPER_LIMIT):
            print(f"  報的總字數 {first}，實際 {by_space}（空白分隔）"
                  f"／{by_apostrophe}（撇號拆開），差 {first - by_space:+d}"
                  f"／{first - by_apostrophe:+d}")
    elif under:
        print(f"  「Il manque」：{under.group(1)}")
    else:
        print("  沒有照範本寫「Plus de … mots écrits」「Il manque … mots」或「Le texte compte … mots」")


def optimized_text(lines):
    """去掉空行、模型自報字數的行、結尾的提問。"""
    kept = []
    self_count = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        found = SELF_COUNT.match(stripped)
        if found:
            self_count = int(found.group(1))
            continue
        if stripped.endswith("?"):
            continue
        kept.append(stripped)
    return " ".join(kept), self_count


def check_file(path, student_words, reference):
    text = normalize(path.read_text(encoding="utf-8"))
    sections = split_sections(text)
    print(f"== {path.name}")

    missing = [title for key, title in HEADINGS if key not in sections]
    print(f"標題：{len(HEADINGS) - len(missing)}/{len(HEADINGS)}"
          + (f"，缺 {'、'.join(missing)}" if missing else ""))

    annotated = sections.get("annotated", [])
    warnings, self_reported = check_warnings(annotated)
    no_reason = [target for target, reason in warnings if reason is None]
    verdict = "符合" if len(warnings) <= MAX_WARNINGS else "超過"
    print(f"⚠️：{len(warnings)} 個（prompt 要求少於 12，{verdict}）"
          + (f"；模型自己報 {self_reported}" if self_reported is not None else ""))
    print(f"沒附理由的 ⚠️：{len(no_reason)}"
          + (f"（{'；'.join(no_reason)}）" if no_reason else ""))
    for i, (target, reason) in enumerate(warnings, 1):
        print(f"  {i:2d}. {target} ← {reason or '（無理由）'}")

    silent = unmarked_changes(annotated, reference)
    print(f"批改段落裡沒標 ⚠️ 的改動：{len(silent)} 處（忽略標點、大小寫；"
          "字序對調算一處；結果由人確認）")
    for ref_part, hyp_part in silent:
        print(f"  原文「{ref_part}」→ 模型「{hyp_part}」")

    for label, marker in (("☑️", CHECK), ("✅", DONE)):
        items = []
        for line in annotated:
            for segment in marker_segments(line, marker):
                word, bracketed = marked_text(segment)
                items.append(word if bracketed else f"{word}…（無方括號）")
        print(f"{label}：{len(items)} 個：" + "；".join(items))

    print("字數統計：")
    check_count_section(sections.get("count", []), student_words)

    low, high = OPTIMIZED_RANGE
    for key, name in (("b1", "B1"), ("b2", "B2")):
        if key not in sections:
            continue
        body, self_count = optimized_text(sections[key])
        by_space, by_apostrophe = count_words(body)
        verdict = "符合" if low <= by_space <= high else "不符合"
        print(f"{name} 優化版本：{by_space} 字（空白分隔，{low}-{high} {verdict}）"
              f"，撇號拆開 {by_apostrophe}"
              + (f"；模型自己報 {self_count}" if self_count is not None else ""))
    print()


def main():
    parser = argparse.ArgumentParser(description="檢查批閱回覆的格式與數字")
    parser.add_argument("files", nargs="+", type=Path, help="UTF-8 文字檔")
    args = parser.parse_args()

    reference = load_reference()
    student_words = count_words(reference)
    print(f"學生原文（參考轉寫）：{student_words[0]} 字（空白分隔，計分用）"
          f"，{student_words[1]} 字（撇號拆開，只供參考）\n")
    for path in args.files:
        check_file(path, student_words, reference)


if __name__ == "__main__":
    main()
