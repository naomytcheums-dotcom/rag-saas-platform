"""Metadata filters: the behaviour the existing tests do not pin down.

* `apply_metadata_filter` / `validate_filters` (used by the `search_kb` tool and the RAG workflow block): date bounds, number bounds, "any of" tags,
  the kill switch, and every malformed filter rejected with a ValueError;
* `build_metadata_filter_clauses` (used by the retrieval pipeline): the clauses are EXECUTED against a JSON column, on SQLite and, when the test
  database is PostgreSQL, on PostgreSQL too (a temporary table, gone with the connection), and the rows they keep are checked.
"""

import datetime as dt

import pytest
from sqlalchemy import JSON, Column, Integer, MetaData, Table, create_engine, select, text
from sqlalchemy.engine import make_url

from api.config import settings
from api.database_url import synchronous_database_url
from api.services.metadata_filtering import apply_metadata_filter, build_metadata_filter_clauses, validate_filters

RESULTS = [
    {"id": "a", "author": "ana", "created_date": "2024-01-10", "file_size": 100, "tags": ["hr", "policy"]},
    {"id": "b", "author": "bob", "created_date": "2024-03-01T12:00:00", "file_size": 2_000, "tags": ["finance"]},
    {"id": "c", "author": "ana", "created_date": "2024-06-30", "file_size": 5_000, "tags": []},
    {"id": "d", "author": None, "created_date": None, "file_size": None, "tags": None},
]


def _ids(results):
    return [r["id"] for r in results]


@pytest.fixture(autouse=True)
def _filtering_on(monkeypatch):
    monkeypatch.setattr(settings, "METADATA_FILTERING_ENABLED", True)


# ------------------------------------------------------------------ apply_metadata_filter (search_kb, workflow RAG block)


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        ({"author": "ana"}, ["a", "c"]),
        ({"created_date": "2024-01-10"}, ["a"]),
        ({"created_date": {"after": "2024-01-10"}}, ["b", "c"]),  # strictly after: "a" itself is excluded
        ({"created_date": {"before": "2024-06-30"}}, ["a", "b"]),  # strictly before
        ({"created_date": {"between": ["2024-01-10", "2024-03-01T12:00:00"]}}, ["a", "b"]),  # inclusive at both ends
        ({"created_date": {"after": dt.date(2024, 2, 1), "before": dt.datetime(2024, 7, 1)}}, ["b", "c"]),
        ({"file_size": 2_000}, ["b"]),
        ({"file_size": {"min": 2_000}}, ["b", "c"]),  # inclusive
        ({"file_size": {"max": 2_000}}, ["a", "b"]),  # inclusive
        ({"file_size": {"min": 101, "max": 4_999}}, ["b"]),
        ({"tags": ["finance", "legal"]}, ["b"]),  # any of
        ({"tags": "policy"}, ["a"]),  # a single tag is a one-element list
        ({"author": "ana", "file_size": {"min": 1_000}}, ["c"]),  # every filter must match
    ],
)
def test_each_field_type_keeps_exactly_the_matching_results(filters, expected):
    assert _ids(apply_metadata_filter(RESULTS, filters)) == expected


def test_a_result_without_the_field_never_matches():
    for filters in ({"author": "ana"}, {"created_date": {"before": "2100-01-01"}}, {"file_size": {"min": 0}}, {"tags": ["hr"]}):
        assert "d" not in _ids(apply_metadata_filter(RESULTS, filters)), filters


def test_no_filter_or_the_kill_switch_returns_every_result_as_a_new_list(monkeypatch):
    unchanged = apply_metadata_filter(RESULTS, {})
    assert unchanged == RESULTS and unchanged is not RESULTS
    monkeypatch.setattr(settings, "METADATA_FILTERING_ENABLED", False)
    passthrough = apply_metadata_filter(RESULTS, {"author": "nobody"})
    assert passthrough == RESULTS and passthrough is not RESULTS


@pytest.mark.parametrize(
    "filters",
    [
        {"owner": "ana"},  # not a filterable field
        {"created_date": {"since": "2024-01-01"}},
        {"created_date": {"between": ["2024-01-01"]}},
        {"created_date": {"between": "2024-01-01/2024-02-01"}},
        {"created_date": "not a date"},
        {"created_date": {"after": "31/12/2024"}},
        {"file_size": {"above": 10}},
        {"file_size": "100"},
        {"file_size": True},
    ],
)
def test_a_malformed_filter_is_rejected_before_anything_is_filtered(filters):
    with pytest.raises(ValueError):
        validate_filters(filters)
    with pytest.raises(ValueError):
        apply_metadata_filter(RESULTS, filters)


