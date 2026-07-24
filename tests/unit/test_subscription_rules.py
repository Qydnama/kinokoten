from datetime import UTC, date, datetime

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.domain.dto import MovieDTO
from app.domain.enums import TrackingMode
from app.domain.exceptions import ValidationError
from app.domain.services.subscription_service import SubscriptionService


def settings() -> Settings:
    return Settings(
        telegram_bot_token=SecretStr("123:example"),
        admin_telegram_id=1,
        backup_send_to_admin=False,
    )


def test_rejects_invalid_range() -> None:
    service = SubscriptionService(settings())
    with pytest.raises(ValidationError):
        service.validate_dates(
            TrackingMode.DATE_RANGE,
            date(2026, 8, 3),
            date(2026, 8, 1),
            date(2026, 7, 24),
        )


def test_exact_date_requires_equal_dates() -> None:
    service = SubscriptionService(settings())
    with pytest.raises(ValidationError):
        service.validate_dates(
            TrackingMode.EXACT_DATE,
            date(2026, 8, 1),
            date(2026, 8, 2),
            date(2026, 7, 24),
        )


def test_first_available_expiration_uses_premiere() -> None:
    expiration = SubscriptionService.calculate_expiration(
        TrackingMode.FIRST_AVAILABLE,
        None,
        MovieDTO(id=1, name="Film", premiere_date=date(2026, 8, 1)),
        datetime(2026, 7, 24, tzinfo=UTC),
    )
    assert expiration == datetime(2026, 9, 15, tzinfo=UTC)
