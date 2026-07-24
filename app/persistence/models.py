from __future__ import annotations

from datetime import date, datetime
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain.enums import (
    CinemaScope,
    NotificationStatus,
    SubscriptionStatus,
    TrackingMode,
)
from app.utils.dates import utc_now


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSON}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    default_city_id: Mapped[int | None]
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Almaty")

    subscriptions: Mapped[list[Subscription]] = relationship(back_populates="user")


class Movie(TimestampMixin, Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True)
    kino_movie_id: Mapped[int] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(String(500))
    name_rus: Mapped[str | None] = mapped_column(String(500))
    name_origin: Mapped[str | None] = mapped_column(String(500))
    normalized_names: Mapped[list[str]] = mapped_column(JSON)
    premiere_date: Mapped[date | None] = mapped_column(Date)
    poster_url: Mapped[str | None] = mapped_column(Text)
    is_pre_sales: Mapped[bool] = mapped_column(Boolean, default=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Cinema(TimestampMixin, Base):
    __tablename__ = "cinemas"
    __table_args__ = (Index("ix_cinemas_city_id", "city_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kino_cinema_id: Mapped[int] = mapped_column(unique=True)
    city_id: Mapped[int]
    name: Mapped[str] = mapped_column(String(500))
    normalized_name: Mapped[str] = mapped_column(String(500))
    address: Mapped[str | None] = mapped_column(Text)
    poster_url: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Subscription(TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscriptions_status_next_check", "status", "next_check_at"),
        Index("ix_subscriptions_user_status", "user_id", "status"),
        Index("ix_subscriptions_city_mode", "city_id", "tracking_mode"),
        CheckConstraint(
            "tracking_mode != 'EXACT_DATE' OR date_from = date_to",
            name="ck_subscription_exact_date",
        ),
        CheckConstraint(
            "tracking_mode != 'DATE_RANGE' OR (date_from IS NOT NULL AND date_to IS NOT NULL)",
            name="ck_subscription_date_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    creation_key: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kino_movie_id: Mapped[int | None]
    movie_title: Mapped[str | None] = mapped_column(String(500))
    movie_original_title: Mapped[str | None] = mapped_column(String(500))
    raw_query: Mapped[str] = mapped_column(String(500))
    release_date: Mapped[date | None] = mapped_column(Date)
    city_id: Mapped[int]
    tracking_mode: Mapped[TrackingMode] = mapped_column(String(32))
    date_from: Mapped[date | None] = mapped_column(Date)
    date_to: Mapped[date | None] = mapped_column(Date)
    cinema_scope: Mapped[CinemaScope] = mapped_column(String(16))
    status: Mapped[SubscriptionStatus] = mapped_column(String(32))
    status_before_error: Mapped[SubscriptionStatus | None] = mapped_column(String(32))
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_errors: Mapped[int] = mapped_column(default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(100))

    user: Mapped[User] = relationship(back_populates="subscriptions")
    selected_cinemas: Mapped[list[SubscriptionCinema]] = relationship(
        back_populates="subscription",
        cascade="all, delete-orphan",
    )
    seen_sessions: Mapped[list[SeenSession]] = relationship(
        back_populates="subscription",
        cascade="all, delete-orphan",
    )


class SubscriptionCinema(Base):
    __tablename__ = "subscription_cinemas"

    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    kino_cinema_id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    subscription: Mapped[Subscription] = relationship(back_populates="selected_cinemas")


class SeenSession(Base):
    __tablename__ = "seen_sessions"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "source_session_key",
            name="uq_seen_subscription_session",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id", ondelete="CASCADE"))
    source_session_key: Mapped[str] = mapped_column(String(255))
    kino_session_id: Mapped[int | None]
    kino_cinema_id: Mapped[int | None]
    session_date: Mapped[date | None] = mapped_column(Date)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    subscription: Mapped[Subscription] = relationship(back_populates="seen_sessions")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id", ondelete="CASCADE"))
    dedupe_key: Mapped[str] = mapped_column(String(255), unique=True)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[NotificationStatus] = mapped_column(String(16))
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SubscriptionRejectedMovie(Base):
    __tablename__ = "subscription_rejected_movies"

    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    kino_movie_id: Mapped[int] = mapped_column(primary_key=True)
    rejected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
