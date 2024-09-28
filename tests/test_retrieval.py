import unittest
from explorer.retrieval import retrieve,check_answer
from explorer.domain import Invalid

def passage(i,text,score):return {'chunk_id':i,'document_id':i,'revision':1,'start':0,'end':len(text),'text':text,'title':i,'vector':[score,(1-score**2)**.5]+[0.]*382}
class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.snapshot={'generation':1,'claims':[{'id':'c','chunk_id':'z','subject':'Iris','relation':'owns','object':'Lumen','support':'Iris owns Lumen.'}], 'vectors':[passage('a','Noise',1.),passage('z','Iris owns Lumen.',0.2)]}
    def test_local_graph_seed_improves_entity_evidence_over_vector_only(self):
        query=[1.]+[0.]*383
        self.assertEqual(retrieve(self.snapshot,'Lumen','vector',query,limit=1)['passages'][0]['chunk_id'],'a')
        self.assertEqual(retrieve(self.snapshot,'Lumen','local',query,limit=1)['passages'][0]['chunk_id'],'z')
    def test_context_budget_does_not_emit_uncited_or_partial_passages(self):
        result=retrieve(self.snapshot,'Lumen','local',[1.]+[0.]*383,character_budget=10)
        self.assertLessEqual(len(result['context']),10)
        self.assertEqual(len(result['passages']),0)
    def test_citation_gate_rejects_fabricated_and_uncited_answers(self):
        allowed=['S1']
        self.assertEqual(check_answer('{"answer":"Iris [S1]","citations":["S1"]}',allowed)['answer'],'Iris [S1]')
        for raw in ['Iris','{"answer":"Iris","citations":[]}','{"answer":"Iris [S2]","citations":["S2"]}']:
            with self.assertRaises(Invalid):check_answer(raw,allowed)
        self.assertTrue(check_answer('{"answer":"Insufficient evidence.","citations":[]}',allowed)['abstained'])
