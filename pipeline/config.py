"""Single source of configuration for the whole pipeline.

The real-world version of this project had DB-credential-loading logic copy-pasted
verbatim across three files, and brand phone numbers hardcoded independently in four
places. Consolidating everything here is the fix.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Fictional multi-brand registry -- one pipeline, several brand instances sharing it.
BRANDS = {
    "senara": {"label": "Senara", "number": "628000000001"},
    "kalvia": {"label": "Kalvia", "number": "628000000002"},
    "alvora": {"label": "Alvora", "number": "628000000003"},
    "mira": {"label": "Mira", "number": "628000000004"},
}
BRAND_NUMBERS = {b["number"] for b in BRANDS.values()}
NUMBER_TO_BRAND = {b["number"]: key for key, b in BRANDS.items()}

DB_PATH = BASE_DIR / os.environ.get("PIPELINE_DB_PATH", "data/demo.duckdb")
INCOMING_DIR = BASE_DIR / "data" / "incoming"
EXPORTS_DIR = BASE_DIR / "data" / "exports"

SEED = int(os.environ.get("PIPELINE_SEED", "42"))
CUSTOMERS = int(os.environ.get("PIPELINE_CUSTOMERS", "400"))
DAYS = int(os.environ.get("PIPELINE_DAYS", "14"))

OFFICE_HOURS_START = 8
OFFICE_HOURS_END = 23

SHEETS_ENABLED = os.environ.get("PIPELINE_SHEETS_ENABLED", "0") == "1"
SHEETS_CREDENTIALS_FILE = os.environ.get("PIPELINE_SHEETS_CREDENTIALS_FILE", "credentials.json")

ALERT_EMAIL = os.environ.get("PIPELINE_ALERT_EMAIL", "")
ALERT_APP_PASSWORD = os.environ.get("PIPELINE_ALERT_APP_PASSWORD", "")
