"""
core/config.py — Централизованная конфигурация через Pydantic Settings v2.

Заменяет settings.py с mutable class-level dict'ами.
Читает из .env файла и переменных окружения.

Usage:
    from app.core.config import settings
    print(settings.mt5_login)
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import MetaTrader5 as mt5


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # MT5
    mt5_login: int = Field(..., description="MT5 account login")
    mt5_password: str = Field(..., description="MT5 account password")
    mt5_server: str = Field(..., description="MT5 broker server name")

    # Database
    postgres_url: str = Field(
        "postgresql+asyncpg://mk:mk@localhost:5432/millionskeeper",
        description="Async PostgreSQL DSN",
    )
    redis_url: str = Field("redis://localhost:6379/0", description="Redis DSN")

    # Trading defaults
    scalp_timeframe: int = Field(mt5.TIMEFRAME_M1, description="M1 — основной таймфрейм для скальпинга")
    trend_timeframe: int = Field(mt5.TIMEFRAME_H1, description="H1 — фильтр тренда")
    default_risk_percent: float = Field(1.0, ge=0.1, le=10.0, description="Risk per trade, %")
    max_open_positions: int = Field(5, ge=1, le=50)
    poll_interval_market: float = Field(10.0, ge=1.0, description="MarketDataAgent poll, seconds")
    poll_interval_position: float = Field(5.0, ge=1.0, description="PositionMonitorAgent poll")
    poll_interval_account: float = Field(30.0, ge=5.0, description="AccountAgent poll")
    poll_interval_history: float = Field(300.0, ge=60.0, description="HistoryAgent poll")

    # Auth (JWT на основе MT5 логина)
    jwt_secret: str = Field("change-me-in-production", description="JWT signing secret")
    jwt_expire_hours: int = Field(24, ge=1, le=168)

    # Web
    web_host: str = "0.0.0.0"
    web_port: int = 8080
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]

    # Feature flags
    enable_redis_cache: bool = True
    log_level: str = "INFO"


# Синглтон — импортируется напрямую
settings = Settings()
