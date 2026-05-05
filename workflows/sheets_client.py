"""
Google Sheets client — single source of truth for the LeetCode roadmap.
All reads and writes go through this module.
"""
import os
import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
COMPLETE_STATUSES = {"solved cold", "solved with hint", "studied solution"}


def _get_sheet():
    creds = Credentials.from_service_account_file(
        os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"],
        scopes=SCOPES,
    )
    gc = gspread.authorize(creds)
    return gc.open_by_key(os.environ["GOOGLE_SHEETS_ID"]).sheet1


def get_next_problem():
    """Return first blank-status row; if none, first REDO row; else None."""
    rows = _get_sheet().get_all_records()
    redo_row = None
    for row in rows:
        status = row.get("Status", "").strip().lower()
        if not status:
            return row
        if status == "redo" and redo_row is None:
            redo_row = row
    return redo_row


def get_roadmap_summary():
    """Return {complete: [...], pending: [...], redo: [...]}."""
    rows = _get_sheet().get_all_records()
    complete, pending, redo = [], [], []
    for row in rows:
        status = row.get("Status", "").strip().lower()
        if status in COMPLETE_STATUSES:
            complete.append(row)
        elif status == "redo":
            redo.append(row)
        else:
            pending.append(row)
    return {"complete": complete, "pending": pending, "redo": redo}


def mark_redo(url):
    """Set Status to 'REDO' for the row matching this URL. Returns True if found."""
    sheet = _get_sheet()
    rows = sheet.get_all_records()
    headers = sheet.row_values(1)
    status_col = headers.index("Status") + 1
    for i, row in enumerate(rows, start=2):  # row 1 is header
        if row.get("URL", "").strip() == url.strip():
            sheet.update_cell(i, status_col, "REDO")
            return True
    return False
