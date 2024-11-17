import importlib.util, unittest
from explorer.graph import build_graph, neighborhood


@unittest.skipUnless(
    importlib.util.find_spec("graphrag"), "Requires frozen GraphRAG runtime"
)
class GraphTests(unittest.TestCase):
    def test_framework_communities_keep_every_evidence_link(self):
        claims = [
            {
                "id": str(n),
                "subject": a,
                "object": b,
                "relation": "uses",
                "chunk_id": str(n),
                "support": a + " uses " + b + ".",
            }
            for n, (a, b) in enumerate(
                [
                    ("A", "B"),
                    ("B", "C"),
                    ("C", "A"),
                    ("C", "D"),
                    ("D", "E"),
                    ("E", "F"),
                    ("F", "D"),
                ]
            )
        ]
        graph = build_graph({"generation": 3, "claims": claims, "vectors": []})
        self.assertEqual(graph["framework"], "graphrag-0.1.1/leiden")
        self.assertEqual(len(graph["nodes"]), 6)
        self.assertEqual(len(graph["edges"]), 7)
        self.assertEqual(
            {n for c in graph["communities"] for n in c["nodes"]},
            {"a", "b", "c", "d", "e", "f"},
        )
        self.assertEqual(
            {x["id"] for x in neighborhood(graph, "a", 1)["nodes"]}, {"a", "b", "c"}
        )
        self.assertEqual(len(neighborhood(graph, "a", 2)["nodes"]), 4)

    def test_empty_and_self_relationships_do_not_crash_clustering(self):
        self.assertEqual(
            build_graph({"generation": 1, "claims": [], "vectors": []})["communities"],
            [],
        )
