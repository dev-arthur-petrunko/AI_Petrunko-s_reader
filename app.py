import os
import asyncio
import hashlib
import edge_tts
import tempfile
from flask import Flask, send_from_directory, request, Response

app = Flask(__name__)

BASE_DIR = os.path.abspath(".")
MAX_TEXT_LENGTH = 5000
CACHE_DIR = os.path.join(tempfile.gettempdir(), "tts_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

EDGE_VOICES = {
    "uk-UA": ["uk-UA-OstapNeural", "uk-UA-PolinaNeural"],
    "ru-RU": ["ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural"],
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

ALL_VOICE_NAMES = set()
for voices in EDGE_VOICES.values():
    ALL_VOICE_NAMES.update(voices)


def is_valid_voice(voice: str) -> bool:
    return voice in ALL_VOICE_NAMES


def cache_key(text, voice, rate):
    return hashlib.sha256(f"{text}|{voice}|{rate}".encode()).hexdigest()


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/tts/voices", methods=["GET"])
def tts_voices():
    return {"voices": EDGE_VOICES}


@app.route("/api/tts", methods=["POST"])
def tts_generate():
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

    key = cache_key(text, voice, rate)
    cached_path = os.path.join(CACHE_DIR, f"{key}.mp3")
    if os.path.exists(cached_path):
        with open(cached_path, "rb") as f:
            return Response(f.read(), mimetype="audio/mpeg")

    try:
        audio_path = asyncio.run(_generate_audio(text, voice, rate, pitch))

        try:
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()
        finally:
            if os.path.exists(audio_path):
                os.unlink(audio_path)

        with open(cached_path, "wb") as f:
            f.write(audio_bytes)

        return Response(audio_bytes, mimetype="audio/mpeg")

    except Exception as e:
        return Response(f"TTS error: {e}", status=500)


async def _generate_audio(text, voice, rate, pitch):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp.close()
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(tmp.name)
    return tmp.name


@app.route("/<path:filename>")
def static_files(filename):
    full_path = os.path.realpath(os.path.join(BASE_DIR, filename))
    if not full_path.startswith(BASE_DIR):
        return Response("Forbidden", status=403)
    return send_from_directory(BASE_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
