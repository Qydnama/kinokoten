class KinoError(Exception):
    """Base Kino.kz adapter error."""


class KinoUnavailableError(KinoError):
    """Kino.kz could not be reached after retrying."""


class KinoRateLimitError(KinoUnavailableError):
    """Kino.kz kept returning HTTP 429."""


class KinoResponseError(KinoError):
    """Kino.kz returned a non-retryable response."""


class KinoSchemaError(KinoError):
    """Kino.kz response no longer matches the expected shape."""
