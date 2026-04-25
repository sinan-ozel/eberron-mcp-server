# Eberron MCP Server

An [MCP](https://modelcontextprotocol.io) server that gives AI assistants access to information about the **Eberron** Dungeons & Dragons campaign setting — capitals of its nations and live lookups against the Eberron Fandom Wiki.

[![CI/CD](https://github.com/sinanozel/eberron-mcp-server/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/sinanozel/eberron-mcp-server/actions/workflows/ci.yaml)
[![Docker Hub](https://img.shields.io/docker/v/sinanozel/eberron-mcp-server?label=Docker%20Hub)](https://hub.docker.com/r/sinanozel/eberron-mcp-server)

---

## Quick Start

The server runs as a Docker container and exposes an MCP endpoint over **Streamable HTTP** on port 8000.

```bash
docker run -p 8000:8000 sinanozel/eberron-mcp-server:latest
```

MCP endpoint:

```
http://localhost:8000/mcp
```

---

## Connecting

### Claude Desktop

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

### Cursor / Windsurf

Add to your MCP settings file:

```json
{
  "mcpServers": {
    "eberron": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Any MCP-compatible client

Transport: **Streamable HTTP**
URL: `http://localhost:8000/mcp`

---

## Tools

| Tool | Description |
|---|---|
| [`get_capital`](tools.md#get_capital) | Returns the capital city of an Eberron nation |
| [`search_eberron_wiki`](tools.md#search_eberron_wiki) | Searches the Eberron Fandom Wiki for lore |

See the [Tools](tools.md) page for full input/output details.

---

## Running Locally for Development

The only requirement is **Docker**.

```bash
git clone https://github.com/sinanozel/eberron-mcp-server.git
cd eberron-mcp-server

# Run the MCP Inspector (browser UI)
docker compose -f inspector/docker-compose.yaml up --build
# Then open http://localhost:6274

# Run tests
docker compose -f tests/docker-compose.yaml up --build --abort-on-container-exit --exit-code-from test

# Lint
docker compose -f lint/docker-compose.yaml up --build --abort-on-container-exit

# Reformat
docker compose -f reformat/docker-compose.yaml up --build --abort-on-container-exit
```
