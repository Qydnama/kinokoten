import logging

from aiogram import Router
from aiogram.types import ErrorEvent

from app.bot.texts import GENERIC_ERROR

logger = logging.getLogger(__name__)
router = Router(name=__name__)


@router.errors()
async def error_handler(event: ErrorEvent) -> bool:
    logger.exception("unhandled update error", exc_info=event.exception)
    update = event.update
    if update.message is not None:
        await update.message.answer(GENERIC_ERROR)
    elif update.callback_query is not None:
        await update.callback_query.answer(GENERIC_ERROR, show_alert=True)
    return True
