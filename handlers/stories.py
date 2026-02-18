from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from config import CHAT_LINK
from database import get_visible_stories, get_story, get_visible_games

router = Router()


def _split_content(content: str, max_length: int = 1000):
    """Разбивает длинный текст на части для отображения на разных экранах."""
    if len(content) <= max_length:
        return [content]
    
    parts = []
    sentences = content.split('. ')
    current_part = ""
    
    for sentence in sentences:
        if len(current_part) + len(sentence) + 2 <= max_length:
            current_part += sentence + ". " if sentence else sentence
        else:
            if current_part:
                parts.append(current_part.strip())
            current_part = sentence + ". " if sentence else sentence
    
    if current_part:
        parts.append(current_part.strip())
    
    return parts if parts else [content]


async def show_story_screen(bot, chat_id, message_id, story_id: int, screen_idx: int = 0, edit: bool = True, back_callback: str = "stories_back", story_index: int = None, total_stories: int = None):
    """Показать экран сюжета.
    
    Args:
        back_callback: callback_data для кнопки "Назад" (по умолчанию "stories_back")
        story_index: индекс текущего сюжета в списке (для переключения между сюжетами)
        total_stories: всего сюжетов (для переключения между сюжетами)
    """
    story = get_story(story_id)
    if not story:
        return False
    
    sid, title, content, image_url, game_id, order_num, hidden = story[:7]
    
    # Разбиваем контент на части
    content_parts = _split_content(content)
    
    if screen_idx >= len(content_parts):
        screen_idx = len(content_parts) - 1
    
    current_text = content_parts[screen_idx]
    display_text = f"**{title}**\n\n{current_text}"
    
    # Кнопки
    kb = []
    
    # Кнопки для переключения между экранами сюжета
    if screen_idx < len(content_parts) - 1:
        # Для следующего экрана используем тот же back_callback
        if back_callback != "stories_back":
            kb.append([InlineKeyboardButton(text="✨ Дальше", callback_data=f"rstory_{sid}_{screen_idx + 1}")])
        else:
            kb.append([InlineKeyboardButton(text="✨ Дальше", callback_data=f"story_{sid}_{screen_idx + 1}")])
    
    # Кнопки для переключения между сюжетами (если указаны индексы)
    if story_index is not None and total_stories is not None and total_stories > 1:
        nav_buttons = []
        if story_index > 0:
            nav_buttons.append(InlineKeyboardButton(text="🔙 Предыдущий", callback_data=f"story_nav_{story_index - 1}"))
        if story_index < total_stories - 1:
            nav_buttons.append(InlineKeyboardButton(text="✨ Следующий", callback_data=f"story_nav_{story_index + 1}"))
        if nav_buttons:
            kb.append(nav_buttons)
    
    kb.extend([
        [
            InlineKeyboardButton(text="🎯 Записаться", callback_data="menu_record"),
            InlineKeyboardButton(text="📆 Расписание", callback_data="menu_schedule"),
        ],
        [InlineKeyboardButton(text="💬 Вступить в чат", url=CHAT_LINK)],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback)],
    ])
    
    reply_markup = InlineKeyboardMarkup(inline_keyboard=kb)
    
    # Отправка с изображением или без
    # Используем file_id напрямую, если это file_id, иначе URL
    if image_url and screen_idx == 0:  # Показываем изображение только на первом экране
        try:
            if edit:
                # Пытаемся отредактировать сообщение с фото
                try:
                    await bot.edit_message_media(
                        chat_id=chat_id,
                        message_id=message_id,
                        media=InputMediaPhoto(media=image_url, caption=display_text, parse_mode="Markdown"),
                        reply_markup=reply_markup,
                    )
                except Exception as e:
                    # Если не получилось отредактировать (например, было текстовое сообщение), удаляем и отправляем заново
                    try:
                        await bot.delete_message(chat_id=chat_id, message_id=message_id)
                    except Exception:
                        pass
                    # Отправляем новое сообщение с фото
                    sent_msg = await bot.send_photo(
                        chat_id=chat_id,
                        photo=image_url,
                        caption=display_text,
                        reply_markup=reply_markup,
                        parse_mode="Markdown",
                    )
                    return True  # Возвращаем True, так как сообщение отправлено
            else:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=image_url,
                    caption=display_text,
                    reply_markup=reply_markup,
                    parse_mode="Markdown",
                )
        except Exception as e:
            # Если не удалось отправить фото, отправляем текст
            if edit:
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=display_text,
                        reply_markup=reply_markup,
                        parse_mode="Markdown",
                    )
                except Exception:
                    # Если не получилось отредактировать, удаляем и отправляем заново
                    try:
                        await bot.delete_message(chat_id=chat_id, message_id=message_id)
                    except Exception:
                        pass
                    await bot.send_message(
                        chat_id=chat_id,
                        text=display_text,
                        reply_markup=reply_markup,
                        parse_mode="Markdown",
                    )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=display_text,
                    reply_markup=reply_markup,
                    parse_mode="Markdown",
                )
    else:
        if edit:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=display_text,
                    reply_markup=reply_markup,
                    parse_mode="Markdown",
                )
            except Exception:
                # Если было фото, а теперь текст - удаляем и отправляем заново
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                except Exception:
                    pass
                await bot.send_message(
                    chat_id=chat_id,
                    text=display_text,
                    reply_markup=reply_markup,
                    parse_mode="Markdown",
                )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=display_text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
    
    return True




