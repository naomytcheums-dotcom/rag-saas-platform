// Connected accounts screen (docs/DECISIONS.md D17): an organization gives the credentials of its own services.
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const put = vi.fn();
const del = vi.fn();

const translation = { t: (key: string) => key };
vi.mock("@/lib/i18n", () => ({ useTranslation: () => translation }));
const currentOrg = { org: { id: "org-1", my_role: "owner" } };
vi.mock("@/lib/useCurrentOrg", () => ({ useCurrentOrg: () => currentOrg }));
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
  return { api: { get: (...a: unknown[]) => get(...a), put: (...a: unknown[]) => put(...a), delete: (...a: unknown[]) => del(...a) }, ApiError };
});

import { ApiError } from "@/lib/api";
import ConnectorsPage from "./page";

const LIST = {
  platform_credentials_allowed: false,
  connectors: [
    { provider: "github", connected: false, fields_set: [], required_fields: [], optional_fields: ["GITHUB_API_TOKEN"], works_without_credentials: true, updated_at: null },
    { provider: "jira", connected: false, fields_set: [], required_fields: ["JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"], optional_fields: [], works_without_credentials: false, updated_at: null },
    { provider: "notion", connected: true, fields_set: ["NOTION_API_TOKEN"], required_fields: ["NOTION_API_TOKEN"], optional_fields: [], works_without_credentials: false, updated_at: "2026-10-11T10:00:00Z" },
  ],
};

beforeEach(() => {
  get.mockReset(); put.mockReset(); del.mockReset();
  currentOrg.org.my_role = "owner";
  get.mockResolvedValue(LIST);
  put.mockResolvedValue({});
  del.mockResolvedValue({});
});

describe("ConnectorsPage", () => {
  it("lists the services with their state", async () => {
    render(<ConnectorsPage />);
    expect(await screen.findByText("Jira")).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith("/organizations/org-1/connectors");
    const notion = document.querySelector("[data-provider='notion']") as HTMLElement;
    expect(within(notion).getByText("connectors.connected")).toBeInTheDocument();
    const jira = document.querySelector("[data-provider='jira']") as HTMLElement;
    expect(within(jira).getByText("connectors.not_connected")).toBeInTheDocument();
    expect(screen.getByText("connectors.public_data_note")).toBeInTheDocument(); // GitHub works without credentials
  });

  it("filters the services by name", async () => {
    render(<ConnectorsPage />);
    await screen.findByText("Jira");
    await userEvent.type(screen.getByLabelText("connectors.filter"), "not");
    expect(screen.queryByText("Jira")).not.toBeInTheDocument();
    expect(screen.getByText("Notion")).toBeInTheDocument();
  });

  it("saves the credentials of the organization, hiding every secret field", async () => {
    render(<ConnectorsPage />);
    const jira = (await screen.findByText("Jira")).closest("li") as HTMLElement;
    await userEvent.click(within(jira).getByRole("button", { name: "connectors.connect" }));

    const token = within(jira).getByLabelText(/Api token/i) as HTMLInputElement;
    expect(token.type).toBe("password");
    expect((within(jira).getByLabelText(/Email/i) as HTMLInputElement).type).toBe("text");

    await userEvent.type(within(jira).getByLabelText(/Base url/i), "https://acme.atlassian.net");
    await userEvent.type(within(jira).getByLabelText(/Email/i), "ada@acme.example");
    await userEvent.type(token, "my-secret-token");
    await userEvent.click(within(jira).getByRole("button", { name: "connectors.save" }));

    await waitFor(() => expect(put).toHaveBeenCalledWith("/organizations/org-1/connectors/jira", {
      fields: { JIRA_BASE_URL: "https://acme.atlassian.net", JIRA_EMAIL: "ada@acme.example", JIRA_API_TOKEN: "my-secret-token" },
    }));
    expect(await within(jira).findByRole("status")).toHaveTextContent("connectors.saved");
    expect(token.value).toBe(""); // the secret is cleared from the screen after saving
  });

  it("shows the server's refusal", async () => {
    put.mockRejectedValue(new ApiError(422, "JIRA_BASE_URL must be an https address"));
    render(<ConnectorsPage />);
    const jira = (await screen.findByText("Jira")).closest("li") as HTMLElement;
    await userEvent.click(within(jira).getByRole("button", { name: "connectors.connect" }));
    await userEvent.type(within(jira).getByLabelText(/Base url/i), "http://x");
    await userEvent.type(within(jira).getByLabelText(/Email/i), "a@b.c");
    await userEvent.type(within(jira).getByLabelText(/Api token/i), "t");
    await userEvent.click(within(jira).getByRole("button", { name: "connectors.save" }));
    expect(await within(jira).findByRole("alert")).toHaveTextContent("https address");
  });

  it("disconnects a service", async () => {
    render(<ConnectorsPage />);
    const notion = (await screen.findByText("Notion")).closest("li") as HTMLElement;
    await userEvent.click(within(notion).getByRole("button", { name: "connectors.replace" }));
    await userEvent.click(within(notion).getByRole("button", { name: "connectors.remove" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("/organizations/org-1/connectors/notion"));
  });

  it("is read-only for a member who is not an administrator", async () => {
    currentOrg.org.my_role = "member";
    render(<ConnectorsPage />);
    await screen.findByText("Jira");
    expect(screen.getByText("connectors.read_only")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "connectors.connect" })).not.toBeInTheDocument();
  });
});
