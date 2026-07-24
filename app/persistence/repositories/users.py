from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import User


class UsersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
    ) -> User:
        user = await self._session.scalar(select(User).where(User.telegram_id == telegram_id))
        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
            )
            self._session.add(user)
            await self._session.flush()
        else:
            user.username = username
            user.first_name = first_name
        return user

    async def set_city(self, telegram_id: int, city_id: int) -> None:
        user = await self._session.scalar(select(User).where(User.telegram_id == telegram_id))
        if user is None:
            raise LookupError("User not found")
        user.default_city_id = city_id

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return cast(
            User | None,
            await self._session.scalar(select(User).where(User.telegram_id == telegram_id)),
        )
