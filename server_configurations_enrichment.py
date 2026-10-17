#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP-сервер 1c-configurations-enrichment — обогащение сохранённого содержимого выгрузок 1С.

Норматив: docs/config-scenarios/CONFIGURATIONS_ENRICHMENT_PLAN.md (узел V17).
Рабочий пример и порядок проверок: validate_enrichment_flow.py.

Таблицы (база ckb_1c_configurations, шаг 1b установки — src/ddl_enrichment.sql,
миграция migrate_v17_enrichment.sql): config_aliases, config_snippets,
config_snippet_dependencies, config_cross_references; витрины v_config_enrichment
(счётчики по объекту) и v_config_alias_targets (алиас вместе с его целью).

Внешний объект адресуется uuid (или source_path каталога выгрузки), а НЕ config_id:
`config_id` был в старой, никогда не работавшей версии сервера и идентификатора объекта
не давал (таблица configurations пуста, а enrichment-таблицы смотрят на external_report.uuid).

Инструментов 18, иных быть не должно (состав сторожит tools/check_mcp_tool_wiring.py):
  генерация и сводка : generate_config_enrichment_tool, config_enrichment_stats_tool
                       (вторая с uuid отдаёт ещё и карточку свойств объекта: имя, синоним,
                       комментарий, сгенерированный тип, основная СКД и формы по умолчанию,
                       реквизиты с типами, табличные части, состав форм и событий, макеты,
                       модули и перечень сниппетов — «что это, из чего состоит, как работает»;
                       читает src/enrichment_generator.py::describe_object, ничего не пишет)
  состав макета      : get_config_template_tool
  привязка к конфигурации: set_object_configuration_tool — привязку заявляет только
                       оператор, ссылка на configurations.id; внешнего ключа в схеме нет
                       (узел V20.1), поэтому существование заголовка проверяет этот
                       инструмент, а потерянная ссылка обнаруживается при чтении — карточка
                       объекта, сводка без uuid и генерация обогащения
  алиасы             : add_config_aliases_tool, search_config_aliases_tool,
                       resolve_config_alias_tool, list_config_aliases_tool,
                       delete_config_alias_tool
  сниппеты           : add_config_snippet_tool, get_config_snippet_tool,
                       list_config_snippets_tool, search_config_snippets_tool,
                       get_config_snippets_for_object_tool, delete_config_snippet_tool
  links documentation: add_config_cross_reference_tool, get_config_cross_references_tool,
                       delete_config_cross_reference_tool

Согласованность с `1c-knowledge-base` (server.py, local_doc.alias_targets / knowledge_snippets):

  | local_doc                                  | здесь                                                  |
  |--------------------------------------------|--------------------------------------------------------|
  | add_aliases_tool(aliases="a,b", groups_id=) | add_config_aliases_tool(aliases="a,b", uuid=...)        |
  | поиск по алиасам (rank 3.0)                 | search_config_aliases_tool / resolve_config_alias_tool  |
  | add_snippet_tool(question, answer, tags...) | add_config_snippet_tool(...) — плюс обязательные цели   |
  | soft-delete алиаса (active=false)           | delete_config_alias_tool (soft по умолчанию, hard=True) |

Различие принципиальное: enrich-сниппет обязан сослаться на цели сохранённого содержимого
(Attribute / TabularSection / Form / FormItem / Template / Module), поэтому находится и по
термину, и по объекту. Различие generated/manual: автоматическая перегенерация снимает только
авто-строки (origin='generated', is_verified=false); ручные алиасы (origin='manual') и ручные
сниппеты (is_verified=true) она не трогает и не восстанавливает.

