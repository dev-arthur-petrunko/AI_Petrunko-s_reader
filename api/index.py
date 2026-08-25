import os
import asyncio
import edge_tts
import tempfile
from flask import Flask, request, Response

app = Flask(__name__)

ALL_VOICES = {
    "uk-UA": [
        {"name": "uk-UA-OstapNeural", "gender": "Male"},
        {"name": "uk-UA-PolinaNeural", "gender": "Female"},
    ],
    "ru-RU": [
        {"name": "ru-RU-DmitryNeural", "gender": "Male"},
        {"name": "ru-RU-SvetlanaNeural", "gender": "Female"},
    ],
    "pl-PL": [
        {"name": "pl-PL-MarekNeural", "gender": "Male"},
        {"name": "pl-PL-ZofiaNeural", "gender": "Female"},
    ],
    "en-US": [
        {"name": "en-US-AvaNeural", "gender": "Female"},
        {"name": "en-US-AndrewNeural", "gender": "Male"},
        {"name": "en-US-EmmaNeural", "gender": "Female"},
        {"name": "en-US-BrianNeural", "gender": "Male"},
        {"name": "en-US-AnaNeural", "gender": "Female"},
        {"name": "en-US-AriaNeural", "gender": "Female"},
        {"name": "en-US-ChristopherNeural", "gender": "Male"},
        {"name": "en-US-EricNeural", "gender": "Male"},
        {"name": "en-US-GuyNeural", "gender": "Male"},
        {"name": "en-US-JennyNeural", "gender": "Female"},
        {"name": "en-US-MichelleNeural", "gender": "Female"},
        {"name": "en-US-RogerNeural", "gender": "Male"},
        {"name": "en-US-SteffanNeural", "gender": "Male"},
    ],
    "en-GB": [
        {"name": "en-GB-LibbyNeural", "gender": "Female"},
        {"name": "en-GB-MaisieNeural", "gender": "Female"},
        {"name": "en-GB-RyanNeural", "gender": "Male"},
        {"name": "en-GB-SoniaNeural", "gender": "Female"},
        {"name": "en-GB-ThomasNeural", "gender": "Male"},
    ],
    "de-DE": [
        {"name": "de-DE-AmalaNeural", "gender": "Female"},
        {"name": "de-DE-ConradNeural", "gender": "Male"},
        {"name": "de-DE-KatjaNeural", "gender": "Female"},
        {"name": "de-DE-KillianNeural", "gender": "Male"},
    ],
    "fr-FR": [
        {"name": "fr-FR-DeniseNeural", "gender": "Female"},
        {"name": "fr-FR-EloiseNeural", "gender": "Female"},
        {"name": "fr-FR-HenriNeural", "gender": "Male"},
    ],
    "es-ES": [
        {"name": "es-ES-XimenaNeural", "gender": "Female"},
        {"name": "es-ES-AlvaroNeural", "gender": "Male"},
        {"name": "es-ES-ElviraNeural", "gender": "Female"},
    ],
    "pt-BR": [
        {"name": "pt-BR-AntonioNeural", "gender": "Male"},
        {"name": "pt-BR-FranciscaNeural", "gender": "Female"},
    ],
    "it-IT": [
        {"name": "it-IT-DiegoNeural", "gender": "Male"},
        {"name": "it-IT-ElsaNeural", "gender": "Female"},
        {"name": "it-IT-IsabellaNeural", "gender": "Female"},
    ],
    "ja-JP": [
        {"name": "ja-JP-KeitaNeural", "gender": "Male"},
        {"name": "ja-JP-NanamiNeural", "gender": "Female"},
    ],
    "zh-CN": [
        {"name": "zh-CN-XiaoxiaoNeural", "gender": "Female"},
        {"name": "zh-CN-XiaoyiNeural", "gender": "Female"},
        {"name": "zh-CN-YunjianNeural", "gender": "Male"},
        {"name": "zh-CN-YunxiNeural", "gender": "Male"},
        {"name": "zh-CN-YunyangNeural", "gender": "Male"},
    ],
    "ko-KR": [
        {"name": "ko-KR-InJoonNeural", "gender": "Male"},
        {"name": "ko-KR-SunHiNeural", "gender": "Female"},
    ],
    "cs-CZ": [
        {"name": "cs-CZ-AntoninNeural", "gender": "Male"},
        {"name": "cs-CZ-VlastaNeural", "gender": "Female"},
    ],
    "tr-TR": [
        {"name": "tr-TR-EmelNeural", "gender": "Female"},
        {"name": "tr-TR-AhmetNeural", "gender": "Male"},
    ],
    "ar-SA": [
        {"name": "ar-SA-HamedNeural", "gender": "Male"},
        {"name": "ar-SA-ZariyahNeural", "gender": "Female"},
    ],
    "hi-IN": [
        {"name": "hi-IN-MadhurNeural", "gender": "Male"},
        {"name": "hi-IN-SwaraNeural", "gender": "Female"},
    ],
    "hu-HU": [
        {"name": "hu-HU-NoemiNeural", "gender": "Female"},
        {"name": "hu-HU-TamasNeural", "gender": "Male"},
    ],
    "ro-RO": [
        {"name": "ro-RO-AlinaNeural", "gender": "Female"},
        {"name": "ro-RO-EmilNeural", "gender": "Male"},
    ],
    "sv-SE": [
        {"name": "sv-SE-MattiasNeural", "gender": "Male"},
        {"name": "sv-SE-SofieNeural", "gender": "Female"},
    ],
    "nb-NO": [
        {"name": "nb-NO-FinnNeural", "gender": "Male"},
        {"name": "nb-NO-PernilleNeural", "gender": "Female"},
    ],
    "fi-FI": [
        {"name": "fi-FI-HarriNeural", "gender": "Male"},
        {"name": "fi-FI-NooraNeural", "gender": "Female"},
    ],
    "nl-NL": [
        {"name": "nl-NL-ColetteNeural", "gender": "Female"},
        {"name": "nl-NL-FennaNeural", "gender": "Female"},
        {"name": "nl-NL-MaartenNeural", "gender": "Male"},
    ],
}


@app.route("/api/tts/voices", methods=["GET"])
def tts_voices():
    return {"voices": ALL_VOICES}


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


async def _generate_audio(text: str, voice: str, rate: str, pitch: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp.close()
    communicate = edge_tts.Communicate(
        text=text, voice=voice, rate=rate, pitch=pitch
    )
    await communicate.save(tmp.name)
    return tmp.name
