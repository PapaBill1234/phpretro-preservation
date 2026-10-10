"""Cutover fault injection and disposable Git source-identity checks."""
import copy
import json
import sys
import subprocess
import tempfile
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import harness
import integrity
from claude_code import activate, install_paused, policy, rollback


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

    def authorization(self, **changes):
        row={'authorized_by':'user','operation':'paused-deploy-before-source-review',
             'source_head':'head','implementation_sha256':'source','stop_mtime_ns':self.before_stop,
             'created_at':time.time()-1,'expires_at':time.time()+3600,**changes}
        self.write('claude-code-migration-authorization.json',row)
        (self.ops/'state/claude-code-migration-authorization.json').chmod(0o600)
        return row

    def test_deployment_deferral_requires_exact_private_scoped_authorization(self):
        self.assertFalse(policy.deployment_authorized(self.ops,'head','source'))
        self.authorization()
        self.assertTrue(policy.deployment_authorized(self.ops,'head','source'))
        self.assertFalse(policy.deployment_authorized(self.ops,'other','source'))
        self.assertFalse(policy.deployment_authorized(self.ops,'head','changed'))
        for changes in ({'authorized_by':'script'},{'operation':'enable'}, {'source_head':'other'},
            {'implementation_sha256':'changed'},{'stop_mtime_ns':0},{'expires_at':time.time()-1},
            {'created_at':time.time()+10},{'expires_at':time.time()+14401},
            {'created_at':True},{'expires_at':float('nan')}):
            with self.subTest(changes=changes):
                self.authorization(**changes)
                self.assertFalse(policy.deployment_authorized(self.ops,'head','source'))
        self.authorization()
        self.write('maintenance-pause.json',{'owner':'later-user-stop','stop_mtime_ns':self.before_stop,'previous_stop':False})
        self.assertFalse(policy.deployment_authorized(self.ops,'head','source'))
        self.safe_state()

    def test_deferred_installer_cannot_use_dirty_or_unpublished_source(self):
        self.authorization()
        with patch.object(install_paused,'checked',side_effect=['','head']):
            install_paused.require_source('head',True)
        for outputs in (['dirty'],['','unpublished']):
            with patch.object(install_paused,'checked',side_effect=outputs), self.assertRaises(integrity.IntegrityError):
                install_paused.require_source('head',True)
        with patch.object(install_paused,'checked',side_effect=['','head']), self.assertRaises(integrity.IntegrityError):
            install_paused.require_source('head',False)
        self.write('claude-code-source-review.json',{'head':'head','verdict':'pass','independent':True})
        with patch.object(install_paused,'checked',side_effect=['','head']):
            install_paused.require_source('head',False)
        self.safe_state()

    def test_deferred_bootstrap_does_not_enable_normal_coding(self):
        self.authorization()
        self.write('claude-code-activation.json',{**self.previous,'source_review_deferred':True})
        self.write('claude-code-validation.json',self.validation)
        data={'image':'tools','review_policy':'temporary-two-family-user-override'}
        with patch.object(policy,'authenticated',return_value=True), \
             patch.object(policy,'version_matches',return_value=True), \
             patch.object(policy,'installed_source_matches',return_value=True), \
             patch.object(policy.subprocess,'check_output',return_value='image'):
            self.assertTrue(policy.bootstrap_ready(data,self.ops,'source'))
            self.assertFalse(policy.bootstrap_ready(data,self.ops,'changed'))
            active={**self.previous,'source_review_deferred':True,'authorized_by':'user',
                    'enabled':True,'review_policy':data['review_policy']}
            self.write('claude-code-activation.json',active)
            self.assertFalse(policy.ready(data,self.ops,'source'))
            self.assertFalse(policy.bootstrap_ready(data,self.ops,'source'))
            self.write('claude-code-activation.json',{**self.previous,'source_review_deferred':True})
            self.authorization(expires_at=time.time()-1)
            self.assertFalse(policy.bootstrap_ready(data,self.ops,'source'))
        self.safe_state()

    def test_installed_source_binds_head_fingerprint_and_clean_checkout(self):
        installed={**self.previous,'implementation_sha256':'source'}
        with patch.object(policy.subprocess,'check_output',side_effect=['head','']):
            self.assertTrue(policy.installed_source_matches(installed,'source'))
        for outputs in (['other',''],['head',' M ops/claude_code/gateway.py'],['head','?? injected.py']):
            with patch.object(policy.subprocess,'check_output',side_effect=outputs):
                self.assertFalse(policy.installed_source_matches(installed,'source'))
        with patch.object(policy.subprocess,'check_output') as git:
            self.assertFalse(policy.installed_source_matches(installed,'changed'))
            self.assertFalse(policy.installed_source_matches({**installed,'installed':False},'source'))
            git.assert_not_called()

    def test_ordinary_admission_requires_review_even_after_normal_install(self):
        data={'image':'tools','review_policy':'temporary-two-family-user-override'}
        active={**self.previous,'source_review_deferred':False,'authorized_by':'user','enabled':True,'review_policy':data['review_policy']}
        self.write('claude-code-activation.json',active);self.write('claude-code-validation.json',self.validation)
        with patch.object(policy,'installed_source_matches',return_value=True):
            self.assertFalse(policy.ready(data,self.ops,'source'))
        self.write('claude-code-source-review.json',{'head':'head','verdict':'pass','independent':True})
        with patch.object(policy,'installed_source_matches',return_value=False):
            self.assertFalse(policy.ready(data,self.ops,'source'))
            self.write('claude-code-activation.json',self.previous)
            self.assertFalse(policy.bootstrap_ready(data,self.ops,'source'))
        self.safe_state()

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


class NativeSourceBindingTests(unittest.TestCase):
    def test_real_git_new_head_and_tracked_or_untracked_edits_are_denied(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            def git(*args):return subprocess.check_output(['git','-C',str(root),*args],text=True,stderr=subprocess.DEVNULL).strip()
            git('init','--quiet');file=root/'fixture';file.write_text('first')
            git('add','fixture');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--quiet','-m','first')
            row={'installed':True,'source_head':git('rev-parse','HEAD'),'implementation_sha256':'source'}
            with patch.object(policy,'ROOT',root):
                self.assertTrue(policy.installed_source_matches(row,'source'))
                file.write_text('edited');self.assertFalse(policy.installed_source_matches(row,'source'))
                git('restore','fixture');extra=root/'injected';extra.write_text('untracked')
                self.assertFalse(policy.installed_source_matches(row,'source'));extra.unlink()
                file.write_text('second');git('add','fixture');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--quiet','-m','second')
                self.assertFalse(policy.installed_source_matches(row,'source'))
                self.assertTrue(policy.installed_source_matches({**row,'source_head':git('rev-parse','HEAD')},'source'))


if __name__ == '__main__':
    unittest.main()
