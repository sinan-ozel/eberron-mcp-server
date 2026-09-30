# Tools

## lookup_eberron_wiki

Looks something up on the [Eberron Wiki](https://eberron.fandom.com) and returns a short, cited answer.

It searches the wiki, opens the best-matching page (an exact title match wins over the top search hit), and returns:

- the page's opening paragraph(s), as plain text;
- its infobox fields (capital, region, ruler, population, ...), each with the sourcebook pages the wiki cites for it;
- the sourcebook pages cited for the page as a whole;
- other matching page titles, to look up next.

Results are capped (summary length, number of facts, value length, number of sources) so a single call can't fill a small model's context window. `truncated` says when something was cut.

!!! warning "Community source"
    The Eberron Wiki is community-written, not an official sourcebook. Every result says so in `source`. The book citations are the ones the wiki gives: cite them, and prefer official sourcebook data when you have it.

**Input**

| Field | Type | Description |
|---|---|---|
| `input.query` | `string` | A page title (`"Breland"`, `"House Cannith"`) or a short question (`"capital of Breland"`). Null and empty values are rejected. |

**Output**

| Field | Type | Description |
|---|---|---|
| `found` | `boolean` | Whether a matching page was found. |
| `title` | `string` | Title of the page used, or `""`. |
| `url` | `string` | Link to the page, or `""`. |
| `source` | `string` | Where the information comes from, and how to cite it. |
| `summary` | `string` | Opening paragraph(s) of the page. |
| `facts` | `array` of `{field, value, sources}` | Infobox fields, each with its own citations. |
| `sources` | `array` of `string` | Citations for the opening and the infobox, e.g. `"Eberron Campaign Setting, p. 142"`. |
| `other_matches` | `array` of `string` | Other matching page titles. |
| `truncated` | `boolean` | True if anything was cut to fit. |
| `message` | `string` | Explanation when nothing was found. |

If the wiki can't be reached, the call fails with a tool error.

**Example**

```
Input:  { "input": { "query": "capital of Breland" } }
Output: {
  "found": true,
  "title": "Wroat",
  "url": "https://eberron.fandom.com/wiki/Wroat",
  "source": "Eberron Wiki (eberron.fandom.com): a community wiki, ...",
  "summary": "Wroat is the capital city of the nation of Breland, ...",
  "facts": [
    { "field": "type", "value": "City", "sources": [] },
    { "field": "region", "value": "Breland", "sources": [] },
    ...
  ],
  "sources": ["Five Nations, p. 60,61,62"],
  "other_matches": ["Breland", "Sharn", "King's Forest", "Boranel ir'Wynarn"],
  "truncated": false,
  "message": ""
}
```

!!! note "Changed in 0.2.0"
    Replaces `get_capital` (a hard-coded table, no sources) and `search_eberron_wiki` (whose wiki endpoint now answers 403). Capitals now come from the wiki's infoboxes, with citations: look up the nation and read its `capital` fact.

## Configuration

| Environment variable | Default | Description |
|---|---|---|
| `EBERRON_WIKI_BASE_URL` | `https://eberron.fandom.com` | Wiki to query (its `/api.php`). The test suite points this at a local stand-in. |
