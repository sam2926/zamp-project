"""Layout matching — and specifically the margin guard that stopped 19% of documents
from being matched to the wrong vendor's template."""
from api.fingerprint import LayoutIndex, is_static, jaccard, signature


def test_is_static_keeps_labels_drops_values():
    assert is_static("TOTAL")
    assert is_static("INVOICE")
    assert not is_static("$1,290.00")   # money
    assert not is_static("12/05/2020")  # date
    assert not is_static("729578")      # id / mostly digits
    assert not is_static("A")           # too short


def test_signature_uses_static_words_on_page_zero(words):
    sig = signature(words)
    texts = {t for (t, _c, _r) in sig}
    assert "TOTAL" in texts and "INVOICE" in texts
    assert "$1,290.00" not in texts     # a value, not part of the form


def test_jaccard_bounds():
    a = frozenset({("X", 0, 0), ("Y", 1, 1)})
    assert jaccard(a, a) == 1.0
    assert jaccard(a, frozenset({("Z", 2, 2)})) == 0.0


LAYOUT_A = frozenset({("ACME", 1, 1), ("INVOICE", 2, 0), ("TOTAL", 5, 9), ("DUE", 6, 9), ("BILLTO", 1, 2)})
LAYOUT_B = frozenset({("OTHER", 0, 0), ("VENDOR", 3, 3), ("PAYMENT", 4, 4)})


def test_clear_match_is_known():
    idx = LayoutIndex()
    idx.add("A", LAYOUT_A)
    idx.add("B", LAYOUT_B)
    m = idx.match(LAYOUT_A)          # identical to A, nothing like B
    assert m.known and m.layout_id == "A"


def test_ambiguous_match_is_rejected_by_the_margin():
    idx = LayoutIndex()
    idx.add("A", LAYOUT_A)
    idx.add("B", LAYOUT_B)
    # Shares roughly half with each — a plausible-looking but unsafe match.
    ambiguous = frozenset({("ACME", 1, 1), ("INVOICE", 2, 0), ("OTHER", 0, 0), ("VENDOR", 3, 3)})
    m = idx.match(ambiguous)
    assert not m.known              # the 2× margin refuses to guess
    assert m.runner_up > 0          # and it did have a runner-up, i.e. it was genuinely close


def test_unseen_layout_registers_as_new():
    idx = LayoutIndex()
    idx.add("A", LAYOUT_A)
    fresh = frozenset({("BRANDNEW", 7, 7), ("VENDORX", 8, 8)})
    m = idx.match_or_create(fresh, "NEW")
    assert not m.known and len(idx) == 2
