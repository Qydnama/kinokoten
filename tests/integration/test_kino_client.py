import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from app.integrations.kino.client import KinoKzClient
from app.integrations.kino.exceptions import KinoResponseError, KinoSchemaError

FIXTURES = Path(__file__).parents[1] / "fixtures"


def fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@respx.mock
async def test_parses_all_confirmed_procedures() -> None:
    respx.get("https://kino.kz/api/trpc/cinema.getCinemas").mock(
        return_value=httpx.Response(200, json=fixture("kino_cinemas.json"))
    )
    respx.get("https://kino.kz/api/trpc/sessions.getSoonMovies").mock(
        return_value=httpx.Response(200, json=fixture("kino_soon_movies.json"))
    )
    respx.get("https://kino.kz/api/trpc/sessions.findMovies").mock(
        return_value=httpx.Response(200, json=fixture("kino_find_movies_found.json"))
    )
    respx.get("https://kino.kz/api/trpc/cinema.getSessions").mock(
        return_value=httpx.Response(200, json=fixture("kino_cinema_sessions.json"))
    )
    async with httpx.AsyncClient() as http_client:
        client = KinoKzClient(http_client, max_retries=1)
        cinemas = await client.get_cinemas(1)
        soon = await client.get_soon_movies(1)
        movies = await client.find_movies(1, date(2026, 7, 24), date(2026, 7, 24))
        schedule = await client.get_cinema_sessions(144, date(2026, 7, 24))

    assert cinemas[0].id == 144
    assert soon[0].premiere_date == date(2026, 7, 26)
    assert movies[0].id == 12175
    assert schedule.movies[0].sessions[0].source_key == "kino:144:12175:6521857"


@respx.mock
async def test_retries_5xx_but_not_400(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("app.integrations.kino.client.asyncio.sleep", no_sleep)
    route = respx.get("https://kino.kz/api/trpc/sessions.findMovies").mock(
        side_effect=[
            httpx.Response(502, json={}),
            httpx.Response(200, json=fixture("kino_find_movies_empty.json")),
        ]
    )
    async with httpx.AsyncClient() as http_client:
        client = KinoKzClient(http_client, max_retries=2)
        assert await client.find_movies(1, date.today(), date.today()) == []
    assert route.call_count == 2

    bad_route = respx.get("https://kino.kz/api/trpc/sessions.getSoonMovies").mock(
        return_value=httpx.Response(400, json={})
    )
    async with httpx.AsyncClient() as http_client:
        client = KinoKzClient(http_client, max_retries=3)
        with pytest.raises(KinoResponseError):
            await client.get_soon_movies(1)
    assert bad_route.call_count == 1


@respx.mock
async def test_missing_required_field_raises_schema_error() -> None:
    respx.get("https://kino.kz/api/trpc/cinema.getCinemas").mock(
        return_value=httpx.Response(
            200,
            json={"result": {"data": {"json": [{"id": 1}]}}},
        )
    )
    async with httpx.AsyncClient() as http_client:
        with pytest.raises(KinoSchemaError):
            await KinoKzClient(http_client, max_retries=1).get_cinemas(1)
