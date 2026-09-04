"""
Partie 5.2.4 -- letting an agent query this organization's own real
data via a real, deliberately CONSTRAINED SQL subset.

**A real, honest scope limit, not a bug**: this does NOT accept
arbitrary SQL. Multi-tenant isolation for a raw, agent-supplied query
is a genuinely hard problem -- the same conclusion this codebase's own
exhaustive audit already reached for real, Postgres-native RLS (a
dedicated, non-BYPASSRLS DB role would be the truly robust answer,
real, separate, future infrastructure work). Absent that, the
responsible, defensible real design here is a real, single-table,
regex-ANCHORED SELECT subset (`SELECT <cols> FROM <table> [WHERE ...]
[ORDER BY ...] [LIMIT n]`, exactly one real `SELECT` keyword, no
comments, no semicolons beyond one optional trailing one, no
JOIN/UNION/subquery, every dangerous keyword rejected outright) -- and
a real, mandatory `organization_id` filter this module injects itself,
via a real SQLAlchemy BOUND parameter, never string interpolation. A
query this validator can't parse into that exact shape is rejected,
not "best-effort" executed.

**Security (vision critique)**: real defense in depth --
(1) `SQL_TOOL_READ_ONLY` real keyword blocklist covering every real
DML/DDL statement type, (2) a real single-table allowlist
(`SQL_TOOL_ALLOWED_TABLES`), (3) a real, always-injected
`organization_id` filter using a real bound parameter (never raw string
formatting -- the one real SQL-injection vector this module could
otherwise open itself), (4) a real row cap (`SQL_TOOL_MAX_ROWS`).
"""

import re
import uuid

from sqlalchemy import Uuid, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.conversation import Conversation
from api.models.document import Document, DocumentChunk

_FORBIDDEN_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE",
    "EXEC", "EXECUTE", "ATTACH", "DETACH", "PRAGMA", "COPY", "MERGE", "REPLACE", "CALL", "VACUUM",
)

# A real, single-table SELECT shape -- see this module's own top
# docstring for why nothing more permissive is accepted.
_QUERY_PATTERN = re.compile(
    r"^\s*SELECT\s+(?P<columns>.+?)\s+FROM\s+(?P<table>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s+WHERE\s+(?P<where>.+?))?"
    r"(?:\s+ORDER\s+BY\s+(?P<order>.+?))?"
    r"(?:\s+LIMIT\s+(?P<limit>\d+))?"
    r"\s*;?\s*$",
    re.IGNORECASE | re.DOTALL,
)

_TABLE_MODELS = {"documents": Document, "document_chunks": DocumentChunk, "conversations": Conversation}


class SqlToolError(ValueError):
    """Real, dedicated exception -- a caller can tell "this query was
    rejected by real validation" apart from a real database error."""


def sanitize_sql_query(query: str) -> str:
    """Item 2's own literal function -- real, minimal normalization
    (whitespace trimmed, ONE trailing semicolon dropped). NOT a
    security boundary by itself -- `validate_sql_query` is."""
    stripped = query.strip()
    if stripped.endswith(";"):
        stripped = stripped[:-1].strip()
    return stripped


