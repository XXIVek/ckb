#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генерация обогащения (алиасы, сниппеты, зависимости) по уже загруженному объекту.

Узел V17. Контракт: docs/CONFIGURATIONS_ENRICHMENT_PLAN.md (решения E1..E6, разделы 2-6).
Вход - только строки, которые загрузчик уже сохранил (external_report, attributes,
tabular_sections, forms, form_ext, templates, bsl_modules). Ничего из выгрузки на диске
здесь не читается: обогащение невозможно для того, чего нет в БД, и потому не зависит от
узлов V14/V15 напрямую - если ordinary-форма не разложена (items пустой), алиасов FormItem
просто не будет. Это ожидаемое состояние, а не ошибка.

Свойства генерации (раздел 5 плана):
  * идемпотентность: сначала удаляются автоматически созданные строки этого объекта
    (config_aliases с origin='generated', config_snippets с is_verified=false, их
    зависимости), затем всё пишется заново. Ручные алиасы (origin='manual', добавлены
    инструментом add_config_aliases_tool) и ручные связи с local_doc НЕ удаляются;
  * одна транзакция (src/external_db.transaction): либо всё, либо ничего;
  * лимит автоалиасов на сниппет - MAX_AUTO_ALIASES_PER_SNIPPET (10), как в
    local_doc (extract_aliases(..., max_count=10)). Ручные алиасы не ограничены;
  * порог полезности сниппета - MIN_BODY_LINES (5 непустых строк тела объявления),
    иначе из модуля идёт шум («Процедура ПустойМодуль()»).

