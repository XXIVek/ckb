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
    этих сниппетов не видит;
  * РЕЖИМ "ФАЙЛ ЦЕЛИКОМ" (whole_file, включён по умолчанию): если ни один нумерованный раздел
    не найден (Введение, приложения - заголовки без номеров вида «N.N»), файл целиком становится
    разделом: заголовок берётся из первой строки текста, а перенос заголовка продолжается, если
    следующая строка короче MAX_TITLE_LINE И (начинается со строчной буквы ИЛИ предыдущая строка
    обрвана служебным словом из TRAILING_FUNCTION_WORD_RE). Текст упаковывается постранично в
    блоки не длиннее MAX_ANSWER (строка пометки об усечении входит в лимит). source_url получает
    маркер #whole, tags - 'whole-file', чтобы режим был отличим от разбора по разделам.
    Отключение - whole_file=False (CLI --no-whole-file). Проверка - validate_pdf_whole_file.py.
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
# «Приложение 11» / «Введение» - заголовок без нумерации разделов; точного номера раздела
# в нём нет, поэтому алиасом служит весь префикс целиком.
APPENDIX_RE = re.compile(r'^(Приложение\s+\d+|Введение)')
# перенос заголовка: следующая строка короче MAX_TITLE_LINE и начинается со строчной буквы
MAX_TITLE_LINE = 90
MAX_TITLE_LINES = 3
WHOLE_FILE_DEFAULT = True
# предыдущая строка обрвана, если кончается служебным словом - значит заголовок продолжается
# («Префиксы пространств имен при» + «JSON-сериализации»). Признаком служит последнее слово
# предыдущей строки, а не регистр следующей: «Введение» + «Структура Руководства» - это два
# разных заголовка, и по регистру их не отличить, когда продолжение начинается с аббревиатуры.
TRAILING_FUNCTION_WORD_RE = re.compile(
    r'(?:^|\s)(при|и|о|об|во|в|на|с|со|к|для|из|по|от|до|над|под|между|без|про|как|типа|'
    r'или|а|но|не|«|„|“)$', re.IGNORECASE)


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


def _first_title(pages):
    """Заголовок файла из первой строки текста.

    Перенос заголовка присоединяется: следующая строка короче MAX_TITLE_LINE и начинается
    со строчной буквы («…Правила автоматического» + «формирования имен элементов формы»).
    Строка, начинающаяся с заглавной («Введение» + «Структура Руководства»), - уже другой
    заголовок, поэтому продолжение не берётся.
    """
    lines = []
    for text in pages:
        for raw in text.split('\n'):
            line = _clean_line(raw)
            if line:
                lines.append(line)
    if not lines or len(lines[0]) > MAX_TITLE_LINE:
        return ''
    title = lines[0]
    for nxt in lines[1:MAX_TITLE_LINES]:
        if len(nxt) > MAX_TITLE_LINE:
            break
        # продолжение: следующая строка со строчной буквы ИЛИ предыдущая обрвана служебным словом
        if not (nxt[:1].islower() or TRAILING_FUNCTION_WORD_RE.search(title)):
            break
        title += ' ' + nxt
    return title[:MAX_TITLE_LEN].strip()


def whole_file_sections(pages, book):
    """Файл целиком как раздел: текст упаковывается постранично в блоки <= MAX_ANSWER.

    Режим включается только когда split_sections не нашёл ни одного нумерованного раздела
    (Введение, приложения - заголовки без номеров «N.N»). Возвращает те же словари, что
    split_sections, плюс whole/part/parts; num пустой, потому что номера раздела нет.
    """
    title = _first_title(pages) or book
    blocks = []
    cur_lines, cur_size, page_from, page_to = [], 0, None, None
    for page_no, text in enumerate(pages, start=1):
        for raw in text.split('\n'):
            line = _clean_line(raw)
            if line is None:
                continue
            if TOC_RE.search(line) and len(line) > 12:
                continue  # строка оглавления
            if cur_lines and cur_size + len(line) + 1 > MAX_ANSWER:
                blocks.append((cur_lines, page_from, page_to))
                cur_lines, cur_size, page_from = [], 0, page_no
            if page_from is None:
                page_from = page_no
            page_to = page_no
            cur_lines.append(line)
            cur_size += len(line) + 1
    if cur_lines:
        blocks.append((cur_lines, page_from, page_to))

    accepted = []
    for lines, page_from, page_to in blocks:
        body = '\n'.join(lines).strip()
        if len(body) >= MIN_SECTION_CHARS:
            accepted.append({'num': '', 'title': title, 'text': body,
                             'page_from': page_from, 'page_to': page_to,
                             'book': book, 'whole': True})
    for idx, sec in enumerate(accepted, start=1):
        sec['part'] = idx
        sec['parts'] = len(accepted)
    return accepted


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
    m = APPENDIX_RE.match(title or '')
    if m:
        add(m.group(1), 1.2)  # «Приложение 11», «Введение» - точный адрес такого раздела
    words = [w for w in re.split(r'[^0-9A-Za-zА-Яа-яЁё]+', title) if len(w) > 3]
    for w in words:
        add(w, 0.9)
    for i in range(len(words) - 1):
        add(words[i] + ' ' + words[i + 1], 1.1)
    return aliases


