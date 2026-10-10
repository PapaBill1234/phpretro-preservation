"""Cutover fault injection. All files are disposable and every subprocess mocked."""
import copy
import json
import sys
import tempfile
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import harness
import integrity
from claude_code import activate, install_paused, rollback


class CutoverTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.home = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.ops = self.home / 'ops'
        (self.ops / 'state').mkdir(parents=True)
        (self.ops / 'STOP').write_text('owned migration pause')
        self.before_stop = (self.ops / 'STOP').stat().st_mtime_ns
        self.previous = {'installed': True, 'enabled': False, 'source_head': 'head'}
        self.write('units.state.json', {'reservations': {}, 'tokens_today': 12})
        self.write('claude-code-activation.json', self.previous)
        self.write('maintenance-pause.json', {
            'owner': 'codex-claude-code-runtime-migration', 'previous_stop': False,
            'stop_mtime_ns': self.before_stop})
        self.validation = {
            'implementation_sha256': 'source', 'validated_at': time.time(),
            'vulnerability_snapshot_at': time.time(), 'image_id': 'image',
            'checks': {k: True for k in ('foundation', 'ops', 'frontend', 'isolation', 'lifecycle', 'resources')}}
        self.commands = []
        self.stack.enter_context(patch.object(Path, 'home', return_value=self.home))
        self.stack.enter_context(patch.object(activate.runtime_policy, 'OPS', self.ops))
        self.stack.enter_context(patch.object(install_paused, 'OPS', self.ops))
        self.stack.enter_context(patch.object(activate.supervisor, 'ENABLED', self.home / 'ENABLED'))
        self.stack.enter_context(patch.object(activate.runtime_policy, 'fingerprint', return_value='source'))
        self.stack.enter_context(patch.object(activate.runtime_policy, 'load', return_value={
            'review_policy': 'temporary-two-family-user-override',
            'model_roles': {'builder': 'gpt-6-luna'}, 'image': 'tools'}))
        self.stack.enter_context(patch.object(activate.worker, 'bus_env', return_value={}))

    def write(self, name, value):
        (self.ops / 'state' / name).write_text(json.dumps(value))

    def safe_state(self):
        self.assertTrue((self.ops / 'STOP').is_file())
        self.assertFalse((self.home / 'ENABLED').exists())
        self.assertEqual(json.loads((self.ops / 'state/units.state.json').read_text())['tokens_today'], 12)

    def test_install_rejects_expired_future_and_invalid_evidence_before_mutation(self):
        with patch.object(install_paused, 'checked', return_value='image'):
            install_paused.require_validation(self.validation)
            for field in ('validated_at', 'vulnerability_snapshot_at'):
                for value in (time.time()-172801, time.time()+100, None, True, 'fresh', float('nan')):
                    row = copy.deepcopy(self.validation)
                    row[field] = value
                    with self.subTest(field=field, value=value), self.assertRaises(integrity.IntegrityError):
                        install_paused.require_validation(row)
            with patch.object(install_paused, 'checked', return_value='changed-image'):
                with self.assertRaises(integrity.IntegrityError):
                    install_paused.require_validation(self.validation)
        self.safe_state()

    def test_activation_rejects_later_intentional_stop_without_side_effects(self):
        self.write('maintenance-pause.json', {'owner': 'codex-claude-code-runtime-migration',
                   'previous_stop': False, 'stop_mtime_ns': 0})
        with patch.object(sys, 'argv', ['activate.py', '--enable']), patch.object(activate.subprocess, 'run') as run:
            with self.assertRaises(integrity.IntegrityError):
                activate.main()
            run.assert_not_called()
        self.safe_state()
        self.assertEqual(json.loads((self.ops / 'state/claude-code-activation.json').read_text()), self.previous)

    def test_activation_failure_restores_pause_and_previous_activation(self):
        def run(args, **kwargs):
            self.commands.append(args)
            if '--now' in args and 'enable' in args:
                raise RuntimeError('injected timer start failure')
        with patch.object(sys, 'argv', ['activate.py', '--enable']), \
             patch.object(activate.runtime_policy, 'ready', return_value=True), \
             patch.object(activate.subprocess, 'run', side_effect=run):
            with self.assertRaises(RuntimeError):
                activate.main()
        self.safe_state()
        self.assertEqual(json.loads((self.ops / 'state/claude-code-activation.json').read_text()), self.previous)
        self.assertTrue(any('stop' in cmd and 'phpretro-orchestrator.timer' in cmd for cmd in self.commands))

    def test_rollback_restores_doctor_dashboard_and_prior_dropins(self):
        backup = self.ops / 'backups/claude-cutover-test'
        backup.mkdir(parents=True)
        base = self.home / 'phpretro-skill-doctor'
        (base / 'runtime').mkdir(parents=True)
        (base / 'runtime/new').write_text('candidate')
        (backup / 'doctor-runtime').mkdir()
        (backup / 'doctor-runtime/old').write_text('original')
        (backup / 'doctor-manifest.json').write_text('{"original":true}')
        dashboard = self.home / 'phpretro-dashboard'
        dashboard.mkdir()
        for name in ('server.py', 'gateway.py', 'index.html'):
            (dashboard / name).write_text('candidate')
            (backup / name).write_text('original')
        unit = 'phpretro-dashboard.service'
        target = self.home / '.config/systemd/user' / (unit+'.d/claude-runtime.conf')
        target.parent.mkdir(parents=True)
        target.write_text('candidate')
        (backup / (unit+'.dropin.previous')).write_text('original')
        (backup / 'rollback.json').write_text(json.dumps({
            'activation': self.previous, 'canvas_exists': False, 'changed_dropins': [unit]}))
        with patch.object(rollback.subprocess, 'run', side_effect=lambda args, **kw: self.commands.append(args)):
            rollback.restore(backup)
        self.safe_state()
        self.assertEqual((base / 'runtime/old').read_text(), 'original')
        self.assertEqual((backup / 'failed-doctor-runtime/new').read_text(), 'candidate')
        self.assertEqual(json.loads((base / 'extension-manifest.json').read_text()), {'original': True})
        self.assertEqual(target.read_text(), 'original')
        for name in ('server.py', 'gateway.py', 'index.html'):
            self.assertEqual((dashboard / name).read_text(), 'original')
        self.assertFalse(any('enable' in cmd for cmd in self.commands))


if __name__ == '__main__':
    unittest.main()