Пороги и веса - здесь, а не в схеме: DDL (src/ddl_enrichment.sql) описывает только
структуру. target_key в config_aliases вычисляется базой, поэтому в INSERT его нет.
"""
import json
import os
import re
import sys

from psycopg2.extras import execute_values

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from external_db import transaction  # noqa: E402
from enrichment_dcs import card_summary as dcs_card_summary  # noqa: E402
from external_table_writer import (  # noqa: E402
    ConfigAliasRowWriter,
    ConfigSnippetDependencyRowWriter,
    ConfigSnippetRowWriter,
    _quote,
)

# Пороги полезности (разделы 2.2 и 4.2 плана V17).
MIN_BODY_LINES = 5                    # непустых строк тела объявления, чтобы не было шума
MAX_AUTO_ALIASES_PER_SNIPPET = 10    # автоалиасы на сниппет; ручные - без лимита
MIN_ALIAS_WORD_LEN = 3               # как extract_aliases в local_doc (len > 2)

# Веса по типу цели (раздел 4.1 плана). Совпадают по смыслу с alias_targets в local_doc.
WEIGHTS = {
    "ExternalReport.name": 1.2,
    "ExternalReport.part": 0.9,
    "ExternalReport.synonym": 1.0,
    "Attribute.name": 0.9,
    "Attribute.synonym": 0.7,
    "TabularSection.name": 0.9,
    "TabularSectionColumn.name": 0.9,
    "Form.name": 1.0,
    "Form.synonym": 1.0,
    "Form.command": 0.7,
    "Form.event_handler": 0.7,
    "FormItem.name": 0.8,
    "FormItem.caption": 0.8,
    "FormItem.data_source": 0.7,
    "Template.name": 0.8,
    "Template.root_tag": 0.6,
    "Module.declaration": 0.7,
    "ConfigSnippet.declaration": 1.1,
    "ConfigSnippet.auto": 1.0,
}

# Стандартные реквизиты табличных частей (_ID, _KeyOfRecord, _LineNumber, ...) - не цели
# поиска: их имена задаёт платформа, а не разработчик.
SKIP_NAME_PREFIX = "_"

DECL_START_RE = re.compile(
    r"^[ \t]*(?P<kw>процедура|функция|procedure|function)\b[ \t]*(?P<rest>.*)$", re.IGNORECASE)
DECL_END_RE = re.compile(
    r"^[ \t]*(конецпроцедуры|конецфункции|endprocedure|endfunction)\b", re.IGNORECASE)
DECL_NAME_RE = re.compile(r"^[^\s(\[<]+")
COMMENT_RE = re.compile(r"^[ \t]*(//|///)[ \t]*(?P<text>.*\S)")
QUERY_TEXT_RE = re.compile(
    r"<[A-Za-z0-9_:.-]*queryText[^>]*>(?P<sql>.*?)</[A-Za-z0-9_:.-]*queryText>", re.DOTALL)
# Узел A (14.10.2026): в схеме компоновки данных запрос набора данных лежит в <query> БЕЗ
# суффикса Text внутри <dataSet xsi:type="DataSetQuery">, поэтому QUERY_TEXT_RE его не находит
# и авто-сниппетов запросов СКД не было вовсе (проверено: list_config_snippets_tool(
# source_kind='template_query') давало пусто для Test1_Otchet). Имена элементов ищутся без
# префикса пространства имён - тот же приём, что _find_local в разборе выгрузки.
# \b после dataSet отсекает <dataSetLink>; закрытый тег </...query> не матчит </...queryText>.
DATASET_BLOCK_RE = re.compile(
    r"<[A-Za-z0-9_:.-]*dataSet\b[^>]*>(?P<body>.*?)</[A-Za-z0-9_:.-]*dataSet>", re.DOTALL)
DATASET_NAME_RE = re.compile(
    r"<[A-Za-z0-9_:.-]*name[^>]*>(?P<name>[^<]*)</[A-Za-z0-9_:.-]*name>")
DATASET_QUERY_RE = re.compile(
    r"<[A-Za-z0-9_:.-]*query>(?P<sql>.*?)</[A-Za-z0-9_:.-]*query>", re.DOTALL)
# Признак текста запроса. До узла A проверялось только «select»: запросы макета СКД выгружаются
# на языке конфигурации («ВЫБРАТЬ»), и прежний фильтр отбрасывал бы их как не-запрос.
QUERY_KEYWORD_RE = re.compile(r"(?:\bselect\b|\bвыбрать\b)", re.IGNORECASE)
CDATA_RE = re.compile(r"^\s*<!\[CDATA\[(?P<body>.*)\]\]>\s*$", re.DOTALL)
XML_ESCAPES = (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'"), ("&amp;", "&"))


def norm_alias(text):
    """Нормальное имя алиаса: lower, без сжатия смысла - только trim и схлопывание пробелов."""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def split_words(text, max_count=None, min_len=MIN_ALIAS_WORD_LEN):
    """Слова из текста (как extract_aliases в local_doc): длина > 2, порядок сохранения, без дублей."""
    words = []
    seen = set()
    for raw in re.split(r"[^0-9A-Za-zА-Яа-яЁё_.]+", str(text or "")):
        word = raw.strip().strip("._")
        if len(word) < min_len:
            continue
        key = word.lower()
        if key in seen:
            continue
        seen.add(key)
        words.append(word)
        if max_count is not None and len(words) >= max_count:
            break
    return words


def caption_of(synonym):
    """Текст подписи из jsonb синонима: ru, иначе первый язык, иначе ''."""
    if not isinstance(synonym, dict):
        return ""
    for key in ("ru", "RU", "ru_RU", "en"):
        value = synonym.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for value in synonym.values():
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def json_of(value, default):
    """Привести значение jsonb к dict/list: psycopg2 обычно отдаёт готовое, но подстрахуемся."""
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return default
    return parsed if isinstance(parsed, type(default)) else default


def resolve_object(uuid=None, source_path=None):
    """Найти объект выгрузки по uuid или каталогу выгрузки (через read_external_meta)."""
    if not uuid and source_path:
        from external_report_loader import read_external_meta
        meta = read_external_meta(source_path)
        if not meta.get("success"):
            return meta
        uuid = meta.get("uuid")
    if not uuid:
        return {"success": False,
                "error": "Не указан объект: нужен uuid внешнего объекта или source_path каталога выгрузки",
                "hint": "Пример: generate_config_enrichment_tool(uuid='d364e104-...') "
                        "или source_path=r'C:\\1C_LLM\\LoadDoc\\Test2_Otchet'."}
    return {"success": True, "uuid": str(uuid).strip(), "object_type": "external_report"}


def fetch_rows(cur, sql, params=None):
    """SELECT в список dict по именам колонок (jsonb приходит dict/list, text[] - списком).

    Публичный хелпер подсистемы: им пользуются src/enrichment_aliases.py и
    src/enrichment_snippets.py, чтобы не дублировать разбор курсора.
    """
    cur.execute(sql, params or ())
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


_rows = fetch_rows  # короткий внутренний псевдоним (вызовы в этом модуле не менялись)


def fetch_value(cur, sql, params=None):
    """SELECT одного скалярного значения (None, если строк нет).

    Публичный хелпер подсистемы: нужен, когда требуется один идентификатор цели
    (uuid строки, id модуля), а не карточка целиком.
    """
    cur.execute(sql, params or ())
    row = cur.fetchone()
    return row[0] if row else None



def object_row(cur, obj_uuid):
    """Карточка внешнего отчёта: uuid, имя, синоним. Обогащение реализовано для него.

    Публичная функция: ей пользуются API-модули, чтобы проверить существование объекта
    и взять его имя для карточки ответа.
    """
    rows = fetch_rows(cur,
                      "SELECT uuid::text AS uuid, name, synonym FROM external_report "
                      "WHERE uuid = %s::uuid LIMIT 1", (obj_uuid,))
    return rows[0] if rows else None


_object_row = object_row  # внутренний псевдоним



def collect_source_data(cur, obj_uuid):
    """Собрать содержимое объекта одним набором запросов (только уже сохранённое)."""
    return {
        "attributes": _rows(
            cur, "SELECT uuid::text AS uuid, name, synonym FROM attributes "
                 "WHERE parent_uuid = %s::uuid ORDER BY name", (obj_uuid,)),
        "tabular_sections": _rows(
            cur, "SELECT uuid::text AS uuid, name, synonym, column_uuids FROM tabular_sections "
                 "WHERE parent_uuid = %s::uuid ORDER BY name", (obj_uuid,)),
        "forms": _rows(
            cur, "SELECT uuid::text AS uuid, name, synonym, form_type FROM forms "
                 "WHERE parent_uuid = %s::uuid ORDER BY name", (obj_uuid,)),
        "form_ext": _rows(
            cur, "SELECT form_uuid::text AS form_uuid, name, items, events, commands, "
                 "auto_command_bar, ext, ext_path "
                 "FROM form_ext WHERE parent_uuid = %s::uuid ORDER BY name", (obj_uuid,)),
        "templates": _rows(
            cur, "SELECT uuid::text AS uuid, name, synonym, ext_root_tag, ext, ext_path "
                 "FROM templates WHERE parent_uuid = %s::uuid ORDER BY name", (obj_uuid,)),
        "bsl_modules": _rows(
            cur, "SELECT id, module_type, module_name, file_path, code FROM bsl_modules "
                 "WHERE parent_uuid = %s::uuid AND code IS NOT NULL ORDER BY id", (obj_uuid,)),
    }


class _AliasCollector:
    """Сбор алиасов без дублей в пределах цели; дубль на уровне БД гасит partial-индекс."""

    def __init__(self, obj_uuid, parent_type):
        self.rows = []
        self.seen = set()
        self.obj_uuid = obj_uuid
        self.parent_type = parent_type

    def add(self, alias, target_type, target_name=None, target_uuid=None,
            weight=1.0, description=None):
        text = re.sub(r"\s+", " ", str(alias or "")).strip()
        if len(text) < MIN_ALIAS_WORD_LEN:
            return False
        key = (norm_alias(text), target_uuid or "")
        if key in self.seen:
            return False
        self.seen.add(key)
        self.rows.append({
            "alias_name": text,
            "alias_norm": norm_alias(text),
            "target_type": target_type,
            "target_name": target_name,
            "target_uuid": target_uuid,
            "parent_uuid": self.obj_uuid,
            "parent_type": self.parent_type,
            "weight": weight,
            "description": description,
            "origin": "generated",
            "active": True,
        })
        return True


def _is_skipped_name(name):
    """Пустое и стандартные имена платформы (_ID, _KeyOfRecord, _LineNumber...) - не цели."""
    return not name or name.startswith(SKIP_NAME_PREFIX)


def _named_entry_name(entry):
    """Имя из записи jsonb: строка либо объект с name/command_name/handler/event."""
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict):
        for key in ("name", "command_name", "handler", "event"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _item_captions(item):
    """Подписи элемента формы: managed - title.<язык>, ordinary - captions.<язык>."""
    captions = []
    for key in ("title", "caption", "captions", "tooltip"):
        value = item.get(key)
        if isinstance(value, dict):
            for text in value.values():
                if isinstance(text, str) and text.strip():
                    captions.append(text.strip())
        elif isinstance(value, str) and value.strip():
            captions.append(value.strip())
    return captions


def build_object_aliases(obj, data):
    """Алиасы по объекту и его сохранённых частях (раздел 4.1 плана V17)."""
    obj_uuid = obj["uuid"]
    collector = _AliasCollector(obj_uuid, "external_report")

    name = (obj.get("name") or "").strip()
    if name:
        collector.add(name, "ExternalReport", target_name=name, target_uuid=obj_uuid,
                      weight=WEIGHTS["ExternalReport.name"], description="имя внешнего отчёта")
        # Части имени по '_': «СравнениеУСНИ90_2» даёт и «СравнениеУСНИ90».
        for part in [p for p in name.split("_") if len(p) >= MIN_ALIAS_WORD_LEN]:
            collector.add(part, "ExternalReport", target_name=name, target_uuid=obj_uuid,
                          weight=WEIGHTS["ExternalReport.part"],
                          description="часть имени внешнего отчёта")
    synonym = caption_of(json_of(obj.get("synonym"), {}))
    if synonym:
        collector.add(synonym, "ExternalReport", target_name=name, target_uuid=obj_uuid,
                      weight=WEIGHTS["ExternalReport.synonym"], description="синоним объекта")

    column_uuids = set()
    for section in data["tabular_sections"]:
        section_name = section.get("name") or ""
        section_uuid = section.get("uuid")
        if not _is_skipped_name(section_name):
            collector.add(section_name, "TabularSection", target_name=section_name,
                          target_uuid=section_uuid, weight=WEIGHTS["TabularSection.name"],
                          description="табличная часть")
        section_caption = caption_of(json_of(section.get("synonym"), {}))
        if section_caption:
            collector.add(section_caption, "TabularSection", target_name=section_name,
                          target_uuid=section_uuid,
                          weight=WEIGHTS["ExternalReport.synonym"],
                          description="синоним табличной части")
        for column_uuid in json_of(section.get("column_uuids"), []):
            column_uuids.add(str(column_uuid))

    for attribute in data["attributes"]:
        attr_name = attribute.get("name") or ""
        attr_uuid = attribute.get("uuid")
        if _is_skipped_name(attr_name):
            continue
        is_column = attr_uuid in column_uuids
        target_type = "TabularSectionColumn" if is_column else "Attribute"
        collector.add(attr_name, target_type, target_name=attr_name, target_uuid=attr_uuid,
                      weight=WEIGHTS["TabularSectionColumn.name"] if is_column
                      else WEIGHTS["Attribute.name"],
                      description="колонка табличной части" if is_column else "реквизит объекта")
        attr_caption = caption_of(json_of(attribute.get("synonym"), {}))
        if attr_caption:
            collector.add(attr_caption, target_type, target_name=attr_name,
                          target_uuid=attr_uuid, weight=WEIGHTS["Attribute.synonym"],
                          description="подпись реквизита")

    form_names = {}
    for form in data["forms"]:
        form_name = form.get("name") or ""
        form_uuid = form.get("uuid")
        form_names[form_uuid] = form_name
        if form_name:
            collector.add(form_name, "Form", target_name=form_name, target_uuid=form_uuid,
                          weight=WEIGHTS["Form.name"], description="форма объекта")
        form_caption = caption_of(json_of(form.get("synonym"), {}))
        if form_caption:
            collector.add(form_caption, "Form", target_name=form_name, target_uuid=form_uuid,
                          weight=WEIGHTS["Form.synonym"], description="подпись формы")

    for form_ext in data["form_ext"]:
        form_uuid = form_ext.get("form_uuid") or ""
        form_name = form_names.get(form_uuid) or form_ext.get("name") or ""
        for item in json_of(form_ext.get("items"), []):
            if not isinstance(item, dict):
                continue
            item_name = item.get("name") or ""
            if not item_name or _is_skipped_name(item_name):
                continue
            target_uuid = f"form_item:{form_uuid}:{item_name}"
            item_caption_texts = _item_captions(item)
            collector.add(item_name, "FormItem", target_name=f"{form_name}.{item_name}",
                          target_uuid=target_uuid, weight=WEIGHTS["FormItem.name"],
                          description="элемент формы")
            for caption in item_caption_texts:
                collector.add(caption, "FormItem", target_name=f"{form_name}.{item_name}",
                              target_uuid=target_uuid, weight=WEIGHTS["FormItem.caption"],
                              description="подпись элемента формы")
            data_source = item.get("datapath") or item.get("data_source") or ""
            for part in [p for p in re.split(r"[.\[\]]", str(data_source))
                         if len(p) >= MIN_ALIAS_WORD_LEN]:
                collector.add(part, "FormItem", target_name=f"{form_name}.{item_name}",
                              target_uuid=target_uuid, weight=WEIGHTS["FormItem.data_source"],
                              description=f"источник данных элемента ({data_source})")
        for command in json_of(form_ext.get("commands"), []):
            command_name = _named_entry_name(command)
            if command_name:
                collector.add(command_name, "Form", target_name=form_name, target_uuid=form_uuid,
                              weight=WEIGHTS["Form.command"], description="команда формы")
        auto_bar = json_of(form_ext.get("auto_command_bar"), {})
        if isinstance(auto_bar, dict):
            for entry in auto_bar.get("commands") or []:
                command_name = _named_entry_name(entry)
                if command_name:
                    collector.add(command_name, "Form", target_name=form_name,
                                  target_uuid=form_uuid, weight=WEIGHTS["Form.command"],
                                  description="команда панели действий формы")
        for event in json_of(form_ext.get("events"), []):
            if not isinstance(event, dict):
                continue
            handler = (event.get("handler") or "").strip()
            if handler:
                collector.add(handler, "Form", target_name=form_name, target_uuid=form_uuid,
                              weight=WEIGHTS["Form.event_handler"],
                              description=f"обработчик события {event.get('event', '')}".strip())

    for template in data["templates"]:
        template_name = template.get("name") or ""
        template_uuid = template.get("uuid")
        if template_name:
            collector.add(template_name, "Template", target_name=template_name,
                          target_uuid=template_uuid, weight=WEIGHTS["Template.name"],
                          description="макет объекта")
        root_tag = (template.get("ext_root_tag") or "").strip()
        if root_tag:
            collector.add(root_tag, "Template", target_name=template_name,
                          target_uuid=template_uuid, weight=WEIGHTS["Template.root_tag"],
                          description=f"корневой тег макета ({root_tag})")

    for module in data["bsl_modules"]:
        module_label = module.get("module_name") or module.get("module_type") or ""
        for declaration in parse_declarations(module.get("code") or ""):
            collector.add(declaration["name"], "Module", target_name=module_label,
                          target_uuid=f"module:{module['id']}",
                          weight=WEIGHTS["Module.declaration"],
                          description="объявление в модуле объекта/менеджера")
    for form_ext in data["form_ext"]:
        form_uuid = form_ext.get("form_uuid") or ""
        form_label = form_names.get(form_uuid) or form_ext.get("name") or ""
        for declaration in parse_declarations(form_ext.get("ext") or ""):
            collector.add(declaration["name"], "Module", target_name=form_label,
                          target_uuid=f"module:form:{form_uuid}",
                          weight=WEIGHTS["Module.declaration"],
                          description="объявление в модуле формы")

    return collector.rows


def parse_declarations(code):
    """Объявления процедур/функций BSL: имя, полный текст, число непустых строк тела.

    Скан построчный, без внешних библиотек: `Процедура|Функция` (и английские ключевые
    слова) до `КонецПроцедуры|КонецФункции`. Вложенных процедур в BSL нет, поэтому такой
    счётчик корректен. Строковые литералы, начинающиеся с «Процедура», - принятое
    ограничение: ложные связи дороже пропущенных.
    """
    declarations = []
    if not code:
        return declarations
    lines = str(code).replace("\r\n", "\n").split("\n")
    index = 0
    while index < len(lines):
        start = DECL_START_RE.match(lines[index])
        if not start:
            index += 1
            continue
        rest = (start.group("rest") or "").strip()
        if not rest or rest.startswith("//"):
            index += 1
            continue
        name_match = DECL_NAME_RE.match(rest)
        if not name_match:
            index += 1
            continue
        name = name_match.group(0).strip()
        body_start = index + 1
        end = None
        scan = body_start
        while scan < len(lines):
            if DECL_END_RE.match(lines[scan]):
                end = scan
                break
            scan += 1
        if end is None:
            index += 1
            continue
        body = lines[body_start:end]
        non_empty = [line for line in body if line.strip()]
        comment = ""
        for line in non_empty:
            found = COMMENT_RE.match(line)
            if found:
                comment = found.group("text").strip()
                break
        declarations.append({
            "name": name,
            "kind": (start.group("kw") or "").lower(),
            "text": "\n".join(lines[index:end + 1]).strip(),
            "body_lines": len(non_empty),
            "comment": comment,
        })
        index = end + 1
    return declarations


def _unescape_xml(text):
    """Разбор XML-сущностей текста запроса (&lt;, &gt;, &quot;, &apos;, &amp;).

    &amp; заменяется последней, иначе '&amp;lt;' превратилось бы в '<' раньше времени.
    Текст запроса макета хранится экранированным («Сумма &lt;&gt; 0», «&amp;Параметр»),
    а в сниппете он нужен читаемым - как в ручном снимке и как в конфигураторе.
    """
    out = text or ""
    for needle, replacement in XML_ESCAPES:
        out = out.replace(needle, replacement)
    return out


def _strip_cdata(text):
    """Снять обёртку <![CDATA[ ... ]]> , если запрос макета выгружен внутри неё."""
    found = CDATA_RE.match(text or "")
    return found.group("body").strip() if found else (text or "").strip()


def _looks_like_query(sql):
    """Похож ли текст на запрос: ключевое слово SELECT или русское «ВЫБРАТЬ»."""
    return bool(QUERY_KEYWORD_RE.search(sql or ""))


def template_queries(ext_text):
    """Тексты запросов из макета: содержимое элементов *queryText (namespace-агностично)."""
    if not ext_text:
        return []
    queries = []
    for match in QUERY_TEXT_RE.finditer(str(ext_text)):
        sql = _strip_cdata(_unescape_xml(match.group("sql")))
        if _looks_like_query(sql):
            queries.append(sql)
    return queries


def template_dataset_queries(ext_text):
    """Запросы наборов данных схемы компоновки данных: <query> внутри <dataSet> (узел A).

    В отличие от queryText, в СКД текст запроса лежит в элементе <query> без суффикса Text,
    а имя набора - в <name> того же блока <dataSet xsi:type="DataSetQuery">. Возвращает
    список [{"dataset": имя набора или "", "sql": текст}] в порядке следования в файле.

    Деградация (намеренная): пустой, битый или не-запросный <query> пропускается, объект
    остаётся без этого авто-сниппета, но генерация продолжается - как с неразобранной
    ordinary-формой в узле V15. Ошибкой это не считается: источник истины - templates.ext.
    """
    if not ext_text:
        return []
    found = []
    for block in DATASET_BLOCK_RE.finditer(str(ext_text)):
        body = block.group("body")
        name_match = DATASET_NAME_RE.search(body)
        dataset_name = (name_match.group("name") or "").strip()
        for query in DATASET_QUERY_RE.finditer(body):
            sql = _strip_cdata(_unescape_xml(query.group("sql")))
            if not _looks_like_query(sql):
                continue
            found.append({"dataset": dataset_name, "sql": sql})
    return found


def _module_source_kind(module_type, module_name):
    """source_kind сниппета по типу модуля (раздел 4.2 плана V17)."""
    kind = (module_type or "").strip()
    if kind == "ObjectModule":
        return "object_module"
    if kind == "ManagerModule":
        return "manager_module"
    if kind == "FormModule":
        return "form_module"
    if kind:
        return f"module:{kind.lower()}"
    return f"module:{(module_name or 'unknown').lower()}"


def build_snippets(obj, data):
    """Сниппеты по объявлениям модулей и по запросам макетов СКД (раздел 4.2 плана V17).

    Возвращает список dict {"row": <строка для config_snippets>, "decl_name": ...}.
    Строка вставляется первой, её id подставляется в зависимости и алиасы сниппета.
    Порог MIN_BODY_LINES отсекает шум: объявления с пустым телом в сниппеты не идут.
    """
    obj_uuid = obj["uuid"]
    obj_name = (obj.get("name") or "").strip() or obj_uuid
    snippets = []

    def add(question, answer, source_kind, source_uuid, source_path,
            target_type, target_uuid, tags, confidence, decl_name):
        if not answer or not question:
            return
        snippets.append({
            "row": {
                "parent_uuid": obj_uuid,
                "parent_type": "external_report",
                "question": question,
                "answer": answer,
                "source_kind": source_kind,
                "source_uuid": source_uuid,
                "source_path": source_path,
                "target_type": target_type,
                "target_uuid": target_uuid,
                "tags": tags,
                "confidence": confidence,
                "is_verified": False,
            },
            "decl_name": decl_name,
        })

    def question_for(decl_name, comment):
        text = obj_name + ": " + decl_name
        if comment:
            text += " - " + comment[:120]
        return text

    for module in data["bsl_modules"]:
        source_uuid = f"module:{module['id']}"
        source_kind = _module_source_kind(module.get("module_type"), module.get("module_name"))
        for declaration in parse_declarations(module.get("code") or ""):
            if declaration["body_lines"] < MIN_BODY_LINES:
                continue
            add(question_for(declaration["name"], declaration["comment"]),
                declaration["text"], source_kind, source_uuid, module.get("file_path"),
                "Module", source_uuid, ["bsl", "config", "generated"], 0.85,
                declaration["name"])

    for form_ext in data["form_ext"]:
        form_uuid = form_ext.get("form_uuid") or ""
        source_uuid = f"module:form:{form_uuid}"
        for declaration in parse_declarations(form_ext.get("ext") or ""):
            if declaration["body_lines"] < MIN_BODY_LINES:
                continue
            add(question_for(declaration["name"], declaration["comment"]),
                declaration["text"], "form_module", source_uuid, form_ext.get("ext_path"),
                "Form", form_uuid, ["bsl", "config", "generated", "form"], 0.85,
                declaration["name"])

    for template in data["templates"]:
        template_uuid = template.get("uuid") or ""
        template_name = template.get("name") or template_uuid
        for sql in template_queries(template.get("ext")):
            if len([line for line in sql.split("\n") if line.strip()]) < MIN_BODY_LINES:
                continue
            add(obj_name + ": запрос макета " + template_name, sql, "template_query",
                f"template:{template_uuid}", template.get("ext_path"), "Template",
                template_uuid, ["bsl", "config", "generated", "dcs", "query"], 0.8,
                "макет " + template_name)
        # Узел A: запрос набора данных схемы компоновки данных. От queryText отличается только
        # элементом-носителем (<query>) и наличием имени набора, поэтому source_kind общий -
        # «текст запроса из макета»; различие видно в question и в decl_name (по нему сниппет
        # находится алиасом). Цель - сам макет (Template), стабильный ключ - его uuid.
        for dataset in template_dataset_queries(template.get("ext")):
            sql = dataset["sql"]
            if len([line for line in sql.split("\n") if line.strip()]) < MIN_BODY_LINES:
                continue
            label = f"{template_name}.{dataset['dataset']}" if dataset["dataset"] else template_name
            add(obj_name + ": запрос набора данных макета " + label, sql, "template_query",
                f"template:{template_uuid}", template.get("ext_path"), "Template",
                template_uuid, ["bsl", "config", "generated", "dcs", "query", "dataset"], 0.8,
                "запрос набора данных " + label)

    return snippets


def _identifier_index(data):
    """Справочник «имя (lower) -> (target_type, target_name, target_uuid)» для зависимостей.

    Имена стандартных реквизитов платформы (_ID, ...) в индекс не попадают: они есть в
    любой выгрузке и дали бы ложные связи.
    """
    index = {}

    def put(name, target_type, target_name, target_uuid):
        if _is_skipped_name(name):
            return
        key = norm_alias(name)
        if len(key) < MIN_ALIAS_WORD_LEN or key in index:
            return
        index[key] = (target_type, target_name, target_uuid)

    for attribute in data["attributes"]:
        put(attribute.get("name"), "Attribute", attribute.get("name"), attribute.get("uuid"))
    for section in data["tabular_sections"]:
        put(section.get("name"), "TabularSection", section.get("name"), section.get("uuid"))
    form_names = {}
    for form in data["forms"]:
        put(form.get("name"), "Form", form.get("name"), form.get("uuid"))
        if form.get("uuid"):
            form_names[form.get("uuid")] = form.get("name") or ""
    for form_ext in data["form_ext"]:
        form_uuid = form_ext.get("form_uuid") or ""
        form_name = form_names.get(form_uuid) or form_ext.get("name") or ""
        for item in json_of(form_ext.get("items"), []):
            if isinstance(item, dict):
                item_name = item.get("name")
                # имя цели qualified ('Форма.Элемент') - то же, что в алиасах и витрине:
                # ключ индекса остаётся голым именем, по нему ищется текст кода
                put(item_name, "FormItem",
                    f"{form_name}.{item_name}" if form_name else item_name,
                    f"form_item:{form_uuid}:{item_name}")
    for template in data["templates"]:
        put(template.get("name"), "Template", template.get("name"), template.get("uuid"))
    return index


IDENTIFIER_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё_]+")


def build_dependencies(snippet, index, own_decl_name=None):
    """Зависимости сниппета типа 'references': объекты, упомянутые в тексте кода.

    Ищем идентификаторы текста сниппета в справочнике имён объекта (индекс имён
    атрибутов, ТЧ, форм, элементов формы, макетов). Тип и имя цели берутся из справочника,
    поэтому связь указывает на конкретную строку (target_uuid), а не на «примерное имя».
    Источник сниппета (модуль/форма/макет) в зависимостях не дублируется: он уже
    записан в config_snippets.source_kind / source_uuid / source_path.
    """
    text = (snippet.get("question") or "") + "\n" + (snippet.get("answer") or "")
    found = []
    seen = set()
    for word in IDENTIFIER_RE.findall(text):
        key = norm_alias(word)
        entry = index.get(key)
        if not entry:
            continue
        target_type, target_name, target_uuid = entry
        if own_decl_name and key == norm_alias(own_decl_name):
            continue
        dep_key = (entry[0], entry[1])
        if dep_key in seen:
            continue
        seen.add(dep_key)
        found.append({"dependency_type": "references", "target_type": target_type,
                      "target_name": target_name, "target_uuid": target_uuid})
    return found


def build_snippet_aliases(snippet_row, snippet_id, obj_uuid, decl_name=None,
                         max_auto=MAX_AUTO_ALIASES_PER_SNIPPET):
    """Автоалиасы сниппета: имя объявления (вес 1.1) + слова из текста (вес 1.0), не больше max_auto.

    Именно здесь нужен порог количества: автоалиасы из question/answer покрывают только
    те термины, которые встречаются в самом коде. Недостающее добавляет оператор инструментом
    add_config_aliases_tool (origin='manual', лимита нет) - так же, как add_aliases_tool
    дополняет алиасы сниппетов в local_doc.
    """
    rows = []
    seen = set()

    def add(alias, weight, description):
        text = re.sub(r"\s+", " ", str(alias or "")).strip()
        if len(text) < MIN_ALIAS_WORD_LEN:
            return False
        key = norm_alias(text)
        if key in seen:
            return False
        seen.add(key)
        rows.append({"alias_name": text, "alias_norm": key,
                     "target_type": "ConfigSnippet",
                     "target_name": snippet_row.get("question"),
                     "target_snippet_id": snippet_id,
                     "parent_uuid": obj_uuid, "parent_type": "external_report",
                     "weight": weight, "description": description,
                     "origin": "generated", "active": True})
        return True

    if decl_name:
        add(decl_name, WEIGHTS["ConfigSnippet.declaration"], "имя объявления из сниппета")
    seed = split_words(snippet_row.get("question") or "", max_count=max_auto)
    if len(seed) < max_auto:
        seed += split_words(snippet_row.get("answer") or "",
                            max_count=max_auto - len(seed))
    for word in seed[:max_auto]:
        if len(rows) >= max_auto:
            break
        add(word, WEIGHTS["ConfigSnippet.auto"], "термин из кода сниппета")
    return rows


def _purge_generated(cur, obj_uuid):
    """Снять автоматически созданные строки объекта. Ручные (origin='manual',
    is_verified=true, связи local_doc) остаются - их создал или изменил оператор.
    Зависимости снимаются только у снимаемых (не verified) сниппетов, иначе у
    ручного сниппета пропали бы его собственные связи."""
    removed = {}
    for table, clause in (("config_snippet_dependencies",
                          "USING config_snippets s WHERE s.id = config_snippet_dependencies.snippet_id"
                          " AND s.parent_uuid = %s::uuid AND s.is_verified = false"),
                         ("config_snippets", "WHERE parent_uuid = %s::uuid AND is_verified = false"),
                         ("config_aliases", "WHERE parent_uuid = %s::uuid AND origin = 'generated'")):
        cur.execute(f"DELETE FROM {table} {clause} RETURNING {table}.id", (obj_uuid,))
        removed[table] = len(cur.fetchall())
    return removed


def _existing_snippet_keys(cur, obj_uuid):
    """Ключи уже существующих сниппетов объекта, чтобы не спорить с ручными строками."""
    cur.execute("SELECT source_kind, COALESCE(source_uuid, ''), question FROM config_snippets "
                "WHERE parent_uuid = %s::uuid", (obj_uuid,))
    return {(row[0], row[1] or "", row[2]) for row in cur.fetchall()}


def generate_enrichment(uuid=None, source_path=None):
    """Пересобрать обогащение объекта: алиасы объекта, сниппеты, зависимости, алиасы сниппетов.

    Одна транзакция: либо всё, либо ничего (в откате нет ни части строк, ни счётчиков).
    Возвращает карточку с числом снятых и созданных строк по каждой таблице.
    """
    resolved = resolve_object(uuid=uuid, source_path=source_path)
    if not resolved.get("success"):
        return resolved
    obj_uuid = resolved["uuid"]

    try:
        with transaction() as cur:
            obj = _object_row(cur, obj_uuid)
            if not obj:
                return {"success": False,
                        "error": f"Внешний объект с uuid={obj_uuid} в external_report не найден",
                        "hint": "Сначала загрузите каталог: load_1c_catalog_tool(source_path=...)."}
            data = collect_source_data(cur, obj_uuid)

            # узел V20.1: привязка к конфигурации в генерации не участвует — конфигурация есть
            # справочная система, нужная при проверке данных отчёта. Поэтому потерянный заголовок
            # НЕ может быть причиной отказа: объект обязан оставаться читаемым и обогатимым даже
            # после удаления строки справочника. Но и молчать об этом нельзя: состояние
            # возвращается предупреждением с указанием действия.
            warnings = []
            binding = _binding_state_row(cur, obj_uuid)
            if binding and binding[0].get("configuration_state") == "dangling":
                warnings.append(
                    f"Привязка к конфигурации битая: configuration_id="
                    f"{binding[0].get('configuration_id')}, строки заголовка конфигурации в "
                    "configurations нет. На состав обогащения это не влияет; нужна перепривязка "
                    "— set_object_configuration_tool(uuid=..., configuration_id=<id>) или снятие "
                    "привязки (configuration_id=None).")

            object_aliases = build_object_aliases(obj, data)
            snippets = build_snippets(obj, data)
            index = _identifier_index(data)

            removed = _purge_generated(cur, obj_uuid)
            existing = _existing_snippet_keys(cur, obj_uuid)

            aliases_inserted, aliases_skipped = ConfigAliasRowWriter.insert_many_skip_duplicates(
                cur, object_aliases)


            snippet_rows = []
            for snippet in snippets:
                row = snippet["row"]
                key = (row["source_kind"], row["source_uuid"] or "", row["question"])
                if key in existing:
                    continue
                snippet_rows.append((snippet, row))
            inserted_ids = ConfigSnippetRowWriter.insert_ids(cur, [row for _, row in snippet_rows])

            dependency_rows = []
            snippet_alias_rows = []
            for (snippet, row), snippet_id in zip(snippet_rows, inserted_ids):
                if not snippet_id:
                    continue
                for dependency in build_dependencies(row, index, own_decl_name=snippet["decl_name"]):
                    dependency_rows.append(dict(dependency, snippet_id=snippet_id))
                snippet_alias_rows += build_snippet_aliases(
                    row, snippet_id, obj_uuid, decl_name=snippet["decl_name"])

            dependencies_inserted = ConfigSnippetDependencyRowWriter.insert_many(cur, dependency_rows)
            snippet_aliases_inserted, _ = ConfigAliasRowWriter.insert_many_skip_duplicates(
                cur, snippet_alias_rows)


            counts = {}
            cur.execute("SELECT count(*) FROM config_aliases WHERE parent_uuid = %s::uuid",
                        (obj_uuid,))
            counts["aliases_total"] = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM config_snippets WHERE parent_uuid = %s::uuid",
                        (obj_uuid,))
            counts["snippets_total"] = cur.fetchone()[0]

            skipped = len(snippets) - len(snippet_rows)
            return {
                "success": True,
                "uuid": obj_uuid,
                "name": obj.get("name"),
                "removed": removed,
                "created": {
                    "object_aliases": aliases_inserted,
                    "snippets": len(inserted_ids),
                    "snippet_dependencies": dependencies_inserted,
                    "snippet_aliases": snippet_aliases_inserted,
                },
                "skipped_duplicates": skipped,
                "warnings": warnings,
                "totals": counts,
                "source_coverage": {
                    "attributes": len(data["attributes"]),
                    "tabular_sections": len(data["tabular_sections"]),
                    "forms": len(data["forms"]),
                    "form_ext": len(data["form_ext"]),
                    "templates": len(data["templates"]),
                    "bsl_modules": len(data["bsl_modules"]),
                },
            }
    except Exception as exc:
        return {"success": False, "error": f"Обогащение не выполнено (полный откат): {exc}"}


# =====================================================
# ПРИВЯЗКА ВНЕШНЕГО ОБЪЕКТА К КОНФИГУРАЦИИ (узлы V20, V20.1)
# =====================================================
#
# Модель (её заявляет только оператор): external_report.configuration_id — id строки заголовка
# конфигурации (configurations.id), а не uuid метаданных 1С. NULL = «привязка не заявлена»;
# состояния «универсальный» в модели нет, автоматического вывода привязки из выгрузки нет.
#
# Узел V20.1 (14.10.2026): внешнего ключа в схеме нет. Конфигурация — справочная система,
# которая нужна только при проверке данных отчёта; ни загрузка, ни генерация, ни карточка для
# своей работы в configurations не обращаются, а FK блокировал бы ведение самого справочника и
# давал ошибку в момент записи, а не при анализе объекта. Поэтому существование строки
# заголовка проверяет этот инструмент (несуществующий id отклоняется — тот же контракт, что у
# add_config_cross_reference_tool для local_doc), а потерявшая заголовок ссылка обнаруживается
# при чтении: карточка объекта и сводка различают not_declared / bound / dangling.

CONFIGURATION_LINK_NOTE = (
    "Привязку заявляет только оператор: в выгрузке 1С ссылки на конфигурацию нет, "
    "автоматического вывода и классификации («универсальный» / «привязанный») нет. "
    "NULL = «привязка не заявлена», и это НЕ значит, что отчёт универсальный — "
    "такого состояния в модели нет."
)

MAX_CONFIGURATION_HINTS = 20   # сколько заголовков перечислять в подсказке к ошибке
CLEAR_BINDINGS = ("", "none", "null")   # как понимают «снять привязку» в аргументе инструмента


def _binding_state_row(cur, obj_uuid):
    """Состояние привязки объекта: not_declared / bound / dangling + разрешённые имя и версия.

    Состояние считается по cfg.id, а не по имени: внешнего ключа нет, и заголовок мог быть
    удалён после установки привязки. Тот же CASE читает карточку и сводку — расхождений между
    ними быть не должно.
    """
    return fetch_rows(
        cur,
        "SELECT er.configuration_id, cfg.name AS configuration_name, "
        "       cfg.version AS configuration_version, "
        "       CASE WHEN er.configuration_id IS NULL THEN 'not_declared' "
        "            WHEN cfg.id IS NULL THEN 'dangling' "
        "            ELSE 'bound' END AS configuration_state "
        "FROM external_report er "
        "LEFT JOIN configurations cfg ON cfg.id = er.configuration_id "
        "WHERE er.uuid = %s::uuid LIMIT 1", (obj_uuid,))


def set_object_configuration(uuid=None, source_path=None, configuration_id=None):
    """Заявить или снять привязку внешнего объекта к конфигурации (configurations.id).

    `configuration_id` — id строки заголовка из configurations; None (или пустая строка) —
    снять привязку, поле снова означает «не заявлена». Значение НЕ является uuid метаданных 1С.

    Существующая строка заголовка проверяется здесь, а не схемой: внешнего ключа нет
    (узел V20.1), поэтому несуществующий id отклоняется инструментом, а не ложится битой
    ссылкой. Если заголовок удалён ПОСЛЕ установки привязки — ссылка становится битой, и это
    называется прямо: карточка объекта и сводка требуют перепривязки. Снимок имени и версии в
    БД не хранится: карточка всегда читает живые значения, поэтому переиспользование id новым
    заголовком видно по другому имени и версии, а не спрятано в устаревшей копии.

    Возвращает прежнее и новое состояние, разрешённые имя и версию и число объектов,
    привязанных к этой конфигурации, — оператор обязан видеть, что он меняет.
    """
    resolved = resolve_object(uuid=uuid, source_path=source_path)
    if not resolved.get("success"):
        return resolved
    obj_uuid = resolved["uuid"]
    try:
        with transaction() as cur:
            cur.execute("SELECT id, name, configuration_id FROM external_report "
                        "WHERE uuid = %s::uuid LIMIT 1", (obj_uuid,))
            row = cur.fetchone()
            if not row:
                return {"success": False,
                        "error": f"Внешний объект с uuid={obj_uuid} в external_report не найден",
                        "hint": "Сначала загрузите каталог: load_1c_catalog_tool(source_path=...)."}
            obj_id, obj_name, previous = row

            if configuration_id is None or (isinstance(configuration_id, str)
                                            and configuration_id.strip().lower() in CLEAR_BINDINGS):
                cur.execute("UPDATE external_report SET configuration_id = NULL WHERE id = %s",
                            (obj_id,))
                return {"success": True, "mode": "cleared", "uuid": obj_uuid,
                        "object_name": obj_name,
                        "previous_configuration_id": previous,
                        "configuration_id": None, "configuration_name": None,
                        "configuration_version": None, "configuration_state": "not_declared",
                        "bound_objects": 0, "note": CONFIGURATION_LINK_NOTE}

            try:
                cfg_id = int(configuration_id)
            except (TypeError, ValueError):
                return {"success": False,
                        "error": "configuration_id должен быть целым id строки заголовка "
                                 f"конфигурации (configurations.id), получено: {configuration_id!r}",
                        "hint": "Это id строки заголовка, а не uuid метаданных 1С. Снять "
                                "привязку — configuration_id=None. " + CONFIGURATION_LINK_NOTE}

            cur.execute("SELECT id, name, version FROM configurations WHERE id = %s", (cfg_id,))
            cfg = cur.fetchone()
            if not cfg:
                available = fetch_rows(cur, "SELECT id, name, version FROM configurations "
                                           "ORDER BY name LIMIT %(l)s",
                                       {"l": MAX_CONFIGURATION_HINTS})
                return {"success": False,
                        "error": f"Конфигурация с id={cfg_id} в configurations не найдена — "
                                 "привязка НЕ установлена",
                        "hint": "Ссылка ведёт в справочную таблицу заголовков; внешнего ключа "
                                "нет, но битой ссылки этот инструмент не создаёт. Доступные "
                                f"заголовки: {available or 'в configurations нет ни одной строки'}. "
                                + CONFIGURATION_LINK_NOTE}

            cur.execute("UPDATE external_report SET configuration_id = %s WHERE id = %s",
                        (cfg_id, obj_id))
            bound = fetch_rows(cur, "SELECT count(*) AS bound_objects FROM external_report "
                                    "WHERE configuration_id = %s",
                               (cfg_id,))[0]["bound_objects"]
            return {"success": True, "mode": "bound", "uuid": obj_uuid,
                    "object_name": obj_name,
                    "previous_configuration_id": previous,
                    "configuration_id": cfg[0], "configuration_name": cfg[1],
                    "configuration_version": cfg[2], "configuration_state": "bound",
                    "bound_objects": bound,
                    "note": "Имя и версия в БД не дублируются: карточка разрешает ссылку "
                            "живым чтением. " + CONFIGURATION_LINK_NOTE}
    except Exception as exc:
        return {"success": False, "error": f"Привязка не изменена: {exc}"}


# =====================================================
# КАРТОЧКА СВОЙСТВ И НАЗНАЧЕНИЯ ОБЪЕКТА (только чтение, ничего не пишет)
# =====================================================

DESCRIBE_DEFAULT_LIMIT = 20   # строк на раздел карточки; 0 — разделы не отдаются, счётчики даются
DESCRIBE_MAX_LIMIT = 200      # верхняя граница limit: карточка не должна разрастаться до дампа


def type_brief(value):
    """Краткое имя типа реквизита из JSON-строки колонки attributes.type.

    Колонка хранит разбор элемента <Type> выгрузки: {"types": [...], "qualifiers": {...}}
    (узел V12, src/external_meta_parser.py). Префикс `cfg:` снимаем — он общий для всех
    ссылочных типов и только шумит (`cfg:CatalogRef.Организации` -> `CatalogRef.Организации`);
    `xs:dateTime` оставляем как есть — это тип XDTO. Квалификатор даты (DateFractions)
    добавляется отдельным членом, иначе два реквизита «дата» в карточке неразличимы.
    """
    payload = json_of(value, {})
    if not isinstance(payload, dict):
        return ""
    names = []
    for raw in payload.get("types") or []:
        text = str(raw)
        names.append(text[4:] if text.startswith("cfg:") else text)
    qualifiers = payload.get("qualifiers")
    if isinstance(qualifiers, dict):
        for value in qualifiers.values():
            if isinstance(value, dict) and value.get("DateFractions"):
                names.append(f"DateFractions={value['DateFractions']}")
    return " | ".join(names)


def _json_len_sql(column):
    """SQL-выражение длины jsonb-массива: NULL и не-массив дают 0, падения нет.

    jsonb_array_length падает на не-массиве, а пустой массив — не NULL (признак разобранной
    формы — jsonb_array_length(items) > 0), поэтому тип проверяется отдельно через jsonb_typeof.
    """
    return (f"CASE WHEN jsonb_typeof({column}) = 'array' "
            f"THEN jsonb_array_length({column}) ELSE 0 END")


# NOT EXISTS по column_uuids отличает реквизиты объекта от колонок табличных частей: и те и другие
# лежат в attributes с parent_uuid внешнего объекта (узел V12), различие — только в ссылке ТЧ.
_OBJECT_ATTRIBUTES_ONLY = (
    "NOT EXISTS (SELECT 1 FROM tabular_sections ts "
    "            WHERE ts.parent_uuid = %(u)s::uuid "
    "              AND ts.column_uuids @> jsonb_build_array(a.uuid))"
)


def describe_object(uuid=None, source_path=None, limit=DESCRIBE_DEFAULT_LIMIT):
    """Карточка свойств и назначения внешнего объекта из уже сохранённого содержимого.

    Отвечает на три вопроса без конфигуратора и без повторной распаковки выгрузки:
      * что это за объект — имя, синоним, комментарий, сгенерированный тип, основная СКД,
        форма и настройки по умолчанию (колонки external_report, узел V12);
      * из чего он состоит — реквизиты (кроме колонок ТЧ), табличные части с числом колонок,
        формы с типом и составом, макеты и содержимое макетов-СКД (наборы данных, параметры,
        вычисляемые и итоговые поля, структура вывода), модули (узлы V12, V13, V14, V15, B);
      * как он работает — перечень сохранённых enrich-сниппетов (объявления модулей, запросы
        макетов), события формы и ссылки на documentation.

    Только чтение, одна транзакция, ничего не пишет. Разделы ограничены `limit`
    (limit=0 — разделы не отдаются, счётчики всё равно считаются). `counts` — полные числа
    по БД, от `limit` они не зависят (в том числе form_elements / form_events): карточка
    обязана называть настоящее число объектов, а усечение списка показывать явно. Обогащение реализовано
    для внешних отчётов, поэтому источник — external_report; для другого типа объекта
    карточка не найдена с явной причиной.
    """
    resolved = resolve_object(uuid=uuid, source_path=source_path)
    if not resolved.get("success"):
        return resolved
    obj_uuid = resolved["uuid"]
    try:
        limit = int(limit if limit is not None else DESCRIBE_DEFAULT_LIMIT)
    except (TypeError, ValueError):
        limit = DESCRIBE_DEFAULT_LIMIT
    limit = max(0, min(limit, DESCRIBE_MAX_LIMIT))

    try:
        with transaction() as cur:
            identity = fetch_rows(
                cur,
                "SELECT er.id AS report_id, er.uuid::text AS uuid, er.name, er.synonym, er.comment, "
                "       er.default_form, er.auxiliary_form, er.default_settings_form, "
                "       er.main_data_composition_schema, er.variants_storage, er.settings_storage, "
                "       er.generatedtype_category, er.generatedtype_name, er.generatedtype_typeid::text, "
                "       er.containedobject_classid::text, er.containedobject_objectid::text, er.created_at, "
                # узел V20: привязка к конфигурации, заявленная оператором. NULL — это
                # «привязка не заявлена», а не «отчёт универсальный»: отдельного состояния
                # «универсальный» в модели нет. Название и версия читаются справочно, чтобы
                # оператор видел, К ЧЕМУ он привязал объект (ссылка — на строку заголовка).
                # узел V20.1: внешнего ключа нет, поэтому строка заголовка могла быть удалена,
                # пока на неё была ссылка. Состояние считается здесь же и по cfg.id, а не по
                # имени: name теоретически пуст, а cfg.id отсутствует ровно тогда, когда
                # заголовка нет. Три состояния различаются и в карточке, и в сводке.
                "       er.configuration_id, cfg.name AS configuration_name, "
                "       cfg.version AS configuration_version, "
                "       CASE WHEN er.configuration_id IS NULL THEN 'not_declared' "
                "            WHEN cfg.id IS NULL THEN 'dangling' "
                "            ELSE 'bound' END AS configuration_state "
                "FROM external_report er "
                "LEFT JOIN configurations cfg ON cfg.id = er.configuration_id "
                "WHERE er.uuid = %s::uuid LIMIT 1", (obj_uuid,))
            if not identity:
                return {"success": False,
                        "error": f"Внешний объект с uuid={obj_uuid} в external_report не найден",
                        "hint": "Сначала загрузите каталог: load_1c_catalog_tool(source_path=...), "
                                "далее generate_config_enrichment_tool(...) для сниппетов."}
            counts = fetch_rows(
                cur,
                "SELECT (SELECT count(*) FROM attributes a WHERE a.parent_uuid = %(u)s::uuid) AS attributes, "
                f"       (SELECT count(*) FROM attributes a WHERE a.parent_uuid = %(u)s::uuid "
                f"        AND {_OBJECT_ATTRIBUTES_ONLY}) AS object_attributes, "
                "       (SELECT count(*) FROM tabular_sections WHERE parent_uuid = %(u)s::uuid) AS tabular_sections, "
                "       (SELECT count(*) FROM forms WHERE parent_uuid = %(u)s::uuid) AS forms, "
                "       (SELECT count(*) FROM form_ext WHERE parent_uuid = %(u)s::uuid) AS form_ext, "
                "       (SELECT count(*) FROM templates WHERE parent_uuid = %(u)s::uuid) AS templates, "
                "       (SELECT count(*) FROM bsl_modules WHERE parent_uuid = %(u)s::uuid) AS bsl_modules, "
                # состав форм и событий считается по витринам — тем же источникам, что и разделы
                # ниже: счётчик в заголовке раздела обязан совпадать с числом строк в БД,
                # а не с числом строк, отданных под limit
                "       (SELECT count(*) FROM v_form_elements "
                "        WHERE report_uuid = %(u)s::uuid) AS form_elements, "
                "       (SELECT count(*) FROM v_form_events "
                "        WHERE report_uuid = %(u)s::uuid) AS form_events, "
                "       (SELECT count(*) FROM config_snippets WHERE parent_uuid = %(u)s::uuid) AS snippets, "
                "       (SELECT count(*) FROM config_aliases WHERE parent_uuid = %(u)s::uuid AND active) AS aliases, "
                "       (SELECT count(*) FROM config_cross_references "
                "        WHERE parent_uuid = %(u)s::uuid) AS doc_links",
                {"u": obj_uuid})[0]
            result = {"success": True, "uuid": obj_uuid, "object": identity[0], "counts": counts,
                      "caption": caption_of(identity[0].get("synonym")), "limit": limit}
            # Узел B: содержимое макетов-СКД считается по сохранённому templates.ext и входит
            # в counts наравне с прочими счётчиками — оно не зависит от limit. Перечень элементов
            # схемы карточка усечёт в слое форматирования, число элементов обязано быть настоящим.
            # При limit=0 разделы не отдаются (as before), но счётчики остаются полными.
            dcs = dcs_card_summary(cur, obj_uuid)
            counts.update(dcs["counters"])
            if not limit:
                return result
            result["dcs"] = dcs["templates"]
            return _describe_sections(cur, result, obj_uuid, limit)
    except Exception as exc:
        return {"success": False, "error": f"Карточка объекта не получена: {exc}"}

def _describe_sections(cur, result, obj_uuid, limit):
    """Разделы карточки по уже найденному объекту: содержимое, состав форм, сниппеты.

    Отделена от describe_object только из-за размера: запросы однотипные, поведение не меняет.
    Состав элементов и событий форм читается через витрины v_form_elements / v_form_events —
    те же источники, что и SQL-сверки (check_external_report_inventory.sql, разделы 10-10e).
    """
    params = {"u": obj_uuid, "l": limit}
    result["attributes"] = fetch_rows(
        cur,
        f"SELECT a.name, a.type, a.comment FROM attributes a "
        f"WHERE a.parent_uuid = %(u)s::uuid AND {_OBJECT_ATTRIBUTES_ONLY} "
        # порядок вставки = порядок обхода ChildObjects выгрузки; отдельной колонки позиции в
        # attributes нет (ordinal_position есть только в information_schema.attributes)
        f"ORDER BY a.id LIMIT %(l)s", params)
    result["tabular_sections"] = fetch_rows(
        cur,
        f"SELECT name, {_json_len_sql('column_uuids')} AS columns, comment "
        f"FROM tabular_sections WHERE parent_uuid = %(u)s::uuid ORDER BY name LIMIT %(l)s",
        params)
    result["forms"] = fetch_rows(
        cur,
        "SELECT f.name, f.form_type, fe.ext_format, fe.ext_path, "
        "       coalesce(length(fe.ext), 0) AS ext_chars, "
        "       coalesce(octet_length(fe.ext_bin), 0) AS ext_bytes, "
        f"       {_json_len_sql('fe.items')} AS items, "
        f"       {_json_len_sql('fe.attributes')} AS attributes, "
        f"       {_json_len_sql('fe.events')} AS events, "
        f"       {_json_len_sql('fe.commands')} AS commands "
        "FROM forms f LEFT JOIN form_ext fe ON fe.form_id = f.id "
        "WHERE f.parent_uuid = %(u)s::uuid ORDER BY f.name LIMIT %(l)s", params)
    result["form_elements"] = fetch_rows(
        cur,
        "SELECT form_name, element_name, element_type, data_source, caption_ru "
        "FROM v_form_elements WHERE report_uuid = %(u)s::uuid "
        "ORDER BY form_name, ordinal LIMIT %(l)s", params)
    result["form_events"] = fetch_rows(
        cur,
        "SELECT form_name, event_name, handler_name FROM v_form_events "
        "WHERE report_uuid = %(u)s::uuid ORDER BY form_name, ordinal LIMIT %(l)s", params)
    result["templates"] = fetch_rows(
        cur,
        "SELECT name, template_type, ext_root_tag, coalesce(length(ext), 0) AS ext_chars, "
        "       coalesce(octet_length(ext_bin), 0) AS ext_bytes "
        "FROM templates WHERE parent_uuid = %(u)s::uuid ORDER BY name LIMIT %(l)s", params)
    result["modules"] = fetch_rows(
        cur,
        "SELECT module_type, module_name, file_path, code_size, truncated "
        "FROM bsl_modules WHERE parent_uuid = %(u)s::uuid ORDER BY module_type, id LIMIT %(l)s",
        params)
    result["snippets"] = fetch_rows(
        cur,
        "SELECT id, question, source_kind, is_verified, length(answer) AS answer_chars "
        "FROM config_snippets WHERE parent_uuid = %(u)s::uuid ORDER BY id LIMIT %(l)s", params)
    return result








