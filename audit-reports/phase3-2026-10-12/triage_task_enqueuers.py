"""Read-only static triage of the functions that put Celery tasks on the queue (phase 3, TEN-005).

For every function that calls `.delay()` / `.apply_async()` and carries no organization/ownership marker itself, walk the call graph upwards (depth 5)
and report whether every path to an HTTP endpoint crosses a guarded function, or ends in a task / a scheduler / nowhere.
Textual markers prove a check is PRESENT, not that it is CORRECT. Run from the repository root:
    python audit-reports/phase3-2026-10-12/triage_task_enqueuers.py
"""

import ast
import collections
import csv
import glob
import re
from pathlib import Path

GUARD = re.compile(r'require_\w+|organization_id|org_id|\.user_id\s*[!=]=|current_user|user\.id|_org_member|get_org|assert_org|check_org|tenant|owner_id|api_key|resolve_org')
OUT = Path(__file__).with_name('task_enqueuer_triage.csv')

funcs, by_name, src = [], collections.defaultdict(list), {}
for f in sorted(g.replace('\\', '/') for g in glob.glob('api/**/*.py', recursive=True)):
    text = Path(f).read_text(encoding='utf-8')
    try:
        tree = ast.parse(text)
    except SyntaxError:
        continue
    src[f] = (text, tree)
    lines = text.split('\n')
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            seg = '\n'.join(lines[node.lineno - 1: node.end_lineno])
            deco = ' '.join(ast.get_source_segment(text, d) or '' for d in node.decorator_list)
            kind = 'endpoint' if re.search(r'router\.(get|post|put|patch|delete)', deco) else ('task' if re.search(r'task|celery', deco, re.I) else 'function')
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
enqueuers = []
for f, (text, tree) in src.items():
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else None)
            enc = enclosing(f, node.lineno)
            if not enc:
                continue
            if name in by_name:
                callers[name].append(enc)
            if isinstance(fn, ast.Attribute) and fn.attr in ('delay', 'apply_async') and enc['kind'] != 'endpoint' and not enc['guarded']:
                enqueuers.append(enc)

ORDER = ['guarded', 'DEPTH_LIMIT', 'NO_CALLERS_FOUND', 'TASK_OR_SCHEDULER', 'UNGUARDED_ENDPOINT']


def verdict(info, depth=0, seen=frozenset()):
    key = (info['file'], info['name'], info['line'])
    if key in seen:
        return 'guarded', []
    seen = seen | {key}
    here = f"{info['file']}::{info['name']}"
    if info['kind'] == 'endpoint':
        return ('guarded' if info['guarded'] else 'UNGUARDED_ENDPOINT'), [here]
    if info['kind'] == 'task':
        return 'TASK_OR_SCHEDULER', [here]
    if info['guarded'] and depth > 0:
        return 'guarded', [here]
    cs = [c for c in callers.get(info['name'], []) if (c['file'], c['name'], c['line']) != key]
    if not cs:
        return 'NO_CALLERS_FOUND', [here]
    if depth >= 5:
        return 'DEPTH_LIMIT', [here]
    worst, chain = 'guarded', []
    for c in cs:
        v, ch = verdict(c, depth + 1, seen)
        if ORDER.index(v) > ORDER.index(worst):
            worst, chain = v, ch
    return worst, [here] + chain


rows, seen_keys = [], set()
for e in enqueuers:
    k = (e['file'], e['name'])
    if k in seen_keys:
        continue
    seen_keys.add(k)
    v, chain = verdict(e)
    rows.append((e['file'], e['name'], v, ' <- '.join(chain)))
with OUT.open('w', newline='', encoding='utf-8') as fh:
    w = csv.writer(fh)
    w.writerow(['file', 'enqueuing_function', 'verdict', 'worst_chain_inner_to_outer'])
    w.writerows(rows)
print('enqueuing functions without their own marker:', len(rows), dict(collections.Counter(r[2] for r in rows)))
for r in rows:
    print(f"  {r[2]:18} {r[0]}::{r[1]}  | {r[3][:150]}")
