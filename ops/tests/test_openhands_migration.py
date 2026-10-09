"""Migration policy/accounting regressions; no provider, Docker or live state."""
from __future__ import annotations
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from harness import tmpdir
import integrity as control
import runtime_policy
import worker
import telemetry
import orchestrator as o
import import_brief
import dashboard_state
import sandbox
import sys
sys.path.insert(0, str(Path(o.__file__).parent / "openhands"))
from runner import normalized_usage


class PolicyTests(unittest.TestCase):
    def test_second_attempt_deepseek_does_not_look_like_fourth_attempt(self):
        u = {"id":"F99","model":o.MODEL["deepseek"],"attempts":2,"tokens":0}
        with (patch.object(o,"jev_triage",return_value={"action":"retry_same","source":"rule"}) as tri,
              patch.object(o,"event"), patch.object(o,"telemetry_event")):
            o._apply_failure_triage(u,{},"failed",{})
        self.assertFalse(tri.call_args.args[-1])
    def test_no_automatic_sol_and_three_review_families(self):
        policy = runtime_policy.load()
        self.assertFalse(policy["automatic_planning"])
        self.assertFalse(policy["automatic_sol"])
        with self.assertRaises(control.IntegrityError):
            runtime_policy.model_settings("gpt-6.1-sol")
        for author in (o.MODEL["luna"], o.MODEL["deepseek"], o.MODEL["haiku"]):
            first = o.reviewer_model_for(author)
            second = o.second_reviewer_model(author, first)
            self.assertEqual(len({control.model_family(m) for m in (author, first, second)}), 3)
            self.assertEqual(o.review_fallback(second, author, (first,)), "")
        self.assertNotIn("sol", o.LADDER)

    def test_paid_planning_denied_even_with_validation(self):
        with patch.object(runtime_policy, "ready", return_value=True):
            for role in ("planner", "audit"):
                self.assertFalse(o.paid_allowed({"day":o.now()[:10],"tokens_today":0,"merged_today":0}, None, role))

    def test_validation_binds_source_image_models_and_age(self):
        root = tmpdir("policy-validation-")
        stamp = root / "state/openhands-validation.json"
        data = {"implementation_sha256": runtime_policy.fingerprint(), "passed": True,
                "validated_at": o.time.time(), "vulnerability_snapshot_at":o.time.time(), "image_id": "image-a",
                "checks": {k:True for k in ("foundation","ops","frontend","isolation","lifecycle","resources","provider")},
                "models":{"gpt-6-luna":{"tool_calls":True,"usage":True}}}
        control.atomic_json(stamp, data)
        with patch.object(runtime_policy, "OPS", root), patch.object(runtime_policy.subprocess, "check_output", return_value="image-a\n"):
            self.assertTrue(runtime_policy.ready("gpt-6-luna"))
            self.assertFalse(runtime_policy.ready("claude-haiku-5-5"))
            with patch.object(runtime_policy, "fingerprint", return_value="changed"):
                self.assertFalse(runtime_policy.ready())
            with patch.object(runtime_policy.subprocess, "check_output", return_value="changed-image"):
                self.assertFalse(runtime_policy.ready())
            data["validated_at"] = 0
            control.atomic_json(stamp, data)
            self.assertFalse(runtime_policy.ready())

    def test_same_family_second_cached_approval_is_rejected(self):
        root = tmpdir("review-family-")
        rid = control.identity()
        u = {"id":"F99","model":o.MODEL["luna"],"review_model":o.MODEL["deepseek"],
             "review2_model":o.MODEL["deepseek"],"review2_id":rid}
        control.atomic_json(root / ("F99-review2-" + rid + ".verdict.json"),
                            {"unit":"F99","head":"head","rc":0,"verdict":"pass","model":o.MODEL["deepseek"]})
        with patch.object(o, "LOG_DIR", root):
            self.assertFalse(o.approval_valid(u,"review2","head"))


