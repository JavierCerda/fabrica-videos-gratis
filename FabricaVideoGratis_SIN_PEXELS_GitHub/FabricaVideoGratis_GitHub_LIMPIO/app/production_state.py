"""Estado duradero en una rama independiente; nunca contiene OAuth ni sesiones de subida."""
import base64
import json
import os
from pathlib import Path
import requests


class StateStore:
    def __init__(self,branch,local_path=None):
        self.local=Path(local_path) if local_path else None
        self.branch=branch;self.sha=None;self.repo=os.getenv('GITHUB_REPOSITORY','JavierCerda/fabrica-videos-gratis')
        self.base='https://api.github.com/repos/'+self.repo
        self.session=requests.Session()
        if not self.local:
            token=os.getenv('GITHUB_TOKEN')
            if not token:raise RuntimeError('Falta el token temporal de Actions para guardar la cola')
            self.session.headers.update({'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})

    def request(self,method,path,**kw):
        response=self.session.request(method,self.base+path,timeout=(15,45),**kw)
        if response.status_code>=400:raise RuntimeError(f'No se pudo guardar el estado: HTTP {response.status_code}')
        return response.json()

    def load(self):
        if self.local:return json.loads(self.local.read_text()) if self.local.exists() else {'schema_version':1,'pending':[],'history':[],'attempts':{}}
        response=self.session.get(self.base+'/contents/automation-state.json',params={'ref':self.branch},timeout=(15,40))
        if response.status_code==404:
            ref=self.session.get(self.base+'/git/ref/heads/'+self.branch,timeout=(15,40))
            if ref.status_code==404:
                head=self.request('GET','/git/ref/heads/main')['object']['sha']
                self.request('POST','/git/refs',json={'ref':'refs/heads/'+self.branch,'sha':head})
            elif ref.status_code>=400:raise RuntimeError('No se pudo comprobar la rama de estado')
            return {'schema_version':1,'pending':[],'history':[],'attempts':{}}
        if response.status_code>=400:raise RuntimeError(f'No se pudo leer el estado: HTTP {response.status_code}')
        obj=response.json();self.sha=obj['sha'];return json.loads(base64.b64decode(obj['content']))

    def save(self,state):
        raw=json.dumps(state,ensure_ascii=False,indent=2)
        if self.local:
            self.local.parent.mkdir(parents=True,exist_ok=True);temp=self.local.with_suffix('.tmp');temp.write_text(raw);temp.replace(self.local);return
        body={'message':'Update Shorts queue and publication journal','branch':self.branch,
              'content':base64.b64encode(raw.encode()).decode()}
        if self.sha:body['sha']=self.sha
        self.sha=self.request('PUT','/contents/automation-state.json',json=body)['content']['sha']
