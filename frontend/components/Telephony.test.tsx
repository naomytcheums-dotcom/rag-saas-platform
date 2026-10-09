// SEC-004 -- the Telephony component must only talk to the organization-scoped call routes
// (the platform-wide /twilio/calls|outbound|{sid}/end routes are superadmin-only now).

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Telephony from "./Telephony";

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));

vi.mock("@/lib/api", () => ({
  api: { get, post },
  ApiError: class ApiError extends Error {
    status: number;
    detail: unknown;
    constructor(status: number, detail: unknown) {
      super(String(detail));
      this.status = status;
      this.detail = detail;
    }
  },
}));

const inProgressCall = {
  id: "c1", call_sid: "CA1", from_number: "+15550000000", to_number: "+15551234567", status: "in-progress",
  duration_seconds: null, started_at: "2026-10-09T10:00:00Z", ended_at: null,
};

describe("Telephony", () => {
  beforeEach(() => {
    get.mockReset().mockResolvedValue([inProgressCall]);
    post.mockReset().mockResolvedValue({});
  });

  it("lists the calls of its own organization", async () => {
    render(<Telephony orgId="org-1" agentId="agent-1" />);
    await waitFor(() => expect(get).toHaveBeenCalledWith("/organizations/org-1/twilio/calls"));
    expect(get).not.toHaveBeenCalledWith("/twilio/calls");
    expect(await screen.findByText("+15551234567")).toBeInTheDocument();
  });

  it("places a call through the organization route with a JSON body", async () => {
    render(<Telephony orgId="org-1" agentId="agent-1" />);
    await userEvent.type(screen.getByPlaceholderText("+15551234567"), "+15557654321");
    await userEvent.click(screen.getByRole("button", { name: "Call" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/organizations/org-1/twilio/outbound", { to: "+15557654321", agent_id: "agent-1" }),
    );
  });

  it("ends a call through the organization route", async () => {
    render(<Telephony orgId="org-1" agentId="agent-1" />);
    await userEvent.click(await screen.findByRole("button", { name: "End call" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/organizations/org-1/twilio/calls/CA1/end"));
  });
});
