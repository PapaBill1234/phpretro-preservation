"""Private bounded SDK timeline. Never serialize agents, configs or exceptions."""
import re,time
import integrity as control

SCHEMA='phpretro.session-journal.v1'
KINDS={'brief','assistant','tool','provider_request','provider_error','result'}

def redact(text,secrets=()):
    text=str(text)
    for secret in secrets:
        if isinstance(secret,str) and len(secret)>=4:text=text.replace(secret,'[redacted]')
    text=re.sub(r'(?i)\b(?:sk-|oc_sk_)[a-z0-9_-]{12,}', '[redacted]',text)
    text=re.sub(r'(?i)(Bearer\s+)[a-z0-9._~-]+',r'\1[redacted]',text)
    text=re.sub(r'(?im)((?:api[_-]?key|authorization|password|access[_-]?token)\s*[=:]\s*)[^\n,}]+',r'\1[redacted]',text)
    return text

class Journal:
    def __init__(self,path,secrets=()):
        self.path=path;self.secrets=tuple(secrets);self.failed=False
        self.data={'schema':SCHEMA,'complete':False,'truncated':False,'events':[]}
    def save(self):
        self.data['updated_at']=time.time()
        try:control.atomic_json(self.path,self.data)
        except OSError:self.failed=True
    def add(self,kind,text='',**meta):
        if kind not in KINDS:raise ValueError('invalid journal event')
        if len(self.data['events'])>=512:
            self.data['truncated']=True;self.save();return
        safe=redact(text,self.secrets)
        if len(safe)>4000:self.data['truncated']=True
        row={'at':time.time(),'kind':kind,'text':safe[:4000]}
        for key in ('rc','request','provider'):
            if key in meta and (type(meta[key]) is int or key=='provider' and meta[key] in ('a6api','portdan','anthropic')):row[key]=meta[key]
        self.data['events'].append(row);self.save()
    def finish(self,complete):
        self.data['complete']=bool(complete and not self.failed and not self.data['truncated']);self.save()
