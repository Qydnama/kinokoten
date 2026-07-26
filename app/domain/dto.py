from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class CinemaDTO:
    id: int
    name: str
    city_id: int
    address: str | None = None
    poster_url: str | None = None


@dataclass(frozen=True, slots=True)
class MovieDTO:
    id: int
    name: str
    name_rus: str | None = None
    name_origin: str | None = None
    premiere_date: date | None = None
    poster_url: str | None = None
    is_pre_sales: bool = False

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(n for n in (self.name, self.name_rus, self.name_origin) if n))


@dataclass(frozen=True, slots=True)
class SessionDTO:
    session_id: int
    cinema_id: int
    movie_id: int
    session_date: date
    hour: int
    minute: int
    hall_name: str | None = None
    language: str | None = None
    adult_price: int | None = None
    child_price: int | None = None
    student_price: int | None = None
    vip_price: int | None = None
    formats: tuple[str, ...] = field(default_factory=tuple)
    purchase_verified: bool = False

    @property
    def source_key(self) -> str:
        key = f"kino:{self.cinema_id}:{self.movie_id}:{self.session_id}"
        return f"{key}:sale-open" if self.purchase_verified else key

    @property
    def minimum_price(self) -> int | None:
        positive = [
            price
            for price in (
                self.adult_price,
                self.child_price,
                self.student_price,
                self.vip_price,
            )
            if price is not None and price > 0
        ]
        return min(positive) if positive else None


@dataclass(frozen=True, slots=True)
class MovieSessionsDTO:
    movie: MovieDTO
    sessions: tuple[SessionDTO, ...]


@dataclass(frozen=True, slots=True)
class CinemaScheduleDTO:
    cinema_id: int
    available_dates: tuple[date, ...]
    movies: tuple[MovieSessionsDTO, ...]


@dataclass(frozen=True, slots=True)
class MovieCandidate:
    movie: MovieDTO
    score: float
    matched_name: str
