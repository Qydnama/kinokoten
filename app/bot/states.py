from aiogram.fsm.state import State, StatesGroup


class WatchStates(StatesGroup):
    choose_city = State()
    enter_movie_query = State()
    choose_movie = State()
    choose_tracking_mode = State()
    choose_dates = State()
    choose_cinema_scope = State()
    choose_cinemas = State()
    confirm_subscription = State()
