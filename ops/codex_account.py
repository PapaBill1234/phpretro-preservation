"""Read subscription state through the official CLI; never read/return tokens."""
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import threading
import time

BASE = Path.home() / 'phpretro-codex'
CLI = BASE / 'cli/node_modules/.bin/codex'
AUTH = BASE / 'private'


def environment():
    # No inference-provider keys, alternate API base or API-key billing fallback.
    return {**{k:os.environ[k] for k in ('HOME','PATH','LANG','SSL_CERT_FILE','SSL_CERT_DIR') if k in os.environ},
            'CODEX_HOME':str(AUTH), 'NO_COLOR':'1'}


class AccountClient:
    def __enter__(self):
        self.messages = queue.Queue(maxsize=100)
        self.proc = subprocess.Popen([str(CLI),'app-server','--stdio',
            '-c','forced_login_method="chatgpt"'],env=environment(),
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            text=True,start_new_session=True)
        def reader():
            for line in iter(lambda:self.proc.stdout.readline(1024*1024), ''):
                try: self.messages.put(json.loads(line), timeout=1)
                except (ValueError,queue.Full): pass
        threading.Thread(target=reader,daemon=True).start()
        try:
            self.rpc(1,'initialize',{'clientInfo':{'name':'phpretro_supervisor','version':'1.0'},
                                    'capabilities':{'experimentalApi':True}})
            self.send({'method':'initialized'})
            return self
        except BaseException:
            self.__exit__(None,None,None)
            raise

    def send(self, value):
        self.proc.stdin.write(json.dumps(value)+'\n'); self.proc.stdin.flush()

    def rpc(self, identity, method, params):
        self.send({'id':identity,'method':method,'params':params})
        deadline = time.monotonic()+20
        while time.monotonic()<deadline:
            try: item=self.messages.get(timeout=min(1,max(.01,deadline-time.monotonic())))
            except queue.Empty:
                if self.proc.poll() is not None: raise RuntimeError('account service exited')
                continue
            if item.get('id') != identity: continue
            if 'error' in item: raise RuntimeError('account read unavailable')
            return item['result']
        raise TimeoutError('account read timed out')

    def __exit__(self, *_):
        if self.proc.poll() is None:
            try: os.killpg(self.proc.pid,signal.SIGTERM)
            except ProcessLookupError: pass
        try: self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired: os.killpg(self.proc.pid,signal.SIGKILL); self.proc.wait()
        for stream in (self.proc.stdin,self.proc.stdout): stream.close()


def window(value):
    if not isinstance(value,dict): return None
    used=value.get('usedPercent'); duration=value.get('windowDurationMins'); reset=value.get('resetsAt')
    if type(used) is not int or not 0<=used<=100: return None
    if type(duration) is not int or duration<=0 or type(reset) is not int or reset<=0: return None
    return {'used_percent':used,'duration_minutes':duration,'resets_at':reset}


def sanitize_limits(raw):
    buckets=raw.get('rateLimitsByLimitId')
    row=buckets.get('codex',{}) if isinstance(buckets,dict) else raw.get('rateLimits',{})
    if not isinstance(row,dict) or row.get('limitId') not in (None,'codex'): return {'available':False}
    primary,secondary=window(row.get('primary')),window(row.get('secondary'))
    return {'available':bool(primary and secondary), 'primary':primary, 'secondary':secondary,
            'ordinary_allowed':raw.get('ordinaryUsageAllowed') is True,
            'blocked':bool(row.get('rateLimitReachedType') or row.get('spendControlReached'))}


def read_account():
    try:
        with AccountClient() as client:
            account=client.rpc(2,'account/read',{'refreshToken':False}).get('account') or {}
            if account.get('type')!='chatgpt': return {'authenticated':False,'quota':{'available':False},'model_available':False}
            quota=sanitize_limits(client.rpc(3,'account/rateLimits/read',{}))
            models=client.rpc(4,'model/list',{'limit':100,'includeHidden':False}).get('data',[])
            return {'authenticated':True,'quota':quota,
                    'model_available':isinstance(models,list) and any(isinstance(row,dict) and
                        (row.get('id')=='gpt-6.1-sol' or row.get('model')=='gpt-6.1-sol') for row in models)}
    except (OSError,ValueError,KeyError,RuntimeError,TimeoutError,AttributeError,TypeError):
        return {'authenticated':False,'quota':{'available':False},'model_available':False}


def allowed(account):
    quota=account.get('quota',{})
    return bool(account.get('authenticated') and account.get('model_available') and quota.get('available')
        and quota.get('ordinary_allowed') and not quota.get('blocked')
        and quota['primary']['used_percent']<90 and quota['secondary']['used_percent']<90
        and quota['primary']['resets_at']>time.time() and quota['secondary']['resets_at']>time.time())


if __name__=='__main__': print(json.dumps(read_account()))
