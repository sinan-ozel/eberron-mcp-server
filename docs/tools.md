# Tools

## get_capital

Returns the capital city of an Eberron nation.

**Input**

| Field | Type | Description |
|---|---|---|
| `nation` | `string` | Nation name, case-insensitive. Null values are rejected. |

**Supported nations**

| Nation | Capital |
|---|---|
| Aundair | Fairhaven |
| Breland | Wroat |
| Cyre | Metrol |
| Darguun | Rhukaan Draal |
| Droaam | the Great Craag |
| Eldeen Reaches | Greenheart |
| Karrnath | Korth |
| Lhazaar Principalities | Regalport |
| Mror Holds | Krona Peak |
| Q'barra | Newthrone |
| Talenta Plains | Gatherhold |
| Thrane | Flamekeep |
| Valenar | Taer Valaestas |
| Zilargo | Trolanport |

**Output**

The capital city name as a string, or `"Unknown nation"` if the input doesn't match any supported nation.

**Example**

```
Input:  { "nation": "Breland" }
Output: "Wroat"

Input:  { "nation": "eldeen-reaches" }
Output: "Greenheart"

Input:  { "nation": "Mordain" }
Output: "Unknown nation"
```

!!! note "Name matching"
    The tool normalises spacing and hyphens, so `eldeen-reaches`, `eldeen reaches`, and `EldeenReaches` all resolve correctly.

---

## search_eberron_wiki

Queries the [Eberron Fandom Wiki](https://eberron.fandom.com) for a given term and returns the article content.

**Input**

| Field | Type | Description |
|---|---|---|
| `query` | `string` | Article title or search term. Null values are rejected. |

**Output**

Raw HTML content of the matched wiki article, returned as a single string. If the wiki returns an error or the article is not found, the tool returns an error message.

**Example**

```
Input:  { "query": "House Cannith" }
Output: "<html>...</html>"  (full article HTML from the Fandom Wiki)

Input:  { "query": "Treaty of Throne" }
Output: "<html>...</html>"
```

!!! tip "Usage guidance"
    Pass exact article titles when possible (e.g. `"Sharn"`, `"Droaam"`, `"Mourning"`). The Fandom API resolves redirects automatically.

