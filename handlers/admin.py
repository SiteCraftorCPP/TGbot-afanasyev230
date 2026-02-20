import asyncio
import csv
import io
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BufferedInputFile,
)

from config import ADMIN_IDS
from utils import escape_md
from database import (
    get_all_games,
    get_leads,
    get_subscriptions,
    get_holiday_orders,
    get_users_for_export,
    get_users_for_broadcast,
    add_game,
    update_game,
    get_game,
    toggle_game_visibility,
    delete_game,
    get_setting,
    set_setting,
    get_all_stories,
    get_story,
    add_story,
    update_story,
    toggle_story_visibility,
    delete_story,
    get_visible_games,
    add_scenario,
    get_scenarios,
    get_scenario,
    update_scenario,
    delete_scenario,
    get_stories_by_scenario,
    get_format_screens,
    update_format_screen,
    swap_story_order,
    get_format_info,
    update_format_info,
)

router = Router()


class AdminGameStates(StatesGroup):
    menu = State()
    add_name = State()
    add_date = State()
    add_time = State()
    add_place = State()
    add_price = State()
    add_desc = State()
    add_limit = State()
    edit_game = State()
    edit_field = State()


class AdminStoryStates(StatesGroup):
    add_content = State()
    add_image = State()
    edit_story = State()
    edit_field = State()
    choose_scenario = State()  # Выбор сценария при добавлении сюжета


class AdminScenarioStates(StatesGroup):
    add_name = State()
    add_desc = State()
    edit_name = State()
    edit_desc = State()


class AdminFormatStates(StatesGroup):
    edit_text = State()
    edit_image = State()


class AdminBroadcastStates(StatesGroup):
    get_text = State()
    get_media = State()
    confirm = State()



def _admin_only(func):
    async def wrapper(event, *args, **kwargs):
        uid = event.from_user.id if hasattr(event, "from_user") else event.message.from_user.id
        if uid not in ADMIN_IDS:
            return
        return await func(event, *args, **kwargs)
    return wrapper


@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(f"Нет доступа. Ваш ID: {message.from_user.id}")
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Игры", callback_data="admin_games")],
            [InlineKeyboardButton(text="📆 Расписание", callback_data="admin_schedule")],
            [InlineKeyboardButton(text="📂 Сценарии", callback_data="admin_scenarios")],
            [InlineKeyboardButton(text="📝 Формат", callback_data="admin_format")],
            [InlineKeyboardButton(text="📈 Лиды", callback_data="admin_leads")],
            [InlineKeyboardButton(text="🔄 Follow-up", callback_data="admin_followup")],
        ]
    )
    await message.answer("Админ-панель:", reply_markup=kb)


def _games_list_kb():
    games = get_all_games()
    text = "**Игры:**\n\n"
    kb = []
    for g in games:
        gid, name, date, time, place, price, desc, limit, hidden = g
        status = "❌" if hidden else "✅"
        text += f"{status} {escape_md(name)} — {escape_md(date)}\n"
        kb.append([
            InlineKeyboardButton(text=f"{'✅ Показать' if hidden else '❌ Скрыть'}", callback_data=f"adm_toggle_{gid}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"adm_delete_{gid}"),
        ])
    kb.append([InlineKeyboardButton(text="➕ Добавить игру", callback_data="admin_add_game")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    return text, InlineKeyboardMarkup(inline_keyboard=kb)


def _schedule_edit_kb(games):
    """Расписание с кнопками редактирования."""
    text = "**📆 Расписание (редактирование):**\n\n"
    kb = []
    for g in games:
        gid, name, date, time, place, price, desc, limit, hidden = g
        status = "❌" if hidden else "✅"
        text += f"{status} {escape_md(name)} — {escape_md(date)}" + (f" {escape_md(time)}" if time else "") + "\n"
        kb.append([
            InlineKeyboardButton(text="✏️", callback_data=f"adm_edit_{gid}"),
            InlineKeyboardButton(text=f"{'✅' if hidden else '❌'}", callback_data=f"adm_toggle_s_{gid}"),
            InlineKeyboardButton(text="🗑", callback_data=f"adm_delete_s_{gid}"),
        ])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    return text, InlineKeyboardMarkup(inline_keyboard=kb)


async def _refresh_games_list(message: types.Message):
    text, kb = _games_list_kb()
    await message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "admin_games")
async def admin_games_list(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    text, kb = _games_list_kb()
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "admin_schedule")
async def admin_schedule_list(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await state.clear()
    games = get_all_games()
    text, kb = _schedule_edit_kb(games)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


def _game_edit_kb(gid: int, g):
    """Клавиатура редактирования игры."""
    _, name, date, time, place, price, desc, limit, hidden = g[:9]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Название: {name[:20]}...", callback_data=f"adm_ef_{gid}_name")],
        [InlineKeyboardButton(text=f"Дата: {date}", callback_data=f"adm_ef_{gid}_game_date")],
        [InlineKeyboardButton(text=f"Время: {time or '—'}", callback_data=f"adm_ef_{gid}_game_time")],
        [InlineKeyboardButton(text=f"Место: {(place or '—')[:20]}", callback_data=f"adm_ef_{gid}_place")],
        [InlineKeyboardButton(text=f"Цена: {price or '—'}", callback_data=f"adm_ef_{gid}_price")],
        [InlineKeyboardButton(text=f"Описание: {(desc or '—')[:20]}...", callback_data=f"adm_ef_{gid}_description")],
        [InlineKeyboardButton(text=f"Лимит: {limit}", callback_data=f"adm_ef_{gid}_limit_places")],
        [InlineKeyboardButton(text="🔙 К списку", callback_data="admin_schedule")],
    ])


@router.callback_query(F.data.startswith("adm_edit_"))
async def admin_edit_game(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    gid = int(callback.data.split("_")[2])
    row = get_game(gid)
    if not row:
        await callback.answer("Игра не найдена", show_alert=True)
        return
    g = row
    _, name, date, time, place, price, desc, limit, hidden = g[:9]
    text = f"✏️ Редактировать: {name}\n\n{date} {time or ''}\n📍 {place or '—'}\n💰 {price or '—'}\n\n{desc or '—'}\nЛимит: {limit}"
    await callback.message.edit_text(text, reply_markup=_game_edit_kb(gid, g))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_ef_"))
async def admin_edit_field_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    parts = callback.data.split("_")
    gid = int(parts[2])
    field = "_".join(parts[3:]) if len(parts) > 3 else ""
    prompts = {
        "name": "Новое название:",
        "game_date": "Новая дата (например 20.02.2026):",
        "game_time": "Новое время (например 19:00) или «пропустить»:",
        "place": "Новое место или «пропустить»:",
        "price": "Новая цена или «пропустить»:",
        "description": "Новое описание или «пропустить»:",
        "limit_places": "Новый лимит мест (число):",
    }
    await state.set_state(AdminGameStates.edit_field)
    await state.update_data(edit_gid=gid, edit_field=field)
    skip_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="💫 Пропустить", callback_data="adm_ef_skip")]]
    ) if field in ("game_time", "place", "price", "description") else None
    await callback.message.edit_text(prompts.get(field, "Введи значение:"), reply_markup=skip_kb)
    await callback.answer()


