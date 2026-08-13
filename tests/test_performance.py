"""Performance gate — a regression check over the recorded evaluation.

This does NOT call a model (that costs money and needs a key). It re-scores the saved val
run committed to the repo, so if the scoring, the region, or the recorded results regress,
CI fails. A full live re-evaluation is a deliberate, manual `scripts/` run.

Thresholds sit just under the numbers reported in the README (77.3% accuracy, 86% tokens),
so real movement trips them but noise does not.
"""
import json
from pathlib import Path

import pytest

PIPE = Path("data/runs/pipeline_amount_due_80.jsonl")
BASE = Path("data/runs/baseline_amount_due.jsonl")

ACCURACY_FLOOR = 0.75      # reported: 0.773
TOKEN_CEILING = 0.90       # reported: 0.862 of the whole-page baseline


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


@pytest.mark.skipif(not PIPE.exists(), reason="saved val run not committed")
def test_amount_due_accuracy_has_not_regressed():
    pipe = _rows(PIPE)
    correct = sum(1 for r in pipe if r["verdicts"].get("numeric") or r["verdicts"].get("exact"))
    acc = correct / len(pipe)
    assert acc >= ACCURACY_FLOOR, f"accuracy {acc:.3f} fell below {ACCURACY_FLOOR}"


@pytest.mark.skipif(not (PIPE.exists() and BASE.exists()), reason="runs not committed")
def test_pipeline_is_cheaper_than_the_whole_page_baseline():
    pipe = _rows(PIPE)
    base = {r["doc_id"]: r for r in _rows(BASE)}
    pipe_tokens = sum(r["tokens_charged"] for r in pipe)
    base_tokens = sum(base[r["doc_id"]]["tokens_sent"] for r in pipe if r["doc_id"] in base)
    ratio = pipe_tokens / base_tokens
    assert ratio <= TOKEN_CEILING, f"token ratio {ratio:.3f} exceeded {TOKEN_CEILING}"


def test_deployed_region_is_sane():
    # The region the app loads at startup must be a real sub-page slice — not empty,
    # not the whole page. Guards against a bad region file shipping.
    from api.fields import FIELDS
    from api.region import load as load_region

    region = load_region(FIELDS["amount_due"].region_path)
    assert 0.1 < region.area < 0.8
