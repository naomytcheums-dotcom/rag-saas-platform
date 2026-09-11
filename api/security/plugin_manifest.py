"""
Partie 16 (ter) -- plugin manifest validation + static code scan.

Honest scope on "sandbox": no plugin RUNTIME exists anywhere in this
codebase (nothing here ever `eval`s, `exec`s, or otherwise executes
uploaded third-party code) -- so there is no real process to sandbox. A
genuine, safe execution sandbox (an isolated V8/WASM/Docker-per-plugin
runtime) is a real, separate engineering effort this pass does not
build, and faking one (e.g. a `try/except` around a real `exec()` call)
would be exactly the kind of fabricated completeness this project's
whole discipline exists to avoid. What IS real here: (1) strict
manifest schema + a fixed permission whitelist (same static-catalog
pattern as api/security/permission_catalog.py -- a plugin cannot
declare a permission this platform doesn't actually recognize), and
(2) a real static regex scan of the uploaded code for a fixed list of
dangerous call patterns, rejecting publication outright rather than
silently flagging -- the same class of real-but-simple pattern matching
api/services/security_scan.py's own secret scan already uses, not a
full taint-analysis tool.
"""

import re

MAX_PLUGIN_CODE_BYTES = 1 * 1024 * 1024  # 1 MB -- a plugin is UI glue/a small handler, not a bundled app
MAX_MANIFEST_NAME_LENGTH = 200
MAX_MANIFEST_DESCRIPTION_LENGTH = 2000

# Fixed, real whitelist -- same reasoning as permission_catalog.py's own
# top docstring: a permission this list doesn't name is not something
# any router actually checks for, so a manifest declaring one would be
# a permission that LOOKS granted but does nothing real.
ALLOWED_PLUGIN_PERMISSIONS: list[dict] = [
    {"id": "read_documents", "label": "Read this organization's documents"},
    {"id": "read_conversations", "label": "Read this organization's conversations"},
    {"id": "read_agents", "label": "Read this organization's agents"},
    {"id": "send_notifications", "label": "Send notifications on this organization's behalf"},
    {"id": "read_analytics", "label": "Read this organization's usage analytics"},
]
_ALLOWED_PERMISSION_IDS = {p["id"] for p in ALLOWED_PLUGIN_PERMISSIONS}

REQUIRED_MANIFEST_FIELDS = ("name", "version", "entry_point", "description", "permissions")

_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")  # real semver (major.minor.patch), no pre-release/build metadata needed here
_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,98}[a-z0-9]$")

# Real, simple forbidden-pattern scan -- flags the call shapes a plugin
# has no legitimate reason to use (arbitrary code execution, shelling
# out, raw filesystem/network escape hatches), across whichever
# language the entry_point implies (JS or Python are the only two this
# scan bothers with -- the only two entry_point extensions this
# manifest schema accepts, see validate_manifest below).
_FORBIDDEN_CODE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("eval() call", re.compile(r"\beval\s*\(")),
    ("Function constructor (JS eval-equivalent)", re.compile(r"\bnew\s+Function\s*\(")),
    ("exec() call", re.compile(r"\bexec\s*\(")),
    ("os.system() call", re.compile(r"\bos\.system\s*\(")),
    ("subprocess module usage", re.compile(r"\bsubprocess\.")),
    ("Node child_process usage", re.compile(r"require\(\s*['\"]child_process['\"]\s*\)")),
    ("Node raw filesystem access", re.compile(r"require\(\s*['\"]fs['\"]\s*\)")),
    ("Python raw filesystem access", re.compile(r"\b__import__\s*\(\s*['\"]os['\"]")),
]


class PluginManifestError(ValueError):
    pass


class PluginCodeSecurityError(ValueError):
    pass


def validate_manifest(manifest: dict, *, slug: str) -> None:
    """Raises PluginManifestError with a real, specific reason on any
    violation. Never mutates `manifest` -- the caller stores exactly
    what was submitted (minus nothing), so a later re-read reflects
    what was actually validated."""
    if not isinstance(manifest, dict):
        raise PluginManifestError("manifest.json must be a JSON object")

    missing = [field for field in REQUIRED_MANIFEST_FIELDS if field not in manifest]
    if missing:
        raise PluginManifestError(f"manifest.json is missing required field(s): {', '.join(missing)}")

    name = manifest["name"]
    if not isinstance(name, str) or not (1 <= len(name) <= MAX_MANIFEST_NAME_LENGTH):
        raise PluginManifestError(f"manifest 'name' must be a string of 1-{MAX_MANIFEST_NAME_LENGTH} characters")

    description = manifest["description"]
    if not isinstance(description, str) or not (1 <= len(description) <= MAX_MANIFEST_DESCRIPTION_LENGTH):
        raise PluginManifestError(f"manifest 'description' must be a string of 1-{MAX_MANIFEST_DESCRIPTION_LENGTH} characters")

    version = manifest["version"]
    if not isinstance(version, str) or not _VERSION_PATTERN.match(version):
        raise PluginManifestError("manifest 'version' must be real semver, e.g. '1.0.0'")

    entry_point = manifest["entry_point"]
    if not isinstance(entry_point, str) or not entry_point.endswith((".js", ".py")):
        raise PluginManifestError("manifest 'entry_point' must be a .js or .py filename -- the only two languages this platform's static scan covers")

    permissions = manifest["permissions"]
    if not isinstance(permissions, list) or not all(isinstance(p, str) for p in permissions):
        raise PluginManifestError("manifest 'permissions' must be a list of permission id strings")
    unknown = sorted(set(permissions) - _ALLOWED_PERMISSION_IDS)
    if unknown:
        raise PluginManifestError(f"manifest declares unknown permission(s): {', '.join(unknown)} -- allowed: {', '.join(sorted(_ALLOWED_PERMISSION_IDS))}")

    if not _SLUG_PATTERN.match(slug):
        raise PluginManifestError("plugin slug must be 3-100 lowercase alphanumeric characters or hyphens, not starting/ending with a hyphen")


def scan_plugin_code(content: bytes) -> None:
    """Raises PluginCodeSecurityError on the first forbidden pattern
    found. Real size limit enforced first (a real DoS-by-upload guard,
    same reasoning as api/services/storage.py's MAX_AVATAR_BYTES).
    Non-UTF-8 content (a real binary, not a JS/Python source file) is
    rejected outright -- a plugin's `entry_point` names a real
    .js/.py source file, so real plugin code is always real text."""
    if len(content) > MAX_PLUGIN_CODE_BYTES:
        raise PluginCodeSecurityError(f"plugin code exceeds the {MAX_PLUGIN_CODE_BYTES // 1024}KB limit")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise PluginCodeSecurityError("plugin code must be real UTF-8 text (a .js or .py source file), not binary content")

    for label, pattern in _FORBIDDEN_CODE_PATTERNS:
        if pattern.search(text):
            raise PluginCodeSecurityError(f"plugin code rejected -- contains a forbidden pattern: {label}")


def validate_rating(rating: int) -> None:
    if not isinstance(rating, int) or not (1 <= rating <= 5):
        raise PluginManifestError("rating must be an integer from 1 to 5")
