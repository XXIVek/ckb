#!/usr/bin/env python3
"""File loaders for 1C Knowledge Base."""
import os
import re
import psycopg2.extras as pg_extras
from .mcp_tools_core import _get_pool, extract_aliases


def parse_html_file(filepath):
    """Parse BSL HTML file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return None
    
    result = {'pagetitle': '', 'title': '', 'description': '', 'versionInfo': ''}
    
    m = re.search(r'<h1[^>]*class="V8SH_pagetitle"[^>]*>(.*?)</h1>', content, re.DOTALL)
    if m:
        result['pagetitle'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()
    
    m = re.search(r'<p[^>]*class="V8SH_title"[^>]*>(.*?)</p>', content, re.DOTALL)
    if m:
        result['title'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()
    
    m = re.search(r'versionInfo[^>]*>(.*?)</', content, re.DOTALL | re.IGNORECASE)
    if m:
        result['versionInfo'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()
    
    m = re.search(r'<body[^>]*>(.*)</body>', content, re.DOTALL | re.IGNORECASE)
    result['description'] = m.group(1).strip() if m else ''
    
    return result


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
    stats = {'files_processed': 0, 'groups_created': 0, 'aliases_created': 0, 'errors': 0}
    
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
        
        # Batch insert
        if groups_batch:
            sql = "INSERT INTO groups (parent_id, name, description, tags, pagetitle, title, versionInfo) VALUES %s"
            data = []
            for item in groups_batch:
                parent_id, name, desc, tags, pt, ti, vi = item
                tl = tags if isinstance(tags, (list, tuple)) else [t.strip() for t in tags.split(',') if t.strip()]
                data.append((parent_id, name, desc, tl, pt or None, ti or None, vi or None))
            pg_extras.execute_values(cur, sql, data, template="(%s, %s, %s, %s::text[], %s, %s, %s)", page_size=500)
            stats['groups_created'] += cur.rowcount
            conn.commit()
        
        cur.close()
        return {**stats, 'success': True}
    
    except Exception as e:
        print(f'[ERROR load_files]: {str(e)}', flush=True)
        return {'success': False, 'error': str(e), **stats}
