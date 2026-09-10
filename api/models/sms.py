"""Real Twilio SMS/WhatsApp send log. One real, honest scope: sending
only (a real user/org action triggering an outbound message) --
inbound SMS/WhatsApp webhooks are not built (no real inbound use case
exists in this app yet, unlike the CRM inbound integration, Partie
15.1, which had a real target: document ingestion)."""

import datetime as dt
import enum
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class SmsChannel(str, enum.Enum):
    sms = "sms"
    whatsapp = "whatsapp"


class SmsStatus(str, enum.Enum):
    queued = "queued"
    sent = "sent"
    failed = "failed"


class SmsMessage(Base):
    __tablename__ = "sms_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    channel: Mapped[SmsChannel] = mapped_column(nullable=False)
    to_number: Mapped[str] = mapped_column(String(32), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SmsStatus] = mapped_column(nullable=False, default=SmsStatus.queued)
    # Twilio's own real message SID once actually sent -- NULL if the
    # send failed before Twilio ever accepted it.
    provider_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
