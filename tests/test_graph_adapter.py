import importlib.util
import json
import unittest
from explorer.graph_adapter import extract_graph


@unittest.skipUnless(
    importlib.util.find_spec("graphrag"), "Requires frozen GraphRAG runtime"
)
class GraphAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_period_extractor_keeps_only_supported_model_triples(self):
        calls = []

        def model(prompt):
            calls.append(prompt)
            return {
                "text": json.dumps(
                    [
                        {"subject": "Mira", "relation": "owns", "object": "Atlas"},
                        {"subject": "Omar", "relation": "owns", "object": "Atlas"},
                    ]
                ),
                "input_tokens": 5,
                "output_tokens": 10,
            }

        result = await extract_graph("Mira owns Atlas.", model)
        self.assertEqual(len(calls), 1)
        self.assertIn("Mira owns Atlas.", calls[0])
        self.assertEqual(set(result["nodes"]), {"MIRA", "ATLAS"})
        self.assertEqual(len(result["edges"]), 1)
        self.assertEqual(len(result["accepted"]), 1)
        self.assertEqual(len(result["rejected"]), 1)

    async def test_invalid_model_output_is_not_silently_reported_as_a_built_graph(self):
        def model(prompt):
            return {"text": "this is not JSON"}

        with self.assertRaises(ValueError):
            await extract_graph("Mira owns Atlas.", model)
