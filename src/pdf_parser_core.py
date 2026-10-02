"""
PDF Parser Core — базовые классы и логика парсинга PDF документов 1С.
Использует pypdf для быстрого извлечения текста + pdfplumber для таблиц.
"""

import os
import sys
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict

# Fix Windows console encoding for Unicode characters (only once)
if sys.platform == 'win32' and not hasattr(sys.stdout, 'encoding') or sys.stdout.encoding != 'utf-8':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass  # Fallback to default stdout
try:
    import pdfplumber
except ImportError:
    print("Ошибка: pip install pdfplumber")
    sys.exit(1)

try:
    import pypdf
except ImportError:
    pypdf = None  # Fallback to pdfplumber only


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
class Chapter:
    title: str
    level: int = 1
    content: str = ""
    methods: List[MethodSignature] = field(default_factory=list)
    code_blocks: List[CodeBlock] = field(default_factory=list)


@dataclass
class ParsedDocument:
    title: str
    chapters: List[Chapter] = field(default_factory=list)
    total_pages: int = 0


class PDFParser:
    CODE_KEYWORDS = {"Процедура", "Функция", "КонецПроцедуры", "Если", "Тогда", "Для", "Цикл", "Новый", "Запрос"}
    TAG_PATTERNS = {"code": [r"код|пример|блок|процедура"], "howto": [r"как\s+создать|настройка"], "api": [r"метод|свойство|объект"], "syntax": [r"синтаксис|описание|параметр"], "error": [r"ошибка|исключение"]}
    ALIASES = {"регистр накопления": ["накопительный регистр"], "проводка": ["движение документа"], "справочник": ["справочник-ссылок"]}

    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists(): raise FileNotFoundError(f"PDF файл не найден: {pdf_path}")
        self.parsed = None

    def _detect_heading_level(self, line):
        if re.match(r"^Заняти[ея]\s+\d+", line): return 2
        if re.match(r"^Глава\s+\d+", line): return 1
        match = re.match(r"^\d+\.\d{1,2}\.", line)
        if match: return min(len(re.findall(r"\.", line[:10])) + 1, 4)
        if len(line) < 80 and not line.endswith(".") and not line.endswith(","): return 3
        return None

    def _clean_title(self, title): return re.sub(r"[\s\.\-\u2013\u2014]+", " ", re.sub(r"\(\d+:\d+\)", "", title)).strip()

    def _extract_code_blocks(self, page):
        """Извлекает блоки кода из текста страницы (не из таблиц)."""
        blocks = []
        if hasattr(page, 'extract_text'):
            text = page.extract_text() or ""
            # Ищем блоки кода по ключевым словам
            lines = text.split('\n')
            in_code = False
            code_lines = []
            for line in lines:
                stripped = line.strip()
                if any(kw in stripped for kw in self.CODE_KEYWORDS):
                    in_code = True
                    code_lines.append(stripped)
                elif in_code and (stripped.startswith('Процедура') or stripped.startswith('Функция') or stripped == 'КонецПроцедуры' or stripped == 'КонецФункции'):
                    if len(code_lines) > 2:
                        blocks.append(CodeBlock(code='\n'.join(code_lines)[:3000], description="Извлечено из текста PDF"))
                    in_code = False
                    code_lines = []
                elif in_code and stripped:
                    code_lines.append(stripped)
        return blocks
        for table in tables:
            if not table or len(table) < 2: continue
            full_text = chr(10).join(" ".join(str(c) for c in row if c) for row in table if row and len(" ".join(str(c) for c in row if c)) > 10)
            if any(kw in full_text for kw in self.CODE_KEYWORDS) and len(full_text) > 50: blocks.append(CodeBlock(code=full_text[:2000], description="Извлечено из таблицы PDF"))
        return blocks

    def _extract_methods(self, text):
        methods, seen = [], set()
        for match in re.finditer(r"(Процедура|Функция)\s+(\w+)(\([^)]*\))?", text):
            name = match.group(2)
            if name not in seen and len(name) > 2:
                seen.add(name); methods.append(MethodSignature(name=name, signature=match.group(3) or "", description=f'{match.group(1)} {name}{match.group(3)}', category='language'))
        return methods

    def get_tags_for_text(self, text):
        tags, tl = [], text.lower()
        for tag, patterns in self.TAG_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, tl, re.IGNORECASE) and tag not in tags: tags.append(tag); break
        return tags

    def get_aliases_for_method(self, method_name):
        aliases = {method_name: 2.0}
        for term, alias_list in self.ALIASES.items():
            if term in method_name.lower() or method_name.lower() in term:
                for alias in alias_list: aliases[alias] = 1.5
        return aliases

    def parse(self):
        """Парсит PDF с использованием pypdf для текста + pdfplumber для таблиц."""
        print(f"\n{'='*60}"); print(f"Парсинг PDF: {self.pdf_path.name}"); print(f"{'='*60}")
        file_size = self.pdf_path.stat().st_file_size / (1024 * 1024) if hasattr(self.pdf_path.stat(), 'st_file_size') else self.pdf_path.stat().st_size / (1024 * 1024)
        print(f"Размер файла: {file_size:.2f} МБ"); is_large = file_size > 5.0
        chapters, all_content, all_methods, all_code_blocks, first_title, page_num = [], [], [], [], None, 0
        
        use_pypdf = pypdf is not None and is_large
        
        if use_pypdf:
            # Быстрый текст через pypdf + таблицы через pdfplumber по чанкам
            chunk_size = 80  # Увеличил для уменьшения количества open/close
            total_pages = 0
            with pypdf.PdfReader(str(self.pdf_path)) as temp_reader:
                total_pages = len(temp_reader.pages)
            print(f"Всего страниц: {total_pages}\n")
            print(f"📦 Большой файл! Чанкинг по {chunk_size} страниц...\n")
            
            for chunk_start in range(0, total_pages, chunk_size):
                chunk_end = min(chunk_start + chunk_size, total_pages)
                print(f"  📄 Чанк [{chunk_start+1}-{chunk_end}] из {total_pages}...")
                
                # Текст через pypdf
                with pypdf.PdfReader(str(self.pdf_path)) as pdf:
                    for i in range(chunk_start, chunk_end):
                        page_num = i + 1
                        page = pdf.pages[i]
                        text = page.extract_text()
                        if not text: continue
                        lines = text.split(chr(10)); meaningful_lines = [l.strip() for l in lines if l.strip() and len(l.strip()) > 5]
                        if meaningful_lines: all_content.append(chr(10).join(meaningful_lines))
                        heading_level, line_stripped = None, None
                        for line in lines:
                            line_stripped = line.strip()
                            if not line_stripped or len(line_stripped) > 200: continue
                            heading_level = self._detect_heading_level(line_stripped)
                            if heading_level: break
                        if heading_level and heading_level <= 3:
                            title = self._clean_title(line_stripped)
                            if not first_title: first_title = title
                            chapters.append(Chapter(title=f"Раздел {len(chapters)+1}: {title}", level=heading_level, content=''))
                            print(f"[{page_num}] Раздел {len(chapters)}: {title[:80]}")
                        for m in self._extract_methods(text): all_methods.append(m)
                        
                        # Извлекаем блоки кода из текста (text-based) — ВНУТРИ контекстного менеджера!
                        blocks = self._extract_code_blocks(pdf.pages[i])
                        for cb in blocks: all_code_blocks.append(cb)
                
                import gc; gc.collect()
        else:
            # Для маленьких файлов — стандартный подход
            with pdfplumber.open(str(self.pdf_path)) as pdf:
                total_pages = len(pdf.pages); print(f"Всего страниц: {total_pages}\n")
                for i, page in enumerate(pdf.pages):
                    page_num = i + 1
                    text = page.extract_text()
                    if not text: continue
                    lines = text.split(chr(10)); meaningful_lines = [l.strip() for l in lines if l.strip() and len(l.strip()) > 5]
                    if meaningful_lines: all_content.append(chr(10).join(meaningful_lines))
                    heading_level, line_stripped = None, None
                    for line in lines:
                        line_stripped = line.strip()
                        if not line_stripped or len(line_stripped) > 200: continue
                        heading_level = self._detect_heading_level(line_stripped)
                        if heading_level: break
                    if heading_level and heading_level <= 3:
                        title = self._clean_title(line_stripped)
                        if not first_title: first_title = title
                        chapters.append(Chapter(title=f"Раздел {len(chapters)+1}: {title}", level=heading_level, content=''))
                        print(f"[{page_num}] Раздел {len(chapters)}: {title[:80]}")
                    blocks = self._extract_code_blocks(page)
                    for cb in blocks: all_code_blocks.append(cb)
                    for m in self._extract_methods(text): all_methods.append(m)
        
        if first_title and chapters:
            main_chapter = Chapter(title=first_title, level=1, content='')
            main_chapter.content = chr(10).join(all_content)[:50000]; main_chapter.methods = all_methods; main_chapter.code_blocks = all_code_blocks
            chapters.insert(0, main_chapter)
        self.parsed = ParsedDocument(title=first_title or self._extract_title_from_pdf(), chapters=chapters, total_pages=page_num)
        total_content = sum(len(c.content) for c in chapters); filled = sum(1 for c in chapters if len(c.content) > 0)
        print(f"\n{'='*60}"); print("Результат парсинга:"); print(f"  Главы/разделы: {len(chapters)}"); print(f"  Методы найдены: {sum(len(c.methods) for c in chapters)}")
        print(f"  Блоки кода: {sum(len(c.code_blocks) for c in chapters)}"); print(f"  Контент (символов): {total_content}"); print(f"  Главы с контентом: {filled}/{len(chapters)}"); print(f"{'='*60}\n")
        return self.parsed

    def _extract_title_from_pdf(self):
        try:
            with pdfplumber.open(str(self.pdf_path)) as pdf:
                for line in (pdf.pages[0].extract_text() or "").split(chr(10))[:20]:
                    line = line.strip()
                    if 10 < len(line) < 100 and any(kw in line.lower() for kw in ["пособие", "руководство"]): return self._clean_title(line)
        except Exception: pass
        return self._clean_title(self.pdf_path.stem.replace("_", " "))

parsed_parser = None
