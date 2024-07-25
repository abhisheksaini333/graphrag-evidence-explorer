import tempfile
from pathlib import Path
import unittest
from explorer.domain import DocumentInput
from explorer.store import Store, Conflict, Missing


def document(text='Mira owns Atlas.',title='Atlas'):
    return DocumentInput.parse({'id':'atlas','title':title,'text':text})


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'corpus.sqlite'
        self.store = Store(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_revision_identity_is_durable_and_old_text_immutable(self):
        first = self.store.put_document(document())
        self.assertEqual(first['revision'],1)
        second = self.store.put_document(document('Omar owns Atlas.'),expected_revision=1)
        self.assertEqual(second['revision'],2)
        reopened = Store(self.path)
        self.assertEqual(reopened.get_document('atlas')['text'],'Omar owns Atlas.')
        self.assertEqual(reopened.get_document('atlas',revision=1)['text'],'Mira owns Atlas.')
        self.assertEqual(len(reopened.list_documents()),1)

    def test_compare_and_swap_prevents_lost_update(self):
        self.store.put_document(document())
        self.store.put_document(document('Nora owns Atlas.'),expected_revision=1)
        with self.assertRaises(Conflict):self.store.put_document(document('Omar owns Atlas.'),expected_revision=1)
        with self.assertRaises(Conflict):self.store.put_document(document())
        self.assertEqual(self.store.get_document('atlas')['revision'],2)

    def test_identical_retry_does_not_create_revision(self):
        self.store.put_document(document())
        before = self.store.generation()
        result = self.store.put_document(document(),expected_revision=1)
        self.assertFalse(result['changed'])
        self.assertEqual(self.store.generation(),before)
        with self.assertRaises(Missing):self.store.get_document('absent')

    def test_each_revision_persists_exact_source_chunks(self):
        self.store.put_document(document('Mira owns Atlas.\n' * 90))
        rows = self.store.chunks('atlas')
        source = self.store.get_document('atlas')['text']
        self.assertGreater(len(rows),1)
        for row in rows:
            self.assertEqual(row['text'],source[row['start']:row['end']])
            self.assertEqual(self.store.get_chunk(row['id'])['document_id'],'atlas')
        old_id = rows[0]['id']
        self.store.put_document(document('Omar owns Atlas.'),expected_revision=1)
        self.assertEqual(self.store.chunks('atlas')[0]['revision'],2)
        with self.assertRaises(Missing):self.store.get_chunk(old_id)
