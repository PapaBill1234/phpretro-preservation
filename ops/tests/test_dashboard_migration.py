"""Dashboard migration projections use typed evidence, never merge inference."""
import importlib.util
import json
import hashlib
import http.client
import http.server
import threading
import time
from unittest.mock import patch
import unittest
from harness import REPO, tmpdir
import progress

spec = importlib.util.spec_from_file_location("migration_dashboard", REPO / "ops/dashboard/server.py")
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
gateway_spec = importlib.util.spec_from_file_location("migration_gateway", REPO / "ops/dashboard/gateway.py")
g = importlib.util.module_from_spec(gateway_spec)
gateway_spec.loader.exec_module(g)


class ParityTests(unittest.TestCase):
    def setUp(self):
        self.root = tmpdir("dashboard-assessment-")
        (self.root / "stage3-original-phpretro").mkdir()
        (self.root / "stage3-original-phpretro/profile.php").write_text("<?php // fixture")
        (self.root / "source.go").write_text("package fixture\n")
        self.ops = tmpdir("dashboard-state-")
        (self.ops / "state").mkdir()
        self.units = [{"id":"F1", "status":"merged", "title":"profile.php"}]

    def assess(self, classification):
        (self.ops / "state/progress.json").write_text(json.dumps({"available":True, "units":[{
            "id":"F1", "classification":classification, "assessment_current":True,
            "evidence":[{"path":"source.go", "fingerprint":progress.fingerprint(self.root / "source.go")}]}]}))

    def parity(self):
        with patch.object(d, "REPO", self.root), patch.object(d, "OPS", self.ops):
            return d.parity(self.units)

    def test_merge_and_citation_do_not_prove_implementation(self):
        result = self.parity()
        self.assertEqual(result["implemented_percent"], 0)
        self.assertEqual(result["routes"][0]["status"], "not assessed")
        self.assess("scaffold")
        self.assertEqual(self.parity()["routes"][0]["status"], "scaffold")
        self.assertEqual(self.parity()["implemented_percent"], 0)

    def test_only_current_reviewed_evidence_can_support_classification(self):
        self.assess("implemented")
        self.assertEqual(self.parity()["implemented_percent"], 100)
        self.assertEqual(self.parity()["verified_percent"], 0)
        (self.root / "source.go").write_text("package changed\n")
        self.assertEqual(self.parity()["implemented_percent"], 0)
        self.assess("verified")
        self.assertEqual(self.parity()["verified_percent"], 100)


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.root = tmpdir("gateway-session-")
        self.patches = [patch.object(g,"ROOT",self.root),patch.object(g,"DB",self.root / "access.sqlite3")]
        for item in self.patches: item.start()
        self.token = "synthetic-session-token-for-test-only-1234567890"
        with g.db() as db:
            db.execute("INSERT INTO sessions VALUES(?,?)",(hashlib.sha256(self.token.encode()).hexdigest(),time.time()+60))
        class FixtureHandler(g.Handler):
            def proxy(handler): handler.send(200,{"fixture":True})
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1",0),FixtureHandler)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(2)
        for item in reversed(self.patches): item.stop()

    def request(self, method="GET", **headers):
        conn = http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=3)
        try:
            conn.request(method,"/api/state",headers=headers)
            response = conn.getresponse(); response.read()
            return response.status
        finally: conn.close()

    def test_protected_api_requires_live_session_and_allowed_host(self):
        self.assertEqual(self.request(),401)
        cookie = "pd_session="+self.token
        self.assertEqual(self.request(Cookie=cookie),200)
        self.assertEqual(self.request(Cookie=cookie,Host="untrusted.invalid"),403)
        with g.db() as db: db.execute("UPDATE sessions SET expires=?",(time.time()-1,))
        self.assertEqual(self.request(Cookie=cookie),401)

    def test_mutation_rejects_cross_origin_requests_even_with_session(self):
        cookie = "pd_session="+self.token
        self.assertEqual(self.request("POST",Cookie=cookie,Origin="https://untrusted.invalid"),403)
        origin = "http://127.0.0.1:"+str(self.server.server_port)
        self.assertEqual(self.request("POST",Cookie=cookie,Origin=origin),200)


if __name__ == "__main__": unittest.main()
