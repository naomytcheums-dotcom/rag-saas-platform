"""
Shared logic behind every loop-aware Redis client in api/security/
(rate_limit.py, geoip.py, webauthn.py) and api/security/documents.py's
progress-pubsub client -- extracted after 4 modules independently
hand-copied the same fix (see rate_limit.py's docstring for the full
"Event loop is closed" incident this exists to prevent).

Each module still keeps its OWN `_redis`/`_redis_loop` module globals
(deliberately -- geoip.py and webauthn.py's own docstrings explain why
sharing rate_limit.py's private client would create an import cycle,
and the test suite monkeypatches these globals directly), but the
rebuild-on-loop-mismatch LOGIC -- the part that was actually getting
copy-pasted -- now lives in one place.
"""

import asyncio

import redis.asyncio as redis_asyncio


async def _close_quietly(client: redis_asyncio.Redis) -> None:
    try:
        await client.aclose()
    except Exception:  # noqa: BLE001 -- a client bound to a now-dead loop may fail to close cleanly; that's fine
        pass


def get_or_rebuild(
    client: redis_asyncio.Redis | None,
    client_loop: asyncio.AbstractEventLoop | None,
    url: str,
    **client_kwargs,
) -> tuple[redis_asyncio.Redis, asyncio.AbstractEventLoop]:
    """Returns (client, loop) for the CURRENTLY running loop: `client`
    unchanged if it already belongs to this loop, otherwise a freshly
    built one. A client's connection pool binds its socket to whichever
    loop is running the first time it's actually used, not to the loop
    that was running when from_url() was called -- reusing a client
    across a loop change reproduces "Event loop is closed" the moment
    the old loop is torn down.

    The outgoing client is closed (not just dropped) on rebind, so a
    loop transition doesn't leak its connection pool. The close is
    fire-and-forget on the NEW loop, since the old client's own loop is
    typically already gone by the time a mismatch is detected -- that's
    the whole reason a mismatch exists."""
    loop = asyncio.get_running_loop()
    if client is None or client_loop is not loop:
        if client is not None:
            loop.create_task(_close_quietly(client))
        client = redis_asyncio.from_url(url, **client_kwargs)
        client_loop = loop
    return client, client_loop
