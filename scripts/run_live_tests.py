"""Run the EXTERNAL-dependency tests (payment-provider sandboxes, third-party OAuth grants) without ever exposing the real `.env`.

    python scripts/run_live_tests.py --provider stripe --env-file C:\\secrets\\stripe-test.env [-- <extra pytest arguments>]

The env file (KEY=VALUE lines) must live OUTSIDE the repository. Only the names allowed for the chosen provider are read; everything else in
the file is ignored. Stripe and Paystack keys must be TEST keys (`sk_test_...`): a live key is refused before anything starts. The rest of the
environment is the sanitized local stack of scripts/run_isolated_tests.py (local PostgreSQL / Redis / MinIO, no other credential).
Staging tests are not run here: they target the hosted staging database and have their own guarded runner (scripts/staging_validate.py).
Nothing printed contains a secret."""

import argparse
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_isolated_tests import IsolationRefused, build_test_environment  # noqa: E402

PROVIDERS = {
    "stripe": {"names": ("STRIPE_SECRET_KEY", "STRIPE_TEST_PRICE_ID"), "optional": ("STRIPE_WEBHOOK_SECRET", "STRIPE_TEST_WEBHOOK_PAYLOAD_FILE", "STRIPE_TEST_WEBHOOK_SIGNATURE"), "tests": ("tests/test_billing_stripe_live.py",), "test_key": "STRIPE_SECRET_KEY"},
    "paystack": {"names": ("PAYSTACK_SECRET_KEY", "PAYSTACK_TEST_PLAN_CODE"), "optional": ("PAYSTACK_TEST_WEBHOOK_PAYLOAD_FILE", "PAYSTACK_TEST_WEBHOOK_SIGNATURE"), "tests": ("tests/test_billing_paystack_live.py",), "test_key": "PAYSTACK_SECRET_KEY"},
    "google-drive": {"names": ("GOOGLE_DRIVE_REFRESH_TOKEN", "GOOGLE_DRIVE_CLIENT_ID", "GOOGLE_DRIVE_CLIENT_SECRET"),
                     "tests": ("tests/test_google_drive_extraction_integration.py", "tests/test_documents_integration.py"), "test_key": None},
    "onedrive": {"names": ("ONEDRIVE_REFRESH_TOKEN", "ONEDRIVE_CLIENT_ID", "ONEDRIVE_CLIENT_SECRET"), "tests": ("tests/test_onedrive_extraction_integration.py",), "test_key": None},
    "notion": {"names": ("NOTION_API_TOKEN",), "tests": ("tests/test_notion_extraction_integration.py",), "test_key": None},
}


def read_env_file(path: Path) -> dict[str, str]:
    """KEY=VALUE lines; comments and blank lines ignored; surrounding quotes removed."""
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def build_live_environment(parent: Mapping[str, str], provider: str, file_values: Mapping[str, str]) -> dict[str, str]:
    """The local sanitized environment plus ONLY the provider's allowed variables. Raises IsolationRefused (message without any value)."""
    spec = PROVIDERS[provider]
    chosen = {name: file_values[name] for name in spec["names"] if file_values.get(name)}
    missing = [name for name in spec["names"] if name not in chosen]
    if missing:
        raise IsolationRefused("the env file does not define: " + ", ".join(missing))
    chosen.update({name: file_values[name] for name in spec.get("optional", ()) if file_values.get(name)})
    key_name = spec["test_key"]
    if key_name and not chosen[key_name].startswith(("sk_test_", "rk_test_")):
        raise IsolationRefused(f"{key_name} must be a TEST key (sk_test_...): a live or unrecognised key is refused")
    env = build_test_environment(parent)
    env.update(chosen)
    return env


def main(argv: list[str] | None = None, parent: Mapping[str, str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    pytest_args: list[str] = []
    if "--" in argv:
        split = argv.index("--")
        argv, pytest_args = argv[:split], argv[split + 1:]
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    parser.add_argument("--env-file", required=True, help="KEY=VALUE file outside the repository")
    parser.add_argument("--check", action="store_true", help="validate the inputs and exit without running the tests")
    args = parser.parse_args(argv)
    parent = os.environ if parent is None else parent
    path = Path(args.env_file).resolve()
    if ROOT in path.parents:
        print("refused: the env file must be outside the repository", file=sys.stderr)
        return 2
    if not path.is_file():
        print("refused: the env file does not exist", file=sys.stderr)
        return 2
    try:
        env = build_live_environment(parent, args.provider, read_env_file(path))
    except IsolationRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(f"inputs accepted for '{args.provider}': local stack, no other credential, {len(PROVIDERS[args.provider]['names'])} provider variable(s) passed.")
    if args.check:
        return 0
    targets = pytest_args or ["-v", "-rfEsx", *PROVIDERS[args.provider]["tests"]]
    return subprocess.call([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *targets], cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
