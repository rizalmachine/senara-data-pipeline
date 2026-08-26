"""Export layer. patch_by_key is the one technique generalized from the real
per-brand exporters: match rows by a business key before patching columns, instead
of assuming row order -- safe to run against a file a human might also be editing.
Only applied to rpt_queue (already one row per customer per day); rpt_main is a
message-level detail log with no natural unique key, so it's a plain overwrite.
CSV export always runs (the default, offline path); GSheet export is optional,
gated by config.SHEETS_ENABLED. See docs/adr/004.
"""
import pandas as pd

from pipeline import config, targets


def patch_by_key(existing: pd.DataFrame, incoming: pd.DataFrame, key_col: str, patch_cols: list) -> pd.DataFrame:
    """Update patch_cols on matching key_col rows in `existing` from `incoming`;
    append any incoming rows whose key isn't present yet. Row order and any other
    columns already in `existing` are left untouched.

    key_col and patch_cols are coerced to str on both sides before comparing --
    `existing` typically came back from a CSV round-trip (everything is text there),
    while `incoming` is freshly computed (a pure-digit key can be int64, a date can
    be a real Timestamp). Without this, key matching silently breaks and every row
    looks "new" on every run.
    """
    if existing is None or existing.empty:
        return incoming.copy()

    existing = existing.astype({c: str for c in [key_col, *patch_cols] if c in existing.columns})
    incoming = incoming.astype({c: str for c in [key_col, *patch_cols] if c in incoming.columns})

    merged = existing.set_index(key_col)
    updates = incoming.set_index(key_col)

    common = updates.index.intersection(merged.index)
    for col in patch_cols:
        if col in updates.columns:
            merged.loc[common, col] = updates.loc[common, col]

    new_keys = updates.index.difference(merged.index)
    if len(new_keys):
        merged = pd.concat([merged, updates.loc[new_keys]])

    return merged.reset_index()


def export_csv(csv_path, df, key_col=None, patch_cols=None):
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    if key_col and patch_cols and csv_path.exists():
        existing = pd.read_csv(csv_path)
        df = patch_by_key(existing, df, key_col=key_col, patch_cols=patch_cols)

    df.to_csv(csv_path, index=False)
    print(f"    [EXPORT] -> {csv_path} ({len(df)} rows)")
    return csv_path


def export_gsheet(brand, df, con, data_date):
    if not config.SHEETS_ENABLED:
        print(f"    [SKIP] GSheet export disabled (PIPELINE_SHEETS_ENABLED=0) for {brand}")
        return

    from pipeline import sheets  # lazy: google-api deps only needed if this path runs

    target = targets.get_export_targets()[brand]
    service = sheets.get_sheets_service(config.SHEETS_CREDENTIALS_FILE)
    sheets.check_cell_capacity(service, target["gsheet_id"], label=brand)
    sheets.idempotent_append(con, service, target["gsheet_id"], target["gsheet_tab"], df, data_date, label=brand)


def run(con=None, data_date=None):
    from pipeline import db as db_module

    own_con = con is None
    con = con or db_module.get_connection()
    try:
        rows_exported = 0
        for brand in config.BRANDS:
            main_df = con.execute(
                "SELECT * FROM silver.rpt_main WHERE brand = ? AND data_date = ?", [brand, data_date],
            ).fetchdf()
            queue_df = con.execute(
                "SELECT * FROM silver.rpt_queue WHERE brand = ? AND data_date = ?", [brand, data_date],
            ).fetchdf()
            if main_df.empty and queue_df.empty:
                continue

            if not main_df.empty:
                export_csv(config.EXPORTS_DIR / f"{brand}_main.csv", main_df)
            if not queue_df.empty:
                export_csv(
                    config.EXPORTS_DIR / f"{brand}_queue.csv", queue_df,
                    key_col="customer_phone", patch_cols=["contact_reason", "sent_at", "queue_method"],
                )
            export_gsheet(brand, main_df, con, data_date)
            rows_exported += len(main_df) + len(queue_df)
        return {"data_date": data_date, "rows_exported": rows_exported}
    finally:
        if own_con:
            con.close()
