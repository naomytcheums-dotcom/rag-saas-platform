"""
Agentic layer: wraps the existing RAG pipeline and real external API calls
behind Claude's tool-use, so the assistant *decides* per question whether to
search the documentation, check GitHub for a known issue, escalate to a
human, log a gap for review, or answer neither and say so -- instead of
always running the same fixed retrieval step.

Four tools, chosen to stay inside this project's actual domain (a FastAPI
docs assistant that can also hand off what it can't resolve) rather than
bolting on unrelated demo tools:

- search_fastapi_docs      -- the existing hybrid retriever (src/retrieval.py).
- search_github_issues     -- a real, unauthenticated call to the GitHub
  Search API against fastapi/fastapi, for "is this a known bug?" questions
  that no amount of doc-searching can answer. Client pattern lifted from
  this same portfolio's `conduit` MCP server (slim response, read-only).
- escalate_to_human         -- books a real Google Calendar event (Phase 02,
  src/integrations.py) when neither of the above resolves an on-topic
  question, or the user explicitly asks for a person.
- log_question_for_review   -- appends a real row to a Google Sheet (Phase
  02) for questions that reveal a documentation gap, so a human can spot
  patterns later -- not called for every question, only notable ones.

The routing decision itself (which tool, or none) is made by the model via
Claude's tool-use, not by keyword rules here -- this file only executes
whatever the model asks for and feeds the result back.

Phase 03 (resilience) added two things that don't touch the tools above:
a retryable-vs-fatal split with exponential backoff around the Claude API
call itself (_call_model_with_retry), and schema validation of every tool
call the model makes before it's dispatched (_validate_tool_input) -- a
malformed call becomes a normal tool error fed back to the model instead
of an uncaught KeyError/TypeError crashing the run.

Phase 05 (observability, src/observability.py) needs a real cost number
per run, so run() now sums token usage across every API call in a
tool-use round-trip (not just the last one) and returns it -- logging
itself stays out of this file; record_run() wraps a call to run() from
the outside instead.
"""

import datetime as dt
import json
import logging
import os
import time

import anthropic
import httpx
from anthropic import Anthropic

from generation import CLIENT_TIMEOUT_SECONDS, MODEL_NAME, load_dotenv_if_present
from integrations import CalendarClient, SheetsClient
from retrieval import FINAL_TOP_K, Retriever

GITHUB_API = "https://api.github.com"
GITHUB_REPO = "fastapi/fastapi"
GITHUB_TIMEOUT_SECONDS = 10.0

# Escalations are booked at a fixed, deterministic offset from "now" --
# rounded to the next half hour -- rather than letting the model invent a
# timestamp, which it has no real basis (someone's actual availability) to
# pick correctly.
ESCALATION_LEAD_TIME_MINUTES = 60

MAX_TOOL_ITERATIONS = 4
AGENT_MAX_TOKENS = 1024

# Phase 03: resilience. Retry transient failures against the Claude API
# (rate limits, overload, momentary network issues) with exponential
# backoff; anything else (bad request, auth failure, ...) won't resolve by
# retrying, so it's raised immediately instead of wasting attempts on it.
MAX_API_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 1.0
RETRYABLE_STATUS_CODES = {429, 500, 503, 504, 529}

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = """You are a technical assistant for the FastAPI web framework. You have four tools:

- search_fastapi_docs: the official documentation. Use it for "how do I...", "what is...", or any question about FastAPI's features, parameters, or intended usage.
- search_github_issues: open issues on the fastapi/fastapi GitHub repo. Use it when the user asks whether something is a known bug, a known limitation, or an open feature request -- not for ordinary usage questions.
- escalate_to_human: books a real calendar slot with a person. Use only when the user explicitly asks to talk to a human, OR when search_fastapi_docs and search_github_issues have both been tried on a clearly on-topic question and neither resolved it. Never use it as a first response.
- log_question_for_review: records a question as a documentation gap for a human to review later. Use it only for questions you could not fully answer, or where the docs and GitHub issues gave conflicting or incomplete information -- not for questions you answered cleanly.

You may call a tool, call several if the question genuinely needs them, or call none and answer directly if the question is off-topic (not about FastAPI) -- in that case say plainly that you only answer FastAPI questions, don't guess.

When you do use a tool's results, cite them: documentation excerpts as [1], [2]... in the order given, GitHub issues by their number and a link. Never state a fact that isn't backed by a tool result or that isn't common, uncontroversial knowledge about how FastAPI itself works."""

