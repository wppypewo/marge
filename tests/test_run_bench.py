"""run_bench.py 的測試：用本機假伺服器模擬串流 API，確認單題失敗不會讓整輪結果消失。

執行：python3 -m unittest tests.test_run_bench
"""

import csv
import json
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "bench" / "run_bench.py"
OK = b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\ndata: [DONE]\n\n'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        prompt = body["messages"][0]["content"]
        if prompt == "BADSTATUS":
            # 狀態列壞掉 → http.client.BadStatusLine（HTTPException，不是 OSError）
            self.wfile.write(b"garbage\r\n\r\n")
            self.close_connection = True
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        payload = {"BADJSON": b"data: {broken\n\n", "BADUTF8": b"data: \xff\xfe\n\n"}.get(prompt, OK)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if prompt == "SLOW":
            self.server.slow_started.set()
            time.sleep(10)
        self.wfile.write(payload)


class RunBenchTest(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.server.slow_started = threading.Event()
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def args(self, prompts):
        tests = [{"id": f"T{i}", "name": p, "prompt": p, "check": ""} for i, p in enumerate(prompts, 1)]
        path = self.dir / "prompts.json"
        path.write_text(json.dumps(tests), encoding="utf-8")
        return [sys.executable, "-I", str(SCRIPT), "--base-url", self.url, "--model", "m",
                "--label", "測試", "--prompts", str(path), "--out", str(self.dir / "out"),
                "--timeout", "15"]

    def rows(self):
        with (self.dir / "out" / "summary.csv").open(encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    def test_bad_stream_does_not_stop_run(self):
        r = subprocess.run(self.args(["OK", "BADJSON", "BADUTF8", "BADSTATUS", "OK"]),
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = self.rows()
        self.assertEqual([row["題號"] for row in rows], ["T1", "T2", "T3", "T4", "T5"])
        self.assertEqual([bool(row["錯誤"]) for row in rows], [False, True, True, True, False])
        md = next((self.dir / "out").glob("*.md")).read_text(encoding="utf-8")
        self.assertIn("## T5 OK", md)

    def test_ctrl_c_keeps_finished_tests(self):
        p = subprocess.Popen(self.args(["OK", "SLOW", "OK"]),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertTrue(self.server.slow_started.wait(15))
        p.send_signal(signal.SIGINT)
        out, err = p.communicate(timeout=15)
        self.assertEqual(p.returncode, 130, err)
        self.assertEqual([row["題號"] for row in self.rows()], ["T1"])
        md = next((self.dir / "out").glob("*.md")).read_text(encoding="utf-8")
        self.assertIn("手動中斷", md)
        self.assertNotIn("## T3", md)


if __name__ == "__main__":
    unittest.main()
