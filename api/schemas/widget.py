import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class WidgetPublicConfigResponse(BaseModel):
    public_key: str
    logo_url: str | None
    avatar_url: str | None
    colors: dict
    border_radius: str
    font_family: str
    name: str | None
    short_name: str | None
    welcome_message: str | None
    position: str
    position_mobile: str
    offset_x: int
    offset_y: int
    position_locked: bool
    language: str
    auto_detect_language: bool
    theme: str
    custom_css: str | None
    suggested_questions: list[dict]
    max_messages: int


class WidgetConfigUpdateRequest(BaseModel):
    primary_color: str | None = None
    secondary_color: str | None = None
    text_color: str | None = None
    background_color: str | None = None
    header_background: str | None = None
    border_radius: str | None = None
    font_family: str | None = None


# Phase 4, Étape 5 (Domain Allowlist Widget) -- admin-only (this field
# deliberately never rides along on `WidgetPublicConfigResponse`, this
# étape's own explicit "ne fuite pas la config d'autres tenants" ask --
# though the real concern here is simpler: an organization's OWN
# allowlist is not secret to that org's own admins, but it has no real
# reason to be broadcast to every real, anonymous widget visitor
# either).
class WidgetDomainsUpdateRequest(BaseModel):
    # Real, deliberate `list[str]`, not `list[str] | None` -- an admin
    # always sends the real, COMPLETE, intended list (empty list =
    # real, explicit "remove all restrictions", matching
    # `update_widget_config`'s own established "None reaching here is
    # always a real, deliberate reset" convention elsewhere in this
    # module).
    allowed_domains: list[str] = Field(max_length=20)


class WidgetDomainsResponse(BaseModel):
    allowed_domains: list[str]


class WidgetThemeUpdateRequest(BaseModel):
    theme: str | None = None
    theme_custom_css: str | None = Field(default=None, max_length=10_000)


class WidgetThemeResponse(BaseModel):
    theme: str
    theme_custom_css: str | None


class WidgetPositionUpdateRequest(BaseModel):
    position: str | None = None
    position_mobile: str | None = None
    offset_x: int | None = None
    offset_y: int | None = None
    position_locked: bool | None = None


class WidgetPositionResponse(BaseModel):
    position: str
    position_mobile: str
    offset_x: int
    offset_y: int
    position_locked: bool


class WidgetNameUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class WidgetLanguageUpdateRequest(BaseModel):
    language: str


class WidgetWelcomeUpdateRequest(BaseModel):
    message: str


class WidgetSessionRequest(BaseModel):
    public_key: str


class WidgetSessionResponse(BaseModel):
    session_token: str
    expires_in: int


class WidgetChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None


class WidgetChatResponse(BaseModel):
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    response: str
    citations: list[dict]


class SuggestedQuestionCreateRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    label: str | None = Field(default=None, max_length=64)


class SuggestedQuestionUpdateRequest(BaseModel):
    question: str | None = None
    label: str | None = None
    is_active: bool | None = None


class SuggestedQuestionResponse(BaseModel):
    id: uuid.UUID
    question: str
    label: str | None
    position: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ReorderQuestionsRequest(BaseModel):
    question_ids: list[uuid.UUID]
