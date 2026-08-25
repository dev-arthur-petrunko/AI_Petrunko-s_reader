# Petrunko's Reader

Markdown → formatted page with TTS. Paste text, read aloud.

## Features

### Markdown Editor
- Dark code-editor style input area
- Syntax: headings, bold, italic, lists, tables, blockquotes, code blocks, links, images
- GFM tables rendered as styled HTML tables
- Code blocks highlighted with highlight.js (Atom One Dark)
- 4 built-in samples: Markdown, Python, Table, Article

### Reading Mode
- Cream/warm typography (Merriweather serif) for long reading
- `Ctrl+Enter` or button to open
- Word count and detected language shown in header

### Click-to-Read
- Every paragraph, heading, and list item is clickable
- Click any element → TTS starts from that point
- Purple left-border indicator on the currently reading chunk
- Auto-scroll follows the voice

### TTS (Text-to-Speech)
- **edge-tts** backend — Microsoft Neural voices, 322 voices, 22 languages
- Voice selector with gender labels (♂/♀)
- Auto-detect language from text, pre-select voice
- 6 speed options (0.7x – 1.5x)
- Progress bar and chunk counter
- Pause/Resume/Stop controls
- Fallback to browser `speechSynthesis` if backend unavailable
- Markdown syntax cleaned before sending to TTS (no more reading `#` or `|`)

### Languages
Ukrainian, Russian, Polish, English (US/UK), German, French, Spanish, Portuguese, Italian, Japanese, Chinese, Korean, Czech, Turkish, Arabic, Hindi, Hungarian, Romanian, Swedish, Norwegian, Finnish, Dutch

### Theme Toggle
- **Dark mode** (default) — dark editor + dark reading screen
- **Light mode** — light editor + warm cream reading screen
- Toggle button (☀️/🌙) in top-right corner
- Preference saved to localStorage

## Run Locally

```bash
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000`

## Deploy to Vercel

The repo includes `vercel.json` pointing to `api/index.py` as a serverless function.

```bash
git push origin main
```

Then on Vercel dashboard: **Redeploy → Skip Build Cache**

## Tech Stack

- **Backend**: Flask + edge-tts (Python)
- **Frontend**: Vanilla JS, marked.js, highlight.js
- **Fonts**: Inter, JetBrains Mono, Merriweather (Google Fonts)
- **Hosting**: Vercel (serverless) or local
