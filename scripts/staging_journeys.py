"""Guarded live journeys. Run with --execute only after provisioning .env.staging.

S3 settings and provider keys may also come from the process. Optionally set
STAGING_JOURNEY_MODEL (otherwise LLM_DEFAULT_MODEL from staging, or the API
default). No general dotenv, existing API, remote Redis, or Celery beat is used.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import math
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import dotenv_values
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

if __package__:
    from .staging_target import (
        ROOT,
        STAGING_ENV,
        StagingTargetError,
        isolated_environment,
        staging_url,
    )
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.staging_target import (
        ROOT,
        STAGING_ENV,
        StagingTargetError,
        isolated_environment,
        staging_url,
    )

S3_VARIABLES = (
    "S3_ENDPOINT_URL",
    "S3_REGION",
    "S3_ACCESS_KEY_ID",
    "S3_SECRET_ACCESS_KEY",
    "S3_BUCKET_NAME",
    "S3_DOCUMENTS_BUCKET_NAME",
    "S3_VOICE_BUCKET_NAME",
)
PROVIDER_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "gemini": "GEMINI_API_KEY",
}
JOURNEYS = (
    "registration-login",
    "upload-txt",
    "upload-pdf",
    "upload-docx",
    "search",
    "chat-citations",
    "workflow-worker",
    "evaluation",
    "quality-alert",
)


class JourneyFailure(RuntimeError):
    """Only safe, deliberately authored diagnostics belong in this exception."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise JourneyFailure(message)


def prerequisites() -> tuple[dict[str, str], list[str]]:
    values = dict(dotenv_values(STAGING_ENV)) if STAGING_ENV.is_file() else {}
    values.update(os.environ)
    missing = [name for name in S3_VARIABLES if not values.get(name)]
    model = (
        values.get("STAGING_JOURNEY_MODEL")
        or values.get("LLM_DEFAULT_MODEL")
        or "claude-3-5-sonnet-20241022"
    )
    provider = (
        model.split("/", 1)[0]
        if "/" in model
        else (
            "anthropic"
            if model.startswith("claude-")
            else "openai"
            if model.startswith("gpt-")
            else ""
        )
    )
    key = PROVIDER_KEYS.get(provider)
    if key is None:
        missing.append("STAGING_JOURNEY_MODEL (supported provider required)")
    elif not values.get(key):
        missing.append(key)
    try:
        env = isolated_environment(staging_url())
    except StagingTargetError as exc:
        return {}, missing + [str(exc)]
    for name in (*S3_VARIABLES, *PROVIDER_KEYS.values()):
        if values.get(name):
            env[name] = values[name]
    env.update(
        {
            "LLM_DEFAULT_MODEL": model.split("/", 1)[-1],
            "STAGING_JOURNEY_PROVIDER": provider,
            "CELERY_BROKER_URL": "redis://127.0.0.1:6379/0",
            "CELERY_RESULT_BACKEND": "redis://127.0.0.1:6379/1",
            "RATE_LIMIT_REDIS_URL": "redis://127.0.0.1:6379/2",
            "CACHE_REDIS_URL": "redis://127.0.0.1:6379/3",
            "AWS_EC2_METADATA_DISABLED": "true",
        }
    )
    return env, missing


