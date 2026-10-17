// Drives a REAL Chromium against the voice harness (e2e/voice/harness: the real VADIndicator and VoiceOutput components) for
// tests/contracts/test_browser_voice.py. The microphone is Chromium's fake capture device fed with a WAV file, so the VAD hears real audio.
//   node browser_voice_driver.mjs '<json options>'   -> prints one JSON line with what happened in the page.
import { createRequire } from "node:module";

const options = JSON.parse(process.argv[2]);
const require = createRequire(options.playwrightFrom);
const { chromium } = require("playwright");

// Chromium with a fake capture device occasionally stalls at launch: never let it hold the test suite.
setTimeout(() => { console.log(JSON.stringify({ ok: false, error: "watchdog" })); process.exit(3); }, options.watchdogMs ?? 150000).unref();

const browser = await chromium.launch({
  headless: true,
  args: [
    "--use-fake-device-for-media-stream",
    "--use-fake-ui-for-media-stream",
    `--use-file-for-fake-audio-capture=${options.micWav}`,
    "--autoplay-policy=no-user-gesture-required",
  ],
});
const result = { scenario: options.scenario };
try {
  const context = await browser.newContext({ permissions: ["microphone"] });
  const page = await context.newPage();
  if (options.token) await page.addInitScript((token) => window.localStorage.setItem("access_token", token), options.token);
  const consoleErrors = [];
  page.on("console", (message) => message.type() === "error" && consoleErrors.push(message.text().slice(0, 300)));
  const ttsResponses = [];
  page.on("response", async (response) => {
    if (response.url().includes("/voice/tts")) ttsResponses.push({ status: response.status(), type: response.headers()["content-type"], t: Date.now() });
  });
  const ttsRequests = [];
  page.on("request", (request) => request.url().includes("/voice/tts") && ttsRequests.push(Date.now()));

  await page.goto(options.url, { waitUntil: "load" });

  if (options.scenario === "vad") {
    await page.getByRole("button", { name: "Enable auto-detect" }).click();
    await page.waitForTimeout(options.listenMs);
    result.state = await page.locator("#vad").innerText();
  } else if (options.scenario === "tts") {
    const startedAt = Date.now();
    await page.getByRole("button", { name: "Play" }).click();
    if (options.stopAfterMs) {
      await page.waitForTimeout(options.stopAfterMs);
      result.stopVisible = await page.getByRole("button", { name: "Stop" }).count();
      if (result.stopVisible) await page.getByRole("button", { name: "Stop" }).click();
      await page.waitForTimeout(500);
    } else {
      await page.waitForFunction(() => window.__voice.events.some((e) => e.event === "audio-ended") && !document.querySelector('button[aria-label="Stop"]'), null, { timeout: options.timeoutMs });
    }
    result.elapsedMs = Date.now() - startedAt;
    result.output = await page.locator("#output").innerText();
  }
  result.events = await page.evaluate(() => window.__voice.events);
  result.ttsResponses = ttsResponses;
  result.ttsRequests = ttsRequests;
  result.consoleErrors = consoleErrors;
  result.ok = true;
} catch (error) {
  result.ok = false;
  result.error = String(error).slice(0, 800);
} finally {
  await browser.close();
}
console.log(JSON.stringify(result));
