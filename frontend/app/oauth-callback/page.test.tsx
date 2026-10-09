// MAP-002: the OAuth / SSO return page. It must read the session (or the MFA hand-off) from the URL fragment, remove the fragment from the
// address bar, and finish the sign-in. The API client is mocked.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { parseOAuthFragment } from "@/lib/oauth-callback";

const post = vi.fn();

vi.mock("@/components/auth/AuthShell", () => ({
  default: ({ title, subtitle, error, children, footer }: { title: string; subtitle?: string; error?: string | null; children: React.ReactNode; footer?: React.ReactNode }) => (
    <div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}{error && <p role="alert">{error}</p>}{children}{footer}</div>
  ),
  AuthField: ({ label, ...props }: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) => <label>{label}<input {...props} /></label>,
  AuthButton: ({ children, disabled }: { children: React.ReactNode; disabled?: boolean }) => <button type="submit" disabled={disabled}>{children}</button>,
  AuthLink: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}));
vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status: number;
    detail: unknown;
    constructor(status: number, detail: unknown) {
      super(String(detail));
      this.status = status;
      this.detail = detail;
    }
  }
  return { api: { post: (...a: unknown[]) => post(...a) }, ApiError };
});

import { ApiError } from "@/lib/api";
import OAuthCallbackPage from "./page";

describe("parseOAuthFragment", () => {
  it("reads a finished sign-in", () => {
    expect(parseOAuthFragment("#access_token=abc&expires_in=900")).toEqual({ kind: "session", accessToken: "abc" });
  });
  it("reads the MFA hand-off", () => {
    expect(parseOAuthFragment("#mfa_required=true&mfa_token=m1&methods=totp,webauthn")).toEqual({ kind: "mfa", mfaToken: "m1", methods: ["totp", "webauthn"] });
  });
  it.each(["", "#", "#mfa_required=true", "#something=else", "#mfa_required=false&mfa_token=x"])("treats %j as nothing usable", (hash) => {
    expect(parseOAuthFragment(hash)).toEqual({ kind: "none" });
  });
});

const originalLocation = window.location;
const replace = vi.fn();

function setLocation(hash: string) {
  Object.defineProperty(window, "location", { configurable: true, value: { hash, pathname: "/oauth-callback", replace } });
}

beforeEach(() => {
  post.mockReset();
  replace.mockReset();
  window.localStorage.clear();
  vi.spyOn(window.history, "replaceState").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
  Object.defineProperty(window, "location", { configurable: true, value: originalLocation });
});

describe("OAuth callback page", () => {
  it("stores the session, clears the fragment and goes to the dashboard", async () => {
    setLocation("#access_token=jwt-1&expires_in=900");
    render(<OAuthCallbackPage />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
    expect(window.localStorage.getItem("access_token")).toBe("jwt-1");
    expect(window.history.replaceState).toHaveBeenCalledWith(null, "", "/oauth-callback");
  });

  it("asks for the authenticator code and completes the sign-in with it", async () => {
    setLocation("#mfa_required=true&mfa_token=m-token&methods=totp");
    post.mockResolvedValue({ access_token: "jwt-2" });
    render(<OAuthCallbackPage />);

    await userEvent.type(await screen.findByLabelText("Authentication code"), "123456");
    await userEvent.click(screen.getByRole("button", { name: "Verify" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
    expect(post).toHaveBeenCalledWith("/auth/2fa/verify-login", { mfa_token: "m-token", code: "123456" });
    expect(window.localStorage.getItem("access_token")).toBe("jwt-2");
  });

  it("can use a recovery code instead", async () => {
    setLocation("#mfa_required=true&mfa_token=m-token&methods=totp");
    post.mockResolvedValue({ access_token: "jwt-3" });
    render(<OAuthCallbackPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Use a recovery code instead" }));
    await userEvent.type(screen.getByLabelText("Recovery code"), "ABCD-EFGH");
    await userEvent.click(screen.getByRole("button", { name: "Verify" }));

    await waitFor(() => expect(post).toHaveBeenCalledWith("/auth/2fa/verify-recovery-code", { mfa_token: "m-token", recovery_code: "ABCD-EFGH" }));
  });

  it("shows a wrong code and stays on the page", async () => {
    setLocation("#mfa_required=true&mfa_token=m-token&methods=totp");
    post.mockRejectedValue(new ApiError(401, "Invalid code"));
    render(<OAuthCallbackPage />);

    await userEvent.type(await screen.findByLabelText("Authentication code"), "000000");
    await userEvent.click(screen.getByRole("button", { name: "Verify" }));

    expect(await screen.findByText("Invalid code")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
    expect(window.localStorage.getItem("access_token")).toBeNull();
  });

  it("explains an empty or reused link and offers the login page", async () => {
    setLocation("");
    render(<OAuthCallbackPage />);
    expect(await screen.findByText(/incomplete or has already been used/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to sign in" })).toHaveAttribute("href", "/login");
    expect(replace).not.toHaveBeenCalled();
  });
});
