from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dto import CinemaDTO, MovieDTO
from app.persistence.models import Cinema, Movie
from app.utils.normalization import normalize_title


class CatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def sync_movies(self, movies: list[MovieDTO], synced_at: datetime) -> None:
        if not movies:
            return
        existing = {
            item.kino_movie_id: item
            for item in (
                await self._session.scalars(
                    select(Movie).where(Movie.kino_movie_id.in_([m.id for m in movies]))
                )
            ).all()
        }
        for dto in movies:
            model = existing.get(dto.id)
            values = {
                "name": dto.name,
                "name_rus": dto.name_rus,
                "name_origin": dto.name_origin,
                "normalized_names": [normalize_title(name) for name in dto.names],
                "premiere_date": dto.premiere_date,
                "poster_url": dto.poster_url,
                "is_pre_sales": dto.is_pre_sales,
                "last_synced_at": synced_at,
            }
            if model is None:
                self._session.add(Movie(kino_movie_id=dto.id, **values))
            else:
                for key, value in values.items():
                    setattr(model, key, value)

    async def sync_cinemas(self, cinemas: list[CinemaDTO], synced_at: datetime) -> None:
        if not cinemas:
            return
        existing = {
            item.kino_cinema_id: item
            for item in (
                await self._session.scalars(
                    select(Cinema).where(Cinema.kino_cinema_id.in_([c.id for c in cinemas]))
                )
            ).all()
        }
        for dto in cinemas:
            model = existing.get(dto.id)
            values = {
                "city_id": dto.city_id,
                "name": dto.name,
                "normalized_name": normalize_title(dto.name),
                "address": dto.address,
                "poster_url": dto.poster_url,
                "last_synced_at": synced_at,
            }
            if model is None:
                self._session.add(Cinema(kino_cinema_id=dto.id, **values))
            else:
                for key, value in values.items():
                    setattr(model, key, value)

    async def get_cinemas_by_ids(self, cinema_ids: set[int]) -> list[Cinema]:
        if not cinema_ids:
            return []
        result = await self._session.scalars(
            select(Cinema).where(Cinema.kino_cinema_id.in_(cinema_ids)).order_by(Cinema.name)
        )
        return list(result.all())
