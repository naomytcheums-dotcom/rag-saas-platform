"""Specs 11.2.x / 15.2.x -- usage insights, gap reports, feedback analysis and feedback-to-evaluation cases. Fast SQLite suite."""

import datetime as dt
import uuid

from sqlalchemy import select

from api.models.citation import Citation
from api.models.conversation import Conversation, ConversationMessage
from api.models.document import Document
from api.models.evaluation import EvaluationQuestion
from api.models.message_actions import MessageFeedback
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.response import Response
from api.models.user import User
from api.services import insights


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ pure functions

def test_refusals_are_detected_in_several_languages():
    for text in ("I don't know the answer", "Je ne sais pas.", "No lo sé", "Ich weiß nicht", "Não sei dizer"):
        assert insights.is_refusal(text)
    assert not insights.is_refusal("The contract ends on 31 December.")
    assert not insights.is_refusal(None)


def test_most_asked_groups_case_and_punctuation_variants():
    pairs = [{"question": q} for q in ("How do I reset my password?", "how do i reset my password", "What are your hours?")]
    top = insights.most_asked(pairs, 5)
    assert top[0]["count"] == 2 and top[1]["count"] == 1


def test_clusters_group_similar_questions_and_keep_distinct_ones_apart():
    questions = ["How to reset my password", "reset password how", "Reset the password please", "What is the refund policy", "refund policy details"]
    clusters = insights.cluster_questions(questions)
    sizes = sorted(c["size"] for c in clusters)
    assert sizes == [2, 3]
    assert any("password" in c["keywords"] for c in clusters) and any("refund" in c["keywords"] for c in clusters)


def test_worst_documents_need_enough_citations():
    usage = [
        {"document_id": 1, "name": "a", "citations": 5, "average_relevance": 0.2},
        {"document_id": 2, "name": "b", "citations": 1, "average_relevance": 0.05},
        {"document_id": 3, "name": "c", "citations": 4, "average_relevance": 0.9},
    ]
    assert [d["name"] for d in insights.worst_documents(usage)] == ["a", "c"]
    assert [d["name"] for d in insights.top_documents(usage, 1)] == ["a"]


def test_feedback_reasons_map_to_eval_lab_categories():
    assert insights.classify_feedback_reason("Hallucination") == "GENERATION_HALLUCINATION"
    assert insights.classify_feedback_reason("incomplete answer") == "GENERATION_INCOMPLETE"
    assert insights.classify_feedback_reason("wrong source") == "RETRIEVAL_FAILURE"
    assert insights.classify_feedback_reason(None, "meh") == "OTHER"


# ------------------------------------------------------------------ endpoints

