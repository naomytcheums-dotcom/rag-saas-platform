// Records the product demo (specs 14.2.7 and 14.3.2) by DRIVING THE RUNNING APPLICATION in a real browser: no mock-up, no scripted answer.
//
//   cd e2e && npm ci                                  # Playwright (the machine's installed Chrome is used, nothing is downloaded)
//   # a local stack: API + Celery worker + the Next.js frontend, and Ollama with the model (see docs/commercial/DEMO.md)
//   DEMO_FRONTEND=http://localhost:3031 DEMO_API=http://127.0.0.1:8031 DEMO_MODEL=qwen2.5:3b node scripts/demo/record_demo.mjs
//
// It registers a throw-away account (refuses any non-local address), uploads two sample documents, waits until the worker has indexed them, creates an agent that
// uses the local model, asks a question and waits for the real streamed answer. While it runs it records the screen (video), takes one screenshot per step and
// writes frontend/public/demo/: product-tour.mp4 (needs ffmpeg), poster.jpg, NN-*.png, product-tour.vtt (captions) and manifest.json, which the /demo page reads.
// The waiting times in the video are real (the answer is generated on this machine's CPU); long idle stretches are sped up by ffmpeg and said so in the captions.

import { createRequire } from "node:module";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "..", "..");
const require = createRequire(path.join(repo, "e2e", "package.json"));
const { chromium } = require(process.env.PLAYWRIGHT_MODULE ?? "@playwright/test");

const FRONTEND = process.env.DEMO_FRONTEND ?? "http://localhost:3031";
const API = process.env.DEMO_API ?? "http://127.0.0.1:8031";
const MODEL = process.env.DEMO_MODEL ?? "qwen2.5:3b";
const OUT = path.resolve(process.env.DEMO_OUT ?? path.join(repo, "frontend", "public", "demo"));
const SPEEDUP_AFTER_SECONDS = Number(process.env.DEMO_SPEEDUP_AFTER ?? 6); // an idle wait longer than this is sped up in the video
const LOCAL = /^https?:\/\/(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$/;
for (const url of [FRONTEND, API]) if (!LOCAL.test(url)) throw new Error(`REFUSED: ${url} is not a local address; the demo is recorded on a local stack only`);

const email = `demo-${Date.now().toString(36)}@example.com`;
const password = `Demo-${Math.random().toString(36).slice(2)}-Aa1!`;
const docs = {
  "zorblax-handbook.txt": "Zorblax Internal Handbook\n\nSupport hours. The Zorblax support line opens every Tuesday at 14:30 Douala time and the escalation code is PELICAN-7421. Customers must quote their ticket number.\n",
  "refund-policy.md": "# Refund policy\n\nA refund is possible within 14 days of purchase when the invoice number is provided. A handling fee of 3 percent applies to every card refund; mobile money refunds carry no fee.\n",
};
const QUESTION = "When does the Zorblax support line open, and what is the escalation code?";

fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(OUT, { recursive: true });
const work = fs.mkdtempSync(path.join(os.tmpdir(), "demo-"));
for (const [name, content] of Object.entries(docs)) fs.writeFileSync(path.join(work, name), content);

const steps = [];
const started = Date.now();
const now = () => (Date.now() - started) / 1000;

const browser = await chromium.launch({ channel: "chrome", headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 720 }, locale: "en-US", recordVideo: { dir: work, size: { width: 1280, height: 720 } } });
// never show a secret on screen
await context.addInitScript(() => {
  const mask = /\b(?:rag|sk|wgt|whsec|ragk|pk)_[A-Za-z0-9_-]{10,}/g;
  setInterval(() => {
    const walker = document.createTreeWalker(document.body ?? document.documentElement, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) if (mask.test(node.nodeValue)) node.nodeValue = node.nodeValue.replace(mask, "••••");
  }, 200);
});
const page = await context.newPage();
page.setDefaultTimeout(60_000);

