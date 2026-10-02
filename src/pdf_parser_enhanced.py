#!/usr/bin/env python3
"""
Улучшенный PDF парсер для документации 1С.
Извлекает: структуру, заголовки, методы, блоки кода.
"""
import sys
sys.path.insert(0, r'C:\1C_LLM\ckb')

try:
    import PyPDF2
except ImportError:
    print("Установите PyPDF2: pip install PyPDF2")
    sys.exit(1)

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from pathlib import Path

@dataclass
class Chapter:
    title: str
    level: int
    start_page: int = 0
    content: str = ""
    sub_chapters: List['Chapter'] = field(default_factory=list)


@dataclass
class CodeBlock:
    code: str
    language: str = "1c"
    description: str = ""
    parent_title: str = ""


@dataclass
class MethodSignature:
    name: str
    signature: str = ""
    description: str = ""
    category: str = "language"


@dataclass
class ParsedDocument:
    title: str = ""
    chapters: List[Chapter] = field(default_factory=list)
    methods: List[MethodSignature] = field(default_factory=list)
    code_blocks: List[CodeBlock] = field(default_factory=list)
    total_pages: int = 0
    raw_content: str = ""

HEADER_PATTERNS = [
    (r"^(Глава\s+\d+[\.\s][^\n\r]+)", 1),
    (r"^(Раздел\s+\d+[\.\s][^\n\r]+)", 1),
    (r"^(Введение|Заключение|Приложение)[\s\.]*$", 1),
    (r"^(\d+\.\d+[\.\d]*\s+[^\n\r]+)", 2),
    (r"^(\d+\.\d+[\.\d]*)\.$", 2),
]

METHOD_PATTERNS = [
    r"(Процедура|Функция)\s+(\w+)(\([^)]*\))?",
    r"(\w+)\s*[:\(]\s*(метод|функция|процедура)",
    r"\b(Справочник|Документ|ПланВидовХарактеристик|ПланСчетов|БизнесПроцесс|Задача|Перечисление|Константа|РегистрНакопления|РегистрБухгалтерии)\b",
]

def detect_header_level(line):
    line = line.strip()
    if not line or len(line) > 150:
        return None, None
    for pattern, level in HEADER_PATTERNS:
        match = re.match(pattern, line, re.IGNORECASE | re.UNICODE)
        if match:
            header_text = match.group(1).strip()
            header_text = re.sub(r"[\s\.]+$", "", header_text)
            return level, header_text
    return None, None

def detect_code_blocks(text, context_lines=5):
    blocks = []
    lines = text.split(chr(10))
    in_code_block = False
    code_start = 0
    description = ""
    for i, line in enumerate(lines):
        stripped = line.strip()
        if any(kw in stripped.lower() for kw in ["пример", "код", "синтаксис", "программа"]):
            description = stripped[:100]
        if line.startswith("    ") or line.startswith(chr(9)):
            if not in_code_block:
                in_code_block = True
                code_start = i
            continue
        else:
            if in_code_block and (i - code_start) >= 3:
                code_text = chr(10).join(lines[code_start:i])
                if len(code_text.strip()) > 20:
                    blocks.append(CodeBlock(code=code_text.strip(), description=description))
                in_code_block = False
    return blocks

def extract_methods_from_text(text):
    methods = []
    for pattern in METHOD_PATTERNS:
        matches = re.finditer(pattern, text, re.UNICODE)
        for match in matches:
            if pattern.startswith(r"\\b"):
                type_name = match.group(1)
                context_start = max(0, match.start() - 100)
                context_end = min(len(text), match.end() + 100)
                context = text[context_start:context_end].lower()
                if any(kw in context for kw in ["объект", "тип", "конфигурация", "регистр"]):
                    methods.append(MethodSignature(name=type_name, description=f"Объект конфигурации: {type_name}"))
    seen = set()
    unique_methods = []
    for m in methods:
        if m.name not in seen:
            seen.add(m.name)
            unique_methods.append(m)
    return unique_methods[:50]

def parse_pdf_structure(file_path):
    doc = ParsedDocument()
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        doc.total_pages = len(reader.pages)
        all_text_parts = []
        current_chapter = None
        chapters_by_level = {1: [], 2: [], 3: []}
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if not text:
                continue
            all_text_parts.append(text)
            lines = text.split(chr(10))
            for line in lines:
                level, header_text = detect_header_level(line)
                if level and header_text:
                    chapter = Chapter(title=header_text, level=level, start_page=page_num + 1)
                    doc.chapters.append(chapter)
                    chapters_by_level[level].append(chapter)
                    current_chapter = chapter
                    if level >= 2 and chapters_by_level[level - 1]:
                        parent = chapters_by_level[level - 1][-1]
                        parent.sub_chapters.append(chapter)
                    continue
                if current_chapter and line.strip():
                    if not current_chapter.content:
                        current_chapter.content = line.strip()
                    else:
                        current_chapter.content += chr(10) + line.strip()
        doc.raw_content = chr(10).join(all_text_parts)
        doc.methods = extract_methods_from_text(doc.raw_content)
        doc.code_blocks = detect_code_blocks(doc.raw_content)
        if doc.chapters and doc.chapters[0].level == 1:
            doc.title = doc.chapters[0].title
        elif all_text_parts:
            first_page_text = all_text_parts[0]
            for line in first_page_text.split(chr(10)):
                level, header_text = detect_header_level(line)
                if level and header_text:
                    doc.title = header_text
                    break
            else:
                doc.title = first_page_text[:200].strip()
    return doc

def main():
    pdf_dir = Path(r"C:\1C_LLM\ckb\docs\pdf")
    files = [f for f in pdf_dir.iterdir() if f.suffix.lower() == ".pdf"]
    target_file = None
    for f in files:
        if "Глава 1" in f.name and "Введение" not in f.name:
            target_file = f
            break
    if not target_file:
        print("Файл не найден")
        return
    print(f"Парсинг: {target_file.name}")
    doc = parse_pdf_structure(str(target_file))
    print(f"Заголовок: {doc.title[:100]}")
    print(f"Страниц: {doc.total_pages}")
    print(f"Разделов: {len(doc.chapters)}")
    for ch in doc.chapters[:15]:
        indent = "  " * (ch.level - 1)
        print(f"{indent}- [{ch.level}] {ch.title[:60]}")
    if doc.methods:
        print(f"Методов: {len(doc.methods)}")
        for m in doc.methods[:10]:
            print(f"  - {m.name}: {m.description[:50]}")
    if doc.code_blocks:
        print(f"Блоков кода: {len(doc.code_blocks)}")

if __name__ == "__main__":
    main()
