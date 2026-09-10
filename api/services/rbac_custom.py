"""
Partie 10.1 -- custom roles and granular permissions, additive on top of
api/security/organizations.py's fixed 5-tier OrganizationRole hierarchy
(see api/models/rbac.py's own docstring for the full design rationale).

Permission catalog seeding: the 52-row Permission/PermissionGroup
catalog (api/security/permission_catalog.py) is fixed and defined in
code, but RolePermission needs real DB rows to foreign-key against.
ensure_permission_catalog_seeded() is an idempotent upsert-by-count
check called at the top of every function here that touches
Permission -- NOT a migration-only data seed, deliberately: this
repo's fast test suite creates its schema via Base.metadata.create_all
(tests/conftest.py), which never runs Alembic data migrations, so
seeding only in a migration would leave the catalog empty in every
test. Same "idempotent create_default_X, called at point of use"
pattern this codebase already uses for org quotas/settings/branding
(api/security/organizations.py's create_organization_with_owner).
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.rbac import CustomRole, Permission, PermissionGroup, RolePermission, UserCustomRole
from api.security.permission_catalog import RESOURCES, permission_catalog


class RBACError(Exception):
    pass


class RoleNotFoundError(RBACError):
    pass


class PermissionNotFoundError(RBACError):
    pass


class DuplicateRoleNameError(RBACError):
    pass


async def ensure_permission_catalog_seeded(db: AsyncSession) -> None:
    existing = await db.scalar(select(func.count()).select_from(Permission))
    if existing:
        return

    groups: dict[str, PermissionGroup] = {}
    for index, (resource_key, resource_label) in enumerate(RESOURCES):
        group = PermissionGroup(key=resource_key, label=resource_label, sort_order=index)
        db.add(group)
        groups[resource_key] = group
    await db.flush()

    for entry in permission_catalog():
        db.add(Permission(
            key=entry["key"], resource=entry["resource"], action=entry["action"],
            description=entry["description"], group_id=groups[entry["resource"]].id,
        ))
    await db.flush()


async def list_permissions(db: AsyncSession) -> list[Permission]:
    await ensure_permission_catalog_seeded(db)
    return list((await db.scalars(select(Permission).order_by(Permission.resource, Permission.action))).all())


async def list_custom_roles(db: AsyncSession, organization_id: uuid.UUID) -> list[CustomRole]:
    return list((await db.scalars(
        select(CustomRole)
        .options(selectinload(CustomRole.role_permissions).selectinload(RolePermission.permission))
        .where(CustomRole.organization_id == organization_id).order_by(CustomRole.name)
    )).all())


async def get_custom_role_or_404(db: AsyncSession, role_id: uuid.UUID, organization_id: uuid.UUID) -> CustomRole:
    """Eagerly loads role_permissions (+ each one's permission) --
    every real caller (the routers' own _role_to_response) reads
    `role.role_permissions[*].permission.key` right after this returns,
    and an async session never implicitly lazy-loads outside an
    explicit await (see assign_permissions_to_role's own docstring)."""
    role = await db.scalar(
        select(CustomRole)
        .options(selectinload(CustomRole.role_permissions).selectinload(RolePermission.permission))
        .where(CustomRole.id == role_id, CustomRole.organization_id == organization_id)
    )
    if role is None:
        raise RoleNotFoundError(str(role_id))
    return role


async def create_custom_role(
    db: AsyncSession, *, organization_id: uuid.UUID, name: str, description: str | None, user_id: uuid.UUID,
) -> CustomRole:
    existing = await db.scalar(
        select(CustomRole).where(CustomRole.organization_id == organization_id, CustomRole.name == name)
    )
    if existing is not None:
        raise DuplicateRoleNameError(name)
    role = CustomRole(organization_id=organization_id, name=name, description=description, created_by=user_id)
    db.add(role)
    await db.flush()
    return role


async def update_custom_role(
    db: AsyncSession, *, role_id: uuid.UUID, organization_id: uuid.UUID, name: str | None, description: str | None,
) -> CustomRole:
    role = await get_custom_role_or_404(db, role_id, organization_id)
    if name is not None:
        role.name = name
    if description is not None:
        role.description = description
    await db.flush()
    return role


async def delete_custom_role(db: AsyncSession, *, role_id: uuid.UUID, organization_id: uuid.UUID) -> None:
    role = await get_custom_role_or_404(db, role_id, organization_id)
    await db.delete(role)
    await db.flush()


async def assign_permissions_to_role(
    db: AsyncSession, *, role_id: uuid.UUID, organization_id: uuid.UUID, permission_ids: list[uuid.UUID],
) -> CustomRole:
    """Real, deliberate note: this queries RolePermission directly
    (`select(...)`) rather than reading `role.role_permissions` -- an
    async ORM session never implicitly lazy-loads a relationship
    outside a real `await` context (SQLAlchemy's own MissingGreenlet
    error, caught by this module's own tests), so any caller needing
    a role's permissions after it's been loaded must ask for them
    explicitly, the same way this whole codebase's other async
    relationship accesses already do (e.g. Organization.owner's own
    docstring)."""
    role = await get_custom_role_or_404(db, role_id, organization_id)
    existing_permission_ids = {
        row for row in (await db.scalars(select(RolePermission.permission_id).where(RolePermission.role_id == role.id))).all()
    }
    for permission_id in permission_ids:
        if permission_id in existing_permission_ids:
            continue
        permission = await db.get(Permission, permission_id)
        if permission is None:
            raise PermissionNotFoundError(str(permission_id))
        db.add(RolePermission(role_id=role.id, permission_id=permission_id))
    await db.flush()
    return role


async def remove_permission_from_role(db: AsyncSession, *, role_id: uuid.UUID, organization_id: uuid.UUID, permission_id: uuid.UUID) -> None:
    role = await get_custom_role_or_404(db, role_id, organization_id)
    row = await db.scalar(
        select(RolePermission).where(RolePermission.role_id == role.id, RolePermission.permission_id == permission_id)
    )
    if row is not None:
        await db.delete(row)
        await db.flush()


async def assign_role_to_user(db: AsyncSession, *, user_id: uuid.UUID, role_id: uuid.UUID, organization_id: uuid.UUID, assigned_by: uuid.UUID) -> UserCustomRole:
    await get_custom_role_or_404(db, role_id, organization_id)
    existing = await db.scalar(
        select(UserCustomRole).where(UserCustomRole.user_id == user_id, UserCustomRole.role_id == role_id)
    )
    if existing is not None:
        return existing
    assignment = UserCustomRole(user_id=user_id, role_id=role_id, assigned_by=assigned_by)
    db.add(assignment)
    await db.flush()
    return assignment


async def remove_role_from_user(db: AsyncSession, *, user_id: uuid.UUID, role_id: uuid.UUID) -> None:
    row = await db.scalar(
        select(UserCustomRole).where(UserCustomRole.user_id == user_id, UserCustomRole.role_id == role_id)
    )
    if row is not None:
        await db.delete(row)
        await db.flush()


async def get_role_permission_keys(db: AsyncSession, role_id: uuid.UUID) -> list[str]:
    """A direct join query, not `role.role_permissions[*].permission.key`
    -- deliberately: an async session's identity map can serve a STALE,
    previously-loaded (possibly empty) relationship collection for an
    object mutated earlier in the same request (e.g. right after
    assign_permissions_to_role's own INSERTs), and eager-reloading it
    reliably would need either an explicit `db.expire()` or a full
    re-fetch either way -- a plain, fresh query sidesteps the ambiguity
    entirely and is exactly as cheap."""
    rows = (await db.scalars(
        select(Permission.key).join(RolePermission, RolePermission.permission_id == Permission.id).where(RolePermission.role_id == role_id)
    )).all()
    return sorted(rows)


async def get_user_effective_permissions(db: AsyncSession, *, user_id: uuid.UUID, organization_id: uuid.UUID) -> set[str]:
    """The union of every permission granted by every CustomRole this
    user holds IN this organization -- a `manage` permission on a
    resource additionally implies read/write/delete on that same
    resource (a role granted `documents:manage` doesn't also need three
    more explicit rows to actually be useful)."""
    rows = (await db.execute(
        select(Permission.key, Permission.resource, Permission.action)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(CustomRole, CustomRole.id == RolePermission.role_id)
        .join(UserCustomRole, UserCustomRole.role_id == CustomRole.id)
        .where(UserCustomRole.user_id == user_id, CustomRole.organization_id == organization_id)
    )).all()

    effective: set[str] = set()
    for key, resource, action in rows:
        effective.add(key)
        if action == "manage":
            effective.add(f"{resource}:read")
            effective.add(f"{resource}:write")
            effective.add(f"{resource}:delete")
    return effective


async def check_permission(db: AsyncSession, *, user_id: uuid.UUID, organization_id: uuid.UUID, resource: str, action: str) -> bool:
    effective = await get_user_effective_permissions(db, user_id=user_id, organization_id=organization_id)
    return f"{resource}:{action}" in effective
