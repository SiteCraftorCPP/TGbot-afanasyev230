"""Логирует каждое действие пользователя (кроме админов) в user_events."""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from config import ADMIN_IDS
from database import log_user_event


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
            try:
                log_user_event(
                    user.id,
                    user.username,
                    user.first_name,
                    user.last_name,
                    event_type,
                )
            except Exception:
                pass

        return await handler(event, data)
