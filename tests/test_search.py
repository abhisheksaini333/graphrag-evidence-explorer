import importlib.util,json,unittest
import test_evidence
from explorer.search import Search
from explorer.graph_adapter import PROFILE

class AnswerModel:
    def health(self):
        from explorer.models import model_manifest
        m=model_manifest();return {'model_revision':m['generation']['revision'],'embedding_revision':m['embedding']['revision'],'embedding_dimensions':384}
    def embed(self,texts):return {'vectors':[[1.]+[0.]*383 for _ in texts],'input_tokens':5}
    def generate(self,prompt,max_new_tokens=192):
        if 'MAP EVIDENCE' in prompt:text=json.dumps({'points':[{'description':'Mira owns Atlas [S1].','score':90}]})
        else:text=json.dumps({'answer':'Mira owns Atlas [S1].','citations':['S1']})
        return {'text':text,'input_tokens':50,'output_tokens':15}

@unittest.skipUnless(importlib.util.find_spec('graphrag'),'Requires frozen GraphRAG runtime')
class SearchTests(unittest.TestCase):
    setUp=test_evidence.EvidenceTests.setUp
    tearDown=test_evidence.EvidenceTests.tearDown
    publish=test_evidence.EvidenceTests.publish
    def prepared(self):
        self.publish();self.jobs.finish(self.job['id'],self.job['lease_token'],'complete')
        return Search(self.store,AnswerModel(),profile='profile')
    def test_real_framework_local_and_global_orchestration_keep_citations_and_usage(self):
        service=self.prepared()
        for mode in ('vector','local','global'):
            result=service.query('Who owns Atlas?',mode)
            self.assertEqual(result['status'],'complete',result)
            self.assertEqual(result['result']['answer'],'Mira owns Atlas [S1].')
            self.assertGreaterEqual(len(result['calls']),2)
            self.assertEqual(result['result']['passages'][0]['document_id'],'atlas')
    def test_update_during_model_call_never_returns_old_answer(self):
        from explorer.domain import DocumentInput
        service=self.prepared();original=service.model.generate
        def generate(*args,**kwargs):
            self.store.put_document(DocumentInput('atlas','Atlas','Omar owns Atlas.'),1)
            return original(*args,**kwargs)
        service.model.generate=generate
        result=service.query('Who owns Atlas?','local')
        self.assertEqual(result['status'],'stale');self.assertIsNone(result['result'])
        self.assertTrue(all(c['response'] is None for c in result['calls']))