async def _org(client, db_session, email="insights-owner@example.com"):
    token = (await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    owner = await db_session.scalar(select(User).where(User.email == email))
    org = (await client.post("/organizations", json={"name": "Insights Org"}, headers=_h(token))).json()
    return token, owner, uuid.UUID(org["id"])


async def _qa(db_session, owner, org_id, question, answer, rating=None, reason=None, correction=None):
    conv = Conversation(agent_id="a1", user_id=owner.id, organization_id=org_id, title="t")
    db_session.add(conv)
    await db_session.flush()
    now = dt.datetime.now(dt.timezone.utc)
    db_session.add(ConversationMessage(conversation_id=conv.id, role="user", content=question, created_at=now - dt.timedelta(seconds=2)))
    reply = ConversationMessage(conversation_id=conv.id, role="assistant", content=answer, created_at=now - dt.timedelta(seconds=1))
    db_session.add(reply)
    await db_session.flush()
    if rating:
        db_session.add(MessageFeedback(message_id=reply.id, user_id=owner.id, rating=rating, reason=reason, correction=correction))
    await db_session.commit()
    return reply


async def test_endpoints_report_most_asked_failures_gaps_and_success_rate(client, db_session):
    token, owner, org_id = await _org(client, db_session)
    for _ in range(3):
        await _qa(db_session, owner, org_id, "How do I export my invoices?", "I don't know.")
    await _qa(db_session, owner, org_id, "What is the refund policy?", "Refunds are possible within 30 days.")
    base = f"/organizations/{org_id}/insights"
    assert (await client.get(f"{base}/most-asked", headers=_h(token))).json()["items"][0] == {"question": "How do I export my invoices?", "count": 3}
    failed = (await client.get(f"{base}/failed-questions", headers=_h(token))).json()["items"]
    assert len(failed) == 3 and failed[0]["reasons"] == ["no_answer"]
    rate = (await client.get(f"{base}/retrieval-success", headers=_h(token))).json()
    assert rate["answered_questions"] == 4 and rate["refused"] == 3 and rate["success_rate"] == 0.25
    gaps = (await client.get(f"{base}/knowledge-gaps", headers=_h(token))).json()["items"]
    assert gaps and gaps[0]["size"] == 3 and "invoices" in gaps[0]["keywords"]
    db_session.add(Document(organization_id=org_id, name="Invoices FAQ.pdf", file_type="pdf", file_size=1, status="ready", file_key="k/x.pdf"))
    await db_session.commit()
    report = (await client.get(f"{base}/documentation-gaps", headers=_h(token))).json()["items"]
    assert report[0]["times_asked"] == 3 and report[0]["status"] == "partially_covered" and report[0]["related_documents"] == ["Invoices FAQ.pdf"]
    clusters = (await client.get(f"{base}/question-clusters", headers=_h(token))).json()["items"]
    assert clusters[0]["size"] == 3


async def test_document_usage_reports_top_and_worst_documents(client, db_session):
    token, owner, org_id = await _org(client, db_session, "insights-docs@example.com")
    good = Document(organization_id=org_id, name="Handbook.pdf", file_type="pdf", file_size=1, status="ready", file_key="k/x.pdf")
    noisy = Document(organization_id=org_id, name="Misc.pdf", file_type="pdf", file_size=1, status="ready", file_key="k/x.pdf")
    db_session.add_all([good, noisy])
    await db_session.flush()
    response = Response(organization_id=org_id, query="q", answer="a", created_by=owner.id)
    db_session.add(response)
    await db_session.flush()
    for i, (doc, score) in enumerate([(good, 0.9), (good, 0.8), (good, 0.85), (noisy, 0.1), (noisy, 0.2)]):
        db_session.add(Citation(response_id=response.id, document_id=doc.id, text="t", relevance_score=score, citation_number=i + 1))
    await db_session.commit()
    base = f"/organizations/{org_id}/insights/documents"
    assert (await client.get(f"{base}/top", headers=_h(token))).json()["items"][0]["name"] == "Handbook.pdf"
    assert (await client.get(f"{base}/worst", headers=_h(token))).json()["items"][0]["name"] == "Misc.pdf"


async def test_feedback_analysis_and_conversion_into_evaluation_cases(client, db_session):
    token, owner, org_id = await _org(client, db_session, "insights-feedback@example.com")
    await _qa(db_session, owner, org_id, "Who signs the contract?", "Maybe the CEO.", rating="negative", reason="hallucination", correction="The CFO signs.")
    await _qa(db_session, owner, org_id, "Where is the policy?", "Somewhere.", rating="negative", reason="wrong source")
    analysis = (await client.get(f"/organizations/{org_id}/feedback/analysis", headers=_h(token))).json()
    assert analysis == {"negative_feedback": 2, "by_category": {"GENERATION_HALLUCINATION": 1, "RETRIEVAL_FAILURE": 1}}
    dataset = (await client.post(f"/organizations/{org_id}/datasets", json={"name": "from feedback"}, headers=_h(token))).json()
    url = f"/organizations/{org_id}/feedback/to-evaluation"
    result = (await client.post(url, json={"dataset_id": dataset["id"], "only_with_correction": True}, headers=_h(token))).json()
    assert result == {"created": 1, "skipped": 1}
    again = (await client.post(url, json={"dataset_id": dataset["id"]}, headers=_h(token))).json()
    assert again["created"] == 1  # the second negative answer now; the first question already exists
    questions = (await db_session.scalars(select(EvaluationQuestion).order_by(EvaluationQuestion.created_at))).all()
    assert {q.question for q in questions} == {"Who signs the contract?", "Where is the policy?"}
    assert next(q for q in questions if q.question.startswith("Who")).expected_answer == "The CFO signs."


async def test_feedback_accepts_a_proposed_correction(client, db_session):
    token, owner, org_id = await _org(client, db_session, "insights-correction@example.com")
    reply = await _qa(db_session, owner, org_id, "q?", "a")
    r = await client.post(f"/messages/{reply.id}/feedback", json={"rating": "negative", "reason": "wrong", "correction": "The right answer"}, headers=_h(token))
    assert r.status_code == 200 and r.json()["correction"] == "The right answer"


async def test_insights_are_isolated_per_organization_and_closed_to_plain_members(client, db_session):
    token, owner, org_id = await _org(client, db_session, "insights-iso@example.com")
    await _qa(db_session, owner, org_id, "Secret question?", "I don't know")
    other_token, other_owner, other_org = await _org(client, db_session, "insights-other@example.com")
    assert (await client.get(f"/organizations/{other_org}/insights/most-asked", headers=_h(other_token))).json()["items"] == []
    assert (await client.get(f"/organizations/{org_id}/insights/most-asked", headers=_h(other_token))).status_code in (403, 404)
    member_token = (await client.post("/auth/register", json={"email": "insights-member@example.com", "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    member = await db_session.scalar(select(User).where(User.email == "insights-member@example.com"))
    db_session.add(OrganizationMember(organization_id=org_id, user_id=member.id, role=OrganizationRole.member))
    await db_session.commit()
    assert (await client.get(f"/organizations/{org_id}/insights/most-asked", headers=_h(member_token))).status_code == 403
    assert other_owner and token


async def test_cost_per_user_and_per_answer_come_from_credit_consumption(client, db_session):
    from api.models.billing import CreditTransaction, CreditTransactionType

    token, owner, org_id = await _org(client, db_session, "insights-cost@example.com")
    other = await db_session.scalar(select(User).where(User.email == "insights-cost@example.com"))
    for amount in (-4, -6, -2):
        db_session.add(CreditTransaction(organization_id=org_id, type=CreditTransactionType.consume, amount=amount, balance_after=100, reason="chat", user_id=other.id))
    db_session.add(CreditTransaction(organization_id=org_id, type=CreditTransactionType.purchase, amount=500, balance_after=600, reason="pack", user_id=other.id))
    await db_session.commit()
    per_user = (await client.get(f"/organizations/{org_id}/insights/cost-per-user", headers=_h(token))).json()["items"]
    assert per_user == [{"user_id": str(owner.id), "email": "insights-cost@example.com", "operations": 3, "credits_spent": 12}]
    per_answer = (await client.get(f"/organizations/{org_id}/insights/cost-per-answer", headers=_h(token))).json()
    assert per_answer == {"credits_spent": 12, "billed_operations": 3, "credits_per_operation": 4.0}
    empty_token, _o, empty_org = await _org(client, db_session, "insights-cost-empty@example.com")
    assert (await client.get(f"/organizations/{empty_org}/insights/cost-per-answer", headers=_h(empty_token))).json()["credits_per_operation"] is None


async def test_profile_stores_a_job_title(client, db_session):
    token, _owner, _org_id = await _org(client, db_session, "insights-title@example.com")
    r = await client.patch("/account/profile", json={"job_title": "  Head of Legal "}, headers=_h(token))
    assert r.status_code == 200 and r.json()["job_title"] == "Head of Legal"
    assert (await client.get("/account/me", headers=_h(token))).json()["job_title"] == "Head of Legal"
    cleared = await client.patch("/account/profile", json={"job_title": "   "}, headers=_h(token))
    assert cleared.json()["job_title"] is None
    assert (await client.patch("/account/profile", json={"job_title": "x" * 201}, headers=_h(token))).status_code == 422
