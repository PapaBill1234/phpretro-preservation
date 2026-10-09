"""Maintenance A fault injection. No providers, GitHub mutations or workers."""
import copy
import json
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from harness import tmpdir
import orchestrator as o
import integrity as c
import telemetry as tel


def unit(uid="X", **kw):
    return {"id": uid, "title": "fixture", "size": "S", "status": "todo",
            "paths": ["internal/x"], "depends_on": [], "tokens": 0,
            "acceptance": ["synthetic behavior"], "tests": ["go test ./internal/x/..."],
            "attempts": 0, "model": o.MODEL["luna"], **kw}


def state(**kw):
    return {"day": o.now()[:10], "tokens_today": 0, "merged_today": 0,
            "events": [], **kw}


class Isolated(unittest.TestCase):
    def setUp(self):
        self.root = tmpdir("maintenance-")
        self.ops = self.root / "ops"
        self.repo = self.root / "repo"
        self.repo.mkdir()
        values = {"OPS": self.ops, "STATE_DIR": self.ops / "state", "LOG_DIR": self.ops / "logs",
                  "BRIEF_DIR": self.ops / "briefs", "LOCK_DIR": self.ops / "locks", "WORK": self.root / "work",
                  "STOP_FILE": self.ops / "STOP", "STATE_JSON": self.ops / "state/units.state.json",
                  "STATE_MD": self.ops / "state/STATE.md", "LIVE_UNITS": self.ops / "state/units.live.yaml",
                  "REPO": self.repo, "REPO_UNITS": self.repo / "units.yaml",
                  "MERGE_CAP_FILE": self.ops / "state/merge-cap.json",
                  "HISTORY_JSON": self.ops / "state/history.json"}
        self.patches = [patch.object(o, k, v) for k, v in values.items()]
        token_policy = o.runtime_policy.load()
        token_policy["estimated_daily_cost_ceiling"] = 100
        self.patches += [patch.object(o, "sh", Mock(side_effect=AssertionError("unexpected external command"))),
                         patch.object(o.runtime_policy, "load", return_value=token_policy),
                         patch.object(o.runtime_policy, "ready", return_value=True),
                         patch.object(o.sandbox, "cleanup"), patch.object(o.sandbox, "assert_absent"),
                         patch.object(o, "_load_jev", return_value=None),
                         patch.object(o, "telemetry_event"), patch.object(o, "_load_telemetry", return_value=tel),
                         patch.object(tel, "STATE", self.ops / "state"),
                         patch.object(tel, "RUNS", self.ops / "state/runs.jsonl"),
                         patch.object(tel, "EVENTS", self.ops / "state/events.jsonl"),
                         patch.object(tel, "default_flags", return_value={})]
        for p in self.patches:
            p.start()
        o.ensure_dirs()
        # Existing supervisor fixtures execute only synthetic commands. Preserve
        # the fixture command instead of loading the paid SDK runner.
        prepare = o.prepare_worker
        def fixture_prepare(*args, **kwargs):
            with patch.object(o, "RUNTIME", "fixture"):
                return prepare(*args, **kwargs)
        wrapper = patch.object(o, "prepare_worker", side_effect=fixture_prepare)
        wrapper.start()
        self.patches.append(wrapper)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()

    def record(self, **kw):
        c.append_record(o.STATE_DIR / "runs.jsonl", {"ts_start": o.now(), "ts_end": o.now(),
            "unit": "X", "role": "builder", "usage": {"total_tokens": 50}, **kw})


class ReviewSchema(unittest.TestCase):
    def test_pass_requires_successful_transport_and_schema(self):
        cases = [(124, '{"verdict":"pass","findings":[]}'), (1, '{"verdict":"pass","findings":[]}'),
                 (0, "hello"), (0, '{"verdict":"approve","findings":[]}'),
                 (0, '{"verdict":"pass"}'), (0, '{"verdict":"pass","findings":[null]}'),
                 (0, '{"verdict":"pass","findings":[]} {"verdict":"block","findings":[]}')]
        for rc, text in cases:
            with self.subTest(text=text):
                self.assertEqual(c.review_result(rc, text)[0], "unavailable")

    def test_block_without_findings_is_still_block(self):
        v, reason = c.review_result(0, '{"verdict":"block","findings":[]}')
        self.assertEqual(v, "block")
        self.assertTrue(reason)

    def test_blocker_overrides_pass(self):
        self.assertEqual(c.review_result(0, json.dumps({"verdict": "pass", "findings": [
            {"severity": "blocker", "file": "x.go", "line": 1, "issue": "wrong behavior"}]}))[0], "fix")


