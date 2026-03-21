import asyncio
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.client.session.aiohttp import AiohttpSession

from config import (
    BOT_TOKEN,
    ADMIN_IDS,
    CHAT_LINK,
    POST_CHANNEL_1,
    POST_CHANNEL_2,
    POST_CHAT_ID,
    POST_CHAT_THREAD_ID,
    TELEGRAM_PROXY,
)


def _post_chat_thread_kwargs(chat_id: int) -> dict:
    """Для отложенного постинга в группу с темами — указать message_thread_id."""
    if (
        POST_CHAT_ID is not None
        and POST_CHAT_THREAD_ID is not None
        and chat_id == POST_CHAT_ID
    ):
        return {"message_thread_id": POST_CHAT_THREAD_ID}
    return {}
from database import (
    get_game,
    create_tables,
    save_user_utm,
    add_subscription,
    get_subscriptions,
    get_active_funnel_steps,
    get_funnel_log_sent_set,
    mark_funnel_step_sent,
    get_due_scheduled_posts,
    mark_scheduled_post_status,
    get_users_for_broadcast,
)
from middlewares.user_log import UserLogMiddleware
from keyboards import MENU_KB, MENU_TEXT, get_main_reply_kb
from utils import text_to_telegram_html, normalize_telegram_button_url
from handlers.main import router as main_router
from handlers.recording import router as recording_router, start_record as recording_start
from handlers.format_funnel import router as format_router, format_show_screen
from handlers.schedule import router as schedule_router
from handlers.question import router as question_router
from handlers.admin import router as admin_router
from handlers.stories import router as stories_router
from handlers.holiday_quest import router as holiday_router

session = AiohttpSession(proxy=TELEGRAM_PROXY) if TELEGRAM_PROXY else None
bot = Bot(token=BOT_TOKEN, session=session)
dp = Dispatcher()
dp.message.middleware(UserLogMiddleware())
dp.callback_query.middleware(UserLogMiddleware())


async def safe_answer_callback(callback: CallbackQuery):
    """Безопасный ответ на callback query с обработкой ошибок."""
    try:
        await callback.answer()
    except Exception:
        pass  # Игнорируем ошибки для старых/невалидных callback'ов


def _is_html_parse_error(e: Exception) -> bool:
    if not isinstance(e, TelegramBadRequest):
        return False
    msg = str(e).lower()
    return (
        "can't parse entities" in msg
        or "cant parse entities" in msg
        or "unsupported start tag" in msg
        or "wrong tag" in msg
    )


@dp.callback_query(F.data == "menu_record")
async def cb_menu_record(callback: CallbackQuery, state: FSMContext):
    await safe_answer_callback(callback)
    await recording_start(callback, state)

@dp.callback_query(F.data == "menu_format")
async def cb_menu_format(callback: CallbackQuery):
    await safe_answer_callback(callback)
    await format_show_screen(callback)

# Обработчик menu_chat больше не нужен - кнопка теперь использует прямой URL

@dp.callback_query(F.data == "menu_question")
async def cb_menu_question(callback: CallbackQuery, state: FSMContext):
    from handlers.question import QuestionStates
    await safe_answer_callback(callback)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="question_back")],
    ])
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text="Напиши свой вопрос, и менеджер ответит в ближайшее время:",
        reply_markup=kb,
    )
    await state.set_state(QuestionStates.waiting)

@dp.callback_query(F.data == "menu_schedule")
async def cb_menu_schedule(callback: CallbackQuery):
    from handlers.schedule import get_schedule_content
    await safe_answer_callback(callback)
    text, kb = get_schedule_content(with_back=True)
    try:
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=kb,
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
            parse_mode="HTML",
            reply_markup=kb,
        )