TOOLS = [
    {
        "name": "search_fastapi_docs",
        "description": (
            "Search the official FastAPI documentation for content relevant to a question. "
            "Use for 'how do I...', 'what is...', or any question about FastAPI's features, "
            "APIs, or intended usage."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query, ideally close to the user's own wording.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_github_issues",
        "description": (
            "Search open issues on the fastapi/fastapi GitHub repository. Use when the user "
            "asks whether something is a known bug, a known limitation, or an open feature "
            "request -- not for general usage questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keywords to search for in issue titles and bodies.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Book a real calendar slot with a person. Use only when the user explicitly asks "
            "to talk to a human, or when both search tools have been tried on a clearly "
            "on-topic question and neither resolved it -- never as a first response."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "What the human needs to help with -- specific enough for them to prepare.",
                }
            },
            "required": ["reason"],
        },
    },
    {
        "name": "log_question_for_review",
        "description": (
            "Record a question as a documentation gap for later review. Use only for questions "
            "that could not be fully answered, or where sources gave conflicting or incomplete "
            "information -- not for questions that were answered cleanly."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["missing-docs", "unclear-docs", "known-bug", "unsupported-feature", "other"],
                    "description": "Why this question couldn't be cleanly answered.",
                },
                "answered": {
                    "type": "boolean",
                    "description": "Whether the user still got some form of answer, even an imperfect one.",
                },
            },
            "required": ["category", "answered"],
        },
    },
]


def _slim_issue(issue):
    """Only the fields worth spending an LLM's context on -- mirrors the
    same trim conduit's github_client.py does on the raw GitHub payload."""
    return {
        "number": issue["number"],
        "title": issue["title"],
        "state": issue["state"],
        "labels": [label["name"] for label in issue.get("labels", [])],
        "url": issue.get("html_url"),
    }


def search_github_issues(query, limit=5, http_client=None):
    """Real call to the GitHub Search API, unauthenticated (10 req/min limit
    -- fine for a demo; add a GITHUB_TOKEN header here first if this needs
    to run at any real volume). `http_client` is injectable for tests."""
    client = http_client or httpx
    params = {
        "q": f"repo:{GITHUB_REPO} is:issue in:title,body {query}",
        "per_page": limit,
    }
    try:
        response = client.get(
            f"{GITHUB_API}/search/issues",
            params=params,
            headers={"Accept": "application/vnd.github+json"},
            timeout=GITHUB_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise RuntimeError(f"GitHub issue search timed out after {GITHUB_TIMEOUT_SECONDS}s") from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"GitHub API returned an error (status {exc.response.status_code})") from exc
    except httpx.RequestError as exc:
        raise RuntimeError("Could not reach the GitHub API -- check network connectivity") from exc

    items = response.json().get("items", [])
    return [_slim_issue(item) for item in items if "pull_request" not in item]


def _next_escalation_slot():
    """Lead time from now, rounded up to the next clean half hour -- letting
    timedelta arithmetic handle any hour/day rollover rather than computing
    it by hand."""
    target = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=ESCALATION_LEAD_TIME_MINUTES)
    target = target.replace(second=0, microsecond=0)
    remainder = target.minute % 30
    if remainder:
        target += dt.timedelta(minutes=30 - remainder)
    return target


def _is_retryable(exc):
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code in RETRYABLE_STATUS_CODES
    return isinstance(exc, anthropic.APIConnectionError)  # also covers APITimeoutError, a subclass


TOOLS_BY_NAME = {tool["name"]: tool for tool in TOOLS}


def _validate_tool_input(name, tool_input):
    """Check the model's tool call against that tool's own declared schema
    before anything tries to use it -- a malformed call (missing field,
    wrong type, an enum value that doesn't exist) becomes a clear tool
    error fed back to the model instead of an uncaught KeyError/TypeError
    crashing the whole run."""
    schema = TOOLS_BY_NAME.get(name)
    if schema is None:
        raise ValueError(f"Unknown tool requested by the model: {name}")

    properties = schema["input_schema"].get("properties", {})
    required = schema["input_schema"].get("required", [])
    missing = [field for field in required if field not in tool_input]
    if missing:
        raise ValueError(f"Tool '{name}' call is missing required field(s): {', '.join(missing)}")

    type_checks = {"string": str, "boolean": bool, "number": (int, float), "integer": int}
    for field, value in tool_input.items():
        spec = properties.get(field)
        if spec is None:
            continue  # extra fields are ignored, not an error -- the model may be verbose
        expected_type = type_checks.get(spec.get("type"))
        if expected_type is not None and not isinstance(value, expected_type):
            raise ValueError(f"Tool '{name}' field '{field}' must be a {spec['type']}, got {type(value).__name__}")
        if "enum" in spec and value not in spec["enum"]:
            raise ValueError(f"Tool '{name}' field '{field}' must be one of {spec['enum']}, got {value!r}")


