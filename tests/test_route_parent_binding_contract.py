"""Contract (phase 5 of the 2026-10-12 security audit, follow-up of TEN-011..013): a route must not authorize the caller on a PARENT of its path
(the organization, an agent, a workspace, a dataset, ...) and then act on a CHILD object named by another identifier of the same path without using that parent.

Defect found on 2026-10-12 in five routes: DELETE /organizations/{org_id}/api-keys/{key_id} revoked the key of ANY organization, because the service loaded the key by
`key_id` alone. This reads the routers (no database) and lists every route whose path has a parent identifier followed by a child identifier while the function body
never uses the parent. Textual: it proves the parent is MENTIONED, not that the check is correct (the A/B tests of tests/test_p3_*.py prove the behaviour).
A route that is bound some other way (a dependency that resolves the child inside its parent) goes in ALLOWED with the reason.
"""

import ast
import re
from pathlib import Path

ROUTERS = Path(__file__).resolve().parents[1] / "api" / "routers"
PARENTS = ("org_id", "agent_id", "workspace_id", "dataset_id", "workflow_id", "conversation_id", "team_id", "document_id", "project_id", "integration_id", "channel_id")
_ROUTE = re.compile(r"router\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)[\"']")

# "METHOD /path" -> why the child is bound to the parent although the body does not name the parent. Empty on purpose today.
ALLOWED: dict[str, str] = {}


def unbound_child_routes(sources: dict[str, str]) -> list[str]:
    found = []
    for name, text in sorted(sources.items()):
        lines = text.split("\n")
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decorators = " ".join(ast.get_source_segment(text, d) or "" for d in node.decorator_list)
            route = _ROUTE.search(decorators)
            if not route:
                continue
            method, path = route.group(1).upper(), route.group(2)
            params = re.findall(r"\{(\w+)\}", path)
            parent = next((p for p in params if p in PARENTS), None)
            children = [p for p in params if p.endswith("_id") and p != parent]
            if parent is None or not children or params.index(parent) > params.index(children[0]):
                continue
            body = "\n".join(lines[node.body[0].lineno - 1: node.end_lineno])
            body = re.sub(r"log_audit_action\((?:[^()]|\([^()]*\))*\)", "", body, flags=re.S)  # an audit entry does not bind anything
            root = parent[:-3]
            uses = len(re.findall(rf"\b{parent}\b", body))
            uses += len(re.findall(r"\borganization_id\b", body)) if parent == "org_id" else len(re.findall(rf"\b{root}\w*", body))
            if uses == 0 and f"{method} {path}" not in ALLOWED:
                found.append(f"{name}: {method} {path} ({node.name}) acts on {children[0]} without using {parent}")
    return found


def test_no_route_acts_on_a_child_object_without_using_its_authorized_parent():
    sources = {path.name: path.read_text(encoding="utf-8") for path in ROUTERS.glob("*.py")}
    assert len(sources) > 20, "the routers were not found"
    assert unbound_child_routes(sources) == []


def test_the_contract_detects_the_defect_found_on_2026_10_12():
    defective = '''
@router.delete("/organizations/{org_id}/api-keys/{key_id}", status_code=204)
async def revoke(org_id: uuid.UUID, key_id: uuid.UUID, caller=Depends(require_permission("settings:manage")), db=Depends(get_db)):
    revoked = await revoke_api_key(db, key_id)
    await log_audit_action(db, user_id=caller.user_id, organization_id=org_id, resource_id=str(key_id))
'''
    fixed = defective.replace("revoke_api_key(db, key_id)", "revoke_api_key(db, key_id, organization_id=org_id)")
    assert len(unbound_child_routes({"defective.py": defective})) == 1
    assert unbound_child_routes({"fixed.py": fixed}) == []


def test_a_resolved_parent_object_counts_as_binding():
    bound = '''
@router.delete("/agents/{agent_id}/api-keys/{key_id}", status_code=204)
async def revoke(key_id: uuid.UUID, agent_ctx=Depends(require_agent_manager), db=Depends(get_db)):
    agent, _caller = agent_ctx
    row = await db.get(AgentAPIKey, key_id)
    if row is not None and row.agent_id == agent.id:
        await revoke_api_key(db, key_id)
'''
    assert unbound_child_routes({"bound.py": bound}) == []
