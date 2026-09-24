// Phase 5, Étape 5 -- real render/interaction tests for the Workflow
// Builder UI's own components. `@/lib/api` is mocked (no real network
// call in a component test), same convention as fine-tuning/media/etc.

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { validateWorkflow } from "./validator";
import { VariablePanel, type WorkflowVariable } from "./VariablePanel";
import { Toolbar } from "./Toolbar";
import type { WorkflowEdge, WorkflowNode } from "@/lib/services/workflows";

const mockApi = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(), postMultipart: vi.fn(), putMultipart: vi.fn(), postFile: vi.fn() }));

vi.mock("@/lib/api", () => ({
  api: mockApi,
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, detail: unknown) {
      super(String(detail));
      this.status = status;
    }
  },
  fileUrl: (path: string) => `http://localhost:8000${path}`,
}));

describe("validateWorkflow", () => {
  const trigger: WorkflowNode = { id: "start", type: "trigger", position: { x: 0, y: 0 } };

  it("flags duplicate node ids, exactly mirroring the real backend check", () => {
    const nodes: WorkflowNode[] = [trigger, { id: "start", type: "llm_call", position: { x: 0, y: 0 } }];
    const result = validateWorkflow(nodes, []);
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toMatch(/dupliqués/);
  });

  it("flags an unknown node type", () => {
    const nodes: WorkflowNode[] = [trigger, { id: "bad", type: "not_real" as WorkflowNode["type"], position: { x: 0, y: 0 } }];
    const result = validateWorkflow(nodes, []);
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toMatch(/type inconnu/);
  });

  it("flags a dangling edge", () => {
    const nodes: WorkflowNode[] = [trigger];
    const edges: WorkflowEdge[] = [{ id: "e1", source: "start", target: "missing" }];
    const result = validateWorkflow(nodes, edges);
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toMatch(/nœud inconnu/);
  });

  it("accepts a real, valid linear graph with zero errors", () => {
    const nodes: WorkflowNode[] = [trigger, { id: "llm", type: "llm_call", position: { x: 0, y: 0 } }];
    const edges: WorkflowEdge[] = [{ id: "e1", source: "start", target: "llm" }];
    const result = validateWorkflow(nodes, edges);
    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it("warns (does not error) on a real cycle -- the backend caps steps at runtime instead of rejecting it", () => {
    const nodes: WorkflowNode[] = [trigger, { id: "a", type: "code", position: { x: 0, y: 0 } }, { id: "b", type: "code", position: { x: 0, y: 0 } }];
    const edges: WorkflowEdge[] = [
      { id: "e1", source: "start", target: "a" },
      { id: "e2", source: "a", target: "b" },
      { id: "e3", source: "b", target: "a" },
    ];
    const result = validateWorkflow(nodes, edges);
    expect(result.valid).toBe(true);
    expect(result.warnings.some((w) => w.includes("cycle"))).toBe(true);
  });

  it("warns on an orphan node unreachable from the trigger", () => {
    const nodes: WorkflowNode[] = [trigger, { id: "orphan", type: "code", position: { x: 0, y: 0 } }];
    const result = validateWorkflow(nodes, []);
    expect(result.valid).toBe(true);
    expect(result.warnings.some((w) => w.includes("orphan"))).toBe(true);
  });
});

describe("VariablePanel", () => {
  it("renders existing variables and adds a new one", () => {
    const variables: WorkflowVariable[] = [{ name: "question", type: "string", default_value: "", scope: "global" }];
    const onChange = vi.fn();
    render(<VariablePanel variables={variables} onChange={onChange} />);

    expect(screen.getByDisplayValue("question")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("add-variable"));
    expect(onChange).toHaveBeenCalledWith([
      variables[0],
      { name: "", type: "string", default_value: "", description: "", scope: "global" },
    ]);
  });
});

describe("Toolbar", () => {
  it("renders validation errors and warnings when present", () => {
    render(
      <Toolbar
        onAddNode={vi.fn()}
        onSave={vi.fn()}
        saving={false}
        onExport={vi.fn()}
        onImport={vi.fn()}
        onUseTemplate={vi.fn()}
        onUndo={vi.fn()}
        onRedo={vi.fn()}
        canUndo={false}
        canRedo={false}
        validationErrors={["Un vrai problème"]}
        validationWarnings={["Un vrai avertissement"]}
      />,
    );
    expect(screen.getByTestId("validation-errors")).toHaveTextContent("Un vrai problème");
    expect(screen.getByTestId("validation-warnings")).toHaveTextContent("Un vrai avertissement");
  });

  it("lists every real template and calls onUseTemplate with its id", () => {
    const onUseTemplate = vi.fn();
    render(
      <Toolbar
        onAddNode={vi.fn()}
        onSave={vi.fn()}
        saving={false}
        onExport={vi.fn()}
        onImport={vi.fn()}
        onUseTemplate={onUseTemplate}
        onUndo={vi.fn()}
        onRedo={vi.fn()}
        canUndo={false}
        canRedo={false}
        validationErrors={[]}
        validationWarnings={[]}
      />,
    );
    fireEvent.click(screen.getByTestId("templates-button"));
    fireEvent.click(screen.getByTestId("use-template-simple-chatbot"));
    expect(onUseTemplate).toHaveBeenCalledWith("simple-chatbot");
  });
});
