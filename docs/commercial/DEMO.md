# Product demo (specs 14.2.7 demo video, 14.3.2 video or interactive demo)

Two things ship, both produced from the **running product**, not drawn:

1. **`/demo`** (`frontend/app/demo/page.tsx`, linked from the landing page's "See the demo" button): the screencast with captions, and an interactive step-by-step walk through
   the same recording (step list, previous / next, arrow keys, "jump to this moment in the video"). It reads `frontend/public/demo/manifest.json`; without that file the page
   says the recording is unavailable instead of showing an empty frame.
2. **`frontend/public/demo/`**: `product-tour.mp4`, `poster.jpg`, `product-tour.vtt` (captions), one screenshot per step and `manifest.json`, written by
   `scripts/demo/record_demo.mjs`.

## What the recording shows

A real session on a local stack: sign up, upload two sample documents (invented facts, so a model cannot answer from its own knowledge), wait for the Celery worker to index them,
create an agent that uses a local model (Ollama), ask a question, read the streamed answer with its source. The script fails (and publishes nothing) if the expected fact is not in the
answer. Waits longer than six seconds are sped up eight times by ffmpeg and the captions say so; the answer is generated on the machine's CPU, so the real waiting time is long.

## Regenerate it

```
cd e2e && npm ci                                              # Playwright; the installed Chrome is used
# 1. API + worker on a disposable database, e.g. . scripts/test_env/e2e_stack_env.sh && scripts/test_env/e2e_stack_start.sh
# 2. the frontend:  cd frontend && NEXT_PUBLIC_API_URL=http://127.0.0.1:8031 npx next dev -p 3031 --webpack
# 3. Ollama running with the model (default qwen2.5:3b)
DEMO_FRONTEND=http://localhost:3031 DEMO_API=http://127.0.0.1:8031 DEMO_MODEL=qwen2.5:3b node scripts/demo/record_demo.mjs
```

The script refuses any address that is not local, creates a throw-away account, masks anything that looks like a key on screen and never uses a paid service.
Re-record after a visible UI change; the date on the page is the recording date.

## Limits, stated plainly

- English interface only (the recording shows the English UI); the page chrome around it is translated (en, fr).
- The documents and the question are sample data; the answer quality shown depends on the local model and says nothing general about the product's accuracy.
- The recording is not signed off by a presenter and has no voice-over: it is captioned, not narrated.
