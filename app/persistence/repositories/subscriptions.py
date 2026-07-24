from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.enums import (
    ACTIVE_SUBSCRIPTION_STATUSES,
    CinemaScope,
    SubscriptionStatus,
    TrackingMode,
)
from app.persistence.models import Subscription, SubscriptionCinema


@dataclass(frozen=True, slots=True)
class SubscriptionCreate:
    creation_key: str
    user_id: int
    raw_query: str
    city_id: int
    tracking_mode: TrackingMode
    cinema_scope: CinemaScope
    next_check_at: datetime
    expires_at: datetime
    kino_movie_id: int | None = None
    movie_title: str | None = None
    movie_original_title: str | None = None
    release_date: date | None = None
    date_from: date | None = None
    date_to: date | None = None
    selected_cinema_ids: tuple[int, ...] = ()


class SubscriptionsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_idempotent(self, data: SubscriptionCreate) -> tuple[Subscription, bool]:
        existing = await self._session.scalar(
            select(Subscription).where(Subscription.creation_key == data.creation_key)
        )
        if existing is not None:
            return existing, False
        status = (
            SubscriptionStatus.WAITING_TICKETS
            if data.kino_movie_id is not None
            else SubscriptionStatus.PENDING_MOVIE
        )
        subscription = Subscription(
            creation_key=data.creation_key,
            user_id=data.user_id,
            kino_movie_id=data.kino_movie_id,
            movie_title=data.movie_title,
            movie_original_title=data.movie_original_title,
            raw_query=data.raw_query,
            release_date=data.release_date,
            city_id=data.city_id,
            tracking_mode=data.tracking_mode,
            date_from=data.date_from,
            date_to=data.date_to,
            cinema_scope=data.cinema_scope,
            status=status,
            next_check_at=data.next_check_at,
            expires_at=data.expires_at,
        )
        self._session.add(subscription)
        await self._session.flush()
        if data.cinema_scope == CinemaScope.SELECTED:
            self._session.add_all(
                [
                    SubscriptionCinema(
                        subscription_id=subscription.id,
                        kino_cinema_id=cinema_id,
                    )
                    for cinema_id in data.selected_cinema_ids
                ]
            )
        return subscription, True

    async def list_for_user(self, telegram_id: int) -> list[Subscription]:
        result = await self._session.scalars(
            select(Subscription)
            .join(Subscription.user)
            .where(Subscription.user.has(telegram_id=telegram_id))
            .where(Subscription.status != SubscriptionStatus.CANCELLED)
            .options(selectinload(Subscription.selected_cinemas))
            .order_by(Subscription.created_at.desc())
        )
        return list(result.unique().all())

    async def get_owned(self, subscription_id: int, telegram_id: int) -> Subscription | None:
        return cast(
            Subscription | None,
            await self._session.scalar(
                select(Subscription)
                .where(Subscription.id == subscription_id)
                .where(Subscription.user.has(telegram_id=telegram_id))
                .options(selectinload(Subscription.selected_cinemas))
            ),
        )

    async def get_due(self, now: datetime) -> list[Subscription]:
        result = await self._session.scalars(
            select(Subscription)
            .where(Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES))
            .where(Subscription.next_check_at <= now)
            .options(selectinload(Subscription.selected_cinemas), selectinload(Subscription.user))
            .order_by(Subscription.next_check_at)
        )
        return list(result.unique().all())

    async def set_status_owned(
        self,
        subscription_id: int,
        telegram_id: int,
        status: SubscriptionStatus,
    ) -> bool:
        subscription = await self.get_owned(subscription_id, telegram_id)
        if subscription is None:
            return False
        subscription.status = status
        return True
