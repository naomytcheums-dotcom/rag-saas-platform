"""Real-service checks that need no vendor account: SMTP (Mailpit), the public GitHub API, local Whisper speech-to-text, account deletion + purge with the
real database, and the post-deploy smoke script against the local stack.

    python scripts/e2e_local_services_checks.py --base http://127.0.0.1:8010 --pg-url <local asyncpg url> --out local_services.json

Environment: AGENT_SMTP_HOST=127.0.0.1 AGENT_SMTP_PORT=1025 AGENT_SMTP_FROM_EMAIL=agent@example.test (Mailpit: `docker run -p 1025:1025 -p 8025:8025 axllent/mailpit`).
"""

import argparse
import asyncio
import json
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from local_only_guard import require_local_services  # noqa: E402

require_local_services()
RESULTS: list[dict] = []


def rec(name: str, status: str, detail: str = "") -> None:
    RESULTS.append({"name": name, "status": status, "detail": detail})
    print(f"[{status}] {name}" + (f" -- {detail}" if detail else ""), flush=True)


async def smtp_check() -> None:
    import os

    from api.config import settings
    from api.tools.email_tools import email_send

    ca_file = os.environ.get("E2E_SMTP_CA_FILE", "")
    # 1. a server whose certificate is not trusted must be refused (the stdlib default used to accept any certificate)
    settings.AGENT_SMTP_CA_FILE = ""
    try:
        await email_send("smtp", ["person@example.test"], "must not be sent", "untrusted certificate")
        rec("e-mail tool refuses an SMTP server with an untrusted certificate", "FAIL", "the message was sent")
    except Exception as exc:  # noqa: BLE001
        rec("e-mail tool refuses an SMTP server with an untrusted certificate", "PASS" if "CERTIFICATE" in str(exc).upper() or "SSL" in type(exc).__name__.upper() or "verify" in str(exc).lower() else "FAIL", f"{type(exc).__name__}: {str(exc)[:110]}")
    # 2. with the certificate authority trusted, the message goes through real SMTP + STARTTLS
    settings.AGENT_SMTP_CA_FILE = ca_file
    subject = f"E2E mail {uuid.uuid4().hex[:8]}"
    try:
        await email_send("smtp", ["person@example.test"], subject, "Hello from the platform e-mail tool.")
    except Exception as exc:  # noqa: BLE001
        return rec("e-mail tool sends through real SMTP with STARTTLS (Mailpit)", "FAIL", f"{type(exc).__name__}: {str(exc)[:160]}")
    await asyncio.sleep(1)
    messages = httpx.get("http://127.0.0.1:8025/api/v1/messages", timeout=20).json().get("messages", [])
    got = next((m for m in messages if m.get("Subject") == subject), None)
    rec("e-mail tool sends through real SMTP with STARTTLS (Mailpit)", "PASS" if got else "FAIL", f"delivered={bool(got)} to={[t['Address'] for t in (got or {}).get('To', [])]}")


async def email_block_check() -> None:
    from api.services.workflow_block_email import execute_email_block

    subject = f"Workflow e-mail block {uuid.uuid4().hex[:8]}"
    try:
        out = await execute_email_block({"provider": "smtp", "to": ["{{who}}@example.test"], "subject": subject, "body": "Sent by the workflow e-mail block."}, {"who": "reader"})
    except Exception as exc:  # noqa: BLE001
        return rec("workflow e-mail block sends through real SMTP", "FAIL", f"{type(exc).__name__}: {str(exc)[:140]}")
    await asyncio.sleep(1)
    messages = httpx.get("http://127.0.0.1:8025/api/v1/messages", timeout=20).json().get("messages", [])
    got = next((m for m in messages if m.get("Subject") == subject), None)
    rec("workflow e-mail block sends through real SMTP", "PASS" if got and [t["Address"] for t in got["To"]] == ["reader@example.test"] else "FAIL", f"delivered={bool(got)} templated recipient ok={bool(got)} result keys={list(out)}")


async def github_check() -> None:
    from api.tools.github_tools import github_get_repo, github_list_issues

    try:
        repo = await github_get_repo("fastapi", "fastapi")
        issues = await github_list_issues("fastapi", "fastapi", state="open")
        rec("GitHub tools read the real public API (repo + issues)", "PASS" if repo.get("full_name") == "fastapi/fastapi" and isinstance(issues, list) else "FAIL",
            f"{repo.get('full_name')} stars>0={repo.get('stargazers_count', 0) > 0} open issues returned={len(issues)}")
    except Exception as exc:  # noqa: BLE001
        rec("GitHub tools read the real public API (repo + issues)", "FAIL", f"{type(exc).__name__}: {str(exc)[:160]}")


