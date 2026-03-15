"""Логирует каждое действие пользователя (кроме админов) в user_events. В executor, чтобы не блокировать ответ бота."""
import asyncio
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from config import ADMIN_IDS
from database import log_user_event


def _log_user_event_sync(tg_id: int, username: str, first_name: str, last_name: str, event_type: str) -> None:
    try:
        log_user_event(tg_id, username, first_name, last_name, event_type)
    except Exception:
        pass


class UserLogMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = None
        event_type = ""
        if isinstance(event, Message):
            user = getattr(event, "from_user", None)
            if event.text:
                event_type = "msg:start" if event.text.startswith("/start") else "msg:text"
            elif event.photo:
                event_type = "msg:photo"
            else:
                event_type = "msg"
        elif isinstance(event, CallbackQuery):
            user = getattr(event, "from_user", None)
            event_type = "cb:" + (event.data[:80] if event.data else "?")

        if user and user.id not in ADMIN_IDS and event_type:
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                lambda: _log_user_event_sync(
                    user.id,
                    user.username or "",
                    user.first_name or "",
                    user.last_name or "",
                    event_type,
                ),
            )

        return await handler(event, data)
