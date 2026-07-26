from dataclasses import replace
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domain.dto import SessionDTO
from app.domain.enums import CinemaScope, TrackingMode
from app.persistence.database import session_scope
from app.persistence.repositories.notifications import NotificationsRepository
from app.persistence.repositories.subscriptions import (
    SubscriptionCreate,
    SubscriptionsRepository,
)
from app.persistence.repositories.users import UsersRepository


async def test_double_confirmation_is_idempotent(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with session_scope(factory) as session:
        user = await UsersRepository(session).upsert(
            telegram_id=100,
            username=None,
            first_name="Test",
        )
        data = SubscriptionCreate(
            creation_key="same-draft",
            user_id=user.id,
            raw_query="Одиссея",
            city_id=1,
            tracking_mode=TrackingMode.FIRST_AVAILABLE,
            cinema_scope=CinemaScope.ALL,
            next_check_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=30),
            kino_movie_id=10,
        )
        first, first_created = await SubscriptionsRepository(session).create_idempotent(data)
        second, second_created = await SubscriptionsRepository(session).create_idempotent(data)

    assert first.id == second.id
    assert first_created
    assert not second_created


async def test_session_dedupe_reserves_once(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with session_scope(factory) as session:
        user = await UsersRepository(session).upsert(
            telegram_id=100,
            username=None,
            first_name="Test",
        )
        subscription, _ = await SubscriptionsRepository(session).create_idempotent(
            SubscriptionCreate(
                creation_key="draft",
                user_id=user.id,
                raw_query="Одиссея",
                city_id=1,
                tracking_mode=TrackingMode.FIRST_AVAILABLE,
                cinema_scope=CinemaScope.ALL,
                next_check_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(days=30),
                kino_movie_id=10,
            )
        )
        session_dto = SessionDTO(
            session_id=500,
            cinema_id=20,
            movie_id=10,
            session_date=datetime.now(UTC).date(),
            hour=18,
            minute=0,
        )
        repository = NotificationsRepository(session)
        first = await repository.reserve(
            subscription.id,
            [session_dto],
            session_dto.session_date,
        )
        await session.flush()
        assert first is not None
        await repository.mark_sent(first.id, 777)
        second = await repository.reserve(
            subscription.id,
            [session_dto],
            session_dto.session_date,
        )
        verified = replace(session_dto, purchase_verified=True)
        verified_sale = await repository.reserve(
            subscription.id,
            [verified],
            verified.session_date,
        )

    assert second is None
    assert verified_sale is not None
