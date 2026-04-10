"""
alembic/env.py — Конфигурация Alembic с поддержкой asyncpg и автоматическим
чтением DATABASE_URL из .env через Pydantic Settings.

Запуск миграций:
    cd backend
    alembic upgrade head

Создание новой миграции:
    alembic revision --autogenerate -m "описание"
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Добавляем backend/ в sys.path для импорта app
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.models.db import Base  # noqa: E402  — нужен после sys.path

# Alembic Config object
config = context.config

# Логирование из alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные для autogenerate
target_metadata = Base.metadata


def get_url() -> str:
    """Читает POSTGRES_URL из окружения (через .env)."""
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

    url = os.getenv("POSTGRES_URL", "")
    # asyncpg → psycopg2 для Alembic (sync)
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    # aiosqlite → sqlite для Alembic (sync)
    url = url.replace("sqlite+aiosqlite://", "sqlite://")
    return url


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
