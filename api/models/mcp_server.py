"""
Phase 5, Étape 9 -- MCP (Model Context Protocol) client-side config:
a real, org-scoped, persisted registration of an EXTERNAL MCP server
this platform's own agents can call tools from (`stdio`/`sse`/
`streamable_http` transport, matching the real `mcp` SDK's own client
transports -- see api/services/mcp/client.py's own docstring).

Separate, deliberately, from this platform's own MCP SERVER role
(api/routers/mcp_server.py exposes OUR tools to external MCP clients,
reusing the existing `OrganizationAPIKey`/`mcp:tools` scope -- no new
model needed for that direction, it's just another public-API surface).

`MCPTool` rows are a real, cached discovery snapshot (`tools/list`
result), refreshed by `discover_tools` -- never the live source of
truth for what a call actually accepts (the external server always is),
just enough for the agent tool-selection/UI to show what's available
without a live round-trip on every page load.
"""

import datetime as dt
import uuid
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class MCPTransport(StrEnum):
    stdio = "stdio"
    sse = "sse"
    streamable_http = "streamable_http"


class MCPAuthType(StrEnum):
    none = "none"
    bearer = "bearer"
    api_key = "api_key"


class MCPServerConfig(Base):
    __tablename__ = "mcp_server_configs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    transport: Mapped[str] = mapped_column(String(20), nullable=False)
    # For sse/streamable_http only. Never used for stdio.
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # For stdio only -- a real, operator-configured local subprocess
    # command, never derived from untrusted input (see
    # api/services/mcp/client.py's own security docstring).
    command: Mapped[str | None] = mapped_column(String(500), nullable=True)
    args: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    env: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    auth_type: Mapped[str] = mapped_column(String(20), nullable=False, default=MCPAuthType.none.value)
    # Real, encrypted at rest via api/security/encryption.py -- the same
    # discipline as every other third-party credential this codebase
    # stores (never plaintext, e.g. api/models/chat_integration.py's
    # own bot_token columns).
    auth_credential_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    last_sync_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_mcp_server_configs_org_name"),)


class MCPToolCache(Base):
    __tablename__ = "mcp_tool_cache"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    server_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mcp_server_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_schema: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    discovered_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("server_id", "name", name="uq_mcp_tool_cache_server_name"),)
