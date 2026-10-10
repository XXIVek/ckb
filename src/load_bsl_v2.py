#!/usr/bin/env python3
"""load_bsl_v2.py — Загрузка BSL документации v2.

Принцип:
1. Каждый HTML-файл = одна группа в таблице groups
2. Иерархия через parent_id на основе структуры каталогов
3. Алиасы извлекаются и привязываются ВНЕШНЕ ensure_group_with_fields (через extract_aliases)
4. catalog213 + tables = "Работа с запросами"

Использование:
    python load_bsl_v2.py --path=C:\\1C_LLM\\LoadDoc\\html\\BSL -v
"""

import os, sys, re, argparse, html
from datetime import datetime

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

try:
    from src.mcp_tools import (
        ensure_group_with_fields, update_group_fields,
        add_alias_target,
        batch_insert_snippets
    )
    from src.database import get_connection, release_connection
except ImportError as e:
    print(f'ERROR: {e}'); sys.exit(1)

BSL_TAGS = "language,bsl"
OBJECTS_TAGS = "language,bsl,objects"
TABLES_TAGS = "language,bsl,tables"


def log(msg, level='INFO'):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] [{level}] {msg}', flush=True)


def error_log(msg):
    log(msg, 'ERROR')


# ============================================================================
# Парсер HTML
# ============================================================================

