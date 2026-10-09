"""Manual acceptance of the built extension without changing the live UI."""
import json,os,subprocess,sys,time
from pathlib import Path
here=Path(__file__).parent;base=Path.home()/'phpretro-skill-doctor'
manifest=json.loads((base/'extension-manifest.json').read_text());source=Path(manifest['package']).parent
env=dict(os.environ,HOME=str(base/'audit-home'),NODE_OPTIONS='--require '+str(here/'deep-mode.cjs'),DOCTOR_TEST_PORT='38125')
os.umask(0o077)
log=(base/'preview-private.log').open('w')
process=subprocess.Popen(['node',str(source/'dist/index.cjs'),'ui',str(base/'agents'),'--port','38125','--no-open'],env=env,stdout=log,stderr=log)
try:
 for _ in range(30):
  if '/session/' in (base/'preview-private.log').read_text():break
  time.sleep(.2)
 subprocess.run([sys.executable,str(here/'check_scan.py')],env=env,check=True)
finally:
 process.terminate()
 try:process.wait(15)
 except subprocess.TimeoutExpired:process.kill();process.wait()
 log.close();(base/'preview-private.log').unlink(missing_ok=True)
