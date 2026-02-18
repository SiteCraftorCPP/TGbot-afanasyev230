from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import OPERATOR_CHAT_ID
from database import get_visible_games, add_lead, get_game, get_user_utm

router = Router()


class RecordStates(StatesGroup):
    choose_game = State()
    choose_count = State()
    get_contact = State()
    get_comment = State()
    confirm = State()


def _back_btn(callback_data="menu_back"):
    return [InlineKeyboardButton(text="🔙 Назад", callback_data=callback_data)]

def _games_keyboard():
    games = get_visible_games()
    if not games:
        return None
    kb = []
    for g in games:
        gid, name, date, time, place, price, desc, limit = g
        label = f"{name} — {date}"
        if time:
            label += f" {time}"
        kb.append([InlineKeyboardButton(text=label, callback_data=f"rgame_{gid}")])
    kb.append(_back_btn("rback_game"))
    return InlineKeyboardMarkup(inline_keyboard=kb)


def _count_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=str(i), callback_data=f"rcount_{i}") for i in (1, 2, 3, 4)],
            [InlineKeyboardButton(text="5+", callback_data="rcount_5")],
            _back_btn("rback_count"),
        ]
    )


async def start_record(callback_or_msg, state: FSMContext):
    games = get_visible_games()
    is_callback = hasattr(callback_or_msg, "message") and hasattr(callback_or_msg, "bot")
    msg = callback_or_msg.message if is_callback else callback_or_msg
    bot = callback_or_msg.bot if is_callback else None

    if not games:
        text = "Пока нет доступных игр. Загляни в расписание или задай вопрос менеджеру."
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Расписание", callback_data="menu_schedule")],
                [InlineKeyboardButton(text="Вопрос менеджеру", callback_data="menu_question")],
                _back_btn(),
            ]
        )
        if is_callback and bot:
            await bot.edit_message_text(chat_id=msg.chat.id, message_id=msg.message_id, text=text, reply_markup=kb)
        else:
            await msg.answer(text, reply_markup=kb)
        await state.clear()
        return False

    text = "Выбери игру/дату:"
    kb = _games_keyboard()
    if is_callback and bot:
        await bot.edit_message_text(chat_id=msg.chat.id, message_id=msg.message_id, text=text, reply_markup=kb)
    else:
        await msg.answer(text, reply_markup=kb)
    await state.set_state(RecordStates.choose_game)
    return True


@router.callback_query(F.data == "record_game")
async def cb_record(callback: types.CallbackQuery, state: FSMContext):
    await start_record(callback, state)


# Записаться обрабатывается в main.py handle_menu


@router.callback_query(RecordStates.choose_game, F.data.startswith("rgame_"))
async def record_choose_game(callback: types.CallbackQuery, state: FSMContext):
    gid = int(callback.data.split("_")[1])
    row = get_game(gid)
    if not row:
        await callback.answer("Игра не найдена", show_alert=True)
        return
    g = row
    await state.update_data(game_id=gid, game_name=g[1])
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=f"Выбрано: **{g[1]}**\n{g[2]} {g[3] or ''}\n\nСколько человек будет?",
        reply_markup=_count_keyboard(),
        parse_mode="Markdown",
    )
    await state.set_state(RecordStates.choose_count)
    await callback.answer()


@router.callback_query(RecordStates.choose_count, F.data == "rback_count")
async def record_back_count(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(RecordStates.choose_game)
    text = "Выбери игру/дату:"
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=text,
        reply_markup=_games_keyboard(),
    )
    await callback.answer()


@router.callback_query(RecordStates.choose_count, F.data.startswith("rcount_"))
async def record_choose_count(callback: types.CallbackQuery, state: FSMContext):
    cnt = callback.data.split("_")[1]
    cnt_int = 5 if cnt == "5" else int(cnt)
    await state.update_data(participants_count=cnt_int)
    await callback.message.answer(
        "Оставь контакт для связи с менеджером.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Пропустить", callback_data="rskip_contact")],
                _back_btn("rback_contact"),
            ]
        ),
    )
    await state.set_state(RecordStates.get_contact)
    await callback.answer()


