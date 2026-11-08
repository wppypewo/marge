#!/usr/bin/env python3
"""tools/bench/run_grading_local.py 的端到端測試。

用標準函式庫的 http.server 起一個假的 OpenAI 相容伺服器，以子程序執行腳本。
證據目錄用暫存資料夾與自編內容，不讀 ../local-first-ai，也不連真的模型。
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "bench" / "run_grading_local.py"


def sse(*chunks):
    """把 chunk 串成 SSE 回應內容。"""
    lines = [f"data: {json.dumps(c, ensure_ascii=False)}\n\n" for c in chunks]
    return "".join(lines + ["data: [DONE]\n\n"]).encode()


def ok(text, finish="stop"):
    return (200, sse(
        {"choices": [{"delta": {"content": text}, "finish_reason": None}]},
        {"choices": [{"delta": {}, "finish_reason": finish}]},
        {"choices": [], "usage": {"completion_tokens": 3}},
    ))


class FakeServer:
    """依序回傳 replies 裡的 (狀態碼, 內容)，並記下每次收到的請求。"""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers["Content-Length"])
                outer.requests.append(json.loads(self.rfile.read(n)))
                status, body = outer.replies.pop(0)
                self.send_response(status)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/v1"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class TestRunGradingLocal(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "批閱prompts.md").write_text(
            "# 測試\n\n## C4-B1\n\n```text\n請批閱這份作文。\n```\n", encoding="utf-8")
        (self.dir / "參考轉寫_IMG_2968.md").write_text(
            "# 參考\n\n## 轉寫\n\nUne phrase de test.\n\n## 備註\n", encoding="utf-8")
        (self.dir / "IMG_2968.jpg").write_bytes(b"\xff\xd8fake")
        self.out = self.dir / "回覆.txt"

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, server, *extra, out=None):
        env = {**os.environ, "MARGE_EVIDENCE": str(self.dir)}
        cmd = [sys.executable, str(SCRIPT), "--base-url", server.url, "--label", "測試",
               "--thinking", "off", "--out", str(out or self.out), *extra]
        return subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)

    def serve(self, replies):
        server = FakeServer(replies)
        self.addCleanup(server.close)
        return server

    def test_三則都成功(self):
        server = self.serve([ok("好的"), ok("OCR 結果"), ok("批閱結果")])
        r = self.run_script(server)
        self.assertEqual(r.returncode, 0, r.stderr)
        text = self.out.read_text(encoding="utf-8")
        self.assertIn("好的\n\nOCR 結果\n\n批閱結果\n", text)
        meta = json.loads(self.out.with_suffix(".json").read_text(encoding="utf-8"))
        self.assertEqual(len(meta["turns"]), 3)
        self.assertTrue(meta["complete"])
        # 第三則帶參考轉寫，前兩則的回答都在對話裡，思考關閉
        last = server.requests[-1]
        self.assertEqual(last["messages"][-1]["content"], "Une phrase de test.")
        self.assertEqual([m["content"] for m in last["messages"] if m["role"] == "assistant"],
                         ["好的", "OCR 結果"])
        self.assertFalse(last["chat_template_kwargs"]["enable_thinking"])

    def test_第三則失敗時保留前兩則(self):
        server = self.serve([ok("好的"), ok("OCR 結果"), (500, b"boom")])
        r = self.run_script(server)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.out.exists(), "沒跑完不該寫出給 check_grading 用的 .txt")
        partial = self.dir / "回覆.partial.json"
        self.assertTrue(partial.exists(), r.stderr)
        meta = json.loads(partial.read_text(encoding="utf-8"))
        self.assertFalse(meta["complete"])
        self.assertEqual([t["answer"] for t in meta["turns"]], ["好的", "OCR 結果"])
        self.assertIn("500", meta["error"])

    def test_串流中的錯誤chunk要報錯(self):
        # llama-server 生成途中出錯時，會在 SSE 裡送 {"error": …}，沒有 finish_reason
        broken = (200, sse(
            {"choices": [{"delta": {"content": "OCR 只做了一半"}, "finish_reason": None}]},
            {"error": {"code": 500, "message": "context shift failed"}},
        ))
        server = self.serve([ok("好的"), broken])
        r = self.run_script(server)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.out.exists())
        meta = json.loads((self.dir / "回覆.partial.json").read_text(encoding="utf-8"))
        self.assertEqual(len(meta["turns"]), 1)
        self.assertIn("context shift failed", meta["error"])

    def test_out是json時拒絕執行(self):
        server = self.serve([])
        out = self.dir / "回覆.json"
        r = self.run_script(server, out=out)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(server.requests, [])
        self.assertFalse(out.exists())

    def test_被截斷時照寫但要警告(self):
        server = self.serve([ok("好的"), ok("OCR 結果"), ok("批閱寫到一半", finish="length")])
        r = self.run_script(server)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("第 3 則", r.stderr)
        self.assertIn("max-tokens", r.stderr)

    def test_圖片MIME依副檔名(self):
        (self.dir / "a.webp").write_bytes(b"RIFFfake")
        server = self.serve([ok("1"), ok("2"), ok("3")])
        r = self.run_script(server, "--image", str(self.dir / "a.webp"))
        self.assertEqual(r.returncode, 0, r.stderr)
        url = server.requests[1]["messages"][2]["content"][0]["image_url"]["url"]
        self.assertTrue(url.startswith("data:image/webp;base64,"), url[:40])

    def test_不是圖片的檔案拒絕執行(self):
        (self.dir / "a.txt").write_text("x", encoding="utf-8")
        server = self.serve([])
        r = self.run_script(server, "--image", str(self.dir / "a.txt"))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(server.requests, [])


if __name__ == "__main__":
    unittest.main()
