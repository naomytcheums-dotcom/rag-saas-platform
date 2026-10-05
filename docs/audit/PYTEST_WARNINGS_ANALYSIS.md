# Investigation des warnings pytest

Date: 2026-10-03. The first attempt with the system Python failed during
`tests/conftest.py` import because that interpreter does not have the declared
`pgvector` dependency. No package was installed; the repository `.venv` was
used for the valid reproduction and replay.

## Findings

### A2A unraisable coroutine warnings — reproduced, root cause identified, fixed

Reproduction before the fix:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_a2a_router.py -q -W default
11 passed, 2 warnings in 9.63s
PytestUnraisableExceptionWarning:
Exception ignored in: <coroutine object ActiveTask._run_consumer ...>
RuntimeError: coroutine ignored GeneratorExit
PytestUnraisableExceptionWarning:
Exception ignored in: <coroutine object ActiveTask._run_producer ...>
RuntimeError: coroutine ignored GeneratorExit
```

The test label reported by pytest was the final rate/spend-cap test, but the
request itself exits before constructing an A2A handler. This is where garbage
collection surfaced pending tasks left by preceding successful A2A requests,
not evidence that the spend-cap branch creates those tasks.

Root cause established from the installed, pinned `a2a-sdk==1.2.0` source:

- `a2a.server.request_handlers.__init__` aliases `DefaultRequestHandler` to
  `DefaultRequestHandlerV2`.
- V2 creates an `ActiveTaskRegistry`; it exposes `async def aclose()` to drain
  active tasks.
- The JSON-RPC endpoint created one handler per HTTP request and returned the
  dispatcher response without closing that handler.
- The SDK `ActiveTask` starts separate producer and consumer asyncio tasks.
  Their pending coroutines generated the warnings at loop teardown.

Correction in `api/routers/a2a.py`: handlers now close on exceptions before
the response is built, and normal/streaming responses receive a Starlette
background task which preserves any existing background callback and closes
the handler after response transmission. This timing avoids closing an A2A
stream before its response body has been consumed.

Replay after the fix:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_a2a_router.py -q -W default
11 passed in 9.33s
.\.venv\Scripts\python.exe -m pytest tests/test_a2a_router.py tests/test_a2a_integration.py tests/test_a2a_idor.py -q -W default
15 passed in 10.84s
```

Both successful runs reported no warning summary. This verifies the covered
local A2A paths in SQLite with providers mocked; it is not a production load,
stream disconnect, or external-provider test.

### `PytestAssertRewriteWarning: anyio` — harness/order issue, still present in
historical evidence

The earlier IDOR proof files report:

```text
PytestAssertRewriteWarning: Module already imported so cannot be rewritten; anyio
```

The IDOR test bootstrap imports `api.routers.auth` before invoking pytest;
the app/conftest import graph loads `anyio` before pytest's assertion-rewrite
discovery. Therefore pytest cannot rewrite that already-imported module.
The warning is a test bootstrap/plugin-order issue, not an application
assertion failure. The present direct A2A pytest invocation did not emit it.
No warning filter was added, and this audit did not change the bootstrap or
pytest plugin ordering. The old evidence keeps its original warning output.

### Other warnings

No `PytestUnraisableExceptionWarning` reproduced in the combined A2A suite
after the handler cleanup. No claim is made that every warning in the full
test suite has been enumerated: the full suite was not run in this task.

## Status

**A2A warning cause:** confirmed and locally corrected.
**A2A targeted replay:** 15 passed, no warnings reported.
**anyio rewrite warning:** explained, not suppressed or changed.
**Full test suite warning inventory:** incomplete.
