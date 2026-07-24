from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Settings
from app.domain.dto import CinemaDTO, CinemaScheduleDTO, MovieDTO
from app.domain.enums import CinemaScope, TrackingMode
from app.domain.services.catalog_service import CatalogService
from app.domain.services.monitoring_service import MonitoringService, WorkerHeartbeat
from app.domain.services.title_matcher import TitleMatcher
from app.integrations.kino.exceptions import KinoUnavailableError
from app.persistence.database import session_scope
from app.persistence.models import Notification
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


class SelectedCinemasUnavailableSource(SelectedCinemasWithoutMovieSource):
    async def get_cinema_sessions(
        self,
        cinema_id: int,
        target_date: date,
    ) -> CinemaScheduleDTO:
        raise KinoUnavailableError("temporary schedule failure")


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