def fixture_files(tag: str) -> dict[str, tuple[bytes, str]]:
    import pymupdf
    from docx import Document

    text = f"The journey code is {tag}. Support is available on Monday at 09:00."
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((72, 72), text)
        pdf_bytes = pdf.tobytes()
    docx = Document()
    docx.add_paragraph(text)
    stream = io.BytesIO()
    docx.save(stream)
    return {
        "txt": (text.encode(), "text/plain"),
        "pdf": (pdf_bytes, "application/pdf"),
        "docx": (
            stream.getvalue(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
    }


class Child:
    def __init__(self, service: str, port: int, queue: str, env: dict[str, str]):
        self.errors: deque[str] = deque(maxlen=8)
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "scripts.staging_journeys",
                "--service",
                service,
                "--port",
                str(port),
                "--queue",
                queue,
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.reader = threading.Thread(target=self._drain, daemon=True)
        self.reader.start()

    def _drain(self) -> None:
        if self.process.stdout is None:
            return
        for line in self.process.stdout:
            # Raw child logs can contain credentials. Retain exception names only.
            self.errors.extend(
                re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)\b", line)
            )

    def check(self) -> None:
        code = self.process.poll()
        if code is not None:
            raise JourneyFailure(
                f"local service exited: code={code}, exception_types={list(self.errors)}"
            )

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
                print("PARTIAL: local child required forced termination before cleanup")
        self.reader.join(timeout=5)
        if self.process.stdout is not None:
            self.process.stdout.close()


class Journeys:
    def __init__(
        self,
        client: httpx.AsyncClient,
        session_factory,
        timeout: float,
        *,
        children=(),
        tag=None,
    ):
        self.client = client
        self.session_factory = session_factory
        self.timeout = timeout
        self.children = children
        self.tag = tag or uuid.uuid4().hex
        require(
            bool(re.fullmatch(r"[0-9a-f]{32}", self.tag)), "invalid fixture run marker"
        )
        self.email = f"journey-{self.tag}@example.com"
        self.password = secrets.token_urlsafe(28)
        self.org_id: uuid.UUID | None = None
        self.documents: set[uuid.UUID] = set()
        self.agent_id: str | None = None
        self.failures = 0
        self.statuses: set[int] = set()

    async def request(self, method: str, path: str, **kwargs):
        response = await self.client.request(method, path, **kwargs)
        self.statuses.add(response.status_code)
        require(
            200 <= response.status_code < 300,
            f"HTTP {response.status_code}; response body withheld",
        )
        return response.json() if response.content else None

    async def poll(self, path: str) -> dict:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            for child in self.children:
                child.check()
            result = await self.request("GET", path)
            if result["status"] == "completed":
                return result
            require(
                result["status"] not in {"failed", "cancelled", "stopped", "timeout"},
                f"asynchronous job status={result['status']}; error payload withheld",
            )
            await asyncio.sleep(2)
        raise JourneyFailure("asynchronous job timed out")

    async def step(self, name: str, action) -> None:
        self.statuses.clear()
        started = time.monotonic()
        try:
            counts = await action()
        except (JourneyFailure, httpx.RequestError, SQLAlchemyError) as exc:
            self.failures += 1
            reason = str(exc) if isinstance(exc, JourneyFailure) else type(exc).__name__
            print(f"{name}: FAIL HTTP={sorted(self.statuses)} reason={reason}")
        else:
            print(f"{name}: PASS HTTP={sorted(self.statuses)} rows={counts}")
        finally:
            print(f"{name}: duration_seconds={time.monotonic() - started:.2f}")

    async def authenticate(self) -> dict:
        await self.request(
            "POST",
            "/auth/register",
            json={
                "email": self.email,
                "password": self.password,
                "accept_terms": True,
            },
        )
        login = await self.request(
            "POST",
            "/auth/login",
            json={
                "email": self.email,
                "password": self.password,
            },
        )
        self.client.headers["Authorization"] = "Bearer " + login["access_token"]
        organizations = (await self.request("GET", "/organizations"))["items"]
        require(len(organizations) == 1, "expected exactly one new organization")
        self.org_id = uuid.UUID(organizations[0]["id"])
        return {"users": 1, "organizations": 1}

    async def upload(self, extension: str, content: bytes, content_type: str) -> dict:
        from sqlalchemy import func, select
        from api.models.document import DocumentChunk

        require(self.org_id is not None, "registration/login prerequisite failed")
        document = await self.request(
            "POST",
            f"/organizations/{self.org_id}/documents",
            files={"file": (f"journey.{extension}", content, content_type)},
        )
        require(
            document["organization_id"] == str(self.org_id), "document tenant mismatch"
        )
        require(not document["is_duplicate"], "fresh fixture unexpectedly deduplicated")
        document_id = uuid.UUID(document["id"])
        await self.poll(f"/documents/{document_id}/status")
        async with self.session_factory() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(DocumentChunk)
                .where(
                    DocumentChunk.document_id == document_id,
                )
            )
        require(
            count is not None and count > 0,
            "completed document has no persisted chunks",
        )
        self.documents.add(document_id)
        return {"documents": 1, "chunks": count}

    async def search(self) -> dict:
        require(bool(self.documents), "no successfully indexed fixture")
        results = (
            await self.request(
                "POST",
                f"/organizations/{self.org_id}/search",
                json={"query": f"What is the journey code {self.tag}?", "top_k": 5},
            )
        )["results"]
        require(bool(results), "retrieval returned no rows")
        require(
            all(uuid.UUID(row["document_id"]) in self.documents for row in results),
            "retrieval returned a document outside this run",
        )
        return {"retrieved_chunks": len(results)}

    async def chat(self) -> dict:
        from sqlalchemy import select
        from api.models.agent_run import AgentRunRecord
        from api.models.citation import Citation
        from api.models.document import Document
        from api.models.response import Response

        require(bool(self.documents), "no successfully indexed fixture")
        agent = await self.request(
            "POST",
            f"/organizations/{self.org_id}/agents",
            json={
                "name": "Staging journey",
                "model_config": {
                    "model": os.environ["LLM_DEFAULT_MODEL"],
                    "provider": os.environ["STAGING_JOURNEY_PROVIDER"],
                },
                "system_prompt": "Answer from the retrieved context and cite your sources.",
                "citation_required": True,
            },
        )
        self.agent_id = agent["id"]
        key = await self.request(
            "POST",
            f"/organizations/{self.org_id}/api-keys",
            json={"name": "Staging journey", "scopes": ["chat:write"]},
        )
        chat = await self.request(
            "POST",
            "/v1/chat",
            headers={"X-API-Key": key["key"]},
            json={"agent_id": self.agent_id, "message": "When is support available?"},
        )
        require(
            bool(chat["response"].strip()) and bool(chat["citations"]),
            "empty answer or citations",
        )
        async with self.session_factory() as session:
            run = await session.get(
                AgentRunRecord, uuid.UUID(chat["metadata"]["run_id"])
            )
            require(
                run is not None and run.organization_id == self.org_id,
                "chat run tenant mismatch",
            )
            response = await session.get(Response, run.response_id)
            require(
                response is not None and response.organization_id == self.org_id,
                "response tenant mismatch",
            )
            citations = (
                await session.scalars(
                    select(Citation).where(Citation.response_id == response.id)
                )
            ).all()
            require(
                len(citations) == len(chat["citations"]) and bool(citations),
                "citation row count mismatch",
            )
            for citation in citations:
                require(
                    citation.document_id in self.documents,
                    "citation is not attached to a fixture document",
                )
                document = await session.get(Document, citation.document_id)
                require(
                    document is not None and document.organization_id == self.org_id,
                    "citation tenant mismatch",
                )
        return {"responses": 1, "citations": len(citations)}

    async def workflow(self) -> dict:
        require(self.org_id is not None, "registration/login prerequisite failed")
        workflow = await self.request(
            "POST",
            f"/organizations/{self.org_id}/workflows",
            json={
                "name": "Staging journey",
                "nodes": [
                    {
                        "id": "start",
                        "type": "trigger",
                        "data": {},
                        "position": {"x": 0, "y": 0},
                    },
                    {
                        "id": "check",
                        "type": "condition",
                        "data": {
                            "condition": "marker == 7",
                            "output_key": "checked",
                        },
                        "position": {"x": 100, "y": 0},
                    },
                ],
                "edges": [{"id": "start-check", "source": "start", "target": "check"}],
            },
        )
        run = await self.request(
            "POST", f"/workflows/{workflow['id']}/run", json={"input": {"marker": 7}}
        )
        completed = await self.poll(f"/workflows/runs/{run['id']}")
        require(
            completed["output"]["checked"]["result"] is True,
            "worker did not execute the condition",
        )
        trace = await self.request("GET", f"/workflows/runs/{run['id']}/trace")
        require(len(trace) == 2, "worker trace must contain both real node executions")
        return {"workflow_runs": 1, "node_executions": len(trace)}

    async def evaluation(self) -> dict:
        require(bool(self.documents), "no successfully indexed fixture")
        dataset = await self.request(
            "POST",
            f"/organizations/{self.org_id}/datasets",
            json={"name": "Staging journey"},
        )
        await self.request(
            "POST",
            f"/datasets/{dataset['id']}/questions",
            json={
                "question": "When is support available?",
                "expected_answer": "Monday at 09:00",
                "expected_documents": [
                    {"document_id": str(document), "relevance_score": 1.0}
                    for document in self.documents
                ],
            },
        )
        job = await self.request(
            "POST",
            f"/datasets/{dataset['id']}/evaluate",
            json={
                "model_config_override": {
                    "model": os.environ["LLM_DEFAULT_MODEL"],
                    "provider": os.environ["STAGING_JOURNEY_PROVIDER"],
                },
            },
        )
        completed = await self.poll(f"/jobs/{job['id']}")
        require(
            completed["completed_questions"] == 1
            and completed["results"]["failed_questions"] == 0,
            "evaluation completed with failed or missing questions",
        )
        results = await self.request("GET", f"/jobs/{job['id']}/results")
        require(
            results["total"] == 1 and len(results["items"]) == 1,
            "evaluation result row missing",
        )
        result = results["items"][0]
        require(bool(result["actual_answer"].strip()), "evaluation generated no answer")
        metrics = result["metrics"]
        for name in ("recall_at_5", "mrr", "ndcg_at_5"):
            value = metrics.get(name)
            require(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                and 0 <= value <= 1,
                f"missing/invalid real metric: {name}",
            )
        print(
            "evaluation: metrics="
            + str({name: metrics[name] for name in ("recall_at_5", "mrr", "ndcg_at_5")})
        )
        return {"evaluation_questions": 1, "evaluation_results": 1}

    async def alert(self) -> dict:
        require(self.org_id is not None, "registration/login prerequisite failed")
        rule = await self.request(
            "POST",
            f"/organizations/{self.org_id}/quality-alerts/rules",
            json={
                "name": "Staging journey",
                "metric": "recall_at_5",
                "operator": "lt",
                "threshold": 0.8,
            },
        )
        rules = await self.request(
            "GET", f"/organizations/{self.org_id}/quality-alerts/rules"
        )
        require(
            any(row["id"] == rule["id"] for row in rules),
            "quality alert was not persisted",
        )
        return {"alert_rules": 1}

    async def cleanup(self) -> None:
        import boto3
        from sqlalchemy import delete, func, select
        from api.models.organization import (
            Organization,
            OrganizationMember,
            OrganizationRole,
        )
        from api.models.user import User
        from api.models.document import Document, DocumentChunk
        from api.models.citation import Citation
        from api.models.response import Response

        async with self.session_factory() as session:
            user = await session.scalar(select(User).where(User.email == self.email))
            if user is None:
                print(
                    "cleanup: PASS users=0 organizations=0 (registration persisted nothing)"
                )
                return
            org_ids = (
                await session.scalars(
                    select(Organization.id)
                    .join(
                        OrganizationMember,
                        OrganizationMember.organization_id == Organization.id,
                    )
                    .where(
                        OrganizationMember.user_id == user.id,
                        OrganizationMember.role == OrganizationRole.owner,
                    )
                )
            ).all()
            document_ids = (
                await session.scalars(
                    select(Document.id).where(Document.organization_id.in_(org_ids))
                )
            ).all()
            response_ids = (
                await session.scalars(
                    select(Response.id).where(Response.organization_id.in_(org_ids))
                )
            ).all()
            s3 = boto3.client(
                "s3",
                endpoint_url=os.environ["S3_ENDPOINT_URL"],
                region_name=os.environ["S3_REGION"],
                aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
                aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
            )
            removed = 0
            try:
                for org_id in org_ids:
                    prefix = f"documents/{org_id}/"
                    pages = s3.get_paginator("list_objects_v2").paginate(
                        Bucket=os.environ["S3_DOCUMENTS_BUCKET_NAME"],
                        Prefix=prefix,
                    )
                    for page in pages:
                        for item in page.get("Contents", []):
                            require(
                                item["Key"].startswith(prefix),
                                "cleanup storage scope mismatch",
                            )
                            s3.delete_object(
                                Bucket=os.environ["S3_DOCUMENTS_BUCKET_NAME"],
                                Key=item["Key"],
                            )
                            removed += 1
                    remaining_objects = s3.list_objects_v2(
                        Bucket=os.environ["S3_DOCUMENTS_BUCKET_NAME"],
                        Prefix=prefix,
                        MaxKeys=1,
                    )
                    require(
                        remaining_objects["KeyCount"] == 0,
                        "cleanup left fixture storage objects",
                    )
                if org_ids:
                    await session.execute(
                        delete(Organization).where(Organization.id.in_(org_ids))
                    )
                await session.execute(
                    delete(User).where(User.id == user.id, User.email == self.email)
                )
                await session.commit()
                remaining = await session.scalar(
                    select(func.count())
                    .select_from(User)
                    .where(User.email == self.email)
                )
                org_remaining = await session.scalar(
                    select(func.count())
                    .select_from(Organization)
                    .where(
                        Organization.id.in_(org_ids),
                    )
                )
                chunks_remaining = await session.scalar(
                    select(func.count())
                    .select_from(DocumentChunk)
                    .where(
                        DocumentChunk.document_id.in_(document_ids),
                    )
                )
                citations_remaining = await session.scalar(
                    select(func.count())
                    .select_from(Citation)
                    .where(
                        Citation.response_id.in_(response_ids),
                    )
                )
                require(
                    all(
                        count == 0
                        for count in (
                            remaining,
                            org_remaining,
                            chunks_remaining,
                            citations_remaining,
                        )
                    ),
                    "cleanup left fixture rows",
                )
                print(
                    f"cleanup: PASS users=0 organizations=0 chunks=0 citations=0 "
                    f"removed_storage_objects={removed}; audit logs retained"
                )
            except (BotoCoreError, ClientError, SQLAlchemyError, JourneyFailure) as exc:
                # Keep recoverable DB references when storage cleanup fails.
                print(
                    f"cleanup: FAIL type={type(exc).__name__}; fixture run marker={self.tag}; "
                    "retry with --cleanup-run <marker> --execute"
                )
                raise
            finally:
                s3.close()


