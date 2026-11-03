# -*- coding: utf-8 -*-
"""check_v54_scheduled_jobs.py — постоянная проверка узла V54 (регламентные задания).

Зачем. Узел V54 закрыл круг позиции 2.9 нормативного списка «Структура конфигурации.txt»:
каталог `ScheduledJobs/` с файлом содержимого `Ext/Schedule.xml`, две таблицы
(`scheduled_jobs` — версионируемая цепь, `scheduled_job_schedules` — записи расписания без
своей цепи), стадию `s4i_scheduled_jobs` и двенадцатый инструмент регистра. Пока эти строки
лежат в базе, обязан существовать прогон, который повторяет их числа и состояния, а не
пересказывает план. Источник ожиданий — `docs/CONFIGURATION_SCHEDULED_JOBS_PLAN.md`
(раздел 1 — круг тремя ногами плюс ногой содержимого, раздел 2 — словарь десяти тегов,
форма расписания и разрешения обработчика, раздел 5 — меры M1…M7, раздел 9 — критерии
готовности); числа сняты замерами `_v54_p0_probe.py`, `_v54_q2_shape_probe.py`,
`_v54_q_resolve_probe.py`, `_v54_q4_range_probe.py`, `_v54_m1_probe.py` и подтверждены
`_v54_p3_parse_probe.py`, `_v54_p4_load_probe.py`, `_v54_p5_db_check.py` (прогон
03.11.2026). Числа `PLAN_EXPECTATIONS` переносятся без правок: сглаживать число проверкой
значило бы подтверждать неверное число (прецедент узлов V49/V50).

Контуры (номера совпадают с `check_v53_event_subscriptions.py`):

  1. СХЕМА. Две таблицы живы и держат эталонное число колонок; ключ строки вида —
     (`configuration_uuid`, `object_name`, `revision_no`); запись расписания привязана к
     строке вида внешним ключом с `ON DELETE CASCADE` и ссылается на родителя композитным
     ключом той же таблицы (`parent_id`, `scheduled_job_id`) — родитель чужого задания
     отклоняется схемой, а не разбором (Q1 узла V54, закрыт оператором 03.11.2026);
     позиция записи уникальна в пределах родителя; витрины текущего состояния обеих таблиц
     живы, при этом таблица расписания в реестре версионируемых НЕ состоит осознанно (Q2).
  2. СЛОВАРИ ↔ CHECK. Каждый закрытый словарь состояний разбора (`STATE_VOCABULARIES`)
     замкнут CHECK живой схемы в обе стороны: словарь шире CHECK — состояние записано и не
     пройдёт; CHECK шире словаря — схема допускает то, чего разбор не производит.
     Состояния атрибутов записи замкнуты иначе, и это названо отдельной проверкой:
     схема держит перечень ключей jsonb (`..._attribute_states_closed`, два набора
     `ARRAY[...]`) и соответствие состояния колонке — отдельно для дат/времени и для
     целых (`..._datetime_states_match_values`,
     `..._integer_states_match_values`); отдельного CHECK на значения состояний нет
     осознанно (прецедент Q7 узла V50).
  3. ГРАНИЦА КРУГА. Файлы `ScheduledJobs/*.xml` ↔ верхние записи индекса состава
     (`ScheduledJob.<Имя>`) ↔ перечень `configurations.scheduled_jobs[]` ↔ строки таблицы;
     отдельной ногой — файлы `Ext/Schedule.xml` ↔ дочерние записи индекса
     (`ScheduledJob.<Имя>.Schedule`). Расхождений ног ноль; у 43 заданий расписания нет ни
     файлом, ни индексом — это состояние `absent`, а не потерянная строка (мера M4).
  4. СТРОКА ВИДА ↔ РАЗБОР. Строки таблицы сравниваются с кругом, разобранным ТЕМ ЖЕ
     модулем (`collect_scheduled_jobs`), что и загрузка: имена, свойства, состояния и
     разложенные части обработчика. Пустая строка `job_key`
     писателем приводится к NULL (`EMPTY_TEXT_TO_NULL`): расхождение называется заметкой,
     а не провалом — пустое значение в файле и есть пустое значение в базе.
  5. ДЕРЕВО РАСПИСАНИЯ. Ровно одна корневая запись `schedule` на задание с расписанием,
     глубина не больше `MAX_DEPTH`, вложенных не больше `MAX_DETAILED_PER_RECORD`, родитель
     принадлежит тому же заданию, позиция уникальна, `schedule_record_count` равен числу
     записей.
  6. ЗНАЧЕНИЯ АТРИБУТОВ. Состояние каждого из двенадцати атрибутов названо в закрытом
     словаре; значение-страж платформенного типа (`0001-01-01`, `00:00:00`) в колонки
     `date`/`time` не записан (Q4), фактический ноль записан значением (состояние `zero`),
     наборы `WeekDays`/`Months` замкнуты диапазонами платформы, пустой элемент читается
     состоянием `empty_element_all` (мера M5).
     Число состояний считается по парам (запись, колонка): двенадцать атрибутов на запись,
     поэтому 313 записей дают 3 756 состояний — это не удвоенное число записей.
  7. ОБРАБОТЧИК. `MethodName` разложен на модуль и метод, состояние пересчитывается по
     витрине общих модулей СВОЕЙ конфигурации и совпадает с сохранённым.
  8. ВИТРИНЫ И СИРОТЫ. Витрины текущего состояния отдают ровно строки текущей ревизии;
     записей расписания вне текущей ревизии задания — ноль.
  9. КОНТРАКТ. Стадия `s4i_scheduled_jobs` стоит сразу после `s4h_event_subscriptions` и
     перед `s4b_object_modules` (порядок позиций 2.8 → 2.9, модули остаются второй
     транзакцией); у стадии есть зеркало `STAGE_FULL_RELOAD_ONLY`, подсказка продолжения
     называет `load_scheduled_jobs_tool`, незакрытая группа — позиция 2.9; круг снятия
     начинается с дочерней таблицы (иначе каскад снял бы строки молча, M7); вид назван
     сохранённым в `STORED_META_KINDS` — тем же словарём, которым пользуется карточка
     загрузки (дефект, вскрытый `_v54_p5_stage_probe.py`).
  10. ИТОГ ПО КОРПУСУ и неприкосновенность чужих кругов: суммы по четырём выгрузкам равны
     разделам 1 и 2 плана (346 заданий, 313 записей расписания, 303 корневых и 10 вложенных,
     3 756 состояний атрибутов из них 1 441 страж, 43 задания без расписания); прогон
     читающий — число строк чужих таблиц до и после него совпадает, а отсутствующая таблица
     называется, а не пропускается.

Границы проверки (названы, а не промолчаны). Объявленность метода обработчика в файле
модуля (`declared`/`not_declared`) не проверяется: тексты общих модулей узлом V46/V47 в
базе не читались, поэтому состояние обязано быть `text_unavailable` — это и проверяется, а
утверждать объявленность было бы ложью (Q8). Остановка конвейера и продолжение отдельным
входом — проба `_v54_p5_stage_probe.py` и шаг П8, а не этот скрипт: проверка читает базу и
ничего в неё не пишет. Независимая регулярковая мера файла регистрации (байты, число тегов)
здесь не повторяется: она снята `_v54_p0_probe.py` и `_v54_p3_parse_probe.py`, а скрипт
сверяет разбор с базой — второй независимый путь к тем же числам.

Запуск:
    python tools/check_v54_scheduled_jobs.py [MinCfg|KomMag|BGU2|BP3|all]
Код возврата 0 — провалов нет; 1 — есть. Пропуск называется причиной, а не тишиной.
Охват одной выгрузки — это её граница круга и свои строки; контур сумм корпуса при таком
охвате пропускается с причиной, потому что сравнивать его с планом четырёх выгрузок нельзя.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "src", ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 — перекодировка вывода не является проверкой
    pass

from configuration_load_contract import (  # noqa: E402
    SCHEDULED_JOBS_REMOVE_ORDER, SCHEDULED_JOBS_TABLES, STAGE_EVENT_SUBSCRIPTIONS,
    STAGE_FILTER_CRITERIA, STAGE_FULL_RELOAD_ONLY, STAGE_OBJECT_MODULES,
    STAGE_SCHEDULED_JOBS, STAGES, STORED_META_KINDS, stage_resume_hint, stage_title,
    stages_after,
)
from configuration_module_slots import resolve_dump_dir  # noqa: E402
from configuration_scheduled_jobs import (  # noqa: E402
    ATTRIBUTE_COLUMNS, DATE_SENTINEL, DIR_NAME, KIND_DETAILED_DAILY, KIND_SCHEDULE,
    MAX_DEPTH, MAX_DETAILED_PER_RECORD, METHOD_STATE_EXACT, METHOD_TEXT_UNAVAILABLE,
    MONTHS_RANGE, SCHEDULE_ATTRIBUTE_NAMES, SCHEDULE_ATTRIBUTES, SCHEDULE_FILE_NAME,
    SCHEDULE_KINDS, SCHEDULE_ROOT_TAG, STATE_VOCABULARIES, TIME_SENTINEL,
    VALUE_KIND_DATE, VALUE_KIND_INT, VALUE_KIND_TIME, VALUE_SENTINEL, VALUE_SET,
    VALUE_ZERO, WEEK_DAY_RANGE, collect_scheduled_jobs, state_vocabulary,
)
from configuration_scheduled_jobs_loader import (  # noqa: E402
    read_common_module_names, read_index_records,
)
from current_revision import CONFIGURATION_VERSIONED_TABLES, current_view  # noqa: E402
from external_db import transaction  # noqa: E402
from external_table_writer import CONFIGURATION_UNVERSIONED_TABLES  # noqa: E402

SCHEDULES_TABLE = "scheduled_job_schedules"
TABLE_NAME = "scheduled_jobs"
JOBS_VIEW = current_view(TABLE_NAME)
# Запись расписания своей цепи ревизий не имеет (Q2, предложение вариантом A), поэтому её
# витрина не порождается реестром `CURRENT_VIEWS`, а построена связкой в DDL: имя называется
# литералом и проверяется контуром 1 отдельно — «витрина жива» и «таблицы в реестре
# версионируемых нет осознанно» являются разными утверждениями.
SCHEDULES_VIEW = "v_current_scheduled_job_schedules"
HEADER_NAME_COLUMN = "scheduled_jobs"
COMMON_MODULES_VIEW = "v_current_common_modules"

# Поля записи расписания, сверяемые «разбор ↔ строка базы»: дерево, файл, значения и
# их состояния. Имена взяты из контракта разбора `walk_schedule_records` — того же,
# из которого строит строки загрузчик; расхождение имени называется ошибкой сравнения.
RECORD_FIELDS = (
    "kind", "depth", "ordinal", "parent_kind", "parent_ordinal", "root_tag",
    "file_path", "file_sha256", "file_size", "file_modified",
    *SCHEDULE_ATTRIBUTE_NAMES, "week_days", "months",
    "week_days_state", "months_state", "attribute_states",
)

DUMP_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
DEFAULT_SCOPE = "all"
MAX_NAMES = 8

# Числа колонок двух таблиц — эталон шага П1 (`migrate_v54_scheduled_jobs.sql` и то же
# зеркало в `create_1c_configurations_db.sql`).
EXPECTED_COLUMN_COUNTS = {"scheduled_jobs": 30, SCHEDULES_TABLE: 29}

# Колонки, принадлежащие цепи ревизий (узел V19), а не узлу V54: их заполняет не разбор, и
# сравнивать их с ключом строки разбора — значит требовать от слоя чужого.
REVISION_COLUMNS = ("id", "configuration_uuid", "created_at", "revision_no", "changed_at",
                    "changed_by", "is_committed")

PASSED, FAILED, SKIPPED, INFO = [], [], [], []

# ── ожидания (числа плана docs/CONFIGURATION_SCHEDULED_JOBS_PLAN.md, разделы 1.1, 2.1–2.5) ──
# Ключ — каталог выгрузки, а не имя строки заголовка: имя заголовка меняется вместе с
# выгрузкой, а каталог — адрес, по которому проверка находит файлы.
#   files / subdirs / non_xml — каталог `ScheduledJobs/` (файл регистрации + подкаталог
#            `Ext/`, других детей у вида нет — замер 1.2);
#   schedule_files — файлы `Ext/Schedule.xml` (нога содержимого);
#   index_rows / index_children — записи индекса `ScheduledJob.<Имя>` и её дочерняя запись
#            `ScheduledJob.<Имя>.Schedule` (замер 1.2): нога содержимого существует ровно
#            там, где файл есть, поэтому `index_children` равен `schedule_files` (138/162),
#            а число СТРОК расписания больше (143/164) — один файл несёт до двух записей;
#   header_list — заполненный стадией S2 перечень `configurations.scheduled_jobs[]`;
#   db_rows / db_schedules / db_roots / db_detailed — строки двух таблиц;
#   schedule_absent — задания без расписания ни файлом, ни индексом (мера M4);
#   props_all_known / method_exact / method_text_unavailable — состояния, обязанные быть
#            полными на всём круге (замеры 2.1 и 2.4).
PLAN_EXPECTATIONS: Dict[str, Dict[str, int]] = {
    "MinCfg": {"files": 2, "subdirs": 2, "non_xml": 0, "schedule_files": 2,
               "index_rows": 2, "index_children": 2, "header_list": 2,
               "db_rows": 2, "db_schedules": 5, "db_roots": 2, "db_detailed": 3,
               "schedule_absent": 0, "props_all_known": 2, "method_exact": 2,
               "method_text_unavailable": 2},
    "KomMag": {"files": 1, "subdirs": 1, "non_xml": 0, "schedule_files": 1,
               "index_rows": 1, "index_children": 1, "header_list": 1,
               "db_rows": 1, "db_schedules": 1, "db_roots": 1, "db_detailed": 0,
               "schedule_absent": 0, "props_all_known": 1, "method_exact": 1,
               "method_text_unavailable": 1},
    "BGU2": {"files": 157, "subdirs": 138, "non_xml": 0, "schedule_files": 138,
             "index_rows": 157, "index_children": 138, "header_list": 157,
             "db_rows": 157, "db_schedules": 143, "db_roots": 138, "db_detailed": 5,
             "schedule_absent": 19, "props_all_known": 157, "method_exact": 157,
             "method_text_unavailable": 157},
    "BP3": {"files": 186, "subdirs": 162, "non_xml": 0, "schedule_files": 162,
            "index_rows": 186, "index_children": 162, "header_list": 186,
            "db_rows": 186, "db_schedules": 164, "db_roots": 162, "db_detailed": 2,
            "schedule_absent": 24, "props_all_known": 186, "method_exact": 186,
            "method_text_unavailable": 186},
}

# Ожидания корпуса (четыре выгрузки, 346 файлов) — замеры 2.2–2.5 плана, подтверждённые
# `_v54_p5_db_check.py` 03.11.2026. Глубина и кратность держатся замером 2.5 (M6).
# Состояния наборов считаются ОТДЕЛЬНО по каждой колонке: запись несёт и `WeekDays`, и
# `Months`, поэтому сумма двух колонок — 313 × 2 = 626, а замер 2.2 называет 290/23 на
# колонку; сложить их в одну меру значило бы удвоить число плана.
CORPUS_EXPECTATIONS = {
    "jobs": 346, "schedules": 313, "roots": 303, "detailed": 10,
    "depth_1": 303, "depth_2": 10, "max_ordinal_depth_2": 1,
    "sentinel": 1441, "zero": 1449, "set": 866,
    "week_days_values": 290, "week_days_empty_element_all": 23,
    "months_values": 290, "months_empty_element_all": 23,
    "week_day_min": min(WEEK_DAY_RANGE), "week_day_max": max(WEEK_DAY_RANGE),
    "months_min": min(MONTHS_RANGE), "months_max": max(MONTHS_RANGE),
}


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


def array_literal_groups(definition):
    """Наборы литералов внутри `ARRAY[...]` ограничения схемы. Отдельный разбор, а не
    `literals_of`: в CHECK перечня ключей jsonb встречаются и служебные литералы
    (`'object'::text` из `jsonb_typeof`, `'{}'::jsonb` из проверки вычитания), которые
    ключами не являются и называть их ключами — значило бы врать о схеме."""
    return [tuple(literals_of(group))
            for group in re.findall(r"ARRAY\[([^\]]*)\]", str(definition))]


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


def unique_indexes(cur, table):
    """Уникальные индексы живой схемы: имя → текст определения
    (пустая строка, если определения нет)."""
    out = {}
    for row in q(cur, "SELECT i.relname AS name, pg_get_indexdef(i.oid) AS def "
                      "FROM pg_index x JOIN pg_class i ON i.oid = x.indexrelid "
                      "JOIN pg_class t ON t.oid = x.indrelid "
                      "WHERE t.relname = %s AND x.indisunique", (table,)):
        out[str(row["name"])] = str(row["def"] or "")
    return out


def compact(text):
    """Одна строка для сравнения и вывода: переносы и двойные пробелы схемы не значимы."""
    return " ".join(str(text).split())


# ── контур 1: живая схема круга ──────────────────────────────────────────────────────────────
def check_schema(cur):
    section("Контур 1 — живая схема круга")
    for table in (TABLE_NAME, SCHEDULES_TABLE):
        if not q(cur, "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                 (table,)):
            check(f"{table}: таблица существует", False, "таблицы в схеме нет")
            continue
        columns = table_columns(cur, table)
        check(f"{table}: таблица существует и держит {EXPECTED_COLUMN_COUNTS[table]} колонок "
              f"(эталон П1)", len(columns) == EXPECTED_COLUMN_COUNTS[table],
              f"факт: {len(columns)}")
    if not q(cur, "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
             (SCHEDULES_TABLE,)):
        return

    wanted = "(configuration_uuid, object_name, revision_no)"
    keys = unique_constraints(cur, TABLE_NAME)
    scope = [d for d in keys.values() if compact(d).endswith(wanted)]
    check(f"`{TABLE_NAME}`: ключ области видимости строк узла живой {wanted}",
          len(scope) == 1, f"ключи схемы: {names(list(keys))}")

    fks = foreign_keys(cur, SCHEDULES_TABLE)
    cascade = [d for d in fks.values()
               if "REFERENCES scheduled_jobs(id)" in compact(d)
               and "ON DELETE CASCADE" in compact(d)]
    check(f"`{SCHEDULES_TABLE}`: внешний ключ на строку задания с `ON DELETE CASCADE` (Q1)",
          len(cascade) == 1, f"ключи: {names(list(fks))}")
    selfref = [d for d in fks.values()
               if "(parent_id, scheduled_job_id)" in compact(d)
               and "REFERENCES scheduled_job_schedules(id, scheduled_job_id)" in compact(d)]
    check(f"`{SCHEDULES_TABLE}`: композитная самоссылка `(parent_id, scheduled_job_id)` "
          "отклоняет родителя чужого задания схемой, а не разбор (Q1, вариант A)",
          len(selfref) == 1, f"ключи: {names(list(fks))}")
    positions = [d for n, d in unique_indexes(cur, SCHEDULES_TABLE).items()
                 if "scheduled_job_id" in compact(d) and "ordinal" in compact(d)]
    check(f"`{SCHEDULES_TABLE}`: позиция записи уникальна в пределах родителя",
          len(positions) == 1,
          f"уникальные индексы: {names(list(unique_indexes(cur, SCHEDULES_TABLE)))}")
    target = [d for d in unique_constraints(cur, SCHEDULES_TABLE).values()
              if "UNIQUE" in compact(d).upper()
              and compact(d).split("UNIQUE", 1)[1].strip() == "(id, scheduled_job_id)"]
    check(f"`{SCHEDULES_TABLE}`: пара `(id, scheduled_job_id)` объявлена уникальной — "
          "мишень композитной самоссылки",
          len(target) == 1,
          f"ключи: {names(list(unique_constraints(cur, SCHEDULES_TABLE)))}")

    for view in (JOBS_VIEW, SCHEDULES_VIEW):
        try:
            n = scalar(cur, f"SELECT count(*) FROM {view}")
            check(f"витрина текущего состояния `{view}` жива и читается", True)
            info(f"витрина `{view}`: строк {n}")
        except Exception as exc:  # noqa: BLE001 — отсутствующая витрина называется отказом
            cur.connection.rollback()
            check(f"витрина текущего состояния `{view}` жива и читается", False, str(exc))

    check(f"`{TABLE_NAME}` состоит в реестре версионируемых (цепь узла V19)",
          TABLE_NAME in CONFIGURATION_VERSIONED_TABLES,
          f"реестр: {names(sorted(CONFIGURATION_VERSIONED_TABLES))}")
    check(f"`{SCHEDULES_TABLE}` НЕ версионируется своей цепью осознанно (Q2, вариант A) и "
          "названа списком невersonируемых", SCHEDULES_TABLE not in CONFIGURATION_VERSIONED_TABLES
          and SCHEDULES_TABLE in CONFIGURATION_UNVERSIONED_TABLES,
          f"невersonируемые: {names(sorted(CONFIGURATION_UNVERSIONED_TABLES))}")
    check("перечень заголовка `configurations.scheduled_jobs` жив (его заполняет стадия S2)",
          bool(q(cur, "SELECT 1 FROM information_schema.columns WHERE table_name = "
                      "'configurations' AND column_name = %s", (HEADER_NAME_COLUMN,))))


# ── контур 2: словари состояний ↔ CHECK'ы схемы ──────────────────────────────────────────────
def compare_vocabulary(cur, table, column, vocabulary):
    """Словарь модуля и замкнутость схемы равны; расхождение называется множествами."""
    constraint = f"{table}_{column}_known"
    definition = constraint_def(cur, table, constraint)
    if not definition:
        check(f"{table}.{column}: CHECK замкнутости `{constraint}` живой схемы", False,
              "ограничения с таким именем в схеме нет — словарь схемы нечем подтвердить")
        return
    schema_values = set(literals_of(definition))
    module_values = set(vocabulary)
    check(f"{table}.{column}: CHECK живой схемы перечисляет словарь модуля "
          f"({len(module_values)} значений)", schema_values == module_values,
          f"в словаре нет: {names(sorted(schema_values - module_values))}; "
          f"CHECK допускает: {names(sorted(module_values - schema_values))}")


def compare_attribute_states(cur):
    """Словарь состояний атрибутов записи. Замкнутость здесь держат НЕ один `_known` CHECK,
    а два ограничения: перечень ключей jsonb (`{SCHEDULES_TABLE}_attribute_states_closed`)
    и соответствие состояния содержимому колонки — отдельно для даты/времени и для целых
    (`..._datetime_states_match_values`, `..._integer_states_match_values`). Отдельного
    CHECK на значения состояний в схеме нет осознанно (прецедент Q7 узла V50): незнакомое
    значение остаётся значением с состоянием `unknown_value`, а не отказом записи, поэтому
    проверка идёт по ключам и по покрытию match-CHECK'ов."""
    expected_keys = set(SCHEDULE_ATTRIBUTE_NAMES)
    closed = constraint_def(cur, SCHEDULES_TABLE,
                            f"{SCHEDULES_TABLE}_attribute_states_closed")
    groups = array_literal_groups(closed) if closed else []
    schema_keys = set(groups[0]) if groups else set()
    check(f"{SCHEDULES_TABLE}.attribute_states: CHECK перечня ключей "
          f"`{SCHEDULES_TABLE}_attribute_states_closed` держит замкнутость перечня двумя "
          f"наборами `ARRAY[...]` — оба называют ровно {len(expected_keys)} атрибутов файла",
          bool(closed) and len(groups) >= 2
          and all(set(group) == schema_keys for group in groups)
          and schema_keys == expected_keys,
          "ограничения в схеме нет" if not closed else
          f"наборов ARRAY: {len(groups)}; в CHECK нет: "
          f"{names(sorted(expected_keys - schema_keys))}; лишние: "
          f"{names(sorted(schema_keys - expected_keys))}")

    states = set(state_vocabulary(f"{SCHEDULES_TABLE}.attribute_states"))
    covered, confirmed = set(), set()
    for suffix, group in (("datetime_states_match_values", (VALUE_KIND_DATE, VALUE_KIND_TIME)),
                          ("integer_states_match_values", (VALUE_KIND_INT,))):
        definition = constraint_def(cur, SCHEDULES_TABLE, f"{SCHEDULES_TABLE}_{suffix}")
        wanted = {attribute for attribute, _column, kind in SCHEDULE_ATTRIBUTES
                  if kind in group}
        named = {attribute for attribute in expected_keys if f"'{attribute}'" in definition}
        check(f"{SCHEDULES_TABLE}: match-CHECK `{suffix}` покрывает ровно {len(wanted)} "
              "атрибутов своей группы типов",
              bool(definition) and named == wanted,
              "ограничения в схеме нет" if not definition else
              f"не покрыты: {names(sorted(wanted - named))}; лишних: "
              f"{names(sorted(named - wanted))}")
        covered |= named
        confirmed |= set(literals_of(definition)) & states
    check(f"{SCHEDULES_TABLE}.attribute_states: состояния {sorted(states)} подтверждены "
          "покрытием match-CHECK'ов по всем атрибутам — словарь модуля и схема говорят "
          "об одном и том же",
          covered == expected_keys and confirmed == states,
          f"покрыто атрибутов: {len(covered)} из {len(expected_keys)}; подтверждено "
          f"состояний: {names(sorted(confirmed))}; словарь модуля: "
          f"{names(sorted(states))}")