@dp.callback_query(F.data == "admin_followup")
async def cb_admin_followup(callback: CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass
    if callback.from_user.id not in ADMIN_IDS:
        return
    from handlers.admin import _show_followup_screen
    try:
        await _show_followup_screen(callback)
    except Exception as e:
        try:
            await callback.message.answer(f"Ошибка: {str(e)[:200]}")
        except Exception:
            pass


@dp.callback_query(F.data.startswith("adm_edit_"))
async def cb_admin_edit_game(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await safe_answer_callback(callback)
        return
    from handlers.admin import _game_edit_kb
    try:
        gid = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка", show_alert=True)
        return
    row = get_game(gid)
    if not row:
        await callback.answer("Игра не найдена", show_alert=True)
        return
    g = row
    _, name, date, time, place, price, desc, limit, hidden = g[:9]
    text = f"✏️ Редактировать: {name}\n\n{date} {time or ''}\n📍 {place or '—'}\n💰 {price or '—'}\n\n{desc or '—'}\nЛимит: {limit}"
    kb = _game_edit_kb(gid, g)
    await callback.answer("Открыто")
    await bot.send_message(
        callback.message.chat.id,
        text,
        reply_markup=kb,
    )

@dp.callback_query(F.data.in_(["menu_back", "question_back"]))
async def cb_menu_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_answer_callback(callback)
    # Всегда удаляем текущее сообщение (может быть фото из сюжета — edit_message_text по нему падает),
    # затем отправляем меню новым сообщением. Так «Назад» гарантированно срабатывает.
    try:
        await callback.bot.delete_message(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
        )
    except Exception:
        pass
    await callback.bot.send_message(
        chat_id=callback.message.chat.id,
        text=MENU_TEXT,
        reply_markup=MENU_KB,
    )


def _funnel_build_queue():
    """Синхронно собирает очередь

    Элементы: (tg_id, step_id, text, media_type, media_file_id, button_text, button_url).
    Один запрос на funnel_log — без блокировки БД.
    """
    steps = get_active_funnel_steps()
    if not steps:
        return []
    sent_set = get_funnel_log_sent_set()
    subs = get_subscriptions(limit=100000)
    now = datetime.now(timezone.utc)
    queue = []
    for tg_id, username, first_name, last_name, started_at in subs:
        if not started_at:
            continue
        try:
            s = str(started_at).replace("Z", "+00:00").strip()
            started_dt = datetime.fromisoformat(s)
            if started_dt.tzinfo is None:
                started_dt = started_dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        delta_hours = (now - started_dt).total_seconds() / 3600.0
        for step in steps:
            step_id, order_num, delay_hours, text, media_type, media_file_id, button_text, button_url = step
            if delta_hours < float(delay_hours or 0):
                continue
            if (tg_id, step_id) in sent_set:
                continue
            queue.append(
                (
                    tg_id,
                    step_id,
                    text or "",
                    media_type,
                    media_file_id,
                    button_text,
                    button_url,
                )
            )
    return queue


# Макс. сообщений автоворонки за один проход — чтобы не перегружать сессию и не задерживать ответы юзеру
FUNNEL_SENDS_PER_CYCLE = 15

async def funnel_worker():
    """Фоновый воркер автоворонки. Сбор очереди в executor; за цикл шлём не больше FUNNEL_SENDS_PER_CYCLE."""
    loop = asyncio.get_event_loop()
    while True:
        try:
            queue = await loop.run_in_executor(None, _funnel_build_queue)
            for tg_id, step_id, text, media_type, media_file_id, button_text, button_url in queue[:FUNNEL_SENDS_PER_CYCLE]:
                try:
                    reply_markup = None
                    if button_text and button_url:
                        reply_markup = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [InlineKeyboardButton(text=button_text, url=button_url)]
                            ]
                        )
                    html_text = text_to_telegram_html(text) if text else None
                    parse_mode = "HTML" if html_text else None
                    if media_type == "photo" and media_file_id:
                        try:
                            await bot.send_photo(
                                tg_id,
                                media_file_id,
                                caption=html_text or None,
                                parse_mode=parse_mode,
                                reply_markup=reply_markup,
                            )
                        except Exception as e:
                            if _is_html_parse_error(e):
                                await bot.send_photo(
                                    tg_id,
                                    media_file_id,
                                    caption=(text or None),
                                    reply_markup=reply_markup,
                                )
                            else:
                                raise
                    elif media_type == "video" and media_file_id:
                        try:
                            await bot.send_video(
                                tg_id,
                                media_file_id,
                                caption=html_text or None,
                                parse_mode=parse_mode,
                                reply_markup=reply_markup,
                            )
                        except Exception as e:
                            if _is_html_parse_error(e):
                                await bot.send_video(
                                    tg_id,
                                    media_file_id,
                                    caption=(text or None),
                                    reply_markup=reply_markup,
                                )
                            else:
                                raise
                    elif media_type == "document" and media_file_id:
                        try:
                            await bot.send_document(
                                tg_id,
                                media_file_id,
                                caption=html_text or None,
                                parse_mode=parse_mode,
                                reply_markup=reply_markup,
                            )
                        except Exception as e:
                            if _is_html_parse_error(e):
                                await bot.send_document(
                                    tg_id,
                                    media_file_id,
                                    caption=(text or None),
                                    reply_markup=reply_markup,
                                )
                            else:
                                raise
                    elif html_text:
                        try:
                            await bot.send_message(
                                tg_id,
                                html_text,
                                parse_mode=parse_mode,
                                reply_markup=reply_markup,
                            )
                        except Exception as e:
                            if _is_html_parse_error(e):
                                await bot.send_message(tg_id, text, reply_markup=reply_markup)
                            else:
                                raise
                    else:
                        continue
                    mark_funnel_step_sent(tg_id, step_id)
                except Exception:
                    continue
                await asyncio.sleep(0.08)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Ошибка воркера автоворонки: {e}")
        await asyncio.sleep(60)