@router.callback_query(AdminGameStates.edit_field, F.data == "adm_ef_skip")
async def admin_edit_field_skip(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    data = await state.get_data()
    gid, field = data["edit_gid"], data["edit_field"]
    val = "" if field != "limit_places" else 0
    update_game(gid, **{field: val})
    await state.clear()
    row = get_game(gid)
    g = row
    _, name, date, time, place, price, desc, limit, hidden = g[:9]
    text = f"**✏️ Редактировать:** {escape_md(name)}\n\n{escape_md(date)} {escape_md(time or '')}\n📍 {escape_md(place or '—')}\n💰 {escape_md(price or '—')}\n\n{escape_md(desc or '—')}\nЛимит: {limit}"
    await callback.message.edit_text(text, reply_markup=_game_edit_kb(gid, g), parse_mode="Markdown")
    await callback.answer("Сохранено")


@router.message(AdminGameStates.edit_field, F.text)
async def admin_edit_field_value(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    gid, field = data["edit_gid"], data["edit_field"]
    val = message.text.strip()
    if field == "limit_places":
        try:
            val = int(val or "0")
        except ValueError:
            val = 0
    elif field == "game_time" and val.lower() in ("пропустить", "-", ""):
        val = ""
    elif field in ("place", "price", "description") and val.lower() in ("пропустить", "-", ""):
        val = ""
    update_game(gid, **{field: val})
    await state.clear()
    row = get_game(gid)
    g = row
    _, name, date, time, place, price, desc, limit, hidden = g[:9]
    text = f"**✏️ Редактировать:** {escape_md(name)}\n\n{escape_md(date)} {escape_md(time or '')}\n📍 {escape_md(place or '—')}\n💰 {escape_md(price or '—')}\n\n{escape_md(desc or '—')}\nЛимит: {limit}"
    await message.answer(text, reply_markup=_game_edit_kb(gid, g), parse_mode="Markdown")


async def _refresh_schedule_list(message: types.Message):
    games = get_all_games()
    text, kb = _schedule_edit_kb(games)
    await message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("adm_delete_s_"))
async def admin_delete_game_schedule(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    gid = int(callback.data.split("_")[3])
    delete_game(gid)
    await callback.answer("Игра удалена")
    await _refresh_schedule_list(callback.message)


@router.callback_query(F.data.startswith("adm_toggle_s_"))
async def admin_toggle_game_schedule(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    gid = int(callback.data.split("_")[3])
    h = toggle_game_visibility(gid)
    status = "скрыта" if h else "показана"
    await callback.answer(f"Игра {status}")
    await _refresh_schedule_list(callback.message)


@router.callback_query(F.data.startswith("adm_delete_"))
async def admin_delete_game(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    gid = int(callback.data.split("_")[2])
    delete_game(gid)
    await callback.answer("Игра удалена")
    await _refresh_games_list(callback.message)


@router.callback_query(F.data.startswith("adm_toggle_"))
async def admin_toggle_game(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    gid = int(callback.data.split("_")[2])
    h = toggle_game_visibility(gid)
    status = "скрыта" if h else "показана"
    await callback.answer(f"Игра {status}")
    await _refresh_games_list(callback.message)


@router.callback_query(F.data == "admin_add_game")
async def admin_add_game_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await state.set_state(AdminGameStates.add_name)
    await callback.message.answer("Название игры:")
    await callback.answer()


@router.message(AdminGameStates.add_name, F.text)
async def admin_add_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminGameStates.add_date)
    await message.answer("Дата (например: 20.02.2026):")


@router.message(AdminGameStates.add_date, F.text)
async def admin_add_date(message: types.Message, state: FSMContext):
    await state.update_data(game_date=message.text.strip())
    await state.set_state(AdminGameStates.add_time)
    await message.answer("Время (например: 19:00) или «пропустить»:")


@router.message(AdminGameStates.add_time, F.text)
async def admin_add_time(message: types.Message, state: FSMContext):
    t = message.text.strip().lower()
    await state.update_data(game_time="" if t in ("пропустить", "-", "") else t)
    await state.set_state(AdminGameStates.add_place)
    await message.answer(
        "Место или «пропустить»:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💫 Пропустить", callback_data="admin_skip_place")]]
        ),
    )


