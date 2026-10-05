"""Verify API import without optional integrations or any network connection."""

from __future__ import annotations

import importlib.abc
import os
import secrets
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OPTIONAL_MODULES = frozenset({
    "docling", "deepeval", "dspy", "mem0", "lightrag",
    "beeai_framework", "presidio_analyzer", "openlineage", "opa_client",
})


class BlockOptionalImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.partition(".")[0] in OPTIONAL_MODULES:
            raise ModuleNotFoundError(f"Optional dependency blocked: {fullname}", name=fullname)
        return None


def deny_network(event: str, args: tuple) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        raise RuntimeError("Network access is disabled during the import-only check.")


def main() -> int:
    safe_environment = {
        key: value for key, value in os.environ.items()
        if key in {
            "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE",
            "APPDATA", "LOCALAPPDATA", "PROGRAMFILES", "COMSPEC", "PATHEXT",
        }
    }
    with tempfile.TemporaryDirectory(prefix="rag-import-check-") as directory:
        os.environ.clear()
        os.environ.update(safe_environment)
        os.environ.update({
            "RAG_ENV_FILE": str(Path(directory) / ".env"),
            "PYTHON_DOTENV_DISABLED": "1",
            "DATABASE_URL": "postgresql+asyncpg://test:test@127.0.0.1:1/import_check",
            "SUPPORT_EMAIL": "import-check@example.invalid",
            "JWT_SECRET_KEY": secrets.token_hex(32),
            "SESSION_MIDDLEWARE_SECRET": secrets.token_hex(32),
            "AUDIT_LOG_HMAC_SECRET_KEY": secrets.token_hex(32),
            "LITELLM_LOCAL_MODEL_COST_MAP": "True",
            "HF_HUB_OFFLINE": "1",
            "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
            "AWS_EC2_METADATA_DISABLED": "true",
            "MEM0_TELEMETRY": "False",
        })
        sys.path.insert(0, str(ROOT))
        for name in list(sys.modules):
            if name.partition(".")[0] in OPTIONAL_MODULES:
                del sys.modules[name]
        sys.meta_path.insert(0, BlockOptionalImports())
        sys.addaudithook(deny_network)
        try:
            import api.main  # noqa: F401
        except Exception as exc:
            print(f"ERROR: {type(exc).__name__}", file=sys.stderr)
            for frame in traceback.extract_tb(exc.__traceback__):
                print(f"  {frame.filename}:{frame.lineno} in {frame.name}", file=sys.stderr)
            if isinstance(exc, ImportError):
                print(f"  module: {exc.name}", file=sys.stderr)
            return 1
        print("OK: api.main imported with all 9 optional module roots blocked; no lifespan or network.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
