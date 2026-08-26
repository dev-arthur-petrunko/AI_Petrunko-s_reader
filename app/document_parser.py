"""Парсер документів: PDF, EPUB, FB2, MOBI/AZW3 → текст."""

import io
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def parse_pdf(data: bytes) -> str:
    """Текст з PDF."""
    from PyPDF2 import PdfReader
    reader = PdfReader(io.BytesIO(data))
    parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def parse_epub(data: bytes) -> str:
    """Текст з EPUB (зберігає порядок глав)."""
    from ebooklib import epub
    from lxml import etree

    book = epub.read_epub(io.BytesIO(data), options={"ignore_ncx": True, "ignore_smil": True})
    parts = []

    for item in book.get_items():
        if item.get_type() == 9:
            html = item.get_content()
            try:
                tree = etree.HTML(html)
                text = etree.tostring(tree, method="text", encoding="unicode")
                text = text.strip()
                if text:
                    parts.append(text)
            except Exception:
                pass

    return "\n\n".join(parts)


def parse_fb2(data: bytes) -> str:
    """Текст з FB2 ( FictionBook2, XML-формат)."""
    from lxml import etree

    tree = etree.parse(io.BytesIO(data))
    ns = {"fb": "http://www.gribuser.ru/xml/fictionbook/2.0"}

    parts = []

    for body in tree.xpath("//fb:body", namespaces=ns):
        for elem in body.iter():
            tag = etree.QName(elem.tag).localname if isinstance(elem.tag, str) else ""
            if tag in ("p", "subtitle", "title", "epigraph", "cite", "text-author"):
                text = etree.tostring(elem, method="text", encoding="unicode").strip()
                if text:
                    parts.append(text)
            elif tag == "empty-line":
                parts.append("")

    return "\n".join(parts)


def parse_mobi(data: bytes) -> str:
    """Текст з MOBI/AZW3."""
    import tempfile
    import mobi

    tmp_dir = tempfile.mkdtemp()
    try:
        tmp_path = os.path.join(tmp_dir, "book.mobi")
        with open(tmp_path, "wb") as f:
            f.write(data)

        result = mobi.extract(tmp_path)

        opf_path = result.get("opf")
        if not opf_path:
            html_path = result.get("html")
            if not html_path:
                return ""
            with open(html_path, "r", encoding="utf-8", errors="replace") as f:
                html = f.read()
        else:
            opf_dir = os.path.dirname(opf_path)
            with open(opf_path, "r", encoding="utf-8", errors="replace") as f:
                opf = f.read()

            from lxml import etree
            tree = etree.parse(io.BytesIO(opf.encode()))
            ns = {"opf": "http://www.idpf.org/2007/opf"}
            spine = tree.xpath("//opf:spine/opf:itemref/@idref", namespaces=ns)

            manifest_ns = {"opf": "http://www.idpf.org/2007/opf"}
            manifest = tree.xpath("//opf:manifest/opf:item", namespaces=ns)
            id_to_href = {}
            for item in manifest:
                item_id = item.get("id")
                href = item.get("href")
                if item_id and href:
                    id_to_href[item_id] = href

            parts = []
            for item_id in spine:
                href = id_to_href.get(item_id)
                if href:
                    fpath = os.path.join(opf_dir, href)
                    if os.path.exists(fpath):
                        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                            html = f.read()
                        from lxml import etree as et
                        tree_html = et.HTML(html)
                        text = et.tostring(tree_html, method="text", encoding="unicode").strip()
                        if text:
                            parts.append(text)

            return "\n\n".join(parts)

        from lxml import etree
        tree = etree.HTML(html)
        text = etree.tostring(tree, method="text", encoding="unicode")
        return text.strip()

    except Exception as e:
        logger.error("MOBI parse error: %s", e)
        raise
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


PARSERS = {
    ".pdf": parse_pdf,
    ".epub": parse_epub,
    ".fb2": parse_fb2,
    ".mobi": parse_mobi,
    ".azw3": parse_mobi,
}


def parse_document(filename: str, data: bytes) -> tuple[str, str]:
    """Розпізнає формат за розширенням та повертає (текст, формат).

    Повертає (порожній рядок, "") якщо формат не підтримується.
    """
    ext = os.path.splitext(filename)[1].lower()
    parser = PARSERS.get(ext)
    if not parser:
        return "", ""
    try:
        text = parser(data)
        fmt = ext.lstrip(".")
        return text, fmt
    except Exception as e:
        logger.error("Parse error for %s: %s", filename, e)
        raise
