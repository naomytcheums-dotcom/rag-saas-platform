"""Read-only static triage of the "lookups by identifier without an organization marker" candidates of the phase 0 audit (TEN-004).

For every candidate (same heuristic as the phase 0 report) it finds the enclosing function and walks the call graph upwards (depth 4):
  guarded            every path to an entry point crosses a function that mentions an organization/ownership check
  UNGUARDED_ENDPOINT some HTTP endpoint reaches it with no such marker in the endpoint itself
  TASK_TRUSTS_ID     a Celery task reaches it (the trust boundary is the broker)
  NO_CALLERS_FOUND   no caller found by name (dead code, dynamic dispatch, or a test-only helper)
A "guard marker" is textual (require_*, organization_id, user_id comparison, current_user ...): it proves a check is PRESENT in the caller, not that it is CORRECT.
Run from the repository root: python audit-reports/phase3-2026-10-12/triage_candidates.py
"""

import ast
import collections
import csv
import glob
import re
from pathlib import Path

MODELS = ['Document', 'DocumentChunk', 'Conversation', 'EvaluationDataset', 'EvaluationJob', 'EvaluationQuestion', 'Workflow', 'WorkflowRun', 'AgentRun',
          'Invoice', 'Credit', 'OrganizationAPIKey', 'Message', 'ConversationMessage']
GUARD = re.compile(r'require_\w+|organization_id|org_id|\.user_id\s*[!=]=|current_user|user\.id|_org_member|get_org|assert_org|check_org|tenant|owner_id|api_key|resolve_org')
CTX_MARKER = re.compile(r'organization_id|org_id|require_org|get_org|_org_|owner_id|user_id\s*==|current_user\.id|require_|check_org|assert_org|tenant')
OUT = Path(__file__).with_name('candidate_triage.csv')

files = [f.replace('\\', '/') for f in glob.glob('api/**/*.py', recursive=True)]
src = {f: Path(f).read_text(encoding='utf-8') for f in files}
trees, funcs, by_name = {}, [], collections.defaultdict(list)
for f, text in src.items():
    try:
        trees[f] = ast.parse(text)
    except SyntaxError:
        continue
    lines = text.split('\n')
    for node in ast.walk(trees[f]):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            seg = '\n'.join(lines[node.lineno - 1: node.end_lineno])
            deco = ' '.join(ast.get_source_segment(text, d) or '' for d in node.decorator_list)
            kind = 'endpoint' if re.search(r'router\.(get|post|put|patch|delete)|\b\w+\.(get|post|put|patch|delete)\(', deco) else ('task' if re.search(r'task|celery', deco, re.I) else 'function')
            info = dict(file=f, name=node.name, line=node.lineno, end=node.end_lineno, kind=kind, guarded=bool(GUARD.search(seg)))
            funcs.append(info)
            by_name[node.name].append(info)


def enclosing(f, line):
    best = None
    for i in funcs:
        if i['file'] == f and i['line'] <= line <= i['end'] and (best is None or i['line'] > best['line']):
            best = i
    return best


callers = collections.defaultdict(list)
for f, tree in trees.items():
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else None)
            if name and name in by_name:
                enc = enclosing(f, node.lineno)
                if enc:
                    callers[name].append(enc)

ORDER = ['guarded', 'DEPTH_LIMIT', 'NO_CALLERS_FOUND', 'TASK_TRUSTS_ID', 'UNGUARDED_ENDPOINT']


def verdict(info, depth=0, seen=frozenset()):
    key = (info['file'], info['name'], info['line'])
    if key in seen:
        return 'guarded', []
    seen = seen | {key}
    here = f"{info['file']}::{info['name']}"
    if info['kind'] == 'endpoint':
        return ('guarded' if info['guarded'] else 'UNGUARDED_ENDPOINT'), [here]
    if info['kind'] == 'task':
        return 'TASK_TRUSTS_ID', [here]
    if info['guarded'] and depth > 0:
        return 'guarded', [here]
    cs = [c for c in callers.get(info['name'], []) if (c['file'], c['name'], c['line']) != key]
    if not cs:
        return 'NO_CALLERS_FOUND', [here]
    if depth >= 4:
        return 'DEPTH_LIMIT', [here]
    worst, chain = 'guarded', []
    for c in cs:
        v, ch = verdict(c, depth + 1, seen)
        if ORDER.index(v) > ORDER.index(worst):
            worst, chain = v, ch
    return worst, [here] + chain


cands = []
for f, text in src.items():
    lines = text.split('\n')
    for i, l in enumerate(lines):
        for m in MODELS:
            if re.search(rf'\b{m}\.id\s*==|\bdb\.get\(\s*{m}\s*,|\.get\(\s*{m}\s*,', l):
                if not CTX_MARKER.search('\n'.join(lines[max(0, i - 8): i + 9])):
                    cands.append((f, i + 1, m))

rows = []
for f, line, m in cands:
    enc = enclosing(f, line)
    if not enc:
        rows.append((f, line, m, '?', 'NO_ENCLOSING_FUNCTION', ''))
        continue
    v, chain = verdict(enc)
    rows.append((f, line, m, enc['name'], v, ' <- '.join(chain)))
with OUT.open('w', newline='', encoding='utf-8') as fh:
    w = csv.writer(fh)
    w.writerow(['file', 'line', 'model', 'function', 'verdict', 'worst_chain_inner_to_outer'])
    w.writerows(rows)
print('candidates:', len(rows), dict(collections.Counter(r[4] for r in rows)))
for r in rows:
    if r[4] != 'guarded':
        print(' ', r[0], r[1], r[2], r[3], r[4], '|', r[5][:140])