def check_state_vocabulary_checks(cur):
    section("Контур 2 (часть 2) — словари состояний против CHECK'ов схемы")
    for column_key in sorted(STATE_VOCABULARIES):
        if column_key.endswith(".attribute_states"):
            continue
        table, column = column_key.split(".", 1)
        compare_vocabulary(cur, table, column, state_vocabulary(column_key))
    compare_attribute_states(cur)


# ── независимая мера круга: обход каталога без знания о состояниях разбора ───────────────────
def circle_measures(dump_dir):
    """Число файлов регистрации, подкаталогов, не-XML и файлов `Ext/Schedule.xml` обходом."""
    root = Path(dump_dir) / DIR_NAME
    totals = {"files": 0, "subdirs": 0, "non_xml": 0, "schedule_files": 0, "bytes": 0}
    if not root.exists():
        return totals
    for entry in sorted(root.iterdir()):
        if entry.is_dir():
            totals["subdirs"] += 1
            continue
        if entry.suffix.lower() != ".xml":
            totals["non_xml"] += 1
            continue
        totals["files"] += 1
        totals["bytes"] += entry.stat().st_size
    for schedule in root.rglob(SCHEDULE_FILE_NAME):
        if schedule.is_file():
            totals["schedule_files"] += 1
    return totals


