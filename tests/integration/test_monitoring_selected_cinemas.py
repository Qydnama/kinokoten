from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Settings
from app.domain.dto import (
    CinemaDTO,
    CinemaScheduleDTO,
    MovieDTO,
    MovieSessionsDTO,
    SessionDTO,
)
from app.domain.enums import CinemaScope, SubscriptionStatus, TrackingMode
from app.domain.services.catalog_service import CatalogService
from app.domain.services.monitoring_service import MonitoringService, WorkerHeartbeat
from app.domain.services.notification_service import NotificationService
from app.domain.services.title_matcher import TitleMatcher
from app.integrations.kino.exceptions import KinoUnavailableError
from app.persistence.database import session_scope
from app.persistence.models import Notification, Subscription
from app.persistence.repositories.subscriptions import (
    SubscriptionCreate,
    SubscriptionsRepository,
)
from app.persistence.repositories.users import UsersRepository


class SelectedCinemasWithoutMovieSource:
    async def get_cinemas(self, city_id: int) -> list[CinemaDTO]:
        return [
            CinemaDTO(id=10, name="Kinopark Keruen", city_id=city_id),
            CinemaDTO(id=11, name="Kinopark Saryarka", city_id=city_id),
            CinemaDTO(id=12, name="Kinopark Talant Towers", city_id=city_id),
        ]

    async def get_soon_movies(self, city_id: int) -> list[MovieDTO]:
        return []

    async def find_movies(
        self,
        city_id: int,
        start_date: date,
        end_date: date,
    ) -> list[MovieDTO]:
        return [MovieDTO(id=100, name="Одиссея")]

    async def get_cinema_sessions(
        self,
        cinema_id: int,
        target_date: date,
    ) -> CinemaScheduleDTO:
        return CinemaScheduleDTO(
            cinema_id=cinema_id,
            available_dates=(target_date,),
            movies=(),
        )

    async def is_session_purchasable(self, city_id: int, session_id: int) -> bool:
        return False


class SelectedCinemasUnavailableSource(SelectedCinemasWithoutMovieSource):
    async def get_cinema_sessions(
        self,
        cinema_id: int,
        target_date: date,
    ) -> CinemaScheduleDTO:
        raise KinoUnavailableError("temporary schedule failure")


class SessionsAvailabilitySource(SelectedCinemasWithoutMovieSource):
    def __init__(
        self,
        purchasable_session_ids: set[int],
        *,
        fail_availability: bool = False,
    ) -> None:
        self.purchasable_session_ids = purchasable_session_ids
        self.fail_availability = fail_availability

    async def get_cinema_sessions(
        self,
        cinema_id: int,
        target_date: date,
    ) -> CinemaScheduleDTO:
        sessions: tuple[SessionDTO, ...] = ()
        if cinema_id == 10:
            sessions = (
                SessionDTO(
                    session_id=1,
                    cinema_id=cinema_id,
                    movie_id=100,
                    session_date=target_date,
                    hour=18,
                    minute=0,
                ),
                SessionDTO(
                    session_id=2,
                    cinema_id=cinema_id,
                    movie_id=100,
                    session_date=target_date,
                    hour=20,
                    minute=30,
                ),
            )
        return CinemaScheduleDTO(
            cinema_id=cinema_id,
            available_dates=(target_date,),
            movies=(
                MovieSessionsDTO(
                    movie=MovieDTO(id=100, name="Одиссея"),
                    sessions=sessions,
                ),
            ),
        )

    async def is_session_purchasable(self, city_id: int, session_id: int) -> bool:
        if self.fail_availability:
            raise KinoUnavailableError("temporary ticket availability failure")
        return session_id in self.purchasable_session_ids


async def create_due_subscription(
    factory: async_sessionmaker[AsyncSession],
    target_date: date,
    creation_key: str,
) -> Subscription:
    async with session_scope(factory) as session:
        user = await UsersRepository(session).upsert(
            telegram_id=123,
            username=None,
            first_name="Test",
        )
        await SubscriptionsRepository(session).create_idempotent(
            SubscriptionCreate(
                creation_key=creation_key,
                user_id=user.id,
                raw_query="Одиссея",
                city_id=1,
                tracking_mode=TrackingMode.EXACT_DATE,
                cinema_scope=CinemaScope.SELECTED,
                next_check_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(days=4),
                kino_movie_id=100,
                movie_title="Одиссея",
                date_from=target_date,
                date_to=target_date,
                selected_cinema_ids=(10, 11),
            )
        )
    async with session_scope(factory) as session:
        due = await SubscriptionsRepository(session).get_due(datetime.now(UTC))
    return due[0]


