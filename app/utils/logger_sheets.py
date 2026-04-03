import os
import json
import threading
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Cache sheet client để tránh auth lại mỗi lần
_sheet_client = None
_sheet_lock = threading.Lock()

def _get_log_sheet():
    global _sheet_client
    with _sheet_lock:
        if _sheet_client is None:
            creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
            if creds_json:
                creds_dict = json.loads(creds_json)
                creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            else:
                creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
            _sheet_client = gspread.authorize(creds)

    sheet_name = os.getenv("SHEET_NAME", "vivu-danang-bot")
    spreadsheet = _sheet_client.open(sheet_name)
    try:
        return spreadsheet.worksheet("logs")
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="logs", rows=2000, cols=8)
        ws.append_row([
            "timestamp", "user_id", "user_name",
            "user_message", "bot_response",
            "intent", "score", "fallback"
        ])
        return ws

def _write_log(user_id, user_name, user_message, bot_response, intent, score, fallback):
    """Chạy trong background thread — không block response"""
    try:
        ws = _get_log_sheet()
        ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_id,
            user_name,
            user_message,
            bot_response[:300],
            intent,
            round(score, 1),
            "YES" if fallback else "NO"
        ])
    except Exception as e:
        logger.error(f"[Logger] Failed: {e}")

def log_interaction(
    user_id: str,
    user_message: str,
    bot_response: str,
    intent: str,
    score: float,
    fallback: bool,
    user_name: str = ""
):
    """
    Fire-and-forget: ghi log vào Google Sheet trong background thread.
    Không ảnh hưởng tốc độ response về ManyChat.
    """
    t = threading.Thread(
        target=_write_log,
        args=(user_id, user_name, user_message, bot_response, intent, score, fallback),
        daemon=True
    )
    t.start()
