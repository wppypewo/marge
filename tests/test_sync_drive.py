#!/usr/bin/env python3
"""tools/report/sync_drive.sh 的測試。

雲端資料夾用 MARGE_DRIVE_DIR 指到暫存目錄；PATH 前面放假的 pgrep（回報 Google Drive 在執行）
和假的 open（被呼叫就失敗），所以不會碰到真的 Google Drive。
"""

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "report" / "sync_drive.sh"


class TestSyncDrive(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.local, self.drive, bin_dir = root / "local", root / "drive", root / "bin"
        for d in (self.local, self.drive, bin_dir):
            d.mkdir()
        (bin_dir / "pgrep").write_text("#!/bin/sh\nexit 0\n")
        (bin_dir / "open").write_text("#!/bin/sh\necho 不該啟動 Google Drive >&2\nexit 1\n")
        for f in bin_dir.iterdir():
            f.chmod(0o755)
        self.env = {**os.environ, "MARGE_DRIVE_DIR": str(self.drive),
                    "PATH": f"{bin_dir}:{os.environ['PATH']}"}
        self.env.pop("MARGE_FORCE", None)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name, local=None, cloud=None, cloud_newer=True):
        """建立本機與雲端檔案；cloud_newer 決定哪一邊的修改時間比較新。"""
        now = time.time()
        if local is not None:
            (self.local / name).write_text(local, encoding="utf-8")
            os.utime(self.local / name, (now, now - 100 if cloud_newer else now))
        if cloud is not None:
            (self.drive / name).write_text(cloud, encoding="utf-8")
            os.utime(self.drive / name, (now, now if cloud_newer else now - 100))

    def sync(self, *names, force=False):
        env = dict(self.env, **({"MARGE_FORCE": "1"} if force else {}))
        return subprocess.run(["bash", str(SCRIPT), *names], cwd=self.local, env=env,
                              capture_output=True, text=True, timeout=30)

    def cloud(self, name):
        return (self.drive / name).read_text(encoding="utf-8")

    def test_雲端較新且內容不同時一個都不寫(self):
        self.put("a.md", local="本機新版", cloud="舊", cloud_newer=False)
        self.put("b.md", local="本機", cloud="雲端被人改過", cloud_newer=True)
        r = self.sync("a.md", "b.md")
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("b.md", r.stderr)
        self.assertEqual(self.cloud("a.md"), "舊")
        self.assertEqual(self.cloud("b.md"), "雲端被人改過")

    def test_MARGE_FORCE可以覆寫(self):
        self.put("b.md", local="本機", cloud="雲端被人改過", cloud_newer=True)
        r = self.sync("b.md", force=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cloud("b.md"), "本機")

    def test_上次同步後沒人動過可以照常寫(self):
        # cat > 覆寫後雲端時間比本機新，但內容相同
        self.put("a.md", local="同一版", cloud="同一版", cloud_newer=True)
        self.put("n.md", local="新檔")
        r = self.sync("a.md", "n.md")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cloud("n.md"), "新檔")

    def test_本機較新照常覆寫(self):
        self.put("a.md", local="本機新版", cloud="舊", cloud_newer=False)
        r = self.sync("a.md")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cloud("a.md"), "本機新版")
        self.assertIn("OK a.md", r.stdout)

    def test_check只列出不寫(self):
        self.put("a.md", local="本機新版", cloud="舊", cloud_newer=False)
        r = self.sync("--check")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cloud("a.md"), "舊")


if __name__ == "__main__":
    unittest.main()
