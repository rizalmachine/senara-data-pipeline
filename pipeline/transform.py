"""Silver layer. The six techniques worth reusing from the real pipeline, ported
and generalized (no hardcoded brand/phone lists -- everything comes from config):

1. normalize_phone           -- strip non-digits/prefixes, reject implausible numbers
2. add_direction_and_customer -- which side of a from/to pair is the brand vs the customer
3. compute_response_time     -- vectorized via .shift(), no row loops
4. flag_new_contacts         -- first-contact detection by diffing a historical snapshot
5. build_queue / build_queue_final -- two dedup strategies, kept side by side (see below)
6. load_to_silver            -- idempotent delete-insert per data_date

build_queue (recency-only) and build_queue_final (priority-rank with a deterministic
tie-break) are both kept, on purpose: in the real system, one legacy brand was never
migrated off the old recency-only dedup when the rest moved to priority-rank. Here,
brand "mira" plays that role -- see docs/adr/003.
"""
import re

import pandas as pd

from pipeline import config, db

PRIORITY_ORDER = {"complaint": 0, "new_lead": 1, "follow_up": 2, "general": 3}
LEGACY_RECENCY_BRANDS = {"mira"}


def normalize_phone(raw):
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    digits = re.sub(r"\D", "", str(raw))
    if not digits:
        return None
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("8"):
        digits = "62" + digits
    if not digits.startswith("62") or not (10 <= len(digits) <= 15):
        return None
    return digits


def add_direction_and_customer(df):
    from_is_brand = df["from_number"].isin(config.BRAND_NUMBERS)
    to_is_brand = df["to_number"].isin(config.BRAND_NUMBERS)
    df = df[from_is_brand ^ to_is_brand].copy()  # drop rows where neither/both sides are a known brand number

    from_is_brand = df["from_number"].isin(config.BRAND_NUMBERS)  # recompute, index now matches filtered df
    df["direction"] = "out"
    df.loc[~from_is_brand, "direction"] = "in"
    df["brand_number"] = df["from_number"].where(from_is_brand, df["to_number"])
    df["customer_phone"] = df["to_number"].where(from_is_brand, df["from_number"])
    df["brand"] = df["brand_number"].map(config.NUMBER_TO_BRAND)
    return df.drop(columns=["brand_number"])


def compute_response_time(df):
    df = df.sort_values(["customer_phone", "sent_at"]).reset_index(drop=True)
    grouped = df.groupby("customer_phone")
    df["next_sent_at"] = grouped["sent_at"].shift(-1)
    df["next_direction"] = grouped["direction"].shift(-1)
    is_pair = (df["direction"] == "in") & (df["next_direction"] == "out")
    df["response_time_minutes"] = pd.NA
    df.loc[is_pair, "response_time_minutes"] = (
        (df.loc[is_pair, "next_sent_at"] - df.loc[is_pair, "sent_at"]).dt.total_seconds() / 60
    )
    return df.drop(columns=["next_sent_at", "next_direction"])


def flag_new_contacts(df, prior_contacts):
    df = df.copy()
    first_seen = df.groupby("customer_phone")["sent_at"].transform("min")
    df["is_new_contact"] = (~df["customer_phone"].isin(prior_contacts)) & (df["sent_at"] == first_seen)
    return df


def build_queue(inbound_df):
    """Recency-only dedup: last inbound message per customer per day wins."""
    if inbound_df.empty:
        return inbound_df.assign(queue_method="recency")
    idx = inbound_df.groupby(["customer_phone", "data_date"])["sent_at"].idxmax()
    out = inbound_df.loc[idx].copy()
    out["queue_method"] = "recency"
    return out


def build_queue_final(inbound_df):
    """Priority-rank dedup: highest-priority contact_reason wins, tie-broken by recency."""
    if inbound_df.empty:
        return inbound_df.assign(queue_method="priority_rank")
    df = inbound_df.copy()
    df["_priority"] = df["contact_reason"].map(PRIORITY_ORDER).fillna(99)
    df = df.sort_values(
        ["customer_phone", "data_date", "_priority", "sent_at"],
        ascending=[True, True, True, False],
    )
    out = df.drop_duplicates(subset=["customer_phone", "data_date"], keep="first")
    out = out.drop(columns=["_priority"]).copy()
    out["queue_method"] = "priority_rank"
    return out


def build_silver_queue(inbound_df):
    cols = ["customer_phone", "brand", "data_date", "sent_at", "contact_reason", "queue_method"]
    if inbound_df.empty:
        return inbound_df.reindex(columns=cols)
    legacy_mask = inbound_df["brand"].isin(LEGACY_RECENCY_BRANDS)
    priority_part = build_queue_final(inbound_df[~legacy_mask])
    recency_part = build_queue(inbound_df[legacy_mask])
    return pd.concat([priority_part[cols], recency_part[cols]], ignore_index=True)


def load_to_silver(con, table, df, data_date):
    """Idempotent delete-insert: safe to re-run the same data_date any number of times."""
    con.register("_stage", df)
    try:
        exists = con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema='silver' AND table_name=?",
            [table],
        ).fetchone() is not None
        if not exists:
            con.execute(f"CREATE TABLE silver.{table} AS SELECT * FROM _stage WHERE 1=0")
        con.execute(f"DELETE FROM silver.{table} WHERE data_date = ?", [data_date])
        con.execute(f"INSERT INTO silver.{table} SELECT * FROM _stage")
    finally:
        con.unregister("_stage")


def run(con=None, data_date=None):
    own_con = con is None
    con = con or db.get_connection()
    try:
        raw = con.execute("SELECT * FROM bronze.raw_messages").fetchdf()
        prior_contacts = set(
            con.execute("SELECT customer_phone FROM bronze.ref_prior_contacts").fetchdf()["customer_phone"]
        )

        raw["from_number"] = raw["from_number"].apply(normalize_phone)
        raw["to_number"] = raw["to_number"].apply(normalize_phone)
        raw = raw.dropna(subset=["from_number", "to_number"])

        df = add_direction_and_customer(raw)
        df["data_date"] = pd.to_datetime(df["sent_at"]).dt.date.astype(str)
        df = compute_response_time(df)
        df = flag_new_contacts(df, prior_contacts)

        if data_date is None:
            # Skip straight to "max date with inbound activity" -- the tail end of a
            # generated window can have a trailing day of spillover outbound-only
            # follow-ups (see data_gen) with no inbound messages of its own.
            inbound_dates = df.loc[df["direction"] == "in", "data_date"]
            data_date = inbound_dates.max() if not inbound_dates.empty else df["data_date"].max()

        day_df = df[df["data_date"] == data_date].copy()

        rpt_main = day_df[[
            "message_id", "brand", "customer_phone", "direction", "sent_at",
            "agent_name", "response_time_minutes", "is_new_contact", "data_date",
        ]]
        load_to_silver(con, "rpt_main", rpt_main, data_date)

        inbound = day_df[day_df["direction"] == "in"]
        queue = build_silver_queue(inbound)
        load_to_silver(con, "rpt_queue", queue, data_date)

        return {"data_date": data_date, "rpt_main_rows": len(rpt_main), "rpt_queue_rows": len(queue)}
    finally:
        if own_con:
            con.close()
