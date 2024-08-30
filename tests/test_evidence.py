import tempfile
from pathlib import Path
import unittest
from explorer.domain import DocumentInput,Invalid
from explorer.store import Store,Conflict
from explorer.jobs import JobQueue
from explorer.evidence import EvidenceStore


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.now=1000.
        self.store=Store(Path(self.temp.name)/'db',clock=lambda:self.now)
        self.store.put_document(DocumentInput('atlas','Atlas','Mira owns Atlas.'))
        self.jobs=JobQueue(self.store);self.jobs.enqueue('atlas','profile')
        self.job=self.jobs.claim('one',lease_seconds=10)
        self.evidence=EvidenceStore(self.jobs);self.chunk=self.store.chunks()[0]
        self.result={'accepted':[{'subject':'Mira','relation':'owns','object':'Atlas','start':0,'end':16,'support':'Mira owns Atlas.'}], 'rejected':[], 'nodes':{'MIRA':{},'ATLAS':{}},'edges':[{'source':'MIRA','target':'ATLAS'}],'response':{'text':'raw retained'},'framework':'graphrag-0.1.1'}
        self.vector=[1.]+[0.]*383

    def tearDown(self):self.temp.cleanup()

    def publish(self):return self.evidence.publish(self.job['id'],self.job['lease_token'],self.chunk['id'],self.result,self.vector)

    def test_complete_job_publishes_one_source_bound_claim_and_vector(self):
        self.publish();self.publish()
        self.assertEqual(self.evidence.snapshot('profile')['claims'],[])
        before=self.store.generation()
        self.jobs.finish(self.job['id'],self.job['lease_token'],'complete')
        snapshot=self.evidence.snapshot('profile')
        self.assertEqual(len(snapshot['claims']),1)
        self.assertEqual(len(snapshot['vectors']),1)
        self.assertEqual(snapshot['claims'][0]['support'],'Mira owns Atlas.')
        self.assertGreater(snapshot['generation'],before)
        self.assertEqual(self.evidence.completed_chunks(self.job['id']),{self.chunk['id']})

    def test_expired_publication_is_rejected_and_old_results_disappear_on_update(self):
        self.now+=11
        self.jobs.claim('two',lease_seconds=10)
        with self.assertRaises(Conflict):self.publish()
        self.assertEqual(self.evidence.completed_chunks(self.job['id']),set())

    def test_deleted_sources_do_not_remain_in_graph_snapshot(self):
        self.publish();self.jobs.finish(self.job['id'],self.job['lease_token'],'complete')
        self.store.delete_document('atlas',1)
        self.assertEqual(self.evidence.snapshot('profile')['claims'],[])
        self.assertEqual(self.evidence.snapshot('profile')['vectors'],[])

    def test_invalid_embeddings_and_unbacked_claims_are_rejected(self):
        for vector in [[0.]*384,[float('nan')]+[0.]*383,[1.]]:
            with self.assertRaises(Invalid):self.evidence.publish(self.job['id'],self.job['lease_token'],self.chunk['id'],self.result,vector)
        self.result['accepted'][0]['support']='Omar owns Atlas.'
        with self.assertRaises(Invalid):self.publish()
