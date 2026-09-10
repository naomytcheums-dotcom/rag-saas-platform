"""Request/response bodies for Partie 10.1 (custom roles & granular permissions)."""

import datetime as dt
import uuid

from pydantic import BaseModel


class PermissionResponse(BaseModel):
    id: uuid.UUID
    key: str
    resource: str
    action: str
    description: str

    model_config = {"from_attributes": True}


class CustomRoleCreateRequest(BaseModel):
    name: str
    description: str | None = None


class CustomRoleUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class CustomRoleResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    permission_keys: list[str] = []

    model_config = {"from_attributes": True}


class AssignPermissionsRequest(BaseModel):
    permission_ids: list[uuid.UUID]


class AssignRoleToUserRequest(BaseModel):
    role_id: uuid.UUID


class EffectivePermissionsResponse(BaseModel):
    user_id: uuid.UUID
    organization_id: uuid.UUID
    permissions: list[str]
    is_org_admin_or_owner: bool


class PermissionCheckRequest(BaseModel):
    organization_id: uuid.UUID
    resource: str
    action: str


class PermissionCheckResponse(BaseModel):
    allowed: bool
