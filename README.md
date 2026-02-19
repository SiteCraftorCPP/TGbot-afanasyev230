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

**Follow-up в админке (/admin → Follow-up):** вкл/выкл рассылки, экспорт подписок и заявок в CSV.

**Интеграция с Google Sheets (обязательна для сдачи заказчику):**

1. Создать таблицу в [Google Sheets](https://sheets.google.com): два листа с именами **«Подписки»** и **«Заявки»**.
2. В [Google Cloud Console](https://console.cloud.google.com) создать проект → включить **Google Sheets API** → **APIs & Services → Credentials → Create Credentials → Service account** → создать ключ (JSON), скачать файл.
3. Открыть доступ к таблице: в Google Sheets нажать «Поделиться» и добавить email сервисного аккаунта (из JSON, поле `client_email`) с правом «Редактор».
4. В `.env` указать:
   - `GOOGLE_SHEET_ID` — ID таблицы из URL (`https://docs.google.com/spreadsheets/d/ЭТОТ_ID/edit`).
   - `GOOGLE_CREDENTIALS_PATH` — путь к скачанному JSON (например `credentials.json` в папке бота).
5. После этого при каждом /start строка добавляется в лист «Подписки», при каждой заявке (игра или квест на праздник) — в лист «Заявки». Таблицу можно сразу передать заказчику или открыть доступ по ссылке.

**Экспорт CSV (если Sheets не настроен):** в админке Follow-up — кнопки «Экспорт подписок» и «Экспорт заявок»; файлы можно открыть в Excel или загрузить в Sheets вручную.

