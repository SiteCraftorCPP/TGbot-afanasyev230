from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CHAT_LINK
from database import get_format_screens

router = Router()

# Ссылка на видео о формате
VIDEO_URL = "https://www.youtube.com/watch?v=x3Ir917gDiM&list=PLDqVqfBsY9O-fPcm-pK-TpYWfnuJWSBFI"


def _get_screens():
    """Получает экраны из БД и преобразует в формат для отображения."""
    db_screens = get_format_screens()
    # db_screens: [(id, title, text, video_url), ...]
    return [{"title": s[1], "text": s[2], "video_url": s[3]} for s in db_screens]


def cta_keyboard(screen_idx: int, total_screens: int):
    """Единый порядок кнопок на всех экранах: Видео → Дальше → Записаться/Расписание → Чат → Назад."""
    kb = []
    
    # Кнопка видео теперь зависит от настройки в БД (video_url)
    # Но для обратной совместимости или если в БД не заполнено, можно использовать VIDEO_URL
    # В текущей реализации БД мы добавили video_url в таблицу.
    # Здесь мы просто добавим общую кнопку, если это первые экраны, как раньше, 
    # или можно брать URL из экрана. 
    # По требованию "везде должна быть кнопка с видео" - оставляем VIDEO_URL.
    kb.append([InlineKeyboardButton(text="🎬 Посмотреть видео", url=VIDEO_URL)])
    
    if screen_idx < total_screens - 1:
        kb.append([InlineKeyboardButton(text="✨ Дальше", callback_data=f"format_{screen_idx + 1}")])
        
    kb.extend([
        [
            InlineKeyboardButton(text="🎯 Записаться", callback_data="menu_record"),
            InlineKeyboardButton(text="📆 Расписание", callback_data="menu_schedule"),
        ],
        [InlineKeyboardButton(text="💬 Вступить в чат", url=CHAT_LINK)],
    ])
    back_data = "menu_back" if screen_idx == 0 else f"format_{screen_idx - 1}"
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data=back_data)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


# Что это за формат обрабатывается в main.py handle_menu


async def format_show_screen(target, screen_idx: int):
    screens = _get_screens()
    if not screens:
        return
        
    if screen_idx >= len(screens):
        screen_idx = 0
        
    s = screens[screen_idx]
    text = f"**{s['title']}**\n\n{s['text']}"
    kb = cta_keyboard(screen_idx, len(screens))
    
    if hasattr(target, "bot") and hasattr(target, "message"):
        try:
            await target.bot.edit_message_text(
                chat_id=target.message.chat.id,
                message_id=target.message.message_id,
                text=text,
                reply_markup=kb,
                parse_mode="Markdown",
            )
        except Exception:
            # Fallback для фото
            try:
                await target.bot.delete_message(chat_id=target.message.chat.id, message_id=target.message.message_id)
            except Exception:
                pass
            await target.bot.send_message(
                chat_id=target.message.chat.id,
                text=text,
                reply_markup=kb,
                parse_mode="Markdown",
            )
    else:
        await target.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("format_"))
async def format_next(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass  # Игнорируем ошибки для старых callback'ов
    idx = int(callback.data.split("_")[1])
    await format_show_screen(callback, idx)