class BriefTests(unittest.TestCase):
    def brief(self):
        return {"schema":"phpretro.brief.v1","planning_source":"subscription-codex","base_commit":"head",
                "units":[{"id":"F99","title":"bounded","size":"S","paths":["internal/x"],
                          "acceptance":["observable"],"tests":["go test ./internal/x"],"fixtures":["synthetic"],
                          "allowed_models":["gpt-6-luna"],"token_cap":3000000,"depends_on":[]}]}
    def test_import_preserves_counters_and_rejects_bad_scope_base_cycle(self):
        doc = self.brief()
        road = {"F99":{"status":"parked","attempts":3,"tokens":123,"depends_on":[]}}
        result = import_brief.validate(doc,road,"head")[0]
        self.assertEqual((result["attempts"],result["tokens"]),(3,123))
        self.assertTrue(result["implementation_ready"])
        saved = o.parse_yaml("units:\n" + o.dump_unit_yaml(result))["units"][0]
        self.assertEqual(saved["allowed_models"],["gpt-6-luna"])
        self.assertEqual(saved["brief_base"],"head")
        for changed in ({"paths":["ops/worker.py"]},{"allowed_models":["gpt-6.1-sol"]},{"depends_on":["F99"]}):
            bad = self.brief();bad["units"][0].update(changed)
            with self.assertRaises(control.IntegrityError): import_brief.validate(bad,road,"head")
        with self.assertRaises(control.IntegrityError): import_brief.validate(doc,road,"other-head")


class UsageTests(unittest.TestCase):
    def test_spending_guard_accounts_for_baseline_and_rejects_unknown_cost(self):
        root = tmpdir("quote-budget-")
        st = {"day":o.now()[:10],"tokens_today":30000000,"merged_today":0}
        unit = {"id":"F99","tokens":0}
        with (patch.object(o,"paid_allowed",return_value=True), patch.object(o,"STATE_DIR",root),
              patch.object(o,"STATE_JSON",root / "state.json")):
            with self.assertRaises(o.BudgetDenied): o.admit_paid(st,unit,"builder")
            control.append_record(root / "runs.jsonl",{"record_type":"run","run_id":"fixture","ts_end":o.now(),
                                 "charged_tokens":123,"cost_estimate":None,"usage_complete":False})
            st["tokens_today"] = 123
            with self.assertRaises(o.BudgetDenied): o.admit_paid(st,unit,"builder")
        self.assertFalse(st["reservations"])
    def test_cache_read_write_normalized_once_reasoning_inside_output(self):
        metrics = SimpleNamespace(accumulated_token_usage=SimpleNamespace(prompt_tokens=100,completion_tokens=20,
                     cache_read_tokens=30,cache_write_tokens=10,reasoning_tokens=5), token_usages=[1])
        usage = normalized_usage(metrics,{"input_includes_cache":True},started=1,finished=1,complete=True)
        self.assertEqual(usage["input_tokens"],60)
        self.assertEqual(usage["total_tokens"],120)
        self.assertTrue(usage["usage_complete"])
        self.assertFalse(normalized_usage(metrics,{"input_includes_cache":True},started=2,finished=1,complete=True)["usage_complete"])

    def test_openhands_partial_sidecar_stays_partial_and_never_uses_hermes_db(self):
        root = tmpdir("openhands-usage-")
        usage = root / "usage.json"
        usage.write_text(json.dumps({"runtime":"openhands","total_tokens":17,"api_calls":1,"usage_complete":False}))
        with patch.object(worker.sqlite3,"connect",side_effect=AssertionError("no interactive DB access")):
            result = worker.usage_snapshot(usage,root / "state.db","RUN ID fixture","openhands")
            self.assertFalse(result["usage_complete"])
            self.assertEqual(o.accounted_usage(result)["accounted_tokens"],o.TIMEOUT_FALLBACK_TOKENS)
            missing = worker.usage_snapshot(root / "missing",root / "state.db","marker","openhands")
            self.assertFalse(missing["usage_complete"])
            self.assertEqual(missing["runtime"],"openhands")
            record = telemetry.build_run(ts_start=o.now(),ts_end=o.now(),role="builder",model="gpt-6-luna",usage=missing)
            self.assertEqual(record["runtime"],"openhands")
            self.assertIsNone(record["cost_estimate"])

    def test_rotated_runs_overlay_outcomes_without_reservations_or_duplicate_charges(self):
        root = tmpdir("openhands-ledger-")
        row = {"record_type":"run","run_id":"fixture","charged_tokens":123,"cost_estimate":None,"usage_complete":False}
        control.append_record(root / "runs-2026-09.jsonl",row)
        control.append_record(root / "runs.jsonl",{"record_type":"reservation","run_id":"other"})
        control.append_record(root / "runs.jsonl",row)
        control.append_record(root / "runs.jsonl",{"record_type":"outcome","run_id":"fixture","outcome":"gate_failed"})
        rows = list(telemetry.read_runs(root / "runs.jsonl"))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["outcome"],"gate_failed")
        self.assertEqual(telemetry.run_total(rows[0]),123)
        self.assertIsNone(dashboard_state.run_cost(rows[0]))

    def test_malformed_ledger_cannot_be_silently_dropped(self):
        root = tmpdir("malformed-ledger-");(root / "runs.jsonl").write_text('{"partial":')
        with self.assertRaises(ValueError): list(telemetry.read_runs(root / "runs.jsonl"))


