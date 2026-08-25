"""Piper TTS — локальний, повністю безкоштовний синтез мови без API-ключів.

Підключається як другий движок для українських голосів,
які звучать живіше за деякі нейро-голоси Edge TTS.

ВСТАНОВЛЕННЯ:
    pip install piper-tts

ЗАВАНТАЖЕННЯ МОДЕЛЕЙ (один раз перед першим запуском):
    python -m piper.download_voices uk_UA-ukrainian_tts-medium --download-dir ./piper_voices
    python -m piper.download_voices uk_UA-lada-x_low --download-dir ./piper_voices

Шлях до папки з моделями можна перевизначити змінною PIPER_VOICES_DIR.
"""

from __future__ import annotations

import io
import os
import wave
from functools import lru_cache

from piper import PiperVoice

PIPER_VOICES_DIR: str = os.environ.get("PIPER_VOICES_DIR", "./piper_voices")

PIPER_VOICES: dict[str, dict] = {
    "piper:uk_UA-ukrainian_tts-medium-0": {
        "model": "uk_UA-ukrainian_tts-medium",
        "speaker": 0,
        "label": "Ukrainian TTS — голос 1",
    },
    "piper:uk_UA-ukrainian_tts-medium-1": {
        "model": "uk_UA-ukrainian_tts-medium",
        "speaker": 1,
        "label": "Ukrainian TTS — голос 2",
    },
    "piper:uk_UA-ukrainian_tts-medium-2": {
        "model": "uk_UA-ukrainian_tts-medium",
        "speaker": 2,
        "label": "Ukrainian TTS — голос 3",
    },
    "piper:uk_UA-lada-x_low": {
        "model": "uk_UA-lada-x_low",
        "speaker": None,
        "label": "Лада (компактна модель)",
    },
}


class PiperVoiceNotFound(RuntimeError):
    """Модель не скачана в PIPER_VOICES_DIR."""


@lru_cache(maxsize=4)
def _load_voice(model_name: str) -> PiperVoice:
    """Завантажує та кешує модель в пам'яті."""
    onnx_path = os.path.join(PIPER_VOICES_DIR, f"{model_name}.onnx")
    if not os.path.exists(onnx_path):
        raise PiperVoiceNotFound(
            f"Model '{model_name}' not found in {PIPER_VOICES_DIR}. "
            f"Download: python -m piper.download_voices {model_name} "
            f"--download-dir {PIPER_VOICES_DIR}"
        )
    return PiperVoice.load(onnx_path)


def is_piper_voice(voice_id: str) -> bool:
    """Check if voice_id belongs to Piper engine."""
    return voice_id in PIPER_VOICES


def synthesize_wav(text: str, voice_id: str, length_scale: float = 1.0) -> bytes:
    """Synthesize speech via Piper, returns WAV bytes.

    Args:
        text: Text to synthesize.
        voice_id: Piper voice identifier.
        length_scale: Speed control (>1.0 slower, <1.0 faster).

    Returns:
        WAV audio bytes.

    Raises:
        ValueError: Unknown voice_id.
        PiperVoiceNotFound: Model file not downloaded.
    """
    cfg = PIPER_VOICES.get(voice_id)
    if cfg is None:
        raise ValueError(f"Unknown piper voice: {voice_id}")

    voice = _load_voice(cfg["model"])

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        synth_kwargs: dict = {"length_scale": length_scale}
        if cfg["speaker"] is not None:
            synth_kwargs["speaker_id"] = cfg["speaker"]
        voice.synthesize(text, wav_file, **synth_kwargs)

    return buf.getvalue()
