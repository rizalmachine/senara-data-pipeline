# ADR-002: One config module, not per-file constants

## Context

The pipeline this project is modeled on grew organically: DB-credential-loading
logic ended up copy-pasted verbatim into three different files, and each brand's
phone numbers were hardcoded independently in four places. None of the copies ever
drifted apart by accident, but nothing prevented it either, and adding a fifth
brand meant touching five files instead of one.

## Decision

`pipeline/config.py` is the single place that knows: the brand registry (label +
number, keyed by a short brand id), file paths (`DB_PATH`, `INCOMING_DIR`,
`EXPORTS_DIR`), generation parameters, and the two optional-feature flags
(`SHEETS_ENABLED`, plus the alert email settings). Every other module imports from
here; nothing re-derives or re-hardcodes any of it.

`pipeline/targets.py` builds its per-brand export-target dict from
`config.BRANDS` and environment variables, so adding a brand is a one-line change
in one file, not a find-and-replace across five.

## Consequences

Config values are read from `os.environ` at call time (via `get_export_targets()`,
not a module-level constant), which is slightly more verbose than a plain dict but
means tests can override `config.DB_PATH`/`config.EXPORTS_DIR` per-test without
needing a module reload.
