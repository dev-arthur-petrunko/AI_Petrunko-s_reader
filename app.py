import os
import asyncio
import edge_tts
import tempfile
from flask import Flask, send_from_directory, request, Response

app = Flask(__name__)

EDGE_VOICES = {
    "uk-UA": ["uk-UA-PolinaNeural", "uk-UA-OstapNeural"],
    "ru-RU": ["ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural"],
    "pl-PL": ["pl-PL-AgnieszkaNeural", "pl-PL-MarekNeural"],
    "en-US": ["en-US-JennyNeural", "en-US-GuyNeural", "en-GB-SoniaNeural", "en-US-AriaNeural"],
    "de-DE": ["de-DE-KatjaNeural", "de-DE-ConradNeural"],
    "fr-FR": ["fr-FR-DeniseNeural", "fr-FR-HenriNeural"],
    "es-ES": ["es-ES-ElviraNeural", "es-ES-AlvaroNeural"],
    "pt-BR": ["pt-BR-FranciscaNeural", "pt-BR-AntonioNeural"],
    "it-IT": ["it-IT-ElsaNeural", "it-IT-DiegoNeural"],
    "ja-JP": ["ja-JP-NanamiNeural", "ja-JP-KeitaNeural"],
    "zh-CN": ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"],
    "ko-KR": ["ko-KR-SunHiNeural", "ko-KR-InJoonNeural"],
    "cs-CZ": ["cs-CZ-VlastaNeural", "cs-CZ-AntoninNeural"],
}


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(".", filename)


@app.route("/api/tts/voices", methods=["GET"])
def tts_voices():
    return {"voices": EDGE_VOICES}


@app.route("/api/tts", methods=["POST"])
def tts_generate():
    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    voice = data.get("voice", "uk-UA-PolinaNeural")
    rate = data.get("rate", "+0%")

    if not text:
        return Response("No text", status=400)

    try:
        loop = asyncio.new_event_loop()
        try:
            audio_path = loop.run_until_complete(
                _generate_audio(text, voice, rate)
            )
        finally:
            loop.close()

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        os.unlink(audio_path)

        return Response(audio_bytes, mimetype="audio/mpeg")

    except Exception as e:
        return Response(f"TTS error: {e}", status=500)


async def _generate_audio(text: str, voice: str, rate: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp.close()
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    await communicate.save(tmp.name)
    return tmp.name


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
