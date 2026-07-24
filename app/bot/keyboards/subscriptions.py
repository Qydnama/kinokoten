from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks import SubscriptionActionCallback
from app.domain.enums import SubscriptionStatus
from app.persistence.models import Subscription


def subscription_actions(subscription: Subscription) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if subscription.status == SubscriptionStatus.PAUSED:
        rows.append(
            [
                InlineKeyboardButton(
                    text="▶️ Возобновить",
                    callback_data=SubscriptionActionCallback(
                        action="resume",
                        subscription_id=subscription.id,
                    ).pack(),
                )
            ]
        )
    elif subscription.status not in {
        SubscriptionStatus.CANCELLED,
        SubscriptionStatus.EXPIRED,
    }:
        rows.append(
            [
                InlineKeyboardButton(
                    text="⏸ Приостановить",
                    callback_data=SubscriptionActionCallback(
                        action="pause",
                        subscription_id=subscription.id,
                    ).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="🗑 Завершить",
                callback_data=SubscriptionActionCallback(
                    action="cancel",
                    subscription_id=subscription.id,
                ).pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
