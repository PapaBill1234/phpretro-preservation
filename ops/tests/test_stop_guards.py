"""Stop-file and disabled-guard admission regressions."""

import unittest
from unittest.mock import Mock, patch

from test_maintenance import Isolated, state, unit
import orchestrator as o


class StopGuardTest(Isolated):
    def test_pending_ci_retains_unit_then_merges_without_paid_work(self):
        u=unit('F1',status='pr_open',pr=42,branch='unit/F1',review_head='head-1',review_verdict='pass',attempts=2,tokens=100)
        st=state()
        with patch.object(o,'git',return_value=(0,'')), patch.object(o,'git_out',side_effect=lambda *a,**k:'head-1' if a[:2]==('rev-parse','HEAD') else ''), \
             patch.object(o,'changed_files',return_value=['internal/x.go']),patch.object(o,'guard_violations',return_value=[]), \
             patch.object(o,'run_check',return_value=(0,'ok')),patch.object(o,'quality_gate',return_value={'ok':True}), \
             patch.object(o,'ensure_reviewed',return_value=True),patch.object(o,'approval_valid',return_value=True), \
             patch.object(o,'required_ci',side_effect=[('pending','foundation pending'),('ready','passed')]), \
             patch.object(o,'append_actions_note'),patch.object(o,'drop_worktree'),patch.object(o,'jev_note_merged'), \
             patch.object(o,'hermes_run',side_effect=AssertionError('No paid work while resuming CI')), \
             patch.object(o,'sh',return_value=(0,'')) as merge:
            self.assertFalse(o.merge_queue(u,self.repo,st));self.assertEqual(u['status'],'pr_open');merge.assert_not_called()
            self.assertTrue(o.merge_queue(u,self.repo,st));self.assertEqual(u['status'],'merged')
        self.assertEqual(u['attempts'],2);self.assertEqual(u['tokens'],100);self.assertEqual(u['reason'],'')

    def test_guard_disabled_denies_paid_work(self):
        with patch.object(o, "GUARD_DISABLED", True):
            self.assertFalse(o.paid_allowed(state(), unit(), "builder"))

    def test_stop_created_during_required_ci_prevents_merge_command(self):
        u = unit("F1", status="pr_open", pr=42, branch="unit/F1",
                 review_head="head-1", review_verdict="pass")
        st = state()

        def advisory(*args, **kwargs):
            o.STOP_FILE.touch()
            return "ready", "green"

        with patch.object(o, "git", return_value=(0, "")), \
             patch.object(o, "git_out", side_effect=lambda *a, **k: "head-1" if a[:2] == ("rev-parse", "HEAD") else ""), \
             patch.object(o, "changed_files", return_value=["internal/x.go"]), \
             patch.object(o, "guard_violations", return_value=[]), \
             patch.object(o, "run_check", return_value=(0, "ok")), \
             patch.object(o, "quality_gate", return_value={"ok": True}), \
             patch.object(o, "ensure_reviewed", return_value=True), \
             patch.object(o, "approval_valid", return_value=True), \
             patch.object(o, "required_ci", side_effect=advisory), \
             patch.object(o, "append_actions_note"), \
             patch.object(o, "sh", Mock(side_effect=AssertionError("merge command must be blocked"))) as sh:
            self.assertFalse(o.merge_queue(u, self.repo, st))
        sh.assert_not_called()
        self.assertEqual(u["status"], "pr_open")


if __name__ == "__main__":
    unittest.main()
