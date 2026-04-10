"""create backtest_runs table

Revision ID: 002
Revises: 001
Create Date: 2026-04-09
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("strategy", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("bars", sa.Integer(), nullable=False),
        sa.Column("deposit", sa.Float(), nullable=False),
        sa.Column("spread", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("risk_percent", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("total_trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("win_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("profit_factor", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sharpe_ratio", sa.Float(), nullable=False, server_default="0"),
        sa.Column("max_drawdown", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_profit", sa.Float(), nullable=False, server_default="0"),
        sa.Column("equity_curve", sa.JSON(), nullable=True),
        sa.Column("trades_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backtest_runs_strategy", "backtest_runs", ["strategy"])


def downgrade() -> None:
    op.drop_index("ix_backtest_runs_strategy", table_name="backtest_runs")
    op.drop_table("backtest_runs")