@router.message(AdminGameStates.add_place, F.text)
async def admin_add_place(message: types.Message, state: FSMContext):
    t = message.text.strip().lower()
    await state.update_data(place="" if t in ("пропустить", "-", "") else message.text.strip())
    await state.set_state(AdminGameStates.add_price)
    await message.answer(
        "Цена или «пропустить»:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💫 Пропустить", callback_data="admin_skip_price")]]
        ),
    )


@router.callback_query(AdminGameStates.add_place, F.data == "admin_skip_place")
async def admin_skip_place(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await state.update_data(place="")
    await state.set_state(AdminGameStates.add_price)
    await callback.message.edit_text(
        "Цена или «пропустить»:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💫 Пропустить", callback_data="admin_skip_price")]]
        ),
    )
    await callback.answer()


@router.message(AdminGameStates.add_price, F.text)
async def admin_add_price(message: types.Message, state: FSMContext):
    t = message.text.strip().lower()
    await state.update_data(price="" if t in ("пропустить", "-", "") else message.text.strip())
    await state.set_state(AdminGameStates.add_desc)
    await message.answer(
        "Короткое описание или «пропустить»:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💫 Пропустить", callback_data="admin_skip_desc")]]
        ),
    )


@router.callback_query(AdminGameStates.add_price, F.data == "admin_skip_price")
async def admin_skip_price(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await state.update_data(price="")
    await state.set_state(AdminGameStates.add_desc)
    await callback.message.edit_text(
        "Короткое описание или «пропустить»:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💫 Пропустить", callback_data="admin_skip_desc")]]
        ),
    )
    await callback.answer()


@router.message(AdminGameStates.add_desc, F.text)
async def admin_add_desc(message: types.Message, state: FSMContext):
    t = message.text.strip().lower()
    await state.update_data(description="" if t in ("пропустить", "-", "") else message.text.strip())
    await state.set_state(AdminGameStates.add_limit)
    await message.answer(
        "Лимит мест (число) или 0:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💫 Пропустить (0)", callback_data="admin_skip_limit")]]
        ),
    )


@router.callback_query(AdminGameStates.add_desc, F.data == "admin_skip_desc")
async def admin_skip_desc(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await state.update_data(description="")
    await state.set_state(AdminGameStates.add_limit)
    await callback.message.edit_text(
        "Лимит мест (число) или 0:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💫 Пропустить (0)", callback_data="admin_skip_limit")]]
        ),
    )
    await callback.answer()


