"""The two stores: the dedup cache, and human corrections. Uses a throwaway DB per test."""
import pytest

from api import store


@pytest.fixture
def conn(tmp_path):
    c = store.connect(tmp_path / "test.db")
    yield c
    c.close()


def test_dedup_roundtrip(conn):
    sha = store.file_hash(b"%PDF-1.4 hello")
    assert store.get_cached(conn, sha) is None
    store.put_cached(conn, sha, "a.pdf", {"pipeline": "v2", "value": "1.00"})
    assert store.get_cached(conn, sha)["value"] == "1.00"


def test_correction_records_box_and_updates_cache(conn):
    sha = store.file_hash(b"%PDF one")
    store.put_cached(conn, sha, "a.pdf", {"value": "WRONG", "status": "review"})
    store.record_correction(conn, sha, "amount_due", was="WRONG", now="1,290.00",
                            box=[0.82, 0.9, 0.95, 0.93])
    # the box is kept (it's the part worth learning from)
    assert store.correction_boxes(conn, "amount_due") == [[0.82, 0.9, 0.95, 0.93]]
    # and the cache now reflects the correction, so a re-upload never re-serves the mistake
    cached = store.get_cached(conn, sha)
    assert cached["value"] == "1,290.00" and cached["status"] == "ok"


def test_correction_without_a_box_is_kept_but_not_learnable(conn):
    sha = store.file_hash(b"%PDF two")
    store.put_cached(conn, sha, "b.pdf", {"value": "x"})
    store.record_correction(conn, sha, "amount_due", was="x", now="5.00", box=None)
    # value-only correction fixes the file but can't move the region
    assert store.correction_boxes(conn, "amount_due") == []


def test_clear_cache_keeps_corrections(conn):
    sha = store.file_hash(b"%PDF three")
    store.put_cached(conn, sha, "c.pdf", {"value": "9.99"})
    store.record_correction(conn, sha, "amount_due", was="9.99", now="10.00",
                            box=[0.8, 0.9, 0.9, 0.92])
    cleared = store.clear_cache(conn)
    assert cleared == 1
    assert store.get_cached(conn, sha) is None                 # cache gone
    assert len(store.correction_boxes(conn, "amount_due")) == 1  # learning kept
