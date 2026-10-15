"""its_pdf_loader — загрузка PDF-документации 1С в ЖИВУЮ схему local_doc.

Живая схема local_doc: groups / knowledge_snippets / alias_targets / doc_categories / doc_tags.
Таблиц docs, doc_fragments, search_aliases в схеме нет, поэтому старый путь
(src/pdf_parser.py -> src/pdf_loader.py) к живой схеме неприменим: он пишет в несуществующие
таблицы. Здесь реализован сценарий B правил LOAD_RULES.md: один раздел документации =
один knowledge_snippets (groups_id = NULL) + алиасы прямо к snippets_id.

Источник — PDF глав «1С:Предприятие 8.3.27. Документация» (Руководство разработчика ИТС).
Текст берётся pypdf (кириллица и блоки кода сохраняются), границы разделов — по номерам вида
«10.3.4.» из текста страниц; оглавление в начале файла отбрасывается (строки с номером
страницы на конце).

Правила:
  * повторный прогон того же файла не создаёт дублей: срез по source_url (путь + страницы);
  * разделы короче MIN_SECTION_CHARS символов не сохраняются (оглавления, заглушки);
  * answer не длиннее MAX_ANSWER символов, усечение помечено явно;
  * tags содержат категорию (по умолчанию 'its') - иначе фильтр search_docs_tool(category=...)
    этих сниппетов не видит.
"""

import os
import re
import sys

if sys.platform == 'win32':
    import io
    if getattr(sys.stdout, 'encoding', 'utf-8') != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from external_db import connect  # noqa: E402

MAX_ANSWER = 6000          # предел текста сниппета, символов
MIN_SECTION_CHARS = 400    # разделы короче не сохраняются
MAX_TITLE_LEN = 160

# «10.3.4. Язык выражений системы компоновки данных» / «10.3 Система компоновки данных»
SECTION_RE = re.compile(r'^\s*(\d{1,2}(?:\.\d{1,2}){1,4})\.?\s+(\S[^\d]{2,140}?)\s*$')
# строки оглавления: заголовок + номер страницы на конце
TOC_RE = re.compile(r'\s\d{1,4}\s*$')
PAGE_NO_RE = re.compile(r'^\s*\d{1,4}\s*$')
NOISE_PATTERNS = [
    re.compile(r'^\s*Копировать в буфер обмена\s*$'),
    re.compile(r'^\s*Оглавление\s*$'),
    re.compile(r'^\s*ОГЛАВЛЕНИЕ\s*$'),
    re.compile(r'^\s*https?://\S+\s*$'),
]
BOOK_FROM_NAME_RE = re.compile(r'^(Глава\s+\d+\.[^_]*)')


def book_title_from_path(pdf_path):
    """Короткое имя книги из имени файла: «Глава 10. Система компоновки данных»."""
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    m = BOOK_FROM_NAME_RE.match(stem)
    if m:
        return m.group(1).strip()
    return stem.replace('__', ' ').strip()[:MAX_TITLE_LEN]


def _clean_line(line):
    line = line.rstrip()
    if not line or PAGE_NO_RE.match(line):
        return None
    for pat in NOISE_PATTERNS:
        if pat.match(line):
            return None
    return line.strip()


def extract_pages(pdf_path):
    if PdfReader is None:
        raise RuntimeError('pypdf не установлен: pip install pypdf')
    reader = PdfReader(pdf_path)
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or '')
        except Exception:
            pages.append('')
    return pages


def split_sections(pages, book):
    """Разбивает текст страниц на разделы по номерам «N.N…».

    Список словарей: num, title, text, page_from, page_to, book.
    Первое вхождение номера считается началом раздела (повторы в тексте игнорируются),
    строки оглавления отбрасываются.
    """
    sections = []
    current = None
    for page_no, text in enumerate(pages, start=1):
        for raw in text.split('\n'):
            line = _clean_line(raw)
            if line is None:
                continue
            if TOC_RE.search(line) and len(line) > 12:
                continue  # строка оглавления
            m = SECTION_RE.match(line)
            if m and len(line) <= MAX_TITLE_LEN and not line.endswith('.'):
                num, title = m.group(1), m.group(2).strip()
                if current is not None and current['num'] == num:
                    continue
                if current is not None:
                    current['page_to'] = page_no
                    sections.append(current)
                current = {'num': num, 'title': title[:MAX_TITLE_LEN], 'lines': [],
                           'page_from': page_no, 'page_to': page_no}
                continue
            if current is not None:
                current['lines'].append(line)
    if current is not None:
        sections.append(current)

    result = []
    for sec in sections:
        body = '\n'.join(sec['lines']).strip()
        if len(body) < MIN_SECTION_CHARS:
            continue
        result.append({'num': sec['num'], 'title': sec['title'], 'text': body,
                       'page_from': sec['page_from'], 'page_to': sec['page_to'], 'book': book})
    return result


