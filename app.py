"""Run with: python app.py. Production defaults use Waitress and loopback only."""

import secrets
from pathlib import Path
from urllib.parse import urlsplit

from dash import Dash
from flask import abort, request, session

from src.callbacks.workspace import register_callbacks
from src.components.layout import layout
from src.connections.adomd_provider import AdomdProvider
from src.models.session import SessionRegistry


def create_app(provider=None):
    app = Dash(
        __name__,
        title="DAX Browser Studio",
        assets_folder=str(Path(__file__).parent / "assets"),
        update_title="Working…",
        suppress_callback_exceptions=False,
    )
    server = app.server
    server.secret_key = secrets.token_hex(32)
    server.config.update(
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict", MAX_CONTENT_LENGTH=2_000_000
    )

    @server.before_request
    def local_only():
        if request.host.split(":")[0].lower() not in {"127.0.0.1", "localhost"}:
            abort(403)
        origin = request.headers.get("Origin")
        if origin and urlsplit(origin).netloc != request.host:
            abort(403)
        if request.headers.get("Sec-Fetch-Site") == "cross-site":
            abort(403)
        if "studio_id" not in session:
            session["studio_id"] = secrets.token_urlsafe(32)

    @server.after_request
    def privacy_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    app.layout = layout
    registry = SessionRegistry()
    register_callbacks(app, provider if provider is not None else AdomdProvider(), registry)
    return app


if __name__ == "__main__":
    from waitress import serve

    application = create_app()
    print("DAX Browser Studio: http://127.0.0.1:8050 (Ctrl+C to stop)")
    serve(application.server, host="127.0.0.1", port=8050, threads=6)
