#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Единая точка входа загрузки каталога 1С: определение варианта и маршрутизация.

Норматив поведения: docs/config-scenarios/FLOWCHART_1c-configurations-core.md
(блок-схема 0, узлы T1..T6; правила R1..R8).

Реализовано:
  * detect_load_variant()  - T1..T6: сканирование только корневого каталога (R1, R6);
  * load_catalog()         - маршрутизация на загрузчик варианта (R2, R7);
  * format_load_result()   - единый формат четырёх исходов (R8).

Узел V32 (17.10.2026): вариант «конфигурация» больше не заглушка — Configuration.xml
разбирается в справочник заголовков `configurations` (src/configuration_meta_parser.py +
src/configuration_loader.py, запись строки — ConfigurationRowWriter). Ни исходов, ни
инструментов при этом не прибавилось: те же четыре исхода, тот же format_load_result,
контракт core остаётся четырьмя инструментами (решение D-B). Вариант «расширение»
остаётся заглушкой. Провенанс (колонки origin_*, узел V31) у строк конфигурации НЕ
ведётся: колонок нет, схему этот узел не менял — границу называет карточка.

Точка входа MCP: server_configurations_core.py::load_1c_catalog_tool
(тонкая обёртка: разбор аргументов -> load_catalog -> format_load_result).
"""
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from external_report_loader import detect_external_object_type, register_external_report
# Узел V32: заголовок конфигурации пишется своим загрузчиком (своя таблица-справочник,
# свои коллизии `name`), но точкой входа остаётся `load_catalog` — отдельного
# MCP-инструмента для конфигураций нет (решение D-B, контракт core остаётся 4).
from configuration_loader import OBJECTS_TABLE, register_configuration
# Узел V31: формулировки провенанса принадлежат модулю провенанса, а не карточке. Карточка
# объекта, карточка дубликата и сводка печатают один и тот же текст по одному описанию —
# по той же причине, по которой словарь тегов карантина держат в одном модуле (узел Q3).
from external_provenance import (
    STATE_RECORDED,
    describe_lines as provenance_describe_lines,
    state_of as provenance_state_of,
    verdict_lines as provenance_verdict_lines,
)

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
# Узел V32: «конфигурация» снята с заглушки — заголовок разбирается из Configuration.xml
# в справочник configurations (src/configuration_loader.py). «Расширение» остаётся
# заглушкой: разбора ConfigurationExtensionPurpose в таблицы config_extensions нет, а
# дочерние таблицы attributes/tabular_sections всё ещё рассчитаны на внешний объект
# (глобальный UNIQUE(uuid), п. 13 правил core).
NOT_IMPLEMENTED_VARIANTS = (VARIANT_EXTENSION,)

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
    elif result.get("name_conflict"):
        # узел V32: `name` в configurations уникален (configurations_name_key) — uuid другой,
        # а имя занято. Отдельный исход, а не «дубликат»: force=True снял бы ЧУЖУЮ
        # конфигурацию (по образцу kind_conflict узла V22).
        result["status"] = "name_conflict"
    elif result.get("kind_conflict"):
        # узел V22: uuid занят строкой другого вида — это не дубликат и не перезагрузка
        result["status"] = "kind_conflict"
    elif result.get("already_exists"):
        result["status"] = "duplicate"
    elif not result.get("status"):
        result["status"] = "error"
    return result


def load_catalog(source_path, force=False, origin=None, origin_kind=None):
    """Единая точка входа загрузки (R2): анализ и загрузка одним вызовом.

    force=True - перезаписать существующую запись с тем же UUID без запроса
    подтверждения (R4, R5).

    Узел V31: origin/origin_kind - путь источника и его вид для провенанса строки. Их
    заявляет вызывающий, а не разбор: разбор видит только каталог, который ему указали, и
    не отличит каталог XML-выгрузки от каталога разбора, собранного ibcmd из .erf (узел V25)
    или обратной сборкой (узлы V29, V18). По умолчанию (вызов от `load_1c_catalog_tool`)
    источником считается сам `source_path` вида `catalog` — см. external_provenance.resolve_origin.

    Узел V32: вариант «конфигурация» идёт своим загрузчиком (таблица-справочник
    `configurations`, а не заголовок внешнего объекта). Провенанс для него НЕ передаётся:
    колонок origin_* у `configurations` нет, и в этом узле их не заводили (решение D-C) —
    карточка называет это границей, а не «не записанным провенансом».
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
            origin=origin,
            origin_kind=origin_kind,
        )
        return _normalize(result, detection)

    if variant == VARIANT_CONFIGURATION:
        # Узел V32: заголовок конфигурации из Configuration.xml. Дочерних таблиц у этого
        # узла нет (объекты метаданных — V18), поэтому загрузчик пишет ровно одну строку
        # справочника, а предупреждения разбора (что в выгрузке есть, а в БД не ляжет)
        # идут в карточку тем же полем `warnings`, что и у внешних объектов.
        result = register_configuration(
            source_path,
            force=bool(force),
            xml_path=detection["xml_path"],
        )
        return _normalize(result, detection)

    if variant in NOT_IMPLEMENTED_VARIANTS:
        return _stub_result(detection)

    return _error(f"Неизвестный вариант загрузки: {variant}")


