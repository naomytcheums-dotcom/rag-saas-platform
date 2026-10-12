"""Contract on the Alembic revision chain (phase 4 of the 2026-10-12 security audit, MIG-003).

Two branches each had a migration numbered 0137 with the same parent 0136 (`0137_evaluation_split` and `0137_tenant_rls_policies_pilot`): merging them would have
produced a duplicate revision id and two heads, found only by hand. This reads the migration files (no database) and fails as soon as such a state is on a branch,
so the CI of a merge candidate catches it. Existing migrations are never modified: the fix for a collision is to renumber the NEWER, unmerged file.
"""

import re
from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "api" / "alembic" / "versions"
_REVISION = re.compile(r'^revision(?::\s*str)?\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
_DOWN = re.compile(r'^down_revision(?::[^=]+)?\s*=\s*(.+)$', re.MULTILINE)


def chain_problems(files: dict[str, str]) -> list[str]:
    """`files` maps a migration file name to its source. Returns a readable list of everything that would break `alembic upgrade head`."""
    problems, revisions, parents = [], {}, {}
    for name, text in sorted(files.items()):
        found = _REVISION.search(text)
        if not found:
            problems.append(f"{name}: no revision id")
            continue
        revision = found.group(1)
        if revision != name.split("_", 1)[0]:
            problems.append(f"{name}: the file number is not the revision id ({revision})")
        if revision in revisions:
            problems.append(f"duplicate revision id {revision}: {revisions[revision]} and {name}")
        revisions[revision] = name
        down = _DOWN.search(text)
        raw = down.group(1).strip() if down else "None"
        parents[revision] = [] if raw == "None" else re.findall(r'["\']([^"\']+)["\']', raw)
        if "def downgrade" not in text:
            problems.append(f"{name}: no downgrade()")
    children: dict[str, list[str]] = {}
    for revision, parent_ids in parents.items():
        for parent in parent_ids:
            if parent not in revisions:
                problems.append(f"{revisions[revision]}: parent {parent} does not exist")
            children.setdefault(parent, []).append(revision)
    for parent, kids in children.items():
        if len(kids) > 1:
            problems.append(f"fork: {parent} has several children {sorted(kids)}")
    heads = sorted(revision for revision in revisions if revision not in children)
    if len(heads) != 1:
        problems.append(f"expected exactly one head, found {heads}")
    roots = sorted(revision for revision, parent_ids in parents.items() if not parent_ids)
    if len(roots) != 1:
        problems.append(f"expected exactly one root, found {roots}")
    return problems


def _migration(revision: str, parent: str | None, name_suffix: str = "x") -> tuple[str, str]:
    return f"{revision}_{name_suffix}.py", f'revision: str = "{revision}"\ndown_revision: str | None = {parent!r}\n\ndef downgrade():\n    pass\n'.replace("'", '"')


def test_the_real_migration_chain_is_one_linear_chain_with_unique_ids():
    files = {path.name: path.read_text(encoding="utf-8") for path in VERSIONS.glob("*.py")}
    assert len(files) > 100, "the migration files were not found"
    assert chain_problems(files) == []


def test_a_collision_like_0137_is_detected():
    chain = dict([_migration("0001", None), _migration("0136", "0001"), _migration("0137", "0136", "evaluation_split")])
    assert chain_problems(chain) == []
    chain["0137_tenant_rls_policies_pilot.py"] = _migration("0137", "0136", "tenant_rls_policies_pilot")[1]
    problems = chain_problems(chain)
    assert any("duplicate revision id 0137" in p for p in problems)


def test_two_heads_a_missing_parent_a_wrong_file_number_and_a_missing_downgrade_are_detected():
    base = dict([_migration("0001", None), _migration("0002", "0001")])
    two_heads = {**base, **dict([_migration("0003", "0002", "a"), _migration("0004", "0002", "b")])}
    assert any("exactly one head" in p for p in chain_problems(two_heads))
    assert any("does not exist" in p for p in chain_problems({**base, **dict([_migration("0003", "0099")])}))
    assert any("file number" in p for p in chain_problems({**base, "0009_wrong.py": _migration("0003", "0002")[1]}))
    assert any("no downgrade" in p for p in chain_problems({**base, "0003_x.py": 'revision: str = "0003"\ndown_revision: str | None = "0002"\n'}))
