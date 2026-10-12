"""Read-only static scan for the class of defect found on 2026-10-12 in DELETE /organizations/{org_id}/api-keys/{key_id}:
the route authorizes the caller on the organization of the PATH, then hands another identifier of the same path to a service that loads the object by that
identifier alone, so an administrator of ANOTHER organization can act on this object.

An endpoint is listed when its path has `{org_id}` plus at least one other `{..._id}`, and the body never uses `org_id` / `organization_id` other than for an audit
log or a response. A listed endpoint is a CANDIDATE to review by hand (the service may bind the object itself); an unlisted one is not proven safe.
Run from the repository root: python audit-reports/phase3-2026-10-12/scan_path_org_with_object_id.py
"""

import ast
import csv
import glob
import re
from pathlib import Path

OUT = Path(__file__).with_name('path_org_object_scan.csv')
PARENTS = ('org_id', 'agent_id', 'workspace_id', 'dataset_id', 'workflow_id', 'conversation_id', 'team_id', 'document_id', 'project_id', 'integration_id', 'channel_id')
ROUTE = re.compile(r'router\.(get|post|put|patch|delete)\(\s*["\']([^"\']+)["\']')
rows = []
for f in sorted(g.replace('\\', '/') for g in glob.glob('api/routers/*.py')):
    text = Path(f).read_text(encoding='utf-8')
    lines = text.split('\n')
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        deco = ' '.join(ast.get_source_segment(text, d) or '' for d in node.decorator_list)
        m = ROUTE.search(deco)
        if not m:
            continue
        method, path = m.group(1).upper(), m.group(2)
        params = re.findall(r'\{(\w+)\}', path)
        parent = next((p for p in params if p in PARENTS), None)
        others = [p for p in params if p.endswith('_id') and p != parent]
        if parent is None or not others or params.index(parent) > params.index(others[0]):
            continue
        body_start = node.body[0].lineno - 1
        body = '\n'.join(lines[body_start: node.end_lineno])
        body_wo_audit = re.sub(r'log_audit_action\((?:[^()]|\([^()]*\))*\)', '', body, flags=re.S)
        root = parent[:-3]
        uses = len(re.findall(rf'\b{parent}\b', body_wo_audit))
        if parent == 'org_id':
            uses += len(re.findall(r'\borganization_id\b', body_wo_audit))  # strict for organizations: only the identifier itself counts
        else:
            uses += len(re.findall(rf'\b{root}\w*', body_wo_audit))  # an already-resolved parent object (agent, workflow, ...) counts
        if uses == 0:
            rows.append((f, node.lineno, method, path, node.name, f'child object loaded by id with no use of the parent {parent} in the body'))
with OUT.open('w', newline='', encoding='utf-8') as fh:
    w = csv.writer(fh)
    w.writerow(['file', 'line', 'method', 'path', 'function', 'note'])
    w.writerows(rows)
print('candidates:', len(rows))
for r in rows:
    print(' ', r[2], r[3], '|', r[0], r[4], '|', r[5])
