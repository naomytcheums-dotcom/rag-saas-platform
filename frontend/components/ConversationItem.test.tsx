// Regression (E2E, 2026-10-12): the row held a <button> (select) containing another <button> (rename title): invalid HTML and a React hydration error.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

const translation = { t: (key: string) => key };
vi.mock("@/lib/i18n", () => ({ useTranslation: () => translation }));
vi.mock("@/lib/api", () => ({ api: { patch: vi.fn(), delete: vi.fn() }, ApiError: class extends Error {} }));

import ConversationItem from "./ConversationItem";

const conversation = { id: "c1", title: "Kribi office", updated_at: "2026-10-12T10:00:00Z" } as never;

describe("ConversationItem", () => {
  it("never nests a button inside a button", () => {
    const { container } = render(<ConversationItem conversation={conversation} onSelect={() => {}} onRenamed={() => {}} onDeleted={() => {}} />);
    expect(container.querySelector("button button")).toBeNull();
    expect(container.querySelector('[role="button"] button')).toBeNull();
  });

  it("selects the conversation on click and on Enter", async () => {
    const onSelect = vi.fn();
    render(<ConversationItem conversation={conversation} onSelect={onSelect} onRenamed={() => {}} onDeleted={() => {}} />);
    const row = screen.getAllByRole("button")[0];
    await userEvent.click(row);
    row.focus();
    await userEvent.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledTimes(2);
    expect(onSelect).toHaveBeenCalledWith("c1");
  });

  it("opens the rename input on double click", async () => {
    render(<ConversationItem conversation={conversation} onSelect={() => {}} onRenamed={() => {}} onDeleted={() => {}} />);
    await userEvent.dblClick(screen.getByText("Kribi office"));
    expect(screen.getByDisplayValue("Kribi office")).toBeTruthy();
  });
});
