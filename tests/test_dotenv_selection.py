"""The legacy RAG loader must honor an explicit isolated dotenv target."""

from generation import load_dotenv_if_present


def test_explicit_dotenv_selection(tmp_path, monkeypatch):
    monkeypatch.setattr("generation.PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("RAG_ENV_FILE", ".env.staging")
    monkeypatch.delenv("DOTENV_SELECTION_TEST", raising=False)
    (tmp_path / ".env").write_text("DOTENV_SELECTION_TEST=production-marker\n", encoding="utf-8")
    (tmp_path / ".env.staging").write_text("DOTENV_SELECTION_TEST=staging-marker\n", encoding="utf-8")
    load_dotenv_if_present()
    import os

    assert os.environ["DOTENV_SELECTION_TEST"] == "staging-marker"


def test_missing_selected_file_never_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr("generation.PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("RAG_ENV_FILE", ".env.missing")
    monkeypatch.delenv("DOTENV_SELECTION_TEST", raising=False)
    (tmp_path / ".env").write_text("DOTENV_SELECTION_TEST=production-marker\n", encoding="utf-8")
    load_dotenv_if_present()
    import os

    assert "DOTENV_SELECTION_TEST" not in os.environ
