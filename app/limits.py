"""Спільна точка налаштування лімітів — використовують і локальний сервер, і Vercel serverless.

Під час читання довгого тексту (особливо з таблицями) клієнт робить по кілька запитів
на абзац: основний голос + англійські сегменти + попереднє завантаження. 60/minute
виявилося замало — клієнт отримував 429, відкочувався у голос браузера і текст
«пропускався».

Тут лише загальний default_limits, а не окремі ліміти per-route: у локального сервера
сигнатура `open(...)` вже зареєстрована через Blueprint (view_functions: api.tts_generate),
а на Vercel — прямими маршрутами (tts_generate). Загальний ліміт покриває обидві точки
входу однаково, без залежності від префікса endpoint.
"""

# Загальний ліміт для всіх маршрутів API (голос читає довгий текст багатьма короткими запитами)
API_RATE_LIMIT = "600/minute"


def apply_limits(app):
    """Накладає загальний ліміт на всі маршрути або тихо пропускає, якщо flask-limiter немає."""
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
    except Exception:  # ImportError — лімітер не встановлено (типово на serverless-збірці)
        return None

    limiter = Limiter(get_remote_address, app=app, default_limits=[API_RATE_LIMIT])
    # flask-limiter підсовує себе під app.limiter сам; залишаємо явний атрибут
    if not hasattr(app, "limiter"):
        app.limiter = limiter
    return limiter
