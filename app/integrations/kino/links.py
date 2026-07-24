from urllib.parse import urlparse


def movie_url(movie_id: int) -> str:
    if movie_id <= 0:
        raise ValueError("movie_id must be positive")
    return f"https://kino.kz/ru/movie/{movie_id}"


def session_url(movie_id: int, session_id: int) -> str:
    if movie_id <= 0 or session_id <= 0:
        raise ValueError("movie_id and session_id must be positive")
    return f"https://kino.kz/ru/movie/{movie_id}/tickets/{session_id}"


def is_allowed_purchase_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in {"kino.kz", "www.kino.kz"}
