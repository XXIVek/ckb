#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Loader for external reports/processing (ERF/EPF) in ckb_1c_configurations."""
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from external_db import transaction
from external_meta_parser import parse_external_meta
# Узел V19 (M1–M5, S1–S5): версионность состояний. Единая точка доступа к «текущему» —
# src/current_revision.py: имена витрин, разрешение состава детей манифестом, простановка
# штампа ревизии и сборка самого манифеста. Загрузчик НЕ имеет права писать свой
# max(revision_no) и свой формат ключей: ровно та же причина, по которой фильтр карантина
# держат в src/quarantine.py (сторожит tools/_v19_read_sites.py).
from current_revision import (
    CHANGED_BY_LOAD,
    FIRST_REVISION,
    MANIFEST_KEYS,
    build_children_manifest,
    current_child_count_sql,
    current_view,
    manifest_member_count_sql,
    manifest_missing_sql,
    stamp_revision_rows,
)
# узел V31: провенанс строки — ОТКУДА появилась эта запись и чем подтвердить, что источник
# тот же. Логика (отпечатки, манифест, формулировки, сверка) держится в одном модуле по той
# же причине, по которой там держат словарь тегов карантина: в двух местах тексты разъезжаются.
from external_provenance import (
    ORIGIN_CATALOG,
    collect as collect_provenance,
    columns_of as provenance_columns,
    compare as compare_provenance,
    manifest_of as provenance_manifest_of,
    manifest_from_flat as provenance_manifest_from_flat,
    resolve_origin,
)
from external_subdir_parser import parse_external_subdirs
from external_table_writer import (
    AttributesRowWriter,
    BslModuleRowWriter,
    ExternalProcessingRowWriter,
    ExternalReportRowWriter,
    FormExtRowWriter,
    FormsRowWriter,
    TabularSectionsRowWriter,
    TemplatesRowWriter,
)


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


# Узел V22 (14.10.2026): ОДНА таблица-заголовок на оба вида внешних объектов.
# Ключ словаря — вид (он же parent_type у дочерних строк, он же значение
# external_report.object_kind). Отличаются только заголовок в карточке и то, какие колонки
# заполняет писатель; таблица, колонка связи модулей и наличие дочерних данных — общие:
#   * table = external_report для обоих: у обработки заголовок — строка этой же таблицы,
#     поэтому FK parent_uuid -> external_report(uuid) ON DELETE CASCADE работает и для неё
#     (до V22 реквизит обработки отклонялся constraint attributes_parent_uuid_fkey);
#   * bsl_column = report_id для обоих: колонка processing_id и её FK удалены вместе с
#     таблицей external_processing (в ней было 0 строк, строк bsl_modules с processing_id
#     не было);
#   * has_children = True для обоих: attributes/tabular_sections/forms/form_ext/templates
#     универсальны и читаются по parent_uuid.
_EXTERNAL_TABLES = {
    "external_report": {
        "table": "external_report",
        "bsl_column": "report_id",
        "has_children": True,
        "title": "внешний отчёт",
    },
    "external_processing": {
        "table": "external_report",
        "bsl_column": "report_id",
        "has_children": True,
        "title": "внешняя обработка",
    },
}


def _external_meta_info(obj_type):
    """Конфигурация таблиц для внешнего отчёта/обработки."""
    return _EXTERNAL_TABLES.get(obj_type, _EXTERNAL_TABLES["external_report"])


def detect_external_object_type(xml_path):
    """Тип внешнего объекта по XML-файлу: '' если не распознан.

    В выгрузке 1С корневой элемент - MetaDataObject, а ExternalReport /
    ExternalDataProcessor является его потомком верхнего уровня, поэтому проверяется
    и имя корневого тега, и имена элементов верхнего уровня.
    """
    try:
        root = ET.parse(str(xml_path)).getroot()
    except Exception:
        return ""
    names = {str(root.tag).split("}")[-1]}
    names.update(str(child.tag).split("}")[-1] for child in root)
    if "ExternalReport" in names:
        return "external_report"
    if "ExternalDataProcessor" in names:
        return "external_processing"
    return ""


