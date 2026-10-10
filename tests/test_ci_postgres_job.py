"""CI contract (Lot G): the PostgreSQL-specific tests are executed by a dedicated job, against a throw-away database the guard accepts."""

from pathlib import Path

import yaml

from disposable_pg_guard import disposable_pg_refusal

WORKFLOW = yaml.safe_load((Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
JOB = WORKFLOW["jobs"]["backend-postgres-tests"]
STEPS = {step.get("name", ""): step for step in JOB["steps"]}


def test_the_job_runs_a_pgvector_postgres_service_with_a_scratch_database():
    service = JOB["services"]["postgres"]
    assert "pgvector" in service["image"] and service["env"]["POSTGRES_DB"].endswith("scratch")


def test_the_job_applies_the_whole_chain_and_a_round_trip_before_the_tests():
    run = next(step["run"] for name, step in STEPS.items() if name.startswith("Apply the whole Alembic chain"))
    assert run.index("upgrade head") < run.index("downgrade -1") < run.rindex("upgrade head")


def test_the_target_the_job_gives_the_tests_is_accepted_by_the_guard_and_differs_from_the_application_url():
    env = next(step["env"] for name, step in STEPS.items() if name.startswith("PostgreSQL tests"))
    refusal = disposable_pg_refusal(env["RAG_DISPOSABLE_PG_URL"], env["RAG_DISPOSABLE_PG_CONFIRM"], env["DATABASE_URL"])
    assert refusal is None, refusal


def test_the_job_names_every_postgres_test_file():
    run = next(step["run"] for name, step in STEPS.items() if name.startswith("PostgreSQL tests"))
    for name in ("test_postgres_tenant_rls", "test_postgres_subscription_concurrency", "test_postgres_credits_concurrency", "test_postgres_invoice_concurrency"):
        assert name in run
    on_disk = {path.stem for path in (Path(__file__).parent).glob("test_postgres_*.py")}
    assert {name for name in on_disk if name not in run} <= {"test_postgres_integration"}, "a test_postgres_* file is not run by the job"
