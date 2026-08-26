import pytest

from pipeline import config


@pytest.fixture
def isolated_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "demo.duckdb")
    monkeypatch.setattr(config, "INCOMING_DIR", tmp_path / "incoming")
    monkeypatch.setattr(config, "EXPORTS_DIR", tmp_path / "exports")


def test_pipeline_runs_end_to_end_and_is_idempotent(isolated_paths):
    from data_gen import bootstrap
    from pipeline import pipeline as pipeline_module, db

    bootstrap.bootstrap(customers=30, days=5, seed=1)

    assert pipeline_module.run() is True

    con = db.get_connection()
    try:
        first_count = con.execute("SELECT COUNT(*) FROM silver.rpt_main").fetchone()[0]
        assert first_count > 0
    finally:
        con.close()

    # Re-run without --force: same date resolves again, delete-insert keeps row count stable.
    assert pipeline_module.run() is True

    con = db.get_connection()
    try:
        second_count = con.execute("SELECT COUNT(*) FROM silver.rpt_main").fetchone()[0]
    finally:
        con.close()

    assert second_count == first_count


def test_dry_run_makes_no_changes(isolated_paths):
    from data_gen import bootstrap
    from pipeline import pipeline as pipeline_module

    bootstrap.bootstrap(customers=10, days=3, seed=2)
    assert pipeline_module.run(dry_run=True) is True

    from pipeline import db
    con = db.get_connection()
    try:
        exists = con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema='silver' AND table_name='rpt_main'"
        ).fetchone()
        assert exists is None
    finally:
        con.close()
