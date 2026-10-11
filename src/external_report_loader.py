#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Loader for external reports/processing (ERF/EPF) in ckb_1c_configurations."""
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


def _run_psql(query, db="ckb_1c_configurations"):
    """Execute SQL query on ckb_1c_configurations database."""
    # Используем stdin для передачи SQL — это наиболее надёжный способ на Windows
    cmd = [r"C:\Postgres\bin\psql.exe", "-U", "postgres", "-d", db, "-h", "localhost", "-tA"]
    env = dict(os.environ)
    env["PGPASSWORD"] = "Sta090860"
    # Критически важно: PGCLIENTENCODING=UTF8 для корректной передачи русских символов
    env["PGCLIENTENCODING"] = "UTF8"
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    
    # Передаём SQL как UTF-8 байты напрямую через stdin
    # psql с PGCLIENTENCODING=UTF8 корректно обрабатывает UTF-8 из stdin
    stdout, stderr = proc.communicate(input=query.encode("utf-8"))
    
    # Проверяем stderr на наличие ошибок (даже при returncode == 0 — psql может вернуть 0 с ошибкой в stderr)
    if stderr and stderr.strip():
        try:
            err_msg = stderr.decode("cp1251").strip()
        except (UnicodeDecodeError, LookupError):
            try:
                err_msg = stderr.decode("utf-8").strip()
            except Exception:
                err_msg = "Unknown error"
        if "ERROR:" in err_msg or "error:" in err_msg:
            return {"error": f"PSQL error: {err_msg}"}
    
    if proc.returncode != 0:
        try:
            err_msg = stderr.decode("cp1251").strip() if stderr else "Unknown error"
        except (UnicodeDecodeError, LookupError):
            err_msg = "Unknown encoding error"
        return {"error": f"PSQL error (rc={proc.returncode}): {err_msg}"}

    
    if not stdout or not stdout.strip():
        return []
    
    lines = [l for l in stdout.decode("utf-8").split("\n") if l.strip()]
    if not lines:
        return []
    try:
        val = int(lines[0])
        return [{"result": val}]
    except ValueError:
        pass
    headers = [h.strip() for h in lines[0].split("|")]
    rows = []
    for line in lines[1:]:
        s = line.strip()
        if not s or s.startswith("CREATE") or s.startswith("SELECT"):
            continue
        values = [v.strip() for v in line.split("|")]
        row = {}
        for h, v in zip(headers, values):
            if not v:
                row[h] = None
            elif v.lower() == "t":
                row[h] = True
            elif v.lower() == "f":
                row[h] = False
            else:
                try:
                    row[h] = int(v)
                except ValueError:
                    try:
                        row[h] = float(v)
                    except ValueError:
                        row[h] = v
        rows.append(row)
    return rows


def _psql_fields(query, db="ckb_1c_configurations"):
    """Выполнить SQL и вернуть строки как списки текстовых полей.

    psql вызывается в режиме -tA (tuples only), поэтому заголовки столбцов
    не выводятся и штатный парсер _run_psql многоколоночные выборки не разбирает.
    Возвращает список списков либо {"error": ...}.
    """
    cmd = [r"C:\Postgres\bin\psql.exe", "-U", "postgres", "-d", db, "-h", "localhost", "-tA"]
    env = dict(os.environ)
    env["PGPASSWORD"] = "Sta090860"
    # Критически важно: PGCLIENTENCODING=UTF8 для корректной передачи русских символов
    env["PGCLIENTENCODING"] = "UTF8"
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    stdout, stderr = proc.communicate(input=query.encode("utf-8"))

    if stderr and stderr.strip():
        try:
            err_msg = stderr.decode("cp1251").strip()
        except (UnicodeDecodeError, LookupError):
            try:
                err_msg = stderr.decode("utf-8").strip()
            except Exception:
                err_msg = "Unknown error"
        if "ERROR:" in err_msg or "error:" in err_msg:
            return {"error": f"PSQL error: {err_msg}"}

    if proc.returncode != 0:
        try:
            err_msg = stderr.decode("cp1251").strip() if stderr else "Unknown error"
        except (UnicodeDecodeError, LookupError):
            err_msg = "Unknown encoding error"
        return {"error": f"PSQL error (rc={proc.returncode}): {err_msg}"}

    if not stdout or not stdout.strip():
        return []

    rows = []
    for line in stdout.decode("utf-8").split("\n"):
        if not line.strip():
            continue
        rows.append([field.strip() for field in line.split("|")])
    return rows


