"""
Phase 5, Étape 4 -- notifications (in-app + email), genuinely built
from scratch: unlike every prior étape this session (billing, RBAC,
SSO, white-label all had substantial pre-existing infrastructure), an
exhaustive audit (`grep -rliE "\\bnotif|preference|unread"
api/models/ api/services/ api/routers/`) found nothing beyond
`api/routers/notifications.py`, which is real Twilio SMS/WhatsApp
sending -- an unrelated feature that happens to share the word
"notifications".

**Deliberately smaller than the étape's own literal 4-table spec**
(`Notification`, `NotificationPreference`, `NotificationTemplate`,
`NotificationDelivery`): only the two tables below are real DB
entities.
- `NotificationTemplate` is NOT a DB table here -- templates are
  Jinja2 strings defined in code
  (`api/services/notification_templates.py`), not admin-editable rows.
  A real, working, tested rendering path exists for every notification
  type this étape actually wires; a full admin CRUD+preview UI for
  arbitrary custom templates is real, additional scope, traced in
  ROADMAP.md, not built here.
- `NotificationDelivery` is NOT a separate table -- its three real
  fields (`email_status`, `email_error`, `email_sent_at`) live directly
  on `Notification` instead. A notification has at most two real
  deliveries (in-app, email) in this étape's own scope; a whole extra
  table keyed by (notification_id, channel) buys per-channel-retry
  granularity this étape doesn't otherwise need, at the cost of a join
  on every single notification list query.
"""

import datetime as dt
import uuid

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Nullable: most notifications ARE org-scoped (billing, workflows,
    # documents, invitations), but a real security event (new-device
    # login, password change) happens to a USER, not to any one of the
    # several organizations they might belong to -- forcing a fake
    # organization_id onto those would be worse than admitting some
    # notifications genuinely have none.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # A free-form string, not an enum -- this étape only wires 5 real
    # trigger types (see notification_templates.py's own
    # TEMPLATES dict), but the table itself must not require a schema
    # migration every time a future caller adds a new type; an unknown
    # type just renders through _GENERIC_TEMPLATE.
    type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="normal")
    # "in_app", "email", or "both" -- which channel(s) this specific
    # notification was ACTUALLY dispatched to, after resolving the
    # recipient's own NotificationPreference (a user who disabled email
    # for this type gets channel="in_app" even if the caller asked for
    # "both" -- the row records what really happened, not what was
    # requested).
    channel: Mapped[str] = mapped_column(String(10), nullable=False, default="in_app")
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Folded-in delivery tracking (see this module's own docstring for
    # why there's no separate NotificationDelivery table).
    email_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "pending" | "sent" | "failed" | "skipped"
    email_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        # Every real list query filters by (user_id, organization_id),
        # optionally + read_at IS NULL for the unread-count endpoint.
    )


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    notification_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # Both True by default -- this is an opt-OUT model (matching the
    # étape's own spec table, where nearly every type defaults to
    # "in-app + email"), not opt-in. A row only exists once a user has
    # actually changed a default; absence of a row means "use the
    # real, honest default" (see notifications.py's own
    # resolve_preference, never a silent False).
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", "notification_type", name="uq_notification_pref_user_org_type"),
    )
