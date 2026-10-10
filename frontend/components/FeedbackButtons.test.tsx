// Specs 8.1.9 / 15.2.2 / 15.2.3 / 15.2.4: a thumbs down can carry a reason, a free comment and a proposed correction.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const post = vi.fn();
const translation = { t: (key: string) => key };
vi.mock("@/lib/i18n", () => ({ useTranslation: () => translation }));
vi.mock("@/lib/api", () => {
  class ApiError extends Error {}
  return { api: { post: (...a: unknown[]) => post(...a) }, ApiError };
});

import FeedbackButtons from "./FeedbackButtons";

beforeEach(() => post.mockReset());

describe("FeedbackButtons", () => {
  it("sends a thumbs up straight away", async () => {
    post.mockResolvedValue({});
    render(<FeedbackButtons messageId="m1" />);
    await userEvent.click(screen.getByLabelText("good_response"));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/messages/m1/feedback", { rating: "positive", comment: null, reason: null, correction: null }));
  });

  it("asks for details on a thumbs down and sends reason, comment and correction", async () => {
    post.mockResolvedValue({});
    render(<FeedbackButtons messageId="m2" />);
    await userEvent.click(screen.getByLabelText("bad_response"));
    await userEvent.selectOptions(screen.getByLabelText("feedback.reason"), "hallucination");
    await userEvent.type(screen.getByPlaceholderText("what_went_wrong"), "Invented a date");
    await userEvent.type(screen.getByLabelText("feedback.correction"), "The date is 3 March");
    await userEvent.click(screen.getByRole("button", { name: "send" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/messages/m2/feedback", { rating: "negative", comment: "Invented a date", reason: "hallucination", correction: "The date is 3 March" }));
  });

  it("lets the user skip the details", async () => {
    post.mockResolvedValue({});
    render(<FeedbackButtons messageId="m3" />);
    await userEvent.click(screen.getByLabelText("bad_response"));
    await userEvent.click(screen.getByRole("button", { name: "skip" }));
    expect(screen.queryByLabelText("feedback.reason")).toBeNull();
    expect(post).not.toHaveBeenCalled();
  });
});