def read_job_rows(cur, cfg_uuid):
    """Строки вида текущей ревизии — через витрину, а не прямым чтением версионируемой таблицы."""
    return q(cur, f"SELECT * FROM {JOBS_VIEW} WHERE configuration_uuid = %s::uuid "
                  "ORDER BY full_name", (cfg_uuid,))


def read_schedule_rows(cur, cfg_uuid):
    return q(cur, f"SELECT s.* FROM {SCHEDULES_VIEW} s WHERE s.configuration_uuid = %s::uuid "
                  "ORDER BY s.job_full_name, s.depth, s.ordinal", (cfg_uuid,))


def read_index_aggregates(cur, configuration_id):
    """Записи индекса состава вида и его содержимого — отдельным SQL, а не памятью
    разбора. Нога вида — строка без родителя (`ScheduledJob.<Имя>`, глубина 0), нога
    содержимого — строка с родителем (`ScheduledJob.<Имя>.Schedule`, глубина 1): `object_name`
    детской записи несёт имя объекта, а не `.Schedule`, поэтому ноги различаются родителем
    (замер 1.2, тот же приём, что в разборе через `kind_root_index_rows`)."""
    return {
        "kind_rows": scalar(
            cur, "SELECT count(*) FROM configuration_objects WHERE configuration_id = %s "
                 "AND object_type = 'ScheduledJob' AND parent_name IS NULL",
            (configuration_id,)) or 0,
        "child_rows": scalar(
            cur, "SELECT count(*) FROM configuration_objects WHERE configuration_id = %s "
                 "AND object_type = 'ScheduledJob' AND parent_name IS NOT NULL",
            (configuration_id,)) or 0,
    }


