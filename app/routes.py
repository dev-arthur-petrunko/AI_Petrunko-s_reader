"""Flask routes for Petrunko's Reader."""

import os
import logging

from flask import Blueprint, request, Response, send_from_directory

from app.config import BASE_DIR, MAX_TEXT_LENGTH, EDGE_VOICES, ALL_VOICE_NAMES, VOICE_LABELS
from app.tts import generate_audio_sync, cleanup_cache

logger = logging.getLogger(__name__)

api = Blueprint("api", __name__)

STATIC_DIR = os.path.join(BASE_DIR, "static")

ALLOWED_EXTENSIONS = {".txt", ".md", ".markdown", ".text"}


def is_valid_voice(voice: str) -> bool:
    """Check if a voice name is in the allowed list."""
    return voice in ALL_VOICE_NAMES


@api.after_request
def add_cors_headers(response: Response) -> Response:
    """Add CORS headers to all API responses."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@api.route("/health", methods=["GET"])
def health_check() -> dict:
    """Health-check endpoint for monitoring."""
    return {"status": "ok"}


@api.route("/api/tts/voices", methods=["GET"])
def tts_voices() -> dict:
    """Return available TTS voices grouped by locale with labels."""
    return {
        "voices": EDGE_VOICES,
        "voice_labels": VOICE_LABELS,
    }


@api.route("/api/tts", methods=["POST"])
def tts_generate() -> Response:
    """Generate TTS audio from text."""
    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    voice = data.get("voice", "uk-UA-PolinaNeural")
    rate = data.get("rate", "+0%")
    pitch = data.get("pitch", "+0Hz")

    if not text:
        return Response("No text", status=400)

    if not is_valid_voice(voice):
        return Response("Invalid voice", status=400)

    if len(text) > MAX_TEXT_LENGTH:
        return Response(f"Text too long (max {MAX_TEXT_LENGTH} chars)", status=413)

    try:
        audio_bytes, mime = generate_audio_sync(text, voice, rate, pitch)
        return Response(audio_bytes, mimetype=mime)
    except RuntimeError as e:
        logger.error("TTS error: %s", e, exc_info=True)
        msg = str(e).lower()
        status = 503 if ("not installed" in msg or "not found" in msg) else 500
        return Response("TTS generation failed", status=status)


# ── Knowledge Base ──────────────────────────────────────────────


@api.route("/api/docs", methods=["GET"])
def docs_list() -> dict:
    """List all documents in the knowledge base."""
    from app.database import list_documents, search_documents
    query = request.args.get("q", "").strip()
    if query:
        return {"documents": search_documents(query)}
    return {"documents": list_documents()}


@api.route("/api/docs", methods=["POST"])
def docs_upload():
    """Upload a document to the knowledge base.
    Accepts multipart/form-data with 'file' field (txt/md) or JSON with 'title' + 'content'.
    """
    from app.database import add_document, MAX_AGE_DAYS

    if request.content_type and "multipart" in request.content_type:
        file = request.files.get("file")
        if not file or not file.filename:
            return Response("No file", status=400)
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return Response(f"Unsupported format: {ext}. Use .txt or .md", status=400)
        title = request.form.get("title", "").strip() or file.filename
        content = file.read().decode("utf-8", errors="replace")
        fmt = ext.lstrip(".")
    else:
        data = request.get_json(force=True)
        title = data.get("title", "").strip()
        content = data.get("content", "").strip()
        fmt = data.get("format", "txt")
        if not title or not content:
            return Response("title and content required", status=400)

    if not content:
        return Response("Empty content", status=400)

    if len(content) > 500_000:
        return Response("Document too large (max 500k chars)", status=413)

    doc_id = add_document(title, content, fmt)
    return {"id": doc_id, "title": title, "word_count": len(content.split())}, 201


@api.route("/api/docs/<int:doc_id>", methods=["GET"])
def docs_get(doc_id: int):
    """Get a document by ID (for reading)."""
    from app.database import get_document
    doc = get_document(doc_id)
    if not doc:
        return Response("Not found", status=404)
    return doc


@api.route("/api/docs/<int:doc_id>", methods=["DELETE"])
def docs_delete(doc_id: int):
    """Delete a document."""
    from app.database import delete_document
    deleted = delete_document(doc_id)
    if not deleted:
        return Response("Not found", status=404)
    return {"deleted": True}


def create_app() -> "Flask":
    """Create and configure the Flask application."""
    from flask import Flask

    app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2 MB

    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        limiter = Limiter(get_remote_address, app=app, default_limits=["60/minute"])
        api.route = limiter.limit("30/minute")(api.route)  # type: ignore
    except ImportError:
        pass

    app.register_blueprint(api)
    cleanup_cache()

    # Initialize knowledge base
    try:
        from app.database import init_db, cleanup_stale
        init_db()
        cleanup_stale()
    except Exception as e:
        logger.warning("Knowledge base init failed: %s", e)

    @app.route("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.route("/favicon.ico")
    def favicon():
        path = os.path.join(STATIC_DIR, "favicon.ico")
        if os.path.exists(path):
            return send_from_directory(STATIC_DIR, "favicon.ico")
        return Response(status=404)

    return app
