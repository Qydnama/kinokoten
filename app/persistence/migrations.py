from __future__ import annotations

import logging
from pathlib import Path

from alembic.config import Config

from alembic import command
from app.config import load_settings

logger = logging.getLogger(__name__)


def upgrade_database() -> None:
    settings = load_settings()
    settings.ensure_data_directories()
    project_root = Path(__file__).resolve().parents[2]
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")
    logger.info("migrations completed")