def read_header_name_list(cur, cfg_uuid):
    """Перечень заголовка, заполненный стадией S2: имена элементов или NULL (пустой
    перечень различим от отсутствующего — колонка `text[]`, а не jsonb)."""
    row = one(cur, f"SELECT coalesce(array_length({HEADER_NAME_COLUMN}, 1), 0) AS n, "
                   f"({HEADER_NAME_COLUMN} IS NULL) AS is_null FROM configurations "
                   "WHERE uuid = %s::uuid", (cfg_uuid,))
    return int(row.get("n") or 0), bool(row.get("is_null"))


def set_diff(label, left, right, tag):
    """Две стороны одного множества сравниваются попарно; расхождение называется именами."""
    missing, extra = sorted(right - left), sorted(left - right)
    check(f"{tag}: {label} совпадают во все четыре стороны", not missing and not extra,
          f"не названо: {names(missing)}; лишнее: {names(extra)}")


def index_names(rows):
    """Имена видов из записей индекса состава (`ScheduledJob.<Имя>` → `<Имя>`)."""
    prefix = "ScheduledJob."
    out = set()
    for row in rows or []:
        name = str(row.get("object_name") or "")
        if name.startswith(prefix) and "." not in name[len(prefix):]:
            out.add(name[len(prefix):])
    return out


def registration_names(dump_dir):
    """Имена видов по файлам регистрации (без расширения) — независимая мера каталога."""
    root = Path(dump_dir) / DIR_NAME
    if not root.exists():
        return set()
    return {entry.stem for entry in root.iterdir()
            if entry.is_file() and entry.suffix.lower() == ".xml"}


# ── контур 3: граница круга — файлы, индекс состава, перечень заголовка, строки таблицы ──────
def check_circle(cur, header, dump_dir, index_info, expect, parsed, tag):
    raw = circle_measures(dump_dir)
    keys = ("files", "subdirs", "non_xml", "schedule_files")
    check(f"{tag}: независимые меры `ScheduledJobs/` (файлы, подкаталоги, не-XML, "
          "файлы расписания) совпадают с планом",
          all(raw[k] == expect[k] for k in keys),
          "; ".join(f"{k}: факт {raw[k]}, план {expect[k]}" for k in keys
                    if raw[k] != expect[k]))

    agg = read_index_aggregates(cur, int(header["id"]))
    check(f"{tag}: записей вида в индексе состава — {expect['index_rows']}, содержимого — "
          f"{expect['index_children']} (замер 1.2)",
          agg["kind_rows"] == expect["index_rows"]
          and agg["child_rows"] == expect["index_children"],
          f"факт: вид {agg['kind_rows']}, содержимое {agg['child_rows']}")
    check(f"{tag}: агрегатный COUNT индекса ↔ построчный обход разбора",
          agg["kind_rows"] == parsed["index_kind_records"]
          and agg["child_rows"] == parsed["index_child_records"],
          f"агрегат: {agg}, разбор: kind={parsed['index_kind_records']}, "
          f"child={parsed['index_child_records']}")

    header_list, header_is_null = read_header_name_list(cur, str(header["uuid"]))
    check(f"{tag}: перечень заголовка называет те же {expect['header_list']} заданий",
          header_list == expect["header_list"]
          and header_is_null is (expect["header_list"] == 0),
          f"факт: элементов {header_list}, NULL-перечень {header_is_null}")

    job_rows = read_job_rows(cur, str(header["uuid"]))
    check(f"{tag}: строк вида от разбора — {expect['db_rows']}",
          len(parsed["rows"]) == expect["db_rows"], f"разбор дал {len(parsed['rows'])}")
    check(f"{tag}: строк вида в базе — {expect['db_rows']}",
          len(job_rows) == expect["db_rows"], f"в базе {len(job_rows)}")

    from_files = registration_names(dump_dir)
    from_index = index_names(index_info.get("rows"))
    header_items = one(cur, f"SELECT {HEADER_NAME_COLUMN} AS items FROM configurations "
                            "WHERE uuid = %s::uuid",
                       (str(header["uuid"]),)).get("items") or []
    from_header = {str(item) for item in header_items}
    from_db = {str(row["object_name"]) for row in job_rows}
    set_diff("имена видов (файлы ↔ индекс ↔ перечень заголовка ↔ строки таблицы)",
             from_files | from_index | from_header, from_db, tag)

    for key in ("index_only", "file_only", "uuid_mismatch", "schedule_index_only",
                "schedule_file_only", "schedule_uuid_mismatch", "duplicate_names"):
        found = parsed.get(key) or []
        check(f"{tag}: расхождений `{key}` — ноль (круг замкнут во всех выгрузках, замер 1.3)",
              not found, f"названо {len(found)}: {names(found)}")

    with_content = sum(1 for row in job_rows if row["schedule_state"] == "with_content")
    absent = sum(1 for row in job_rows if row["schedule_state"] == "absent")
    check(f"{tag}: наличие содержимого названо состояниями: `with_content` "
          f"{expect['db_rows'] - expect['schedule_absent']}, `absent` "
          f"{expect['schedule_absent']} (мера M4 — расписания нет ни файлом, ни индексом)",
          with_content == expect["db_rows"] - expect["schedule_absent"]
          and absent == expect["schedule_absent"],
          f"факт: with_content {with_content}, absent {absent}")
    file_states = Counter(row["schedule_file_state"] for row in job_rows)
    check(f"{tag}: две ноги содержимого согласованы: `file_and_index` "
          f"{expect['schedule_files']}, `absent` {expect['schedule_absent']}, `file_only` и "
          "`index_only` — нули (замер 1.3)",
          file_states.get("file_and_index", 0) == expect["schedule_files"]
          and file_states.get("absent", 0) == expect["schedule_absent"]
          and not file_states.get("file_only") and not file_states.get("index_only"),
          f"факт: {dict(file_states)}")
    return job_rows


