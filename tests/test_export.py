import pandas as pd

from pipeline.export import export_csv, patch_by_key


def test_patch_by_key_updates_matching_and_appends_new():
    existing = pd.DataFrame({"customer_phone": ["628111111111", "628222222222"], "status": ["old", "old"]})
    incoming = pd.DataFrame({"customer_phone": ["628111111111", "628333333333"], "status": ["new", "new"]})

    out = patch_by_key(existing, incoming, key_col="customer_phone", patch_cols=["status"]).set_index("customer_phone")

    assert out.loc["628111111111", "status"] == "new"  # patched
    assert out.loc["628222222222", "status"] == "old"  # untouched, not in incoming
    assert out.loc["628333333333", "status"] == "new"  # appended, new key
    assert len(out) == 3


def test_patch_by_key_is_stable_across_a_csv_round_trip(tmp_path):
    """Regression: a pure-digit key column round-tripped through CSV without
    dtype=str comes back as int64, breaking key matching against the (string-typed)
    incoming frame and silently duplicating every row on each re-run."""
    path = tmp_path / "queue.csv"
    df = pd.DataFrame({
        "customer_phone": ["628111111111", "628222222222"],
        "contact_reason": ["complaint", "general"],
    })

    export_csv(path, df, key_col="customer_phone", patch_cols=["contact_reason"])
    export_csv(path, df, key_col="customer_phone", patch_cols=["contact_reason"])
    export_csv(path, df, key_col="customer_phone", patch_cols=["contact_reason"])

    result = pd.read_csv(path, dtype={"customer_phone": str})
    assert len(result) == 2