def _configuration_card(existing):
    """Карточка уже загруженной конфигурации (узел V32).

    Отдельная, а не общая с внешними объектами: у строки `configurations` нет ни вида
    (`object_kind`), ни привязки к конфигурации (она и есть конфигурация), ни провенанса
    (колонок `origin_*` нет, решение D-C). Зато есть то, чего нет у внешних объектов:
    число привязанных внешних объектов и число строк с тем же uuid — `uuid` в этой таблице
    уникальным не является, уникальным является `name`.
    """
    cfg_id = existing.get("id")
    lines = [
        f"  ID существующей записи: {cfg_id}",
        f"  Название: {existing.get('name', '')}",
        f"  UUID: {existing.get('uuid', '')}",
        f"  Версия: {existing.get('version') or 'в выгрузке не указана'}",
        f"  Режим запуска / совместимость: {existing.get('main_mode') or '—'} / "
        f"{existing.get('compatibility_mode') or '—'}",
        f"  Дата загрузки: {existing.get('created_at', '')}",
        f"  BSL-модулей с configuration_id={cfg_id}: {existing.get('bsl_modules_count', 0)} "
        "(у XML-выгрузки конфигурации модулей нет: пары ClassId/ObjectId в InternalInfo корня — "
        "предопределённые ссылки платформы, строками bsl_modules они не являются)",
        f"  Расширений в config_extensions: {existing.get('extensions_count', 0)} "
        "(вариант «расширение» — заглушка, строки заполняет только SQL)",
        f"  Привязано внешних объектов: {existing.get('bound_external_objects', 0)} "
        "(состояния читает config_enrichment_stats_tool без uuid)",
        "  Провенанс: для строк конфигурации НЕ ведётся — колонок origin_* у configurations нет "
        "(узел V31 описывает только заголовки внешних объектов; узел V32 схему не менял).",
        f"  Таблица: {VARIANT_TABLES[VARIANT_CONFIGURATION]}",
    ]
    duplicate_rows = existing.get("duplicate_rows") or 0
    if duplicate_rows > 1:
        # find_configuration отдаёт первую по id строку и число строк с тем же uuid:
        # выборка по uuid обязана быть однозначной, а молчать о дубле заголовка нельзя.
        ids = ", ".join(str(i) for i in (existing.get("duplicate_ids") or []))
        lines.append(
            f"⚠️ В таблице {duplicate_rows} строк с тем же uuid (id: {ids or '—'}): uuid в "
            "configurations не уникален (уникален name) — выборка по uuid дала бы несколько строк."
        )
    return lines


