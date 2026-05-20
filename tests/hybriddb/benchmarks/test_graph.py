"""Graph benchmarks: node/edge CRUD, traversal, algorithms."""

import pytest

from .helpers import generate_graph_data

networkx = pytest.importorskip("networkx")


@pytest.fixture
def graph_db(db):
    db.create_table("nodes", {"type": "TEXT", "label": "TEXT"})
    db.create_table("edges", {"source_id": "TEXT", "target_id": "TEXT", "type": "TEXT", "weight": "REAL"})
    return db


def test_add_nodes_batch(benchmark, graph_db, scale):
    nodes, _ = generate_graph_data(scale.n_graph_nodes, 0)

    def _add():
        graph_db.insert_batch("nodes", nodes, sync=False)

    benchmark(_add)


def test_add_edges_batch(benchmark, graph_db, scale):
    nodes, edges = generate_graph_data(scale.n_graph_nodes, scale.n_graph_edges)
    graph_db.insert_batch("nodes", nodes, sync=False)

    def _add():
        graph_db.insert_batch("edges", edges)

    benchmark(_add)


def test_get_neighbors(benchmark, graph_db, scale):
    nodes, edges = generate_graph_data(scale.n_graph_nodes, scale.n_graph_edges)
    graph_db.insert_batch("nodes", nodes, sync=False)
    for e in edges:
        graph_db.register_entity_node("nodes", e["source_id"])
        graph_db.register_entity_node("nodes", e["target_id"])
        graph_db.add_edge(
            e["id"], e["source_id"], e["target_id"],
            edge_type=e["type"], weight=e["weight"],
        )

    target = nodes[len(nodes) // 2]["id"]

    def _neighbors():
        return graph_db.get_neighbors(target)

    benchmark(_neighbors)


def test_shortest_path(benchmark, graph_db, scale):
    nodes, edges = generate_graph_data(scale.n_graph_nodes, scale.n_graph_edges)
    graph_db.insert_batch("nodes", nodes, sync=False)
    for e in edges:
        graph_db.register_entity_node("nodes", e["source_id"])
        graph_db.register_entity_node("nodes", e["target_id"])
        graph_db.add_edge(
            e["id"], e["source_id"], e["target_id"],
            edge_type=e["type"], weight=e["weight"],
        )

    src = nodes[0]["id"]
    dst = nodes[-1]["id"]

    def _path():
        return graph_db.shortest_path(src, dst)

    benchmark(_path)


def test_pagerank(benchmark, graph_db, scale):
    nodes, edges = generate_graph_data(scale.n_graph_nodes, scale.n_graph_edges)
    graph_db.insert_batch("nodes", nodes, sync=False)
    for e in edges:
        graph_db.register_entity_node("nodes", e["source_id"])
        graph_db.register_entity_node("nodes", e["target_id"])
        graph_db.add_edge(
            e["id"], e["source_id"], e["target_id"],
            edge_type=e["type"], weight=e["weight"],
        )

    def _pr():
        return graph_db.pagerank()

    benchmark(_pr)


def test_decay_edges(benchmark, graph_db, scale):
    nodes, edges = generate_graph_data(100, 500)
    graph_db.insert_batch("nodes", nodes, sync=False)
    for e in edges:
        graph_db.register_entity_node("nodes", e["source_id"])
        graph_db.register_entity_node("nodes", e["target_id"])
        graph_db.add_edge(
            e["id"], e["source_id"], e["target_id"],
            edge_type=e["type"], weight=e["weight"],
        )

    def _decay():
        return graph_db.decay_edges()

    benchmark(_decay)
