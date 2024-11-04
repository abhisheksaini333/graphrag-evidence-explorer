import tempfile,unittest
from pathlib import Path
from explorer.runtime_control import OperatorLease,recover_queries
from explorer.store import Store,Conflict
from explorer.query_runs import QueryRuns

class RuntimeControlTests(unittest.TestCase):
    def test_two_api_process_owners_cannot_recover_each_others_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'db'
            with OperatorLease(path):
                with self.assertRaises(Conflict):
                    with OperatorLease(path):pass
            with OperatorLease(path):pass
    def test_restart_retains_cost_and_marks_unfinished_queries_interrupted(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'db');runs=QueryRuns(store,owner='api')
            run=runs.start('local','Who owns Lumen?',0)
            runs.reserve(run['id'],'generate',100)
            self.assertEqual(recover_queries(store),1)
            recovered=runs.get(run['id'])
            self.assertEqual(recovered['status'],'failed');self.assertEqual(recovered['error'],'process_interrupted')
            self.assertEqual(len(recovered['calls']),1)

    def test_api_recovery_does_not_interrupt_independent_cli_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'db');runs=QueryRuns(store)
            run=runs.start('local','Who owns Lumen?',0)
            self.assertEqual(recover_queries(store),0)
            self.assertEqual(runs.get(run['id'])['status'],'running')
