"""E2E finding 2026-10-13 -- the first document processed by a freshly started worker failed with
"cannot import name 'AutoTokenizer' from 'transformers'" because the embedder warm-up thread and the indexing task imported the lazy `transformers`
module concurrently. The tokenizer import must wait for any model load in progress (same lock)."""

import threading
import time

from api.security import documents
from api.services import transformers_import


def test_the_embedder_lock_and_the_tokenizer_import_share_one_lock():
    assert documents._EMBEDDER_LOCK is transformers_import.EMBEDDER_LOCK


def test_tokenizer_import_waits_while_a_model_is_being_loaded():
    finished = threading.Event()
    result = {}

    def importer():
        result["cls"] = transformers_import.import_auto_tokenizer()
        finished.set()

    with transformers_import.EMBEDDER_LOCK:  # the warm-up thread is loading the embedder
        thread = threading.Thread(target=importer, daemon=True)
        thread.start()
        time.sleep(0.5)
        assert not finished.is_set(), "the tokenizer import must not run while the embedder is loading"
    thread.join(timeout=120)
    assert finished.is_set()
    assert result["cls"].__name__ == "AutoTokenizer"


def test_chunking_and_media_use_the_serialised_import():
    import inspect

    from api.services import media, sentence_chunking

    assert "import_auto_tokenizer" in inspect.getsource(sentence_chunking.get_tokenizer)
    assert "from transformers import AutoTokenizer" not in inspect.getsource(media)
