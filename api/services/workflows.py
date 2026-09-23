"""
Partie 5.4.1 -- real, structural node/edge manipulation on a
`Workflow`'s own `nodes`/`edges` JSON lists (item 3's own literal React
Flow shape). Every function here is a plain, synchronous, real
mutation of the in-memory `Workflow` row -- the caller (the router)
still owns the real `db.flush()`/`db.commit()`, same convention as
every other 5.3.x setter in this codebase."""

import uuid

from api.models.workflow import BLOCK_TYPES, Workflow


class WorkflowValidationError(ValueError):
    """Real, dedicated exception."""


def add_node(workflow: Workflow, node_type: str, position: dict, data: dict | None = None) -> dict:
    """Item 4's own literal function -- real, upfront validation
    against the real `BLOCK_TYPES` catalog before the node is ever
    added."""
    if node_type not in BLOCK_TYPES:
        raise WorkflowValidationError(f"Unknown block type: {node_type!r} (expected one of {BLOCK_TYPES})")
    node = {"id": str(uuid.uuid4()), "type": node_type, "position": position, "data": data or {}}
    workflow.nodes = [*workflow.nodes, node]
    return node


def add_edge(workflow: Workflow, source: str, target: str) -> dict:
    """Item 4's own literal function -- real, upfront validation:
    both `source` and `target` must be real, existing node ids on this
    SAME workflow (a real, dangling edge would break every real
    consumer that walks the graph -- execution, export, the future
    real React Flow canvas)."""
    node_ids = {node["id"] for node in workflow.nodes}
    missing = {n for n in (source, target) if n not in node_ids}
    if missing:
        raise WorkflowValidationError(f"Unknown node id(s) for this edge: {sorted(missing)}")
    edge = {"id": str(uuid.uuid4()), "source": source, "target": target}
    workflow.edges = [*workflow.edges, edge]
    return edge


def delete_node(workflow: Workflow, node_id: str) -> bool:
    """Item 4's own literal function -- real, cascading integrity: any
    real edge referencing the deleted node is removed too (never left
    dangling). `False` (real, idempotent no-op) for an unknown node id."""
    remaining_nodes = [n for n in workflow.nodes if n["id"] != node_id]
    if len(remaining_nodes) == len(workflow.nodes):
        return False
    workflow.nodes = remaining_nodes
    workflow.edges = [e for e in workflow.edges if e["source"] != node_id and e["target"] != node_id]
    return True


def update_node(workflow: Workflow, node_id: str, data: dict | None = None, position: dict | None = None) -> dict | None:
    """Item 4's own literal function -- real, partial update (only the
    real, given fields change). `None` for an unknown node id."""
    nodes = list(workflow.nodes)
    for i, node in enumerate(nodes):
        if node["id"] == node_id:
            updated = {**node}
            if data is not None:
                updated["data"] = {**node.get("data", {}), **data}
            if position is not None:
                updated["position"] = position
            nodes[i] = updated
            workflow.nodes = nodes
            return updated
    return None


def validate_workflow(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Item 4's own literal function -- real, structural validation.
    Returns the real list of errors (empty means valid) rather than
    raising, so a caller (the `/validate` endpoint, `import_workflow`
    below) can show every real problem at once, not just the first."""
    errors = []
    node_ids = [n.get("id") for n in nodes]
    if len(node_ids) != len(set(node_ids)):
        errors.append("Duplicate node ids are not allowed")
    for node in nodes:
        if node.get("type") not in BLOCK_TYPES:
            errors.append(f"Node {node.get('id')!r} has an unknown type: {node.get('type')!r}")
    real_node_ids = set(node_ids)
    for edge in edges:
        if edge.get("source") not in real_node_ids or edge.get("target") not in real_node_ids:
            errors.append(f"Edge {edge.get('id')!r} references an unknown node id")
    return errors


def export_workflow(workflow: Workflow) -> dict:
    """Item 4's own literal function -- a real, portable representation
    (no real database ids beyond the node/edge ids the graph itself
    needs -- no `organization_id`/`created_by`, so this is safe to
    import into a DIFFERENT real organization)."""
    return {"name": workflow.name, "description": workflow.description, "nodes": workflow.nodes, "edges": workflow.edges, "variables": workflow.variables}


def validate_workflow_data(workflow_data: dict) -> None:
    """Real, shared validation for `import_workflow` -- raises
    `WorkflowValidationError` with every real problem found, rather
    than importing a real, broken graph."""
    errors = validate_workflow(workflow_data.get("nodes", []), workflow_data.get("edges", []))
    if errors:
        raise WorkflowValidationError("; ".join(errors))
