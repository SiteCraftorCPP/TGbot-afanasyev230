## TGbot afanasyev230

Минимальный телеграм‑бот на **aiogram 3** для записи на игры.

### Что уже готово для VPS

- `requirements.txt` — зависимости (`aiogram`, `python-dotenv`).
- `.env.example` — пример переменных окружения.
- `.gitignore` — скрывает `.env`, кеши и локальные БД.
- Точка входа: `main.py`.

### Как разворачивать на VPS

```bash
git clone <repo_url> tg-bot
cd tg-bot

python3 -m venv venv
source venv/bin/activate  # Windows на VPS: venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
nano .env  # вписать BOT_TOKEN, CHAT_LINK, OPERATOR_CHAT_ID и т.д.

python main.py
```

### Быстрый systemd‑юнит (Linux)

```ini
[Unit]
Description=TGbot afanasyev230
After=network.target

[Service]
WorkingDirectory=/var/www/tg-bot
ExecStart=/var/www/tg-bot/venv/bin/python main.py
Restart=always
User=www-data
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Сохранить как `/etc/systemd/system/tgbot.service`, затем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tgbot
```

---

### Follow-up и сбор данных для заказчика

**Две таблицы:**
1. **Подписки** — все, кто нажал /start (первый контакт). Таблица `subscriptions`.
2. **Заявки** — кто прошёл запись на игру или «Заказать квест на праздник». Таблицы `leads` и `holiday_orders`.

**Follow-up в админке (/admin → Follow-up):** выгрузка пользователей в CSV (tg_id, имя, активность, телефон), рассылка с текстом и/или медиа по фильтрам (всем / с заявкой / без заявки).

