"""add voice_messages, voice_settings, call_records (Partie 8.2.7/8.2.8/8.2.13)

Revision ID: 0082
Revises: 0081
Create Date: 2026-09-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0082"
down_revision: Union[str, None] = "0081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "voice_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("audio_key", sa.String(500), nullable=True),
        sa.Column("transcription", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_voice_messages_conversation_id", "voice_messages", ["conversation_id"])

    op.create_table(
        "voice_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("language", sa.String(10), nullable=False, server_default="fr-FR"),
        sa.Column("tts_provider", sa.String(20), nullable=False, server_default="web_speech"),
        sa.Column("tts_voice", sa.String(100), nullable=True),
        sa.Column("tts_speed", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("tts_pitch", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("tts_volume", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("stt_provider", sa.String(20), nullable=False, server_default="web_speech"),
        sa.Column("stt_language", sa.String(10), nullable=True),
        sa.Column("vad_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("vad_threshold", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("audio_history_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("push_to_talk_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "call_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("call_sid", sa.String(64), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("from_number", sa.String(32), nullable=False),
        sa.Column("to_number", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="initiated"),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("recording_url", sa.String(500), nullable=True),
        sa.Column("transcription", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_call_records_call_sid", "call_records", ["call_sid"], unique=True)


def downgrade() -> None:
    op.drop_table("call_records")
    op.drop_table("voice_settings")
    op.drop_table("voice_messages")
