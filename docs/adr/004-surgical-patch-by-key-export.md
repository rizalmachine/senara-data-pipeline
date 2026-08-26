# ADR-004: Patch by key, not by row position

## Context

The real system's exports land in spreadsheets that humans and downstream formulas
also read from -- sometimes the same sheet a person has open, sometimes one with
formula columns computed from the raw columns the pipeline writes. Two exporters
existed for the same problem: one assumed row N in the source matched row N in the
destination (fragile -- any manual reorder or filter breaks it silently), and one
matched rows by phone number before touching anything (safe, but only applied to
one brand).

## Decision

`pipeline/export.py`'s `patch_by_key()` generalizes the safe version: match
`existing` and `incoming` rows by a business key, update only the requested
columns on matching rows, append rows whose key is new, and leave every other
column and the existing row order untouched. It's applied to `rpt_queue` (already
one row per customer per day) and deliberately *not* to `rpt_main`, which is a
message-level detail log with no natural unique key -- that one is a plain
overwrite instead of a forced fit.

One non-obvious failure mode surfaced while testing this: a pure-digit key like a
phone number round-trips through a CSV write/read as `int64`, while the freshly
computed incoming frame has it as a string -- silently breaking every key match and
duplicating rows on every re-run. `patch_by_key()` now coerces the key and patch
columns to `str` on both sides before comparing, and there's a regression test
(`tests/test_export.py`) that re-runs the same export three times and asserts the
row count never grows.

The optional Google Sheets path (`pipeline/sheets.py`, off by default) carries over
the other real showcase piece: `check_cell_capacity()` warns before a write gets
anywhere near Google's hard 10-million-cell-per-sheet limit, instead of finding out
via a failed write mid-run.

## Consequences

Export order in the destination file is stable across runs, which matters if a
human or a spreadsheet formula depends on it. The cost is one extra existing-file
read per patched export -- irrelevant at this data volume, and the same tradeoff
the real system made.