@router.callback_query(AdminGameStates.add_limit, F.data == "admin_skip_limit")
async def admin_skip_limit(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    data = await state.get_data()
    add_game(
        name=data["name"],
        game_date=data["game_date"],
        game_time=data.get("game_time"),
        place=data.get("place"),
        price=data.get("price"),
        description=data.get("description"),
        limit_places=0,
    )
    await state.clear()
    await callback.message.edit_text("✓ Игра добавлена.", reply_markup=None)
    await callback.answer()


@router.message(AdminGameStates.add_limit, F.text)
async def admin_add_limit(message: types.Message, state: FSMContext):
    try:
        limit = int(message.text.strip() or "0")
    except ValueError:
        limit = 0
    data = await state.get_data()
    add_game(
        name=data["name"],
        game_date=data["game_date"],
        game_time=data.get("game_time"),
        place=data.get("place"),
        price=data.get("price"),
        description=data.get("description"),
        limit_places=limit,
    )
    await state.clear()
    await message.answer("✓ Игра добавлена.")


@router.callback_query(F.data == "admin_leads")
async def admin_leads_list(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    leads = get_leads(50)
    if not leads:
        text = "Лидов пока нет."
    else:
        lines = []
        for l in leads:
            lid, tg_id, uname, name, phone, gname, cnt, comment, status, created = l
            date_str = created[:10] if created else "—"
            lines.append(f"#{lid} {escape_md(name or '—')} | {escape_md(gname)} | {cnt} чел. | {date_str}")
        text = "**Лиды (последние 50):**\n_Лид = юзер прошёл запись и нажал «Подтвердить»_\n\n" + "\n".join(lines[:20])
        if len(lines) > 20:
            text += f"\n\n... и ещё {len(lines) - 20}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]]
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


def _followup_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Выгрузить пользователей (CSV)", callback_data="admin_export_users")],
            [InlineKeyboardButton(text="📤 Рассылка", callback_data="admin_broadcast_start")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
        ]
    )


async def _show_followup_screen(callback: types.CallbackQuery):
    """Показать экран Follow-up (без answer — вызывающий должен ответить на callback)."""
    users_count = len(get_users_for_broadcast("all"))
    text = (
        f"🔄 **Follow-up**\n\n"
        f"Пользователей в базе: **{users_count}**\n\n"
        f"• **Выгрузить** — таблица со всеми, кто хоть раз нажал кнопку в боте (tg_id, имя, активность, телефон).\n"
        f"• **Рассылка** — отправить сообщение с текстом и/или медиа всем или по фильтру."
    )
    await callback.message.edit_text(text, reply_markup=_followup_kb(), parse_mode="Markdown")


@router.callback_query(F.data == "admin_followup")
async def admin_followup(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass
    if callback.from_user.id not in ADMIN_IDS:
        return
    try:
        await _show_followup_screen(callback)
    except Exception as e:
        try:
            await callback.message.answer(f"Ошибка Follow-up: {str(e)[:200]}")
        except Exception:
            pass


@router.callback_query(F.data == "admin_export_users")
async def admin_export_users(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    rows = get_users_for_export()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["tg_id", "username", "first_name", "last_name", "first_seen", "last_seen", "event_count", "events_sample", "phone"])
    for r in rows:
        w.writerow(list(r))
    buf.seek(0)
    file = BufferedInputFile(buf.getvalue().encode("utf-8-sig"), filename="users.csv")
    await callback.bot.send_document(callback.message.chat.id, file, caption=f"Пользователи ({len(rows)} записей)")
    await callback.answer("Файл отправлен.")


# --- Рассылка ---

@router.callback_query(F.data == "admin_broadcast_start")
async def admin_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await state.set_state(AdminBroadcastStates.get_text)
    await state.update_data(media_file_id=None)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_broadcast_cancel")]])
    await callback.message.edit_text(
        "📤 **Рассылка**\n\nВведите текст сообщения (можно Markdown). Или отправьте «-» чтобы только медиа:",
        reply_markup=kb,
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast_cancel")
async def admin_broadcast_cancel(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await state.clear()
    await admin_followup(callback)


@router.message(AdminBroadcastStates.get_text, F.text)
async def admin_broadcast_text(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    text = "" if (message.text or "").strip() == "-" else (message.text or "").strip()
    await state.update_data(broadcast_text=text)
    await state.set_state(AdminBroadcastStates.get_media)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить медиа", callback_data="admin_broadcast_skip_media")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_broadcast_cancel")],
    ])
    await message.answer("Отправьте фото или файл для прикрепления. Или нажмите «Пропустить»:", reply_markup=kb)


@router.message(AdminBroadcastStates.get_text, F.photo)
async def admin_broadcast_text_photo(message: types.Message, state: FSMContext):
    """Фото с подписью — сразу текст и медиа."""
    if message.from_user.id not in ADMIN_IDS:
        return
    text = (message.caption or "").strip() if message.caption else ""
    await state.update_data(broadcast_text=text, media_file_id=message.photo[-1].file_id, media_type="photo")
    await state.set_state(AdminBroadcastStates.confirm)
    await _admin_broadcast_confirm(message, state)


@router.message(AdminBroadcastStates.get_media, F.photo)
async def admin_broadcast_media_photo(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    file_id = message.photo[-1].file_id
    await state.update_data(media_file_id=file_id, media_type="photo")
    await state.set_state(AdminBroadcastStates.confirm)
    await _admin_broadcast_confirm(message, state)


@router.message(AdminBroadcastStates.get_media, F.document)
async def admin_broadcast_media_doc(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    file_id = message.document.file_id
    await state.update_data(media_file_id=file_id, media_type="document")
    await state.set_state(AdminBroadcastStates.confirm)
    await _admin_broadcast_confirm(message, state)


@router.callback_query(AdminBroadcastStates.get_media, F.data == "admin_broadcast_skip_media")
async def admin_broadcast_skip_media(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await state.update_data(media_file_id=None, media_type=None)
    await state.set_state(AdminBroadcastStates.confirm)
    await _admin_broadcast_confirm(callback.message, state, callback)


async def _admin_broadcast_confirm(msg_target, state: FSMContext, callback=None):
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    media_id = data.get("media_file_id")
    media_type = data.get("media_type")
    filter_type = data.get("broadcast_filter", "all")
    user_ids = get_users_for_broadcast(filter_type)
    count = len(user_ids)

    if not text and not media_id:
        err = "Добавьте текст или медиа."
        if callback:
            await callback.message.edit_text(err)
            await callback.answer()
        else:
            await msg_target.answer(err)
        return

    preview_raw = (text[:100] + "...") if len(text) > 100 else (text or "(нет)")
    preview = f"Текст: {escape_md(preview_raw)}"
    if media_id:
        preview += f"\nМедиа: {media_type}"
    preview += f"\n\nПолучателей: **{count}**"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Всем", callback_data="admin_broadcast_filter_all"),
            InlineKeyboardButton(text="С заявкой", callback_data="admin_broadcast_filter_with_lead"),
            InlineKeyboardButton(text="Без заявки", callback_data="admin_broadcast_filter_without_lead"),
        ],
        [InlineKeyboardButton(text="✅ Отправить", callback_data="admin_broadcast_send")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_broadcast_cancel")],
    ])
    if callback:
        await callback.message.edit_text(f"📤 **Подтверждение рассылки**\n\n{preview}", reply_markup=kb, parse_mode="Markdown")
        await callback.answer()
    else:
        await msg_target.answer(f"📤 **Подтверждение рассылки**\n\n{preview}", reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("admin_broadcast_filter_"))
async def admin_broadcast_filter(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    # admin_broadcast_filter_all -> all, admin_broadcast_filter_with_lead -> with_lead, etc.
    f = callback.data.replace("admin_broadcast_filter_", "")
    await state.update_data(broadcast_filter=f)
    await _admin_broadcast_confirm(callback.message, state, callback)


@router.callback_query(F.data == "admin_broadcast_send")
async def admin_broadcast_send(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    media_id = data.get("media_file_id")
    media_type = data.get("media_type")
    if not text and not media_id:
        await callback.answer("Добавьте текст или медиа.", show_alert=True)
        return
    filter_type = data.get("broadcast_filter", "all")
    user_ids = get_users_for_broadcast(filter_type)
    await state.clear()

    await callback.message.edit_text(f"📤 Отправка {len(user_ids)} пользователям...")
    sent, failed = 0, 0
    safe_text = escape_md(text) if text else None
    for uid in user_ids:
        try:
            if media_id and media_type == "photo":
                await callback.bot.send_photo(uid, photo=media_id, caption=safe_text, parse_mode="Markdown" if safe_text else None)
            elif media_id and media_type == "document":
                await callback.bot.send_document(uid, document=media_id, caption=safe_text, parse_mode="Markdown" if safe_text else None)
            else:
                await callback.bot.send_message(uid, text=safe_text or "—", parse_mode="Markdown")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await callback.message.edit_text(f"✅ Рассылка завершена.\nОтправлено: {sent}, не доставлено: {failed}")
    await callback.answer()


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await state.clear()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Игры", callback_data="admin_games")],
            [InlineKeyboardButton(text="📆 Расписание", callback_data="admin_schedule")],
            [InlineKeyboardButton(text="📂 Сценарии", callback_data="admin_scenarios")],
            [InlineKeyboardButton(text="📝 Формат", callback_data="admin_format")],
            [InlineKeyboardButton(text="📈 Лиды", callback_data="admin_leads")],
            [InlineKeyboardButton(text="🔄 Follow-up", callback_data="admin_followup")],
        ]
    )
    await callback.message.edit_text("Админ-панель:", reply_markup=kb)
    await callback.answer()




# --- Scenarios Management ---

def _scenarios_list_kb():
    scenarios = get_scenarios()
    text = "**Сценарии:**\n\n"
    kb = []
    for s in scenarios:
        sid, name, desc = s
        text += f"🔹 {escape_md(name)}\n"
        kb.append([
            InlineKeyboardButton(text=f"✏️ {name}", callback_data=f"adm_scen_edit_{sid}"),
            InlineKeyboardButton(text="📖 Сюжеты", callback_data=f"adm_scen_stories_{sid}"),
        ])
        kb.append([InlineKeyboardButton(text="🗑 Удалить", callback_data=f"adm_scen_del_{sid}")])
    
    kb.append([InlineKeyboardButton(text="➕ Добавить сценарий", callback_data="admin_add_scenario")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    return text, InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(F.data == "admin_scenarios")
async def admin_scenarios_list(callback: types.CallbackQuery):
    text, kb = _scenarios_list_kb()
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "admin_add_scenario")
async def admin_add_scenario_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminScenarioStates.add_name)
    await callback.message.answer("Введите название нового сценария:")
    await callback.answer()


@router.message(AdminScenarioStates.add_name, F.text)
async def admin_add_scenario_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым. Введите название сценария:")
        return
    
    # Создаём сценарий сразу только с названием (без описания)
    add_scenario(name, "")
    await state.clear()
    await message.answer(f"✅ Сценарий «{name}» создан.")
    
    # Показываем список сценариев
    text, kb = _scenarios_list_kb()
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("adm_scen_del_"))
async def admin_delete_scenario(callback: types.CallbackQuery):
    sid = int(callback.data.split("_")[3])
    delete_scenario(sid)
    await callback.answer("Сценарий удалён")
    text, kb = _scenarios_list_kb()
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("adm_scen_edit_"))
async def admin_edit_scenario(callback: types.CallbackQuery, state: FSMContext):
    sid = int(callback.data.split("_")[3])
    scenario = get_scenario(sid)
    if not scenario:
        await callback.answer("Сценарий не найден", show_alert=True)
        return
    
    await state.update_data(sid=sid)
    await state.set_state(AdminScenarioStates.edit_name)
    await callback.message.answer(f"Редактирование сценария «{scenario[1]}».\nВведите новое название (или - чтобы оставить):")
    await callback.answer()


