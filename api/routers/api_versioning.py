"""Partie 9.2.8 -- API versioning. Real, public (no auth needed to ask
"what versions exist")."""

from fastapi import APIRouter, HTTPException, status

from api.config import settings

router = APIRouter(prefix="/api/versions", tags=["API Versioning"])


def _version_info(version: str) -> dict:
    return {
        "version": version, "current": version == settings.API_VERSION_CURRENT,
        "deprecated": version in settings.API_VERSION_DEPRECATED, "supported": version in settings.API_VERSION_SUPPORTED,
    }


@router.get("")
async def list_api_versions_endpoint():
    return {
        "current": settings.API_VERSION_CURRENT, "default": settings.API_VERSION_DEFAULT,
        "supported": settings.API_VERSION_SUPPORTED, "deprecated": settings.API_VERSION_DEPRECATED,
        "versions": [_version_info(v) for v in settings.API_VERSION_SUPPORTED],
    }


@router.get("/{version}")
async def get_api_version_endpoint(version: str):
    if version not in settings.API_VERSION_SUPPORTED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown or unsupported API version {version!r}")
    return _version_info(version)