def _find_root_object_xml(source_path):
    """V1: найти XML внешнего отчёта/обработки среди файлов КОРНЕВОГО каталога (R1).

    Возвращает (путь, тип) либо (None, None). Признак - элемент ExternalReport /
    ExternalDataProcessor в XML, а не вхождение подстроки: файл конфигурации тоже
    может содержать слово ExternalReport в описаниях.
    """
    try:
        xml_files = sorted([p for p in Path(source_path).glob("*.xml") if p.is_file()],
                           key=lambda p: p.name.lower())
    except OSError:
        return None, None
    for xml_file in xml_files:
        obj_type = detect_external_object_type(xml_file)
        if obj_type:
            return str(xml_file), obj_type
    return None, None


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
    # Узел V19 (M5, S1): карточка описывает ТЕКУЩЕЕ состояние объекта, поэтому строку читают
    # из витрины current_view(), а не из базовой таблицы. Писать здесь свой max(revision_no)
    # нельзя: uuid больше не уникален (уникальна пара uuid, revision_no), и выборка без
    # фильтра ревизий отдала бы произвольную строку цепочки, а не текущую.
    header_view = current_view(table)

    columns = [
        "t.id",
        "REPLACE(COALESCE(t.name, ''), '|', ' ')",
        "COALESCE(t.uuid::text, '')",
        "COALESCE(t.created_at::text, '')",
        # узел V19 (M1, M7): номер текущего состояния и длина всей цепочки. Нужны оба числа:
        # force=True снимает историю целиком (M7), и оператор обязан видеть, сколько ревизий
        # будет снято, ДО подтверждения перезагрузки.
        "COALESCE(t.revision_no::text, '')",
        f"(SELECT COUNT(*) FROM {table} h WHERE h.uuid = t.uuid)",
        # узел V19 (M3, A1): заявлен ли состав детей. «манифеста нет» (NULL — строки,
        # загруженные до V19) и «манифест пуст» (состав снят целиком) — разные утверждения,
        # и карточка обязана различать их, а не выдавать 0 как факт о составе.
        f"COALESCE(({manifest_missing_sql('t.uuid')})::text, 'true')",
        f"COALESCE({manifest_member_count_sql('t.uuid')}, 0)",
        # узел V22: вид строки заголовка. uuid в таблице глобален (UNIQUE), поэтому он не
        # может принадлежать и отчёту, и обработке: если найденная строка другого вида,
        # оператор указал каталог не того объекта — это не дубликат для force=True.
        "COALESCE(t.object_kind, '')",
        # узел V20: привязка к конфигурации заявлена оператором и из выгрузки не
        # восстанавливается, поэтому её читаем здесь же — force=True переносит её на
        # новую строку. Колонка общая для обоих видов (узел V22).
        "COALESCE(t.configuration_id::text, '')",
        # узел V31: провенанс строки — он нужен в карточке дубликата по той же причине, что и
        # привязка: оператор сверяет, ТОТ ли источник грузили раньше, и видит, что при
        # force=True будет записан новый. Манифест читается частями (->>), а не целиком:
        # _psql_fields разделяет колонки символом '|', а JSON пути и причин содержит их.
        "COALESCE(t.origin_kind, '')",
        "COALESCE(t.origin_path, '')",
        "COALESCE(t.origin_sha256, '')",
        "COALESCE(t.origin_recorded_at::text, '')",
        "COALESCE(t.origin_manifest->>'digest_scope', '')",
        "COALESCE(t.origin_manifest->>'file_count', '')",
        "COALESCE(t.origin_manifest->>'total_bytes', '')",
        "COALESCE(t.origin_manifest->>'truncated', '')",
        "COALESCE(t.origin_manifest->>'digest_reason', '')",
        # узел V19 (M5): состав детей считается не «по parent_uuid», а по манифесту текущей
        # ревизии родителя — иначе в счётчик попали бы строки всех ревизий и уже снятые дети.
        current_child_count_sql("bsl_modules", "t.uuid", include_without_manifest=True),
    ]
    keys = ["id", "name", "uuid", "created_at", "revision_no", "history_revisions",
            "manifest_missing", "manifest_members",
            "object_kind", "configuration_id",
            "origin_kind", "origin_path", "origin_sha256", "origin_recorded_at",
            "origin_digest_scope", "origin_file_count", "origin_total_bytes",
            "origin_truncated", "origin_digest_reason",
            "bsl_modules_count"]

    if info["has_children"]:
        for child_table, key in (
            ("attributes", "attributes_count"),
            ("tabular_sections", "tabular_sections_count"),
            ("forms", "forms_count"),
            ("form_ext", "form_ext_count"),
            ("templates", "templates_count"),
        ):
            # include_without_manifest=True — оговорка для снимков до V19: их состав никогда
            # не заявлялся, и ноль от строгого подсчёта по манифесту прочитался бы как
            # «детей нет». Число, полученное так, карточка обязана назвать числом без
            # заявленного состава (src/current_revision.py, manifest_missing_sql).
            columns.append(current_child_count_sql(
                child_table, "t.uuid", include_without_manifest=True))
            keys.append(key)

    safe_uuid = str(uuid_val).replace("'", "''")
    sql = f"SELECT {', '.join(columns)} FROM {header_view} t WHERE t.uuid = '{safe_uuid}'::uuid LIMIT 1"

    rows = _psql_fields(sql)
    if isinstance(rows, dict) and "error" in rows:
        return None
    if not rows:
        return None

    values = rows[0]
    int_keys = {"id", "bsl_modules_count", "attributes_count", "tabular_sections_count",
                "forms_count", "form_ext_count", "templates_count",
                # узел V19: номер текущей ревизии, длина цепочки и число заявленных членов
                # состава — числа, а не текст; пустое значение читается нулём.
                "revision_no", "history_revisions", "manifest_members"}
    found = {}
    for key, value in zip(keys, values):
        if key in int_keys:
            try:
                found[key] = int(value)
            except (TypeError, ValueError):
                found[key] = 0
        else:
            found[key] = value or ""
    # узел V20: пустая привязка — это None, а не 0. Различать «оператор ничего не заявлял»
    # (NULL) и конкретный id строки заголовка критично: 0 в configurations не бывает.
    try:
        found["configuration_id"] = int(found.get("configuration_id") or 0) or None
    except (TypeError, ValueError):
        found["configuration_id"] = None
    # узел V19 (M3, A1): «манифеста нет» (NULL — строки, загруженные до V19) и «манифест
    # пуст» (состав снят целиком) — разные состояния, и числом членов это не разрешается:
    # у отсутствующего манифеста members = 0 ровно как у пустого. Различие отдаёт отдельный
    # флаг, посчитанный src/current_revision.py::manifest_missing_sql.
    found["manifest_missing"] = (
        str(found.get("manifest_missing") or "true").strip().lower() != "false"
    )
    # узел V31: манифест строки собирается из плоских полей самим модулем провенанса —
    # форма манифеста ({digest_scope, file_count, ...}) принадлежит ему, и читатели
    # (describe_lines, compare) работают с одной структурой. Пустой dict = манифеста нет,
    # что отличается от «манифест есть, но без отпечатка» (у такого digest_reason заполнен).
    found["origin_manifest"] = provenance_manifest_from_flat(found)
    found["object_type"] = obj_type
    # узел V22: одна таблица-заголовок на оба вида, а uuid уникален глобально. Строка
    # другого вида с тем же uuid — конфликт каталогов, а не дубликат: force=True снял бы
    # чужой объект. Случай называется отдельно и не ведёт себя как перезагрузка.
    found_kind = found.get("object_kind") or ""
    found["kind_mismatch"] = bool(found_kind and found_kind != obj_type)
    return found


