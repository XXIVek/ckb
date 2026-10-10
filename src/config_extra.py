#!/usr/bin/env python3
import os
from pathlib import Path
import re as _re
from config_tools import (_run_config_psql, find_config_by_name_uuid,
                          delete_objects_by_config, update_configuration_status,
                          delete_configuration_full)



def search_bsl_code(query, config_id=None):
    q = query.replace("'", "''")
    sql = f"SELECT bm.module_name, bm.object_type, LEFT(bm.code, 200) as code_preview FROM bsl_modules bm JOIN configuration c ON bm.configuration_id = c.id WHERE LOWER(bm.code) LIKE '%{q.lower()}%'"
    if config_id: sql += f" AND bm.configuration_id = {config_id}"
    sql += " ORDER BY bm.module_name LIMIT 30"
    results = _run_config_psql(sql)
    if isinstance(results, dict) and 'error' in results: return f"Ошибка: {results['error']}"
    lines = [f"Найдено {len(results)} модулей (поиск '{query}'):"]
    for r in results:
        module = (r.get('module_name') or '')[:40]; preview = (r.get('code_preview') or '')[:80]
        lines.append(f"  [{(r.get('object_type',''))}] {module}")
        if preview: lines.append(f"    {preview}")
    return '\n'.join(lines)


def get_enum_values(config_id, enum_name=None):
    sql = f"SELECT co.name as enum_name, e.value FROM enum_values e JOIN configuration_objects co ON e.configuration_object_id = co.id WHERE co.configuration_id = {config_id} AND co.type = 'enum'"
    if enum_name: sql += " AND co.name = '" + enum_name.replace("'", "''") + "'"
    sql += " ORDER BY co.name, e.value LIMIT 200"
    results = _run_config_psql(sql)
    if isinstance(results, dict) and 'error' in results: return f"Ошибка: {results['error']}"
    lines = [f"Значения перечислений (конфигурация ID={config_id}):"]
    for r in results: lines.append(f"  - {(r.get('enum_name',''))}: {r.get('value','')}")
    return '\n'.join(lines)


def register_cross_reference(local_doc_element_id=None, local_doc_snippet_id=None, configuration_id=None, target_object_type=None, target_object_name=None, reference_type=None):
    if not local_doc_element_id and not local_doc_snippet_id: return "Ошибка: указать ID"
    if not configuration_id or not target_object_name: return "Ошибка: указать config_id и name"
    srt = (reference_type or "linked_to").replace("'", "''")
    stn = target_object_name.replace("'", "''")
    sql = f"INSERT INTO cross_references (local_doc_element_id, local_doc_snippet_id, configuration_id, target_object_type, target_object_name, cross_reference_type) VALUES ({local_doc_element_id}, {local_doc_snippet_id}, {configuration_id}, '{target_object_type}', '{stn}', '{srt}') RETURNING id"
    result = _run_config_psql(sql, db="local_doc")
    if isinstance(result, dict) and 'error' in result: return f"Ошибка: {result['error']}"
    if result: return f"Связь создана! ID={result[0]['id']}"
    return "Связь создана."


