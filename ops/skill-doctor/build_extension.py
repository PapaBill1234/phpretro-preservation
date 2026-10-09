"""Build the pinned upstream extension before activating it. No credentials read."""
import hashlib,json,subprocess,sys,time
from pathlib import Path
base=Path.home()/'phpretro-skill-doctor';here=Path(__file__).parent
pin='fe1f942cf715a47faa67def0fa5f07882f3a84dc'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
inputs={n:digest(here/n) for n in ('patch_upstream.py','OpenHandsSessions.tsx','OpenHandsSessions.test.tsx','RuntimeDashboard.tsx','RuntimeDashboard.test.tsx','runtimeDashboard.css','build_extension.py')}
source=base/'extension-build'/str(int(time.time()));source.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
def run(*args,cwd=None):subprocess.run(args,cwd=cwd,check=True)
run('git','clone','--quiet','https://github.com/evilstar2016/skill-doctor.git',str(source))
run('git','checkout','--quiet',pin,cwd=source)
run(sys.executable,str(here/'patch_upstream.py'),str(source))
run('npm','ci','--ignore-scripts','--no-audit','--no-fund',cwd=source)
run('npm','run','typecheck:ui',cwd=source);run('npm','run','build',cwd=source)
run('npm','pack','--ignore-scripts',cwd=source)
package=source/'evilstar2025-skill-doctor-0.7.0.tgz';assert package.is_file()
manifest={'pin':pin,'inputs':inputs,'package':str(package),'sha256':digest(package)}
(base/'extension-manifest.json').write_text(json.dumps(manifest));(base/'extension-manifest.json').chmod(0o600)
print('Prepared pinned Skill Doctor extension; activation is separate.')
