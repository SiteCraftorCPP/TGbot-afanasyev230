import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN")
_raw_admin = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = {int(x.strip()) for x in _raw_admin.split(",") if x.strip()}
_raw_op = os.getenv("OPERATOR_IDS", "")
OPERATOR_IDS = {int(x.strip()) for x in _raw_op.split(",") if x.strip()} or ADMIN_IDS
# Общий чат для пользователей (кнопки «Вступить в чат» в меню, в формате, в расписании)
CHAT_LINK = os.getenv("CHAT_LINK", "https://t.me/+t67He7tKXcxiNWQy")

# Канал/чат куда приходят уведомления о заявках и вопросах менеджеру (НЕ общий чат)
OPERATOR_CHAT_ID = int(os.getenv("OPERATOR_CHAT_ID", "-1003650005079"))
DATABASE_PATH = BASE_DIR / "data" / "quest_bot.db"

# Google Sheets: ID таблицы (из URL) и путь к JSON ключу сервисного аккаунта
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
_raw_creds = os.getenv("GOOGLE_CREDENTIALS_PATH", "").strip()
GOOGLE_CREDENTIALS_PATH = Path(_raw_creds) if _raw_creds else None
if GOOGLE_CREDENTIALS_PATH and not GOOGLE_CREDENTIALS_PATH.is_absolute():
    GOOGLE_CREDENTIALS_PATH = BASE_DIR / GOOGLE_CREDENTIALS_PATH
