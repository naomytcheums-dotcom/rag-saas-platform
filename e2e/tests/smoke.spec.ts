import { expect, test, type Page } from "@playwright/test";

// A throw-away account on the isolated local database. The password is not a real credential and the database is deleted with the run.
const EMAIL = `e2e-${Date.now()}@example.com`;
const PASSWORD = "E2e-Smoke-Test-2026-xyz!";

async function dismissCookieBanner(page: Page) {
  await page.addInitScript(() => window.localStorage.setItem("cookie_consent_ack", "1"));
}

test.describe("authentication", () => {
  test("the login page renders its form", async ({ page }) => {
    await dismissCookieBanner(page);
    await page.goto("/login");
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
    await expect(page.getByRole("button", { name: /log in|sign in/i })).toBeVisible();
  });

  test("a wrong password shows an error and stays on the login page", async ({ page }) => {
    await dismissCookieBanner(page);
    await page.goto("/login");
    await page.getByLabel("Email").fill("nobody@example.com");
    await page.getByLabel("Password").fill("not-the-password");
    await page.getByRole("button", { name: /log in|sign in/i }).click();
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("register, then reach the dashboard", async ({ page, request }) => {
    await dismissCookieBanner(page);
    // Register through the API (the registration form has its own unit tests), then log in through the real login form.
    const registered = await request.post("http://127.0.0.1:8765/auth/register", { data: { email: EMAIL, password: PASSWORD, accept_terms: true } });
    expect(registered.ok()).toBeTruthy();
    await page.goto("/login");
    await page.getByLabel("Email").fill(EMAIL);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: /log in|sign in/i }).click();
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByRole("heading", { name: /hello/i })).toBeVisible();
  });
});

test.describe("signed-in navigation", () => {
  test.beforeEach(async ({ page, request }) => {
    await dismissCookieBanner(page);
    const login = await request.post("http://127.0.0.1:8765/auth/login", { data: { email: EMAIL, password: PASSWORD } });
    expect(login.ok()).toBeTruthy();
    const { access_token } = await login.json();
    await request.post("http://127.0.0.1:8765/organizations", { data: { name: "E2E Org" }, headers: { Authorization: `Bearer ${access_token}` } });
    await page.addInitScript((token) => window.localStorage.setItem("access_token", token), access_token);
  });

  for (const [route, heading] of [
    ["/dashboard/documents", /documents/i],
    ["/dashboard/escalations", /escalations/i],
    ["/dashboard/insights", /usage insights/i],
    ["/dashboard/teams", /teams and workspaces/i],
  ] as const) {
    test(`${route} loads without a client error`, async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await page.goto(route);
      await expect(page.getByRole("heading", { name: heading }).first()).toBeVisible();
      expect(errors).toEqual([]);
    });
  }

  test("the documents page offers multi-file upload and a drop zone", async ({ page }) => {
    await page.goto("/dashboard/documents");
    await expect(page.getByTestId("drop-zone")).toBeVisible();
    await expect(page.locator('input[type="file"][multiple]')).toHaveCount(1);
  });

  test("the chat page explains that an agent is needed when there is none", async ({ page }) => {
    await page.goto("/chat");
    await expect(page.getByText(/no agent exists yet/i)).toBeVisible();
  });

  test("the escalations page can be filtered by status", async ({ page }) => {
    await page.goto("/dashboard/escalations");
    await page.getByLabel("Status").selectOption("resolved");
    await expect(page.getByText(/no tickets/i)).toBeVisible();
  });
});
