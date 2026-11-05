#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/check_v56_functional_options.py — узел V56: функциональные опции (шаг П6).

Это постоянная проверка, а не проба шага: она обязана переживать и перезагрузку выгрузок, и
правки кода загрузки. Источник ожиданий — `docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PLAN.md`
(разделы 1–2 — замеры базовой линии, раздел 7 — шаги, раздел 9 — критерии готовности). Числа
перенесены из замеров `_v56_p0_probe.py`/`_v56_m1_probe.py` без правок: сглаживать число
проверкой — значит подтверждать неверное число (прецедент узлов V49/V50).

Что сторожится — по контурам:

  1. ГРАНИЦА СХЕМЫ (контур 1). Две таблицы узла (`functional_options` — свойства вида,
     `functional_option_content` — строки перечня `<Content>`), числа колонок (26 и 14 —
     эталон П1), колонки цепи ревизий только у таблицы вида, ключ области видимости
     `(configuration_uuid, object_name, revision_no)`, ключ применения
     `(functional_option_id, ordinal)`, внешний ключ применения с `ON DELETE CASCADE` и
     отсутствие внешнего ключа у таблицы вида (прецедент V20.1), индексы круга, витрины,
     запись таблицы вида в реестр версионируемых и исключение таблицы применения из
     версионности — названы реестрами, а не угаданы.
  2. СЛОВАРИ СОСТОЯНИЙ ↔ CHECK (контур 2). Каждый словарь модуля разбора сверяется с
     CHECK **конкретной таблицы** по имени колонки (`STATE_VOCABULARY_TABLES`), а не
     «где-нибудь в схеме»; ограничения согласованности состояния со значением обязаны
     существовать и не допускать состояний вне словарей; CHECK на ЗНАЧЕНИЯ свойств вида
     отсутствуют осознанно (Q7, вариант A: XSD вида нет, незнакомое остаётся значением с
     состоянием). Отдельно сверяется связка `COUNT_KEYS` ↔ `COUNT_STATE_KEYS` ↔ колонок:
     вывод из имени дал бы `location_form` вместо `location_target_form`, и нулевой
     контракт молча потерял бы состояние.
  3. ГРАНИЦА КРУГА (контур 3). Опция адресуется ТРЕМЯ ногами: каталогом
     `FunctionalOptions/` (`<Имя>.xml`), индексом состава (`FunctionalOption.<Имя>`) и
     перечнем `configurations.functional_options`; строки таблицы — четвёртая. Множества
     имён сравниваются попарно во все стороны. Отдельная проверка: записи вида
     `FunctionalOptionsParameter` (позиция 2.12, 5/7/2 записи на корпус — замер 1.2) в круг
     НЕ входят, потому что сравнение вида точное, а не по префиксу (`kind_index_rows`).
  4. СТРОКА ВИДА ↔ РАЗБОР (контур 4). Каждая колонка строки обязана совпадать с кругом,
     разобранным ТЕМ ЖЕ модулем (`collect_functional_options`), что и загрузка: иначе
     проверка проверяла бы себя, а не то, донёс ли писатель строку.
  5. СТРОКИ ПРИМЕНЕНИЯ ↔ ФАЙЛ (контур 5). Множество `(ordinal, цель, тег, вид цели,
     состояние разрешения, остаток пути)` строк вида равно перечню `<Content>` его файла;
     есть НЕЗАВИСИМЫЙ подсчёт элементов перечня регулярным выражением по тексту файла, без
     знания о состояниях разбора; `targets_count` равен числу строк применения; повтор цели
     внутри одного перечня корпусом не давался (замер 2.2) и остаётся наблюдением, а не
     уникальным ключом (M6).
  6. РАЗРЕШИМОСТЬ ССЫЛОК (контур 6). Сохранённая ссылка `Location` и каждая цель
     разрешаются ЗАНОВО по строкам индекса состава (`resolve_reference`): состояние,
     `object_id`, `object_uuid` и остаток пути обязаны совпасть с сохранёнными. На корпусе
     разрешимость полная — 765/765 ссылок и 10 063/10 063 целей (замеры 2.1, 2.2), и нули
     `prefix_only`/`unresolved` здесь являются проверяемым утверждением, а не
     предположением (Q3). Форма адреса `Location` пересчитывается по адресу и сравнивается
     с эталоном 605/154/6 — тем, чем она разрешается (M5).
  7. ВИТРИНЫ, ЦЕПИ И СИРОТЫ (контур 7). Строк вне витрин текущего состояния — ноль;
     строк применения, висящих на НЕ-текущей ревизии вида, — ноль; сирот применения —
     ноль; `configuration_uuid`/`option_object_uuid`/`option_full_name` строки применения
     равны значениям её родителя (M8 — ради этого круг и читается в обе стороны).
  8. КОНТРАКТ СТАДИИ (контур 8). Закрытый контракт ответа (`functional_options_defaults`)
     перечисляет ровно ключи `COUNT_KEYS`/`SUMMARY_KEYS` с нулями по полному замкнутому
     словарю; форматёр называет каждое состояние, а не только ненулевые; порядок снятия
     начинается с таблицы применения (M7); стадия `s4k_functional_options` стоит в `STAGES`
     между `s4j_bots` и `s4b_object_modules` и имеет подсказку продолжения; инструмент
     `load_functional_options_tool` внесён в реестр сервера (`EXPECTED_TOOLS`).
  9. КОРПУС (контур 9). Суммы по четырём выгрузкам сходятся с разделами 1.1, 2.1, 2.2:
     765 файлов, 765 записей индекса, 765 строк вида, 10 063 строки применения, 765
     разрешённых ссылок `Location`, 203 пустых перечня, максимум 438 целей на вид, 21 класс
     цели. У KomMag каталога вида нет ни файлом, ни записями индекса (замер 1.1) — ответ
     обязан быть пустым кругом с наблюдением `directory_missing`, а не отказом.

