"""Optional Google Sheets export helpers -- ported from the real pipeline's strongest
module (gsheet_helpers.py) almost verbatim in logic. Off by default
(config.SHEETS_ENABLED); only imported when that path actually runs, so
google-api-python-client is never required for the default CSV-only demo path.
See docs/adr/004.
"""

GSHEET_CELL_LIMIT = 10_000_000


def get_sheets_service(credentials_file):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        credentials_file, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds)


def check_cell_capacity(service, spreadsheet_id, label="", warn_threshold=0.85):
    """Warn (don't block) before writing if a spreadsheet is nearing Google's hard
    10M-cell-per-sheet limit -- catches the problem before a write silently fails."""
    meta = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields="sheets.properties.gridProperties"
    ).execute()
    total = sum(
        sh["properties"]["gridProperties"].get("rowCount", 0)
        * sh["properties"]["gridProperties"].get("columnCount", 0)
        for sh in meta.get("sheets", [])
    )
    pct = total / GSHEET_CELL_LIMIT
    if pct >= warn_threshold:
        print(f"  [!!! WARNING] {label}: {total:,}/{GSHEET_CELL_LIMIT:,} cells "
              f"({pct * 100:.1f}%) -- nearing GSheet limit")
    return pct


def surgical_write(service, spreadsheet_id, sheet_name, df, mapping, label=""):
    """Clear + write only specific ranges/columns, instead of the whole sheet."""
    if df is None or df.empty:
        print(f"    [SKIP] {sheet_name}: empty DataFrame")
        return
    for m in mapping:
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!{m['clear_range']}", body={},
        ).execute()
        sub = df[m["cols"]].fillna("").astype(str)
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!{m['write_range']}",
            valueInputOption="USER_ENTERED", body={"values": sub.values.tolist()},
        ).execute()
        print(f"    [WRITE] ({label}) {sheet_name} ({m['clear_range']}) -> {len(sub)} rows")


def check_exported(con, data_date, spreadsheet_id, sheet_name):
    row = con.execute(
        "SELECT 1 FROM audit.export_history WHERE data_date=? AND sheet_id=? AND tab_name=?",
        [data_date, spreadsheet_id, sheet_name],
    ).fetchone()
    return row is not None


def log_exported(con, data_date, spreadsheet_id, sheet_name, label, rows_written):
    con.execute(
        """INSERT INTO audit.export_history (data_date, sheet_id, tab_name, sheet_label, rows_written)
           VALUES (?, ?, ?, ?, ?)""",
        [data_date, spreadsheet_id, sheet_name, label, rows_written],
    )


def idempotent_append(con, service, spreadsheet_id, sheet_name, df, data_date, label=""):
    """Append below existing data, skipping if this data_date was already logged as
    exported -- the audit log is the source of truth, not re-reading the sheet."""
    if df is None or df.empty:
        print(f"    [SKIP] {sheet_name}: empty DataFrame")
        return
    if check_exported(con, data_date, spreadsheet_id, sheet_name):
        print(f"    [SKIP] {label} {sheet_name} -> {data_date} already exported")
        return
    values = df.fillna("").astype(str).values.tolist()
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'",
        valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS", body={"values": values},
    ).execute()
    log_exported(con, data_date, spreadsheet_id, sheet_name, label, len(df))
    print(f"    [APPEND] {label} {sheet_name} -> +{len(df)} rows")
