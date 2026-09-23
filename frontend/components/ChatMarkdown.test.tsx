// Phase 5, Étape 9 -- real render tests for ChatMarkdown: Markdown
// rendering, syntax-highlighted code blocks, and real citation
// click-through preservation, all in one component. No network mock
// needed -- this component takes plain text/citations as props.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ChatMarkdown from "./ChatMarkdown";

const CITATION = {
  id: "c1", citation_number: 1, document_id: "d1", document_title: "Doc One", url: null, exact_passage: "Some passage", relevance_score: 0.9,
};

describe("ChatMarkdown", () => {
  it("renders real Markdown formatting (bold, headings, lists)", () => {
    render(<ChatMarkdown text={"# Title\n\n**bold** and a list:\n\n- one\n- two"} />);

    expect(screen.getByRole("heading", { level: 1, name: "Title" })).toBeInTheDocument();
    expect(screen.getByText("bold")).toBeInTheDocument();
    expect(screen.getByText("one")).toBeInTheDocument();
  });

  it("renders a fenced code block with syntax highlighting, not plain text", () => {
    render(<ChatMarkdown text={"```python\nprint('hi')\n```"} />);

    expect(screen.getByText("print")).toBeInTheDocument();
  });

  it("renders a real, clickable citation badge for a [n] marker with a matching citation", () => {
    render(<ChatMarkdown text="The sky is blue [1]." citations={[CITATION]} />);

    expect(screen.getByRole("button", { name: /1/ })).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("leaves an unmatched [n] marker as real, plain link text", () => {
    render(<ChatMarkdown text="See [1] for details." citations={[]} />);

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByText(/for details/)).toBeInTheDocument();
  });

  it("never renders a real, executable <script> element from raw HTML input", () => {
    const { container } = render(<ChatMarkdown text={"<script>window.__hacked = true</script>real text"} />);

    expect(container.querySelector("script")).not.toBeInTheDocument();
    expect((window as unknown as { __hacked?: boolean }).__hacked).toBeUndefined();
  });
});
