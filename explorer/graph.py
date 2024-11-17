"""Evidence-preserving entity graph and deterministic period Leiden communities."""
import hashlib
from .domain import Invalid


def build_graph(snapshot):
    import networkx as nx
    from graphrag.index.verbs.graph.clustering.strategies.leiden import run

    graph = nx.Graph()
    edges = []
    for claim in snapshot["claims"]:
        source, target = claim["subject"].casefold(), claim["object"].casefold()
        graph.add_node(source, label=claim["subject"])
        graph.add_node(target, label=claim["object"])
        if source != target:
            if graph.has_edge(source, target):
                graph[source][target]["weight"] += 1
            else:
                graph.add_edge(source, target, weight=1.0)
        edges.append(
            {
                "source": source,
                "target": target,
                "relation": claim["relation"],
                "claim_id": claim["id"],
                "chunk_id": claim["chunk_id"],
                "support": claim["support"],
            }
        )
    memberships = []
    if graph.number_of_edges():
        clustered = run(graph, {"use_lcc": False, "seed": 17, "max_cluster_size": 8})
        memberships = list(clustered.get(0, {}).values())
    assigned = {node for nodes in memberships for node in nodes}
    memberships.extend([[node] for node in sorted(set(graph) - assigned)])
    communities = []
    for members in memberships:
        nodes = sorted(members)
        identity = hashlib.sha256("\0".join(nodes).encode()).hexdigest()[:16]
        evidence = [
            edge["claim_id"]
            for edge in edges
            if edge["source"] in nodes and edge["target"] in nodes
        ]
        communities.append({"id": identity, "nodes": nodes, "claim_ids": evidence})
    return {
        "generation": snapshot["generation"],
        "framework": "graphrag-0.1.1/leiden",
        "nodes": [
            {"id": key, **values} for key, values in sorted(graph.nodes(data=True))
        ],
        "edges": edges,
        "communities": sorted(communities, key=lambda c: c["id"]),
    }


def neighborhood(graph, entity, hops=1):
    if type(hops) is not int or not 1 <= hops <= 2:
        raise Invalid("Choose one or two graph hops")
    entity = entity.casefold()
    if entity not in {node["id"] for node in graph["nodes"]}:
        raise Invalid("Entity is unavailable")
    selected = {entity}
    for _ in range(hops):
        selected |= {
            endpoint
            for edge in graph["edges"]
            if edge["source"] in selected or edge["target"] in selected
            for endpoint in (edge["source"], edge["target"])
        }
    return {
        "generation": graph["generation"],
        "nodes": [node for node in graph["nodes"] if node["id"] in selected],
        "edges": [
            edge
            for edge in graph["edges"]
            if edge["source"] in selected and edge["target"] in selected
        ],
    }
