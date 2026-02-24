from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_visible_games
from config import CHAT_LINK
from utils import text_to_telegram_html

router = Router()

# URL для Bronibiz/Афиша — можно задать в .env
BRONIBIZ_URL = "https://example.com"  # заменить на реальный


def get_schedule_content(with_back: bool = False):
    games = get_visible_games()
    if not games:
        text = "Пока нет запланированных игр. Следи за обновлениями в чате!"
    else:
        lines = []
        for g in games:
            gid, name, date, time, place, price, desc, limit = g
            name_fmt = text_to_telegram_html(name)
            line = f"• {name_fmt} — {date}"
            if time:
                line += f" {time}"
            if place:
                line += f"\n   📍 {place}"
            if price:
                line += f"\n   💰 {price}"
            if desc:
                line += f"\n   {text_to_telegram_html(desc)}"
            lines.append(line)
        text = "📆 Ближайшие игры:\n\n" + "\n\n".join(lines)
    kb = [
        [InlineKeyboardButton(text="🎯 Записаться", callback_data="menu_record")],
        [InlineKeyboardButton(text="💬 Вступить в чат", url=CHAT_LINK)],
    ]
    if with_back:
        kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")])
    return text, InlineKeyboardMarkup(inline_keyboard=kb)


async def show_schedule(message: types.Message, with_back: bool = False):
    text, kb = get_schedule_content(with_back)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(lambda c: c.data == "schedule")
async def cb_schedule(callback: types.CallbackQuery):
    await callback.answer()
    text, kb = get_schedule_content(with_back=True)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await show_schedule(callback.message, with_back=True)
