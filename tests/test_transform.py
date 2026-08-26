from datetime import datetime

import pandas as pd

from pipeline import config, transform


def test_normalize_phone():
    assert transform.normalize_phone("0812-3456-7890") == "6281234567890"
    assert transform.normalize_phone("+62 812 3456 7890") == "6281234567890"
    assert transform.normalize_phone("8123456789") == "628123456789"
    assert transform.normalize_phone(None) is None
    assert transform.normalize_phone("abc") is None
    assert transform.normalize_phone("123") is None  # too short to be plausible


def test_add_direction_and_customer():
    brand_number = next(iter(config.BRAND_NUMBERS))
    df = pd.DataFrame([
        {"from_number": "628111111111", "to_number": brand_number},  # inbound
        {"from_number": brand_number, "to_number": "628111111111"},  # outbound
        {"from_number": "628222222222", "to_number": "628333333333"},  # neither side is a brand -> dropped
    ])
    out = transform.add_direction_and_customer(df)
    assert len(out) == 2
    assert set(out["direction"]) == {"in", "out"}
    assert (out["customer_phone"] == "628111111111").all()


def test_compute_response_time_only_pairs_in_then_out():
    df = pd.DataFrame([
        {"customer_phone": "628111111111", "direction": "in", "sent_at": datetime(2026, 1, 1, 10, 0)},
        {"customer_phone": "628111111111", "direction": "out", "sent_at": datetime(2026, 1, 1, 10, 5)},
        {"customer_phone": "628222222222", "direction": "out", "sent_at": datetime(2026, 1, 1, 11, 0)},
    ])
    out = transform.compute_response_time(df)
    row = out[(out["customer_phone"] == "628111111111") & (out["direction"] == "in")].iloc[0]
    assert row["response_time_minutes"] == 5
    row2 = out[out["customer_phone"] == "628222222222"].iloc[0]
    assert pd.isna(row2["response_time_minutes"])


def test_flag_new_contacts_only_flags_first_message():
    df = pd.DataFrame([
        {"customer_phone": "628111111111", "sent_at": datetime(2026, 1, 1, 9, 0)},
        {"customer_phone": "628111111111", "sent_at": datetime(2026, 1, 1, 10, 0)},
        {"customer_phone": "628999999999", "sent_at": datetime(2026, 1, 1, 9, 0)},
    ])
    out = transform.flag_new_contacts(df, prior_contacts={"628999999999"})
    new_flags = out.set_index(["customer_phone", "sent_at"])["is_new_contact"]
    assert new_flags[("628111111111", datetime(2026, 1, 1, 9, 0))] == True
    assert new_flags[("628111111111", datetime(2026, 1, 1, 10, 0))] == False
    assert new_flags[("628999999999", datetime(2026, 1, 1, 9, 0))] == False  # in prior_contacts


def _inbound_frame():
    return pd.DataFrame([
        # senara customer: complaint arrives FIRST, general arrives LATER -- priority-rank
        # must still pick the (earlier) complaint, proving it overrides plain recency.
        {"customer_phone": "628111111111", "brand": "senara", "data_date": "2026-01-01",
         "sent_at": datetime(2026, 1, 1, 9, 0), "contact_reason": "complaint"},
        {"customer_phone": "628111111111", "brand": "senara", "data_date": "2026-01-01",
         "sent_at": datetime(2026, 1, 1, 14, 0), "contact_reason": "general"},
        {"customer_phone": "628222222222", "brand": "mira", "data_date": "2026-01-01",
         "sent_at": datetime(2026, 1, 1, 9, 0), "contact_reason": "complaint"},
        {"customer_phone": "628222222222", "brand": "mira", "data_date": "2026-01-01",
         "sent_at": datetime(2026, 1, 1, 14, 0), "contact_reason": "general"},
    ])


def test_build_queue_final_priority_rank_beats_recency():
    out = transform.build_queue_final(_inbound_frame())
    row = out[out["customer_phone"] == "628111111111"].iloc[0]
    assert row["contact_reason"] == "complaint"  # higher priority wins despite being the earlier message


def test_build_queue_is_recency_only():
    out = transform.build_queue(_inbound_frame())
    row = out[out["customer_phone"] == "628222222222"].iloc[0]
    assert row["sent_at"] == datetime(2026, 1, 1, 14, 0)  # last message wins regardless of reason


def test_build_silver_queue_routes_legacy_brand_to_recency():
    out = transform.build_silver_queue(_inbound_frame())
    methods = out.set_index("brand")["queue_method"]
    assert methods["senara"] == "priority_rank"
    assert methods["mira"] == "recency"
