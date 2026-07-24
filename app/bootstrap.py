from __future__ import annotations

from dataclasses import dataclass

import httpx
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Settings
from app.domain.services.catalog_service import CatalogService
from app.domain.services.monitoring_service import MonitoringService, WorkerHeartbeat
from app.domain.services.notification_service import NotificationService
from app.domain.services.subscription_service import SubscriptionService
from app.domain.services.title_matcher import TitleMatcher
from app.integrations.kino.client import KinoKzClient
from app.persistence.database import create_database


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    http_client: httpx.AsyncClient
    bot: Bot
    cinema_source: KinoKzClient
    catalog_service: CatalogService
    subscription_service: SubscriptionService
    monitoring_service: MonitoringService
    notification_service: NotificationService
    heartbeat: WorkerHeartbeat

    async def close(self) -> None:
        await self.http_client.aclose()
        await self.engine.dispose()


def build_container(settings: Settings) -> AppContainer:
    engine, session_factory = create_database(settings.database_url)
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.kino_request_timeout_seconds),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        follow_redirects=False,
    )
    bot = Bot(
        token=settings.telegram_bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    source = KinoKzClient(
        http_client,
        base_url=settings.kino_base_url,
        max_retries=settings.kino_max_retries,
    )
    heartbeat = WorkerHeartbeat()
    catalog = CatalogService(
        source,
        session_factory,
        settings,
        TitleMatcher(),
    )
    subscriptions = SubscriptionService(settings)
    monitoring = MonitoringService(
        source,
        catalog,
        session_factory,
        settings,
        heartbeat,
    )
    notifications = NotificationService(bot, session_factory)
    return AppContainer(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        http_client=http_client,
        bot=bot,
        cinema_source=source,
        catalog_service=catalog,
        subscription_service=subscriptions,
        monitoring_service=monitoring,
        notification_service=notifications,
        heartbeat=heartbeat,
    )