# Ключи строки вида, которые даёт разбор и которые несёт таблица: имена совпадают намеренно
# (`prepare_scheduled_jobs_rows` ничего не переименовывает), поэтому сравнение идёт по одному
# перечню. Колонки версионности и `configuration_uuid` в перечень не входят намеренно (их
# заполняет писатель), `unknown_property_names` сравнивается отдельно как список.
JOB_ROW_KEYS = (
    "object_uuid", "object_name", "full_name", "synonym", "comment", "description",
    "job_key", "use_flag", "predefined", "restart_count_on_failure",
    "restart_interval_on_failure", "method_name", "method_module", "method_method",
    "method_state", "method_declared_state", "schedule_state", "schedule_record_count",
    "schedule_file_state", "schedule_source_path", "properties_state",
)
# Ключи записи расписания, общие для разбора и таблицы: `parent_kind`/`parent_ordinal` разбор
# даёт как указатель, а таблица — как числовой `parent_id`, поэтому родитель сравнивается
# контуром 5 отдельно.
SCHEDULE_ROW_KEYS = (
    "job_full_name", "job_object_uuid", "kind", "depth", "ordinal", "file_path",
    "root_tag", "week_days", "months", "week_days_state", "months_state",
) + tuple(ATTRIBUTE_COLUMNS)


# Пустой текст ключа: разбор сохраняет пустую строку (`job_key = (child.text or "").strip()`
# с комментарием «пустое значение сохраняется пустой строкой»), а общий писатель узлов сводит
# пустой текст к NULL (`return text or None` в `external_table_writer`). Различие «пустой
# ключ» / «ключа нет» несёт состояние разбора, а не колонка — комментарий DDL к `job_key`:
# «пустое значение отличается от отсутствующего состоянием разбора, а не нулём». Сравнение
# учитывает это явно и называет число таких ключей, а не прячет расхождение.
EMPTY_TEXT_TO_NULL = ("job_key",)


def norm_value(value, column=None):
    """Одно представление значения для сравнения разбора и строки БД."""
    if value is None:
        return None
    if column in EMPTY_TEXT_TO_NULL and value == "":
        return None
    if isinstance(value, (list, tuple, set)):
        return tuple(sorted(str(v) for v in value))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


# ── контур 4: строка вида ↔ разбор того же файла (тот же модуль, что загрузка) ───────────────
def check_job_rows(parsed, job_rows, expect, tag):
    by_name = {str(row["full_name"]): row for row in job_rows}
    mismatches, unknown_lists, empty_keys = [], [], []
    for parsed_row in parsed["rows"]:
        name = str(parsed_row["full_name"])
        db_row = by_name.get(name)
        if db_row is None:
            mismatches.append(f"{name}: строки вида в базе нет")
            continue
        for key in JOB_ROW_KEYS:
            left, right = parsed_row.get(key), db_row.get(key)
            if norm_value(left, key) != norm_value(right, key):
                mismatches.append(f"{name}.{key}: разбор "
                                  f"{_brief(left)}, база {_brief(right)}")
            elif key in EMPTY_TEXT_TO_NULL and left == "" and right is None:
                empty_keys.append(name)
        parsed_unknown = norm_value(parsed_row.get("unknown_property_names"))
        db_unknown = norm_value(db_row.get("unknown_property_names"))
        if parsed_unknown != db_unknown:
            unknown_lists.append(f"{name}: {parsed_unknown} ≠ {db_unknown}")
    extra = sorted(set(by_name) - {str(r["full_name"]) for r in parsed["rows"]})
    check(f"{tag}: каждая колонка строки вида совпадает с разбором того же файла "
          f"({len(JOB_ROW_KEYS)} ключей на {len(parsed['rows'])} строк)",
          not mismatches and not extra,
          f"расхождений {len(mismatches)}: {names(mismatches)}; лишних строк базы: "
          f"{names(extra)}")
    if empty_keys:
        info(f"{tag}: пустое значение `job_key` пришло в базу NULL'ом ({len(empty_keys)} строк: "
             f"{names(empty_keys)}) — писатель общих узлов сводит пустой текст к NULL, а "
             "различие пустого и отсутствующего ключа несёт состояние разбора (комментарий DDL "
             "к `job_key`); расхождение названо, а не спрятано")
    check(f"{tag}: перечень неизвестных свойств (`unknown_property_names`) пуст и у разбора, "
          "и в базе — состояние `all_known` не врёт",
          not unknown_lists and not [r for r in job_rows if r["unknown_property_names"]],
          names(unknown_lists))
    states = Counter(str(r["properties_state"]) for r in job_rows)
    check(f"{tag}: свойств вида разобрано без неизвестных — {states.get('all_known', 0)} "
          f"(план {expect_of(tag)['props_all_known']}); `unknown_value`/`unknown_tag`/absent — "
          "нули (замер 2.1)",
          states.get("all_known", 0) == expect_of(tag)["props_all_known"]
          and not states.get("unknown_value") and not states.get("unknown_tag")
          and not states.get("absent"),
          f"факт: {dict(states)}")


def _brief(value, limit=90):
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[:limit] + " …"


_EXPECT_BY_TAG: Dict[str, Dict[str, int]] = {}


def expect_of(tag):
    """Эталон выгрузки — из `PLAN_EXPECTATIONS`; неизвестная выгрузка не получает нулей."""
    return PLAN_EXPECTATIONS[tag]


