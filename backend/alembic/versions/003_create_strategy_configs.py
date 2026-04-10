"""create strategy_configs table

Revision ID: 003
Revises: 002
Create Date: 2026-04-09
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Начальные конфигурации стратегий
INITIAL_STRATEGIES = [
    ("bollinger_scalp",    True,  "Bollinger Bands + RSI скальпинг на M1"),
    ("ema_scalp",          True,  "EMA crossover скальпинг на M1"),
    ("ema_pullback",       True,  "EMA pullback стратегия"),
    ("cci_rsi",            True,  "CCI + RSI комбинированный сигнал"),
    ("candle_reversal",    False, "Разворотные свечные паттерны"),
    ("fibonacci_retracement", False, "Fibonacci уровни для входа"),
    ("range_breakout",     False, "Пробой флэтового диапазона"),
    ("news_breakout",      False, "Торговля на новостях (требует фильтр времени)"),
    ("stochastic_scalp",   False, "Stochastic осциллятор скальпинг"),
    ("alligator",          False, "Williams Alligator (из alligatorBot.py)"),
]


def upgrade() -> None:
    op.create_table(
        "strategy_configs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Seed начальных конфигураций (op.execute совместим с SQLite и PostgreSQL)
    conn = op.get_bind()
    for idx, (name, enabled, desc) in enumerate(INITIAL_STRATEGIES, start=1):
        conn.execute(
            sa.text(
                "INSERT INTO strategy_configs (id, name, enabled, description, params) "
                "VALUES (:id, :name, :enabled, :desc, :params)"
            ),
            {"id": idx, "name": name, "enabled": int(enabled), "desc": desc, "params": "{}"},
        )


def downgrade() -> None:
    op.drop_table("strategy_configs")
