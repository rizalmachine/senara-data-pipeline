import pandas as pd

from pipeline import tagging


def test_known_typos_map_to_canonical_tag():
    assert tagging.canonicalize_tag("Intersted") == "interested"
    assert tagging.canonicalize_tag("folowup") == "follow_up"
    assert tagging.canonicalize_tag("Follow-Up") == "follow_up"
    assert tagging.canonicalize_tag("komplain") == "complaint"
    assert tagging.canonicalize_tag("ga jadi") == "not_interested"


def test_unknown_tag_falls_back_to_normalized_form():
    assert tagging.canonicalize_tag("Some New Tag") == "some_new_tag"


def test_empty_or_missing_tag_is_unknown():
    assert tagging.canonicalize_tag("") == "unknown"
    assert tagging.canonicalize_tag(None) == "unknown"


def test_canonicalize_series():
    out = tagging.canonicalize_series(pd.Series(["komplain", None, "folowup"]))
    assert list(out) == ["complaint", "unknown", "follow_up"]
