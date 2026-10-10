// Spec 1.1.5 / 1.1.6: the login and register pages must offer "Continue with Google / GitHub" when the deployment enables those providers.
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/i18n", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock("@/lib/api", () => ({ fileUrl: (path: string) => `http://api.test${path}` }));

import OAuthButtons from "./OAuthButtons";

afterEach(() => vi.unstubAllEnvs());

describe("OAuthButtons", () => {
  it("renders nothing when no provider is enabled", () => {
    vi.stubEnv("NEXT_PUBLIC_OAUTH_PROVIDERS", "");
    const { container } = render(<OAuthButtons />);
    expect(container).toBeEmptyDOMElement();
  });

  it("links each enabled provider to the API authorize route", () => {
    vi.stubEnv("NEXT_PUBLIC_OAUTH_PROVIDERS", "google, github");
    render(<OAuthButtons />);
    expect(screen.getByText("auth.oauth.google").closest("a")).toHaveAttribute("href", "http://api.test/auth/oauth/google/authorize");
    expect(screen.getByText("auth.oauth.github").closest("a")).toHaveAttribute("href", "http://api.test/auth/oauth/github/authorize");
  });

  it("ignores unknown providers", () => {
    vi.stubEnv("NEXT_PUBLIC_OAUTH_PROVIDERS", "google,facebook");
    render(<OAuthButtons />);
    expect(screen.queryByText("auth.oauth.github")).toBeNull();
    expect(screen.getAllByRole("link")).toHaveLength(1);
  });
});
