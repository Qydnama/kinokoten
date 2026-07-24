from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks import CinemaToggleCallback, DraftActionCallback
from app.domain.dto import CinemaDTO


def cinemas_keyboard(
    cinemas: list[CinemaDTO],
    selected: set[int],
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=("✅ " if cinema.id in selected else "▫️ ") + cinema.name,
                callback_data=CinemaToggleCallback(cinema_id=cinema.id).pack(),
            )
        ]
        for cinema in cinemas[:30]
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="Готово",
                callback_data=DraftActionCallback(action="cinemas_done").pack(),
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="Отмена",
                callback_data=DraftActionCallback(action="cancel").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
