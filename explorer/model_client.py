"""Bounded local model HTTP contract; no automatic generation retries."""
import json
import urllib.error
import urllib.request
from .domain import Invalid


class ModelUnavailable(Invalid):
    pass


class ModelClient:
    def __init__(self,url='http://127.0.0.1:8090',timeout=65):
        self.url,self.timeout = url.rstrip('/'),timeout

    def post(self,path,payload):
        body = json.dumps(payload,allow_nan=False).encode()
        request = urllib.request.Request(self.url+path,data=body,headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=self.timeout) as response:
                raw = response.read(1024*1024+1)
                if len(raw) > 1024*1024:
                    raise ModelUnavailable('Model response exceeds the bounded contract')
                return json.loads(raw)
        except (OSError,ValueError) as exc:
            raise ModelUnavailable('Local model request failed; inspect model readiness and request limits') from exc

    def health(self):
        try:
            with urllib.request.urlopen(self.url+"/health",timeout=5) as response:
                return json.loads(response.read(65536))
        except (OSError,ValueError) as exc:
            raise ModelUnavailable("Local model is not ready") from exc

    def generate(self,prompt,max_new_tokens=192):
        return self.post('/generate',{'prompt':prompt,'max_new_tokens':max_new_tokens})

    def embed(self,texts):
        return self.post('/embed',{'texts':texts})
