import json
import threading
import unittest
import urllib.error
import urllib.request
from explorer.model_service import create_server
from explorer.model_client import ModelClient, ModelUnavailable


class FakeModel:
    def health(self):return {'status':'ready','model_revision':'fixture','embedding_dimensions':384}
    def generate(self,prompt,tokens):return {'text':'fixture answer','input_tokens':3,'output_tokens':2,'latency_ms':1.0}
    def embed(self,texts):return {'vectors':[[1.0]+[0.0]*383 for _ in texts],'input_tokens':len(texts),'latency_ms':1.0}


class ModelHTTPTests(unittest.TestCase):
    def setUp(self):
        self.server=create_server(FakeModel(),'127.0.0.1',0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_port)
        self.client=ModelClient(self.url)

    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join()

    def test_real_http_contract_and_strict_input_errors(self):
        self.assertEqual(self.client.generate('hello',10)['text'],'fixture answer')
        self.assertEqual(len(self.client.embed(['Atlas'])['vectors'][0]),384)
        with self.assertRaises(ModelUnavailable):self.client.generate('hello',300)

    def test_cross_origin_model_requests_are_denied(self):
        body=json.dumps({'prompt':'hello'}).encode()
        req=urllib.request.Request(self.url+'/generate',data=body,headers={'Content-Type':'application/json','Origin':'https://untrusted.example'})
        with self.assertRaises(urllib.error.HTTPError) as failure:urllib.request.urlopen(req)
        self.assertEqual(failure.exception.code,403)

    def test_wrong_content_type_is_not_interpreted_as_model_input(self):
        req=urllib.request.Request(self.url+'/generate',data=b'{"prompt":"hello"}',headers={'Content-Type':'text/plain'})
        with self.assertRaises(urllib.error.HTTPError) as failure:urllib.request.urlopen(req)
        self.assertEqual(failure.exception.code,415)
