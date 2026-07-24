from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from app.bootstrap import AppContainer
from app.persistence.backup import create_sqlite_backup

router = Router(name=__name__)


@router.message(Command("health"))
async def health(message: Message, container: AppContainer) -> None:
    heartbeat = container.heartbeat
    await message.answer(
        "<b>Состояние</b>\n"
        f"Последний цикл: <code>{heartbeat.last_cycle_finished_at or 'ещё не было'}</code>\n"
        f"Последний успешный Kino.kz: "
        f"<code>{heartbeat.last_kino_success_at or 'ещё не было'}</code>\n"
        f"Ошибка цикла: <code>{heartbeat.last_cycle_error or 'нет'}</code>"
    )


@router.message(Command("backup"))
async def backup(message: Message, bot: Bot, container: AppContainer) -> None:
    if (
        container.settings.admin_telegram_id is None
        or message.from_user is None
        or message.from_user.id != container.settings.admin_telegram_id
    ):
        await message.answer("Команда доступна только администратору.")
        return
    path = await create_sqlite_backup(
        container.settings.database_url,
        container.settings.data_dir / "backups",
        container.settings.backup_keep_count,
    )
    await bot.send_document(
        message.chat.id,
        FSInputFile(path),
        caption="Согласованная резервная копия SQLite.",
    )
