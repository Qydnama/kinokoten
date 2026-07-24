from __future__ import annotations

import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "dist" / "kino-ticket-bot.zip"
REQUIRED = {
    "pyproject.toml",
    "uv.lock",
    "requirements.txt",
    "alembic.ini",
    "app/__main__.py",
    "alembic/env.py",
}
FORBIDDEN_PARTS = {
    ".env",
    ".git",
    ".venv",
    "__pycache__",
    "data",
    "dist",
    "tests",
    "backups",
}
TOKEN_PATTERN = re.compile(rb"\d{6,12}:[A-Za-z0-9_-]{30,}")


def inspect() -> None:
    with zipfile.ZipFile(ARCHIVE) as archive:
        names = set(archive.namelist())
        missing = REQUIRED - names
        if missing:
            raise RuntimeError(f"Archive misses required files: {sorted(missing)}")
        forbidden = [
            name for name in names if any(part in FORBIDDEN_PARTS for part in Path(name).parts)
        ]
        if forbidden:
            raise RuntimeError(f"Archive contains excluded paths: {forbidden[:5]}")
        for name in names:
            if TOKEN_PATTERN.search(archive.read(name)):
                raise RuntimeError(f"Possible Telegram token found in {name}")
    print(f"OK: {ARCHIVE} ({len(names)} files)")


if __name__ == "__main__":
    inspect()