def _local(tag):
    """Локальное имя тега без префикса пространства имён XML."""
    return tag.split('}')[-1] if isinstance(tag, str) and '}' in tag else (tag or '')


def _find_local(element, name):
    """Поиск первого вложенного элемента по локальному имени (namespace-агностично).

    Нужно потому, что часть метаданных 1С выгружается с префиксами xr:/v8:,
    которые не входят в словарь пространств имён 'md'.
    """
    if element is None:
        return None
    for child in element.iter():
        if _local(child.tag) == name:
            return child
    return None


def _prop_text(element):
    """Текст свойства метаданных: прямой текст или v8:content внутри v8:item."""
    if element is None:
        return ''
    text = element.text
    if text and text.strip():
        return text.strip()
    for sub in element.iter():
        if sub is element:
            continue
        if _local(sub.tag).lower() == 'content' and sub.text and sub.text.strip():
            return sub.text.strip()
    return (text or '').strip()


def _extract_text(element, tag, ns=None):
    """Extract text from XML element by tag name."""
    if ns is None:
        ns = {'md': 'http://v8.1c.ru/8.3/MDClasses'}
    child = element.find(f'.//{ns["md"]}:{tag}', ns) if ns else element.find(f'.//{{http://v8.1c.ru/8.3/MDClasses}}{tag}')
    if child is None:
        return ''
    text = child.text
    if not text:
        for sub in child:
            if 'content' in sub.tag.lower() and sub.text:
                text = sub.text
                break
    return (text or '').strip()


def _parse_child_objects(root, ns):
    """Parse ChildObjects from ExternalReport/ExternalDataProcessor."""
    attributes = []
    tabular_sections = []
    forms = []
    templates = []
    
    child_objects = root.find('.//md:ChildObjects', ns)
    if child_objects is None:
        return attributes, tabular_sections, forms, templates
    
    for obj in child_objects:
        tag_name = obj.tag.replace('{http://v8.1c.ru/8.3/MDClasses}', '')
        
        if tag_name == 'Attribute':
            attr_uuid = obj.get('uuid')
            props_obj = obj.find('.//md:Properties', ns)
            attr_data = {'uuid': attr_uuid}
            if props_obj is not None:
                for prop in props_obj:
                    attr_data[_local(prop.tag)] = _prop_text(prop)
            attributes.append(attr_data)
            
        elif tag_name == 'TabularSection':
            ts_uuid = obj.get('uuid')
            props_obj = obj.find('.//md:Properties', ns)
            ts_data = {'uuid': ts_uuid}
            if props_obj is not None:
                for prop in props_obj:
                    ts_data[_local(prop.tag)] = _prop_text(prop)
            child_objs = obj.find('.//md:ChildObjects', ns)
            columns = []
            if child_objs is not None:
                for col in child_objs:
                    c_name = col.tag.replace('{http://v8.1c.ru/8.3/MDClasses}', '')
                    if c_name == 'Attribute':
                        col_uuid = col.get('uuid')
                        col_props = col.find('.//md:Properties', ns)
                        col_data = {'uuid': col_uuid}
                        if col_props is not None:
                            for cp in col_props:
                                col_data[_local(cp.tag)] = _prop_text(cp)
                        columns.append(col_data)
            ts_data['columns'] = columns
            tabular_sections.append(ts_data)
            
        elif tag_name == 'Form':
            forms.append({'name': obj.text or ''})
        elif tag_name == 'Template':
            templates.append({'name': obj.text or ''})
    
    return attributes, tabular_sections, forms, templates


