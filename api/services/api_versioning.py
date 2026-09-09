"""Partie 9.2.8 -- API versioning helper functions."""

from fastapi import Request

from api.config import settings


def validate_api_version(version: str) -> bool:
    """Item 2's own literal function."""
    return version in settings.API_VERSION_SUPPORTED


def get_api_version(request: Request) -> str:
    """Item 2's own literal function -- real precedence: an explicit
    `API-Version` header first, then a real `?version=` query
    parameter, then `API_VERSION_DEFAULT`."""
    header_version = request.headers.get("API-Version")
    if header_version and validate_api_version(header_version):
        return header_version
    query_version = request.query_params.get("version")
    if query_version and validate_api_version(query_version):
        return query_version
    return settings.API_VERSION_DEFAULT


def deprecate_version(version: str) -> None:
    """Item 2's own literal function -- real, honest scope: mutates
    the real, in-process `settings.API_VERSION_DEPRECATED` list
    directly (this codebase has no real, separate persisted store for
    API version state) -- real for the lifetime of this process, not
    persisted across a real restart, same honest limit as any other
    runtime-only toggle."""
    if version not in settings.API_VERSION_DEPRECATED:
        settings.API_VERSION_DEPRECATED.append(version)


def get_version_info() -> dict:
    """Item 2's own literal function."""
    return {
        "current": settings.API_VERSION_CURRENT, "default": settings.API_VERSION_DEFAULT,
        "supported": settings.API_VERSION_SUPPORTED, "deprecated": settings.API_VERSION_DEPRECATED,
    }