def _existing_card(existing, table):
    """Карточка уже загруженного объекта (узел V5, исход 'дубликат')."""
    if existing.get("row_kind") == "configuration":
        # узел V32: строка справочника конфигураций описывается своей карточкой.
        return _configuration_card(existing)
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
    # узел V31: провенанс строки — второй ответ того же вопроса, что и привязка, но про
    # источник: ОТКУДА и из какого состояния файлов эта строка появилась. В карточке
    # дубликата это и есть ответ на «тот ли источник я держу в руках»: строка могла быть
    # загружена из другого каталога или из двоичного файла.
    lines.extend(provenance_describe_lines(existing, indent="  "))
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
    # Узел V19 (M1, M5): карточка дубликата обязана назвать ревизию, которую увидит
    # последующая работа (это id строки из витрины текущего состояния), и сколько состояний
    # у объекта в истории. Различие «манифеста нет» и «манифест пуст» — не деталь схемы:
    # у строки, загруженной до V19, состав не заявлен, и посчитанные по строкам текущей
    # ревизии числа нельзя выдавать за заявленный состав (иначе 0 прочитался бы как «детей
    # нет»). Флаг и число считает src/current_revision.py — тот же канал, что и витрины.
    revision_no = existing.get("revision_no")
    if revision_no:
        history = existing.get("history_revisions") or revision_no
        if existing.get("manifest_missing"):
            manifest_note = ("манифест состава НЕ записан (строка загружена до узла V19): "
                             "числа детей посчитаны по строкам текущей ревизии, это не "
                             "заявленный состав")
        else:
            manifest_note = (f"манифест состава: {existing.get('manifest_members', 0)} членов")
        lines.append(f"  Ревизия: {revision_no} из {history} состояний; {manifest_note}")
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
            if result.get("variant") == VARIANT_CONFIGURATION:
                # узел V32: снимается строка справочника конфигураций. Вместе с ней снимаются
                # расширения и модули, ссылающиеся на неё (FK объявлены без ON DELETE, поэтому
                # их снимает явный DELETE в _remove_rows), а привязки внешних объектов
                # остаются числами: внешнего ключа нет (узел V20.1), значит они становятся
                # битыми. Число снятых детей берётся из `children_deleted` загрузчика —
                # выдумывать его карточка не вправе. Про битые привязки говорит предупреждение
                # загрузчика (оно же перечисляет объекты), здесь — только счётчики снятия.
                children_deleted = replaced.get("children_deleted") or {}
                lines.append(
                    f"♻️ Удалена предыдущая запись ID={replaced.get('old_id')} "
                    f"(расширений снято: {children_deleted.get('config_extensions', 0)}, "
                    f"BSL-модулей снято: {children_deleted.get('bsl_modules', 0)})"
                )
                # Узел V32: привязки внешних объектов к снятой строке остаются числами
                # configuration_id без строки — внешнего ключа нет (узел V20.1), значит они
                # стали битыми. Карточка обязана это назвать: оператор иначе узнает о битой
                # ссылке только из карточки объекта. Число и имена берём из ответа загрузчика
                # (`bound_external_objects`, `bound_external_object_names`), выдумывать их
                # карточка не вправе.
                bound_objects = int(replaced.get("bound_external_objects") or 0)
                if bound_objects:
                    names = ", ".join(
                        str(name) for name in replaced.get("bound_external_object_names") or []
                    )
                    lines.append(
                        f"⚠️ Привязка к конфигурации станет битой: привязано внешних "
                        f"объектов {bound_objects} ({names}). Перепривяжите их "
                        f"`set_object_configuration_tool(uuid=…, "
                        f"configuration_id={result.get('id')})` или снимите (внешнего ключа нет, "
                        "узел V20.1)"
                    )
                # Провенанса у строки конфигурации нет (решение D-C): вердикт сравнения
                # источника здесь не вычисляется и выдумывать его нельзя.
            else:
                lines.append(
                    f"♻️ Удалена предыдущая запись ID={replaced.get('old_id')} "
                    f"(BSL-модулей удалено: {replaced.get('bsl_modules_deleted', 0)})"
                )
                # узел V20: привязка к конфигурации — данные оператора, а не выгрузки; то, что она
                # перенесена, должно быть видно в карточке перезагрузки.
                if replaced.get("configuration_id"):
                    lines.append(f"   Привязка к конфигурации перенесена: "
                                 f"configuration_id={replaced['configuration_id']}")
                # узел V31: старая строка снята вместе со своим провенансом, новая получила
                # провенанс текущего источника. Вердикт сравнения (его считал загрузчик ДО
                # удаления) остаётся в карточке: это ответ на «изменялась ли выгрузка»,
                # который узел V19 не умеет дать по колонке version (её нет).
                lines.extend(provenance_verdict_lines(replaced.get("provenance_match"), indent="   "))
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
        # Узел V19 (M1, M3, M7): карточка называет ревизию, которую записала эта загрузка, и
        # состав, заявленный манифестом. Это не справка о схеме, а ответ на вопрос оператора
        # «что стало с историей»: force=True снимает цепочку состояний (M7), поэтому строка
        # всегда ревизия 1 — молчать об этом нельзя, иначе ожидалась бы «ревизия 2».
        revision_no = result.get("revision_no")
        if revision_no is not None:
            members = result.get("manifest_members") or {}
            total = sum(int(count or 0) for count in members.values())
            detail = ", ".join(
                f"{kind} {int(members.get(kind) or 0)}" for kind in sorted(members)
            )
            lines.append(
                f"Ревизия: {revision_no} (история прежних состояний снята этой загрузкой — M7); "
                f"манифест состава: {total} членов"
                + (f" ({detail})" if detail else " (состав пуст — детей у объекта нет)")
            )
        # узел V32: конфигурация пишет строку справочника — счётчики детей внешнего
        # объекта к ней не относятся. Вместо них печатаются те части выгрузки, которые в БД
        # НЕ легли. Молчать об этом нельзя: «✅ загружено» без этих строк читается как
        # «конфигурация загружена целиком».
        counts = result.get("counts") or {}
        if result.get("variant") == VARIANT_CONFIGURATION:
            child_counts = counts.get("child_objects") or {}
            if child_counts:
                by_type = ", ".join(
                    f"{tag} {count}" for tag, count in sorted(child_counts.items())
                )
                # Узел V33: фраза «состав конфигурации в БД не сохраняется» после появления
                # configuration_objects стала неверной целиком — различать надо по источнику.
                # `<ChildObjects>` Configuration.xml по-прежнему никуда не раскладывается
                # (таблиц объектов метаданных по ним нет, узел V18), а перечень состава из
                # ConfigDumpInfo.xml пишется в configuration_objects — про него ниже своя
                # строка с фактическими числами.
                lines.append(
                    f"Состав из <ChildObjects> Configuration.xml: объектов "
                    f"{sum(child_counts.values())} — по типам: {by_type}; эти записи в БД не "
                    "раскладываются (таблиц объектов метаданных по ним в схеме нет, узел V18)"
                )
            # Узел V33: что реально легло в configuration_objects. Карточка обязана назвать
            # и индекс: «✅ Загружено» без этой строки читается как «записан только
            # заголовок», хотя загрузчик писал ещё и перечень состава (или не писал — и
            # почему, тоже говорит здесь же).
            if result.get("index_found"):
                index_counts = result.get("index_counts") or {}
                lines.append(
                    f"Индекс состава (ConfigDumpInfo.xml): разобрано записей "
                    f"{index_counts.get('entries_total', 0)}, записано в {OBJECTS_TABLE} "
                    f"{result.get('configuration_objects_written', 0)}; типов "
                    f"{result.get('index_types', 0)}, максимальная глубина "
                    f"{index_counts.get('max_depth', 0)}, ссылок на отсутствующего родителя "
                    f"{index_counts.get('parent_unresolved', 0)}"
                )
            else:
                lines.append(
                    f"Индекс состава (ConfigDumpInfo.xml) в каталоге не найден — "
                    f"{OBJECTS_TABLE} по этой конфигурации не заполнялась (узел V33)"
                )
        if counts.get("properties_total"):
            # Что из Properties не имеет колонки в схеме, называется числом, а не молчанием:
            # «✅ Загружено» без этой строки читается как «свойства сохранены все».
            lines.append(
                f"Свойства Configuration.xml: найдено {counts.get('properties_total', 0)}, "
                f"известных схеме {counts.get('properties_mapped', 0)}, "
                f"без колонки {counts.get('properties_unstored', 0)} (из них с непустым "
                f"значением {len(counts.get('properties_unstored_nonempty') or [])})"
            )
            # Узел V32 ссылка вела на check_configuration_inventory.sql, которого на диске
            # нет: перечень колонок оставался обещанием. Перечень отдаёт сам разбор
            # (`not_filled_columns`), значит печатать надо его, а не указатель вникуда.
            for column, reason in sorted((result.get("not_filled_columns") or {}).items()):
                lines.append(f"   не заполняется: {column} — {reason}")
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
        # узел V31: что легло в колонки origin_* — тем же описанием, что и в карточке
        # дубликата (одна формулировка на оба места). Если провенанс не записан, причину
        # уже называет предупреждение ниже, и вторить ему советом «как записать» в карточке
        # загрузки не нужно: действие там же, что и при отказе.
        origin_columns = result.get("origin_columns") or {}
        if provenance_state_of(origin_columns) == STATE_RECORDED:
            lines.extend(provenance_describe_lines(origin_columns, indent="  "))
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
        is_configuration = result.get("variant") == VARIANT_CONFIGURATION
        lines = [
            "⚠️ Уже загружено — загрузка НЕ выполнена: "
            + ("конфигурация с UUID" if is_configuration else "объект с UUID")
            + f" {existing.get('uuid', result.get('uuid', ''))} уже есть в таблице {table}."
        ]
        lines.extend(_existing_card(existing, table))
        # узел V31: «тот ли это источник, что я держу в руках» — вопрос, который раньше
        # оставался без ответа (колонки version в таблице нет, узел V19). Отвечает
        # сравнение отпечатков, его считает загрузчик ДО отказа; карточка печатает
        # готовый вердикт теми же словами, что и карточка перезагрузки.
        lines.extend(provenance_verdict_lines(result.get("provenance_match")))
        lines.append("")
        lines.append(f"ℹ️ {result.get('error', 'Такой объект уже загружен.')}")
        lines.append(
            "ℹ️ Если версия объекта менялась при том же UUID — это тот же случай (R5)."
        )
        if is_configuration:
            # узел V32: у конфигурации нет ни провенанса (решение D-C), ни инструмента
            # удаления (решение D-B) — прежний текст обещал бы delete_external_report_tool,
            # которого для конфигурации не существует, и молчал бы о её расширениях.
            lines.append(
                f"Подтвердите перезагрузку: load_1c_catalog_tool(source_path=..., force=True) — "
                f"запись ID={existing.get('id')}, её расширения и BSL-модули будут удалены, "
                "конфигурация загрузится заново."
            )
            lines.append(
                "ℹ️ Привязки внешних объектов к этому id (external_report.configuration_id) "
                "после force=True числятся битыми до перепривязки: set_object_configuration_tool "
                "принимает только id существующего заголовка (V20.1)."
            )
            lines.append(
                "ℹ️ Инструмента удаления конфигурации в контракте нет: строку справочника "
                "снимает только SQL валидатора (решение D-B)."
            )
        else:
            lines.append(
                f"Подтвердите перезагрузку: load_1c_catalog_tool(source_path=..., force=True) — "
                f"запись ID={existing.get('id')} и её BSL-модули будут удалены, объект загрузится заново."
            )
            lines.append(
                f"Либо удалите запись отдельно: delete_external_report_tool(source_path=...) или "
                f"delete_external_report_tool(report_id={existing.get('id')})."
            )
        return "\n".join(lines)

    if status == "name_conflict":
        # узел V32: имя конфигурации уникально глобально (configurations_name_key), а дубликат
        # ищется по UUID — значит под другим UUID существует ДРУГАЯ конфигурация с тем же
        # именем. force=True здесь не предлагается: он снял бы чужую запись.
        # загрузчик кладёт конфликтующую строку в общий ключ `existing` (тот же контракт,
        # что у `duplicate` и `kind_conflict`) — читать обязан быть он, а не выдуманный ключ.
        conflict = result.get("existing") or {}
        lines = [f"❌ Не могу загрузить: {result.get('error', 'имя уже занято другой конфигурацией')}"]
        if result.get("hint"):
            lines.append(f"   {result['hint']}")
        if conflict:
            lines.append("   Строка, занявшая имя:")
            lines.extend(_configuration_card(conflict))
        # force=True здесь не предлагается — это уже сказано в hint загрузчика;
        # повторять ту же мысль второй строкой в той же карточке не нужно.
        lines.append("   Действие: загрузите другой каталог, измените <Name> в Configuration.xml "
                     "или снимите занявшую строку (delete_configuration(cfg_id=...)) — и повторите запрос.")
        return "\n".join(lines)

    if status == "not_implemented":
        lines = [f"❌ Не могу загрузить: {result.get('error', 'сценарий не реализован')}"]
        if result.get("hint"):
            lines.append(f"   {result['hint']}")
        lines.append("   Реализованы варианты «внешний отчёт» и «внешняя обработка» (V22), файл "
                     "внешнего объекта (.erf/.epf) — отдельным инструментом (V25), заголовок "
                     "конфигурации — с узла V32 (состав выгрузки не сохраняется). Вариант "
                     "«расширение» остаётся заглушкой (см. раздел 5 норматива загрузки).")
        return "\n".join(lines)

    lines = [f"❌ Не могу загрузить: {result.get('error', 'неизвестная ошибка')}"]
    if result.get("hint"):
        lines.append(f"   {result['hint']}")
    return "\n".join(lines)



