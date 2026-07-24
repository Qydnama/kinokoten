from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiogram.types import FSInputFile

from app.bootstrap import AppContainer
from app.persistence.backup import create_sqlite_backup

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, container: AppContainer) -> None:
        self._container = container
        self._tasks: list[asyncio.Task[None]] = []
        self._stop = asyncio.Event()

    def start(self) -> None:
        self._tasks = [asyncio.create_task(self._monitor_loop(), name="monitor-worker")]
        if (
            self._container.settings.backup_send_to_admin
            and self._container.settings.admin_telegram_id is not None
        ):
            self._tasks.append(asyncio.create_task(self._backup_loop(), name="backup-worker"))
        logger.info("worker started")

    async def stop(self) -> None:
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with suppress(asyncio.CancelledError):
                await task
        logger.info("worker stopped")

    async def _monitor_loop(self) -> None:
        while not self._stop.is_set():
            jobs = await self._container.monitoring_service.run_cycle()
            for job in jobs:
                await self._container.notification_service.send(job)
            await self._wait(self._container.settings.worker_tick_seconds)

    async def _backup_loop(self) -> None:
        await self._wait(self._container.settings.backup_interval_hours * 3600)
        while not self._stop.is_set():
            try:
                path = await create_sqlite_backup(
                    self._container.settings.database_url,
                    self._container.settings.data_dir / "backups",
                    self._container.settings.backup_keep_count,
                )
                admin_id = self._container.settings.admin_telegram_id
                if admin_id is not None:
                    await self._container.bot.send_document(
                        admin_id,
                        FSInputFile(path),
                        caption="Ежедневная резервная копия SQLite.",
                    )
                logger.info("daily backup sent")
            except Exception:
                logger.exception("daily backup failed")
            await self._wait(self._container.settings.backup_interval_hours * 3600)

    async def _wait(self, seconds: int) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except TimeoutError:
            return
