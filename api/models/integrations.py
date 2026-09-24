"""
Partie 15.1/15.2/15.3 -- universal inbound integrations (Zapier/Make/n8n/
any webhook-capable CRM) + Airbyte.

Real, non-duplicating scope: OUTBOUND webhooks ("notify Zapier when a
message/document/conversation event happens in this app") already
exist for real -- `Webhook`/`WebhookDelivery`, Partie 9.2.7. Pointing a
Zapier/Make/n8n "webhook trigger" step at one of THOSE URLs is the real
way to build "when X happens here, run my Zap" -- nothing new needed,
not duplicated here.

What's genuinely new is the INBOUND direction: an external system
(a CRM, Zapier's own "webhooks by Zapier" action, an n8n workflow)
POSTing data INTO this app. `IntegrationConnection` is one real,
per-organization inbound receiver (its own bearer token, its own
target action); `IntegrationMapping` is optional per-connection field
renaming/normalization; `IntegrationLog` is the real receipt log
(every POST, whether accepted or rejected).
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class IntegrationProvider(str, enum.Enum):
    webhook = "webhook"  # a generic, unbranded inbound webhook
    zapier = "zapier"
    make = "make"
    n8n = "n8n"


class IntegrationAction(str, enum.Enum):
    # Phase 5, Étape 17 -- extended from the original two actions to
    # support real, useful automation triggered by inbound webhooks
    # (Zapier/Make/n8n can now do more than just log or ingest).
    ingest_document = "ingest_document"  # real: feeds payload text into this org's real document/RAG pipeline
    log_only = "log_only"  # real: just recorded in IntegrationLog, no side effect
    create_agent = "create_agent"  # real: creates a new Agent in this organization
    create_conversation = "create_conversation"  # real: creates a new Conversation
    send_notification = "send_notification"  # real: sends an in-app + email notification
    trigger_workflow = "trigger_workflow"  # real: triggers a Workflow run


class IntegrationConnection(Base):
    __tablename__ = "integration_connections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[IntegrationProvider] = mapped_column(nullable=False, default=IntegrationProvider.webhook)
    action: Mapped[IntegrationAction] = mapped_column(nullable=False, default=IntegrationAction.log_only)
    # Real bearer token this connection's inbound POSTs must present
    # (Authorization: Bearer <token>) -- generated once, shown once,
    # same real convention as an API key's own plaintext.
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class IntegrationMapping(Base):
    __tablename__ = "integration_mappings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("integration_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    source_field: Mapped[str] = mapped_column(String(200), nullable=False)
    target_field: Mapped[str] = mapped_column(String(200), nullable=False)
    # One of api/services/integrations.py's real, pure transform
    # functions ("normalize_email"/"normalize_phone"/"normalize_date"/
    # None) -- an unknown name is a no-op, never a crash.
    transform: Mapped[str | None] = mapped_column(String(50), nullable=True)


class IntegrationLogStatus(str, enum.Enum):
    accepted = "accepted"
    rejected = "rejected"
    error = "error"


class IntegrationLog(Base):
    __tablename__ = "integration_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("integration_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[IntegrationLogStatus] = mapped_column(nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class AirbyteConnection(Base):
    """Partie 15.3 -- one real Airbyte connection this org has actually
    created via a real Airbyte instance's own API
    (api/services/airbyte_client.py). Stores only Airbyte's own ids;
    every other detail (which of Airbyte's 300+ source types, its
    schema/catalog, sync history) is real data that lives in Airbyte
    itself, read live via its API rather than mirrored here."""

    __tablename__ = "airbyte_connections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    airbyte_source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    airbyte_connection_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
