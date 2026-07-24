from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks import DraftActionCallback, MovieCallback
from app.domain.dto import MovieCandidate


def movies_keyboard(candidates: list[MovieCandidate]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{candidate.movie.name} · {round(candidate.score)}%",
                callback_data=MovieCallback(movie_id=candidate.movie.id).pack(),
            )
        ]
        for candidate in candidates
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="Фильма ещё нет в каталоге",
                callback_data=MovieCallback(movie_id=0).pack(),
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
