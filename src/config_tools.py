#!/usr/bin/env python3
"""Module tools for Configurations DB."""
import os, subprocess, re as _re
from pathlib import Path


def _run_config_psql(query, db="configurations"):
    cmd = [r"C:\Postgres\bin\psql.exe", "-U", "postgres", "-d", db, "-h", "localhost", "-F", "|"]
    env = dict(os.environ); env["PGPASSWORD"] = "Sta090860"; env["PGCLIENTENCODING"] = "UTF8"
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    stdout, stderr = proc.communicate(input=query.encode("utf-8"))
    if proc.returncode != 0: return {"error": f"PSQL error: {stderr.decode('cp1251').strip()}"}
    lines = [l for l in stdout.decode("utf-8").split("\n") if l.strip()]
    filtered = [l for l in lines if not (l.strip().startswith("(") and (l.strip().endswith(" rows") or l.strip().endswith(" row")))]
    lines = filtered
    if len(lines) < 3: return []
    headers = [h.strip() for h in lines[0].split("|")]
    rows = []
    for line in lines[2:]:
        s = line.strip()
        if s.startswith("(") and s.endswith(")"): continue
        values = [v.strip() for v in line.split("|")]
        row = {}
        for h, v in zip(headers, values):
            if not v: row[h] = None
            elif v.lower() == "t": row[h] = True
            elif v.lower() == "f": row[h] = False
            else:
                try: row[h] = int(v)
                except ValueError:
                    try: row[h] = float(v)
                    except ValueError: row[h] = v
        rows.append(row)
    return rows


def get_bsl_modules(config_id, module_name=None):
    """Получить BSL-модули конфигурации с полным кодом."""
    sql = f"SELECT id, module_name, file_path, length(code) as code_len FROM bsl_modules WHERE configuration_id = {config_id}"
    if module_name:
        safe_mod = module_name.replace("'", "''")
        sql += f" AND module_name = '{safe_mod}'"
    sql += " ORDER BY module_name"
    results = _run_config_psql(sql)
    if isinstance(results, dict) and 'error' in results: return f"Ошибка: {results['error']}"
    
    lines = [f"BSL-модули конфигурации ID={config_id} ({len(results)} шт.):"]
    for m in results:
        lines.append(f"  [{m['id']}] {m['module_name']} | файл: {m.get('file_path', '?')} | код: {m.get('code_len', 0)} символов")
    return '\n'.join(lines)


def get_bsl_module_code(config_id, module_name=None):
    """Получить полный код BSL-модуля(ей)."""
    sql = f"SELECT id, module_name, file_path, code FROM bsl_modules WHERE configuration_id = {config_id}"
    if module_name:
        safe_mod = module_name.replace("'", "''")
        sql += f" AND module_name = '{safe_mod}'"
    sql += " ORDER BY module_name"
    results = _run_config_psql(sql)
    if isinstance(results, dict) and 'error' in results: return f"Ошибка: {results['error']}"
    
    if not results: return "BSL-модули не найдены"
    
    output_lines = []
    for m in results:
        code = m.get('code') or ''
        output_lines.append(f"\n{'='*80}")
        output_lines.append(f"МОДУЛЬ: {m['module_name']}")
        output_lines.append(f"Файл: {m.get('file_path', '?')}")
        output_lines.append(f"Размер: {len(code)} символов")
        output_lines.append(f"{'='*80}")
        output_lines.append(code)
    
    return '\n'.join(output_lines)


def read_config_file(config_id, file_path=None):
    """Прочитать XML/JSON файл из каталога конфигурации."""
    results = _run_config_psql(f"SELECT source_path FROM configuration WHERE id = {config_id}")
    if isinstance(results, dict) and 'error' in results: return f"Ошибка: {results['error']}"
    if not results: return "Конфигурация не найдена"
    
    base_path = results[0].get('source_path', '')
    if not base_path or not os.path.isdir(base_path):
        return f"Каталог конфигурации не найден: {base_path}"
    
    # Если file_path указан — ищем файл внутри каталога
    if file_path:
        target = Path(base_path) / file_path
    else:
        # Иначе читаем все XML файлы в корне
        target = Path(base_path)
    
    if not target.exists():
        return f"Файл/каталог не найден: {target}"
    
    if target.is_file() and target.suffix.lower() in ('.xml', '.json'):
        try:
            with open(target, 'r', encoding='utf-8') as f:
                content = f.read()
            return f"Файл: {target}\nРазмер: {len(content)} символов\n\n{content[:50000]}"
        except Exception as e:
            return f"Ошибка чтения файла: {e}"
    
    if target.is_dir():
        files = list(target.rglob('*'))
        lines = [f"Каталог: {target} ({len(files)} файлов):"]
        for f in sorted(files):
            if f.is_file() and f.suffix.lower() in ('.xml', '.json'):
                size = f.stat().st_size
                rel = f.relative_to(target)
                lines.append(f"  [{size:>6} байт] {rel}")
        return '\n'.join(lines)
    
    return f"Неизвестный тип: {target}"


