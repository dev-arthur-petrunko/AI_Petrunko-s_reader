# Petrunko's Reader

Web app that converts Markdown into a beautifully formatted single-page site with high-quality TTS (Microsoft Neural voices via edge-tts) and click-to-read functionality.

## Features

### Markdown Editor
- Code-editor style input area with syntax dots and character counter
- Full GFM support: headings (`#`), bold, italic, inline code, code blocks, lists, tables, blockquotes, links, images, horizontal rules
- GFM tables rendered as styled HTML tables with alternating row backgrounds
- Code blocks syntax-highlighted with highlight.js (Atom One Dark theme)
- `Ctrl+Enter` shortcut to open reading mode
- 4 built-in samples: Markdown, Python code, Table, Article
- Text saved to localStorage between sessions

### Reading Mode
- Clean typographic layout with Merriweather serif font, justified text, proper margins
- Article rendered in a white card with subtle shadows
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
- Voice selector dropdown showing voice name + gender (♂ Male / ♀ Female)
- Voice preference saved to localStorage, persists between sessions
- Auto-detect language from text content, pre-select matching voice
- 6 speed presets: 0.7x, 0.85x, 1x (default), 1.15x, 1.3x, 1.5x
- Progress bar with percentage and chunk counter (e.g. "5/12")
- Play / Pause / Resume / Stop controls
- Markdown syntax cleaned before TTS — strips `#`, `**`, `|`, backticks, links, so voice reads clean text
- Fallback to browser `speechSynthesis` API when backend unavailable
- Engine badge shows current mode: "edge-tts" (green) or "browser" (orange)

### Supported Languages
| Language | Locale | Default Voice |
|---|---|---|
| Українська | uk-UA | Polina (♀), Ostap (♂) |
| Русский | ru-RU | Svetlana (♀), Dmitry (♂) |
| Polski | pl-PL | Zofia (♀), Marek (♂) |
| English (US) | en-US | Ava, Emma, Brian, Guy, + 9 more |
| English (UK) | en-GB | Sonia, Libby, Ryan, + 2 more |
| Deutsch | de-DE | Katja, Conrad, Amala, Killian |
| Français | fr-FR | Denise, Eloise, Henri |
| Español | es-ES | Elvira, Alvaro, Ximena |
| Português (BR) | pt-BR | Francisca, Antonio |
| Italiano | it-IT | Elsa, Diego, Isabella |
| 日本語 | ja-JP | Nanami (♀), Keita (♂) |
| 中文 | zh-CN | Xiaoxiao, Yunxi, + 3 more |
| 한국어 | ko-KR | SunHi (♀), InJoon (♂) |
| Čeština | cs-CZ | Vlasta (♀), Antonin (♂) |
| Türkçe | tr-TR | Emel (♀), Ahmet (♂) |
| العربية | ar-SA | Zariyah (♀), Hamed (♂) |
| हिन्दी | hi-IN | Swara (♀), Madhur (♂) |
| Magyar | hu-HU | Noemi (♀), Tamas (♂) |
| Română | ro-RO | Alina (♀), Emil (♂) |
| Svenska | sv-SE | Sofie (♀), Mattias (♂) |
| Norsk | nb-NO | Pernille (♀), Finn (♂) |
| Suomi | fi-FI | Noora (♀), Harri (♂) |
| Nederlands | nl-NL | Colette, Fenna (♀), Maarten (♂) |

### Theme Toggle
- Button in top-right corner (☀️ / 🌙) toggles between themes
- **Dark mode** (default):
  - Editor: deep dark background (#0f0f14) with purple accent glow
  - Reader: dark background with purple accent colors, light text
  - Animated gradient background on editor screen
- **Light mode**:
  - Editor: soft light gray background with purple accents
  - Reader: warm cream background (#fdfbf7) with brown typography (classic book feel)
  - Same Merriweather serif font for comfortable reading
- Preference saved to localStorage, persists between sessions
- Smooth CSS transitions on theme switch

## Project Structure

```
ЧИТАЛКА/
├── app.py              # Flask backend (local/Render) — serves static + TTS API
├── api/
│   └── index.py        # Flask backend (Vercel serverless) — API routes only
├── index.html           # Single-page frontend (editor + reader + TTS controls)
├── requirements.txt     # Python deps: flask, gunicorn, edge-tts
├── vercel.json          # Vercel config — maxDuration: 60s
├── .gitignore           # __pycache__, .env, node_modules
└── README.md            # This file
```

## Run Locally

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

## Deploy to Vercel

1. Push to GitHub:
```bash
git push origin main
```

2. On Vercel dashboard:
   - Import the repo `AI_Petrunko-s_reader`
   - Framework: **Other**
   - Build command: _(leave empty)_
   - Output directory: _(leave empty)_
   - Deploy

3. After each push, on Vercel: **Redeploy → Skip Build Cache**

## Tech Stack

- **Backend**: Python, Flask, edge-tts (Microsoft Neural voices)
- **Frontend**: Vanilla JavaScript (no framework), marked.js v4.3.0, highlight.js v11.9.0
- **Fonts**: Inter (UI), JetBrains Mono (code), Merriweather (reading) via Google Fonts
- **Hosting**: Vercel (serverless functions) or local Flask server
- **Data**: localStorage for theme, voice, text persistence (no database)
