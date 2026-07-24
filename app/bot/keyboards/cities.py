from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks import CityCallback
from app.integrations.kino.cities import CITIES


def cities_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index in range(0, len(CITIES), 2):
        rows.append(
            [
                InlineKeyboardButton(
                    text=city.name,
                    callback_data=CityCallback(city_id=city.id).pack(),
                )
                for city in CITIES[index : index + 2]
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)