def test_too_many_filters_are_rejected(monkeypatch):
    monkeypatch.setattr(settings, "METADATA_FILTER_MAX_OPERATORS", 2)
    with pytest.raises(ValueError, match="Too many filters"):
        validate_filters({"author": "ana", "source": "x", "document_type": "pdf"})
    validate_filters({"author": "ana", "source": "x"})


# ------------------------------------------------------------------ build_metadata_filter_clauses, executed for real

ROWS = [
    (1, {"year": 2019, "dept": "hr"}),
    (2, {"year": 2020, "dept": "finance"}),
    (3, {"year": 2021, "dept": "finance"}),
    (4, {"year": 2022, "dept": "legal"}),
    (5, {"dept": "hr"}),  # no "year"
]

CASES = [
    ({"year": {"not_equals": 2020}}, [1, 3, 4]),  # a row without the key is NOT kept (SQL NULL), on both dialects
    ({"year": {"in": [2019, 2021]}}, [1, 3]),
    ({"year": {"not_in": [2019, 2021]}}, [2, 4]),
    ({"year": {"gte": 2021}}, [3, 4]),
    ({"year": {"lt": 2021}}, [1, 2]),
    ({"year": {"lte": 2021}}, [1, 2, 3]),
    ({"year": {"gt": 2021.5}}, [4]),
    ({"dept": {"not_equals": "finance"}}, [1, 4, 5]),
    ({"dept": {"in": ["hr", "legal"]}}, [1, 4, 5]),
    ({"dept": {"not_in": ["hr", "legal"]}}, [2, 3]),
    ({"dept": "finance", "year": {"gt": 2020}}, [3]),
]


def _table(prefixes=()):
    return Table("metadata_filter_probe", MetaData(), Column("id", Integer, primary_key=True), Column("metadata_json", JSON), prefixes=list(prefixes))


def _kept(connection, table, filters):
    clauses = build_metadata_filter_clauses(table.c.metadata_json, filters)
    return sorted(connection.execute(select(table.c.id).where(*clauses)).scalars())


@pytest.mark.parametrize(("filters", "expected"), CASES)
def test_the_sql_clauses_keep_the_right_rows_on_sqlite(filters, expected):
    engine = create_engine("sqlite://")
    table = _table()
    with engine.begin() as connection:
        table.create(connection)
        connection.execute(table.insert(), [{"id": i, "metadata_json": m} for i, m in ROWS])
        assert _kept(connection, table, filters) == expected
    engine.dispose()


@pytest.fixture
def postgres_connection():
    url = make_url(str(settings.DATABASE_URL))
    if not url.drivername.startswith("postgresql"):
        pytest.skip("the PostgreSQL half needs a PostgreSQL DATABASE_URL (disposable): the fast suite runs on SQLite")
    if (url.host or "") not in {"127.0.0.1", "localhost", "::1"} or "test" not in (url.database or ""):
        pytest.fail("refused: DATABASE_URL must be a local database whose name contains 'test'")
    engine = create_engine(synchronous_database_url(url))
    try:
        connection = engine.connect()
    except Exception as exc:  # noqa: BLE001
        engine.dispose()
        pytest.skip(f"PostgreSQL is not reachable ({type(exc).__name__})")
    transaction = connection.begin()
    try:
        yield connection
    finally:
        transaction.rollback()  # the temporary table and its rows disappear with the transaction
        connection.close()
        engine.dispose()


def test_the_sql_clauses_keep_the_same_rows_on_postgresql(postgres_connection):
    table = _table(prefixes=["TEMPORARY"])
    table.create(postgres_connection)
    postgres_connection.execute(table.insert(), [{"id": i, "metadata_json": m} for i, m in ROWS])
    assert postgres_connection.execute(text("SELECT count(*) FROM metadata_filter_probe")).scalar() == len(ROWS)
    for filters, expected in CASES:
        assert _kept(postgres_connection, table, filters) == expected, filters
