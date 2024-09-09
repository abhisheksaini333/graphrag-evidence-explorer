import unittest
import test_evidence
from explorer.corrections import Corrections
from explorer.store import Conflict

class CorrectionTests(unittest.TestCase):
    setUp=test_evidence.EvidenceTests.setUp
    tearDown=test_evidence.EvidenceTests.tearDown
    publish=test_evidence.EvidenceTests.publish
    def test_reject_and_restore_claim_invalidate_graph_and_passage_retrieval(self):
        self.publish();self.jobs.finish(self.job['id'],self.job['lease_token'],'complete')
        snap=self.evidence.snapshot('profile');claim=snap['claims'][0]
        corrections=Corrections(self.evidence)
        corrections.set_status(claim['id'],'rejected','Wrong relationship assignment',snap['generation'])
        self.assertEqual(self.evidence.snapshot('profile')['claims'],[])
        self.assertEqual(self.evidence.snapshot('profile')['vectors'],[])
        with self.assertRaises(Conflict):corrections.set_status(claim['id'],'accepted','stale screen',snap['generation'])
        corrections.set_status(claim['id'],'accepted','Checked against source',self.store.generation())
        self.assertEqual(len(self.evidence.snapshot('profile')['claims']),1)
        self.assertEqual(len(corrections.history()),2)

    def test_correcting_a_deleted_source_is_rejected(self):
        self.publish();self.jobs.finish(self.job['id'],self.job['lease_token'],'complete')
        claim=self.evidence.snapshot('profile')['claims'][0]
        self.store.delete_document('atlas',1)
        with self.assertRaises(Conflict):Corrections(self.evidence).set_status(claim['id'],'rejected','Unavailable',self.store.generation())