def _aliases_for_section(num, title):
    """Алиасы раздела: точный номер, полный заголовок, значимые слова, биграммы."""
    aliases = []
    seen = set()

    def add(value, weight):
        value = (value or '').strip()
        key = value.lower()
        if len(key) < 3 or key in seen:
            return
        seen.add(key)
        aliases.append((value, weight))

    add(num, 1.2)
    add(title, 1.0)
    words = [w for w in re.split(r'[^0-9A-Za-zА-Яа-яЁё]+', title) if len(w) > 3]
    for w in words:
        add(w, 0.9)
    for i in range(len(words) - 1):
        add(words[i] + ' ' + words[i + 1], 1.1)
    return aliases


def load_pdf(pdf_path, category='its', limit=None, dry_run=False, conn=None):
    """Загружает один PDF в knowledge_snippets + alias_targets. Возвращает статистику."""
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError('PDF не найден: %s' % pdf_path)
    book = book_title_from_path(pdf_path)
    pages = extract_pages(pdf_path)
    sections = split_sections(pages, book)

    stats = {'pdf': os.path.basename(pdf_path), 'pages': len(pages),
             'sections_found': len(sections), 'snippets_added': 0,
             'snippets_skipped': 0, 'aliases_added': 0}

    if dry_run:
        for sec in sections[:(limit or 20)]:
            print('[dry-run] %s | стр. %s-%s | %s симв. | %s'
                  % (sec['num'], sec['page_from'], sec['page_to'], len(sec['text']), sec['title'][:70]))
        return stats

    own_conn = conn is None
    if own_conn:
        conn = connect('local_doc')
    cur = conn.cursor()
    try:
        for idx, sec in enumerate(sections, start=1):
            if limit and stats['snippets_added'] >= limit:
                break
            source_url = '%s#p%d-%d' % (pdf_path, sec['page_from'], sec['page_to'])
            cur.execute("SELECT id FROM knowledge_snippets WHERE source_url = %s", (source_url,))
            if cur.fetchone():
                stats['snippets_skipped'] += 1
                continue
            answer = sec['text']
            if len(answer) > MAX_ANSWER:
                total = len(answer)
                answer = answer[:MAX_ANSWER] + (
                    '\n…[усечено: в разделе %d симв., полный текст — PDF по диапазону страниц из source_url]' % total)
            question = '%s %s — %s' % (sec['num'], sec['title'], book)
            tags = [category, 'pdf', 'its-book']
            cur.execute(
                "INSERT INTO knowledge_snippets (groups_id, question, answer, source_url, tags, confidence, is_verified)"
                " VALUES (NULL, %s, %s, %s, %s, %s, FALSE) RETURNING id",
                (question, answer, source_url, tags, 0.8),
            )
            snippet_id = cur.fetchone()[0]
            stats['snippets_added'] += 1
            for alias, weight in _aliases_for_section(sec['num'], sec['title']):
                cur.execute(
                    "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags, weight)"
                    " VALUES (%s, 'snippet', NULL, %s, %s, %s) ON CONFLICT DO NOTHING",
                    (alias, snippet_id, tags, weight),
                )
                stats['aliases_added'] += cur.rowcount
            if idx % 25 == 0:
                conn.commit()
                print('  … %d разделов обработано' % idx)
        conn.commit()
    finally:
        cur.close()
        if own_conn:
            conn.close()
    return stats


def load_directory(pdf_dir, category='its', limit_per_file=None, only=None, dry_run=False):
    """Загружает PDF из каталога. only - подстрока имени файла (фильтр выборки)."""
    files = sorted(f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf'))
    if only:
        files = [f for f in files if only.lower() in f.lower()]
    results = []
    conn = connect('local_doc')
    try:
        for name in files:
            stats = load_pdf(os.path.join(pdf_dir, name), category=category,
                             limit=limit_per_file, dry_run=dry_run, conn=conn)
            results.append(stats)
            print('%s: страниц %d, разделов %d, сниппетов %d, пропущено %d, алиасов %d'
                  % (stats['pdf'], stats['pages'], stats['sections_found'], stats['snippets_added'],
                     stats['snippets_skipped'], stats['aliases_added']))
    finally:
        conn.close()
    return results


