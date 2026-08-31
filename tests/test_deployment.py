"""
Phase 06: structural validation of the deployment config files -- the
Dockerfile, .dockerignore, and render.yaml. This is NOT a build test:
no Docker daemon is available in the environment this was built in, so
`docker build` itself has never been run against this Dockerfile. What's
checked here is the kind of thing a typo or a dropped line would break
silently -- the required instructions are present, in the right order,
pointing at real files in this repo -- same spirit as
tests/test_injection_test_set.py validating its data file's shape rather
than running a live attack.
"""

import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _dockerfile_lines():
    text = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]


# ---- Dockerfile -------------------------------------------------------

def test_dockerfile_exists():
    assert (PROJECT_ROOT / "Dockerfile").exists()


def test_dockerfile_starts_from_a_pinned_python_base_image():
    lines = _dockerfile_lines()
    from_lines = [l for l in lines if l.startswith("FROM")]
    assert len(from_lines) == 1
    assert "python:3.13" in from_lines[0]


def test_dockerfile_installs_from_the_real_requirements_file():
    assert (PROJECT_ROOT / "requirements.txt").exists()
    lines = _dockerfile_lines()
    assert any("requirements.txt" in l for l in lines if l.startswith("COPY"))
    assert any("pip install" in l and "requirements.txt" in l for l in lines if l.startswith("RUN"))


def test_dockerfile_exposes_the_streamlit_default_port():
    lines = _dockerfile_lines()
    assert "EXPOSE 8501" in lines


def test_dockerfile_runs_the_real_dashboard_entrypoint():
    assert (PROJECT_ROOT / "dashboard" / "app.py").exists()
    lines = _dockerfile_lines()
    cmd_lines = [l for l in lines if l.startswith("CMD")]
    assert len(cmd_lines) == 1
    assert "dashboard/app.py" in cmd_lines[0]
    assert "--server.port=8501" in cmd_lines[0]


def test_dockerfile_declares_a_healthcheck():
    lines = _dockerfile_lines()
    assert any(l.startswith("HEALTHCHECK") for l in lines)


def test_dockerfile_instruction_order_is_from_then_workdir_then_copy_then_run_then_cmd():
    # A COPY before pip install would bust the layer cache on every source
    # change instead of only when requirements.txt changes -- order isn't
    # cosmetic here.
    lines = _dockerfile_lines()
    instructions = [l.split()[0] for l in lines]
    assert instructions.index("FROM") < instructions.index("WORKDIR")
    first_copy = instructions.index("COPY")
    first_run_pip = next(i for i, l in enumerate(lines) if l.startswith("RUN") and "pip install" in l)
    assert first_copy < first_run_pip
    assert instructions.index("CMD") == len(instructions) - 1


# ---- .dockerignore -------------------------------------------------------

def test_dockerignore_excludes_secrets_and_heavy_derived_data():
    text = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
    for must_exclude in [".env", "data/chroma/", "data/raw/", ".venv/", ".git/"]:
        assert must_exclude in text, f"{must_exclude} should be dockerignored"


# ---- render.yaml -----------------------------------------------------

def test_render_yaml_is_valid_and_points_at_the_real_dockerfile():
    config = yaml.safe_load((PROJECT_ROOT / "render.yaml").read_text(encoding="utf-8"))
    services = config["services"]
    assert len(services) == 1
    service = services[0]
    assert service["runtime"] == "docker"
    assert (PROJECT_ROOT / service["dockerfilePath"].removeprefix("./")).exists()
    assert service["healthCheckPath"] == "/_stcore/health"


def test_render_yaml_does_not_commit_secret_values():
    config = yaml.safe_load((PROJECT_ROOT / "render.yaml").read_text(encoding="utf-8"))
    env_vars = config["services"][0]["envVars"]
    secret_keys = {"ANTHROPIC_API_KEY", "GOOGLE_SERVICE_ACCOUNT_FILE", "GOOGLE_CALENDAR_ID", "GOOGLE_SHEET_ID"}
    declared = {var["key"]: var for var in env_vars}
    assert secret_keys <= declared.keys()
    for key in secret_keys:
        assert declared[key].get("sync") is False, f"{key} must be sync: false, not a committed value"