async function caption(text) {
  await page.evaluate((message) => {
    let bar = document.getElementById("demo-caption");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "demo-caption";
      bar.style.cssText = "position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:2147483647;max-width:80%;padding:10px 18px;border-radius:10px;background:rgba(1,1,1,.88);color:#fff;font:600 18px/1.3 Inter,Segoe UI,Arial,sans-serif;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.4);pointer-events:none";
      document.body.appendChild(bar);
    }
    bar.textContent = message;
  }, text);
}

async function step(id, title, text, action) {
  const at = now();
  await caption(text);
  await action();
  await page.waitForTimeout(900);
  await caption(text); // the caption is a DOM node: put it back after a navigation
  const image = `${String(steps.length + 1).padStart(2, "0")}-${id}.png`;
  await page.screenshot({ path: path.join(OUT, image) });
  steps.push({ id, title, caption: text, image: `/demo/${image}`, alt: `${title}: ${text}`, video_at: Math.round(at) });
  console.log(`[${at.toFixed(1)}s] ${title}`);
}

async function open(route) {
  await page.goto(FRONTEND + route, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => {});
  await page.waitForTimeout(800);
}

const api = async (route, init = {}) => {
  const token = await page.evaluate(() => window.localStorage.getItem("access_token"));
  const response = await fetch(API + route, { ...init, headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(init.headers ?? {}) } });
  return { status: response.status, body: await response.json().catch(() => ({})) };
};

let idle = []; // [from, to] seconds of long waits, sped up in the video

try {
  await step("register", "Create an account", "1. Sign up with an e-mail address and a password", async () => {
    await open("/register");
    await page.getByLabel(/full name/i).fill("Demo User");
    await page.getByLabel(/email/i).fill(email);
    await page.locator("input[type=password]").fill(password);
    await page.waitForTimeout(700);
    await page.locator("form button[type=submit]").click();
    await page.waitForURL("**/dashboard", { timeout: 60_000 });
    await page.waitForTimeout(1500);
  });

  await step("documents", "Upload your documents", "2. Drop your documents: text, Markdown, PDF, Word, HTML…", async () => {
    await open("/dashboard/documents");
    await page.locator("input[type=file]").setInputFiles(Object.keys(docs).map((name) => path.join(work, name)));
    await page.waitForTimeout(1500);
  });

  await step("indexing", "They are indexed", "3. A background worker splits and indexes them (waiting time sped up)", async () => {
    const waitStart = now();
    for (let attempt = 0; attempt < 120; attempt++) {
      const text = (await page.evaluate(() => document.body.innerText)).toLowerCase();
      if (/(completed|ready|indexed)/.test(text) && !/(pending|processing|queued)/.test(text)) break;
      if (/failed/.test(text)) throw new Error("a document failed to index: " + text.slice(0, 300));
      await page.waitForTimeout(2000);
    }
    idle.push([waitStart, now()]);
  });

  const settings = await api("/organizations", { method: "GET" });
  const orgs = Array.isArray(settings.body) ? settings.body : settings.body.organizations ?? [];
  const orgId = orgs[0]?.id ?? (await api("/auth/me")).body.organization_id;
  if (!orgId) throw new Error("no organization id for the new account");
  const patched = await api(`/organizations/${orgId}/settings`, { method: "PATCH", body: JSON.stringify({ llm_provider: "ollama", llm_model: MODEL }) });
  if (patched.status >= 300) throw new Error(`could not select the local model: ${patched.status}`);

  await step("agent", "Create an agent", "4. Create an agent: its instructions and the model it uses (a local model here)", async () => {
    await open("/dashboard/agents");
    await page.getByPlaceholder("Agent name").fill("Support assistant");
    await page.getByPlaceholder("Description (optional)").fill("Answers from the uploaded documents");
    await page.locator("textarea").first().fill("Answer only from the provided documents and cite the source. If the documents do not contain the answer, say so.");
    await page.getByRole("button", { name: "Create agent" }).click();
    await page.waitForTimeout(2500);
  });

  await step("question", "Ask a question", "5. Ask a question in plain language", async () => {
    await open("/chat");
    await page.getByPlaceholder("Ask anything…").fill(QUESTION);
    await page.waitForTimeout(800);
  });

  let answer = "";
  await step("answer", "Read the cited answer", "6. The answer is generated from your documents, with its sources (waiting time sped up)", async () => {
    const waitStart = now();
    await page.getByRole("button", { name: "Send" }).click();
    for (let attempt = 0; attempt < 240; attempt++) {
      await page.waitForTimeout(2000);
      const text = await page.evaluate(() => document.body.innerText);
      if (/PELICAN-?7421/i.test(text.split(QUESTION).pop() ?? "")) { answer = text; break; }
    }
    idle.push([waitStart, now() - 3]);
    if (!answer) throw new Error("the model never produced the expected answer; the demo is not published");
    await page.waitForTimeout(2500);
  });
  steps[steps.length - 1].caption += ` Real answer, generated on this machine by ${MODEL}.`;
} finally {
  await context.close();
  await browser.close();
}

