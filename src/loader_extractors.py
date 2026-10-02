#!/usr/bin/env python3
"""Парсеры контента: HTML, Markdown, DOCX, PDF."""
import re, sys
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field

try:
    from .loader_core import detect_tags, assess_usefulness, detect_category
except ImportError:
    from loader_core import detect_tags, assess_usefulness, detect_category

try:
    import requests
except ImportError:
    requests = None
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
try:
    import markdown
except ImportError:
    markdown = None
try:
    import docx
except ImportError:
    docx = None
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None


@dataclass
class ParsedContent:
    """Результат парсинга документа."""
    title: str = ""
    content: str = ""
    category: str = "language"
    tags: List[str] = field(default_factory=list)
    has_code: bool = False
    is_useful: bool = False
    confidence: float = 0.0


def extract_html_content(html):
    """Извлекает контент из HTML."""
    result = ParsedContent()
    if BeautifulSoup is None:
        result.content = html[:1000]
        return result
    soup = BeautifulSoup(html, 'html.parser')
    h1 = soup.find('h1')
    title_tag = soup.find('title')
    if h1:
        result.title = h1.get_text().strip()
    elif title_tag:
        result.title = title_tag.get_text().strip()
    else:
        result.title = "Unknown"
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'button', 'meta', 'link']):
        tag.decompose()
    text_parts = []
    code_blocks = []
    for tag in soup.find_all(['p', 'h2', 'h3', 'h4', 'li', 'pre', 'blockquote', 'td', 'th', 'div']):
        text = tag.get_text().strip()
        if text and len(text) > 10:
            text_parts.append(text)
        if tag.name == 'pre' or 'code' in tag.get('class', []):
            code_text = tag.get_text().strip()
            if code_text and len(code_text) > 20:
                code_blocks.append(code_text)
    result.content = chr(10)+chr(10).join(text_parts)
    result.has_code = len(code_blocks) > 0
    result.tags = detect_tags(result.content)
    result.category = detect_category(result.content)
    result.is_useful, result.confidence = assess_usefulness(result.content, result.tags)
    return result


def extract_markdown_content(md_text):
    """Извлекает контент из Markdown."""
    result = ParsedContent()
    result.content = md_text
    h1_match = re.search(r'^# (.+)$', md_text, re.MULTILINE)
    if h1_match:
        result.title = h1_match.group(1).strip()
    else:
        result.title = "Markdown Document"
    code_blocks = re.findall(r'```[\s\S]*?```', md_text)
    result.has_code = len(code_blocks) > 0
    result.tags = detect_tags(md_text)
    result.category = detect_category(md_text)
    result.is_useful, result.confidence = assess_usefulness(md_text, result.tags)
    return result


def extract_docx_content(file_path):
    """Извлекает контент из DOCX."""
    result = ParsedContent()
    if docx is None:
        result.content = "docx module not available"
        return result
    try:
        doc = docx.Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        result.content = chr(10)+chr(10).join(paragraphs)
        result.title = paragraphs[0][:100] if paragraphs else "DOCX Document"
        result.has_code = False
        result.tags = detect_tags(result.content)
        result.category = detect_category(result.content)
        result.is_useful, result.confidence = assess_usefulness(result.content, result.tags)
    except Exception as e:
        return result


def extract_pdf_content(file_path):
    """Извлекает контент из PDF."""
    result = ParsedContent()
    if PyPDF2 is None:
        result.content = "PyPDF2 module not available"
        return result
    try:
        text_parts = []
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        result.content = chr(10)+chr(10).join(text_parts)
        result.title = text_parts[0][:100] if text_parts else "PDF Document"
        result.has_code = False
        result.tags = detect_tags(result.content)
        result.category = detect_category(result.content)
        result.is_useful, result.confidence = assess_usefulness(result.content, result.tags)
    except Exception as e:
        result.content = f"Error reading PDF: {e}"
    return result


def load_from_url(url):
    """Загружает контент по URL и определяет формат."""
    if requests is None:
        raise ImportError("requests library is required for URL loading")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    content_type = response.headers.get('Content-Type', '')
    if 'html' in content_type.lower():
        return extract_html_content(response.text)
    elif 'markdown' in content_type.lower() or 'text/plain' in content_type.lower():
        return extract_markdown_content(response.text)
    else:
        if '<html' in response.text[:500]:
            return extract_html_content(response.text)
        elif response.text.strip().startswith('#'):
            return extract_markdown_content(response.text)
        else:
            raise ValueError(f"Unknown content type for URL: {url}")


def load_from_file(file_path):
    """Загружает контент из файла по расширению."""
    path = Path(file_path)
    ext = path.suffix.lower()
    if ext in ('.html', '.htm'):
        with open(path, 'r', encoding='utf-8') as f:
            return extract_html_content(f.read())
    elif ext == '.md':
        with open(path, 'r', encoding='utf-8') as f:
            return extract_markdown_content(f.read())
    elif ext in ('.docx',):
        return extract_docx_content(str(path))
    elif ext == '.txt':
        with open(path, 'r', encoding='utf-8') as f:
            return extract_markdown_content(f.read())
    elif ext in ('.pdf',):
        return extract_pdf_content(str(path))
    else:
        raise ValueError(f"Unsupported file format: {ext}")

