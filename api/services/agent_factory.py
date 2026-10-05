"""
Hardening Mission (§14) -- Factory: turn a plain-language REQUIREMENT into a
real, validated, optionally pre-evaluated RAG agent.

    requirement -> blueprint (configuration + rationale)
                -> validation against the platform's REAL validators/registries
                -> deployment through the REAL `create_agent`
                -> optional evaluation on a dataset -> go / hold-back decision

Not a decorative JSON generator: every field of the blueprint is something the
real code reads (`Agent` columns, `knowledge_base_config` consumed by the Eval
Lab, tool names that exist in the real agent tool catalog) and `validate_blueprint`
runs the SAME validators `create_agent`/the MCP tools use, so a blueprint that
validates can be created and one that cannot is rejected with every problem
listed, before anything is written.

The blueprint is built by explicit, inspectable RULES (keyword profiles, EN +
FR) rather than an LLM call: it is deterministic, free, works offline, and every
decision carries its `rationale`. A profile is a starting point to be measured,
not a claim of optimality -- the optional evaluation step and the retrieval
Evolution Engine exist precisely to check and improve it.
"""

import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession


class FactoryError(ValueError):
    """Raised with ALL validation problems at once (`problems`)."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


# (profile, keywords, retrieval config, agent overrides, rationale) -- first match wins, in order.
_PROFILES: list[tuple[str, tuple[str, ...], dict, dict, str]] = [
    (
        "compliance",
        ("legal", "contract", "compliance", "policy", "regulation", "medical", "juridique", "contrat", "conformité", "conformite", "réglementation", "médical", "medical", "finance"),
        {"strategy": "hybrid_reranked", "top_k": 8, "score_threshold": 0.5},
        {"citation_required": True, "answer_only_from_context": True, "idk_threshold": 0.3, "content_filter_level": "high"},
        "precision-critical domain: reranked retrieval, citations mandatory, answers restricted to the retrieved context, abstain when unsure",
    ),
    (
        "support",
        ("support", "faq", "customer", "helpdesk", "help desk", "ticket", "client", "assistance", "service client"),
        {"strategy": "hybrid", "top_k": 5},
        {"citation_required": True, "memory_enabled": True, "memory_window_size": 10},
        "customer-facing Q&A: balanced hybrid retrieval, cited answers, short conversational memory",
    ),
    (
        "technical",
        ("code", "api", "developer", "documentation", "sdk", "engineering", "technical", "technique", "développeur", "developpeur"),
        {"strategy": "hybrid_reranked", "top_k": 8},
        {"citation_required": True},
        "technical documentation: exact terms matter (BM25 in the hybrid) and ranking quality matters (reranking)",
    ),
    (
        "research",
        ("research", "analy", "report", "summar", "synthes", "recherche", "synthèse", "rapport", "résumé", "resume"),
        {"strategy": "hybrid", "top_k": 12, "mmr": True, "multi_query": True},
        {"citation_required": True},
        "broad synthesis: wider candidate pool, MMR diversification and multi-query to cover several angles",
    ),
]
_DEFAULT_PROFILE = ("general", {"strategy": "hybrid", "top_k": 5}, {"citation_required": True}, "no specific domain detected: balanced defaults, citations on")

# tool intent keywords -> names of the REAL agent tool catalog (api/services/agent_tools.py::AGENT_TOOL_CATALOG,
# the vocabulary `Agent.tools` is validated and resolved against at run time)
_TOOL_INTENTS: list[tuple[tuple[str, ...], str]] = [
    (("web", "internet", "news", "current", "actualité", "actualite", "recent"), "web_search"),
    (("calculate", "calculation", "math", "price", "pricing", "calcul", "tarif"), "calculate"),
    (("url", "link", "website", "lien", "site web"), "read_url"),
    (("escalate", "human", "handoff", "escalade", "humain"), "escalate_to_human"),
]


def _matches(text: str, keywords: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(k)}", text) for k in keywords)


def build_agent_blueprint(requirement: str, name: str | None = None, registered_tools: set[str] | None = None) -> dict:
    """Pure and deterministic. `registered_tools` defaults to the real agent
    tool catalog; it is a parameter only so tests can pin it."""
    if not requirement or len(requirement.strip()) < 10:
        raise FactoryError(["requirement must describe the agent's purpose in at least a short sentence"])
    text = requirement.lower()

    profile, retrieval, overrides, why = _DEFAULT_PROFILE[0], dict(_DEFAULT_PROFILE[1]), dict(_DEFAULT_PROFILE[2]), _DEFAULT_PROFILE[3]
    for candidate_profile, keywords, candidate_retrieval, candidate_overrides, candidate_why in _PROFILES:
        if _matches(text, keywords):
            profile, retrieval, overrides, why = candidate_profile, dict(candidate_retrieval), dict(candidate_overrides), candidate_why
            break
    rationale = [f"profile '{profile}': {why}"]

    if registered_tools is None:
        from api.services.agent_tools import AGENT_TOOL_CATALOG

        registered_tools = set(AGENT_TOOL_CATALOG)
    tools: list[dict] = []
    if "search_knowledge_base" in registered_tools:
        tools.append({"name": "search_knowledge_base", "enabled": True, "config": {}})
        rationale.append("tool 'search_knowledge_base': every RAG agent must be able to query the organization's documents")
    for keywords, tool_name in _TOOL_INTENTS:
        if tool_name in registered_tools and _matches(text, keywords) and not any(t["name"] == tool_name for t in tools):
            tools.append({"name": tool_name, "enabled": True, "config": {}})
            rationale.append(f"tool '{tool_name}': the requirement mentions a matching capability")

    agent = {
        "name": (name or _derive_name(requirement)).strip()[:200],
        "description": requirement.strip()[:500],
        "system_prompt": _system_prompt(requirement.strip(), overrides),
        "tools": tools,
        "memory_enabled": overrides.pop("memory_enabled", True),
        "memory_window_size": overrides.pop("memory_window_size", 10),
        "guardrails_enabled": True,
        "prompt_injection_detection_enabled": True,
        **overrides,
    }
    rationale.append("prompt-injection detection on: this agent answers from retrieved documents, which can carry hostile instructions")
    return {"profile": profile, "agent": agent, "retrieval_config": retrieval, "rationale": rationale}


def _derive_name(requirement: str) -> str:
    words = re.sub(r"[^\w\s-]", "", requirement).split()[:6]
    return " ".join(w.capitalize() for w in words) or "RAG Agent"


def _system_prompt(requirement: str, overrides: dict) -> str:
    lines = [
        f"You are an assistant for the following purpose: {requirement}",
        "Answer only from the provided context and the tools you are given; when the context does not contain the answer, say so plainly instead of guessing.",
    ]
    if overrides.get("citation_required"):
        lines.append("Cite the sources of every claim using the numbered references from the context.")
    return "\n".join(lines)


def validate_blueprint(blueprint: dict) -> list[str]:
    """Runs the platform's REAL validators and registries; returns every
    problem found (empty list = deployable)."""
    from api.services.agent_guardrails import AgentGuardrailError, validate_guardrails_config
    from api.services.agent_idk import InvalidIdkThresholdError, validate_idk_threshold
    from api.services.agent_knowledge_base import AgentKnowledgeBaseError, validate_retrieval_config
    from api.services.agent_memory_config import AgentMemoryConfigError, validate_memory_config
    from api.services.agent_tools import AgentToolError, validate_tools_list

    agent = blueprint.get("agent", {})
    problems: list[str] = []
    for label, check in (
        ("retrieval_config", lambda: validate_retrieval_config(blueprint.get("retrieval_config") or {})),
        ("tools", lambda: validate_tools_list(agent.get("tools") or [])),
        ("memory", lambda: validate_memory_config(agent)),
        ("guardrails", lambda: validate_guardrails_config(agent)),
        ("idk_threshold", lambda: validate_idk_threshold(agent.get("idk_threshold"))),
    ):
        try:
            check()
        except (AgentKnowledgeBaseError, AgentToolError, AgentMemoryConfigError, AgentGuardrailError, InvalidIdkThresholdError, ValueError) as exc:
            problems.append(f"{label}: {exc}")
    if not (agent.get("name") or "").strip():
        problems.append("name: required")
    if not (agent.get("system_prompt") or "").strip():
        problems.append("system_prompt: required")
    return problems


async def deploy_blueprint(
    db: AsyncSession, organization_id: uuid.UUID, blueprint: dict, created_by: uuid.UUID | None,
    evaluate_dataset_id: uuid.UUID | None = None, min_target_value: float | None = None, target_metric: str = "recall_at_5",
) -> dict:
    """Validate -> create the real agent -> (optional) benchmark it ->
    go / hold-back. With `evaluate_dataset_id`, the agent is benchmarked on
    that dataset (its retrieval config is applied for real by the Eval Lab);
    if `min_target_value` is given and the measured `target_metric` average is
    below it, the agent is created but left PAUSED ("held_back") instead of
    active, and the measured metrics are returned -- a measured gate, never a
    silent deploy of something that failed its own bar."""
    from api.models.agent import AgentStatus
    from api.models.evaluation import EvaluationDataset
    from api.security.agents import create_agent

    problems = validate_blueprint(blueprint)
    if problems:
        raise FactoryError(problems)
    if evaluate_dataset_id is not None:
        dataset = await db.get(EvaluationDataset, evaluate_dataset_id)
        if dataset is None or dataset.organization_id != organization_id:
            raise FactoryError(["evaluate_dataset_id: dataset not found"])

    agent = await create_agent(db, organization_id, dict(blueprint["agent"]), created_by)
    agent.knowledge_base_config = dict(blueprint.get("retrieval_config") or {})
    await db.flush()

    metrics: dict | None = None
    decision = "deployed"
    if evaluate_dataset_id is not None:
        from api.services.evaluation_jobs import create_evaluation_job, run_evaluation_job
        from api.services.mcp.builtin_tools import _job_metric_averages

        job = await create_evaluation_job(db, evaluate_dataset_id, agent_id=agent.id, created_by=created_by)
        await db.commit()
        job = await run_evaluation_job(db, job.id)
        metrics = await _job_metric_averages(db, job.id)
        measured = metrics.get(target_metric)
        if min_target_value is not None and (measured is None or measured < min_target_value):
            agent.status = AgentStatus.paused.value
            decision = "held_back"
        else:
            decision = "deployed_and_evaluated"
    await db.flush()
    return {
        "agent_id": agent.id, "status": agent.status, "decision": decision, "metrics": metrics,
        "target_metric": target_metric, "min_target_value": min_target_value, "blueprint": blueprint,
    }