def get_cross_references(local_doc_element_id):
    sql = f"SELECT cr.id, c.name as config_name, cr.target_object_type, cr.target_object_name FROM cross_references cr JOIN configuration c ON cr.configuration_id = c.id WHERE cr.local_doc_element_id = {local_doc_element_id} ORDER BY cr.id DESC"
    results = _run_config_psql(sql, db="local_doc")
    if isinstance(results, dict) and 'error' in results: return f"Ошибка: {results['error']}"
    lines = [f"Связи элемента ID={local_doc_element_id} ({len(results)} шт.):"]
    for r in results: lines.append(f"  [{r.get('config_name','')}] -> [{r.get('target_object_type','')}] {r.get('target_object_name','')}")
    return '\n'.join(lines)



    sql = f"SELECT source_path FROM configuration WHERE id = {config_id}"
    configs = _run_config_psql(sql)
    if not configs: return {"success": False, "error": f"Конфигурация ID={config_id} не найдена"}
    base_path = Path(configs[0].get('source_path', ''))
    if not base_path.is_dir(): return {"success": False, "error": f"Путь не найден: {base_path}"}
    type_map = {'catalog': ('Catalogs', 'catalog'), 'document': ('Documents', 'document'), 'register_info': ('InformationRegisters', 'register_info'), 'register_accumulation': ('AccumulationRegisters', 'register_accumulation'), 'enum': ('Enums', 'enum'), 'constant': ('Constants', 'constant'), 'plan_accounts': ('ChartsOfAccounts', 'plan_accounts')}
    total, success_count, failed_count, errors = 0, 0, 0, []
    if type_filter:
        tf = type_filter.lower()
        if tf not in type_map: return {"success": False, "error": f"Неизвестный тип: {type_filter}"}
        types_to_process = [tf]
    else: types_to_process = list(type_map.keys())
    for obj_type in types_to_process:
        folder_name, db_type = type_map[obj_type]
        folder_path = base_path / folder_name
        if not folder_path.is_dir(): continue
        for xml_file in sorted(folder_path.rglob('*.xml')):
            parts = xml_file.parts
            if len(parts) < 4 or xml_file.name != f"{xml_file.stem}.xml": continue
            obj_name = xml_file.stem; safe_name = obj_name.replace("'", "''")
            description = ""
            try:
                with open(xml_file, 'r', encoding='utf-8') as f: content_xml = f.read()
                m = _re.search(r'<Description[^>]*>([^<]+)</Description>', content_xml)
                if m: description = m.group(1).strip().replace("'", "''")
            except Exception: pass
            ins_sql = f"INSERT INTO configuration_objects (configuration_id, type, name, description) VALUES ({config_id}, '{db_type}', '{safe_name}', '{description}') ON CONFLICT (configuration_id, type, name) DO NOTHING"
            res = _run_config_psql(ins_sql)
            if isinstance(res, dict) and 'error' in res: errors.append(f"{obj_name}: {res['error']}"); failed_count += 1
            else: success_count += 1
            total += 1
    return {"success": True, "total": total, "success_count": success_count, "failed_count": failed_count, "errors": errors[:20]}


