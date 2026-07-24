from app.domain.dto import MovieDTO
from app.domain.services.title_matcher import TitleMatcher


def test_typo_returns_expected_candidate() -> None:
    movies = [
        MovieDTO(id=1, name="Одиссея", name_origin="The Odyssey"),
        MovieDTO(id=2, name="Аватар"),
    ]

    candidates = TitleMatcher().find("Одисея", movies)

    assert candidates
    assert candidates[0].movie.id == 1
    assert candidates[0].score > 80


def test_low_score_is_not_auto_selected() -> None:
    movies = [MovieDTO(id=1, name="Одиссея")]
    matcher = TitleMatcher(minimum_score=80)

    assert matcher.exact("совсем другое", movies) is None
    assert matcher.find("совсем другое", movies) == []


def test_exact_match_checks_alternative_names() -> None:
    movie = MovieDTO(id=1, name="Одиссея", name_origin="The Odyssey")
    assert TitleMatcher().exact("the odyssey", [movie]) == movie
