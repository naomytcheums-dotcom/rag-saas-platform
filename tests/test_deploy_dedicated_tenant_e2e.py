"""Specs 10.4.7 - 10.4.11 (dedicated tenant, dedicated database, private / on-premise / VPC deployment), executed for real with Docker on this machine.

Three complete stacks are provisioned with the real script (deploy/dedicated-tenant/provision.sh) from the real image built from Dockerfile.api:
tenant A and tenant B (normal), tenant C (air-gapped overlay: no route to the internet). Each is its own compose project: API, worker, beat, PostgreSQL with pgvector,
Redis, MinIO. What is proved:

  * every service is up and healthy, the migrations are at head, /health and /health/ready answer;
  * no database / Redis / MinIO port is published, the API is published on the loopback address only;
  * two tenants are isolated: separate databases (an account created in A does not exist in B), separate secrets and keys, a token minted by A is refused by B, A's API
    container cannot reach B's containers on the network;
  * the worker consumes tasks (celery inspect ping), a document is uploaded, ingested with the local embedding model (no download), retrieved by search;
  * the air-gapped tenant: the API container has no route to the internet (an outbound request fails), the published port works through the edge proxy, ingestion and
    search still work, and a real answer comes from a local Ollama attached to the private network (the model never leaves the machine).

Opt-in (heavy: three stacks, a few GB of RAM, minutes):
    RUN_DEPLOY_E2E=1 DEDICATED_IMAGE=rag-saas-api:infra-test HF_CACHE_DIR=~/.cache/huggingface scripts/run_tests_local.sh tests/test_deploy_dedicated_tenant_e2e.py -q
DEDICATED_IMAGE must be an image built from Dockerfile.api; HF_CACHE_DIR a Hugging Face cache holding sentence-transformers/all-MiniLM-L6-v2 (and the cross-encoder
reranker); OLLAMA_CONTAINER (default rag-test-ollama) a running Ollama container with OLLAMA_MODEL (default qwen2.5:3b) pulled; without it the answer step is skipped."""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "deploy" / "dedicated-tenant"
sys.path.insert(0, str(ROOT / "scripts"))

pytestmark = pytest.mark.skipif(os.environ.get("RUN_DEPLOY_E2E") != "1" or not shutil.which("docker"), reason="set RUN_DEPLOY_E2E=1 (needs Docker and a built image)")
IMAGE = os.environ.get("DEDICATED_IMAGE", "rag-saas-api:infra-test")
OLLAMA_CONTAINER = os.environ.get("OLLAMA_CONTAINER", "rag-test-ollama")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
SERVICES = {"db", "redis", "minio", "api", "worker", "beat"}


def run(*cmd, check=True, timeout=900, **kw):
    env = dict(os.environ, MSYS_NO_PATHCONV="1")
    env.update(kw.pop("env", {}))
    return subprocess.run(list(cmd), capture_output=True, text=True, check=check, timeout=timeout, env=env, cwd=kw.pop("cwd", None))