def analyze_config_load(source_path):
    """
    Быстрый анализ объекта в каталоге + сравнение с БД (без загрузки!).
    Время выполнения: < 1 секунды.
    Определяет тип: configuration / extension / external_processor / external_report
    """
    if not os.path.isdir(source_path):
        return {"success": False, "error": f"Каталог не найден: {source_path}"}
    
    # 1. Читаем Configuration.xml (быстро, ~10мс)
    config_xml = None
    for xml_file in ['Configuration.xml', 'configuration.xml']:
        candidate = Path(source_path) / xml_file
        if candidate.exists():
            config_xml = str(candidate)
            break
    
    # 2. Определяем тип объекта
    obj_type = "unknown"
    
    if config_xml:
        try:
            with open(config_xml, 'r', encoding='utf-8') as f:
                content_xml = f.read()
            if '<ConfigurationExtensionPurpose>' in content_xml:
                obj_type = "extension"
            elif _re.search(r'<Configuration[ \t]+uuid=', content_xml, _re.IGNORECASE):
                obj_type = "configuration"
        except Exception:
            pass
    
    # Если не нашли — ищем внешнюю обработку/отчет
    if obj_type == "unknown":
        for xml_file in Path(source_path).rglob('*.xml'):
            try:
                with open(xml_file, 'r', encoding='utf-8') as f:
                    content_xml = f.read()
                if '<ExternalDataProcessor' in content_xml:
                    obj_type = "external_processor"; break
                if '<ExternalReport' in content_xml:
                    obj_type = "external_report"; break
            except Exception:
                pass
    
    # 3. Парсим XML (если есть Configuration.xml)
    name, full_name, vendor, version, uuid_val = "unknown", "", "", "", ""
    if config_xml:
        try:
            with open(config_xml, 'r', encoding='utf-8') as f:
                content_xml = f.read()
            m = _re.search(r'<Name[^>]*>([^<]+)</Name>', content_xml)
            if m: name = m.group(1).strip()
            m = _re.search(r'<FullName[^>]*>([^<]+)</FullName>', content_xml)
            if m: full_name = m.group(1).strip()
            m = _re.search(r'<Vendor[^>]*>([^<]+)</Vendor>', content_xml)
            if m: vendor = m.group(1).strip()
            m = _re.search(r'<Version[^>]*>([^<]+)</Version>', content_xml)
            if m: version = m.group(1).strip()
            guid_pat = r'<GUID[^>]*>\{([^}]+)\}</GUID>'
            m = _re.search(guid_pat, content_xml, _re.IGNORECASE)
            if m: uuid_val = m.group(1).strip()
        except Exception:
            pass
    
    catalog_info = {
        "name": name, "full_name": full_name, "vendor": vendor,
        "version": version, "uuid": uuid_val,
        "xml_path": config_xml or "", "object_type": obj_type
    }
    
    # 4. Ищем в БД (только для configuration/extension)
    existing = None
    if obj_type in ("configuration", "extension"):
        existing = find_config_by_name_uuid(name, uuid_val)
    
    result = {
        "success": True, "catalog_info": catalog_info,
        "existing_in_db": None, "is_update": False,
        "version_changed": False, "comparison": {},
        "recommendation": "", "warning": None
    }
    
    # 5. Для внешних обработок/отчетов — сразу рекомендация
    if obj_type in ("external_processor", "external_report"):
        label = obj_type == 'external_processor' and 'Внешняя обработка' or 'Внешний отчет'
        result["recommendation"] = (
            f"✅ {label} — не является конфигурацией.\n   Загружается отдельно."
        )
        return result
    
    # 6. Для конфигураций и расширений — сравниваем с БД
    if existing:
        result["existing_in_db"] = existing
        old_version = existing.get('version', '') or ''
        new_version = version or ''
        uuid_match = (uuid_val or '').strip() == (existing.get('uuid') or '').strip()
        
        # Если UUID пустой И имя не совпадает — это НЕ обновление!
        if not uuid_val.strip() and name != existing.get('name', ''):
            result["recommendation"] = (
                f"✅ НОВАЯ конфигурация/расширение (UUID отсутствует в каталоге).\n"
                f"   Имя: {name} ≠ {existing.get('name', '')} из БД.\n   Можно безопасно загружать."
            )
            return result
        
        result["is_update"] = True
        result["version_changed"] = old_version != new_version
        result["comparison"] = {
            "name": {"old": existing.get('name', ''), "new": name, "changed": (existing.get('name') or '') != name},
            "version": {"old": old_version, "new": new_version, "changed": old_version != new_version},
            "vendor": {"old": existing.get('vendor', ''), "new": vendor, "changed": (existing.get('vendor') or '') != vendor},
            "uuid_match": uuid_match
        }
        
        if not uuid_match and uuid_val:
            result["warning"] = "uuid_mismatch"
            result["recommendation"] = (
                f"⚠️ UUID не совпадает! Это может быть ДРУГАЯ конфигурация.\n"
                f"   Старый UUID: {existing.get('uuid', 'N/A')}\n   Новый UUID:  {uuid_val}"
            )
        elif old_version != new_version and old_version:
            result["recommendation"] = (
                f"✅ Обнаружено обновление версии ({old_version} → {new_version}).\n   Можно перезагрузить."
            )
        else:
            result["recommendation"] = (
                f"ℹ️ Конфигурация не изменилась (версия {version or old_version}).\n   Загрузка не требуется."
            )
    else:
        result["recommendation"] = (
            f"✅ НОВАЯ конфигурация/расширение — не найдена в БД.\n   Можно безопасно загружать."
        )
    
    return result



def delete_config(config_id, force=False):
    """
    Удаление конфигурации и всех связанных данных (hard-delete).
    force=True — подтверждение пользователя получено.
    force=False — только показать что будет удалено.
    Возвращает: {'success': True, 'preview': {...}} или {'success': True, 'deleted': {...}}
    """
    # Проверяем существование конфигурации
    sql = f"SELECT id, name, version, status FROM configuration WHERE id = {config_id}"
    config = _run_config_psql(sql)
    
    if not config:
        return {"success": False, "error": f"Конфигурация с ID {config_id} не найдена"}
    
    cfg = config[0]
    
    # Считаем что будет удалено
    sql_obj = f"SELECT COUNT(*) as cnt FROM configuration_objects WHERE configuration_id = {config_id}"
    res = _run_config_psql(sql_obj)
    obj_count = int(res[0].get('cnt', 0)) if res else 0
    
    sql_bsl = f"SELECT COUNT(*) as cnt FROM bsl_modules WHERE configuration_id = {config_id}"
    res = _run_config_psql(sql_bsl)
    bsl_count = int(res[0].get('cnt', 0)) if res else 0
    
    sql_cr = f"SELECT COUNT(*) as cnt FROM cross_references WHERE configuration_id = {config_id}"
    res = _run_config_psql(sql_cr)
    cr_count = int(res[0].get('cnt', 0)) if res else 0
    
    preview = {
        "id": cfg['id'],
        "name": cfg.get('name', ''),
        "version": cfg.get('version', ''),
        "status": cfg.get('status', ''),
        "will_delete": {
            "configuration_objects": obj_count,
            "bsl_modules": bsl_count,
            "cross_references": cr_count,
            "enum_values": "CASCADE",
            "object_attributes": "CASCADE",
            "register_dimensions": "CASCADE",
            "register_resources": "CASCADE"
        },
        "total_objects": obj_count + bsl_count + cr_count
    }
    
    if not force:
        return {"success": True, "preview": preview}
    
    # Удаление
    result = delete_configuration_full(config_id)
    
    if isinstance(result, dict) and 'error' in result:
        return {"success": False, "error": result['error']}
    
    deleted = result.get('deleted', {})
    total_deleted = sum(deleted.values())
    
    preview["was_deleted"] = deleted
    preview["total_deleted"] = total_deleted
    
    return {"success": True, "deleted_result": preview}


