import unittest, tempfile, pathlib, json, math, os
from unittest.mock import patch, Mock

class Maintenance(unittest.TestCase):

    def test_gre01(self):
        from explorer.retrieval import check_answer
        from explorer.domain import Invalid
        for answer in ('','   ','\ud800'):
            with self.assertRaises(Invalid): check_answer(json.dumps(dict(answer=answer,citations=['S1'])),['S1'])
        self.assertFalse(check_answer(json.dumps(dict(answer='Supported [S1]',citations=['S1'])),['S1'])['abstained'])
        self.assertTrue(check_answer(json.dumps(dict(answer='Insufficient evidence.',citations=[])),[])['abstained'])

    def test_gre02(self):
        from explorer.retrieval import retrieve
        from explorer.domain import Invalid
        snapshot=dict(vectors=[],claims=[],generation=0); vector=[1]+[0]*383
        for key in ('limit','character_budget'):
            for value in (True,0,-1,1.5,'3',20001):
                with self.assertRaises(Invalid): retrieve(snapshot,'question','vector',vector,**{key:value})
        self.assertEqual(retrieve(snapshot,'question','vector',vector)['passages'],[])

    def test_gre03(self):
        from explorer.model_client import ModelClient
        from explorer.domain import Invalid
        for url in ('file:///tmp/model','http://user:pass@localhost','http://localhost/path','http://localhost?key=x','http://localhost#secret','http://localhost:99999',None,' http://localhost'):
            with self.assertRaises(Invalid): ModelClient(url)
        for timeout in (True,0,'65',float('nan'),float('inf'),301):
            with self.assertRaises(Invalid): ModelClient(timeout=timeout)
        self.assertEqual(ModelClient('http://models:8090/').url,'http://models:8090')
        self.assertEqual(ModelClient('https://model.example').timeout,65)

    def test_gre04(self):
        import io
        from explorer.model_client import ModelClient, ModelUnavailable
        for payload in (b'{"ready":true}'+b' '*65536,b'{"ready":true}'):
            with patch('urllib.request.urlopen',return_value=io.BytesIO(payload)):
                if len(payload)>65536:
                    with self.assertRaises(ModelUnavailable): ModelClient().health()
                else: self.assertEqual(ModelClient().health(),dict(ready=True))

    def test_gre05(self):
        import io
        from explorer.model_client import ModelClient, ModelUnavailable
        for raw in (b'{"ready":false,"ready":true}',b'{"score":NaN}'):
            for method in ('health','generate','embed'):
                with patch('urllib.request.urlopen',return_value=io.BytesIO(raw)):
                    with self.assertRaises(ModelUnavailable):
                        getattr(ModelClient(),method)(*([] if method=='health' else ['input']))
        with patch('urllib.request.urlopen',return_value=io.BytesIO(b'{"ready":true}')):
            self.assertEqual(ModelClient().health(),dict(ready=True))

    def test_gre06(self):
        from explorer.store import Store
        from explorer.domain import DocumentInput, Invalid
        from explorer.jobs import JobQueue
        with tempfile.TemporaryDirectory() as root:
            store=Store(pathlib.Path(root)/'db');store.put_document(DocumentInput('doc','Title','Text'))
            queue=JobQueue(store)
            for budget in ([],[1],[1,100,3],1,{},'12'):
                with self.assertRaises(Invalid): queue.enqueue('doc','profile',budget)
                self.assertEqual(queue.list(),[])
            self.assertEqual(queue.enqueue('doc','profile',(1,100))['status'],'queued')

    def test_gre07(self):
        from explorer.store import Store
        from explorer.query_runs import QueryRuns
        from explorer.domain import Invalid
        with tempfile.TemporaryDirectory() as root:
            runs=QueryRuns(Store(pathlib.Path(root)/'db'))
            for generation in (False,0.0,-1,'0',None):
                with self.assertRaises(Invalid): runs.start('vector','Question?',generation)
                self.assertEqual(runs.list(),[])
            self.assertEqual(runs.start('vector','Question?',0)['generation'],0)

    def test_gre08(self):
        from explorer.store import Store
        from explorer.query_runs import QueryRuns
        from explorer.domain import Invalid
        with tempfile.TemporaryDirectory() as root:
            runs=QueryRuns(Store(pathlib.Path(root)/'db'));run=runs.start('vector','Question?',0)
            for kind in ('unknown','',None,3,[]):
                with self.assertRaises(Invalid): runs.reserve(run['id'],kind,1)
                self.assertEqual(runs.get(run['id'])['calls'],[])
            for kind in ('embed','generate','community_report'): runs.reserve(run['id'],kind,1)
            self.assertEqual(len(runs.get(run['id'])['calls']),3)

    def test_gre09(self):
        from explorer.store import Store, Conflict
        from explorer.query_runs import QueryRuns
        from explorer.domain import DocumentInput
        with tempfile.TemporaryDirectory() as root:
            store=Store(pathlib.Path(root)/'db');runs=QueryRuns(store)
            run=runs.start('vector','Question?',0);call=runs.reserve(run['id'],'generate',1)
            runs.finish(run['id'],dict(answer='complete'))
            with self.assertRaises(Conflict): runs.complete_call(call,dict(text='late'))
            self.assertEqual(runs.get(run['id'])['calls'][0]['status'],'pending')
            run=runs.start('vector','Question?',0);call=runs.reserve(run['id'],'generate',1)
            store.put_document(DocumentInput('doc','Title','New source'))
            with self.assertRaises(Conflict): runs.complete_call(call,dict(text='old source'))
            with store.connect() as db:
                self.assertIsNone(db.execute('SELECT response FROM query_calls WHERE id=?',(call,)).fetchone()[0])
            run=runs.start('vector','Question?',store.generation());call=runs.reserve(run['id'],'generate',1)
            runs.complete_call(call,dict(text='current'))
            self.assertEqual(runs.get(run['id'])['calls'][0]['status'],'complete')
