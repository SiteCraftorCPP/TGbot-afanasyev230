"""Общие клавиатуры."""
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from config import CHAT_LINK, ADMIN_IDS

MENU_TEXT = "Привет! Я помогу выбрать игру в Екатеринбурге. Что нужно?"

MENU_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎯 Записаться на ближайшую игру", callback_data="menu_record")],
    [InlineKeyboardButton(text="🎂 Заказать квест на праздник", callback_data="menu_holiday_quest")],
    [InlineKeyboardButton(text="💡 Что это за формат? (1 мин)", callback_data="menu_format")],
    [InlineKeyboardButton(text="📚 Подробнее о сценариях", callback_data="menu_stories")],
    [InlineKeyboardButton(text="💬 Вступить в чат", url=CHAT_LINK)],
    [InlineKeyboardButton(text="📆 Расписание", callback_data="menu_schedule")],
    [InlineKeyboardButton(text="💭 Задать вопрос", callback_data="menu_question")],
])


MAIN_REPLY_KB_USER = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Старт")]],
    resize_keyboard=True,
    one_time_keyboard=False,
)

MAIN_REPLY_KB_ADMIN = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Админ"), KeyboardButton(text="Старт")]],
    resize_keyboard=True,
    one_time_keyboard=False,
)


def get_main_reply_kb(user_id: int):
    return MAIN_REPLY_KB_ADMIN if user_id in ADMIN_IDS else MAIN_REPLY_KB_USER
