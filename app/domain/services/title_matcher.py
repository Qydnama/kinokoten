from rapidfuzz.fuzz import WRatio

from app.domain.dto import MovieCandidate, MovieDTO
from app.utils.normalization import normalize_title


class TitleMatcher:
    def __init__(self, minimum_score: float = 55.0) -> None:
        self._minimum_score = minimum_score

    def find(self, query: str, movies: list[MovieDTO], limit: int = 8) -> list[MovieCandidate]:
        normalized_query = normalize_title(query)
        if not normalized_query:
            return []
        candidates: list[MovieCandidate] = []
        for movie in movies:
            scores = [
                (float(WRatio(normalized_query, normalize_title(name))), name)
                for name in movie.names
            ]
            score, matched_name = max(scores, default=(0.0, movie.name))
            if score >= self._minimum_score:
                candidates.append(
                    MovieCandidate(movie=movie, score=score, matched_name=matched_name)
                )
        return sorted(candidates, key=lambda item: (-item.score, item.movie.name))[:limit]

    def exact(self, query: str, movies: list[MovieDTO]) -> MovieDTO | None:
        normalized_query = normalize_title(query)
        for movie in movies:
            if any(normalize_title(name) == normalized_query for name in movie.names):
                return movie
        return None
