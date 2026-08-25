"""Flask routes for Petrunko's Reader."""

from flask import Blueprint, request, Response, send_from_directory

from app.config import BASE_DIR, MAX_TEXT_LENGTH, EDGE_VOICES, ALL_VOICE_NAMES, VOICE_LABELS
from app.tts import generate_audio_sync

api = Blueprint("api", __name__)


def is_valid_voice(voice: str) -> bool:
    """Check if a voice name is in the allowed list."""
    return voice in ALL_VOICE_NAMES


@api.after_request
def add_cors_headers(response: Response) -> Response:
    """Add CORS headers to all API responses."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@api.route("/api/tts/voices", methods=["GET"])
def tts_voices() -> dict:
    """Return available TTS voices grouped by locale with labels."""
    return {
        "voices": EDGE_VOICES,
        "voice_labels": VOICE_LABELS,
    }


@api.route("/api/tts", methods=["POST"])
def tts_generate() -> Response:
    """Generate TTS audio from text.

    Supports both edge-tts (cloud, MP3) and Piper (local, WAV) engines.
    Piper voices start with 'piper:' prefix.
    """
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
        return Response(str(e), status=500)


def create_app() -> "Flask":
    """Create and configure the Flask application."""
    from flask import Flask

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB

    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        limiter = Limiter(get_remote_address, app=app, default_limits=["60/minute"])
        api.route = limiter.limit("30/minute")(api.route)  # type: ignore
    except ImportError:
        pass

    app.register_blueprint(api)

    @app.route("/")
    def index():
        return send_from_directory(BASE_DIR, "index.html")

    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(BASE_DIR, "favicon.ico")

    return app
