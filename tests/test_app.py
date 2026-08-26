"""Tests for Petrunko's Reader Flask app."""
import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app


MOCK_AUDIO = b"\x00" * 100  # fake audio bytes


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestHealthCheck:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok"}


class TestVoicesEndpoint:
    def test_voices_returns_200(self, client):
        resp = client.get("/api/tts/voices")
        assert resp.status_code == 200

    def test_voices_has_expected_languages(self, client):
        data = client.get("/api/tts/voices").get_json()
        voices = data["voices"]
        for lang in ["uk-UA", "en-US", "ru-RU", "de-DE", "fr-FR", "ja-JP", "pl-PL"]:
            assert lang in voices, f"Missing language: {lang}"

    def test_voices_has_piper_labels(self, client):
        data = client.get("/api/tts/voices").get_json()
        labels = data["voice_labels"]
        assert "piper:uk_UA-ukrainian_tts-medium-0" in labels
        assert "piper:uk_UA-lada-x_low" in labels


class TestTTSValidation:
    def test_no_text_returns_400(self, client):
        resp = client.post(
            "/api/tts",
            data=json.dumps({"text": "", "voice": "uk-UA-PolinaNeural"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_no_text_field_returns_400(self, client):
        resp = client.post(
            "/api/tts",
            data=json.dumps({"voice": "uk-UA-PolinaNeural"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_invalid_voice_returns_400(self, client):
        resp = client.post(
            "/api/tts",
            data=json.dumps({"text": "Hello", "voice": "nonexistent-voice"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_text_too_long_returns_413(self, client):
        resp = client.post(
            "/api/tts",
            data=json.dumps({"text": "a" * 60000, "voice": "uk-UA-PolinaNeural"}),
            content_type="application/json",
        )
        assert resp.status_code == 413

    def test_text_one_over_limit_rejected(self, client):
        resp = client.post(
            "/api/tts",
            data=json.dumps({"text": "a" * 50001, "voice": "en-US-AvaNeural"}),
            content_type="application/json",
        )
        assert resp.status_code == 413

    @patch("app.routes.generate_audio_sync", return_value=(MOCK_AUDIO, "audio/mpeg"))
    def test_valid_request_returns_audio(self, mock_gen, client):
        resp = client.post(
            "/api/tts",
            data=json.dumps({"text": "Hello world", "voice": "en-US-AvaNeural", "rate": "+0%"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.content_type == "audio/mpeg"
        mock_gen.assert_called_once()

    @patch("app.routes.generate_audio_sync", side_effect=RuntimeError("Piper TTS not installed"))
    def test_piper_not_installed_returns_503(self, mock_gen, client):
        resp = client.post(
            "/api/tts",
            data=json.dumps({"text": "Test", "voice": "piper:uk_UA-ukrainian_tts-medium-0"}),
            content_type="application/json",
        )
        assert resp.status_code == 503

    @patch("app.routes.generate_audio_sync", side_effect=RuntimeError("Some other error"))
    def test_generation_error_returns_500(self, mock_gen, client):
        resp = client.post(
            "/api/tts",
            data=json.dumps({"text": "Test", "voice": "en-US-AvaNeural"}),
            content_type="application/json",
        )
        assert resp.status_code == 500


class TestStaticSecurity:
    def test_root_serves_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Petrunko" in resp.data

    def test_app_py_returns_404(self, client):
        resp = client.get("/app.py")
        assert resp.status_code == 404

    def test_requirements_returns_404(self, client):
        resp = client.get("/requirements.txt")
        assert resp.status_code == 404

    def test_run_py_returns_404(self, client):
        resp = client.get("/run.py")
        assert resp.status_code == 404

    def test_config_py_returns_404(self, client):
        resp = client.get("/app/config.py")
        assert resp.status_code == 404

    def test_routes_py_returns_404(self, client):
        resp = client.get("/app/routes.py")
        assert resp.status_code == 404


class TestStripMarkdown:
    def test_headers_stripped(self):
        from app.tts import strip_markdown_for_tts
        result = strip_markdown_for_tts("# Hello\n## World")
        assert "#" not in result
        assert "Hello" in result
        assert "World" in result

    def test_bold_italic_stripped(self):
        from app.tts import strip_markdown_for_tts
        result = strip_markdown_for_tts("**bold** and *italic*")
        assert "**" not in result
        assert "*" not in result
        assert "bold" in result
        assert "italic" in result

    def test_links_stripped(self):
        from app.tts import strip_markdown_for_tts
        result = strip_markdown_for_tts("[Google](https://google.com)")
        assert "[" not in result
        assert "]" not in result
        assert "(" not in result
        assert "Google" in result

    def test_code_blocks_stripped(self):
        from app.tts import strip_markdown_for_tts
        result = strip_markdown_for_tts("text\n```python\nprint(1)\n```\nmore")
        assert "```" not in result
        assert "print(1)" not in result
        assert "text" in result
        assert "more" in result

    def test_inline_code_stripped(self):
        from app.tts import strip_markdown_for_tts
        result = strip_markdown_for_tts("use `pip install foo` now")
        assert "`" not in result
        assert "pip install foo" not in result
        assert "use" in result

    def test_table_converted(self):
        from app.tts import strip_markdown_for_tts
        result = strip_markdown_for_tts("| a | b |\n|---|---|\n| 1 | 2 |")
        assert "|" not in result
        assert "a" in result
        assert "b" in result

    def test_blockquote_stripped(self):
        from app.tts import strip_markdown_for_tts
        result = strip_markdown_for_tts("> Important text")
        assert ">" not in result
        assert "Important text" in result

    def test_images_removed(self):
        from app.tts import strip_markdown_for_tts
        result = strip_markdown_for_tts("![alt](http://img.png) text")
        assert "!" not in result
        assert "text" in result

    def test_complex_markdown(self):
        from app.tts import strip_markdown_for_tts
        md = "# Title\n\n**Bold** [link](http://x.com)\n\n```\ncode\n```\n\n> quote"
        result = strip_markdown_for_tts(md)
        for sym in ["#", "**", "[", "]", "(", ")", "```", ">"]:
            assert sym not in result, f"Found '{sym}' in result"


class TestPiperVoices:
    def test_piper_voices_in_ukraine_list(self, client):
        data = client.get("/api/tts/voices").get_json()
        uk_voices = data["voices"]["uk-UA"]
        piper_voices = [v for v in uk_voices if v.startswith("piper:")]
        assert len(piper_voices) == 4


class TestKnowledgeBase:
    def test_list_empty(self, client):
        r = client.get("/api/docs")
        assert r.status_code == 200
        data = r.get_json()
        assert "documents" in data

    def test_upload_json(self, client):
        r = client.post("/api/docs", json={"title": "Test", "content": "Hello world"})
        assert r.status_code == 201
        data = r.get_json()
        assert data["title"] == "Test"
        assert data["word_count"] == 2

    def test_upload_empty(self, client):
        r = client.post("/api/docs", json={"title": "", "content": ""})
        assert r.status_code == 400

    def test_get_document(self, client):
        r = client.post("/api/docs", json={"title": "Doc1", "content": "Some text here"})
        doc_id = r.get_json()["id"]
        r2 = client.get(f"/api/docs/{doc_id}")
        assert r2.status_code == 200
        assert r2.get_json()["content"] == "Some text here"

    def test_get_nonexistent(self, client):
        r = client.get("/api/docs/99999")
        assert r.status_code == 404

    def test_delete_document(self, client):
        r = client.post("/api/docs", json={"title": "Delete me", "content": "trash"})
        doc_id = r.get_json()["id"]
        r2 = client.delete(f"/api/docs/{doc_id}")
        assert r2.status_code == 200
        assert r2.get_json()["deleted"] is True
        r3 = client.get(f"/api/docs/{doc_id}")
        assert r3.status_code == 404

    def test_delete_nonexistent(self, client):
        r = client.delete("/api/docs/99999")
        assert r.status_code == 404

    def test_search(self, client):
        client.post("/api/docs", json={"title": "Python guide", "content": "Learn Python"})
        client.post("/api/docs", json={"title": "JS basics", "content": "Learn JavaScript"})
        r = client.get("/api/docs?q=Python")
        docs = r.get_json()["documents"]
        assert len(docs) >= 1
        assert any("Python" in d["title"] for d in docs)