class ReviewBoundary(Isolated):
    def test_sensitive_work_obeys_temporary_and_restored_strict_policy(self):
        def sensitive_git(*args, **kwargs):
            if args[0] == "diff":
                return "diff --git a/internal/authflow/x.go b/internal/authflow/x.go\n+++ b/internal/authflow/x.go\n+ change\n"
            return self.git_value(*args, **kwargs)
        u = unit(model=o.MODEL["deepseek"])
        with (patch.object(o,"git_out",side_effect=sensitive_git),
              patch.object(o,"hermes_run",return_value=(0,'{"verdict":"pass","findings":[]}',{"total_tokens":2})) as run):
            self.assertTrue(o.ensure_reviewed(u,self.repo,state()))
        self.assertEqual(run.call_count,1)
        self.assertEqual(run.call_args.args[1],o.MODEL["sol"])
        policy = o.runtime_policy.load().copy()
        policy["required_review_families"] = 3
        with (patch.object(o.runtime_policy,"load",return_value=policy),
              patch.object(o,"git_out",side_effect=sensitive_git),
              patch.object(o,"hermes_run") as run):
            self.assertFalse(o.ensure_reviewed(u,self.repo,state()))
        run.assert_not_called()

    def git_value(self, *args, **kwargs):
        if args[:2] == ("rev-parse", "HEAD"):
            return "reviewed-head"
        if args[0] == "diff":
            return "diff --git a/internal/x/x.go b/internal/x/x.go\n+ change\n"
        if args[0] == "rev-list":
            return "1"
        return ""

    def test_outage_defers_when_no_other_independent_route_exists(self):
        u, st = unit(attempts=1), state()
        response = [(124, "", {"total_tokens": 10}), (0, '{"verdict":"pass","findings":[]}', {"total_tokens": 20})]
        with patch.object(o, "git_out", side_effect=self.git_value), patch.object(o, "hermes_run", side_effect=response) as run:
            self.assertEqual(o.run_review(u, self.repo, st, u["model"])[0], "unavailable")
        self.assertEqual(run.call_count, 1)
        models = [r.args[1] for r in run.call_args_list]
        self.assertEqual(models, [o.MODEL["deepseek"]])
        self.assertNotEqual(c.model_family(u["model"]), c.model_family(models[0]))
        self.assertNotIn("review_head", u)
        self.assertEqual(st["tokens_today"], 10)
        self.assertEqual(u["attempts"], 1)

    def test_malformed_review_without_independent_fallback_parks_only_unit(self):
        u, st = unit(attempts=1), state()
        with patch.object(o, "git_out", side_effect=self.git_value), patch.object(o, "hermes_run", return_value=(0, "bad JSON", {"total_tokens": 2})) as run:
            self.assertFalse(o.ensure_reviewed(u, self.repo, st))
        self.assertEqual(run.call_count, 1)
        self.assertEqual(u["status"], "parked")
        self.assertFalse(o.STOP_FILE.exists())

    def test_block_and_repeated_fix_never_merge(self):
        for verdict, rounds in (("block", 0), ("fix", 1)):
            u = unit(attempts=2, review_rounds=rounds)
            with patch.object(o, "git_out", side_effect=self.git_value), patch.object(o, "hermes_run", return_value=(0, json.dumps({"verdict": verdict, "findings": []}), {"total_tokens": 2})):
                self.assertFalse(o.ensure_reviewed(u, self.repo, state()))
            self.assertEqual(u["status"], "parked")
            self.assertEqual(u["attempts"], 2)

    def test_admission_denied_review_defers_existing_pr(self):
        u, st = unit(attempts=1, pr=7), state(merged_today=o.effective_merge_cap({}))
        with patch.object(o, "git_out", side_effect=self.git_value), patch.object(o, "hermes_run", return_value=(75, "cap admission denied", {"total_tokens": 0, "api_calls": 0, "admission_denied": True})):
            self.assertFalse(o.ensure_reviewed(u, self.repo, st))
        self.assertEqual(u["status"], "pr_open")
        self.assertEqual(u["pr"], 7)
        self.assertEqual(u["attempts"], 1)

    def test_sensitive_second_review_waits_for_replacement_family(self):
        u = unit(attempts=4, model=o.MODEL["sol"], review_model=o.MODEL["deepseek"])
        with patch.object(o, "git_out", side_effect=self.git_value), patch.object(o, "hermes_run", return_value=(0, '{"verdict":"pass","findings":[]}', {"total_tokens": 1})) as run:
            self.assertEqual(o.run_second_review(u, self.repo, state())[0], "unavailable")
        run.assert_not_called()

    def test_changed_head_discards_approval(self):
        u = unit(attempts=1)
        heads = iter(["old", "changed", "changed"])
        def git_value(*args, **kw):
            return next(heads, "changed") if args[0] == "rev-parse" else ""
        with patch.object(o, "git_out", side_effect=git_value), patch.object(o, "hermes_run", return_value=(0, '{"verdict":"pass","findings":[]}', {"total_tokens": 2})):
            self.assertEqual(o.run_review(u, self.repo, state(), u["model"])[0], "unavailable")
        self.assertNotIn("review_head", u)

    def test_reviewer_write_discards_approval(self):
        def git_value(*args, **kw):
            return " M internal/x/x.go" if args[0] == "status" else self.git_value(*args, **kw)
        with patch.object(o, "git_out", side_effect=git_value), patch.object(o, "hermes_run", return_value=(0, '{"verdict":"pass","findings":[]}', {"total_tokens": 2})):
            self.assertEqual(o.run_review(unit(), self.repo, state(), o.MODEL["luna"])[0], "unavailable")

    def test_forged_or_missing_receipt_cannot_approve(self):
        u = unit(review_head="reviewed-head", review_verdict="pass", review_model=o.MODEL["deepseek"])
        self.assertFalse(o.approval_valid(u, "review", "reviewed-head"))
        u["review_id"] = c.identity()
        path = o.LOG_DIR / f"X-review-{u['review_id']}.verdict.json"
        c.atomic_json(path, {"unit": "X", "head": "reviewed-head", "rc": 0, "verdict": "pass", "model": o.MODEL["deepseek"]})
        self.assertTrue(o.approval_valid(u, "review", "reviewed-head"))
        self.assertFalse(o.approval_valid(u, "review", "another-head"))
        u["model"] = o.MODEL["deepseek"]
        self.assertFalse(o.approval_valid(u, "review", "reviewed-head"))

    def test_missing_quality_module_is_a_failed_gate(self):
        with patch.object(o, "_load_quality", return_value=None):
            self.assertFalse(o.quality_gate(self.repo, unit(), state(), "origin/main")["ok"])
        self.assertTrue(o.STOP_FILE.exists())

    def test_successful_exit_with_provider_outage_cannot_approve(self):
        u, st = unit(), state()
        for output, usage in [('{"verdict":"pass","findings":[]}', {"total_tokens": 2, "provider_error": True}),
                              ('HTTP error 500\n{"verdict":"pass","findings":[]}', {"total_tokens": 2})]:
            with patch.object(o, "git_out", side_effect=self.git_value), patch.object(o, "hermes_run", return_value=(0, output, usage)):
                self.assertFalse(o.ensure_reviewed(u, self.repo, st))
                self.assertNotEqual(u.get("review_verdict"), "pass")

    def test_malformed_review_retries_only_author_independent_approved_routes(self):
        u, st = unit(model=o.MODEL["sol"]), state()
        models = []
        def reviewer(profile, model, *args, **kwargs):
            models.append(model)
            return (0, "malformed" if len(models) == 1 else '{"verdict":"pass","findings":[]}', {"total_tokens": 2})
        with patch.object(o, "git_out", side_effect=self.git_value), patch.object(o, "hermes_run", side_effect=reviewer):
            verdict, _, _ = o.validated_review(u, self.repo, st, o.MODEL["deepseek"], "review")
        self.assertEqual(verdict, "unavailable")
        self.assertEqual(models, [o.MODEL["deepseek"]])
        self.assertFalse(o.approval_valid(u, "review", "reviewed-head"))

    def test_merge_refusal_parks_without_protection_mutation(self):
        u = unit(attempts=1, pr=1, review_head="before-rebase", review_verdict="pass")
        with patch.object(o, "git", return_value=(0, "")), patch.object(o, "git_out", side_effect=self.git_value), \
             patch.object(o, "changed_files", return_value=["internal/x/x.go"]), \
             patch.object(o, "run_check", return_value=(0, "passed")), patch.object(o, "quality_gate", return_value={"ok": True}), \
             patch.object(o, "hermes_run", return_value=(0, '{"verdict":"pass","findings":[]}', {"total_tokens": 1})) as review, \
             patch.object(o, "ci_advisory", return_value=(True, "ok")), patch.object(o, "append_actions_note"), \
             patch.object(o, "sh", return_value=(1, "base branch policy refused")) as gh:
            self.assertFalse(o.merge_queue(u, self.repo, state()))
        self.assertEqual(review.call_count, 1)  # rebased head gets a fresh review
        self.assertEqual(u["status"], "parked")
        self.assertIn("merge refused", u["reason"])
        self.assertEqual(u["attempts"], 1)
        self.assertEqual(gh.call_count, 1)
        self.assertIn("--match-head-commit", gh.call_args.args[0])
        self.assertNotIn("api", gh.call_args.args[0])

    def test_jev_skip_claim_cannot_bypass_independent_review(self):
        u = unit(attempts=1, pr=1)
        with patch.object(o, "git", return_value=(0, "")), patch.object(o, "git_out", side_effect=self.git_value), \
             patch.object(o, "changed_files", return_value=[]), patch.object(o, "commit_if_dirty"), \
             patch.object(o, "run_check", return_value=(0, "ok")), patch.object(o, "quality_gate", return_value={"ok": True}), \
             patch.object(o, "rec_quality"), patch.object(o, "push_and_open_pr", return_value=1), \
             patch.object(o, "jev_review_gate", return_value={"skip": True}) as jev, \
             patch.object(o, "hermes_run", return_value=(0, '{"verdict":"block","findings":[]}', {"total_tokens": 1})), \
             patch.object(o, "merge_queue") as merge:
            o._publish_attempt(u, self.repo, state(), {"v": "other"})
        jev.assert_not_called()
        merge.assert_not_called()


