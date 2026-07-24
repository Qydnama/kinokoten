from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bootstrap import AppContainer
from app.bot.callbacks import (
    CinemaScopeCallback,
    CinemaToggleCallback,
    CityCallback,
    DraftActionCallback,
    ModeCallback,
    MovieCallback,
)
from app.bot.keyboards.cinemas import cinemas_keyboard
from app.bot.keyboards.cities import cities_keyboard
from app.bot.keyboards.main_menu import main_menu_keyboard
from app.bot.keyboards.movies import movies_keyboard
from app.bot.keyboards.tracking import (
    cinema_scope_keyboard,
    confirm_keyboard,
    tracking_modes_keyboard,
)
from app.bot.states import WatchStates
from app.domain.dto import CinemaDTO, MovieDTO
from app.domain.enums import CinemaScope, TrackingMode
from app.domain.exceptions import ValidationError
from app.integrations.kino.cities import CITY_BY_ID
from app.persistence.database import session_scope
from app.persistence.repositories.subscriptions import SubscriptionsRepository
from app.persistence.repositories.users import UsersRepository
from app.utils.dates import format_date_ru, local_today
from app.utils.html import escape_html

router = Router(name=__name__)


@router.message(Command("watch"))
async def watch_command(message: Message, state: FSMContext) -> None:
    await begin_watch(message, state)


