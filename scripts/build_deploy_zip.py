from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "kino-ticket-bot.zip"
EXCLUDED_DIRS = {
    ".git",
    ".github",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "data",
    "dist",
    "tests",
    "backups",
}
EXCLUDED_NAMES = {".env", ".env.example", ".coverage", "docker-compose.yml"}
EXCLUDED_SUFFIXES = {".db", ".log", ".pyc", ".pyo"}


def should_include(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    if path.name in EXCLUDED_NAMES or path.suffix in EXCLUDED_SUFFIXES:
        return False
    return path.is_file()


def build() -> Path:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.rglob("*")):
            if should_include(path):
                archive.write(path, path.relative_to(ROOT).as_posix())
    print(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    build()
