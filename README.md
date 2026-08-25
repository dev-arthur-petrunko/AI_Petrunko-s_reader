# Petrunko's Reader

Convert any Markdown text into a beautifully formatted, readable web page with high-quality text-to-speech powered by Microsoft Neural voices.

## Features

- **Markdown Rendering** — headings, lists, tables, code blocks with syntax highlighting, blockquotes, images, links
- **High-Quality TTS** — edge-tts with Microsoft Neural voices (Polina, Dmitry, Jenny, Guy, and 20+ more)
- **13 Languages** — Ukrainian, Russian, Polish, English, German, French, Spanish, Portuguese, Italian, Japanese, Chinese, Korean, Czech
- **Auto Language Detection** — the app detects the text language and selects the appropriate voice
- **Voice Selection** — choose between male and female voices for each language
- **Speed Control** — adjustable reading speed from 0.7x to 1.5x
- **Warm Reading Theme** — serif typography (Merriweather) optimized for long-form reading
- **Dark Code Blocks** — Atom One Dark theme with highlight.js syntax highlighting
- **Responsive Design** — works on desktop and mobile

## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

## Deploy on Render

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your repo
4. Render auto-detects Python and uses `render.yaml` config
5. Deploy — done

## Tech Stack

- **Backend:** Python, Flask, edge-tts
- **Frontend:** Vanilla JS, marked.js, highlight.js
- **Fonts:** Inter, Merriweather, JetBrains Mono

## API

| Endpoint | Method | Description |
|---|---|---|
| `/api/tts` | POST | Generate audio from text. Body: `{"text": "...", "voice": "uk-UA-PolinaNeural", "rate": "+0%"}` |
| `/api/tts/voices` | GET | List available voices |

## License

MIT