def list_configurations(status=None):
    query = "SELECT id, name, full_name, vendor, version, uuid, source_path, status FROM configuration"
    if status:
        safe_status = status.replace("'", "''")
        query += f" WHERE status = '{safe_status}'"
    query += " ORDER BY created_at DESC"
    results = _run_config_psql(query)
    lines = [f"Найдено {len(results)} конфигураций:\n"]
    for c in results:
        lines.append(f"[ID:{c['id']}] {c['name']} | v{c.get('version', '?')} | status={c['status']}")
        if c.get('source_path'): lines.append(f"  Путь: {c['source_path']}")
    return '\n'.join(lines)


def get_configuration(config_id):
    query = f"SELECT id, name, full_name, vendor, version, compatibility_mode, script_language, uuid, source_path, dump_file, status FROM configuration WHERE id = {config_id}"
    configs = _run_config_psql(query)
    if not configs: return f"Конфигурация с ID {config_id} не найдена"
    c = configs[0]
    lines = [f"[ID:{c['id']}] {c['name']}"]
    for k in ['full_name', 'vendor', 'version', 'compatibility_mode', 'script_language']:
        lines.append(f"{k}: {c.get(k, 'N/A')}")
    lines.append(f"UUID: {c.get('uuid', 'N/A')}")
    if c.get('source_path'): lines.append(f"Путь: {c['source_path']}")
    if c.get('dump_file'): lines.append(f"Дамп: {c['dump_file']}")
    lines.append(f"Статус: {c['status']}")
    return '\n'.join(lines)


def search_config_objects(query, config_id=None):
    q = query.replace("'", "''")
    sql = f"SELECT co.id, co.type, co.name, co.description, c.name as configuration_name FROM configuration_objects co JOIN configuration c ON co.configuration_id = c.id WHERE (co.name ILIKE '%{q}%' OR co.description ILIKE '%{q}%')"
    if config_id: sql += f" AND co.configuration_id = {config_id}"
    sql += " ORDER BY co.type, co.name LIMIT 50"
    results = _run_config_psql(sql)
    if isinstance(results, dict) and 'error' in results: return f"Ошибка: {results['error']}"
    lines = [f"Найдено {len(results)} объектов (поиск '{query}'):"]
    for r in results:
        name = (r.get('name') or '')[:60]; desc = (r.get('description') or '')[:80]
        obj_type = r.get('type', '?'); config_name = r.get('configuration_name', '')
        lines.append(f"  [{obj_type}] {config_name}/{name} - {desc}")
    return '\n'.join(lines)


def get_object_structure(config_id, object_name):
    safe_name = object_name.replace("'", "''")
    sql = f"SELECT co.id, co.type, co.name FROM configuration_objects co WHERE co.configuration_id = {config_id} AND co.name = '{safe_name}'"
    objects = _run_config_psql(sql)
    if not objects: return f"Объект '{object_name}' не найден в конфигурации ID={config_id}"
    obj = objects[0]; obj_id = obj['id']; obj_type = obj['type']
    lines = [f"Структура объекта: {obj.get('name', '')} ({obj_type})"]
    attr_sql = f"SELECT name, type FROM object_attributes WHERE configuration_object_id = {obj_id}"
    attributes = _run_config_psql(attr_sql)
    if isinstance(attributes, dict): return f"Ошибка: {attributes['error']}"
    if attributes:
        lines.append("Реквизиты:")
        for a in attributes: lines.append(f"  - {a['name']} ({a['type']})")
    return '\n'.join(lines)


def list_config_objects(config_id, object_type=None):
    sql = f"SELECT type, name FROM configuration_objects WHERE configuration_id = {config_id}"
    if object_type: sql += " AND type = '" + object_type.replace("'", "''") + "'"
    sql += " ORDER BY type, name LIMIT 200"
    results = _run_config_psql(sql)
    if isinstance(results, dict) and 'error' in results: return f"Ошибка: {results['error']}"
    lines = [f"Объекты конфигурации ID={config_id} ({len(results)} шт.):"]
    for r in results: lines.append(f"  [{r.get('type','')}] {r.get('name','')}")
    return '\n'.join(lines)



def find_config_by_name_uuid(name, uuid_val):
    """Поиск конфигурации по имени и UUID. Возвращает первую запись или None."""
    safe_name = name.replace("'", "''")
    safe_uuid = (uuid_val or '').replace("'", "''")
    sql = f"SELECT id, name, version, vendor, uuid, status FROM configuration WHERE uuid = '{safe_uuid}' LIMIT 1"
    results = _run_config_psql(sql)
    if results and len(results) > 0: return results[0]
    sql = f"SELECT id, name, version, vendor, uuid, status FROM configuration WHERE name = '{safe_name}' LIMIT 1"
    results = _run_config_psql(sql)
    if results and len(results) > 0: return results[0]
    return None


def count_objects_by_config(config_id):
    """Подсчёт количества объектов конфигурации."""
    sql = f"SELECT COUNT(*) as cnt FROM configuration_objects WHERE configuration_id = {config_id}"
    results = _run_config_psql(sql)
    if isinstance(results, dict) and 'error' in results: return 0
    if results: return int(results[0].get('cnt', 0))
    return 0


