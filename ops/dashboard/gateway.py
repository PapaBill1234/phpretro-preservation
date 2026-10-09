#!/usr/bin/env python3
"""Authenticated loopback gateway; HTTPS arrives through Cloudflare Tunnel."""
import base64,hashlib,http.client,http.server,json,os,re,secrets,select,socket,sqlite3,subprocess,threading,time
from pathlib import Path
from http.cookies import SimpleCookie
from urllib.parse import urlsplit
ROOT=Path.home()/'phpretro-dashboard'; DB=ROOT/'access.sqlite3'; RATE={}; RATE_LOCK=threading.Lock()
OPENHANDS_PORT=38082

def backend_route(raw_path):
 path=urlsplit(raw_path).path
 if path=='/canvas' or path.startswith('/canvas/'):
  return OPENHANDS_PORT,raw_path,True
 if path=='/openhands' or path.startswith('/openhands/'):
  suffix=raw_path[len('/openhands'):]
  return OPENHANDS_PORT,('/'+suffix if not suffix.startswith('/') else suffix),True
 if path=='/hermes' or path.startswith('/hermes/'):
  suffix=raw_path[len('/hermes'):]
  return 9119,('/'+suffix if not suffix.startswith('/') else suffix),False
 if path in ('/','/api/state','/api/stop','/api/balance'):
  return int((ROOT/'port').read_text()),raw_path,False
 if path=='/chat' or path.startswith('/chat/'):
  suffix=raw_path[len('/chat'):]
  return 8766,('/'+suffix if not suffix.startswith('/') else suffix),False
 return 8766,raw_path,False

def openhands_html(data):
 # The pinned Canvas frontend supports named backends. Seed ours without
 # changing Codex's root API routes or overwriting a user's other backends.
 script=b'''<script>(function(){
 const key=window.__AGENT_CANVAS_SESSION_API_KEY__;if(!key)return;
 let rows=[],active=null;
 try{rows=JSON.parse(localStorage.getItem('openhands-backends')||'[]');if(!Array.isArray(rows))rows=[];}catch(e){}
 try{active=JSON.parse(sessionStorage.getItem('openhands-active-backend')||localStorage.getItem('openhands-active-backend')||'null');}catch(e){}
 rows=rows.filter(x=>x&&x.id!=='phpretro-local');
 rows.push({id:'phpretro-local',name:'PHPRetro OpenHands',host:location.origin+'/openhands',apiKey:key,kind:'local'});
 localStorage.setItem('openhands-backends',JSON.stringify(rows));
 if(!active||active.backendId==='default-local'||active.backendId==='phpretro-local'){
  const selection=JSON.stringify({backendId:'phpretro-local',orgId:null});
  sessionStorage.setItem('openhands-active-backend',selection);localStorage.setItem('openhands-active-backend',selection);
 }
})();</script>'''
 return data.replace(b'</head>',script+b'</head>',1)
def db():
 c=sqlite3.connect(DB,timeout=1); c.execute('CREATE TABLE IF NOT EXISTS account(id INTEGER PRIMARY KEY CHECK(id=1),salt TEXT,hash TEXT)'); c.execute('CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY,expires REAL)'); c.commit(); return c
def configured():
 with db() as c: return bool(c.execute('SELECT 1 FROM account').fetchone())
def digest(password,salt): return hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1,dklen=32).hex()
def public_url():
 try:
  source=ROOT/'public-domain' if (ROOT/'public-domain').exists() else ROOT/'public-url'
  value=source.read_text().strip()
  return value if value=='https://phpretro.work.gd' or re.fullmatch(r'https://[a-z0-9-]+\.trycloudflare\.com',value) else ''
 except OSError: return ''
def setup_code():
 p=ROOT/'secrets/setup-code'
 if not p.exists(): p.write_text(secrets.token_urlsafe(32)+'\n'); p.chmod(0o600)
 return p.read_text().strip()
