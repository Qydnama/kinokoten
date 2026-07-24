from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap import AppContainer
from app.bot.callbacks import SubscriptionActionCallback
from app.bot.keyboards.subscriptions import subscription_actions
from app.domain.enums import CinemaScope, SubscriptionStatus, TrackingMode
from app.integrations.kino.cities import CITY_BY_ID
from app.persistence.database import session_scope
from app.persistence.models import Subscription
from app.persistence.repositories.catalog import CatalogRepository
from app.persistence.repositories.subscriptions import SubscriptionsRepository
from app.utils.dates import format_date_ru
from app.utils.html import escape_html

router = Router(name=__name__)

STATUS_LABELS = {
    SubscriptionStatus.PENDING_MOVIE: "фильм ещё не появился в каталоге",
    SubscriptionStatus.PENDING_CONFIRMATION: "нужно подтвердить найденный фильм",
    SubscriptionStatus.WAITING_TICKETS: "ожидаем билеты",
    SubscriptionStatus.NOTIFIED: "билеты найдены, проверка приостановлена",
    SubscriptionStatus.PAUSED: "приостановлено",
    SubscriptionStatus.EXPIRED: "срок отслеживания закончился",
    SubscriptionStatus.CANCELLED: "завершено",
    SubscriptionStatus.ERROR: "временная ошибка, проверки продолжатся",
}


def _format_datetime(value: datetime | None, timezone_name: str) -> str:
    if value is None:
        return "ещё не было"
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(ZoneInfo(timezone_name)).strftime("%d.%m.%Y %H:%M")


def _tracking_label(subscription: Subscription) -> str:
    if subscription.tracking_mode == TrackingMode.FIRST_AVAILABLE:
        return "первые доступные билеты"
    if subscription.tracking_mode == TrackingMode.EXACT_DATE and subscription.date_from:
        return format_date_ru(subscription.date_from)
    if subscription.date_from and subscription.date_to:
        return (
            f"с {format_date_ru(subscription.date_from)} по {format_date_ru(subscription.date_to)}"
        )
    return str(subscription.tracking_mode)


def format_subscription_text(
    subscription: Subscription,
    cinema_names: list[str],
    timezone_name: str,
) -> str:
    title = subscription.movie_title or subscription.raw_query
    city = CITY_BY_ID.get(subscription.city_id)
    city_name = city.name if city is not None else f"город #{subscription.city_id}"
    if subscription.cinema_scope == CinemaScope.ALL:
        cinemas = "все кинотеатры города"
    elif cinema_names:
        cinemas = "\n".join(f"• {escape_html(name)}" for name in cinema_names)
    else:
        cinemas = "выбранные кинотеатры (названия обновляются)"
    return (
        f"🎬 <b>#{subscription.id} · {escape_html(title)}</b>\n\n"
        f"Город: <b>{escape_html(city_name)}</b>\n"
        f"Дата: <b>{escape_html(_tracking_label(subscription))}</b>\n"
        f"Статус: <b>{STATUS_LABELS[subscription.status]}</b>\n\n"
        f"<b>Кинотеатры:</b>\n{cinemas}\n\n"
        f"Последняя успешная проверка: "
        f"<code>{_format_datetime(subscription.last_success_at, timezone_name)}</code>\n"
        f"Следующая проверка: "
        f"<code>{_format_datetime(subscription.next_check_at, timezone_name)}</code>"
    )


async def _cinema_names(
    session: AsyncSession,
    subscription: Subscription,
) -> list[str]:
    cinema_ids = {item.kino_cinema_id for item in subscription.selected_cinemas}
    cinemas = await CatalogRepository(session).get_cinemas_by_ids(cinema_ids)
    names_by_id = {cinema.kino_cinema_id: cinema.name for cinema in cinemas}
    return [
        names_by_id.get(cinema_id, f"Кинотеатр #{cinema_id}") for cinema_id in sorted(cinema_ids)
    ]


@router.message(Command("subscriptions"))
async def subscriptions_command(message: Message, container: AppContainer) -> None:
    await show_subscriptions(message, container)


async def show_subscriptions(message: Message, container: AppContainer) -> None:
    if message.from_user is None:
        return
    cards: list[tuple[Subscription, str]] = []
    async with session_scope(container.session_factory) as session:
        subscriptions = await SubscriptionsRepository(session).list_for_user(message.from_user.id)
        for subscription in subscriptions[:20]:
            names = await _cinema_names(session, subscription)
            cards.append(
                (
                    subscription,
                    format_subscription_text(
                        subscription,
                        names,
                        container.settings.timezone,
                    ),
                )
            )
    if not cards:
        await message.answer("У вас пока нет активных отслеживаний.")
        return
    for subscription, text in cards:
        await message.answer(text, reply_markup=subscription_actions(subscription))


@router.callback_query(SubscriptionActionCallback.filter())
async def subscription_action(
    query: CallbackQuery,
    callback_data: SubscriptionActionCallback,
    container: AppContainer,
) -> None:
    text: str | None = None
    subscription: Subscription | None = None
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
        if changed and subscription is not None:
            names = await _cinema_names(session, subscription)
            text = format_subscription_text(
                subscription,
                names,
                container.settings.timezone,
            )
    if not changed or subscription is None or text is None:
        await query.answer("Действие недоступно", show_alert=True)
        return
    await query.answer("Сохранено")
    if isinstance(query.message, Message):
        await query.message.edit_text(
            text,
            reply_markup=(
                subscription_actions(subscription)
                if subscription.status != SubscriptionStatus.CANCELLED
                else None
            ),
        )