def configure_queue(queue: str):
    from api.tasks.celery_app import celery_app

    require(
        queue.startswith("staging-journey-")
        and bool(re.fullmatch(r"staging-journey-[0-9a-f]{32}", queue)),
        "invalid isolated worker queue",
    )
    require(
        not celery_app.conf.task_routes,
        "explicit Celery routes prevent guaranteed queue isolation",
    )
    celery_app.conf.task_default_queue = queue
    celery_app.conf.task_default_exchange = queue
    celery_app.conf.task_default_routing_key = queue
    return celery_app


@asynccontextmanager
async def local_services(env: dict[str, str], timeout: float):
    from redis import Redis

    redis = Redis(
        host="127.0.0.1", port=6379, socket_connect_timeout=3, socket_timeout=3
    )
    try:
        require(redis.ping(), "local Redis did not answer PING")
        queue = "staging-journey-" + uuid.uuid4().hex
        celery_app = configure_queue(queue)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        children: list[Child] = []
        try:
            children.append(Child("worker", port, queue, env))
            children.append(Child("api", port, queue, env))
            async with httpx.AsyncClient(
                base_url=f"http://127.0.0.1:{port}", timeout=timeout, trust_env=False
            ) as client:
                deadline = time.monotonic() + min(timeout, 120)
                while time.monotonic() < deadline:
                    for child in children:
                        child.check()
                    try:
                        response = await client.get("/openapi.json")
                    except httpx.ConnectError:
                        await asyncio.sleep(1)
                        continue
                    if response.status_code == 200:
                        break
                    await asyncio.sleep(1)
                else:
                    raise JourneyFailure("local API readiness timed out")
                replies = await asyncio.to_thread(
                    celery_app.control.ping,
                    destination=[queue + "@localhost"],
                    timeout=10,
                )
                require(bool(replies), "isolated local worker did not answer PING")
                yield client, children
        finally:
            for child in reversed(children):
                child.close()
            # Never purge the shared broker: only this run's exact queue keys.
            redis.delete(
                queue,
                "_kombu.binding." + queue,
                *(queue + "\x06\x16" + str(priority) for priority in (3, 6, 9)),
            )
    finally:
        redis.close()