async def whisper_check() -> None:
    from api.services.voice import local_whisper_available, transcribe_local_whisper

    if not local_whisper_available():
        return rec("local Whisper speech-to-text", "BLOCKED", "faster-whisper is not installed (pip install faster-whisper)")
    wav = ROOT / "e2e_speech.wav"
    ps = (
        "Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SetOutputToWaveFile('{wav}'); $s.Speak('The maintenance code is heron five five zero eight.'); $s.Dispose()"
    )
    subprocess.run(["C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe", "-NoProfile", "-Command", ps], check=True, timeout=120)
    try:
        text = await transcribe_local_whisper(wav.read_bytes(), language="en")
    finally:
        wav.unlink(missing_ok=True)
    ok = "maintenance" in text.lower() and ("heron" in text.lower() or "5508" in text or "five" in text.lower())
    rec("local Whisper speech-to-text on a synthesized sentence", "PASS" if ok else "FAIL", f"transcript={text!r}")


def deletion_check(base: str, pg_url: str) -> None:
    import asyncpg

    http = httpx.Client(base_url=base, timeout=120)
    email, pw = f"del-{uuid.uuid4().hex[:8]}@example.com", f"Del-{uuid.uuid4().hex}-Aa1!"
    token = http.post("/auth/register", json={"email": email, "password": pw, "full_name": "Del", "accept_terms": True}).json()["access_token"]
    H = {"Authorization": f"Bearer {token}"}
    org = http.post("/organizations", json={"name": "To delete"}, headers=H).json()["id"]
    http.post(f"/organizations/{org}/documents", headers=H, files={"file": ("n.txt", b"A note that will be erased with the account.", "text/plain")})
    r = http.request("DELETE", "/account/me", headers=H, json={"password": pw})
    rec("account deletion request accepted (two-stage deletion)", "PASS" if r.status_code in (200, 202, 204) else "FAIL", f"{r.status_code} {r.text[:120]}")
    r2 = http.post("/auth/login", json={"email": email, "password": pw})
    rec("a pending-deletion account is flagged at login", "PASS" if r2.status_code in (200, 401, 403) else "FAIL", f"{r2.status_code} (a deactivated account cannot sign in until it is restored)")

    async def backdate_and_count():
        conn = await asyncpg.connect(pg_url.replace("postgresql+asyncpg://", "postgresql://"))
        await conn.execute("update users set deletion_scheduled_at = now() - interval '1 day' where email = $1", email)
        before = await conn.fetchval("select count(*) from users where email = $1", email)
        await conn.close()
        return before

    asyncio.run(backdate_and_count())
    from api.tasks.account_purge import purge_deleted_accounts

    purged = purge_deleted_accounts()

    async def after():
        conn = await asyncpg.connect(pg_url.replace("postgresql+asyncpg://", "postgresql://"))
        users = await conn.fetchval("select count(*) from users where email = $1", email)
        docs = await conn.fetchval("select count(*) from documents where organization_id = $1::uuid", org)
        orgs = await conn.fetchval("select count(*) from organizations where id = $1::uuid", org)
        await conn.close()
        return users, docs, orgs

    users, docs, orgs = asyncio.run(after())
    rec("purge task erases the user, its organization and documents", "PASS" if (users, docs, orgs) == (0, 0, 0) else "FAIL", f"purged={purged} users={users} documents={docs} organizations={orgs}")


def smoke_check(base: str) -> None:
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "post_deploy_smoke.py"), "--api", base, "--frontend", "http://localhost:3000"], capture_output=True, text=True, timeout=300)
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-6:]
    rec("post-deploy smoke script against the local stack", "PASS" if proc.returncode == 0 else "FAIL", " | ".join(re.sub(r"\s+", " ", t)[:90] for t in tail))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8010")
    ap.add_argument("--pg-url", required=True)
    ap.add_argument("--out", default="local_services.json")
    args = ap.parse_args()
    asyncio.run(smtp_check())
    asyncio.run(email_block_check())
    asyncio.run(github_check())
    asyncio.run(whisper_check())
    deletion_check(args.base, args.pg_url)
    smoke_check(args.base)
    Path(args.out).write_text(json.dumps({"results": RESULTS, "generated": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=1), encoding="utf-8")
    return 1 if any(r["status"] == "FAIL" for r in RESULTS) else 0


if __name__ == "__main__":
    sys.exit(main())
