"""Routing boundaries and isolated UI adoption, without providers or Docker."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

OPS = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gateway = load('webui_gateway', OPS / 'dashboard/gateway.py')
installer = load('webui_installer', OPS / 'openhands/webui_install.py')


class WebUIRouting(unittest.TestCase):
    def test_prefix_boundaries_and_query(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = gateway.ROOT
            gateway.ROOT = Path(directory)
            (gateway.ROOT / 'port').write_text('12345')
            try:
                cases = {
                    '/canvas/assets/ui.js?v=1': (38082, '/canvas/assets/ui.js?v=1', True),
                    '/openhands/api/settings?x=1': (38082, '/api/settings?x=1', True),
                    '/openhands?x=1': (38082, '/?x=1', True),
                    '/openhands-other/api': (8766, '/openhands-other/api', False),
                    '/canvas-other': (8766, '/canvas-other', False),
                    '/hermes/api?a=1': (9119, '/api?a=1', False),
                    '/chat/session': (8766, '/session', False),
                    '/api/state?refresh=1': (12345, '/api/state?refresh=1', False),
                    '/api/conversations': (8766, '/api/conversations', False),
                }
                for path, expected in cases.items():
                    with self.subTest(path=path):
                        self.assertEqual(gateway.backend_route(path), expected)
            finally:
                gateway.ROOT = previous

    def test_html_seed_preserves_non_html(self):
        payload = b'{"example":"unchanged"}'
        self.assertEqual(gateway.openhands_html(payload), payload)


class WebUIIsolation(unittest.TestCase):
    def test_adoption_rejects_host_mount_and_public_binding(self):
        container = {
            'Image': installer.IMAGE.split('@')[1],
            'Config': {'Env': ['AGENT_CANVAS_ALLOW_LAN_SESSION_KEY=true', 'AGENT_CANVAS_DISABLE_TELEMETRY=1', 'OH_TELEMETRY_EXPORTER=none']},
            'Mounts': [{'Type': 'volume', 'Name': name, 'Destination': target} for target, name in installer.VOLUMES.items()],
            'HostConfig': {'PortBindings': {'8000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '38082'}]},
                           'Memory': 1600 * 1024 * 1024, 'NanoCpus': 1000000000, 'PidsLimit': 256,
                           'CapDrop': ['ALL'], 'Privileged': False, 'SecurityOpt': ['no-new-privileges'],
                           'RestartPolicy': {'Name': 'unless-stopped'}},
        }
        self.assertTrue(installer.check_existing(container))
        container['Mounts'].append({'Type': 'bind', 'Source': '/var/run/docker.sock', 'Destination': '/var/run/docker.sock'})
        self.assertFalse(installer.check_existing(container))
        container['Mounts'].pop()
        container['HostConfig']['PortBindings']['8000/tcp'][0]['HostIp'] = '0.0.0.0'
        self.assertFalse(installer.check_existing(container))


if __name__ == '__main__':
    unittest.main()
