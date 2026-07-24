from datetime import UTC, datetime

from app.bot.keyboards.subscriptions import subscription_actions
from app.domain.enums import CinemaScope, SubscriptionStatus, TrackingMode
from app.persistence.models import Subscription


def test_notified_subscription_can_continue_from_its_card() -> None:
    subscription = Subscription(
        id=42,
        creation_key="keyboard",
        user_id=1,
        raw_query="Одиссея",
        city_id=1,
        tracking_mode=TrackingMode.FIRST_AVAILABLE,
        cinema_scope=CinemaScope.ALL,
        status=SubscriptionStatus.NOTIFIED,
        next_check_at=datetime.now(UTC),
        expires_at=datetime(2027, 1, 1, tzinfo=UTC),
    )

    keyboard = subscription_actions(subscription)

    assert keyboard.inline_keyboard[0][0].text == "▶️ Продолжить отслеживание"
    assert keyboard.inline_keyboard[0][0].callback_data == "sa:continue:42"
