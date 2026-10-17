#!/usr/bin/env python
"""Real validation of 10.3.9 / 13.5.8 (error tracking, Sentry).

    RUN_LIVE_VENDOR_VALIDATION=1 SENTRY_DSN=https://<key>@o<org>.ingest.sentry.io/<project> python scripts/validate_sentry_live.py

1. initializes Sentry exactly as the API and the Celery worker do (the product's `setup_error_tracking`) and checks it is active;
2. sends ONE info event titled "RAG platform validation event" straight to the ingest endpoint of that DSN and requires HTTP 200 with the event id
   (the SDK's own background transport hides rejections, so the acceptance is checked synchronously here). The event shows up in the project's issue
   list: delete it there.
"""
import asyncio
import json
import os
import sys
import time
import uuid
from urllib.parse import urlsplit

import httpx

sys.path.insert(0, os.path.dirname(__file__))
import _live_vendor as live  # noqa: E402


async def main() -> int:
    live.require_opt_in("Sentry (your project)", "one event, free")
    report = live.Report("error_tracking")
    if not live.have("SENTRY_DSN"):
        report.skipped("sentry", "SENTRY_DSN is not in the process environment")
        return report.finish()
    tracking = live.product("api.security.error_tracking")

    async def initialized():
        import sentry_sdk

        tracking.setup_error_tracking()
        assert tracking._initialized and sentry_sdk.get_client().is_active(), "setup_error_tracking() did not activate the SDK"
        return {"environment": tracking.settings.SENTRY_ENVIRONMENT, "send_default_pii": sentry_sdk.get_client().options["send_default_pii"]}

    await report.check("sentry:product-setup", initialized)

    async def ingest():
        dsn = urlsplit(os.environ["SENTRY_DSN"])
        project = dsn.path.strip("/")
        event_id = uuid.uuid4().hex
        event = {"event_id": event_id, "message": "RAG platform validation event", "level": "info", "platform": "python", "timestamp": time.time(),
                 "environment": tracking.settings.SENTRY_ENVIRONMENT, "tags": {"origin": "rag-validation"}}
        body = "\n".join([json.dumps({"event_id": event_id}), json.dumps({"type": "event"}), json.dumps(event)])
        url = f"{dsn.scheme}://{dsn.hostname}{':' + str(dsn.port) if dsn.port else ''}/api/{project}/envelope/"
        async with httpx.AsyncClient(timeout=20) as http:
            response = await http.post(url, content=body, headers={"X-Sentry-Auth": f"Sentry sentry_version=7, sentry_key={dsn.username}, sentry_client=rag-validation/1"})
        assert response.status_code == 200 and response.json().get("id") == event_id, f"ingest answered {response.status_code}: {response.text[:200]}"
        return {"event_id": event_id}

    await report.check("sentry:ingest-accepts-the-dsn", ingest)
    return report.finish()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
