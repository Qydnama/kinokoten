FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY app ./app
RUN uv sync --frozen --no-dev --no-editable

COPY alembic.ini ./
COPY alembic ./alembic

RUN groupadd --system bot \
    && useradd --system --gid bot --home-dir /app bot \
    && mkdir -p /app/data \
    && chown -R bot:bot /app

USER bot

CMD ["python", "-m", "app"]
