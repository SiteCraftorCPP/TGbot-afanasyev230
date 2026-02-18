import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config import BOT_TOKEN, ADMIN_IDS, CHAT_LINK
from database import get_game
from database import create_tables, save_user_utm
from keyboards import MENU_KB, MENU_TEXT
from handlers.main import router as main_router
from handlers.recording import router as recording_router, start_record as recording_start
from handlers.format_funnel import router as format_router, format_show_screen
from handlers.schedule import router as schedule_router
from handlers.question import router as question_router
from handlers.admin import router as admin_router
from handlers.stories import router as stories_router

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def safe_answer_callback(callback: CallbackQuery):
    """Безопасный ответ на callback query с обработкой ошибок."""
    try:
        await callback.answer()
    except Exception:
        pass  # Игнорируем ошибки для старых/невалидных callback'ов


@dp.callback_query(F.data == "menu_record")
async def cb_menu_record(callback: CallbackQuery, state: FSMContext):
    await safe_answer_callback(callback)
    await recording_start(callback, state)

@dp.callback_query(F.data == "menu_format")
async def cb_menu_format(callback: CallbackQuery):
    await safe_answer_callback(callback)
    await format_show_screen(callback, 0)

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
            reply_markup=kb,
            parse_mode="Markdown",
        )
    except Exception:
        # Если текущее сообщение — фото/медиа (например, из "Сюжеты"), редактирование текста упадёт.
        # Тогда удаляем и отправляем расписание новым сообщением.
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
            parse_mode="Markdown",
        )

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
    try:
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=MENU_TEXT,
            reply_markup=MENU_KB,
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
            text=MENU_TEXT,
            reply_markup=MENU_KB,
        )

dp.include_router(admin_router)  # первым — admin callbacks (adm_edit_, adm_ef_ и т.д.)
dp.include_router(question_router)
dp.include_router(main_router)
dp.include_router(recording_router)
dp.include_router(format_router)
dp.include_router(schedule_router)
dp.include_router(stories_router)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
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
    await message.answer(MENU_TEXT, reply_markup=MENU_KB)


async def main():
    create_tables()
    from database import seed_demo_data
    seed_demo_data()
    print("Бот запущен. ADMIN_IDS:", ADMIN_IDS or "(пусто)")
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем.")
    except Exception as e:
        print(f"Ошибка при работе бота: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
