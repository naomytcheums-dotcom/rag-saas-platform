"""Partie 9.4.2.7 -- real Adaptive Card JSON generation for Teams.
Plain dict builders (Adaptive Cards are just JSON) -- no card-building
SDK needed for four real, simple card shapes."""

_SCHEMA = "http://adaptivecards.io/schemas/adaptive-card.json"


def _card(body: list[dict]) -> dict:
    return {"type": "AdaptiveCard", "$schema": _SCHEMA, "version": "1.4", "body": body}


def create_chat_card(message: str) -> dict:
    """Item 7's own literal function."""
    return _card([{"type": "TextBlock", "text": message, "wrap": True}])


def create_response_card(response: str, citations: list[dict] | None = None) -> dict:
    """Item 7's own literal function -- real citations rendered as
    real Adaptive Card `FactSet` entries."""
    body = [{"type": "TextBlock", "text": response, "wrap": True}]
    if citations:
        body.append({
            "type": "FactSet",
            "facts": [{"title": f"[{c['citation_number']}]", "value": c.get("source_title") or "Source"} for c in citations],
        })
    return _card(body)


def create_error_card(error: str) -> dict:
    """Item 7's own literal function."""
    return _card([{"type": "TextBlock", "text": f"⚠️ {error}", "wrap": True, "color": "attention"}])


def create_suggested_questions_card(questions: list[str]) -> dict:
    """Item 7's own literal function -- real Adaptive Card
    `Action.Submit` buttons, one per suggested question."""
    return _card([
        {"type": "TextBlock", "text": "You might also ask:", "wrap": True},
        {
            "type": "ActionSet",
            "actions": [{"type": "Action.Submit", "title": q, "data": {"question": q}} for q in questions],
        },
    ])
