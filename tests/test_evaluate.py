import unittest
from explorer.evaluate import score_case
class EvaluationTests(unittest.TestCase):
    def test_failed_answer_gets_zero_coverage_even_if_retrieval_succeeded(self):
        case={'id':'q','kind':'direct','required_docs':['one'],'answer_terms':['Iris']}
        run={'id':'r','mode':'vector','status':'failed','calls':[],'result':{'answer':None,'passages':[{'document_id':'one'}]}}
        row=score_case(case,run)
        self.assertEqual(row['retrieval_document_recall'],1.)
        self.assertEqual(row['answer_term_coverage'],0.)
    def test_model_failure_does_not_count_as_correct_abstention(self):
        case={'id':'q','kind':'abstention','required_docs':[],'answer_terms':[]}
        run={'id':'r','mode':'local','status':'failed','calls':[],'result':None}
        self.assertFalse(score_case(case,run)['expected_abstention_observed'])
