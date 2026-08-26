"""Конфігурація додатку."""

import os
import tempfile

BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_TEXT_LENGTH: int = 10000
MAX_CONTENT_LENGTH: int = 2 * 1024 * 1024
RATE_LIMIT_DEFAULT: str = "30/minute"
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

ALL_VOICE_NAMES: set[str] = set()
for _voices in EDGE_VOICES.values():
    ALL_VOICE_NAMES.update(_voices)

VOICE_LABELS: dict[str, str] = {
    "piper:uk_UA-ukrainian_tts-medium-0": "Ukrainian TTS — голос 1",
    "piper:uk_UA-ukrainian_tts-medium-1": "Ukrainian TTS — голос 2",
    "piper:uk_UA-ukrainian_tts-medium-2": "Ukrainian TTS — голос 3",
    "piper:uk_UA-lada-x_low": "Лада (компактна модель)",
}
