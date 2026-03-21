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
    InputMediaPhoto,
)

from config import ADMIN_IDS, POST_CHANNEL_1, POST_CHANNEL_2, POST_CHAT_ID
from datetime import datetime
from zoneinfo import ZoneInfo
from utils import broadcast_text_to_html, normalize_telegram_button_url
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
    get_funnel_steps,
    add_funnel_step,
    update_funnel_step,
    delete_funnel_step,
    get_scheduled_posts,
    add_scheduled_post,
    cancel_scheduled_post,
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
    button_text = State()
    confirm = State()


class AdminFunnelStates(StatesGroup):
    add_delay = State()
    add_content = State()
    add_button_text = State()
    add_button_url = State()
    edit_delay = State()
    edit_content = State()
    edit_button_text = State()
    edit_button_url = State()


class AdminScheduledStates(StatesGroup):
    text = State()
    media = State()
    datetime = State()
    targets = State()
    button_text = State()
    button_url = State()



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
            [InlineKeyboardButton(text="📬 Автоворонка", callback_data="admin_funnel")],
            [InlineKeyboardButton(text="📅 Отложенные посты", callback_data="admin_scheduled")],
        ]
    )
    await message.answer("Админ-панель:", reply_markup=kb)


def _games_list_kb():
    games = get_all_games()
    text = "Игры:\n\n"
    kb = []
    for g in games:
        gid, name, date, time, place, price, desc, limit, hidden = g
        status = "❌" if hidden else "✅"
        text += f"{status} {name} — {date}\n"
        kb.append([
            InlineKeyboardButton(text=f"{'✅ Показать' if hidden else '❌ Скрыть'}", callback_data=f"adm_toggle_{gid}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"adm_delete_{gid}"),
        ])
    kb.append([InlineKeyboardButton(text="➕ Добавить игру", callback_data="admin_add_game")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    return text, InlineKeyboardMarkup(inline_keyboard=kb)


def _schedule_edit_kb(games):
    """Расписание с кнопками редактирования."""
    text = "📆 Расписание (редактирование):\n\n"
    kb = []
    for g in games:
        gid, name, date, time, place, price, desc, limit, hidden = g
        status = "❌" if hidden else "✅"
        text += f"{status} {name} — {date}" + (f" {time}" if time else "") + "\n"
        kb.append([
            InlineKeyboardButton(text="✏️", callback_data=f"adm_edit_{gid}"),
            InlineKeyboardButton(text=f"{'✅' if hidden else '❌'}", callback_data=f"adm_toggle_s_{gid}"),
            InlineKeyboardButton(text="🗑", callback_data=f"adm_delete_s_{gid}"),
        ])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    return text, InlineKeyboardMarkup(inline_keyboard=kb)


async def _refresh_games_list(message: types.Message):
    text, kb = _games_list_kb()
    await message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "admin_games")
async def admin_games_list(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    text, kb = _games_list_kb()
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "admin_schedule")
async def admin_schedule_list(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await state.clear()
    games = get_all_games()
    text, kb = _schedule_edit_kb(games)
    await callback.message.edit_text(text, reply_markup=kb)
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
    text = f"✏️ Редактировать: {name}\n\n{date} {time or ''}\n📍 {place or '—'}\n💰 {price or '—'}\n\n{desc or '—'}\nЛимит: {limit}"
    await callback.message.edit_text(text, reply_markup=_game_edit_kb(gid, g))
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
    text = f"✏️ Редактировать: {name}\n\n{date} {time or ''}\n📍 {place or '—'}\n💰 {price or '—'}\n\n{desc or '—'}\nЛимит: {limit}"
    await message.answer(text, reply_markup=_game_edit_kb(gid, g))


async def _refresh_schedule_list(message: types.Message):
    games = get_all_games()
    text, kb = _schedule_edit_kb(games)
    await message.edit_text(text, reply_markup=kb)


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
            lines.append(f"#{lid} {(name or '—')} | {gname} | {cnt} чел. | {date_str}")
        text = "Лиды (последние 50)\nЛид = юзер прошёл запись и нажал «Подтвердить»\n\n" + "\n".join(lines[:20])
        if len(lines) > 20:
            text += f"\n\n... и ещё {len(lines) - 20}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]]
    )
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


def _followup_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Выгрузить пользователей (CSV)", callback_data="admin_export_users")],
            [InlineKeyboardButton(text="📤 Рассылка", callback_data="admin_broadcast_start")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
        ]
    )


# --- Scheduled posts (отложенный постинг в каналы/чат) ---


def _scheduled_list_text_and_kb():
    rows = get_scheduled_posts(limit=50)
    msk = ZoneInfo("Europe/Moscow")
    if not rows:
        text = "📅 Отложенные посты\n\nПока нет запланированных постов."
    else:
        lines = ["📅 Отложенные посты:\n"]
        for idx, (pid, txt, media_type, media_file_id, to_ch1, to_ch2, to_chat, to_admins, run_at_utc, status, last_error, btn_text, btn_url) in enumerate(rows, start=1):
            try:
                dt_utc = datetime.fromisoformat(str(run_at_utc))
                if dt_utc.tzinfo is None:
                    dt_utc = dt_utc.replace(tzinfo=ZoneInfo("UTC"))
                dt_msk = dt_utc.astimezone(msk)
                ts = dt_msk.strftime("%d.%m.%Y %H:%M")
            except Exception:
                ts = str(run_at_utc)
            targets = []
            if to_ch1:
                targets.append("Канал СПБ")
            if to_ch2:
                targets.append("Канал ЕКБ")
            if to_chat:
                targets.append("Чат")
            if to_admins:
                targets.append("Пользователям бота")
            targets_str = ", ".join(targets) if targets else "—"
            preview = (txt or "").strip()
            if not preview and media_type:
                preview = f"[{media_type}]"
            if len(preview) > 60:
                preview = preview[:60] + "..."
            btn_info = ""
            if btn_text and btn_url:
                btn_info = f"\n🔗 Кнопка: {btn_text} → {btn_url}"
            lines.append(f"Пост #{idx}: {ts} → {targets_str}\n{preview}{btn_info}\n")
        text = "\n".join(lines)

    kb_rows = [
        [InlineKeyboardButton(text="➕ Новый пост", callback_data="admin_scheduled_new")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
    ]
    # Кнопки удаления для каждого поста (по фактическому номеру в списке)
    for idx, (pid, *_rest) in enumerate(rows, start=1):
        kb_rows.insert(
            0,
            [InlineKeyboardButton(text=f"🗑 Удалить #{idx}", callback_data=f"admin_scheduled_cancel_{pid}")],
        )

    return text, InlineKeyboardMarkup(inline_keyboard=kb_rows)


@router.callback_query(F.data == "admin_scheduled")
async def admin_scheduled_root(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    text, kb = _scheduled_list_text_and_kb()
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "admin_scheduled_new")
async def admin_scheduled_new(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await state.set_state(AdminScheduledStates.text)
    await state.update_data(
        sched_text="",
        sched_media_type=None,
        sched_media_file_id=None,
        sched_run_at_utc=None,
        sched_to_ch1=bool(POST_CHANNEL_1),
        sched_to_ch2=bool(POST_CHANNEL_2),
        sched_to_chat=bool(POST_CHAT_ID),
        sched_to_admins=True,
        sched_button_text=None,
        sched_button_url=None,
        sched_cta_buttons=None,
    )
    await callback.message.answer(
        "✏️ Текст отложенного поста.\n\n"
        "Отправьте текст сообщения или «-», если будет только медиа.",
    )
    await callback.answer()


@router.message(AdminScheduledStates.text, F.text)
async def admin_scheduled_text(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    raw = (message.text or "").strip()
    text = "" if raw == "-" else raw
    await state.update_data(sched_text=text)
    await state.set_state(AdminScheduledStates.media)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💫 Без медиа", callback_data="admin_scheduled_skip_media")],
        ]
    )
    await message.answer("📎 Отправьте фото/видео/файл для поста или нажмите «Без медиа».", reply_markup=kb)


@router.callback_query(AdminScheduledStates.media, F.data == "admin_scheduled_skip_media")
async def admin_scheduled_skip_media(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await state.update_data(sched_media_type=None, sched_media_file_id=None)
    await state.set_state(AdminScheduledStates.datetime)
    await callback.message.answer(
        "⏰ Время публикации по МСК.\n\n"
        "Формат: ДД.ММ.ГГГГ ЧЧ:ММ\n"
        "Например: 25.03.2026 19:30",
    )
    await callback.answer()


def _save_scheduled_media(message: types.Message, state: FSMContext, media_type: str, file_id: str):
    return state.update_data(sched_media_type=media_type, sched_media_file_id=file_id)


@router.message(AdminScheduledStates.media, F.photo)
async def admin_scheduled_media_photo(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    file_id = message.photo[-1].file_id
    await _save_scheduled_media(message, state, "photo", file_id)
    # Не создаём фиктивный CallbackQuery: `callback.answer()` требует mounted bot instance.
    await state.set_state(AdminScheduledStates.datetime)
    await message.answer(
        "⏰ Время публикации по МСК.\n\n"
        "Формат: ДД.ММ.ГГГГ ЧЧ:ММ\n"
        "Например: 25.03.2026 19:30",
    )


@router.message(AdminScheduledStates.media, F.video)
async def admin_scheduled_media_video(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    file_id = message.video.file_id
    await _save_scheduled_media(message, state, "video", file_id)
    # Не создаём фиктивный CallbackQuery: `callback.answer()` требует mounted bot instance.
    await state.set_state(AdminScheduledStates.datetime)
    await message.answer(
        "⏰ Время публикации по МСК.\n\n"
        "Формат: ДД.ММ.ГГГГ ЧЧ:ММ\n"
        "Например: 25.03.2026 19:30",
    )


@router.message(AdminScheduledStates.media, F.document)
async def admin_scheduled_media_document(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    file_id = message.document.file_id
    await _save_scheduled_media(message, state, "document", file_id)
    # Не создаём фиктивный CallbackQuery: `callback.answer()` требует mounted bot instance.
    await state.set_state(AdminScheduledStates.datetime)
    await message.answer(
        "⏰ Время публикации по МСК.\n\n"
        "Формат: ДД.ММ.ГГГГ ЧЧ:ММ\n"
        "Например: 25.03.2026 19:30",
    )


@router.message(AdminScheduledStates.datetime, F.text)
async def admin_scheduled_datetime(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    raw = (message.text or "").strip()
    try:
        dt_msk = datetime.strptime(raw, "%d.%m.%Y %H:%M").replace(tzinfo=ZoneInfo("Europe/Moscow"))
        dt_utc = dt_msk.astimezone(ZoneInfo("UTC"))
    except Exception:
        await message.answer("Не удалось разобрать дату/время. Формат: ДД.ММ.ГГГГ ЧЧ:ММ")
        return
    await state.update_data(sched_run_at_utc=dt_utc.isoformat(timespec="seconds"))
    # Сначала спрашиваем кнопку (как в автоворонке), потом выбираем цели
    await state.set_state(AdminScheduledStates.button_text)
    await message.answer(
        "🔗 Отправьте текст для кнопки под постом.\n\n"
        "Или отправьте «-», чтобы создать пост без кнопки.",
    )


def _build_scheduled_preview_kb_cta(data: dict) -> InlineKeyboardMarkup | None:
    """Та же логика кнопок, что в рассылке (Follow-up): sched_cta_buttons или текст+url."""
    buttons = data.get("sched_cta_buttons")
    if not buttons:
        t = (data.get("sched_button_text") or "").strip()
        u = (data.get("sched_button_url") or "").strip()
        if not t or not u:
            return None
        if not (u.startswith("http://") or u.startswith("https://")):
            u = normalize_telegram_button_url(u)
        buttons = [{"type": "url", "text": t[:64], "url": u}]
    row = []
    for b in buttons:
        if b.get("type") == "url":
            row.append(InlineKeyboardButton(text=b.get("text", "Ссылка"), url=b.get("url", "")))
        else:
            row.append(
                InlineKeyboardButton(
                    text=b.get("text", "Подробнее"),
                    callback_data=b.get("callback", "menu_record"),
                )
            )
    return InlineKeyboardMarkup(inline_keyboard=[row]) if row else None


async def _send_followup_style_preview(
    bot,
    chat_id: int,
    *,
    text: str,
    media_file_id: str | None,
    media_kind: str | None,
    kb_cta: InlineKeyboardMarkup | None,
) -> None:
    """Предпросмотр как в рассылке (admin_broadcast_preview): те же send_* и parse_mode."""
    html_caption = broadcast_text_to_html(text) if text else None
    parse_mode = "HTML" if html_caption else None
    try:
        if media_file_id and media_kind == "photo":
            await bot.send_photo(
                chat_id,
                media_file_id,
                caption=html_caption or None,
                parse_mode=parse_mode,
                reply_markup=kb_cta,
            )
        elif media_file_id and media_kind == "video":
            await bot.send_video(
                chat_id,
                media_file_id,
                caption=html_caption or None,
                parse_mode=parse_mode,
                reply_markup=kb_cta,
            )
        elif media_file_id and media_kind == "document":
            await bot.send_document(
                chat_id,
                media_file_id,
                caption=html_caption or None,
                parse_mode=parse_mode,
                reply_markup=kb_cta,
            )
        else:
            await bot.send_message(
                chat_id,
                html_caption or "—",
                parse_mode=parse_mode,
                reply_markup=kb_cta,
            )
    except Exception:
        pass


async def _admin_scheduled_show_targets(msg_target, state: FSMContext):
    data = await state.get_data()
    to_ch1 = bool(data.get("sched_to_ch1"))
    to_ch2 = bool(data.get("sched_to_ch2"))
    to_chat = bool(data.get("sched_to_chat"))
    to_admins = bool(data.get("sched_to_admins"))

    lines = ["📍 Куда отправлять пост:\n"]
    if POST_CHANNEL_1:
        lines.append(f"{'✅' if to_ch1 else '❌'} Канал СПБ")
    if POST_CHANNEL_2:
        lines.append(f"{'✅' if to_ch2 else '❌'} Канал ЕКБ")
    if POST_CHAT_ID:
        lines.append(f"{'✅' if to_chat else '❌'} Чат")
    lines.append(f"{'✅' if to_admins else '❌'} Пользователям бота (ЛС)")
    text = "\n".join(lines)

    kb_rows = []
    if POST_CHANNEL_1:
        kb_rows.append([InlineKeyboardButton(text="Канал СПБ", callback_data="admin_scheduled_toggle_ch1")])
    if POST_CHANNEL_2:
        kb_rows.append([InlineKeyboardButton(text="Канал ЕКБ", callback_data="admin_scheduled_toggle_ch2")])
    if POST_CHAT_ID:
        kb_rows.append([InlineKeyboardButton(text="Чат", callback_data="admin_scheduled_toggle_chat")])
    kb_rows.append([InlineKeyboardButton(text="Пользователям бота", callback_data="admin_scheduled_toggle_admins")])
    kb_rows.append([InlineKeyboardButton(text="👁 Предпросмотр", callback_data="admin_scheduled_preview")])
    kb_rows.append([InlineKeyboardButton(text="✅ Создать пост", callback_data="admin_scheduled_create")])
    kb_rows.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_scheduled_cancel_create")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    await msg_target.answer(text, reply_markup=kb)


@router.callback_query(AdminScheduledStates.targets, F.data.startswith("admin_scheduled_toggle_"))
async def admin_scheduled_toggle_target(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    data = await state.get_data()
    key = callback.data.replace("admin_scheduled_toggle_", "")
    if key == "ch1":
        data["sched_to_ch1"] = not bool(data.get("sched_to_ch1"))
    elif key == "ch2":
        data["sched_to_ch2"] = not bool(data.get("sched_to_ch2"))
    elif key == "chat":
        data["sched_to_chat"] = not bool(data.get("sched_to_chat"))
    elif key == "admins":
        data["sched_to_admins"] = not bool(data.get("sched_to_admins"))
    await state.update_data(**{
        "sched_to_ch1": data.get("sched_to_ch1"),
        "sched_to_ch2": data.get("sched_to_ch2"),
        "sched_to_chat": data.get("sched_to_chat"),
        "sched_to_admins": data.get("sched_to_admins"),
    })
    await callback.answer()
    await _admin_scheduled_show_targets(callback.message, state)


@router.callback_query(AdminScheduledStates.targets, F.data == "admin_scheduled_preview")
async def admin_scheduled_preview(callback: types.CallbackQuery, state: FSMContext):
    """Живой предпросмотр отложенного поста в ЛС админа (как в рассылке)."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    data = await state.get_data()
    text = (data.get("sched_text") or "").strip()
    media_file_id = data.get("sched_media_file_id")
    if not text and not media_file_id:
        await callback.answer("Нет текста и медиа для предпросмотра.", show_alert=True)
        return
    kb_cta = _build_scheduled_preview_kb_cta(data)
    await _send_followup_style_preview(
        callback.bot,
        callback.message.chat.id,
        text=data.get("sched_text") or "",
        media_file_id=data.get("sched_media_file_id"),
        media_kind=data.get("sched_media_type"),
        kb_cta=kb_cta,
    )
    await callback.answer("Предпросмотр отправлен.")


@router.callback_query(AdminScheduledStates.targets, F.data == "admin_scheduled_cancel_create")
async def admin_scheduled_cancel_create(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await state.clear()
    await admin_scheduled_root(callback)


@router.callback_query(AdminScheduledStates.targets, F.data == "admin_scheduled_create")
async def admin_scheduled_create(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    data = await state.get_data()
    text = data.get("sched_text") or ""
    media_type = data.get("sched_media_type")
    media_file_id = data.get("sched_media_file_id")
    run_at_utc = data.get("sched_run_at_utc")
    to_ch1 = bool(data.get("sched_to_ch1"))
    to_ch2 = bool(data.get("sched_to_ch2"))
    to_chat = bool(data.get("sched_to_chat"))
    to_admins = bool(data.get("sched_to_admins"))
    if not (to_ch1 or to_ch2 or to_chat or to_admins):
        await callback.answer("Нужно выбрать хотя бы один ресурс", show_alert=True)
        return
    if not run_at_utc:
        await callback.answer("Не задано время публикации", show_alert=True)
        return

    btn_text = data.get("sched_button_text")
    btn_url = data.get("sched_button_url")
    add_scheduled_post(
        text=text,
        media_type=media_type,
        media_file_id=media_file_id,
        send_to_channel1=to_ch1,
        send_to_channel2=to_ch2,
        send_to_chat=to_chat,
        send_to_admins=to_admins,
        run_at_utc=run_at_utc,
        button_text=btn_text,
        button_url=btn_url,
    )
    await state.clear()
    await callback.answer("Пост запланирован")
    text_list, kb = _scheduled_list_text_and_kb()
    await callback.message.edit_text(text_list, reply_markup=kb)


@router.message(AdminScheduledStates.button_text, F.text)
async def admin_scheduled_button_text(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    raw = (message.text or "").strip()
    if raw in ("", "-"):
        # без кнопки
        await state.update_data(
            sched_button_text=None,
            sched_button_url=None,
            sched_cta_buttons=None,
        )
        await state.set_state(AdminScheduledStates.targets)
        await _admin_scheduled_show_targets(message, state)
        return

    await state.update_data(sched_button_text=raw, sched_cta_buttons=None)
    await state.set_state(AdminScheduledStates.button_url)
    await message.answer(
        "🌐 Отправьте ссылку для кнопки (как в рассылке: обязательно с https:// или http://)."
    )


@router.message(AdminScheduledStates.button_url, F.text)
async def admin_scheduled_button_url(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    url = (message.text or "").strip()
    data = await state.get_data()
    btn_text = (data.get("sched_button_text") or "").strip()
    if not btn_text:
        await state.clear()
        await message.answer("Ошибка: не найден текст кнопки.")
        return
    # Как в рассылке (Follow-up): только http(s), плюс тот же формат cta_buttons для предпросмотра
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.answer("Отправьте корректную ссылку, начинающуюся с http:// или https://")
        return
    label = btn_text[:64] if len(btn_text) > 64 else btn_text
    await state.update_data(
        sched_button_url=url,
        sched_cta_buttons=[{"type": "url", "text": label, "url": url}],
    )
    await state.set_state(AdminScheduledStates.targets)
    await _admin_scheduled_show_targets(message, state)


@router.callback_query(F.data.startswith("admin_scheduled_cancel_"))
async def admin_scheduled_cancel(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    try:
        pid = int(callback.data.rsplit("_", 1)[-1])
    except ValueError:
        await callback.answer("Некорректный ID", show_alert=True)
        return
    cancel_scheduled_post(pid)
    await callback.answer("Пост отменён")
    text, kb = _scheduled_list_text_and_kb()
    await callback.message.edit_text(text, reply_markup=kb)


async def _show_followup_screen(callback: types.CallbackQuery):
    """Показать экран Follow-up (без answer — вызывающий должен ответить на callback)."""
    users_count = len(get_users_for_broadcast("all"))
    text = f"🔄 Follow-up\n\nПользователей в базе: {users_count}"
    await callback.message.edit_text(text, reply_markup=_followup_kb())


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
    await state.update_data(
        media_items=[],
        media_kind=None,
        broadcast_filter="all",
        add_cta=False,
        media_prompt_shown=False,
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_broadcast_cancel")]]
    )
    await callback.message.edit_text(
        "📤 Рассылка\n\nВведите текст сообщения. Или отправьте «-» чтобы только медиа:",
        reply_markup=kb,
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
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💫 Пропустить медиа", callback_data="admin_broadcast_skip_media")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_broadcast_cancel")],
        ]
    )
    await message.answer(
        "Отправьте фото/видео",
        reply_markup=kb,
    )


@router.message(AdminBroadcastStates.get_text, F.photo)
async def admin_broadcast_text_photo(message: types.Message, state: FSMContext):
    """Фото с подписью — сразу текст и первое медиа, дальше можно добавить ещё."""
    if message.from_user.id not in ADMIN_IDS:
        return
    text = (message.caption or "").strip() if message.caption else ""
    first_photo_id = message.photo[-1].file_id
    # Сохраняем текст и переводим в состояние добавления медиа
    await state.update_data(broadcast_text=text)
    await state.set_state(AdminBroadcastStates.get_media)
    # Общая логика добавления фото и перехода к следующему шагу
    await _broadcast_add_photo_and_maybe_next(message, state, first_photo_id)


@router.message(AdminBroadcastStates.get_media, F.photo)
async def admin_broadcast_media_photo(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    file_id = message.photo[-1].file_id
    await _broadcast_add_photo_and_maybe_next(message, state, file_id)


async def _broadcast_add_photo_and_maybe_next(message: types.Message, state: FSMContext, file_id: str):
    """Общая логика добавления фото в рассылку.

    - Собираем до 10 фото (альбом).
    - Если это одиночное фото (нет media_group_id) — сразу переходим к шагу настройки кнопки.
    - Если это альбом (есть media_group_id) — ждём ~0.8 сек, чтобы догрузились все фото с тем же media_group_id,
      потом переходим к шагу настройки кнопки один раз.
    """
    data = await state.get_data()
    media_items = data.get("media_items") or []
    media_kind = data.get("media_kind")

    if media_kind not in (None, "photo"):
        await message.answer("Уже добавлен файл. В одной рассылке либо фото (альбом), либо один файл.")
        return
    if len(media_items) >= 10:
        await message.answer("Уже добавлено 10 фото. Это максимум для одного поста.")
        return

    media_items.append({"type": "photo", "file_id": file_id})
    await state.update_data(media_items=media_items, media_kind="photo")

    group_id = message.media_group_id
    # Одиночное фото — сразу следующий шаг
    if not group_id:
        await _broadcast_goto_button_step(message, state)
        return

    # Альбом: запоминаем media_group_id и стартуем отложенный переход.
    last_group_id = data.get("last_media_group_id")
    await state.update_data(last_media_group_id=group_id)
    # Только для первого фото этой группы запускаем таймер
    if last_group_id != group_id:
        async def _delayed_next():
            # ждём, пока долетят остальные фото альбома
            await asyncio.sleep(0.8)
            # если состояние уже сменили — выходим
            if await state.get_state() != AdminBroadcastStates.get_media:
                return
            cur = await state.get_data()
            if cur.get("last_media_group_id") != group_id:
                return
            await _broadcast_goto_button_step(message, state)

        asyncio.create_task(_delayed_next())


def _broadcast_button_step_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔁 Раздел записи", callback_data="admin_broadcast_btn_internal")],
            [InlineKeyboardButton(text="🌐 Своя ссылка", callback_data="admin_broadcast_btn_url")],
            [InlineKeyboardButton(text="💫 Без кнопки", callback_data="admin_broadcast_cta_skip")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_broadcast_cta_back")],
        ]
    )


async def _broadcast_goto_button_step(message: types.Message, state: FSMContext):
    """Переход к шагу настройки текста инлайн-кнопки."""
    await state.set_state(AdminBroadcastStates.button_text)
    await message.answer(
        "📌 Выберите вариант кнопки под сообщением:\n\n"
        "1️⃣ Использовать раздел записи внутри бота\n"
        "2️⃣ Вставить свою ссылку\n"
        "3️⃣ Без кнопки",
        reply_markup=_broadcast_button_step_kb(),
    )


def _is_video_document(doc) -> bool:
    """Файл считается видео, если mime_type или расширение указывают на видео."""
    if getattr(doc, "mime_type", None) and str(doc.mime_type).startswith("video/"):
        return True
    fn = (getattr(doc, "file_name", None) or "").lower()
    return fn.endswith((".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"))


@router.message(AdminBroadcastStates.get_media, F.video)
async def admin_broadcast_media_video(message: types.Message, state: FSMContext):
    """Видео, отправленное как видео (не как файл) — уходит в рассылку как нормальное видео с превью."""
    if message.from_user.id not in ADMIN_IDS:
        return
    file_id = message.video.file_id
    data = await state.get_data()
    media_items = data.get("media_items") or []
    media_kind = data.get("media_kind")
    if media_items and media_kind not in (None, "video"):
        await message.answer("Уже добавлены фото/файл. В одной рассылке либо фото (альбом), либо один файл/видео.")
        return
    media_items = [{"type": "video", "file_id": file_id}]
    await state.update_data(media_items=media_items, media_kind="video")
    await _broadcast_goto_button_step(message, state)


@router.message(AdminBroadcastStates.get_media, F.document)
async def admin_broadcast_media_doc(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    doc = message.document
    file_id = doc.file_id
    data = await state.get_data()
    media_items = data.get("media_items") or []
    media_kind = data.get("media_kind")
    if media_items and media_kind not in (None, "document", "video"):
        await message.answer("Уже добавлены фото. Сейчас можно либо альбом из фото, либо один файл/видео.")
        return
    # Если документ — видео (mp4 и т.д.), сохраняем как видео и переходим к шагу кнопки (как для фото)
    if _is_video_document(doc):
        media_items = [{"type": "video", "file_id": file_id}]
        await state.update_data(media_items=media_items, media_kind="video")
        await _broadcast_goto_button_step(message, state)
    else:
        media_items = [{"type": "document", "file_id": file_id}]
        await state.update_data(media_items=media_items, media_kind="document")
        await state.set_state(AdminBroadcastStates.confirm)
        await _admin_broadcast_confirm(message, state)


@router.callback_query(AdminBroadcastStates.get_media, F.data == "admin_broadcast_skip_media")
async def admin_broadcast_skip_media(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    # Явный переход к шагу настройки кнопки (без фото / только с уже добавленными)
    await _broadcast_goto_button_step(callback.message, state)
    await callback.answer()


@router.callback_query(AdminBroadcastStates.button_text, F.data == "admin_broadcast_cta_skip")
async def admin_broadcast_cta_skip(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await state.update_data(cta_text=None, add_cta=False)
    await state.set_state(AdminBroadcastStates.confirm)
    await _admin_broadcast_confirm(callback.message, state, callback)
    await callback.answer()


@router.callback_query(AdminBroadcastStates.button_text, F.data == "admin_broadcast_btn_internal")
async def admin_broadcast_btn_internal(callback: types.CallbackQuery, state: FSMContext):
    """Простой вариант: стандартная кнопка записи внутри бота."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    buttons = [
        {"type": "internal", "text": "Записаться на игру", "callback": "menu_record"},
    ]
    await state.update_data(cta_buttons=buttons, add_cta=True, expect_url_only=False)
    await state.set_state(AdminBroadcastStates.confirm)
    await _admin_broadcast_confirm(callback.message, state, callback)
    await callback.answer()


@router.callback_query(AdminBroadcastStates.button_text, F.data == "admin_broadcast_btn_url")
async def admin_broadcast_btn_url(callback: types.CallbackQuery, state: FSMContext):
    """Вариант: одна своя ссылка. Дальше ждём URL сообщением."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await state.update_data(expect_url_only=True, cta_url=None)
    await callback.message.answer("🌐 Отправьте ссылку.")
    await callback.answer()


@router.callback_query(AdminBroadcastStates.button_text, F.data == "admin_broadcast_cta_back")
async def admin_broadcast_cta_back(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await state.set_state(AdminBroadcastStates.get_media)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💫 Пропустить медиа", callback_data="admin_broadcast_skip_media")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_broadcast_cancel")],
        ]
    )
    await callback.message.edit_text(
        "Отправьте фото/видео",
        reply_markup=kb,
    )
    await callback.answer()


@router.message(AdminBroadcastStates.button_text, F.text)
async def admin_broadcast_button_text(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    raw = (message.text or "").strip()
    data = await state.get_data()
    # Простой сценарий: ждём сначала URL, потом текст для кнопки
    if data.get("expect_url_only"):
        url_stored = data.get("cta_url")
        if not url_stored:
            url = raw
            if not (url.startswith("http://") or url.startswith("https://")):
                await message.answer("Отправьте корректную ссылку, начинающуюся с http:// или https://")
                return
            await state.update_data(cta_url=url)
            await message.answer("✏️ Отправьте текст для кнопки (например: «Перейти в канал»).")
            return
        else:
            btn_text = raw or "Перейти"
            buttons = [{"type": "url", "text": btn_text, "url": url_stored}]
            await state.update_data(
                cta_buttons=buttons,
                add_cta=True,
                expect_url_only=False,
                cta_url=None,
            )
    else:
        # Расширенный сценарий (оставляем для совместимости, если админ пришлёт текст вручную)
        if raw in ("-", ""):
            await state.update_data(cta_buttons=[], add_cta=False, cta_text=None)
        else:
            lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
            buttons = []
            for ln in lines[:5]:  # не больше 5 кнопок
                if "|" in ln:
                    text_part, url_part = ln.split("|", 1)
                    text_part = text_part.strip()
                    url_part = url_part.strip()
                    if not text_part or not url_part:
                        continue
                    buttons.append({"type": "url", "text": text_part, "url": url_part})
                else:
                    # Внутренняя кнопка внутри бота (menu_record)
                    buttons.append({"type": "internal", "text": ln, "callback": "menu_record"})
            await state.update_data(
                cta_buttons=buttons,
                add_cta=bool(buttons),
            )
    await state.set_state(AdminBroadcastStates.confirm)
    await _admin_broadcast_confirm(message, state)


@router.callback_query(AdminBroadcastStates.get_media, F.data == "admin_broadcast_more_media")
async def admin_broadcast_more_media(callback: types.CallbackQuery, state: FSMContext):
    """Технический хэндлер для клавиатуры — просто подсказываем, что можно слать ещё фото."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await callback.answer("Отправьте ещё фото для этой рассылки.")


@router.callback_query(AdminBroadcastStates.get_media, F.data == "admin_broadcast_to_confirm")
async def admin_broadcast_to_confirm(callback: types.CallbackQuery, state: FSMContext):
    """Переход к шагу подтверждения с предпросмотром."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await state.set_state(AdminBroadcastStates.confirm)
    await _admin_broadcast_confirm(callback.message, state, callback)


async def _admin_broadcast_confirm(msg_target, state: FSMContext, callback=None):
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    media_items = data.get("media_items") or []
    media_kind = data.get("media_kind")
    # кнопки нам здесь не нужны, только счётчик получателей
    filter_type = data.get("broadcast_filter", "all")
    # Фильтр получателей: всем / с заявкой / только админам
    if filter_type == "admins":
        user_ids = ADMIN_IDS
    else:
        user_ids = get_users_for_broadcast(filter_type)
    count = len(user_ids)

    if not text and not media_items:
        err = "Добавьте текст или медиа."
        if callback:
            await callback.message.edit_text(err)
            await callback.answer()
        else:
            await msg_target.answer(err)
        return

    preview_raw = (text[:100] + "...") if len(text) > 100 else (text or "(нет)")
    preview_raw_html = broadcast_text_to_html(preview_raw)
    if media_items:
        if media_kind == "photo":
            media_desc = f"фото x{len(media_items)}"
        elif media_kind == "video":
            media_desc = "видео"
        elif media_kind == "document":
            media_desc = "файл"
        else:
            media_desc = "медиа"
        preview = f"Текст:\n{preview_raw_html}\n\nМедиа: {media_desc}\n\nПолучателей: {count}"
    else:
        preview = f"Текст:\n{preview_raw_html}\n\nПолучателей: {count}"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Всем", callback_data="admin_broadcast_filter_all"),
                InlineKeyboardButton(text="С заявкой", callback_data="admin_broadcast_filter_with_lead"),
                InlineKeyboardButton(text="Админам", callback_data="admin_broadcast_filter_admins"),
            ],
            [InlineKeyboardButton(text="👁 Предпросмотр", callback_data="admin_broadcast_preview")],
            [InlineKeyboardButton(text="✅ Отправить", callback_data="admin_broadcast_send")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_broadcast_cancel")],
        ]
    )
    if callback:
        await callback.message.edit_text(
            f"📤 Подтверждение рассылки\n\n{preview}",
            reply_markup=kb,
            parse_mode="HTML",
        )
        await callback.answer()
    else:
        await msg_target.answer(
            f"📤 Подтверждение рассылки\n\n{preview}",
            reply_markup=kb,
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("admin_broadcast_filter_"))
async def admin_broadcast_filter(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    # admin_broadcast_filter_all -> all, admin_broadcast_filter_admins -> admins
    f = callback.data.replace("admin_broadcast_filter_", "")
    await state.update_data(broadcast_filter=f)
    await _admin_broadcast_confirm(callback.message, state, callback)


@router.callback_query(AdminBroadcastStates.confirm, F.data == "admin_broadcast_preview")
async def admin_broadcast_preview(callback: types.CallbackQuery, state: FSMContext):
    """Живой предпросмотр из финального шага (форма уже с кнопкой/фильтрами)."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    media_items = data.get("media_items") or []
    media_kind = data.get("media_kind")
    add_cta = data.get("add_cta", True)
    bot = callback.bot
    chat_id = callback.message.chat.id
    # Строим клавиатуру с кнопками: либо из нового поля cta_buttons, либо из старого cta_text (для обратной совместимости)
    kb_cta = None
    buttons = data.get("cta_buttons")
    if not buttons:
        cta_text = (data.get("cta_text") or "").strip() or None
        if add_cta and cta_text:
            buttons = [{"type": "internal", "text": cta_text, "callback": "menu_record"}]
    if add_cta and buttons:
        row = []
        for b in buttons:
            if b.get("type") == "url":
                row.append(InlineKeyboardButton(text=b.get("text", "Ссылка"), url=b.get("url", "")))
            else:
                row.append(
                    InlineKeyboardButton(
                        text=b.get("text", "Подробнее"),
                        callback_data=b.get("callback", "menu_record"),
                    )
                )
        kb_cta = InlineKeyboardMarkup(inline_keyboard=[row])
    media_file_id = media_items[0]["file_id"] if media_items else None
    mk = media_kind if media_file_id else None
    await _send_followup_style_preview(
        bot,
        chat_id,
        text=text,
        media_file_id=media_file_id,
        media_kind=mk,
        kb_cta=kb_cta,
    )
    await callback.answer("Предпросмотр отправлен.")


@router.callback_query(F.data == "admin_broadcast_toggle_cta")
async def admin_broadcast_toggle_cta(callback: types.CallbackQuery, state: FSMContext):
    # Хэндлер больше не используется (кнопки нет), оставлен заглушкой на случай старых апдейтов
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast_send")
async def admin_broadcast_send(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    media_items = data.get("media_items") or []
    media_kind = data.get("media_kind")
    add_cta = data.get("add_cta", True)
    if not text and not media_items:
        await callback.answer("Добавьте текст или медиа.", show_alert=True)
        return
    filter_type = data.get("broadcast_filter", "all")
    if filter_type == "admins":
        user_ids = ADMIN_IDS
    else:
        user_ids = get_users_for_broadcast(filter_type)
    await state.clear()

    # Кнопки CTA для рассылки
    kb_cta = None
    buttons = data.get("cta_buttons")
    if not buttons:
        cta_text = (data.get("cta_text") or "").strip() or None
        if add_cta and cta_text:
            buttons = [{"type": "internal", "text": cta_text, "callback": "menu_record"}]
    if add_cta and buttons:
        row = []
        for b in buttons:
            if b.get("type") == "url":
                row.append(InlineKeyboardButton(text=b.get("text", "Ссылка"), url=b.get("url", "")))
            else:
                row.append(
                    InlineKeyboardButton(
                        text=b.get("text", "Подробнее"),
                        callback_data=b.get("callback", "menu_record"),
                    )
                )
        kb_cta = InlineKeyboardMarkup(inline_keyboard=[row])
    html_caption = broadcast_text_to_html(text) if text else None
    total = len(user_ids)
    await callback.message.edit_text(f"📤 Отправка {total} пользователям...")
    sent, failed = 0, 0
    for uid in user_ids:
        try:
            if media_items and media_kind == "photo":
                await callback.bot.send_photo(
                    uid,
                    photo=media_items[0]["file_id"],
                    caption=html_caption or None,
                    parse_mode="HTML" if html_caption else None,
                    reply_markup=kb_cta,
                )
            elif media_items and media_kind == "video":
                await callback.bot.send_video(
                    uid,
                    video=media_items[0]["file_id"],
                    caption=html_caption or None,
                    parse_mode="HTML" if html_caption else None,
                    reply_markup=kb_cta,
                )
            elif media_items and media_kind == "document":
                await callback.bot.send_document(
                    uid,
                    document=media_items[0]["file_id"],
                    caption=html_caption or None,
                    parse_mode="HTML" if html_caption else None,
                    reply_markup=kb_cta,
                )
            else:
                await callback.bot.send_message(
                    uid,
                    html_caption or "—",
                    parse_mode="HTML" if html_caption else None,
                    reply_markup=kb_cta,
                )
            sent += 1
        except Exception:
            # Игнорируем ошибки доставки для статистики — администратору показываем полный охват
            failed += 1
        await asyncio.sleep(0.05)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_followup")]])
    await callback.message.edit_text(
        f"✅ Рассылка завершена.\nОтправлено: {total}",
        reply_markup=kb,
    )
    await callback.answer()


# --- Autopipeline / Onboarding funnel ---


def _funnel_list_text_and_kb():
    """Список шагов автоворонки для админки."""
    steps = get_funnel_steps()
    if not steps:
        text = "📬 Автоворонка"
    else:
        lines = ["📬 Автоворонка\n"]
        for idx, row in enumerate(steps, start=1):
            sid, order_num, delay_hours, text_raw, media_type, media_file_id, is_active, button_text, button_url = row
            status = "✅" if is_active else "❌"
            preview = (text_raw or "").strip()
            if not preview:
                if media_type:
                    preview = f"[{media_type}]"
                else:
                    preview = "(пусто)"
            if len(preview) > 80:
                preview = preview[:80] + "..."
            delay_label = "0 (сразу)" if delay_hours == 0 else f"+{delay_hours} ч"
            btn_info = ""
            if button_text and button_url:
                btn_info = f"\n🔗 Кнопка: {button_text} → {button_url}"
            lines.append(f"{status} Шаг #{idx}: {delay_label}\n{preview}{btn_info}\n")
        text = "\n".join(lines)

    kb_rows = [
        [InlineKeyboardButton(text="➕ Добавить шаг", callback_data="admin_funnel_add")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
    ]

    # Для каждого шага добавляем ряд кнопок
    for idx, row in enumerate(steps, start=1):
        sid = row[0]
        is_active = row[6]
        kb_rows.insert(
            0,
            [
                InlineKeyboardButton(text=f"✏️ Шаг #{idx}", callback_data=f"admin_funnel_edit_{sid}"),
                InlineKeyboardButton(
                    text=("❌ Выкл" if is_active else "✅ Вкл"),
                    callback_data=f"admin_funnel_toggle_{sid}",
                ),
                InlineKeyboardButton(text="🗑", callback_data=f"admin_funnel_delete_{sid}"),
            ],
        )

    return text, InlineKeyboardMarkup(inline_keyboard=kb_rows)


@router.callback_query(F.data == "admin_funnel")
async def admin_funnel_root(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    text, kb = _funnel_list_text_and_kb()
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "admin_funnel_add")
async def admin_funnel_add_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminFunnelStates.add_delay)
    await callback.message.answer(
        "Через сколько часов после первого захода пользователя в бота отправлять этот шаг?\n"
        "Например: 0 (сразу); 1 (через 1 ч); 2 (через 2 ч); 3 (через 3 ч)... 24 (через сутки)."
    )


@router.message(AdminFunnelStates.add_delay, F.text)
async def admin_funnel_add_delay(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    raw = (message.text or "").strip()
    try:
        hours = int(raw)
        if hours < 0:
            raise ValueError
    except ValueError:
        await message.answer("Введи целое число часов (0 или больше).")
        return
    await state.update_data(delay_hours=hours)
    await state.set_state(AdminFunnelStates.add_content)
    await message.answer("📩 Отправь сообщение для рассылки.")


def _extract_funnel_media(message: types.Message):
    """Вернуть (media_type, file_id, text) из сообщения админа для автоворонки."""
    text = (message.text or "").strip() if message.text else ""
    media_type = None
    file_id = None
    caption = (message.caption or "").strip() if message.caption else ""

    if message.photo:
        media_type = "photo"
        file_id = message.photo[-1].file_id
        if caption:
            text = caption
    elif message.video:
        media_type = "video"
        file_id = message.video.file_id
        if caption:
            text = caption
    elif message.document:
        media_type = "document"
        file_id = message.document.file_id
        if caption:
            text = caption

    return media_type, file_id, text


@router.message(AdminFunnelStates.add_content)
async def admin_funnel_add_content(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    delay_hours = data.get("delay_hours", 0)

    media_type, file_id, text = _extract_funnel_media(message)
    if not text and not file_id:
        await message.answer("Нужно добавить либо текст, либо медиа.")
        return

    sid = add_funnel_step(delay_hours=delay_hours, text=text, media_type=media_type, media_file_id=file_id)
    await state.update_data(funnel_step_id=sid)
    await state.set_state(AdminFunnelStates.add_button_text)
    await message.answer(
        "🔗 Отправьте текст для кнопки.\n\n"
        "Или отправьте «-», чтобы оставить шаг без кнопки.",
    )


@router.callback_query(F.data.startswith("admin_funnel_delete_"))
async def admin_funnel_delete(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    sid = int(callback.data.split("_")[-1])
    delete_funnel_step(sid)
    text, kb = _funnel_list_text_and_kb()
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer("Шаг удалён")


@router.callback_query(F.data.startswith("admin_funnel_toggle_"))
async def admin_funnel_toggle(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    sid = int(callback.data.split("_")[-1])
    # переключаем is_active 1 <-> 0
    from database import get_funnel_steps as _get_all_steps
    steps = _get_all_steps()
    current = next((s for s in steps if s[0] == sid), None)
    if not current:
        await callback.answer("Шаг не найден", show_alert=True)
        return
    _, order_num, delay_hours, text_raw, media_type, media_file_id, is_active = current
    update_funnel_step(sid, is_active=0 if is_active else 1)
    text, kb = _funnel_list_text_and_kb()
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer("Статус изменён")


@router.callback_query(F.data.startswith("admin_funnel_edit_"))
async def admin_funnel_edit_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    sid = int(callback.data.split("_")[-1])
    steps = get_funnel_steps()
    current = next((s for s in steps if s[0] == sid), None)
    if not current:
        await callback.answer("Шаг не найден", show_alert=True)
        return
    _, order_num, delay_hours, text_raw, media_type, media_file_id, is_active, button_text, button_url = current
    await state.update_data(funnel_step_id=sid)
    await state.set_state(AdminFunnelStates.edit_delay)
    preview = (text_raw or "").strip()
    if len(preview) > 100:
        preview = preview[:100] + "..."
    delay_label = "0 (сразу)" if delay_hours == 0 else f"+{delay_hours} ч"
    await callback.message.answer(
        f"Редактирование шага #{sid}.\n"
        f"Сейчас: {delay_label}, активен: {'да' if is_active else 'нет'}.\n\n"
        f"Текст:\n{preview or '(пусто)'}\n\n"
        f"Введи новое количество часов (0, 1, 2... 72 и т.д.):"
    )
    await callback.answer()


@router.message(AdminFunnelStates.edit_delay, F.text)
async def admin_funnel_edit_delay(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    raw = (message.text or "").strip()
    try:
        hours = int(raw)
        if hours < 0:
            raise ValueError
    except ValueError:
        await message.answer("Введи целое число часов (0 или больше).")
        return
    data = await state.get_data()
    sid = data.get("funnel_step_id")
    update_funnel_step(sid, delay_hours=hours)
    await state.set_state(AdminFunnelStates.edit_content)
    await message.answer(
        "Теперь отправь новое сообщение для этого шага (текст или медиа с подписью).\n"
        "Если хочешь оставить текст/медиа как есть — просто продублируй текущее сообщение."
    )


@router.message(AdminFunnelStates.edit_content)
async def admin_funnel_edit_content(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    sid = data.get("funnel_step_id")
    media_type, file_id, text = _extract_funnel_media(message)
    if not text and not file_id:
        await message.answer("Нужно добавить либо текст, либо медиа.")
        return
    update_funnel_step(
        sid,
        text=text,
        media_type=media_type,
        media_file_id=file_id,
    )
    await state.set_state(AdminFunnelStates.edit_button_text)
    await message.answer(
        "✅ Контент шага обновлён.\n\n"
        "Теперь настрой кнопку.\n"
        "Отправьте новый текст для кнопки или «-», чтобы удалить кнопку / оставить без неё.",
    )


@router.message(AdminFunnelStates.add_button_text, F.text)
async def admin_funnel_add_button_text(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    raw = (message.text or "").strip()
    data = await state.get_data()
    sid = data.get("funnel_step_id")
    if not sid:
        await state.clear()
        await message.answer("Ошибка: не найден шаг автоворонки.")
        return
    if raw in ("", "-"):
        update_funnel_step(sid, button_text=None, button_url=None)
        await state.clear()
        await message.answer("Шаг автоворонки добавлен без кнопки.")
        text_list, kb = _funnel_list_text_and_kb()
        await message.answer(text_list, reply_markup=kb)
        return

    await state.update_data(tmp_button_text=raw)
    await state.set_state(AdminFunnelStates.add_button_url)
    await message.answer(
        "🌐 Теперь отправьте ссылку для кнопки:"
    )


@router.message(AdminFunnelStates.add_button_url, F.text)
async def admin_funnel_add_button_url(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    url = (message.text or "").strip()
    data = await state.get_data()
    sid = data.get("funnel_step_id")
    btn_text = (data.get("tmp_button_text") or "").strip()
    if not sid or not btn_text:
        await state.clear()
        await message.answer("Ошибка: не найден шаг автоворонки или текст кнопки.")
        return
    update_funnel_step(sid, button_text=btn_text, button_url=url)
    await state.clear()
    await message.answer("✅ Шаг автоворонки добавлен с кнопкой.")
    text_list, kb = _funnel_list_text_and_kb()
    await message.answer(text_list, reply_markup=kb)


@router.message(AdminFunnelStates.edit_button_text, F.text)
async def admin_funnel_edit_button_text(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    raw = (message.text or "").strip()
    data = await state.get_data()
    sid = data.get("funnel_step_id")
    if not sid:
        await state.clear()
        await message.answer("Ошибка: не найден шаг автоворонки.")
        return
    if raw in ("", "-"):
        update_funnel_step(sid, button_text=None, button_url=None)
        await state.clear()
        await message.answer("✅ Кнопка для шага удалена / отключена.")
        text_list, kb = _funnel_list_text_and_kb()
        await message.answer(text_list, reply_markup=kb)
        return

    await state.update_data(tmp_button_text=raw)
    await state.set_state(AdminFunnelStates.edit_button_url)
    await message.answer(
        "🌐 Теперь отправьте новую ссылку для кнопки:"
    )


@router.message(AdminFunnelStates.edit_button_url, F.text)
async def admin_funnel_edit_button_url(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    url = (message.text or "").strip()
    data = await state.get_data()
    sid = data.get("funnel_step_id")
    btn_text = (data.get("tmp_button_text") or "").strip()
    if not sid or not btn_text:
        await state.clear()
        await message.answer("Ошибка: не найден шаг автоворонки или текст кнопки.")
        return
    update_funnel_step(sid, button_text=btn_text, button_url=url)
    await state.clear()
    await message.answer("✅ Кнопка для шага обновлена.")
    text_list, kb = _funnel_list_text_and_kb()
    await message.answer(text_list, reply_markup=kb)


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
            [InlineKeyboardButton(text="📬 Автоворонка", callback_data="admin_funnel")],
            [InlineKeyboardButton(text="📅 Отложенные посты", callback_data="admin_scheduled")],
        ]
    )
    await callback.message.edit_text("Админ-панель:", reply_markup=kb)
    await callback.answer()




# --- Scenarios Management ---

def _scenarios_list_kb():
    scenarios = get_scenarios()
    text = "Сценарии:\n\n"
    kb = []
    for s in scenarios:
        sid, name, desc = s
        text += f"🔹 {name}\n"
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
    await callback.message.edit_text(text, reply_markup=kb)
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
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("adm_scen_del_"))
async def admin_delete_scenario(callback: types.CallbackQuery):
    sid = int(callback.data.split("_")[3])
    delete_scenario(sid)
    await callback.answer("Сценарий удалён")
    text, kb = _scenarios_list_kb()
    await callback.message.edit_text(text, reply_markup=kb)


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
    await message.answer(text, reply_markup=kb)


# --- Stories Management (per scenario) ---

def _scenario_stories_kb(scenario_id):
    scenario = get_scenario(scenario_id)
    if not scenario:
        return "Сценарий не найден", None
        
    stories = get_stories_by_scenario(scenario_id)
    text = f"Сюжеты сценария «{scenario[1]}»:\n\n"
    kb = []
    
    if not stories:
        text += "Пока нет сюжетов.\n"
    else:
        for i, s in enumerate(stories):
            sid, title, content, image_url, game_id, order_num, hidden, scen_id = s
            status = "❌" if hidden else "✅"
            preview = (title[:20] + "...") if len(title) > 20 else title
            text += f"{status} {preview}\n"
            
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
    await callback.message.edit_text(text, reply_markup=kb)
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
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("adm_story_move_"))
async def admin_move_story(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    sid = int(parts[3])
    scenario_id = int(parts[4])
    direction = parts[5] # up/down
    
    swap_story_order(sid, direction)
    await callback.answer()
    
    text, kb = _scenario_stories_kb(scenario_id)
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("adm_story_delete_"))
async def admin_delete_story(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    sid = int(parts[3])
    scenario_id = int(parts[4])
    
    delete_story(sid)
    await callback.answer("Сюжет удалён")
    
    text, kb = _scenario_stories_kb(scenario_id)
    await callback.message.edit_text(text, reply_markup=kb)


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
    update_story(sid, content=new_text)  # title остаётся "Сюжет N"
    
    await state.clear()
    await message.answer("✅ Текст обновлён.")
    
    text, kb = _scenario_stories_kb(scenario_id)
    await message.answer(text, reply_markup=kb)


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
    await message.answer(text, reply_markup=kb)


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
    
    # Считаем order_num: сколько уже есть сюжетов (Сюжет 1, Сюжет 2, ...)
    existing = get_stories_by_scenario(scenario_id)
    order_num = len(existing)
    
    add_story(
        title=f"Сюжет {order_num + 1}",
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
    await message.answer(text, reply_markup=kb)


# --- Format Management (один экран "Что это за формат?") ---

@router.callback_query(F.data == "admin_format")
async def admin_format_edit(callback: types.CallbackQuery):
    text_db, image_url, _ = get_format_info()
    
    text = "Редактирование «Что это за формат?»\n\n"
    if text_db:
        preview = (text_db[:100] + "...") if len(text_db) > 100 else text_db
        text += f"Текущий текст:\n{preview}\n\n"
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
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "adm_fmt_edit_text")
async def admin_format_edit_text_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminFormatStates.edit_text)
    text_db, _, _ = get_format_info()
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
    _, current_img, _ = get_format_info()  # Сохраняем текущую картинку
    update_format_info(new_text, current_img or "")
    await state.clear()
    await message.answer("✅ Текст обновлён.")
    
    # Возвращаем меню редактирования
    text_db, image_url, _ = get_format_info()
    text = "Редактирование «Что это за формат?»\n\n"
    if text_db:
        preview = (text_db[:100] + "...") if len(text_db) > 100 else text_db
        text += f"Текущий текст:\n{preview}\n\n"
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
    await message.answer(text, reply_markup=kb)


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
    text_db, image_url, _ = get_format_info()
    text = "Редактирование «Что это за формат?»\n\n"
    if text_db:
        preview = (text_db[:100] + "...") if len(text_db) > 100 else text_db
        text += f"Текущий текст:\n{preview}\n\n"
    text += "❌ Картинка не прикреплена\n\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать текст", callback_data="adm_fmt_edit_text")],
        [InlineKeyboardButton(text="🖼 Изменить картинку", callback_data="adm_fmt_edit_img")],
        [InlineKeyboardButton(text="👁 Предпросмотр", callback_data="adm_fmt_preview")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
    ])
    await callback.message.answer(text, reply_markup=kb)


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
    text_db, image_url, _ = get_format_info()
    text = "Редактирование «Что это за формат?»\n\n"
    if text_db:
        preview = (text_db[:100] + "...") if len(text_db) > 100 else text_db
        text += f"Текущий текст:\n{preview}\n\n"
    text += "✅ Картинка прикреплена\n\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать текст", callback_data="adm_fmt_edit_text")],
        [InlineKeyboardButton(text="🖼 Изменить картинку", callback_data="adm_fmt_edit_img")],
        [InlineKeyboardButton(text="👁 Предпросмотр", callback_data="adm_fmt_preview")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
    ])
    await message.answer(text, reply_markup=kb)


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
    text_db, image_url, _ = get_format_info()
    text = "Редактирование «Что это за формат?»\n\n"
    if text_db:
        preview = (text_db[:100] + "...") if len(text_db) > 100 else text_db
        text += f"Текущий текст:\n{preview}\n\n"
    text += "❌ Картинка не прикреплена\n\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать текст", callback_data="adm_fmt_edit_text")],
        [InlineKeyboardButton(text="🖼 Изменить картинку", callback_data="adm_fmt_edit_img")],
        [InlineKeyboardButton(text="👁 Предпросмотр", callback_data="adm_fmt_preview")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
    ])
    await message.answer(text, reply_markup=kb)


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