def bash() -> str:
    if sys.platform != "win32":
        return "bash"
    for root in (shutil.which("git") and Path(shutil.which("git")).resolve().parents) or []:
        if (root / "bin" / "bash.exe").is_file():
            return str(root / "bin" / "bash.exe")
    return shutil.which("bash") or "bash"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class Tenant:
    def __init__(self, name: str, **options):
        self.name = f"{name}-{uuid.uuid4().hex[:5]}"
        self.port = free_port()
        self.options = options
        self.env_file = DIR / f".env.{self.name}"

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def compose(self, *args, check=True, timeout=600):
        files = ["-f", "docker-compose.tenant.yml"] + (["-f", "docker-compose.airgapped.yml"] if self.options.get("AIRGAPPED") else [])
        return run("docker", "compose", "--env-file", self.env_file.name, *files, *args, check=check, timeout=timeout, cwd=DIR)

    def provision(self):
        env = {"TENANT": self.name, "API_PORT": str(self.port), "IMAGE": IMAGE, "COOKIE_SECURE": "false", "WEB_CONCURRENCY": "1", **{k: str(v) for k, v in self.options.items()}}
        result = run(bash(), "provision.sh", env=env, check=False, timeout=1500, cwd=DIR)
        assert result.returncode == 0, f"provision failed:\n{result.stdout[-2500:]}\n{result.stderr[-2500:]}"
        return result

    def destroy(self):
        if self.env_file.exists():
            self.compose("down", "-v", "--remove-orphans", check=False)
            self.env_file.unlink()

    def exec(self, service: str, *cmd, check=True, timeout=120):
        return self.compose("exec", "-T", service, *cmd, check=check, timeout=timeout)

    def container(self, service: str) -> str:
        return self.compose("ps", "-q", service).stdout.strip().splitlines()[0]

    def env_value(self, key: str) -> str:
        return next(line.split("=", 1)[1] for line in self.env_file.read_text().splitlines() if line.startswith(key + "="))


def wait_ready(tenant: Tenant, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"{tenant.base}/health/ready", timeout=5).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(3)
    pytest.fail(f"{tenant.name} never became ready:\n{tenant.compose('logs', '--tail', '40', 'api', check=False).stdout[-2000:]}")


@pytest.fixture(scope="module")
def image():
    if run("docker", "image", "inspect", IMAGE, check=False).returncode != 0:
        pytest.skip(f"image {IMAGE} not found: build it with `docker build -f Dockerfile.api -t {IMAGE} .` or set DEDICATED_IMAGE")
    return IMAGE


@pytest.fixture(scope="module")
def models_dir():
    path = os.environ.get("HF_CACHE_DIR")
    if not path:
        pytest.skip("HF_CACHE_DIR (a Hugging Face cache with all-MiniLM-L6-v2) is required for the offline ingestion steps")
    return str(Path(path).expanduser().resolve()).replace("\\", "/")


@pytest.fixture(scope="module")
def tenants(image, models_dir):
    a = Tenant("ta", MODELS_DIR=models_dir, HF_HUB_OFFLINE=1)
    b = Tenant("tb", MODELS_DIR=models_dir, HF_HUB_OFFLINE=1)
    made = []
    try:
        for tenant in (a, b):
            made.append(tenant)
            tenant.provision()
            wait_ready(tenant)
        yield a, b
    finally:
        for tenant in made:
            tenant.destroy()


@pytest.fixture(scope="module")
def airgapped(image, models_dir):
    c = Tenant("tc", MODELS_DIR=models_dir, AIRGAPPED=1)
    try:
        c.provision()
        wait_ready(c)
        yield c
    finally:
        c.destroy()


def register(base: str, label: str):
    email, password = f"{label}-{uuid.uuid4().hex[:8]}@example.com", f"Tenant-{uuid.uuid4().hex}-Aa1!"
    response = httpx.post(f"{base}/auth/register", json={"email": email, "password": password, "full_name": label, "accept_terms": True}, timeout=60)
    assert response.status_code in (200, 201), response.text
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    org = httpx.post(f"{base}/organizations", json={"name": f"{label} {uuid.uuid4().hex[:6]}"}, headers=headers, timeout=60).json()
    return {"email": email, "password": password, "headers": headers, "token": token, "org_id": org["id"]}


# ----------------------------------------------------------------------------- one tenant: up, healthy, migrated, closed


def test_every_service_is_running_healthy_and_migrated(tenants):
    a, _ = tenants
    running = {line.strip() for line in a.compose("ps", "--services", "--status", "running").stdout.splitlines() if line.strip()}
    assert SERVICES <= running, running
    assert httpx.get(f"{a.base}/health", timeout=10).status_code == 200
    assert httpx.get(f"{a.base}/health/ready", timeout=10).status_code == 200
    assert "(head)" in a.exec("api", "python", "-m", "alembic", "current").stdout
    pong = a.exec("worker", "celery", "-A", "api.tasks.celery_app", "inspect", "ping", "--timeout", "20", timeout=90).stdout
    assert "pong" in pong, pong
    assert "beat" in a.compose("logs", "beat", check=False).stdout.lower()


