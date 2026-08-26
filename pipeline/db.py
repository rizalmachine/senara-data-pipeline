"""DuckDB connection factory.

No Postgres path in this demo -- see docs/adr/001 for why. DuckDB's native
multi-schema support maps directly onto the pipeline's bronze/silver/audit layering.
"""
import duckdb

from pipeline import config

SCHEMAS = ("bronze", "silver", "audit")

_AUDIT_TABLES = {
    "pipeline_runs": """
        CREATE TABLE IF NOT EXISTS audit.pipeline_runs (
            run_id VARCHAR, data_date VARCHAR, step VARCHAR,
            start_time TIMESTAMP, end_time TIMESTAMP,
            status VARCHAR, error_message VARCHAR
        )
    """,
    "export_history": """
        CREATE TABLE IF NOT EXISTS audit.export_history (
            data_date VARCHAR, sheet_id VARCHAR, tab_name VARCHAR,
            sheet_label VARCHAR, rows_written INTEGER,
            exported_at TIMESTAMP DEFAULT current_timestamp
        )
    """,
}


def get_connection():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(config.DB_PATH))
    for schema in SCHEMAS:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    for ddl in _AUDIT_TABLES.values():
        con.execute(ddl)
    return con
