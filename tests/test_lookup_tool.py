"""End-to-end calls to the running server (tests/docker-compose.yaml).

The server is pointed at wiki-mock, which serves recorded wiki responses.
pytest-mcp-tools covers the protocol and schema checks; these check that the
answers are right.
"""

import asyncio

import pytest
from fastmcp import Client

SERVER_URL = "http://mcp-server:8000/mcp"


def lookup(query: str) -> dict:
    async def call():
        async with Client(SERVER_URL) as client:
            result = await client.call_tool(
                "lookup_eberron_wiki", {"input": {"query": query}}
            )
            return result.structured_content

    return asyncio.run(call())


def facts(result: dict) -> dict:
    return {f["field"]: f["value"] for f in result["facts"]}


def test_exactly_the_lookup_tools_are_exposed():
    async def names():
        async with Client(SERVER_URL) as client:
            return [tool.name for tool in await client.list_tools()]

    assert sorted(asyncio.run(names())) == [
        "lookup_eberron_wiki",
        "lookup_keith_baker_blog",
    ]


def test_capital_question_lands_on_the_capital_city():
    result = lookup("capital of Breland")
    assert result["found"] is True
    assert result["title"] == "Wroat"
    assert "capital city of the nation of Breland" in result["summary"]
    assert "Breland" in result["other_matches"]


def test_exact_title_wins_over_top_search_hit():
    result = lookup("breland")
    assert result["title"] == "Breland"
    assert facts(result)["capital"] == "Wroat"
    assert "Eberron Campaign Setting, p. 142" in result["sources"]


def test_unknown_query_reports_not_found():
    result = lookup("Nothing on the wiki matches this")
    assert result["found"] is False
    assert result["facts"] == []
    assert "No Eberron Wiki page matched" in result["message"]


@pytest.mark.parametrize("query", ["Droaam", "House Cannith"])
def test_every_result_says_it_is_the_community_wiki(query):
    assert "community wiki" in lookup(query)["source"]