# ── контур 5: дерево расписания — родитель, глубина, позиция, счётчик записей ────────────────
def check_schedule_tree(cur, header, parsed, expect, tag):
    schedule_rows = read_schedule_rows(cur, str(header["uuid"]))
    check(f"{tag}: записей расписания от разбора — {expect['db_schedules']}",
          len(parsed["schedule_rows"]) == expect["db_schedules"],
          f"разбор дал {len(parsed['schedule_rows'])}")
    check(f"{tag}: записей расписания в базе — {expect['db_schedules']}",
          len(schedule_rows) == expect["db_schedules"], f"в базе {len(schedule_rows)}")

    kinds = Counter(str(row["kind"]) for row in schedule_rows)
    check(f"{tag}: записей `schedule` — {expect['db_roots']}, `detailed_daily` — "
          f"{expect['db_detailed']} (замер 2.3)",
          kinds.get(KIND_SCHEDULE, 0) == expect["db_roots"]
          and kinds.get(KIND_DETAILED_DAILY, 0) == expect["db_detailed"]
          and set(kinds) <= set(SCHEDULE_KINDS),
          f"факт: {dict(kinds)}")

    bad_roots = q(cur, f"SELECT job_full_name FROM {SCHEDULES_VIEW} WHERE "
                       "configuration_uuid = %s::uuid GROUP BY job_full_name "
                       "HAVING count(*) FILTER (WHERE kind = %s) <> 1",
                  (str(header["uuid"]), KIND_SCHEDULE))
    check(f"{tag}: ровно одна корневая запись на задание с расписанием "
          f"({expect['db_roots']} заданий)", not bad_roots,
          names([r["job_full_name"] for r in bad_roots]))
    shape = scalar(cur, "SELECT count(*) FROM %s WHERE configuration_uuid = %%s::uuid AND "
                        "((kind = %%s AND (depth <> 1 OR parent_id IS NOT NULL OR "
                        "ordinal <> 0)) OR (kind = %%s AND (depth <> 2 OR parent_id IS NULL)))"
                   % SCHEDULES_VIEW,
                   (str(header["uuid"]), KIND_SCHEDULE, KIND_DETAILED_DAILY))
    check(f"{tag}: вид записи согласован с глубиной, позицией и родителем "
          "(`schedule` — глубина 1, позиция 0, родителя нет; `detailed_daily` — глубина 2, "
          "родитель есть)", not shape, f"нарушений: {shape}")
    deeper = scalar(cur, f"SELECT count(*) FROM {SCHEDULES_VIEW} WHERE configuration_uuid = "
                         "%s::uuid AND (depth < 1 OR depth > %s)",
                    (str(header["uuid"]), MAX_DEPTH))
    check(f"{tag}: глубина расписания не больше {MAX_DEPTH} (замер 2.5, M6)", not deeper,
          f"записей вне диапазона: {deeper}")
    too_many = scalar(cur, f"SELECT count(*) FROM (SELECT parent_id FROM {SCHEDULES_VIEW} "
                           "WHERE configuration_uuid = %s::uuid AND parent_id IS NOT NULL "
                           "GROUP BY parent_id HAVING count(*) > %s) t",
                      (str(header["uuid"]), MAX_DETAILED_PER_RECORD))
    check(f"{tag}: вложенных записей на запись не больше {MAX_DETAILED_PER_RECORD} "
          "(замер 2.5, M6)", not too_many, f"родителей с превышением: {too_many}")
    foreign_parent = scalar(cur, f"SELECT count(*) FROM {SCHEDULES_VIEW} c JOIN "
                                f"{SCHEDULES_VIEW} p ON p.id = c.parent_id WHERE "
                                "c.configuration_uuid = %s::uuid AND c.parent_id IS NOT NULL "
                                "AND (c.scheduled_job_id <> p.scheduled_job_id OR "
                                "p.depth <> 1 OR p.kind <> %s)",
                           (str(header["uuid"]), KIND_SCHEDULE))
    check(f"{tag}: родитель записи принадлежит тому же заданию и является корневой "
          "(композитный ключ работает на данных)", not foreign_parent,
          f"нарушений: {foreign_parent}")

    mismatch_counts = q(cur, f"SELECT j.full_name, j.schedule_record_count, count(s.id) AS n "
                             f"FROM {JOBS_VIEW} j LEFT JOIN {SCHEDULES_VIEW} s "
                             "ON s.scheduled_job_id = j.id WHERE j.configuration_uuid = "
                             "%s::uuid GROUP BY j.full_name, j.schedule_record_count "
                             "HAVING count(s.id) <> j.schedule_record_count",
                        (str(header["uuid"]),))
    check(f"{tag}: `schedule_record_count` равен фактическому числу записей по каждому "
          "заданию (счётчик — вывод разбора, вручную не переписывается)",
          not mismatch_counts,
          names([f"{r['full_name']}: {r['schedule_record_count']} ≠ {r['n']}"
                 for r in mismatch_counts]))

    by_position = {(str(row["job_full_name"]), str(row["kind"]), int(row["ordinal"])): row
                   for row in schedule_rows}
    diffs = []
    for parsed_row in parsed["schedule_rows"]:
        key = (str(parsed_row["job_full_name"]), str(parsed_row["kind"]),
               int(parsed_row["ordinal"]))
        db_row = by_position.get(key)
        if db_row is None:
            diffs.append(f"{key[0]}/{key[1]}/{key[2]}: записи в базе нет")
            continue
        for column in SCHEDULE_ROW_KEYS:
            if norm_value(parsed_row.get(column)) != norm_value(db_row.get(column)):
                diffs.append(f"{key[0]}/{key[1]}/{key[2]}.{column}: разбор "
                             f"{_brief(parsed_row.get(column))}, база "
                             f"{_brief(db_row.get(column))}")
        parsed_parent = parsed_row.get("parent_kind")
        db_parent = db_row["parent_id"]
        if parsed_parent is None:
            if db_parent is not None:
                diffs.append(f"{key[0]}/{key[1]}/{key[2]}: корневой записи разбора "
                             f"соответствует запись базы с parent_id={db_parent}")
            continue
        parent_key = (str(parsed_row["job_full_name"]), str(parsed_parent),
                      int(parsed_row["parent_ordinal"]))
        if db_parent is None or by_position.get(parent_key, {}).get("id") != db_parent:
            diffs.append(f"{key[0]}/{key[1]}/{key[2]}: родитель разбора "
                         f"{parsed_parent}/{parsed_row['parent_ordinal']}, в базе "
                         f"parent_id={db_parent}")
    extra = sorted(set(by_position)
                   - {(str(r["job_full_name"]), str(r["kind"]), int(r["ordinal"]))
                      for r in parsed["schedule_rows"]})
    check(f"{tag}: каждая колонка записи расписания совпадает с разбором того же файла "
          f"({len(SCHEDULE_ROW_KEYS)} ключей на {len(parsed['schedule_rows'])} записей)",
          not diffs and not extra,
          f"расхождений {len(diffs)}: {names(diffs)}; лишних записей базы: {names(extra)}")
    return schedule_rows


# ── контур 6: значения атрибутов записи — стражи, нули, наборы ───────────────────────────────
def check_attribute_values(cur, header, schedule_rows, tag):
    cfg = str(header["uuid"])
    states = Counter()
    for row in schedule_rows:
        for attribute, state in dict(row["attribute_states"] or {}).items():
            states[(str(attribute), str(state))] += 1
    allowed = set(state_vocabulary(f"{SCHEDULES_TABLE}.attribute_states"))
    named = {attribute for attribute, _state in states}
    check(f"{tag}: ключи `attribute_states` замкнуты: ровно {len(named)} атрибутов файла и "
          f"только состояния {sorted(allowed)}",
          named == set(SCHEDULE_ATTRIBUTE_NAMES)
          and {state for _a, state in states} <= allowed,
          f"атрибутов названо: {len(named)}; состояний: "
          f"{sorted({s for _a, s in states})}")

    sentinel_in_columns = scalar(
        cur, "SELECT count(*) FROM %s WHERE configuration_uuid = %%s::uuid AND "
             "(begin_date = %%s::date OR end_date = %%s::date OR begin_time = %%s::time OR "
             "end_time = %%s::time OR completion_time = %%s::time)" % SCHEDULES_TABLE,
        (cfg, DATE_SENTINEL, DATE_SENTINEL, TIME_SENTINEL, TIME_SENTINEL, TIME_SENTINEL))
    check(f"{tag}: значений-стражей платформы (`{DATE_SENTINEL}`, `{TIME_SENTINEL}`) в "
          "колонках `date`/`time` нет — они названы состоянием (Q4, вариант A)",
          not sentinel_in_columns, f"в колонках: {sentinel_in_columns}")

    pairs = list(zip(SCHEDULE_ATTRIBUTE_NAMES, ATTRIBUTE_COLUMNS))
    # Имена колонок подставляются в SQL литералом (они берутся из констант модуля разбора,
    # а не из ввода), значения атрибутов — параметрами.
    clauses = " OR ".join(
        f"(attribute_states ->> %s = 'set' AND {column} IS NULL)"
        f" OR (attribute_states ->> %s IN ('sentinel', 'absent') AND {column} IS NOT NULL)"
        for _attribute, column in pairs)
    state_column_mismatch = scalar(
        cur, f"SELECT count(*) FROM {SCHEDULES_TABLE} "
             f"WHERE configuration_uuid = %s::uuid AND ({clauses})",
        (str(header["uuid"]),)
        + tuple(attribute for attribute, _column in pairs for _twice in (0, 1)))
    check(f"{tag}: состояние атрибута согласовано с колонкой: `set` — значение есть, "
          "`sentinel`/`absent` — колонки нет (CHECK на данных)",
          not state_column_mismatch, f"расхождений: {state_column_mismatch}")

    integer_columns = [(attribute, column) for attribute, column, kind in SCHEDULE_ATTRIBUTES
                       if kind == VALUE_KIND_INT]
    zero_clauses = " OR ".join(
        f"(attribute_states ->> %s = 'zero' AND {column} IS DISTINCT FROM 0)"
        for _attribute, column in integer_columns)
    zero_mismatch = scalar(
        cur, f"SELECT count(*) FROM {SCHEDULES_TABLE} "
             f"WHERE configuration_uuid = %s::uuid AND ({zero_clauses})",
        (str(header["uuid"]),)
        + tuple(attribute for attribute, _column in integer_columns))
    check(f"{tag}: состояние `zero` обязано сопровождаться значением 0 в колонке — «нет "
          "повторов» и «нет паузы» выразимы числом, а не отсутствием (замер 2.2)",
          not zero_mismatch, f"расхождений: {zero_mismatch}")

    out_of_range = scalar(
        cur, f"SELECT count(*) FROM {SCHEDULES_TABLE} WHERE configuration_uuid = %s::uuid "
             "AND (exists(SELECT 1 FROM unnest(week_days) d WHERE d NOT BETWEEN %s AND %s) "
             "OR exists(SELECT 1 FROM unnest(months) m WHERE m NOT BETWEEN %s AND %s))",
        (cfg, min(WEEK_DAY_RANGE), max(WEEK_DAY_RANGE), min(MONTHS_RANGE), max(MONTHS_RANGE)))
    check(f"{tag}: наборы дней ({min(WEEK_DAY_RANGE)}…{max(WEEK_DAY_RANGE)}) и месяцев "
          f"({min(MONTHS_RANGE)}…{max(MONTHS_RANGE)}) замкнуты диапазонами платформы",
          not out_of_range, f"вне диапазона: {out_of_range}")

    set_mismatch = scalar(
        cur, f"SELECT count(*) FROM {SCHEDULES_TABLE} WHERE configuration_uuid = %s::uuid "
             "AND ((week_days_state = 'values' AND week_days IS NULL) OR "
             "(week_days_state IN ('empty_element_all', 'absent') AND week_days IS NOT NULL) "
             "OR (months_state = 'values' AND months IS NULL) OR "
             "(months_state IN ('empty_element_all', 'absent') AND months IS NOT NULL))",
        (cfg,))
    check(f"{tag}: состояние набора согласовано с колонкой: `values` — массив есть, "
          "`empty_element_all`/`absent` — массива нет (мера M5: пустой элемент — «все дни», "
          "а не «ни одного дня»)", not set_mismatch, f"расхождений: {set_mismatch}")
    return Counter((str(row["week_days_state"]), str(row["months_state"]))
                   for row in schedule_rows)