Неприкосновенность чужих кругов: прогон читающий, числа соседних витрин (V48…V55) и
`bsl_modules` в нём не меняются.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python tools/check_v56_functional_options.py [MinCfg|KomMag|BGU2|BP3|all]
По умолчанию — `all`: все строки заголовков, для которых находится каталог выгрузки. Код
возврата 0 — расхождений нет. Пропуск контура называется причиной (нет строки заголовка, нет
выгрузки, строк узла не загружалось, индекс состава недоступен): ноль проверок не читается
как «всё хорошо».
"""

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

try:  # кириллица в консоли Windows (cp1251) — как в остальных валидаторах
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from configuration_functional_options import (  # noqa: E402
    CONTENT_EMPTY, CONTENT_ELEMENT_TAG, CONTENT_ITEM_TAG, CONTENT_ROW_KEYS,
    CONTENT_STATE_COLUMNS, CONTENT_STATES, CONTENT_TABLE_NAME, CONTENT_WITH,
    CIRCLE_DISCREPANCIES, COUNT_KEYS, COUNT_STATE_KEYS,
    DIR_NAME, FUNCTIONAL_OPTION_PROPERTIES, FUNCTIONAL_OPTION_PROPERTY_COUNT,
    INDEX_NAME_SEPARATOR, INDEX_OBJECT_TYPE,
    LOCATION_COLUMNS, LOCATION_FORM_ATTRIBUTE, LOCATION_FORM_EMPTY, LOCATION_FORM_OTHER,
    LOCATION_FORM_REGISTER_RESOURCE, LOCATION_FORM_SINGLE, LOCATION_FORMS, LOCATION_STATES,
    OBJECT_KIND_TAG, OPTION_LINK_KEY, OPTION_UUID_KEY, PROPERTIES_STATES, PROPS_ALL_KNOWN,
    PROPERTY_BY_COLUMN, SIBLING_INDEX_OBJECT_TYPE, STATE_VOCABULARIES,
    STATE_VOCABULARY_TABLES, SUMMARY_KEYS, TABLE_NAME, TARGET_EXACT, TARGET_PREFIX_ONLY,
    TARGET_RESOLVE_STATES, TARGET_UNRESOLVED, XML_PROPERTY_NAMES,
    collect_functional_options, index_rows_by_name, location_target_form, property_columns,
    property_kind, read_text_file, resolve_reference, state_columns, target_object_type,
)
from configuration_functional_options_loader import read_index_records  # noqa: E402
from configuration_load_contract import (  # noqa: E402
    FOREIGN_STAGE_TABLES, FUNCTIONAL_OPTIONS_CIRCLE_BOUNDARY, FUNCTIONAL_OPTIONS_DIR,
    FUNCTIONAL_OPTIONS_META_TAG, FUNCTIONAL_OPTIONS_REMOVE_ORDER,
    FUNCTIONAL_OPTIONS_REPEAT_HINT, FUNCTIONAL_OPTIONS_SECTION_HEADER,
    FUNCTIONAL_OPTIONS_TABLES, STORED_META_KINDS, STAGE_BOTS, STAGE_FULL_RELOAD_ONLY,
    STAGE_FUNCTIONAL_OPTIONS, STAGE_FUNCTIONAL_OPTIONS_PARAMETERS, STAGE_OBJECT_MODULES,
    STAGES, functional_options_defaults,
    format_functional_options_lines, stage_resume_hint, stage_title, stages_after,
)
from configuration_module_slots import resolve_dump_dir  # noqa: E402
from current_revision import CONFIGURATION_VERSIONED_TABLES, current_view  # noqa: E402
from external_db import transaction  # noqa: E402
from external_table_writer import (  # noqa: E402
    CONFIGURATION_OBJECT_WRITERS, CONFIGURATION_UNVERSIONED_TABLES,
)

DUMP_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
DEFAULT_SCOPE = "all"
MAX_NAMES = 10          # сколько расхождений называется именами (дальше — только число)

OPTION_VIEW = current_view(TABLE_NAME)
# Таблица применения своей цепи ревизий не имеет (Q2, вариант A), поэтому `current_view()`
# для неё не вызывается — имя витрины называется прямо, как у `v_current_role_rights` (V49)
# и `v_current_common_attribute_targets` (V50): витрина связывается с витриной родителя.
CONTENT_VIEW = "v_current_functional_option_content"
INDEX_TABLE = "configuration_objects"
HEADER_NAME_COLUMN = "functional_options"   # перечень заголовка (стадия S2, узел V43)
# Чужой круг соседнего узла V57 (параметры функциональных опций, позиция 2.12). Имена
# названы списком, а не суженным LIKE: маска `functional_option%` захватывает и их, и
# граница круга узла должна читаться составом чужих таблиц, а не удачным совпадением
# префикса (прецедент — соседние круги V48…V56 в `FOREIGN_TABLES` ниже).
PARAMETER_CIRCLE_TABLES = ("functional_option_parameters",
                           "functional_option_parameter_targets")

# Колонки, которые принадлежат цепи ревизий (узел V19), а не узлу V56: их заполняет не
# разбор, и сравнивать их с ключом строки разбора — значит требовать от слоя чужого.
REVISION_COLUMNS = ("id", "configuration_uuid", "created_at", "revision_no", "changed_at",
                    "changed_by", "is_committed")
# Колонки строки применения, которые подставляет вызывающий слой (связь с ревизией вида),
# а не разбор: они сторожатся контуром 5 отдельно.
CONTENT_WRITER_COLUMNS = (OPTION_LINK_KEY, OPTION_UUID_KEY)

# Ожидаемые числа колонок двух таблиц — эталон шага П1 (миграция V56 + зеркало DDL).
EXPECTED_COLUMN_COUNTS = {TABLE_NAME: 26, CONTENT_TABLE_NAME: 14}

# Имена CHECK замкнутости состояний: имя не выводится из имени колонки для
# `target_resolve_state` (в DDL оно `..._resolve_state_known`), поэтому связка
# «колонка → имя ограничения» держится словарём, а не выводом (прецедент V52/V54).
STATE_CHECK_NAMES = {
    (TABLE_NAME, "properties_state"): "functional_options_properties_state_known",
    (TABLE_NAME, "location_state"): "functional_options_location_state_known",
    (TABLE_NAME, "location_target_form"): "functional_options_location_target_form_known",
    (TABLE_NAME, "content_state"): "functional_options_content_state_known",
    (CONTENT_TABLE_NAME, "target_resolve_state"):
        "functional_option_content_resolve_state_known",
}

# Ограничения согласованности состояния со значением колонок (DDL узла V56): отсутствие
# любого из них означает, что состояние описывало бы само себя, а не структуру строки.
MATCH_CONSTRAINTS = (
    "functional_options_names_not_blank",
    "functional_options_properties_state_matches_unknown",
    "functional_options_privileged_get_mode_declared",
    "functional_options_location_state_matches_value",
    "functional_options_location_type_matches_name",
    "functional_options_location_form_matches_name",
    "functional_options_location_uuid_only_when_resolved",
    "functional_options_content_state_matches_targets",
    "functional_options_configuration_object_revision_key",
    "functional_options_revision_no_positive",
    "functional_option_content_names_not_blank",
    "functional_option_content_resolve_matches_reference",
    "functional_option_content_type_matches_name",
    "functional_option_content_ordinal_non_negative",
    "functional_option_content_option_ordinal_key",
    "functional_option_content_functional_option_id_fkey",
)

# Поля строки вида, которые сверяются с разбором дословно (контур 4). `synonym` и
# `unknown_property_names` сравниваются отдельными проверками: jsonb и текстовый массив
# имеют свою форму пустого значения (NULL, а не пустая структура).
OPTION_COMPARE_FIELDS = (
    "object_uuid", "object_name", "full_name", "comment", "source_path",
    "location_ref", "location_full_name", "location_object_type", "location_target_form",
    "location_object_id", "location_object_uuid", "location_unresolved_path",
    "location_state", "privileged_get_mode", "content_state", "targets_count",
    "properties_state",
)
# Поля строки применения (контур 5): связь с родителем и дедупликация полей вида
# сравниваются отдельно.
CONTENT_COMPARE_FIELDS = (
    "ordinal", "target_tag", "target_full_name", "target_object_type", "target_object_id",
    "target_object_uuid", "target_resolve_state", "target_unresolved_path",
    "configuration_uuid", "option_object_uuid", "option_full_name",
)

# ── ожидания проверки (числа плана docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PLAN.md) ──────────
# Ключ — каталог выгрузки, а не имя строки заголовка: имя заголовка меняется вместе с
# выгрузкой, а каталог — адрес, по которому проверка находит файлы (прецедент V50).
#   files / subdirs / non_xml — каталог `FunctionalOptions/` (плоский, только XML — замер 1.1);
#   index_records — записей `FunctionalOption.<Имя>` в индексе состава (замер 1.1);
#   sibling_index — записей ЧУЖДОГО вида `FunctionalOptionsParameter` (позиция 2.12, замер
#     1.2): они существуют в индексе и обязаны НЕ входить в круг;
#   header_names — элементов перечня `configurations.functional_options` (стадия S2);
#   header_null — перечень NULL (у KomMag вида нет ни файлами, ни записями — замер 1.1);
#   db_rows / targets — строки витрин текущего состояния узла (замеры 1.1, 2.2);
#   distinct / max_targets — кратность целей и максимум на один перечень (замер 2.2, M6);
#   loc_exact / single / register_resource / attribute / other — состояние и форма адреса
#     `Location` (замер 2.1: 765/765 `exact`, формы 605/154/6, `other` — граница разбора);
#   content_with / content_empty — состояния перечня `<Content>` (замер 2.2: 562/203);
#   priv_true / priv_false — флаг `PrivilegedGetMode` (замер 2: 764/1);
#   kinds — число классов цели перечня (замер 2.2: 21 на корпус).
PLAN_EXPECTATIONS = {
    "MinCfg": {"files": 2, "subdirs": 0, "non_xml": 0, "index_records": 2,
               "sibling_index": 2, "header_names": 2, "header_null": 0, "db_rows": 2,
               "targets": 0, "distinct": 0, "max_targets": 0, "loc_exact": 2,
               "single": 2, "register_resource": 0, "attribute": 0, "other": 0,
               "target_exact": 0,
               "content_with": 0, "content_empty": 2, "priv_true": 1, "priv_false": 1,
               "kinds": 0},
    "KomMag": {"files": 0, "subdirs": 0, "non_xml": 0, "index_records": 0,
               "sibling_index": 0, "header_names": 0, "header_null": 1, "db_rows": 0,
               "targets": 0, "distinct": 0, "max_targets": 0, "loc_exact": 0,
               "single": 0, "register_resource": 0, "attribute": 0, "other": 0,
               "target_exact": 0,
               "content_with": 0, "content_empty": 0, "priv_true": 0, "priv_false": 0,
               "kinds": 0},
    "BGU2": {"files": 224, "subdirs": 0, "non_xml": 0, "index_records": 224,
             "sibling_index": 5, "header_names": 224, "header_null": 0, "db_rows": 224,
             "targets": 3274, "distinct": 3144, "max_targets": 438, "loc_exact": 224,
             "single": 209, "register_resource": 14, "attribute": 1, "other": 0,
             "target_exact": 3274,
             "content_with": 161, "content_empty": 63, "priv_true": 224, "priv_false": 0,
             "kinds": 20},
    "BP3": {"files": 539, "subdirs": 0, "non_xml": 0, "index_records": 539,
            "sibling_index": 7, "header_names": 539, "header_null": 0, "db_rows": 539,
            "targets": 6789, "distinct": 5704, "max_targets": 402, "loc_exact": 539,
            "single": 394, "register_resource": 140, "attribute": 5, "other": 0,
            "target_exact": 6789,
            "content_with": 401, "content_empty": 138, "priv_true": 539, "priv_false": 0,
            "kinds": 20},
}

# Классы целей перечня `<Content>` по всему корпусу (раздел 2.2 плана, M1): 21 вид
# метаданных, 10 063 цели. Сумма значений равна числу целей — это и есть проверка полноты
# сверки, а не отдельное число.
EXPECTED_KINDS = {
    "Document": 4881, "InformationRegister": 1261, "Catalog": 1112, "CommonCommand": 596,
    "DataProcessor": 516, "Report": 504, "Enum": 324, "AccumulationRegister": 266,
    "Subsystem": 240, "Constant": 96, "DocumentJournal": 93, "CommonForm": 89,
    "ChartOfCharacteristicTypes": 24, "Task": 16, "AccountingRegister": 13,
    "ChartOfAccounts": 11, "CommonAttribute": 8, "BusinessProcess": 5,
    "ExchangePlan": 3, "ChartOfCalculationTypes": 3, "FilterCriterion": 2,
}

# Суммы по четырём выгрузкам (разделы 1.1, 2.1, 2.2 плана) — они же эталоны живой базы:
# строки витрин обязаны сходиться с файлами и индексом, а не только с разбором.
CORPUS_TOTALS = {
    "files": 765, "index_records": 765, "header_names": 765, "db_rows": 765,
    "targets": 10063, "loc_exact": 765, "single": 605, "register_resource": 154,
    "attribute": 6, "other": 0, "target_exact": 10063,
    "content_with": 562, "content_empty": 203,
    "priv_true": 764, "priv_false": 1, "kinds": 21, "sibling_index": 14,
    "max_targets": 438, "circle_discrepancies": 0, "unknown_states": 0,
    "unresolved_total": 0, "orphans": 0, "outside_views": 0,
}

# Чужие круги (соседние узлы V48…V57 и круг модулей V47): прогон проверки читающий, и
# ни одна их строка не имеет права измениться. Числа берутся до и после обхода.
# Круг V57 добавлен узлом V57: его таблицы появились в схеме, и прогон V56 обязан
# назвать их чужими, а не промолчать о них.
FOREIGN_TABLES = (
    "session_parameters", "roles", "role_rights", "role_restriction_templates",
    "common_attributes", "common_attribute_targets", "exchange_plans",
    "exchange_plan_content", "filter_criteria", "filter_criterion_content",
    "event_subscriptions", "event_subscription_sources", "scheduled_jobs",
    "scheduled_job_schedules", "bots", "bsl_modules", "configuration_objects",
    "configurations",
) + PARAMETER_CIRCLE_TABLES

PASSED: list = []
FAILED: list = []
SKIPPED: list = []
INFO: list = []


# ── форма выдачи: PASS / FAIL / SKIP / INFO, отказ называется, а не обрывает прогон ──────────
def check(name, ok, detail=""):
    if ok:
        PASSED.append(name)
        print(f"PASS {name}")
    else:
        FAILED.append(name)
        print(f"FAIL {name}" + (f"\n      {detail}" if detail else ""))


def skip(name, reason):
    SKIPPED.append(name)
    print(f"SKIP {name}\n      {reason}")


def info(text):
    INFO.append(text)
    print(f"INFO {text}")


def section(title):
    print(f"\n{title}\n{'-' * len(title)}")


def q(cur, sql, params=None):
    cur.execute(sql, params or ())
    if not cur.description:
        return []
    columns = [d[0] for d in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def one(cur, sql, params=None):
    rows = q(cur, sql, params)
    return rows[0] if rows else {}


def scalar(cur, sql, params=None):
    row = one(cur, sql, params)
    return list(row.values())[0] if row else None


def names(sample, limit=MAX_NAMES):
    shown = list(sample)[:limit]
    tail = "" if len(sample) <= limit else f" … ещё {len(sample) - limit}"
    return ", ".join(str(s) for s in shown) + tail


def _brief(value, limit=120):
    text = str(value).replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + " …"


def table_columns(cur, table):
    """Колонки таблицы по живой схеме (список берётся из схемы, а не из памяти проверки)."""
    return [row["column_name"] for row in q(
        cur, "SELECT column_name FROM information_schema.columns WHERE table_name = %s "
             "ORDER BY ordinal_position", (table,))]


def constraint_def(cur, table, constraint):
    """Текст ограничения живой схемы; отсутствующее ограничение — пустая строка (называется)."""
    return scalar(cur, "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                       "WHERE conrelid = %s::regclass AND conname = %s",
                  (table, constraint)) or ""


def literals_of(definition):
    """Литералы ограничения — закрытый словарь схемы. Кавычек внутри состояний нет."""
    out, raw, i = [], str(definition), 0
    while i < len(raw):
        if raw[i] == "'":
            j = i + 1
            while j < len(raw) and raw[j] != "'":
                j += 1
            out.append(raw[i + 1:j])
            i = j + 1
        else:
            i += 1
    return out


def unique_constraints(cur, table):
    """Ограничения UNIQUE живой схемы: имя → текст (ключ ищется по схеме, не по памяти)."""
    return {str(r["conname"]): str(r["def"]) for r in q(
        cur, "SELECT conname, pg_get_constraintdef(oid) AS def FROM pg_constraint "
             "WHERE conrelid = %s::regclass AND contype IN ('u', 'p')", (table,))}


def foreign_keys(cur, table):
    """Внешние ключи живой схемы: имя → текст."""
    return {str(r["conname"]): str(r["def"]) for r in q(
        cur, "SELECT conname, pg_get_constraintdef(oid) AS def FROM pg_constraint "
             "WHERE conrelid = %s::regclass AND contype = 'f'", (table,))}


def indexes_of(cur, table):
    """Индексы живой схемы: имя → текст определения (не только уникальные)."""
    out = {}
    for row in q(cur, "SELECT i.relname AS name, pg_get_indexdef(i.oid) AS def "
                      "FROM pg_index x JOIN pg_class i ON i.oid = x.indexrelid "
                      "JOIN pg_class t ON t.oid = x.indrelid WHERE t.relname = %s",
                 (table,)):
        out[str(row["name"])] = str(row["def"])
    return out


def compact(text):
    return " ".join(str(text).split())


def expect_of(tag):
    return PLAN_EXPECTATIONS[tag]


def set_diff(label, left, right, tag):
    """Две стороны одного множества сравниваются попарно; расхождение называется именами."""
    missing, extra = sorted(right - left), sorted(left - right)
    check(f"{tag}: {label} совпадают во все стороны", not missing and not extra,
          f"не названо: {names(missing)}; лишнее: {names(extra)}")


# ── контур 1: живая схема круга ──────────────────────────────────────────────────────────────
def check_schema(cur):
    section("Контур 1 — живая схема круга")
    for table in (TABLE_NAME, CONTENT_TABLE_NAME):
        if not q(cur, "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                 (table,)):
            check(f"{table}: таблица существует", False, "таблицы в схеме нет")
            return
    for table in (TABLE_NAME, CONTENT_TABLE_NAME):
        columns = table_columns(cur, table)
        check(f"{table}: таблица существует и держит {EXPECTED_COLUMN_COUNTS[table]} "
              "колонок (эталон П1)", len(columns) == EXPECTED_COLUMN_COUNTS[table],
              f"факт: {len(columns)}")

    # Круг узла — ровно две таблицы (Q1, вариант A): обход схемы по маске вида обязан дать
    # их обе и ничего больше — ни таблицы словей (`functional_options_*` от другого вида),
    # ни чужого круга. Границу чужого круга называет список `PARAMETER_CIRCLE_TABLES`, а не
    # подстановка в LIKE: соседний узел V57 (параметры функциональных опций, позиция 2.12)
    # назвал свои таблицы `functional_option_parameter*`, и широкая маска `functional_option%`
    # их захватывает. Отсутствия этих таблиц в базе отказом узла не является: круг V56 от
    # их наличия или отсутствия не меняется.
    kind_tables = [str(r["table_name"]) for r in q(
        cur, "SELECT table_name FROM information_schema.tables WHERE table_name LIKE %s "
             "ORDER BY table_name", ("functional_option%",))]
    foreign_found = sorted(t for t in kind_tables if t in PARAMETER_CIRCLE_TABLES)
    node_tables = sorted(t for t in kind_tables if t not in PARAMETER_CIRCLE_TABLES)
    check("таблиц вида по маске `functional_option%` без чужого круга V57 — ровно две "
          "(Q1 вариант A: свойства вида и перечень применения)",
          node_tables == sorted([TABLE_NAME, CONTENT_TABLE_NAME]),
          f"найдено: {names(kind_tables)}")
    check("таблиц чужого круга V57 в круг узла не вошло — граница названа списком таблиц, "
          "а не совпадением префикса (позиция 2.12, узел V57)",
          len(foreign_found) in (0, len(PARAMETER_CIRCLE_TABLES)),
          f"чужих таблиц: {names(foreign_found)}")

    option_columns = set(table_columns(cur, TABLE_NAME))
    content_columns = set(table_columns(cur, CONTENT_TABLE_NAME))
    absent = sorted(column for column in ("revision_no", "changed_at", "changed_by",
                                          "is_committed") if column in content_columns)
    check(f"`{CONTENT_TABLE_NAME}`: колонок цепи ревизий нет осознанно (Q2, вариант A) — "
          "текущность читается связкой с родителем, а не собственной цепью", not absent,
          f"лишние колонки: {names(absent)}")
    missing_chain = sorted(c for c in REVISION_COLUMNS if c not in option_columns)
    check(f"`{TABLE_NAME}`: колонки цепи ревизий узла V19 живы целиком "
          f"({len(REVISION_COLUMNS)} колонок)", not missing_chain,
          f"нет: {names(missing_chain)}")

    wanted_option_key = "(configuration_uuid, object_name, revision_no)"
    keys = unique_constraints(cur, TABLE_NAME)
    scope = [d for d in keys.values() if compact(d).endswith(wanted_option_key)]
    check(f"`{TABLE_NAME}`: ключ области видимости строк узла живой {wanted_option_key} "
          "(M1: 135 uuid и 143 имени вида совпадают у BGU2 и BP3 — замер 1.3)",
          len(scope) == 1, f"ключи схемы: {names(list(keys))}")

    content_keys = unique_constraints(cur, CONTENT_TABLE_NAME)
    wanted_content_key = "(functional_option_id, ordinal)"
    content_scope = [d for d in content_keys.values()
                     if compact(d).endswith(wanted_content_key)]
    check(f"`{CONTENT_TABLE_NAME}`: ключ применения живой {wanted_content_key} — порядок "
          "перечня восстанавливается по ordinal, уникального ключа по паре (вид, цель) нет "
          "осознанно (M6: повтор цели легален в другой выгрузке)",
          len(content_scope) == 1, f"ключи схемы: {names(list(content_keys))}")

    option_fks = foreign_keys(cur, TABLE_NAME)
    check(f"`{TABLE_NAME}`: внешних ключей нет осознанно — ни на заголовок (прецедент "
          "V20.1), ни на цель ссылки `Location` (Q3: слои `Constants`/регистров/справочников "
          "не загружены, состояние разрешения называется строкой)", not option_fks,
          f"ключи: {names(list(option_fks))}")

    content_fks = foreign_keys(cur, CONTENT_TABLE_NAME)
    cascade = [d for d in content_fks.values()
               if "ON DELETE CASCADE" in compact(d).upper()
               and "functional_options" in compact(d)]
    check(f"`{CONTENT_TABLE_NAME}`: ровно один внешний ключ на `{TABLE_NAME}(id)` с "
          "`ON DELETE CASCADE` (снимает применение вместе с ревизией вида)",
          len(content_fks) == 1 and len(cascade) == 1,
          f"ключи: {names(list(content_fks))}")

    wanted_indexes = {
        "idx_functional_options_object_uuid_revision": "(object_uuid, revision_no)",
        "idx_functional_options_location_full_name": "location_full_name",
        "idx_functional_options_location_object_uuid": "location_object_uuid",
        "idx_functional_option_content_configuration_uuid": "configuration_uuid",
        "idx_functional_option_content_target_full_name": "target_full_name",
        "idx_functional_option_content_target_object_uuid": "target_object_uuid",
        "idx_functional_option_content_configuration_type":
            "configuration_uuid, target_object_type",
    }
    for table in (TABLE_NAME, CONTENT_TABLE_NAME):
        prefix = ("idx_functional_options_" if table == TABLE_NAME
                  else "idx_functional_option_content_")
        found = indexes_of(cur, table)
        for index_name, fragment in wanted_indexes.items():
            if not index_name.startswith(prefix):
                continue
            definition = compact(found.get(index_name, ""))
            check(f"`{table}`: индекс `{index_name}` жив и ведёт по `{compact(fragment)}`",
                  bool(definition) and compact(fragment) in definition,
                  "индекса в схеме нет" if not definition
                  else f"определение: {_brief(definition)}")

    for view in (OPTION_VIEW, CONTENT_VIEW):
        try:
            count = scalar(cur, f"SELECT count(*) FROM {view}")
            check(f"витрина текущего состояния `{view}` жива и читается", True)
            info(f"витрина `{view}`: строк {count}")
        except Exception as exc:  # noqa: BLE001 — отсутствующая витрина называется отказом
            cur.connection.rollback()
            check(f"витрина текущего состояния `{view}` жива и читается", False, str(exc))

    check(f"`{TABLE_NAME}` состоит в реестре версионируемых (цепь узла V19, Q2)",
          TABLE_NAME in CONFIGURATION_VERSIONED_TABLES,
          f"реестр: {names(sorted(CONFIGURATION_VERSIONED_TABLES))}")
    check(f"`{CONTENT_TABLE_NAME}` НЕ версионируется своей цепью и названа исключением "
          "`CONFIGURATION_UNVERSIONED_TABLES` (Q2, вариант A — прецеденты `role_rights` V49, "
          "`common_attribute_targets` V50, `filter_criterion_content` V52)",
          CONTENT_TABLE_NAME not in CONFIGURATION_VERSIONED_TABLES
          and CONTENT_TABLE_NAME in CONFIGURATION_UNVERSIONED_TABLES,
          f"исключение: {names(list(CONFIGURATION_UNVERSIONED_TABLES))}")
    check(f"имя витрины вида задаёт реестр, а не DDL: `current_view()` отдаёт `{OPTION_VIEW}`",
          current_view(TABLE_NAME) == OPTION_VIEW,
          f"реестр даёт: {current_view(TABLE_NAME)}")
    # Для таблицы применения `current_view()` обязан отказать: своей цепи ревизий у неё нет
    # (Q2, вариант A), поэтому имя витрины называется слоем, а не выводится из реестра —
    # тот же порядок, что `v_current_role_rights` (V49) и
    # `v_current_common_attribute_targets` (V50).
    try:
        registry_answer = f"реестр версионируемых вернул имя {current_view(CONTENT_TABLE_NAME)}"
        refused = False
    except ValueError as exc:
        registry_answer = str(exc)
        refused = True
    check(f"`current_view()` для `{CONTENT_TABLE_NAME}` отказывает (своей цепи нет), имя "
          f"витрины `{CONTENT_VIEW}` называется слоем прямо",
          refused and "не версионируется" in registry_answer, registry_answer)
    check("писатели обеих таблиц внесены в `CONFIGURATION_OBJECT_WRITERS` (реестр выбирает "
          "писателя по таблице, отсутствие означало бы выбор класса по имени)",
          TABLE_NAME in CONFIGURATION_OBJECT_WRITERS
          and CONTENT_TABLE_NAME in CONFIGURATION_OBJECT_WRITERS,
          f"писатель вида: {CONFIGURATION_OBJECT_WRITERS.get(TABLE_NAME)}, применения: "
          f"{CONFIGURATION_OBJECT_WRITERS.get(CONTENT_TABLE_NAME)}")
    check(f"перечень заголовка `configurations.{HEADER_NAME_COLUMN}` жив (его заполняет "
          "стадия S2 узла V43, стадия V56 её не перезаписывает)",
          bool(q(cur, "SELECT 1 FROM information_schema.columns WHERE table_name = "
                      "'configurations' AND column_name = %s", (HEADER_NAME_COLUMN,))))


# ── контур 2: словари состояний ↔ CHECK'ы конкретной таблицы ────────────────────────────────
def compare_vocabulary(cur, table, column, vocabulary):
    """Словарь модуля и замкнутость схемы равны; расхождение называется множествами.

    CHECK ищется по таблице, которой принадлежит колонка (`STATE_VOCABULARY_TABLES`):
    «где-нибудь в схеме» нашло бы словарь чужого узла с тем же именем состояния
    (`content_state`, `target_resolve_state` есть у V50/V52).
    """
    constraint = STATE_CHECK_NAMES.get((table, column))
    if not constraint:
        check(f"{table}.{column}: имя CHECK замкнутости названо словарём "
              "`STATE_CHECK_NAMES`", False, "связки «таблица, колонка → имя ограничения» нет")
        return set()
    definition = constraint_def(cur, table, constraint)
    if not definition:
        check(f"{table}.{column}: CHECK замкнутости `{constraint}` живой схемы", False,
              "ограничения с таким именем в схеме нет — словарь схемы нечем подтвердить")
        return set()
    schema_values = set(literals_of(definition))
    module_values = set(vocabulary)
    check(f"{table}.{column}: CHECK живой схемы перечисляет словарь модуля "
          f"({len(module_values)} значений)", schema_values == module_values,
          f"в словаре нет: {names(sorted(schema_values - module_values))}; "
          f"CHECK допускает: {names(sorted(module_values - schema_values))}")
    return schema_values


def check_state_vocabulary_checks(cur):
    section("Контур 2 — словари состояний против CHECK'ов конкретной таблицы")
    columns_by_table = {table: set(table_columns(cur, table))
                        for table in (TABLE_NAME, CONTENT_TABLE_NAME)}
    vocabularies = {}
    for column in sorted(STATE_VOCABULARIES):
        table = STATE_VOCABULARY_TABLES.get(column)
        if table is None:
            check(f"колонка состояния `{column}` имеет таблицу в "
                  f"`STATE_VOCABULARY_TABLES`", False,
                  "связки нет — проверка сверяла бы словарь не с той таблицей")
            continue
        vocabularies[column] = STATE_VOCABULARIES[column]
        compare_vocabulary(cur, table, column, vocabularies[column])

    outside = sorted(column for column, table in STATE_VOCABULARY_TABLES.items()
                     if column not in columns_by_table.get(table, set()))
    check(f"словари состояний разбора стоят на колонках своих таблиц "
          f"({len(STATE_VOCABULARY_TABLES)} колонок)", not outside,
          f"колонок в схеме нет: {names(outside)}")
    check(f"`state_columns()` отдаёт ровно замкнутый словарь "
          f"({len(STATE_VOCABULARIES)} колонок) — ответ и проверка перечисляют состояния "
          "списком, а не догадкой",
          tuple(sorted(state_columns())) == tuple(sorted(STATE_VOCABULARIES)),
          f"функция даёт: {names(state_columns())}")

    names_present = set()
    for table in (TABLE_NAME, CONTENT_TABLE_NAME):
        names_present |= {str(r["conname"]) for r in q(
            cur, "SELECT conname FROM pg_constraint WHERE conrelid = %s::regclass", (table,))}
    missing = [c for c in MATCH_CONSTRAINTS if c not in names_present]
    check(f"ограничений DDL узла V56 в схеме нет — {len(missing)} "
          f"(ожидаются {len(MATCH_CONSTRAINTS)})", not missing, names(missing))

    known = set()
    for vocabulary in vocabularies.values():
        known |= set(vocabulary)
    admitted = set()
    for constraint in MATCH_CONSTRAINTS:
        for table in (TABLE_NAME, CONTENT_TABLE_NAME):
            literals = set(literals_of(constraint_def(cur, table, constraint)))
            admitted |= {value for value in literals if value in known}
    check(f"match-CHECK'ы допускают состояния только из словарей модуля "
          f"({len(admitted)} значений)", admitted <= known,
          f"вне словарей: {names(sorted(admitted - known))}")

    check(f"`{TABLE_NAME}.unknown_property_names`: колонка виновников жива (Q1 вариант A: "
          "XSD вида нет, незнакомый тег не является отказом записи)",
          "unknown_property_names" in columns_by_table[TABLE_NAME],
          f"колонок: {len(columns_by_table[TABLE_NAME])}")
    check("CHECK `functional_options_properties_state_matches_unknown` связывает состояние с "
          "перечнем виновников: `all_known` не держит имён, `unknown_value`/`unknown_tag`/"
          "`absent` называют хотя бы одно",
          "functional_options_properties_state_matches_unknown" in names_present
          and "unknown_property_names" in constraint_def(
              cur, TABLE_NAME, "functional_options_properties_state_matches_unknown"))

    # Q7 (вариант A): значения свойств замкнуты НЕ были — незнакомое значение обязано
    # оставаться значением с состоянием, а не отказом записи.
    value_checks = [str(r["conname"]) for r in q(
        cur, "SELECT conname FROM pg_constraint WHERE conrelid = %s::regclass "
             "AND (conname LIKE '%%synonym%%' OR conname LIKE '%%comment%%' "
             "OR conname LIKE '%%location_ref%%')", (TABLE_NAME,))]
    check("CHECK'ов на ЗНАЧЕНИЯ свойств вида нет осознанно (Q7 вариант A): ограничений по "
          "значениям `synonym`/`comment`/`location_ref` в схеме нет",
          not value_checks, f"найдено: {names(value_checks)}")

    # Связка «ключ сводки → колонка состояния»: вывод из имени дал бы `location_form`
    # вместо `location_target_form`, и нулевой контракт молча потерял бы состояние.
    check("ключи `COUNT_STATE_KEYS` равны ключам `COUNT_KEYS` (словарь не разъехался)",
          set(COUNT_STATE_KEYS) == set(COUNT_KEYS),
          f"лишние: {names(sorted(set(COUNT_STATE_KEYS) - set(COUNT_KEYS)))}; нет: "
          f"{names(sorted(set(COUNT_KEYS) - set(COUNT_STATE_KEYS)))}")
    bad_columns = []
    for key, column in COUNT_STATE_KEYS.items():
        table = STATE_VOCABULARY_TABLES.get(column)
        if table is None or column not in columns_by_table.get(table, set()):
            bad_columns.append(f"{key}→{column}")
    check(f"колонки состояний из `COUNT_STATE_KEYS` существуют в своих таблицах "
          f"({len(COUNT_STATE_KEYS)} связок)", not bad_columns, names(bad_columns))
    check("словари состояний `COUNT_KEYS` покрывают ВСЕ колонки состояний двух таблиц — "
          "контракт не теряет состояние молча",
          set(COUNT_STATE_KEYS.values()) == set(STATE_VOCABULARIES),
          f"вне контракта: "
          f"{names(sorted(set(STATE_VOCABULARIES) - set(COUNT_STATE_KEYS.values())))}")


def check_key_columns_match(cur):
    """Ключ строки разбора ↔ колонки таблицы: ни ключа без колонки, ни колонки без причины.

    Разбор работает без живой базы и колонок цепи ревизий не выдумывает; писатель П4
    подставляет связь строки применения с ревизией вида. Всё остальное обязано иметь
    колонку, иначе проверка «ключа ↔ колонок» теряет смысл (прецедент V50).
    """
    section("Контур 2.1 — ключ разбора против колонок схемы")
    option_columns = set(table_columns(cur, TABLE_NAME))
    content_columns = set(table_columns(cur, CONTENT_TABLE_NAME))

    parse_option_columns = (set(property_columns()) | set(LOCATION_COLUMNS)
                            | set(CONTENT_STATE_COLUMNS)
                            | {"object_uuid", "full_name", "source_path", "properties_state",
                               "unknown_property_names"})
    check(f"словарь свойств ({FUNCTIONAL_OPTION_PROPERTY_COUNT} тегов), ссылка `Location` "
          f"({len(LOCATION_COLUMNS)} колонок) и перечень ({len(CONTENT_STATE_COLUMNS)} колонок) "
          f"дают ровно {len(parse_option_columns)} колонок строки вида",
          parse_option_columns <= option_columns,
          f"ключей без колонки: {names(sorted(parse_option_columns - option_columns))}")
    unexplained = sorted(option_columns - parse_option_columns - set(REVISION_COLUMNS))
    check(f"`{TABLE_NAME}`: колонок, которым нет причины, — ноль "
          f"({len(option_columns)} = {len(parse_option_columns)} разбора + "
          f"{len(REVISION_COLUMNS)} цепи ревизий)", not unexplained, names(unexplained))

    content_expected = (set(CONTENT_ROW_KEYS) | {"functional_option_id", "configuration_uuid",
                                                "id", "created_at"})
    check(f"`{CONTENT_TABLE_NAME}`: ключ разбора ({len(CONTENT_ROW_KEYS)}) + связь слоя + "
          "служебные колонки равны колонкам таблицы "
          f"({len(content_expected)} = {len(content_columns)})",
          content_expected == content_columns,
          f"нет в таблице: {names(sorted(content_expected - content_columns))}; вне разбора: "
          f"{names(sorted(content_columns - content_expected))}")

    check(f"словарь свойств вида держится ОДНИМ местом: `property_columns()` даёт "
          f"{len(property_columns())} колонок, `XML_PROPERTY_NAMES` — "
          f"{len(XML_PROPERTY_NAMES)} тегов, `PROPERTY_BY_COLUMN` — "
          f"{len(PROPERTY_BY_COLUMN)} связок",
          len(FUNCTIONAL_OPTION_PROPERTIES) == FUNCTIONAL_OPTION_PROPERTY_COUNT
          and len(PROPERTY_BY_COLUMN) == FUNCTIONAL_OPTION_PROPERTY_COUNT
          and len(XML_PROPERTY_NAMES) == FUNCTIONAL_OPTION_PROPERTY_COUNT
          and len(property_columns()) == FUNCTIONAL_OPTION_PROPERTY_COUNT - 2,
          f"связок: {len(PROPERTY_BY_COLUMN)}")
    check("плейсхолдеры `Location`/`Content` названы отдельными видами разбора "
          "(`property_kind`), а не колонками-одиночками: их имён нет среди колонок схемы "
          "(у ссылки восемь колонок, у перечня — вторая таблица); колонки ссылки и перечня "
          "возвращают None — они вне словаря свойств",
          property_kind("location") == "location"
          and property_kind("content") == "content"
          and "location" not in option_columns and "content" not in option_columns
          and property_kind("location_ref") is None
          and property_kind("content_state") is None
          and property_kind("object_name") == "text"
          and property_kind("privileged_get_mode") == "bool",
          f"location: {property_kind('location')}, content: {property_kind('content')}, "
          f"колонок-плейсхолдеров в схеме: "
          f"{names(sorted({'location', 'content'} & option_columns))}")


# ── независимая мера круга: обход каталога и текста файлов без знания о состоянии разбора ────
# Регулярные выражения читают ТЕКСТ файла: проверка не пользуется словарём состояний
# разбора, иначе она подтверждала бы разбор его же утверждением (приём V50/V52).
NAME_RE = re.compile(r"<Name>\s*(.*?)\s*</Name>", re.S)
LOCATION_RE = re.compile(r"<Location>(.*?)</Location>", re.S)
PRIVILEGED_RE = re.compile(r"<PrivilegedGetMode>\s*(.*?)\s*</PrivilegedGetMode>", re.S)
CONTENT_BLOCK_RE = re.compile(
    r"<(?:[\w.-]+:)?Content\s*/>|<(?:[\w.-]+:)?Content\b[^>]*>(.*?)</(?:[\w.-]+:)?Content\s*>",
    re.S)
CONTENT_ITEM_RE = re.compile(r"<(?:[\w.-]+:)?Object\b[^>]*>(.*?)</(?:[\w.-]+:)?Object\s*>",
                            re.S)


def circle_measures(dump_dir):
    """Файлы регистрации, подкаталоги, не-XML, элементы `<Object>` и пустые перечни.

    `content_items` считается по тексту файла, `empty_content_files` — по файлам, где блок
    перечня пуст (`<Content/>` или `<Content></Content>`): 203 таких на корпус — это
    состояние вида (Q6, вариант A), а не отсутствие опции.
    """
    root = Path(dump_dir) / DIR_NAME
    totals = {"files": 0, "subdirs": 0, "non_xml": 0, "bytes": 0, "directory_exists": 0,
              "content_items": 0, "empty_content_files": 0, "location_tags": 0,
              "priv_true": 0, "priv_false": 0, "names": set(), "items_by_name": {}}
    if not root.exists():
        return totals
    totals["directory_exists"] = 1
    for entry in sorted(root.iterdir()):
        if entry.is_dir():
            totals["subdirs"] += 1
            continue
        if entry.suffix.lower() != ".xml":
            totals["non_xml"] += 1
            continue
        totals["files"] += 1
        totals["bytes"] += entry.stat().st_size
        text, error = read_text_file(entry)
        if error or text is None:
            continue
        name_match = NAME_RE.search(text)
        option_name = name_match.group(1).strip() if name_match else entry.stem
        totals["names"].add(option_name)
        if LOCATION_RE.search(text):
            totals["location_tags"] += 1
        privileged = PRIVILEGED_RE.search(text)
        if privileged:
            value = privileged.group(1).strip()
            if value == "true":
                totals["priv_true"] += 1
            elif value == "false":
                totals["priv_false"] += 1
        blocks = CONTENT_BLOCK_RE.findall(text)
        items = 0
        for block in blocks:
            if block:
                items += len(CONTENT_ITEM_RE.findall(block))
        totals["content_items"] += items
        totals["items_by_name"][option_name] = items
        if blocks and items == 0:
            totals["empty_content_files"] += 1
    return totals


def registration_names(dump_dir):
    """Имена видов по файлам регистрации (без расширения) — независимая мера каталога."""
    root = Path(dump_dir) / DIR_NAME
    if not root.exists():
        return set()
    return {entry.stem for entry in root.iterdir()
            if entry.is_file() and entry.suffix.lower() == ".xml"}


def read_index_aggregates(cur, configuration_id):
    """Записи индекса состава вида и ЧУЖДОГО вида параметров — отдельным SQL.

    Отдельный запрос нужен потому, что граница круга держится ТОЧНЫМ значением
    `object_type`: `FunctionalOptionsParameter` начинается с того же префикса и попал бы
    в круг при сравнении по началу строки (раздел 1.2 плана, `_v56_m1_probe.py`).
    """
    rows = q(cur, f"SELECT object_name, object_id, uuid::text AS uuid, depth, parent_name "
                  f"FROM {INDEX_TABLE} WHERE configuration_id = %s AND object_type = %s "
                  "ORDER BY object_name", (configuration_id, INDEX_OBJECT_TYPE))
    prefix = f"{INDEX_OBJECT_TYPE}{INDEX_NAME_SEPARATOR}"
    names = set()
    for row in rows:
        value = str(row["object_name"] or "")
        names.add(value[len(prefix):] if value.startswith(prefix) else value)
    children = [row for row in rows if row["parent_name"]]
    sibling_rows = q(cur, f"SELECT object_name FROM {INDEX_TABLE} WHERE configuration_id = %s "
                          "AND object_type = %s ORDER BY object_name",
                     (configuration_id, SIBLING_INDEX_OBJECT_TYPE))
    sibling_prefix = f"{SIBLING_INDEX_OBJECT_TYPE}{INDEX_NAME_SEPARATOR}"
    sibling_names = set()
    for row in sibling_rows:
        value = str(row["object_name"] or "")
        sibling_names.add(value[len(sibling_prefix):]
                          if value.startswith(sibling_prefix) else value)
    return {"kind_rows": len(rows), "child_rows": len(children), "names": names,
            "sibling_rows": len(sibling_names), "sibling_names": sibling_names}


def read_header_name_list(cur, cfg_uuid):
    """Перечень заголовка, заполненный стадией S2: имена элементов или NULL (пустой
    перечень различим от отсутствующего — колонка `text[]`, а не jsonb)."""
    row = one(cur, f"SELECT coalesce(array_length({HEADER_NAME_COLUMN}, 1), 0) AS n, "
                   f"({HEADER_NAME_COLUMN} IS NULL) AS is_null, "
                   f"coalesce({HEADER_NAME_COLUMN}, '{{}}') AS items FROM configurations "
                   "WHERE uuid = %s::uuid", (cfg_uuid,))
    items = [str(item) for item in (row.get("items") or [])]
    return int(row.get("n") or 0), bool(row.get("is_null")), items


def read_option_rows(cur, cfg_uuid):
    """Строки вида текущей ревизии — через витрину, а не прямым чтением версионируемой
    таблицы."""
    return q(cur, f"SELECT * FROM {OPTION_VIEW} WHERE configuration_uuid = %s::uuid "
                   "ORDER BY full_name", (cfg_uuid,))


def read_content_rows(cur, cfg_uuid):
    """Строки применения текущих ревизий — через витрину применения (связка с витриной
    вида, а не с таблицей: иначе строки не-текущей ревизии попали бы в ответ)."""
    return q(cur, f"SELECT * FROM {CONTENT_VIEW} WHERE configuration_uuid = %s::uuid "
                   "ORDER BY option_full_name, ordinal", (cfg_uuid,))


# ── контур 3: граница круга — файлы, индекс состава, перечень заголовка, строки таблицы ──────
def check_circle(cur, header, dump_dir, index_info, expect, parsed, tag):
    section(f"Контур 3 — граница круга ({tag})")
    raw = circle_measures(dump_dir)
    agg = read_index_aggregates(cur, int(header["id"]))
    db_rows = read_option_rows(cur, str(header["uuid"]))
    content_rows = read_content_rows(cur, str(header["uuid"]))
    header_count, header_is_null, header_items = read_header_name_list(cur,
                                                                       str(header["uuid"]))

    check(f"{tag}: файлов регистрации — {expect['files']} (замер 1.1)",
          raw["files"] == expect["files"], f"факт: {raw['files']}")
    check(f"{tag}: каталог вида плоский — подкаталогов и не-XML ноль "
          f"(замер 1.2: форм, макетов, команд и модулей у вида нет)",
          raw["subdirs"] == expect["subdirs"] and raw["non_xml"] == expect["non_xml"],
          f"подкаталогов: {raw['subdirs']}, не-XML: {raw['non_xml']}")
    check(f"{tag}: записей индекса состава вида — {expect['index_records']} (замер 1.1)",
          agg["kind_rows"] == expect["index_records"], f"факт: {agg['kind_rows']}")
    check(f"{tag}: записей детей вида в индексе нет — {expect['index_records']} ног, "
          "детей 0 (расхождений `child_mismatches` в словаре круга нет осознанно)",
          agg["child_rows"] == 0, f"детских записей: {agg['child_rows']}")
    check(f"{tag}: строк вида в витрине — {expect['db_rows']}, строк применения — "
          f"{expect['targets']} (замеры 1.1, 2.2)",
          len(db_rows) == expect["db_rows"] and len(content_rows) == expect["targets"],
          f"факт: вида {len(db_rows)}, применения {len(content_rows)}")
    check(f"{tag}: перечень заголовка `configurations.{HEADER_NAME_COLUMN}` — "
          f"{expect['header_names']} имён (третью ногу круга пишет стадия S2)",
          header_count == expect["header_names"], f"факт: {header_count}")

    file_names = registration_names(dump_dir)
    set_diff("файлы каталога и имена индекса состава", file_names, agg["names"], tag)
    set_diff("имена индекса состава и перечень заголовка", agg["names"],
             {str(item) for item in header_items}, tag)
    set_diff("перечень заголовка и строки таблицы", {str(item) for item in header_items},
             {str(row["object_name"]) for row in db_rows}, tag)
    set_diff("файлы каталога и строки таблицы", file_names,
             {str(row["object_name"]) for row in db_rows}, tag)

    # Раздел 1.2 плана: `FunctionalOptionsParameter` — другой вид (позиция 2.12, узел V57).
    # Он существует в индексе состава (5/7/2 записи на корпус) и обязан НЕ попасть в круг:
    # сравнение вида точное, а не по префиксу.
    check(f"{tag}: записей ЧУЖДОГО вида `FunctionalOptionsParameter` в индексе "
          f"{agg['sibling_rows']} (замер 1.2), в круг узла не вошла ни одна — предикат "
          "вида точный, а не по префиксу",
          agg["sibling_rows"] == expect["sibling_index"]
          and not ({str(row["object_name"]) for row in db_rows} & agg["sibling_names"]),
          f"чужих записей: {agg['sibling_rows']}, ожидание: {expect['sibling_index']}, "
          f"пересечение с кругом: {names(sorted({str(row['object_name']) for row in db_rows} & agg['sibling_names']))}")
    overlap = sorted(name for name in agg["names"] if name in agg["sibling_names"])
    info(f"{tag}: общих имён у вида и у параметров — {len(overlap)}; предикат круга "
         "различает виды по значению `object_type`, а не по имени, поэтому пересечение "
         "имён на круг не влияет"
         + (f" (примеры: {names(overlap)})" if overlap else ""))

    # Расхождения двух ног круга обязаны быть названы, а не нулевыми по умолчанию:
    # словарь `CIRCLE_DISCREPANCIES` замкнут, и ответ стадии обязан перечислять его весь.
    discrepancies = {key: len(parsed.get(key) or []) for key in CIRCLE_DISCREPANCIES}
    check(f"{tag}: расхождений файла с индексом состава нет — "
          f"{', '.join(f'{k}={v}' for k, v in discrepancies.items())} (замер 1.1 даёт "
          "равенство трёх ног)",
          all(value == 0 for value in discrepancies.values()),
          f"факт: {discrepancies}")
    observations = {}
    for kind, _detail in (parsed.get("observations") or []):
        observations[str(kind)] = observations.get(str(kind), 0) + 1
    if expect["files"] == 0 and not raw["directory_exists"]:
        check(f"{tag}: каталога вида нет — ответ обязан быть пустым кругом с наблюдением "
              "`directory_missing`, а не отказом стадии (Q9, вариант A; KomMag даёт именно "
              "так)",
              observations.get("directory_missing") == 1 and parsed["success"] is True,
              f"наблюдения: {observations}, success: {parsed['success']}")
    else:
        check(f"{tag}: наблюдений `directory_missing` нет (каталог вида есть)",
              "directory_missing" not in observations, f"наблюдения: {observations}")
    return db_rows, content_rows, raw, agg, header_count, header_is_null


# ── контур 4: строка таблицы ↔ разбор тем же модулем, что и загрузка ─────────────────────────
def normalize(value):
    """Одна форма сравнения значения разбора и строки базы. Пустая строка НЕ сводится к
    NULL: `location_ref = ''` и «тега нет» различаются состоянием `location_state`, а не
    подстановкой (прецедент V52/V53/V55)."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if value is None:
        return None
    return str(value)


