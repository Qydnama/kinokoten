from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from app.config import Settings
from app.domain.dto import MovieDTO
from app.domain.enums import CinemaScope, SubscriptionStatus, TrackingMode
from app.domain.exceptions import ValidationError
from app.persistence.models import Subscription
from app.persistence.repositories.subscriptions import (
    SubscriptionCreate,
    SubscriptionsRepository,
)
from app.utils.dates import utc_now


class SubscriptionService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def create(
        self,
        repository: SubscriptionsRepository,
        *,
        creation_key: str,
        user_id: int,
        raw_query: str,
        city_id: int,
        tracking_mode: TrackingMode,
        cinema_scope: CinemaScope,
        movie: MovieDTO | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        selected_cinema_ids: tuple[int, ...] = (),
    ) -> tuple[Subscription, bool]:
        now = utc_now()
        self.validate_dates(tracking_mode, date_from, date_to, now.date())
        if cinema_scope == CinemaScope.SELECTED and not selected_cinema_ids:
            raise ValidationError("Выберите хотя бы один кинотеатр")
        expires_at = self.calculate_expiration(tracking_mode, date_to, movie, now)
        return await repository.create_idempotent(
            SubscriptionCreate(
                creation_key=creation_key,
                user_id=user_id,
                raw_query=raw_query.strip(),
                city_id=city_id,
                tracking_mode=tracking_mode,
                cinema_scope=cinema_scope,
                next_check_at=now,
                expires_at=expires_at,
                kino_movie_id=movie.id if movie else None,
                movie_title=movie.name if movie else None,
                movie_original_title=movie.name_origin if movie else None,
                release_date=movie.premiere_date if movie else None,
                date_from=date_from,
                date_to=date_to,
                selected_cinema_ids=selected_cinema_ids,
            )
        )

    def validate_dates(
        self,
        mode: TrackingMode,
        date_from: date | None,
        date_to: date | None,
        today: date,
    ) -> None:
        if mode == TrackingMode.FIRST_AVAILABLE:
            if date_from is not None or date_to is not None:
                raise ValidationError("Для первых билетов даты не задаются")
            return
        if date_from is None or date_to is None:
            raise ValidationError("Выберите дату")
        if date_from < today:
            raise ValidationError("Нельзя отслеживать прошедшую дату")
        if date_to < date_from:
            raise ValidationError("Конец диапазона раньше начала")
        if mode == TrackingMode.EXACT_DATE and date_from != date_to:
            raise ValidationError("Для точной даты начало и конец должны совпадать")
        if (date_to - date_from).days + 1 > self._settings.date_range_max_days:
            raise ValidationError(
                f"Диапазон не может быть длиннее {self._settings.date_range_max_days} дней"
            )
        if date_to > today + timedelta(days=self._settings.date_selection_horizon_days):
            raise ValidationError("Дата находится за пределами доступного горизонта")

    @staticmethod
    def calculate_expiration(
        mode: TrackingMode,
        date_to: date | None,
        movie: MovieDTO | None,
        now: datetime,
    ) -> datetime:
        if mode in {TrackingMode.EXACT_DATE, TrackingMode.DATE_RANGE}:
            if date_to is None:
                raise ValidationError("Дата окончания обязательна")
            return datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=UTC)
        if movie is not None and movie.premiere_date is not None:
            expiry = movie.premiere_date + timedelta(days=45)
            return datetime.combine(expiry, time.min, tzinfo=UTC)
        return now + timedelta(days=180)

    @staticmethod
    async def pause(
        repository: SubscriptionsRepository, subscription_id: int, telegram_id: int
    ) -> bool:
        return await repository.set_status_owned(
            subscription_id, telegram_id, SubscriptionStatus.PAUSED
        )

    @staticmethod
    async def resume(
        repository: SubscriptionsRepository,
        subscription_id: int,
        telegram_id: int,
    ) -> bool:
        subscription = await repository.get_owned(subscription_id, telegram_id)
        if subscription is None:
            return False
        subscription.status = (
            SubscriptionStatus.WAITING_TICKETS
            if subscription.kino_movie_id is not None
            else SubscriptionStatus.PENDING_MOVIE
        )
        subscription.next_check_at = utc_now()
        return True

    @staticmethod
    async def cancel(
        repository: SubscriptionsRepository,
        subscription_id: int,
        telegram_id: int,
    ) -> bool:
        return await repository.set_status_owned(
            subscription_id, telegram_id, SubscriptionStatus.CANCELLED
        )
