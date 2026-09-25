"use client";

// Phase 5, Étape 5 -- the main Workflow Builder canvas, wiring
// React Flow to the real backend (api/routers/workflows.py). Save
// persists via PATCH /workflows/{id}; Run triggers a real execution
// and streams it live (DebugPanel); Import/Export round-trip through
// the real backend endpoints this étape's own audit found missing and
// added.

import { useCallback, useEffect, useMemo, useState } from "react";
import ReactFlow, {
  Background, Controls, MiniMap, addEdge, applyEdgeChanges, applyNodeChanges,
  type Connection, type Edge, type EdgeChange, type Node, type NodeChange,
} from "reactflow";
import "reactflow/dist/style.css";

import { DebugPanel } from "@/components/workflows/DebugPanel";
import { ExecutionHistory } from "@/components/workflows/ExecutionHistory";
import { NodeEditor } from "@/components/workflows/NodeEditor";
import { nodeTypes } from "@/components/workflows/nodeTypes";
import { Toolbar } from "@/components/workflows/Toolbar";
import { WORKFLOW_TEMPLATES } from "@/components/workflows/templates";
import { useTranslation } from "@/lib/i18n";
import { validateWorkflow } from "@/components/workflows/validator";
import { useHistory } from "@/lib/hooks/useHistory";
import { VariablePanel, type WorkflowVariable } from "@/components/workflows/VariablePanel";
import * as workflowService from "@/lib/services/workflows";
import type { Workflow, WorkflowEdge, WorkflowNode, WorkflowNodeType } from "@/lib/services/workflows";

function toRFNode(node: WorkflowNode): Node {
  return { id: node.id, type: node.type, position: node.position, data: node.data ?? {} };
}
function toRFEdge(edge: WorkflowEdge): Edge {
  return { id: edge.id, source: edge.source, target: edge.target };
}
function fromRFNode(node: Node): WorkflowNode {
  return { id: node.id, type: node.type as WorkflowNodeType, position: node.position, data: node.data };
}
function fromRFEdge(edge: Edge): WorkflowEdge {
  return { id: edge.id, source: edge.source, target: edge.target };
}

// The `email` block's real backend config expects `to` as a LIST
// (api/services/workflow_block_email.py's own `config["to"]` check) --
// NodeEditor's own UI keeps it as one comma-separated string field for
// simplicity, converted back to a real list only at save time.
function serializeNodeData(node: WorkflowNode): WorkflowNode {
  if (node.type !== "email" || typeof node.data?.to !== "string") return node;
  const to = (node.data.to as string).split(",").map((s) => s.trim()).filter(Boolean);
  return { ...node, data: { ...node.data, to } };
}

const WORKFLOW_TEMPLATES_MAP = Object.fromEntries(WORKFLOW_TEMPLATES.map((t) => [t.id, t]));

let nodeCounter = 0;

