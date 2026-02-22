"""Раздел «Что это за формат?» — один экран: картинка (если задана) + текст из админки.
Блоки воронки (для кого подходит, не с кем играть и т.д.) здесь не отображаются."""
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from config import CHAT_LINK
from database import get_format_info

router = Router()

CAPTION_MAX_LENGTH = 1024


async def format_show_screen(target):
    """Показать один экран «Что это за формат?»: картинка (если есть) + текст + кнопка видео."""
    text, image_url, video_url = get_format_info()
    image_url = (image_url or "").strip()
    video_url = (video_url or "").strip()

    if not text:
        text = "Сюжетная игра (ролевой квест) — это как фильм, только ты внутри истории.\n\nТебе дают роль и цель, дальше события разворачиваются через общение и решения. Ведущий всё ведёт и помогает."

    kb_rows = [
        [
            InlineKeyboardButton(text="🎯 Записаться", callback_data="menu_record"),
            InlineKeyboardButton(text="📆 Расписание", callback_data="menu_schedule"),
        ],
        [InlineKeyboardButton(text="💬 Вступить в чат", url=CHAT_LINK)],
    ]
    if video_url:
        kb_rows.append([InlineKeyboardButton(text="🎬 Смотреть видео", url=video_url)])
    kb_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    if image_url:
        caption = text[:CAPTION_MAX_LENGTH]  # text already escaped
        if hasattr(target, "bot") and hasattr(target, "message"):
            try:
                await target.bot.edit_message_media(
                    chat_id=target.message.chat.id,
                    message_id=target.message.message_id,
                    media=InputMediaPhoto(media=image_url, caption=caption),
                    reply_markup=kb,
                )
            except Exception:
                try:
                    await target.bot.delete_message(
                        chat_id=target.message.chat.id,
                        message_id=target.message.message_id,
                    )
                except Exception:
                    pass
                await target.bot.send_photo(
                    chat_id=target.message.chat.id,
                    photo=image_url,
                    caption=caption,
                    reply_markup=kb,
                )
        else:
            await target.answer_photo(photo=image_url, caption=caption, reply_markup=kb)
    else:
        if hasattr(target, "bot") and hasattr(target, "message"):
            try:
                await target.bot.edit_message_text(
                    chat_id=target.message.chat.id,
                    message_id=target.message.message_id,
                    text=text,
                    reply_markup=kb,
                )
            except Exception:
                try:
                    await target.bot.delete_message(
                        chat_id=target.message.chat.id,
                        message_id=target.message.message_id,
                    )
                except Exception:
                    pass
                await target.bot.send_message(
                    chat_id=target.message.chat.id,
                    text=text,
                    reply_markup=kb,
                )
        else:
            await target.answer(text, reply_markup=kb)
