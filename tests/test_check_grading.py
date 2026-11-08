#!/usr/bin/env python3
"""tools/bench/check_grading.py 的段落切分與優化版本字數測試。

只用 Python 標準函式庫：python3 -m unittest discover -s tests
測試資料是自己寫的句子，不含學生作文；不讀 ../local-first-ai。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "bench"))

import check_grading as cg  # noqa: E402


class TestSplitSections(unittest.TestCase):

    def test_標題獨立一行(self):
        text = "\n".join([
            "**原文轉錄與校對**",
            "Je suis ⚠️ content (accord).",
            "字數統計",
            "Le texte compte 3 mots, soit 117 mots de trop.",
        ])
        secs = cg.split_sections(text)
        self.assertEqual(secs["annotated"], ["Je suis ⚠️ content (accord)."])
        self.assertEqual(secs["count"], ["Le texte compte 3 mots, soit 117 mots de trop."])

    def test_標題和內容寫在同一行(self):
        # 2026-11-06 本機 Qwen 修正版第 1 次的寫法：原本整行超過 40 字元就不算標題，7 個標題全漏
        text = "\n".join([
            "- 原文轉錄與校對（含標記）： Je suis ⚠️ content (accord), et voilà une phrase assez longue.",
            "- 字數統計 : Le texte compte 156 mots, soit 36 mots de trop.",
            "- 優點 : ",
            "  1. 結構清晰",
            "- 以 B1 檢定為目標的優化版本（120-140字） : ",
            "  Une phrase.",
        ])
        secs = cg.split_sections(text)
        self.assertEqual(secs["annotated"],
                         ["Je suis ⚠️ content (accord), et voilà une phrase assez longue."])
        self.assertEqual(secs["count"], ["Le texte compte 156 mots, soit 36 mots de trop."])
        self.assertEqual(secs["strengths"], ["  1. 結構清晰"])
        self.assertEqual(secs["b1"], ["  Une phrase."])

    def test_沒有冒號的長句不當標題(self):
        text = "\n".join([
            "原文轉錄與校對",
            "x",
            "缺點",
            "優點是結構清楚、連接詞用得正確，而且整篇作文的論點從頭到尾都很一致，值得在下一版完整保留下來",
        ])
        secs = cg.split_sections(text)
        self.assertNotIn("strengths", secs)
        self.assertEqual(len(secs["weaknesses"]), 1)


class TestOptimizedText(unittest.TestCase):

    def 字數(self, lines):
        body, self_count = cg.optimized_text(lines)
        return cg.count_words(body)[0], self_count

    def test_標記與粗體不算字(self):
        lines = ["**☑️ D'une part**, les fans sont ✅ nombreux.",
                 "Dans la limite du raisonnable ☑️, c'est bien ✅."]
        n, _ = self.字數(lines)
        # D'une part, les fans sont nombreux. Dans la limite du raisonnable, c'est bien.
        self.assertEqual(n, 13)

    def test_分隔線不算字(self):
        n, _ = self.字數(["Une deux trois.", "---"])
        self.assertEqual(n, 3)

    def test_法文冒號前的空格不把冒號算成字(self):
        # ADR-012：只有標點的 token 不算字
        n, _ = self.字數(["Il y a deux raisons : la première."])
        self.assertEqual(n, 7)

    def test_自報字數可帶粗體或斜體(self):
        for line in ("(129 mots)", "*(129 mots)*", "**(129 mots)**"):
            n, self_count = self.字數(["Une deux trois.", line])
            self.assertEqual((n, self_count), (3, 129), line)

    def test_只去掉結尾的提問_本文的問句照算(self):
        lines = ["Pourquoi aimons-nous les idoles ?",
                 "Parce que nous rêvons.",
                 "(9 mots)",
                 "Souhaitez-vous un autre exercice ?"]
        n, self_count = self.字數(lines)
        # 本文 8 個字（「?」獨立不算，ADR-012）；模型自報的 9 原樣取出
        self.assertEqual((n, self_count), (8, 9))


class TestCountWords(unittest.TestCase):

    def test_法文排版的獨立標點不算字(self):
        text = "Pourquoi ? Parce que : « oui » ; enfin !"
        self.assertEqual(cg.count_words(text), (5, 5))

    def test_黏在字上的標點與撇號規則不變(self):
        # 「l'idole,」仍是空白分隔 1 個字、撇號拆開 2 個
        self.assertEqual(cg.count_words("l'idole, c'est 2026."), (3, 5))

    def test_單獨的撇號或破折號不算字(self):
        self.assertEqual(cg.count_words("un – deux ' trois"), (3, 3))


if __name__ == "__main__":
    unittest.main()
