#!/usr/bin/env python3
"""Module config_export_manager."""
import os, json
from datetime import datetime

def _get_config_db_connection():
    import psycopg2
    return psycopg2.connect(host='localhost', port=5432, dbname='configurations', user='postgres', password='Sta090860')

def export_config_changes(config_id, target_path=None):
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT source_path FROM configuration WHERE id = %s', (config_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            return {'success': False, 'error': f'Конфигурация ID={config_id} не найдена'}
        base_source_path = row[0]
        if not target_path:
            target_path = base_source_path
        cur.execute('SELECT id, type, name, description, file_relative_path, original_xml, updated_at FROM configuration_objects WHERE configuration_id = %s AND modified = TRUE ORDER BY type, name', (config_id,))
        modified_objects = cur.fetchall()
        if not modified_objects:
            return {'success': True, 'export_file': None, 'target_path': target_path, 'base_source_path': base_source_path, 'objects_count': 0, 'snippets_count': 0, 'message': 'Нет изменённых объектов'}
        cur.execute('SELECT id, question, answer, tags FROM config_snippets WHERE config_id = %s', (config_id,))
        snippets = cur.fetchall()
        export_data = {'config_id': config_id, 'exported_at': datetime.now().isoformat(), 'base_source_path': base_source_path, 'snippets_count': len(snippets), 'changes_count': len(modified_objects), 'objects': []}
        cur.execute('SELECT csd.snippet_id, csd.target_type, csd.target_name, csd.dependency_type FROM config_snippet_dependencies csd JOIN config_snippets cs ON csd.snippet_id = cs.id WHERE cs.config_id = %s', (config_id,))
        dependencies = cur.fetchall()
        deps_by_snippet = {}
        for snippet_id, target_type, target_name, dep_type in dependencies:
            if snippet_id not in deps_by_snippet:
                deps_by_snippet[snippet_id] = []
            deps_by_snippet[snippet_id].append({'target_type': target_type, 'target_name': target_name, 'dependency_type': dep_type})
        objects_map = {}
        for snippet_id, question, answer, tags in snippets:
            snippet_deps = deps_by_snippet.get(snippet_id, [])
            for dep in snippet_deps:
                obj_key = f"{dep['target_type']}:{dep['target_name']}"
                if obj_key not in objects_map:
                    objects_map[obj_key] = {'type': dep['target_type'], 'name': dep['target_name'], 'snippets': [], 'relative_path': f"{dep['target_type']}/{dep['target_name']}"}
                objects_map[obj_key]['snippets'].append({'id': snippet_id, 'question': question[:200], 'answer': answer[:5000], 'tags': tags or [], 'dependency_type': dep['dependency_type']})
        export_data['objects'] = list(objects_map.values())
        export_data['changes_count'] = len(objects_map)
        os.makedirs(target_path, exist_ok=True)
        export_file = os.path.join(target_path, 'config_changes_export.json')
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        exported_files = []
        for obj_id, obj_type, obj_name, description, rel_path, original_xml, updated_at in modified_objects:
            if not original_xml or not original_xml.strip():
                continue
            obj_file_path = os.path.join(target_path, rel_path)
            obj_dir = os.path.dirname(obj_file_path)
            os.makedirs(obj_dir, exist_ok=True)
            with open(obj_file_path, 'w', encoding='utf-8') as f:
                f.write(original_xml)
            exported_files.append({'file': obj_file_path, 'type': obj_type, 'name': obj_name, 'updated_at': str(updated_at) if updated_at else None})
        cur.close()
        _log_export(config_id, target_path, len(exported_files), len(snippets))
        return {'success': True, 'export_file': export_file, 'target_path': target_path, 'base_source_path': base_source_path, 'objects_count': len(exported_files), 'snippets_count': len(snippets), 'exported_files': exported_files}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()

def _log_export(config_id, target_path, objects_count, changes_count):
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        safe_path = target_path.replace("'", "''")
        sql = f"INSERT INTO config_export_log (config_id, target_path, objects_count, changes_count, status) VALUES ({config_id}, '{safe_path}', {objects_count}, {changes_count}, 'success')"
        cur.execute(sql)
        conn.commit()
        cur.close()
    except Exception as e:
        conn.rollback()
        print(f'[ERROR _log_export]: {str(e)}', flush=True)
    finally:
        conn.close()

def get_export_log(config_id=None, limit=20):
    conn = _get_config_db_connection()
    try:
        cur = conn.cursor()
        if config_id is not None:
            sql = f"SELECT id, config_id, target_path, objects_count, changes_count, status, error_message, exported_at FROM config_export_log WHERE config_id = {config_id} ORDER BY exported_at DESC LIMIT {limit}"
        else:
            sql = f"SELECT id, config_id, target_path, objects_count, changes_count, status, error_message, exported_at FROM config_export_log ORDER BY exported_at DESC LIMIT {limit}"
        cur.execute(sql)
        rows = cur.fetchall()
        result = []
        for row in rows:
            result.append({'id': row[0], 'config_id': row[1], 'target_path': row[2], 'objects_count': row[3], 'changes_count': row[4], 'status': row[5], 'error_message': row[6], 'exported_at': str(row[7]) if row[7] else None})
        cur.close()
        return result
    except Exception as e:
        return [{'error': str(e)}]
    finally:
        conn.close()
