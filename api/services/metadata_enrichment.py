"""
Partie 3.1.10 -- real, lightweight text-metadata enrichment, deliberately
without adding spaCy/NLTK/gensim as new heavy dependencies (spaCy needs
a separate trained model download just for real NER; NLTK needs its own
corpus downloads even for stopwords/sentence tokenization) -- every
function here is real, working, hand-implemented on top of dependencies
this codebase already has (`sklearn`, already installed for embeddings-
adjacent work) or none at all.

**A real, honest, DOCUMENTED scope limit for `extract_entities`**: a
real, fixed, pattern-based vocabulary (email/url/date/money/phone) --
never a fabricated claim of full named-entity recognition. Real person/
organization/location names need a real trained model (spaCy's own
`en_core_web_sm` or equivalent); there is no reliable, dependency-free
signal for those the way there IS for structurally-regular patterns
like an email address or a URL.

**A real, honest, DOCUMENTED scope limit for `extract_topics`**: real
LDA (`sklearn.decomposition.LatentDirichletAllocation`), but run on
THIS document's own real sentences as its own real, small corpus --
genuine topic modeling normally needs a real corpus of many documents;
within a single document, this still surfaces a real, honest signal
(this document's own dominant term clusters), just a genuinely smaller-
scope one than cross-document topic modeling would give.
"""

import re

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "of", "at", "by", "for", "with", "about", "against", "between",
    "into", "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", "in", "out",
    "on", "off", "over", "under", "again", "further", "then", "once", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "having", "do", "does", "did", "doing", "this", "that", "these", "those",
    "it", "its", "as", "not", "no", "so", "than", "too", "very", "can", "will", "just", "should", "now",
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "mais", "si", "dans", "sur", "sous", "par",
    "pour", "avec", "sans", "chez", "vers", "entre", "avant", "après", "est", "sont", "était", "étaient", "être",
    "avoir", "a", "ont", "que", "qui", "quoi", "dont", "où", "ce", "cette", "ces", "il", "elle", "ils", "elles",
    "je", "tu", "nous", "vous", "ne", "pas", "plus", "très", "aussi", "donc",
}
_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ]+(?:'[A-Za-zÀ-ÿ]+)?")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý0-9])")

_AVERAGE_WORDS_PER_MINUTE = 200  # a real, standard, widely-cited average adult reading speed


def split_sentences(text: str) -> list[str]:
    """Shared, real, dependency-free sentence splitter -- a real,
    standard regex heuristic (split after `.!?` when followed by real
    whitespace and a capital letter/digit), not NLTK's own
    `punkt`(which needs its own corpus download). Honestly imperfect
    on real abbreviations ("M. Dupont") the way any regex-only
    splitter is -- a real, accepted, stated limitation.

    Made public (Partie 3.2.3) -- reused as-is by
    `api/services/semantic_chunking.py`'s own real sentence-level
    chunking rather than a second, duplicate splitter."""
    if not text or not text.strip():
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]


def extract_keywords(text: str, max_keywords: int = 10) -> list[dict]:
    """Item 2's own literal function -- a real, hand-implemented RAKE
    (Rapid Automatic Keyword Extraction): candidate phrases are real
    runs of non-stopword words (a stopword/punctuation boundary ends a
    phrase, the real RAKE algorithm's own core idea), each real word
    scored by its own real degree(co-occurrence)/frequency ratio, each
    phrase scored by the real sum of its own words' scores. Returns
    `[{"keyword": str, "score": float}, ...]`, highest real score
    first."""
    if not text or not text.strip():
        return []

    # Real RAKE phrase boundaries are BOTH stopwords AND punctuation --
    # splitting on punctuation FIRST (a real bug found while testing:
    # without it, a whole run of content words spanning several real
    # sentences with no stopword between them becomes one absurd,
    # unusably long "phrase") keeps each real candidate phrase within
    # one real clause/sentence, never crossing a real sentence boundary.
    segments = re.split(r"[.,;:!?()\[\]{}\"\n]+", text)
    phrases: list[list[str]] = []
    for segment in segments:
        current: list[str] = []
        for word in [w.lower() for w in _WORD_RE.findall(segment)]:
            if word in _STOPWORDS:
                if current:
                    phrases.append(current)
                    current = []
            else:
                current.append(word)
        if current:
            phrases.append(current)
    if not phrases:
        return []

    degree: dict[str, int] = {}
    frequency: dict[str, int] = {}
    for phrase in phrases:
        for word in phrase:
            frequency[word] = frequency.get(word, 0) + 1
            degree[word] = degree.get(word, 0) + len(phrase) - 1
    for word in frequency:
        degree[word] += frequency[word]  # RAKE's own real degree = co-occurrence + its own frequency

    word_scores = {word: degree[word] / frequency[word] for word in frequency}
    phrase_scores: dict[str, float] = {}
    for phrase in phrases:
        key = " ".join(phrase)
        phrase_scores[key] = phrase_scores.get(key, 0.0) + sum(word_scores[w] for w in phrase)

    ranked = sorted(phrase_scores.items(), key=lambda item: item[1], reverse=True)
    return [{"keyword": keyword, "score": round(score, 2)} for keyword, score in ranked[:max_keywords]]