class PlanValidation(Isolated):
    def plan(self, entries):
        return "units:\n" + "\n".join(o.dump_unit_yaml({k: v for k, v in e.items() if k != "model"}) for e in entries)

    def test_entire_plan_rejected_without_partial_mutation(self):
        for bad in (unit("A", paths=["ops/x.py"]), unit("A", paths=["../x"]), unit("A", paths=["scripts"]),
                    unit("A", depends_on=["missing"]), unit("A", depends_on=["A"]),
                    unit("A", status="merged"), unit("A", tokens=1), unit("P")):
            road = {"P": unit("P", status="merged", tokens=123, attempts=3, pr=9)}
            before = copy.deepcopy(road)
            self.assertFalse(o.apply_planner_output(road, state(), {}, self.plan([unit("good"), bad])))
            self.assertEqual(road, before)

    def test_duplicate_ids_and_cycle_rejected(self):
        for entries in ([unit("A"), unit("A")], [unit("A", depends_on=["B"]), unit("B", depends_on=["A"])]):
            self.assertFalse(o.apply_planner_output({}, state(), {}, self.plan(entries)))

    def test_split_parent_reference_never_self_depends(self):
        parent = unit("P", paths=["internal/x"], attempts=2, tokens=100)
        road = {"P": parent, "consumer": unit("consumer", depends_on=["P"])}
        plan = [unit("Pa", depends_on=["P"], model=""), unit("Pb", depends_on=["P"], model="")]
        self.assertTrue(o.apply_planner_output(road, state(), parent, self.plan(plan), old_id="P", mode="split"))
        self.assertEqual(road["Pa"]["depends_on"], [])
        self.assertEqual(road["Pb"]["depends_on"], ["Pa"])
        self.assertEqual(road["consumer"]["depends_on"], ["Pa", "Pb"])
        self.assertEqual(parent["tokens"], 100)
        self.assertNotEqual(road["Pa"]["revision_id"], road["Pb"]["revision_id"])


