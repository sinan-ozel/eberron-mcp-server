"""Unit tests for turning Keith Baker's blog posts into tool results.

Uses posts recorded from keith-baker.com (tests/wiki_mock/fixtures/blog/), with
no network access.
"""

import json
from pathlib import Path

from server.main import (
    BLOG_SOURCE_LABEL,
    MAX_EXCERPT_CHARS,
    MAX_PASSAGE_CHARS,
    MAX_PASSAGES,
    _is_locked,
    blog_post,
    build_blog_result,
    html_paragraphs,
    select_passages,
)

BLOG = Path(__file__).parent / "wiki_mock" / "fixtures" / "blog"


def post(post_id: int) -> dict:
    return json.loads((BLOG / "posts" / f"{post_id}.json").read_text())


def search(name: str) -> list[dict]:
    return json.loads((BLOG / "search" / f"{name}.json").read_text())


def test_paragraphs_are_plain_text_with_entities_decoded():
    paragraphs = html_paragraphs(post(42294)["content"]["rendered"])
    assert paragraphs[0].startswith("People ask me a lot of questions")
    assert "I’ve" in paragraphs[0]
    assert all("<" not in p and "&#" not in p for p in paragraphs)


def test_passages_answer_the_query_with_the_question_above():
    result = build_blog_result(post(39909), "lightning rail", [])
    assert result.found is True
    assert (
        result.title
        == "Lightning Round 2/26/18: Languages, Elementals and Pirates!"
    )
    assert result.date == "2018-02-26"
    assert result.source == BLOG_SOURCE_LABEL
    assert 0 < len(result.passages) <= MAX_PASSAGES
    assert all("lightning rail" in p.lower() for p in result.passages)


def test_question_already_picked_is_not_repeated():
    paragraphs = ["Intro.", "Is the sky blue?", "Yes, the sky is blue."]
    passages, truncated = select_passages(paragraphs, "sky blue")
    assert passages == ["Is the sky blue?", "Yes, the sky is blue."]
    assert truncated is False


def test_answer_brings_its_question_along():
    paragraphs = ["Intro.", "What colour is it?", "The sky is blue."]
    passages, _ = select_passages(paragraphs, "sky")
    assert passages == ["What colour is it?\nThe sky is blue."]


def test_no_matching_paragraph_falls_back_to_the_opening():
    paragraphs = ["One.", "Two.", "Three.", "Four."]
    passages, _ = select_passages(paragraphs, "warforged")
    assert passages == paragraphs[:MAX_PASSAGES]


def test_long_passages_are_clipped():
    passages, truncated = select_passages(["word " * 500], "word")
    assert truncated is True
    assert len(passages[0]) <= MAX_PASSAGE_CHARS


def test_patreon_locked_posts_are_detected():
    assert _is_locked(post(98543)["content"]["rendered"])
    assert not _is_locked(post(98554)["content"]["rendered"])


def test_search_hits_flag_patreon_posts_and_trim_excerpts():
    hits = {p.title: p for p in map(blog_post, search("house_sivis"))}
    locked = hits["House Sivis and the Mark of Scribing"]
    public = hits["Excerpt: House Sivis and the Mark of Scribing"]
    assert locked.patreon_only is True
    assert public.patreon_only is False
    assert public.url == "https://keith-baker.com/excerpt-house-sivis/"
    assert public.date == "2025-12-24"
    assert "Continue reading" not in public.excerpt
    assert len(public.excerpt) <= MAX_EXCERPT_CHARS
