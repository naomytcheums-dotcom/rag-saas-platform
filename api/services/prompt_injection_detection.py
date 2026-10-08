"""
Real prompt-injection/jailbreak detection -- closes the gap this
codebase's own competitive audit (docs/COMPETITIVE_AUDIT_KNOWFLOW.md)
flagged as absent: `api/services/agent_guardrails.py`'s real
`check_content_safety` already protects against unsafe-INTENT topics
(bombs, drugs, self-harm), but nothing in this codebase previously
detected an attempt to override an agent's own system prompt/
instructions (e.g. "ignore all previous instructions and...").

**Deliberately a real, dedicated classifier model
(`protectai/deberta-v3-base-prompt-injection-v2`, Apache 2.0) via
`transformers` -- ALREADY a real dependency of this codebase (embeddings,
tokenizers, semantic chunking) -- rather than NeMo Guardrails (NVIDIA's
own framework)**: NeMo Guardrails' real value is its Colang
configuration DSL for building multi-turn conversational rail flows;
this étape's own real need is ONE classification (is this input a
prompt-injection attempt, yes/no) that a purpose-built, real,
already-fine-tuned model answers directly, with zero new DSL, config
format, or runtime to learn/maintain -- adding a second, heavier
framework for a single boolean check would be the same kind of
needless-duplication this codebase's own Ragas/DeepEval decision (see
ROADMAP.md) already reasoned through and rejected.

**Same lazy-loaded, cached-singleton pattern as
api/services/sentence_chunking.py's own `get_tokenizer`**: loading a
real HuggingFace model is a real, multi-second (and, on first use, a
real download) operation -- never paid by a deployment/agent that
leaves this off."""

import logging

logger = logging.getLogger(__name__)

_MODEL_NAME = "protectai/deberta-v3-base-prompt-injection-v2"
_CLASSIFIER = None

# Real, deliberate default -- this model's own real, documented output
# label for a detected injection/jailbreak attempt (the other real
# label is "SAFE").
_INJECTION_LABEL = "INJECTION"
DEFAULT_SCORE_THRESHOLD = 0.75


class PromptInjectionDetectorNotAvailableError(Exception):
    """Same honest-degradation contract as
    api/services/pii_detection.py's own PresidioNotAvailableError."""


def _get_classifier():
    global _CLASSIFIER
    if _CLASSIFIER is None:
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise PromptInjectionDetectorNotAvailableError(f"transformers is not installed: {exc}") from exc
        _CLASSIFIER = pipeline("text-classification", model=_MODEL_NAME)
    return _CLASSIFIER


def detect_prompt_injection(text: str, score_threshold: float = DEFAULT_SCORE_THRESHOLD) -> dict:
    """Real classification -- `{"is_injection": bool, "score": float,
    "label": str}`, the model's own real output, not reshaped into a
    fabricated category set."""
    classifier = _get_classifier()
    # truncation=True: a real, necessary bound -- this model's own real
    # max sequence length (512 tokens) would otherwise raise on a real,
    # long user message rather than classifying the text it CAN see.
    result = classifier(text, truncation=True)[0]
    is_injection = result["label"] == _INJECTION_LABEL and result["score"] >= score_threshold
    return {"is_injection": is_injection, "score": result["score"], "label": result["label"]}
