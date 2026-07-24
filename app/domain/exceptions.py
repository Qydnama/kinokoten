class KinoTicketBotError(Exception):
    """Base application error."""


class ValidationError(KinoTicketBotError):
    """Domain data is invalid."""


class OwnershipError(KinoTicketBotError):
    """The requested object does not belong to the current user."""
