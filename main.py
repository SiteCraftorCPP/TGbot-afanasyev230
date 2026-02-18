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

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.callback_query(F.data == "menu_record")
async def cb_menu_record(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await recording_start(callback, state)

@dp.callback_query(F.data == "menu_format")
async def cb_menu_format(callback: CallbackQuery):
    await callback.answer()
    await format_show_screen(callback, 0)

@dp.callback_query(F.data == "menu_chat")
async def cb_menu_chat(callback: CallbackQuery):
    await callback.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Вступить в чат", url=CHAT_LINK)],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
    ])
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=f"Переходи в наш чат:\n\n👉 {CHAT_LINK}",
        reply_markup=kb,
    )

@dp.callback_query(F.data == "menu_question")
async def cb_menu_question(callback: CallbackQuery, state: FSMContext):
    from handlers.question import QuestionStates
    await callback.answer()
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
    await callback.answer()
    text, kb = get_schedule_content(with_back=True)
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=text,
        reply_markup=kb,
        parse_mode="Markdown",
    )

@dp.callback_query(F.data.startswith("adm_edit_"))
async def cb_admin_edit_game(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
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

@dp.callback_query(F.data.in_(["menu_back", "rback_game", "question_back"]))
async def cb_menu_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=MENU_TEXT,
        reply_markup=MENU_KB,
    )

dp.include_router(admin_router)  # первым — admin callbacks (adm_edit_, adm_ef_ и т.д.)
dp.include_router(question_router)
dp.include_router(main_router)
dp.include_router(recording_router)
dp.include_router(format_router)
dp.include_router(schedule_router)


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
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