@router.message(AdminScenarioStates.edit_name, F.text)
async def admin_edit_scenario_name(message: types.Message, state: FSMContext):
    new_name = message.text.strip()
    data = await state.get_data()
    sid = data["sid"]
    scenario = get_scenario(sid)
    
    name = new_name if new_name != "-" else scenario[1]
    await state.update_data(name=name)
    
    await state.set_state(AdminScenarioStates.edit_desc)
    await message.answer(f"Введите новое описание (было: {scenario[2] or 'пусто'}) или - чтобы оставить:")


@router.message(AdminScenarioStates.edit_desc, F.text)
async def admin_edit_scenario_desc(message: types.Message, state: FSMContext):
    new_desc = message.text.strip()
    data = await state.get_data()
    sid = data["sid"]
    scenario = get_scenario(sid)
    
    desc = new_desc if new_desc != "-" else (scenario[2] or "")
    update_scenario(sid, data["name"], desc)
    await state.clear()
    await message.answer("✅ Сценарий обновлён.")
    
    text, kb = _scenarios_list_kb()
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


# --- Stories Management (per scenario) ---

def _scenario_stories_kb(scenario_id):
    scenario = get_scenario(scenario_id)
    if not scenario:
        return "Сценарий не найден", None
        
    stories = get_stories_by_scenario(scenario_id)
    text = f"**Сюжеты сценария «{escape_md(scenario[1])}»:**\n\n"
    kb = []
    
    if not stories:
        text += "Пока нет сюжетов.\n"
    else:
        for i, s in enumerate(stories):
            sid, title, content, image_url, game_id, order_num, hidden, scen_id = s
            status = "❌" if hidden else "✅"
            preview = (title[:20] + "...") if len(title) > 20 else title
            text += f"{status} {escape_md(preview)}\n"
            
            # Ряд управления: Ред, Вверх, Вниз (обе кнопки всегда показываем)
            control_row = [
                InlineKeyboardButton(text="✏️", callback_data=f"adm_story_edit_{sid}_{scenario_id}"),
                InlineKeyboardButton(text="⬆️", callback_data=f"adm_story_move_{sid}_{scenario_id}_up"),
                InlineKeyboardButton(text="⬇️", callback_data=f"adm_story_move_{sid}_{scenario_id}_down"),
            ]
            kb.append(control_row)
            
            # Ряд статуса и удаления
            kb.append([
                InlineKeyboardButton(text=f"{'✅ Показать' if hidden else '❌ Скрыть'}", callback_data=f"adm_story_toggle_{sid}_{scenario_id}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"adm_story_delete_{sid}_{scenario_id}"),
            ])
            
    kb.append([InlineKeyboardButton(text="➕ Добавить сюжет", callback_data=f"adm_add_story_{scenario_id}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад к сценариям", callback_data="admin_scenarios")])
    return text, InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(F.data.startswith("adm_scen_stories_"))
async def admin_scenario_stories(callback: types.CallbackQuery):
    sid = int(callback.data.split("_")[3])
    text, kb = _scenario_stories_kb(sid)
    if not kb:
        await callback.answer(text)
        return
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("adm_story_toggle_"))
async def admin_toggle_story(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    sid = int(parts[3])
    scenario_id = int(parts[4])
    
    h = toggle_story_visibility(sid)
    status = "скрыт" if h else "показан"
    await callback.answer(f"Сюжет {status}")
    
    text, kb = _scenario_stories_kb(scenario_id)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("adm_story_move_"))
