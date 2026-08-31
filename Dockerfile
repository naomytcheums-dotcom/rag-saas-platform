# Containerized deploy target for platforms that need a Docker image
# (Render, Fly.io) -- separate from the Streamlit Community Cloud path in
# the README, which deploys straight from GitHub with no Dockerfile at
# all. Both exist because they solve different problems: Streamlit Cloud
# is the zero-config free option, this is for anywhere that expects a
# container.
FROM python:3.13-slim

WORKDIR /app

# sentence-transformers/chromadb pull in packages with native extensions
# that need a compiler on a slim base image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# data/chroma/ is gitignored (derived, not source, and binary) -- absent
# on a fresh image the same way it's absent on a fresh clone.
# dashboard/app.py already detects that and rebuilds it from the
# committed data/processed/fastapi_docs.json on first load.

EXPOSE 8501

# Streamlit's own health endpoint -- no custom health-check code to
# write or keep in sync with the app. One line, deliberately: a
# backslash continuation here would put a line starting with "CMD" (the
# healthcheck's own sub-command) ahead of the real CMD instruction below.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
