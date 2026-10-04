"""End-to-end calls to lookup_keith_baker_blog on the running server.

The server is pointed at wiki-mock, which also serves recorded responses from
keith-baker.com's WordPress API.
"""

import asyncio

from fastmcp import Client

SERVER_URL = "http://mcp-server:8000/mcp"


def lookup(query: str) -> dict:
    async def call():
        async with Client(SERVER_URL) as client:
            result = await client.call_tool(
                "lookup_keith_baker_blog", {"input": {"query": query}}
            )
            return result.structured_content

    return asyncio.run(call())


def test_reads_the_most_relevant_post():
    result = lookup("warforged blood of vol")
    assert result["found"] is True
    assert result["title"] == "iFAQ: Warforged, Blood, and the Blood of Vol"
    assert result["url"] == "https://keith-baker.com/ifaq-warforgedbov/"
    assert any("Blood of Vol" in p for p in result["passages"])
    assert "not official canon" in result["source"]
    assert result["title"] not in [p["title"] for p in result["other_posts"]]


def test_q_and_a_passages_match_the_query():
    result = lookup("lightning rail")
    assert result["date"] == "2018-02-26"
    assert all("lightning rail" in p.lower() for p in result["passages"])


def test_patreon_posts_are_listed_but_not_read():
    result = lookup("house sivis")
    assert result["title"] == "Excerpt: House Sivis and the Mark of Scribing"
    locked = [p for p in result["other_posts"] if p["patreon_only"]]
    assert "House Sivis and the Mark of Scribing" in [
        p["title"] for p in locked
    ]


def test_unknown_query_reports_not_found():
    result = lookup("nothing on the blog matches this")
    assert result["found"] is False
    assert result["passages"] == []
    assert "No post on Keith Baker's blog matched" in result["message"]
