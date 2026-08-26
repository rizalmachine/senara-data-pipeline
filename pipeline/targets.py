"""Central registry of export destinations -- one dict-of-dicts, imported everywhere
that needs to know where a brand's data goes. In the real pipeline this same shape
held 30+ real GSheet IDs across a 230-line file; here every value is a placeholder
or env-sourced default, never a real spreadsheet.
"""
import os

from pipeline import config


def get_export_targets():
    """Built fresh on each call (not a module-level constant) so tests can point
    config.EXPORTS_DIR at a tmp directory without needing a module reload."""
    return {
        brand: {
            "label": meta["label"],
            "gsheet_id": os.environ.get(f"{brand.upper()}_SHEET_ID", "<YOUR_SHEET_ID>"),
            "gsheet_tab": "Daily",
        }
        for brand, meta in config.BRANDS.items()
    }
