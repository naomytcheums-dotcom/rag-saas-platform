import subprocess
import sys
from pathlib import Path


def test_dotenv_loader_import_does_not_require_legacy_rag_dependencies():
    source_directory = Path(__file__).resolve().parent.parent / "src"
    script = """
import builtins

original_import = builtins.__import__

def import_without_legacy_dependencies(name, *args, **kwargs):
    if name.split(".", 1)[0] in {"anthropic", "retrieval"}:
        raise ModuleNotFoundError(f"blocked optional dependency: {name}")
    return original_import(name, *args, **kwargs)

builtins.__import__ = import_without_legacy_dependencies
from generation import load_dotenv_if_present
assert callable(load_dotenv_if_present)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=source_directory,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
