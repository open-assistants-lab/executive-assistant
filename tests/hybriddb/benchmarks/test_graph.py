"""Graph benchmarks: node/edge CRUD, traversal, algorithms."""

import pytest

from .helpers import generate_graph_data

networkx = pytest.importorskip("networkx")


def test_add_nodes_batch(benchmark, db, scale):
    nodes, _ = generate_graph_data(scale.n_graph_nodes, 0)

    def _add():
        db.add_nodes(nodes)

    benchmark(_add)


def test_add_edges_batch(benchmark, db, scale):
    nodes, edges = generate_graph_data(scale.n_graph_nodes, scale.n_graph_edges)
    db.add_nodes(nodes)

    def _add():
        for e in edges:
            db.add_edge(
                e["id"], e["source_id"], e["target_id"],
                type=e["type"], weight=e["weight"],
            )

    benchmark(_add)


def test_get_neighbors(benchmark, db, scale):
    nodes, edges = generate_graph_data(scale.n_graph_nodes, scale.n_graph_edges)
    db.add_nodes(nodes)
    for e in edges:
        db.add_edge(
            e["id"], e["source_id"], e["target_id"],
            type=e["type"], weight=e["weight"],
        )

    target = nodes[len(nodes) // 2]["id"]

    def _neighbors():
        return db.neighbors(target)

    benchmark(_neighbors)


def test_shortest_path(benchmark, db, scale):
    nodes, edges = generate_graph_data(scale.n_graph_nodes, scale.n_graph_edges)
    db.add_nodes(nodes)
    for e in edges:
        db.add_edge(
            e["id"], e["source_id"], e["target_id"],
            type=e["type"], weight=e["weight"],
        )

    src = nodes[0]["id"]
    dst = nodes[-1]["id"]

    def _path():
        return db.shortest_path(src, dst)

    benchmark(_path)


def test_pagerank(benchmark, db, scale):
    nodes, edges = generate_graph_data(scale.n_graph_nodes, scale.n_graph_edges)
    db.add_nodes(nodes)
    for e in edges:
        db.add_edge(
            e["id"], e["source_id"], e["target_id"],
            type=e["type"], weight=e["weight"],
        )

    def _pr():
        return db.pagerank()

    benchmark(_pr)


def test_decay_edges(benchmark, db, scale):
    nodes, edges = generate_graph_data(100, 500)
    db.add_nodes(nodes)
    for e in edges:
        db.add_edge(
            e["id"], e["source_id"], e["target_id"],
            type=e["type"], weight=e["weight"],
        )

    def _decay():
        return db.decay_edges()

    benchmark(_decay)
