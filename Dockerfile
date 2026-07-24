FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/kinokoten/.venv/bin:$PATH"

WORKDIR /opt/kinokoten

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY app ./app
RUN uv sync --frozen --no-dev --no-editable

COPY alembic.ini ./
COPY alembic ./alembic
COPY docker-entrypoint.sh /usr/local/bin/kinokoten-entrypoint

RUN chmod +x /usr/local/bin/kinokoten-entrypoint

CMD ["kinokoten-entrypoint"]
