import tempfile
import unittest
from pathlib import Path
from explorer.models import verify_model, generation_request, embedding_request
from explorer.domain import Invalid


class ModelContractTests(unittest.TestCase):
    def test_checksum_verification_rejects_missing_or_changed_files(self):
        import hashlib
        with tempfile.TemporaryDirectory() as root:
            path=Path(root);(path/'config.json').write_bytes(b'original')
            model={'files':[{'file':'config.json','sha256':hashlib.sha256(b'original').hexdigest()}]}
            verify_model(path,model)
            (path/'config.json').write_bytes(b'changed')
            with self.assertRaises(Invalid):verify_model(path,model)
            (path/'config.json').unlink()
            with self.assertRaises(Invalid):verify_model(path,model)

    def test_generation_is_bounded_and_cannot_enable_arbitrary_options(self):
        self.assertEqual(generation_request({'prompt':'Extract this','max_new_tokens':100}),('Extract this',100))
        for value in [{'prompt':''},{'prompt':'x','max_new_tokens':True},{'prompt':'x','max_new_tokens':300},{'prompt':'x','temperature':3}]:
            with self.assertRaises(Invalid):generation_request(value)

    def test_embedding_batches_and_text_are_bounded(self):
        self.assertEqual(embedding_request({'texts':['Atlas']}),['Atlas'])
        for texts in [[],['x']*33,['x'*16001],[3]]:
            with self.assertRaises(Invalid):embedding_request({'texts':texts})
