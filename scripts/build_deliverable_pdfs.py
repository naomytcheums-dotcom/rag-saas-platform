"""Spec 14.2.1-14.2.6 / 14.2.8: build the delivery PDFs from the Markdown documentation of the repository.

    python scripts/build_deliverable_pdfs.py            # writes deliverables/*.pdf

Markdown is converted by a small built-in converter (headings, paragraphs, lists, tables, code blocks, bold / italic / inline code / links) and printed to
PDF with the headless Chrome or Edge installed on the machine (`CHROME_BIN` overrides the lookup). No Python dependency is added. The PDFs are exports of
the existing documents: they say exactly what the sources say, including their stated limits.
"""

import csv
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "deliverables"

_CSS = """
body{font-family:Segoe UI,Arial,sans-serif;font-size:11pt;line-height:1.45;color:#1a1a1a;margin:0}
h1{font-size:22pt;border-bottom:2px solid #222;padding-bottom:4pt;margin-top:26pt}
h2{font-size:16pt;margin-top:20pt;border-bottom:1px solid #bbb} h3{font-size:13pt;margin-top:14pt}
code{background:#f1f1f1;padding:1px 3px;border-radius:3px;font-size:9.5pt}
pre{background:#f6f6f6;border:1px solid #ddd;padding:8pt;overflow-wrap:anywhere;white-space:pre-wrap;font-size:8.5pt}
table{border-collapse:collapse;width:100%;font-size:9pt;margin:8pt 0} th,td{border:1px solid #bbb;padding:3pt 5pt;vertical-align:top;text-align:left} th{background:#eee}
.cover{page-break-after:always;text-align:center;padding-top:200pt} .cover h1{border:0;font-size:30pt}
.part{page-break-before:always}
"""


def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\w)", r"<em>\1</em>", text)
    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', text)


def markdown_to_html(source: str) -> str:
    """Convert the Markdown subset used in docs/ to HTML."""
    out: list[str] = []
    lines = source.replace("\r\n", "\n").split("\n")
    i = 0
    list_kind: str | None = None

    def close_list():
        nonlocal list_kind
        if list_kind:
            out.append(f"</{list_kind}>")
            list_kind = None

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            close_list()
            block = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            out.append("<pre>" + html.escape("\n".join(block)) + "</pre>")
        elif re.match(r"^\s*\|.*\|\s*$", line) and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1]):
            close_list()
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            out.append("<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in header) + "</tr></thead><tbody>")
            i += 2
            while i < len(lines) and re.match(r"^\s*\|.*\|\s*$", lines[i]):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue
        elif m := re.match(r"^(#{1,6})\s+(.*)$", line):
            close_list()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
        elif m := re.match(r"^\s*([-*+])\s+(.*)$", line):
            if list_kind != "ul":
                close_list()
                out.append("<ul>")
                list_kind = "ul"
            out.append(f"<li>{_inline(m.group(2))}</li>")
        elif m := re.match(r"^\s*\d+[.)]\s+(.*)$", line):
            if list_kind != "ol":
                close_list()
                out.append("<ol>")
                list_kind = "ol"
            out.append(f"<li>{_inline(m.group(1))}</li>")
        elif not line.strip():
            close_list()
        else:
            close_list()
            paragraph = [line]
            while i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r"^(#{1,6}\s|\s*[-*+]\s|\s*\d+[.)]\s|\s*\||```)", lines[i + 1]):
                i += 1
                paragraph.append(lines[i])
            out.append("<p>" + _inline(" ".join(p.strip() for p in paragraph)) + "</p>")
        i += 1
    close_list()
    return "\n".join(out)


def csv_to_markdown_table(path: Path, columns: list[str]) -> str:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    for row in rows:
        lines.append("| " + " | ".join((row.get(c, "") or "").replace("|", "/").replace("\n", " ")[:160] for c in columns) + " |")
    return "\n".join(lines)