async def admin_move_story(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    sid = int(parts[3])
    scenario_id = int(parts[4])
    direction = parts[5] # up/down
    
    swap_story_order(sid, direction)
    await callback.answer()
    
    text, kb = _scenario_stories_kb(scenario_id)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("adm_story_delete_"))
async def admin_delete_story(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    sid = int(parts[3])
    scenario_id = int(parts[4])
    
    delete_story(sid)
    await callback.answer("Сюжет удалён")
    
    text, kb = _scenario_stories_kb(scenario_id)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("adm_story_edit_"))
async def admin_edit_story_start(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    sid = int(parts[3])
    scenario_id = int(parts[4])
    
    story = get_story(sid)
    if not story:
        await callback.answer("Сюжет не найден")
        return

    await state.update_data(sid=sid, scenario_id=scenario_id)
    
    text = f"Редактирование сюжета (ID: {sid}):\n\n{story[2][:100]}..."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="adm_st_ed_text")],
        [InlineKeyboardButton(text="🖼 Изменить фото", callback_data="adm_st_ed_img")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"adm_scen_stories_{scenario_id}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "adm_st_ed_text")
async def admin_edit_story_text_ask(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStoryStates.edit_story)
    await callback.message.answer("Введите новый текст сюжета:")
    await callback.answer()


@router.message(AdminStoryStates.edit_story, F.text)
async def admin_edit_story_text_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    sid = data["sid"]
    scenario_id = data["scenario_id"]
    new_text = message.text.strip()
    
    update_story(sid, title=new_text, content=new_text)
    
    await state.clear()
    await message.answer("✅ Текст обновлён.")
    
    text, kb = _scenario_stories_kb(scenario_id)
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "adm_st_ed_img")
async def admin_edit_story_img_ask(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStoryStates.edit_field)
    await callback.message.answer("Отправьте новое фото (или URL, или «-» чтобы удалить фото):")
    await callback.answer()


@router.message(AdminStoryStates.edit_field, F.photo)
async def admin_edit_story_img_save_photo(message: types.Message, state: FSMContext):
    file_id = _get_photo_file_id(message)
    if not file_id:
        await message.answer("Ошибка фото.")
        return
    await _save_story_img(message, state, file_id)


