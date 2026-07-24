from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bootstrap import AppContainer
from app.bot.callbacks import SubscriptionActionCallback
from app.bot.keyboards.subscriptions import subscription_actions
from app.domain.enums import SubscriptionStatus
from app.persistence.database import session_scope
from app.persistence.models import Subscription
from app.persistence.repositories.subscriptions import SubscriptionsRepository
from app.utils.html import escape_html

router = Router(name=__name__)


def _subscription_text(subscription: Subscription) -> str:
    title = subscription.movie_title or subscription.raw_query
    return (
        f"<b>#{subscription.id} · {escape_html(title)}</b>\n"
        f"Статус: <code>{subscription.status}</code>\n"
        f"Режим: <code>{subscription.tracking_mode}</code>"
    )


@router.message(Command("subscriptions"))
async def subscriptions_command(message: Message, container: AppContainer) -> None:
    await show_subscriptions(message, container)


async def show_subscriptions(message: Message, container: AppContainer) -> None:
    if message.from_user is None:
        return
    async with session_scope(container.session_factory) as session:
        subscriptions = await SubscriptionsRepository(session).list_for_user(message.from_user.id)
        if not subscriptions:
            await message.answer("У вас пока нет активных отслеживаний.")
            return
        for subscription in subscriptions[:20]:
            await message.answer(
                _subscription_text(subscription),
                reply_markup=subscription_actions(subscription),
            )


@router.callback_query(SubscriptionActionCallback.filter())
async def subscription_action(
    query: CallbackQuery,
    callback_data: SubscriptionActionCallback,
    container: AppContainer,
) -> None:
    async with session_scope(container.session_factory) as session:
        repository = SubscriptionsRepository(session)
        if callback_data.action == "pause":
            changed = await container.subscription_service.pause(
                repository,
                callback_data.subscription_id,
                query.from_user.id,
            )
        elif callback_data.action in {"resume", "continue"}:
            changed = await container.subscription_service.resume(
                repository,
                callback_data.subscription_id,
                query.from_user.id,
            )
        elif callback_data.action == "cancel":
            changed = await container.subscription_service.cancel(
                repository,
                callback_data.subscription_id,
                query.from_user.id,
            )
        else:
            changed = False
        subscription = await repository.get_owned(
            callback_data.subscription_id,
            query.from_user.id,
        )
    if not changed or subscription is None:
        await query.answer("Действие недоступно", show_alert=True)
        return
    await query.answer("Сохранено")
    if isinstance(query.message, Message):
        await query.message.edit_text(
            _subscription_text(subscription),
            reply_markup=subscription_actions(subscription)
            if subscription.status != SubscriptionStatus.CANCELLED
            else None,
        )