async def execute(env: dict[str, str], timeout: float) -> int:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(
        staging_url(), poolclass=NullPool, connect_args={"timeout": 10}
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with local_services(env, timeout) as (client, children):
            journeys = Journeys(client, session_factory, timeout, children=children)
            try:
                await journeys.step("registration-login", journeys.authenticate)
                for extension, (content, content_type) in fixture_files(
                    journeys.tag
                ).items():

                    async def upload(
                        extension=extension, content=content, content_type=content_type
                    ):
                        return await journeys.upload(extension, content, content_type)

                    await journeys.step("upload-" + extension, upload)
                for name, action in (
                    ("search", journeys.search),
                    ("chat-citations", journeys.chat),
                    ("workflow-worker", journeys.workflow),
                    ("evaluation", journeys.evaluation),
                    ("quality-alert", journeys.alert),
                ):
                    await journeys.step(name, action)
                return 1 if journeys.failures else 0
            finally:
                # Stop API/worker writes before deleting only this new user's rows.
                for child in reversed(children):
                    child.close()
                await journeys.cleanup()
    finally:
        await engine.dispose()


async def retry_cleanup(marker: str) -> int:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(
        staging_url(), poolclass=NullPool, connect_args={"timeout": 10}
    )
    try:
        async with httpx.AsyncClient() as client:
            runner = Journeys(
                client,
                async_sessionmaker(engine, expire_on_commit=False),
                30,
                tag=marker,
            )
            await runner.cleanup()
        return 0
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Create and clean up live staging fixtures",
    )
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument(
        "--cleanup-run",
        help="Retry cleanup of a fixture run marker after a cleanup failure",
    )
    parser.add_argument("--service", choices=("api", "worker"), help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--queue", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()
    require(args.timeout > 0, "timeout must be positive")
    if args.cleanup_run:
        require(
            bool(re.fullmatch(r"[0-9a-f]{32}", args.cleanup_run)),
            "invalid fixture run marker",
        )
    env, missing = prerequisites()
    if missing:
        for name in missing:
            print("BLOCKED_EXTERNAL_PROVIDER: " + name)
        for name in JOURNEYS:
            print(f"{name}: BLOCKED_EXTERNAL_PROVIDER HTTP=[] rows=NOT_MEASURED")
        return 2
    if not args.execute and not args.service:
        print(
            "VERIFIED: staging prerequisites present; dry run, no connection or process started"
        )
        return 0
    if args.service:
        require(
            os.environ.get("RAG_ENV_FILE") == str(STAGING_ENV),
            "child must use the guarded staging environment",
        )
        require(
            os.environ.get("DATABASE_URL") == env["DATABASE_URL"],
            "child database target mismatch",
        )
        celery_app = configure_queue(args.queue)
        if args.service == "worker":
            celery_app.worker_main(
                [
                    "worker",
                    "--pool=solo",
                    "--concurrency=1",
                    "--loglevel=WARNING",
                    "--queues",
                    args.queue,
                    "--hostname",
                    args.queue + "@localhost",
                ]
            )
        else:
            import uvicorn

            require(0 < args.port < 65536, "invalid local API port")
            uvicorn.run(
                "api.main:app",
                host="127.0.0.1",
                port=args.port,
                log_level="warning",
                access_log=False,
            )
        return 0
    os.environ.clear()
    os.environ.update(env)
    if args.cleanup_run:
        return asyncio.run(retry_cleanup(args.cleanup_run))
    return asyncio.run(execute(env, args.timeout))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except JourneyFailure as exc:
        print("FAIL: " + str(exc))
        raise SystemExit(1) from None
    except (
        httpx.RequestError,
        OSError,
        SQLAlchemyError,
        RedisError,
        BotoCoreError,
        ClientError,
    ) as exc:
        print("FAIL: " + type(exc).__name__ + "; sensitive exception payload withheld")
        raise SystemExit(1) from None