@router.callback_query(F.data == "menu_stories")
async def cb_stories_list(callback: types.CallbackQuery):
    """Показать первый сюжет сразу, с возможностью листать."""
    try:
        await callback.answer()
    except Exception:
        pass
    
    stories = get_visible_stories()
    if not stories:
        text = "📖 Пока нет доступных сюжетов. Следи за обновлениями!"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
        ])
        try:
            await callback.bot.edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text=text,
                reply_markup=kb,
            )
        except Exception:
            # Если не получилось отредактировать (например, было фото), удаляем и отправляем заново
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
                reply_markup=kb,
            )
        return
    
    # Показываем первый сюжет сразу
    first_story_id = stories[0][0]
    # При первом показе используем edit=True, но show_story_screen сам обработает случай с фото
    await show_story_screen(
        callback.bot,
        callback.message.chat.id,
        callback.message.message_id,
        first_story_id,
        screen_idx=0,
        edit=True,  # Редактируем сообщение меню
        back_callback="menu_back",
        story_index=0,  # Индекс текущего сюжета в списке
        total_stories=len(stories),  # Всего сюжетов
    )


@router.callback_query(F.data.startswith("story_nav_"))
async def cb_story_nav(callback: types.CallbackQuery):
    """Переключение между сюжетами."""
    try:
        await callback.answer()
    except Exception:
        pass
    
    try:
        story_index = int(callback.data.split("_")[2])
    except ValueError:
        return
    
    stories = get_visible_stories()
    if not stories or story_index < 0 or story_index >= len(stories):
        return
    
    story_id = stories[story_index][0]
    await show_story_screen(
        callback.bot,
        callback.message.chat.id,
        callback.message.message_id,
        story_id,
        screen_idx=0,
        edit=True,
        back_callback="menu_back",
        story_index=story_index,
        total_stories=len(stories),
    )


@router.callback_query(F.data.startswith("story_"))
async def cb_story_screen(callback: types.CallbackQuery):
    """Показать экран сюжета."""
    try:
        await callback.answer()
    except Exception:
        pass
    
    # Проверяем, что это не story_nav_
    if callback.data.startswith("story_nav_"):
        return
    
    parts = callback.data.split("_")
    if len(parts) < 3:
        return
    
    try:
        story_id = int(parts[1])
        screen_idx = int(parts[2])
    except ValueError:
        return
    
    # Получаем список сюжетов для определения индекса
    stories = get_visible_stories()
    story_index = None
    for idx, s in enumerate(stories):
        if s[0] == story_id:
            story_index = idx
            break
    
    await show_story_screen(
        callback.bot,
        callback.message.chat.id,
        callback.message.message_id,
        story_id,
        screen_idx,
        edit=True,
        back_callback="menu_back",
        story_index=story_index,
        total_stories=len(stories) if stories else None,
    )


@router.callback_query(F.data == "stories_back")
async def cb_stories_back(callback: types.CallbackQuery):
    """Вернуться к списку сюжетов."""
    try:
        await callback.answer()
    except Exception:
        pass
    
    # Вызываем cb_stories_list, который правильно обработает случай с фото
    await cb_stories_list(callback)
