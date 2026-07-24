from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class KinoModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class CinemaSchema(KinoModel):
    id: int
    name: str
    city_id: int
    address: str | None = None
    small_poster: str | None = None


class MovieSchema(KinoModel):
    id: int
    name: str
    name_rus: str | None = None
    name_origin: str | None = None
    premiere_kaz: datetime | date | None = None
    small_poster: str | None = None
    is_pre_sales: bool = False


class HallSchema(KinoModel):
    id: int | None = None
    name: str | None = None
    imax: bool = False
    laser: bool = False


class SessionSchema(KinoModel):
    id: int | None = None
    session_id: int
    cinema_id: int
    movie_id: int
    session_date: datetime | date
    hour: str | int = "0"
    minutes: str | int = "0"
    lang_label: str | None = None
    adult: int | None = None
    child: int | None = None
    student: int | None = None
    vip: int | None = None
    is_3_d: bool = Field(default=False, alias="is_3_d")
    is_atmos: bool = False
    is_imax: bool = False
    is_fdx: bool = False


class SessionItemSchema(KinoModel):
    session: SessionSchema
    hall: HallSchema | None = None


class MovieSessionGroupSchema(KinoModel):
    movie: MovieSchema
    items: list[SessionItemSchema] = Field(default_factory=list)


class CinemaScheduleSchema(KinoModel):
    available_dates: list[date] = Field(default_factory=list)
    sessions: list[MovieSessionGroupSchema] = Field(default_factory=list)