class Handler(http.server.BaseHTTPRequestHandler):
 protocol_version='HTTP/1.1'
 def log_message(self,*args): pass
 def setup(self): super().setup(); self.connection.settimeout(35)
 def allowed_host(self):
  host=self.headers.get('Host',''); allowed=['127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port)]
  pub=public_url()
  if pub: allowed.append(urlsplit(pub).netloc)
  return host in allowed
 def origin(self): return ('https://' if self.headers.get('Host')==urlsplit(public_url()).netloc and public_url() else 'http://')+self.headers.get('Host','')
 def same_origin(self): return self.headers.get('Origin')==self.origin() and self.headers.get('Sec-Fetch-Site')!='cross-site'
 def cookie(self):
  try:
   cookies=SimpleCookie(); cookies.load(self.headers.get('Cookie','')); return cookies['pd_session'].value if 'pd_session' in cookies else ''
  except Exception: return ''
 def authenticated(self):
  token=self.cookie()
  if not re.fullmatch(r'[a-zA-Z0-9_-]{40,100}',token): return False
  with db() as c: return bool(c.execute('SELECT 1 FROM sessions WHERE hash=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone())
 def send(self,status,body,kind='application/json',headers=None):
  data=json.dumps(body).encode() if kind=='application/json' else body.encode() if isinstance(body,str) else body
  if status>=400: self.close_connection=True
  self.send_response(status); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Referrer-Policy','no-referrer'); self.send_header('X-Frame-Options','SAMEORIGIN'); self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'")
  if self.origin().startswith('https://'): self.send_header('Strict-Transport-Security','max-age=31536000')
  for k,v in (headers or {}).items(): self.send_header(k,v)
  self.end_headers(); self.wfile.write(data)
 def body(self):
  n=int(self.headers.get('Content-Length','0'))
  if n<1 or n>65536 or self.headers.get('Transfer-Encoding'): raise ValueError()
  x=json.loads(self.rfile.read(n))
  if not isinstance(x,dict): raise ValueError()
  return x
 def do_GET(self):
  if not self.allowed_host(): self.send(403,{'error':'Host rejected'}); return
  path=urlsplit(self.path).path
  if path=='/auth/status': self.send(200,{'configured':configured(),'authenticated':self.authenticated()}); return
  if not self.authenticated():
   if path in ('/','/login'): self.send(200,(ROOT/'login.html').read_bytes(),'text/html; charset=utf-8')
   else: self.send(401,{'error':'Sign in required'})
   return
  if path=='/api/access/status':
   self.send(200,{'public_url':public_url(),'provider':'A6API','endpoint':'https://api.a6api.com/v1','credential_configured':(ROOT/'secrets/a6api.env').exists(),'workspace':str(ROOT),'desktop':'enabled'}); return
  if path=='/login': self.send(303,b'',headers={'Location':'/'}); return
  self.proxy()
 def do_POST(self):
  if not self.allowed_host() or not self.same_origin(): self.send(403,{'error':'Origin/Host rejected'}); return
  path=urlsplit(self.path).path
  if path in ('/auth/setup','/auth/login'):
   ip=self.headers.get('CF-Connecting-IP',self.client_address[0]); now=time.time()
   with RATE_LOCK:
    attempts=RATE.setdefault(ip,[]); attempts[:]=[x for x in attempts if now-x<300]
    if len(attempts)>=5: self.send(429,{'error':'Try again in five minutes'}); return
    attempts.append(now)
    if len(RATE)>1000: RATE.clear()
   try:
    data=self.body(); password=data.get('password')
    if not isinstance(password,str) or not 12<=len(password)<=256: self.send(400,{'error':'Use a password of 12?256 characters'}); return
    with db() as c:
     row=c.execute('SELECT salt,hash FROM account WHERE id=1').fetchone()
     if path=='/auth/setup':
      if row: self.send(409,{'error':'Setup already completed'}); return
      supplied=data.get('setup_code','')
      if not isinstance(supplied,str) or not secrets.compare_digest(supplied,setup_code()): self.send(403,{'error':'Owner setup code required'}); return
      salt=secrets.token_hex(16); hashed=digest(password,salt)
      try: c.execute('INSERT INTO account VALUES(1,?,?)',(salt,hashed)); c.commit()
      except sqlite3.IntegrityError: self.send(409,{'error':'Setup already completed'}); return
     elif not row or not secrets.compare_digest(digest(password,row[0]),row[1]): self.send(401,{'error':'Incorrect password'}); return
     token=secrets.token_urlsafe(32); c.execute('DELETE FROM sessions WHERE expires<?',(now,)); c.execute('INSERT INTO sessions VALUES(?,?)',(hashlib.sha256(token.encode()).hexdigest(),now+8*3600)); c.commit()
    secure='; Secure' if self.origin().startswith('https://') else ''
    self.send(200,{'ok':True},headers={'Set-Cookie':'pd_session='+token+'; Path=/; HttpOnly; SameSite=Strict; Max-Age=28800'+secure})
   except (ValueError,TypeError,sqlite3.Error): self.send(400,{'error':'Invalid request'})
   return
  if not self.authenticated(): self.send(401,{'error':'Sign in required'}); return
  if path=='/auth/logout':
   with db() as c: c.execute('DELETE FROM sessions WHERE hash=?',(hashlib.sha256(self.cookie().encode()).hexdigest(),)); c.commit()
   self.send(200,{'ok':True},headers={'Set-Cookie':'pd_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'}); return
  if path=='/api/access/provider': self.send(405,{'error':'Configure A6API using the masked SSH setup command.'}); return
  if path=='/api/access/password':
   try:
    data=self.body(); old=data.get('current_password',''); new=data.get('password','')
    if not isinstance(old,str) or not isinstance(new,str) or not 12<=len(new)<=256: raise ValueError()
    with db() as c:
     row=c.execute('SELECT salt,hash FROM account WHERE id=1').fetchone()
     if not row or not secrets.compare_digest(digest(old,row[0]),row[1]): self.send(403,{'error':'Incorrect current password'}); return
     salt=secrets.token_hex(16); c.execute('UPDATE account SET salt=?,hash=? WHERE id=1',(salt,digest(new,salt))); c.execute('DELETE FROM sessions'); c.commit()
    self.send(200,{'ok':True})
   except Exception: self.send(400,{'error':'Invalid password'})
   return
  self.proxy()
 def do_PUT(self):
  if not self.allowed_host() or not self.same_origin() or not self.authenticated(): self.send(403,{'error':'Forbidden'}); return
  self.proxy()
 do_PATCH=do_PUT
 do_DELETE=do_PUT
 def proxy(self):
  port,upstream_path,openhands=backend_route(self.path)
  if self.headers.get('Upgrade','').lower()=='websocket': self.websocket(port,upstream_path); return
  try:
   n=int(self.headers.get('Content-Length','0'))
   if n<0 or n>24*1024*1024 or self.headers.get('Transfer-Encoding'): raise ValueError()
   body=self.rfile.read(n) if n else None
   headers={k:v for k,v in self.headers.items() if k.lower() not in ('host','origin','cookie','connection','authorization','proxy-authorization','x-forwarded-host','x-forwarded-proto','x-forwarded-prefix','cf-connecting-ip','cf-visitor','accept-encoding')}
   headers['Host']='127.0.0.1:'+str(port)
   if port==9119: headers['X-Forwarded-Prefix']='/hermes'
   if self.command not in ('GET','HEAD'): headers['Origin']='http://127.0.0.1:'+str(port)
   con=http.client.HTTPConnection('127.0.0.1',port,timeout=120); con.request(self.command,upstream_path,body,headers); resp=con.getresponse()
   # WebUI streaming responses require immediate forwarding; do not buffer turns.
   streaming=resp.getheader('Content-Type','').startswith('text/event-stream') or resp.getheader('Content-Type','').startswith('application/x-ndjson')
   self.send_response(resp.status)
   for k,v in resp.getheaders():
    if k.lower() not in ('connection','transfer-encoding','set-cookie','content-security-policy','x-frame-options','content-length'): self.send_header(k,v)
   self.send_header('X-Frame-Options','SAMEORIGIN'); self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'self'; frame-src 'self'; base-uri 'self'")
   if streaming:
    self.send_header('Connection','close'); self.end_headers(); self.close_connection=True
    while True:
     chunk=resp.read1(65536)
     if not chunk: break
     self.wfile.write(chunk); self.wfile.flush()
   else:
    data=resp.read(32*1024*1024)
    if openhands and resp.getheader('Content-Type','').startswith('text/html'):
     data=openhands_html(data)
    self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
   con.close()
  except (OSError,ValueError,http.client.HTTPException):
   self.send(502,{'error':'Backend unavailable; retry shortly'})
 def websocket(self,port,path):
  if not self.same_origin(): self.send(403,{'error':'WebSocket origin rejected'}); return
  upstream=None
  try:
   upstream=socket.create_connection(('127.0.0.1',port),timeout=10)
   headers={k:v for k,v in self.headers.items() if k.lower() not in ('host','origin','cookie','authorization','proxy-authorization','x-forwarded-host','x-forwarded-proto','x-forwarded-prefix','cf-connecting-ip','cf-visitor')}
   headers['Host']='127.0.0.1:'+str(port)
   if port==9119: headers['X-Forwarded-Prefix']='/hermes'; headers['Origin']='http://127.0.0.1:'+str(port)
   raw='GET '+path+' HTTP/1.1\r\n'+''.join(k+': '+v+'\r\n' for k,v in headers.items())+'\r\n'; upstream.sendall(raw.encode())
   self.connection.settimeout(None); upstream.settimeout(None); deadline=time.monotonic()+8*3600
   while time.monotonic()<deadline and self.authenticated():
    ready,_,_=select.select([upstream,self.connection],[],[],30)
    for sock in ready:
     data=sock.recv(65536)
     if not data: return
     (self.connection if sock is upstream else upstream).sendall(data)
   self.close_connection=True
  except OSError: pass
  finally:
   if upstream: upstream.close()
   self.close_connection=True
if __name__=='__main__':
 os.umask(0o077); setup_code()
 p=ROOT/'gateway-port'
 if p.exists(): port=int(p.read_text().strip()); server=http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler)
 else:
  for _ in range(100):
   port=20000+secrets.randbelow(40001)
   try: server=http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler); break
   except OSError: continue
  else: raise RuntimeError('no free port')
  p.write_text(str(port)+'\n')
 server.daemon_threads=True; print('Authenticated gateway on 127.0.0.1:'+str(port),flush=True); server.serve_forever()
