from datetime import date, datetime

from app.domain.dto import (
    CinemaDTO,
    CinemaScheduleDTO,
    MovieDTO,
    MovieSessionsDTO,
    SessionDTO,
)
from app.integrations.kino.schemas import CinemaScheduleSchema, CinemaSchema, MovieSchema


def _as_date(value: date | datetime | None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value


def map_cinema(value: CinemaSchema) -> CinemaDTO:
    return CinemaDTO(
        id=value.id,
        name=value.name,
        city_id=value.city_id,
        address=value.address,
        poster_url=value.small_poster,
    )


def map_movie(value: MovieSchema) -> MovieDTO:
    return MovieDTO(
        id=value.id,
        name=value.name,
        name_rus=value.name_rus,
        name_origin=value.name_origin,
        premiere_date=_as_date(value.premiere_kaz),
        poster_url=value.small_poster,
        is_pre_sales=value.is_pre_sales,
    )


def map_schedule(
    cinema_id: int,
    target_date: date,
    value: CinemaScheduleSchema,
) -> CinemaScheduleDTO:
    movie_groups: list[MovieSessionsDTO] = []
    for group in value.sessions:
        sessions: list[SessionDTO] = []
        for item in group.items:
            raw = item.session
            hall = item.hall
            formats = []
            if raw.is_imax or (hall is not None and hall.imax):
                formats.append("IMAX")
            if raw.is_3_d:
                formats.append("3D")
            if raw.is_atmos:
                formats.append("Atmos")
            if raw.is_fdx:
                formats.append("4DX")
            if hall is not None and hall.laser:
                formats.append("Laser")
            sessions.append(
                SessionDTO(
                    session_id=raw.session_id,
                    cinema_id=raw.cinema_id,
                    movie_id=raw.movie_id,
                    session_date=_as_date(raw.session_date) or target_date,
                    hour=int(raw.hour),
                    minute=int(raw.minutes),
                    hall_name=hall.name if hall else None,
                    language=raw.lang_label,
                    adult_price=raw.adult,
                    child_price=raw.child,
                    student_price=raw.student,
                    vip_price=raw.vip,
                    formats=tuple(dict.fromkeys(formats)),
                )
            )
        movie_groups.append(
            MovieSessionsDTO(movie=map_movie(group.movie), sessions=tuple(sessions))
        )
    return CinemaScheduleDTO(
        cinema_id=cinema_id,
        available_dates=tuple(value.available_dates),
        movies=tuple(movie_groups),
    )