def compare_option_rows(parsed, db_rows, expect, tag):
    section(f"Контур 4 — строка вида против разбора ({tag})")
    parsed_rows = parsed["rows"]
    by_name = {str(row["object_name"]): row for row in parsed_rows}
    db_by_name = {str(row["object_name"]): row for row in db_rows}
    check(f"{tag}: имена разбора и строк базы равны ({len(by_name)})",
          set(by_name) == set(db_by_name),
          f"только в разборе: {names(sorted(set(by_name) - set(db_by_name)))}; только в "
          f"базе: {names(sorted(set(db_by_name) - set(by_name)))}")

    mismatches = []
    for name in sorted(set(by_name) & set(db_by_name)):
        parsed_row, db_row = by_name[name], db_by_name[name]
        for field in OPTION_COMPARE_FIELDS:
            left, right = normalize(parsed_row.get(field)), normalize(db_row.get(field))
            if field.endswith("uuid"):
                left = str(left or "").lower() or None
                right = str(right or "").lower() or None
            if left != right:
                mismatches.append(f"{name}.{field}: разбор {_brief(left)}, база "
                                  f"{_brief(right)}")
    check(f"{tag}: {len(OPTION_COMPARE_FIELDS)} полей каждой строки совпадают с разбором",
          not mismatches, "; ".join(mismatches[:6]))

    synonym_diff = []
    for name in sorted(set(by_name) & set(db_by_name)):
        if by_name[name].get("synonym") != db_by_name[name].get("synonym"):
            synonym_diff.append(f"{name}: {_brief(by_name[name].get('synonym'))} ↔ "
                                f"{_brief(db_by_name[name].get('synonym'))}")
    check(f"{tag}: многоязычный синоним (`synonym` jsonb) сохранён без правок (замер 2 "
          "плана: `Synonym` есть во всех файлах круга)", not synonym_diff,
          "; ".join(synonym_diff[:4]))

    culprit_diff = []
    for name in sorted(set(by_name) & set(db_by_name)):
        parsed_culprits = by_name[name].get("unknown_property_names")
        db_culprits = db_by_name[name].get("unknown_property_names")
        if parsed_culprits is None:
            ok = db_culprits is None
        else:
            ok = [str(v) for v in (db_culprits or [])] == [str(v) for v in parsed_culprits]
        if not ok:
            culprit_diff.append(f"{name}: {_brief(parsed_culprits)} ↔ {_brief(db_culprits)}")
    check(f"{tag}: пустой перечень виновников — NULL, а не пустой массив (CHECK "
          "`functional_options_properties_state_matches_unknown`)", not culprit_diff,
          "; ".join(culprit_diff[:4]))

    # Состояния из сводки разбора сравниваются с построчным группированием базы: один и тот
    # же круг, посчитанный двумя способами (приём V50/V54/V55).
    for column, vocabulary in sorted(STATE_VOCABULARIES.items()):
        if column == "target_resolve_state":
            continue   # состояния применения сравнивает контур 5
        parsed_counts = Counter(str(row.get(column)) for row in parsed_rows)
        db_counts = Counter(str(row[column]) for row in db_rows)
        check(f"{tag}: состояния колонки `{column}` в разборе и в базе совпадают",
              parsed_counts == db_counts,
              f"разбор: {dict(parsed_counts)}, база: {dict(db_counts)}")
        outside = set(db_counts) - set(vocabulary)
        check(f"{tag}: состояний колонки `{column}` вне замкнутого словаря в базе нет",
              not outside, f"вне словаря: {names(sorted(outside))}")

    forms = Counter()
    location_counts = Counter()
    content_counts = Counter()
    privileged = Counter()
    for row in db_rows:
        location_counts[str(row["location_state"])] += 1
        forms[str(row["location_target_form"])] += 1
        content_counts[str(row["content_state"])] += 1
        privileged[str(bool(row["privileged_get_mode"]))] += 1
    check(f"{tag}: состояние ссылки `Location` `{TARGET_EXACT}` — {expect['loc_exact']} "
          "раз(а) (замер 2.1 плана: разрешимость полная)",
          location_counts.get(TARGET_EXACT, 0) == expect["loc_exact"],
          f"факт: {dict(location_counts)}")
    for plan_key, form in (("single", LOCATION_FORM_SINGLE),
                           ("register_resource", LOCATION_FORM_REGISTER_RESOURCE),
                           ("attribute", LOCATION_FORM_ATTRIBUTE),
                           ("other", LOCATION_FORM_OTHER)):
        check(f"{tag}: форма адреса `{form or '(пустая)'}` — {expect[plan_key]} раз(а) "
              "(замер 2.1: 605/154/6 на корпус, `other` — граница разбора)",
              forms.get(form, 0) == expect[plan_key], f"факт: {dict(forms)}")
    for plan_key, state in (("content_with", CONTENT_WITH), ("content_empty", CONTENT_EMPTY)):
        check(f"{tag}: состояние перечня `{state}` — {expect[plan_key]} раз(а) (замер 2.2: "
              "562/203 на корпус)", content_counts.get(state, 0) == expect[plan_key],
              f"факт: {dict(content_counts)}")
    for plan_key, value in (("priv_true", "True"), ("priv_false", "False")):
        check(f"{tag}: флаг `PrivilegedGetMode` = {value.lower()} — {expect[plan_key]} "
              "раз(а) (замер 2 плана: 764/1)",
              privileged.get(value, 0) == expect[plan_key], f"факт: {dict(privileged)}")

    # Форма адреса вычисляется по самому адресу — по ней она и разрешается (мера M5).
    # Пересчёт идёт функцией разбора по сохранённому `location_full_name`: если бы писатель
    # перепутал колонки, пересчёт не совпал бы с сохранённым значением.
    form_diff = []
    for row in db_rows:
        expected_form = location_target_form(row["location_full_name"])
        if str(row["location_target_form"]) != expected_form:
            form_diff.append(f"{row['object_name']}: сохранено {row['location_target_form']!r},"
                             f" адрес {_brief(row['location_full_name'])} даёт "
                             f"{expected_form!r}")
    check(f"{tag}: `location_target_form` равна форме сохранённого адреса (пересчёт "
          "функцией разбора)", not form_diff, "; ".join(form_diff[:4]))

    unknown_states = sum(1 for row in db_rows
                         if str(row["properties_state"]) != PROPS_ALL_KNOWN)
    check(f"{tag}: все {len(db_rows)} строк разобраны без неизвестных тегов и значений "
          "(`all_known`), состояний `unknown_tag`/`unknown_value`/`absent` — ноль",
          unknown_states == 0 and len(db_rows) == expect["db_rows"],
          f"строк с иным состоянием: {unknown_states}")