def parse_bsl_html(filepath):
    """Парсит один HTML-файл BSL. Возвращает словарь с полями."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return None

    result = {
        'pagetitle': '', 'title': '', 'description': '', 'versionInfo': '',
        'code_examples': [],
    }

    # pagetitle
    m = re.search(r'<h1[^>]*class="V8SH_pagetitle"[^>]*>(.*?)</h1>', content, re.DOTALL)
    if m:
        result['pagetitle'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()

    # title (V8SH_title)
    m = re.search(r'<p[^>]*class="V8SH_title"[^>]*>(.*?)</p>', content, re.DOTALL)
    if m:
        result['title'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()

    # versionInfo — информация о версии платформы (для определения совместимости)
    m = re.search(r'versionInfo[^>]*>(.*?)</', content, re.DOTALL | re.IGNORECASE)
    if m:
        result['versionInfo'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()

    # description — ВЕСЬ <body> целиком (HTML для долговременной памяти)
    body_m = re.search(r'<body[^>]*>(.*)</body>', content, re.DOTALL | re.IGNORECASE)
    result['description'] = body_m.group(1).strip() if body_m else ''

    # code_examples — все <table> из body
    code_examples = []
    for table_m in re.finditer(r'<table[^>]*>(.*?)</table>', result['description'], re.DOTALL | re.IGNORECASE):
        tc = table_m.group(1)
        tc = re.sub(r'</?(?:tbody|tr|td)[^>]*>', '\n', tc, flags=re.IGNORECASE)
        tc = re.sub(r'<br\s*/?>', '\n', tc, flags=re.IGNORECASE)
        code = re.sub(r'<[^>]+>', '', tc)
        code = html.unescape(code).replace('\xa0', ' ')
        lines = [l.strip() for l in code.split('\n') if l.strip()]
        code = '\n'.join(lines)
        if len(code) > 10:
            code_examples.append(code)
    result['code_examples'] = code_examples

    return result


# ============================================================================
# Сканирование
# ============================================================================

def scan_bsl_directory(bsl_path):
    """Возвращает структуру для загрузки."""
    objects_dir = os.path.join(bsl_path, 'objects')
    tables_dir = os.path.join(bsl_path, 'tables')
    
    result = {
        'bsl_path': bsl_path,
        'objects_dir': objects_dir,
        'tables_dir': tables_dir,
        'root_files': [],
        'subdirs': {},
        'tables_subdirs': {},
        'total_html': 0,
        'total_st': 0,
        'total_files': 0,
    }
    
    # Корневые файлы objects/
    if os.path.isdir(objects_dir):
        for fn in sorted(os.listdir(objects_dir)):
            fp = os.path.join(objects_dir, fn)
            if os.path.isfile(fp):
                result['root_files'].append({'name': fn, 'path': fp, 'size': os.path.getsize(fp)})
    
    # Подкаталоги objects/
    if os.path.isdir(objects_dir):
        for item in sorted(os.listdir(objects_dir)):
            ip = os.path.join(objects_dir, item)
            if os.path.isdir(ip):
                html_files = []
                st_files = []
                total = 0
                for root, dirs, files in os.walk(ip):
                    for fn in files:
                        fp = os.path.join(root, fn)
                        total += 1
                        if fn.endswith('.html'):
                            html_files.append(fp)
                        elif fn.endswith('.st'):
                            st_files.append(fp)
                result['subdirs'][item] = {
                    'path': ip,
                    'total_files': total,
                    'html_files': len(html_files),
                    'st_files': len(st_files),
                    'html_files_list': html_files,
                }
    
    # Подкаталоги tables/
    if os.path.isdir(tables_dir):
        for item in sorted(os.listdir(tables_dir)):
            ip = os.path.join(tables_dir, item)
            if os.path.isdir(ip):
                html_files = []
                st_files = []
                total = 0
                for root, dirs, files in os.walk(ip):
                    for fn in files:
                        fp = os.path.join(root, fn)
                        total += 1
                        if fn.endswith('.html'):
                            html_files.append(fp)
                        elif fn.endswith('.st'):
                            st_files.append(fp)
                result['tables_subdirs'][item] = {
                    'path': ip,
                    'total_files': total,
                    'html_files': len(html_files),
                    'st_files': len(st_files),
                    'html_files_list': html_files,
                }
    
    # Итоги
    result['total_html'] = len([f for f in result['root_files'] if f['name'].endswith('.html')])
    result['total_st'] = len([f for f in result['root_files'] if f['name'].endswith('.st')])
    for info in result['subdirs'].values():
        result['total_html'] += info['html_files']
        result['total_st'] += info['st_files']
    for info in result['tables_subdirs'].values():
        result['total_html'] += info['html_files']
        result['total_st'] += info['st_files']
    result['total_files'] = result['total_html'] + result['total_st']
    
    return result


# ============================================================================
# Очистка BSL-данных
# ============================================================================

def cleanup_old_bsl_data():
    """Очищает старые BSL-данные по tags."""
    log('Очистка старых BSL-данных...')
    conn = get_connection()
    cur = conn.cursor()
    
    queries = [
        "DELETE FROM knowledge_snippets WHERE 'bsl' = ANY(tags)",
        "DELETE FROM elements WHERE 'bsl' = ANY(tags)",
        "DELETE FROM groups WHERE 'bsl' = ANY(tags)",
        # Алиасы чистим по tags — быстро и точно
        "DELETE FROM alias_targets WHERE 'bsl' = ANY(tags)",
    ]
    
    for sql in queries:
        try:
            cur.execute(sql)
            conn.commit()
            log(f'  OK: {sql[:60]}...')
        except Exception as e:
            log(f'  WARNING: {e}')
    
    cur.close()
    release_connection(conn)
    log('Очистка завершена.')


# ============================================================================
# Загрузка каталога catalog213 + tables
# ============================================================================

def load_catalog213_with_tables(scan):
    """Загрузка catalog213 + tables как единой иерархии."""
    cat213_path = os.path.join(scan['bsl_path'], 'objects', 'catalog213')
    catalog213_name = 'Работа с запросами'
    
    # Ищем pagetitle из первого HTML в catalog213
    if os.path.isdir(cat213_path):
        for fn in os.listdir(cat213_path):
            fp = os.path.join(cat213_path, fn)
            if os.path.isfile(fp) and fn.endswith('.html'):
                parsed = parse_bsl_html(fp)
                if parsed and parsed['pagetitle']:
                    catalog213_name = parsed['pagetitle']
                    break
    
    # Создаём группу "Работа с запросами"
    cat213_id = ensure_group_with_fields(catalog213_name, parent_id=None, description='', tags=BSL_TAGS)
    if not cat213_id.get('success'):
        log(f'  ERROR creating catalog213: {cat213_id}')
        return
    
    cat213_id = cat213_id['group_id']
    log(f'  Created catalog213: "{catalog213_name}" (ID={cat213_id})')
    
    # Подгруппы catalog213
    if os.path.isdir(cat213_path):
        for item in sorted(os.listdir(cat213_path)):
            ip = os.path.join(cat213_path, item)
            if os.path.isdir(ip):
                sub_result = ensure_group_with_fields(item, parent_id=cat213_id, description='', tags=OBJECTS_TAGS)
                if sub_result.get('success'):
                    log(f'    Created subgroup: {item} (ID={sub_result["group_id"]})')
    
    # Группа "Таблицы запросов" (name="tables")
    tables_group_result = ensure_group_with_fields(
        'tables', parent_id=cat213_id, description='', tags=TABLES_TAGS,
        pagetitle='Таблицы запросов', title='Таблицы запросов'
    )
    
    if not tables_group_result.get('success'):
        log(f'  ERROR creating tables group')
        return
    
    tables_group_id = tables_group_result['group_id']
    log(f'  Created "Таблицы запросов" (ID={tables_group_id})')
    
    # Загружаем файлы из tables/
    tables_dir = scan['tables_dir']
    if os.path.isdir(tables_dir):
        for fn in sorted(os.listdir(tables_dir)):
            fp = os.path.join(tables_dir, fn)
            if os.path.isdir(fp):
                sub_result = ensure_group_with_fields(fn, parent_id=tables_group_id, description='', tags=TABLES_TAGS)
                if sub_result.get('success'):
                    sub_id = sub_result['group_id']
                    log(f'    Created table group: {fn} (ID={sub_id})')
                    
                    # Обрабатываем HTML-файлы внутри
                    html_files = []
                    for root, dirs, files in os.walk(fp):
                        for f in sorted(files):
                            if f.endswith('.html') and f != '__categories__':
                                html_files.append(os.path.join(root, f))
                    
                    for hfp in html_files:
                        parsed = parse_bsl_html(hfp)
                        if parsed and parsed['pagetitle']:
                            ensure_group_with_fields(
                                parsed['pagetitle'], parent_id=sub_id,
                                description=parsed['description'], tags=TABLES_TAGS,
                                pagetitle=parsed['pagetitle'], title=parsed['title']
                            )


# ============================================================================
# Загрузка подкаталогов objects/*/
# ============================================================================

def load_all_html_elements(scan, filter_name=''):
    """Загрузка HTML-файлов как групп.
    
    Оптимизация: одно соединение на пачку из 500 файлов вместо одного на каждый файл.
    """
    from src.mcp_tools import ensure_group_in_conn, commit_conn
    
    stats = {
        'html_files_processed': 0,
        'groups_created': 0,
        'aliases_added': 0,
        'snippets_created': 0,
        'skipped_empty': 0,
        'errors': 0,
    }
    
    # =========================================================================
    # Шаг 1: Сбор файлов
    # =========================================================================
    log('Сбор файлов для загрузки...')
    
    all_files = []  # (filepath, parent_id_or_none, tags)
    
    # Корневые файлы objects/*.html
    for f in scan['root_files']:
        if not f['name'].endswith('.html') or f['name'] == '__categories__':
            continue
        if filter_name and filter_name not in f['name']:
            continue
        all_files.append((f['path'], None, OBJECTS_TAGS))
    
    # Подкаталоги objects/*/
    for dir_name, info in scan['subdirs'].items():
        if filter_name and filter_name not in dir_name:
            continue
        if dir_name == 'catalog213':
            continue
        
        for fp in info['html_files_list']:
            all_files.append((fp, dir_name, OBJECTS_TAGS))
    
    log(f'Всего файлов для обработки: {len(all_files)}')
    
    # =========================================================================
    # Шаг 2: Парсинг + создание групп пачками (500 файлов = 1 conn)
    # =========================================================================
    log('Парсинг HTML-файлов...')
    
    batch_size = 500
    snippets_batch = []
    parsed_count = 0
    
    for i in range(0, len(all_files), batch_size):
        batch = all_files[i:i+batch_size]
        
        # Открываем ОДНО соединение на всю пачку
        conn = get_connection()
        cur = conn.cursor(cursor_factory=get_connection().cursor.__class__) if False else conn.cursor()
        
        batch_created = 0
        
        for filepath, parent_ref, tags in batch:
            parsed = parse_bsl_html(filepath)
            
            if not parsed or not parsed['pagetitle']:
                stats['skipped_empty'] += 1
                continue
            
            # Определяем parent_id (только для первого файла в пачке — кэшируем)
            group_parent_id = None
            if parent_ref:
                cur2 = conn.cursor()
                cur2.execute(
                    "SELECT id FROM groups WHERE name = %s AND parent_id IS NULL LIMIT 1",
                    (parent_ref,)
                )
                row = cur2.fetchone()
                if row:
                    group_parent_id = row[0]
                cur2.close()
            
            # Определяем name для группы
            group_name = os.path.basename(filepath).replace('.html', '')
            
            # Создаём группу в том же соединении (без open/close)
            result = ensure_group_in_conn(
                conn,
                group_name, parent_id=group_parent_id,
                description=parsed['description'], tags=tags,
                pagetitle=parsed['pagetitle'], title=parsed['title'],
                versionInfo=parsed.get('versionInfo', '')
            )
            
            if result.get('success'):
                stats['groups_created'] += 1
                stats['aliases_added'] += result.get('aliases_created', 0)
                batch_created += 1
                
                # Сниппеты кода
                code_count = len(parsed.get('code_examples', []))
                if code_count > 0:
                    for code in parsed['code_examples'][:3]:
                        snippets_batch.append((
                            result['group_id'],
                            f'Пример: {parsed["pagetitle"]}',
                            code,
                            ['bsl', 'code'],
                            0.9,
                        ))
                    log(f'  +{code_count} snippet(s) for {parsed["pagetitle"][:40]}')
            else:
                stats['errors'] += 1
            
            parsed_count += 1
        
        # Коммитим пачку и закрываем соединение
        commit_conn(conn)
        
        log(f'  обработано {parsed_count} файлов (пачка: {batch_created} групп)...')
        
        # Возвращаем соединение в пул — КРИТИЧЕСКИ ВАЖНО для предотвращения исчерпания
        release_connection(conn)
    
    stats['html_files_processed'] = parsed_count
    
    # =========================================================================
    # Шаг 3: Batch-вставка сниппетов
    # =========================================================================
    if snippets_batch:
        log(f'Вставка {len(snippets_batch)} сниппетов...')
        
        snip_size = 500
        inserted = 0
        for i in range(0, len(snippets_batch), snip_size):
            batch = snippets_batch[i:i+snip_size]
            
            result = batch_insert_snippets(batch)
            if result.get('success'):
                cnt = result.get('count', 0)
                inserted += cnt
                log(f'  Вставлено: {cnt} (итого: {inserted})')
            else:
                log(f'  ERROR вставки сниппетов: {result.get("error")}')
                break
        
        stats['snippets_created'] = inserted
    
    return stats


# ============================================================================
# Статистика
# ============================================================================

def print_statistics():
    """Выводит статистику из БД."""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT COUNT(*) FROM groups WHERE 'bsl' = ANY(tags)")
        groups_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM elements WHERE 'bsl' = ANY(tags)")
        elements_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM knowledge_snippets WHERE 'bsl' = ANY(tags)")
        snippets_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM alias_targets WHERE 'bsl' = ANY(tags)")
        aliases_count = cur.fetchone()[0]
        
        print('\n' + '=' * 60)
        print('DATABASE STATE:')
        print(f'  Groups (BSL):     {groups_count}')
        print(f'  Elements (BSL):   {elements_count}')
        print(f'  Snippets (BSL):   {snippets_count}')
        print(f'  Aliases:          {aliases_count}')
        print('=' * 60 + '\n')
    
    except Exception as e:
        log(f'ERROR getting statistics: {e}')
    finally:
        cur.close()
        release_connection(conn)


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Загрузка BSL документации v2')
    parser.add_argument('--path', required=True, help='Path to BSL root')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--filter', default='', help='Filter by directory name')
    args = parser.parse_args()
    
    bsl_path = os.path.abspath(args.path)
    log(f'Starting BSL v2 load from: {bsl_path}')
    
    if not os.path.isdir(bsl_path):
        print(f'ERROR: Path does not exist: {bsl_path}'); sys.exit(1)
    
    objects_dir = os.path.join(bsl_path, 'objects')
    tables_dir = os.path.join(bsl_path, 'tables')
    
    if not os.path.isdir(objects_dir):
        print(f'ERROR: Missing directory: {objects_dir}'); sys.exit(1)
    if not os.path.isdir(tables_dir):
        print(f'ERROR: Missing directory: {tables_dir}'); sys.exit(1)
    
    # Шаг 1: Сканирование
    log('Step 1: Scanning file structure...')
    scan = scan_bsl_directory(bsl_path)
    
    log(f'  Root files objects/: {len(scan["root_files"])}')
    log(f'  Objects subdirs: {len(scan["subdirs"])}')
    log(f'  Tables subdirs: {len(scan["tables_subdirs"])}')
    log(f'\n  TOTAL: {scan["total_html"]} HTML, {scan["total_st"]} .st, {scan["total_files"]} total')
    
    # Шаг 2: Очистка
    log('\nStep 2: Cleaning old BSL data...')
    cleanup_old_bsl_data()
    
    # Шаг 3: Создание групп из объектов (root-файлы)
    log('\nStep 3: Loading objects groups...')
    
    for f in scan['root_files']:
        if not f['name'].endswith('.html') or f['name'] == '__categories__':
            continue
        
        parsed = parse_bsl_html(f['path'])
        if not parsed or not parsed['pagetitle']:
            continue
        
        result = ensure_group_with_fields(
            parsed['pagetitle'], parent_id=None,
            description=parsed['description'], tags=OBJECTS_TAGS,
            pagetitle=parsed['pagetitle'], title=parsed['title'],
            versionInfo=parsed.get('versionInfo', '')
        )
        
        if result.get('success'):
            log(f'  Created root group: "{parsed["pagetitle"]}" (ID={result["group_id"]}, aliases={result["aliases_created"]})')
    
    # Шаг 4: Загрузка подкаталогов objects/*/
    log('\nStep 4: Loading subdirectory groups...')
    
    stats = load_all_html_elements(scan, args.filter)
    
    # Шаг 5: catalog213 + tables
    log('\nStep 5: Loading catalog213 + tables...')
    load_catalog213_with_tables(scan)
    
    # Итоги
    log(f'\nUpload statistics:')
    log(f'  Files processed: {stats["html_files_processed"]}')
    log(f'  Groups created: {stats["groups_created"]}')
    log(f'  Aliases added: {stats["aliases_added"]}')
    log(f'  Snippets created: {stats["snippets_created"]}')
    log(f'  Skipped (empty): {stats["skipped_empty"]}')
    log(f'  Errors: {stats["errors"]}')
    
    print_statistics()
    log('BSL v2 load completed!')


if __name__ == '__main__':
    main()
