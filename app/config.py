from __future__ import annotations

from functools import cached_property
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    telegram_bot_token: SecretStr
    admin_telegram_id: int | None = None
    private_mode: bool = True
    allowed_telegram_user_ids: str = ""

    database_url: str = "sqlite+aiosqlite:///./data/bot.db"
    data_dir: Path = Path("./data")
    timezone: str = "Asia/Almaty"
    log_level: str = "INFO"

    kino_base_url: str = "https://kino.kz"
    kino_request_timeout_seconds: float = Field(default=15, gt=0, le=120)
    kino_max_retries: int = Field(default=3, ge=1, le=6)

    worker_tick_seconds: int = Field(default=60, ge=5)
    pending_movie_interval_seconds: int = Field(default=3600, ge=60)
    first_available_interval_seconds: int = Field(default=600, ge=60)
    far_date_interval_seconds: int = Field(default=900, ge=60)
    near_date_interval_seconds: int = Field(default=300, ge=60)
    near_date_days: int = Field(default=3, ge=0)
    date_selection_horizon_days: int = Field(default=365, ge=1, le=730)
    date_range_max_days: int = Field(default=31, ge=1, le=90)

    catalog_horizon_days: int = Field(default=120, ge=1, le=365)
    first_available_horizon_days: int = Field(default=120, ge=1, le=365)
    catalog_cache_seconds: int = Field(default=1800, ge=60)

    max_consecutive_errors: int = Field(default=5, ge=1, le=100)
    user_error_notification_hours: int = Field(default=24, ge=1)

    backup_interval_hours: int = Field(default=24, ge=1)
    backup_keep_count: int = Field(default=7, ge=7, le=100)
    backup_send_to_admin: bool = True

    @field_validator("telegram_bot_token")
    @classmethod
    def validate_token(cls, value: SecretStr) -> SecretStr:
        token = value.get_secret_value().strip()
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        if ":" not in token:
            raise ValueError("TELEGRAM_BOT_TOKEN has an invalid format")
        return SecretStr(token)

    @field_validator("kino_base_url")
    @classmethod
    def validate_kino_url(cls, value: str) -> str:
        normalized = value.rstrip("/")
        if normalized != "https://kino.kz":
            raise ValueError("KINO_BASE_URL must be https://kino.kz")
        return normalized

    @model_validator(mode="after")
    def validate_private_mode(self) -> Settings:
        if self.private_mode and not self.allowed_user_ids and self.admin_telegram_id is None:
            raise ValueError("PRIVATE_MODE requires ADMIN_TELEGRAM_ID or ALLOWED_TELEGRAM_USER_IDS")
        if self.backup_send_to_admin and self.admin_telegram_id is None:
            raise ValueError("BACKUP_SEND_TO_ADMIN requires ADMIN_TELEGRAM_ID")
        return self

    @cached_property
    def allowed_user_ids(self) -> frozenset[int]:
        values: set[int] = set()
        for part in self.allowed_telegram_user_ids.split(","):
            cleaned = part.strip()
            if cleaned:
                try:
                    values.add(int(cleaned))
                except ValueError as exc:
                    raise ValueError(
                        "ALLOWED_TELEGRAM_USER_IDS must contain comma-separated integers"
                    ) from exc
        if self.admin_telegram_id is not None:
            values.add(self.admin_telegram_id)
        return frozenset(values)

    def ensure_data_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "backups").mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    return Settings()
