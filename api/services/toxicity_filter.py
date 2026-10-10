"""Spec 10.2.7 -- toxicity filtering (insults, profanity, threats) for user questions and model answers.

A deterministic, dependency-free lexical detector with accent / leet-speak / repeated-letter normalisation and word-boundary matching, for English,
French, Spanish, German and Portuguese. It is a first line of defence, not a moderation model: it will miss subtle or novel toxicity and cannot
understand context. Deployments that need more can set an external moderation endpoint later behind the same `detect_toxicity` interface.

The matched terms are never returned (only categories and a score), so a blocked message is not echoed back into logs or error messages.
"""

import re
import unicodedata

# Category -> word list. Whole-word match after normalisation. Deliberately conservative: strong profanity, direct insults and explicit threats.
_LEXICON: dict[str, tuple[str, ...]] = {
    "profanity": (
        "fuck", "fucking", "shit", "bullshit", "asshole", "bastard", "bitch", "dick", "cunt",
        "merde", "putain", "connard", "connasse", "salaud", "salope", "enculer", "encule", "foutre",
        "mierda", "joder", "puta", "cabron", "cono", "gilipollas",
        "scheisse", "scheiss", "arschloch", "wichser", "fotze", "hurensohn",
        "porra", "caralho", "foda", "buceta", "filho da puta",
    ),
    "insult": (
        "idiot", "moron", "stupid", "imbecile", "retard", "loser", "dumbass", "scumbag",
        "debile", "abruti", "cretin", "imbecile", "nul a chier", "pauvre type",
        "estupido", "idiota", "imbecil", "gilipollas", "subnormal",
        "dummkopf", "trottel", "vollidiot",
        "burro", "otario", "babaca", "idiota",
    ),
    "threat": (
        "i will kill you", "i am going to kill you", "kill yourself", "i will hurt you", "you will die", "i will find you", "i will destroy you",
        "je vais te tuer", "je vais te massacrer", "creve", "tu vas mourir", "je vais te retrouver",
        "te voy a matar", "vas a morir", "te voy a encontrar",
        "ich bring dich um", "ich werde dich toten", "du stirbst",
        "vou te matar", "voce vai morrer", "vou te encontrar",
    ),
}

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i"})
_WEIGHTS = {"threat": 1.0, "profanity": 0.6, "insult": 0.5}
DEFAULT_THRESHOLD = 0.5


def _normalize(text: str) -> str:
    """lower-case, strip accents, undo leet-speak, collapse repeated letters ('fuuuck' -> 'fuck') and punctuation into single spaces."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c)).translate(_LEET)
    text = re.sub(r"(.)\1{2,}", r"\1", text)          # 3+ repeated letters -> 1
    # letters spelled out with separators ("f.u.c.k", "f u c k") are joined back into one word
    text = re.sub(r"(?<![a-z])(?:[a-z][.\-_* ]){2,}[a-z](?![a-z])", lambda m: re.sub(r"[.\-_* ]", "", m.group(0)), text)
    text = re.sub(r"[^a-z\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return f" {text} "


_PATTERNS = {
    category: [re.compile(rf"(?<![a-z]){re.escape(' '.join(_normalize(term).split()))}(?![a-z])") for term in terms]
    for category, terms in _LEXICON.items()
}


def detect_toxicity(text: str, threshold: float = DEFAULT_THRESHOLD) -> dict:
    """Return `{"is_toxic": bool, "score": float 0..1, "categories": [..]}`. Never includes the matched words."""
    if not text or not text.strip():
        return {"is_toxic": False, "score": 0.0, "categories": []}
    normalized = _normalize(text)
    categories: list[str] = []
    score = 0.0
    for category, patterns in _PATTERNS.items():
        hits = sum(1 for pattern in patterns if pattern.search(normalized))
        if hits:
            categories.append(category)
            # one hit counts fully, extra hits add a little (diminishing), capped at 1
            score = max(score, min(1.0, _WEIGHTS[category] + 0.15 * (hits - 1)))
    return {"is_toxic": score >= threshold, "score": round(score, 2), "categories": categories}
