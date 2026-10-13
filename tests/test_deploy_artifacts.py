"""The deployment files (deploy/) are checked against what the application really needs and against each vendor's published schema.

Why this file exists: the first versions of these files had never been run. Running them showed that every target set a bare `REDIS_URL` that the application never
reads (its Redis settings are CELERY_BROKER_URL / CELERY_RESULT_BACKEND / RATE_LIMIT_REDIS_URL) and left out three settings without which the API does not start; the
Railway health check would have failed the worker and beat services forever, and Fly would have health-checked the worker on a port it does not open.

Always run (no Docker, no network):
  * the environment contract: every target provides every setting the application requires, no target sets a bare REDIS_URL;
  * railway.*.json against Railway's JSON schema, the DigitalOcean app spec against the DigitalOcean App Spec schema (both vendored in tests/fixtures/deploy/);
  * fly.toml structure (process groups, health check only on the HTTP group, beat count), Kubernetes / Helm structure (beat is a single Recreate pod, probes exist);
  * the health endpoints those probes call exist in the application.

Opt-in (RUN_DEPLOY_TOOLING=1, needs Docker and the network for provider plugins): terraform fmt / init / validate for aws, gcp and azure, helm lint + template,
kubeconform -strict on the Kubernetes manifest and on both Helm renderings. This is the reproducible command:
  RUN_DEPLOY_TOOLING=1 scripts/run_tests_local.sh tests/test_deploy_artifacts.py -q"""

import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import jsonschema
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "deploy"

# Settings the application cannot start without, taken from the application itself, plus what the deployment must always provide.
REDIS_VARS = ("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", "RATE_LIMIT_REDIS_URL")
ENCRYPTION_VARS = ("ENCRYPTION_MASTER_KEY", "SECRET_ENCRYPTION_KEY")


def _required_settings() -> list[str]:
    from api.config import Settings

    return [name for name, field in Settings.model_fields.items() if field.is_required()]


def _contract() -> list[str]:
    return sorted(set(_required_settings()) | set(REDIS_VARS) | set(ENCRYPTION_VARS))


def test_the_contract_is_derived_from_the_application_not_copied():
    required = _required_settings()
    assert {"DATABASE_URL", "JWT_SECRET_KEY", "SESSION_MIDDLEWARE_SECRET", "SUPPORT_EMAIL", "AUDIT_LOG_HMAC_SECRET_KEY"} <= set(required), required
    assert "REDIS_URL" not in _contract()


def _text(relative: str) -> str:
    return (DEPLOY / relative).read_text(encoding="utf-8")


@pytest.mark.parametrize("relative", [
    "README.md", "railway/README.md", "fly/fly.toml", "kubernetes/rag-saas.yaml", "terraform/aws/variables.tf", "terraform/azure/main.tf",
    "dedicated-tenant/docker-compose.tenant.yml", "terraform/digitalocean/app.yaml", "render/render.api.yaml",
])
def test_every_target_provides_the_whole_environment_contract(relative):
    text = _text(relative)
    missing = [name for name in _contract() if name not in text]
    assert not missing, f"deploy/{relative} does not provide {missing}"
    assert "- { key: REDIS_URL" not in text and "REDIS_URL=" not in text.replace("RATE_LIMIT_REDIS_URL=", "").replace("CACHE_REDIS_URL=", ""), "bare REDIS_URL is ignored by the application"


def test_digitalocean_every_component_has_the_secrets_and_the_non_secret_support_email():
    spec = yaml.safe_load(_text("terraform/digitalocean/app.yaml"))
    for component in (*spec["services"], *spec["workers"]):
        keys = {entry["key"] for entry in component["envs"]}
        assert set(_contract()) - {"SUPPORT_EMAIL"} <= keys, (component["name"], set(_contract()) - keys)
        assert "SUPPORT_EMAIL" in keys
        for entry in component["envs"]:
            if entry["key"].endswith(("_KEY", "_SECRET", "_URL", "_BACKEND")) or entry["key"] in ("JWT_SECRET_KEY", "SESSION_MIDDLEWARE_SECRET"):
                assert entry.get("type") == "SECRET" and "value" not in entry, f"{component['name']}.{entry['key']} must be a SECRET without a value"


def test_render_every_component_has_the_contract():
    spec = yaml.safe_load(_text("render/render.api.yaml"))
    for service in spec["services"]:
        if service.get("type") == "cron":
            continue
        keys = {entry["key"] for entry in service["envVars"]}
        assert set(_contract()) <= keys, (service["name"], set(_contract()) - keys)


