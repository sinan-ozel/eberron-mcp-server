"""Stand-in for the Eberron wiki's MediaWiki API (``/api.php``).

Serves responses recorded from eberron.fandom.com in ``fixtures/``, so the test
suite never depends on the live wiki (or on Cloudflare letting CI runners
through). Search results live in ``fixtures/search/<query>.json`` and pages in
``fixtures/parse/<title>.json``, both lower-cased with spaces as underscores.
Anything else answers like the real API does for a miss.
"""

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

FIXTURES = Path(__file__).parent / "fixtures"

NO_RESULTS = {"batchcomplete": True, "query": {"search": []}}
MISSING_TITLE = {
    "error": {
        "code": "missingtitle",
        "info": "The page you specified doesn't exist.",
    }
}


def fixture_name(text: str) -> str:
    """File name for a query or title, e.g. 'House Cannith' ->
    'house_cannith'."""
    return re.sub(r"[^a-z0-9_']", "", text.strip().lower().replace(" ", "_"))


def load(kind: str, text: str, default: dict) -> dict:
    path = FIXTURES / kind / f"{fixture_name(text)}.json"
    return json.loads(path.read_text()) if path.is_file() else default


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/health":
            return self.reply(200, {"ok": True})
        if url.path != "/api.php":
            return self.reply(404, {"error": "not found"})
        params = {k: v[0] for k, v in parse_qs(url.query).items()}
        action = params.get("action")
        if action == "query" and params.get("list") == "search":
            body = load("search", params.get("srsearch", ""), NO_RESULTS)
        elif action == "parse":
            body = load("parse", params.get("page", ""), MISSING_TITLE)
        else:
            body = {"error": {"code": "badvalue", "info": "Unsupported."}}
        return self.reply(200, body)

    def reply(self, status: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
