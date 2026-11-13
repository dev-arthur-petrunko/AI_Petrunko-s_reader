"""Сервіс TTS: edge-tts (хмарний) + Piper (локальний)."""

import os
import re
import time
import asyncio
import hashlib
import logging
import tempfile
import threading
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


def cache_key(text: str, voice: str, rate: str, pitch: str = "+0Hz") -> str:
    return hashlib.sha256(f"{text}|{voice}|{rate}|{pitch}".encode()).hexdigest()


def get_cached_path(text: str, voice: str, rate: str, pitch: str = "+0Hz") -> Optional[str]:
    ext = ".wav" if voice.startswith("piper:") else ".mp3"
    path = os.path.join(CACHE_DIR, f"{cache_key(text, voice, rate, pitch)}{ext}")
    return path if os.path.exists(path) else None


MAX_CACHE_FILES: int = 800


def _prune_cache_if_large(target: int = 600) -> None:
    """Видаляє найстаріші файли, якщо кеш розрісся."""
    try:
        entries = [
            (os.path.getmtime(os.path.join(CACHE_DIR, name)), name)
            for name in os.listdir(CACHE_DIR)
            if os.path.isfile(os.path.join(CACHE_DIR, name))
        ]
    except OSError:
        return
    if len(entries) <= MAX_CACHE_FILES:
        return
    entries.sort()
    removed = 0
    for _mtime, name in entries[: len(entries) - target]:
        try:
            os.unlink(os.path.join(CACHE_DIR, name))
            removed += 1
        except OSError:
            pass
    if removed:
        logger.info("Cache prune: removed %d oldest files", removed)


def save_to_cache(audio_bytes: bytes, text: str, voice: str, rate: str, pitch: str = "+0Hz") -> str:
    ext = ".wav" if voice.startswith("piper:") else ".mp3"
    path = os.path.join(CACHE_DIR, f"{cache_key(text, voice, rate, pitch)}{ext}")
    # пишемо через тимчасовий файл + atomic replace: паралельний запит ніколи
    # не прочитає недописаний MP3 (інакше можливе «бите»/обірване аудіо)
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(audio_bytes)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
    _prune_cache_if_large()
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


async def _generate_edge_audio(
    text: str, voice: str, rate: str, pitch: str, attempts: int = 2, attempt_timeout: float = 10.0
) -> str:
    """Синтез через edge-tts із повторними спробами (Microsoft інколи троттлить IP → 403/порожньо).

    Кожна спроба обмежена timeout, щоб зависання websocket не блокувало запит назавжди —
    інакше відтворення «зависає» і не починає читати далі. Дві спроби по 10с дають
    передбачувану стелю ~21с: стільки ж чекає клієнт, тому голос не «срибає» на браузерний
    через довгий, але успішний синтез.
    """
    last_err: Optional[Exception] = None
    for attempt in range(attempts):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp.close()
        try:
            communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
            await asyncio.wait_for(communicate.save(tmp.name), timeout=attempt_timeout)
            if os.path.getsize(tmp.name) > 0:
                return tmp.name
            raise RuntimeError("edge-tts повернув порожній файл")
        except asyncio.TimeoutError:
            last_err = RuntimeError(f"edge-tts перевищив час очікування ({attempt_timeout:.0f}с)")
        except Exception as e:
            last_err = e
        if os.path.exists(tmp.name):
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
        if last_err and attempt < attempts - 1:
            await asyncio.sleep(0.6 * (attempt + 1))
    raise last_err if last_err else RuntimeError("edge-tts не вдалося")


def _synthesize(cleaned: str, voice: str, rate: str, pitch: str) -> tuple[bytes, str]:
    """Безпосередній синтез без кешу та дедуплікації."""
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
    return audio_bytes, "audio/mpeg"


# Дедуплікація одночасних запитів: клієнт обриває повільний запит за таймаутом
# і одразу повторює його. Без цього сервер починав синтез заново (подвійна робота
# і знову ризик не встигнути). Тепер повторний запит чекає вже запущений синтез
# і віддає готовий файл із кешу.
_inflight_lock = threading.Lock()
_inflight: dict[str, threading.Event] = {}
INFLIGHT_WAIT_TIMEOUT: float = 30.0


def _read_cached(path: str) -> tuple[bytes, str]:
    with open(path, "rb") as f:
        mime = "audio/wav" if path.endswith(".wav") else "audio/mpeg"
        return f.read(), mime


def generate_audio_sync(text: str, voice: str, rate: str, pitch: str) -> tuple[bytes, str]:
    cleaned = strip_markdown_for_tts(text)

    cached = get_cached_path(cleaned, voice, rate, pitch)
    if cached:
        return _read_cached(cached)

    key = cache_key(cleaned, voice, rate, pitch)
    with _inflight_lock:
        event = _inflight.get(key)
        is_owner = event is None
        if is_owner:
            event = threading.Event()
            _inflight[key] = event

    if not is_owner:
        # хтось уже синтезує цей самий текст — дочекаємось результату в кеші
        event.wait(INFLIGHT_WAIT_TIMEOUT)
        cached = get_cached_path(cleaned, voice, rate, pitch)
        if cached:
            return _read_cached(cached)

    try:
        audio_bytes, mime = _synthesize(cleaned, voice, rate, pitch)
        save_to_cache(audio_bytes, cleaned, voice, rate, pitch)
        return audio_bytes, mime
    finally:
        if is_owner:
            with _inflight_lock:
                _inflight.pop(key, None)
            event.set()