def test_dedicated_tenant_compose_exposes_neither_the_database_nor_redis_and_pins_one_beat():
    compose = yaml.safe_load(_text("dedicated-tenant/docker-compose.tenant.yml"))
    services = compose["services"]
    assert "ports" not in services["db"] and "ports" not in services["redis"]
    assert services["api"]["ports"][0].startswith("${BIND_ADDRESS:-127.0.0.1}:"), "published on loopback unless the operator opens it on purpose"
    assert set(_contract()) - {"DATABASE_URL"} <= set(services["api"]["environment"]) | {"DATABASE_URL"}
    assert services["worker"]["environment"] is services["api"]["environment"] or services["worker"]["environment"] == services["api"]["environment"]
    assert "deploy" not in services["beat"] or services["beat"]["deploy"].get("replicas", 1) == 1
    assert services["beat"]["command"].startswith("celery -A api.tasks.celery_app beat")


# ----------------------------------------------------------------------------- vendor schemas


@pytest.mark.parametrize("name", ["railway.api.json", "railway.worker.json", "railway.beat.json"])
def test_railway_files_validate_against_the_published_schema(name):
    schema = json.loads((FIXTURES / "railway.schema.json").read_text(encoding="utf-8"))
    config = json.loads(_text(f"railway/{name}"))
    jsonschema.validate(config, schema)
    assert config["build"] == {"builder": "DOCKERFILE", "dockerfilePath": "Dockerfile.api"}
    if name != "railway.api.json":
        assert "healthcheckPath" not in config["deploy"], "a worker does not listen on HTTP: a health check would fail every deployment"
        assert config["deploy"]["numReplicas"] == 1 and "celery -A api.tasks.celery_app" in config["deploy"]["startCommand"]
    else:
        assert config["deploy"]["healthcheckPath"] == "/health"
    assert "beat" in json.loads(_text("railway/railway.beat.json"))["deploy"]["startCommand"]


def test_railway_schema_rejects_a_wrong_value():
    """Negative control: the validation above is able to fail."""
    schema = json.loads((FIXTURES / "railway.schema.json").read_text(encoding="utf-8"))
    config = json.loads(_text("railway/railway.api.json"))
    config["deploy"]["restartPolicyType"] = "SOMETIMES"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(config, schema)


def _property_names(schema: dict, components: dict) -> set[str]:
    names = set(schema.get("properties", {}))
    if "$ref" in schema:
        names |= _property_names(components[schema["$ref"].rsplit("/", 1)[1]], components)
    for part in schema.get("allOf", []):
        names |= _property_names(part, components)
    return names


def test_digitalocean_app_spec_validates_against_the_published_schema():
    schema = json.loads((FIXTURES / "do_app_spec.schema.json").read_text(encoding="utf-8"))
    spec = yaml.safe_load(_text("terraform/digitalocean/app.yaml"))
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(spec))
    assert not errors, [error.message for error in errors]
    # the published schema leaves objects open, so unknown keys (typos) are checked explicitly against the properties it declares
    components = schema["components"]["schemas"]
    service_keys = _property_names(components["app_service_spec"], components)
    worker_keys = _property_names(components["app_worker_spec"], components)
    assert {"name", "dockerfile_path", "github", "http_port", "instance_count", "instance_size_slug", "health_check", "envs"} <= service_keys
    for service in spec["services"]:
        assert set(service) <= service_keys, set(service) - service_keys
    for worker in spec["workers"]:
        assert set(worker) <= worker_keys, set(worker) - worker_keys
    assert [worker["instance_count"] for worker in spec["workers"] if worker["name"] == "celery-beat"] == [1]


def test_digitalocean_schema_rejects_a_wrong_type():
    schema = json.loads((FIXTURES / "do_app_spec.schema.json").read_text(encoding="utf-8"))
    spec = yaml.safe_load(_text("terraform/digitalocean/app.yaml"))
    spec["services"][0]["http_port"] = "eighty"
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(spec))


# ----------------------------------------------------------------------------- Fly.io, Kubernetes, Helm


def test_fly_process_groups_and_health_check():
    config = tomllib.loads(_text("fly/fly.toml"))
    assert set(config["processes"]) == {"app", "worker", "beat"}
    assert config["processes"]["worker"].startswith("celery -A api.tasks.celery_app worker")
    assert config["processes"]["beat"].startswith("celery -A api.tasks.celery_app beat")
    # only the HTTP group is health-checked and routed; otherwise Fly checks the worker and the beat on a port they never open
    assert config["http_service"]["processes"] == ["app"] and config["http_service"]["internal_port"] == 8000
    assert config["http_service"]["checks"][0]["path"] == "/health"
    assert sorted(group for vm in config["vm"] for group in vm["processes"]) == ["app", "beat", "worker"]
    assert config["env"]["COOKIE_SECURE"] == "true" and config["env"]["CREDITS_ALLOW_UNPAID_TOPUP"] == "false"
    assert config["build"]["dockerfile"].endswith("Dockerfile.api") and (DEPLOY / "fly" / config["build"]["dockerfile"]).resolve().is_file()


def _k8s_documents():
    return [doc for doc in yaml.safe_load_all(_text("kubernetes/rag-saas.yaml")) if doc]