# ── контур 7: обработчик — разложение, разрешение по витрине СВОЕЙ конфигурации ───────────────
def check_method_resolution(cur, header, job_rows, modules, expect, tag):
    states = Counter(str(row["method_state"]) for row in job_rows)
    check(f"{tag}: состояний обработчика — `exact` {expect['method_exact']}, "
          "`unresolved`/`unknown_form`/`empty_value`/`absent` — нули (замер 2.4: 346 из 346 "
          "проходят форму)",
          states.get(METHOD_STATE_EXACT, 0) == expect["method_exact"]
          and not states.get("unresolved") and not states.get("unknown_form")
          and not states.get("empty_value") and not states.get("absent"),
          f"факт: {dict(states)}")

    bad_form = scalar(
        cur, f"SELECT count(*) FROM {JOBS_VIEW} WHERE configuration_uuid = %s::uuid AND "
             "(method_state = 'exact' AND (method_name IS DISTINCT FROM "
             "'CommonModule.' || method_module || '.' || method_method "
             "OR method_module IS NULL OR method_method IS NULL))",
        (str(header["uuid"]),))
    check(f"{tag}: `MethodName` разложен на модуль и метод: текст обработчика равен "
          "`CommonModule.<модуль>.<метод>` во всех строках (мера V53 — вопрос «какие задания "
          "вызывает этот модуль» читается индексом без разбора текста)", not bad_form,
          f"расхождений: {bad_form}")

    unresolved_modules = q(
        cur, f"SELECT j.full_name, j.method_module FROM {JOBS_VIEW} j WHERE "
             "j.configuration_uuid = %s::uuid AND j.method_state = 'exact' "
             f"AND NOT exists(SELECT 1 FROM {COMMON_MODULES_VIEW} m WHERE "
             "m.configuration_uuid = j.configuration_uuid AND m.object_name = j.method_module)",
        (str(header["uuid"]),))
    check(f"{tag}: каждый разрешённый обработчик существует в общих модулях ТЕКУЩЕЙ ревизии "
          "СВОЕЙ конфигурации (витрина, а не вся таблица — Q3 узла V54)",
          not unresolved_modules,
          names([f"{r['full_name']} → {r['method_module']}" for r in unresolved_modules]))
    allowed = set(modules.get("names") or set())
    wrong = sorted(str(row["method_module"]) for row in job_rows
                   if row["method_state"] == METHOD_STATE_EXACT
                   and str(row["method_module"]) not in allowed)
    check(f"{tag}: состояние пересчитано по тому же перечню модулей, что и загрузка "
          f"(перечень доступен: {bool(allowed)})", not wrong,
          f"модулей вне перечня: {names(wrong)}")

    declared = Counter(str(row["method_declared_state"]) for row in job_rows)
    check(f"{tag}: объявление метода названо состоянием `{METHOD_TEXT_UNAVAILABLE}` для всех "
          f"{len(job_rows)} строк — текстов общих модулей в базе нет (решение D-S4 узла V46), "
          "поэтому `declared`/`not_declared` нечем подтвердить (Q8, вариант A)",
          declared.get(METHOD_TEXT_UNAVAILABLE, 0) == len(job_rows)
          and not declared.get("declared") and not declared.get("not_declared"),
          f"факт: {dict(declared)}")


# ── контур 8: витрины текущего состояния и сироты ─────────────────────────────────────────────
def check_revisions_and_views(cur):
    section("Контур 8 — витрины текущего состояния и сироты")
    current_direct = scalar(
        cur, f"SELECT count(*) FROM {TABLE_NAME} j WHERE NOT exists("
             f"SELECT 1 FROM {TABLE_NAME} n WHERE n.configuration_uuid = j.configuration_uuid "
             "AND n.object_name = j.object_name AND n.revision_no > j.revision_no)")
    in_view = scalar(cur, f"SELECT count(*) FROM {JOBS_VIEW}")
    check(f"витрина `{JOBS_VIEW}` отдаёт ровно строки максимальной ревизии "
          f"({current_direct} строк)", current_direct == in_view,
          f"вне витрины: {current_direct}, в витрине: {in_view}")

    orphans = scalar(cur, f"SELECT count(*) FROM {SCHEDULES_TABLE} s WHERE NOT exists("
                          f"SELECT 1 FROM {JOBS_VIEW} j WHERE j.id = s.scheduled_job_id)")
    check(f"записей расписания вне текущей ревизии задания — ноль (свои сироты узла V54)",
          not orphans, f"сирот: {orphans}")
    wrong_owner = scalar(
        cur, f"SELECT count(*) FROM {SCHEDULES_TABLE} s JOIN {JOBS_VIEW} j "
             "ON j.id = s.scheduled_job_id WHERE s.configuration_uuid <> j.configuration_uuid "
             f"OR s.job_object_uuid <> j.object_uuid OR s.job_full_name <> j.full_name")
    check("граница конфигурации и указатели на строку задания совпадают у каждой записи",
          not wrong_owner, f"расхождений: {wrong_owner}")
    bad_root_tag = scalar(cur, f"SELECT count(*) FROM {SCHEDULES_TABLE} WHERE root_tag <> %s",
                          (SCHEDULE_ROOT_TAG,))
    check(f"корневым тегом записи является `{SCHEDULE_ROOT_TAG}` — обещание сохранения "
          "содержимого обратно (возражение группы F модели A–H)", not bad_root_tag,
          f"чужих тегов: {bad_root_tag}")
    paths = scalar(cur, f"SELECT count(*) FROM {SCHEDULES_TABLE} WHERE file_path NOT LIKE %s",
                   (f"{DIR_NAME}/%/Ext/{SCHEDULE_FILE_NAME}",))
    check(f"путь файла содержимого у всех записей — `*/Ext/{SCHEDULE_FILE_NAME}`",
          not paths, f"чужих путей: {paths}")


