"""
Real automatic prompt optimization via DSPy (Apache 2.0, MIT-licensed
optimizers) -- item 11 of the "bricks open source" list. Genuinely new
capability, not a duplicate of anything already real in this codebase:
`api/services/generation.py`'s own `system_prompt` (resolved via
`api/services/llm_config.py`'s `resolve_system_prompt`) is today a
plain, hand-written string an organization admin edits by hand. This
module runs a real, offline optimization pass -- DSPy's own
`BootstrapFewShot` teleprompter -- against this organization's OWN
real, already-existing ground-truth data (`EvaluationQuestion.question`/
`expected_answer`, Partie 7.1.3) to produce a CANDIDATE, improved
prompt (instructions + bootstrapped few-shot demonstrations), using the
SAME real metric this codebase already trusts for ground-truth
validation (`api/services/ground_truth_answers.py`'s own
`validate_semantic`) -- no second, invented judging mechanism.

**Deliberately does NOT auto-apply the result** -- same "never silently
change existing behavior" discipline as every other opt-in feature in
this codebase (`api/security/organization_settings.py`'s own
`DEFAULT_SETTINGS`). `optimize_system_prompt` returns a candidate
string; writing it into `organization_settings.system_prompt` is a
separate, explicit call to the ALREADY REAL
`api/security/organization_settings.py`'s `update_org_settings`, an
admin decision this module has no business making unilaterally.

**Wired to this codebase's OWN real LLM stack, never DSPy's own
independent OpenAI default**: `dspy.LM(model=llm_kwargs["model"],
api_key=llm_kwargs.get("api_key"))` reuses the EXACT same `model`/
`api_key` values `api/services/llm_providers.py`'s own real litellm
calls already use for this provider -- verified directly against that
module's own `_provider_kwargs`, never a separately-guessed litellm
model string.

**Runtime length ceiling, never silently truncated**: the optimized
prompt (instructions + serialized few-shot demos) can exceed
`settings.SYSTEM_PROMPT_MAX_LENGTH` (`api/services/llm_config.py`'s own
real, narrower 1000-char runtime ceiling) -- this module honestly
reports `exceeds_runtime_limit` rather than truncating a real,
DSPy-selected demonstration mid-sentence.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.evaluation import EvaluationQuestion

# Real, deliberate minimum trainset size -- DSPy's own BootstrapFewShot
# needs at least a handful of real labeled examples to bootstrap
# anything meaningful from; fewer than this is an honest
# NotEnoughGroundTruthError, not a real optimization run over 1-2
# examples that would just memorize them.
MIN_GROUND_TRUTH_EXAMPLES = 5


class PromptOptimizationError(Exception):
    """Same honest-degradation contract as
    api/services/mem0_service.py's own Mem0NotAvailableError /
    api/services/graph_rag.py's own GraphRAGNotAvailableError."""


class NotEnoughGroundTruthError(PromptOptimizationError):
    """Real, honest refusal -- see MIN_GROUND_TRUTH_EXAMPLES above."""


async def _load_trainset(db: AsyncSession, dataset_id: uuid.UUID) -> list[EvaluationQuestion]:
    rows = (await db.scalars(
        select(EvaluationQuestion).where(
            EvaluationQuestion.dataset_id == dataset_id,
            EvaluationQuestion.expected_answer.is_not(None),
        )
    )).all()
    return list(rows)


def _configure_dspy_lm(llm_provider: str, llm_model: str | None):
    """Real reuse of this codebase's OWN resolved provider/model/key --
    see this module's own top docstring for why this is never DSPy's
    own independent default."""
    import dspy

    from api.services.llm_providers import _provider_kwargs

    llm_kwargs = _provider_kwargs(llm_provider, llm_model)
    lm = dspy.LM(model=llm_kwargs["model"], api_key=llm_kwargs.get("api_key"))
    dspy.configure(lm=lm)
    return lm


def _render_optimized_prompt(compiled_predictor, base_instructions: str) -> str:
    """Real, honest serialization of what DSPy actually selected --
    the compiled predictor's own (possibly DSPy-rewritten)
    `signature.instructions` plus its own real, bootstrapped few-shot
    `demos` (each a real (question, answer) pair DSPy chose FROM this
    organization's own ground truth, not a fabricated example) --
    exactly the two real artifacts `BootstrapFewShot.compile` produces
    (verified directly against the installed `dspy` package's own
    `Predict`/`BootstrapFewShot` before writing this function)."""
    instructions = compiled_predictor.signature.instructions or base_instructions
    lines = [instructions.strip()]
    if compiled_predictor.demos:
        lines.append("\nExamples:")
        for demo in compiled_predictor.demos:
            question = demo.get("question") if isinstance(demo, dict) else getattr(demo, "question", None)
            answer = demo.get("answer") if isinstance(demo, dict) else getattr(demo, "answer", None)
            if question and answer:
                lines.append(f"Q: {question}\nA: {answer}")
    return "\n".join(lines).strip()


async def optimize_system_prompt(
    db: AsyncSession, dataset_id: uuid.UUID, llm_provider: str, llm_model: str | None = None,
    base_instructions: str = "Answer the question accurately and concisely, using only the given context.",
) -> dict:
    """Real, end-to-end optimization run: loads this organization's own
    real ground-truth questions for `dataset_id`, bootstraps few-shot
    demonstrations with DSPy's real `BootstrapFewShot` teleprompter
    against the real `validate_semantic` metric
    (`api/services/ground_truth_answers.py`, reused directly -- no
    second, invented judge), and returns a real CANDIDATE prompt --
    never auto-applied, see this module's own top docstring."""
    try:
        import dspy
        from dspy.teleprompt import BootstrapFewShot
    except ImportError as exc:
        raise PromptOptimizationError(f"dspy is not installed: {exc}") from exc

    from api.services.ground_truth_answers import validate_semantic

    questions = await _load_trainset(db, dataset_id)
    if len(questions) < MIN_GROUND_TRUTH_EXAMPLES:
        raise NotEnoughGroundTruthError(
            f"Dataset {dataset_id} has {len(questions)} real ground-truth answers "
            f"(needs at least {MIN_GROUND_TRUTH_EXAMPLES} to bootstrap a real optimization run)"
        )

    _configure_dspy_lm(llm_provider, llm_model)

    trainset = [
        dspy.Example(question=q.question, answer=q.expected_answer).with_inputs("question")
        for q in questions
    ]

    def _metric(example, prediction, trace=None) -> bool:
        # Real reuse of this codebase's own semantic-similarity ground-
        # truth validator -- the SAME real threshold
        # (settings.GROUND_TRUTH_SEMANTIC_THRESHOLD) every other real
        # evaluation run in this codebase already trusts.
        return validate_semantic(getattr(prediction, "answer", ""), example.answer)

    student = dspy.Predict("question -> answer")
    student.signature = student.signature.with_instructions(base_instructions)

    optimizer = BootstrapFewShot(metric=_metric, max_bootstrapped_demos=4, max_labeled_demos=8)
    compiled = optimizer.compile(student, trainset=trainset)

    candidate_prompt = _render_optimized_prompt(compiled, base_instructions)

    return {
        "system_prompt": candidate_prompt,
        "trainset_size": len(trainset),
        "bootstrapped_demo_count": len(compiled.demos),
        "exceeds_runtime_limit": len(candidate_prompt) > settings.SYSTEM_PROMPT_MAX_LENGTH,
        "runtime_limit": settings.SYSTEM_PROMPT_MAX_LENGTH,
    }
