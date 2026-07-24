import sqlite3
from pathlib import Path

import pytest

from app.persistence.migrations import upgrade_database


def test_startup_creates_data_directory_and_applies_migrations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "nested" / "bot.db"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:example")
    monkeypatch.setenv("ADMIN_TELEGRAM_ID", "1")
    monkeypatch.setenv("BACKUP_SEND_TO_ADMIN", "false")
    monkeypatch.setenv("DATA_DIR", str(database_path.parent))
    monkeypatch.setenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{database_path.as_posix()}",
    )

    upgrade_database()

    assert database_path.exists()
    with sqlite3.connect(database_path) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert revision == ("682e4245ba46",)
