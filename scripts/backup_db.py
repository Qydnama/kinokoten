from __future__ import annotations

import asyncio

from app.config import load_settings
from app.persistence.backup import create_sqlite_backup


async def run() -> None:
    settings = load_settings()
    settings.ensure_data_directories()
    path = await create_sqlite_backup(
        settings.database_url,
        settings.data_dir / "backups",
        settings.backup_keep_count,
    )
    print(path)


if __name__ == "__main__":
    asyncio.run(run())
