"""Tests for SIDScope's resource portal, pure-Python Pyodide workbench, and local HTTP demo."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import threading
import unittest
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "demo") not in sys.path:
    sys.path.insert(0, str(ROOT / "demo"))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import browser_example
import serve_demo


class SidScopePortalTests(unittest.TestCase):
    def test_browser_example_verifies_8_tables_rq1_to_rq3_and_c1_failure(self) -> None:
        payload = browser_example.run_example()
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(len(payload["table5_profiles"]), 8)
        self.assertEqual(len(payload["table10_traces"]), 3)
        self.assertEqual(len(payload["dact_handoff"]), 5)
        self.assertTrue(payload["dact_gate_live"]["threshold_match"])
        self.assertTrue(all(s["pass_all"] for s in payload["dact_gate_live"]["seeds"]))
        self.assertTrue(payload["c1_failure_check"]["c1_failed"])
        # Live cross-stratum A_b > S_b proof
        tail = next(r for r in payload["rq1_live_ab_sb"]["d4"] if r["bucket"] == "tail")
        self.assertGreater(tail["allocation_ab"], tail["global_singleton_sb"])
        self.assertGreater(tail["cross_stratum_shared"], 0)
        # Live D7 resolver comparison
        sim = payload["d7_live_sim"]
        self.assertGreater(sim["path_survival"], sim["singleton_credit"])
        self.assertGreater(sim["popularity_resolver"], sim["singleton_credit"])

    def test_custom_csv_c1_mismatch_fails_closed(self) -> None:
        bad = "item_id,sid_level_0,sid_level_1,sid\n1,1,2,1-9\n"
        with self.assertRaises(ValueError) as ctx:
            browser_example.audit_custom_csv(bad)
        self.assertIn("C1 mismatch", str(ctx.exception))

    def test_local_http_demo_endpoints_and_security(self) -> None:
        server = serve_demo.ThreadingHTTPServer(("127.0.0.1", 0), serve_demo.Handler)
        server.bind_host = "127.0.0.1"
        server.workflow_lock = threading.Lock()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with request.urlopen(f"{base}/health", timeout=5) as resp:
                health = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(health["status"], "ready")
                self.assertEqual(health["version"], "2.0.0")

            with request.urlopen(f"{base}/", timeout=5) as resp:
                html = resp.read().decode("utf-8")
                self.assertIn("SIDScope", html)
                self.assertIn("nonce-", resp.headers.get("Content-Security-Policy", ""))

            req = request.Request(
                f"{base}/api/audit",
                data=json.dumps({"sid_csv": "item_id,sid_0,sid_1\n1,2,3\n2,2,3\n3,4,5\n"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=5) as resp:
                audit_resp = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(audit_resp["report"]["d5"]["items"], 3)
                self.assertEqual(audit_resp["report"]["d5"]["unique_sid"], 2)

            bad_origin = request.Request(
                f"{base}/api/run",
                data=b"{}",
                headers={"Content-Type": "application/json", "Origin": "https://evil.example"},
                method="POST",
            )
            with self.assertRaises(error.HTTPError) as ctx:
                request.urlopen(bad_origin, timeout=5)
            self.assertEqual(ctx.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
