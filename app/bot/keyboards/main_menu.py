from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎬 Отслеживать фильм")],
            [KeyboardButton(text="📋 Мои отслеживания")],
        ],
        resize_keyboard=True,
    )
