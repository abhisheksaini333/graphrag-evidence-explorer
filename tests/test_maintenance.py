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