def register_configuration(source_path, dump_file=None):
    """Регистрация или обновление конфигурации из папки выгрузки.
    Автоматически определяет object_type (configuration/extension)."""
    if not os.path.isdir(source_path): return {"success": False, "error": f"Папка не найдена: {source_path}"}
    
    # Определяем тип объекта
    obj_type = "configuration"
    config_xml = None
    for xml_file in ['Configuration.xml', 'configuration.xml']:
        candidate = Path(source_path) / xml_file
        if candidate.exists(): 
            config_xml = str(candidate); break
    
    name, full_name, vendor, version, uuid_val = "unknown", "", "", "", ""
    if config_xml:
        try:
            with open(config_xml, 'r', encoding='utf-8') as f: content_xml = f.read()
            m = _re.search(r'<Name[^>]*>([^<]+)</Name>', content_xml)
            if m: name = m.group(1).strip()
            m = _re.search(r'<FullName[^>]*>([^<]+)</FullName>', content_xml)
            if m: full_name = m.group(1).strip()
            m = _re.search(r'<Vendor[^>]*>([^<]+)</Vendor>', content_xml)
            if m: vendor = m.group(1).strip()
            m = _re.search(r'<Version[^>]*>([^<]+)</Version>', content_xml)
            if m: version = m.group(1).strip()
            guid_pat = r'<GUID[^>]*>\{([^}]+)\}</GUID>'
            m = _re.search(guid_pat, content_xml, _re.IGNORECASE)
            if m: uuid_val = m.group(1).strip()
            # Определяем тип по содержимому XML
            if '<ConfigurationExtensionPurpose>' in content_xml:
                obj_type = "extension"
        except Exception: pass
    
    # Ищем существующую конфигурацию по UUID (ТОЛЬКО если UUID не пустой!)
    existing = None
    if uuid_val.strip():
        existing = find_config_by_name_uuid(name, uuid_val)
    
    safe_name = name.replace("'", "''"); safe_full = full_name.replace("'", "''")
    safe_vendor = vendor.replace("'", "''"); safe_uuid = uuid_val.replace("'", "''")
    src_escaped = source_path.replace(chr(92), chr(92) + chr(92))
    dump_escaped = (dump_file or '').replace("'", "''")
    
    if existing:
        # === ОБНОВЛЕНИЕ СУЩЕСТВУЮЩЕЙ КОНФИГУРАЦИИ ===
        config_id = existing['id']
        del_result = delete_objects_by_config(config_id)
        if isinstance(del_result, dict) and 'error' in del_result:
            return {"success": False, "error": del_result['error']}
        deleted_count = sum(del_result.get('deleted', {}).values())
        update_configuration_status(config_id, 'pending', source_path)
        
        return {
            "success": True, "id": config_id, "name": name, "full_name": full_name,
            "vendor": vendor, "version": version, "uuid": uuid_val,
            "status": "pending", "source_path": source_path,
            "is_update": True, "was_deleted": deleted_count, "object_type": obj_type
        }
    else:
        # === НОВАЯ КОНФИГУРАЦИЯ/РАСШИРЕНИЕ ===
        sql = f"INSERT INTO configuration (name, full_name, vendor, version, uuid, source_path, dump_file, status) VALUES ('{safe_name}', '{safe_full}', '{safe_vendor}', '{version}', '{safe_uuid}', '{src_escaped}', '{dump_escaped}', 'pending') RETURNING id"
        result = _run_config_psql(sql)
        if isinstance(result, dict) and 'error' in result: return {"success": False, "error": result['error']}
        config_id = result[0]['id'] if result else 0
        return {
            "success": True, "id": config_id, "name": name, "full_name": full_name,
            "vendor": vendor, "version": version, "uuid": uuid_val,
            "status": "pending", "source_path": source_path,
            "is_update": False, "object_type": obj_type
        }


