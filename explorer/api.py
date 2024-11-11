"""Loopback operator API with same-origin mutations and bounded query admission."""
import argparse,json,logging,mimetypes,threading
from http.server import BaseHTTPRequestHandler
from .runtime_control import BoundedHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,unquote
from .budget import ModelBudget
from .corrections import Corrections
from .json_contract import strict_json
from .domain import DocumentInput,Invalid
from .evidence import EvidenceStore
from .graph import build_graph,neighborhood
from .graph_adapter import PROFILE
from .jobs import JobQueue
from .model_client import ModelClient,ModelUnavailable
from .query_runs import QueryRuns
from .reports import Reports
from .search import Search
from .store import Store,Conflict,Missing


def create_server(store,model,host='127.0.0.1',port=8089,static=None):
    jobs=JobQueue(store);evidence=EvidenceStore(jobs);corrections=Corrections(evidence)
    runs=QueryRuns(store);search=Search(store,model,owner='api');reports=Reports(store,model,owner='api')
    admission=threading.BoundedSemaphore(1)
    static=Path(static).resolve() if static else None
    graph_lock=threading.Lock();graph_cache={}
    def current_graph():
        with graph_lock:
            generation=store.generation()
            if graph_cache.get('generation')!=generation:
                graph_cache.clear();graph_cache.update(build_graph(evidence.snapshot(PROFILE)))
            if store.generation()!=graph_cache['generation']:raise Conflict('Graph changed while loading; refresh')
            return dict(graph_cache)
    def public_job(job):
        return {k:v for k,v in job.items() if k not in ('lease_token',)}

    class Handler(BaseHTTPRequestHandler):
        server_version='EvidenceExplorer/0.1'
        def log_message(self,*args):pass
        def setup(self):
            super().setup();self.connection.settimeout(10)
        def send(self,status,value,content_type='application/json'):
            raw=json.dumps(value,allow_nan=False).encode() if content_type=='application/json' else value
            self.send_response(status)
            for key,val in {'Content-Type':content_type,'Content-Length':str(len(raw)),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"}.items():self.send_header(key,val)
            self.end_headers()
            try:self.wfile.write(raw)
            except (BrokenPipeError,ConnectionResetError):pass
        def trust(self):
            hosts=self.headers.get_all('Host') or []
            if len(hosts)!=1:return False
            try:
                target=urlsplit('http://'+hosts[0])
                if target.hostname not in ('127.0.0.1','localhost','graph-api') or target.username or target.path:return False
                origin=self.headers.get('Origin')
                if origin:
                    allowed={'http://127.0.0.1:'+str(self.server.server_port),'http://localhost:'+str(self.server.server_port),'http://127.0.0.1:5189','http://localhost:5189'}
                    if origin not in allowed:return False
                return self.headers.get('Sec-Fetch-Site') not in ('cross-site',)
            except ValueError:return False
        def body(self):
            if self.headers.get('Content-Type','').split(';')[0].lower()!='application/json':raise Invalid('JSON content type is required')
            lengths=self.headers.get_all('Content-Length') or []
            if len(lengths)!=1 or self.headers.get('Transfer-Encoding'):raise Invalid('One bounded Content-Length is required')
            try:
                size=int(lengths[0])
                if not 1<=size<=262144:raise ValueError()
                raw=self.rfile.read(size)
                if len(raw)!=size:raise ValueError()
                value=strict_json(raw)
            except (ValueError,UnicodeError,TimeoutError) as error:raise Invalid('Invalid or oversized JSON body') from error
            if not isinstance(value,dict):raise Invalid('JSON object is required')
            return value
        def handle_request(self,method):
            if not self.trust():return self.send(403,{'error':'local_origin_required'})
            try:
                path=unquote(urlsplit(self.path).path)
                status,value=self.route(method,path,self.body() if method=='POST' else None)
                self.send(status,value)
            except Missing as error:self.send(404,{'error':'not_found','message':str(error)})
            except Conflict as error:self.send(409,{'error':'conflict','message':str(error)})
            except ModelUnavailable as error:self.send(503,{'error':'model_unavailable','message':str(error)})
            except Invalid as error:self.send(422,{'error':'invalid_request','message':str(error)})
            except (KeyError,TypeError):self.send(422,{'error':'invalid_request','message':'Required request fields are missing or invalid'})
            except Exception:
                logging.exception('Operator request failed');self.send(500,{'error':'request_failed'})
        def do_GET(self):
            if self.path.startswith('/api/'):return self.handle_request('GET')
            if not self.trust():return self.send(403,{'error':'local_origin_required'})
            if not static:return self.send(404,{'error':'frontend_not_built'})
            path=(static/unquote(urlsplit(self.path).path).lstrip('/')).resolve()
            if not path.is_relative_to(static):return self.send(404,{'error':'not_found'})
            if path==static:path=static/'index.html'
            if not path.is_file():return self.send(404,{'error':'not_found'})
            self.send(200,path.read_bytes(),mimetypes.guess_type(str(path))[0] or 'application/octet-stream')
        def do_POST(self):return self.handle_request('POST')
        def route(self,method,path,value):
            if method=='GET':
                if path=='/api/health':return 200,{'status':'ready','generation':store.generation(),'profile':PROFILE}
                if path=='/api/documents':return 200,store.list_documents()
                if path.startswith('/api/documents/'):return 200,store.get_document(path.rsplit('/',1)[1])
                if path=='/api/jobs':return 200,[{**public_job(j),'usage':ModelBudget(jobs).usage(j['id'])} for j in jobs.list()]
                if path=='/api/graph':return 200,current_graph()
                if path.startswith('/api/entities/'):return 200,neighborhood(current_graph(),path.rsplit('/',1)[1],2)
                if path.startswith('/api/passages/'):return 200,store.get_chunk(path.rsplit('/',1)[1])
                if path=='/api/corrections':return 200,corrections.history()
                if path=='/api/queries':return 200,runs.list()
                if path.startswith('/api/queries/'):return 200,runs.get(path.rsplit('/',1)[1])
                if path.startswith('/api/extractions/'):
                    job=jobs.get(path.rsplit('/',1)[1]);document=store.get_document(job['document_id'])
                    if document['revision']!=job['revision']:raise Conflict('Extraction source changed')
                    return 200,evidence.extraction_details(job['id'])
            else:
                if path=='/api/demo':
                    from .seed import seed
                    return 202,[public_job(job) for job in seed(store,Path(__file__).resolve().parents[1]/'examples/corpus.json')]
                if path=='/api/documents':return 201,store.put_document(DocumentInput.parse(value),value.get('expected_revision'))
                if path.startswith('/api/documents/') and path.endswith('/delete'):return 200,store.delete_document(path.split('/')[3],value['expected_revision'])
                if path=='/api/index':
                    calls,tokens=value.get('max_calls',32),value.get('max_tokens',65536)
                    if type(calls) is not int or not 1<=calls<=128 or type(tokens) is not int or not 1<=tokens<=262144:raise Invalid('Index budget is outside the supported limits')
                    job=jobs.enqueue(value['document_id'],PROFILE,budget=(calls,tokens))
                    return 202,public_job(job)
                if path.startswith('/api/jobs/'):
                    parts=path.split('/');action=parts[-1];job_id=parts[-2]
                    if action=='cancel':return 200,public_job(jobs.cancel(job_id))
                    if action=='retry':return 202,public_job(jobs.retry(job_id))
                if path=='/api/corrections':return 200,corrections.set_status(value['claim_id'],value['status'],value['reason'],value['expected_generation'])
                if path in ('/api/query','/api/community-report'):
                    if not admission.acquire(False):return 429,{'error':'query_busy','message':'One query or report is already running'}
                    try:
                        result=search.query(value['question'],value['mode']) if path=='/api/query' else reports.generate(value['community_id'],value['expected_generation'])
                        return 200,result
                    finally:admission.release()
            raise Missing('Route is unavailable')
    server=BoundedHTTPServer((host,port),Handler);server.daemon_threads=True
    return server


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',default='.data/corpus.sqlite');parser.add_argument('--model-url',default='http://127.0.0.1:8090')
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8089);parser.add_argument('--static',default='web/dist')
    args=parser.parse_args()
    from .runtime_control import OperatorLease,recover_queries
    with OperatorLease(args.database):
        store=Store(args.database);recover_queries(store)
        # Import the scientific runtime before announcing API readiness.
        build_graph({'generation':0,'claims':[],'vectors':[]})
        server=create_server(store,ModelClient(args.model_url),args.host,args.port,args.static)
        print(f'Evidence Explorer listening on {args.host}:{args.port}',flush=True)
        try:server.serve_forever()
        finally:server.server_close()

if __name__=='__main__':main()
