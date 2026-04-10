"""create trades table

Revision ID: 001
Revises:
Create Date: 2026-04-09
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trades",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticket", sa.BigInteger(), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("order_type", sa.String(4), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("open_price", sa.Float(), nullable=False),
        sa.Column("close_price", sa.Float(), nullable=False),
        sa.Column("sl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tp", sa.Float(), nullable=False, server_default="0"),
        sa.Column("profit", sa.Float(), nullable=False),
        sa.Column("swap", sa.Float(), nullable=False, server_default="0"),
        sa.Column("commission", sa.Float(), nullable=False, server_default="0"),
        sa.Column("strategy", sa.String(64), nullable=True),
        sa.Column("comment", sa.String(256), nullable=True),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket"),
    )
    op.create_index("ix_trades_ticket", "trades", ["ticket"])
    op.create_index("ix_trades_symbol", "trades", ["symbol"])
    op.create_index("ix_trades_strategy", "trades", ["strategy"])
    op.create_index("ix_trades_symbol_close_time", "trades", ["symbol", "close_time"])


def downgrade() -> None:
    op.drop_index("ix_trades_symbol_close_time", table_name="trades")
    op.drop_index("ix_trades_strategy", table_name="trades")
    op.drop_index("ix_trades_symbol", table_name="trades")
    op.drop_index("ix_trades_ticket", table_name="trades")
    op.drop_table("trades")
