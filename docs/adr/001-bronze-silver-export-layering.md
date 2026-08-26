# ADR-001: Bronze / Silver / Export layering, no Postgres

## Context

The pipeline this project is modeled on ingests messy, semi-structured CRM export
files (WhatsApp conversation logs) on a daily cadence, and needs the output to be
safe to re-run: a failed or repeated run must never corrupt or duplicate downstream
data. It also needs a place to put raw data as-landed, separate from cleaned data,
so a transform bug can be fixed and replayed without re-fetching from source.

## Decision

Three DuckDB schemas, each with one job:

- `bronze` -- landed data, as close to the source shape as possible. Loaded by
  `pipeline/extract.py`. Staging tables are skip-if-exists-else-force (don't
  reprocess a large source every run); reference/lookup tables are always-replace
  (small, cheap, must stay current).
- `silver` -- cleaned, typed, deduplicated data. Built by `pipeline/transform.py`,
  one data_date at a time, via delete-insert (`load_to_silver`) so a re-run is a
  no-op rather than a duplicate.
- `audit` -- `pipeline_runs` (one row per step per run) and `export_history` (one
  row per successful export), so idempotency checks and failure diagnosis don't
  require re-deriving state from the data itself.

DuckDB instead of Postgres: this is a portfolio demo, not a production system with
concurrent writers -- an embedded, zero-server-setup database that still gives real
multi-schema SQL is the better fit. A Postgres backend is a plausible future
extension (swap the connection factory in `pipeline/db.py`), not something worth
building and leaving untested here.

## Consequences

Anyone cloning this repo gets a working pipeline with one `pip install` and no
external service dependencies. The tradeoff is that this demo doesn't exercise
concurrent-write behavior a real multi-writer Postgres deployment would need to
handle -- that's out of scope for what this project is trying to show.