# ── узел V25: формат ответа «разбор бинарного файла → загрузка» ──────────────────
#
# Карточка четырёх исходов остаётся карточкой четырёх исходов: раздел разбора добавляется
# ОТДЕЛЬНО, потому что «не удалось сконвертировать» и «загрузчик отказал» — два разных ответа,
# и оператор обязан видеть границу между ними (правило R13, раздел 13.7 норматива).

CONVERSION_HEADER = "─── РАЗБОР БИНАРНОГО ФАЙЛА (ibcmd) ───"


def _conversion_lines(conversion):
    """Строки раздела разбора: чем работали, в каком контексте и что получилось."""
    lines = [CONVERSION_HEADER]
    version = conversion.get("ibcmd_version") or "версия не определена"
    lines.append(f"Инструмент: {conversion.get('ibcmd')} ({version})")
    ib_state = "создана сейчас" if conversion.get("infobase_created") else "переиспользована"
    lines.append(f"Информационная база: {conversion.get('db_path')} ({ib_state})")

    facts = conversion.get("type_names") or {}
    if facts.get("available"):
        lines.append(
            "Типы в разборе: имён cfg: — %s, идентификаторов <v8:TypeId> — %s"
            % (facts.get("cfg_type_names"), facts.get("type_id_elements"))
        )
    else:
        lines.append(f"Типы в разборе: проверить не удалось — {facts.get('reason')}")
    if conversion.get("config_loaded_now"):
        took = (conversion.get("timings") or {}).get("config_load")
        lines.append(f"Конфигурация в ИБ: загружена сейчас ({took}с)")
    if conversion.get("config_note"):
        lines.append("⚠️ " + conversion["config_note"])

    lines.append(
        f"Разобранный XML: {conversion.get('root_xml')}; "
        f"файлов содержимого: {conversion.get('content_files')}"
    )
    # Предупреждения самого разбора (узел V29): пустое содержимое внешнего объекта —
    # штатное состояние, каталог содержимого платформой не создаётся. Молчать об этом
    # нельзя: отсутствие каталога видно и в карточке, и оператор обязан понять причину.
    for warning in conversion.get("warnings") or []:
        lines.append("⚠️ " + warning)
    timings = ", ".join(f"{name} {value}с"
                        for name, value in (conversion.get("timings") or {}).items())
    if timings:
        lines.append("Время: " + timings)
    if conversion.get("layout_removed"):
        lines.append("Каталог разбора: удалён (загрузка выполнена)")
    elif conversion.get("layout_dir"):
        lines.append(f"Каталог разбора сохранён: {conversion['layout_dir']}")
    return lines


def format_binary_load_result(result):
    """Ответ по результату ibcmd_bridge.convert_and_load (узел V25).

    Сначала — итог загрузки (ради него вызов и делался), ниже — чем он обеспечен. Если до
    загрузки дело не дошло, карточка загрузки не печатается: исхода загрузки не было.
    """
    if not isinstance(result, dict):
        return "❌ Не могу загрузить: мост ibcmd вернул некорректный ответ: " + str(result)

    conversion = result.get("conversion") or {}
    body = []
    if result.get("stage") == "load":
        body.append(format_load_result(result))
    else:
        body.append(f"❌ Не могу загрузить: {result.get('error', 'разбор не выполнен')}")
        if result.get("hint"):
            body.append(f"   {result['hint']}")
        # Граница стадии называется словами: при отказе разбора раздела разбора нет (отчёта
        # просто не существует), и без этой строки ответ неотличим от отказа загрузчика.
        # Для стадии `load` границу показывает раздел разбора ниже — он выполнен успешно.
        body.append("Этап отказа: разбор бинарного файла (загрузчик не вызывался)")
    if conversion:
        body.append("")
        body.extend(_conversion_lines(conversion))
    return "\n".join(line for line in body if line is not None)

