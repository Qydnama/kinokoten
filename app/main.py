from __future__ import annotations

import asyncio
import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.bootstrap import build_container
from app.bot.commands import set_commands
from app.bot.handlers import build_router
from app.bot.middlewares.private_mode import PrivateModeMiddleware
from app.bot.middlewares.throttling import ThrottlingMiddleware
from app.config import load_settings
from app.logging_config import configure_logging
from app.workers.scheduler import Scheduler

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    logger.info("startup: settings loaded")
    settings.ensure_data_directories()
    logger.info("startup: data directories ready")
    container = build_container(settings)
    logger.info("startup: application container built")
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.update.outer_middleware(PrivateModeMiddleware(settings))
    dispatcher.update.outer_middleware(ThrottlingMiddleware())
    dispatcher.include_router(build_router())
    scheduler = Scheduler(container)

    try:
        logger.info("startup: deleting Telegram webhook")
        await container.bot.delete_webhook(drop_pending_updates=False)
        logger.info("startup: setting Telegram commands")
        await set_commands(container.bot)
        logger.info("startup: starting scheduler")
        scheduler.start()
        logger.info("bot started")
        await dispatcher.start_polling(
            container.bot,
            container=container,
            tasks_concurrency_limit=50,
        )
    finally:
        await scheduler.stop()
        await container.close()
        logger.info("bot stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