# ── контур 5: строки применения против элементов `<Object>` файла (независимая мера) ─────────
def file_content_items(dump_dir):
    """Элементы перечня по тексту файла регистрации: имя цели и порядок в файле.

    Мера независима от разбора: регулярные выражения, а не словарь состояний. Ребро
    `<xr:Object>` встречается в выгрузке только внутри `<Content>` (замер 2.2: адрес
    несёт элемент `<Location>`), поэтому блок перечня и есть круг применения. Порядок
    (`ordinal`) проверяется по позициям элементов в файле — тот же приём, что в V49/V50.
    Признака `UseContentFilter` в схеме нет (колонок под него узел V56 не заводил:
    элемент в четырёх выгрузках не даётся), поэтому и мера его не считает.
    """
    root = Path(dump_dir) / DIR_NAME
    result = {}
    if not root.exists():
        return result
    for entry in sorted(root.glob("*.xml")):
        text, error = read_text_file(entry)
        if error or text is None:
            continue
        name_match = NAME_RE.search(text)
        option_name = name_match.group(1).strip() if name_match else entry.stem
        items = []
        for block in CONTENT_BLOCK_RE.findall(text):
            if not block:
                continue
            for position, element in enumerate(CONTENT_ITEM_RE.finditer(block)):
                inner = element.group(1)
                # Ребро перечня несёт имя цели текстом элемента (`<xr:Object>Document.Имя
                # </xr:Object>`), вложенного `<Name>` у него нет — снимать теги, а не искать
                # их (иначе мера называла бы цель пустой и сравнивала бы не с тем).
                target = re.sub(r"<[^>]+>", "", inner).strip()
                items.append({"target_full_name": target, "position": position})
        result[option_name] = items
    return result


