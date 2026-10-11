"""Desktop observer is bounded/read-only and follows real builder receipts."""
import json,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import harness
from claude_code import desktop

class DesktopTests(unittest.TestCase):
    def test_invalid_identity_and_control_sequences_cannot_escape_view(self):
        for value in ('../private','',None,'not-a-run'):
            self.assertFalse(desktop.identity(value))
        safe=desktop.safe_text('hello\x1b]52;clipboard\x07 api_key=synthetic-secret-value')
        self.assertNotIn('\x1b',safe);self.assertNotIn('\x07',safe)
        self.assertNotIn('synthetic-secret-value',safe)

    def test_only_two_active_native_builders_are_selected(self):
        with tempfile.TemporaryDirectory() as folder:
            ops=Path(folder);receipts=ops/'state/receipts';receipts.mkdir(parents=True)
            for change in ({},{},{},{'role':'reviewer'},{'runtime':'openhands'},{'status':'complete'}):
                rid=str(uuid.uuid4());row={'run_id':rid,'runtime':'claude-code','role':'builder','status':'running','worker_pid':1,'worker_identity':'identity',**change}
                (receipts/(rid+'.json')).write_text(json.dumps(row))
            (receipts/'not-a-receipt.json').write_text('{}')
            with patch.object(desktop.worker,'alive',return_value=True):
                rows=desktop.active_builders(ops)
            self.assertEqual(len(rows),2)
            self.assertTrue(all(r['role']=='builder' and r['runtime']=='claude-code' and r['status']=='running' for r in rows))
            with patch.object(desktop.worker,'alive',return_value=False):self.assertEqual(desktop.active_builders(ops),[])

    def test_symlink_and_oversize_journals_are_not_read(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source';source.write_text('{"secret":"fixture"}')
            link=root/'link';link.symlink_to(source)
            self.assertEqual(desktop.read(link),{})
            self.assertEqual(desktop.read(source,4),{})
            self.assertEqual(desktop.read(root/'missing'),{})

    def test_view_reads_retained_redacted_journal_without_launching_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            ops=Path(folder);receipts=ops/'state/receipts';receipts.mkdir(parents=True);rid=str(uuid.uuid4())
            path=receipts/(rid+'.json');path.write_text(json.dumps({'run_id':rid,'runtime':'claude-code','role':'builder','status':'complete','model':'gpt-6.1-sol','rc':0}))
            path.with_suffix('.session.json').write_text(json.dumps({'schema':desktop.session_journal.SCHEMA,'events':[{'kind':'tool','text':'printf accepted'}]}))
            with patch('builtins.print') as output,patch.object(desktop.subprocess,'Popen') as launch:
                desktop.view(ops,rid,linger=0)
            launch.assert_not_called()
            self.assertTrue(any('printf accepted' in str(args) for args in output.call_args_list))

if __name__=='__main__':unittest.main()
