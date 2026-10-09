import importlib.util,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('doctor_gateway',Path(__file__).resolve().parents[1]/'dashboard/gateway.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
class DoctorGatewayTests(unittest.TestCase):
    def test_workshop_detection_does_not_reuse_other_project_agents(self):
        with tempfile.TemporaryDirectory() as root:
            home=Path(root);(home/'phpretro-skill-doctor/agents/.openhands/skills').mkdir(parents=True)
            payload={'snapshot':{},'detectedAgents':[{'platform':'codex','projectDetected':True,'globalDetected':False,'recommended':True}]}
            result=g.doctor_bootstrap(payload,True,home)
            self.assertEqual([a['platform'] for a in result['detectedAgents']],['openhands'])
            self.assertTrue(result['detectedAgents'][0]['recommended']);self.assertIsNone(result['snapshot'])
    def test_prefixed_routes_preserve_query(self):
        self.assertEqual(g.backend_route('/skill-doctor/api/bootstrap?x=1'),(38123,'/api/bootstrap?x=1',False))
        self.assertNotEqual(g.backend_route('/skill-doctor-evil/')[0],38123)
    def test_asset_and_api_prefixing(self):
        data=b'<script src="/assets/app.js"></script> fetch("/api/bootstrap"); new EventSource(`/api/scans/${id}`)'
        rewritten=g.skill_doctor_asset(data)
        self.assertIn(b'"/skill-doctor/assets/',rewritten)
        self.assertIn(b'"/skill-doctor/api/bootstrap',rewritten)
        self.assertIn(b'`/skill-doctor/api/scans/',rewritten)
    def test_agent_view_and_manual_only_default(self):
        self.assertEqual(g.backend_route('/agent-doctor/api/bootstrap'),(38123,'/api/bootstrap',False))
        data=g.skill_doctor_asset(b'<head></head><script src="/assets/app.js"></script>',b'/agent-doctor')
        self.assertIn(b'/agent-doctor/assets/',data)
        self.assertIn(b'useAiAudit:false',data)
        self.assertIn(b"'skill-doctor-analysis-mode','standard'",data)
