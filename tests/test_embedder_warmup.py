import sys
import threading
import time
import types

from api.config import settings
from api.security import documents
from api.tasks import celery_app


def _install_slow_sentence_transformer(monkeypatch):
    loads = []

    class FakeSentenceTransformer:
        def __init__(self, model_name):
            loads.append(model_name)
            time.sleep(0.05)
            self.model_name = model_name

    monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer))
    monkeypatch.setattr(documents, "_EMBEDDER_CACHE", {})
    return loads


def test_concurrent_cold_requests_load_the_embedder_once(monkeypatch):
    loads = _install_slow_sentence_transformer(monkeypatch)
    results = []
    threads = [threading.Thread(target=lambda: results.append(documents.get_embedder("model-a"))) for _ in range(5)]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert loads == ["model-a"]
    assert len({id(result) for result in results}) == 1


def test_startup_warmup_loads_the_default_embedder(monkeypatch):
    loads = _install_slow_sentence_transformer(monkeypatch)
    monkeypatch.setattr(settings, "EMBEDDER_WARMUP_ON_STARTUP", True)

    thread = documents.start_embedder_warmup("model-b")
    thread.join(timeout=2)

    assert loads == ["model-b"]
    assert documents.get_embedder("model-b").model_name == "model-b"


def test_startup_warmup_can_be_disabled(monkeypatch):
    loads = _install_slow_sentence_transformer(monkeypatch)
    monkeypatch.setattr(settings, "EMBEDDER_WARMUP_ON_STARTUP", False)

    assert documents.start_embedder_warmup("model-c") is None
    assert loads == []


def test_solo_worker_warms_the_embedder_when_ready(monkeypatch):
    calls = []
    monkeypatch.setattr(celery_app, "_warm_embedder", lambda: calls.append("warm"))

    solo_pool = type("SoloPool", (), {"__module__": "celery.concurrency.solo"})()
    celery_app._warm_embedder_in_inline_worker(sender=types.SimpleNamespace(pool=solo_pool))

    assert calls == ["warm"]


def test_prefork_parent_leaves_warmup_to_pool_processes(monkeypatch):
    calls = []
    monkeypatch.setattr(celery_app, "_warm_embedder", lambda: calls.append("warm"))

    prefork_pool = type("PreforkPool", (), {"__module__": "celery.concurrency.prefork"})()
    celery_app._warm_embedder_in_inline_worker(sender=types.SimpleNamespace(pool=prefork_pool))

    assert calls == []
