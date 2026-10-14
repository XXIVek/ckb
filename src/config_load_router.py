#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Единая точка входа загрузки каталога 1С: определение варианта и маршрутизация.

Норматив поведения: docs/config-scenarios/FLOWCHART_1c-configurations-core.md
(блок-схема 0, узлы T1..T6; правила R1..R8).

Реализовано:
  * detect_load_variant()  - T1..T6: сканирование только корневого каталога (R1, R6);
  * load_catalog()         - маршрутизация на загрузчик варианта (R2, R7);
  * format_load_result()   - единый формат четырёх исходов (R8).

Точка входа MCP: server_configurations_core.py::load_1c_catalog_tool
(тонкая обёртка: разбор аргументов -> load_catalog -> format_load_result).
"""
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from external_report_loader import detect_external_object_type, register_external_report

VARIANT_CONFIGURATION = "configuration"
VARIANT_EXTENSION = "extension"
VARIANT_EXTERNAL_REPORT = "external_report"
VARIANT_EXTERNAL_PROCESSING = "external_processing"

VARIANT_TITLES = {
    VARIANT_CONFIGURATION: "конфигурация",
    VARIANT_EXTENSION: "расширение",
    VARIANT_EXTERNAL_REPORT: "внешний отчёт",
    VARIANT_EXTERNAL_PROCESSING: "внешняя обработка",
}

# Целевые таблицы БД ckb_1c_configurations для каждого варианта.
# Узел V22 (14.10.2026): оба внешних варианта пишут в ОДНУ таблицу-заголовок
# external_report — вид строки различает колонка object_kind. Для конфигурации и
# расширения целевые таблицы остались отдельными: это другой сценарий (не выгрузка
# одного внешнего объекта), и они по-прежнему заглушки.
VARIANT_TABLES = {
    VARIANT_CONFIGURATION: "configurations",
    VARIANT_EXTENSION: "config_extensions",
    VARIANT_EXTERNAL_REPORT: "external_report",
    VARIANT_EXTERNAL_PROCESSING: "external_report",
}

# Варианты, которые пока нечем загрузить (R7 - заглушки).
# Узел V22: «внешняя обработка» снята из заглушек — заголовок и содержимое пишутся теми же
# универсальными таблицами, что и отчёт (отдельный писатель строки заголовка —
# ExternalProcessingRowWriter).
NOT_IMPLEMENTED_VARIANTS = (VARIANT_CONFIGURATION, VARIANT_EXTENSION)

CONFIGURATION_XML_NAME = "configuration.xml"


def _local_name(tag):
    """Локальное имя тега XML без пространства имён."""
    return str(tag).split("}")[-1]


def _root_xml_files(source_path):
    """Файлы *.xml только корневого каталога, без подкаталогов (R1)."""
    try:
        return sorted([p for p in Path(source_path).glob("*.xml") if p.is_file()], key=lambda p: p.name.lower())
    except OSError:
        return []


def _find_configuration_xml(source_path):
    """Файл Configuration.xml в корне каталога (регистр имени не учитывается)."""
    for xml_file in _root_xml_files(source_path):
        if xml_file.name.lower() == CONFIGURATION_XML_NAME:
            return xml_file
    return None


def _configuration_extension_purpose(config_xml):
    """Значение ConfigurationExtensionPurpose из Configuration.xml ('' если не найдено)."""
    try:
        root = ET.parse(str(config_xml)).getroot()
    except Exception:
        return ""
    for element in root.iter():
        if _local_name(element.tag) == "ConfigurationExtensionPurpose":
            return (element.text or "").strip()
    return ""


def _error(reason, hint=""):
    """Ошибка загрузки (исход 'не могу загрузить')."""
    return {"success": False, "status": "error", "error": reason, "hint": hint}


def detect_load_variant(source_path):
    """Узлы T1..T6: определить, какой из четырёх загрузчиков нужен для каталога.

    Возвращает dict:
      успех - {"success": True, "variant", "title", "table", "xml_path"}
      отказ - {"success": False, "status": "error", "error", "hint"}
    Признак маршрута - наличие Configuration.xml в КОРНЕ каталога (R1); внешние объекты
    различаются по элементу ExternalReport / ExternalDataProcessor в XML корневых файлов
    (в выгрузке 1С он является потомком верхнего уровня корневого элемента MetaDataObject).
    Подкаталоги не сканируются.
    """
    if not source_path or not os.path.isdir(str(source_path)):
        return _error(
            f"Каталог не найден: {source_path}",
            "Проверьте путь: нужен каталог выгрузки 1С, существующий на диске.",
        )

    configuration_xml = _find_configuration_xml(source_path)
    if configuration_xml is not None:
        purpose = _configuration_extension_purpose(configuration_xml)
        variant = VARIANT_EXTENSION if purpose else VARIANT_CONFIGURATION
        return {
            "success": True,
            "variant": variant,
            "title": VARIANT_TITLES[variant],
            "table": VARIANT_TABLES[variant],
            "xml_path": str(configuration_xml),
            "extension_purpose": purpose,
        }

    for xml_file in _root_xml_files(source_path):
        obj_type = detect_external_object_type(xml_file)
        if obj_type == "external_report":
            variant = VARIANT_EXTERNAL_REPORT
        elif obj_type == "external_processing":
            variant = VARIANT_EXTERNAL_PROCESSING
        else:
            continue
        return {
            "success": True,
            "variant": variant,
            "title": VARIANT_TITLES[variant],
            "table": VARIANT_TABLES[variant],
            "xml_path": str(xml_file),
        }

    root_files = ", ".join([p.name for p in _root_xml_files(source_path)]) or "XML-файлов в корне нет"
    return _error(
        "Каталог не подходит: в его корне нет ни Configuration.xml, ни XML внешнего отчёта или обработки.",
        f"Просмотрены корневые XML: {root_files}. Подкаталоги не просматриваются (R1).",
    )


def _stub_result(detection):
    """G0 для нереализованного варианта (R7): предсказуемый отказ без записи в БД."""
    title = detection["title"]
    return {
        "success": False,
        "status": "not_implemented",
        "not_implemented": True,
        "variant": detection["variant"],
        "variant_title": title,
        "table": detection["table"],
        "error": f"Сценарий «{title}» ещё не реализован (заглушка).",
        "hint": (
            f"Каталог определён корректно ({title}, целевая таблица {detection['table']}), "
            "но загрузчик этого варианта не реализован; в БД ничего не записано."
        ),
    }


def _normalize(result, detection):
    """Привести ответ загрузчика к единой схеме исходов."""
    result = dict(result or {})
    result.setdefault("variant", detection["variant"])
    result.setdefault("variant_title", detection["title"])
    result.setdefault("table", detection["table"])
    if result.get("success"):
        result["status"] = "reloaded" if result.get("replaced") else "loaded"
    elif result.get("kind_conflict"):
        # узел V22: uuid занят строкой другого вида — это не дубликат и не перезагрузка
        result["status"] = "kind_conflict"
    elif result.get("already_exists"):
        result["status"] = "duplicate"
    elif not result.get("status"):
        result["status"] = "error"
    return result


def load_catalog(source_path, force=False):
    """Единая точка входа загрузки (R2): анализ и загрузка одним вызовом.

    force=True - перезаписать существующую запись с тем же UUID без запроса
    подтверждения (R4, R5).
    """
    detection = detect_load_variant(source_path)
    if not detection.get("success"):
        return detection

    variant = detection["variant"]
    if variant in (VARIANT_EXTERNAL_REPORT, VARIANT_EXTERNAL_PROCESSING):
        # Узел V22: оба внешних варианта идут через один загрузчик — различие только в
        # виде строки заголовка (его проставляет писатель) и в наборе колонок заголовка.
        result = register_external_report(
            source_path,
            force=bool(force),
            xml_path=detection["xml_path"],
            obj_type=variant,
        )
        return _normalize(result, detection)

    if variant in NOT_IMPLEMENTED_VARIANTS:
        return _stub_result(detection)

    return _error(f"Неизвестный вариант загрузки: {variant}")


def _existing_card(existing, table):
    """Карточка уже загруженного объекта (узел V5, исход 'дубликат')."""
    lines = [
        f"  ID существующей записи: {existing.get('id')}",
        f"  Название: {existing.get('name', '')}",
        f"  UUID: {existing.get('uuid', '')}",
        # узел V22: вид строки заголовка (внешний отчёт / внешняя обработка) — то, по чему
        # строку ищут обогащение и сводка; в карточке дубликата он всегда совпадает с
        # запрошенным вариантом (несовпадение — отдельный исход kind_conflict).
        f"  Вид: {existing.get('object_kind', '')}",
        f"  Дата загрузки: {existing.get('created_at', '')}",
        f"  Связанные данные: BSL-модулей {existing.get('bsl_modules_count', 0)}",
    ]
    # узел V20: привязка к конфигурации — данные оператора; показываем её в карточке
    # дубликата, чтобы оператор знал, что при force=True она будет перенесена, а не потеряна.
    if existing.get("configuration_id"):
        lines.append(f"  Привязка к конфигурации: configuration_id={existing['configuration_id']} "
                     f"(заявлена оператором, будет перенесена при force=True)")
    else:
        lines.append("  Привязка к конфигурации: не заявлена (NULL — это не «универсальный»)")
    # V13: все счётчики дочерних данных одной строкой (формы, их описания, макеты).
    parts = [f"{label} {existing[key]}" for key, label in (
        ("attributes_count", "реквизитов"),
        ("tabular_sections_count", "табличных частей"),
        ("forms_count", "форм"),
        ("form_ext_count", "описаний форм"),
        ("templates_count", "макетов"),
    ) if key in existing]
    if parts:
        lines.append("  Дочерние данные: " + ", ".join(parts))
    lines.append(f"  Таблица: {table}")
    return lines


def format_load_result(result):
    """Единый формат ответа точки входа: ровно четыре исхода (R8, раздел 1 норматива)."""
    if not isinstance(result, dict):
        return "❌ Не могу загрузить: загрузчик вернул некорректный ответ.\n   Ответ: " + str(result)

    status = result.get("status") or "error"
    title = result.get("variant_title") or result.get("object_type") or "объект"
    table = result.get("table", "")

    if status in ("loaded", "reloaded"):
        lines = ["♻️ Перезагружено: старая запись удалена, объект загружен заново."
                 if status == "reloaded" else "✅ Загружено."]
        lines.append(f"Тип: {title}" + (f" (таблица {table})" if table else ""))
        lines.append(f"ID: {result.get('id')}")
        lines.append(f"UUID: {result.get('uuid', '')}")
        lines.append(f"Название: {result.get('name', '')}")
        replaced = result.get("replaced")
        if replaced:
            lines.append(
                f"♻️ Удалена предыдущая запись ID={replaced.get('old_id')} "
                f"(BSL-модулей удалено: {replaced.get('bsl_modules_deleted', 0)})"
            )
            # узел V20: привязка к конфигурации — данные оператора, а не выгрузки; то, что она
            # перенесена, должно быть видно в карточке перезагрузки.
            if replaced.get("configuration_id"):
                lines.append(f"   Привязка к конфигурации перенесена: "
                             f"configuration_id={replaced['configuration_id']}")
        # V13: полные счётчики сохранённых дочерних данных (узел V13 норматива).
        written = {
            "attributes": result.get("attributes_written"),
            "tabular_sections": result.get("tabular_sections_written"),
            "forms": result.get("forms_written"),
            "form_ext": result.get("form_ext_written"),
            "templates": result.get("templates_written"),
            "bsl_modules": result.get("bsl_modules_written", result.get("bsl_modules_indexed")),
        }
        if any(value is not None for value in written.values()):
            lines.append(
                "Сохранено: реквизитов {a}, табличных частей {ts}, форм {f}, описаний форм {fe}, "
                "макетов {t}, BSL-модулей {b}".format(
                    a=written["attributes"] or 0,
                    ts=written["tabular_sections"] or 0,
                    f=written["forms"] or 0,
                    fe=written["form_ext"] or 0,
                    t=written["templates"] or 0,
                    b=written["bsl_modules"] or 0,
                )
            )
        # Модуль формы по правилам V13 хранится в form_ext.ext, а не в bsl_modules:
        # если у формы есть модуль, но в bsl_modules он не попал - это не ошибка.
        found = result.get("child_found") or {}
        for key, label in (
            ("forms", "формы"),
            ("form_ext", "описания форм"),
            ("templates", "макеты"),
            ("bsl_modules", "BSL-модули"),
        ):
            found_count = found.get(key) or 0
            saved_count = written.get(key) or 0
            if found_count and saved_count < found_count:
                lines.append(
                    f"ℹ️ {label.capitalize()}: найдено в каталоге {found_count}, "
                    f"сохранено {saved_count} — причину см. в предупреждениях ниже."
                )
        for warning in result.get("warnings") or []:
            lines.append(f"⚠️ {warning}")
        return "\n".join(lines)

    if status == "kind_conflict":
        # узел V22: тот же uuid уже принадлежит строке другого вида. Отдельный исход,
        # а не «дубликат»: force=True в такой ситуации снял бы чужой объект.
        existing = result.get("existing") or {}
        lines = ["❌ Не могу загрузить: " + str(result.get("error", "uuid занят строкой другого вида"))]
        if result.get("hint"):
            lines.append(f"   {result['hint']}")
        lines.extend(_existing_card(existing, table))
        return "\n".join(lines)

    if status == "duplicate":
        existing = result.get("existing") or {}
        lines = [f"⚠️ Уже загружено — загрузка НЕ выполнена: объект с UUID {existing.get('uuid', result.get('uuid', ''))} уже есть в таблице {table}."]
        lines.extend(_existing_card(existing, table))
        lines.append("")
        lines.append(f"ℹ️ {result.get('error', 'Такой объект уже загружен.')}")
        lines.append(
            "ℹ️ Если версия объекта менялась при том же UUID — это тот же случай (R5)."
        )
        lines.append(
            f"Подтвердите перезагрузку: load_1c_catalog_tool(source_path=..., force=True) — "
            f"запись ID={existing.get('id')} и её BSL-модули будут удалены, объект загрузится заново."
        )
        lines.append(
            f"Либо удалите запись отдельно: delete_external_report_tool(source_path=...) или "
            f"delete_external_report_tool(report_id={existing.get('id')})."
        )
        return "\n".join(lines)

    if status == "not_implemented":
        lines = [f"❌ Не могу загрузить: {result.get('error', 'сценарий не реализован')}"]
        if result.get("hint"):
            lines.append(f"   {result['hint']}")
        lines.append("   Реализованы варианты «внешний отчёт» и «внешняя обработка»; "
                     "конфигурация и расширение — заглушки (см. раздел 5 норматива загрузки).")
        return "\n".join(lines)

    lines = [f"❌ Не могу загрузить: {result.get('error', 'неизвестная ошибка')}"]
    if result.get("hint"):
        lines.append(f"   {result['hint']}")
    return "\n".join(lines)


