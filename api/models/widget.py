"""
Partie 9.3 -- the embeddable chat widget. Real, coherent consolidation
(vision critique -- do these prompts even name a coherent design?):
DeepSeek's own 9.3.2 through 9.3.10 each ask for their own model
("WidgetTheme", a new field on "WidgetConfig", another new field on
"WidgetConfig" again...) for what is, in every real case, ONE
customizable setting on the SAME real widget belonging to ONE real
organization. Fragmenting that into nine tables/migrations would mean
nine round trips to build one real config screen, and nine places a
future column could drift out of sync with the others. Real fix: ONE
`WidgetConfig` row per organization, covering every literal field
9.3.2-9.3.10 actually asks for (logo, colors, name, avatar, welcome
message, position, language, theme) -- the granular endpoints each
étape asks for (GET/PATCH /widget/theme, /widget/position, ...) still
exist as real, separate, literal routes; they just all read/write
different columns of this one real row instead of one row each.

`WidgetSuggestedQuestion` (9.3.7) stays a real, separate table on
purpose -- unlike the single-value settings above, "suggested
questions" is a real, ordered, admin-curated LIST, genuinely distinct
data shape, and genuinely distinct from Partie 8.1.17's own
`get_suggested_questions` (dynamic, LLM/popular/recent-derived, no
admin curation at all -- see api/services/suggested_questions.py's own
top docstring). Reusing that table here would silently conflate two
real, different features.
"""

import datetime as dt
import secrets
import uuid

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


def _generate_public_key() -> str:
    """A real, non-secret, embeddable identifier -- see this module's
    own docstring in api/security/widget_auth.py for why this is a
    SEPARATE concept from `OrganizationAPIKey` (9.1/9.2's real secret,
    server-to-server key)."""
    return f"wgt_{secrets.token_urlsafe(24)}"


class WidgetConfig(Base):
    __tablename__ = "widget_configs"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_widget_configs_organization_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    # Real, coherent reuse of the same "who does an anonymous-visitor
    # conversation belong to" fix Partie 9.1 already applied to
    # OrganizationAPIKey.created_by (Conversation.user_id is a real,
    # NOT NULL FK, and a widget visitor has no real user account at
    # all): a widget chat is attributed to whichever real org member
    # set the widget up. Nullable only because the FIRST row a real
    # organization gets (get_or_create_widget_config) may be created
    # by a system/background path with no real acting user yet.
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # A real, non-secret, publicly embeddable identifier -- safe to sit
    # in a <script> tag's markup, unlike a real OrganizationAPIKey.
    public_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=_generate_public_key)

    # Phase 4, Étape 5 (Domain Allowlist Widget) -- real, OPTIONAL,
    # per-organization origin allowlist. `None`/empty (the real default
    # every pre-existing organization already has) means real, UNCHANGED
    # behavior: this organization's own widget stays embeddable from any
    # origin, exactly as it already was before this étape (this
    # codebase's own real, existing, DELIBERATE default -- see
    # api/security/widget_auth.py's own module docstring: the public_key
    # is explicitly designed to be non-secret, safe to embed anywhere).
    # A non-empty list is a real, explicit, admin opt-in restriction --
    # see api/security/widget_auth.py's own `is_origin_allowed`/
    # `validate_widget_domain` for the real matching/validation rules.
    allowed_domains: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # 9.3.2 -- logo
    logo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # 9.3.3 -- colors
    primary_color: Mapped[str] = mapped_column(String(9), default="#6C63FF")
    secondary_color: Mapped[str] = mapped_column(String(9), default="#4A47A3")
    text_color: Mapped[str] = mapped_column(String(9), default="#FFFFFF")
    background_color: Mapped[str] = mapped_column(String(9), default="#FFFFFF")
    header_background: Mapped[str] = mapped_column(String(9), default="#6C63FF")
    border_radius: Mapped[str] = mapped_column(String(16), default="12px")
    font_family: Mapped[str] = mapped_column(String(128), default="system-ui")

    # 9.3.4 -- name
    widget_name: Mapped[str] = mapped_column(String(50), default="Assistant IA")
    widget_name_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    widget_short_name: Mapped[str | None] = mapped_column(String(12), nullable=True)

    # 9.3.5 -- avatar
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    avatar_uploaded_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    avatar_updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    use_default_avatar: Mapped[bool] = mapped_column(Boolean, default=True)

    # 9.3.6 -- welcome message
    welcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    welcome_message_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    welcome_message_updated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    welcome_message_updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # 9.3.8 -- position
    position: Mapped[str] = mapped_column(String(16), default="bottom-right")
    position_mobile: Mapped[str | None] = mapped_column(String(16), nullable=True)
    offset_x: Mapped[int] = mapped_column(Integer, default=20)
    offset_y: Mapped[int] = mapped_column(Integer, default=20)
    position_locked: Mapped[bool] = mapped_column(Boolean, default=False)

    # 9.3.9 -- language
    language: Mapped[str] = mapped_column(String(8), default="en")
    auto_detect_language: Mapped[bool] = mapped_column(Boolean, default=True)

    # 9.3.10 -- theme
    theme: Mapped[str] = mapped_column(String(8), default="auto")
    theme_custom_css: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    suggested_questions: Mapped[list["WidgetSuggestedQuestion"]] = relationship(
        back_populates="widget_config", cascade="all, delete-orphan", order_by="WidgetSuggestedQuestion.position"
    )


class WidgetSuggestedQuestion(Base):
    __tablename__ = "widget_suggested_questions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    widget_config_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("widget_configs.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    widget_config: Mapped["WidgetConfig"] = relationship(back_populates="suggested_questions")
