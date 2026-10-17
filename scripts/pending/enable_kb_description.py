"""Enables persistence of `POST /v1/knowledge-bases` -> `description`.

NOT applied automatically: it needs migration 0132 (workspaces.description) on the PRODUCTION
database (the assistant's attempt to run it was blocked by the safety
classifier, so it was deliberately left for the owner). Steps:

    python scripts/pending/enable_kb_description.py     # moves the migration into place + patches 3 files
    alembic upgrade head                                 # adds the nullable column (reversible: alembic downgrade -1)

Idempotent. Until it is run, `description` is accepted and echoed back but not stored.
"""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[2]
shutil.move(str(root / "scripts/pending/0132_workspace_description.py"), str(root / "api/alembic/versions/0132_workspace_description.py")) if (root / "scripts/pending/0132_workspace_description.py").exists() else None

p = root / "api/models/workspace.py"
s = p.read_text(encoding="utf-8")
if "description" not in s:
    s = s.replace("from sqlalchemy import DateTime, ForeignKey, String, func", "from sqlalchemy import DateTime, ForeignKey, String, Text, func", 1)
    s = s.replace('    name: Mapped[str] = mapped_column(String(200), nullable=False)\n', '    name: Mapped[str] = mapped_column(String(200), nullable=False)\n    description: Mapped[str | None] = mapped_column(Text, nullable=True)\n', 1)
    p.write_text(s, encoding="utf-8")

p = root / "api/services/public_api.py"
s = p.read_text(encoding="utf-8")
s = s.replace('Workspace(organization_id=key_row.organization_id, name=name, created_by=key_row.created_by)', 'Workspace(organization_id=key_row.organization_id, name=name, description=description, created_by=key_row.created_by)', 1)
s = s.replace('"name": w.name, "created_at": w.created_at}', '"name": w.name, "description": w.description, "created_at": w.created_at}', 1)
p.write_text(s, encoding="utf-8")

p = root / "api/routers/public_api.py"
s = p.read_text(encoding="utf-8")
s = s.replace("description=payload.description, created_at=workspace.created_at", "description=workspace.description, created_at=workspace.created_at", 1)
p.write_text(s, encoding="utf-8")
print("patched -- now run: alembic upgrade head")
