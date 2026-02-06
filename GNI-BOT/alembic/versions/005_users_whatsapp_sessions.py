"""Add users and whatsapp_sessions tables.

Revision ID: 005_users_wa
Revises: 004_dlq
Create Date: 2025-02-04

- users: id, email (unique), password_hash, created_at
- whatsapp_sessions: user_id (unique FK), status, session_path, qr_payload, qr_expires_at, phone_e164, connected_at, updated_at
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_users_wa"
down_revision: Union[str, Sequence[str], None] = "004_dlq"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "whatsapp_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="disconnected"),
        sa.Column("session_path", sa.Text(), nullable=True),
        sa.Column("qr_payload", sa.Text(), nullable=True),
        sa.Column("qr_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("phone_e164", sa.String(32), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_whatsapp_sessions_user_id", "whatsapp_sessions", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_whatsapp_sessions_user_id", table_name="whatsapp_sessions")
    op.drop_table("whatsapp_sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
