from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.persistence.database import sqlite_path_from_url


def _backup_sync(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with (
        sqlite3.connect(source) as source_connection,
        sqlite3.connect(destination) as destination_connection,
    ):
        source_connection.backup(destination_connection)


async def create_sqlite_backup(
    database_url: str,
    backup_dir: Path,
    keep_count: int,
) -> Path:
    source = sqlite_path_from_url(database_url)
    if not source.exists():
        raise FileNotFoundError(f"SQLite database not found: {source}")
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = backup_dir / f"bot-{timestamp}.db"
    await asyncio.to_thread(_backup_sync, source, destination)
    backups = sorted(backup_dir.glob("bot-*.db"), key=lambda item: item.stat().st_mtime)
    for old_backup in backups[:-keep_count]:
        old_backup.unlink(missing_ok=True)
    return destination
