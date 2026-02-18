from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from config import ADMIN_IDS
from database import (
    get_all_games,
    get_leads,
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
            [InlineKeyboardButton(text="📖 Сюжеты", callback_data="admin_stories")],
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
    text = "**📆 Расписание (редактирование):**\n\n"
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
    text = f"**✏️ Редактировать:** {name}\n\n{date} {time or ''}\n📍 {place or '—'}\n💰 {price or '—'}\n\n{desc or '—'}\nЛимит: {limit}"
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
    text = f"**✏️ Редактировать:** {name}\n\n{date} {time or ''}\n📍 {place or '—'}\n💰 {price or '—'}\n\n{desc or '—'}\nЛимит: {limit}"
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
            lines.append(f"#{lid} {name or '—'} | {gname} | {cnt} чел. | {date_str}")
        text = "**Лиды (последние 50):**\n_Лид = юзер прошёл запись и нажал «Подтвердить»_\n\n" + "\n".join(lines[:20])
        if len(lines) > 20:
            text += f"\n\n... и ещё {len(lines) - 20}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]]
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "admin_followup")
async def admin_followup(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    cur = get_setting("follow_up_enabled", "1")
    status = "вкл" if cur == "1" else "выкл"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Выключить" if cur == "1" else "✅ Включить",
                    callback_data="admin_followup_toggle",
                )
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
        ]
    )
    desc = "\n\n_Авто-прогрев: воронка «Что это за формат» тем, кто зашёл в бота, но не оставил заявку. Логика пока не реализована._"
    await callback.message.edit_text(f"Follow-up сообщения: **{status}**{desc}", reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "admin_followup_toggle")
async def admin_followup_toggle(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    cur = get_setting("follow_up_enabled", "1")
    new = "0" if cur == "1" else "1"
    set_setting("follow_up_enabled", new)
    await callback.answer("Сохранено")
    await admin_followup(callback)


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
            [InlineKeyboardButton(text="📖 Сюжеты", callback_data="admin_stories")],
            [InlineKeyboardButton(text="📈 Лиды", callback_data="admin_leads")],
            [InlineKeyboardButton(text="🔄 Follow-up", callback_data="admin_followup")],
        ]
    )
    await callback.message.edit_text("Админ-панель:", reply_markup=kb)
    await callback.answer()


# Stories Admin
def _stories_list_kb():
    """Клавиатура со списком сюжетов для админки."""
    stories = get_all_stories()
    text = "**📖 Сюжеты:**\n\n"
    kb = []
    
    # Кнопка "Добавить сюжет" всегда должна быть видна в начале
    kb.append([InlineKeyboardButton(text="➕ Добавить сюжет", callback_data="admin_add_story")])
    
    if not stories:
        text += "Пока нет сюжетов.\n"
    else:
        for s in stories:
            sid, title, content, image_url, game_id, order_num, hidden = s
            status = "❌" if hidden else "✅"
            text += f"{status} {title}\n"
            kb.append([
                InlineKeyboardButton(text=f"{'✅ Показать' if hidden else '❌ Скрыть'}", callback_data=f"adm_story_toggle_{sid}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"adm_story_delete_{sid}"),
            ])
    
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    return text, InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(F.data == "admin_stories")
async def admin_stories_list(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    text, kb = _stories_list_kb()
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("adm_story_toggle_"))
async def admin_toggle_story(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    sid = int(callback.data.split("_")[3])
    h = toggle_story_visibility(sid)
    status = "скрыт" if h else "показан"
    await callback.answer(f"Сюжет {status}")
    text, kb = _stories_list_kb()
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("adm_story_delete_"))
async def admin_delete_story(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    sid = int(callback.data.split("_")[3])
    delete_story(sid)
    await callback.answer("Сюжет удалён")
    text, kb = _stories_list_kb()
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "admin_add_story")
async def admin_add_story_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    # Начинаем сразу с текста сюжета (без названия)
    await state.set_state(AdminStoryStates.add_content)
    await callback.message.answer("📝 Текст сюжета (можно длинный, будет разбит на экраны):")
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
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await state.update_data(image_url="")
    # Сразу сохраняем сюжет без привязки к игре и порядка
    data = await state.get_data()
    content = data["content"]
    # Название = весь текст сюжета
    sid = add_story(
        title=content,
        content=content,
        image_url="",
        game_id=None,
        order_num=0,
    )
    await state.clear()
    await callback.message.edit_text(f"✓ Сюжет добавлен. ID: {sid}")
    await callback.answer()


@router.message(AdminStoryStates.add_image, F.text)
async def admin_add_story_image(message: types.Message, state: FSMContext):
    image_url = message.text.strip()
    if image_url.lower() in ("пропустить", "-", ""):
        image_url = ""
    # Сразу сохраняем сюжет без привязки к игре и порядка
    data = await state.get_data()
    content = data["content"]
    # Название = весь текст сюжета
    sid = add_story(
        title=content,
        content=content,
        image_url=image_url,
        game_id=None,
        order_num=0,
    )
    await state.clear()
    await message.answer(f"✓ Сюжет добавлен. ID: {sid}")


@router.message(AdminStoryStates.add_image, F.photo)
async def admin_add_story_image_photo(message: types.Message, state: FSMContext):
    """Обработка загрузки изображения через фото."""
    # Получаем file_id самого большого фото - используем file_id напрямую
    photo = message.photo[-1]
    file_id = photo.file_id
    # Сохраняем file_id вместо URL - Telegram может работать с file_id напрямую
    await state.update_data(image_url=file_id)
    # Сразу сохраняем сюжет без привязки к игре и порядка
    data = await state.get_data()
    content = data["content"]
    # Название = весь текст сюжета
    sid = add_story(
        title=content,
        content=content,
        image_url=file_id,
        game_id=None,
        order_num=0,
    )
    await state.clear()
    await message.answer(f"✓ Сюжет добавлен. ID: {sid}")


