"""Concurrent access benchmarks: read, write, mixed contention."""

import threading
import time

import pytest

from .helpers import generate_docs


def _reader_worker(db, stop, results):
    while not stop.is_set():
        try:
            db.search("bench_concurrent", "hello", search_type="keyword")
            results["reads"] += 1
        except Exception:
            pass


def _writer_worker(db, stop, results, doc_id_counter):
    while not stop.is_set():
        try:
            with doc_id_counter["lock"]:
                cid = doc_id_counter["val"]
                doc_id_counter["val"] += 1
            doc = {"id": str(cid), "content": f"concurrent test doc {cid}"}
            db.insert("bench_concurrent", doc)
            results["writes"] += 1
        except Exception:
            pass


@pytest.fixture
def concurrent_db(db, scale):
    db.create_table("bench_concurrent", {"content": "LONGTEXT"})
    docs = generate_docs(scale.n_docs, [{"name": "content", "type": "LONGTEXT"}])
    db.insert_batch("bench_concurrent", docs, sync=False)
    return db


def test_read_contention(benchmark, concurrent_db, scale):
    n_readers = 4

    def _run():
        stop = threading.Event()
        results = {"reads": 0}
        threads = [
            threading.Thread(target=_reader_worker, args=(concurrent_db, stop, results))
            for _ in range(n_readers)
        ]
        for t in threads:
            t.start()
        time.sleep(scale.concurrent_duration_s)
        stop.set()
        for t in threads:
            t.join()
        return results["reads"]

    result = benchmark(_run)
    assert result > 0


def test_write_contention(benchmark, concurrent_db, scale):
    n_writers = 2
    doc_id_counter = {"val": scale.n_docs + 1, "lock": threading.Lock()}

    def _run():
        stop = threading.Event()
        results = {"writes": 0}
        threads = [
            threading.Thread(
                target=_writer_worker,
                args=(concurrent_db, stop, results, doc_id_counter),
            )
            for _ in range(n_writers)
        ]
        for t in threads:
            t.start()
        time.sleep(scale.concurrent_duration_s)
        stop.set()
        for t in threads:
            t.join()
        return results["writes"]

    result = benchmark(_run)
    assert result > 0


def test_read_write_mixed(benchmark, concurrent_db, scale):
    doc_id_counter = {"val": scale.n_docs + 1, "lock": threading.Lock()}

    def _run():
        stop = threading.Event()
        results = {"reads": 0, "writes": 0}
        readers = [
            threading.Thread(target=_reader_worker, args=(concurrent_db, stop, results))
            for _ in range(4)
        ]
        writers = [
            threading.Thread(
                target=_writer_worker,
                args=(concurrent_db, stop, results, doc_id_counter),
            )
            for _ in range(1)
        ]
        for t in readers + writers:
            t.start()
        time.sleep(scale.concurrent_duration_s)
        stop.set()
        for t in readers + writers:
            t.join()
        return results

    result = benchmark(_run)
    assert result["reads"] > 0 or result["writes"] > 0