def load_pdf(pdf_path, category='its', limit=None, dry_run=False, conn=None,
             whole_file=WHOLE_FILE_DEFAULT):
    """Загружает один PDF в knowledge_snippets + alias_targets. Возвращает статистику.

    whole_file=True включает режим «файл целиком» для файлов без нумерованных разделов
    (Введение, приложения): иначе такие файлы не дают в базе ни одной записи.
    """
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError('PDF не найден: %s' % pdf_path)
    book = book_title_from_path(pdf_path)
    pages = extract_pages(pdf_path)
    sections = split_sections(pages, book)
    whole_blocks = 0
    if not sections and whole_file:
        sections = whole_file_sections(pages, book)
        whole_blocks = len(sections)

    stats = {'pdf': os.path.basename(pdf_path), 'pages': len(pages),
             'sections_found': len(sections), 'whole_file_blocks': whole_blocks,
             'snippets_added': 0, 'snippets_skipped': 0, 'aliases_added': 0}

    if dry_run:
        for sec in sections[:(limit or 20)]:
            print('[dry-run] %s | стр. %s-%s | %s симв. | %s'
                  % (sec['num'] or 'файл целиком', sec['page_from'], sec['page_to'],
                     len(sec['text']), sec['title'][:70]))
        return stats

    own_conn = conn is None
    if own_conn:
        conn = connect('local_doc')
    cur = conn.cursor()
    try:
        for idx, sec in enumerate(sections, start=1):
            if limit and stats['snippets_added'] >= limit:
                break
            whole = bool(sec.get('whole'))
            source_url = '%s#p%d-%d' % (pdf_path, sec['page_from'], sec['page_to'])
            if whole:
                source_url = '%s#whole#p%d-%d' % (pdf_path, sec['page_from'], sec['page_to'])
            cur.execute("SELECT id FROM knowledge_snippets WHERE source_url = %s", (source_url,))
            if cur.fetchone():
                stats['snippets_skipped'] += 1
                continue
            answer = sec['text']
            parts = sec.get('parts', 1)
            if whole and parts > 1:
                answer = ('[Продолжение текста «%s»: часть %d из %d, страницы %d-%d; начало — часть 1.]\n'
                          % (sec['title'], sec['part'], parts, sec['page_from'], sec['page_to'])) + answer
            if len(answer) > MAX_ANSWER:
                total = len(answer)
                marker = ('\n…[усечено: в разделе %d симв., полный текст — PDF по диапазону страниц из source_url]'
                          % total)
                # строка пометки учитывается в лимите: answer не длиннее MAX_ANSWER целиком
                answer = answer[:max(0, MAX_ANSWER - len(marker))] + marker
            if whole:
                suffix = '' if parts == 1 else ' (часть %d из %d)' % (sec['part'], parts)
                question = '%s%s — %s' % (sec['title'], suffix, book)
            else:
                question = '%s %s — %s' % (sec['num'], sec['title'], book)
            tags = [category, 'pdf', 'its-book']
            if whole:
                tags.append('whole-file')
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


def load_directory(pdf_dir, category='its', limit_per_file=None, only=None, dry_run=False,
                   whole_file=WHOLE_FILE_DEFAULT):
    """Загружает PDF из каталога. only - подстрока имени файла (фильтр выборки)."""
    files = sorted(f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf'))
    if only:
        files = [f for f in files if only.lower() in f.lower()]
    results = []
    conn = connect('local_doc')
    try:
        for name in files:
            stats = load_pdf(os.path.join(pdf_dir, name), category=category,
                             limit=limit_per_file, dry_run=dry_run, conn=conn,
                             whole_file=whole_file)
            results.append(stats)
            whole_note = ''
            if stats.get('whole_file_blocks'):
                whole_note = ' [файл без нумерованных разделов -> %d блок(а)]' % stats['whole_file_blocks']
            print('%s: страниц %d, разделов %d, сниппетов %d, пропущено %d, алиасов %d%s'
                  % (stats['pdf'], stats['pages'], stats['sections_found'], stats['snippets_added'],
                     stats['snippets_skipped'], stats['aliases_added'], whole_note))
    finally:
        conn.close()
    return results