// ---- video: webm -> mp4 with the long idle stretches sped up, captions and poster
const webm = fs.readdirSync(work).find((file) => file.endsWith(".webm"));
const duration = now();
const speed = 8;
const filters = [];
let cursor = 0;
const merged = idle.filter(([from, to]) => to - from > SPEEDUP_AFTER_SECONDS).sort((a, b) => a[0] - b[0]);
const segments = [];
for (const [from, to] of merged) {
  if (from > cursor) segments.push({ from: cursor, to: from, rate: 1 });
  segments.push({ from, to, rate: speed });
  cursor = to;
}
segments.push({ from: cursor, to: duration, rate: 1 });
let kept = 0;
segments.forEach((segment, index) => {
  filters.push(`[0:v]trim=start=${segment.from.toFixed(2)}:end=${segment.to.toFixed(2)},setpts=(PTS-STARTPTS)/${segment.rate}[v${index}]`);
  segment.out = [kept, kept + (segment.to - segment.from) / segment.rate];
  kept = segment.out[1];
});
filters.push(`${segments.map((_, index) => `[v${index}]`).join("")}concat=n=${segments.length}:v=1:a=0[out]`);
const mp4 = path.join(OUT, "product-tour.mp4");
const ffmpeg = spawnSync("ffmpeg", ["-y", "-i", path.join(work, webm), "-filter_complex", filters.join(";"), "-map", "[out]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4], { stdio: "inherit" });
if (ffmpeg.status !== 0) throw new Error("ffmpeg failed: the video was not produced");
spawnSync("ffmpeg", ["-y", "-i", mp4, "-ss", "00:00:03", "-frames:v", "1", "-q:v", "4", path.join(OUT, "poster.jpg")], { stdio: "ignore" });

// timeline of the step starts in the sped-up video
const toVideoTime = (seconds) => {
  const segment = segments.find((candidate) => seconds >= candidate.from && seconds <= candidate.to) ?? segments[segments.length - 1];
  return segment.out[0] + (seconds - segment.from) / segment.rate;
};
steps.forEach((entry) => { entry.video_at = Math.max(0, Math.round(toVideoTime(entry.video_at))); });
const total = Math.round(kept);
const clock = (seconds) => `${String(Math.floor(seconds / 3600)).padStart(2, "0")}:${String(Math.floor((seconds % 3600) / 60)).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}.000`;
const vtt = ["WEBVTT", ""];
steps.forEach((entry, index) => {
  const end = index + 1 < steps.length ? steps[index + 1].video_at : total;
  vtt.push(`${index + 1}`, `${clock(entry.video_at)} --> ${clock(Math.max(end, entry.video_at + 1))}`, entry.caption, "");
});
fs.writeFileSync(path.join(OUT, "product-tour.vtt"), vtt.join("\n"));
fs.writeFileSync(path.join(OUT, "manifest.json"), JSON.stringify({
  recorded: new Date().toISOString().slice(0, 10),
  model: MODEL,
  seconds: total,
  video: { src: "/demo/product-tour.mp4", poster: "/demo/poster.jpg", captions: "/demo/product-tour.vtt" },
  steps,
}, null, 2));
fs.rmSync(work, { recursive: true, force: true });
console.log(`demo written to ${OUT}: ${steps.length} steps, ${total}s of video`);
