![CI/CD](https://github.com/sinan-ozel/eberron-mcp-server/actions/workflows/ci.yaml/badge.svg?branch=main)
![Docker Hub](https://img.shields.io/docker/v/sinanozel/eberron-mcp-server?label=Docker%20Hub)
![License](https://img.shields.io/github/license/sinan-ozel/eberron-mcp-server.svg)

# Eberron MCP Server

An [MCP](https://modelcontextprotocol.io) server that gives AI assistants access to information about the **Eberron** Dungeons & Dragons campaign setting. Built with [FastMCP](https://github.com/jlowin/fastmcp) and served over Streamable HTTP.

## Tools

| Tool | Description |
|---|---|
| `get_capital` | Returns the capital city of an Eberron nation |
| `search_eberron_wiki` | Searches the [Eberron Fandom Wiki](https://eberron.fandom.com) for lore |

### `get_capital`

Returns the capital of any of the 14 Eberron nations. Input is case-insensitive.

```
get_capital("Breland")        → "Wroat"
get_capital("Eldeen Reaches") → "Greenheart"
get_capital("Q'barra")        → "Newthrone"
```

Supported nations: Aundair, Breland, Cyre, Darguun, Droaam, Eldeen Reaches, Karrnath, Lhazaar Principalities, Mror Holds, Q'barra, Talenta Plains, Thrane, Valenar, Zilargo.

### `search_eberron_wiki`

Queries the Eberron Fandom Wiki API and returns the article content for a given title.

```
search_eberron_wiki("House Cannith")
search_eberron_wiki("Sharn")
search_eberron_wiki("The Mourning")
```

---

## Quickstart

```bash
docker run -p 8000:8000 sinanozel/eberron-mcp-server:latest
```

MCP endpoint: `http://localhost:8000/mcp`

### Connect from Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "eberron": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Connect from Cursor / Windsurf

```json
{
  "mcpServers": {
    "eberron": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

---

## Development

Requires Docker only.

### VS Code Tasks

Open **Terminal → Run Task**:

| Task | What it does |
|---|---|
| `test` | Runs the full test suite |
| `lint` | Runs ruff |
| `reformat` | Runs black + isort + docformatter |
| `validate-docs` | Builds MkDocs with `--strict` |
| `inspector` | Starts the MCP Inspector at http://localhost:6274 |

### CLI

```bash
# Test
docker compose -f tests/docker-compose.yaml up --build --abort-on-container-exit --exit-code-from test

# Lint
docker compose -f lint/docker-compose.yaml up --build --abort-on-container-exit

# Reformat
docker compose -f reformat/docker-compose.yaml up --build --abort-on-container-exit

# Inspector
docker compose -f inspector/docker-compose.yaml up --build
```

---

## CI/CD

Every push runs lint and tests. On `main`, if `server/` changed since the last tag:

- **Stable release** (`__version__` > last tag) → pushes `sinanozel/eberron-mcp-server:x.y.z` and `:latest` to Docker Hub, creates a GitHub release, deploys docs to GitHub Pages
- **Dev release** (`__version__` == last tag) → pushes `sinanozel/eberron-mcp-server:x.y.z.devYYYYMMDDHHMM`

Bump `__version__` in `server/__init__.py` to cut a stable release.
