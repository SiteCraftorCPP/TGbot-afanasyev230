"""Заказ квеста на праздник: Имя → Номер → отправка заявки."""
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import OPERATOR_CHAT_ID
from database import add_holiday_order

router = Router()


class HolidayOrderStates(StatesGroup):
    get_name = State()
    get_phone = State()


def _back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
    ])


@router.callback_query(F.data == "menu_holiday_quest")
async def holiday_quest_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(HolidayOrderStates.get_name)
    await callback.message.answer(
        "🎂 **Заказ квеста на праздник**\n\nУкажите ваше имя:",
        reply_markup=_back_kb(),
        parse_mode="Markdown",
    )


@router.message(HolidayOrderStates.get_name, F.text)
async def holiday_quest_name(message: types.Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name:
        await message.answer("Введите имя текстом.")
        return
    await state.update_data(name=name)
    await state.set_state(HolidayOrderStates.get_phone)
    await message.answer(
        "Укажите номер телефона:",
        reply_markup=_back_kb(),
    )


@router.message(HolidayOrderStates.get_phone, F.text)
async def holiday_quest_phone(message: types.Message, state: FSMContext):
    phone = (message.text or "").strip()
    if not phone:
        await message.answer("Введите номер телефона.")
        return
    data = await state.get_data()
    name = data.get("name", "")
    await state.clear()
    user = message.from_user
    add_holiday_order(tg_id=user.id, username=user.username, name=name, phone=phone)
    notify = (
        f"🎂 **Заявка: квест на праздник**\n\n"
        f"Имя: {name}\n"
        f"Телефон: {phone}\n"
        f"От: @{user.username or '—'} | {user.full_name or '—'}"
    )
    try:
        await message.bot.send_message(OPERATOR_CHAT_ID, notify, parse_mode="Markdown")
    except Exception:
        pass
    await message.answer(
        "✓ Заявка отправлена! Менеджер свяжется с вами в ближайшее время.",
        reply_markup=_back_kb(),
    )
