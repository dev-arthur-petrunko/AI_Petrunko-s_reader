import os
import asyncio
import edge_tts
import tempfile
from flask import Flask, send_from_directory, request, Response

app = Flask(__name__)

_cache_voices = None


def _get_cached_voices():
    global _cache_voices
    if _cache_voices:
        return _cache_voices
    loop = asyncio.new_event_loop()
    try:
        _cache_voices = loop.run_until_complete(edge_tts.list_voices())
    finally:
        loop.close()
    return _cache_voices


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/tts/voices", methods=["GET"])
def tts_voices():
    raw = _get_cached_voices()
    by_locale = {}
    for v in raw:
        loc = v["Locale"]
        if loc not in by_locale:
            by_locale[loc] = []
        by_locale[loc].append({
            "name": v["ShortName"],
            "gender": v["Gender"],
        })
    return {"voices": by_locale}


@app.route("/api/tts", methods=["POST"])
def tts_generate():
    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    voice = data.get("voice", "uk-UA-PolinaNeural")
    rate = data.get("rate", "+0%")
    pitch = data.get("pitch", "+0Hz")

    if not text:
        return Response("No text", status=400)

    try:
        loop = asyncio.new_event_loop()
        try:
            audio_path = loop.run_until_complete(
                _generate_audio(text, voice, rate, pitch)
            )
        finally:
            loop.close()

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        os.unlink(audio_path)

        return Response(audio_bytes, mimetype="audio/mpeg")

    except Exception as e:
        return Response(f"TTS error: {e}", status=500)


async def _generate_audio(text, voice, rate, pitch):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp.close()
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(tmp.name)
    return tmp.name


if __name__ == "__main__":
    app.run(debug=True, port=5000)
