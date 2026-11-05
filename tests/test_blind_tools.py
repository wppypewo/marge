"""盲評工具（make_blind_pack、make_blind_html、fill_blind_md）的測試，只用合成資料。

執行：python3 -m unittest tests.test_blind_tools
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BENCH = Path(__file__).resolve().parents[1] / "tools" / "bench"
sys.path.insert(0, str(BENCH))
from make_blind_html import parse_pack, signature  # noqa: E402

# 合成盲評表：錯誤清單一句、模型 A 一個 ⚠️、一處沒標改動、一個標記
PACK = """# 盲評表（測試）

## 1. 錯誤清單（先填，再看模型）

| 段 | 原句 | 學生寫錯的地方 |
|---|---|---|
| 1 | Je suis allé a Paris. | E1：a → à |

## 模型 A

### 批改後的原文

> Je suis allé ⚠️à (介系詞) Paris.

### ⚠️ 逐條判斷

| # | 改成 | 理由 | 改得對 | 理由合理 | 對應錯誤 |
|---|---|---|---|---|---|
| 1 | à | 介系詞 |  |  |  |

### 沒標 ⚠️ 就改掉的地方

| 參考轉寫 | 模型版本 | 改得對 | 對應錯誤 |
|---|---|---|---|
| allé | allée |  |  |

### ☑️／✅ 標記

| 標記 | 字詞 | 類別 | 用得對 |
|---|---|---|---|
| ☑️ | Paris |  |  |
"""


def results(sig):
    """HTML 匯出 JSON 的最小形狀；sig 為 None 時不放簽章。"""
    data = {
        "source": "pack.md",
        "models": [{
            "letter": "A",
            "warn": [{"ok": "對", "reason_ok": "合理", "errs": ["E1"]}],
            "silent": [{"ok": "錯", "errs": []}],
            "marks": [{"cat": "拼字", "use": "對"}],
        }],
    }
    if sig is not None:
        data["sig"] = sig
    return data


def run(script, *args, env=None):
    return subprocess.run([sys.executable, "-I", str(BENCH / script), *map(str, args)],
                          capture_output=True, text=True, timeout=20, env=env)


class SignatureTest(unittest.TestCase):
    def test_signature_changes_with_items(self):
        sig = signature(parse_pack(PACK))
        self.assertRegex(sig, r"^[0-9a-f]{12}$")
        self.assertEqual(sig, signature(parse_pack(PACK)))
        self.assertNotEqual(sig, signature(parse_pack(PACK.replace("| allé | allée |", "| suis | sommes |"))))


class FillTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.pack = self.dir / "pack.md"
        self.pack.write_text(PACK, encoding="utf-8")
        self.out = self.dir / "out.md"

    def tearDown(self):
        self.tmp.cleanup()

    def fill(self, data):
        js = self.dir / "r.json"
        js.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return run("fill_blind_md.py", self.pack, js, "--out", self.out)

    def test_matching_signature_fills(self):
        r = self.fill(results(signature(parse_pack(PACK))))
        self.assertEqual(r.returncode, 0, r.stderr)
        text = self.out.read_text(encoding="utf-8")
        self.assertIn("| 1 | à | 介系詞 | 對 | 合理 | E1 |", text)
        self.assertIn("| ☑️ | Paris | 拼字 | 對 |", text)

    def test_mismatched_signature_refuses(self):
        r = self.fill(results("000000000000"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("簽章", r.stderr)
        self.assertFalse(self.out.exists())

    def test_missing_signature_warns_but_fills(self):
        r = self.fill(results(None))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("沒有簽章", r.stderr)
        self.assertTrue(self.out.exists())


class PackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        # 合成參考轉寫，讓 make_blind_pack 不讀真的評測證據
        (self.dir / "參考轉寫_IMG_2968.md").write_text(
            "# 參考轉寫\n\n## 轉寫\n\nJe suis allé a Paris.\n\n## 備註\n", encoding="utf-8")
        self.reply = self.dir / "reply.txt"
        self.reply.write_text("Je suis allé ⚠️à (介系詞) Paris.\n", encoding="utf-8")
        self.env = {**os.environ, "MARGE_EVIDENCE": str(self.dir)}

    def tearDown(self):
        self.tmp.cleanup()

    def test_out_equal_key_rejected(self):
        same = self.dir / "same.md"
        r = run("make_blind_pack.py", self.reply, "--out", same, "--key",
                self.dir / "." / "same.md", env=self.env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("同一個檔", r.stderr)
        self.assertFalse(same.exists())

    def test_key_written_before_pack(self):
        # 對照檔寫不成時，不能留下沒有對照的盲評表
        out = self.dir / "pack.md"
        r = run("make_blind_pack.py", self.reply, "--out", out, "--key",
                self.dir / "沒有這個資料夾" / "key.md", env=self.env)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(out.exists())

    def test_normal_run_writes_both(self):
        out, key = self.dir / "pack.md", self.dir / "key.md"
        r = run("make_blind_pack.py", self.reply, "--out", out, "--key", key, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("## 模型 A", out.read_text(encoding="utf-8"))
        self.assertIn("reply.txt", key.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
