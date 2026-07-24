from types import SimpleNamespace
from typing import Any, cast

from aiogram.types import TelegramObject, Update, User

from app.bot.middlewares.private_mode import PrivateModeMiddleware
from app.config import Settings


def make_settings(*, private_mode: bool, allowed_user_ids: frozenset[int]) -> Settings:
    return cast(
        Settings,
        SimpleNamespace(
            private_mode=private_mode,
            allowed_user_ids=allowed_user_ids,
        ),
    )


async def test_public_mode_allows_any_user() -> None:
    middleware = PrivateModeMiddleware(
        make_settings(private_mode=False, allowed_user_ids=frozenset())
    )
    event = Update(update_id=1)
    user = User(id=999_999, is_bot=False, first_name="Guest")
    handled: list[int] = []

    async def handler(_event: TelegramObject, data: dict[str, Any]) -> str:
        handled.append(data["event_from_user"].id)
        return "handled"

    result = await middleware(handler, event, {"event_from_user": user})

    assert result == "handled"
    assert handled == [user.id]


async def test_private_mode_blocks_user_outside_allowlist() -> None:
    middleware = PrivateModeMiddleware(
        make_settings(private_mode=True, allowed_user_ids=frozenset({123}))
    )
    event = Update(update_id=2)
    user = User(id=999_999, is_bot=False, first_name="Guest")
    handled = False

    async def handler(_event: TelegramObject, _data: dict[str, Any]) -> None:
        nonlocal handled
        handled = True

    result = await middleware(handler, event, {"event_from_user": user})

    assert result is None
    assert handled is False
