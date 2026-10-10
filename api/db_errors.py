"""Database errors caused by what a client submitted must answer 4xx, not 500 (TEN-007, TEN-021, TEN-022).

The audit found ~27 creation/update routes answering 500 for a NUL character or a 100 000-character string (the database rejects the
value at flush time), concurrent registrations with the same e-mail answering 7 x 500 instead of 409, and a duplicate usage alert answering
500. Validating every field of every schema is the long-term fix; this handler makes the whole API behave correctly meanwhile, and keeps
a server-side warning (SQLSTATE only, never the values) so a real bug is not silently turned into a 4xx.

* unique violation -> 409
* foreign-key violation (a submitted id that does not exist) -> 422
* data exception (invalid characters, value too long, numeric overflow, bad format) -> 422
* any other integrity/database error is NOT handled here: it is a server problem and stays a 500."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError

logger = logging.getLogger(__name__)

_UNIQUE = "23505"
_FOREIGN_KEY = "23503"
_DATA_EXCEPTION_CLASS = "22"


def _sqlstate(exc) -> str | None:
    orig = getattr(exc, "orig", None)
    code = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    if code:
        return str(code)
    message = str(orig or "")
    if "UNIQUE constraint failed" in message:  # SQLite (tests, local development)
        return _UNIQUE
    if "FOREIGN KEY constraint failed" in message:
        return _FOREIGN_KEY
    return None


async def _db_error_handler(request: Request, exc: DBAPIError):
    """Classified by SQLSTATE: SQLAlchemy's asyncpg dialect does not map every asyncpg error to its DataError class (a NUL character
    arrives as a plain DBAPIError whose `orig` is CharacterNotInRepertoireError, SQLSTATE 22021)."""
    state = _sqlstate(exc)
    if state == _UNIQUE:
        logger.warning("%s %s: unique violation (SQLSTATE %s) answered 409", request.method, request.url.path, state)
        return JSONResponse(status_code=409, content={"detail": "This value conflicts with existing data (it may already exist)"})
    if state == _FOREIGN_KEY:
        logger.warning("%s %s: foreign key violation (SQLSTATE %s) answered 422", request.method, request.url.path, state)
        return JSONResponse(status_code=422, content={"detail": "A referenced item does not exist"})
    if state and state.startswith(_DATA_EXCEPTION_CLASS):
        logger.warning("%s %s: data exception (SQLSTATE %s) answered 422", request.method, request.url.path, state)
        return JSONResponse(status_code=422, content={"detail": "A submitted value is not acceptable (invalid characters, too long or out of range)"})
    raise exc


def register_db_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DBAPIError, _db_error_handler)