def compare_content_rows(parsed, content_rows, dump_dir, expect, tag):
    section(f"Контур 5 — строки применения против перечня файла ({tag})")
    raw_items = file_content_items(dump_dir)
    parsed_content = parsed["targets"]
    raw_total = sum(len(v) for v in raw_items.values())
    check(f"{tag}: строк применения — {expect['targets']} (замер 2.2 плана)",
          len(content_rows) == expect["targets"] == len(parsed_content),
          f"база: {len(content_rows)}, разбор: {len(parsed_content)}")
    check(f"{tag}: элементов `<Content><xr:Object>` по тексту файлов — {raw_total}, строк "
          "применения в базе столько же (мера M2: ни цели, ни порядка не потеряно)",
          raw_total == len(content_rows),
          f"файлы: {raw_total}, база: {len(content_rows)}")

    parsed_keys = sorted((str(r["option_full_name"]), int(r["ordinal"]),
                          str(r["target_full_name"])) for r in parsed_content)
    db_keys = sorted((str(r["option_full_name"]), int(r["ordinal"]),
                      str(r["target_full_name"])) for r in content_rows)
    only_parsed = [f"{k[0]}#{k[1]}" for k in parsed_keys if k not in set(db_keys)]
    only_db = [f"{k[0]}#{k[1]}" for k in db_keys if k not in set(parsed_keys)]
    check(f"{tag}: ключи строк применения (вид, порядок, адрес цели) совпадают с разбором",
          parsed_keys == db_keys,
          f"только в разборе: {names(only_parsed)}; только в базе: {names(only_db)}")

    parsed_index = {(str(r[OPTION_LINK_KEY]), int(r["ordinal"])): r
                    for r in parsed_content}
    value_diff = []
    for row in content_rows:
        key = (str(row["option_full_name"]), int(row["ordinal"]))
        parsed_row = parsed_index.get(key)
        if parsed_row is None:
            continue
        if str(row["target_object_uuid"]).lower() != str(
                parsed_row["target_object_uuid"] or "").lower():
            value_diff.append(f"{key[0]}#{key[1]}: uuid цели "
                              f"{_brief(parsed_row['target_object_uuid'])} ↔ "
                              f"{_brief(row['target_object_uuid'])}")
        if str(row["target_object_id"] or "") != str(parsed_row["target_object_id"] or ""):
            value_diff.append(f"{key[0]}#{key[1]}: id цели "
                              f"{_brief(parsed_row['target_object_id'])} ↔ "
                              f"{_brief(row['target_object_id'])}")
        if str(row["target_resolve_state"]) != str(parsed_row["target_resolve_state"]):
            value_diff.append(
                f"{key[0]}#{key[1]}: состояние "
                f"{_brief(parsed_row['target_resolve_state'])} ↔ "
                f"{_brief(row['target_resolve_state'])}")
        if (str(row["target_unresolved_path"] or "")
                != str(parsed_row["target_unresolved_path"] or "")):
            value_diff.append(f"{key[0]}#{key[1]}: остаток пути "
                              f"{_brief(parsed_row['target_unresolved_path'])} ↔ "
                              f"{_brief(row['target_unresolved_path'])}")
    check(f"{tag}: значения `target_object_uuid`, `target_object_id`, "
          "`target_resolve_state`, `target_unresolved_path` совпадают с разбором",
          not value_diff, "; ".join(value_diff[:5]))

    # Файл ↔ база: адрес цели и порядок по позициям элементов. Ключ — имя вида из
    # `<Name>` файла против `option_full_name` строки применения (префикс вида снимается
    # тем же разделителем, каким он ставится: `INDEX_NAME_SEPARATOR`).
    db_by_option = {}
    for row in content_rows:
        full = str(row["option_full_name"])
        prefix = f"{INDEX_OBJECT_TYPE}{INDEX_NAME_SEPARATOR}"
        plain = full[len(prefix):] if full.startswith(prefix) else full
        db_by_option.setdefault(plain, []).append(row)
    file_diff = []
    for option_name, items in sorted(raw_items.items()):
        rows = sorted(db_by_option.get(option_name, []), key=lambda r: int(r["ordinal"]))
        if len(rows) != len(items):
            file_diff.append(f"{option_name}: элементов {len(items)}, строк {len(rows)}")
            continue
        for item, row in zip(items, rows):
            if str(row["target_full_name"]) != item["target_full_name"]:
                file_diff.append(f"{option_name}: адрес {_brief(row['target_full_name'])} ↔ "
                                 f"{_brief(item['target_full_name'])}")
            if int(row["ordinal"]) != item["position"]:
                file_diff.append(f"{option_name}: порядок {row['ordinal']} ≠ позиции "
                                 f"{item['position']} в файле")
    check(f"{tag}: адрес цели и порядок каждой строки применения равны элементу файла "
          "(признака `UseContentFilter` в схеме нет — колонок под него узел V56 не заводил)",
          not file_diff, "; ".join(file_diff[:5]))

    ordinal_diff = []
    for option_name, rows in sorted(db_by_option.items()):
        orders = [int(row["ordinal"]) for row in rows]
        if orders != list(range(len(orders))):
            ordinal_diff.append(f"{option_name}: {orders}")
    check(f"{tag}: порядки целей непрерывны от 0 внутри каждой опции (CHECK "
          "`functional_option_content_ordinal_non_negative`)", not ordinal_diff,
          "; ".join(ordinal_diff[:5]))

    # Вид метаданных цели пересчитывается из сохранённого адреса — тем же словарём, каким
    # он был вычислен при разборе (мера M5).
    type_diff = []
    for row in content_rows:
        expected_type = target_object_type(row["target_full_name"])
        if str(row["target_object_type"]) != expected_type:
            type_diff.append(f"{row['option_full_name']}: сохранено "
                             f"{row['target_object_type']!r}, адрес "
                             f"{_brief(row['target_full_name'])} даёт {expected_type!r}")
    check(f"{tag}: `target_object_type` равна виду сохранённого адреса цели (пересчёт)",
          not type_diff, "; ".join(type_diff[:5]))

    states = Counter(str(row["target_resolve_state"]) for row in content_rows)
    check(f"{tag}: все {len(content_rows)} целей разрешены точно (`{TARGET_EXACT}` = "
          f"{expect['target_exact']}); состояний `prefix_only`/`unresolved` — ноль",
          len(content_rows) == expect["target_exact"]
          and states.get(TARGET_EXACT, 0) == expect["target_exact"], f"факт: {dict(states)}")
    kinds = Counter(str(row["target_object_type"]) for row in content_rows)
    info(f"{tag}: цели применения по видам метаданных: "
         + ", ".join(f"{kind}={count}" for kind, count in sorted(kinds.items())))
    distinct_targets = len({str(row["target_object_uuid"]) for row in content_rows})
    info(f"{tag}: уникальных целей применения — {distinct_targets} при {len(content_rows)} "
         "строках: одна цель встречается у нескольких опций, уникального ключа по цели "
         "нет осознанно (Q4, вариант A)")
    per_option = Counter(str(row["option_full_name"]) for row in content_rows)
    if per_option:
        max_option, max_count = max(per_option.items(), key=lambda kv: (-kv[1], kv[0]))
        check(f"{tag}: максимальное число целей у одной опции — {max_count} (замер 2.2: "
              f"158), опций с непустым перечнем — {expect['content_with']} (замер 2.2: "
              "562)",
              max_count <= 158 and len(per_option) == expect["content_with"],
              f"максимум: {max_count} у {max_option}, опций: {len(per_option)}")


