"""Vercel serverless entrypoint exposing the FastAPI app."""

import os
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

for path_entry in (str(ROOT_DIR), str(SRC_DIR)):
    if path_entry not in sys.path:
        sys.path.insert(0, path_entry)

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

from src.lock_adapter import app  # noqa: E402


class VercelPathRestoreMiddleware:
    """Restore the original request path from __path added by vercel.json rewrites."""

    def __init__(self, asgi_app):
        self.app = asgi_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") in ("http", "websocket"):
            raw_qs = scope.get("query_string", b"").decode("latin-1")
            if "__path=" in raw_qs:
                pairs = parse_qsl(raw_qs, keep_blank_values=True)
                restored_path = None
                remaining = []
                for k, v in pairs:
                    if k == "__path" and restored_path is None:
                        restored_path = v
                    else:
                        remaining.append((k, v))
                if restored_path:
                    if not restored_path.startswith("/"):
                        restored_path = "/" + restored_path
                    scope = dict(scope)
                    scope["path"] = restored_path
                    scope["raw_path"] = restored_path.encode("latin-1")
                    scope["root_path"] = ""
                    scope["query_string"] = urlencode(remaining).encode("latin-1")
        await self.app(scope, receive, send)


if app is not None:
    app.add_middleware(VercelPathRestoreMiddleware)
