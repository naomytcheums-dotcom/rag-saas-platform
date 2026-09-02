"""Request/response bodies for api/routers/admin_users.py (Etape 1.2.1)."""

import uuid

from pydantic import BaseModel

from api.models.user import UserRole


class UserRoleUpdateRequest(BaseModel):
    """Body of PATCH /admin/users/{user_id}/role."""

    role: UserRole


class UserRoleUpdateResponse(BaseModel):
    user_id: uuid.UUID
    role: UserRole
