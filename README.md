# Petrunko's Reader

Web app that converts Markdown into a beautifully formatted single-page site with high-quality TTS (Microsoft Neural voices via edge-tts + Piper TTS for Ukrainian) and click-to-read functionality.

## Features

### Markdown Editor
- Code-editor style input area with syntax dots and character counter
- Full GFM support: headings, bold, italic, inline code, code blocks, lists, tables, blockquotes, links, images, horizontal rules
- GFM tables rendered as styled HTML tables with alternating row backgrounds
- Code blocks syntax-highlighted with highlight.js (Atom One Dark theme)
- `Ctrl+Enter` shortcut to open reading mode
- 4 built-in samples: Markdown, Python code, Table, Article
- Text saved to localStorage between sessions

### Reading Mode
- Clean typographic layout with Merriweather serif font, justified text, proper margins
- Article rendered in a card with subtle shadows
- Word count and auto-detected language shown in header
- Back button to return to editor

### Click-to-Read
- Every paragraph, heading, and list item is individually clickable
- Click any element to start TTS reading from that exact point
- Purple left-border indicator highlights the currently playing chunk
- Auto-scroll follows the voice position
- Click the same element again to stop

### TTS (Text-to-Speech)
- **edge-tts** backend — Microsoft Azure Neural voices, 80+ voices across 22 languages
- Voice selector dropdown showing voice name + gender (Male / Female)
- Voice preference saved to localStorage
- Auto-detect language from text content, pre-select matching voice
- 6 speed presets: 0.7x — 1.5x
- Progress bar with percentage and chunk counter
- Play / Pause / Resume / Stop controls
- Markdown syntax cleaned before TTS (no reading `#`, `|`, backticks)
- Fallback to browser `speechSynthesis` API when backend unavailable
- Audio caching by SHA-256 hash of (text + voice + rate)

### Piper TTS (Local Ukrainian Voices)
- **Piper** engine — fully local, free, no API keys, no external server calls
- 4 Ukrainian voice models: 3 speakers from `ukrainian-tts-medium` + compact `lada` model
- Shows "Piper (local)" badge in voice selector, "edge-tts" for cloud voices
- Same speed slider works for both engines (rate converted to Piper's length_scale)
- Audio cached as WAV (Piper) or MP3 (edge-tts) by content hash
- Models must be downloaded once before first run (see Setup below)

### Supported Languages
22 languages: Ukrainian, Russian, Polish, English (US/UK), German, French, Spanish, Portuguese, Italian, Japanese, Chinese, Korean, Czech, Turkish, Arabic, Hindi, Hungarian, Romanian, Swedish, Norwegian, Finnish, Dutch.

### Theme Toggle
- Button in top-right corner (sun/moon icon) toggles between dark and light modes
- Dark mode: dark editor + dark reading screen with purple accents
- Light mode: light editor + warm cream reading screen
- Preference saved to localStorage

### Security
- **XSS protection**: DOMPurify sanitizes rendered Markdown HTML
- **Voice validation**: only known voice names accepted by API
- **Text length limit**: max 5000 characters per TTS request
- **MAX_CONTENT_LENGTH**: 1 MB max request size
- **Path traversal protection**: static file routes validated against BASE_DIR
- **Rate limiting**: flask-limiter (30 TTS requests/minute, 60 general/minute)
- **CORS**: controlled Access-Control headers on API routes
- **Temp file cleanup**: guaranteed via finally blocks

## Project Structure

```
ЧИТАЛКА/
├── app/                   # Flask application package
│   ├── __init__.py        # App factory (create_app)
│   ├── config.py          # Constants: voices, limits, paths
│   ├── routes.py          # API routes + static file serving
│   └── tts.py             # edge-tts + Piper wrapper with caching
├── api/
│   └── index.py           # Vercel serverless entry (standalone)
├── piper_engine.py        # Piper TTS local engine (Ukrainian voices)
├── piper_voices/          # Downloaded .onnx models (gitignored)
├── index.html             # Frontend: editor + reader + TTS controls
├── run.py                 # Local/Render entry point
├── requirements.txt       # Pinned Python dependencies
├── vercel.json            # Vercel config — maxDuration: 60s
├── .gitignore
└── README.md
```

## Run Locally

```bash
pip install -r requirements.txt
python run.py
```

Open http://localhost:5000

With gunicorn:
```bash
gunicorn "run:app" --bind 0.0.0.0:5000
```

## Download Piper Voice Models (one time)

Piper voices require `.onnx` model files to be downloaded once:

```bash
python -m piper.download_voices uk_UA-ukrainian_tts-medium --download-dir ./piper_voices
python -m piper.download_voices uk_UA-lada-x_low --download-dir ./piper_voices
```

This creates `./piper_voices/` with `.onnx` + `.onnx.json` files.
On Render, set `PIPER_VOICES_DIR` env var to a persistent disk path.

## Deploy to Vercel

1. Push to GitHub
2. On Vercel: import repo, Framework: **Other**, no build command
3. After each push: **Redeploy → Skip Build Cache**

## Tech Stack

- **Backend**: Python 3.11+, Flask 3.1, edge-tts 7.2, piper-tts 1.2, flask-limiter 3.12
- **Frontend**: Vanilla JS, marked.js 4.3, highlight.js 11.9, DOMPurify 3.1
- **Fonts**: Inter (UI), JetBrains Mono (code), Merriweather (reading)
- **Hosting**: Vercel (serverless) or local Flask/gunicorn
- **Data**: localStorage only (no database)