async def scheduled_posts_worker():
    """Фоновый воркер отложенных постов."""
    while True:
        try:
            now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
            posts = get_due_scheduled_posts(now_utc, limit=50)
            for pid, text, media_type, media_file_id, to_ch1, to_ch2, to_chat, to_admins, button_text, button_url in posts:
                targets = []
                if to_ch1 and POST_CHANNEL_1 is not None:
                    targets.append(POST_CHANNEL_1)
                if to_ch2 and POST_CHANNEL_2 is not None:
                    targets.append(POST_CHANNEL_2)
                if to_chat and POST_CHAT_ID is not None:
                    targets.append(POST_CHAT_ID)
                if to_admins:
                    # всем пользователям бота (как в рассылке, фильтр all)
                    user_ids = get_users_for_broadcast("all")
                    targets.extend(user_ids)
                # на всякий случай дедуп
                targets = list(dict.fromkeys(targets))
                if not targets:
                    mark_scheduled_post_status(pid, "failed", "Нет целевых чатов/каналов для отправки")
                    continue
                ok = True
                err = ""
                html_text = text_to_telegram_html(text) if text else None
                parse_mode = "HTML" if html_text else None
                for chat_id in targets:
                    try:
                        th = _post_chat_thread_kwargs(chat_id)
                        reply_markup = None
                        if button_text and button_url:
                            safe_url = normalize_telegram_button_url(button_url)
                            label = (button_text or "")[:64] or "Ссылка"
                            reply_markup = InlineKeyboardMarkup(
                                inline_keyboard=[
                                    [InlineKeyboardButton(text=label, url=safe_url)]
                                ]
                            )
                        if media_type == "photo" and media_file_id:
                            try:
                                await bot.send_photo(
                                    chat_id,
                                    media_file_id,
                                    caption=html_text or None,
                                    parse_mode=parse_mode,
                                    reply_markup=reply_markup,
                                    **th,
                                )
                            except Exception as e:
                                if _is_html_parse_error(e):
                                    await bot.send_photo(
                                        chat_id,
                                        media_file_id,
                                        caption=(text or None),
                                        reply_markup=reply_markup,
                                        **th,
                                    )
                                else:
                                    raise
                        elif media_type == "video" and media_file_id:
                            try:
                                await bot.send_video(
                                    chat_id,
                                    media_file_id,
                                    caption=html_text or None,
                                    parse_mode=parse_mode,
                                    reply_markup=reply_markup,
                                    **th,
                                )
                            except Exception as e:
                                if _is_html_parse_error(e):
                                    await bot.send_video(
                                        chat_id,
                                        media_file_id,
                                        caption=(text or None),
                                        reply_markup=reply_markup,
                                        **th,
                                    )
                                else:
                                    raise
                        elif media_type == "document" and media_file_id:
                            try:
                                await bot.send_document(
                                    chat_id,
                                    media_file_id,
                                    caption=html_text or None,
                                    parse_mode=parse_mode,
                                    reply_markup=reply_markup,
                                    **th,
                                )
                            except Exception as e:
                                if _is_html_parse_error(e):
                                    await bot.send_document(
                                        chat_id,
                                        media_file_id,
                                        caption=(text or None),
                                        reply_markup=reply_markup,
                                        **th,
                                    )
                                else:
                                    raise
                        else:
                            try:
                                await bot.send_message(
                                    chat_id,
                                    html_text or "",
                                    parse_mode=parse_mode,
                                    reply_markup=reply_markup,
                                    **th,
                                )
                            except Exception as e:
                                if _is_html_parse_error(e):
                                    await bot.send_message(chat_id, text or "", reply_markup=reply_markup, **th)
                                else:
                                    raise
                        await asyncio.sleep(0.1)
                    except Exception as e:
                        ok = False
                        err = str(e)[:200]
                mark_scheduled_post_status(pid, "sent" if ok else "failed", err)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Ошибка воркера отложенных постов: {e}")
        await asyncio.sleep(30)

