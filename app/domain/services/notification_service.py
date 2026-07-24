from __future__ import annotations

import logging
from collections import defaultdict

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.dto import SessionDTO
from app.domain.enums import SubscriptionStatus
from app.domain.services.monitoring_service import NotificationJob
from app.integrations.kino.links import movie_url
from app.persistence.database import session_scope
from app.persistence.models import Subscription
from app.persistence.repositories.notifications import NotificationsRepository
from app.utils.dates import format_date_ru, utc_now
from app.utils.html import escape_html

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(
        self,
        bot: Bot,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._bot = bot
        self._session_factory = session_factory

    async def send(self, job: NotificationJob) -> bool:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Купить на Kino.kz", url=movie_url(job.movie_id))],
                [
                    InlineKeyboardButton(
                        text="Продолжить отслеживание",
                        callback_data=f"sa:continue:{job.subscription_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Завершить",
                        callback_data=f"sa:cancel:{job.subscription_id}",
                    )
                ],
            ]
        )
        try:
            message = await self._bot.send_message(
                job.telegram_id,
                self.format_message(job),
                reply_markup=keyboard,
            )
            async with session_scope(self._session_factory) as session:
                await NotificationsRepository(session).mark_sent(
                    job.notification_id,
                    message.message_id,
                )
                subscription = await session.get(Subscription, job.subscription_id)
                if subscription is not None:
                    subscription.status = SubscriptionStatus.NOTIFIED
                    subscription.notified_at = utc_now()
            logger.info(
                "notification sent subscription_id=%s notification_id=%s",
                job.subscription_id,
                job.notification_id,
            )
            return True
        except Exception as exc:
            async with session_scope(self._session_factory) as session:
                await NotificationsRepository(session).mark_failed(
                    job.notification_id,
                    type(exc).__name__,
                )
            logger.exception("notification failed subscription_id=%s", job.subscription_id)
            return False

    @staticmethod
    def format_message(job: NotificationJob) -> str:
        lines = [
            "🎟 <b>Билеты появились!</b>",
            "",
            f"«{escape_html(job.movie_title)}»",
            format_date_ru(job.target_date),
        ]
        cinema_names = {cinema.id: cinema.name for cinema in job.cinemas}
        grouped: dict[int, list[SessionDTO]] = defaultdict(list)
        for session in job.sessions:
            grouped[session.cinema_id].append(session)
        shown = 0
        for cinema_id, sessions in grouped.items():
            lines.extend(["", f"<b>{escape_html(cinema_names.get(cinema_id, 'Кинотеатр'))}:</b>"])
            for session in sessions:
                if shown >= 10:
                    break
                details = [f"{session.hour:02d}:{session.minute:02d}"]
                if session.hall_name:
                    details.append(escape_html(session.hall_name))
                if session.formats:
                    details.append(", ".join(session.formats))
                if session.language:
                    details.append(escape_html(session.language))
                if session.minimum_price is not None:
                    details.append(f"от {session.minimum_price:,} ₸".replace(",", " "))
                lines.append("• " + " · ".join(details))
                shown += 1
        remaining = len(job.sessions) - shown
        if remaining > 0:
            lines.extend(["", f"Ещё {remaining} сеанс(ов) доступны на Kino.kz."])
        if not job.sessions:
            lines.extend(["", "Продажа обнаружена. Подробное расписание доступно на Kino.kz."])
        return "\n".join(lines)
