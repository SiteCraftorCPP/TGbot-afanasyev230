from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import OPERATOR_CHAT_ID
from database import add_question

router = Router()


class QuestionStates(StatesGroup):
    waiting = State()


@router.message(QuestionStates.waiting, F.text)
async def question_save(message: types.Message, state: FSMContext):
    user = message.from_user
    qid = add_question(
        tg_id=user.id,
        username=user.username,
        name=user.full_name or "",
        question_text=message.text,
    )
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="menu_back")],
    ])
    await message.answer("✓ Вопрос отправлен менеджеру. Ответим в ближайшее время!", reply_markup=kb)
    # Публикация в чат операторов
    notify = (
        f"💭 Вопрос\n"
        f"От: @{user.username or '—'} | {user.full_name or 'Без имени'}\n\n"
        f"{message.text}"
    )
    try:
        await message.bot.send_message(OPERATOR_CHAT_ID, notify)
    except Exception:
        pass


@router.callback_query(F.data == "question_btn")
async def question_btn(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="question_back")],
    ])
    await callback.message.answer(
        "Напиши свой вопрос, и менеджер ответит в ближайшее время:",
        reply_markup=kb,
    )
    await state.set_state(QuestionStates.waiting)
