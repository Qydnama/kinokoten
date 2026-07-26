from datetime import date

from app.domain.dto import CinemaDTO, SessionDTO
from app.domain.enums import CinemaScope
from app.domain.services.monitoring_service import NotificationJob
from app.domain.services.notification_service import NotificationService


def test_notification_escapes_external_text_and_formats_price() -> None:
    job = NotificationJob(
        notification_id=1,
        subscription_id=2,
        telegram_id=3,
        movie_id=4,
        movie_title="<Одиссея>",
        target_date=date(2026, 7, 27),
        cinema_scope=CinemaScope.SELECTED,
        cinemas=(CinemaDTO(id=5, name="Cinema & Hall", city_id=1),),
        sessions=(
            SessionDTO(
                session_id=6,
                cinema_id=5,
                movie_id=4,
                session_date=date(2026, 7, 27),
                hour=18,
                minute=30,
                hall_name="Зал <3>",
                adult_price=4000,
                formats=("IMAX",),
            ),
        ),
    )

    text = NotificationService.format_message(job)

    assert "&lt;Одиссея&gt;" in text
    assert "Cinema &amp; Hall" in text
    assert "Отслеживаемые кинотеатры" in text
    assert "Продажа открыта" in text
    assert "от 4 000 ₸" in text
    assert "18:30" in text
