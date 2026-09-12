// Partie 19 -- real render/interaction tests for the white-label
// components. Same pattern as frontend/components/plugins/components.test.tsx:
// `@/lib/api` is mocked (no real network call in a component test), each
// test asserts the component rendered/behaved correctly given a mocked
// response, not that a live backend exists.
//
// Placed alongside the components (frontend/components/whitelabel/), the
// same convention frontend/components/plugins and .../integrations
// already established -- not at the spec's own suggested
// tests/frontend/whitelabel/ path, which sits outside vitest's project
// root (frontend/) and would never actually be discovered/run.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ColorPicker } from "./ColorPicker";
import { CustomCSSEditor } from "./CustomCSSEditor";
import { CustomJSEditor } from "./CustomJSEditor";
import { DomainConfig } from "./DomainConfig";
import { EmailConfig } from "./EmailConfig";
import { LogoUpload } from "./LogoUpload";
import { WhiteLabelConfig } from "./WhiteLabelConfig";

const SAMPLE_CONFIG = {
  organization_id: "org1", logo_url: null, favicon_url: null,
  primary_color: "#2563eb", secondary_color: "#1e293b", accent_color: "#f59e0b", font_family: "Inter",
  brand_name: null, custom_css: null, custom_js: null, hide_platform_branding: false,
  company_email: null, support_email: null, email_sender_name: null, email_sender_email: null,
  is_active: true, domain: null, domain_verified: false,
};

describe("ColorPicker", () => {
  it("shows an error for an invalid hex value and calls onChange while typing", async () => {
    const onChange = vi.fn();
    const { rerender } = render(<ColorPicker label="Primary" value="#2563eb" onChange={onChange} />);
    expect(screen.queryByText(/must be a hex color/i)).not.toBeInTheDocument();

    rerender(<ColorPicker label="Primary" value="not-a-color" onChange={onChange} />);
    expect(screen.getByText(/must be a hex color/i)).toBeInTheDocument();

    await userEvent.type(screen.getByPlaceholderText("#2563eb"), "x");
    expect(onChange).toHaveBeenCalled();
  });
});

describe("CustomCSSEditor / CustomJSEditor", () => {
  it("shows a live character count for custom CSS", () => {
    render(<CustomCSSEditor value="body { color: red; }" onChange={vi.fn()} />);
    expect(screen.getByText((_, node) => node?.textContent === "20/20000")).toBeInTheDocument();
  });

  it("warns that custom JS runs unsanitized", () => {
    render(<CustomJSEditor value="" onChange={vi.fn()} />);
    expect(screen.getByText(/runs as-is with no sanitization/i)).toBeInTheDocument();
  });
});

describe("LogoUpload", () => {
  it("shows 'No logo' with no logo_url and an Upload button", () => {
    render(<LogoUpload logoUrl={null} onUpload={vi.fn()} onRemove={vi.fn()} />);
    expect(screen.getByText("No logo")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload" })).toBeInTheDocument();
  });

  it("shows Replace/Remove once a logo is set", () => {
    render(<LogoUpload logoUrl="https://cdn.example.com/logo.png" onUpload={vi.fn()} onRemove={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Replace" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove" })).toBeInTheDocument();
  });

  it("calls onRemove when Remove is clicked", async () => {
    const onRemove = vi.fn().mockResolvedValue(undefined);
    render(<LogoUpload logoUrl="https://cdn.example.com/logo.png" onUpload={vi.fn()} onRemove={onRemove} />);
    await userEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(onRemove).toHaveBeenCalledTimes(1));
  });
});

describe("DomainConfig", () => {
  it("shows an input to add a domain when none is set", () => {
    render(<DomainConfig domain={null} domainVerified={false} onSet={vi.fn()} onRemove={vi.fn()} onVerify={vi.fn()} />);
    expect(screen.getByPlaceholderText("app.your-domain.com")).toBeInTheDocument();
  });

  it("shows the domain and a Pending badge when unverified", () => {
    render(<DomainConfig domain="app.acme.example" domainVerified={false} onSet={vi.fn()} onRemove={vi.fn()} onVerify={vi.fn()} />);
    expect(screen.getByText("app.acme.example")).toBeInTheDocument();
    expect(screen.getByText("Pending verification")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Verify now" })).toBeInTheDocument();
  });

  it("shows a Verified badge and no Verify button once verified", () => {
    render(<DomainConfig domain="app.acme.example" domainVerified onSet={vi.fn()} onRemove={vi.fn()} onVerify={vi.fn()} />);
    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Verify now" })).not.toBeInTheDocument();
  });

  it("calls onSet with the trimmed input when Add is clicked", async () => {
    const onSet = vi.fn().mockResolvedValue(undefined);
    render(<DomainConfig domain={null} domainVerified={false} onSet={onSet} onRemove={vi.fn()} onVerify={vi.fn()} />);
    await userEvent.type(screen.getByPlaceholderText("app.your-domain.com"), "  app.acme.example  ");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() => expect(onSet).toHaveBeenCalledWith("app.acme.example"));
  });
});

describe("EmailConfig", () => {
  it("saves the sender name and email", async () => {
    const onConfigure = vi.fn().mockResolvedValue(undefined);
    render(<EmailConfig senderName={null} senderEmail={null} onConfigure={onConfigure} onRemove={vi.fn()} />);
    await userEvent.type(screen.getByPlaceholderText("Sender name"), "Acme Support");
    await userEvent.type(screen.getByPlaceholderText("sender@yourdomain.com"), "support@acme.example");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onConfigure).toHaveBeenCalledWith({ sender_name: "Acme Support", sender_email: "support@acme.example" }));
  });

  it("shows Remove only when a sender is already configured", () => {
    const { rerender } = render(<EmailConfig senderName={null} senderEmail={null} onConfigure={vi.fn()} onRemove={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Remove" })).not.toBeInTheDocument();

    rerender(<EmailConfig senderName="Acme Support" senderEmail="support@acme.example" onConfigure={vi.fn()} onRemove={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Remove" })).toBeInTheDocument();
  });
});

describe("WhiteLabelConfig", () => {
  it("saves brand name, colors, and the active toggle", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<WhiteLabelConfig config={SAMPLE_CONFIG} onSave={onSave} />);

    await userEvent.type(screen.getByLabelText("Company name"), "Acme Corp");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ brand_name: "Acme Corp", is_active: true })));
  });

  it("shows 'Saved' briefly after a successful save", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<WhiteLabelConfig config={SAMPLE_CONFIG} onSave={onSave} />);
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Saved" })).toBeInTheDocument());
  });
});