_EXTERNAL_TABLES = {
    "external_report": {
        "table": "external_report",
        "bsl_column": "report_id",
        "has_children": True,
        "title": "внешний отчёт",
    },
    "external_processing": {
        "table": "external_processing",
        "bsl_column": "processing_id",
        "has_children": False,
        "title": "внешняя обработка",
    },
}


def _external_meta_info(obj_type):
    """Конфигурация таблиц для внешнего отчёта/обработки."""
    return _EXTERNAL_TABLES.get(obj_type, _EXTERNAL_TABLES["external_report"])


def find_external_object(uuid_val, obj_type="external_report"):
    """Найти ранее загруженный внешний отчёт/обработку по UUID.

    Возвращает dict с id/name/created_at и счётчиками связанных данных,
    либо None, если записи (или самого UUID) нет. Ошибки БД дубликатом не
    считаются: возвращается None, и дальнейший INSERT сам сообщит о реальной
    проблеме (например, о duplicate key).
    """
    if not uuid_val:
        return None

    info = _external_meta_info(obj_type)
    table = info["table"]
    bsl_column = info["bsl_column"]

    columns = [
        "t.id",
        "REPLACE(COALESCE(t.name, ''), '|', ' ')",
        "COALESCE(t.uuid::text, '')",
        "COALESCE(t.created_at::text, '')",
        f"(SELECT COUNT(*) FROM bsl_modules b WHERE b.{bsl_column} = t.id)",
    ]
    keys = ["id", "name", "uuid", "created_at", "bsl_modules_count"]

    if info["has_children"]:
        for child_table, key in (
            ("attributes", "attributes_count"),
            ("tabular_sections", "tabular_sections_count"),
            ("forms", "forms_count"),
            ("templates", "templates_count"),
        ):
            columns.append(f"(SELECT COUNT(*) FROM {child_table} c WHERE c.parent_uuid = t.uuid)")
            keys.append(key)

    safe_uuid = str(uuid_val).replace("'", "''")
    sql = f"SELECT {', '.join(columns)} FROM {table} t WHERE t.uuid = '{safe_uuid}'::uuid LIMIT 1"

    rows = _psql_fields(sql)
    if isinstance(rows, dict) and "error" in rows:
        return None
    if not rows:
        return None

    values = rows[0]
    int_keys = {"id", "bsl_modules_count", "attributes_count", "tabular_sections_count", "forms_count", "templates_count"}
    found = {}
    for key, value in zip(keys, values):
        if key in int_keys:
            try:
                found[key] = int(value)
            except (TypeError, ValueError):
                found[key] = 0
        else:
            found[key] = value or ""
    found["object_type"] = obj_type
    return found


def delete_external_object(obj_id=None, uuid_val=None, obj_type="external_report"):
    """Удалить внешний отчёт/обработку вместе со связанными BSL-модулями.

    Дочерние таблицы (attributes/forms/templates/tabular_sections) удаляются
    каскадно по FK parent_uuid -> external_report(uuid) ON DELETE CASCADE,
    а bsl_modules чистится явно: FK на bsl_modules.report_id отсутствует.
    """
    info = _external_meta_info(obj_type)
    table = info["table"]
    bsl_column = info["bsl_column"]

    if obj_id is None:
        found = find_external_object(uuid_val, obj_type)
        if not found:
            return {"success": False, "error": f"Объект с UUID {uuid_val} в таблице {table} не найден"}
        obj_id = found["id"]

    try:
        obj_id = int(obj_id)
    except (TypeError, ValueError):
        return {"success": False, "error": f"Некорректный ID объекта: {obj_id}"}

    rows = _psql_fields(f"SELECT t.id, REPLACE(COALESCE(t.name, ''), '|', ' ') FROM {table} t WHERE t.id = {obj_id} LIMIT 1")
    if isinstance(rows, dict) and "error" in rows:
        return {"success": False, "error": rows["error"]}
    if not rows:
        return {"success": False, "error": f"Объект с ID {obj_id} в таблице {table} не найден"}
    obj_name = rows[0][1] if len(rows[0]) > 1 else ""

    bsl_deleted = 0
    count_res = _run_psql(f"SELECT COUNT(*) FROM bsl_modules WHERE {bsl_column} = {obj_id}")
    if isinstance(count_res, list) and count_res and isinstance(count_res[0].get("result"), int):
        bsl_deleted = count_res[0]["result"]
    if bsl_deleted:
        del_res = _run_psql(f"DELETE FROM bsl_modules WHERE {bsl_column} = {obj_id}")
        if isinstance(del_res, dict) and "error" in del_res:
            return {"success": False, "error": f"Не удалось удалить BSL-модули: {del_res['error']}"}

    del_res = _run_psql(f"DELETE FROM {table} WHERE id = {obj_id}")
    if isinstance(del_res, dict) and "error" in del_res:
        return {"success": False, "error": del_res["error"]}

    check = _psql_fields(f"SELECT t.id FROM {table} t WHERE t.id = {obj_id} LIMIT 1")
    if isinstance(check, dict) and "error" in check:
        return {"success": False, "error": check["error"]}
    if check:
        return {"success": False, "error": f"Запись ID={obj_id} осталась в таблице {table} после удаления"}

    return {
        "success": True,
        "id": obj_id,
        "name": obj_name,
        "object_type": obj_type,
        "table": table,
        "bsl_modules_deleted": bsl_deleted,
        "children_cascaded": info["has_children"],
    }


