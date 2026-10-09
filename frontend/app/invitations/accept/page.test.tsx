// MAP-001: the page the invitation e-mail links to. An existing account just accepts; a new invitee is asked for the account details
// once the API says a password is needed. The API client is mocked: the assertions are about what is sent and where the user ends up.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const post = vi.fn();
const push = vi.fn();
let token: string | null = "tok-123";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => ({ get: (key: string) => (key === "token" ? token : null) }),
}));
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
import AcceptInvitationPage from "./page";

const originalLocation = window.location;
const replace = vi.fn();

beforeEach(() => {
  post.mockReset();
  push.mockReset();
  replace.mockReset();
  token = "tok-123";
  window.localStorage.clear();
  Object.defineProperty(window, "location", { configurable: true, value: { replace } });
});

afterEach(() => {
  Object.defineProperty(window, "location", { configurable: true, value: originalLocation });
});

describe("Accept invitation page", () => {
  it("accepts with the token only for an existing account and goes to the login page", async () => {
    post.mockResolvedValue({ message: "Invitation accepted -- log in to access the organization" });
    render(<AcceptInvitationPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Accept invitation" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/login"));
    expect(post).toHaveBeenCalledWith("/invitations/accept", { token: "tok-123" });
  });

  it("asks for the account details when the API needs a password, then signs the new user in", async () => {
    post.mockRejectedValueOnce(new ApiError(400, "A password is required to create your account"));
    post.mockResolvedValueOnce({ message: "Account created and invitation accepted", access_token: "jwt-abc" });
    render(<AcceptInvitationPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Accept invitation" }));
    await userEvent.type(await screen.findByLabelText("Password"), "correct-horse-battery");
    await userEvent.type(screen.getByLabelText("Full name"), "Ada Lovelace");
    const submit = screen.getByRole("button", { name: "Create account and join" });
    expect(submit).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(submit);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
    expect(post).toHaveBeenLastCalledWith("/invitations/accept", { token: "tok-123", password: "correct-horse-battery", full_name: "Ada Lovelace", accept_terms: true });
    expect(window.localStorage.getItem("access_token")).toBe("jwt-abc");
  });

  it("shows an invalid or expired invitation instead of the account form", async () => {
    post.mockRejectedValue(new ApiError(400, "Invalid or expired invitation"));
    render(<AcceptInvitationPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Accept invitation" }));

    expect(await screen.findByText("Invalid or expired invitation")).toBeInTheDocument();
    expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
  });

  it("explains a link without a token and sends nothing", async () => {
    token = null;
    render(<AcceptInvitationPage />);
    expect(await screen.findByText(/missing its token/)).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });
});
