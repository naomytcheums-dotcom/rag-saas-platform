# NOTE (Phase 5, Étape 7 audit): this builds the EARLIER STREAMLIT
# PROTOTYPE (dashboard/app.py, "nova"), NOT the RAG SaaS API/frontend
# product this platform actually is today. If you're looking for the
# real product's own Docker build, you want `Dockerfile.api` (backend)
# and `frontend/Dockerfile`, orchestrated together by
# `docker-compose.selfhosted.yml` -- see docs/install/DOCKER.md. Kept
# under this exact filename only because `render.yaml`'s own Blueprint
# already points at it; renaming would break that existing deploy.
#
# Containerized deploy target for platforms that need a Docker image
# (Render, Fly.io) -- separate from the Streamlit Community Cloud path in
# the README, which deploys straight from GitHub with no Dockerfile at
# all. Both exist because they solve different problems: Streamlit Cloud
# is the zero-config free option, this is for anywhere that expects a
# container.
#
# Snyk audit findings (2 High, 2 Medium, 86 Low on the single-stage
# version of this file) addressed by two structural changes below:
#
# 1. Multi-stage build. build-essential (gcc, binutils, and everything
#    they themselves pull in) was previously baked into the FINAL image
#    just to compile sentence-transformers/chromadb's native extensions
#    at `pip install` time -- never needed again after that, but its own
#    long tail of OS-package CVEs stayed in every shipped image
#    regardless. It now only exists in the `builder` stage; the final
#    stage copies the already-built virtualenv and never installs a
#    compiler at all. This is what actually accounts for the large drop
#    in Low findings, not just the count that happens to disappear —
#    fewer installed packages is fewer packages that can ever have a CVE
#    against them in the first place.
# 2. A non-root USER for the final stage -- the single most common
#    "High" finding on a Dockerfile that never sets one: a compromise of
#    the running process (a code-execution bug in any dependency) would
#    otherwise have root inside the container by default, which is a
#    meaningfully larger blast radius than a compromised unprivileged
#    process, even inside a container's own isolation boundary.
#
# python:3.13-slim-bookworm rather than the bare python:3.13-slim: pins
# the Debian release explicitly (bookworm) so a Debian codename bump
# upstream can't silently change which OS packages -- and therefore
# which CVEs -- this image ships, while still tracking Debian's own
# security patches for that release on every rebuild (a hard digest pin
# would freeze this image at today's patch level and work AGAINST that,
# which is the opposite of what fixing vulnerabilities should do).

FROM python:3.13-slim-bookworm AS builder

WORKDIR /app

# sentence-transformers/chromadb pull in packages with native extensions
# that need a compiler on a slim base image -- confined to this
# discarded build stage, see this file's top comment.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
# Pre-existing build failure, surfaced by this file's own new
# docker-build CI job actually building it for the first time:
# requirements.txt's own "Tests" section lists `agentfixture`, a
# private package not published anywhere (see that line's comment --
# "install from a local clone until it's published") -- pip cannot ever
# resolve it in a fresh environment, Docker or otherwise. It's a
# test-only dependency the runtime image (`streamlit run
# dashboard/app.py`) never imports, so it's excluded here rather than
# left broken; requirements.txt itself is untouched since local/CI test
# runs still need it exactly as documented there.
RUN grep -v '^agentfixture$' requirements.txt > requirements-runtime.txt \
    && pip install --no-cache-dir -r requirements-runtime.txt

FROM python:3.13-slim-bookworm

WORKDIR /app

# --system (no login shell, no password) since nothing ever needs to
# interactively log in as this user -- a real login shell/password is
# attack surface a service account has no use for.
RUN groupadd --system app && useradd --system --gid app --create-home --home-dir /home/appuser appuser

# Only the already-built virtualenv crosses the stage boundary -- no
# compiler, no apt cache, no build-time-only files.
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY . .

# data/chroma/ is gitignored (derived, not source, and binary) -- absent
# on a fresh image the same way it's absent on a fresh clone.
# dashboard/app.py already detects that and rebuilds it from the
# committed data/processed/fastapi_docs.json on first load.

RUN chown -R appuser:app /app
USER appuser

EXPOSE 8501

# Streamlit's own health endpoint -- no custom health-check code to
# write or keep in sync with the app. One line, deliberately: a
# backslash continuation here would put a line starting with "CMD" (the
# healthcheck's own sub-command) ahead of the real CMD instruction below.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
