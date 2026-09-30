"""Unit tests for turning wiki pages into tool results.

Uses pages recorded from eberron.fandom.com (tests/wiki_mock/fixtures/), with
no network access.
"""

import json
from pathlib import Path

import pytest

from server.main import (
    MAX_FACT_VALUE_CHARS,
    MAX_FACTS,
    MAX_SOURCES,
    MAX_SUMMARY_CHARS,
    SOURCE_LABEL,
    build_result,
    choose_title,
)

PAGES = Path(__file__).parent / "wiki_mock" / "fixtures" / "parse"


def page(name: str):
    parsed = json.loads((PAGES / f"{name}.json").read_text())["parse"]
    return parsed["title"], parsed["wikitext"]


def result_for(name: str, other_matches=()):
    title, wikitext = page(name)
    return build_result(title, wikitext, list(other_matches))


def fact(result, field: str):
    matches = [f for f in result.facts if f.field == field]
    assert matches, f"no {field!r} fact in {[f.field for f in result.facts]}"
    return matches[0]


def test_nation_capital_comes_from_the_infobox():
    result = result_for("breland")
    assert result.found
    assert result.title == "Breland"
    assert fact(result, "capital").value == "Wroat"
    assert fact(result, "largest city").value == "Sharn"


def test_capital_is_spelled_as_on_the_wiki():
    assert fact(result_for("droaam"), "capital").value == "The Great Crag"


def test_named_refs_resolve_to_book_and_page():
    result = result_for("breland")
    assert "Eberron Campaign Setting, p. 142" in result.sources
    assert "Five Nations, p. 47" in result.sources
    assert "Rising from the Last War, p. 107" in result.sources


def test_fact_sources_come_from_inline_refs():
    result = result_for("breland")
    assert fact(result, "religion").sources == [
        "Eberron Campaign Setting, p. 145"
    ]
    assert fact(result, "population").sources == [
        "Eberron Campaign Setting, p. 142",
        "Five Nations, p. 47",
    ]


def test_summary_is_the_opening_prose_as_plain_text():
    result = result_for("wroat")
    assert result.summary.startswith(
        "Wroat is the capital city of the nation of Breland"
    )
    for leftover in ("[[", "{{", "<ref", "'''"):
        assert leftover not in result.summary
    assert "Five Nations, p. 60,61,62" in result.sources


def test_empty_and_image_fields_are_skipped():
    fields = {f.field for f in result_for("breland").facts}
    assert not fields & {"image", "caption", "name", "alignment", "size"}
    assert not any(field.endswith("refs") for field in fields)


def test_templates_render_as_text():
    result = result_for("breland")
    assert fact(result, "races").value.startswith("Humans 44%, Gnomes 14%")
    assert "formerly Eston" in fact(result_for("house_cannith"), "base").value


def test_organization_infobox_after_another_template():
    result = result_for("house_cannith")
    assert fact(result, "type").value == "Dragonmarked House"
    assert fact(result, "favored deity").sources == ["Exploring Eberron, p. 65"]
    assert result.summary.startswith("House Cannith is a human dragonmarked")


@pytest.mark.parametrize(
    "name", ["breland", "wroat", "droaam", "house_cannith"]
)
def test_results_stay_small(name):
    result = result_for(name, other_matches=["A", "B", "C", "D"])
    assert len(result.summary) <= MAX_SUMMARY_CHARS
    assert len(result.facts) <= MAX_FACTS
    assert all(len(f.value) <= MAX_FACT_VALUE_CHARS for f in result.facts)
    assert len(result.sources) <= MAX_SOURCES
    assert len(result.model_dump_json()) < 6000


def test_result_is_labelled_as_community_wiki():
    result = result_for("wroat")
    assert result.source == SOURCE_LABEL
    assert "community wiki" in result.source
    assert result.url.endswith("/wiki/Wroat")


def test_other_matches_exclude_the_chosen_page():
    result = result_for("breland", other_matches=["Breland", "Breland Ledger"])
    assert result.other_matches == ["Breland Ledger"]


@pytest.mark.parametrize(
    "query, titles, expected",
    [
        ("breland", ["Breland Ledger", "Breland"], "Breland"),
        ("capital of Breland", ["Wroat", "Breland"], "Wroat"),
        ("anything", [], None),
    ],
)
def test_choose_title(query, titles, expected):
    assert choose_title(query, titles) == expected
