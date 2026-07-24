from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.bot.texts import UNAUTHORIZED
from app.config import Settings


class PrivateModeMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if not self._settings.private_mode or (
            user is not None and user.id in self._settings.allowed_user_ids
        ):
            return await handler(event, data)
        if isinstance(event, Message):
            await event.answer(UNAUTHORIZED)
        elif isinstance(event, CallbackQuery):
            await event.answer(UNAUTHORIZED, show_alert=True)
        return None