def delete_external_object(obj_id=None, uuid_val=None, obj_type="external_report"):
    """Удалить внешний отчёт/обработку вместе со всеми связанными данными (V13, V19).

    Узел V19 (инвариант 6 принятой модели): внешний ключ `parent_uuid ->
    external_report(uuid)` из схемы снят — при двух ревизиях одного uuid `uuid` не уникален,
    поэтому каскада больше нет ни у одной дочерней таблицы. Очистка обязанна быть явной и
    обязана снимать строки ВСЕХ ревизий: удаляется объект, а не одна его ревизия (M7 —
    загрузка каталога историю сбрасывает, удаление — тем более). После удаления по любой
    границе сирот по всем `revision_no` быть не должно.

    Порядок снятия:
      * bsl_modules - явный DELETE по report_id И по parent_uuid (колонки processing_id нет,
        узел V22; FK на bsl_modules.report_id в схеме не было никогда);
      * form_ext -> forms (у form_ext есть FK form_id -> forms(id) ON DELETE CASCADE, но
        явный порядок держит счётчики честными), затем templates, attributes,
        tabular_sections — все по parent_uuid, то есть все ревизии;
      * строки заголовка — по uuid, а не по id: одна цепочка состояний одного объекта
        снимается целиком, иначе следующая загрузка каталога упала бы на
        `UNIQUE (uuid, revision_no)`.
    Строки обогащения (config_*) FK не имеют — снимаются явно по parent_uuid (узел V17).
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

    rows = _psql_fields(f"SELECT t.id, REPLACE(COALESCE(t.name, ''), '|', ' '), COALESCE(t.uuid::text, '') FROM {table} t WHERE t.id = {obj_id} LIMIT 1")
    if isinstance(rows, dict) and "error" in rows:
        return {"success": False, "error": rows["error"]}
    if not rows:
        return {"success": False, "error": f"Объект с ID {obj_id} в таблице {table} не найден"}
    obj_name = rows[0][1] if len(rows[0]) > 1 else ""
    obj_uuid = rows[0][2] if len(rows[0]) > 2 else ""
    # V13: модули могут быть привязаны и к ID объекта (report_id), и к его UUID
    # (parent_uuid) - удаляем по обоим основаниям, сирот не остаётся.
    by_parent = f" OR parent_uuid = '{obj_uuid}'::uuid" if obj_uuid else ""

    bsl_deleted = 0
    count_res = _run_psql(f"SELECT COUNT(*) FROM bsl_modules WHERE {bsl_column} = {obj_id}{by_parent}")
    if isinstance(count_res, list) and count_res and isinstance(count_res[0].get("result"), int):
        bsl_deleted = count_res[0]["result"]
    if bsl_deleted:
        del_res = _run_psql(f"DELETE FROM bsl_modules WHERE {bsl_column} = {obj_id}{by_parent}")
        if isinstance(del_res, dict) and "error" in del_res:
            return {"success": False, "error": f"Не удалось удалить BSL-модули: {del_res['error']}"}

    # V13/V19: формы, их содержимое, макеты, реквизиты и табличные части снимаем ЯВНО и в
    # правильном порядке: form_ext -> forms (FK form_id -> forms(id) остаётся), затем
    # templates, attributes, tabular_sections. Узел V19: FK parent_uuid ->
    # external_report(uuid) снят, каскада нет ни у одной из этих таблиц, поэтому молчаливая
    # ставка на каскад оставила бы сирот по всем revision_no (инвариант 6 модели).
    # Условие `parent_uuid = uuid` снимает строки всех ревизий — удаляется объект целиком.
    children_deleted = {}
    if info["has_children"] and obj_uuid:
        for child_table in ("form_ext", "forms", "templates",
                            "attributes", "tabular_sections"):
            counted = _run_psql(f"SELECT COUNT(*) FROM {child_table} WHERE parent_uuid = '{obj_uuid}'::uuid")
            count = counted[0]["result"] if isinstance(counted, list) and counted else 0
            if count:
                gone = _run_psql(f"DELETE FROM {child_table} WHERE parent_uuid = '{obj_uuid}'::uuid")
                if isinstance(gone, dict) and "error" in gone:
                    return {"success": False,
                            "error": f"Не удалось удалить связанные строки {child_table}: {gone['error']}"}
            children_deleted[child_table] = count

    # V17: строки обогащения (config_aliases, config_snippets, config_snippet_dependencies,
    # config_cross_references) НЕ имеют FK на объект выгрузки - каскада нет, удаляем явно по
    # parent_uuid. Зависимости сниппетов формально ушли бы каскадом по FK
    # snippet_id -> config_snippets(id), но у таблицы нет колонки parent_uuid, поэтому они
    # считаются и удаляются через JOIN с config_snippets - иначе карточка удаления была бы
    # неполной, а сироты по parent_uuid не проверялись бы вовсе.
    if obj_uuid:
        counted = _run_psql(
            f"SELECT COUNT(*) FROM config_snippet_dependencies d "
            f"JOIN config_snippets s ON s.id = d.snippet_id "
            f"WHERE s.parent_uuid = '{obj_uuid}'::uuid")
        deps_count = counted[0]["result"] if isinstance(counted, list) and counted else 0
        if deps_count:
            gone = _run_psql(
                f"DELETE FROM config_snippet_dependencies d "
                f"USING config_snippets s WHERE s.id = d.snippet_id "
                f"AND s.parent_uuid = '{obj_uuid}'::uuid")
            if isinstance(gone, dict) and "error" in gone:
                return {"success": False,
                        "error": f"Не удалось удалить зависимости сниппетов: {gone['error']}"}
        children_deleted["config_snippet_dependencies"] = deps_count

        for child_table in ("config_aliases", "config_snippets", "config_cross_references"):
            counted = _run_psql(
                f"SELECT COUNT(*) FROM {child_table} WHERE parent_uuid = '{obj_uuid}'::uuid")
            count = counted[0]["result"] if isinstance(counted, list) and counted else 0
            if count:
                gone = _run_psql(
                    f"DELETE FROM {child_table} WHERE parent_uuid = '{obj_uuid}'::uuid")
                if isinstance(gone, dict) and "error" in gone:
                    return {"success": False,
                            "error": f"Не удалось удалить связанные строки {child_table}: {gone['error']}"}
            children_deleted[child_table] = count

    # Узел V19 (M7, инвариант 6): снимается цепочка состояний объекта ЦЕЛИКОМ, а не одна
    # ревизия: при удалении по id осталась бы история того же uuid, и следующая загрузка
    # каталога упала бы на UNIQUE (uuid, revision_no). Поэтому заголовок удаляется по uuid
    # (все revision_no); по id — только если uuid строки неизвестен (старые снимки без
    # заполненной колонки uuid, что для внешнего объекта невозможно: R3 требует uuid).
    where_header = (f"uuid = '{obj_uuid}'::uuid" if obj_uuid else f"id = {obj_id}")
    del_res = _run_psql(f"DELETE FROM {table} WHERE {where_header}")
    if isinstance(del_res, dict) and "error" in del_res:
        return {"success": False, "error": del_res["error"]}

    check_where = (f"t.uuid = '{obj_uuid}'::uuid" if obj_uuid else f"t.id = {obj_id}")
    check = _psql_fields(f"SELECT t.id FROM {table} t WHERE {check_where} LIMIT 1")
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
        "children_deleted": children_deleted,
        # Узел V19: ключ `children_cascaded` переименован — каскада по parent_uuid в схеме
        # больше нет (внешний ключ снят), поэтому утверждать о каскаде было бы неправдой.
        # Снятые строки перечислены в `children_deleted` по каждой дочерней таблице.
        "children_removed_by_parent_uuid": bool(info["has_children"] and obj_uuid),
    }


def read_external_meta(source_path):
    """Прочитать UUID, имя и тип внешнего отчёта/обработки из каталога выгрузки (только корень, R1)."""
    if not os.path.isdir(str(source_path)):
        return {"success": False, "error": f"Каталог не найден: {source_path}"}

    ext_xml, obj_type = _find_root_object_xml(source_path)
    if not ext_xml:
        return {"success": False,
                "error": "Внешний отчёт или обработка не найдены: в корне каталога нет XML "
                         "с элементом ExternalReport или ExternalDataProcessor"}

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


def register_external_report(source_path, replace=None, force=None, xml_path=None, obj_type=None,
                            origin=None, origin_kind=None):
    """Загрузить внешний отчёт/обработку из каталога выгрузки в ckb_1c_configurations.

    Блок-схема варианта 3: docs/config-scenarios/FLOWCHART_1c-configurations-core.md (узлы V1..V11).
    force=True - перезаписать запись с тем же UUID без подтверждения оператора (R4, R5);
    параметр replace сохранён как устаревший псевдоним force.
    xml_path/obj_type передаёт точка входа (src/config_load_router.py); при вызове напрямую
    они определяются по XML в КОРНЕ каталога (R1).
    Разбор и запись: src/external_meta_parser.py (JSON-контракты) и
    src/external_table_writer.py (классы-писатели), одна транзакция на загрузку.
    Дочерние данные: реквизиты и колонки табличных частей - таблица attributes,
    табличные части - tabular_sections (связь column_uuids), формы - forms + form_ext
    (содержимое Forms/<Имя>/Ext/Form.xml и модуль формы), макеты - templates
    (содержимое Templates/<Имя>/Ext/Template.xml), модули объекта и менеджера -
    bsl_modules (модуль формы хранится в form_ext.ext, а не в bsl_modules).
    Пустой или некорректный uuid любого элемента, включая форму и макет, - ошибка
    загрузки (R3), откат. Отсутствующие Forms//Templates//Ext/, двоичная форма или
    двоичный макет - не ошибка, а предупреждение в карточке результата.
    Провенанс (узел V31): origin/origin_kind - путь источника и его вид. Их заявляет
    ВЫЗЫВАЮЩИЙ, а не разбор: загрузчик не может знать, передан ли ему каталог выгрузки,
    названный оператор, или каталог разбора, который ibcmd собрал из .erf (узел V25 - его
    путь после успешной загрузки удаляется). Значение по умолчанию - ('catalog',
    source_path); для двоичного файла мост передаёт путь самого файла и вид 'binary_file'.
    Не удалось вычислить отпечаток - колонки остаются NULL, загрузка продолжается, в
    карточке появляется предупреждение (провенанс описывает источник, а не содержимое).
    """
    if not os.path.isdir(str(source_path)):
        return {"success": False,
                "error": f"Каталог не найден: {source_path}",
                "hint": "Проверьте путь: нужен каталог выгрузки, существующий на диске."}

    force = bool(force) or bool(replace)

    if not xml_path:
        xml_path, detected_type = _find_root_object_xml(source_path)
        obj_type = obj_type or detected_type
    elif not obj_type:
        obj_type = detect_external_object_type(xml_path)

    if not xml_path or not obj_type:
        return {"success": False,
                "error": "Внешний отчёт или внешняя обработка не найдены: в корне каталога нет XML "
                         "с элементом ExternalReport или ExternalDataProcessor",
                "hint": "Каталог не подходит для загрузчика внешних объектов (R1, R6)."}

    ext_xml = str(xml_path)

    # V7/V8/V12: разбор корневого XML в JSON-контракты таблиц external_report,
    # attributes и tabular_sections. Пустой или некорректный uuid корневого элемента
    # либо любого дочернего элемента - явная ошибка загрузки (R3): в БД ничего не пишется.
    parsed = parse_external_meta(ext_xml, obj_type)
    if not parsed.get("success"):
        return parsed

    report_uuid = parsed["uuid"]
    report_row = parsed["report"]
    attribute_rows = parsed["attributes"]
    tabular_section_rows = parsed["tabular_sections"]
    child_counts = parsed.get("counts") or {}

    
    # Имя для карточки и подписи BSL-модулей: из Properties/Name, иначе - имя файла выгрузки.
    name = report_row.get("name") or Path(ext_xml).stem
    report_row["name"] = name


    # V5/V6 (R4, R5): дубликат ищем по UUID. Без force оператор получает карточку уже
    # загруженного объекта, в БД ничего не меняется. Тот же UUID при другой версии - тот же
    # случай: сравнение версий не выполняется, колонки version в таблице нет.
    warnings = []
    # Узел V22: предупреждения разбора корневого XML (пустой ClassId — вид подтверждён только
    # корневым элементом). Отказом это не является, но и молчать загрузчик не должен.
    warnings.extend(parsed.get("warnings") or [])

    # Узел V31: провенанс считаем ДО записи строки (файловая операция вне транзакции) и
    # НЕ из разбора: разбор знает только путь, который ему передали, — а это может быть и
    # каталог выгрузки, названный оператором, и каталог разбора, собранный ibcmd из .erf
    # (узел V25, после успеха он удаляется). Источник заявляет вызывающий: origin/origin_kind.
    # Не вычислен — предупреждение, а не отказ: провенанс описывает источник, а не
    # содержимое объекта, и отсутствие отпечатка не делает загруженные данные неверными.
    origin_path, origin_kind = resolve_origin(origin, origin_kind, source_path)
    provenance = collect_provenance(origin_kind, origin_path)
    if provenance.get("success"):
        warnings.extend(provenance.get("warnings") or [])
        report_row.update(provenance_columns(provenance))
    else:
        warnings.append(
            "Провенанс НЕ записан: "
            + str(provenance.get("reason") or "неизвестная причина")
            + f" (источник: {origin_path or 'не передан'}, вид: {origin_kind or 'не указан'}). "
            "Колонки origin_* остались NULL: содержимое объекта при этом загружено полностью, "
            "провенанс — слепок источника, а не данных объекта."
        )
        # provenance остаётся словарём отказа: compare() по нему назовёт причину, а
        # columns_of() всё равно отдаёт пустые колонки (признак успеха — success=False).

    replaced = None
    existing = find_external_object(report_uuid, obj_type)
    if existing and existing.get("kind_mismatch"):
        # узел V22: uuid занят строкой ДРУГОГО вида. Это не дубликат: force=True снял бы
        # чужой объект вместе со всем его содержимым. Загрузка останавливается, оператор
        # решает сам — указать верный каталог или удалить занятую строку.
        return {
            "success": False,
            "kind_conflict": True,
            "existing": existing,
            "error": (
                f"UUID {report_uuid} занят строкой другого вида: в таблице "
                f"'{_external_meta_info(obj_type)['table']}' уже есть "
                f"{existing.get('object_kind') or 'неизвестного вида'} "
                f"(ID={existing['id']}, имя='{existing['name']}'), а каталог описывает "
                f"{_external_meta_info(obj_type)['title']}"
            ),
            "hint": "Загрузка не выполнена: uuid уникален глобально. Проверьте каталог "
                    "выгрузки либо удалите занятую строку delete_external_report_tool(report_id=...).",
        }
    if existing:
        if not force:
            return {
                "success": False,
                "already_exists": True,
                "existing": existing,
                # узел V31: тот же каталог или другой? ответ даёт отпечаток источника,
                # а не сравнение версий (колонки version в таблице нет).
                "provenance_match": compare_provenance(provenance, existing),
                "error": (
                    f"Внешний объект ({_external_meta_info(obj_type)['title']}) с UUID {report_uuid} "
                    f"уже загружен в таблицу '{_external_meta_info(obj_type)['table']}' "
                    f"(ID={existing['id']}, имя='{existing['name']}')"
                ),
            }
        removed = delete_external_object(obj_id=existing["id"], obj_type=obj_type)
        if not removed.get("success"):
            return {"success": False,
                    "error": f"Не удалось удалить ранее загруженный объект: {removed.get('error')}"}
        replaced = {
            "old_id": existing["id"],
            "old_name": existing.get("name", ""),
            "bsl_modules_deleted": removed.get("bsl_modules_deleted", 0),
            # узел V31: force=True снимает старую строку вместе с её провенансом, новая
            # строка получает провенанс текущего источника. Сравнение нужно оператору ДО
            # подтверждения: оно и есть ответ на вопрос "изменилась ли выгрузка".
            "provenance_match": compare_provenance(provenance, existing),
        }
        # узел V20 (решение оператора 14.10.2026): привязка к конфигурации — данные оператора,
        # а не выгрузки 1С, и обратно из XML они не восстанавливаются. Старая строка снята,
        # поэтому прежнее значение переносится на новую. Автоматического вывода привязки нет.
        if existing.get("configuration_id"):
            report_row["configuration_id"] = existing["configuration_id"]
            replaced["configuration_id"] = existing["configuration_id"]

    # V13: содержимое подкаталогов каталога объекта (Forms/, Templates/, Ext/). Каталог
    # объекта - папка с тем же именем, что и корневой XML (V10). Разбор выполняется ДО
    # открытия транзакции: пустой или некорректный uuid формы/макета - ошибка по R3,
    # в БД не идёт ни одной вставки. Отсутствующие каталоги и двоичные формы/макеты -
    # предупреждения, они загрузку не прерывают.
    base_path = Path(ext_xml).parent / Path(ext_xml).stem
    subdirs = parse_external_subdirs(
        base_path, report_uuid, parent_type=obj_type, object_name=name,
        refs=parsed.get("refs") or {}, source_path=source_path,
    )
    if not subdirs.get("success"):
        return subdirs
    warnings.extend(subdirs.get("warnings") or [])
    form_rows = subdirs["forms"]
    form_ext_rows = subdirs["form_ext"]
    template_rows = subdirs["templates"]
    bsl_rows = subdirs["bsl_modules"]

    # Узел V19 (M1, M3, M7): заголовок и все его дети одной загрузки пишутся ОДНОЙ ревизией.
    # Штамп (revision_no, changed_at, changed_by) у всей цепочки состояния общий: состояние
    # описывается моментом, когда оно появилось, а не моментом вставки каждой строки, поэтому
    # changed_at считается один раз и передаётся всем спискам тем же значением.
    # Явная загрузка каталога историю сбрасывает (M7): строки прежнего uuid сняты до вставки
    # (delete_external_object снимает цепочку целиком), поэтому первая строка новой цепочки —
    # revision_no = FIRST_REVISION. Продолжить цепочку ревизий может только правка состояния
    # в БД, а не повторная загрузка выгрузки.
    # Манифест состава собирается по контрактам разбора ДО транзакции: загрузчик знает полный
    # состав до первой вставки, и ровно тот же состав он вставит (одна транзакция, иначе —
    # полный откат). Считать состав запросом после вставки означало бы описать состояние тем,
    # что в него попало, и не заметить молча не вставшую строку. Канал — src/current_revision.py,
    # тот же модуль, которым состав потом читают (S1): имена ключей и формат элемента
    # `parent_type|file_path` задаёт он, а не это место.
    revision_no = FIRST_REVISION
    children_manifest = build_children_manifest(
        attribute_rows=attribute_rows,
        tabular_section_rows=tabular_section_rows,
        form_rows=form_rows,
        template_rows=template_rows,
        bsl_rows=bsl_rows,
    )
    report_row["children_manifest"] = children_manifest
    changed_at = stamp_revision_rows([report_row], revision_no=revision_no)
    # form_ext_rows штампуются здесь же, хотя form_id им подставляется внутри транзакции:
    # описание формы относится к ревизии своей формы (uq_form_ext_form_id_revision), другой
    # ревизии у этой загрузки нет.
    for child_rows in (attribute_rows, tabular_section_rows, form_rows,
                       template_rows, bsl_rows, form_ext_rows):
        stamp_revision_rows(child_rows, revision_no=revision_no, changed_at=changed_at)
    manifest_members = {key: len(values or ()) for key, values in children_manifest.items()}

    # V9/V12/V13/V22: основная запись и ВСЕ дочерние данные пишутся ОДНОЙ транзакцией.
    # Не загрузилось - откат: в БД не остаётся ни основной записи, ни дочерних данных.
    # Писатель заголовка выбирается по виду: обе строки идут в одну таблицу external_report,
    # но спецификации колонок у них разные (узел V22), и вид проставляет сам писатель.
    table_writer = ExternalReportRowWriter if obj_type == "external_report" else ExternalProcessingRowWriter
    # Колонка связи модулей одна на оба вида: processing_id удалена узлом V22.
    parent_id_column = _external_meta_info(obj_type)["bsl_column"]
    try:
        with transaction() as cursor:
            object_id = table_writer.insert(cursor, report_row)
            written_attributes = AttributesRowWriter.insert_many(cursor, attribute_rows)
            written_sections = TabularSectionsRowWriter.insert_many(cursor, tabular_section_rows)
            # V13: формы - сначала реестр (forms.id), затем содержимое (form_ext.form_id).
            # Связь строки form_ext с формой строится по uuid формы, а не по индексу списка.
            form_ids = FormsRowWriter.insert_ids(cursor, form_rows)
            form_ids_by_uuid = {
                row.get("uuid"): row_id for row, row_id in zip(form_rows, form_ids) if row_id
            }
            for row in form_ext_rows:
                row["form_id"] = form_ids_by_uuid.get(row.get("form_uuid"))
            written_form_ext = FormExtRowWriter.insert_many(cursor, form_ext_rows)
            written_templates = TemplatesRowWriter.insert_many(cursor, template_rows)
            # V13: модули объекта и менеджера привязываются и к ID объекта (report_id),
            # и к его UUID (parent_uuid): обе колонки нужны для поиска и для очистки.
            for row in bsl_rows:
                row[parent_id_column] = object_id
            written_bsl = BslModuleRowWriter.insert_many(cursor, bsl_rows)
            written_forms = len([row_id for row_id in form_ids if row_id])
    except Exception as exc:
        return {"success": False,
                "error": f"Не удалось сохранить данные объекта в БД: {str(exc).strip()}",
                "hint": "Загрузка прекращена, транзакция откатана: проверьте состав выгрузки "
                        "(реквизиты, табличные части, формы, макеты и модули сохраняются "
                        "вместе с основным объектом)."}

    if not object_id:
        return {"success": False,
                "error": f"Не получен ID записи после вставки в {table_writer.TABLE} (UUID {report_uuid})",
                "hint": "Объект в БД не записан: вставка не выполнена или не возвращён идентификатор."}
    
    # V13: индексация BSL через _run_psql удалена: модули объекта и менеджера
    # пишет тот же транзакционный писатель, что и остальные таблицы, а модуль формы
    # хранится в form_ext.ext. Разбор Forms/, Templates/, Ext/ - выше, каталог объекта
    # (base_path) совпадает с именем корневого XML (V10).

    
    return {
        "success": True,
        "id": object_id,
        "name": name,
        "object_type": obj_type,
        "object_kind": obj_type,
        "table": _external_meta_info(obj_type)["table"],
        "variant_title": _external_meta_info(obj_type)["title"],
        "uuid": report_uuid,
        # Устаревший ключ сохранён для совместимости проверок: то же число, что
        # в bsl_modules_written (модули объекта и менеджера; модуль формы - в form_ext.ext).
        "bsl_modules_indexed": written_bsl,
        "attributes_written": written_attributes,
        "tabular_sections_written": written_sections,
        "forms_written": written_forms,
        "form_ext_written": written_form_ext,
        "templates_written": written_templates,
        "bsl_modules_written": written_bsl,
        # Узел V19 (M1, M3, M7): какая ревизия записана этой загрузкой и сколько членов
        # состава заявлено манифестом. history_revisions здесь = 1 не как догадка: явная
        # загрузка каталога снимает цепочку состояний до вставки (M7), поэтому у новой
        # строки истории быть не может. Члены считаются по собранному манифесту, а не по
        # строкам БД: карточка загрузки описывает то, что в неё вошло, а совпадение манифеста
        # с фактическими строками проверяет tools/check_v19_revisions.py.
        "revision_no": revision_no,
        "manifest_members": manifest_members,
        "history_revisions": 1,
        "child_refs": child_counts,
        # Найдено на диске (до записи в БД): нужно карточке, чтобы объяснить,
        # почему часть данных не сохранилась (нет каталога, двоичная форма, ошибка разбора).
        "child_found": {
            "forms": len(form_rows),
            "form_ext": len(form_ext_rows),
            "templates": len(template_rows),
            "bsl_modules": len(bsl_rows),
        },
        "replaced": replaced,
        # Узел V31: те же колонки, что легли в строку (все NULL = провенанс не записан,
        # причина — в warnings). Формат — словарь колонок: карточка печатает его тем же
        # describe_lines(), что и карточку дубликата, отдельной формы у провенанса нет.
        "origin_columns": provenance_columns(provenance),
        "warnings": warnings,
    }

