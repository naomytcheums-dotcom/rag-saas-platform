"""Hardening Mission, Phase 2 -- real, DB-persistent account lockout.
See api/models/user.py's own User.failed_login_attempts/locked_until
docstring for the real design: deliberately independent of Redis
(api/security/rate_limit.py's own documented fail-open behavior means a
Redis outage otherwise leaves zero brute-force protection at all).

Purely additive: `failed_login_attempts` defaults to 0 (server_default
"0"), `locked_until` defaults to NULL -- every existing user row is
immediately, correctly "not locked" with no backfill needed.

Reversible: `downgrade` drops both columns.

Revision ID: 0129
Revises: 0128
Create Date: 2026-10-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0129"
down_revision: Union[str, None] = "0128"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
