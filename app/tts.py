"""Text-to-Speech service using edge-tts."""

import os
import asyncio
import hashlib
import tempfile
from typing import Optional

import edge_tts

from app.config import CACHE_DIR


def cache_key(text: str, voice: str, rate: str) -> str:
    """Generate SHA-256 cache key from TTS parameters."""
    return hashlib.sha256(f"{text}|{voice}|{rate}".encode()).hexdigest()


def get_cached_path(text: str, voice: str, rate: str) -> Optional[str]:
    """Return path to cached MP3 if it exists, else None."""
    path = os.path.join(CACHE_DIR, f"{cache_key(text, voice, rate)}.mp3")
    return path if os.path.exists(path) else None


def save_to_cache(audio_bytes: bytes, text: str, voice: str, rate: str) -> str:
    """Save audio bytes to cache and return the path."""
    path = os.path.join(CACHE_DIR, f"{cache_key(text, voice, rate)}.mp3")
    with open(path, "wb") as f:
        f.write(audio_bytes)
    return path


async def _generate_audio(text: str, voice: str, rate: str, pitch: str) -> str:
    """Generate MP3 audio from text using edge-tts. Returns temp file path."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp.close()
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(tmp.name)
    return tmp.name


def generate_audio_sync(text: str, voice: str, rate: str, pitch: str) -> bytes:
    """Generate TTS audio synchronously. Returns audio bytes.

    Tries cache first. On miss, generates via edge-tts, caches result,
    and returns the audio bytes.

    Raises:
        RuntimeError: If edge-tts generation fails.
    """
    cached = get_cached_path(text, voice, rate)
    if cached:
        with open(cached, "rb") as f:
            return f.read()

    try:
        audio_path = asyncio.run(_generate_audio(text, voice, rate, pitch))
    except Exception as e:
        raise RuntimeError(f"TTS generation failed: {e}") from e

    try:
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)

    save_to_cache(audio_bytes, text, voice, rate)
    return audio_bytes
