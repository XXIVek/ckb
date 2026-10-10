#!/usr/bin/env python3
"""BSL reloader - новая версия загрузчика BSL с полями heading и алиасами."""

import os
import re
import psycopg2.extras as pg_extras
from mcp_tools_core import _get_pool
from mcp_tools_api import add_snippet as _add_snippet


def parse_html_file(filepath):
    """Parse BSL HTML file with heading extraction."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return None

    result = {'pagetitle': '', 'title': '', 'heading': '', 'description': '', 'versionInfo': ''}

    m = re.search(r'<h1[^>]*class="[^"]*V8SH_pagetitle[^"]*"[^>]*>(.*?)</h1>', content, re.DOTALL)
    if m:
        result['pagetitle'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()

    m = re.search(r'<p[^>]*class="[^"]*V8SH_title[^"]*"[^>]*>(.*?)</p>', content, re.DOTALL)
    if m:
        result['title'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()

    m = re.search(r'<p[^>]*class="[^"]*V8SH_heading[^"]*"[^>]*>(.*?)</', content, re.DOTALL)
    if m:
        result['heading'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()

    m = re.search(r'versionInfo[^>]*>(.*?)</', content, re.DOTALL | re.IGNORECASE)
    if m:
        result['versionInfo'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()

    m = re.search(r'<body[^>]*>(.*)</body>', content, re.DOTALL | re.IGNORECASE)
    result['description'] = m.group(1).strip() if m else ''

    return result


def extract_all_code_examples(html_content):
    """Извлекает ВСЕ примеры кода из HTML-содержимого."""
    if not html_content:
        return []
    
    examples = []
    example_pattern = re.compile(
        r'<p\s+class="[^"]*V8SH_chapter[^"]*"[^>]*>Пример:</p>\s*(.*?)$',
        re.DOTALL | re.IGNORECASE
    )
    
    for example_match in example_pattern.finditer(html_content):
        example_section = example_match.group(1)
        table_match = re.search(r'<TABLE[^>]*>(.*?)</TABLE>', example_section, re.DOTALL | re.IGNORECASE)
        if not table_match:
            continue
        
        table_content = table_match.group(1)
        text = re.sub(r'<font[^>]*>', '', table_content)
        text = re.sub(r'</font>', '', text)
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = text.replace('&nbsp;', ' ')
        
        lines = []
        for line in text.split('\n'):
            cleaned = re.sub(r'\s+', ' ', line).strip()
            if cleaned:
                lines.append(cleaned)
        
        code = '\n'.join(lines)
        if len(code.strip()) >= 10:
            examples.append(code)
    
    return examples


def load_bsl_docs_v2(path):
    """Загрузка BSL документации с полями heading, алиасами и сниппетами."""
    if not os.path.isdir(path):
        return {'success': False, 'error': f'Path is not a directory: {path}'}

    objects_dir = os.path.join(path, 'objects')
    tables_dir = os.path.join(path, 'tables')

    if not os.path.isdir(objects_dir):
        return {'success': False, 'error': f'Missing: {objects_dir}'}
    if not os.path.isdir(tables_dir):
        return {'success': False, 'error': f'Missing: {tables_dir}'}

    OBJECTS_TAGS = 'language,bsl,objects'
    stats = {'files_processed': 0, 'groups_created': 0, 'aliases_created': 0, 'snippets_created': 0}

    try:
        pool = _get_pool()
        conn = pool.getconn()
        cur = conn.cursor()

        # Step 1: Сканирование всех HTML-файлов
        print('[INFO] Scanning BSL files...', flush=True)
        all_html_files = []
        
        for fn in sorted(os.listdir(objects_dir)):
            fp = os.path.join(objects_dir, fn)
            if os.path.isfile(fp) and fn.endswith('.html') and fn != '__categories__':
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
        
        total_files = len(all_html_files)
        use_batch = total_files > 200
        
        print(f'[INFO] Found {total_files} HTML files. Use batch mode: {use_batch}', flush=True)

        # Step 2: Очистка старых BSL-данных
        print('[INFO] Cleaning old BSL data...', flush=True)
        cur.execute("DELETE FROM knowledge_snippets WHERE groups_id IN (SELECT id FROM groups WHERE tags && ARRAY['language','bsl'])")
        deleted_snippets = cur.rowcount
        cur.execute("DELETE FROM alias_targets WHERE groups_id IN (SELECT id FROM groups WHERE tags && ARRAY['language','bsl'])")
        deleted_aliases = cur.rowcount
        cur.execute("DELETE FROM groups WHERE tags && ARRAY['language','bsl']")
        deleted_groups = cur.rowcount
        conn.commit()
        print(f'[INFO] Cleaned: {deleted_groups} groups, {deleted_snippets} snippets, {deleted_aliases} aliases', flush=True)

        # Step 3: Парсинг всех HTML-файлов
        print('[INFO] Parsing HTML files...', flush=True)
        
        groups_data = []
        
        for fp in all_html_files:
            parsed = parse_html_file(fp)
            if not parsed or not parsed['pagetitle']:
                continue
            
            group_name = os.path.basename(fp).replace('.html', '')
            rel_path = os.path.relpath(fp, objects_dir)
            parts = rel_path.split(os.sep)
            parent_id = None
            if len(parts) > 1:
                parent_dir = parts[0]
                parent_file = os.path.join(objects_dir, f'{parent_dir}.html')
                if os.path.isfile(parent_file):
                    parent_parsed = parse_html_file(parent_file)
                    if parent_parsed and parent_parsed['pagetitle']:
                        cur_parent = conn.cursor()
                        cur_parent.execute("SELECT id FROM groups WHERE pagetitle = %s AND parent_id IS NULL LIMIT 1", (parent_parsed['pagetitle'],))
                        row = cur_parent.fetchone()
                        if row:
                            parent_id = row[0]
                        cur_parent.close()
            
            tags_list = [t.strip() for t in OBJECTS_TAGS.split(',') if t.strip()]
            groups_data.append((parent_id, group_name, parsed['description'], tags_list, parsed['pagetitle'] or None, parsed['title'] or None, parsed['heading'] or None, parsed['versionInfo'] or None, fp))
        
        stats['files_processed'] = len(groups_data)
        print(f'[INFO] Parsed {len(groups_data)} groups', flush=True)

        # Step 4: Batch INSERT групп
        if use_batch and len(groups_data) > 200:
            print(f'[INFO] Batch-inserting {len(groups_data)} groups by 500...', flush=True)
            for i in range(0, len(groups_data), 500):
                batch = groups_data[i:i+500]
                data = []
                for item in batch:
                    parent_id, name, desc, tags, pt, ti, heading, vi, fp_path = item
                    tl = tags if isinstance(tags, (list, tuple)) else [t.strip() for t in tags.split(',') if t.strip()]
                    data.append((parent_id, name, desc, tl, pt or None, ti or None, heading or None, vi or None))
                sql = "INSERT INTO groups (parent_id, name, description, tags, pagetitle, title, heading, versionInfo) VALUES %s"
                pg_extras.execute_values(cur, sql, data, template="(%s, %s, %s, %s::text[], %s, %s, %s, %s)", page_size=500)
                stats['groups_created'] += cur.rowcount
                conn.commit()
        else:
            for item in groups_data:
                parent_id, name, desc, tags, pt, ti, heading, vi, fp_path = item
                tl = tags if isinstance(tags, (list, tuple)) else [t.strip() for t in tags.split(',') if t.strip()]
                cur.execute("INSERT INTO groups (parent_id, name, description, tags, pagetitle, title, heading, versionInfo) VALUES (%s, %s, %s, %s::text[], %s, %s, %s, %s) RETURNING id", (parent_id, name, desc, tl, pt or None, ti or None, heading or None, vi or None))
                stats['groups_created'] += 1
                conn.commit()
        
        print(f'[INFO] Groups created: {stats["groups_created"]}', flush=True)

        # Step 5: Извлечение кода и создание сниппетов (один на группу, все примеры склеены)
        print('[INFO] Extracting code examples and creating snippets...', flush=True)
        snippets_data = []
        
        for item in groups_data:
            group_name = item[1]
            cur.execute("SELECT id FROM groups WHERE name = %s LIMIT 1", (group_name,))
            row = cur.fetchone()
            if not row:
                continue
            group_id = row[0]
            filepath = item[8]
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    html_content = f.read()
            except Exception:
                continue
            
            code_examples = extract_all_code_examples(html_content)
            if not code_examples:
                continue
            
            combined_answer = ""
            for idx, example in enumerate(code_examples, 1):
                combined_answer += f"[Пример {idx}]\n{example}\n\n"
            
            parsed = parse_html_file(filepath)
            pagetitle = parsed.get('pagetitle', group_name)
            question = f"Как использовать {pagetitle}?"
            tags_list = ['bsl', 'code']
            snippets_data.append((group_id, question, combined_answer, tags_list, 0.95))
        
        stats['snippets_possible'] = len(snippets_data)
        print(f'[INFO] Found {len(snippets_data)} groups with code examples', flush=True)

        # Step 6: Batch INSERT сниппетов
        if use_batch and len(snippets_data) > 200:
            print(f'[INFO] Batch-inserting {len(snippets_data)} snippets by 500...', flush=True)
            for i in range(0, len(snippets_data), 500):
                batch = snippets_data[i:i+500]
                data = []
                for group_id, question, answer, tags, confidence in batch:
                    tl = [t.strip() for t in tags if isinstance(tags, (list, tuple))] or [t.strip() for t in str(tags).split(',') if t.strip()]
                    data.append((group_id, question, answer[:100000], tl, confidence))
                sql = "INSERT INTO knowledge_snippets (groups_id, question, answer, tags, confidence) VALUES %s"
                pg_extras.execute_values(cur, sql, data, template="(%s, %s, %s, %s::text[], %s)", page_size=500)
                stats['snippets_created'] += cur.rowcount
                conn.commit()
        else:
            for group_id, question, answer, tags, confidence in snippets_data:
                tl = [t.strip() for t in tags if isinstance(tags, (list, tuple))] or [t.strip() for t in str(tags).split(',') if t.strip()]
                cur.execute("INSERT INTO knowledge_snippets (groups_id, question, answer, tags, confidence) VALUES (%s, %s, %s, %s::text[], %s) RETURNING id", (group_id, question, answer[:100000], tl, confidence))
                stats['snippets_created'] += 1
                conn.commit()
        
        print(f'[INFO] Snippets created: {stats["snippets_created"]}', flush=True)

        # Step 7: Генерация групповых алиасов
        print('[INFO] Generating group aliases...', flush=True)
        from src.alias_generator import generate_bsl_aliases
        
        all_groups_for_aliases = []
        cur.execute("SELECT id, title, heading, tags FROM groups WHERE 'bsl' = ANY(tags)")
        for row in cur.fetchall():
            group_id, title, heading, tags = row
            tag_list = list(tags) if tags else ['language', 'bsl']
            all_groups_for_aliases.append((group_id, title or '', heading or '', tag_list))
        
        total_aliases = 0
        if use_batch and len(all_groups_for_aliases) > 200:
            print(f'[INFO] Batch-generating {len(all_groups_for_aliases)} group aliases...', flush=True)
            for i in range(0, len(all_groups_for_aliases), 500):
                batch = all_groups_for_aliases[i:i+500]
                for gid, tle, hdg, tgs in batch:
                    added = generate_bsl_aliases(gid, tle, hdg, tgs, conn)
                    total_aliases += added
            conn.commit()
        else:
            for group_id, title, heading, tags in all_groups_for_aliases:
                added = generate_bsl_aliases(group_id, title, heading, tags, conn)
                total_aliases += added
            conn.commit()
        
        stats['aliases_created'] = total_aliases
        print(f'[INFO] Aliases created: {total_aliases}', flush=True)

        # Step 8: Привязка ВСЕХ алиасов группы к её сниппету (batch по 500)
        print('[INFO] Binding aliases to snippets...', flush=True)
        
        if use_batch and len(snippets_data) > 200:
            for i in range(0, len(snippets_data), 500):
                batch = snippets_data[i:i+500]
                for group_id, question, answer, tags, confidence in batch:
                    cur.execute("SELECT id FROM knowledge_snippets WHERE groups_id = %s LIMIT 1", (group_id,))
                    snippet_row = cur.fetchone()
                    if not snippet_row:
                        continue
                    snippet_id = snippet_row[0]
                    cur.execute("UPDATE alias_targets SET snippets_id = %s WHERE groups_id = %s AND snippets_id IS NULL", (snippet_id, group_id))
                    bound = cur.rowcount
                    print(f'  Bound {bound} aliases for group {group_id}', flush=True)
                conn.commit()
        else:
            for group_id, question, answer, tags, confidence in snippets_data:
                cur.execute("SELECT id FROM knowledge_snippets WHERE groups_id = %s LIMIT 1", (group_id,))
                snippet_row = cur.fetchone()
                if not snippet_row:
                    continue
                snippet_id = snippet_row[0]
                cur.execute("UPDATE alias_targets SET snippets_id = %s WHERE groups_id = %s AND snippets_id IS NULL", (snippet_id, group_id))
                bound = cur.rowcount
                print(f'  Bound {bound} aliases for group {group_id}', flush=True)
            conn.commit()
        
        stats['snippets_bound'] = len(snippets_data)
        cur.close()
        return {**stats, 'success': True}

    except Exception as e:
        print(f'[ERROR load_bsl_docs_v2]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e), **stats}
