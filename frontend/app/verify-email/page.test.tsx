// Spec 1.1.4: the e-mail verification screen sends the 6-digit code to POST /auth/verify-email/confirm and can request a new one.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const post = vi.fn();
const push = vi.fn();

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/i18n", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock("@/components/auth/AuthShell", () => ({
  default: ({ title, error, children, footer }: { title: string; error?: string | null; children: React.ReactNode; footer?: React.ReactNode }) => (
    <div><h1>{title}</h1>{error && <p role="alert">{error}</p>}{children}{footer}</div>
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
import VerifyEmailPage from "./page";

beforeEach(() => {
  post.mockReset();
  push.mockReset();
});

describe("VerifyEmailPage", () => {
  it("keeps the submit button disabled until 6 characters are typed", async () => {
    render(<VerifyEmailPage />);
    expect(screen.getByRole("button", { name: "auth.verify.submit" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("auth.verify.code"), "12345");
    expect(screen.getByRole("button", { name: "auth.verify.submit" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("auth.verify.code"), "6");
    expect(screen.getByRole("button", { name: "auth.verify.submit" })).toBeEnabled();
  });

  it("sends the code and goes to the profile on success", async () => {
    post.mockResolvedValue({ message: "ok" });
    render(<VerifyEmailPage />);
    await userEvent.type(screen.getByLabelText("auth.verify.code"), "123456");
    await userEvent.click(screen.getByRole("button", { name: "auth.verify.submit" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/auth/verify-email/confirm", { code: "123456" }));
    expect(push).toHaveBeenCalledWith("/dashboard/profile");
  });

  it("shows the server error for a wrong code and does not navigate", async () => {
    post.mockRejectedValue(new ApiError(400, "Invalid or expired code"));
    render(<VerifyEmailPage />);
    await userEvent.type(screen.getByLabelText("auth.verify.code"), "000000");
    await userEvent.click(screen.getByRole("button", { name: "auth.verify.submit" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid or expired code");
    expect(push).not.toHaveBeenCalled();
  });

  it("requests a new code", async () => {
    post.mockResolvedValue({ message: "sent" });
    render(<VerifyEmailPage />);
    await userEvent.click(screen.getByRole("button", { name: "auth.verify.resend" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/auth/verify-email/request", {}));
    expect(await screen.findByRole("status")).toHaveTextContent("auth.verify.sent");
  });
});
