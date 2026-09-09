"""Partie 9.2.8 (API versioning) + 9.2.9 (OpenAPI/Swagger)."""

from api.config import settings
from api.services.api_versioning import deprecate_version, get_version_info, validate_api_version


def test_validate_api_version():
    """Validation criterion: les versions sont validées."""
    assert validate_api_version("v1") is True
    assert validate_api_version("v99") is False


def test_get_version_info():
    info = get_version_info()
    assert info["current"] == "v1"
    assert "v1" in info["supported"]


def test_deprecate_version():
    """Validation criterion: cohérence -- dépréciation."""
    try:
        deprecate_version("v1")
        assert "v1" in settings.API_VERSION_DEPRECATED
    finally:
        settings.API_VERSION_DEPRECATED.remove("v1")


async def test_list_api_versions_endpoint(client):
    """Validation criterion: le versioning fonctionne."""
    response = await client.get("/api/versions")
    assert response.status_code == 200
    assert response.json()["current"] == "v1"


async def test_get_api_version_endpoint(client):
    response = await client.get("/api/versions/v1")
    assert response.status_code == 200
    assert response.json()["current"] is True


async def test_get_api_version_endpoint_rejects_unknown_version(client):
    """Validation criterion: robustesse -- version invalide."""
    response = await client.get("/api/versions/v99")
    assert response.status_code == 404


async def test_every_response_carries_api_version_header(client):
    response = await client.get("/api/versions")
    assert response.headers["API-Version"] == "v1"
    assert "API-Deprecated" not in response.headers


async def test_openapi_json_is_served_with_configured_metadata(client):
    """Validation criterion: complétude -- la doc OpenAPI est générée."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == settings.OPENAPI_TITLE
    assert schema["info"]["version"] == settings.OPENAPI_VERSION


async def test_swagger_ui_is_served(client):
    response = await client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()


async def test_redoc_is_served(client):
    response = await client.get("/redoc")
    assert response.status_code == 200
