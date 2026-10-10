"""SQuAD 2.0 adapter and answer-level metrics (Lot E). The fixture below is a SYNTHETIC mini file written for these tests: it is NOT SQuAD
data and no number produced from it is a benchmark result."""

import copy

import pytest

from api.services.squad_eval import (
    ANSWERABLE_CATEGORY, UNANSWERABLE_CATEGORY, SquadFormatError, best_over_golds, citation_support, context_key, corpus_documents,
    exact_match, f1_score, load_squad, normalize_answer, questions_for_import, score_predictions,
)

SYNTHETIC = {
    "version": "v2.0",
    "data": [
        {"title": "Synthetic Rivers", "paragraphs": [
            {"context": "The River Alpha is 120 kilometres long and flows into the Beta Sea.", "qas": [
                {"id": "q1", "question": "How long is the River Alpha?", "is_impossible": False, "answers": [{"text": "120 kilometres", "answer_start": 19}, {"text": "120 kilometres long", "answer_start": 19}]},
                {"id": "q2", "question": "Where does the River Alpha flow into?", "is_impossible": False, "answers": [{"text": "the Beta Sea", "answer_start": 55}]},
                {"id": "q3", "question": "Who built the River Alpha dam?", "is_impossible": True, "answers": [], "plausible_answers": [{"text": "nobody", "answer_start": 0}]},
            ]},
        ]},
        {"title": "Synthetic Cities", "paragraphs": [
            {"context": "Gamma City was founded in 1850 and has a famous clock tower.", "qas": [
                {"id": "q4", "question": "When was Gamma City founded?", "is_impossible": False, "answers": [{"text": "1850", "answer_start": 25}]},
            ]},
        ]},
    ],
}


def test_the_synthetic_file_loads_with_every_id_and_every_gold_answer():
    corpus = load_squad(SYNTHETIC)
    assert [q.squad_id for q in corpus.questions] == ["q1", "q2", "q3", "q4"]
    assert corpus.questions[0].gold_answers == ("120 kilometres", "120 kilometres long")
    assert corpus.questions[2].is_impossible and corpus.questions[2].gold_answers == ()
    assert len(corpus.contexts) == 2


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d.update(version="v1.1"), "v2"),
    (lambda d: d.pop("data"), "data"),
    (lambda d: d["data"][0]["paragraphs"][0]["qas"].append(dict(d["data"][0]["paragraphs"][0]["qas"][0])), "duplicate"),
    (lambda d: d["data"][0]["paragraphs"][0]["qas"][2].update(answers=[{"text": "x", "answer_start": 0}]), "is_impossible=true"),
    (lambda d: d["data"][0]["paragraphs"][0]["qas"][0].update(answers=[]), "without a gold answer"),
    (lambda d: d["data"][0]["paragraphs"][0].update(context="  "), "no context"),
    (lambda d: d["data"][0]["paragraphs"][0]["qas"][0].update(id=""), "no id"),
])
def test_a_malformed_file_is_refused_not_silently_repaired(mutate, message):
    data = copy.deepcopy(SYNTHETIC)
    mutate(data)
    with pytest.raises(SquadFormatError, match=message):
        load_squad(data)


def test_each_distinct_context_becomes_one_stable_document():
    docs = corpus_documents(load_squad(SYNTHETIC))
    assert len(docs) == 2 and all(d["name"] == f"squad2::{d['key']}" for d in docs)
    assert docs[0]["key"] == corpus_documents(load_squad(SYNTHETIC))[0]["key"]  # stable across runs
    assert context_key("T", "c") != context_key("T", "d") and context_key("T", "c") != context_key("U", "c")


def test_dataset_rows_point_to_the_real_document_ids_and_unanswerable_rows_expect_nothing():
    corpus = load_squad(SYNTHETIC)
    ids = {d["key"]: f"00000000-0000-4000-8000-00000000000{n}" for n, d in enumerate(corpus_documents(corpus), start=1)}
    rows = questions_for_import(corpus, ids)
    assert rows[0]["expected_documents"] == [{"document_id": ids[corpus.questions[0].context_key], "relevance_score": 1.0}]
    assert rows[0]["expected_answer"] == "120 kilometres" and rows[0]["category"] == ANSWERABLE_CATEGORY
    assert rows[2]["expected_documents"] == [] and rows[2]["expected_answer"] is None and rows[2]["category"] == UNANSWERABLE_CATEGORY
    assert rows[3]["expected_documents"][0]["document_id"] == ids[corpus.questions[3].context_key]


def test_a_context_that_was_not_ingested_is_an_error_not_a_dropped_question():
    corpus = load_squad(SYNTHETIC)
    only_first = {corpus.questions[0].context_key: "00000000-0000-4000-8000-000000000001"}
    with pytest.raises(SquadFormatError, match="was not ingested"):
        questions_for_import(corpus, only_first)


def test_official_normalization_drops_case_punctuation_and_articles():
    assert normalize_answer("The  Beta Sea!") == "beta sea"
    assert exact_match("the beta sea", "Beta Sea.") == 1.0 and exact_match("beta", "beta sea") == 0.0


def test_token_f1_values():
    assert f1_score("cat sat", "cat sits") == pytest.approx(0.5)
    assert f1_score("a b c", "a b c") == 1.0 and f1_score("a", "b") == 0.0
    assert f1_score("", "") == 1.0 and f1_score("", "x") == 0.0 and f1_score("x", "") == 0.0  # "no answer" semantics of SQuAD 2.0


def test_the_best_score_over_every_gold_answer_is_taken():
    assert best_over_golds(exact_match, "120 kilometres long", ["120 kilometres", "120 kilometres long"]) == 1.0
    assert best_over_golds(exact_match, "", []) == 1.0  # no gold = the right answer is no answer


def test_a_citation_counts_only_if_the_cited_passage_contains_the_answer():
    right_doc_wrong_passage = "The River Alpha flows through three provinces."
    assert citation_support([right_doc_wrong_passage], ["120 kilometres"]) is False
    assert citation_support(["The River Alpha is 120 kilometres long."], ["120 kilometres"]) is True
    assert citation_support([], ["120 kilometres"]) is False and citation_support(["anything"], []) is False


def test_scores_and_abstention_metrics_are_computed_by_hand_checked_values():
    corpus = load_squad(SYNTHETIC)
    predictions = {
        "q1": {"answer": "120 kilometres", "abstained": False},   # exact
        "q2": {"answer": "", "abstained": True},                  # abstained although answerable: a false abstention
        "q3": {"answer": "", "abstained": True},                  # correct abstention
        "q4": {"answer": "in 1851", "abstained": False},          # wrong
    }
    scores = score_predictions(corpus, predictions)
    assert scores["questions"] == 4 and scores["answerable"] == 3 and scores["unanswerable"] == 1
    assert scores["HasAns_exact"] == pytest.approx(1 / 3) and scores["NoAns_accuracy"] == 1.0
    assert scores["exact"] == pytest.approx((1 + 1) / 4)
    assert scores["abstention_precision"] == pytest.approx(0.5)  # 2 abstentions, 1 right
    assert scores["abstention_recall"] == 1.0
    assert scores["abstention_f1"] == pytest.approx(2 * 0.5 * 1.0 / 1.5)


def test_a_missing_prediction_is_an_error_never_scored_as_an_abstention():
    corpus = load_squad(SYNTHETIC)
    with pytest.raises(SquadFormatError, match="no prediction"):
        score_predictions(corpus, {"q1": {"answer": "x", "abstained": False}})