class Accounting(Isolated):
    def test_interrupted_replace_preserves_old_snapshot(self):
        path = o.STATE_JSON
        path.write_text('{"old":1}')
        with patch.object(c.os, "replace", side_effect=OSError("disk fault")):
            with self.assertRaises(OSError):
                c.atomic_json(path, {"new": 2})
        self.assertEqual(json.loads(path.read_text()), {"old": 1})
        self.assertEqual(len(list(path.parent.glob(".units.state.json.*"))), 0)

    def test_corrupt_accounting_rebuilt_from_ledger(self):
        o.STATE_JSON.write_text('{"partial":')
        self.record(usage={}, charged_tokens=234, run_id="run-fixture")
        for _ in range(2):
            c.append_record(o.STATE_DIR / "runs.jsonl", {"record_type": "delivery", "pr": 1, "merged_at": o.now()})
        st = o.load_state()
        self.assertEqual(st["tokens_today"], 234)
        self.assertEqual(st["merged_today"], 1)

    def test_corrupt_ledger_stops_cycle_before_any_commands(self):
        (o.STATE_DIR / "runs.jsonl").write_text('{"partial":')
        with self.assertRaises(c.IntegrityError):
            o.cycle(no_dispatch=True)
        self.assertTrue(o.STOP_FILE.exists())
        o.sh.assert_not_called()

    def test_missing_previous_accounting_never_becomes_free(self):
        o.LIVE_UNITS.write_text("existing")
        with self.assertRaises(c.IntegrityError):
            o.load_state()

    def test_unknown_usage_charged_conservatively(self):
        self.record(usage={})
        self.assertEqual(o.load_state()["tokens_today"], o.TIMEOUT_FALLBACK_TOKENS)

    def test_decisions_usage_aliases_are_counted(self):
        self.assertEqual(o.usage_tokens({"prompt_tokens": 120, "completion_tokens": 13}), 133)

    def test_accounting_counter_never_drops_below_ledger(self):
        self.record(charged_tokens=999)
        c.atomic_json(o.STATE_JSON, state(tokens_today=1))
        self.assertEqual(o.load_state()["tokens_today"], 999)

    def test_midnight_recovery_retains_new_day_spend(self):
        self.record(charged_tokens=123)
        c.atomic_json(o.STATE_JSON, {**state(tokens_today=999), "day": "2000-01-01"})
        self.assertEqual(o.load_state()["tokens_today"], 123)

    def test_history_revision_is_append_only(self):
        u = unit(attempts=1)
        o.record_history(u, "failed")
        o.record_history(u, "merged")
        rows = [json.loads(x) for x in (o.STATE_DIR / "history.jsonl").read_text().splitlines()]
        self.assertEqual([r["outcome"] for r in rows], ["failed", "merged"])
        self.assertNotEqual(rows[0]["revision_id"], rows[1]["revision_id"])

    def test_legacy_baseline_preserves_missing_historical_spend(self):
        self.record()
        st, road = state(tokens_today=200, merged_today=3), {"X": unit(tokens=300, attempts=2)}
        o.bootstrap_accounting(st, road)
        rebuilt = c.accounting(c.ledger_records(o.STATE_DIR), st["day"], 1000)
        self.assertEqual(rebuilt["tokens_today"], 200)
        self.assertEqual(rebuilt["unit_tokens"]["X"], 300)
        self.assertEqual(rebuilt["unit_attempts"]["X"], 2)
        self.assertEqual(rebuilt["merged_today"], 3)

    def test_unsettled_paid_run_does_not_allow_dispatch(self):
        c.append_record(o.STATE_DIR / "runs.jsonl", {"record_type": "reservation", "run_id": "fixture",
            "reserved_tokens": 100, "unit": "X", "ts_start": o.now()})
        with self.assertRaises(c.IntegrityError):
            o.load_state()

    def test_outcome_records_never_double_charge_telemetry(self):
        self.record(charged_tokens=12, run_id="fixture")
        c.append_record(o.STATE_DIR / "runs.jsonl", {"record_type": "outcome", "run_id": "fixture", "outcome": "merged"})
        rows = list(tel.read_runs())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outcome"], "merged")
        self.assertEqual(tel.run_total(rows[0]), 12)


