"""A local one-slot model process, isolated from the graph runtime dependencies."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import threading
from urllib.parse import urlsplit
from .domain import Invalid
from .models import generation_request,embedding_request


def create_server(runtime,host='127.0.0.1',port=8090):
    admission = threading.BoundedSemaphore(1)

    class Handler(BaseHTTPRequestHandler):
        server_version = 'EvidenceModel/0.1'

        def log_message(self,*args):
            pass

        def send_json(self,status,value):
            payload = json.dumps(value,allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError,ConnectionResetError):
                pass

        def trusted_request(self):
            name = urlsplit('http://'+self.headers.get('Host','')).hostname
            return name in {'127.0.0.1','localhost','graph-model'} and not self.headers.get('Origin')

        def do_GET(self):
            if not self.trusted_request():
                return self.send_json(403,{'error':'local_service_only'})
            if self.path != '/health':
                return self.send_json(404,{'error':'not_found'})
            self.send_json(200,runtime.health())

        def do_POST(self):
            self.connection.settimeout(65)
            if not self.trusted_request():
                return self.send_json(403,{'error':'local_service_only'})
            if self.headers.get('Content-Type','').split(';')[0].lower() != 'application/json':
                return self.send_json(415,{'error':'json_required'})
            lengths = self.headers.get_all('Content-Length') or []
            if self.headers.get('Transfer-Encoding') or len(lengths) != 1:
                return self.send_json(400,{'error':'bounded_length_required'})
            try:
                size = int(lengths[0])
                if not 1 <= size <= 65536:
                    raise ValueError()
                value = json.loads(self.rfile.read(size))
            except (ValueError,UnicodeError,TimeoutError):
                return self.send_json(400,{'error':'invalid_json_body'})
            if self.path not in ('/generate','/embed'):
                return self.send_json(404,{'error':'not_found'})
            if not admission.acquire(blocking=False):
                return self.send_json(503,{'error':'model_busy'})
            try:
                if self.path == '/generate':
                    result = runtime.generate(*generation_request(value))
                else:
                    result = runtime.embed(embedding_request(value))
                self.send_json(200,result)
            except Invalid as exc:
                self.send_json(422,{'error':'invalid_model_request','message':str(exc)})
            except Exception:
                self.send_json(503,{'error':'model_failed'})
            finally:
                admission.release()

    server = ThreadingHTTPServer((host,port),Handler)
    server.daemon_threads = True
    return server


def main():
    from .model_runtime import ModelRuntime
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models',required=True)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8090)
    parser.add_argument('--threads',type=int,default=2)
    args = parser.parse_args()
    runtime = ModelRuntime(args.models,args.threads)
    server = create_server(runtime,args.host,args.port)
    print(json.dumps(runtime.health()),flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