# ── контур 9: контракт стадии, круга снятия и сохранённых видов ───────────────────────────────
def check_contract():
    section("Контур 9 — контракт стадии и круга снятия")
    ids = [stage for stage, _title in STAGES]
    check(f"стадия `{STAGE_SCHEDULED_JOBS}` стоит сразу после `{STAGE_EVENT_SUBSCRIPTIONS}` "
          f"(позиции 2.8 → 2.9 нормативного списка)",
          ids.index(STAGE_SCHEDULED_JOBS) == ids.index(STAGE_EVENT_SUBSCRIPTIONS) + 1,
          f"порядок: {ids}")
    check(f"`{STAGE_OBJECT_MODULES}` остаётся последней стадией (вторая транзакция текстов)",
          ids[-1] == STAGE_OBJECT_MODULES and ids.index(STAGE_SCHEDULED_JOBS) < len(ids) - 1,
          f"порядок: {ids}")
    check(f"`stages_after('{STAGE_EVENT_SUBSCRIPTIONS}')` называет продолжением "
          f"`{STAGE_SCHEDULED_JOBS}`",
          stages_after(STAGE_EVENT_SUBSCRIPTIONS)[:1] == [STAGE_SCHEDULED_JOBS],
          str(stages_after(STAGE_EVENT_SUBSCRIPTIONS)))
    check(f"у стадии `{STAGE_SCHEDULED_JOBS}` есть зеркало продолжения "
          "(`STAGE_FULL_RELOAD_ONLY` = False — стадия дозакрывается отдельным входом)",
          STAGE_FULL_RELOAD_ONLY.get(STAGE_SCHEDULED_JOBS) is False,
          str(STAGE_FULL_RELOAD_ONLY.get(STAGE_SCHEDULED_JOBS)))
    title = stage_title(STAGE_SCHEDULED_JOBS)
    hint = stage_resume_hint(STAGE_SCHEDULED_JOBS)
    check("заголовок стадии называет позицию 2.9 и каталог вида",
          "2.9" in title and DIR_NAME in title, title)
    check("подсказка продолжения называет отдельный вход `load_scheduled_jobs_tool` и "
          "полную перезагрузку",
          "load_scheduled_jobs_tool" in hint and "load_1c_catalog_tool" in hint, _brief(hint))
    check("круг записи — две таблицы вида в порядке иерархии (сначала вид, затем расписание)",
          tuple(SCHEDULED_JOBS_TABLES) == (TABLE_NAME, SCHEDULES_TABLE),
          str(SCHEDULED_JOBS_TABLES))
    check(f"круг снятия начинается с `{SCHEDULES_TABLE}` — иначе каскад внешнего ключа снял "
          "бы строки молча, и число в ответе было бы неправдой (M7)",
          tuple(SCHEDULED_JOBS_REMOVE_ORDER) == (SCHEDULES_TABLE, TABLE_NAME),
          str(SCHEDULED_JOBS_REMOVE_ORDER))
    check("вид `ScheduledJob` назван сохранённым в реестре `STORED_META_KINDS` — тем же "
          "словарём, которым пользуется карточка загрузки (дефект, вскрытый "
          "`_v54_p5_stage_probe.py`)",
          "ScheduledJob" in STORED_META_KINDS,
          f"реестр: {names(sorted(STORED_META_KINDS))}")


# ── корпус и чужие таблицы ────────────────────────────────────────────────────────────────────
FOREIGN_TABLES = (
    "configurations", "configuration_objects", "subsystems", "subsystem_content",
    "common_modules", "session_parameters", "roles", "role_rights",
    "role_restriction_templates", "common_attributes", "common_attribute_targets",
    "exchange_plans", "exchange_plan_content", "filter_criteria",
    "filter_criterion_content", "event_subscriptions", "event_subscription_sources",
    "attributes", "tabular_sections", "forms", "form_ext", "templates", "commands",
    "bsl_modules",
)

# Пары «мера прогона ↔ ключ плана»: суммы по четырём выгрузкам сравниваются с замерами
# 2.2–2.5 плана, а не с числом, выведенным из прогона.
CORPUS_KEYS = (
    ("jobs", "jobs"), ("schedules", "schedules"), ("roots", "roots"),
    ("detailed", "detailed"), ("depth_1", "depth_1"), ("depth_2", "depth_2"),
    ("max_ordinal_depth_2", "max_ordinal_depth_2"),
    (VALUE_SENTINEL, "sentinel"), (VALUE_ZERO, "zero"), (VALUE_SET, "set"),
    ("week_days_values", "week_days_values"),
    ("week_days_empty_element_all", "week_days_empty_element_all"),
    ("months_values", "months_values"),
    ("months_empty_element_all", "months_empty_element_all"),
)


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


def accumulate_corpus(accum, job_rows, schedule_rows):
    accum["jobs"] += len(job_rows)
    accum["schedules"] += len(schedule_rows)
    accum["schedule_absent"] += sum(1 for row in job_rows if row["schedule_state"] == "absent")
    for row in schedule_rows:
        accum["depth_%s" % int(row["depth"])] += 1
        accum["roots" if row["kind"] == KIND_SCHEDULE else "detailed"] += 1
        if int(row["depth"]) == 2:
            accum["max_ordinal_depth_2"] = max(accum["max_ordinal_depth_2"], int(row["ordinal"]))
        for _attribute, state in dict(row["attribute_states"] or {}).items():
            accum[str(state)] += 1
        accum[f"week_days_{row['week_days_state']}"] += 1
        accum[f"months_{row['months_state']}"] += 1


def check_corpus(accum, all_loaded):
    section("Контур корпуса — суммы по четырём выгрузкам")
    check("все четыре выгрузки прогнаны (MinCfg, KomMag, BGU2, BP3)", all_loaded,
          "часть выгрузок не прогнана — суммы сравнивать не с чем")
    for measured, plan_key in CORPUS_KEYS:
        plan = CORPUS_EXPECTATIONS[plan_key]
        check(f"корпус: `{measured}` — {plan} (замеры разделов 2.2–2.5 плана)",
              accum.get(measured, 0) == plan, f"факт: {accum.get(measured, 0)}")
    absent_plan = sum(expect["schedule_absent"] for expect in PLAN_EXPECTATIONS.values())
    check(f"корпус: заданий без расписания — {absent_plan} (BGU2 19, BP3 24 — M4)",
          accum.get("schedule_absent", 0) == absent_plan,
          f"факт: {accum.get('schedule_absent', 0)}")


def run(cur, scope):
    headers = q(cur, "SELECT id, uuid::text AS uuid, name FROM configurations ORDER BY id")
    if not headers:
        FAILED.append("строк заголовков конфигураций в базе нет — сравнивать не с чем")
        print("FAIL строк заголовков конфигураций в базе нет — сравнивать не с чем")
        return
    before = foreign_state(cur)
    accum = Counter()
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
        modules = read_common_module_names(cur, str(header["uuid"]))
        if not modules.get("available"):
            info(f"{tag}: перечень общих модулей недоступен — {modules.get('reason')}")
        parsed = collect_scheduled_jobs(dump_dir, index_info["rows"], modules["names"])
        check(f"{tag}: разбор круга завершён без отказа ({expect['files']} файлов)",
              parsed["success"] is True and parsed["files_found"] == expect["files"]
              and parsed["files_read"] == expect["files"],
              f"success: {parsed['success']}, found: {parsed['files_found']}, "
              f"read: {parsed['files_read']}, failed: {_brief(parsed['files_failed'])}")

        job_rows = check_circle(cur, header, dump_dir, index_info, expect, parsed, tag)
        check_job_rows(parsed, job_rows, expect, tag)
        schedule_rows = check_schedule_tree(cur, header, parsed, expect, tag)
        check_attribute_values(cur, header, schedule_rows, tag)
        check_method_resolution(cur, header, job_rows, modules, expect, tag)

        accumulate_corpus(accum, job_rows, schedule_rows)
        loaded.add(tag)

    check_schema(cur)
    check_state_vocabulary_checks(cur)
    check_revisions_and_views(cur)
    check_contract()
    if scope == DEFAULT_SCOPE:
        check_corpus(accum, loaded == set(PLAN_EXPECTATIONS))
    else:
        skip("Контур корпуса — суммы по четырём выгрузкам",
             f"охват `{scope}`: остальные выгрузки не прогнаны, сравнивать суммы не с чем")
    check_non_interference(before, foreign_state(cur))


def main(argv):
    scope = str(argv[1]) if len(argv) > 1 else DEFAULT_SCOPE
    print(f"=== постоянная проверка узла V54 (регламентные задания) — охват {scope} ===")
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
