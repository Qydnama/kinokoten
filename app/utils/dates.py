from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(UTC)


def local_today(timezone_name: str) -> date:
    return datetime.now(ZoneInfo(timezone_name)).date()


def format_date_ru(value: date) -> str:
    months = (
        "",
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    )
    return f"{value.day} {months[value.month]} {value.year}"