# ── контур 6: разрешимость ссылок — пересчёт по живому индексу состава ───────────────────────
def check_resolvability(cur, header, index_info, db_rows, content_rows, expect, tag):
    """Ссылка `Location` и цель применения разрешены индексом состава данной выгрузки.

    Разрешимость проверяется дважды: пересчётом функцией `resolve_reference` по живому
    индексу (чтобы состояние не было «запомненным») и JOIN'ом с `configuration_objects`
    (чтобы сохранённый uuid цели действительно существовал в этой базе). Второе разбор
    дать не может: он работает без базы.
    """
    section(f"Контур 6 — разрешимость ссылок ({tag})")
    index_rows = list(index_info.get("rows") or [])
    by_name = index_rows_by_name(index_rows)
    pseudo = sum(1 for row in index_rows
                 if str(row.get("name") or "") !=
                 f"{row.get('object_type')}.{row.get('object_name')}")
    info(f"{tag}: записей индекса состава в базе — {len(index_rows)} (из них псевдозаписей "
         f"и записей детей — {pseudo}), вида `{INDEX_OBJECT_TYPE}` — "
         f"{index_info.get('kind_count')}")

    location_diff = []
    location_resolved = 0
    for row in db_rows:
        fresh = resolve_reference(row["location_full_name"], by_name)
        if fresh["state"] == TARGET_EXACT:
            location_resolved += 1
        stored_uuid = str(row["location_object_uuid"]).lower() if row["location_object_uuid"] else None
        fresh_uuid = str(fresh["object_uuid"]).lower() if fresh["object_uuid"] else None
        if fresh["state"] != str(row["location_state"]) or fresh_uuid != stored_uuid:
            location_diff.append(f"{row['object_name']}: сохранено "
                                 f"{row['location_state']}/{_brief(stored_uuid)}, пересчёт "
                                 f"{fresh['state']}/{_brief(fresh_uuid)}")
    check(f"{tag}: пересчёт `resolve_reference` по живому индексу состава даёт те же "
          "состояния и uuid целей, что сохранены в строках вида", not location_diff,
          "; ".join(location_diff[:5]))
    check(f"{tag}: разрешённых ссылок `Location` пересчётом — {location_resolved} "
          f"(ожидание {expect['loc_exact']} — замер 2.1 плана)",
          location_resolved == expect["loc_exact"], f"факт: {location_resolved}")

    orphans = q(cur, f"SELECT o.full_name, o.location_object_uuid FROM {OPTION_VIEW} o "
                     "JOIN configurations c ON c.uuid = o.configuration_uuid "
                     "WHERE o.configuration_uuid = %s::uuid AND "
                     "o.location_object_uuid IS NOT NULL "
                     f"AND NOT EXISTS (SELECT 1 FROM {INDEX_TABLE} i WHERE "
                     "i.configuration_id = c.id AND "
                     "i.uuid = o.location_object_uuid) "
                     "ORDER BY o.full_name", (str(header["uuid"]),))
    check(f"{tag}: uuid цели `location_object_uuid` существует в индексе состава той же "
          "конфигурации — сирот ноль", not orphans,
          "; ".join(f"{row['full_name']} → {_brief(row['location_object_uuid'])}"
                    for row in orphans[:5]))

    type_mismatch = q(cur, f"SELECT o.full_name, o.location_object_type, "
                           "i.object_type AS index_type FROM "
                           f"{OPTION_VIEW} o JOIN configurations c ON c.uuid = "
                           f"o.configuration_uuid JOIN {INDEX_TABLE} i ON i.configuration_id = "
                           "c.id AND i.uuid = o.location_object_uuid "
                           "WHERE o.configuration_uuid = %s::uuid "
                           "AND i.object_type IS DISTINCT FROM o.location_object_type "
                           "ORDER BY o.full_name", (str(header["uuid"]),))
    check(f"{tag}: `location_object_type` равна виду записи индекса, на которую указывает "
          "uuid — расхождений ноль", not type_mismatch,
          "; ".join(f"{row['full_name']}: {row['location_object_type']!r} ≠ "
                    f"{row['index_type']!r}" for row in type_mismatch[:5]))

    # Форма адреса `attribute` (6 файлов на корпус, замер 2.1) разрешается псевдозаписью
    # индекса состава, чьё `name` держит полное точечное имя колонки-носителя. Значит
    # разрешение идёт полным именем, а не срезом префикса: состояний `prefix_only` и
    # `unresolved` на всём круге не должно быть ни одной строки, а
    # `location_unresolved_path` остаётся NULL (мера M5 — форма адреса различается
    # структурой адреса, а не удачей).
    attribute_rows = [row for row in db_rows
                      if str(row["location_target_form"]) == LOCATION_FORM_ATTRIBUTE]
    check(f"{tag}: строк с формой адреса `{LOCATION_FORM_ATTRIBUTE}` — {len(attribute_rows)} "
          f"(замер 2.1: 6 на BP3), все разрешены `{TARGET_EXACT}` по полному адресу",
          len(attribute_rows) == expect["attribute"]
          and all(str(row["location_state"]) == TARGET_EXACT and row["location_ref"]
                  and str(row["location_full_name"]) in by_name for row in attribute_rows),
          f"факт: {len(attribute_rows)}, состояния: "
          f"{names(sorted({str(row['location_state']) for row in attribute_rows}))}")
    for row in attribute_rows[:2]:
        name = str(row["location_full_name"] or "")
        record = by_name.get(name) or {}
        info(f"{tag}: пример — {row['object_name']}: адрес `{name}` разрешился записью "
             f"индекса вида `{record.get('object_type')}` имени `{record.get('object_name')}`")
    half_resolved = q(cur, f"SELECT o.full_name, o.location_state, o.location_unresolved_path "
                           f"FROM {OPTION_VIEW} o WHERE o.configuration_uuid = %s::uuid AND "
                           f"(o.location_state IN (%s, %s) OR "
                           "o.location_unresolved_path IS NOT NULL) ORDER BY o.full_name",
                      (str(header["uuid"]), TARGET_PREFIX_ONLY, TARGET_UNRESOLVED))
    check(f"{tag}: ссылок, разрешённых лишь префиксом (`{TARGET_PREFIX_ONLY}`) или не "
          f"разрешённых вовсе (`{TARGET_UNRESOLVED}`), — ноль; `location_unresolved_path` "
          "не заполнен ни у одной строки", not half_resolved,
          "; ".join(f"{row['full_name']} → {row['location_state']}"
                    for row in half_resolved[:5]))


    content_diff = []
    for row in content_rows:
        fresh = resolve_reference(row["target_full_name"], by_name)
        stored = row["target_object_uuid"]
        stored_uuid = str(stored).lower() if stored else None
        fresh_uuid = str(fresh["object_uuid"]).lower() if fresh["object_uuid"] else None
        if fresh["state"] != str(row["target_resolve_state"]) or fresh_uuid != stored_uuid:
            content_diff.append(f"{row['option_full_name']}#{row['ordinal']}: сохранено "
                                f"{row['target_resolve_state']}/{_brief(stored_uuid)}, "
                                f"пересчёт {fresh['state']}/{_brief(fresh_uuid)}")
    check(f"{tag}: пересчёт разрешения целей применения по живому индексу совпадает со "
          "строками применения", not content_diff, "; ".join(content_diff[:5]))
    content_orphans = q(cur, f"SELECT c.option_full_name, c.ordinal, c.target_object_uuid "
                             f"FROM {CONTENT_VIEW} c JOIN configurations cfg "
                             "ON cfg.uuid = c.configuration_uuid WHERE c.configuration_uuid = "
                             "%s::uuid AND c.target_object_uuid IS NOT NULL AND NOT EXISTS "
                             f"(SELECT 1 FROM {INDEX_TABLE} i WHERE i.configuration_id = cfg.id "
                             "AND i.uuid = c.target_object_uuid) ORDER BY c.option_full_name, "
                             "c.ordinal", (str(header["uuid"]),))
    check(f"{tag}: uuid цели применения существует в индексе состава — сирот ноль",
          not content_orphans,
          "; ".join(f"{row['option_full_name']}#{row['ordinal']} → "
                    f"{_brief(row['target_object_uuid'])}" for row in content_orphans[:5]))
    bad_target_type = q(cur, f"SELECT c.option_full_name, c.ordinal, c.target_object_type, "
                             "i.object_type AS index_type FROM "
                             f"{CONTENT_VIEW} c JOIN configurations cfg ON cfg.uuid = "
                             f"c.configuration_uuid JOIN {INDEX_TABLE} i ON "
                             "i.configuration_id = cfg.id AND i.uuid = c.target_object_uuid "
                             "WHERE c.configuration_uuid = %s::uuid "
                             "AND i.object_type IS DISTINCT FROM c.target_object_type "
                             "ORDER BY c.option_full_name, c.ordinal", (str(header["uuid"]),))
    check(f"{tag}: `target_object_type` равна виду записи индекса цели — расхождений ноль",
          not bad_target_type,
          "; ".join(f"{row['option_full_name']}#{row['ordinal']}: "
                    f"{row['target_object_type']!r} ≠ {row['index_type']!r}"
                    for row in bad_target_type[:5]))
    half_targets = q(cur, f"SELECT c.option_full_name, c.ordinal, c.target_resolve_state FROM "
                          f"{CONTENT_VIEW} c WHERE c.configuration_uuid = %s::uuid AND "
                          f"c.target_resolve_state IN (%s, %s) ORDER BY c.option_full_name, "
                          "c.ordinal", (str(header["uuid"]), TARGET_PREFIX_ONLY,
                                        TARGET_UNRESOLVED))
    check(f"{tag}: целей применения, разрешённых лишь префиксом или не разрешённых, — ноль "
          "(замер 2.2 плана: `exact` на все 10 063 цели)", not half_targets,
          "; ".join(f"{row['option_full_name']}#{row['ordinal']} → "
                    f"{row['target_resolve_state']}" for row in half_targets[:5]))
    filled_paths = q(cur, f"SELECT c.option_full_name, c.ordinal FROM {CONTENT_VIEW} c "
                          "WHERE c.configuration_uuid = %s::uuid AND "
                          "c.target_unresolved_path IS NOT NULL ORDER BY c.option_full_name, "
                          "c.ordinal LIMIT 5", (str(header["uuid"]),))
    check(f"{tag}: `target_unresolved_path` заполнен только при `prefix_only`/`unresolved` — "
          "на этом круге он не заполнен ни у одной строки", not filled_paths,
          "; ".join(f"{row['option_full_name']}#{row['ordinal']}" for row in filled_paths))



# ── контур 7: витрины текущего состояния, цепь ревизий, сироты ───────────────────────────────
def view_definition(cur, view):
    row = one(cur, "SELECT pg_get_viewdef(%s::regclass, true) AS def", (view,))
    return str(row.get("def") or "") if row else ""


def check_revisions_and_views(cur):
    section("Контур 7 — витрины текущего состояния, цепь ревизий и сироты")
    current_direct = scalar(
        cur, f"SELECT count(*) FROM {TABLE_NAME} o WHERE NOT exists("
             f"SELECT 1 FROM {TABLE_NAME} n WHERE n.configuration_uuid = o.configuration_uuid "
             "AND n.object_name = o.object_name AND n.revision_no > o.revision_no)")
    in_view = scalar(cur, f"SELECT count(*) FROM {OPTION_VIEW}")
    check(f"витрина `{OPTION_VIEW}` отдаёт ровно строки максимальной ревизии "
          f"({current_direct} строк)", current_direct == in_view,
          f"вне витрины: {current_direct}, в витрине: {in_view}")
    outside = scalar(cur, f"SELECT count(*) FROM {TABLE_NAME} o WHERE NOT exists("
                          f"SELECT 1 FROM {OPTION_VIEW} v WHERE v.id = o.id)")
    check(f"строк `{TABLE_NAME}` вне витрины текущего состояния — ноль", not outside,
          f"вне витрины: {outside}")

    header_orphans = scalar(
        cur, f"SELECT count(*) FROM {TABLE_NAME} o WHERE NOT exists("
             "SELECT 1 FROM configurations c WHERE c.uuid = o.configuration_uuid)")
    check("строк вида без заголовка конфигурации — ноль (внешнего ключа нет осознанно, "
          "поэтому сироту считает проверка, а не схема — прецедент V20.1)",
          not header_orphans, f"сирот: {header_orphans}")

    index_orphans = scalar(
        cur, f"SELECT count(*) FROM {TABLE_NAME} o WHERE NOT exists("
              "SELECT 1 FROM configurations c "
              f"JOIN {INDEX_TABLE} i ON i.configuration_id = c.id "
              "WHERE c.uuid = o.configuration_uuid AND i.object_type = %s "
              "AND i.parent_name IS NULL AND i.uuid = o.object_uuid)", (INDEX_OBJECT_TYPE,))
    check("строка вида обязана соответствовать записи индекса состава той же конфигурации "
          "(подтверждение по живой БД, правило V43) — расхождений ноль",
          not index_orphans, f"без записи индекса: {index_orphans}")

    # Строка применения версионируется НЕ своей цепью (Q2, вариант A): ключ начинается с
    # числового id конкретной ревизии вида. Значит каждая строка применения обязана висеть
    # на ТЕКУЩЕЙ ревизии — иначе витрина применения показала бы состав, которого в выгрузке
    # нет, а каскад Q11 не сработал бы при снятии вида.
    stale_children = scalar(
        cur, f"SELECT count(*) FROM {CONTENT_TABLE_NAME} c JOIN {TABLE_NAME} o "
             "ON o.id = c.functional_option_id WHERE exists(SELECT 1 FROM "
             f"{TABLE_NAME} n WHERE n.configuration_uuid = o.configuration_uuid "
             "AND n.object_name = o.object_name AND n.revision_no > o.revision_no)")
    check(f"строк применения, висящих на не-текущей ревизии вида, — ноль (связь держит id "
          "конкретной ревизии, а не пару uuid+имя — Q2, вариант A)", not stale_children,
          f"таких строк: {stale_children}")
    child_orphans = scalar(
        cur, f"SELECT count(*) FROM {CONTENT_TABLE_NAME} c WHERE NOT exists("
              f"SELECT 1 FROM {TABLE_NAME} o WHERE o.id = c.functional_option_id)")
    check(f"сирот в `{CONTENT_TABLE_NAME}` (строка применения без строки вида) — ноль",
          not child_orphans, f"сирот: {child_orphans}")
    link_mismatch = scalar(
        cur, f"SELECT count(*) FROM {CONTENT_TABLE_NAME} c JOIN {TABLE_NAME} o "
             "ON o.id = c.functional_option_id WHERE c.configuration_uuid IS DISTINCT FROM "
             "o.configuration_uuid")
    check("`configuration_uuid` строки применения совпадает с конфигурацией строки вида "
          "(дублирование колонки нужно предикату витрины — Q2)", not link_mismatch,
          f"расхождений: {link_mismatch}")

    # Состав витрин: витрина применения читается через витрину вида, а не через версионируемую
    # таблицу. Иначе строки не-текущей ревизии попали бы в ответ — тот же дефект, из-за
    # которого порядок снятия круга начинается с детей (M7).
    option_view_def = view_definition(cur, OPTION_VIEW)
    content_view_def = view_definition(cur, CONTENT_VIEW)
    check(f"витрина `{OPTION_VIEW}` держится предиката «максимальный `revision_no` по "
          "ключу цепочки» (правило узла V19, а не собственного `max()` вызывающего)",
          "revision_no" in option_view_def and " > " in option_view_def
          and "EXISTS" in option_view_def.upper(),
          _brief(option_view_def[:200]))
    check(f"витрина `{CONTENT_VIEW}` связывается с витриной `{OPTION_VIEW}`, а не с "
          f"версионируемой таблицей `{TABLE_NAME}`",
          OPTION_VIEW in content_view_def
          and not re.search(r"(?<!v_current_)functional_options\b", content_view_def),
          _brief(content_view_def[:200]))
    for view in (OPTION_VIEW, CONTENT_VIEW):
        columns = table_columns(cur, view)
        check(f"`{view}`: колонка `configuration_uuid` открыта — предикат выбора круга "
              "читателя", "configuration_uuid" in columns, names(columns))
    exposed = set(table_columns(cur, OPTION_VIEW)) - set(table_columns(cur, TABLE_NAME))
    check(f"витрина вида не привносит колонок, которых нет в таблице (состав читается "
          "тем же словарём)", not exposed, names(sorted(exposed)))

    # Чужие круги: детей у вида, кроме собственной таблицы применения, нет; внешний ключ на
    # вид из чужих таблиц не заявлен ни одним узлом (позиция O1 плана — ссылки других слоёв
    # разбираются отдельным узлом, здесь называется граница).
    parents = q(cur, "SELECT conrelid::regclass::text AS child, conname, confrelid::regclass::text "
                     "AS parent FROM pg_constraint WHERE contype = 'f' AND confrelid = "
                     "%s::regclass AND conrelid::regclass::text <> %s ORDER BY conname",
                (TABLE_NAME, CONTENT_TABLE_NAME))
    check("внешних ключей чужих таблиц на `functional_options` — ноль (ссылки других слоёв "
          "на вид — позиция O1 плана, отдельный узел)", not parents,
          "; ".join(f"{row['child']}.{row['conname']}" for row in parents[:5]))
    children = q(cur, "SELECT conrelid::regclass::text AS child FROM pg_constraint "
                      "WHERE contype = 'f' AND confrelid = %s::regclass "
                      "ORDER BY conrelid::regclass::text", (TABLE_NAME,))
    child_tables = sorted(str(row["child"]) for row in children)
    check(f"таблиц, ссылающихся на `{TABLE_NAME}`, — ровно {len(child_tables)}: "
          f"`{CONTENT_TABLE_NAME}` (связь слоя держит FK, каскад Q11)",
          child_tables == [CONTENT_TABLE_NAME], f"факт: {names(child_tables)}")

    deep = scalar(cur, f"SELECT count(*) FROM {TABLE_NAME} WHERE revision_no > 1")
    info(f"строк не первой ревизии в `{TABLE_NAME}`: {deep} (цепь узла V19 жива; "
         "перезагрузки со второй ревизией корпус не давал)")

