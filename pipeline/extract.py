"""Bronze layer: loads landed CSVs from data/incoming/ into DuckDB.

Mirrors the real ingestion step's two load patterns: staging sources are
skip-if-exists-else-force (don't reload a big append-style source every run),
reference/lookup sources are always-replace (small, cheap, must stay current).
"""
import pandas as pd

from pipeline import config, db


def _table_exists(con, schema, table):
    return con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema=? AND table_name=?",
        [schema, table],
    ).fetchone() is not None


def _load_staging(con, table, csv_path, force=False):
    if _table_exists(con, "bronze", table) and not force:
        print(f"    [SKIP] bronze.{table} already loaded (use --force to reload)")
        return
    df = pd.read_csv(csv_path, parse_dates=["sent_at"])
    con.register("_stage", df)
    con.execute(f"CREATE OR REPLACE TABLE bronze.{table} AS SELECT * FROM _stage")
    con.unregister("_stage")
    print(f"    [LOAD] bronze.{table} <- {csv_path.name} ({len(df)} rows)")


def _load_reference(con, table, csv_path):
    df = pd.read_csv(csv_path)
    con.register("_stage", df)
    con.execute(f"CREATE OR REPLACE TABLE bronze.{table} AS SELECT * FROM _stage")
    con.unregister("_stage")
    print(f"    [LOAD] bronze.{table} <- {csv_path.name} ({len(df)} rows, always-replace)")


def run(con=None, force=False):
    own_con = con is None
    con = con or db.get_connection()
    try:
        for path in (config.INCOMING_DIR / "conversations.csv",
                     config.INCOMING_DIR / "ref_agents.csv",
                     config.INCOMING_DIR / "ref_prior_contacts.csv"):
            if not path.exists():
                raise FileNotFoundError(
                    f"{path} not found -- run `python -m data_gen.bootstrap` first")

        _load_staging(con, "raw_messages", config.INCOMING_DIR / "conversations.csv", force=force)
        _load_reference(con, "ref_agents", config.INCOMING_DIR / "ref_agents.csv")
        _load_reference(con, "ref_prior_contacts", config.INCOMING_DIR / "ref_prior_contacts.csv")
    finally:
        if own_con:
            con.close()
