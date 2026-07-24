from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from datetime import date
from typing import Any, TypeVar, cast

import httpx
from pydantic import TypeAdapter, ValidationError

from app.domain.dto import CinemaDTO, CinemaScheduleDTO, MovieDTO
from app.integrations.kino.exceptions import (
    KinoRateLimitError,
    KinoResponseError,
    KinoSchemaError,
    KinoUnavailableError,
)
from app.integrations.kino.mapper import map_cinema, map_movie, map_schedule
from app.integrations.kino.schemas import CinemaScheduleSchema, CinemaSchema, MovieSchema

logger = logging.getLogger(__name__)
T = TypeVar("T")


class KinoKzClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        base_url: str = "https://kino.kz",
        max_retries: int = 3,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries

    async def get_cinemas(self, city_id: int) -> list[CinemaDTO]:
        payload = await self._request("cinema.getCinemas", city_id, None)
        values = self._validate_list(payload, CinemaSchema)
        return [map_cinema(item) for item in values]

    async def get_soon_movies(self, city_id: int) -> list[MovieDTO]:
        payload = await self._request("sessions.getSoonMovies", city_id, None)
        values = self._validate_list(payload, MovieSchema)
        return [map_movie(item) for item in values]

    async def find_movies(
        self,
        city_id: int,
        start_date: date,
        end_date: date,
    ) -> list[MovieDTO]:
        payload = await self._request(
            "sessions.findMovies",
            city_id,
            {"startDate": start_date.isoformat(), "endDate": end_date.isoformat()},
        )
        values = self._validate_list(payload, MovieSchema)
        return [map_movie(item) for item in values]

    async def get_cinema_sessions(
        self,
        cinema_id: int,
        target_date: date,
    ) -> CinemaScheduleDTO:
        payload = await self._request(
            "cinema.getSessions",
            None,
            {"id": cinema_id, "filter_by": "movies", "date": target_date.isoformat()},
        )
        try:
            schedule = CinemaScheduleSchema.model_validate(payload)
        except ValidationError as exc:
            raise KinoSchemaError("Unexpected cinema.getSessions response") from exc
        return map_schedule(cinema_id, target_date, schedule)

    @staticmethod
    def _validate_list(payload: Any, schema: type[T]) -> list[T]:
        try:
            return TypeAdapter(list[schema]).validate_python(payload)  # type: ignore[valid-type]
        except ValidationError as exc:
            raise KinoSchemaError("Unexpected list response from Kino.kz") from exc

    async def _request(
        self,
        procedure: str,
        city_id: int | None,
        payload: dict[str, Any] | None,
    ) -> Any:
        params = {
            "input": json.dumps(
                {"json": payload},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        }
        headers = {
            "accept": "application/json",
            "x-trpc-source": "nextjs-react",
            "user-agent": "KinoTicketWatcher/1.0",
        }
        last_error: Exception | None = None
        last_status: int | None = None

        for attempt in range(1, self._max_retries + 1):
            started = time.monotonic()
            try:
                request = self._client.build_request(
                    "GET",
                    f"{self._base_url}/api/trpc/{procedure}",
                    params=params,
                    headers=headers,
                )
                if city_id is not None:
                    request.headers.pop("cookie", None)
                    request_cookies = httpx.Cookies(self._client.cookies)
                    request_cookies.set(
                        "city",
                        str(city_id),
                        domain="kino.kz",
                        path="/",
                    )
                    request_cookies.set_cookie_header(request)
                response = await self._client.send(request)
                last_status = response.status_code
                duration_ms = round((time.monotonic() - started) * 1000)
                logger.info(
                    "kino request procedure=%s status=%s duration_ms=%s attempt=%s",
                    procedure,
                    response.status_code,
                    duration_ms,
                    attempt,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self._max_retries:
                        await asyncio.sleep(self._retry_delay(attempt))
                        continue
                    break
                if response.status_code >= 400:
                    raise KinoResponseError(
                        f"Kino.kz returned HTTP {response.status_code} for {procedure}"
                    )
                content_type = response.headers.get("content-type", "").lower()
                if "application/json" not in content_type:
                    raise KinoResponseError("Kino.kz returned a non-JSON response")
                try:
                    document = response.json()
                    return document["result"]["data"]["json"]
                except (ValueError, KeyError, TypeError) as exc:
                    raise KinoSchemaError("Unexpected tRPC envelope from Kino.kz") from exc
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                logger.warning("kino connection error procedure=%s attempt=%s", procedure, attempt)
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay(attempt))
                    continue
                break

        if last_status == 429:
            raise KinoRateLimitError("Kino.kz rate limit persisted after retries")
        raise KinoUnavailableError("Kino.kz is unavailable after retries") from last_error

    @staticmethod
    def _retry_delay(attempt: int) -> float:
        return cast(
            float,
            min(4.0, 0.25 * (2 ** (attempt - 1))) + random.uniform(0.0, 0.15),
        )