class ExportTests(unittest.TestCase):
    def box(self):
        root = tmpdir("sandbox-export-")
        with patch.object(sandbox,"OPS",root):
            box = sandbox.Sandbox(control.identity(),root / "source",writable=True,paths=["internal/x/*.go"])
        box.source.mkdir();(box.stage / "internal/x").mkdir(parents=True)
        return box
    def test_scope_failure_exports_nothing(self):
        box = self.box()
        (box.stage / "internal/x/ok.go").write_text("package x")
        (box.stage / "ops").mkdir();(box.stage / "ops/bad.py").write_text("bad")
        with patch.object(sandbox,"cleanup"),patch.object(sandbox.subprocess,"run"):
            with self.assertRaises(control.IntegrityError): box.export()
        self.assertFalse((box.source / "internal/x/ok.go").exists())
    def test_allowed_binary_artifacts_and_symlink_rejection(self):
        box = self.box();(box.stage / "internal/x/ok.go").write_bytes(b"\xff\x00")
        with patch.object(sandbox,"cleanup"),patch.object(sandbox.subprocess,"run"):
            self.assertEqual(box.export(),["internal/x/ok.go"])
        self.assertEqual((box.source / "internal/x/ok.go").read_bytes(),b"\xff\x00")
        (box.stage / "internal/x/link.go").symlink_to("/etc/passwd")
        with self.assertRaises(control.IntegrityError): sandbox.safe_files(box.stage)


class AdmissionTests(unittest.TestCase):
    def sample(self, state, now, *, available=4 * 1024 * 1024, busy=False):
        policy = runtime_policy.load()
        state["host_cpu_sample"] = [0, 0]
        files = {"/proc/meminfo":f"MemAvailable: {available} kB\n",
                 "/proc/stat":"cpu 90 0 0 10 0 0 0 0\n" if busy else "cpu 0 0 0 100 0 0 0 0\n",
                 "/proc/pressure/memory":"some avg10=0.00\nfull avg10=0.00\n"}
        with patch.object(Path, "read_text", lambda path, *args, **kwargs: files[str(path)]), patch.object(sandbox.time, "time", return_value=now), patch.object(runtime_policy, "load", return_value=policy):
            return sandbox.admission_width(state)

    def test_sustained_pressure_reduces_width_and_stable_window_restores_it(self):
        state = {}
        self.assertEqual(self.sample(state,100,busy=True),2)
        self.assertEqual(self.sample(state,121,busy=True),1)
        self.assertEqual(self.sample(state,200),1)
        self.assertEqual(self.sample(state,499),1)
        self.assertEqual(self.sample(state,501),2)

    def test_critical_headroom_defers_new_work_then_requires_stability(self):
        state = {}
        self.assertEqual(self.sample(state,100,available=1024*1024),0)
        self.assertEqual(self.sample(state,101),1)
        self.assertEqual(self.sample(state,402),2)


if __name__ == "__main__": unittest.main()