class Agent:
    def __init__(self, client=None, calendar_client=None, sheets_client=None, sleep_fn=time.sleep):
        if client is not None:
            self.client = client
        else:
            load_dotenv_if_present()
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise EnvironmentError(
                    "ANTHROPIC_API_KEY is not set. Get a key from https://console.anthropic.com/ "
                    "and either export it in your shell or put it in a .env file at the project "
                    "root as ANTHROPIC_API_KEY=sk-ant-..."
                )
            self.client = Anthropic(api_key=api_key, timeout=CLIENT_TIMEOUT_SECONDS)
        self._retriever = None
        self._calendar_client = calendar_client
        self._sheets_client = sheets_client
        self._sleep = sleep_fn

    def _get_retriever(self):
        if self._retriever is None:
            self._retriever = Retriever()
        return self._retriever

    def _get_calendar_client(self):
        if self._calendar_client is None:
            self._calendar_client = CalendarClient()
        return self._calendar_client

    def _get_sheets_client(self):
        if self._sheets_client is None:
            self._sheets_client = SheetsClient()
        return self._sheets_client

    def _execute_tool(self, name, tool_input, question):
        if name == "search_fastapi_docs":
            chunks = self._get_retriever().retrieve(tool_input["query"], top_k=FINAL_TOP_K)
            sources = [
                {"index": i, "path": c["path"], "heading": c["heading"] or c["doc_title"]}
                for i, c in enumerate(chunks, start=1)
            ]
            result = [{"index": s["index"], "source": s["path"], "text": c["text"]} for s, c in zip(sources, chunks)]
            return result, sources
        if name == "search_github_issues":
            issues = search_github_issues(tool_input["query"])
            return issues, []
        if name == "escalate_to_human":
            booking = self._get_calendar_client().book_escalation(tool_input["reason"], _next_escalation_slot())
            return booking, []
        if name == "log_question_for_review":
            logged = self._get_sheets_client().log_question(question, tool_input["category"], tool_input["answered"])
            return logged, []
        raise ValueError(f"Unknown tool requested by the model: {name}")

    def _call_model_with_retry(self, messages):
        delay = RETRY_BASE_DELAY_SECONDS
        for attempt in range(1, MAX_API_RETRIES + 1):
            try:
                return self.client.messages.create(
                    model=MODEL_NAME,
                    max_tokens=AGENT_MAX_TOKENS,
                    system=AGENT_SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=messages,
                )
            except anthropic.APIError as exc:
                status = getattr(exc, "status_code", None)
                if not _is_retryable(exc) or attempt == MAX_API_RETRIES:
                    detail = f" (status {status})" if status else ""
                    raise RuntimeError(f"Claude API call failed{detail}: {exc.message}") from exc
                logger.warning(
                    "Anthropic call failed (attempt %d/%d, status %s): %s -- retrying in %.1fs",
                    attempt, MAX_API_RETRIES, status, exc.message, delay,
                )
                self._sleep(delay)
                delay *= 2

    def run(self, question, max_tool_iterations=MAX_TOOL_ITERATIONS):
        messages = [{"role": "user", "content": question}]
        tools_used = []
        sources = []
        input_tokens = 0
        output_tokens = 0
        start = time.perf_counter()

        for _ in range(max_tool_iterations):
            response = self._call_model_with_retry(messages)
            messages.append({"role": "assistant", "content": response.content})
            # A tool-use round-trip is 2+ API calls; total usage across all
            # of them is what actually costs money, not just the last one.
            input_tokens += response.usage.input_tokens
            output_tokens += response.usage.output_tokens

            if response.stop_reason != "tool_use":
                answer_text = "".join(block.text for block in response.content if block.type == "text")
                return {
                    "answer": answer_text,
                    "tools_used": tools_used,
                    "sources": sources,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "elapsed_ms": round((time.perf_counter() - start) * 1000),
                }

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                tools_used.append(block.name)
                try:
                    _validate_tool_input(block.name, block.input)
                    result, new_sources = self._execute_tool(block.name, block.input, question)
                    sources.extend(new_sources)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })
                except (RuntimeError, ValueError) as exc:
                    logger.warning("tool %s failed: %s", block.name, exc)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(exc),
                        "is_error": True,
                    })
            messages.append({"role": "user", "content": tool_results})

        raise RuntimeError(
            f"Agent did not reach a final answer within {max_tool_iterations} tool-use rounds "
            "(possible tool-call loop)"
        )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Ask the Nova agentic assistant a question.")
    parser.add_argument("question")
    args = parser.parse_args()

    try:
        agent = Agent()
        result = agent.run(args.question)
    except (RuntimeError, EnvironmentError, anthropic.APIError) as exc:
        raise SystemExit(f"Agent run failed: {exc}")

    print(f"\nQuestion: {args.question}\n")
    print(result["answer"])
    if result["tools_used"]:
        print(f"\nTools used: {', '.join(result['tools_used'])}")
    if result["sources"]:
        print("\nSources:")
        for s in result["sources"]:
            print(f"  [{s['index']}] {s['path']} -- {s['heading']}")
    print(f"\n{result['elapsed_ms']}ms")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    main()
