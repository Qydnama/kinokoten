from __future__ import annotations

import asyncio

import httpx

from app.config import load_settings
from app.integrations.kino.client import KinoKzClient
from app.utils.dates import local_today


async def run() -> None:
    settings = load_settings()
    async with httpx.AsyncClient(
        timeout=settings.kino_request_timeout_seconds,
        limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
    ) as http_client:
        source = KinoKzClient(
            http_client,
            base_url=settings.kino_base_url,
            max_retries=settings.kino_max_retries,
        )
        today = local_today(settings.timezone)
        cinemas = await source.get_cinemas(1)
        soon = await source.get_soon_movies(1)
        current = await source.find_movies(1, today, today)
        schedule_movies = 0
        if cinemas:
            schedule = await source.get_cinema_sessions(cinemas[0].id, today)
            schedule_movies = len(schedule.movies)
        print(
            {
                "city_id": 1,
                "cinemas": len(cinemas),
                "soon_movies": len(soon),
                "current_movies": len(current),
                "first_cinema_schedule_movies": schedule_movies,
            }
        )


if __name__ == "__main__":
    asyncio.run(run())
