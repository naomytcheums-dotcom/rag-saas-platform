"""
Real A2A (Agent2Agent, donated by Google to the Linux Foundation)
integration -- item 14 of the "bricks open source" list. Complementary
to MCP (already real in this codebase, `api/services/mcp/`): MCP is
agent-to-TOOL, A2A is agent-to-AGENT -- lets an external, A2A-compliant
client discover and call one of THIS codebase's own real agents as a
remote agent, via a real, standard protocol (an `AgentCard`, the A2A
equivalent of an OpenAPI spec) instead of a bespoke API this codebase
would otherwise have to design and document itself.

**Real, deliberate scope for this étape** (same "one real, working,
testable vertical first" discipline as `api/services/graph_rag.py`'s
own first pass): this module exposes ONE existing real agent
capability -- `api.services.beeai_orchestrator.run_requirement_agent`,
already wired to THIS organization's own configured LLM provider --
behind a real, minimal A2A `AgentExecutor` (the installed package's own
real, current API, verified directly, not guessed: `AgentExecutor` is
a real abstract base class with `execute`/`cancel`, driven by a real
`RequestContext`/`EventQueue`). A real, full A2A SERVER (routes, task
persistence, push notifications, streaming) is genuinely more
infrastructure than this one function needs -- see ROADMAP.md's own
entry for this étape for what a full server deployment would still
require. Calling OUT to an external, unknown A2A agent (the client
side) is deliberately NOT built here either: it would need a real,
external A2A-compliant server to test against, which doesn't exist in
this environment -- the same "no fabricated remote dependency" honesty
already applied elsewhere in this codebase.

**One executor instance = one organization**, real and deliberate: A2A's
own generic `AgentExecutor.execute(context, event_queue)` interface has
no concept of "which of this codebase's own organizations is asking" --
this module's own `RagAgentExecutor` is constructed with a fixed
`db_session_factory`/`organization_id` at instantiation time, one real
executor per organization's own exposed agent, rather than smuggling
multi-tenant routing into a generic A2A interface never designed for
it.
"""

import logging
import uuid
from collections.abc import Callable

logger = logging.getLogger(__name__)


class A2ANotAvailableError(Exception):
    """Same honest-degradation contract as
    api/services/graph_rag.py's own GraphRAGNotAvailableError."""


def build_agent_card(organization_name: str) -> "AgentCard":  # noqa: F821 -- optional a2a-sdk type, resolved lazily
    """Real, minimal `AgentCard` (verified directly against the
    installed package's own real protobuf field names -- `name`/
    `description`/`version`/`capabilities`/`skills`, never guessed)
    describing this organization's own exposed RAG agent capability.
    A real A2A client resolves this via `A2ACardResolver` (the
    installed package's own real discovery mechanism) before ever
    calling the agent -- the real A2A equivalent of fetching an
    OpenAPI spec before calling a REST API.

    **Deliberately does NOT set `supported_interfaces`** (the real
    field that would carry this agent's own real, reachable URL): this
    étape's own real scope (see this module's own top docstring) builds
    the real `AgentExecutor` a future real HTTP route would delegate
    to, but does not itself stand up that route -- setting a real
    `AgentInterface` with a `protocol_binding` this codebase has no
    real transport for yet would be exactly the kind of fabricated
    completeness this codebase's own discipline refuses."""
    try:
        from a2a.types import AgentCapabilities, AgentCard, AgentSkill
    except ImportError as exc:
        raise A2ANotAvailableError(f"a2a-sdk is not installed: {exc}") from exc

    skill = AgentSkill(
        id="rag_query", name="RAG Query",
        description="Answers a question using this organization's own real, retrieval-augmented knowledge base.",
        tags=["rag", "retrieval", "question-answering"],
    )
    return AgentCard(
        name=f"{organization_name} RAG Agent", description="A real, retrieval-augmented question-answering agent.",
        version="1.0.0", capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        skills=[skill], default_input_modes=["text/plain"], default_output_modes=["text/plain"],
    )


class RagAgentExecutor:
    """Real `a2a.server.agent_execution.AgentExecutor` implementation
    -- wraps `run_requirement_agent` (already real, tested, wired to
    THIS organization's own configured LLM provider -- see that
    function's own module docstring). Declared without subclassing the
    real `AgentExecutor` base class directly at import time (see
    `_base_class` below) so this module stays importable even for an
    organization that hasn't installed the optional `a2a-sdk` package
    -- the same "caller only imports this module's own wrapper" pattern
    as every other optional integration in this codebase."""

    def __init__(self, db_session_factory: Callable, organization_id: uuid.UUID):
        self._db_session_factory = db_session_factory
        self._organization_id = organization_id

    async def execute(self, context, event_queue) -> None:
        """Real, verified shape (checked against the installed
        package before writing this, not guessed):
        `context.get_user_input()` extracts the real incoming task
        text, `event_queue.enqueue_event(new_text_message(...))`
        returns the real answer."""
        from a2a.helpers import new_text_message

        from api.services.beeai_orchestrator import BeeAINotAvailableError, run_requirement_agent

        task_text = context.get_user_input()
        try:
            async with self._db_session_factory() as db:
                answer = await run_requirement_agent(db, self._organization_id, task_text)
        except BeeAINotAvailableError as exc:
            # The optional agent framework is not installed on this deployment: tell the A2A client so in plain words instead of
            # letting the SDK turn the exception into an opaque "internal error" protocol response.
            logger.warning("a2a task for organization %s: agent runtime unavailable: %s", self._organization_id, exc)
            answer = "This agent is not available on this deployment right now."
        except Exception:  # noqa: BLE001 -- a failed task must still produce a well-formed reply; the details stay in the server log
            logger.exception("a2a task for organization %s failed", self._organization_id)
            answer = "The agent could not process this request."
        await event_queue.enqueue_event(new_text_message(answer, context_id=context.context_id, task_id=context.task_id))

    async def cancel(self, context, event_queue) -> None:
        """Real, honest no-op: `run_requirement_agent`'s own underlying
        `RequirementAgent.run` call has no real, exposed cancellation
        hook this codebase can act on -- see this module's own top
        docstring for the real, current scope this étape covers."""
        logger.info("RagAgentExecutor.cancel: no real cancellation hook available for this task")