@pytest.mark.parametrize(
    "source",
    [SelectedCinemasWithoutMovieSource(), SelectedCinemasUnavailableSource()],
)
async def test_city_match_does_not_notify_when_selected_cinemas_have_no_sessions(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    source: SelectedCinemasWithoutMovieSource,
) -> None:
    _, factory = database
    target_date = date.today() + timedelta(days=3)
    async with session_scope(factory) as session:
        user = await UsersRepository(session).upsert(
            telegram_id=123,
            username=None,
            first_name="Test",
        )
        subscription, _ = await SubscriptionsRepository(session).create_idempotent(
            SubscriptionCreate(
                creation_key="selected-cinemas",
                user_id=user.id,
                raw_query="Одиссея",
                city_id=1,
                tracking_mode=TrackingMode.EXACT_DATE,
                cinema_scope=CinemaScope.SELECTED,
                next_check_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(days=4),
                kino_movie_id=100,
                movie_title="Одиссея",
                date_from=target_date,
                date_to=target_date,
                selected_cinema_ids=(10, 11),
            )
        )
        subscription_id = subscription.id

    async with session_scope(factory) as session:
        due = await SubscriptionsRepository(session).get_due(datetime.now(UTC))
    settings = Settings(
        telegram_bot_token=SecretStr("123:example"),
        admin_telegram_id=1,
        backup_send_to_admin=False,
    )
    catalog = CatalogService(source, factory, settings, TitleMatcher())
    service = MonitoringService(source, catalog, factory, settings, WorkerHeartbeat())

    job = await service._build_job(due[0], target_date, target_date)

    async with session_scope(factory) as session:
        notification_count = await session.scalar(select(func.count(Notification.id)))
    assert job is None
    assert notification_count == 0
    assert due[0].id == subscription_id


async def test_schedule_then_open_sale_send_two_notifications(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    target_date = date.today() + timedelta(days=3)
    subscription = await create_due_subscription(factory, target_date, "two-stage-sales")
    source = SessionsAvailabilitySource(set())
    settings = Settings(
        telegram_bot_token=SecretStr("123:example"),
        admin_telegram_id=1,
        backup_send_to_admin=False,
    )
    service = MonitoringService(
        source,
        CatalogService(source, factory, settings, TitleMatcher()),
        factory,
        settings,
        WorkerHeartbeat(),
    )

    schedule_job = await service._build_job(subscription, target_date, target_date)

    assert schedule_job is not None
    assert not schedule_job.purchase_available
    assert [item.session_id for item in schedule_job.sessions] == [1, 2]
    assert all(not item.purchase_verified for item in schedule_job.sessions)

    bot = AsyncMock()
    bot.send_message.return_value = SimpleNamespace(message_id=777)
    notifier = NotificationService(bot, factory)
    assert await notifier.send(schedule_job)
    async with session_scope(factory) as session:
        stored = await session.get(Subscription, subscription.id)
        assert stored is not None
        assert stored.status == SubscriptionStatus.WAITING_TICKETS

    source.purchasable_session_ids = {2}
    sale_service = MonitoringService(
        source,
        CatalogService(source, factory, settings, TitleMatcher()),
        factory,
        settings,
        WorkerHeartbeat(),
    )
    sale_job = await sale_service._build_job(subscription, target_date, target_date)

    assert sale_job is not None
    assert sale_job.purchase_available
    assert [item.session_id for item in sale_job.sessions] == [2]
    assert sale_job.sessions[0].purchase_verified
    assert sale_job.sessions[0].source_key.endswith(":sale-open")
    assert await notifier.send(sale_job)
    async with session_scope(factory) as session:
        stored = await session.get(Subscription, subscription.id)
        assert stored is not None
        assert stored.status == SubscriptionStatus.NOTIFIED

    duplicate_service = MonitoringService(
        source,
        CatalogService(source, factory, settings, TitleMatcher()),
        factory,
        settings,
        WorkerHeartbeat(),
    )
    duplicate = await duplicate_service._build_job(subscription, target_date, target_date)
    assert duplicate is None


@pytest.mark.parametrize(
    "source",
    [
        SessionsAvailabilitySource(set()),
        SessionsAvailabilitySource(set(), fail_availability=True),
    ],
)
async def test_closed_or_unverifiable_sales_send_schedule_notification(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    source: SessionsAvailabilitySource,
) -> None:
    _, factory = database
    target_date = date.today() + timedelta(days=3)
    subscription = await create_due_subscription(
        factory,
        target_date,
        f"no-sale-{source.fail_availability}",
    )
    settings = Settings(
        telegram_bot_token=SecretStr("123:example"),
        admin_telegram_id=1,
        backup_send_to_admin=False,
    )
    service = MonitoringService(
        source,
        CatalogService(source, factory, settings, TitleMatcher()),
        factory,
        settings,
        WorkerHeartbeat(),
    )

    job = await service._build_job(subscription, target_date, target_date)

    async with session_scope(factory) as session:
        notification_count = await session.scalar(select(func.count(Notification.id)))
    assert job is not None
    assert not job.purchase_available
    assert [item.session_id for item in job.sessions] == [1, 2]
    assert notification_count == 1