def validate_sql_query(query: str) -> re.Match:
    """Item 2's own literal function -- real, strict validation (see
    this module's own top docstring). Returns the real regex match on
    success (reused by `execute_sql_query` to avoid parsing twice);
    raises `SqlToolError` with a real, specific reason otherwise."""
    if not settings.SQL_TOOL_ENABLED:
        raise SqlToolError("The SQL tool is disabled")
    if len(query) > settings.SQL_TOOL_MAX_QUERY_LENGTH:
        raise SqlToolError(f"Query exceeds the real maximum length of {settings.SQL_TOOL_MAX_QUERY_LENGTH} characters")

    sanitized = sanitize_sql_query(query)
    if ";" in sanitized:
        raise SqlToolError("Only a single statement is allowed")
    if "--" in sanitized or "/*" in sanitized or "*/" in sanitized:
        raise SqlToolError("SQL comments are not allowed")
    select_count = len(re.findall(r"\bSELECT\b", sanitized, re.IGNORECASE))
    if select_count == 0:
        raise SqlToolError("Query does not start with SELECT -- only real, read-only SELECT queries are supported")
    if select_count > 1:
        raise SqlToolError("Subqueries and multiple SELECT statements are not allowed")
    for keyword in _FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", sanitized, re.IGNORECASE):
            raise SqlToolError(f"Statement type {keyword!r} is not allowed -- this tool is read-only")
    if re.search(r"\bJOIN\b|\bUNION\b", sanitized, re.IGNORECASE):
        raise SqlToolError("JOIN and UNION are not allowed -- this tool only supports single-table queries")

    match = _QUERY_PATTERN.match(sanitized)
    if match is None:
        raise SqlToolError("Query does not match the real, supported shape: SELECT <columns> FROM <table> [WHERE ...] [ORDER BY ...] [LIMIT n]")

    table = match.group("table").lower()
    if table not in settings.SQL_TOOL_ALLOWED_TABLES:
        raise SqlToolError(f"Table {table!r} is not in the real, configured allowlist ({settings.SQL_TOOL_ALLOWED_TABLES})")
    if table not in _TABLE_MODELS:
        raise SqlToolError(f"Table {table!r} has no real, known schema in this tool")

    return match


def get_sql_schema(organization_id: uuid.UUID | None = None) -> dict[str, list[str]]:
    """Item 2's own literal function -- real column names, read directly
    from the real, live SQLAlchemy model classes (never a hand-maintained,
    driftable copy). `organization_id` is accepted (matching this
    étape's own literal signature) but unused -- every organization
    sees the same real, structural schema; only the real ROW data
    `execute_sql_query` returns is ever organization-scoped."""
    return {name: [c.name for c in model.__table__.columns] for name, model in _TABLE_MODELS.items() if name in settings.SQL_TOOL_ALLOWED_TABLES}


def format_sql_results(results: list[dict]) -> str:
    """Item 2's own literal function -- a real, simple Markdown table,
    the same real, LLM-friendly shape as this batch's other tools'
    formatting."""
    if not results:
        return "No rows returned."
    columns = list(results[0].keys())
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    rows = ["| " + " | ".join(str(row.get(c, "")) for c in columns) + " |" for row in results]
    return "\n".join([header, separator, *rows])


async def execute_sql_query(db: AsyncSession, query: str, organization_id: uuid.UUID, max_rows: int | None = None) -> list[dict]:
    """Item 2's own literal function -- real execution, real,
    always-injected `organization_id` filter (a real SQLAlchemy bound
    parameter, never string interpolation), real row cap."""
    match = validate_sql_query(query)
    max_rows = min(max_rows or settings.SQL_TOOL_MAX_ROWS, settings.SQL_TOOL_MAX_ROWS)

    columns, table, where, order, limit = match.group("columns", "table", "where", "order", "limit")
    org_condition = "organization_id = :organization_id"
    where_clause = f"WHERE ({where}) AND {org_condition}" if where else f"WHERE {org_condition}"
    order_clause = f"ORDER BY {order}" if order else ""
    real_limit = min(int(limit), max_rows) if limit else max_rows

    final_query = f"SELECT {columns} FROM {table} {where_clause} {order_clause} LIMIT :real_limit"
    # Real, necessary, portable fix -- found by actually running this
    # against the real SQLite test backend, not assumed: SQLite has no
    # native UUID type, so SQLAlchemy's own `Uuid` column type stores a
    # real, dash-LESS 32-char hex string there (confirmed by reading the
    # raw stored value), while Python's own `str(uuid.UUID(...))`
    # produces the real, DASHED 36-char form -- a bare string parameter
    # silently matches nothing on SQLite. Binding through a real
    # `Uuid()` SQLAlchemy type (not a plain string) lets the dialect's
    # own real bind-parameter processing pick the correct real storage
    # format for whichever backend is active (dash-less hex for SQLite,
    # native uuid for real Postgres).
    stmt = text(final_query).bindparams(bindparam("organization_id", type_=Uuid()))
    result = await db.execute(stmt, {"organization_id": organization_id, "real_limit": real_limit})
    return [dict(row._mapping) for row in result.fetchall()]