def test_kubernetes_beat_is_a_single_recreated_pod_and_probes_exist():
    by_name = {doc["metadata"]["name"]: doc for doc in _k8s_documents() if doc["kind"] == "Deployment"}
    beat = by_name["rag-saas-beat"]
    assert beat["spec"]["replicas"] == 1 and beat["spec"]["strategy"] == {"type": "Recreate"}
    api = by_name["rag-saas-api"]["spec"]["template"]["spec"]["containers"][0]
    assert api["readinessProbe"]["httpGet"]["path"] == "/health/ready" and api["livenessProbe"]["httpGet"]["path"] == "/health"
    assert api["envFrom"] == [{"secretRef": {"name": "rag-saas-secrets"}}]
    hpa = next(doc for doc in _k8s_documents() if doc["kind"] == "HorizontalPodAutoscaler")
    assert hpa["spec"]["minReplicas"] >= 2


def test_the_health_endpoints_the_probes_call_exist():
    from api.main import app

    paths = set(app.openapi()["paths"])
    assert "/health" in paths and "/health/ready" in paths


def test_helm_values_and_templates_stay_consistent_with_the_manifest():
    template = _text("helm/rag-saas/templates/workloads.yaml")
    values = yaml.safe_load(_text("helm/rag-saas/values.yaml"))
    assert values["beat"]["enabled"] is True and "always exactly 1" in _text("helm/rag-saas/values.yaml")
    assert "replicas: 1" in template.split("-beat")[1] and "Recreate" in template
    assert "/health/ready" in template and "/health" in template
    assert values["env"]["COOKIE_SECURE"] == "true" and values["env"]["CREDITS_ALLOW_UNPAID_TOPUP"] == "false"


# ----------------------------------------------------------------------------- opt-in: the real tools, in Docker

TOOLING = os.environ.get("RUN_DEPLOY_TOOLING") == "1"
needs_tooling = pytest.mark.skipif(not (TOOLING and shutil.which("docker")), reason="set RUN_DEPLOY_TOOLING=1 (needs Docker and the network)")


def _docker(*args: str, stdin: str | None = None, timeout: int = 900) -> subprocess.CompletedProcess:
    env = dict(os.environ, MSYS_NO_PATHCONV="1")
    return subprocess.run(["docker", "run", "--rm", *(["-i"] if stdin else []), *args], input=stdin, capture_output=True, text=True, timeout=timeout, env=env, check=False)


@needs_tooling
def test_terraform_fmt_is_clean():
    result = _docker("-v", f"{DEPLOY}:/w", "-w", "/w/terraform", "hashicorp/terraform:1.9", "fmt", "-check", "-recursive", "-diff")
    assert result.returncode == 0, result.stdout + result.stderr


@needs_tooling
@pytest.mark.parametrize("provider", ["aws", "gcp", "azure"])
def test_terraform_validate(provider, tmp_path):
    work = tmp_path / provider
    shutil.copytree(DEPLOY / "terraform" / provider, work)  # init writes .terraform/ and a lock file: never into the repository
    cache = tmp_path / "plugin-cache"
    cache.mkdir()
    base = ["-e", "TF_PLUGIN_CACHE_DIR=/cache", "-v", f"{work}:/w", "-v", f"{cache}:/cache", "-w", "/w", "hashicorp/terraform:1.9"]
    init = _docker(*base, "init", "-backend=false", "-input=false")
    assert init.returncode == 0, init.stdout + init.stderr
    validate = _docker(*base, "validate")
    assert validate.returncode == 0 and "valid" in validate.stdout.lower(), validate.stdout + validate.stderr


@needs_tooling
def test_helm_lint_template_and_kubeconform():
    chart = f"{DEPLOY / 'helm' / 'rag-saas'}:/chart"
    lint = _docker("-v", chart, "alpine/helm:3.16.2", "lint", "/chart")
    assert lint.returncode == 0, lint.stdout + lint.stderr
    for extra in ([], ["--set", "ingress.enabled=true"], ["--set", "worker.enabled=false", "--set", "beat.enabled=false"]):
        rendered = _docker("-v", chart, "alpine/helm:3.16.2", "template", "rel", "/chart", *extra)
        assert rendered.returncode == 0, rendered.stderr
        checked = _docker("ghcr.io/yannh/kubeconform:v0.6.7", "-strict", "-summary", "-kubernetes-version", "1.30.0", "-", stdin=rendered.stdout)
        assert checked.returncode == 0 and "Invalid: 0, Errors: 0" in checked.stdout, checked.stdout + checked.stderr
    manifest = _docker("-v", f"{DEPLOY / 'kubernetes'}:/m", "ghcr.io/yannh/kubeconform:v0.6.7", "-strict", "-summary", "-kubernetes-version", "1.30.0", "/m/rag-saas.yaml")
    assert manifest.returncode == 0 and "Invalid: 0, Errors: 0" in manifest.stdout, manifest.stdout + manifest.stderr
