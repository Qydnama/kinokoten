from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bootstrap import AppContainer
from app.bot.keyboards.main_menu import main_menu_keyboard
from app.bot.texts import MAIN_MENU
from app.persistence.database import session_scope
from app.persistence.repositories.users import UsersRepository

router = Router(name=__name__)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, container: AppContainer) -> None:
    await state.clear()
    if message.from_user is None:
        return
    async with session_scope(container.session_factory) as session:
        await UsersRepository(session).upsert(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
    await message.answer(MAIN_MENU, reply_markup=main_menu_keyboard())


@router.message(F.text == "🎬 Отслеживать фильм")
async def menu_watch(message: Message, state: FSMContext) -> None:
    from app.bot.handlers.watch import begin_watch

    await begin_watch(message, state)


@router.message(F.text == "📋 Мои отслеживания")
async def menu_subscriptions(message: Message, container: AppContainer) -> None:
    from app.bot.handlers.subscriptions import show_subscriptions

    await show_subscriptions(message, container)