# ── контур 8: контракт стадии, круга снятия и реестра сохранённых видов ────────────────────────
def check_contract():
    section("Контур 8 — контракт стадии, круга снятия и реестра сохранённых видов")
    ids = [stage for stage, _title in STAGES]
    check(f"стадия `{STAGE_FUNCTIONAL_OPTIONS}` стоит сразу после `{STAGE_BOTS}` (позиции "
          "2.10 → 2.11 нормативного списка, а не порядок литер)",
          ids.index(STAGE_FUNCTIONAL_OPTIONS) == ids.index(STAGE_BOTS) + 1,
          f"порядок: {ids}")
    check(f"`{STAGE_OBJECT_MODULES}` остаётся последней стадией (вторая транзакция текстов), "
          f"а справа у `{STAGE_FUNCTIONAL_OPTIONS}` — `{STAGE_FUNCTIONAL_OPTIONS_PARAMETERS}` "
          "(узел V57, позиция 2.12)",
          ids[-1] == STAGE_OBJECT_MODULES
          and ids.index(STAGE_FUNCTIONAL_OPTIONS) == len(ids) - 3
          and ids[ids.index(STAGE_FUNCTIONAL_OPTIONS) + 1]
              == STAGE_FUNCTIONAL_OPTIONS_PARAMETERS,
          f"порядок: {ids}")
    check(f"`stages_after('{STAGE_BOTS}')` называет продолжением `{STAGE_FUNCTIONAL_OPTIONS}`",
          stages_after(STAGE_BOTS)[:1] == [STAGE_FUNCTIONAL_OPTIONS],
          str(stages_after(STAGE_BOTS)))
    check(f"`stages_after('{STAGE_FUNCTIONAL_OPTIONS}')` называет продолжением "
          f"`{STAGE_FUNCTIONAL_OPTIONS_PARAMETERS}` (узел V57), а не `{STAGE_OBJECT_MODULES}`; "
          "последней стадией хвоста `s4b_object_modules` при этом остаётся",
          stages_after(STAGE_FUNCTIONAL_OPTIONS)[:1]
          == [STAGE_FUNCTIONAL_OPTIONS_PARAMETERS]
          and stages_after(STAGE_FUNCTIONAL_OPTIONS)[-1:] == [STAGE_OBJECT_MODULES],
          str(stages_after(STAGE_FUNCTIONAL_OPTIONS)))
    check(f"у стадии `{STAGE_FUNCTIONAL_OPTIONS}` есть зеркало продолжения "
          "(`STAGE_FULL_RELOAD_ONLY` = False — стадия дозакрывается отдельным входом)",
          STAGE_FULL_RELOAD_ONLY.get(STAGE_FUNCTIONAL_OPTIONS) is False,
          str(STAGE_FULL_RELOAD_ONLY.get(STAGE_FUNCTIONAL_OPTIONS)))
    title = stage_title(STAGE_FUNCTIONAL_OPTIONS)
    hint = stage_resume_hint(STAGE_FUNCTIONAL_OPTIONS)
    check("заголовок стадии называет позицию 2.11 и каталог вида",
          "2.11" in title and DIR_NAME in title, _brief(title))
    check("подсказка продолжения называет отдельный вход `load_functional_options_tool` и "
          "полную перезагрузку",
          "load_functional_options_tool" in hint and "load_1c_catalog_tool" in hint,
          _brief(hint))
    check("подсказка продолжения равна константе круга (текст один, а не пересказ)",
          hint == FUNCTIONAL_OPTIONS_REPEAT_HINT, _brief(hint))
    check(f"круг записи стадии — две таблицы (`{TABLE_NAME}`, `{CONTENT_TABLE_NAME}`) — Q1, "
          "вариант A: строка применения существует только через строку опции",
          tuple(FUNCTIONAL_OPTIONS_TABLES) == (TABLE_NAME, CONTENT_TABLE_NAME),
          str(FUNCTIONAL_OPTIONS_TABLES))
    check("круг снятия начинается с таблицы применения: FK объявлен с `ON DELETE CASCADE`, и "
          "каскад снял бы строки молча без точного счётчика (M7, прецеденты V50/V52/V54)",
          tuple(FUNCTIONAL_OPTIONS_REMOVE_ORDER) == (CONTENT_TABLE_NAME, TABLE_NAME),
          str(FUNCTIONAL_OPTIONS_REMOVE_ORDER))
    check("обе таблицы круга названы в `FOREIGN_STAGE_TABLES` — иначе стадия S4 снимала бы "
          "чужие строки вида (дефект, закрытый константой `FUNCTIONAL_OPTIONS_TABLES`)",
          all(table in FOREIGN_STAGE_TABLES for table in FUNCTIONAL_OPTIONS_TABLES),
          f"перечень: {names(FOREIGN_STAGE_TABLES)}")
    entry = STORED_META_KINDS.get(FUNCTIONAL_OPTIONS_META_TAG) or {}
    check(f"вид `{FUNCTIONAL_OPTIONS_META_TAG}` назван сохранённым в реестре "
          f"`STORED_META_KINDS` кругом {tuple(FUNCTIONAL_OPTIONS_TABLES)} и позицией 2.11 — "
          "тем же словарём, которым пользуется карточка загрузки (прецедент V55)",
          bool(entry)
          and tuple(entry.get("tables") or ()) == tuple(FUNCTIONAL_OPTIONS_TABLES)
          and str(entry.get("position")) == "2.11" and str(entry.get("node")) == "V56",
          f"запись реестра: {_brief(entry)}")
    check(f"словарь вида один: метка `{FUNCTIONAL_OPTIONS_META_TAG}` и каталог "
          f"`{FUNCTIONAL_OPTIONS_DIR}` контракта совпадают со словарём разбора",
          FUNCTIONAL_OPTIONS_META_TAG == OBJECT_KIND_TAG == INDEX_OBJECT_TYPE
          and FUNCTIONAL_OPTIONS_DIR == DIR_NAME,
          f"контракт: {FUNCTIONAL_OPTIONS_META_TAG}/{FUNCTIONAL_OPTIONS_DIR}, разбор: "
          f"{OBJECT_KIND_TAG}/{DIR_NAME}")
    check("граница круга называется константой, которую читают оба формата ответа: текст "
          "называет обе таблицы, три ноги круга и расхождения ног",
          TABLE_NAME in FUNCTIONAL_OPTIONS_CIRCLE_BOUNDARY
          and CONTENT_TABLE_NAME in FUNCTIONAL_OPTIONS_CIRCLE_BOUNDARY
          and "2.11" in FUNCTIONAL_OPTIONS_CIRCLE_BOUNDARY
          and all(key in FUNCTIONAL_OPTIONS_CIRCLE_BOUNDARY for key in CIRCLE_DISCREPANCIES),
          _brief(FUNCTIONAL_OPTIONS_CIRCLE_BOUNDARY[:200]))
    check("заголовок раздела карточки называет узел V56 и позицию 2.11",
          "V56" in FUNCTIONAL_OPTIONS_SECTION_HEADER
          and "2.11" in FUNCTIONAL_OPTIONS_SECTION_HEADER,
          _brief(FUNCTIONAL_OPTIONS_SECTION_HEADER))

    # Закрытый контракт ответа (C1, C2, C3): нули обязаны быть названы по полному словарю,
    # иначе «стадия не выполнена» читается как «строк нет».
    defaults = functional_options_defaults()
    needed = set(SUMMARY_KEYS) | set(COUNT_KEYS)
    missing = sorted(key for key in needed if key not in defaults)
    check(f"нулевой контракт перечисляет все ключи сводки разбора ({len(needed)} ключей "
          "`SUMMARY_KEYS` и `COUNT_KEYS`)", not missing, names(missing))
    check("нулевой контракт называет круг снятия, стадию и каталог — ответ не зависит от "
          "удачи выгрузки",
          defaults.get("tables") == list(FUNCTIONAL_OPTIONS_REMOVE_ORDER)
          and defaults.get("stage") == STAGE_FUNCTIONAL_OPTIONS
          and defaults.get("directory") == DIR_NAME,
          f"tables: {_brief(defaults.get('tables'))}, stage: {defaults.get('stage')}")
    bad_counts = [f"{key} ≠ {COUNT_STATE_KEYS[key]}" for key in COUNT_KEYS
                  if sorted((defaults.get(key) or {}).keys()) != sorted(
                      STATE_VOCABULARIES[COUNT_STATE_KEYS[key]])]
    check(f"словари состояний нулевого контракта построены по полному словарю колонок "
          f"({len(COUNT_KEYS)} словарей, включая `counts_by_location_form` → "
          "`location_target_form`)", not bad_counts, "; ".join(bad_counts))
    check("нулевой контракт называет состояния колонок целиком: `state_columns()` равна "
          "перечню контракта",
          sorted(defaults.get("state_columns") or []) == sorted(STATE_VOCABULARIES),
          f"контракт: {names(sorted(defaults.get('state_columns') or []))}")
    numbers = {key: value for key, value in defaults.items()
               if isinstance(value, int) and not isinstance(value, bool)}
    check(f"числовые поля нулевого контракта равны нулю ({len(numbers)} полей) — «не "
          "выполнялась» не читается как «строк нет»",
          all(value == 0 for value in numbers.values()),
          f"ненулевые: {names(sorted(key for key, value in numbers.items() if value))}")
    check("нулевой контракт помечает стадию невыполненной (`success` False, статус ≠ успех)",
          defaults.get("success") is False and defaults.get("status") not in ("ok", True),
          f"status: {defaults.get('status')}")
    not_run = [str(line) for line in (format_functional_options_lines(defaults) or [])]
    check("форматтер невыполненной стадии называет сам факт («стадия не выполнена») и чем "
          "продолжить, а не нули строк (C1)",
          bool(not_run) and any("не выполнена" in line for line in not_run)
          and any(TOOL_NAME in line for line in not_run), _brief(compact(not_run[:3])))
    check("форматтер невыполненной стадии не приписывает кругу строк: текст не утверждает "
          "«записано N» при N больше нуля",
          not any("записано" in line and any(digit in line for digit in "123456789")
                  for line in not_run), _brief(compact(not_run[:6])))
    failure = dict(functional_options_defaults())
    failure.update({"status": "error", "success": False,
                    "error": "Круг не записан: 2 файла каталога не разобраны",
                    "reason": "отказ разбора",
                    "files_failed": [{"source_path": f"{DIR_NAME}/Опция.xml",
                                      "reason": "не читается XML"}]})
    failure_lines = [str(line)
                     for line in (format_functional_options_lines(failure) or [])]
    check("форматтер отказа разбора называет причину, стоп до записи и файл-виновник: «не "
          "записано» и «нечего записывать» — разные ответы (C1, приём V12/V46…V55)",
          any("не разобраны" in line for line in failure_lines)
          and any("ДО записи" in line and TABLE_NAME in line for line in failure_lines)
          and any("Опция.xml" in line for line in failure_lines),
          _brief(compact(failure_lines[:4])))
    success = dict(functional_options_defaults())
    success.update({"status": "ok", "success": True})
    success_lines = [str(line)
                     for line in (format_functional_options_lines(success) or [])]
    check("форматтер называет каталог круга и обе таблицы с нулями даже при пустом ответе "
          "успеха: «записано 0» отличается от «стадия не выполнялась»",
          any(DIR_NAME in line for line in success_lines)
          and all(TABLE_NAME in line and CONTENT_TABLE_NAME in line
                  for line in success_lines if "записано" in line),
          _brief(compact(success_lines[:3])))

# ── контур 8.1: отдельный вход группы — регистрация в реестре MCP ─────────────────────────────
TOOL_NAME = "load_functional_options_tool"