@router.message(RecordStates.get_contact, F.contact)
async def record_contact_shared(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else ""
    await _record_got_contact(message, state, phone)


@router.message(RecordStates.get_contact, F.text)
async def record_contact_text(message: types.Message, state: FSMContext):
    phone = (message.text or "").strip()
    await _record_got_contact(message, state, phone)


@router.callback_query(RecordStates.get_contact, F.data == "rback_contact")
async def record_back_contact(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    game_name = data.get("game_name", "")
    await state.set_state(RecordStates.choose_count)
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=f"Выбрано: **{game_name}**\n\nСколько человек будет?",
        reply_markup=_count_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(RecordStates.get_contact, F.data == "rskip_contact")
async def record_skip_contact(callback: types.CallbackQuery, state: FSMContext):
    await _record_got_contact(callback.message, state, "", callback)


async def _record_got_contact(target, state: FSMContext, phone: str, callback=None):
    await state.update_data(phone=phone)
    await state.set_state(RecordStates.get_comment)
    text = "Комментарий (необязательно):"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="rskip_comment")],
            _back_btn("rback_comment"),
        ]
    )
    if callback:
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=text,
            reply_markup=kb,
        )
        await callback.answer()
    else:
        await target.answer(text, reply_markup=kb)


@router.message(RecordStates.get_comment, F.text)
async def record_comment(message: types.Message, state: FSMContext):
    await state.update_data(comment=message.text)
    await _show_confirm(message, state)


@router.callback_query(RecordStates.get_comment, F.data == "rback_comment")
async def record_back_comment(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(RecordStates.get_contact)
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text="Оставь контакт для связи с менеджером.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Пропустить", callback_data="rskip_contact")],
                _back_btn("rback_contact"),
            ]
        ),
    )
    await callback.answer()


@router.callback_query(RecordStates.get_comment, F.data == "rskip_comment")
async def record_skip_comment(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(comment="")
    await _show_confirm(callback.message, state, callback)


async def _show_confirm(msg_target, state: FSMContext, callback=None):
    data = await state.get_data()
    text = (
        f"✅ Проверь заявку:\n\n"
        f"Игра: {data['game_name']}\n"
        f"Участников: {data['participants_count']}\n"
        f"Контакт: {data.get('phone') or '—'}\n"
        f"Комментарий: {data.get('comment') or '—'}\n\n"
        f"Подтвердить?"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="rconfirm_yes"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="rconfirm_no"),
            ],
            _back_btn("rback_confirm"),
        ]
    )
    if callback:
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=text,
            reply_markup=kb,
        )
        await callback.answer()
    else:
        await msg_target.answer(text, reply_markup=kb)
    await state.set_state(RecordStates.confirm)


@router.callback_query(RecordStates.confirm, F.data == "rback_confirm")
async def record_back_confirm(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(RecordStates.get_comment)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="rskip_comment")],
            _back_btn("rback_comment"),
        ]
    )
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text="Комментарий (необязательно):",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(RecordStates.confirm, F.data == "rconfirm_yes")
async def record_confirm_yes(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = callback.from_user
    utm = get_user_utm(user.id)
    lead_id = add_lead(
        tg_id=user.id,
        username=user.username,
        name=user.full_name or "",
        phone=data.get("phone"),
        game_id=data.get("game_id"),
        game_name=data.get("game_name"),
        participants_count=data.get("participants_count", 1),
        comment=data.get("comment"),
        utm_source=data.get("utm_source") or utm.get("utm_source"),
        utm_medium=data.get("utm_medium") or utm.get("utm_medium"),
        utm_campaign=data.get("utm_campaign") or utm.get("utm_campaign"),
    )
    await state.clear()
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text="🎉 Заявка отправлена! Менеджер свяжется с тобой в ближайшее время.",
    )
    # Уведомление в канал операторов
    bot = callback.bot
    lines = [
        "📩 Новая заявка",
        f"Игра: {data['game_name']}",
        f"Участников: {data['participants_count']}",
    ]
    if data.get("phone"):
        lines.append(f"Контакт: {data['phone']}")
    if data.get("comment"):
        lines.append(f"Комментарий: {data['comment']}")
    name_part = user.full_name or ""
    if user.username:
        name_part = f"{name_part} @{user.username}".strip() if name_part else f"@{user.username}"
    if name_part:
        lines.append(name_part)
    notify = "\n".join(lines)
    try:
        await bot.send_message(OPERATOR_CHAT_ID, notify)
    except Exception:
        pass


@router.callback_query(RecordStates.confirm, F.data == "rconfirm_no")
async def record_confirm_no(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text="Заявка отменена.",
    )
    await callback.answer()
