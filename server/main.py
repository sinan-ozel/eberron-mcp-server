import logging
import os
import re
from html.parser import HTMLParser
from urllib.parse import quote

import httpx
import mwparserfromhell
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import FunctionTool
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from server import __version__


class _SuppressMCPUnionValidation(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not record.getMessage().startswith("Failed to validate request:")


logging.getLogger().addFilter(_SuppressMCPUnionValidation())

mcp = FastMCP("eberron-mcp-server")

# Overridable so tests can point the server at a local stand-in for the wiki.
WIKI_BASE_URL = os.environ.get(
    "EBERRON_WIKI_BASE_URL", "https://eberron.fandom.com"
).rstrip("/")
USER_AGENT = (
    f"EberronMCP/{__version__} "
    "(D&D tool; +https://github.com/sinan-ozel/eberron-mcp-server)"
)
HTTP_TIMEOUT_SECONDS = 15.0

SOURCE_LABEL = (
    "Eberron Wiki (eberron.fandom.com): a community wiki, not an official "
    "sourcebook. Book citations in `sources` are the ones the wiki gives."
)

# Keep every result small enough for a small local model's context window.
SEARCH_LIMIT = 5
MAX_SUMMARY_CHARS = 1200
MAX_FACTS = 20
MAX_FACT_VALUE_CHARS = 200
MAX_SOURCES = 8

# Infobox parameters that carry no fact of their own.
_SKIPPED_FIELDS = {"image", "caption", "name", "alt spelling"}
# Link namespaces whose text is not prose.
_NON_PROSE_LINK = re.compile(r"^\s*:?\s*(file|image|category)\s*:", re.I)


class LookupEberronWikiInput(BaseModel):
    """Input model for lookup_eberron_wiki tool."""

    query: str = Field(
        min_length=1,
        json_schema_extra={
            "type": "string",
            "not": {"type": "null"},
            "description": (
                "What to look up: a page title such as 'Breland' or "
                "'House Cannith', or a short question such as "
                "'capital of Breland'."
            ),
        },
    )


class WikiFact(BaseModel):
    """One field of the page's infobox."""

    field: str = Field(description="Infobox field, e.g. 'capital'.")
    value: str = Field(description="Field value as plain text.")
    sources: list[str] = Field(
        description="Book citations the wiki gives for this field, if any."
    )


class WikiLookupResult(BaseModel):
    """Result of lookup_eberron_wiki."""

    found: bool = Field(description="Whether a matching wiki page was found.")
    title: str = Field(description="Title of the page used, or ''.")
    url: str = Field(description="Link to the page, or ''.")
    source: str = Field(
        description="Where this information comes from and how to cite it."
    )
    summary: str = Field(description="Opening paragraph(s) of the page.")
    facts: list[WikiFact] = Field(
        description="Infobox fields (capital, region, ruler, ...)."
    )
    sources: list[str] = Field(
        description="Book citations for the page's opening and infobox."
    )
    other_matches: list[str] = Field(
        description="Other page titles that matched; look one up by title."
    )
    truncated: bool = Field(
        description="True if the summary or facts were cut to fit."
    )
    message: str = Field(description="Explanation when nothing was found.")


def _is_ref(node) -> bool:
    return str(node.tag).strip().lower() == "ref"


def _ref_name(tag) -> str:
    return str(tag.get("name").value).strip() if tag.has("name") else ""


def _citation(contents) -> str:
    """Turn a <ref>'s contents into a readable citation.

    ``{{Cite book/Five Nations|60}}`` becomes ``Five Nations, p. 60``.
    """
    for template in contents.filter_templates(recursive=False):
        name = str(template.name).strip()
        kind, _, title = name.partition("/")
        kind = kind.strip().lower()
        if kind not in ("cite book", "cite web") or not title.strip():
            continue
        title = title.strip()
        pages = ""
        if template.has("1"):
            pages = template.get("1").value.strip_code().strip()
        if kind == "cite book" and pages:
            return f"{title}, p. {pages}"
        return title
    return " ".join(contents.strip_code().split())


def _ref_definitions(code) -> dict[str, str]:
    """Map each named <ref> to its citation, across the whole page."""
    definitions = {}
    for tag in code.filter_tags(matches=_is_ref):
        name = _ref_name(tag)
        if name and tag.contents and str(tag.contents).strip():
            definitions.setdefault(name, _citation(tag.contents))
    return definitions


def _refs_in(code, definitions: dict[str, str]) -> list[str]:
    """Citations of every <ref> in ``code``, in order, without duplicates."""
    citations = []
    for tag in code.filter_tags(matches=_is_ref):
        if tag.contents and str(tag.contents).strip():
            citation = _citation(tag.contents)
        else:
            citation = definitions.get(_ref_name(tag), "")
        if citation and citation not in citations:
            citations.append(citation)
    return citations


def _render_template(template) -> str:
    """Plain-text rendering for the few templates that carry content."""
    name = str(template.name).strip().lower()
    if name == "percentage table":
        values = [p.value.strip_code().strip() for p in template.params]
        pairs = zip(values[0::2], values[1::2])
        return ", ".join(f"{label} {pct}%" for label, pct in pairs if label)
    if name == "former":
        return "formerly"
    return ""


def _plain_text(wikitext: str) -> str:
    """Wikitext to one line of plain text: refs, files and templates out."""
    code = mwparserfromhell.parse(wikitext)
    for tag in code.filter_tags(matches=_is_ref):
        code.remove(tag)
    for link in code.filter_wikilinks():
        if _NON_PROSE_LINK.match(str(link.title)):
            code.remove(link)
    for template in code.filter_templates(recursive=False):
        code.replace(template, _render_template(template))
    return " ".join(code.strip_code().split())


def _clip(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[: limit - 1].rstrip() + "…", True


def _page_url(title: str) -> str:
    return f"{WIKI_BASE_URL}/wiki/{quote(title.replace(' ', '_'))}"


def build_result(
    title: str, wikitext: str, other_matches: list[str]
) -> WikiLookupResult:
    """Build the tool result from a page's wikitext.

    No network access, so it can be unit-tested against recorded pages.
    """
    code = mwparserfromhell.parse(wikitext)
    definitions = _ref_definitions(code)
    truncated = False

    lead = code.get_sections(include_lead=True, flat=True)[0]
    infobox = None
    for template in lead.filter_templates(recursive=False):
        if sum(1 for p in template.params if p.showkey) >= 3:
            infobox = template
            break

    facts: list[WikiFact] = []
    infobox_sources: list[str] = []
    if infobox is not None:
        for param in infobox.params:
            field = str(param.name).strip()
            if not param.showkey or field.lower() in _SKIPPED_FIELDS:
                continue
            if field.lower().endswith("refs"):
                infobox_sources.extend(_refs_in(param.value, definitions))
                continue
            value = _plain_text(str(param.value))
            if not value:
                continue
            if len(facts) == MAX_FACTS:
                truncated = True
                break
            value, cut = _clip(value, MAX_FACT_VALUE_CHARS)
            truncated = truncated or cut
            facts.append(
                WikiFact(
                    field=field,
                    value=value,
                    sources=_refs_in(param.value, definitions),
                )
            )

    prose = mwparserfromhell.parse(str(lead))
    for template in prose.filter_templates(recursive=False):
        prose.remove(template)
    paragraphs = [
        _plain_text(chunk) for chunk in re.split(r"\n\s*\n", str(prose))
    ]
    summary, cut = _clip(
        "\n\n".join(p for p in paragraphs if p), MAX_SUMMARY_CHARS
    )
    truncated = truncated or cut

    sources = list(
        dict.fromkeys(_refs_in(prose, definitions) + infobox_sources)
    )
    if len(sources) > MAX_SOURCES:
        sources = sources[:MAX_SOURCES]
        truncated = True

    return WikiLookupResult(
        found=True,
        title=title,
        url=_page_url(title),
        source=SOURCE_LABEL,
        summary=summary,
        facts=facts,
        sources=sources,
        other_matches=[t for t in other_matches if t != title],
        truncated=truncated,
        message="",
    )


def choose_title(query: str, titles: list[str]) -> str | None:
    """Prefer an exact (case-insensitive) title match, else the top hit."""
    for title in titles:
        if title.strip().lower() == query.strip().lower():
            return title
    return titles[0] if titles else None


async def _api(client: httpx.AsyncClient, **params: str) -> dict:
    params.update(format="json", formatversion="2")
    try:
        response = await client.get(f"{WIKI_BASE_URL}/api.php", params=params)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise ToolError(
            f"Could not reach the Eberron wiki ({type(error).__name__}). "
            "Try again later."
        ) from error


async def _search(client: httpx.AsyncClient, query: str) -> list[str]:
    data = await _api(
        client,
        action="query",
        list="search",
        srsearch=query,
        srlimit=str(SEARCH_LIMIT),
    )
    return [hit["title"] for hit in data.get("query", {}).get("search", [])]


async def _wikitext(
    client: httpx.AsyncClient, title: str
) -> tuple[str, str] | None:
    data = await _api(
        client, action="parse", page=title, prop="wikitext", redirects="1"
    )
    if "error" in data:
        return None
    return data["parse"]["title"], data["parse"]["wikitext"]


async def lookup_eberron_wiki(
    input: LookupEberronWikiInput,
) -> WikiLookupResult:
    """Look something up on the Eberron Wiki (eberron.fandom.com).

    Searches the wiki, opens the best-matching page, and returns its opening
    paragraph, its infobox facts (capital, region, ruler, population, ...), and
    the sourcebook pages the wiki cites for them. Results are kept short;
    `other_matches` lists further pages to look up by exact title.

    The wiki is community-written. Say so when using it, cite the books in
    `sources`, and prefer official sourcebook data when you have it.
    """
    query = input.query.strip()
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=HTTP_TIMEOUT_SECONDS,
        follow_redirects=True,
    ) as client:
        titles = await _search(client, query)
        page = None
        chosen = choose_title(query, titles)
        if chosen is not None:
            page = await _wikitext(client, chosen)
        if page is None:
            # The search index can lag behind; an exact title may still exist.
            page = await _wikitext(client, query)

    if page is None:
        return WikiLookupResult(
            found=False,
            title="",
            url="",
            source=SOURCE_LABEL,
            summary="",
            facts=[],
            sources=[],
            other_matches=titles,
            truncated=False,
            message=f"No Eberron Wiki page matched {query!r}.",
        )
    title, wikitext = page
    return build_result(title, wikitext, titles)


LOOKUP_TITLE = "Look Up Eberron Wiki"
lookup_tool = FunctionTool.from_function(
    lookup_eberron_wiki,
    title=LOOKUP_TITLE,
    annotations=ToolAnnotations(
        title=LOOKUP_TITLE, readOnlyHint=True, openWorldHint=True
    ),
)
# pytest-mcp-tools calls each of these against the running server.
lookup_tool.parameters["examples"] = [
    {"input": {"query": "Breland"}},
    {"input": {"query": "capital of Breland"}},
    {"input": {"query": "House Cannith"}},
]
mcp.add_tool(lookup_tool)


# --- Keith Baker's blog ----------------------------------------------------

BLOG_BASE_URL = os.environ.get(
    "KEITH_BAKER_BLOG_BASE_URL", "https://keith-baker.com"
).rstrip("/")

BLOG_SOURCE_LABEL = (
    "Keith Baker's blog (keith-baker.com): Eberron's creator on how he runs "
    "Eberron. His own ideas, not official canon unless a sourcebook prints "
    "them; he says it may contradict canon."
)

BLOG_SEARCH_LIMIT = 5
MAX_PASSAGES = 3
MAX_PASSAGE_CHARS = 700
MAX_EXCERPT_CHARS = 300

# What a Patreon-locked post shows instead of its text.
_PATREON_LOCK = "you must be a member of keith"
# Too common in the blog to tell passages apart.
_STOPWORDS = {
    "a", "an", "and", "are", "about", "baker", "can", "do", "does", "eberron",
    "for", "from", "how", "in", "is", "keith", "of", "on", "the", "to",
    "what", "when", "where", "who", "why", "with",
}  # fmt: skip


class LookupKeithBakerBlogInput(BaseModel):
    """Input model for lookup_keith_baker_blog tool."""

    query: str = Field(
        min_length=1,
        json_schema_extra={
            "type": "string",
            "not": {"type": "null"},
            "description": (
                "Words to search Keith Baker's blog for, e.g. "
                "'warforged blood of vol' or 'lightning rail'. Use a few "
                "distinctive words; every word must appear in the post."
            ),
        },
    )


class BlogPost(BaseModel):
    """A blog post that matched the search."""

    title: str = Field(description="Post title.")
    date: str = Field(description="Publication date, YYYY-MM-DD.")
    url: str = Field(description="Link to the post.")
    excerpt: str = Field(description="Opening words of the post.")
    patreon_only: bool = Field(
        description="True if the post is locked to Keith's Patreon backers."
    )


class BlogLookupResult(BaseModel):
    """Result of lookup_keith_baker_blog."""

    found: bool = Field(description="Whether a readable post was found.")
    title: str = Field(description="Title of the post read, or ''.")
    url: str = Field(description="Link to the post read, or ''.")
    date: str = Field(description="Date of the post read, YYYY-MM-DD, or ''.")
    source: str = Field(
        description="Where this information comes from and how to cite it."
    )
    passages: list[str] = Field(
        description=(
            "Paragraphs of the post that best match the query, in order, "
            "each preceded by the reader's question it answers, if any."
        )
    )
    other_posts: list[BlogPost] = Field(
        description="Other matching posts, most relevant first."
    )
    truncated: bool = Field(description="True if passages were cut to fit.")
    message: str = Field(description="Explanation when nothing was read.")


class _Paragraphs(HTMLParser):
    """Collects the text of each block element (paragraph, list item...)."""

    _BLOCKS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"}
    _SKIP = {"script", "style"}

    def __init__(self):
        super().__init__()
        self.paragraphs: list[str] = []
        self._current: list[str] = []
        self._skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skipping += 1
        elif tag in self._BLOCKS:
            self._flush()

    def handle_endtag(self, tag):
        if tag in self._SKIP:
            self._skipping = max(0, self._skipping - 1)
        elif tag in self._BLOCKS:
            self._flush()

    def handle_data(self, data):
        if not self._skipping:
            self._current.append(data)

    def close(self):
        super().close()
        self._flush()

    def _flush(self):
        text = " ".join("".join(self._current).split())
        if text:
            self.paragraphs.append(text)
        self._current = []


def html_paragraphs(html: str) -> list[str]:
    """Plain-text paragraphs of a post's rendered HTML."""
    parser = _Paragraphs()
    parser.feed(html)
    parser.close()
    return parser.paragraphs


def _html_text(html: str) -> str:
    return " ".join(html_paragraphs(html))


def _is_locked(html: str) -> bool:
    return _PATREON_LOCK in _html_text(html).lower()


def _query_terms(query: str) -> list[str]:
    words = re.findall(r"[a-z0-9']+", query.lower())
    return list(dict.fromkeys(w for w in words if w not in _STOPWORDS))


def select_passages(
    paragraphs: list[str], query: str
) -> tuple[list[str], bool]:
    """Pick the paragraphs that match the most query terms.

    Each pick brings along the paragraph before it when that is a question,
    since the blog's Q&A posts put the reader's question just above the answer.
    With no match, the post's opening paragraphs are used.
    """
    terms = _query_terms(query)
    scores = [sum(t in p.lower() for t in terms) for p in paragraphs]
    best = max(scores, default=0)
    if best:
        picks = [i for i, s in enumerate(scores) if s == best][:MAX_PASSAGES]
    else:
        picks = list(range(min(MAX_PASSAGES, len(paragraphs))))

    passages, truncated = [], False
    for i in picks:
        text = paragraphs[i]
        before = paragraphs[i - 1] if i > 0 else ""
        if before.endswith("?") and i - 1 not in picks:
            text = f"{before}\n{text}"
        text, cut = _clip(text, MAX_PASSAGE_CHARS)
        truncated = truncated or cut
        passages.append(text)
    return passages, truncated


def blog_post(post: dict) -> BlogPost:
    """A search hit from the WordPress API as a BlogPost."""
    excerpt_html = post.get("excerpt", {}).get("rendered", "")
    excerpt = re.sub(
        r"\s*Continue reading\s*→?\s*$", "", _html_text(excerpt_html)
    )
    return BlogPost(
        title=_html_text(post["title"]["rendered"]),
        date=post.get("date", "")[:10],
        url=post["link"],
        excerpt=_clip(excerpt, MAX_EXCERPT_CHARS)[0],
        patreon_only=_PATREON_LOCK in excerpt.lower(),
    )


def build_blog_result(
    post: dict, query: str, others: list[BlogPost]
) -> BlogLookupResult:
    """Build the tool result from one post's API record (with content).

    No network access, so it can be unit-tested against recorded posts.
    """
    passages, truncated = select_passages(
        html_paragraphs(post["content"]["rendered"]), query
    )
    return BlogLookupResult(
        found=True,
        title=_html_text(post["title"]["rendered"]),
        url=post["link"],
        date=post.get("date", "")[:10],
        source=BLOG_SOURCE_LABEL,
        passages=passages,
        other_posts=others,
        truncated=truncated,
        message="",
    )


async def _blog_api(client: httpx.AsyncClient, path: str, **params: str):
    try:
        response = await client.get(
            f"{BLOG_BASE_URL}/wp-json/wp/v2/{path}", params=params
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise ToolError(
            f"Could not reach Keith Baker's blog ({type(error).__name__}). "
            "Try again later."
        ) from error


async def lookup_keith_baker_blog(
    input: LookupKeithBakerBlogInput,
) -> BlogLookupResult:
    """Search Keith Baker's blog (keith-baker.com) for what he has written.

    Keith Baker created Eberron; his blog answers readers' questions about it
    (Dragonmarks, Lightning Rounds, IFAQs). Opens the most relevant post that
    is not locked to Patreon and returns the paragraphs that best match the
    query, plus other matching posts.

    These are Keith's own ideas for his table, not official canon. Say so when
    using them, link the post, and prefer sourcebook text where it conflicts.
    """
    query = input.query.strip()
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=HTTP_TIMEOUT_SECONDS,
        follow_redirects=True,
    ) as client:
        hits = await _blog_api(
            client,
            "posts",
            search=query,
            orderby="relevance",
            per_page=str(BLOG_SEARCH_LIMIT),
            _fields="id,date,link,title,excerpt",
        )
        hits = hits or []
        posts = [blog_post(hit) for hit in hits]
        for hit, summary in zip(hits, posts):
            if summary.patreon_only:
                continue
            post = await _blog_api(
                client,
                f"posts/{hit['id']}",
                _fields="id,date,link,title,content",
            )
            if post is None or _is_locked(post["content"]["rendered"]):
                continue
            others = [p for p in posts if p is not summary]
            return build_blog_result(post, query, others)

    if posts:
        message = (
            f"Every post matching {query!r} is for Keith's Patreon backers "
            "only; their titles and links are in other_posts."
        )
    else:
        message = (
            f"No post on Keith Baker's blog matched {query!r}. Try fewer or "
            "different words."
        )
    return BlogLookupResult(
        found=False,
        title="",
        url="",
        date="",
        source=BLOG_SOURCE_LABEL,
        passages=[],
        other_posts=posts,
        truncated=False,
        message=message,
    )


BLOG_TITLE = "Look Up Keith Baker's Blog"
blog_tool = FunctionTool.from_function(
    lookup_keith_baker_blog,
    title=BLOG_TITLE,
    annotations=ToolAnnotations(
        title=BLOG_TITLE, readOnlyHint=True, openWorldHint=True
    ),
)
blog_tool.parameters["examples"] = [
    {"input": {"query": "warforged blood of vol"}},
    {"input": {"query": "lightning rail"}},
    {"input": {"query": "house sivis"}},
]
mcp.add_tool(blog_tool)


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