dp.include_router(admin_router)  # первым — admin callbacks (adm_edit_, adm_ef_ и т.д.)
dp.include_router(question_router)
dp.include_router(holiday_router)
dp.include_router(main_router)
dp.include_router(recording_router)
dp.include_router(format_router)
dp.include_router(schedule_router)
dp.include_router(stories_router)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    add_subscription(
        user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )
    utm = {}
    if message.text and message.text.startswith("/start ") and len(message.text.split()) >= 2:
        args = message.text.split(maxsplit=1)[1]
        parts = args.split("_")
        if len(parts) >= 1:
            utm["utm_source"] = parts[0]
        if len(parts) >= 2:
            utm["utm_medium"] = parts[1]
        if len(parts) >= 3:
            utm["utm_campaign"] = parts[2]
    if utm:
        save_user_utm(user.id, **utm)
    # Ставим reply-клавиатуру (над полем ввода), затем отправляем inline-меню
    await message.answer("Кнопки:", reply_markup=get_main_reply_kb(user.id))
    await message.answer(MENU_TEXT, reply_markup=MENU_KB)


@dp.message(F.text == "Старт")
async def btn_start(message: Message):
    # Быстрый возврат в главное меню без /start
    await message.answer(MENU_TEXT, reply_markup=MENU_KB)


@dp.message(F.text == "Админ")
async def btn_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    # Открываем админку без /admin
    from handlers.admin import cmd_admin as _cmd_admin
    await _cmd_admin(message)


async def main():
    create_tables()
    from database import seed_demo_data
    seed_demo_data()
    print("Бот запущен. ADMIN_IDS:", ADMIN_IDS or "(пусто)")
    funnel_task = asyncio.create_task(funnel_worker())
    scheduled_task = asyncio.create_task(scheduled_posts_worker())
    try:
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        print("\nБот остановлен.")
        for task in (funnel_task, scheduled_task):
            task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        try:
            await bot.session.close()
        except Exception:
            pass
        raise
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем.")
    except Exception as e:
        print(f"Ошибка при работе бота: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nВыход.")
