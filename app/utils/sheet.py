import os
import json
import gspread
from google.oauth2.service_account import Credentials
from typing import Optional
import logging

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

_gc = None
_sheet_cache = {}

def get_client():
    global _gc
    if _gc is None:
        creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            creds_dict = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        else:
            # Fallback: dùng file local khi dev
            creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
        _gc = gspread.authorize(creds)
    return _gc

def get_sheet_data(sheet_name: str, tab_name: str) -> list[dict]:
    """Lấy data từ Google Sheet, có cache đơn giản"""
    cache_key = f"{sheet_name}:{tab_name}"

    try:
        gc = get_client()
        spreadsheet = gc.open(sheet_name)
        worksheet = spreadsheet.worksheet(tab_name)
        records = worksheet.get_all_records()
        _sheet_cache[cache_key] = records
        logger.info(f"Loaded {len(records)} records from {tab_name}")
        return records
    except Exception as e:
        logger.error(f"Sheet error: {e}")
        # Trả cache cũ nếu có lỗi
        return _sheet_cache.get(cache_key, [])

def get_faq_data() -> list[dict]:
    sheet_name = os.getenv("SHEET_NAME", "vivu-danang-bot")
    return get_sheet_data(sheet_name, "faq")

def get_vehicles_data() -> list[dict]:
    sheet_name = os.getenv("SHEET_NAME", "vivu-danang-bot")
    return get_sheet_data(sheet_name, "vehicles")

def get_bookings_data() -> list[dict]:
    sheet_name = os.getenv("SHEET_NAME", "vivu-danang-bot")
    return get_sheet_data(sheet_name, "bookings")
