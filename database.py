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
        FOREIGN KEY (game_id) REFERENCES games(id)
    )
    """)

    # Исправляем существующие сюжеты: если hidden NULL (старые записи), делаем видимым
    cur.execute("UPDATE stories SET hidden = 0 WHERE hidden IS NULL")
    
    conn.commit()
    conn.close()


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
        "FROM stories WHERE hidden = 0 ORDER BY created_at"
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


def add_story(title, content, image_url=None, game_id=None, order_num=0):
    """Добавить новый сюжет."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO stories (title, content, image_url, game_id, order_num, hidden)
           VALUES (?, ?, ?, ?, ?, 0)""",
        (title, content or "", image_url or "", game_id, order_num or 0),
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
