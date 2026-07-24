from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks import CinemaScopeCallback, DraftActionCallback, ModeCallback
from app.domain.enums import CinemaScope, TrackingMode


def tracking_modes_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Первые доступные билеты",
                    callback_data=ModeCallback(mode=TrackingMode.FIRST_AVAILABLE).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="На конкретную дату",
                    callback_data=ModeCallback(mode=TrackingMode.EXACT_DATE).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="В диапазоне дат",
                    callback_data=ModeCallback(mode=TrackingMode.DATE_RANGE).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data=DraftActionCallback(action="cancel").pack(),
                )
            ],
        ]
    )


def cinema_scope_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Все кинотеатры города",
                    callback_data=CinemaScopeCallback(scope=CinemaScope.ALL).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="Выбрать кинотеатры",
                    callback_data=CinemaScopeCallback(scope=CinemaScope.SELECTED).pack(),
                )
            ],
        ]
    )


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Начать отслеживание",
                    callback_data=DraftActionCallback(action="confirm").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data=DraftActionCallback(action="cancel").pack(),
                )
            ],
        ]
    )
