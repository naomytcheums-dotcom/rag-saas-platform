// MAP-003: the three pages the e-mailed account links open (restore, consent reactivation, 2FA lockout recovery). The API client is
// mocked: the assertions are about what is sent, when, and what the user sees.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const post = vi.fn();
let token: string | null = "tok-123";

vi.mock("next/navigation", () => ({
  useSearchParams: () => ({ get: (key: string) => (key === "token" ? token : null) }),
}));
vi.mock("@/components/auth/AuthShell", () => ({
  default: ({ title, subtitle, error, children, footer }: { title: string; subtitle?: string; error?: string | null; children: React.ReactNode; footer?: React.ReactNode }) => (
    <div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}{error && <p role="alert">{error}</p>}{children}{footer}</div>
  ),
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
import TwoFactorLockoutRecoveryPage from "@/app/2fa-lockout-recovery/page";
import ReactivateConsentPage from "@/app/reactivate-consent/page";
import RestoreAccountPage from "@/app/restore-account/page";

beforeEach(() => {
  post.mockReset();
  token = "tok-123";
});

describe("Restore account page", () => {
  it("sends nothing on load, then confirms the token when the user presses the button", async () => {
    post.mockResolvedValue({ message: "Account restored -- you can log in again" });
    render(<RestoreAccountPage />);
    expect(post).not.toHaveBeenCalled();

    await userEvent.click(await screen.findByRole("button", { name: "Restore my account" }));

    expect(await screen.findByText("Account restored -- you can log in again")).toBeInTheDocument();
    expect(post).toHaveBeenCalledWith("/account/restore/confirm", { token: "tok-123" });
  });

  it("shows the API's reason when the link is invalid or expired", async () => {
    post.mockRejectedValue(new ApiError(400, "Invalid or expired restore link"));
    render(<RestoreAccountPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Restore my account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid or expired restore link");
  });

  it("explains a link without a token and sends nothing", async () => {
    token = null;
    render(<RestoreAccountPage />);
    expect(await screen.findByText(/missing its token/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });
});

describe("Reactivate consent page", () => {
  it("cannot be confirmed before the terms are accepted again, then sends accept_terms", async () => {
    post.mockResolvedValue({ message: "Account reactivated" });
    render(<ReactivateConsentPage />);

    const button = await screen.findByRole("button", { name: "Reactivate my account" });
    expect(button).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(button);

    await waitFor(() => expect(post).toHaveBeenCalledWith("/account/consent/reactivate/confirm", { token: "tok-123", accept_terms: true }));
    expect(await screen.findByText("Account reactivated")).toBeInTheDocument();
  });
});

describe("2FA lockout recovery page", () => {
  it("confirms the token and shows the not-yet-eligible answer of the API", async () => {
    post.mockRejectedValue(new ApiError(400, "Invalid, expired, or not-yet-eligible recovery link"));
    render(<TwoFactorLockoutRecoveryPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Turn off two-factor" }));

    expect(post).toHaveBeenCalledWith("/auth/2fa/lockout-recovery/confirm", { token: "tok-123" });
    expect(await screen.findByRole("alert")).toHaveTextContent("not-yet-eligible");
  });

  it("shows the confirmation message once the API accepts it", async () => {
    post.mockResolvedValue({ message: "Two-factor authentication turned off" });
    render(<TwoFactorLockoutRecoveryPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Turn off two-factor" }));

    expect(await screen.findByText("Two-factor authentication turned off")).toBeInTheDocument();
  });
});