def test_no_internal_port_is_published_and_the_api_listens_on_loopback_only(tenants):
    a, _ = tenants
    published = json.loads("[" + ",".join(line for line in a.compose("ps", "--format", "json").stdout.splitlines() if line.strip()) + "]")
    by_service = {entry["Service"]: entry.get("Publishers") or [] for entry in published}
    for service in ("db", "redis", "minio", "worker", "beat"):
        assert not [p for p in by_service[service] if p.get("PublishedPort")], f"{service} publishes a port"
    api_ports = [p for p in by_service["api"] if p.get("PublishedPort")]
    assert api_ports and all(p["URL"] in ("127.0.0.1", "::1") for p in api_ports), api_ports


def test_the_generated_secrets_are_distinct_per_tenant_and_the_file_is_private(tenants):
    a, b = tenants
    for key in ("DB_PASSWORD", "JWT_SECRET_KEY", "SESSION_MIDDLEWARE_SECRET", "AUDIT_LOG_HMAC_SECRET_KEY", "ENCRYPTION_MASTER_KEY", "SECRET_ENCRYPTION_KEY", "S3_SECRET_ACCESS_KEY"):
        assert a.env_value(key) != b.env_value(key), key
        assert len(a.env_value(key)) >= 32
    if sys.platform != "win32":
        assert oct(a.env_file.stat().st_mode & 0o777) == "0o600"


# ----------------------------------------------------------------------------- two tenants: isolated


def test_an_account_exists_only_in_its_own_tenant(tenants):
    a, b = tenants
    user_a = register(a.base, "alpha")
    count = lambda t: int(t.exec("db", "psql", "-U", "ragsaas", "-d", "ragsaas", "-tAc", "select count(*) from users").stdout.strip())  # noqa: E731
    assert count(a) == 1 and count(b) == 0
    # the same e-mail can be registered in B: it is another database
    other = httpx.post(f"{b.base}/auth/register", json={"email": user_a["email"], "password": user_a["password"], "full_name": "same", "accept_terms": True}, timeout=60)
    assert other.status_code in (200, 201), other.text
    assert count(a) == 1 and count(b) == 1
    # a token minted by A is not accepted by B (different signing key, different database)
    assert httpx.get(f"{a.base}/auth/me", headers=user_a["headers"], timeout=20).status_code == 200
    assert httpx.get(f"{b.base}/auth/me", headers=user_a["headers"], timeout=20).status_code in (401, 403)
    # and A's organization does not exist in B
    assert httpx.get(f"{b.base}/organizations/{user_a['org_id']}", headers=user_a["headers"], timeout=20).status_code in (401, 403, 404)


def test_one_tenants_containers_cannot_reach_the_others(tenants):
    a, b = tenants
    target = run("docker", "inspect", b.container("api"), "--format", "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}").stdout.split()[0]
    probe = f"import socket;s=socket.socket();s.settimeout(4);s.connect(('{target}',8000))"
    assert a.exec("api", "python", "-c", probe, check=False).returncode != 0, "tenant A reached tenant B's API over the network"
    networks_a = set(run("docker", "inspect", a.container("db"), "--format", "{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}").stdout.split())
    networks_b = set(run("docker", "inspect", b.container("db"), "--format", "{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}").stdout.split())
    assert networks_a and networks_b and not (networks_a & networks_b)


# ----------------------------------------------------------------------------- the product works inside the dedicated stack