@router.message(AdminStoryStates.edit_field, F.text)
async def admin_edit_story_img_save_text(message: types.Message, state: FSMContext):
    url = message.text.strip()
    if url == "-": url = ""
    await _save_story_img(message, state, url)


async def _save_story_img(message: types.Message, state: FSMContext, image_url: str):
    data = await state.get_data()
    sid = data["sid"]
    scenario_id = data["scenario_id"]
    
    update_story(sid, image_url=image_url)
    
    await state.clear()
    await message.answer("✅ Изображение обновлено.")
    
    text, kb = _scenario_stories_kb(scenario_id)
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("adm_add_story_"))
async def admin_add_story_start(callback: types.CallbackQuery, state: FSMContext):
    scenario_id = int(callback.data.split("_")[3])
    await state.update_data(scenario_id=scenario_id)
    
    await state.set_state(AdminStoryStates.add_content)
    await callback.message.answer("📝 Введите текст сюжета:")
    await callback.answer()


@router.message(AdminStoryStates.add_content, F.text)
async def admin_add_story_content(message: types.Message, state: FSMContext):
    await state.update_data(content=message.text.strip())
    await state.set_state(AdminStoryStates.add_image)
    await message.answer(
        "🖼️ Отправь фото или URL изображения (или нажми «пропустить»):",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💫 Пропустить", callback_data="admin_story_skip_image")]]
        ),
    )


@router.callback_query(AdminStoryStates.add_image, F.data == "admin_story_skip_image")
async def admin_story_skip_image(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(image_url="")
    await _finish_add_story(callback.message, state)
    await callback.answer()


def _get_photo_file_id(message: types.Message) -> str | None:
    """Строка file_id фото: из message.photo или из message.document (если изображение)."""
    if message.photo:
        return message.photo[-1].file_id
    if message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        return message.document.file_id
    return None


@router.message(AdminStoryStates.add_image, F.photo)
async def admin_add_story_image_photo(message: types.Message, state: FSMContext):
    file_id = _get_photo_file_id(message)
    if not file_id:
        await message.answer("Не удалось получить фото. Попробуй ещё раз.")
        return
    await state.update_data(image_url=file_id)
    await _finish_add_story(message, state)


@router.message(AdminStoryStates.add_image, F.document)
async def admin_add_story_image_document(message: types.Message, state: FSMContext):
    file_id = _get_photo_file_id(message)
    if not file_id:
        await message.answer("Файл не является изображением. Попробуй ещё раз.")
        return
    await state.update_data(image_url=file_id)
    await _finish_add_story(message, state)


@router.message(AdminStoryStates.add_image, F.text)
async def admin_add_story_image_text(message: types.Message, state: FSMContext):
    url = message.text.strip()
    if url == "-": url = ""
    await state.update_data(image_url=url)
    await _finish_add_story(message, state)


async def _finish_add_story(message: types.Message, state: FSMContext):
    data = await state.get_data()
    content = data["content"]
    image_url = data.get("image_url", "")
    scenario_id = data.get("scenario_id")
    
    # Считаем order_num: сколько уже есть сюжетов
    existing = get_stories_by_scenario(scenario_id)
    order_num = len(existing)
    
    add_story(
        title=content, # Используем контент как заголовок для простоты
        content=content,
        image_url=image_url,
        game_id=None,
        order_num=order_num,
        scenario_id=scenario_id
    )
    
    await state.clear()
    await message.answer("✅ Сюжет добавлен.")
    
    # Возвращаем меню сюжетов сценария
    text, kb = _scenario_stories_kb(scenario_id)
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


# --- Format Management (один экран "Что это за формат?") ---

@router.callback_query(F.data == "admin_format")
async def admin_format_edit(callback: types.CallbackQuery):
    text_db, image_url = get_format_info()
    
    text = "**Редактирование «Что это за формат?»**\n\n"
    if text_db:
        preview = (text_db[:100] + "...") if len(text_db) > 100 else text_db
        text += f"Текущий текст:\n{escape_md(preview)}\n\n"
    if image_url:
        text += "✅ Картинка прикреплена\n\n"
    else:
        text += "❌ Картинка не прикреплена\n\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать текст", callback_data="adm_fmt_edit_text")],
        [InlineKeyboardButton(text="🖼 Изменить картинку", callback_data="adm_fmt_edit_img")],
        [InlineKeyboardButton(text="👁 Предпросмотр", callback_data="adm_fmt_preview")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "adm_fmt_edit_text")
async def admin_format_edit_text_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminFormatStates.edit_text)
    text_db, _ = get_format_info()
    current = text_db or "Сюжетная игра (ролевой квест) — это как фильм, только ты внутри истории.\n\nТебе дают роль и цель, дальше события разворачиваются через общение и решения. Ведущий всё ведёт и помогает."
    await callback.message.answer(
        f"Редактирование текста «Что это за формат?».\n\n"
        f"Текущий текст:\n{current}\n\n"
        f"Введите новый текст (поддерживается Markdown, переносы строк):"
    )
    await callback.answer()


