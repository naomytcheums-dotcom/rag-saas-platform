"""Serialised import of the `transformers` package (E2E finding 2026-10-13).

`transformers` is a lazy module. The embedder warm-up thread (api/security/documents.py `start_embedder_warmup`, started in every API and Celery worker process)
imports `sentence_transformers`, which imports `transformers`, while the first indexing task imports `AutoTokenizer` from the main thread. Two threads importing the
same lazy module at once make one of them fail with "cannot import name 'AutoTokenizer' from 'transformers'": on a freshly started worker the first document it
processed ended `failed` (reproduced twice, 2 of 2 cold starts). Both imports now take the same lock, so the tokenizer import waits for the warm-up to finish.
"""

import os
import threading

# The lock that api.security.documents.get_embedder holds while it loads a model.
EMBEDDER_LOCK = threading.Lock()


def import_auto_tokenizer():
    """Return `transformers.AutoTokenizer`, never importing it while the embedder is being loaded by another thread."""
    os.environ.setdefault("USE_TF", "0")
    with EMBEDDER_LOCK:
        from transformers import AutoTokenizer

    return AutoTokenizer
