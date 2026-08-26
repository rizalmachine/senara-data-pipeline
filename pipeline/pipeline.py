"""CLI orchestrator.

    python -m pipeline.pipeline [DATE] [--force] [--skip-extract] [--only-export] [--step STEP] [--dry-run]

Same shape as the real run_pipeline.py: a steps list, critical-step-abort (if
extract fails, nothing downstream runs), an audit log row per step, and an email
alert on failure.
"""
import argparse
import sys
import traceback
import uuid
from datetime import datetime

from pipeline import config, db, extract, transform, export as export_module, notify

STEPS = ["extract", "transform", "export"]
CRITICAL_STEPS = {"extract"}


def _log_run(con, run_id, data_date, step, status, start, error_message=None):
    con.execute(
        """INSERT INTO audit.pipeline_runs (run_id, data_date, step, start_time, end_time, status, error_message)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [run_id, data_date or "pending", step, start, datetime.now(), status, error_message],
    )


def determine_steps(skip_extract=False, only_export=False, only_step=None):
    if only_step:
        return [only_step]
    if only_export:
        return ["export"]
    steps = list(STEPS)
    if skip_extract:
        steps.remove("extract")
    return steps


def run(date=None, force=False, skip_extract=False, only_export=False, only_step=None, dry_run=False):
    run_id = str(uuid.uuid4())
    steps = determine_steps(skip_extract, only_export, only_step)
    data_date = date
    con = db.get_connection()
    failed = False

    print(f"=== PIPELINE RUN {run_id} | steps={steps} | date={data_date or '(latest)'} ===")
    try:
        for step in steps:
            start = datetime.now()
            print(f"\n--- STEP: {step} ---")
            if dry_run:
                print(f"    [DRY-RUN] would run {step}")
                _log_run(con, run_id, data_date, step, "DRY_RUN", start)
                continue
            try:
                if step == "extract":
                    extract.run(con=con, force=force)
                elif step == "transform":
                    result = transform.run(con=con, data_date=data_date)
                    data_date = result["data_date"]
                elif step == "export":
                    export_module.run(con=con, data_date=data_date)
                _log_run(con, run_id, data_date, step, "SUCCESS", start)
            except Exception as e:
                traceback.print_exc()
                _log_run(con, run_id, data_date, step, "FAILED", start, error_message=str(e))
                failed = True
                if step in CRITICAL_STEPS:
                    print(f"[ABORT] {step} failed and is critical -- stopping")
                    break
    finally:
        con.close()

    if failed:
        notify.send_alert(f"Pipeline FAILED ({run_id})", f"Steps: {steps}\nDate: {data_date}")
    else:
        print(f"\n=== DONE ({run_id}) ===")
    return not failed


def main():
    parser = argparse.ArgumentParser(description="Run the demo pipeline")
    parser.add_argument("date", nargs="?", default=None, help="YYYY-MM-DD, defaults to the latest date in bronze")
    parser.add_argument("--force", action="store_true", help="reload bronze even if already loaded")
    parser.add_argument("--skip-extract", action="store_true")
    parser.add_argument("--only-export", action="store_true")
    parser.add_argument("--step", choices=STEPS, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ok = run(
        date=args.date, force=args.force, skip_extract=args.skip_extract,
        only_export=args.only_export, only_step=args.step, dry_run=args.dry_run,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
