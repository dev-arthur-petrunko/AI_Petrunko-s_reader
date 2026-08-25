"""Text-to-Speech service: edge-tts (cloud) + Piper (local)."""

import os
import asyncio
import hashlib
import tempfile
from typing import Optional

import edge_tts

from app.config import CACHE_DIR

try:
    import piper_engine
    PIPER_AVAILABLE = True
except ImportError:
    PIPER_AVAILABLE = False


def cache_key(text: str, voice: str, rate: str) -> str:
    """Generate SHA-256 cache key from TTS parameters."""
    return hashlib.sha256(f"{text}|{voice}|{rate}".encode()).hexdigest()


def get_cached_path(text: str, voice: str, rate: str) -> Optional[str]:
    """Return path to cached audio if it exists, else None."""
    ext = ".wav" if voice.startswith("piper:") else ".mp3"
    path = os.path.join(CACHE_DIR, f"{cache_key(text, voice, rate)}{ext}")
    return path if os.path.exists(path) else None


def save_to_cache(audio_bytes: bytes, text: str, voice: str, rate: str) -> str:
    """Save audio bytes to cache and return the path."""
    ext = ".wav" if voice.startswith("piper:") else ".mp3"
    path = os.path.join(CACHE_DIR, f"{cache_key(text, voice, rate)}{ext}")
    with open(path, "wb") as f:
        f.write(audio_bytes)
    return path


def rate_to_length_scale(rate: str) -> float:
    """Convert edge-tts rate format ('+0%', '-20%') to Piper length_scale.

    Piper: >1.0 slower, <1.0 faster. edge-tts: +faster, -slower.
    """
    try:
        percent = int(rate.replace("%", "").replace("+", ""))
    except ValueError:
        return 1.0
    return 1.0 - (percent / 100.0)


async def _generate_edge_audio(text: str, voice: str, rate: str, pitch: str) -> str:
    """Generate MP3 via edge-tts. Returns temp file path."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp.close()
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(tmp.name)
    return tmp.name


def generate_audio_sync(text: str, voice: str, rate: str, pitch: str) -> tuple[bytes, str]:
    """Generate TTS audio. Returns (audio_bytes, mime_type).

    Routes to Piper for piper:* voices, edge-tts for all others.
    Tries cache first.

    Returns:
        Tuple of (audio_bytes, mimetype).

    Raises:
        RuntimeError: If generation fails.
        ValueError: If Piper is not installed but a piper voice is requested.
    """
    cached = get_cached_path(text, voice, rate)
    if cached:
        with open(cached, "rb") as f:
            mime = "audio/wav" if cached.endswith(".wav") else "audio/mpeg"
            return f.read(), mime

    if voice.startswith("piper:"):
        if not PIPER_AVAILABLE:
            raise RuntimeError("Piper TTS not installed. Run: pip install piper-tts")
        try:
            length_scale = rate_to_length_scale(rate)
            audio_bytes = piper_engine.synthesize_wav(text, voice, length_scale)
        except piper_engine.PiperVoiceNotFound as e:
            raise RuntimeError(str(e)) from e
        except Exception as e:
            raise RuntimeError(f"Piper TTS error: {e}") from e

        save_to_cache(audio_bytes, text, voice, rate)
        return audio_bytes, "audio/wav"

    try:
        audio_path = asyncio.run(_generate_edge_audio(text, voice, rate, pitch))
    except Exception as e:
        raise RuntimeError(f"Edge TTS error: {e}") from e

    try:
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)

    save_to_cache(audio_bytes, text, voice, rate)
    return audio_bytes, "audio/mpeg"
