from datetime import UTC, date, datetime

from app.bot.handlers.subscriptions import format_subscription_text
from app.domain.enums import CinemaScope, SubscriptionStatus, TrackingMode
from app.persistence.models import Subscription


def test_subscription_card_contains_city_date_cinemas_and_checks() -> None:
    subscription = Subscription(
        id=42,
        creation_key="card",
        user_id=1,
        kino_movie_id=100,
        movie_title="Одиссея",
        raw_query="Одиссея",
        city_id=1,
        tracking_mode=TrackingMode.EXACT_DATE,
        date_from=date(2026, 7, 27),
        date_to=date(2026, 7, 27),
        cinema_scope=CinemaScope.SELECTED,
        status=SubscriptionStatus.WAITING_TICKETS,
        next_check_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        last_success_at=datetime(2026, 7, 24, 11, 55, tzinfo=UTC),
        expires_at=datetime(2026, 7, 28, tzinfo=UTC),
    )

    text = format_subscription_text(
        subscription,
        ["Kinopark Keruen", "Kinopark Saryarka"],
        "Asia/Almaty",
    )

    assert "Астана" in text
    assert "27 июля 2026" in text
    assert "Kinopark Keruen" in text
    assert "Kinopark Saryarka" in text
    assert "ожидаем билеты" in text
    assert "Следующая проверка" in text
