from datetime import UTC, date, datetime

from app.domain.enums import CinemaScope, SubscriptionStatus, TrackingMode
from app.domain.services.monitoring_service import group_subscriptions
from app.persistence.models import Subscription


def subscription(identifier: int, mode: TrackingMode, start: date | None) -> Subscription:
    return Subscription(
        id=identifier,
        creation_key=str(identifier),
        user_id=1,
        raw_query="Movie",
        city_id=1,
        tracking_mode=mode,
        date_from=start,
        date_to=start,
        cinema_scope=CinemaScope.ALL,
        status=SubscriptionStatus.WAITING_TICKETS,
        next_check_at=datetime.now(UTC),
        expires_at=datetime(2027, 1, 1, tzinfo=UTC),
    )


def test_groups_equal_city_and_dates() -> None:
    target = date(2026, 8, 1)
    items = [
        subscription(1, TrackingMode.EXACT_DATE, target),
        subscription(2, TrackingMode.EXACT_DATE, target),
        subscription(3, TrackingMode.FIRST_AVAILABLE, None),
    ]

    groups = group_subscriptions(items, date(2026, 7, 24), 120)

    assert len(groups) == 2
    assert len(groups[(1, target, target)]) == 2
