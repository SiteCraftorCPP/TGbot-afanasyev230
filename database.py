import sqlite3
from datetime import datetime
from pathlib import Path

from config import DATABASE_PATH

Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)


def get_conn():
    return sqlite3.connect(DATABASE_PATH)


def create_tables():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        game_date TEXT NOT NULL,
        game_time TEXT,
        place TEXT,
        price TEXT,
        description TEXT,
        limit_places INTEGER,
        hidden INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER NOT NULL,
        username TEXT,
        name TEXT,
        phone TEXT,
        game_id INTEGER,
        game_name TEXT,
        participants_count INTEGER DEFAULT 1,
        comment TEXT,
        utm_source TEXT,
        utm_medium TEXT,
        utm_campaign TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'new',
        FOREIGN KEY (game_id) REFERENCES games(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER NOT NULL,
        username TEXT,
        name TEXT,
        question_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    cur.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('follow_up_enabled', '1')"
    )

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_utm (
        tg_id INTEGER PRIMARY KEY,
        utm_source TEXT,
        utm_medium TEXT,
        utm_campaign TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        image_url TEXT,
        game_id INTEGER,
        order_num INTEGER DEFAULT 0,
        hidden INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        scenario_id INTEGER,
        FOREIGN KEY (game_id) REFERENCES games(id),
        FOREIGN KEY (scenario_id) REFERENCES scenarios(id)
    )
    """)

    # Миграция: добавляем scenario_id, если его нет
    try:
        cur.execute("ALTER TABLE stories ADD COLUMN scenario_id INTEGER REFERENCES scenarios(id)")
    except sqlite3.OperationalError:
        pass  # Колонка уже есть

    cur.execute("""
    CREATE TABLE IF NOT EXISTS scenarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS format_screens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        text TEXT NOT NULL,
        order_num INTEGER DEFAULT 0,
        video_url TEXT
    )
    """)

    # Исправляем существующие сюжеты: если hidden NULL (старые записи), делаем видимым
    cur.execute("UPDATE stories SET hidden = 0 WHERE hidden IS NULL")
    
    conn.commit()
    conn.close()

    seed_format_screens()


def seed_demo_data():
    """Заполняет демо-данными для тестирования админки."""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM games")
    if cur.fetchone()[0] > 0:
        conn.close()
        return  # уже есть данные

    games = [
        ("Тайна особняка", "22.02.2026", "19:00", "ул. Ленина 50", "1500₽", "Детективная история в старом особняке", 12),
        ("Мафия: Екатеринбург", "23.02.2026", "20:00", "Бар «Подвал»", "800₽", "Классика жанра с ведущим", 16),
        ("Выживание в космосе", "25.02.2026", "18:30", "Квест-рум «Космос»", "2000₽", "Sci-fi ролевка на корабле", 8),
        ("Ромео и Джульетта 2.0", "28.02.2026", "19:00", "Театр «Драма»", "1200₽", "Современная интерпретация", 10),
        ("Ночной дозор", "01.03.2026", "21:00", "Тайная локация", "1000₽", "Тёмное городское фэнтези", 14),
    ]
    for g in games:
        cur.execute(
            """INSERT INTO games (name, game_date, game_time, place, price, description, limit_places, hidden)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (*g, 0),
        )
    cur.execute("UPDATE games SET hidden = 1 WHERE id = 4")  # одна скрытая для теста

    leads = [
        (111111, "ivan_quest", "Иван Петров", "+79001234567", 1, "Тайна особняка", 2, "Хочу с девушкой", "vk", "post", "feb", "new"),
        (222222, "maria_k", "Мария К.", None, 2, "Мафия: Екатеринбург", 4, "", "instagram", "story", "", "contacted"),
        (333333, "alex_ekb", "Алексей", "+79009876543", 3, "Выживание в космосе", 1, "Первый раз", "tg", "ads", "quest", "paid"),
        (444444, "anna_s", "Анна", "+79005550011", 1, "Тайна особняка", 2, "", "", "", "", "new"),
        (555555, "dmitry_v", "Дмитрий В.", "+79003332211", 2, "Мафия: Екатеринбург", 6, "Корпоратив", "yandex", "direct", "corp", "contacted"),
        (666666, "elena_ro", "Елена", None, 5, "Ночной дозор", 1, "Можно без опыта?", "vk", "group", "mar", "new"),
        (777777, "sergey_q", "Сергей", "+79001112233", 4, "Ромео и Джульетта 2.0", 2, "", "tg", "channel", "feb", "paid"),
        (888888, "olga_m", "Ольга М.", "+79007778899", 1, "Тайна особняка", 3, "День рождения", "", "", "", "new"),
    ]
    for l in leads:
        cur.execute(
            """INSERT INTO leads (tg_id, username, name, phone, game_id, game_name, participants_count, comment,
               utm_source, utm_medium, utm_campaign, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            l,
        )

    questions = [
        (999001, "curious_user", "Юзер Тестов", "Есть ли скидки для групп?"),
        (999002, "newbie_bot", "Новичок", "Можно прийти одному?"),
    ]
    for q in questions:
        cur.execute(
            "INSERT INTO questions (tg_id, username, name, question_text) VALUES (?, ?, ?, ?)",
            q,
        )

    # Scenarios & Stories
    scenarios = [
        ("Завещание Флинта", "Пиратская история с поиском сокровищ"),
        ("Где-то на Диком Западе", "Ковбои, шериф и ограбление банка"),
        ("Тайна «Восточного экспресса»", "Детектив в поезде"),
    ]
    
    for s in scenarios:
        cur.execute("INSERT INTO scenarios (name, description) VALUES (?, ?)", s)
        sid = cur.lastrowid
        
        # Добавляем по 3 сюжета в каждый сценарий
        for i in range(1, 4):
            title = f"Глава {i}: Начало истории {s[0]}"
            content = f"Это текст сюжетной линии {i} для сценария «{s[0]}». Здесь описывается завязка, развитие событий и интрига. Игрок должен погрузиться в атмосферу."
            cur.execute(
                """INSERT INTO stories (title, content, image_url, game_id, order_num, hidden, scenario_id)
                   VALUES (?, ?, ?, ?, ?, 0, ?)""",
                (title, content, "", None, i-1, sid),
            )

    conn.commit()
    conn.close()


# Games
def get_visible_games():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, game_date, game_time, place, price, description, limit_places "
        "FROM games WHERE hidden = 0 ORDER BY game_date, game_time"
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_all_games():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, game_date, game_time, place, price, description, limit_places, hidden "
        "FROM games ORDER BY game_date, game_time"
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_game(game_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM games WHERE id = ?", (game_id,))
    row = cur.fetchone()
    conn.close()
    return row


def add_game(name, game_date, game_time, place, price, description, limit_places):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO games (name, game_date, game_time, place, price, description, limit_places)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (name, game_date, game_time or "", place or "", price or "", description or "", limit_places or 0),
    )
    gid = cur.lastrowid
    conn.commit()
    conn.close()
    return gid


def update_game(gid, **kwargs):
    if not kwargs:
        return
    conn = get_conn()
    cur = conn.cursor()
    cols = list(kwargs.keys())
    vals = list(kwargs.values()) + [gid]
    sql = "UPDATE games SET " + ", ".join(f"{c}=?" for c in cols) + " WHERE id=?"
    cur.execute(sql, vals)
    conn.commit()
    conn.close()


def toggle_game_visibility(game_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE games SET hidden = 1 - hidden WHERE id = ?", (game_id,))
    cur.execute("SELECT hidden FROM games WHERE id = ?", (game_id,))
    h = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return h


def delete_game(game_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE leads SET game_id = NULL WHERE game_id = ?", (game_id,))
    cur.execute("DELETE FROM games WHERE id = ?", (game_id,))
    conn.commit()
    conn.close()


# Leads
def add_lead(
    tg_id,
    username,
    name,
    phone=None,
    game_id=None,
    game_name=None,
    participants_count=1,
    comment=None,
    utm_source=None,
    utm_medium=None,
    utm_campaign=None,
):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO leads (tg_id, username, name, phone, game_id, game_name, participants_count, comment,
           utm_source, utm_medium, utm_campaign) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            tg_id,
            username or "",
            name or "",
            phone or "",
            game_id,
            game_name or "",
            participants_count or 1,
            comment or "",
            utm_source or "",
            utm_medium or "",
            utm_campaign or "",
        ),
    )
    lid = cur.lastrowid
    conn.commit()
    conn.close()
    return lid


def get_leads(limit=100):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, tg_id, username, name, phone, game_name, participants_count, comment, status, created_at "
        "FROM leads ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


# Questions
def add_question(tg_id, username, name, question_text):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO questions (tg_id, username, name, question_text) VALUES (?, ?, ?, ?)",
        (tg_id, username or "", name or "", question_text),
    )
    qid = cur.lastrowid
    conn.commit()
    conn.close()
    return qid


# Settings
def get_setting(key: str, default="0"):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else default


def save_user_utm(tg_id: int, utm_source=None, utm_medium=None, utm_campaign=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO user_utm (tg_id, utm_source, utm_medium, utm_campaign) VALUES (?, ?, ?, ?)
           ON CONFLICT(tg_id) DO UPDATE SET utm_source=excluded.utm_source, utm_medium=excluded.utm_medium,
           utm_campaign=excluded.utm_campaign, updated_at=CURRENT_TIMESTAMP""",
        (tg_id, utm_source or "", utm_medium or "", utm_campaign or ""),
    )
    conn.commit()
    conn.close()


