from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.domain.dto import CinemaDTO, MovieCandidate, MovieDTO
from app.domain.protocols import CinemaSource
from app.domain.services.title_matcher import TitleMatcher
from app.persistence.database import session_scope
from app.persistence.repositories.catalog import CatalogRepository
from app.utils.dates import local_today, utc_now


@dataclass(slots=True)
class _CacheEntry:
    expires_at_epoch: float
    movies: list[MovieDTO]


class CatalogService:
    def __init__(
        self,
        source: CinemaSource,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        matcher: TitleMatcher,
    ) -> None:
        self._source = source
        self._session_factory = session_factory
        self._settings = settings
        self._matcher = matcher
        self._movie_cache: dict[int, _CacheEntry] = {}
        self._cinema_cache: dict[int, tuple[float, list[CinemaDTO]]] = {}
        self._lock = asyncio.Lock()

    async def get_movies(self, city_id: int, *, refresh: bool = False) -> list[MovieDTO]:
        now_epoch = asyncio.get_running_loop().time()
        cached = self._movie_cache.get(city_id)
        if not refresh and cached is not None and cached.expires_at_epoch > now_epoch:
            return cached.movies
        async with self._lock:
            cached = self._movie_cache.get(city_id)
            if not refresh and cached is not None and cached.expires_at_epoch > now_epoch:
                return cached.movies
            today = local_today(self._settings.timezone)
            soon, current = await asyncio.gather(
                self._source.get_soon_movies(city_id),
                self._source.find_movies(
                    city_id,
                    today,
                    today + timedelta(days=self._settings.catalog_horizon_days),
                ),
            )
            by_id = {movie.id: movie for movie in [*soon, *current]}
            movies = sorted(by_id.values(), key=lambda item: item.name.casefold())
            async with session_scope(self._session_factory) as session:
                await CatalogRepository(session).sync_movies(movies, utc_now())
            self._movie_cache[city_id] = _CacheEntry(
                expires_at_epoch=now_epoch + self._settings.catalog_cache_seconds,
                movies=movies,
            )
            return movies

    async def search(self, city_id: int, query: str) -> list[MovieCandidate]:
        return self._matcher.find(query, await self.get_movies(city_id))

    async def find_exact(self, city_id: int, query: str) -> MovieDTO | None:
        return self._matcher.exact(query, await self.get_movies(city_id))

    async def get_cinemas(self, city_id: int, *, refresh: bool = False) -> list[CinemaDTO]:
        now_epoch = asyncio.get_running_loop().time()
        cached = self._cinema_cache.get(city_id)
        if not refresh and cached is not None and cached[0] > now_epoch:
            return cached[1]
        cinemas = await self._source.get_cinemas(city_id)
        async with session_scope(self._session_factory) as session:
            await CatalogRepository(session).sync_cinemas(cinemas, utc_now())
        self._cinema_cache[city_id] = (
            now_epoch + self._settings.catalog_cache_seconds,
            cinemas,
        )
        return cinemas
