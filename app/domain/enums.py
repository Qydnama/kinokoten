from enum import StrEnum


class TrackingMode(StrEnum):
    FIRST_AVAILABLE = "FIRST_AVAILABLE"
    EXACT_DATE = "EXACT_DATE"
    DATE_RANGE = "DATE_RANGE"


class CinemaScope(StrEnum):
    ALL = "ALL"
    SELECTED = "SELECTED"


class SubscriptionStatus(StrEnum):
    PENDING_MOVIE = "PENDING_MOVIE"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    WAITING_TICKETS = "WAITING_TICKETS"
    NOTIFIED = "NOTIFIED"
    PAUSED = "PAUSED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class NotificationStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


ACTIVE_SUBSCRIPTION_STATUSES = frozenset(
    {
        SubscriptionStatus.PENDING_MOVIE,
        SubscriptionStatus.WAITING_TICKETS,
        SubscriptionStatus.ERROR,
    }
)
