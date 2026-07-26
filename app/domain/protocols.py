from datetime import date
from typing import Protocol

from app.domain.dto import CinemaDTO, CinemaScheduleDTO, MovieDTO


class CinemaSource(Protocol):
    async def get_cinemas(self, city_id: int) -> list[CinemaDTO]: ...

    async def get_soon_movies(self, city_id: int) -> list[MovieDTO]: ...

    async def find_movies(
        self,
        city_id: int,
        start_date: date,
        end_date: date,
    ) -> list[MovieDTO]: ...

    async def get_cinema_sessions(
        self,
        cinema_id: int,
        target_date: date,
    ) -> CinemaScheduleDTO: ...

    async def is_session_purchasable(self, city_id: int, session_id: int) -> bool: ...