⚠️ Файл ведётся ВРУЧНУЮ и НЕ перегенерируется: generate_servers.py терял блок импортов из
src/, из-за чего прежние версии этого сервера падали на NameError в каждом инструменте
(замер 13.10.2026). Контроль проводки — python tools/check_mcp_tool_wiring.py (он же встроен
в validate_project.py). Вся логика живёт в src/: enrichment_generator.py (генерация),
enrichment_aliases.py (алиасы), enrichment_snippets.py (сниппеты, зависимости, links).
Здесь только тонкие обёртки: разбор аргументов -> вызов функции из src/ -> карточка.
"""
import sys
from pathlib import Path
src_dir = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_dir))
from fastmcp import FastMCP

from enrichment_generator import (generate_enrichment, describe_object, type_brief,
                                 set_object_configuration)
from external_meta_parser import OBJECT_KIND_TITLES
from enrichment_aliases import (add_config_aliases, search_config_aliases, resolve_config_alias,
                                list_config_aliases, delete_config_alias)
from enrichment_snippets import (add_config_snippet, get_config_snippet, list_config_snippets,
                                 search_config_snippets, delete_config_snippet,
                                 mark_config_snippet, unmark_config_snippet,
                                 list_marked_config_snippets, get_snippets_for_object,
                                 add_config_cross_reference, get_config_cross_references,
                                 delete_config_cross_reference, enrichment_stats)
from enrichment_dcs import get_template_content
# Узел Q1 (карантин сниппетов, вариант A): тег пишется в шапке ответа сводки прямо, чтобы
# оператор видел, каким признаком снята строка, и не искал его в коде.
from quarantine import MARKER

mcp = FastMCP("1c-configurations-enrichment")

MAX_ROWS = 30      # строк списка в ответе — карточка не должна разрастаться
MAX_TEXT = 300     # длина вопроса/превью кода в списке


def _fail(res, verb):
    """Одна строка причины отказа + подсказка, если функция её подготовила."""
    lines = [f"❌ {verb}: {res.get('error', 'неизвестная ошибка')}"]
    if res.get('already_exists'):
        lines.append(f"Такая запись уже есть: id={res.get('id')}")
    if res.get('hint'):
        lines.append(f"Подсказка: {res['hint']}")
    if res.get('warning'):
        lines.append(f"Предупреждение: {res['warning']}")
    return "\n".join(lines)


def _obj_line(res):
    """Для какого объекта выгрузки сделана операция: имя + uuid.

    Узел V22: если слой src/ отдал вид объекта (object_kind), он печатается — оператор обязан
    видеть, что операция выполнена над обработкой, а не над отчётом: обе строки живут в одной
    таблице external_report, и по одному uuid этого не отличить.
    """
    if not res.get('uuid'):
        return ""
    name = res.get('object_name') or res.get('name') or ''
    kind = res.get('object_kind')
    kind_part = (f" | вид={res.get('object_kind_title') or OBJECT_KIND_TITLES.get(kind, kind)}"
                 f" ({kind})") if kind else ""
    return f"Объект: {name}{kind_part} | uuid={res.get('uuid')}"


def _counts(pairs):
    """Общий формат счётчиков 'ключ=N, ключ=N' для всех карточек."""
    return ", ".join(f"{key}={value}" for key, value in (pairs or {}).items())


def _clip(text, size=MAX_TEXT):
    """Одна строка текста фиксированной длины (вопросы и превью кода в списках)."""
    text = str(text or '').replace('\r', ' ').replace('\n', ' ').strip()
    return text if len(text) <= size else text[:size] + '…'


def _over_limit(rows, limit=MAX_ROWS):
    if len(rows) > limit:
        # строки не показаны — чтобы увидеть их, нужно увеличить limit (или сузить фильтр).
        # «уменьшите limit» здесь противоречило заголовку раздела («показано M из N,
        # увеличьте limit») и предлагало сделать ровно обратное.
        return [f"  … и ещё {len(rows) - limit} (уточните фильтр или увеличьте limit)"]
    return []


def _section_header(title, rows, counts, count_key):
    """Заголовок раздела карточки: сколько объектов в БД, а не сколько показано.

    Разделы карточки ограничены параметром `limit`, поэтому `len(rows)` бывает меньше
    реального числа объектов. Взять заголовок из `len(rows)` — значит соврать про состав
    объекта (замер 14.10.2026: при limit=4 раздел «ЭЛЕМЕНТЫ ФОРМ» показывал «(4)», хотя
    элементов в форме 6, а строкой выше тот же ответ сообщал «elements 6»). Число берём из
    `counts` (считается по БД без limit), усечение перечисляем явно.
    """
    total = len(rows)
    raw = (counts or {}).get(count_key)
    if raw is not None:
        try:
            total = int(raw)
        except (TypeError, ValueError):
            pass
    if len(rows) < total:
        return f"{title} (всего {total}, показано {len(rows)} — увеличьте limit):"
    return f"{title} ({total}):"


# =====================================================
# 1. ГЕНЕРАЦИЯ И СВОДКА
# =====================================================

@mcp.tool()
def generate_config_enrichment_tool(uuid: str = None, source_path: str = None):
    """Пересобрать алиасы и сниппеты объекта выгрузки из уже сохранённого содержимого.

    Источник — то, что лежит в БД после load_1c_catalog_tool: attributes, tabular_sections,
    forms, form_ext (items/attributes/events/commands), templates, bsl_modules. В конфигуратор
    1С объект не открывается. Одна транзакция: либо все строки, либо ни одной. Снимаются и
    создаются заново только авто-строки (origin='generated', is_verified=false); ручные алиасы
    и ручные сниппеты перегенерация не трогает. Нужен uuid или source_path каталога выгрузки.
    """
    try:
        res = generate_enrichment(uuid=uuid, source_path=source_path)
        if not res.get('success'):
            return _fail(res, "Обогащение не выполнено")
        totals = res.get('totals') or {}
        lines = ["♻️ Обогащение пересобрано (одна транзакция).",
                 f"Объект: {res.get('name')} | uuid={res.get('uuid')}", "",
                 f"Снято авто-строк: {_counts(res.get('removed'))}",
                 f"Создано: {_counts(res.get('created'))}",
                 f"Итого по объекту: алиасы {totals.get('aliases_total')}, "
                 f"сниппеты {totals.get('snippets_total')}",
                 f"Разобрано содержимого: {_counts(res.get('source_coverage'))}"]
        if res.get('skipped_duplicates'):
            lines.append(f"Пропущено сниппетов с тем же вопросом: {res['skipped_duplicates']}")
        for warning in res.get('warnings') or []:
            lines.append(f"⚠️ {warning}")
        lines.append("Дальше: config_enrichment_stats_tool (сводка), "
                     "search_config_aliases_tool (проверка находимости термина).")
        return "\n".join(lines)
    except Exception as exc:
        return f"❌ Внутренняя ошибка генерации обогащения: {exc}"


@mcp.tool()
def config_enrichment_stats_tool(uuid: str = None, limit: int = 20, card: bool = True):
    """Сводка по обогащению (витрина v_config_enrichment) плюс карточка свойств объекта.

    Без uuid — по всем объектам выгрузки плюс итоги по базе. С uuid — сначала карточка самого
    объекта (card=True, card=False — только обогащение): имя, синоним, комментарий,
    сгенерированный тип, основная СКД и формы по умолчанию из external_report; содержимое —
    реквизиты с типами, табличные части с числом колонок, формы с типом и составом элементов и
    событий (v_form_elements / v_form_events), макеты, BSL-модули и перечень сохранённых
    сниппетов (это «что делает код отчёта»). Затем — разбивка обогащения: алиасы по
    происхождению (generated/manual) и типам целей, сниппеты по источникам и is_verified,
    зависимости по типам целей, сироты (алиасы, оставшиеся после удаления сниппета).
    Витрина считает только то, что есть в БД: сколько терминов искал пользователь и не покрыл
    генератор, она не знает — для этого служит add_config_aliases_tool.
    """
    try:
        res = enrichment_stats(uuid=uuid, limit=limit)
        if not res.get('success'):
            return _fail(res, "Сводка не получена")
        objects = res.get('objects') or []

        def _obj_counters(row):
            # Карантин (узел Q1): общее число сниппетов остаётся полным, помеченные
            # показываются отдельной скобкой — «снято N» и «всего M» не должны смешиваться.
            marked = int(row.get('quarantine_snippets') or 0)
            return (f"алиасы {row.get('aliases_total')} "
                    f"(ручных {row.get('aliases_manual')}, на сниппеты {row.get('aliases_snippet')}), "
                    f"сниппеты {row.get('snippets')}"
                    + (f" (в карантине {marked})" if marked else "")
                    + f", зависимости {row.get('snippet_dependencies')}, "
                    f"links documentation {row.get('doc_links')}")

        if not uuid:
            totals = res.get('totals') or {}
            lines = [f"Итого по базе: объектов {totals.get('objects')}, алиасов {totals.get('aliases')}, "
                     f"сниппетов {totals.get('snippets')}, зависимостей {totals.get('dependencies')}, "
                     f"связей documentation {totals.get('doc_links')}",
                     f"Объектов в выборке: {len(objects)}"]
            # Узел V22: обе строки (отчёт и обработка) лежат в одной таблице-заголовке, поэтому
            # сводка обязана называть вид — иначе «объектов N» не отвечает на вопрос, чего именно.
            kinds = res.get('object_kinds') or []
            if kinds:
                lines.append("Виды объектов: " + ", ".join(
                    f"{OBJECT_KIND_TITLES.get(row.get('object_kind'), row.get('object_kind'))}"
                    f" ({row.get('object_kind')})={row.get('objects')}"
                    for row in kinds))
            for row in objects[:MAX_ROWS]:
                lines.append(f"  [{row.get('report_id')}] {row.get('report_name')} "
                             f"| вид={OBJECT_KIND_TITLES.get(row.get('object_kind'), row.get('object_kind'))} "
                             f"| uuid={row.get('report_uuid')} | {_obj_counters(row)}")
            lines += _over_limit(objects)
            lines += _binding_lines(res)
            lines += _quarantine_lines(totals)
            return "\n".join(lines)
        lines = []
        if card:
            card_res = describe_object(uuid=uuid, limit=limit)
            if card_res.get('success'):
                lines += _card_identity_lines(card_res)
                lines += _card_structure_lines(card_res)
                lines += _card_code_lines(card_res)
            else:
                lines.append(f"❌ Карточка объекта не получена: {card_res.get('error')}")
                if card_res.get('hint'):
                    lines.append(f"Подсказка: {card_res['hint']}")
            lines.append("")
        if not objects:
            lines.append(f"ОБОГАЩЕНИЕ ОБЪЕКТА uuid={uuid}: в v_config_enrichment строк нет — "
                         "обогатите объект generate_config_enrichment_tool(uuid=...), "
                         "затем повторите сводку.")
            return "\n".join(lines)
        lines.append(f"ОБОГАЩЕНИЕ ОБЪЕКТА uuid={uuid}")
        lines.append("  " + _obj_counters(objects[0]))
        lines.append("Алиасы по происхождению: "
                     + _counts({row.get('origin'): row.get('cnt')
                                for row in res.get('aliases_by_origin', [])}))
        lines.append("Цели алиасов по типам: "
                     + _counts({row.get('target_type'): row.get('cnt')
                                for row in res.get('aliases_by_target', [])}))
        lines.append("Сниппеты (source_kind/is_verified = количество [символов кода]): "
                     + ", ".join(f"{row.get('source_kind')}/{row.get('is_verified')}={row.get('cnt')}"
                                 f"[{row.get('answer_chars')}]"
                                 for row in res.get('snippets_by_source', [])))
        lines.append("Зависимости по типам целей: "
                     + _counts({row.get('target_type'): row.get('cnt')
                                for row in res.get('dependencies_by_target', [])}))
        orphans = (res.get('orphans') or [{}])[0].get('aliases_without_snippet')
        lines.append(f"Сироты (алиасы без сниппета): {orphans}")
        # Карантин (узел Q1): по объекту totals считаются им же, поэтому строка та же, что и
        # в сводке без uuid. Без неё «сниппеты N» читались бы как «все N рабочих».
        lines += _quarantine_lines(res.get('totals') or {})
        # карточка привязку уже назвала (_card_identity_lines); при card=False её не было,
        # поэтому состояние привязки печатается здесь — иначе объект остался бы без ответа
        # на вопрос «к какой конфигурации он привязан и цела ли ссылка»
        if not card:
            lines += _binding_lines(res)
        return "\n".join(lines)
    except Exception as exc:
        return f"❌ Внутренняя ошибка сводки по обогащению: {exc}"


def _quarantine_lines(totals):
    """Строка карантина сниппетов (узел Q1, вариант A).

    Помеченные `mark-for-deletion` строки остаются в базе и скрыты из поиска и перечней по
    умолчанию. Сводка обязана назвать их число явно: «сниппетов N» без этой строки читалось бы
    как «все N рабочих», а оператор не узнал бы, что часть снята как ошибочная. Пустой карантин
    не печатается — нулевая строка шума не даёт.
    """
    marked = int((totals or {}).get("quarantine_snippets") or 0)
    if not marked:
        return []
    return ["", f"КАРАНТИН СНИППЕТОВ (тег {MARKER}): помечено на удаление {marked}. "
                "Строки в базе, из поиска и перечней по умолчанию скрыты; видны по id "
                "(get_config_snippet_tool) и под include_marked=True. Снять пометку: "
                "unmark_config_snippet_tool(snippet_id); удалить совсем: "
                "python tools/purge_marked_snippets.py --apply (сначала без --apply — что снимет)."]


def _binding_lines(res):
    """Раздел привязок к конфигурации (узел V20.1).

    Состояний три, и все три печатаются прямо: «не заявлена», «привязана» и «битая» —
    последняя обязана требовать перепривязки, потому что внешнего ключа в схеме нет и
    потерянный заголовок возможен по построению. Заодно даётся обратный перечень: какие
    объекты привязаны к каждому заголовку (индекс по configuration_id для этого и нужен).
    """
    links = res.get("configuration_links") or []
    if not links:
        return []
    lines = ["", "ПРИВЯЗКИ К КОНФИГУРАЦИИ (ссылка — на configurations.id, id строки заголовка):"]
    for row in links[:MAX_ROWS]:
        state = row.get("configuration_state")
        cfg_id = row.get("configuration_id")
        head = f"  [{row.get('report_id')}] {row.get('report_name')} | uuid={row.get('report_uuid')}"
        if state == "bound":
            desc = f"configuration_id={cfg_id} — {row.get('configuration_name')}"
            if row.get("configuration_version"):
                desc += f" | версия {row['configuration_version']}"
            lines.append(f"{head}: {desc}")
        elif state == "dangling":
            lines.append(
                f"  ⚠️ [{row.get('report_id')}] {row.get('report_name')} "
                f"| uuid={row.get('report_uuid')}: БИТАЯ — configuration_id={cfg_id}, строки "
                "заголовка в configurations нет. Нужна перепривязка: "
                "set_object_configuration_tool(uuid=..., configuration_id=<id>) или снятие "
                "(configuration_id=None).")
        else:
            lines.append(f"{head}: не заявлена (NULL — это НЕ значит, что отчёт универсальный)")
    totals = res.get("totals") or {}
    if totals:
        lines.append(f"  Итого по базе: привязано {totals.get('configuration_bound', 0)}, "
                     f"битых {totals.get('configuration_dangling', 0)}, "
                     f"не заявлено {totals.get('configuration_not_declared', 0)}")
    configs = res.get("configurations")
    if configs:
        lines.append("  Заголовки конфигураций (id — то самое значение для привязки):")
        for row in configs[:MAX_ROWS]:
            lines.append(f"    id={row.get('id')} | {row.get('name')}"
                         + (f" | версия {row['version']}" if row.get("version") else "")
                         + f" | объектов привязано: {row.get('bound_objects')}")
    elif configs == []:
        lines.append("  Заголовки конфигураций: в configurations нет ни одной строки — "
                     "привязку заявить не на что.")
    return lines


@mcp.tool()
def get_config_template_tool(uuid: str = None, source_path: str = None, name: str = None,
                             template_id: int = None, include_query: bool = True):
    """Содержимое макета выгрузки: наборы данных, параметры, выражения, структура вывода.

    Разбирает сохранённый templates.ext (узел B): конфигуратор не открывается, схема БД не
    меняется, источник — только строки, записанные загрузчиком. Макет ищется по uuid объекта
    (+ name/template_id) — как в разделе МАКЕТЫ карточки; для объекта с одним макетом name
    не обязателен. Для макета-СКД показывается состав: наборы данных и их поля, связи наборов,
    параметры (и то, как они применяются в вариантах настроек), вычисляемые и итоговые поля,
    структура вывода. Если содержимое не разобрано (бинарный макет, обрезанный ext, битый XML,
    чужой корневой элемент) — называется причина: «не разобрано» и «в схеме этого нет» —
    разные ответы. Текст запроса набора данных отдаётся целиком до MAX_ANSWER символов.
    """
    try:
        res = get_template_content(uuid=uuid, source_path=source_path, name=name,
                                   template_id=template_id)
        if not res.get("success"):
            return _fail(res, "Содержимое макета не получено")
        row = res["template"]
        parsed = res["dcs"]
        lines = [_obj_line(res),
                 f"Макет: id={row['id']} | {row['name']} | uuid={row['uuid']}",
                 f"Содержимое: {row['ext_chars']} симв, {row['ext_bytes']} байт "
                 f"| root={row['ext_root_tag'] or '-'} | {row['ext_path'] or '-'}"
                 + (" | сохранено обрезанным" if row["ext_truncated"] else ""), ""]
        lines += _card_dcs_lines({"dcs": [res["dcs_entry"]]}, footer=False)
        if include_query and parsed.get("success"):
            for dataset in parsed["datasets"]:
                if not dataset["query"]:
                    continue
                query = dataset["query"]
                lines += ["", f"ЗАПРОС НАБОРА ДАННЫХ {dataset['name']} ({len(query)} симв):",
                          query[:MAX_ANSWER]]
                if len(query) > MAX_ANSWER:
                    lines.append(f"… обрезано до {MAX_ANSWER} символов, полный текст — "
                                 f"config_snippets.answer (template_query) или templates.ext.")
        if not parsed.get("success"):
            lines += ["", "Подсказка: содержимое макета в БД есть, но разбор не выполнен — "
                          "причина указана выше. Для бинарного макета (только ext_bin) разбор "
                          "схемы неприменим; для обрезанного ext нужно снять усечение на загрузке."]
        return "\n".join([line for line in lines if line is not None])
    except Exception as exc:
        return f"❌ Внутренняя ошибка чтения содержимого макета: {exc}"


# =====================================================
# 1b. ПРИВЯЗКА К КОНФИГУРАЦИИ (узел V20 / V20.1)
# =====================================================

@mcp.tool()
def set_object_configuration_tool(uuid: str = None, source_path: str = None,
                                  configuration_id: int = None):
    """Заявить или снять привязку внешнего объекта к конфигурации (configurations.id).

    Привязку заявляет ТОЛЬКО оператор: из выгрузки 1С она не восстанавливается, автоматического
    вывода и классификации («универсальный» / «параметризуемый» / «привязанный») нет.
    configuration_id — id строки заголовка конфигурации из таблицы configurations, а НЕ uuid
    метаданных 1С; какие заголовки есть — показывает config_enrichment_stats_tool без uuid
    (раздел «Заголовки конфигураций»). configuration_id=None — снять привязку: поле снова
    означает «привязка не заявлена», и это НЕ значит, что отчёт универсальный.

    Внешнего ключа в схеме нет (узел V20.1), поэтому существование заголовка проверяет этот
    инструмент: несуществующий id отклоняется, битой ссылки он не создаёт. Если заголовок
    удалён уже после установки привязки, ссылка становится битой — карточка объекта, сводка и
    генерация обогащения называют это прямо и требуют перепривязки; на чтение содержимого
    объекта это не влияет.
    """
    try:
        res = set_object_configuration(uuid=uuid, source_path=source_path,
                                       configuration_id=configuration_id)
        if not res.get('success'):
            return _fail(res, "Привязка не изменена")
        mode = res.get('mode')
        lines = [("✅ Привязка установлена" if mode == "bound" else "✅ Привязка снята")
                 + f": {res.get('object_name')} | uuid={res.get('uuid')}"]
        if mode == "bound":
            desc = f"configuration_id={res.get('configuration_id')} — {res.get('configuration_name')}"
            if res.get("configuration_version"):
                desc += f" | версия {res['configuration_version']}"
            lines.append(f"  Теперь: {desc}")
            lines.append(f"  К этой конфигурации привязано объектов: {res.get('bound_objects')}")
        else:
            lines.append("  Теперь: привязка не заявлена (NULL — это НЕ значит, что отчёт "
                         "универсальный)")
        previous = res.get('previous_configuration_id')
        lines.append(f"  Было: configuration_id={previous}" if previous is not None
                     else "  Было: привязка не заявлена")
        if res.get('note'):
            lines.append(f"  {res['note']}")
        lines.append("Дальше: config_enrichment_stats_tool(uuid=..., card=True) — карточка "
                     "покажает привязку; тот же вызов без uuid — обратный перечень.")
        return "\n".join(lines)
    except Exception as exc:
        return f"❌ Внутренняя ошибка привязки к конфигурации: {exc}"


# =====================================================
# 2. АЛИАСЫ (аналог local_doc.alias_targets + add_aliases_tool)
# =====================================================

def _alias_rows(rows):
    """Одна строка на алиас: [+]/[-] активен, цель, вес, происхождение (generated/manual)."""
    lines = []
    for row in rows[:MAX_ROWS]:
        mark = "+" if row.get("active", True) else "-"
        target = f"{row.get('target_type')}:{row.get('target_name')}"
        if row.get("target_snippet_id"):
            target += f" (сниппет {row.get('target_snippet_id')})"
        lines.append(f"  [{row.get('id')}] {mark} {row.get('alias_name')} -> {target} "
                     f"| weight {row.get('weight')} | {row.get('origin')}")
    lines += _over_limit(rows)
    return lines


@mcp.tool()
def add_config_aliases_tool(aliases: str, uuid: str = None, source_path: str = None,
                            target_type: str = None, target_name: str = None,
                            target_uuid: str = None, target_snippet_id: int = None,
                            description: str = None, weight: float = None):
    """Добавить ручные алиасы объекта выгрузки (origin='manual') — тот же контракт, что у add_aliases_tool.

    aliases — строка терминов через запятую; дубликаты не создаются (ON CONFLICT DO NOTHING),
    количество не ограничено (в отличие от автоалиасов сниппета). Ручные алиасы нужны там, где
    термина нет в выгрузке: русские формулировки, аббревиатуры, английские термины.
    Цель по умолчанию — сам внешний объект. Для цели на объект содержимого указывают
    target_type/target_name (Attribute, TabularSection, Form, FormItem, Template,
    Module — те же цели, что в зависимостях сниппетов); для цели на сниппет — target_snippet_id
    (тогда target_type='ConfigSnippet'). Нужен uuid или source_path каталога выгрузки.
    target_uuid цели инструмент подставляет сам по target_type+target_name (узел E) — указывать
    его вручную не нужно; несуществующая названная цель отклоняется, а не остаётся алиасом
    с пустым target_key. Модуль формы адресуется target_name='Form.<ИмяФормы>' или именем формы.
    """
    try:
        res = add_config_aliases(aliases=aliases, uuid=uuid, source_path=source_path,
                                 target_type=target_type, target_name=target_name,
                                 target_uuid=target_uuid, target_snippet_id=target_snippet_id,
                                 description=description, weight=weight)
        if not res.get('success'):
            return _fail(res, "Алиасы не добавлены")
        lines = [f"✅ Алиасы добавлены: создано {res.get('created')}, "
                 f"уже было {res.get('already_present')} (запрошено {res.get('requested')}).",
                 _obj_line(res),
                 f"Цель: {res.get('target_type')}:{res.get('target_name')} "
                 f"| target_uuid={res.get('target_uuid')} "
                 f"| target_snippet_id={res.get('target_snippet_id')} "
                 f"| weight={res.get('weight')}",
                 "Термины: " + ", ".join(res.get('aliases') or [])]
        return "\n".join([line for line in lines if line])
    except Exception as exc:
        return f"❌ Внутренняя ошибка добавления алиасов: {exc}"


@mcp.tool()
def search_config_aliases_tool(query: str, uuid: str = None, target_type: str = None,
                               limit: int = 20):
    """Найти алиасы и их цели по началу или середине термина (prefix + подстрока).

    Так работает поиск по alias_targets в 1c-knowledge-base: 'средн' найдёт 'средний возраст',
    'возраст' — тоже. uuid ограничивает выборку одним объектом выгрузки, target_type — типом
    цели (ExternalReport, Attribute, FormItem, ConfigSnippet, ...). Неактивные алиасы не
    отдаются. Точное совпадение — resolve_config_alias_tool.
    """
    try:
        res = search_config_aliases(query=query, uuid=uuid, target_type=target_type, limit=limit)
        if not res.get('success'):
            return _fail(res, "Алиасы не найдены")
        rows = res.get('rows') or []
        if not rows:
            return (f"❌ По запросу '{query}' активного алиаса нет.\n"
                    "Что дальше: search_docs_tool в 1c-knowledge-base; добавить алиас — "
                    "add_config_aliases_tool; список целей объекта — config_enrichment_stats_tool.")
        lines = [f"Найдено алиасов: {res.get('found')} по запросу '{query}'", _obj_line(res)]
        lines += _alias_rows(rows)
        return "\n".join([line for line in lines if line])
    except Exception as exc:
        return f"❌ Внутренняя ошибка поиска по алиасам: {exc}"


@mcp.tool()
def resolve_config_alias_tool(alias: str):
    """Разрешить алиас точно (по нормализованной форме имени) — аналог resolve_aliases из local_doc.

    Возвращает цели, на которые указывает алиас: объект выгрузки, его реквизит, табличная
    часть, форма, элемент формы, макет, модуль или enrich-сниппет. Для начала или середины
    слова используйте search_config_aliases_tool.
    """
    try:
        res = resolve_config_alias(alias=alias)
        if not res.get('success'):
            return _fail(res, "Алиас не разрешён")
        rows = res.get('rows') or []
        lines = [f"Алиас '{res.get('alias')}' разрешён: целей {res.get('found')}"]
        lines += _alias_rows(rows)
        return "\n".join(lines)
    except Exception as exc:
        return f"❌ Внутренняя ошибка разрешения алиаса: {exc}"


@mcp.tool()
def list_config_aliases_tool(uuid: str = None, target_type: str = None, origin: str = None,
                             limit: int = 50, include_inactive: bool = False):
    """Список алиасов объекта (или всех объектов) с фильтрами по цели и происхождению.

    origin='generated' — автоалиасы, 'manual' — добавленные оператором; include_inactive=True
    показывает и снятые мягкой операцией строки (active=false), чтобы видеть, что они не
    удалены физически. Для проверки находимости конкретного термина служит
    search_config_aliases_tool.
    """
    try:
        res = list_config_aliases(uuid=uuid, target_type=target_type, origin=origin, limit=limit,
                                  include_inactive=include_inactive)
        if not res.get('success'):
            return _fail(res, "Список алиасов не получен")
        rows = res.get('rows') or []
        if not rows:
            return "❌ Алиасов под такие фильтры нет."
        lines = [f"Алиасов: {res.get('found')}"
                 + (f" (объект uuid={uuid})" if uuid else " (по всем объектам)")]
        lines += _alias_rows(rows)
        return "\n".join(lines)
    except Exception as exc:
        return f"❌ Внутренняя ошибка списка алиасов: {exc}"


@mcp.tool()
def delete_config_alias_tool(alias_id: int, hard: bool = False):
    """Снять алиас. По умолчанию мягкое снятие (active=false) — как в local_doc.

    Soft-delete сохраняет строку: она видна в истории, поиск её не отдаёт, перегенерация не
    восстанавливает и не удаляет. hard=True — убрать ошибочный ручной алиас совсем.
    """
    try:
        res = delete_config_alias(alias_id=alias_id, hard=hard)
        if not res.get('success'):
            return _fail(res, "Алиас не удалён")
        lines = [f"✅ Алиас снят: режим {res.get('mode')}, id={res.get('id')}, "
                 f"имя '{res.get('alias_name')}'"]
        if res.get('note'):
            lines.append(res['note'])
        return "\n".join(lines)
    except Exception as exc:
        return f"❌ Внутренняя ошибка удаления алиаса: {exc}"


# =====================================================
# 3. СНИППЕТЫ И ЗАВИСИМОСТИ (аналог local_doc.knowledge_snippets)
# =====================================================

MAX_ANSWER = 8000      # символов кода в карточке сниппета: код бывает десятки КБ


def _dep_line(dep):
    return (f"    {dep.get('dependency_type', 'references')} "
            f"{dep.get('target_type')}:{dep.get('target_name')} "
            f"| target_uuid={dep.get('target_uuid')}")


@mcp.tool()
def add_config_snippet_tool(question: str, answer: str, uuid: str = None, source_path: str = None,
                            source_kind: str = "manual", source_uuid: str = None,
                            source_file: str = None, target_type: str = None,
                            target_uuid: str = None, tags: str = None, confidence: float = 1.0,
                            dependencies: str = None):
    """Добавить ручной сниппет по объекту выгрузки (is_verified=true) — аналог add_snippet_tool.

    Отличие от local_doc: сниппет обязан сослаться на сохранённое содержимое объекта, иначе он
    находится только по тексту и не привязывается к объекту. dependencies — строка вида
    'Type:Name; Type:Name', цели берутся из БД: Attribute (реквизит/колонка ТЧ), TabularSection,
    Form, FormItem ('ИмяФормы.ИмяЭлемента' — как его отдаёт витрина v_form_elements), Template,
    Module ('ObjectModule', 'ManagerModule', имя файла модуля или 'Form.<ИмяФормы>').
    Несуществующая цель — отказ, а не молчаливая связь вникуда; существующей цели автоматически
    проставляется стабильный target_uuid (тот же ключ, что у генератора и витрин).
    uuid или source_path — к какому объекту выгрузки относится сниппет. source_kind='manual'
    (ручной текст оператора) или 'file' (код из файла, source_file — путь). Ручной сниппет
    помечается is_verified=true и перегенерацией не снимается. tags — строка через запятую.
    """
    try:
        res = add_config_snippet(question=question, answer=answer, uuid=uuid, source_path=source_path,
                                 source_kind=source_kind, source_uuid=source_uuid,
                                 source_file=source_file, target_type=target_type,
                                 target_uuid=target_uuid, tags=tags, confidence=confidence,
                                 dependencies=dependencies)
        if not res.get('success'):
            return _fail(res, "Сниппет не добавлен")
        lines = [f"✅ Сниппет добавлен: id={res.get('id')}, код {res.get('answer_size')} симв.",
                 _obj_line(res),
                 f"Вопрос: {res.get('question')}",
                 f"Источник: {res.get('source_kind')} | is_verified={res.get('is_verified')}",
                 f"Зависимостей создано: {res.get('dependencies')}"
                 + (f", повторов целей снято: {res['duplicate_dependencies']}"
                    if res.get('duplicate_dependencies') else ""),
                 res.get('note') or ""]
        return "\n".join([line for line in lines if line])
    except Exception as exc:
        return f"❌ Внутренняя ошибка добавления сниппета: {exc}"


@mcp.tool()
def get_config_snippet_tool(snippet_id: int):
    """Полная карточка сниппета: код, зависимости, алиасы, ссылки на documentation.

    По карточке видно, на какие цели объекта указывает сниппет (с стабильными target_uuid),
    какие алиасы на него ведут и есть ли links в local_doc. Код отдаётся целиком до
    8000 символов, дальше — только длина (полный код читается SQL по config_snippets.answer).
    """
    try:
        res = get_config_snippet(snippet_id=snippet_id)
        if not res.get('success'):
            return _fail(res, "Сниппет не получен")
        row = res.get('row') or {}
        answer = str(row.get('answer') or '')
        lines = [f"Сниппет id={row.get('id')} | {row.get('question')}",
                 f"Объект: {row.get('object_name')} | uuid={row.get('parent_uuid')}",
                 f"Источник: {row.get('source_kind')} | {row.get('source_path') or row.get('source_uuid') or '-'} "
                 f"| is_verified={row.get('is_verified')} | confidence={row.get('confidence')}",
                 f"Теги: {', '.join(row.get('tags') or []) or '-'} | код {len(answer)} симв.", ""]
        # Узел Q1: карточка по id — единственная точка, куда оператор попадает за скрытой
        # строкой; она обязана назвать карантин и способ его снять, иначе «почему её нет в
        # поиске» пришлось бы угадывать.
        if row.get('marked'):
            lines.append(f"⚠️ Сниппет в карантине ({MARKER}): скрыт из поиска, списков и "
                         f"раздела «ЧТО ДЕЛАЕТ КОД» карточки объекта.")
            lines.append(f"   Причина: {row.get('marked_reason') or 'не указана'}")
            lines.append(f"   Снять: unmark_config_snippet_tool(snippet_id={row.get('id')}); "
                         f"удалить совсем: python tools/purge_marked_snippets.py --apply")
            lines.append("")
        lines.append("Код:")
        lines.append(answer[:MAX_ANSWER])
        if len(answer) > MAX_ANSWER:
            lines.append(f"… обрезано до {MAX_ANSWER} символов.")
        deps = row.get('dependencies') or []
        lines += ["", f"Зависимости ({len(deps)}):"] + [_dep_line(dep) for dep in deps[:MAX_ROWS]]
        lines += _over_limit(deps)
        aliases = row.get('aliases') or []
        lines += ["", f"Алиасы сниппета ({len(aliases)}):"] + [
            f"    [{a.get('id')}] {a.get('alias_name')} | weight {a.get('weight')} "
            f"| {a.get('origin')}" for a in aliases[:MAX_ROWS]]
        lines += _over_limit(aliases)
        links = row.get('doc_links') or []
        lines += ["", f"Ссылки documentation ({len(links)}):"] + [
            f"    [{x.get('id')}] {x.get('local_doc_kind')}#{x.get('local_doc_id')} "
            f"| {x.get('reference_type')}" for x in links[:MAX_ROWS]]
        return "\n".join(lines)
    except Exception as exc:
        return f"❌ Внутренняя ошибка получения сниппета: {exc}"


def _snippet_rows(res, rows):
    """Строки списка сниппетов: id, происхождение, вопрос, размер кода, зависимости.

    Узел Q1: строка в карантине помечается прямо в выдаче. Без пометки снятый сниппет
    (его отдают list/search при include_marked=True) визуально неотличим от рабочего,
    и оператор выбирает ошибочную строку, сам того не зная.
    """
    lines = []
    for row in rows[:MAX_ROWS]:
        verified = "verified" if row.get("is_verified") else "auto"
        mark = ""
        if row.get("marked"):
            reason = row.get("reason") or row.get("marked_reason") or ""
            mark = f" | ⚠️ помечен на удаление ({MARKER})" + (f": {reason}" if reason else "")
        lines.append(f"  [{row.get('id')}] {verified} | {row.get('source_kind')} "
                     f"| {row.get('dependencies')} зав. | {row.get('answer_size')} симв. "
                     f"| {_clip(row.get('question'))}" + mark)
    lines += _over_limit(rows)
    return lines


@mcp.tool()
def list_config_snippets_tool(uuid: str = None, source_kind: str = None, limit: int = 20,
                              only_verified: bool = False, include_marked: bool = False):
    """Список сниппетов объекта БЕЗ кода целиком (размер и начало): код бывает десятки КБ.

    source_kind='generated' — авто-сниппеты из сохранённых модулей и макета, 'manual'/'file' —
    добавленные оператором; only_verified=True — только ручные (их перегенерация не снимает).
    include_marked=True — показать и сниппеты в карантине (`mark-for-deletion`, узел Q1);
    по умолчанию они скрыты, а показанные помечаются «⚠️ помечен на удаление» и опускаются
    в конец выдачи. Полный код — get_config_snippet_tool.
    """
    try:
        res = list_config_snippets(uuid=uuid, source_kind=source_kind, limit=limit,
                                   only_verified=only_verified, include_marked=include_marked)
        if not res.get('success'):
            return _fail(res, "Список сниппетов не получен")
        rows = res.get('rows') or []
        if not rows:
            return "❌ Сниппетов под такие фильтры нет."
        lines = [f"Сниппетов: {res.get('found')}"
                 + (f" (объект uuid={uuid})" if uuid else " (по всем объектам)")
                 + (f" | в карантине ({MARKER}) показаны" if include_marked
                    else f" | карантин ({MARKER}) скрыт — include_marked=True")]
        lines += _snippet_rows(res, rows)
        return "\n".join(lines)
    except Exception as exc:
        return f"❌ Внутренняя ошибка списка сниппетов: {exc}"


@mcp.tool()
def search_config_snippets_tool(query: str, uuid: str = None, limit: int = 10,
                                include_marked: bool = False):
    """Полнотекстовый поиск по сниппетам (вопрос + код) — аналог search по knowledge_snippets.

    Отличие от 1c-knowledge-base: здесь у сниппета есть цели внутри объекта, поэтому тот же
    запрос находит и документацию языка, и код конкретного объекта выгрузки. Ограничение по
    объекту — uuid. Дальше по найденному сниппету — get_config_snippet_tool.

    Узел Q1: строки в карантине (`mark-for-deletion`) из поиска по умолчанию исключены;
    include_marked=True отдаёт их с явной пометкой и в конце выдачи.
    """
    try:
        res = search_config_snippets(query=query, uuid=uuid, limit=limit,
                                     include_marked=include_marked)
        if not res.get('success'):
            return _fail(res, "Поиск по сниппетам не выполнен")
        rows = res.get('rows') or []
        if not rows:
            return (f"❌ По запросу '{query}' enrich-сниппетов нет. По языку 1С ищите "
                    "search_docs_tool в 1c-knowledge-base."
                    + ("" if include_marked else
                       f" Карантин ({MARKER}) из поиска исключён — include_marked=True."))
        lines = [f"Найдено сниппетов: {res.get('found')} по запросу '{query}'"
                 + (f" | в карантине ({MARKER}) показаны" if include_marked
                    else f" | карантин ({MARKER}) скрыт — include_marked=True")]
        lines += _snippet_rows(res, rows)
        return "\n".join(lines)
    except Exception as exc:
        return f"❌ Внутренняя ошибка поиска по сниппетам: {exc}"


@mcp.tool()
def get_config_snippets_for_object_tool(uuid: str = None, source_path: str = None,
                                        target_type: str = None, target_name: str = None,
                                        include_marked: bool = False):
    """Найти сниппеты, которые ссылаются на конкретную цель объекта (по зависимостям).

    target_type/target_name — та же адресация цели, что в зависимостях и алиасах:
    Attribute, TabularSection, Form, FormItem ('ИмяФормы.ИмяЭлемента'), Template, Module.
    Отвечает на вопрос «что уже известно про этот реквизит/форму/макет» — например перед тем,
    как писать новый сниппет.

    Узел Q1: сниппеты в карантине (`mark-for-deletion`) в ответ по умолчанию не входят:
    вопрос «что известно» не должен отвечать строкой, которую оператор уже снял.
    include_marked=True отдаёт их с пометкой и в конце выдачи.
    """
    try:
        res = get_snippets_for_object(uuid=uuid, source_path=source_path, target_type=target_type,
                                      target_name=target_name, include_marked=include_marked)
        if not res.get('success'):
            return _fail(res, "Сниппеты цели не получены")
        rows = res.get('rows') or []
        lines = [f"Сниппетов, ссылающихся на {res.get('target_type')}:{res.get('target_name')}: "
                 f"{res.get('found')}", _obj_line(res),
                 (f"карантин ({MARKER}) показан" if include_marked
                  else f"карантин ({MARKER}) скрыт — include_marked=True")]
        lines += _snippet_rows(res, rows)
        return "\n".join([line for line in lines if line])
    except Exception as exc:
        return f"❌ Внутренняя ошибка поиска сниппетов по цели: {exc}"


@mcp.tool()
def delete_config_snippet_tool(snippet_id: int):
    """Удалить сниппет вместе с его алиасами, зависимостями и ссылками documentation.

    Удаляется всё, что висит на сниппете, — сироты в config_aliases не остаются. В ответе
    видно, сколько строк каждой таблицы снято, и предупреждение для авто-сниппета: следующая
    генерация создаст его заново из сохранённого кода (ручной, is_verified=true, — не создаст).
    """
    try:
        res = delete_config_snippet(snippet_id=snippet_id)
        if not res.get('success'):
            return _fail(res, "Сниппет не удалён")
        lines = [f"✅ Сниппет удалён: id={res.get('id')} ({res.get('source_kind')}, "
                 f"is_verified={res.get('is_verified')})",
                 f"Снято связанных строк: {_counts(res.get('children_deleted'))}",
                 res.get('note') or ""]
        return "\n".join([line for line in lines if line])
    except Exception as exc:
        return f"❌ Внутренняя ошибка удаления сниппета: {exc}"


# ── Карантин сниппетов (узел Q1, вариант A: зарезервированный тег mark-for-deletion) ──
# Тот же механизм, что в 1c-knowledge-base (mark_snippet_for_deletion_tool): строка остаётся
# в базе, но скрывается из поиска, списков и карточки. Разница только в таблице-природе:
# здесь hard-delete снимает ещё и алиасы, зависимости и ссылки на documentation, поэтому
# «пометить» — это единственный способ зафиксировать ошибочность, не теряя ответ оператора.

@mcp.tool()
def mark_config_snippet_tool(snippet_id: int, reason: str = None):
    """Пометить enrich-сниппет на удаление (узел Q1): строка остаётся, выдача её не отдаёт.

    Отличие от delete_config_snippet_tool: hard-delete снимает и саму строку, и её алиасы,
    зависимости, ссылки documentation — вместе с ней пропадает и ответ оператора. Пометка
    скрывает сниппет из search_config_snippets_tool, list_config_snippets_tool,
    get_config_snippets_for_object_tool и из раздела «ЧТО ДЕЛАЕТ КОД» карточки объекта, но
    строка остаётся доступной по id и в перечне карантина. Причина кладётся вторым тегом
    `mark-for-deletion:reason=…` (колонки под причину вариант A не заводит).
    Для авто-сниппета признак переживает перегенерацию: генератор переносит его по совпадению
    идентичности (parent_uuid + source_kind + source_uuid + question, узел Q2).
    """
    try:
        res = mark_config_snippet(snippet_id=snippet_id, reason=reason)
        if not res.get('success'):
            return _fail(res, "Сниппет не помечен")
        lines = [f"✅ Сниппет помечен на удаление: id={res.get('id')} "
                 f"({res.get('source_kind')}, is_verified={res.get('is_verified')})",
                 _obj_line(res),
                 f"Вопрос: {res.get('question')}",
                 f"Причина: {res.get('reason') or 'не указана'}",
                 f"Признак: {MARKER}"
                 + (f", {MARKER}:reason=…" if res.get('reason') else ""),
                 res.get('note') or ""]
        return "\n".join([line for line in lines if line])
    except Exception as exc:
        return f"❌ Внутренняя ошибка пометки сниппета: {exc}"


@mcp.tool()
def unmark_config_snippet_tool(snippet_id: int):
    """Снять пометку «на удаление» с enrich-сниппета (метку и тег причины).

    Строка возвращается в поиск, списки и карточку объекта. Если строка не помечена,
    инструмент отвечает отказом с прямым текстом («снимать нечего») — молча он ничего не меняет.
    """
    try:
        res = unmark_config_snippet(snippet_id=snippet_id)
        if not res.get('success'):
            return _fail(res, "Признак не снят")
        lines = [f"✅ Пометка снята: id={res.get('id')} ({res.get('source_kind')}, "
                 f"is_verified={res.get('is_verified')})",
                 _obj_line(res),
                 f"Вопрос: {res.get('question')}",
                 res.get('note') or ""]
        return "\n".join([line for line in lines if line])
    except Exception as exc:
        return f"❌ Внутренняя ошибка снятия пометки: {exc}"


@mcp.tool()
def list_marked_config_snippets_tool(uuid: str = None, limit: int = 50):
    """Перечень enrich-сниппетов, помеченных на удаление (разбор перед чисткой).

    Показывает то, что удалит tools/purge_marked_snippets.py: id, объект, вопрос, источник,
    признак is_verified и причину. Ограничение по объекту — uuid. Пустой ответ означает, что
    чистить нечего; это НЕ означает, что ошибочных строк нет — они могли быть удалены сразу.
    """
    try:
        res = list_marked_config_snippets(uuid=uuid, limit=limit)
        if not res.get('success'):
            return _fail(res, "Перечень карантина не получен")
        rows = res.get('rows') or []
        if not rows:
            return f"✅ Сниппетов, помеченных на удаление ({MARKER}), нет — чистить нечего."
        lines = [f"Помечено на удаление ({MARKER}): {res.get('found')}"
                 + (f" (объект uuid={uuid})" if uuid else " (по всем объектам)")]
        for row in rows[:MAX_ROWS]:
            verified = "verified" if row.get("is_verified") else "auto"
            lines.append(f"  [{row.get('id')}] {row.get('object_name') or row.get('parent_uuid')} "
                         f"| {verified} | {row.get('source_kind')} "
                         f"| {row.get('answer_size')} симв. | {_clip(row.get('question'))}"
                         f" | причина: {row.get('reason') or 'не указана'}")
        lines += _over_limit(rows)
        lines.append(f"Снять: unmark_config_snippet_tool(snippet_id). Удалить совсем: "
                     f"python tools/purge_marked_snippets.py --apply (без --apply — что снимет).")
        return "\n".join(lines)
    except Exception as exc:
        return f"❌ Внутренняя ошибка перечня карантина: {exc}"


# =====================================================
# 4. СВЯЗИ DOCUMENTATION (local_doc <-> содержимое объекта выгрузки)
# =====================================================

@mcp.tool()
def add_config_cross_reference_tool(uuid: str = None, source_path: str = None,
                                    local_doc_kind: str = "group", local_doc_id: int = None,
                                    target_type: str = None, target_name: str = None,
                                    target_uuid: str = None, reference_type: str = "linked_to"):
    """Поставить указатель documentation (local_doc) -> конкретная цель объекта выгрузки.

    local_doc_kind='group' (справочник языка/платформы, id из groups) или 'snippet'
    (id из knowledge_snippets). Цель по умолчанию — сам объект выгрузки, а его тип цели
    берётся из вида строки заголовка (узел V22): ExternalReport для отчёта и
    ExternalProcessing для обработки; явно указанный тип другого вида отклоняется. Для цели на
    enrich-сниппет указывают target_type='ConfigSnippet' и target_uuid='snippet:<id>' (ту же
    запись цели читает get_config_snippet_tool). Для цели внутри объекта (Template, Module, Form,
    Attribute, …) достаточно target_type+target_name: инструмент разрешает цель и заполняет
    target_uuid сам (узел E) — якорь переживает перегенерацию и не остаётся слепой зоной;
    несуществующая названная цель отклоняется. Модуль формы — target_name='Form.<ИмяФормы>'
    или имя формы. Указатель проверяется в базе local_doc: битый
    id не сохраняется, чтобы связь вникуда не замусоривала анализ. Дубликат не создаётся.
    Это то, чего не хватало в старом register_cross_reference_tool: он ссылался на
    configuration_id, которого в схеме нет.
    """
    try:
        res = add_config_cross_reference(uuid=uuid, source_path=source_path,
                                         local_doc_kind=local_doc_kind, local_doc_id=local_doc_id,
                                         target_type=target_type, target_name=target_name,
                                         target_uuid=target_uuid, reference_type=reference_type)
        if not res.get('success'):
            return _fail(res, "Связь не создана")
        lines = [f"✅ Связь создана: id={res.get('id')}",
                 _obj_line(res),
                 f"local_doc: {res.get('local_doc_kind')}#{res.get('local_doc_id')}"
                 + (f" — {res.get('local_doc_title')}" if res.get('local_doc_title') else ""),
                 f"Цель: {res.get('target_type')}:{res.get('target_name')} "
                 f"| target_uuid={res.get('target_uuid')} | {res.get('reference_type')}"]
        return "\n".join([line for line in lines if line])
    except Exception as exc:
        return f"❌ Внутренняя ошибка создания связи: {exc}"


@mcp.tool()
def get_config_cross_references_tool(uuid: str = None, local_doc_id: int = None, limit: int = 50):
    """Прочитать связи documentation: по объекту выгрузки (uuid) или по элементу local_doc_id.

    Каждая строка сопровождается проверкой указателя в local_doc: связь могла остаться после
    пересоздания базы документации, и отдавать её как валидную — значит врать. Нужен хотя бы
    один из фильтров.
    """
    try:
        res = get_config_cross_references(uuid=uuid, local_doc_id=local_doc_id, limit=limit)
        if not res.get('success'):
            return _fail(res, "Связи не получены")
        rows = res.get('rows') or []
        if not rows:
            return "❌ Связей под такие фильтры нет."
        lines = [f"Связей: {res.get('found')}"]
        for row in rows[:MAX_ROWS]:
            state = "ok" if row.get("local_doc_found") else "БЫЙ УКАЗАТЕЛЬ"
            title = f" — {row.get('local_doc_title')}" if row.get("local_doc_title") else ""
            lines.append(f"  [{row.get('id')}] {row.get('local_doc_kind')}#{row.get('local_doc_id')}"
                         f"{title} | {state} -> {row.get('target_type')}:{row.get('target_name')} "
                         f"| объект {row.get('object_name')}")
            if row.get("local_doc_note"):
                lines.append(f"      {row['local_doc_note']}")
        lines += _over_limit(rows)
        return "\n".join(lines)
    except Exception as exc:
        return f"❌ Внутренняя ошибка чтения связей: {exc}"


@mcp.tool()
def delete_config_cross_reference_tool(reference_id: int):
    """Снять связь documentation (указатель нужен для чтения, FK в схеме здесь ни при чём)."""
    try:
        res = delete_config_cross_reference(reference_id=reference_id)
        if not res.get('success'):
            return _fail(res, "Связь не удалена")
        return (f"✅ Связь удалена: id={res.get('id')} — "
                f"{res.get('local_doc_kind')}#{res.get('local_doc_id')} -> {res.get('target_type')}")
    except Exception as exc:
        return f"❌ Внутренняя ошибка удаления связи: {exc}"


def _card_identity_lines(res):
    """Шапка карточки: что это за объект и сколько в нём чего."""
    obj = res.get("object") or {}
    counts = res.get("counts") or {}
    lines = ["КАРТОЧКА ОБЪЕКТА (по сохранённой выгрузке, без конфигуратора)",
             f"  [{obj.get('report_id')}] {obj.get('name')} | uuid={obj.get('uuid')}"]
    # Узел V22: вид строки заголовка. Внешний отчёт и внешняя обработка лежат в одной таблице,
    # поэтому карточка обязана сказать, чем является объект: без этой строки карточка обработки
    # читалась бы как карточка отчёта, у которого «пропали» свойства отчёта.
    object_kind = str(res.get("object_kind") or obj.get("object_kind") or "external_report")
    lines.append(f"  Вид объекта: {OBJECT_KIND_TITLES.get(object_kind, object_kind)} "
                 f"(object_kind='{object_kind}', строка таблицы external_report)")
    kind = str(obj.get("generatedtype_category") or "")
    if obj.get("generatedtype_name"):
        kind = f"{kind} ({obj['generatedtype_name']})" if kind else str(obj["generatedtype_name"])
    if kind:
        lines.append(f"  Сгенерированный тип: {kind}")
    if res.get("caption"):
        lines.append(f"  Синоним (назначение в интерфейсе): {res['caption']}")
    if obj.get("comment"):
        lines.append(f"  Комментарий из выгрузки: {_clip(obj['comment'], 500)}")

    # узел V20 / V20.1: привязка к конфигурации. Состояний ровно три, и все три названы явно:
    # «не заявлена» (NULL), «привязано» (строка заголовка есть) и «битая» (значение осталось,
    # а заголовок удалён). Третье состояние появилось вместе со снятием FK (узел V20.1): оно
    # возможно по построению, поэтому карточка обязана назвать его и указать действие —
    # перепривязку. «Универсальный» здесь не пишется никогда: такого состояния в модели нет,
    # автоматического вывода нет.
    cfg_id = obj.get("configuration_id")
    state = str(obj.get("configuration_state") or
                ("not_declared" if not cfg_id else
                 ("bound" if obj.get("configuration_name") else "dangling")))
    if state == "bound" and cfg_id:
        bound = str(obj.get("configuration_name") or "?")
        if obj.get("configuration_version"):
            bound += f" | версия {obj['configuration_version']}"
        lines.append(f"  Привязка к конфигурации: configuration_id={cfg_id} — {bound}")
    elif state == "dangling" and cfg_id:
        lines.append(f"  ⚠️ Привязка к конфигурации: БИТАЯ — configuration_id={cfg_id}, строки "
                     "заголовка конфигурации в configurations нет (внешнего ключа в схеме нет "
                     "осознанно, узел V20.1). Требуется перепривязка: "
                     "set_object_configuration_tool(uuid=..., configuration_id=<id>) или снятие "
                     "привязки (configuration_id=None).")
    else:
        lines.append("  Привязка к конфигурации: не заявлена (NULL = привязки нет; это НЕ значит, "
                     "что отчёт универсальный — состояние «универсальный» в модели отсутствует)")

    properties = []
    for label, key in (("основная СКД", "main_data_composition_schema"),
                       ("форма по умолчанию", "default_form"),
                       ("форма настроек", "default_settings_form"),
                       ("вспомогательная форма", "auxiliary_form")):
        if obj.get(key):
            properties.append(f"{label}: {obj[key]}")
    if properties:
        lines.append("  Свойства: " + "; ".join(properties))
    elif object_kind == "external_report":
        lines.append("  Свойств объекта в выгрузке нет (основная СКД, форма по умолчанию, форма "
                     "настроек, вспомогательная форма) — это состояние объекта, а не пропуск разбора.")
    if object_kind == "external_processing":
        # Узел V22: у внешней обработки свойств СКД и настроек нет в принципе (в выгрузке они не
        # выгружаются), а не «не разобраны». Форма по умолчанию и реквизиты при этом самые обычные.
        # Сказать, что именно не применяется, — значит не оставить читателя с ложным ощущением
        # неполных данных (карточка обработки не должна читаться как карточка отчёта с пробелами).
        lines.append("  Свойства: основная СКД, форма настроек и хранилище вариантов к внешней "
                     "обработке не применяются — в выгрузке их нет (это не пропуск данных).")

    names = {"object_attributes": "реквизитов объекта", "attributes": "строк attributes",
             "tabular_sections": "табличных частей", "forms": "форм",
             "form_ext": "описаний форм", "templates": "макетов",
             "bsl_modules": "BSL-модулей", "aliases": "активных алиасов",
             "snippets": "сниппетов", "doc_links": "links documentation"}
    lines.append("СОДЕРЖИМОЕ: " + ", ".join(
        f"{names[key]} {counts.get(key, 0)}" for key in names))
    return lines



def _card_code_lines(res):
    """Раздел «что делает код»: перечень сохранённых enrich-сниппетов объекта."""
    snippets = res.get("snippets") or []
    if not snippets:
        return ["Сниппетов нет: принцип работы по коду не описан. "
                "Вызовите generate_config_enrichment_tool(uuid=...)."]
    lines = [_section_header("ЧТО ДЕЛАЕТ КОД, enrich-сниппеты", snippets,
                             res.get("counts") or {}, "snippets")]
    for row in snippets[:MAX_ROWS]:
        origin = "ручной" if row.get("is_verified") else str(row.get("source_kind"))
        # Карантин (узел Q1): помеченная строка остаётся в перечне (карточка описывает
        # состояние объекта целиком), но обязана читаться снятой — иначе раздел кода
        # выдавал бы ошибочный сниппет за рабочий.
        mark = ""
        if row.get("marked"):
            mark = f" | ⚠️ помечен на удаление ({MARKER})"
            if row.get("marked_reason"):
                mark += f": {_clip(row['marked_reason'], 120)}"
        lines.append(f"  [{row.get('id')}] {_clip(row.get('question'), MAX_TEXT)} "
                     f"| {origin} | {row.get('answer_chars')} симв{mark}")
    lines += _over_limit(snippets)
    marked_total = int((res.get("counts") or {}).get("snippets_marked") or 0)
    if marked_total:
        lines.append(f"  Из них в карантине ({MARKER}): {marked_total} — скрыты из поиска и "
                     "перечней по умолчанию; снять: unmark_config_snippet_tool(snippet_id).")
    lines.append("Дальше по коду: get_config_snippet_tool(snippet_id) — полный код и цели; "
                 "search_config_snippets_tool(query) — поиск по тексту сниппетов.")
    return lines


def _card_dcs_lines(res, footer=True):
    """Раздел «содержимое макетов СКД» (узел B): читается из сохранённого templates.ext.

    Заголовки считают элементы по счётчикам разбора, а не по показанным строкам: перечень
    ограничен MAX_ROWS, число элементов схемы обязано быть настоящим (то же правило, что у
    `_section_header` для разделов формы). Неразобранный макет показывается с причиной —
    «не разобрано» и «в схеме этого нет» не должны выглядеть одинаково.

    `footer=False` — для get_config_template_tool: он и есть тот инструмент, на который
    сноска ссылается, повторять её в его собственном ответе не нужно.
    """
    entries = res.get("dcs") or []
    if not entries:
        return []
    lines = []
    for entry in entries:
        lines.append("")
        head = (f"СОДЕРЖИМОЕ МАКЕТА {entry.get('name')} "
                f"| {entry.get('root_tag') or 'DataCompositionSchema'} "
                f"| {entry.get('ext_chars')} симв, {entry.get('ext_bytes')} байт")
        if entry.get("truncated"):
            head += " | содержимое сохранено обрезанным"
        lines.append(head)
        if not entry.get("parsed"):
            lines.append(f"  ❌ Схема не разобрана: {entry.get('reason')}")
            continue
        dcs = entry["counts"]
        lines.append("  " + _counts({
            "источников": dcs["data_sources"], "наборов": dcs["datasets"],
            "полей наборов": dcs["dataset_fields"], "связей наборов": dcs["dataset_links"],
            "параметров": dcs["parameters"], "вычисляемых полей": dcs["calculated_fields"],
            "итоговых полей": dcs["total_fields"],
            "вариантов настроек": dcs["settings_variants"],
            "полей вывода": dcs["output_fields"]}))

        datasets = entry["datasets"]
        lines.append(_section_header("  НАБОРЫ ДАННЫХ", datasets, dcs, "datasets"))
        for row in datasets[:MAX_ROWS]:
            extra = [f"источник {row['data_source'] or '-'}"]
            if row["object_name"]:
                extra.append(f"объект {row['object_name']}")
            if row["query"]:
                extra.append(f"запрос {len(row['query'])} симв")
            if row["filters"]:
                extra.append(f"отборов {row['filters']}")
            if row["selections"]:
                extra.append(f"условий отбора {row['selections']}")
            if row["orders"]:
                extra.append(f"сортировок {row['orders']}")
            if row["groups"]:
                extra.append(f"группировок {row['groups']}")
            lines.append(f"    - {row['name']} | {row['kind']} | полей {row['field_count']} | "
                         + "; ".join(extra))
            # Поля набора — то, из чего состоят выражения полей вывода и отборов: без них
            # «полей 32» остаётся числом, а не составом. Перечень усечён MAX_ROWS, как и
            # остальные разделы; полное число — в счётчике выше.
            for field in (row["fields"] or [])[:MAX_ROWS]:
                bits = [field["name"] or field["data_path"] or "без имени"]
                if field["kind"]:
                    bits.append(f"вид {field['kind']}")
                if field["value_type"]:
                    bits.append("тип " + ",".join(field["value_type"]))
                if field["caption"]:
                    bits.append(f"подпись {_clip(field['caption'], 80)}")
                lines.append("      * " + " | ".join(bits))
            lines += _over_limit(row["fields"] or [])
        lines += _over_limit(datasets)

        links = entry["dataset_links"]
        if links:
            lines.append(f"  СВЯЗИ НАБОРОВ ({len(links)}):")
            for row in links[:MAX_ROWS]:
                lines.append(f"    - {row['source_dataset']}.{row['source_expression']} = "
                             f"{row['destination_dataset']}.{row['destination_expression']}"
                             + (f" | {row['join_type']}" if row["join_type"] else ""))
            lines += _over_limit(links)

        parameters = entry["parameters"]
        if parameters:
            lines.append(_section_header("  ПАРАМЕТРЫ", parameters, dcs, "parameters"))
            for row in parameters[:MAX_ROWS]:
                # usage уже собран в разборе: там видно и объявление без <condition>, и
                # выключение параметра вариантом настроек (use=false), и значение по
                # умолчанию. Пересобирать его здесь — значит получить два разных ответа
                # об одном параметре (карточку и разбор).
                value_type = ",".join(row["value_type"]) or "тип не указан"
                lines.append(f"    - {row['name']} | {_clip(row['caption'], 80) or 'без подписи'} "
                             f"| {value_type} | {row['usage']}")
                for applied in (row["settings_usage"] or [])[:MAX_ROWS]:
                    if applied["use"].lower() == "false":
                        state = "выключен (use=false)"
                    elif applied["nil"] == "true":
                        state = "значение не задано (nil)"
                    elif applied["value"]:
                        state = f"значение по умолчанию {_clip(applied['value'], 80)}"
                    else:
                        state = "упомянут без значения"
                    lines.append(f"      * вариант «{applied['variant']}»: {state}")
            lines += _over_limit(parameters)
        calculated = entry["calculated_fields"]
        if calculated:
            lines.append(_section_header("  ВЫЧИСЛЯЕМЫЕ ПОЛЯ", calculated, dcs,
                                         "calculated_fields"))
            for row in calculated[:MAX_ROWS]:
                bits = [f"{row['data_path']} = {_clip(row['expression'], MAX_TEXT)}"]
                if row["selection"]:
                    bits.append(f"условие отбора {_clip(row['selection'], MAX_TEXT)}")
                if row["having"]:
                    bits.append(f"после группировки {_clip(row['having'], MAX_TEXT)}")
                if row["groups"]:
                    bits.append("группировка " + "; ".join(row["groups"]))
                lines.append("    - " + " | ".join(bits))
            lines += _over_limit(calculated)

        totals = entry["total_fields"]
        if totals:
            lines.append(_section_header("  ИТОГОВЫЕ ПОЛЯ", totals, dcs, "total_fields"))
            for row in totals[:MAX_ROWS]:
                group = " | группа " + "; ".join(row["groups"]) if row["groups"] else ""
                lines.append(f"    - {row['data_path']} = {_clip(row['expression'], MAX_TEXT)}"
                             f"{group}"
                             + (f" | вид {row['total_ver']}" if row["total_ver"] else ""))
            lines += _over_limit(totals)

        for variant in entry["settings_variants"]:
            details = variant["details"]
            vd = variant["counts"]
            lines.append(f"  ВАРИАНТ НАСТРОЕК {variant['name']} | " + _counts({
                "уровней структуры": vd["structure_levels"],
                "группировок структуры": vd["structure_groups"],
                "сортировок": vd["orders"], "отборов": vd["filters"],
                "применений параметров": vd["data_parameters"],
                "значений выходных параметров": vd["output_parameters"]}))
            for row in details["structure"][:MAX_ROWS]:
                groups = "; ".join(
                    str(item["field"])
                    + (f" [{item['group_type']}]" if item["group_type"] not in ("", "Items") else "")
                    for item in row["groups"]) or "группировок нет"
                orders = "; ".join(
                    f"{item['field'] or item['kind']} {item['direction']}".strip()
                    for item in row["orders"])
                if orders:
                    groups += f" | сортировка: {orders}"
                lines.append(f"    - уровень {row['level']}: {groups}")
            lines += _over_limit(details["structure"])
            for row in details["orders"][:MAX_ROWS]:
                lines.append(f"    - сортировка вывода: {row['field'] or row['kind']} "
                             f"{row['direction']}")
            for row in details["data_parameters"][:MAX_ROWS]:
                if row["use"].lower() == "false":
                    state = "выключен (use=false)"
                elif row["nil"] == "true":
                    state = "значение не задано (nil)"
                else:
                    state = f"значение {row['value'] or '(пусто)'}"
                lines.append(f"    - параметр {row['parameter']}: {state}")
            for row in details["output_parameters"][:MAX_ROWS]:
                lines.append(f"    - выходной параметр {row['parameter']} "
                             f"[{row['value_type'] or 'тип не указан'}]: "
                             f"{_clip(row['value'] or '(пусто)', 80)}")
            for row in details["filters"][:MAX_ROWS]:
                lines.append(f"    - отбор: {_clip(' '.join(
                    part for part in (row['left'], row['comparison_type'], row['right'])
                    if part), MAX_TEXT)}")

        output = entry["output"]
        if output:
            lines.append(_section_header("  СТРУКТУРА ВЫВОДА", output, dcs, "output_fields"))
            for row in output[:MAX_ROWS]:
                lines.append(f"    - {row['folder'] or 'без группы'} -> {row['field']}")
            lines += _over_limit(output)

        unparsed = {key: value for key, value in entry["unparsed"].items() if value}
        if unparsed:
            lines.append("  НЕ РАЗОБРАНО (элементы схемы есть, состав из них не извлечён): "
                         + _counts(unparsed))
        for warning in entry["warnings"][:MAX_ROWS]:
            lines.append(f"  ⚠️ {warning}")
    if footer:
        lines.append("")
        lines.append("Дальше по составу макета: get_config_template_tool(uuid=..., name=<макет>) — "
                     "полный разбор содержимого; текст запроса набора данных ищется через "
                     "search_config_snippets_tool.")
    return lines


def _card_structure_lines(res):
    """Разделы содержимого: реквизиты, ТЧ, формы и их состав, макеты, модули.

    Заголовки считают содержимое по `counts` (число строк в БД), а не по показанным строкам:
    разделы ограничены `limit`, усечение перечисляется явно — иначе заголовок врёт о составе.
    """
    counts = res.get("counts") or {}
    lines = []
    attributes = res.get("attributes") or []
    if attributes:
        lines.append(_section_header("РЕКВИЗИТЫ ОБЪЕКТА", attributes, counts, "object_attributes"))
        for row in attributes[:MAX_ROWS]:
            brief = type_brief(row.get("type")) or "тип не разобран"
            note = f" | {_clip(row.get('comment'), 120)}" if row.get("comment") else ""
            lines.append(f"  - {row.get('name')} | {brief}{note}")
        lines += _over_limit(attributes)

    sections = res.get("tabular_sections") or []
    if sections:
        lines.append(_section_header("ТАБЛИЧНЫЕ ЧАСТИ", sections, counts, "tabular_sections"))
        for row in sections[:MAX_ROWS]:
            note = f" | {_clip(row.get('comment'), 120)}" if row.get("comment") else ""
            lines.append(f"  - {row.get('name')} | колонок {row.get('columns')}{note}")
        lines += _over_limit(sections)

    forms = res.get("forms") or []
    if forms:
        lines.append(_section_header("ФОРМЫ", forms, counts, "forms"))
        for row in forms[:MAX_ROWS]:
            source = row.get("ext_format") or "нет содержимого"
            if row.get("ext_path"):
                source = f"{source} ({row['ext_path']})"
            lines.append(
                f"  - {row.get('name')} | {row.get('form_type')} | {source} | "
                f"модуль {row.get('ext_chars')} симв, контейнер {row.get('ext_bytes')} байт | "
                f"elements {row.get('items')}, sources {row.get('attributes')}, "
                f"events {row.get('events')}, commands {row.get('commands')}")
        lines += _over_limit(forms)

    elements = res.get("form_elements") or []
    if elements:
        lines.append(_section_header("ЭЛЕМЕНТЫ ФОРМ через v_form_elements", elements,
                                     counts, "form_elements"))
        for row in elements[:MAX_ROWS]:
            extra = []
            if row.get("data_source"):
                extra.append(f"источник {row['data_source']}")
            if row.get("caption_ru"):
                extra.append(f"подпись {_clip(row['caption_ru'], 60)}")
            tail = (" | " + "; ".join(extra)) if extra else ""
            lines.append(f"  - {row.get('form_name')}/{row.get('element_name')} "
                         f"| {row.get('element_type')}{tail}")
        lines += _over_limit(elements)

    events = res.get("form_events") or []
    if events:
        lines.append(_section_header("СОБЫТИЯ ФОРМ через v_form_events", events,
                                     counts, "form_events"))
        for row in events[:MAX_ROWS]:
            handler = row.get("handler_name") or "обработчик не задан"
            lines.append(f"  - {row.get('form_name')}.{row.get('event_name')} -> {handler}")
        lines += _over_limit(events)

    templates = res.get("templates") or []
    if templates:
        lines.append(_section_header("МАКЕТЫ", templates, counts, "templates"))
        for row in templates[:MAX_ROWS]:
            kind = row.get("ext_root_tag") or row.get("template_type") or "тип не определён"
            lines.append(f"  - {row.get('name')} | {kind} | {row.get('ext_chars')} симв, "
                         f"{row.get('ext_bytes')} байт")
        lines += _over_limit(templates)
    # Содержимое макетов-СКД (узел B) идёт сразу за перечнем макетов: читатель видит
    # макет и тут же то, что из его сохранённого XML разобрано (или причину отказа).
    lines += _card_dcs_lines(res)



    modules = res.get("modules") or []
    if modules:
        lines.append(_section_header("BSL-МОДУЛИ", modules, counts, "bsl_modules"))
        for row in modules[:MAX_ROWS]:
            flag = " | обрезан" if row.get("truncated") else ""
            lines.append(f"  - {row.get('module_type')} | {row.get('file_path')} | "
                         f"{row.get('code_size')} байт{flag}")
        lines += _over_limit(modules)
    return lines



def main():
    mcp.run()


if __name__ == "__main__":
    main()
