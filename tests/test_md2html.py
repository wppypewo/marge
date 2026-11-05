#!/usr/bin/env python3
"""tools/report/md2html.py 的測試。只用標準函式庫，測試資料是自編的 Markdown。"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "report" / "md2html.py"


def run(md, timeout=3):
    """以子程序轉換；舊版遇到「#5」這類行會無限迴圈，所以設逾時。"""
    with tempfile.TemporaryDirectory() as d:
        src, dst = Path(d) / "in.md", Path(d) / "out.html"
        src.write_text(md, encoding="utf-8")
        subprocess.run([sys.executable, "-I", str(SCRIPT), str(src), str(dst)],
                       check=True, timeout=timeout, capture_output=True)
        return dst.read_text(encoding="utf-8")


class TestMd2Html(unittest.TestCase):

    def test_井號開頭但不是標題的行當段落(self):
        md = "# 標題\n\n## 1. 第一節\n\n#5 是題號\n##### 五級標題不支援\n\n結尾段落\n"
        out = run(md)
        self.assertIn("<p>#5 是題號 ##### 五級標題不支援</p>", out)
        self.assertIn("<p>結尾段落</p>", out)

    def test_一般結構照舊(self):
        md = ("# 報告\n\n說明 **粗體** 與 `code`\n\n## 1. 一\n\n### 1.1 小節\n\n"
              "- 項目 [連結](x.md)\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n## 附錄 A 資料\n\n```\n<raw>\n```\n")
        out = run(md)
        self.assertIn("<p>說明 <strong>粗體</strong> 與 <code>code</code></p>", out)
        self.assertIn('<h2 id="h0">1. 一</h2>', out)
        self.assertIn('<div class="sub">1.1 小節</div>', out)
        self.assertIn("<li>項目 連結</li>", out)
        self.assertIn("<td>1</td><td>2</td>", out)
        self.assertIn('<h2 id="h2" class="newpage">附錄 A 資料</h2>', out)
        self.assertIn("<pre><code>&lt;raw&gt;</code></pre>", out)
        # 目錄放在第一個 h2 之前
        self.assertLess(out.index('<nav class="toc">'), out.index('<h2'))


if __name__ == "__main__":
    unittest.main()