def delete_objects_by_config(config_id):
    """Удаление всех объектов конфигурации (в правильном порядке)."""
    deleted = {'bsl_modules': 0, 'cross_references': 0, 'configuration_objects': 0}
    sql = f"SELECT COUNT(*) as cnt FROM cross_references WHERE configuration_id = {config_id}"
    res = _run_config_psql(sql)
    if isinstance(res, dict): return {'error': res['error'], 'deleted': deleted}
    count_cr = int(res[0].get('cnt', 0)) if res else 0
    if count_cr > 0:
        _run_config_psql(f"DELETE FROM cross_references WHERE configuration_id = {config_id}")
        deleted['cross_references'] = count_cr
    sql = f"SELECT COUNT(*) as cnt FROM bsl_modules WHERE configuration_id = {config_id}"
    res = _run_config_psql(sql)
    if isinstance(res, dict): return {'error': res['error'], 'deleted': deleted}
    count_bsl = int(res[0].get('cnt', 0)) if res else 0
    if count_bsl > 0:
        _run_config_psql(f"DELETE FROM bsl_modules WHERE configuration_id = {config_id}")
        deleted['bsl_modules'] = count_bsl
    sql = f"SELECT COUNT(*) as cnt FROM configuration_objects WHERE configuration_id = {config_id}"
    res = _run_config_psql(sql)
    if isinstance(res, dict): return {'error': res['error'], 'deleted': deleted}
    count_obj = int(res[0].get('cnt', 0)) if res else 0
    if count_obj > 0:
        _run_config_psql(f"DELETE FROM configuration_objects WHERE configuration_id = {config_id}")
        deleted['configuration_objects'] = count_obj
    return {'success': True, 'deleted': deleted}


def update_configuration_status(config_id, status, source_path=None):
    """Обновить статус и путь к конфигурации."""
    safe_status = status.replace("'", "''")
    sql = f"UPDATE configuration SET status = '{safe_status}', updated_at = now() WHERE id = {config_id}"
    if source_path:
        safe_src = source_path.replace('\\', '\\\\').replace("'", "''")
        sql += f", source_path = '{safe_src}'"
    sql += " RETURNING id"
    result = _run_config_psql(sql)
    return isinstance(result, list) and len(result) > 0


def delete_configuration_full(config_id):
    """Полное удаление конфигурации и всех связанных данных (hard-delete)."""
    deleted = {
        'configuration': 0,
        'cross_references': 0,
        'configuration_aliases': 0,
        'configuration_objects': 0,
        'bsl_modules': 0,
        'enum_values': 0,
        'object_attributes': 0,
        'register_dimensions': 0,
        'register_resources': 0
    }
    
    # 1. Удаляем cross_references по configuration_id (если таблица существует)
    sql = f"SELECT COUNT(*) as cnt FROM cross_references WHERE configuration_id = {config_id}"
    res = _run_config_psql(sql)
    if isinstance(res, dict): return {'error': res['error'], 'deleted': deleted}
    count_cr = int(res[0].get('cnt', 0)) if res else 0
    if count_cr > 0:
        del_sql = f"DELETE FROM cross_references WHERE configuration_id = {config_id}"
        _run_config_psql(del_sql)
        deleted['cross_references'] = count_cr
    
    # 2. Удаляем configuration_aliases (если таблица существует)
    sql = f"SELECT COUNT(*) as cnt FROM configuration_aliases WHERE configuration_id = {config_id}"
    res = _run_config_psql(sql)
    if isinstance(res, dict): return {'error': res['error'], 'deleted': deleted}
    count_ca = int(res[0].get('cnt', 0)) if res else 0
    if count_ca > 0:
        del_sql = f"DELETE FROM configuration_aliases WHERE configuration_id = {config_id}"
        _run_config_psql(del_sql)
        deleted['configuration_aliases'] = count_ca
    
    # 3. Удаляем объекты конфигурации (CASCADE удалит enum_values, bsl_modules, object_attributes и т.д.)
    sql = f"SELECT COUNT(*) as cnt FROM configuration_objects WHERE configuration_id = {config_id}"
    res = _run_config_psql(sql)
    if isinstance(res, dict): return {'error': res['error'], 'deleted': deleted}
    count_obj = int(res[0].get('cnt', 0)) if res else 0
    if count_obj > 0:
        del_sql = f"DELETE FROM configuration_objects WHERE configuration_id = {config_id}"
        _run_config_psql(del_sql)
        deleted['configuration_objects'] = count_obj
    
    # 4. Удаляем запись конфигурации
    sql = f"DELETE FROM configuration WHERE id = {config_id} RETURNING id"
    res = _run_config_psql(sql)
    if isinstance(res, dict): return {'error': res['error'], 'deleted': deleted}
    if res and len(res) > 0:
        deleted['configuration'] = 1
    
    return {'success': True, 'deleted': deleted}