export function WorkflowBuilder({ workflow, onSaved }: { workflow: Workflow; onSaved?: (w: Workflow) => void }) {
  const { t } = useTranslation();
  const history = useHistory<{ nodes: Node[]; edges: Edge[] }>({
    nodes: workflow.nodes.map(toRFNode),
    edges: workflow.edges.map(toRFEdge),
  });
  const nodes = history.state.nodes;
  const edges = history.state.edges;

  const setNodes = useCallback((updater: Node[] | ((prev: Node[]) => Node[])) => {
    const next = typeof updater === "function" ? updater(history.state.nodes) : updater;
    history.set({ nodes: next, edges: history.state.edges });
  }, [history]);

  const setEdges = useCallback((updater: Edge[] | ((prev: Edge[]) => Edge[])) => {
    const next = typeof updater === "function" ? updater(history.state.edges) : updater;
    history.set({ nodes: history.state.nodes, edges: next });
  }, [history]);
  const [variables, setVariables] = useState<WorkflowVariable[]>(() => (workflow.variables as unknown as WorkflowVariable[]) ?? []);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [currentNodeId, setCurrentNodeId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [runRefreshSignal, setRunRefreshSignal] = useState(0);

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((nds) => applyNodeChanges(changes, nds));
  }, [setNodes]);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    setEdges((eds) => applyEdgeChanges(changes, eds));
  }, [setEdges]);

  const undo = useCallback(() => {
    history.undo();
  }, [history]);

  const redo = useCallback(() => {
    history.redo();
  }, [history]);

  // Keyboard shortcuts: Ctrl+Z (undo), Ctrl+Y or Ctrl+Shift+Z (redo)
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
      } else if (
        ((e.ctrlKey || e.metaKey) && e.key === "y") ||
        ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "z")
      ) {
        e.preventDefault();
        redo();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [undo, redo]);

  const onConnect = useCallback((connection: Connection) => {
    setEdges((eds) => addEdge(connection, eds));
    // A condition node's real branch routing comes from its own
    // config (`true_branch`/`false_branch`), not from the edge itself
    // (api/services/workflow_block_condition.py's own real contract) --
    // dragging from its "true"/"false" handle also writes that config.
    if (connection.sourceHandle === "true" || connection.sourceHandle === "false") {
      setNodes((nds) => nds.map((n) => (n.id === connection.source ? { ...n, data: { ...n.data, [`${connection.sourceHandle}_branch`]: connection.target } } : n)));
    }
  }, []);

  const addNode = useCallback((type: WorkflowNodeType) => {
    nodeCounter += 1;
    const id = `${type}_${nodeCounter}`;
    setNodes((nds) => [...nds, { id, type, position: { x: 100 + nds.length * 40, y: 100 + nds.length * 30 }, data: {} }]);
  }, []);

  const updateSelectedNodeData = useCallback((data: Record<string, unknown>) => {
    setNodes((nds) => nds.map((n) => (n.id === selectedNodeId ? { ...n, data } : n)));
  }, [selectedNodeId]);

  const deleteSelectedNode = useCallback(() => {
    setNodes((nds) => nds.filter((n) => n.id !== selectedNodeId));
    setEdges((eds) => eds.filter((e) => e.source !== selectedNodeId && e.target !== selectedNodeId));
    setSelectedNodeId(null);
  }, [selectedNodeId]);

  const workflowNodes = useMemo(() => nodes.map(fromRFNode), [nodes]);
  const workflowEdges = useMemo(() => edges.map(fromRFEdge), [edges]);
  const validation = useMemo(() => validateWorkflow(workflowNodes, workflowEdges), [workflowNodes, workflowEdges]);

  const save = useCallback(async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await workflowService.updateWorkflow(workflow.id, {
        nodes: workflowNodes.map(serializeNodeData),
        edges: workflowEdges,
        variables: variables as unknown as Record<string, unknown>[],
      });
      onSaved?.(updated);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save workflow");
    } finally {
      setSaving(false);
    }
  }, [workflow.id, workflowNodes, workflowEdges, variables, onSaved]);

  const exportJson = useCallback(async () => {
    const exported = await workflowService.exportWorkflow(workflow.id);
    const blob = new Blob([JSON.stringify(exported, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${workflow.name || "workflow"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [workflow.id, workflow.name]);

  const importJson = useCallback(async (file: File) => {
    const text = await file.text();
    try {
      const data = JSON.parse(text) as { name?: string; nodes?: WorkflowNode[]; edges?: WorkflowEdge[]; variables?: WorkflowVariable[] };
      setNodes((data.nodes ?? []).map(toRFNode));
      setEdges((data.edges ?? []).map(toRFEdge));
      setVariables(data.variables ?? []);
    } catch {
      setSaveError(t("workflow_builder.error_invalid_json"));
    }
  }, []);

  const useTemplate = useCallback((templateId: string) => {
    const template = WORKFLOW_TEMPLATES_MAP[templateId];
    if (!template) return;
    setNodes(template.nodes.map(toRFNode));
    setEdges(template.edges.map(toRFEdge));
  }, []);

  const selectedNode = workflowNodes.find((n) => n.id === selectedNodeId) ?? null;

  return (
    <div className="flex h-[calc(100vh-160px)] flex-col rounded-xl border border-border" data-testid="workflow-builder">
      <Toolbar
        onAddNode={addNode}
        onSave={() => void save()}
        saving={saving}
        onExport={() => void exportJson()}
        onImport={(file) => void importJson(file)}
        onUseTemplate={useTemplate}
        onUndo={undo}
        onRedo={redo}
        canUndo={history.canUndo}
        canRedo={history.canRedo}
        validationErrors={validation.errors}
        validationWarnings={validation.warnings}
      />
      {saveError && <p className="px-3 py-1 text-xs text-danger">{saveError}</p>}
      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1" data-testid="canvas">
          <ReactFlow
            nodes={nodes.map((n) => (n.id === currentNodeId ? { ...n, selected: true, className: "ring-2 ring-warning" } : n))}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            fitView
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>
        {selectedNode && (
          <NodeEditor
            node={selectedNode}
            allNodeIds={workflowNodes.map((n) => n.id)}
            onChange={updateSelectedNodeData}
            onClose={() => setSelectedNodeId(null)}
            onDelete={deleteSelectedNode}
          />
        )}
      </div>
      <div className="grid grid-cols-1 divide-x divide-border border-t border-border md:grid-cols-3">
        <VariablePanel variables={variables} onChange={setVariables} />
        <DebugPanel workflowId={workflow.id} onCurrentNodeChange={setCurrentNodeId} onRunStarted={() => setRunRefreshSignal((n) => n + 1)} />
        <ExecutionHistory workflowId={workflow.id} refreshSignal={runRefreshSignal} />
      </div>
    </div>
  );
}
