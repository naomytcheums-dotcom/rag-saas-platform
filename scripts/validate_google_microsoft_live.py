#!/usr/bin/env python
"""Real validation of 5.2.7 / 5.4.11 (calendar: Google, Outlook) and 5.2.8 (e-mail: Gmail, Outlook) with the product's own tools.

    RUN_LIVE_VENDOR_VALIDATION=1 \
      GOOGLE_CALENDAR_CLIENT_ID=... GOOGLE_CALENDAR_CLIENT_SECRET=... GOOGLE_CALENDAR_REFRESH_TOKEN=... \
      GMAIL_CLIENT_ID=... GMAIL_CLIENT_SECRET=... GMAIL_REFRESH_TOKEN=... \
      OUTLOOK_CALENDAR_CLIENT_ID=... OUTLOOK_CALENDAR_CLIENT_SECRET=... OUTLOOK_CALENDAR_REFRESH_TOKEN=... \
      OUTLOOK_EMAIL_CLIENT_ID=... OUTLOOK_EMAIL_CLIENT_SECRET=... OUTLOOK_EMAIL_REFRESH_TOKEN=... \
      python scripts/validate_google_microsoft_live.py

READ-ONLY by default: refresh the OAuth token, list the next 24 h of events, list one e-mail (only counts are printed, never content).
Writes need their own explicit switch, so nothing is created or sent by accident:
    LIVE_ALLOW_CALENDAR_WRITE=1   create one event 10 minutes from now titled "RAG validation (safe to delete)", read it back, delete it
    LIVE_SEND_TEST_EMAIL_TO=you@your-own-address   send ONE e-mail to that address (your own mailbox) through each configured mail provider
"""
import asyncio
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import _live_vendor as live  # noqa: E402

CALENDARS = {"google": ("GOOGLE_CALENDAR_CLIENT_ID", "GOOGLE_CALENDAR_CLIENT_SECRET", "GOOGLE_CALENDAR_REFRESH_TOKEN"),
             "outlook": ("OUTLOOK_CALENDAR_CLIENT_ID", "OUTLOOK_CALENDAR_CLIENT_SECRET", "OUTLOOK_CALENDAR_REFRESH_TOKEN")}
MAILS = {"gmail": ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"),
         "outlook": ("OUTLOOK_EMAIL_CLIENT_ID", "OUTLOOK_EMAIL_CLIENT_SECRET", "OUTLOOK_EMAIL_REFRESH_TOKEN")}


async def main() -> int:
    live.require_opt_in("Google Calendar / Gmail and Microsoft Graph (your own accounts)", "free; read-only unless a write switch is set")
    calendar = live.product("api.tools.calendar_tools")
    mail = live.product("api.tools.email_tools")
    report = live.Report("calendar_and_email")
    now = dt.datetime.now(dt.timezone.utc)
    window = (now.strftime("%Y-%m-%dT%H:%M:%SZ"), (now + dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))

    for provider, variables in CALENDARS.items():
        if not live.have(*variables):
            report.skipped(f"calendar:{provider}", "OAuth variables missing from the process environment")
            continue

        async def read(provider=provider):
            events = await calendar.calendar_list_events(provider, *window, max_results=10)
            slots = await calendar.calendar_find_available_slots(provider, *window, 30)
            return {"events_next_24h": len(events), "free_slots_30min": len(slots)}

        await report.check(f"calendar:{provider}", read)
        if os.environ.get("LIVE_ALLOW_CALENDAR_WRITE") == "1":
            async def write(provider=provider):
                start = now + dt.timedelta(minutes=10)
                created = await calendar.calendar_create_event(provider, "RAG validation (safe to delete)", start.strftime("%Y-%m-%dT%H:%M:%SZ"), (start + dt.timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ"))
                try:
                    fetched = await calendar.calendar_get_event(provider, created["id"])
                    assert fetched.get("id") == created["id"]
                finally:
                    await calendar.calendar_delete_event(provider, created["id"])
                return {"created_read_deleted": True}

            await report.check(f"calendar-write:{provider}", write)

    for provider, variables in MAILS.items():
        if not live.have(*variables):
            report.skipped(f"mail:{provider}", "OAuth variables missing from the process environment")
            continue

        async def read_mail(provider=provider):
            messages = await mail.email_read(provider, limit=1)
            return {"messages_read": len(messages), "has_subject_field": all("subject" in m for m in messages)}

        await report.check(f"mail:{provider}", read_mail)
        target = os.environ.get("LIVE_SEND_TEST_EMAIL_TO")
        if target:
            async def send(provider=provider):
                result = await mail.email_send(provider, [target], "RAG platform validation", "One test message sent by scripts/validate_google_microsoft_live.py.")
                assert result["status"] == "sent"
                return {"sent_to": "LIVE_SEND_TEST_EMAIL_TO"}

            await report.check(f"mail-send:{provider}", send)
    return report.finish()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
