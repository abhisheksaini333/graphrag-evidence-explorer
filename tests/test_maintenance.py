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
