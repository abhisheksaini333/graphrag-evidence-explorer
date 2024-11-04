"""Exclusive operator API ownership and bounded local HTTP connections."""
from contextlib import AbstractContextManager
import fcntl
from http.server import ThreadingHTTPServer
from pathlib import Path
import threading
from .query_runs import QueryRuns
from .store import Conflict

class OperatorLease(AbstractContextManager):
    def __init__(self,database):self.path=Path(str(database)+'.api.lock');self.handle=None
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.handle=self.path.open('a')
        try:fcntl.flock(self.handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as error:
            self.handle.close();self.handle=None
            raise Conflict('Another operator API owns this database') from error
        return self
    def __exit__(self,*args):
        if self.handle:
            fcntl.flock(self.handle.fileno(),fcntl.LOCK_UN);self.handle.close()


def recover_queries(store):
    QueryRuns(store)
    with store.transaction() as db:
        return db.execute("UPDATE query_runs SET status='failed',result=NULL,error='process_interrupted' WHERE status='running' AND owner='api'").rowcount


class BoundedHTTPServer(ThreadingHTTPServer):
    daemon_threads=True
    request_queue_size=16
    def __init__(self,*args,**kwargs):
        self.slots=threading.BoundedSemaphore(16)
        super().__init__(*args,**kwargs)
    def get_request(self):
        request,address=super().get_request();request.settimeout(10)
        return request,address
    def process_request(self,request,address):
        if not self.slots.acquire(False):
            try:request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            finally:self.shutdown_request(request)
            return
        try:super().process_request(request,address)
        except BaseException:
            self.slots.release();raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()
