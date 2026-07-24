#!/bin/sh
set -eu

# JustRunMy.App keeps the application's persistent volume at /app. The source
# code lives elsewhere in the image so that the volume cannot hide it.
: "${DATA_DIR:=/app}"
export DATA_DIR
mkdir -p "$DATA_DIR/backups"

# Preserve the database location used by the original ZIP deployment.
case "${DATABASE_URL:-}" in
    ""|"sqlite+aiosqlite:///./data.db")
        DATABASE_URL="sqlite+aiosqlite:////app/data.db"
        export DATABASE_URL
        ;;
esac

exec python -m app
