import tempfile
from pathlib import Path
import unittest
from explorer.domain import DocumentInput
from explorer.store import Store, Conflict
from explorer.jobs import JobQueue


class JobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = 1000.
        self.store = Store(Path(self.temp.name)/'jobs.sqlite',clock=lambda:self.now)
        self.store.put_document(DocumentInput('atlas','Atlas','Mira owns Atlas.'))
        self.jobs = JobQueue(self.store)

    def tearDown(self):self.temp.cleanup()

    def test_enqueue_identity_and_exclusive_claim(self):
        a = self.jobs.enqueue('atlas','triples-v1')
        self.assertEqual(a['id'],self.jobs.enqueue('atlas','triples-v1')['id'])
        claim = self.jobs.claim('worker-a',lease_seconds=10)
        self.assertEqual(claim['attempt'],1)
        self.assertIsNone(self.jobs.claim('worker-b',lease_seconds=10))
        self.assertEqual(self.jobs.get(a['id'])['status'],'running')

    def test_expired_owner_cannot_publish_or_renew_after_reclaim(self):
        self.jobs.enqueue('atlas','triples-v1')
        a = self.jobs.claim('a',lease_seconds=10)
        self.now += 11
        b = self.jobs.claim('b',lease_seconds=10)
        self.assertNotEqual(a['lease_token'],b['lease_token'])
        with self.assertRaises(Conflict):self.jobs.finish(a['id'],a['lease_token'],'complete')
        with self.assertRaises(Conflict):self.jobs.heartbeat(a['id'],a['lease_token'],10)
        self.jobs.finish(b['id'],b['lease_token'],'complete')
        self.assertEqual(self.jobs.get(b['id'])['status'],'complete')

    def test_revision_change_supersedes_active_job(self):
        job = self.jobs.enqueue('atlas','triples-v1')
        a = self.jobs.claim('a',lease_seconds=10)
        self.store.put_document(DocumentInput('atlas','Atlas','Omar owns Atlas.'),1)
        with self.assertRaises(Conflict):self.jobs.finish(a['id'],a['lease_token'],'complete')
        self.assertIsNone(self.jobs.claim('b'))
        self.assertEqual(self.jobs.get(job['id'])['status'],'superseded')
        self.assertNotEqual(job['id'],self.jobs.enqueue('atlas','triples-v1')['id'])

    def test_crash_retries_are_bounded(self):
        job = self.jobs.enqueue('atlas','triples-v1')
        for i in range(3):
            self.assertEqual(self.jobs.claim(str(i),lease_seconds=1)['attempt'],i+1)
            self.now += 2
        self.assertIsNone(self.jobs.claim('four'))
        self.assertEqual(self.jobs.get(job['id'])['status'],'failed')
        self.assertEqual(self.jobs.get(job['id'])['error'],'lease_exhausted')
