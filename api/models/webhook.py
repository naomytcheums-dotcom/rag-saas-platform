"""Partie 9.2.7 -- real, outbound webhooks notifying external
applications of real platform events."""

import datetime as dt
import uuid

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base

WEBHOOK_EVENTS = (
    "message.created", "message.updated", "document.uploaded", "document.processed", "agent.run_started",
    "agent.run_completed", "conversation.created", "conversation.updated",
)


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    events: Mapped[list] = mapped_column(JSON, nullable=False)
    headers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Real, plaintext-at-rest secret (an HMAC key, not a login
    # credential) -- same real convention this project already uses
    # for other HMAC secrets (AUDIT_LOG_HMAC_SECRET_KEY); never
    # returned again in a real response body after creation, same
    # discipline as an API key's own real plaintext.
    secret: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    webhook_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    delivered_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
