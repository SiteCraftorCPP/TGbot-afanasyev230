"""
Интеграция с Google Sheets: подписки и заявки пишутся в таблицу.
Нужны GOOGLE_SHEET_ID и GOOGLE_CREDENTIALS_PATH в .env.
В таблице два листа: "Подписки", "Заявки".
"""
from datetime import datetime

from config import GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_PATH

_sheet = None


def _get_sheet():
    global _sheet
    if not GOOGLE_SHEET_ID or not GOOGLE_CREDENTIALS_PATH or not GOOGLE_CREDENTIALS_PATH.exists():
        return None
    if _sheet is None:
        try:
            import gspread
            gc = gspread.service_account(filename=str(GOOGLE_CREDENTIALS_PATH))
            _sheet = gc.open_by_key(GOOGLE_SHEET_ID)
        except Exception:
            _sheet = False
    return _sheet if _sheet else None


def _append(sheet_name: str, row: list, headers: list = None):
    sh = _get_sheet()
    if not sh:
        return
    try:
        wks = sh.worksheet(sheet_name)
        if headers and len(wks.get_all_values()) == 0:
            wks.append_row(headers, value_input_option="USER_ENTERED")
        wks.append_row(row, value_input_option="USER_ENTERED")
    except Exception:
        pass


def append_subscription(tg_id: int, username: str = None, first_name: str = None, last_name: str = None):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    _append("Подписки", [tg_id, username or "", first_name or "", last_name or "", now], headers=["tg_id", "username", "first_name", "last_name", "started_at"])


def append_lead(tg_id, username, name, phone, game_name, participants_count, comment, created_at=None):
    created_at = created_at or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    if hasattr(created_at, "strftime"):
        created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
    _append("Заявки", ["игра", tg_id, username or "", name or "", phone or "", game_name or "", participants_count or "", comment or "", created_at], headers=["type", "tg_id", "username", "name", "phone", "game_name", "participants_count", "comment", "created_at"])


def append_holiday_order(tg_id, username, name, phone, created_at=None):
    created_at = created_at or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    if hasattr(created_at, "strftime"):
        created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
    _append("Заявки", ["квест_праздник", tg_id, username or "", name or "", phone or "", "", "", "", created_at], headers=["type", "tg_id", "username", "name", "phone", "game_name", "participants_count", "comment", "created_at"])
