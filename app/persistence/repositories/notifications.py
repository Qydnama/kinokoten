from __future__ import annotations

from datetime import date
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dto import SessionDTO
from app.domain.enums import NotificationStatus
from app.persistence.models import Notification, SeenSession
from app.utils.dates import utc_now


class NotificationsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def reserve(
        self,
        subscription_id: int,
        sessions: list[SessionDTO],
        fallback_date: date,
    ) -> Notification | None:
        if sessions:
            keys = sorted(session.source_key for session in sessions)
            dedupe_key = f"tickets:{subscription_id}:{'|'.join(keys)}"
            existing = cast(
                Notification | None,
                await self._session.scalar(
                    select(Notification).where(Notification.dedupe_key == dedupe_key)
                ),
            )
            if existing is not None:
                if existing.status == NotificationStatus.SENT:
                    return None
                existing.status = NotificationStatus.PENDING
                return existing
            unseen: list[SessionDTO] = []
            for session in sessions:
                exists = await self._session.scalar(
                    select(SeenSession.id).where(
                        SeenSession.subscription_id == subscription_id,
                        SeenSession.source_session_key == session.source_key,
                    )
                )
                if exists is None:
                    unseen.append(session)
            if not unseen:
                return None
        else:
            unseen = []
            dedupe_key = f"tickets:{subscription_id}:{fallback_date.isoformat()}:detected"
            existing = cast(
                Notification | None,
                await self._session.scalar(
                    select(Notification).where(Notification.dedupe_key == dedupe_key)
                ),
            )
            if existing is not None:
                if existing.status == NotificationStatus.SENT:
                    return None
                existing.status = NotificationStatus.PENDING
                return existing
        notification = Notification(
            subscription_id=subscription_id,
            dedupe_key=dedupe_key,
            status=NotificationStatus.PENDING,
        )
        self._session.add(notification)
        for session in unseen:
            self._session.add(
                SeenSession(
                    subscription_id=subscription_id,
                    source_session_key=session.source_key,
                    kino_session_id=session.session_id,
                    kino_cinema_id=session.cinema_id,
                    session_date=session.session_date,
                )
            )
        await self._session.flush()
        return notification

    async def mark_sent(self, notification_id: int, message_id: int) -> None:
        notification = await self._session.get(Notification, notification_id)
        if notification is None:
            raise LookupError("Notification not found")
        notification.status = NotificationStatus.SENT
        notification.telegram_message_id = message_id
        notification.sent_at = utc_now()

    async def mark_failed(self, notification_id: int, error: str) -> None:
        notification = await self._session.get(Notification, notification_id)
        if notification is None:
            raise LookupError("Notification not found")
        notification.status = NotificationStatus.FAILED
        notification.error_message = error[:1000]
