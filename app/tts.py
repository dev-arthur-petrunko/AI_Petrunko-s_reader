"""Сервіс TTS: edge-tts (хмарний) + Piper (локальний)."""

import os
import re
import time
import asyncio
import hashlib
import logging
import tempfile
from typing import Optional

import edge_tts

from app.config import CACHE_DIR

logger = logging.getLogger(__name__)

try:
    import piper_engine
    PIPER_AVAILABLE = True
except ImportError:
    PIPER_AVAILABLE = False


def strip_markdown_for_tts(text: str) -> str:
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


def cache_key(text: str, voice: str, rate: str) -> str:
    return hashlib.sha256(f"{text}|{voice}|{rate}".encode()).hexdigest()


def get_cached_path(text: str, voice: str, rate: str) -> Optional[str]:
    ext = ".wav" if voice.startswith("piper:") else ".mp3"
    path = os.path.join(CACHE_DIR, f"{cache_key(text, voice, rate)}{ext}")
    return path if os.path.exists(path) else None


def save_to_cache(audio_bytes: bytes, text: str, voice: str, rate: str) -> str:
    ext = ".wav" if voice.startswith("piper:") else ".mp3"
    path = os.path.join(CACHE_DIR, f"{cache_key(text, voice, rate)}{ext}")
    with open(path, "wb") as f:
        f.write(audio_bytes)
    return path


def cleanup_cache(max_age_days: int = 7) -> int:
    if not os.path.isdir(CACHE_DIR):
        return 0
    cutoff = time.time() - (max_age_days * 86400)
    removed = 0
    for fname in os.listdir(CACHE_DIR):
        fpath = os.path.join(CACHE_DIR, fname)
        try:
            if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                os.unlink(fpath)
                removed += 1
        except OSError:
            pass
    if removed:
        logger.info("Cache cleanup: removed %d files older than %d days", removed, max_age_days)
    return removed


def rate_to_length_scale(rate: str) -> float:
    try:
        percent = int(rate.replace("%", "").replace("+", ""))
    except ValueError:
        return 1.0
    return 1.0 - (percent / 100.0)


async def _generate_edge_audio(text: str, voice: str, rate: str, pitch: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp.close()
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(tmp.name)
    return tmp.name


def generate_audio_sync(text: str, voice: str, rate: str, pitch: str) -> tuple[bytes, str]:
    cleaned = strip_markdown_for_tts(text)

    cached = get_cached_path(cleaned, voice, rate)
    if cached:
        with open(cached, "rb") as f:
            mime = "audio/wav" if cached.endswith(".wav") else "audio/mpeg"
            return f.read(), mime

    if voice.startswith("piper:"):
        if not PIPER_AVAILABLE:
            raise RuntimeError("Piper TTS not installed. Run: pip install piper-tts")
        try:
            length_scale = rate_to_length_scale(rate)
            audio_bytes = piper_engine.synthesize_wav(cleaned, voice, length_scale)
        except piper_engine.PiperVoiceNotFound as e:
            raise RuntimeError(str(e)) from e
        except Exception as e:
            raise RuntimeError(f"Piper TTS error: {e}") from e

        save_to_cache(audio_bytes, cleaned, voice, rate)
        return audio_bytes, "audio/wav"

    try:
        audio_path = asyncio.run(_generate_edge_audio(cleaned, voice, rate, pitch))
    except Exception as e:
        raise RuntimeError(f"Edge TTS error: {e}") from e

    try:
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)

    save_to_cache(audio_bytes, cleaned, voice, rate)
    return audio_bytes, "audio/mpeg"
