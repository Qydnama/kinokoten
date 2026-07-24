from aiogram import Bot
from aiogram.types import BotCommand


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="watch", description="Создать отслеживание"),
            BotCommand(command="subscriptions", description="Мои отслеживания"),
            BotCommand(command="health", description="Состояние бота"),
            BotCommand(command="cancel", description="Отменить текущий диалог"),
        ]
    )