async def begin_watch(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(WatchStates.choose_city)
    await state.update_data(draft_id=uuid.uuid4().hex)
    await message.answer("Выберите город:", reply_markup=cities_keyboard())


@router.callback_query(CityCallback.filter(), WatchStates.choose_city)
async def choose_city(
    query: CallbackQuery,
    callback_data: CityCallback,
    state: FSMContext,
    container: AppContainer,
) -> None:
    city = CITY_BY_ID.get(callback_data.city_id)
    if city is None or query.from_user is None:
        await query.answer("Неизвестный город", show_alert=True)
        return
    async with session_scope(container.session_factory) as session:
        users = UsersRepository(session)
        user = await users.upsert(
            telegram_id=query.from_user.id,
            username=query.from_user.username,
            first_name=query.from_user.first_name,
        )
        user.default_city_id = city.id
    await state.update_data(city_id=city.id, city_name=city.name)
    await state.set_state(WatchStates.enter_movie_query)
    await query.answer()
    if isinstance(query.message, Message):
        await query.message.edit_text(
            f"Город: <b>{escape_html(city.name)}</b>\n\nВведите название фильма:"
        )


@router.message(WatchStates.enter_movie_query)
async def enter_movie_query(
    message: Message,
    state: FSMContext,
    container: AppContainer,
) -> None:
    raw_query = (message.text or "").strip()
    if not raw_query or len(raw_query) > 200:
        await message.answer("Введите название длиной от 1 до 200 символов.")
        return
    data = await state.get_data()
    city_id = int(data["city_id"])
    await message.answer("Ищу похожие фильмы…")
    candidates = await container.catalog_service.search(city_id, raw_query)
    await state.update_data(raw_query=raw_query)
    await state.set_state(WatchStates.choose_movie)
    if candidates:
        await message.answer(
            "Выберите фильм или укажите, что его пока нет:",
            reply_markup=movies_keyboard(candidates),
        )
    else:
        await message.answer(
            "Похожих фильмов пока нет. Можно всё равно следить за названием.",
            reply_markup=movies_keyboard([]),
        )


@router.callback_query(MovieCallback.filter(), WatchStates.choose_movie)
async def choose_movie(
    query: CallbackQuery,
    callback_data: MovieCallback,
    state: FSMContext,
    container: AppContainer,
) -> None:
    data = await state.get_data()
    movie: MovieDTO | None = None
    if callback_data.movie_id:
        movies = await container.catalog_service.get_movies(int(data["city_id"]))
        movie = next((item for item in movies if item.id == callback_data.movie_id), None)
        if movie is None:
            await query.answer("Список фильмов обновился. Повторите поиск.", show_alert=True)
            return
    await state.update_data(
        movie_id=movie.id if movie else None,
        movie_name=movie.name if movie else None,
        movie_origin=movie.name_origin if movie else None,
        movie_premiere=movie.premiere_date.isoformat() if movie and movie.premiere_date else None,
    )
    await state.set_state(WatchStates.choose_tracking_mode)
    await query.answer()
    if isinstance(query.message, Message):
        title = movie.name if movie else str(data["raw_query"])
        await query.message.edit_text(
            f"Фильм: <b>{escape_html(title)}</b>\n\nКак отслеживать?",
            reply_markup=tracking_modes_keyboard(),
        )


@router.callback_query(ModeCallback.filter(), WatchStates.choose_tracking_mode)
async def choose_mode(
    query: CallbackQuery,
    callback_data: ModeCallback,
    state: FSMContext,
) -> None:
    try:
        mode = TrackingMode(callback_data.mode)
    except ValueError:
        await query.answer("Неизвестный режим", show_alert=True)
        return
    await state.update_data(tracking_mode=mode, date_from=None, date_to=None)
    await query.answer()
    if mode == TrackingMode.FIRST_AVAILABLE:
        await state.set_state(WatchStates.choose_cinema_scope)
        if isinstance(query.message, Message):
            await query.message.edit_text(
                "Какие кинотеатры учитывать?",
                reply_markup=cinema_scope_keyboard(),
            )
        return
    await state.set_state(WatchStates.choose_dates)
    prompt = (
        "Введите дату в формате <code>ГГГГ-ММ-ДД</code>."
        if mode == TrackingMode.EXACT_DATE
        else "Введите начало и конец: <code>ГГГГ-ММ-ДД ГГГГ-ММ-ДД</code>."
    )
    if isinstance(query.message, Message):
        await query.message.edit_text(prompt)


@router.message(WatchStates.choose_dates)
async def choose_dates(message: Message, state: FSMContext, container: AppContainer) -> None:
    data = await state.get_data()
    mode = TrackingMode(data["tracking_mode"])
    parts = (message.text or "").split()
    expected = 1 if mode == TrackingMode.EXACT_DATE else 2
    if len(parts) != expected:
        await message.answer("Проверьте формат даты.")
        return
    try:
        date_from = date.fromisoformat(parts[0])
        date_to = date_from if expected == 1 else date.fromisoformat(parts[1])
        container.subscription_service.validate_dates(
            mode,
            date_from,
            date_to,
            local_today(container.settings.timezone),
        )
    except (ValueError, ValidationError) as exc:
        await message.answer(f"Дата не подходит: {escape_html(str(exc))}")
        return
    await state.update_data(date_from=date_from.isoformat(), date_to=date_to.isoformat())
    await state.set_state(WatchStates.choose_cinema_scope)
    await message.answer("Какие кинотеатры учитывать?", reply_markup=cinema_scope_keyboard())


@router.callback_query(CinemaScopeCallback.filter(), WatchStates.choose_cinema_scope)
async def choose_scope(
    query: CallbackQuery,
    callback_data: CinemaScopeCallback,
    state: FSMContext,
    container: AppContainer,
) -> None:
    try:
        scope = CinemaScope(callback_data.scope)
    except ValueError:
        await query.answer("Неизвестный вариант", show_alert=True)
        return
    await state.update_data(cinema_scope=scope, selected_cinema_ids=[])
    await query.answer()
    if scope == CinemaScope.ALL:
        await show_confirmation(query, state)
        return
    data = await state.get_data()
    cinemas = await container.catalog_service.get_cinemas(int(data["city_id"]))
    await state.update_data(
        cinemas=[{"id": cinema.id, "name": cinema.name} for cinema in cinemas],
    )
    await state.set_state(WatchStates.choose_cinemas)
    if isinstance(query.message, Message):
        await query.message.edit_text(
            "Отметьте кинотеатры и нажмите «Готово»:",
            reply_markup=cinemas_keyboard(cinemas, set()),
        )


@router.callback_query(CinemaToggleCallback.filter(), WatchStates.choose_cinemas)
async def toggle_cinema(
    query: CallbackQuery,
    callback_data: CinemaToggleCallback,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    cinemas = [
        CinemaDTO(
            id=int(item["id"]),
            name=str(item["name"]),
            city_id=int(data["city_id"]),
        )
        for item in data["cinemas"]
    ]
    valid_ids = {cinema.id for cinema in cinemas}
    if callback_data.cinema_id not in valid_ids:
        await query.answer("Кинотеатр больше недоступен", show_alert=True)
        return
    selected = {int(value) for value in data.get("selected_cinema_ids", [])}
    if callback_data.cinema_id in selected:
        selected.remove(callback_data.cinema_id)
    else:
        selected.add(callback_data.cinema_id)
    await state.update_data(selected_cinema_ids=sorted(selected))
    await query.answer()
    if isinstance(query.message, Message):
        await query.message.edit_reply_markup(reply_markup=cinemas_keyboard(cinemas, selected))


@router.callback_query(DraftActionCallback.filter(F.action == "cinemas_done"))
async def cinemas_done(query: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("selected_cinema_ids"):
        await query.answer("Выберите хотя бы один кинотеатр", show_alert=True)
        return
    await query.answer()
    await show_confirmation(query, state)


async def show_confirmation(query: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(WatchStates.confirm_subscription)
    text = format_draft_summary(data, "<b>Проверьте отслеживание</b>")
    if isinstance(query.message, Message):
        await query.message.edit_text(text, reply_markup=confirm_keyboard())


def format_draft_summary(data: dict[str, Any], heading: str) -> str:
    title = data.get("movie_name") or data["raw_query"]
    mode = TrackingMode(data["tracking_mode"])
    date_from = date.fromisoformat(str(data["date_from"])) if data.get("date_from") else None
    date_to = date.fromisoformat(str(data["date_to"])) if data.get("date_to") else None
    mode_text = {
        TrackingMode.FIRST_AVAILABLE: "первые доступные билеты",
        TrackingMode.EXACT_DATE: (
            format_date_ru(date_from) if date_from is not None else "конкретная дата"
        ),
        TrackingMode.DATE_RANGE: (
            f"{format_date_ru(date_from)} — {format_date_ru(date_to)}"
            if date_from is not None and date_to is not None
            else "диапазон дат"
        ),
    }[mode]
    if data["cinema_scope"] == CinemaScope.ALL:
        cinema_text = "все кинотеатры города"
    else:
        selected_ids = {int(value) for value in data.get("selected_cinema_ids", [])}
        cinema_names = [
            str(cinema["name"])
            for cinema in data.get("cinemas", [])
            if int(cinema["id"]) in selected_ids
        ]
        cinema_text = "\n".join(f"• {escape_html(name)}" for name in cinema_names)
    return (
        f"{heading}\n\n"
        f"Фильм: {escape_html(str(title))}\n"
        f"Город: {escape_html(str(data['city_name']))}\n"
        f"Когда: {escape_html(mode_text)}\n\n"
        f"<b>Кинотеатры:</b>\n{cinema_text}"
    )


@router.callback_query(
    DraftActionCallback.filter(F.action == "confirm"),
    WatchStates.confirm_subscription,
)
async def confirm(
    query: CallbackQuery,
    state: FSMContext,
    container: AppContainer,
) -> None:
    data = await state.get_data()
    async with session_scope(container.session_factory) as session:
        users = UsersRepository(session)
        user = await users.upsert(
            telegram_id=query.from_user.id,
            username=query.from_user.username,
            first_name=query.from_user.first_name,
        )
        movie: MovieDTO | None = None
        movie_id = data.get("movie_id")
        if movie_id:
            movies = await container.catalog_service.get_movies(int(data["city_id"]))
            movie = next((item for item in movies if item.id == int(movie_id)), None)
        subscription, created = await container.subscription_service.create(
            SubscriptionsRepository(session),
            creation_key=str(data["draft_id"]),
            user_id=user.id,
            raw_query=str(data["raw_query"]),
            city_id=int(data["city_id"]),
            tracking_mode=TrackingMode(data["tracking_mode"]),
            cinema_scope=CinemaScope(data["cinema_scope"]),
            movie=movie,
            date_from=date.fromisoformat(data["date_from"]) if data.get("date_from") else None,
            date_to=date.fromisoformat(data["date_to"]) if data.get("date_to") else None,
            selected_cinema_ids=tuple(int(value) for value in data.get("selected_cinema_ids", [])),
        )
    summary = format_draft_summary(
        data,
        (
            f"✅ <b>{'Отслеживание создано' if created else 'Отслеживание уже было создано'}</b>"
            f"\nНомер: <code>{subscription.id}</code>"
        ),
    )
    await state.clear()
    await query.answer("Готово")
    if isinstance(query.message, Message):
        await query.message.edit_text(summary)


@router.callback_query(DraftActionCallback.filter(F.action == "cancel"))
async def cancel_callback(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await query.answer("Отменено")
    if isinstance(query.message, Message):
        await query.message.edit_text("Создание отслеживания отменено.")


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Текущий диалог отменён.", reply_markup=main_menu_keyboard())