def read_external_meta(source_path):
    """Прочитать UUID, имя и тип внешнего отчёта/обработки из каталога выгрузки."""
    if not os.path.isdir(source_path):
        return {"success": False, "error": f"Folder not found: {source_path}"}

    ext_xml = None
    obj_type = "external_processing"
    for xml_file in Path(source_path).rglob("*.xml"):
        try:
            with open(xml_file, "r", encoding="utf-8-sig") as f:
                content = f.read()
            if "<ExternalDataProcessor " in content or "<ExternalReport " in content:
                ext_xml = str(xml_file)
                if "<ExternalReport " in content:
                    obj_type = "external_report"
                break
        except Exception:
            pass

    if not ext_xml:
        return {"success": False, "error": "External report/processing XML not found"}

    ns = {"md": "http://v8.1c.ru/8.3/MDClasses"}
    root = ET.parse(ext_xml).getroot()
    if obj_type == "external_report":
        tag = root.find(".//md:ExternalReport", ns)
    else:
        tag = root.find(".//md:ExternalDataProcessor", ns)

    uuid_val = ""
    name = ""
    if tag is not None:
        uuid_val = tag.get("uuid") or root.get("uuid") or ""
        properties = tag.find(".//md:Properties", ns)
        if properties is not None:
            for prop in properties:
                if _local(prop.tag) == "Name":
                    name = _prop_text(prop)
                    break
    else:
        uuid_val = root.get("uuid") or ""

    if not name:
        name = Path(ext_xml).stem

    return {"success": True, "uuid": uuid_val, "name": name, "object_type": obj_type, "xml_path": ext_xml}