def get_user_utm(tg_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT utm_source, utm_medium, utm_campaign FROM user_utm WHERE tg_id = ?", (tg_id,))
    row = cur.fetchone()
    conn.close()
    return {"utm_source": row[0], "utm_medium": row[1], "utm_campaign": row[2]} if row else {}


def set_setting(key: str, value: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


# Stories
def get_visible_stories():
    """Получить видимые сюжеты."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, content, image_url, game_id, order_num "
        "FROM stories WHERE hidden = 0 ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_all_stories():
    """Получить все сюжеты для админки."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, content, image_url, game_id, order_num, hidden "
        "FROM stories ORDER BY order_num, created_at"
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_story(story_id: int):
    """Получить сюжет по ID."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM stories WHERE id = ?", (story_id,))
    row = cur.fetchone()
    conn.close()
    return row


def add_story(title, content, image_url=None, game_id=None, order_num=0, scenario_id=None):
    """Добавить новый сюжет."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO stories (title, content, image_url, game_id, order_num, hidden, scenario_id)
           VALUES (?, ?, ?, ?, ?, 0, ?)""",
        (title, content or "", image_url or "", game_id, order_num or 0, scenario_id),
    )
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return sid


def update_story(sid, **kwargs):
    """Обновить сюжет."""
    if not kwargs:
        return
    conn = get_conn()
    cur = conn.cursor()
    cols = list(kwargs.keys())
    vals = list(kwargs.values()) + [sid]
    sql = "UPDATE stories SET " + ", ".join(f"{c}=?" for c in cols) + " WHERE id=?"
    cur.execute(sql, vals)
    conn.commit()
    conn.close()


def toggle_story_visibility(story_id: int):
    """Переключить видимость сюжета."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE stories SET hidden = 1 - hidden WHERE id = ?", (story_id,))
    cur.execute("SELECT hidden FROM stories WHERE id = ?", (story_id,))
    h = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return h


def delete_story(story_id: int):
    """Удалить сюжет."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM stories WHERE id = ?", (story_id,))
    conn.commit()
    conn.close()


# --- Scenarios ---

def add_scenario(name, description=""):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO scenarios (name, description) VALUES (?, ?)", (name, description))
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return sid


def get_scenarios():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, description FROM scenarios ORDER BY created_at")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_scenario(sid):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, description FROM scenarios WHERE id = ?", (sid,))
    row = cur.fetchone()
    conn.close()
    return row


def update_scenario(sid, name, description):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE scenarios SET name = ?, description = ? WHERE id = ?", (name, description, sid))
    conn.commit()
    conn.close()


def delete_scenario(sid):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM stories WHERE scenario_id = ?", (sid,))
    cur.execute("DELETE FROM scenarios WHERE id = ?", (sid,))
    conn.commit()
    conn.close()


def get_stories_by_scenario(scenario_id):
    """Получить сюжеты конкретного сценария."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, content, image_url, game_id, order_num, hidden, scenario_id "
        "FROM stories WHERE scenario_id = ? ORDER BY order_num, created_at",
        (scenario_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


# --- Format Screens ---

def get_format_screens():
    conn = get_conn()
    cur = conn.cursor()
    # Проверяем наличие таблицы (на случай если миграция не прошла)
    try:
        cur.execute("SELECT id, title, text, video_url FROM format_screens ORDER BY order_num")
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        return []
    conn.close()
    return rows


def update_format_screen(sid, title, text, video_url=None):
    conn = get_conn()
    cur = conn.cursor()
    if video_url is not None:
        cur.execute("UPDATE format_screens SET title = ?, text = ?, video_url = ? WHERE id = ?", (title, text, video_url, sid))
    else:
        cur.execute("UPDATE format_screens SET title = ?, text = ? WHERE id = ?", (title, text, sid))
    conn.commit()
    conn.close()


def seed_format_screens():
    """Заполняет экраны формата, если пусто."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM format_screens")
        if cur.fetchone()[0] > 0:
            conn.close()
            return
    except sqlite3.OperationalError:
        conn.close()
        return

    # Данные из handlers/format_funnel.py
    screens = [
        ("Что за формат?", "Сюжетная игра (ролевой квест) — это как фильм, только ты внутри истории.\n\nТебе дают роль и цель, дальше события разворачиваются через общение и решения. Ведущий всё ведёт и помогает."),
        ("Не с кем?", "Если не с кем выбраться в люди — это идеальный формат.\n\nМожно прийти одному/одной: тебя мягко включат в игру, и компания появляется сама."),
        ("Знакомства без кринжа", "Здесь не нужно «знакомиться специально».\n\nЕсть сюжет и общая задача — разговор начинается сам, и всё получается естественно."),
        ("Надоело одно и то же", "Если устал(а) от «бар/кино/просто посидеть» — это другой уровень досуга.\n\nВместо фона — эмоции, интрига, смех и ощущение «вау, было не как обычно»."),
        ("Я не умею / я интроверт", "Никакого опыта не нужно. Не надо быть актёром и «играть роль».\n\nПравила простые, включиться можно спокойно — ведущий подскажет, как комфортно участвовать."),
        ("Хочу свою тусовку в ЕКБ", "Мы собираем комьюнити в Екатеринбурге: регулярные встречи и «свои» люди.\n\nМожно просто вступить в чат, познакомиться и выбрать удобную дату."),
        ("Готов(а) попробовать?", "Частая реакция после первой игры:\n«Пришёл(ла) без ожиданий — втянулся(ась) за 10 минут и ушёл(ла) с новыми знакомыми».\n\nГотов(а) попробовать? Выбирай: записаться на ближайшую игру или зайти в чат.")
    ]
    
    video_url = "https://www.youtube.com/watch?v=x3Ir917gDiM&list=PLDqVqfBsY9O-fPcm-pK-TpYWfnuJWSBFI"
    
    for i, (title, text) in enumerate(screens):
        v_url = video_url if i in [0, 1, 2] else None
        cur.execute(
            "INSERT INTO format_screens (title, text, order_num, video_url) VALUES (?, ?, ?, ?)",
            (title, text, i, v_url)
        )
    conn.commit()
    conn.close()
