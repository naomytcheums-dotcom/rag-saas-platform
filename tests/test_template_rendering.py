"""Shared {{var}} template substitution, extracted for Partie 5.4.3.
Reused by every real workflow block renderer (Parties 5.4.3-5.4.11)."""

from api.services.template_rendering import find_placeholders, render_template


def test_render_template_substitutes_known_variables():
    assert render_template("Hello {{name}}!", {"name": "Ada"}) == "Hello Ada!"


def test_render_template_leaves_a_missing_variable_as_a_literal_placeholder():
    """Validation criterion: robustesse -- ne jamais effacer silencieusement."""
    assert render_template("Hello {{name}}!", {}) == "Hello {{name}}!"


def test_render_template_stringifies_non_string_values():
    assert render_template("Count: {{n}}", {"n": 5}) == "Count: 5"


def test_render_template_resolves_a_real_dotted_nested_path():
    """Validation criterion: Partie 5.4.10/5.4.11's own {{user.email}}."""
    assert render_template("Hi {{user.name}}, {{user.email}}", {"user": {"name": "Ada", "email": "ada@example.com"}}) == "Hi Ada, ada@example.com"


def test_render_template_leaves_a_missing_dotted_path_as_a_literal_placeholder():
    assert render_template("Hi {{user.name}}", {"user": {}}) == "Hi {{user.name}}"
    assert render_template("Hi {{user.name}}", {}) == "Hi {{user.name}}"


def test_render_template_rejects_no_real_code_execution_via_format():
    """Validation criterion: sécurité -- pas d'injection via format_map."""
    payload = "{0.__class__.__init__.__globals__}"
    assert render_template(payload, {}) == payload


def test_find_placeholders_extracts_every_real_variable_name():
    assert find_placeholders("{{a}} and {{b}} and {{a}}") == ["a", "b", "a"]
