from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.domain.dto import CinemaDTO, SessionDTO
from app.domain.enums import CinemaScope, SubscriptionStatus, TrackingMode
from app.domain.protocols import CinemaSource
from app.domain.services.catalog_service import CatalogService
from app.integrations.kino.exceptions import KinoError
from app.persistence.database import session_scope
from app.persistence.models import Subscription
from app.persistence.repositories.notifications import NotificationsRepository
from app.persistence.repositories.subscriptions import SubscriptionsRepository
from app.utils.dates import local_today, utc_now

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NotificationJob:
    notification_id: int
    subscription_id: int
    telegram_id: int
    movie_id: int
    movie_title: str
    target_date: date
    cinema_scope: CinemaScope
    cinemas: tuple[CinemaDTO, ...]
    sessions: tuple[SessionDTO, ...]


@dataclass(slots=True)
class WorkerHeartbeat:
    last_cycle_started_at: datetime | None = None
    last_cycle_finished_at: datetime | None = None
    last_cycle_error: str | None = None
    last_kino_success_at: datetime | None = None


GroupKey = tuple[int, date, date]
PURCHASE_CHECK_CONCURRENCY = 5


def group_subscriptions(
    subscriptions: list[Subscription],
    today: date,
    first_available_horizon_days: int,
) -> dict[GroupKey, list[Subscription]]:
    grouped: dict[GroupKey, list[Subscription]] = defaultdict(list)
    for subscription in subscriptions:
        if subscription.tracking_mode == TrackingMode.FIRST_AVAILABLE:
            start, end = today, today + timedelta(days=first_available_horizon_days)
        else:
            if subscription.date_from is None or subscription.date_to is None:
                continue
            start, end = subscription.date_from, subscription.date_to
        grouped[(subscription.city_id, start, end)].append(subscription)
    return dict(grouped)