def batch_index_from_dump(config_id, type_filter=None):
    """Пакетная индексация объектов из ConfigDumpInfo.xml с сохранением оригинальных XML.
    
    Args:
        config_id: ID конфигурации
        type_filter: фильтр по типу (catalog, document, register_info и т.д.)
        
    Returns:
        Словарь с результатами индексации
    """
    sql = f"SELECT source_path FROM configuration WHERE id = {config_id}"
    configs = _run_config_psql(sql)
    if not configs: return {"success": False, "error": f"Конфигурация ID={config_id} не найдена"}
    base_path = Path(configs[0].get('source_path', ''))
    if not base_path.is_dir(): return {"success": False, "error": f"Путь не найден: {base_path}"}
    
    # Карта соответствия типов объектов (ключ типа в БД -> (папка, тип в БД))
    type_map = {
        'catalog': ('Catalogs', 'catalog'), 
        'document': ('Documents', 'document'), 
        'register_info': ('InformationRegisters', 'register_info'), 
        'register_accumulation': ('AccumulationRegisters', 'register_accumulation'), 
        'enum': ('Enums', 'enum'), 
        'constant': ('Constants', 'constant'), 
        'plan_accounts': ('ChartsOfAccounts', 'plan_accounts')
    }
    
    total, success_count, failed_count, errors = 0, 0, 0, []
    
    if type_filter:
        tf = type_filter.lower()
        if tf not in type_map: return {"success": False, "error": f"Неизвестный тип: {type_filter}"}
        types_to_process = [tf]
    else: 
        types_to_process = list(type_map.keys())
    
    for obj_type in types_to_process:
        folder_name, db_type = type_map[obj_type]
        folder_path = base_path / folder_name
        
        if not folder_path.is_dir(): 
            continue
            
        for xml_file in sorted(folder_path.rglob('*.xml')):
            parts = xml_file.parts
            # Проверяем что это XML объекта (имя файла совпадает с именем без расширения)
            if len(parts) < 4 or xml_file.name != f"{xml_file.stem}.xml": 
                continue
            
            obj_name = xml_file.stem
            safe_name = obj_name.replace("'", "''")
            
            # Вычисляем относительный путь от base_path (используем / для кросс-платформенности)
            rel_path = str(xml_file.relative_to(base_path)).replace('\\', '/')
            safe_rel_path = rel_path.replace("'", "''")
            
            # Читаем XML и описание
            content_xml = ""
            description = ""
            try:
                with open(xml_file, 'r', encoding='utf-8') as f: 
                    content_xml = f.read()
                m = _re.search(r'<Description[^>]*>([^<]+)</Description>', content_xml)
                if m: 
                    description = m.group(1).strip().replace("'", "''")
            except Exception: 
                pass
            
            # Экранируем XML для PostgreSQL (заменяем ' на '')
            escaped_xml = content_xml.replace("'", "''")
            
            # Проверяем существует ли уже объект
            check_sql = f"SELECT id FROM configuration_objects WHERE configuration_id = {config_id} AND type = '{db_type}' AND name = '{safe_name}'"
            existing = _run_config_psql(check_sql)
            
            if existing:
                # Обновляем существующий объект с original_xml
                update_sql = f"""
                    UPDATE configuration_objects 
                    SET description = '{description}', 
                        file_relative_path = '{safe_rel_path}',
                        original_xml = '{escaped_xml}',
                        updated_at = NOW()
                    WHERE id = {existing[0]['id']}
                """
                res = _run_config_psql(update_sql)
            else:
                # Вставляем новый объект с original_xml
                ins_sql = f"""
                    INSERT INTO configuration_objects 
                    (configuration_id, type, name, description, file_relative_path, original_xml, created_at) 
                    VALUES ({config_id}, '{db_type}', '{safe_name}', '{description}', '{safe_rel_path}', 
                            '{escaped_xml}', 
                            NOW()) 
                    ON CONFLICT (configuration_id, type, name) DO NOTHING
                """
                res = _run_config_psql(ins_sql)
            
            if isinstance(res, dict) and 'error' in res: 
                errors.append(f"{obj_name}: {res['error']}")
                failed_count += 1
            else: 
                success_count += 1
            
            total += 1
    
    return {"success": True, "total": total, "success_count": success_count, "failed_count": failed_count, "errors": errors[:20]}

