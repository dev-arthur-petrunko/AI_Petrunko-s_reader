"""Точка входу Vercel serverless з підтримкою Piper TTS."""

import os
import sys
import time
import sqlite3
import asyncio
import logging

from flask import Flask, request, Response, send_from_directory

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")

sys.path.insert(0, PROJECT_ROOT)

from app.config import MAX_TEXT_LENGTH, CACHE_DIR, EDGE_VOICES, VOICE_LABELS, ALL_VOICE_NAMES
from app.tts import strip_markdown_for_tts, cache_key, rate_to_length_scale, _generate_edge_audio

logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    limiter = Limiter(get_remote_address, app=app, default_limits=["60/minute"])
except ImportError:
    limiter = None


def is_valid_voice(voice: str) -> bool:
    return voice in ALL_VOICE_NAMES


def is_piper_voice(voice_id: str) -> bool:
    return voice_id.startswith("piper:")


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

    cleaned = strip_markdown_for_tts(text)

    key = cache_key(cleaned, voice, rate, pitch)
    ext = ".wav" if is_piper_voice(voice) else ".mp3"
    cached_path = os.path.join(CACHE_DIR, f"{key}{ext}")
    if os.path.exists(cached_path):
        with open(cached_path, "rb") as f:
            mime = "audio/wav" if ext == ".wav" else "audio/mpeg"
            return Response(f.read(), mimetype=mime)

    try:
        if is_piper_voice(voice):
            try:
                import piper_engine
            except ImportError as e:
                raise RuntimeError(f"Piper TTS not installed: {e}") from e
            length_scale = rate_to_length_scale(rate)
            audio_bytes = piper_engine.synthesize_wav(cleaned, voice, length_scale)
            mime = "audio/wav"
        else:
            audio_path = asyncio.run(_generate_edge_audio(cleaned, voice, rate, pitch))
            try:
                with open(audio_path, "rb") as f:
                    audio_bytes = f.read()
            finally:
                if os.path.exists(audio_path):
                    os.unlink(audio_path)
            mime = "audio/mpeg"

        with open(cached_path, "wb") as f:
            f.write(audio_bytes)

        return Response(audio_bytes, mimetype=mime)
    except Exception as e:
        logger.error("TTS error: %s", e, exc_info=True)
        msg = str(e).lower()
        status = 503 if ("not installed" in msg or "not found" in msg) else 500
        return Response("TTS generation failed", status=status)


# ── База знань (працює локально та на Render, недоступна на Vercel serverless) ──

DB_PATH = os.path.join(PROJECT_ROOT, "knowledge_base.db")


def _kb_available():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, content TEXT NOT NULL,
            format TEXT NOT NULL DEFAULT 'txt', word_count INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL, last_accessed REAL NOT NULL
        )""")
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


KB_OK = _kb_available()


@app.route("/api/docs", methods=["GET"])
def docs_list():
    if not KB_OK:
        return Response("Knowledge base not available on serverless", status=501)
    q = request.args.get("q", "").strip()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if q:
        pat = f"%{q}%"
        rows = conn.execute("SELECT id, title, word_count, created_at FROM documents WHERE title LIKE ? OR content LIKE ? ORDER BY last_accessed DESC", (pat, pat)).fetchall()
    else:
        rows = conn.execute("SELECT id, title, word_count, created_at FROM documents ORDER BY last_accessed DESC").fetchall()
    conn.close()
    return {"documents": [dict(r) for r in rows]}


@app.route("/api/docs", methods=["POST"])
def docs_upload():
    if not KB_OK:
        return Response("Knowledge base not available on serverless", status=501)
    allowed = {".txt", ".md", ".markdown", ".text", ".pdf", ".epub", ".fb2", ".mobi", ".azw3"}
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
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("INSERT INTO documents (title,content,format,word_count,created_at,last_accessed) VALUES (?,?,?,?,?,?)",
                       (title, content, fmt, len(content.split()), now, now))
    doc_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": doc_id, "title": title, "word_count": len(content.split())}, 201


@app.route("/api/docs/<int:doc_id>", methods=["GET"])
def docs_get(doc_id):
    if not KB_OK:
        return Response("Knowledge base not available on serverless", status=501)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if row:
        conn.execute("UPDATE documents SET last_accessed = ? WHERE id = ?", (time.time(), doc_id))
        conn.commit()
    conn.close()
    return dict(row) if row else (Response("Not found", status=404))


@app.route("/api/docs/<int:doc_id>", methods=["DELETE"])
def docs_delete(doc_id):
    if not KB_OK:
        return Response("Knowledge base not available on serverless", status=501)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return {"deleted": deleted} if deleted else (Response("Not found", status=404))


if limiter is not None:
    app.view_functions["tts_generate"] = limiter.limit("30/minute")(app.view_functions["tts_generate"])
    app.view_functions["docs_upload"] = limiter.limit("10/minute")(app.view_functions["docs_upload"])