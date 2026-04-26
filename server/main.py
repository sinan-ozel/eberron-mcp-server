import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field

mcp = FastMCP("eberron-mcp-server")

CAPITALS = {
    "breland": "Wroat",
    "cyre": "Metrol",
    "aundair": "Fairhaven",
    "karrnath": "Korth",
    "thrane": "Flamekeep",
    "darguun": "Rhukaan Draal",
    "droaam": "the Great Craag",
    "eldeen reaches": "Greenheart",
    "lhazaar principalities": "Regalport",
    "mror holds": "Krona Peak",
    "q'barra": "Newthrone",
    "talenta plains": "Gatherhold",
    "valenar": "Taer Valaestas",
    "zilargo": "Trolanport",
}


class GetCapitalInput(BaseModel):
    """Input model for get_capital tool."""

    nation: str = Field(
        json_schema_extra={
            "type": "string",
            "not": {"type": "null"},
            "description": "The name of the Eberron nation (case-insensitive). Valid nations: Breland, Cyre, Aundair, Karrnath, Thrane, Darguun, Droaam, Eldeen Reaches, Lhazaar Principalities, Mror Holds, Q'barra, Talenta Plains, Valenar, Zilargo.",
        }
    )


@mcp.tool()
def get_capital(input: GetCapitalInput) -> str:
    """Get the capital city of an Eberron nation.

    Returns the capital city name for the given nation in the Eberron
    campaign setting for Dungeons & Dragons 3.5/5e.

    Args:
        nation: The name of the Eberron nation (case-insensitive).
            Valid nations: Breland, Cyre, Aundair, Karrnath, Thrane,
            Darguun, Droaam, Eldeen Reaches, Lhazaar Principalities,
            Mror Holds, Q'barra, Talenta Plains, Valenar, Zilargo.

    Returns:
        The capital city of the specified nation.
        Returns "Unknown nation" if the nation is not found.
    """
    nation_lower = input.nation.lower().strip()
    if nation_lower in CAPITALS:
        return CAPITALS[nation_lower]
    for key in CAPITALS:
        if key.replace(" ", "-") == nation_lower or key.replace(
            " ", ""
        ) == nation_lower.replace("-", ""):
            return CAPITALS[key]
    return "Unknown nation"


async def generate_wiki_chunks(query: str):
    from urllib.parse import quote

    search_url = f"https://eberron.fandom.com/api/v1/Articles/Details?titles={quote(query)}"
    headers = {
        "User-Agent": "EberronMCP/0.1.0 (D&D Tool; +https://github.com/sinanozel/eberron-mcp-server)",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(headers=headers) as client:
        try:
            response = await client.get(search_url, follow_redirects=True)
            response.raise_for_status()
            html = response.text
            chunk_size = 500
            for i in range(0, len(html), chunk_size):
                yield html[i : i + chunk_size]
        except httpx.HTTPStatusError:
            yield "Error: Unable to fetch from Eberron Wiki. Please try a different query."


class SearchEberronWikiInput(BaseModel):
    """Input model for search_eberron_wiki tool."""

    query: str = Field(
        json_schema_extra={
            "type": "string",
            "not": {"type": "null"},
            "description": "The search query for the Eberron Fandom Wiki (e.g., 'House Cannith', 'Treaty of Throne').",
        }
    )


@mcp.tool()
async def search_eberron_wiki(input: SearchEberronWikiInput) -> str:
    """Search the Eberron Fandom Wiki for information.

    Performs a search on the Eberron Fandom Wiki and returns
    relevant content in streaming chunks. Use this tool to look up
    lore, places, characters, and other information about the
    Eberron Dungeons & Dragons campaign setting.

    Args:
        query: The search query (e.g., "House Cannith", "Treaty of Throne").

    Returns:
        HTML content from the Eberron Fandom Wiki search results,
        streamed in chunks.
    """
    result = ""
    async for chunk in generate_wiki_chunks(input.query):
        result += chunk
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--transport",
        default="streamable-http",
        choices=["streamable-http", "sse"],
        help="Transport type",
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport, host="0.0.0.0", port=8000)
