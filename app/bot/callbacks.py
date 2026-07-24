from aiogram.filters.callback_data import CallbackData


class CityCallback(CallbackData, prefix="city"):
    city_id: int


class MovieCallback(CallbackData, prefix="movie"):
    movie_id: int


class ModeCallback(CallbackData, prefix="mode"):
    mode: str


class CinemaScopeCallback(CallbackData, prefix="scope"):
    scope: str


class CinemaToggleCallback(CallbackData, prefix="ct"):
    cinema_id: int


class DraftActionCallback(CallbackData, prefix="draft"):
    action: str


class SubscriptionActionCallback(CallbackData, prefix="sa"):
    action: str
    subscription_id: int