class MonitoringService:
    def __init__(
        self,
        source: CinemaSource,
        catalog: CatalogService,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        heartbeat: WorkerHeartbeat,
    ) -> None:
        self._source = source
        self._catalog = catalog
        self._session_factory = session_factory
        self._settings = settings
        self.heartbeat = heartbeat
        self._cycle_lock = asyncio.Lock()
        self._purchase_check_semaphore = asyncio.Semaphore(PURCHASE_CHECK_CONCURRENCY)
        self._purchase_status_cache: dict[tuple[int, int], bool] = {}

    async def run_cycle(self) -> list[NotificationJob]:
        if self._cycle_lock.locked():
            logger.warning("monitor cycle skipped: previous cycle is still running")
            return []
        async with self._cycle_lock:
            started = utc_now()
            self._purchase_status_cache.clear()
            self.heartbeat.last_cycle_started_at = started
            self.heartbeat.last_cycle_error = None
            try:
                async with session_scope(self._session_factory) as session:
                    due = await SubscriptionsRepository(session).get_due(started)
                logger.info("monitor cycle started due=%s", len(due))
                jobs = await self._process_due(due)
                self.heartbeat.last_cycle_finished_at = utc_now()
                logger.info("monitor cycle finished notifications=%s", len(jobs))
                return jobs
            except Exception as exc:
                self.heartbeat.last_cycle_error = type(exc).__name__
                self.heartbeat.last_cycle_finished_at = utc_now()
                logger.exception("monitor cycle failed")
                return []

    async def _process_due(self, due: list[Subscription]) -> list[NotificationJob]:
        now = utc_now()
        today = local_today(self._settings.timezone)
        active: list[Subscription] = []
        for subscription in due:
            expires_at = subscription.expires_at
            if expires_at is not None and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at is not None and expires_at <= now:
                await self._mark_expired(subscription.id)
            elif subscription.status == SubscriptionStatus.PENDING_MOVIE:
                await self._check_pending(subscription)
            else:
                active.append(subscription)

        jobs: list[NotificationJob] = []
        groups = group_subscriptions(
            active,
            today,
            self._settings.first_available_horizon_days,
        )
        for (city_id, start, end), subscriptions in groups.items():
            try:
                movies = await self._source.find_movies(city_id, start, end)
                self.heartbeat.last_kino_success_at = utc_now()
                found_ids = {movie.id for movie in movies}
                for subscription in subscriptions:
                    if subscription.kino_movie_id in found_ids:
                        job = await self._build_job(subscription, start, end)
                        if job is not None:
                            jobs.append(job)
                    else:
                        await self._mark_success(subscription.id)
            except KinoError as exc:
                for subscription in subscriptions:
                    await self._mark_error(subscription.id, type(exc).__name__)
        return jobs

    async def _check_pending(self, subscription: Subscription) -> None:
        try:
            await self._catalog.get_movies(subscription.city_id, refresh=True)
            exact = await self._catalog.find_exact(subscription.city_id, subscription.raw_query)
            async with session_scope(self._session_factory) as session:
                current = await session.get(Subscription, subscription.id)
                if current is None:
                    return
                if exact is not None:
                    current.kino_movie_id = exact.id
                    current.movie_title = exact.name
                    current.movie_original_title = exact.name_origin
                    current.release_date = exact.premiere_date
                    current.status = SubscriptionStatus.WAITING_TICKETS
                    current.consecutive_errors = 0
                    current.last_success_at = utc_now()
                    current.next_check_at = utc_now()
                else:
                    self._schedule_success(current)
        except KinoError as exc:
            await self._mark_error(subscription.id, type(exc).__name__)

    async def _build_job(
        self,
        subscription: Subscription,
        start: date,
        end: date,
    ) -> NotificationJob | None:
        movie_id = subscription.kino_movie_id
        if movie_id is None:
            return None
        target_date = await self._first_matching_date(subscription.city_id, movie_id, start, end)
        if target_date is None:
            await self._mark_success(subscription.id)
            return None
        all_cinemas = await self._catalog.get_cinemas(subscription.city_id)
        selected_ids = {item.kino_cinema_id for item in subscription.selected_cinemas}
        cinemas = [
            cinema
            for cinema in all_cinemas
            if subscription.cinema_scope == CinemaScope.ALL or cinema.id in selected_ids
        ]
        sessions: list[SessionDTO] = []
        enrichment_failed = False
        enrichment_error_code = "KinoError"
        try:
            schedules = await asyncio.gather(
                *(self._source.get_cinema_sessions(cinema.id, target_date) for cinema in cinemas)
            )
            for schedule in schedules:
                for movie_group in schedule.movies:
                    if movie_group.movie.id == movie_id:
                        sessions.extend(movie_group.sessions)
        except KinoError as exc:
            enrichment_failed = True
            enrichment_error_code = type(exc).__name__
            logger.warning(
                "schedule enrichment failed subscription_id=%s",
                subscription.id,
            )
        if enrichment_failed:
            logger.warning(
                "cinema schedules unavailable; suppressing unverified notification "
                "subscription_id=%s cinema_scope=%s",
                subscription.id,
                subscription.cinema_scope,
            )
            await self._mark_error(subscription.id, enrichment_error_code)
            return None
        if sessions:
            sessions, availability_errors = await self._purchasable_sessions(
                subscription.city_id,
                sessions,
            )
            if availability_errors and not sessions:
                logger.warning(
                    "ticket availability could not be confirmed subscription_id=%s errors=%s",
                    subscription.id,
                    availability_errors,
                )
                await self._mark_error(subscription.id, "KinoTicketAvailabilityError")
                return None
        if not sessions and not enrichment_failed:
            logger.info(
                "movie exists but has no purchasable sessions in tracked cinemas "
                "subscription_id=%s "
                "cinema_ids=%s target_date=%s",
                subscription.id,
                sorted(cinema.id for cinema in cinemas),
                target_date,
            )
            await self._mark_success(subscription.id)
            return None
        async with session_scope(self._session_factory) as session:
            current = await session.get(Subscription, subscription.id)
            if current is None:
                return None
            notification = await NotificationsRepository(session).reserve(
                subscription.id,
                sessions,
                target_date,
            )
            if notification is None:
                self._schedule_success(current)
                return None
            self._schedule_success(current)
            return NotificationJob(
                notification_id=notification.id,
                subscription_id=subscription.id,
                telegram_id=subscription.user.telegram_id,
                movie_id=movie_id,
                movie_title=subscription.movie_title or subscription.raw_query,
                target_date=target_date,
                cinema_scope=subscription.cinema_scope,
                cinemas=tuple(cinemas),
                sessions=tuple(
                    sorted(sessions, key=lambda item: (item.cinema_id, item.hour, item.minute))
                ),
            )

    async def _purchasable_sessions(
        self,
        city_id: int,
        sessions: list[SessionDTO],
    ) -> tuple[list[SessionDTO], int]:
        results = await asyncio.gather(
            *(self._check_purchase_status(city_id, item) for item in sessions),
            return_exceptions=True,
        )
        purchasable: list[SessionDTO] = []
        errors = 0
        for session, result in zip(sessions, results, strict=True):
            if isinstance(result, BaseException):
                errors += 1
                logger.warning(
                    "ticket availability check failed city_id=%s session_id=%s error=%s",
                    city_id,
                    session.session_id,
                    type(result).__name__,
                )
            elif result:
                purchasable.append(replace(session, purchase_verified=True))
        return purchasable, errors

    async def _check_purchase_status(self, city_id: int, session: SessionDTO) -> bool:
        key = (city_id, session.session_id)
        cached = self._purchase_status_cache.get(key)
        if cached is not None:
            return cached
        async with self._purchase_check_semaphore:
            available = await self._source.is_session_purchasable(
                city_id,
                session.session_id,
            )
        self._purchase_status_cache[key] = available
        return available

    async def _first_matching_date(
        self,
        city_id: int,
        movie_id: int,
        start: date,
        end: date,
    ) -> date | None:
        current = start
        while current <= end:
            movies = await self._source.find_movies(city_id, current, current)
            if any(movie.id == movie_id for movie in movies):
                return current
            current += timedelta(days=1)
        return None

    async def _mark_expired(self, subscription_id: int) -> None:
        async with session_scope(self._session_factory) as session:
            subscription = await session.get(Subscription, subscription_id)
            if subscription is not None:
                subscription.status = SubscriptionStatus.EXPIRED

    async def _mark_success(self, subscription_id: int) -> None:
        async with session_scope(self._session_factory) as session:
            subscription = await session.get(Subscription, subscription_id)
            if subscription is not None:
                self._schedule_success(subscription)

    def _schedule_success(self, subscription: Subscription) -> None:
        now = utc_now()
        subscription.last_checked_at = now
        subscription.last_success_at = now
        subscription.consecutive_errors = 0
        subscription.last_error_code = None
        if subscription.status == SubscriptionStatus.ERROR:
            subscription.status = (
                subscription.status_before_error or SubscriptionStatus.WAITING_TICKETS
            )
            subscription.status_before_error = None
        subscription.next_check_at = now + timedelta(
            seconds=self._interval(subscription, now.date())
        )

    async def _mark_error(self, subscription_id: int, code: str) -> None:
        async with session_scope(self._session_factory) as session:
            subscription = await session.get(Subscription, subscription_id)
            if subscription is None:
                return
            subscription.last_checked_at = utc_now()
            subscription.consecutive_errors += 1
            subscription.last_error_code = code
            if subscription.consecutive_errors >= self._settings.max_consecutive_errors:
                if subscription.status != SubscriptionStatus.ERROR:
                    subscription.status_before_error = subscription.status
                subscription.status = SubscriptionStatus.ERROR
            delay = min(
                6 * 3600,
                self._interval(subscription, utc_now().date())
                * (2 ** min(subscription.consecutive_errors, 6)),
            )
            subscription.next_check_at = utc_now() + timedelta(seconds=delay)

    def _interval(self, subscription: Subscription, today: date) -> int:
        if subscription.status == SubscriptionStatus.PENDING_MOVIE:
            return self._settings.pending_movie_interval_seconds
        if subscription.tracking_mode == TrackingMode.FIRST_AVAILABLE:
            return self._settings.first_available_interval_seconds
        if subscription.date_from is not None:
            days = (subscription.date_from - today).days
            if days <= self._settings.near_date_days:
                return self._settings.near_date_interval_seconds
        return self._settings.far_date_interval_seconds
