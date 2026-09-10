"""
Partie 10.3 -- encryption status/rotation/testing. Global (platform-
wide), gated by the existing require_admin/require_superadmin (same
tier as GET /admin/jwt-keys, api/routers/audit.py) rather than an
org-scoped dependency: encryption keys and the fields they protect
(webhook secrets, bot tokens) span every organization on this platform,
not one -- there is no "per-org encryption key" concept to scope this
to. Key rotation specifically requires require_superadmin (not merely
require_admin): it rewrites every organization's Webhook.secret at
once, a platform-wide, irreversible-without-the-old-key operation on
par with api/routers/admin_users.py's PATCH /admin/users/{id}/role.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_admin, require_superadmin
from api.models.user import User
from api.schemas.encryption import EncryptionAlgorithmEntry, EncryptionStatusResponse, EncryptionTestResponse, RotateKeysResponse
from api.security.encryption import EncryptionNotConfiguredError, supported_algorithms
from api.services.encryption_status import get_encryption_status, rotate_encryption_keys, test_encryption_roundtrip

router = APIRouter(prefix="/encryption", tags=["Encryption"])


@router.get("/status", response_model=EncryptionStatusResponse)
async def encryption_status_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return EncryptionStatusResponse(**await get_encryption_status(db))


@router.get("/algorithms", response_model=list[EncryptionAlgorithmEntry])
async def encryption_algorithms_endpoint(_admin: User = Depends(require_admin)):
    return [EncryptionAlgorithmEntry(**entry) for entry in supported_algorithms()]


@router.post("/rotate-keys", response_model=RotateKeysResponse)
async def rotate_keys_endpoint(admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    try:
        result = await rotate_encryption_keys(db, performed_by=admin.id)
    except EncryptionNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    await db.commit()
    return RotateKeysResponse(**result)


@router.post("/test", response_model=EncryptionTestResponse)
async def test_encryption_endpoint(_admin: User = Depends(require_admin)):
    return EncryptionTestResponse(**test_encryption_roundtrip())