def _read(rel: str) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else f"*(source file `{rel}` not found when this PDF was built)*"


def _find_browser() -> str:
    candidates = [os.environ.get("CHROME_BIN", ""), shutil.which("chrome") or "", shutil.which("google-chrome") or "", shutil.which("chromium") or "", shutil.which("msedge") or "",
                  r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise SystemExit("No Chrome / Edge found: set CHROME_BIN to a Chromium-based browser")


def build_pdf(title: str, parts: list[tuple[str, str]], target: Path, browser: str) -> None:
    body = [f'<div class="cover"><h1>{html.escape(title)}</h1><p>RAG SaaS Platform</p></div>']
    for heading, markdown in parts:
        body.append(f'<div class="part"><h1>{html.escape(heading)}</h1>{markdown_to_html(markdown)}</div>')
    document = f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title><style>{_CSS}</style></head><body>{"".join(body)}</body></html>'
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "doc.html"
        source.write_text(document, encoding="utf-8")
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={target}", source.as_uri()],
            check=True, capture_output=True, timeout=180,
        )


def documents() -> dict[str, tuple[str, list[tuple[str, str]]]]:
    feature_csv = ROOT / "audit-reports" / "functional-audit-2026-10-10" / "01-feature-verification.csv"
    features = csv_to_markdown_table(feature_csv, ["feature_id", "feature_name", "declared_status", "verified_status", "known_gaps"]) if feature_csv.exists() else "*(feature table not found)*"
    return {
        "architecture.pdf": ("Architecture", [("Overview", _read("ARCHITECTURE.md")), ("Platform architecture", _read("docs/architecture/OVERVIEW.md")), ("Data flow", _read("docs/architecture/DATA_FLOW.md"))]),
        "feature-list.pdf": ("Feature list and verified status", [("Verification summary", _read("audit-reports/functional-audit-2026-10-10/00-executive-summary.md")), ("All 514 features", features)]),
        "deployment-guide.pdf": ("Deployment guide", [("Deployment guide", _read("docs/DEPLOYMENT_GUIDE.md")), ("Deployment targets", _read("deploy/README.md")), ("Render", _read("docs/deployment/RENDER.md")), ("Background worker", _read("docs/deployment/WORKER.md"))]),
        "api-documentation.pdf": ("API documentation", [(name, _read(f"docs/api/{name}.md")) for name in ("OVERVIEW", "AUTHENTICATION", "CHAT", "DOCUMENTS", "AGENTS", "WEBHOOKS", "RATE_LIMITS", "ERRORS")]),
        "security-audit.pdf": ("Security audit", [("Security report", _read("docs/SECURITY_REPORT.md")), ("Security architecture", _read("docs/architecture/SECURITY.md")), ("Radiography - executive summary", _read("audit-reports/radiographie-2026-10-10/00_SYNTHESE_EXECUTIVE.md")), ("Radiography - risks", _read("audit-reports/radiographie-2026-10-10/12_DETTES_RISQUES_BLOQUANTS.md"))]),
        "benchmark-report.pdf": ("Benchmark report", [("Performance report", _read("docs/PERFORMANCE_REPORT.md")), ("Limits", "No retrieval-quality baseline (Recall@K, MRR, NDCG) has been produced on a real dataset yet; the numbers above, if any, are performance measurements, not answer-quality measurements.")]),
        "setup-guide.pdf": ("Setup guide", [(name, _read(f"docs/install/{name}.md")) for name in ("SYSTEM_REQUIREMENTS", "SELF_HOSTED", "SSL_AND_DOMAINS", "UPGRADING", "SCALING", "TROUBLESHOOTING", "UNINSTALL")]),
    }


def main() -> int:
    browser = _find_browser()
    only = set(sys.argv[1:])
    for name, (title, parts) in documents().items():
        if only and name not in only:
            continue
        build_pdf(title, parts, OUT / name, browser)
        print(f"wrote {OUT / name} ({(OUT / name).stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
