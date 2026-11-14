"""Точка входу Vercel serverless з підтримкою Piper TTS."""

import os
import sys
import logging

from flask import Flask, request, Response, send_from_directory

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")

sys.path.insert(0, PROJECT_ROOT)

from app.config import MAX_TEXT_LENGTH, MAX_CONTENT_LENGTH, EDGE_VOICES, VOICE_LABELS, ALL_VOICE_NAMES
from app.tts import generate_audio_sync

logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

from app.limits import apply_limits

# єдиний ліміт для локального сервера та Vercel (раніше тут було 60/minute,
# через що читання таблиць добивалося до 429 і відкатувалося у голос браузера)
limiter = apply_limits(app)


def is_valid_voice(voice: str) -> bool:
    return voice in ALL_VOICE_NAMES


@app.route("/health")
def health():
    return {"status": "ok"}


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


@app.route("/api/tts/voices", methods=["GET"])
def tts_voices() -> dict:
    return {"voices": EDGE_VOICES, "voice_labels": VOICE_LABELS}


@app.route("/api/tts", methods=["POST"])
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
    except Exception as e:
        logger.error("TTS error: %s", e, exc_info=True)
        msg = str(e).lower()
        if "перевищив час очікування" in msg:
            status = 504  # таймаут edge-tts — клієнт зробить ще спроби/фолбек
        else:
            status = 503 if ("not installed" in msg or "not found" in msg) else 500
        return Response("TTS generation failed", status=status)


# ── База знань (працює локально, на Render і на serverless через записувану папку) ──
# Єдина реалізація — app.database: тут був дубль тієї ж логіки зі своїм DB_PATH,
# через що serverless читав іншу базу, ніж локальний сервер (документи «губилися»)

from app.database import init_db

try:
    init_db()
    KB_OK = True
except Exception as e:  # read-only середовище serverless — API віддає 501
    logger.warning("Knowledge base init failed: %s", e)
    KB_OK = False


def _kb_guard():
    """501, якщо база недоступна на цьому середовищі."""
    return None if KB_OK else Response("Knowledge base not available on serverless", status=501)


@app.route("/api/docs", methods=["GET"])
def docs_list():
    from app.database import list_documents, search_documents
    blocked = _kb_guard()
    if blocked:
        return blocked
    q = request.args.get("q", "").strip()
    if q:
        return {"documents": search_documents(q)}
    return {"documents": list_documents()}


@app.route("/api/docs", methods=["POST"])
def docs_upload():
    from app.database import add_document
    blocked = _kb_guard()
    if blocked:
        return blocked
    allowed = {".txt", ".md", ".markdown", ".text", ".pdf", ".epub", ".fb2", ".mobi", ".azw3", ".docx", ".odt", ".rtf", ".html", ".htm"}
    if request.content_type and "multipart" in request.content_type:
        f = request.files.get("file")
        if not f or not f.filename:
            return Response("No file", status=400)
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in allowed:
            return Response(f"Unsupported format: {ext}", status=400)
        title = request.form.get("title", "").strip() or f.filename
        raw = f.read()

        if ext in {".txt", ".md", ".markdown", ".text"}:
            content = raw.decode("utf-8", errors="replace")
            fmt = ext.lstrip(".")
        else:
            from app.document_parser import parse_document
            try:
                content, fmt = parse_document(f.filename, raw)
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


@app.route("/api/docs/<int:doc_id>", methods=["GET"])
def docs_get(doc_id):
    from app.database import get_document
    blocked = _kb_guard()
    if blocked:
        return blocked
    doc = get_document(doc_id)
    return doc if doc else Response("Not found", status=404)


@app.route("/api/docs/<int:doc_id>", methods=["DELETE"])
def docs_delete(doc_id):
    from app.database import delete_document
    blocked = _kb_guard()
    if blocked:
        return blocked
    if not delete_document(doc_id):
        return Response("Not found", status=404)
    return {"deleted": True}


# Ліміти накладено у app.limits.apply_limits при створенні застосунку.