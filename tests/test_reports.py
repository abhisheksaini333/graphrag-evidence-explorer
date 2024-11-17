import importlib.util, json, unittest
import test_evidence
from test_search import AnswerModel
from explorer.reports import Reports


class ReportModel(AnswerModel):
    def generate(self, prompt, max_new_tokens=192):
        return {
            "text": json.dumps(
                {
                    "title": "Atlas ownership",
                    "summary": "Mira owns Atlas.",
                    "findings": ["Mira owns Atlas."],
                    "rating": 1.0,
                    "rating_explanation": "One source assertion.",
                }
            ),
            "input_tokens": 50,
            "output_tokens": 40,
        }


@unittest.skipUnless(
    importlib.util.find_spec("graphrag"), "Requires frozen GraphRAG runtime"
)
class ReportTests(unittest.TestCase):
    setUp = test_evidence.EvidenceTests.setUp
    tearDown = test_evidence.EvidenceTests.tearDown
    publish = test_evidence.EvidenceTests.publish

    def test_actual_framework_report_retains_its_generation_and_claim_sources(self):
        self.publish()
        self.jobs.finish(self.job["id"], self.job["lease_token"], "complete")
        service = Reports(self.store, ReportModel(), profile="profile")
        community = service.graph()["communities"][0]
        result = service.generate(community["id"], self.store.generation())
        self.assertEqual(result["status"], "complete", result)
        self.assertEqual(result["result"]["report"]["title"], "Atlas ownership")
        self.assertEqual(len(result["result"]["claim_ids"]), 1)
        self.assertEqual(len(result["calls"]), 1)
