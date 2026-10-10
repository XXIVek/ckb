#!/usr/bin/env python3
"""File loaders for 1C Knowledge Base."""
import os
import re
import psycopg2.extras as pg_extras
from mcp_tools_core import _get_pool, extract_aliases
from mcp_tools_api import add_snippet as _add_snippet


def parse_html_file(filepath):
    """Parse BSL HTML file.
    
    Returns dict with: pagetitle, title, heading (V8SH_heading), description, versionInfo
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return None

    result = {'pagetitle': '', 'title': '', 'heading': '', 'description': '', 'versionInfo': ''}

    # pagetitle (V8SH_pagetitle)
    m = re.search(r'<h1[^>]*class="[^"]*V8SH_pagetitle[^"]*"[^>]*>(.*?)</h1>', content, re.DOTALL)
    if m:
        result['pagetitle'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()

    # title (V8SH_title)
    m = re.search(r'<p[^>]*class="[^"]*V8SH_title[^"]*"[^>]*>(.*?)</p>', content, re.DOTALL)
    if m:
        result['title'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()

    # heading (V8SH_heading) — только первый
    m = re.search(r'<p[^>]*class="[^"]*V8SH_heading[^"]*"[^>]*>(.*?)</', content, re.DOTALL)
    if m:
        result['heading'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()

    # versionInfo
    m = re.search(r'versionInfo[^>]*>(.*?)</', content, re.DOTALL | re.IGNORECASE)
    if m:
        result['versionInfo'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()

    # description — весь body HTML
    m = re.search(r'<body[^>]*>(.*)</body>', content, re.DOTALL | re.IGNORECASE)
    result['description'] = m.group(1).strip() if m else ''

    return result


def extract_all_code_examples(html_content):
    """Извлекает ВСЕ примеры кода из HTML-содержимого.
    
    Ищет все разделы "Пример:" и извлекает код из таблиц <TABLE>.
    
    Args:
        html_content: Полный HTML-контент файла
        
    Returns:
        list[str]: Список очищенных примеров кода
    """
    if not html_content:
        return []
    
    examples = []
    
    # Ищем все разделы "Пример:"
    example_pattern = re.compile(
        r'<p\s+class="[^"]*V8SH_chapter[^"]*"[^>]*>Пример:</p>\s*(.*?)$',
        re.DOTALL | re.IGNORECASE
    )
    
    for example_match in example_pattern.finditer(html_content):
        example_section = example_match.group(1)
        
        # Ищем таблицу с кодом после "Пример:"
        table_match = re.search(r'<TABLE[^>]*>(.*?)</TABLE>', example_section, re.DOTALL | re.IGNORECASE)
        if not table_match:
            continue
        
        table_content = table_match.group(1)
        
        # Извлекаем весь текст из таблицы, удаляя HTML-теги
        text = re.sub(r'<font[^>]*>', '', table_content)
        text = re.sub(r'</font>', '', text)
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Заменяем &nbsp; на пробелы
        text = text.replace('&nbsp;', ' ')
        
        # Очищаем от лишних пробелов и пустых строк
        lines = []
        for line in text.split('\n'):
            cleaned = re.sub(r'\s+', ' ', line).strip()
            if cleaned:
                lines.append(cleaned)
        
        code = '\n'.join(lines)
        
        # Проверяем, что код достаточно содержательный (не менее 10 символов)
        if len(code.strip()) >= 10:
            examples.append(code)
    
    return examples


def extract_code_example(html_content, group_name=None):
    """Извлекает первый пример кода из HTML-содержимого.
    
    Ищет раздел "Пример:" и извлекает код из таблицы <TABLE>.
    Очищает HTML-теги, цвета, &nbsp; и другие артефакты форматирования.
    
    Args:
        html_content: Полный HTML-контент файла
        group_name: Имя группы (используется для формирования вопроса)
        
    Returns:
        str или None: Очищенный текст примера кода, если найден; иначе None
    """
    if not html_content:
        return None
    
    # Ищем раздел "Пример:" в HTML
    example_match = re.search(
        r'<p\s+class="[^"]*V8SH_chapter[^"]*"[^>]*>Пример:</p>\s*(.*?)$',
        html_content,
        re.DOTALL | re.IGNORECASE
    )
    
    if not example_match:
        return None
    
    example_section = example_match.group(1)
    
    # Ищем таблицу с кодом после "Пример:"
    table_match = re.search(r'<TABLE[^>]*>(.*?)</TABLE>', example_section, re.DOTALL | re.IGNORECASE)
    if not table_match:
        return None
    
    table_content = table_match.group(1)
    
    # Извлекаем весь текст из таблицы, удаляя HTML-теги
    # Сначала убираем теги font с атрибутами цвета
    text = re.sub(r'<font[^>]*>', '', table_content)
    text = re.sub(r'</font>', '', text)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)  # Удаляем остальные HTML-теги
    
    # Заменяем &nbsp; на пробелы
    text = text.replace('&nbsp;', ' ')
    
    # Очищаем от лишних пробелов и пустых строк
    lines = []
    for line in text.split('\n'):
        cleaned = re.sub(r'\s+', ' ', line).strip()
        if cleaned:
            lines.append(cleaned)
    
    code = '\n'.join(lines)
    
    # Проверяем, что код достаточно содержательный (не менее 10 символов)
    if len(code.strip()) < 10:
        return None
    
    return code


def load_files(path, category=None):
    """Load HTML files from directory."""
    if not os.path.isdir(path):
        return {'success': False, 'error': f'Path is not a directory: {path}'}

    html_files = []
    for root, dirs, files in os.walk(path):
        for f in files:
            if f.endswith('.html') and f != '__categories__':
                html_files.append(os.path.join(root, f))

    if not html_files:
        return {'success': False, 'error': 'No HTML files found'}

    tags = category or 'language'
    stats = {'files_processed': 0, 'groups_created': 0, 'snippets_created': 0, 'aliases_created': 0, 'errors': 0}

    # Словарь для хранения mapping: group_name -> group_id
    name_to_id = {}

    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()

        groups_batch = []

        for filepath in html_files:
            parsed = parse_html_file(filepath)
            if not parsed or not parsed['pagetitle']:
                continue

            group_name = os.path.basename(filepath).replace('.html', '')
            tags_list = [t.strip() for t in tags.split(',') if t.strip()]

            groups_batch.append((None, group_name, parsed['description'], tags, parsed['pagetitle'], parsed['title'], parsed['versionInfo']))
            stats['files_processed'] += 1

        if groups_batch:
            sql = "INSERT INTO groups (parent_id, name, description, tags, pagetitle, title, versionInfo) VALUES %s"
            data = []
            for item in groups_batch:
                parent_id, name, desc, tags, pt, ti, vi = item
                tl = tags if isinstance(tags, (list, tuple)) else [t.strip() for t in tags.split(',') if t.strip()]
                data.append((parent_id, name, desc, tl, pt or None, ti or None, vi or None))
            pg_extras.execute_values(cur, sql, data, template="(%s, %s, %s, %s::text[], %s, %s, %s)", page_size=500)
            stats['groups_created'] += cur.rowcount
            
            # Сохраняем mapping group_name -> id для последующего создания сниппетов
            for item in groups_batch:
                name = item[1]
                # Получаем ID группы из БД по имени
                cur.execute("SELECT id FROM groups WHERE name = %s AND pagetitle IS NOT NULL ORDER BY id DESC LIMIT 1", (name,))
                row = cur.fetchone()
                if row:
                    name_to_id[name] = row[0]
            
            conn.commit()

        # Step 2: Create snippets for files with code examples
        for filepath in html_files:
            group_name = os.path.basename(filepath).replace('.html', '')
            group_id = name_to_id.get(group_name)
            if not group_id:
                continue
            
            # Читаем HTML-файл и извлекаем пример кода
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    html_content = f.read()
            except Exception:
                continue
            
            code_example = extract_code_example(html_content, group_name)
            if not code_example:
                continue
            
            # Формируем вопрос по pagetitle
            parsed = parse_html_file(filepath)
            pagetitle = parsed.get('pagetitle', group_name)
            
            # Формируем вопрос в зависимости от типа контента
            question = f"Как использовать {pagetitle}?"
            
            # Создаём сниппет
            snippet_result = _add_snippet(
                question=question,
                answer=code_example,
                source_url=filepath,
                tags='bsl,code',
                confidence=0.95,
                groups_id=group_id
            )
            
            if snippet_result.get('success'):
                stats['snippets_created'] += 1
                stats['aliases_created'] += snippet_result.get('aliases_created', 0)

        cur.close()
        return {**stats, 'success': True}

    except Exception as e:
        print(f'[ERROR load_files]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e), **stats}


def load_bsl_docs(path):
    """Load BSL documentation from standard structure (objects/ + tables/).
    
    Алгоритм:
    1. Сканирование структуры каталогов
    2. Очистка старых BSL-данных
    3. Создание корневых групп из objects/*.html
    4. Batch-вставка подкаталогов objects/*/
    5. Специальная обработка catalog213 + tables
    """
    if not os.path.isdir(path):
        return {'success': False, 'error': f'Path is not a directory: {path}'}

    objects_dir = os.path.join(path, 'objects')
    tables_dir = os.path.join(path, 'tables')

    if not os.path.isdir(objects_dir):
        return {'success': False, 'error': f'Missing: {objects_dir}'}
    if not os.path.isdir(tables_dir):
        return {'success': False, 'error': f'Missing: {tables_dir}'}

    OBJECTS_TAGS = 'language,bsl,objects'
    TABLES_TAGS = 'language,bsl,tables'
    stats = {'files_processed': 0, 'groups_created': 0, 'aliases_created': 0, 'snippets_created': 0}

    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()

        # Step 1: Очистка старых BSL-данных
        print('[INFO] Cleaning old BSL data...', flush=True)
        cur.execute("DELETE FROM knowledge_snippets WHERE groups_id IN (SELECT id FROM groups WHERE tags && ARRAY['language','bsl'])")
        deleted_snippets = cur.rowcount
        cur.execute("DELETE FROM alias_targets WHERE groups_id IN (SELECT id FROM groups WHERE tags && ARRAY['language','bsl'])")
        deleted_aliases = cur.rowcount
        cur.execute("DELETE FROM groups WHERE tags && ARRAY['language','bsl']")
        deleted_groups = cur.rowcount
        conn.commit()
        print(f'[INFO] Cleaned: {deleted_groups} groups, {deleted_snippets} snippets, {deleted_aliases} aliases', flush=True)

        # Step 2: Корневые файлы objects/*.html
        root_files = []
        for fn in sorted(os.listdir(objects_dir)):
            fp = os.path.join(objects_dir, fn)
            if os.path.isfile(fp) and fn.endswith('.html') and fn != '__categories__':
                root_files.append(fp)

        # Создаём корневые группы с batch-вставкой
        root_groups_batch = []
        for fp in root_files:
            parsed = parse_html_file(fp)
            if not parsed or not parsed['pagetitle']:
                continue
            
            group_name = os.path.basename(fp).replace('.html', '')
            tags_list = [t.strip() for t in OBJECTS_TAGS.split(',') if t.strip()]
            root_groups_batch.append((None, group_name, parsed['description'], tags_list, 
                                     parsed['pagetitle'] or None, 
                                     parsed['title'] or None, 
                                     parsed['versionInfo'] or None))

        # Batch-вставка корневых групп по 500
        if root_groups_batch:
            sql = "INSERT INTO groups (parent_id, name, description, tags, pagetitle, title, versionInfo) VALUES %s"
            data = []
            for item in root_groups_batch:
                parent_id, name, desc, tags, pt, ti, vi = item
                tl = tags if isinstance(tags, (list, tuple)) else [t.strip() for t in tags.split(',') if t.strip()]
                data.append((parent_id, name, desc, tl, pt or None, ti or None, vi or None))
            pg_extras.execute_values(cur, sql, data, template="(%s, %s, %s, %s::text[], %s, %s, %s)", page_size=500)
            stats['groups_created'] += cur.rowcount
            conn.commit()

        # Создаём алиасы для корневых групп
        for fp in root_files:
            parsed = parse_html_file(fp)
            if not parsed or not parsed['pagetitle']:
                continue
            
            group_name = os.path.basename(fp).replace('.html', '')
            cur.execute("SELECT id FROM groups WHERE name = %s AND parent_id IS NULL LIMIT 1", (group_name,))
            row = cur.fetchone()
            if not row:
                continue
            group_id = row[0]
            
            tag_list = [t.strip() for t in OBJECTS_TAGS.split(',') if t.strip()]
            aliases_created = 0
            alias_texts = []
            if parsed['pagetitle']:
                alias_texts.append(parsed['pagetitle'])
            if parsed['description']:
                alias_texts.append(parsed['description'][:9])
            
            for txt in alias_texts:
                for alias in extract_aliases(txt, max_count=10):
                    cur.execute(
                        "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags, weight) VALUES (%s, 'group', %s, NULL, %s, 1.0) ON CONFLICT (alias_name, groups_id) WHERE groups_id IS NOT NULL DO NOTHING",
                        (alias, group_id, tag_list))
                    aliases_created += 1
            
            stats['aliases_created'] += aliases_created

        # Step 3: Подкаталоги objects/*/
        subdirs_batch = []
        
        for dir_name in sorted(os.listdir(objects_dir)):
            dir_path = os.path.join(objects_dir, dir_name)
            if not os.path.isdir(dir_path):
                continue

            parent_id = None
            parent_file = os.path.join(objects_dir, f'{dir_name}.html')
            if os.path.isfile(parent_file):
                parsed = parse_html_file(parent_file)
                if parsed and parsed['pagetitle']:
                    cur2 = conn.cursor()
                    cur2.execute("SELECT id FROM groups WHERE pagetitle = %s AND parent_id IS NULL LIMIT 1", (parsed['pagetitle'],))
                    row = cur2.fetchone()
                    if row:
                        parent_id = row[0]
                    cur2.close()

            html_files = []
            for root, dirs, files in os.walk(dir_path):
                for f in sorted(files):
                    if f.endswith('.html') and f != '__categories__':
                        html_files.append(os.path.join(root, f))

            for fp in html_files:
                parsed = parse_html_file(fp)
                if not parsed or not parsed['pagetitle']:
                    continue
                
                group_name = os.path.basename(fp).replace('.html', '')
                tags_list = [t.strip() for t in OBJECTS_TAGS.split(',') if t.strip()]
                subdirs_batch.append((parent_id, group_name, parsed['description'], tags_list, 
                                     parsed['pagetitle'] or None, 
                                     parsed['title'] or None, 
                                     parsed['versionInfo'] or None))

            stats['files_processed'] += len(html_files)

        if subdirs_batch:
            sql = "INSERT INTO groups (parent_id, name, description, tags, pagetitle, title, versionInfo) VALUES %s"
            data = []
            for item in subdirs_batch:
                parent_id, name, desc, tags, pt, ti, vi = item
                tl = tags if isinstance(tags, (list, tuple)) else [t.strip() for t in tags.split(',') if t.strip()]
                data.append((parent_id, name, desc, tl, pt or None, ti or None, vi or None))
            pg_extras.execute_values(cur, sql, data, template="(%s, %s, %s, %s::text[], %s, %s, %s)", page_size=500)
            stats['groups_created'] += cur.rowcount
            conn.commit()

        # Step 4: tables/ (catalog213 + tables как единая иерархия)
        table_groups_batch = []
        
        for dir_name in sorted(os.listdir(tables_dir)):
            dir_path = os.path.join(tables_dir, dir_name)
            if not os.path.isdir(dir_path):
                continue

            html_files = []
            for root, dirs, files in os.walk(dir_path):
                for f in sorted(files):
                    if f.endswith('.html') and f != '__categories__':
                        html_files.append(os.path.join(root, f))

            for fp in html_files:
                parsed = parse_html_file(fp)
                if not parsed or not parsed['pagetitle']:
                    continue
                
                group_name = os.path.basename(fp).replace('.html', '')
                tags_list = [t.strip() for t in TABLES_TAGS.split(',') if t.strip()]
                table_groups_batch.append((None, group_name, parsed['description'], tags_list, 
                                          parsed['pagetitle'] or None, 
                                          parsed['title'] or None, 
                                          parsed['versionInfo'] or None))

            stats['files_processed'] += len(html_files)

        if table_groups_batch:
            sql = "INSERT INTO groups (parent_id, name, description, tags, pagetitle, title, versionInfo) VALUES %s"
            data = []
            for item in table_groups_batch:
                parent_id, name, desc, tags, pt, ti, vi = item
                tl = tags if isinstance(tags, (list, tuple)) else [t.strip() for t in tags.split(',') if t.strip()]
                data.append((parent_id, name, desc, tl, pt or None, ti or None, vi or None))
            pg_extras.execute_values(cur, sql, data, template="(%s, %s, %s, %s::text[], %s, %s, %s)", page_size=500)
            stats['groups_created'] += cur.rowcount
            conn.commit()

        # Step 5: Создаём сниппеты для файлов с примерами кода
        all_html_files = []
        
        for fp in root_files:
            all_html_files.append(fp)
        
        for dir_name in sorted(os.listdir(objects_dir)):
            dir_path = os.path.join(objects_dir, dir_name)
            if not os.path.isdir(dir_path):
                continue
            for root, dirs, files in os.walk(dir_path):
                for f in sorted(files):
                    if f.endswith('.html') and f != '__categories__':
                        all_html_files.append(os.path.join(root, f))
        
        for dir_name in sorted(os.listdir(tables_dir)):
            dir_path = os.path.join(tables_dir, dir_name)
            if not os.path.isdir(dir_path):
                continue
            for root, dirs, files in os.walk(dir_path):
                for f in sorted(files):
                    if f.endswith('.html') and f != '__categories__':
                        all_html_files.append(os.path.join(root, f))

        for fp in all_html_files:
            group_name = os.path.basename(fp).replace('.html', '')
            
            cur.execute("SELECT id FROM groups WHERE name = %s LIMIT 1", (group_name,))
            row = cur.fetchone()
            if not row:
                continue
            group_id = row[0]
            
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    html_content = f.read()
            except Exception:
                continue
            
            code_example = extract_code_example(html_content, group_name)
            if not code_example:
                continue
            
            parsed = parse_html_file(fp)
            pagetitle = parsed.get('pagetitle', group_name)
            question = f"Как использовать {pagetitle}?"
            
            snippet_result = _add_snippet(
                question=question,
                answer=code_example,
                source_url=fp,
                tags='bsl,code',
                confidence=0.95,
                groups_id=group_id
            )
            
            if snippet_result.get('success'):
                stats['snippets_created'] += 1

        cur.close()
        return {**stats, 'success': True}

    except Exception as e:
        print(f'[ERROR load_bsl_docs]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e), **stats}