class Admission(Isolated):
    def test_stop_and_caps_admission_for_every_paid_role(self):
        for role in ("builder", "reviewer", "planner", "audit", "jev"):
            with self.subTest(role=role):
                for st, u, stopped in ((state(), unit(), True), (state(tokens_today=o.DAILY_TOKEN_CAP), unit(), False),
                                       (state(), unit(tokens=o.PER_UNIT_TOKEN_CAP), False),
                                       (state(merged_today=o.effective_merge_cap({})), unit(), False)):
                    if stopped:
                        o.STOP_FILE.touch()
                    else:
                        o.STOP_FILE.unlink(missing_ok=True)
                    with self.assertRaises(o.BudgetDenied):
                        o.admit_paid(st, u, role)
        o.sh.assert_not_called()

    def test_parallel_allowance_and_audit_cap(self):
        st = state(tokens_today=o.DAILY_TOKEN_CAP - o.PER_UNIT_TOKEN_CAP)
        o.admit_paid(st, unit(), "builder")
        with self.assertRaises(o.BudgetDenied):
            o.admit_paid(st, unit("Y"), "builder")
        st = state()
        with self.assertRaises(o.BudgetDenied):
            o.admit_paid(st, None, "audit")

    def test_three_provider_failures_pause_dispatch_and_back_off(self):
        st = state()
        with patch.object(o.time, "time", return_value=1000):
            for n in range(3):
                o.note_provider(st, True)
                self.assertGreater(st["provider_retry_at"], 1000)
        with patch.object(o.time, "time", return_value=1001):
            self.assertFalse(o.paid_allowed(st, unit(), "builder"))
        with patch.object(o.time, "time", return_value=99999):
            self.assertTrue(o.paid_allowed(st, unit(), "builder"))
        self.assertEqual(st["provider_errors"], 3)

    def test_actual_overspend_stops_instead_of_hiding_charge(self):
        st = state(tokens_today=o.DAILY_TOKEN_CAP - 1)
        with self.assertRaises(c.IntegrityError):
            o.add_tokens(st, unit(), 2)
        self.assertEqual(st["tokens_today"], o.DAILY_TOKEN_CAP + 1)

    def test_existing_nightly_merge_cap_revert_is_preserved(self):
        st = state()
        with patch.object(o, "nightly_consecutive_failures", return_value=2):
            o.apply_merge_cap_guard(st)
        self.assertEqual(o.effective_merge_cap(st), o.MERGE_CAP_REVERTED)

    def test_corrupt_merge_cap_cannot_raise_allowance(self):
        o.MERGE_CAP_FILE.write_text('{"partial":')
        with self.assertRaises(c.IntegrityError):
            o.effective_merge_cap(state())


