#!/usr/bin/env python3
"""Save private provider profiles locally without probing or starting inference."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import routing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--activate-default', action='store_true', help='Explicitly select A6API Sol; otherwise preserve the active profile')
    args = parser.parse_args()
    root = Path.home() / 'phpretro-openhands'
    credentials = json.loads((root / 'secrets/providers.json').read_text())
    key = subprocess.check_output(['docker', 'exec', 'phpretro-openhands-ui', 'cat',
                                  '/home/openhands/.openhands/agent-canvas/api-key.txt'], text=True).strip()

    def api(path, payload=None):
        request = urllib.request.Request('http://127.0.0.1:38082' + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'X-Session-API-Key': key, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read())

    saved = []
    for provider in ('a6api', 'portdan'):
        for model in ('gpt-6.1-sol', 'gpt-6-luna', 'deepseek-v4.1-flash'):
            name = provider + '-' + model
            deepseek = model.startswith('deepseek')
            config = {'model': ('deepseek/' if deepseek else 'openai/') + model,
                      'base_url': 'https://api.a6api.com/v1' if provider == 'a6api' else 'https://portdan.com/v1',
                      'api_key': routing.credential(credentials, provider, model),
                      'api_mode': 'chat' if deepseek else 'responses',
                      'reasoning_effort': 'low', 'num_retries': 0, 'timeout': 120, 'usage_id': 'agent'}
            api('/api/profiles/' + name, {'llm': config, 'include_secrets': True})
            saved.append(name)
    if args.activate_default:
        api('/api/profiles/a6api-gpt-6.1-sol/activate', {})
    settings = api('/api/settings')
    report = {'configured_at': time.time(), 'profiles': saved,
              'active_profile': settings.get('active_profile'), 'provider_probes': 0,
              'ui_fallback': 'manual saved-profile selection',
              'manual_ui_accounting': 'independent of controller daily guard'}
    (root / 'webui-model-configuration.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
