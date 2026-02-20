import logging
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from config import CHAT_LINK
from database import get_story, get_scenarios, get_stories_by_scenario

logger = logging.getLogger(__name__)
router = Router()

# Лимит подписи к фото в Telegram
CAPTION_MAX_LENGTH = 1024


async def show_scenarios_list(callback: types.CallbackQuery):
    """Показать список сценариев кнопками."""
    scenarios = get_scenarios()
    
    text = "📚 **Библиотека сценариев**"
    if not scenarios:
        text = "Пока нет доступных сценариев."
    
    kb = []
    for s in scenarios:
        sid, name, desc = s
        kb.append([InlineKeyboardButton(text=name, callback_data=f"story_scen_{sid}")])
    
    kb.append([InlineKeyboardButton(text="🔙 Назад в меню", callback_data="menu_back")])
    
    # Пытаемся редактировать или отправляем новое
    try:
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        )
    except Exception:
        try:
            await callback.bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
            )
        except Exception:
            pass
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text=text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        )


async def show_story_screen(bot, chat_id, message_id, story_id: int, edit: bool = True, story_index: int = None, total_stories: int = None, scenario_id: int = None):
    """Показать экран сюжетной линии сценария.
    
    Args:
        story_id: ID сюжета
        story_index: индекс текущего сюжета в сценарии (0-based)
        total_stories: всего сюжетов в сценарии
        scenario_id: ID сценария (для навигации)
    """
    story = get_story(story_id)
    if not story:
        return False
    
    # story: (id, title, content, image_url, game_id, order_num, hidden, scenario_id, created_at)
    sid, title, content, image_url, game_id, order_num, hidden, scen_id = story[:8]
    image_url = (image_url or "").strip()
    
    # Текст без parse_mode — контент из БД может содержать _ * [ ] и ломать Markdown
    display_text = f"{title}\n\n{content}"
    caption_plain = display_text
    # Лимит Telegram
    if len(display_text) > 4096:
        display_text = display_text[:4093] + "..."
    caption_for_photo = caption_plain[:CAPTION_MAX_LENGTH]
    
    # Кнопки навигации внутри сценария
    kb = []
    
    nav_buttons = []
    if story_index is not None and total_stories is not None and total_stories > 1 and scenario_id:
        if story_index > 0:
            nav_buttons.append(InlineKeyboardButton(text="🔙 Назад", callback_data=f"story_nav_{scenario_id}_{story_index - 1}"))
        if story_index < total_stories - 1:
            nav_buttons.append(InlineKeyboardButton(text="✨ Дальше", callback_data=f"story_nav_{scenario_id}_{story_index + 1}"))
    
    if nav_buttons:
        kb.append(nav_buttons)
    
    # Кнопка "Все сценарии"
    kb.append([InlineKeyboardButton(text="📚 Все сценарии", callback_data="menu_stories")])
    
    # Кнопки действий
    kb.extend([
        [
            InlineKeyboardButton(text="🎯 Записаться", callback_data="menu_record"),
            InlineKeyboardButton(text="📆 Расписание", callback_data="menu_schedule"),
        ],
    ])
    
    reply_markup = InlineKeyboardMarkup(inline_keyboard=kb)
    
    # Отправка с изображением или без (подпись без Markdown — иначе API падает и фото не уходит)
    # Важно: если у сюжета есть фото — держим его на всех экранах, иначе при "Дальше"
    # фото-сообщение пытались заменить на текст и получались дубли/пропажа фото.
    if image_url:
        try:
            if edit:
                try:
                    await bot.edit_message_media(
                        chat_id=chat_id,
                        message_id=message_id,
                        media=InputMediaPhoto(media=image_url, caption=caption_for_photo),
                        reply_markup=reply_markup,
                    )
                except Exception as e1:
                    logger.debug("edit_message_media failed: %s", e1)
                    try:
                        await bot.delete_message(chat_id=chat_id, message_id=message_id)
                    except Exception:
                        pass
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=image_url,
                        caption=caption_for_photo,
                        reply_markup=reply_markup,
                    )
                    return True
            else:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=image_url,
                    caption=caption_for_photo,
                    reply_markup=reply_markup,
                )
        except Exception as e:
            logger.warning("Story photo send failed story_id=%s image_url=%s: %s", story_id, (image_url[:30] if image_url else ""), e)
            if edit:
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=display_text,
                        reply_markup=reply_markup,
                    )
                except Exception:
                    try:
                        await bot.delete_message(chat_id=chat_id, message_id=message_id)
                    except Exception:
                        pass
                    await bot.send_message(
                        chat_id=chat_id,
                        text=display_text,
                        reply_markup=reply_markup,
                    )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=display_text,
                    reply_markup=reply_markup,
                )
    else:
        if edit:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=display_text,
                    reply_markup=reply_markup,
                )
            except Exception:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                except Exception:
                    pass
                await bot.send_message(
                    chat_id=chat_id,
                    text=display_text,
                    reply_markup=reply_markup,
                )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=display_text,
                reply_markup=reply_markup,
            )
    
    return True




@router.callback_query(F.data == "menu_stories")
async def cb_stories_list(callback: types.CallbackQuery):
    """Показать список сценариев."""
    try:
        await callback.answer()
    except Exception:
        pass
    await show_scenarios_list(callback)


@router.callback_query(F.data.startswith("story_scen_"))
async def cb_story_scenario(callback: types.CallbackQuery):
    """Выбран сценарий -> показать первую сюжетную линию."""
    try:
        await callback.answer()
    except Exception:
        pass
        
    try:
        sid = int(callback.data.split("_")[2])
    except ValueError:
        return

    stories = get_stories_by_scenario(sid)
    if not stories:
        await callback.answer("В этом сценарии пока нет сюжетов", show_alert=True)
        return

    first_story = stories[0]
    await show_story_screen(
        callback.bot,
        callback.message.chat.id,
        callback.message.message_id,
        first_story[0],
        edit=True,
        story_index=0,
        total_stories=len(stories),
        scenario_id=sid
    )


@router.callback_query(F.data.startswith("story_nav_"))
async def cb_story_nav(callback: types.CallbackQuery):
    """Навигация по сюжетным линиям внутри сценария."""
    try:
        await callback.answer()
    except Exception:
        pass
    
    parts = callback.data.split("_")
    if len(parts) < 4:
        return
    
    try:
        scenario_id = int(parts[2])
        story_index = int(parts[3])
    except ValueError:
        return
    
    stories = get_stories_by_scenario(scenario_id)
    if not stories or story_index < 0 or story_index >= len(stories):
        return
    
    story_id = stories[story_index][0]
    await show_story_screen(
        callback.bot,
        callback.message.chat.id,
        callback.message.message_id,
        story_id,
        edit=True,
        story_index=story_index,
        total_stories=len(stories),
        scenario_id=scenario_id
    )
