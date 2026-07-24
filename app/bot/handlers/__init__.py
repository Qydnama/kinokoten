from aiogram import Router

from app.bot.handlers.admin import router as admin_router
from app.bot.handlers.common import router as common_router
from app.bot.handlers.start import router as start_router
from app.bot.handlers.subscriptions import router as subscriptions_router
from app.bot.handlers.watch import router as watch_router


def build_router() -> Router:
    router = Router(name="root")
    router.include_routers(
        start_router,
        watch_router,
        subscriptions_router,
        admin_router,
        common_router,
    )
    return router