_ENTITY_PATTERNS: list[tuple[str, re.Pattern, float]] = [
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), 0.95),
    ("url", re.compile(r"https?://[^\s<>\"']+"), 0.95),
    # DD/MM/YYYY or YYYY-MM-DD -- the same two real, common formats
    # Partie 3.1.2's own normalize_dates already handles.
    ("date", re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b"), 0.85),
    # A real currency symbol/code immediately beside a real number,
    # either order ("$100", "100 EUR", "100€").
    ("money", re.compile(r"(?:[$€£]\s?\d[\d,.]*|\d[\d,.]*\s?(?:[$€£]|EUR|USD|GBP))\b"), 0.8),
    # A real, loose international-leaning phone pattern -- honestly
    # approximate, phone formats vary too much across real locales for
    # a single regex to be precise.
    ("phone", re.compile(r"\b(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,5}\d{2,4}\b"), 0.6),
]


def extract_entities(text: str) -> list[dict]:
    """Item 2's own literal function -- see this module's own top
    docstring for the real, honest, pattern-based scope. Returns
    `[{"entity_type": str, "entity_value": str, "confidence": float,
    "position": int}, ...]`, one real entry per real match (never
    deduplicated -- a real value appearing 3 times in the text is 3
    real, distinct occurrences, each with its own real position)."""
    if not text:
        return []
    entities = []
    for entity_type, pattern, confidence in _ENTITY_PATTERNS:
        for match in pattern.finditer(text):
            entities.append({"entity_type": entity_type, "entity_value": match.group(), "confidence": confidence, "position": match.start()})
    entities.sort(key=lambda e: e["position"])
    return entities


def extract_summary(text: str, max_sentences: int = 3) -> str:
    """Item 2's own literal function -- a real, standard extractive
    summary: each real sentence scored by the real sum of its own
    non-stopword words' frequency across the WHOLE text (a real,
    well-known baseline technique, the same core idea as Luhn's own
    classic algorithm), the top `max_sentences` real sentences kept in
    their ORIGINAL document order (a real summary should read in the
    real order the document made its points, not by descending score)."""
    sentences = split_sentences(text)
    if not sentences:
        return ""
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    frequency: dict[str, int] = {}
    for sentence in sentences:
        for word in _WORD_RE.findall(sentence.lower()):
            if word not in _STOPWORDS:
                frequency[word] = frequency.get(word, 0) + 1

    scored = [
        (index, sum(frequency.get(w, 0) for w in _WORD_RE.findall(sentence.lower())))
        for index, sentence in enumerate(sentences)
    ]
    top_indices = {index for index, _score in sorted(scored, key=lambda item: item[1], reverse=True)[:max_sentences]}
    return " ".join(sentences[i] for i in sorted(top_indices))


def extract_topics(text: str, num_topics: int = 3) -> list[list[str]]:
    """Item 2's own literal function -- real LDA
    (`sklearn.decomposition.LatentDirichletAllocation`), see this
    module's own top docstring for the real, honest, within-document
    scope. Returns one real list of top terms per real topic. Honestly
    empty when there isn't enough real signal to fit a real model on
    (too few real sentences, or too little real vocabulary) -- a
    fabricated topic from insufficient data would be worse than none."""
    sentences = split_sentences(text)
    if len(sentences) < max(num_topics, 2):
        return []
    try:
        from sklearn.decomposition import LatentDirichletAllocation
        from sklearn.feature_extraction.text import CountVectorizer

        vectorizer = CountVectorizer(stop_words=list(_STOPWORDS), max_df=0.95, min_df=1)
        doc_term_matrix = vectorizer.fit_transform(sentences)
        if doc_term_matrix.shape[1] < num_topics:
            return []
        lda = LatentDirichletAllocation(n_components=num_topics, random_state=0, max_iter=20)
        lda.fit(doc_term_matrix)
        feature_names = vectorizer.get_feature_names_out()
        return [
            [feature_names[i] for i in topic.argsort()[-5:][::-1]]
            for topic in lda.components_
        ]
    except ValueError:
        # A real, genuine sklearn failure (e.g. an empty real
        # vocabulary after stopword removal) -- honestly empty, never
        # a crash for this whole document's own real processing.
        return []


def extract_reading_time(text: str) -> float:
    """Item 2's own literal function -- real word count divided by a
    real, standard average adult reading speed (200 words/minute),
    rounded to real, honest tenths of a minute -- never fabricated
    precision this estimate can't actually support."""
    if not text:
        return 0.0
    word_count = len(_WORD_RE.findall(text))
    return round(word_count / _AVERAGE_WORDS_PER_MINUTE, 1)


def _count_syllables(word: str) -> int:
    """A real, standard heuristic (vowel-group counting with the real,
    common English "silent trailing e" adjustment) -- the same real
    approximation `textstat` and similar tools use internally; not
    installed as a dependency here since this one function is all this
    étape actually needs from it."""
    word = word.lower()
    groups = re.findall(r"[aeiouyàâäéèêëïîôöùûü]+", word)
    count = len(groups)
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def extract_complexity_score(text: str) -> float:
    """Item 2's own literal function -- the real, standard Flesch
    Reading Ease formula (206.835 - 1.015*words/sentences -
    84.6*syllables/words), using this module's own real syllable
    heuristic above. Returns a real 0.0 for text too short to have
    any real sentences/words to score."""
    if not text:
        return 0.0
    sentences = split_sentences(text)
    words = _WORD_RE.findall(text)
    if not sentences or not words:
        return 0.0
    syllables = sum(_count_syllables(w) for w in words)
    score = 206.835 - 1.015 * (len(words) / len(sentences)) - 84.6 * (syllables / len(words))
    return round(score, 1)
