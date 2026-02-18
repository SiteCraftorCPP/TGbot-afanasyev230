"""Общие клавиатуры."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CHAT_LINK

MENU_TEXT = "Привет! Я помогу выбрать игру в Екатеринбурге. Что нужно?"

MENU_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎯 Записаться на ближайшую игру", callback_data="menu_record")],
    [InlineKeyboardButton(text="💡 Что это за формат? (1 мин)", callback_data="menu_format")],
    [InlineKeyboardButton(text="📖 Почитать об играх", callback_data="menu_stories")],
    [InlineKeyboardButton(text="💬 Вступить в чат", url=CHAT_LINK)],
    [InlineKeyboardButton(text="📆 Расписание", callback_data="menu_schedule")],
    [InlineKeyboardButton(text="💭 Задать вопрос", callback_data="menu_question")],
])