def read_repo_text(rel_path):
    """Текст файла репозитория — реестр инструментов читается текстом, а не импортом.

    Импортировать `server_configurations_core.py` нельзя: импорт поднимает сервер MCP и
    его зависимости, а проверка обязана работать и без запущенного сервера. Состав реестра
    сторожит `tools/check_mcp_tool_wiring.py`, поэтому здесь сверяются два текста: объявление
    инструмента и запись в `EXPECTED_TOOLS`.
    """
    path = ROOT / rel_path
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def check_tool_registration():
    section("Контур 8.1 — регистрация отдельного входа в реестре MCP")
    server_text = read_repo_text("server_configurations_core.py")
    check(f"`{TOOL_NAME}` объявлен инструментом сервера "
          "`server_configurations_core.py` (`@mcp.tool()` — реестр, а не память)",
          f"def {TOOL_NAME}(" in server_text and "@mcp.tool" in server_text,
          _brief(f"def {TOOL_NAME}(: {'есть' if f'def {TOOL_NAME}(' in server_text else 'нет'}"
                 f", @mcp.tool: {'есть' if '@mcp.tool' in server_text else 'нет'})"))
    wiring_text = read_repo_text("tools/check_mcp_tool_wiring.py")
    check(f"`{TOOL_NAME}` внесён в `EXPECTED_TOOLS` файла "
          "`tools/check_mcp_tool_wiring.py` — состав реестра сторожит она, а не обещание "
          "подсказки продолжения",
          TOOL_NAME in wiring_text, f"файл: {ROOT / 'tools/check_mcp_tool_wiring.py'}")
    loader_text = read_repo_text("src/configuration_functional_options_loader.py")
    check("отдельный вход реализован слоем `src/configuration_functional_options_loader.py` "
          "(`load_functional_options`)",
          "def load_functional_options(" in loader_text,
          f"файл: {ROOT / 'src/configuration_functional_options_loader.py'}")
    pipeline_text = read_repo_text("src/configuration_loader.py")
    check(f"конвейер вызывает стадию `{STAGE_FUNCTIONAL_OPTIONS}` тем же слоем — отдельный "
          "вход и конвейер не два разных разбора (прецеденты V48…V55)",
          "load_functional_options(" in pipeline_text
          and STAGE_FUNCTIONAL_OPTIONS in pipeline_text,
          f"файл: {ROOT / 'src/configuration_loader.py'}")
    router_text = read_repo_text("src/config_load_router.py")
    check("карточка загрузки печатает раздел стадии (заголовок и форматтер читаются из "
          "контракта, а не пересказываются)",
          "FUNCTIONAL_OPTIONS_SECTION_HEADER" in router_text
          and "format_functional_options_lines" in router_text,
          f"файл: {ROOT / 'src/config_load_router.py'}")


# ── контур 9: корпус и чужие таблицы ──────────────────────────────────────────────────────────
# Пары «мера прогона ↔ ключ эталона плана»: суммы по четырём выгрузкам сравниваются с
# разделами 1.1, 2.1, 2.2 плана V56, а не с числом, выведенным из самого прогона.
CORPUS_KEYS = (
    ("files", "files"), ("index_records", "index_records"),
    ("header_names", "header_names"), ("db_rows", "db_rows"),
    ("targets", "targets"), ("loc_exact", "loc_exact"),
    ("single", "single"), ("register_resource", "register_resource"),
    ("attribute", "attribute"), ("other", "other"),
    ("content_with", "content_with"), ("content_empty", "content_empty"),
    ("target_exact", "target_exact"),
    ("priv_true", "priv_true"), ("priv_false", "priv_false"),
    ("sibling_index", "sibling_index"), ("max_targets", "max_targets"),
    ("circle_discrepancies", "circle_discrepancies"),
    ("unknown_states", "unknown_states"), ("unresolved_total", "unresolved_total"),
)

# Формы адреса — открытым именем, потому что пустая форма (`''`) в счётчике базы именно
# пустая строка: «адреса нет» и «формы нет» различаются состоянием, а не подстановкой.
FORM_MEASURE_KEYS = {
    LOCATION_FORM_SINGLE: "single",
    LOCATION_FORM_REGISTER_RESOURCE: "register_resource",
    LOCATION_FORM_ATTRIBUTE: "attribute",
    LOCATION_FORM_EMPTY: "empty_form",
}


def foreign_state(cur):
    """Число строк чужих таблиц — одно число на таблицу, отсутствующая — None."""
    state = {}
    for table in FOREIGN_TABLES:
        try:
            state[table] = scalar(cur, f"SELECT count(*) FROM {table}")
        except Exception:  # noqa: BLE001 — отсутствующую таблицу назовёт следующий контур
            cur.connection.rollback()
            state[table] = None
    return state


def check_non_interference(before, after):
    section("Уборка за чужими таблицами (прогон читающий)")
    touched = [table for table in FOREIGN_TABLES if before.get(table) != after.get(table)]
    check(f"чужих таблиц затронуто — {len(touched)} (прогон ничего не пишет)",
          not touched, f"изменились: {names(touched)}")
    missing = [table for table in FOREIGN_TABLES if after.get(table) is None]
    check(f"отсутствующих чужих таблиц в базе — {len(missing)} (названы, а не пропущены)",
          not missing, names(missing))
    if before.get("bsl_modules") is not None and after.get("bsl_modules") is not None:
        check("строк `bsl_modules` в прогоне не снято ни одной — узел V56 не трогает круг "
              "V47 (тексты модулей — чужой узел)",
              before["bsl_modules"] == after["bsl_modules"],
              f"до: {before['bsl_modules']}, после: {after['bsl_modules']}")


def accumulate_corpus(accum, kind_totals, db_rows, content_rows, parsed, raw, agg,
                      header_count, header_is_null):
    """Суммы прогона по всем четырём выгрузкам — мерой прогона, а не числом плана."""
    accum["files"] += int(raw.get("files") or 0)
    accum["index_records"] += int(agg.get("kind_rows") or 0)
    accum["sibling_index"] += int(agg.get("sibling_rows") or 0)
    accum["header_names"] += int(header_count or 0)
    accum["header_null"] += 1 if header_is_null else 0
    accum["db_rows"] += len(db_rows)
    accum["targets"] += len(content_rows)
    accum["max_targets"] = max(accum["max_targets"],
                               int(parsed.get("max_targets_per_file") or 0))
    accum["targets_distinct"] += int(parsed.get("targets_distinct") or 0)
    for key in CIRCLE_DISCREPANCIES:
        accum["circle_discrepancies"] += len(parsed.get(key) or [])
    accum["unresolved_total"] += int(parsed.get("unresolved_targets_total") or 0)
    accum["unresolved_total"] += int(parsed.get("unresolved_locations_total") or 0)
    for row in db_rows:
        if str(row["location_state"]) == TARGET_EXACT:
            accum["loc_exact"] += 1
        accum[FORM_MEASURE_KEYS.get(str(row["location_target_form"]), "other")] += 1
        accum["content_with" if str(row["content_state"]) == CONTENT_WITH
              else "content_empty"] += 1
        accum["priv_true" if row["privileged_get_mode"] else "priv_false"] += 1
        if str(row["properties_state"]) != PROPS_ALL_KNOWN:
            accum["unknown_states"] += 1
    for row in content_rows:
        kind = str(row["target_object_type"] or "")
        kind_totals[kind] += 1
        if str(row["target_resolve_state"]) == TARGET_EXACT:
            accum["target_exact"] += 1


def check_corpus(cur, accum, kind_totals, all_loaded):
    section("Контур 9 — суммы по четырём выгрузкам")
    check("все четыре выгрузки прогнаны (MinCfg, KomMag, BGU2, BP3)", all_loaded,
          "часть выгрузок не прогнана — сравнивать суммы не с чем")
    for measured, plan_key in CORPUS_KEYS:
        plan = CORPUS_TOTALS[plan_key]
        check(f"корпус: `{measured}` — {plan} (план V56, разделы 1.1, 2.1, 2.2)",
              accum.get(measured, 0) == plan, f"факт: {accum.get(measured, 0)}")
    check(f"корпус: классов целей применения — {len(EXPECTED_KINDS)} (замер 2.2), сумма "
          f"значений — {sum(EXPECTED_KINDS.values())} целей",
          len(kind_totals) == len(EXPECTED_KINDS)
          and sum(kind_totals.values()) == CORPUS_TOTALS["targets"],
          f"факт: классов {len(kind_totals)}, целей {sum(kind_totals.values())}")
    wrong = [f"{kind}: {count} ≠ {EXPECTED_KINDS.get(kind)}" for kind, count in
             sorted(kind_totals.items()) if kind not in EXPECTED_KINDS
             or count != EXPECTED_KINDS[kind]]
    absent = sorted(kind for kind in EXPECTED_KINDS if kind not in kind_totals)
    check("распределение целей по видам метаданных совпадает с замером 2.2 поимённо "
          "(21 класс, а не только сумма)", not wrong and not absent,
          "; ".join(wrong[:6] + ([f"нет классов: {names(absent)}"] if absent else [])))
    check(f"корпус: пустых перечней — {CORPUS_TOTALS['content_empty']} файлов из "
          f"{CORPUS_TOTALS['files']} остаются строкой вида с состоянием `empty_content`, а "
          "не исчезнувшей строкой (M3, Q6 вариант A)",
          accum.get("content_with", 0) + accum.get("content_empty", 0)
          == accum.get("db_rows", 0) == CORPUS_TOTALS["db_rows"],
          f"с непустым: {accum.get('content_with', 0)}, с пустым: "
          f"{accum.get('content_empty', 0)}, строк вида: {accum.get('db_rows', 0)}")

    # Две меры по живой базе на всём круге — «сирот» и «вне витрин» считаются по всем
    # конфигурациям, а не по прогнанной выгрузке: сирота могла остаться от прежней загрузки.
    orphans = scalar(cur, f"SELECT count(*) FROM {CONTENT_TABLE_NAME} c WHERE NOT exists("
                          f"SELECT 1 FROM {TABLE_NAME} o WHERE o.id = c.functional_option_id)")
    check("корпус: сирот применения (строка без строки вида) — ноль по всей базе",
          not orphans, f"сирот: {orphans}")
    outside = scalar(
        cur, f"SELECT (SELECT count(*) FROM {TABLE_NAME} o WHERE NOT exists("
             f"SELECT 1 FROM {OPTION_VIEW} v WHERE v.id = o.id)) + "
             f"(SELECT count(*) FROM {CONTENT_TABLE_NAME} c WHERE NOT exists("
             f"SELECT 1 FROM {CONTENT_VIEW} v WHERE v.id = c.id))")
    check("корпус: строк обеих таблиц вне витрин текущего состояния — ноль (цепь V19 и "
          "связка применения даются одной миграцией — M4)", not outside,
          f"вне витрин: {outside}")
    kind_rows = scalar(cur, f"SELECT count(*) FROM {INDEX_TABLE} i WHERE i.object_type = %s",
                       (INDEX_OBJECT_TYPE,))
    check(f"корпус: записей вида `{INDEX_OBJECT_TYPE}` во всех индексах состава — "
          f"{CORPUS_TOTALS['index_records']} (мера M1: сравнение по всему кругу)",
          kind_rows == CORPUS_TOTALS["index_records"], f"факт: {kind_rows}")
    sibling_rows = scalar(cur, f"SELECT count(*) FROM {INDEX_TABLE} i WHERE i.object_type = %s",
                          (SIBLING_INDEX_OBJECT_TYPE,))
    check(f"корпус: записей ЧУЖДОГО вида `{SIBLING_INDEX_OBJECT_TYPE}` — "
          f"{CORPUS_TOTALS['sibling_index']} (позиция 2.12, узел V57), и ни одна не вошла "
          "в круг V56", sibling_rows == CORPUS_TOTALS["sibling_index"],
          f"факт: {sibling_rows}")



def run(cur, scope):
    headers = q(cur, "SELECT id, uuid::text AS uuid, name FROM configurations ORDER BY id")
    if not headers:
        FAILED.append("строк заголовков конфигураций в базе нет — сравнивать не с чем")
        print("FAIL строк заголовков конфигураций в базе нет — сравнивать не с чем")
        return
    before = foreign_state(cur)
    accum = Counter()
    kind_totals = Counter()
    loaded = set()
    for header in headers:
        resolved = resolve_dump_dir(header["uuid"], DUMP_ROOT)
        dump_dir = resolved.get("path") or ""
        tag = Path(dump_dir).name if dump_dir else str(header["name"])
        if scope not in (DEFAULT_SCOPE, tag, str(header["name"])):
            continue
        section(f"Конфигурация {tag} (uuid {header['uuid']})")
        if not dump_dir:
            skip(f"{tag}: прогон выгрузки",
                 f"каталог выгрузки по uuid не найден ({resolved.get('reason', 'нет причины')})")
            continue
        if tag not in PLAN_EXPECTATIONS:
            skip(f"{tag}: сравнение с эталоном",
                 "PLAN_EXPECTATIONS этой выгрузки не называет — числа пришлось бы придумывать")
            continue
        expect = expect_of(tag)
        index_info = read_index_records(cur, int(header["id"]))
        if not index_info.get("available"):
            skip(f"{tag}: сверка круга с индексом состава",
                 f"индекс состава недоступен: {index_info.get('reason')}")
        parsed = collect_functional_options(dump_dir, index_rows=index_info["rows"])
        check(f"{tag}: разбор круга завершён без отказа ({expect['files']} файлов)",
              parsed["success"] is True and parsed["files_found"] == expect["files"]
              and parsed["files_read"] == expect["db_rows"],
              f"success: {parsed['success']}, found: {parsed['files_found']}, read: "
              f"{parsed['files_read']}, failed: {_brief(parsed['files_failed'])}")

        db_rows, content_rows, raw, agg, header_count, header_is_null = check_circle(
            cur, header, dump_dir, index_info, expect, parsed, tag)
        compare_option_rows(parsed, db_rows, expect, tag)
        compare_content_rows(parsed, content_rows, dump_dir, expect, tag)
        check_resolvability(cur, header, index_info, db_rows, content_rows, expect, tag)
        accumulate_corpus(accum, kind_totals, db_rows, content_rows, parsed, raw, agg,
                          header_count, header_is_null)
        loaded.add(tag)

    check_schema(cur)
    check_key_columns_match(cur)
    check_state_vocabulary_checks(cur)
    check_revisions_and_views(cur)
    check_contract()
    check_tool_registration()
    if scope == DEFAULT_SCOPE:
        check_corpus(cur, accum, kind_totals, loaded == set(PLAN_EXPECTATIONS))
    else:
        skip("Контур 9 — суммы по четырём выгрузкам",
             f"охват `{scope}`: остальные выгрузки не прогнаны, сравнивать суммы не с чем "
             "(у KomMag каталога вида нет — его нули входят в эталон)")
    check_non_interference(before, foreign_state(cur))


def main(argv):
    scope = str(argv[1]) if len(argv) > 1 else DEFAULT_SCOPE
    print(f"=== постоянная проверка узла V56 (функциональные опции, позиция 2.11) — "
          f"охват {scope} ===")
    try:
        with transaction() as cur:
            run(cur, scope)
    except Exception as exc:  # noqa: BLE001 — отказ прогона обязан быть назван
        FAILED.append(f"прогон прерван исключением: {exc}")
        import traceback
        traceback.print_exc()
    print(f"\nИТОГО: проверок {len(PASSED) + len(FAILED)}, PASS {len(PASSED)}, "
          f"FAIL {len(FAILED)}, SKIP {len(SKIPPED)}, INFO {len(INFO)}")
    if FAILED:
        print("ПРОВАЛЫ:")
        for name in FAILED:
            print(f"  — {name}")
        return 1
    print("ПРОВАЛОВ НЕТ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))














