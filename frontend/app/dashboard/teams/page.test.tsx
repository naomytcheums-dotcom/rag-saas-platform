// Specs 1.3.2 / 1.3.3: workspaces and teams screen.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
const del = vi.fn();

const translation = { t: (key: string) => key };
vi.mock("@/lib/i18n", () => ({ useTranslation: () => translation }));
const currentOrg = { org: { id: "org-1" } };
vi.mock("@/lib/useCurrentOrg", () => ({ useCurrentOrg: () => currentOrg }));
vi.mock("@/components/LoadingState", () => ({ default: () => <p>loading</p> }));
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
  return { api: { get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a), delete: (...a: unknown[]) => del(...a) }, ApiError };
});

import { ApiError } from "@/lib/api";
import TeamsPage from "./page";

beforeEach(() => {
  get.mockReset(); post.mockReset(); del.mockReset();
  get.mockImplementation((path: string) => {
    if (path.endsWith("/workspaces")) return Promise.resolve({ items: [{ id: "w1", name: "Marketing" }] });
    if (path.endsWith("/teams")) return Promise.resolve({ items: [{ id: "t1", name: "Support", description: null }] });
    if (path === "/teams/t1/members") return Promise.resolve({ items: [{ user_id: "u1", email: "ana@example.com", role: "member" }] });
    return Promise.resolve({ items: [] });
  });
  post.mockResolvedValue({});
  del.mockResolvedValue({});
});

describe("TeamsPage", () => {
  it("lists workspaces and teams", async () => {
    render(<TeamsPage />);
    expect(await screen.findByText("Marketing")).toBeInTheDocument();
    expect(screen.getByText("Support")).toBeInTheDocument();
  });

  it("creates a workspace and a team", async () => {
    render(<TeamsPage />);
    await userEvent.type(await screen.findByLabelText("teams.workspace_name"), "Sales");
    await userEvent.click(screen.getAllByRole("button", { name: "teams.create" })[0]);
    await waitFor(() => expect(post).toHaveBeenCalledWith("/organizations/org-1/workspaces", { name: "Sales" }));
    await userEvent.type(screen.getByLabelText("teams.team_name"), "Legal");
    await userEvent.click(screen.getAllByRole("button", { name: "teams.create" })[1]);
    await waitFor(() => expect(post).toHaveBeenCalledWith("/organizations/org-1/teams", { name: "Legal" }));
  });

  it("opens a team, adds a member by e-mail and removes another", async () => {
    render(<TeamsPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Support" }));
    expect(await screen.findByText(/ana@example\.com/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("teams.member_email"), "bob@example.com");
    await userEvent.click(screen.getByRole("button", { name: "teams.add_member" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/teams/t1/members", { email: "bob@example.com", role: "member" }));
    await userEvent.click(screen.getByRole("button", { name: "teams.remove" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("/teams/t1/members/u1"));
  });

  it("deletes a workspace and shows server errors", async () => {
    del.mockRejectedValueOnce(new ApiError(403, "Admins only"));
    render(<TeamsPage />);
    const buttons = await screen.findAllByRole("button", { name: "teams.delete" });
    await userEvent.click(buttons[0]);
    expect(await screen.findByRole("alert")).toHaveTextContent("Admins only");
    expect(del).toHaveBeenCalledWith("/workspaces/w1");
  });
});
