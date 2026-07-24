import pytest

from app.integrations.kino.links import is_allowed_purchase_url
from app.utils.normalization import normalize_title


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Ёлки!  ", "елки"),
        ("ОДИССЕЯ", "одиссея"),
        ("Человек-паук: Нет пути домой", "человек паук нет пути домой"),
        ("  Дюна\t2  ", "дюна 2"),
    ],
)
def test_normalize_title(raw: str, expected: str) -> None:
    assert normalize_title(raw) == expected


def test_only_kino_domain_is_allowed_for_purchase() -> None:
    assert is_allowed_purchase_url("https://kino.kz/ru/movie/12")
    assert not is_allowed_purchase_url("http://kino.kz/ru/movie/12")
    assert not is_allowed_purchase_url("https://kino.kz.evil.example/ru/movie/12")
