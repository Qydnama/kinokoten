import re
import unicodedata

_PUNCTUATION_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().replace("ё", "\u0435")
    normalized = _PUNCTUATION_RE.sub(" ", normalized)
    return _SPACE_RE.sub(" ", normalized).strip()
