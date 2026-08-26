"""Точка входу Vercel serverless з підтримкою Piper TTS."""

import os
import io
import asyncio
import hashlib
import wave
import tempfile
import logging

from flask import Flask, request, Response, send_from_directory
import edge_tts

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

MAX_TEXT_LENGTH: int = 10000
CACHE_DIR: str = os.path.join(tempfile.gettempdir(), "tts_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

EDGE_VOICES: dict[str, list[str]] = {
    "uk-UA": [
        "uk-UA-OstapNeural", "uk-UA-PolinaNeural",
        "piper:uk_UA-ukrainian_tts-medium-0",
        "piper:uk_UA-ukrainian_tts-medium-1",
        "piper:uk_UA-ukrainian_tts-medium-2",
        "piper:uk_UA-lada-x_low",
    ],
    "ru-RU": ["ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural"],
    "pl-PL": ["pl-PL-MarekNeural", "pl-PL-ZofiaNeural"],
    "en-US": [
        "en-US-AvaNeural", "en-US-AndrewNeural", "en-US-EmmaNeural",
        "en-US-BrianNeural", "en-US-AnaNeural", "en-US-AriaNeural",
        "en-US-ChristopherNeural", "en-US-EricNeural", "en-US-GuyNeural",
        "en-US-JennyNeural", "en-US-MichelleNeural", "en-US-RogerNeural",
        "en-US-SteffanNeural",
    ],
    "en-GB": ["en-GB-LibbyNeural", "en-GB-MaisieNeural", "en-GB-RyanNeural", "en-GB-SoniaNeural", "en-GB-ThomasNeural"],
    "de-DE": ["de-DE-AmalaNeural", "de-DE-ConradNeural", "de-DE-KatjaNeural", "de-DE-KillianNeural"],
    "fr-FR": ["fr-FR-DeniseNeural", "fr-FR-EloiseNeural", "fr-FR-HenriNeural"],
    "es-ES": ["es-ES-XimenaNeural", "es-ES-AlvaroNeural", "es-ES-ElviraNeural"],
    "pt-BR": ["pt-BR-AntonioNeural", "pt-BR-FranciscaNeural"],
    "it-IT": ["it-IT-DiegoNeural", "it-IT-ElsaNeural", "it-IT-IsabellaNeural"],
    "ja-JP": ["ja-JP-KeitaNeural", "ja-JP-NanamiNeural"],
    "zh-CN": ["zh-CN-XiaoxiaoNeural", "zh-CN-XiaoyiNeural", "zh-CN-YunjianNeural", "zh-CN-YunxiNeural", "zh-CN-YunyangNeural"],
    "ko-KR": ["ko-KR-InJoonNeural", "ko-KR-SunHiNeural"],
    "cs-CZ": ["cs-CZ-AntoninNeural", "cs-CZ-VlastaNeural"],
    "tr-TR": ["tr-TR-EmelNeural", "tr-TR-AhmetNeural"],
    "ar-SA": ["ar-SA-HamedNeural", "ar-SA-ZariyahNeural"],
    "hi-IN": ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural"],
    "hu-HU": ["hu-HU-NoemiNeural", "hu-HU-TamasNeural"],
    "ro-RO": ["ro-RO-AlinaNeural", "ro-RO-EmilNeural"],
    "sv-SE": ["sv-SE-MattiasNeural", "sv-SE-SofieNeural"],
    "nb-NO": ["nb-NO-FinnNeural", "nb-NO-PernilleNeural"],
    "fi-FI": ["fi-FI-HarriNeural", "fi-FI-NooraNeural"],
    "nl-NL": ["nl-NL-ColetteNeural", "nl-NL-FennaNeural", "nl-NL-MaartenNeural"],
}

VOICE_LABELS: dict[str, str] = {
    "piper:uk_UA-ukrainian_tts-medium-0": "Ukrainian TTS — голос 1",
    "piper:uk_UA-ukrainian_tts-medium-1": "Ukrainian TTS — голос 2",
    "piper:uk_UA-ukrainian_tts-medium-2": "Ukrainian TTS — голос 3",
    "piper:uk_UA-lada-x_low": "Лада (компактна модель)",
}

ALL_VOICE_NAMES: set[str] = set()
for _voices in EDGE_VOICES.values():
    ALL_VOICE_NAMES.update(_voices)

PIPER_VOICES_DIR: str = os.environ.get("PIPER_VOICES_DIR", "./piper_voices")


def cache_key(text: str, voice: str, rate: str) -> str:
    return hashlib.sha256(f"{text}|{voice}|{rate}".encode()).hexdigest()


def is_valid_voice(voice: str) -> bool:
    return voice in ALL_VOICE_NAMES


def rate_to_length_scale(rate: str) -> float:
    try:
        percent = int(rate.replace("%", "").replace("+", ""))
    except ValueError:
        return 1.0
    return 1.0 - (percent / 100.0)


def is_piper_voice(voice_id: str) -> bool:
    return voice_id.startswith("piper:")


def strip_markdown_for_tts(text: str) -> str:
    import re
    text = re.sub(r'```[\s\S]*?```', ' ', text)
    text = re.sub(r'`[^`]+`', ' ', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', ' ', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\|', '', text, flags=re.MULTILINE)
    text = re.sub(r'\|$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\|', ',', text)
    text = re.sub(r'^[-*_]{3,}$', ' ', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _synthesize_piper(text: str, voice_id: str, length_scale: float) -> bytes:
    """Синтез мови через Piper. Повертає WAV-байти."""
    model_map = {
        "piper:uk_UA-ukrainian_tts-medium-0": ("uk_UA-ukrainian_tts-medium", 0),
        "piper:uk_UA-ukrainian_tts-medium-1": ("uk_UA-ukrainian_tts-medium", 1),
        "piper:uk_UA-ukrainian_tts-medium-2": ("uk_UA-ukrainian_tts-medium", 2),
        "piper:uk_UA-lada-x_low": ("uk_UA-lada-x_low", None),
    }

    if voice_id not in model_map:
        raise ValueError(f"Unknown piper voice: {voice_id}")

    model_name, speaker_id = model_map[voice_id]
    onnx_path = os.path.join(PIPER_VOICES_DIR, f"{model_name}.onnx")

    if not os.path.exists(onnx_path):
        raise RuntimeError(
            f"Model '{model_name}' not found in {PIPER_VOICES_DIR}. "
            f"Download: python -m piper.download_voices {model_name} "
            f"--download-dir {PIPER_VOICES_DIR}"
        )

    from piper import PiperVoice
    voice = PiperVoice.load(onnx_path)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        synth_kwargs: dict = {"length_scale": length_scale}
        if speaker_id is not None:
            synth_kwargs["speaker_id"] = speaker_id
        voice.synthesize(text, wav_file, **synth_kwargs)

    return buf.getvalue()


async def _generate_edge_audio(text: str, voice: str, rate: str, pitch: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp.close()
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(tmp.name)
    return tmp.name


@app.after_request
def add_cors_headers(response: Response) -> Response:
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


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

    key = cache_key(cleaned, voice, rate)
    ext = ".wav" if is_piper_voice(voice) else ".mp3"
    cached_path = os.path.join(CACHE_DIR, f"{key}{ext}")
    if os.path.exists(cached_path):
        with open(cached_path, "rb") as f:
            mime = "audio/wav" if ext == ".wav" else "audio/mpeg"
            return Response(f.read(), mimetype=mime)

    try:
        if is_piper_voice(voice):
            length_scale = rate_to_length_scale(rate)
            audio_bytes = _synthesize_piper(cleaned, voice, length_scale)
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
        return Response("TTS generation failed", status=500)


# ── База знань (працює локально та на Render, недоступна на Vercel serverless) ──

DB_PATH = os.path.join(PROJECT_ROOT, "knowledge_base.db")

def _kb_available():
    try:
        import sqlite3
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
    import time, sqlite3
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
    import time, sqlite3
    allowed = {".txt", ".md", ".markdown", ".text"}
    if request.content_type and "multipart" in request.content_type:
        f = request.files.get("file")
        if not f or not f.filename:
            return Response("No file", status=400)
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in allowed:
            return Response(f"Unsupported format: {ext}", status=400)
        title = request.form.get("title", "").strip() or f.filename
        content = f.read().decode("utf-8", errors="replace")
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
    import time, sqlite3
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
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return {"deleted": deleted} if deleted else (Response("Not found", status=404))
