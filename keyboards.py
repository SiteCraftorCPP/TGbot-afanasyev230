"""Общие клавиатуры."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

MENU_TEXT = "Привет! Я помогу выбрать игру в Екатеринбурге. Что нужно?"

MENU_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎟 Записаться на ближайшую игру", callback_data="menu_record")],
    [InlineKeyboardButton(text="🧩 Что это за формат? (1 мин)", callback_data="menu_format")],
    [InlineKeyboardButton(text="🤝 Вступить в чат (знакомства/компания)", callback_data="menu_chat")],
    [InlineKeyboardButton(text="🗓 Расписание", callback_data="menu_schedule")],
    [InlineKeyboardButton(text="❓ Задать вопрос менеджеру", callback_data="menu_question")],
])
