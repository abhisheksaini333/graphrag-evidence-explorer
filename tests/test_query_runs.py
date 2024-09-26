import tempfile,unittest
from pathlib import Path
from explorer.store import Store,Conflict
from explorer.domain import DocumentInput
from explorer.query_runs import QueryRuns,QueryBudgetExceeded

class QueryRunTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'db');self.runs=QueryRuns(self.store)
    def tearDown(self):self.temp.cleanup()
    def test_reservations_are_durable_before_calls_and_bound_spend(self):
        run=self.runs.start('local','Who owns Lumen?',0,max_calls=1,max_tokens=300)
        call=self.runs.reserve(run['id'],'generate',200)
        with self.assertRaises(QueryBudgetExceeded):self.runs.reserve(run['id'],'generate',10)
        self.runs.complete_call(call,{'text':'Iris','input_tokens':20,'output_tokens':2})
        result=self.runs.finish(run['id'],{'answer':'Iris'})
        self.assertEqual(result['status'],'complete');self.assertEqual(result['calls'][0]['status'],'complete')
    def test_generation_change_discards_the_answer_and_prevents_future_calls(self):
        run=self.runs.start('vector','Who owns Lumen?',0)
        self.store.put_document(DocumentInput('lumen','Lumen','Iris owns Lumen.'))
        with self.assertRaises(Conflict):self.runs.reserve(run['id'],'generate',20)
        result=self.runs.finish(run['id'],{'answer':'old result'})
        self.assertEqual(result['status'],'stale');self.assertIsNone(result['result'])
    def test_live_read_hides_old_answers_after_source_changes(self):
        run=self.runs.start('global','Question?',0);self.runs.finish(run['id'],{'answer':'draft'})
        self.store.put_document(DocumentInput('lumen','Lumen','Iris owns Lumen.'))
        self.assertIsNone(self.runs.get(run['id'])['result'])
        self.assertEqual(self.runs.get(run['id'])['status'],'stale')