class Providers(Isolated):
    def test_all_requested_statuses_and_gateway_errors(self):
        for code in (402, 403, 429, 500, 502, 503, 599):
            self.assertTrue(c.provider_error(1, f"API HTTP error {code}"))
            self.assertTrue(c.provider_error(code, ""))
        self.assertTrue(c.provider_error(124, "gateway timeout"))
        self.assertFalse(c.provider_error(1, "compile failed at source line 503"))

    def test_compile_and_test_source_locations_are_not_provider_statuses(self):
        for output in ("internal/api/handler.go:503:12: undefined: foo", "internal/api/x_test.go:500: got 1 want 2",
                       "internal/provider/error.go:402: syntax error", "internal/http/status.go:403: invalid operation"):
            self.assertFalse(c.provider_error(1, output), output)

    def test_provider_failure_does_not_publish_split_park_or_consume_attempt(self):
        u, st = unit(attempts=1), state()
        usage, output = o.LOG_DIR / "usage.json", o.LOG_DIR / "builder.log"
        usage.write_text('{"total_tokens":7}')
        output.write_text("API HTTP error 429")
        proc = Mock(returncode=1)
        rid = o.admit_paid(st, u, "builder")
        receipt = o.prepare_worker(rid, st, "builder", u["model"], ["fixture"], self.repo, usage, 10, 1)
        rec = o.read_json(receipt, {})
        rec.update(status="complete", rc=1, completed_at=o.time.time(), usage={"total_tokens":7})
        o.write_json(receipt, rec)
        job = {"unit": u, "proc": proc, "started": o.time.time(), "logfile": Mock(),
               "usage": usage, "log_path": output, "wt": self.repo, "ts_start": o.now(),
               "run_id": rid, "receipt": receipt}
        with patch.object(o, "_publish_attempt") as publish:
            o.finish_build(job, {"X": u}, st)
        publish.assert_not_called()
        self.assertEqual(u["attempts"], 0)
        self.assertEqual(u["status"], "todo")
        self.assertFalse(u.get("split_requested", False))
        self.assertEqual(st["tokens_today"], 7)

    def test_provider_planner_failure_preserves_retry_budget(self):
        (self.repo / "docs").mkdir()
        (self.repo / "docs/contract.md").write_text("approved bounded synthetic contract")
        u = unit("P", status="design", model="", planner_retries=1, planning_ready=True,
                 planning_context="docs/contract.md", planning_paths=["internal/x"],
                 planning_acceptance=["synthetic behavior"], planning_tests=["go test ./internal/x/..."])
        st = state()
        with patch.object(o, "hermes_run", return_value=(1, "API HTTP error 502", {"total_tokens": 7})):
            self.assertFalse(o.maybe_plan({"P": u}, st))
        self.assertEqual(u["planner_retries"], 1)
        self.assertEqual(u["status"], "design")
        self.assertEqual(u["tokens"], 0)

    def test_success_without_usage_is_never_free(self):
        u, st = unit(), state()
        def complete_worker(command, **kwargs):
            path = Path(command[-1])
            rec = o.read_json(path, {})
            rec.update(status="complete", rc=0, completed_at=o.time.time(), usage={})
            o.write_json(path, rec)
            return 0, "done"
        with patch.object(o, "sh", side_effect=complete_worker):
            _, _, usage = o.hermes_run("reviewer", o.MODEL["deepseek"], "fixture", "file", self.repo,
                                       "planner", 1, state=st, budget_unit=u)
        self.assertEqual(usage["accounted_tokens"], o.TIMEOUT_FALLBACK_TOKENS)
        self.assertFalse(st["reservations"])

    def test_incomplete_worker_never_settles_or_releases_reservation(self):
        u, st = unit(), state()
        with patch.object(o, "sh", return_value=(1, "service stop failed")):
            with self.assertRaises(c.IntegrityError):
                o.hermes_run("reviewer", o.MODEL["deepseek"], "fixture", "file", self.repo,
                             "planner", 1, state=st, budget_unit=u)
        rows = c.ledger_records(o.STATE_DIR)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record_type"], "reservation")
        self.assertEqual(len(st["reservations"]), 1)

    def test_builder_incomplete_cleanup_never_publishes_or_releases(self):
        u, st = unit(attempts=1), state()
        rid = o.admit_paid(st, u, "builder")
        usage = o.LOG_DIR / "usage.json"
        receipt = o.prepare_worker(rid, st, "builder", u["model"], ["fixture"], self.repo, usage, 10, 1)
        job = {"unit": u, "proc": Mock(returncode=1), "started": o.time.time(),
               "logfile": Mock(), "usage": usage, "wt": self.repo, "run_id": rid, "receipt": receipt}
        with patch.object(o, "_publish_attempt") as publish, self.assertRaises(c.IntegrityError):
            o.finish_build(job, {"X": u}, st)
        publish.assert_not_called()
        self.assertIn(rid, st["reservations"])
        self.assertEqual(len(c.ledger_records(o.STATE_DIR)), 1)

    def test_builder_launch_failure_is_not_an_attempt(self):
        u, st = unit(), state()
        with patch.object(o, "ensure_worktree", return_value=self.repo), patch.object(o.subprocess, "Popen", side_effect=OSError("worker unavailable")):
            with self.assertRaises(OSError):
                o.start_build(u, st, {"X": u})
        self.assertEqual(u["attempts"], 0)
        self.assertEqual(st["reservations"], {})
        ledger = c.accounting(c.ledger_records(o.STATE_DIR), o.now()[:10], o.TIMEOUT_FALLBACK_TOKENS)
        self.assertFalse(ledger["unsettled"])
        self.assertEqual(ledger["tokens_today"], 0)

    def test_real_launch_identifiers_and_files_never_reused(self):
        st, u = state(), unit()
        with patch.object(o, "ensure_worktree", return_value=self.repo), patch.object(o.subprocess, "Popen", return_value=Mock(returncode=0)):
            first = o.start_build(u, st, {"X": u})
            first["logfile"].close()
            first["usage"].write_text('{"total_tokens":1}')
            o.release_paid(st, first["run_id"])
            u["status"] = "todo"
            second = o.start_build(u, st, {"X": u})
            second["logfile"].close()
        self.assertNotEqual(first["usage"], second["usage"])
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertTrue(first["usage"].exists())
        self.assertEqual(u["attempts"], 2)


