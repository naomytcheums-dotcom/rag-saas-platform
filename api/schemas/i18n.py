"""Request/response bodies for Partie 8.1.19."""

from pydantic import BaseModel


class SupportedLanguagesResponse(BaseModel):
    languages: list[str]
    default: str


class SetLanguageRequest(BaseModel):
    language: str