def _ingest_and_search(base: str, user: dict):
    sys.modules.pop("e2e_full_journey", None)
    import e2e_full_journey as journey  # the project's own end-to-end client

    api = journey.Api(base)
    content = "Zorblax handbook. The Zorblax support line opens every Tuesday at 14:30 Douala time and the escalation code is PELICAN-7421."
    upload = api.http.post(f"/organizations/{user['org_id']}/documents", headers=user["headers"], files={"file": ("zorblax.txt", content.encode(), "text/plain")})
    assert upload.status_code in (200, 201, 202), upload.text
    doc_id = upload.json().get("id") or upload.json()["document"]["id"]
    final = journey.wait_docs(api, user, {doc_id}, 600)
    assert final.get(doc_id, {}).get("status") == "completed", final
    code, results = journey.search(api, user, "What is the escalation code of the support line?")
    assert code == 200 and any("PELICAN-7421" in json.dumps(r) for r in results), results
    return api, journey


def test_ingestion_with_the_local_embedding_model_and_search_work_in_the_tenant(tenants):
    a, _ = tenants
    user = register(a.base, "ingest")
    _ingest_and_search(a.base, user)
    # the document bytes are in the tenant's own MinIO, not elsewhere
    listing = a.exec("api", "python", "-c", "import boto3,os;c=boto3.client('s3',endpoint_url=os.environ['S3_ENDPOINT_URL'],aws_access_key_id=os.environ['S3_ACCESS_KEY_ID'],"
                     "aws_secret_access_key=os.environ['S3_SECRET_ACCESS_KEY'],region_name='us-east-1');print(c.list_objects_v2(Bucket='documents').get('KeyCount'))").stdout.strip()
    assert int(listing) >= 1


# ----------------------------------------------------------------------------- air-gapped / on-premise


def test_the_air_gapped_api_has_no_route_to_the_internet_but_serves_through_the_edge(airgapped):
    c = airgapped
    assert httpx.get(f"{c.base}/health", timeout=10).status_code == 200  # published by the edge proxy
    api_container = c.container("api")
    networks = run("docker", "inspect", api_container, "--format", "{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}").stdout.split()
    assert len(networks) == 1, f"the API must be on the internal network only: {networks}"
    internal = run("docker", "network", "inspect", networks[0], "--format", "{{.Internal}}").stdout.strip()
    assert internal == "true"
    outbound = c.exec("api", "python", "-c",
                      "import urllib.request;urllib.request.urlopen('https://example.com',timeout=6)", check=False, timeout=60)
    assert outbound.returncode != 0, "the air-gapped API reached the internet"
    for service in ("worker", "beat", "db", "redis", "minio"):
        assert c.container(service)
    dns = c.exec("api", "python", "-c", "import socket;socket.gethostbyname('example.com')", check=False, timeout=60)
    assert dns.returncode != 0


def test_the_air_gapped_tenant_ingests_searches_and_answers_with_a_local_model(airgapped):
    c = airgapped
    user = register(c.base, "airgap")
    api, journey = _ingest_and_search(c.base, user)
    if run("docker", "inspect", OLLAMA_CONTAINER, check=False).returncode != 0:
        pytest.skip(f"no running {OLLAMA_CONTAINER}: ingestion and search were proved, the local-model answer was not")
    network = run("docker", "inspect", c.container("api"), "--format", "{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}").stdout.strip()
    run("docker", "network", "connect", "--alias", "ollama", network, OLLAMA_CONTAINER)  # the local LLM joins the private network (a compose profile does the same in a real install)
    try:
        agent = api.http.post(f"/organizations/{user['org_id']}/agents", headers=user["headers"], json={
            "name": "airgap agent", "system_prompt": "Answer only from the provided context.", "model_config": {"provider": "ollama", "model": OLLAMA_MODEL}})
        assert agent.status_code in (200, 201), agent.text
        res = api.chat(user["headers"], agent.json()["id"], "What is the escalation code of the Zorblax support line?")
        assert res["status"] == 200 and not res["error"], res
        assert re.search(r"PELICAN-?7421", res["text"]), res["text"]
    finally:
        run("docker", "network", "disconnect", network, OLLAMA_CONTAINER, check=False)
