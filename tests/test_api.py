import http.client,json,tempfile,threading,unittest
from pathlib import Path
from explorer.api import create_server
from explorer.store import Store
from test_search import AnswerModel

class APITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'db')
        self.server=create_server(self.store,AnswerModel(),port=0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.temp.cleanup()
    def request(self,method,path,value=None,headers=None):
        connection=http.client.HTTPConnection(*self.server.server_address)
        body=json.dumps(value) if value is not None else None
        connection.request(method,path,body,{'Content-Type':'application/json',**(headers or {})})
        response=connection.getresponse();data=response.read();status=response.status;connection.close()
        return status,json.loads(data)
    def test_create_update_and_delete_use_exact_revision(self):
        doc={'id':'atlas','title':'Atlas','text':'Mira owns Atlas.'}
        self.assertEqual(self.request('POST','/api/documents',doc)[0],201)
        self.assertEqual(self.request('POST','/api/documents',{**doc,'text':'Omar owns Atlas.'})[0],409)
        self.assertEqual(self.request('POST','/api/documents',{**doc,'text':'Omar owns Atlas.','expected_revision':1})[0],201)
        self.assertEqual(self.request('POST','/api/documents/atlas/delete',{'expected_revision':1})[0],409)
        self.assertEqual(self.request('POST','/api/documents/atlas/delete',{'expected_revision':2})[0],200)
    def test_foreign_origin_host_and_malformed_json_are_rejected(self):
        self.assertEqual(self.request('GET','/api/health',headers={'Host':'attacker.example'})[0],403)
        self.assertEqual(self.request('POST','/api/documents',{},headers={'Origin':'https://attacker.example'})[0],403)
        self.assertEqual(self.request('POST','/api/documents',[])[0],422)
    def test_budget_validation_does_not_leave_a_job_after_bad_request(self):
        self.request('POST','/api/documents',{'id':'atlas','title':'Atlas','text':'Mira owns Atlas.'})
        status,_=self.request('POST','/api/index',{'document_id':'atlas','max_calls':0})
        self.assertEqual(status,422)
        self.assertEqual(self.request('GET','/api/jobs')[1],[])
    def test_index_budget_is_installed_before_a_worker_can_claim_the_job(self):
        from explorer.jobs import JobQueue
        from explorer.budget import ModelBudget
        self.request('POST','/api/documents',{'id':'atlas','title':'Atlas','text':'Mira owns Atlas.'})
        status,job=self.request('POST','/api/index',{'document_id':'atlas','max_calls':3,'max_tokens':4096})
        self.assertEqual(status,202)
        claimed=JobQueue(self.store).claim('test')
        self.assertEqual(ModelBudget(JobQueue(self.store)).usage(claimed['id'])['max_calls'],3)
