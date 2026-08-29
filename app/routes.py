"""Маршрути Flask для Petrunko's Reader."""

import os
import logging

from flask import Blueprint, request, Response, send_from_directory

from app.config import BASE_DIR, MAX_TEXT_LENGTH, EDGE_VOICES, ALL_VOICE_NAMES, VOICE_LABELS
from app.tts import generate_audio_sync, cleanup_cache

logger = logging.getLogger(__name__)

api = Blueprint("api", __name__)

STATIC_DIR = os.path.join(BASE_DIR, "static")

ALLOWED_EXTENSIONS = {".txt", ".md", ".markdown", ".text", ".pdf", ".epub", ".fb2", ".mobi", ".azw3"}


def is_valid_voice(voice: str) -> bool:
    return voice in ALL_VOICE_NAMES


@api.route("/health", methods=["GET"])
def health_check() -> dict:
    return {"status": "ok"}


@api.route("/api/tts/voices", methods=["GET"])
def tts_voices() -> dict:
    return {
        "voices": EDGE_VOICES,
        "voice_labels": VOICE_LABELS,
    }


@api.route("/api/tts", methods=["POST"])
def tts_generate() -> Response:
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


# ── База знань ─────────────────────────────────────────────────


@api.route("/api/docs", methods=["GET"])
def docs_list() -> dict:
    from app.database import list_documents, search_documents
    query = request.args.get("q", "").strip()
    if query:
        return {"documents": search_documents(query)}
    return {"documents": list_documents()}


@api.route("/api/docs", methods=["POST"])
def docs_upload():
    from app.database import add_document

    if request.content_type and "multipart" in request.content_type:
        file = request.files.get("file")
        if not file or not file.filename:
            return Response("No file", status=400)
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return Response(f"Unsupported format: {ext}", status=400)
        title = request.form.get("title", "").strip() or file.filename
        raw = file.read()

        if ext in {".txt", ".md", ".markdown", ".text"}:
            content = raw.decode("utf-8", errors="replace")
            fmt = ext.lstrip(".")
        else:
            from app.document_parser import parse_document
            try:
                content, fmt = parse_document(file.filename, raw)
            except Exception as e:
                logger.error("Document parse error: %s", e)
                content, fmt = "", ""
            if not content:
                return Response(f"Could not extract text from {ext}", status=422)
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
    from app.database import get_document
    doc = get_document(doc_id)
    if not doc:
        return Response("Not found", status=404)
    return doc


@api.route("/api/docs/<int:doc_id>", methods=["DELETE"])
def docs_delete(doc_id: int):
    from app.database import delete_document
    deleted = delete_document(doc_id)
    if not deleted:
        return Response("Not found", status=404)
    return {"deleted": True}


def create_app() -> "Flask":
    from flask import Flask

    app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        limiter = Limiter(get_remote_address, app=app, default_limits=["60/minute"])
        api.route = limiter.limit("30/minute")(api.route)  # type: ignore
    except ImportError:
        pass

    app.register_blueprint(api)
    cleanup_cache()

    try:
        from app.database import init_db, cleanup_stale
        init_db()
        cleanup_stale()
    except Exception as e:
        logger.warning("Knowledge base init failed: %s", e)

    @app.route("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.route("/manifest.json")
    def manifest():
        return send_from_directory(STATIC_DIR, "manifest.json")

    @app.route("/sw.js")
    def service_worker():
        return send_from_directory(STATIC_DIR, "sw.js")

    @app.route("/icon.svg")
    def icon():
        return send_from_directory(STATIC_DIR, "icon.svg")

    @app.route("/favicon.ico")
    def favicon():
        path = os.path.join(STATIC_DIR, "favicon.ico")
        if os.path.exists(path):
            return send_from_directory(STATIC_DIR, "favicon.ico")
        return Response(status=404)

    return app