def register_external_report(source_path, replace=False):
    """Register external report/processing from directory into ckb_1c_configurations."""
    if not os.path.isdir(source_path):
        return {"success": False, "error": f"Folder not found: {source_path}"}
    
    ext_xml = None
    obj_type = "external_processing"
    
    for xml_file in Path(source_path).rglob("*.xml"):
        try:
            with open(xml_file, "r", encoding="utf-8-sig") as f:
                content = f.read()
            if "<ExternalDataProcessor " in content or "<ExternalReport " in content:
                ext_xml = str(xml_file)
                if "<ExternalReport " in content:
                    obj_type = "external_report"
                break
        except Exception:
            pass
    
    if not ext_xml:
        return {"success": False, "error": "External report/processing XML not found"}
    
    tree = ET.parse(ext_xml)
    root = tree.getroot()
    ns = {'md': 'http://v8.1c.ru/8.3/MDClasses'}
    
    report_uuid = root.get('uuid')
    if obj_type == "external_report":
        report_tag = root.find('.//md:ExternalReport', ns)
    else:
        report_tag = root.find('.//md:ExternalDataProcessor', ns)
    
    if report_tag is None:
        return {"success": False, "error": f"Could not find {obj_type} element in XML"}
    
    if not report_uuid:
        report_uuid = report_tag.get('uuid', root.get('uuid'))
    
    properties = report_tag.find('.//md:Properties', ns)
    props = {}
    if properties is not None:
        for prop in properties:
            props[_local(prop.tag)] = _prop_text(prop)
    
    name = props.get('Name', Path(ext_xml).stem)
    synonym = props.get('Synonym', '')
    comment = props.get('Comment', '')

    # Проверка дубликата: объект с таким UUID уже мог быть загружен ранее.
    # Перезагрузка выполняется только по явному подтверждению оператора (replace=True),
    # иначе оператор получает информацию о уже загруженном объекте и ничего не меняется.
    warnings = []
    replaced = None
    existing = find_external_object(report_uuid, obj_type)
    if existing:
        if not replace:
            return {
                "success": False,
                "already_exists": True,
                "existing": existing,
                "error": (
                    f"Внешний {'отчёт' if obj_type == 'external_report' else 'обработка'} с UUID {report_uuid} "
                    f"уже загружен в таблицу '{_external_meta_info(obj_type)['table']}' "
                    f"(ID={existing['id']}, имя='{existing['name']}')"
                ),
            }
        removed = delete_external_object(obj_id=existing["id"], obj_type=obj_type)
        if not removed.get("success"):
            return {"success": False, "error": f"Не удалось удалить ранее загруженный объект: {removed.get('error')}"}
        replaced = {
            "old_id": existing["id"],
            "old_name": existing.get("name", ""),
            "bsl_modules_deleted": removed.get("bsl_modules_deleted", 0),
        }
    
    attributes, tabular_sections, forms, templates = _parse_child_objects(root, ns)
    
    # Helper functions for SQL escaping
    def sql_escape(s):
        return (s or '').replace("'", "''")
    
    def sql_val(s):
        if not s:
            return "NULL"
        return "'" + sql_escape(s) + "'"
    
    # Insert into external_report or external_processing
    if obj_type == "external_report":
        mds = sql_val(props.get("MainDataCompositionSchema", "").split(".")[-1] if props.get("MainDataCompositionSchema") else None)
        df = sql_val(props.get("DefaultForm", "").split(".")[-1] if props.get("DefaultForm") else None)
        af = sql_val(props.get("AuxiliaryForm", "").split(".")[-1] if props.get("AuxiliaryForm") else None)
        dsf = sql_val(props.get("DefaultSettingsForm", "").split(".")[-1] if props.get("DefaultSettingsForm") else None)
        asf = sql_val(props.get("AuxiliarySettingsForm", "").split(".")[-1] if props.get("AuxiliarySettingsForm") else None)
        dvf = sql_val(props.get("DefaultVariantForm", "").split(".")[-1] if props.get("DefaultVariantForm") else None)
        vs = sql_val(props.get("VariantsStorage", "").split(".")[-1] if props.get("VariantsStorage") else None)
        ss = sql_val(props.get("SettingsStorage", "").split(".")[-1] if props.get("SettingsStorage") else None)
        
        # Извлекаем данные из InternalInfo для соответствия схеме БД
        internal_info = root.find('.//md:InternalInfo', ns)
        contained_classid = ''
        contained_objectid = ''
        gen_type_name = ''
        gen_type_category = ''
        gen_type_typeid = ''
        gen_type_valueid = ''
        
        if internal_info is not None:
            # Элементы InternalInfo выгружаются с префиксом xr:, поэтому поиск
            # идёт по локальным именам тегов, а не через пространство имён 'md'.
            contained = _find_local(internal_info, 'ContainedObject')
            if contained is not None:
                contained_classid = _prop_text(_find_local(contained, 'ClassId'))
                contained_objectid = _prop_text(_find_local(contained, 'ObjectId'))
            
            gen_type = _find_local(internal_info, 'GeneratedType')
            if gen_type is not None:
                gen_type_name = gen_type.get('name', '') or ''
                gen_type_category = gen_type.get('category', '') or ''
                gen_type_typeid = _prop_text(_find_local(gen_type, 'TypeId'))
                gen_type_valueid = _prop_text(_find_local(gen_type, 'ValueId'))
        
        # synonym сохраняется как jsonb: заполненный перевод либо пустой объект '{}'
        # (значения передаются через psql в UTF-8, апострофы удваиваются sql_escape)
        if synonym:
            synonym_val = "jsonb_build_object('ru', '" + sql_escape(synonym) + "')"
        else:
            synonym_val = "'{}'::jsonb"
        
        # Формируем UUID-значения (пустые → NULL)
        def uuid_val(v):
            return f"'{v}'::uuid" if v else 'NULL'
        
        sql = (f"INSERT INTO external_report (name, synonym, comment, uuid, "
               f"containedobject_classid, containedobject_objectid, "
               f"generatedtype_name, generatedtype_category, generatedtype_typeid, generatedtype_valueid, "
               f"main_data_composition_schema, default_form, auxiliary_form, "
               f"default_settings_form, auxiliary_settings_form, default_variant_form, "
               f"variants_storage, settings_storage) VALUES ("
               f"'{sql_escape(name)}', ({synonym_val})::jsonb, '{sql_escape(comment)}', "
               f"{uuid_val(report_uuid)}, "
               f"{uuid_val(contained_classid)}, "
               f"{uuid_val(contained_objectid)}, "
               f"'{sql_escape(gen_type_name)}', '{sql_escape(gen_type_category)}', "
               f"{uuid_val(gen_type_typeid)}, "
               f"{uuid_val(gen_type_valueid)}, "
               f"{mds}, {df}, {af}, {dsf}, {asf}, {dvf}, {vs}, {ss}) RETURNING id")
        result = _run_psql(sql)
    else:
        sql = (f"INSERT INTO external_processing (name, synonym, comment, version, uuid, class_id) "
               f"VALUES ('{sql_escape(name)}', '{sql_escape(synonym)}', '{sql_escape(comment)}', "
               f"'1.0.0.0', '{report_uuid}'::uuid, 'e41aff26-25cf-4bb6-b6c1-3f478a75f374') RETURNING id")
        result = _run_psql(sql)
    
    if isinstance(result, dict) and "error" in result:
        return {"success": False, "error": result["error"]}
    
    object_id = 0
    if isinstance(result, list) and len(result) > 0:
        if "result" in result[0]:
            object_id = result[0]["result"]
        elif isinstance(result[0], dict):
            for k, v in result[0].items():
                if isinstance(v, int):
                    object_id = v
                    break
    
    # Fallback: если INSERT не вернул ID (пустой ChildObjects, особенности psql)
    if object_id == 0 or object_id is None:
        try:
            fallback_sql = f"SELECT id FROM external_report WHERE uuid = '{report_uuid}'::uuid"
            fb_result = _run_psql(fallback_sql)
            if fb_result and isinstance(fb_result, list) and len(fb_result) > 0:
                for k, v in fb_result[0].items():
                    if isinstance(v, int):
                        object_id = v
                        break
        except Exception:
            pass
    
    # Второй fallback: если запись не найдена по UUID — берём MAX(id)
    if object_id == 0 or object_id is None:
        try:
            max_sql = "SELECT MAX(id) FROM external_report"
            max_result = _run_psql(max_sql)
            if max_result and isinstance(max_result, list) and len(max_result) > 0:
                for v in max_result[0].values():
                    if v is not None and isinstance(v, int):
                        object_id = v
                        break
        except Exception:
            pass
    
    if object_id == 0 or object_id is None:
        return {"success": False, "error": f"Failed to get object ID from INSERT result: {result}"}
    
    # Insert attributes
    for attr in attributes:
        sql = (f"INSERT INTO report_attributes (report_id, uuid, name, synonym, type, password_mode, fill_checking) "
               f"VALUES ({object_id}, '{attr.get('uuid')}', "
               f"'{sql_escape(attr.get('Name', ''))}', '{sql_escape(attr.get('Synonym') or '')}', "
               f"'{sql_escape(attr.get('Type') or '')}', "
               f"{'false' if attr.get('PasswordMode') == 'true' else 'true'}, "
               f"'{sql_escape(attr.get('FillChecking', 'DontCheck'))}')")
        res = _run_psql(sql)
        if isinstance(res, dict) and "error" in res:
            warnings.append(f"Реквизит '{attr.get('Name', '')}' не вставлен: {res['error']}")
    
    # Insert tabular sections and columns
    tsection_ids = {}
    for ts in tabular_sections:
        sql = (f"INSERT INTO report_tabular_sections (report_id, uuid, name, synonym) "
               f"VALUES ({object_id}, '{ts.get('uuid')}', "
               f"'{sql_escape(ts.get('Name', ''))}', '{sql_escape(ts.get('Synonym') or '')}') RETURNING id")
        ts_result = _run_psql(sql)
        if isinstance(ts_result, dict) and "error" in ts_result:
            warnings.append(f"Табличная часть '{ts.get('Name', '')}' не вставлена: {ts_result['error']}")
        tsection_id = 0
        if isinstance(ts_result, list) and len(ts_result) > 0:
            tsection_id = ts_result[0].get("result", 0)
        tsection_ids[ts.get('Name', '')] = tsection_id
        
        for col in ts.get('columns', []):
            sql = (f"INSERT INTO tabular_section_attributes (tsection_id, uuid, name, synonym, type) "
                   f"VALUES ({tsection_id}, '{col.get('uuid')}', "
                   f"'{sql_escape(col.get('Name', ''))}', '{sql_escape(col.get('Synonym') or '')}', "
                   f"'{sql_escape(col.get('Type') or '')}')")
            col_res = _run_psql(sql)
            if isinstance(col_res, dict) and "error" in col_res:
                warnings.append(f"Колонка ТЧ '{col.get('Name', '')}' не вставлена: {col_res['error']}")
    
    # Insert forms
    base_path = Path(ext_xml).parent / Path(ext_xml).stem
    for form_info in forms:
        form_name = form_info['name']
        form_xml_path = base_path / "Forms" / f"{form_name}.xml"
        
        if not form_xml_path.exists():
            continue
        
        form_tree = ET.parse(str(form_xml_path))
        form_root = form_tree.getroot()
        form_uuid = form_root.get('{http://v8.1c.ru/8.3/MDClasses}uuid') or form_root.attrib.get('uuid', '')
        form_props = form_root.find('.//md:Properties', ns)
        
        fname = ''
        fsynonym = ''
        ftype = 'Managed'
        
        if form_props is not None:
            for prop in form_props:
                p_name = _local(prop.tag)
                p_text = _prop_text(prop)
                if p_name == 'Name':
                    fname = p_text
                elif p_name == 'Synonym':
                    fsynonym = p_text
                elif p_name == 'FormType':
                    ftype = p_text or 'Managed'
        
        module_path = base_path / form_name / "Ext" / "Form" / "Module.bsl"
        module_code = ''
        if module_path.exists():
            with open(module_path, 'r', encoding='utf-8-sig') as f:
                module_code = f.read()[:5000]
        
        sql = (f"INSERT INTO report_forms (report_id, uuid, name, synonym, form_type, xml_file_path, module_code) "
               f"VALUES ({object_id}, '{form_uuid}', '{sql_escape(fname)}', "
               f"'{sql_escape(fsynonym)}', '{ftype}', '{str(form_xml_path).replace(chr(92), chr(47))}', "
               f"'{sql_escape(module_code)}')")
        form_res = _run_psql(sql)
        if isinstance(form_res, dict) and "error" in form_res:
            warnings.append(f"Форма '{fname}' не вставлена: {form_res['error']}")
    
    # Insert templates
    for template_info in templates:
        template_name = template_info['name']
        template_xml_path = base_path / "Templates" / f"{template_name}.xml"
        
        if not template_xml_path.exists():
            continue
        
        template_tree = ET.parse(str(template_xml_path))
        template_root = template_tree.getroot()
        template_uuid = template_root.get('{http://v8.1c.ru/8.3/MDClasses}uuid') or template_root.attrib.get('uuid', '')
        template_props = template_root.find('.//md:Properties', ns)
        
        tname = ''
        tsynonym = ''
        ttype = 'MXL'
        
        if template_props is not None:
            for prop in template_props:
                p_name = _local(prop.tag)
                p_text = _prop_text(prop)
                if p_name == 'Name':
                    tname = p_text
                elif p_name == 'Synonym':
                    tsynonym = p_text
                elif p_name == 'TemplateType':
                    ttype = p_text or 'MXL'
        
        content_path = base_path / template_name / "Ext" / "Template.xml"
        content_path_str = str(content_path).replace(chr(92), chr(47)) if content_path.exists() else None
        
        xml_path_str = str(template_xml_path).replace(chr(92), chr(47))
        
        if content_path_str:
            sql = (f"INSERT INTO report_templates (report_id, uuid, name, synonym, template_type, xml_file_path, content_path) "
                   f"VALUES ({object_id}, '{template_uuid}', '{sql_escape(tname)}', "
                   f"'{sql_escape(tsynonym)}', '{ttype}', '{xml_path_str}', '{sql_escape(content_path_str)}')")
        else:
            sql = (f"INSERT INTO report_templates (report_id, uuid, name, synonym, template_type, xml_file_path) "
                   f"VALUES ({object_id}, '{template_uuid}', '{sql_escape(tname)}', "
                   f"'{sql_escape(tsynonym)}', '{ttype}', '{xml_path_str}')")
        tpl_res = _run_psql(sql)
        if isinstance(tpl_res, dict) and "error" in tpl_res:
            warnings.append(f"Макет '{tname}' не вставлен: {tpl_res['error']}")
    
    # Index BSL modules
    ext_folders = []
    ext_folder = base_path / "Ext"
    if ext_folder.is_dir():
        ext_folders.append(ext_folder)
    
    for form_ext in base_path.rglob("Ext"):
        if form_ext.is_dir():
            parent = form_ext.parent.name
            grandparent = form_ext.parent.parent.name
            if parent == "Forms":
                ext_folders.append(form_ext)
            elif grandparent and grandparent.lower() in ("forms", "template", "шаблон"):
                ext_folders.append(form_ext)
    
    bsl_seen = set()
    bsl_count = 0
    for ef in ext_folders:
        for bsl_file in ef.rglob("*.bsl"):
            if str(bsl_file) in bsl_seen:
                continue
            bsl_seen.add(str(bsl_file))
            rel_path = str(bsl_file.relative_to(Path(source_path))).replace(chr(92), chr(47))
            
            with open(bsl_file, 'r', encoding='utf-8-sig') as bf:
                code_content = bf.read()[:50000]
            
            obj_module_type = 'ObjectModule'
            if '/Form/' in str(bsl_file) or 'Form' in str(bsl_file.parent):
                obj_module_type = 'FormModule'
            
            sql = (f"INSERT INTO bsl_modules (configuration_id, module_name, file_path, code, object_type, object_name, report_id) "
                   f"VALUES (NULL, '{bsl_file.name}', '{rel_path}', '{sql_escape(code_content)}', "
                   f"'{obj_module_type}', '{sql_escape(name)}', {object_id})")
            bsl_res = _run_psql(sql)
            if isinstance(bsl_res, dict) and "error" in bsl_res:
                warnings.append(f"BSL-модуль '{rel_path}' не проиндексирован: {bsl_res['error']}")
                continue
            bsl_count += 1
    
    return {
        "success": True,
        "id": object_id,
        "name": name,
        "object_type": obj_type,
        "uuid": report_uuid,
        "attributes_count": len(attributes),
        "tabular_sections_count": len(tabular_sections),
        "forms_count": len(forms),
        "templates_count": len(templates),
        "bsl_modules_indexed": bsl_count,
        "replaced": replaced,
        "warnings": warnings,
    }

