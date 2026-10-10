// Specs 8.2.8 / 8.2.13: the voice settings page mounts the voice settings and, once an agent exists, the telephony panel.
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const translation = { t: (key: string) => key };
vi.mock("@/lib/i18n", () => ({ useTranslation: () => translation }));
const currentOrg = { org: { id: "org-1" } };
vi.mock("@/lib/useCurrentOrg", () => ({ useCurrentOrg: () => currentOrg }));
vi.mock("@/components/VoiceSettings", () => ({ default: () => <p>voice-settings-component</p> }));
vi.mock("@/components/Telephony", () => ({ default: ({ orgId, agentId }: { orgId: string; agentId: string }) => <p>telephony-{orgId}-{agentId}</p> }));
vi.mock("@/lib/api", () => ({ api: { get: (...a: unknown[]) => get(...a) } }));

import VoiceSettingsPage from "./page";

beforeEach(() => get.mockReset());

describe("VoiceSettingsPage", () => {
  it("shows the settings and the telephony panel for the first agent", async () => {
    get.mockResolvedValue([{ id: "agent-9" }]);
    render(<VoiceSettingsPage />);
    expect(screen.getByText("voice-settings-component")).toBeInTheDocument();
    expect(await screen.findByText("telephony-org-1-agent-9")).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith("/organizations/org-1/agents");
  });

  it("hides the telephony panel when the organization has no agent", async () => {
    get.mockResolvedValue([]);
    render(<VoiceSettingsPage />);
    await screen.findByText("voice-settings-component");
    expect(screen.queryByText(/telephony-/)).toBeNull();
  });
});