@router.message(AdminFormatStates.edit_text, F.text)
async def admin_format_edit_text_save(message: types.Message, state: FSMContext):
    new_text = message.text.strip()
    _, current_img = get_format_info()  # Сохраняем текущую картинку
    update_format_info(new_text, current_img or "")
    await state.clear()
    await message.answer("✅ Текст обновлён.")
    
    # Возвращаем меню редактирования
    text_db, image_url = get_format_info()
    text = "**Редактирование «Что это за формат?»**\n\n"
    if text_db:
        preview = (text_db[:100] + "...") if len(text_db) > 100 else text_db
        text += f"Текущий текст:\n{escape_md(preview)}\n\n"
    if image_url:
        text += "✅ Картинка прикреплена\n\n"
    else:
        text += "❌ Картинка не прикреплена\n\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать текст", callback_data="adm_fmt_edit_text")],
        [InlineKeyboardButton(text="🖼 Изменить картинку", callback_data="adm_fmt_edit_img")],
        [InlineKeyboardButton(text="👁 Предпросмотр", callback_data="adm_fmt_preview")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "adm_fmt_edit_img")
async def admin_format_edit_img_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminFormatStates.edit_image)
    await callback.message.answer(
        "Отправьте картинку (фото) для раздела «Что это за формат?»\n"
        "Или отправьте «-» чтобы удалить текущую картинку:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💫 Удалить картинку", callback_data="adm_fmt_img_delete")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data == "adm_fmt_img_delete")
async def admin_format_delete_img(callback: types.CallbackQuery, state: FSMContext):
    update_format_info(image_url="")  # Обновляем только image_url, text оставляем
    await state.clear()
    await callback.message.answer("✅ Картинка удалена.")
    await callback.answer()
    
    # Возвращаем меню
    text_db, image_url = get_format_info()
    text = "**Редактирование «Что это за формат?»**\n\n"
    if text_db:
        preview = (text_db[:100] + "...") if len(text_db) > 100 else text_db
        text += f"Текущий текст:\n{escape_md(preview)}\n\n"
    text += "❌ Картинка не прикреплена\n\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать текст", callback_data="adm_fmt_edit_text")],
        [InlineKeyboardButton(text="🖼 Изменить картинку", callback_data="adm_fmt_edit_img")],
        [InlineKeyboardButton(text="👁 Предпросмотр", callback_data="adm_fmt_preview")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
    ])
    await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.message(AdminFormatStates.edit_image, F.photo)
async def admin_format_edit_img_photo(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await _admin_format_save_img(message, state, file_id)


@router.message(AdminFormatStates.edit_image, F.document)
async def admin_format_edit_img_document(message: types.Message, state: FSMContext):
    file_id = _get_photo_file_id(message)
    if not file_id:
        await message.answer("Файл не является изображением. Отправь фото или изображение.")
        return
    await _admin_format_save_img(message, state, file_id)


async def _admin_format_save_img(message: types.Message, state: FSMContext, file_id: str):
    update_format_info(image_url=file_id)
    await state.clear()
    await message.answer("✅ Картинка обновлена.")
    
    # Возвращаем меню
    text_db, image_url = get_format_info()
    text = "**Редактирование «Что это за формат?»**\n\n"
    if text_db:
        preview = (text_db[:100] + "...") if len(text_db) > 100 else text_db
        text += f"Текущий текст:\n{escape_md(preview)}\n\n"
    text += "✅ Картинка прикреплена\n\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать текст", callback_data="adm_fmt_edit_text")],
        [InlineKeyboardButton(text="🖼 Изменить картинку", callback_data="adm_fmt_edit_img")],
        [InlineKeyboardButton(text="👁 Предпросмотр", callback_data="adm_fmt_preview")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.message(AdminFormatStates.edit_image, F.text)
async def admin_format_edit_img_text(message: types.Message, state: FSMContext):
    if message.text.strip() == "-":
        update_format_info(image_url="")
        await state.clear()
        await message.answer("✅ Картинка удалена.")
    else:
        await message.answer("Отправьте фото или нажмите «Удалить картинку».")
        return
    
    # Возвращаем меню
    text_db, image_url = get_format_info()
    text = "**Редактирование «Что это за формат?»**\n\n"
    if text_db:
        preview = (text_db[:100] + "...") if len(text_db) > 100 else text_db
        text += f"Текущий текст:\n{escape_md(preview)}\n\n"
    text += "❌ Картинка не прикреплена\n\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать текст", callback_data="adm_fmt_edit_text")],
        [InlineKeyboardButton(text="🖼 Изменить картинку", callback_data="adm_fmt_edit_img")],
        [InlineKeyboardButton(text="👁 Предпросмотр", callback_data="adm_fmt_preview")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "adm_fmt_preview")
async def admin_format_preview(callback: types.CallbackQuery):
    """Предпросмотр: как увидит пользователь."""
    from handlers.format_funnel import format_show_screen

    class TempTarget:
        def __init__(self, bot, chat_id):
            self.bot = bot
            self.chat_id = chat_id
        async def answer(self, text, **kwargs):
            return await self.bot.send_message(chat_id=self.chat_id, text=text, **kwargs)
        async def answer_photo(self, photo, caption, **kwargs):
            return await self.bot.send_photo(chat_id=self.chat_id, photo=photo, caption=caption, **kwargs)

    temp = TempTarget(callback.bot, callback.message.chat.id)
    await format_show_screen(temp)
    await callback.answer("👁 Предпросмотр отправлен.")


