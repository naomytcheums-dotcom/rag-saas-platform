"""Spec 3.4.5 -- synonym expansion of the question before retrieval."""

from api.services.query_rewriting import expand_with_synonyms


def test_built_in_synonyms_are_appended_after_the_original_query():
    result = expand_with_synonyms("what is the price")
    assert result.startswith("what is the price ")
    assert "cost" in result and "fee" in result


def test_french_terms_are_expanded_too():
    assert "tarif" in expand_with_synonyms("quel est le prix")


def test_a_query_without_known_terms_is_unchanged():
    assert expand_with_synonyms("quarterly planning offsite") == "quarterly planning offsite"
    assert expand_with_synonyms("") == ""


def test_custom_synonyms_extend_and_override_the_built_in_table():
    custom = {"widget": ["gadget", "thingamajig"], "price": ["tariff"]}
    result = expand_with_synonyms("widget price", custom)
    assert "gadget" in result and "thingamajig" in result and "tariff" in result
    assert "cost" not in result  # the organization's own entry replaced the built-in one


def test_synonyms_already_in_the_query_are_not_repeated_and_the_total_is_capped():
    assert expand_with_synonyms("price cost").count("cost") == 1
    long = {f"t{i}": [f"s{i}a", f"s{i}b"] for i in range(20)}
    expanded = expand_with_synonyms(" ".join(long), long, max_additions=4)
    assert len(expanded.split()) == 20 + 4


async def test_the_settings_endpoint_validates_the_synonym_table(client, db_session):
    token = (await client.post("/auth/register", json={"email": "syn-owner@example.com", "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    org = (await client.post("/organizations", json={"name": "Syn Org"}, headers=h)).json()
    url = f"/organizations/{org['id']}/settings"
    ok = await client.patch(url, json={"query_expansion_enabled": True, "query_synonyms": {"contract": ["agreement", "deal"]}}, headers=h)
    assert ok.status_code == 200 and ok.json()["query_synonyms"] == {"contract": ["agreement", "deal"]}
    assert (await client.patch(url, json={"query_synonyms": {"x": ["a"] * 21}}, headers=h)).status_code == 422
    assert (await client.patch(url, json={"query_synonyms": {"": ["a"]}}, headers=h)).status_code == 422
    assert (await client.patch(url, json={"query_synonyms": {"y" * 65: ["a"]}}, headers=h)).status_code == 422