class Reconciliation(Isolated):
    def test_git_delivery_restores_all_requested_units_and_preserves_history(self):
        road = {uid: unit(uid, attempts=2, tokens=123, pr=9) for uid in ("F35", "F36", "F37", "F40", "other")}
        prs = [{"number": i + 1, "headRefName": "unit/" + uid, "mergeCommit": {"oid": "fixture"}, "mergedAt": o.now()}
               for i, uid in enumerate(road)]
        with patch.object(o, "sh", return_value=(0, json.dumps(prs))), patch.object(o, "git", return_value=(0, "")):
            self.assertEqual(set(o.reconcile_deliveries(road, state())), set(road))
        for u in road.values():
            self.assertEqual(u["status"], "merged")
            self.assertEqual(u["tokens"], 123)
            self.assertEqual(u["attempts"], 2)
        self.assertEqual(len((o.STATE_DIR / "reconciliation.jsonl").read_text().splitlines()), 5)
        self.assertEqual(c.accounting(c.ledger_records(o.STATE_DIR), o.now()[:10], 1)["merged_today"], 0)

    def test_nonancestor_delivery_cannot_be_adopted(self):
        road = {"X": unit()}
        prs = [{"number": 1, "headRefName": "unit/X", "mergeCommit": {"oid": "fixture"}, "mergedAt": o.now()}]
        with patch.object(o, "sh", return_value=(0, json.dumps(prs))), patch.object(o, "git", return_value=(1, "")):
            with self.assertRaises(c.IntegrityError):
                o.reconcile_deliveries(road, state())
        self.assertEqual(road["X"]["status"], "todo")

    def test_dispatch_disabled_cycle_launches_no_workers_or_merges(self):
        u = unit()
        o.REPO_UNITS.write_text("units:\n" + o.dump_unit_yaml(u))
        o.STOP_FILE.touch()
        with patch.object(o, "git", return_value=(0, "")), patch.object(o, "sh", return_value=(0, "[]")), \
             patch.object(o, "apply_merge_cap_guard"), patch.object(o, "write_state_md"), \
             patch.object(o, "dispatch") as dispatch, patch.object(o, "resume_open_prs") as merge, \
             patch.object(o, "hermes_run") as worker:
            o.cycle(no_dispatch=True)
        dispatch.assert_not_called()
        merge.assert_not_called()
        worker.assert_not_called()
        self.assertTrue(o.STOP_FILE.exists())

    def test_inventory_transport_outage_defers_without_permanent_stop(self):
        o.REPO_UNITS.write_text("units:\n" + o.dump_unit_yaml(unit()))
        with patch.object(o, "git", return_value=(0, "")), patch.object(o, "sh", return_value=(1, "network unavailable")), \
             patch.object(o, "apply_merge_cap_guard"), patch.object(o, "write_state_md"), patch.object(o, "dispatch") as dispatch:
            o.cycle()
        self.assertFalse(o.STOP_FILE.exists())
        dispatch.assert_not_called()

    def test_git_fetch_transport_outage_defers_without_permanent_stop(self):
        o.REPO_UNITS.write_text("units:\n" + o.dump_unit_yaml(unit()))
        with patch.object(o, "git", return_value=(1, "network unavailable")), \
             patch.object(o, "apply_merge_cap_guard"), patch.object(o, "write_state_md"), patch.object(o, "dispatch") as dispatch:
            o.cycle()
        self.assertFalse(o.STOP_FILE.exists())
        dispatch.assert_not_called()

    def test_jev_cannot_swallow_critical_accounting_fault(self):
        mod = Mock()
        mod.size_check.side_effect = c.IntegrityError("accounting fault")
        mod.triage.side_effect = c.IntegrityError("accounting fault")
        with patch.object(o, "_load_jev", return_value=mod):
            with self.assertRaises(c.IntegrityError):
                o.jev_size_check(unit())
            with self.assertRaises(c.IntegrityError):
                o.jev_triage(unit(), "compile failed", 1, False)

    def test_jev_telemetry_names_its_actual_provider(self):
        mod = Mock(JEV_MODEL="typesafe/jev-1.13")
        st, road = state(), {"X": unit()}
        with patch.object(o, "_load_jev", return_value=mod):
            o.configure_jev_accounting(st, road)
        rid = mod.CONTROL_BEFORE("X")
        mod.CONTROL_AFTER(rid, "X", {"prompt_tokens": 120, "completion_tokens": 13}, False)
        rows = list(tel.read_runs())
        self.assertEqual(rows[0]["provider"], "openrouter")
        self.assertEqual(rows[0]["charged_tokens"], 133)


class TerminatorMaintenance(Isolated):
    def test_deselect_and_uninstall_fail_closed_and_preserve_telemetry(self):
        cfg = o.HOME / ".hermes/profiles/builder/config.yaml"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text("context:\n  engine: token-terminator\n")
        venv = self.root / "venv/bin/python"
        with patch.object(o, "tt_engine", side_effect=["compressor"]), \
             patch.object(o, "_hermes_venv_python", return_value=venv), \
             patch.object(o, "sh", return_value=(1, "uninstall failed")) as uninstall:
            self.assertFalse(o._tt_revert("fixture"))
        self.assertIn("engine: compressor", cfg.read_text())
        self.assertIn("uninstall", uninstall.call_args.args[0])
        self.assertEqual(uninstall.call_args.args[0][-1], "token-terminator")


if __name__ == "__main__":
    unittest.main()
