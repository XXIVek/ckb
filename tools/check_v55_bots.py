# -*- coding: utf-8 -*-
"""check_v55_bots.py — постоянная проверка узла V55 (боты, позиция 2.10 нормативного списка).

Зачем. Узел V55 закрыл круг позиции 2.10: каталог `Bots/` (файл регистрации вида +
единственный ребёнок `Ext/Module.bsl`), одну таблицу `bots` с цепью ревизий, стадию
`s4j_bots` и тринадцатый инструмент регистра `load_bots_tool`. Пока эти строки лежат в
базе, обязан существовать прогон, который повторяет их числа и состояния, а не пересказывает
план. Источник ожиданий — `docs/CONFIGURATION_BOTS_PLAN.md` (раздел 1.1 — круг тремя ногами
по четырём выгрузкам, 2.1 — словарь пяти тегов и ссылка `Picture` с двумя классами цели,
1.2 — единственная дочерняя запись индекса, раздел 5 — меры M1…M7, раздел 9 — критерии
готовности); числа сняты `_v55_p0_probe.py`, `_v55_m1_probe.py`, `_v55_p3_parse_probe.py` и
подтверждены `_v55_p4_load_probe.py`, `_v55_p5_stage_probe.py` (прогон 04.11.2026). Числа
`PLAN_EXPECTATIONS` переносятся без правок: сглаживать число проверкой значило бы
подтверждать неверное число (прецедент узлов V49/V50).

Отличие круга от V48–V54 одно, и проверку строит именно оно: **вид существует ровно в одной
выгрузке эталонного набора**. `Bots/` есть только у `MinCfg` (2 файла регистрации и 2 файла
модулей); у `KomMag`, `BGU2`, `BP3` каталога нет ни файлом, ни строкой индекса, а перечень
`configurations.bots` у этих трёх строк — `NULL`. Поэтому нули обязано называть числом и
наблюдением `directory_missing`, а не молчанием (Q9, мера M6): прогон обязан уметь отличить
«вида нет в выгрузке» от «стадия не запускалась».

Контуры (номера совпадают с `check_v54_scheduled_jobs.py`):

  1. СХЕМА. Таблица `bots` жива и держит эталонное число колонок (28 — эталон шага П1); ключ
     строки вида — (`configuration_uuid`, `object_name`, `revision_no`) (M1); внешнего ключа
     на заголовок и на цель ссылки нет осознанно (прецедент V20.1, Q3); второй таблицы вида
     нет (M3) — обход `information_schema` по маске вида обязан дать ровно `bots`; витрина
     `v_current_bots` жива и выведена реестром версионируемых.
  2. СЛОВАРИ ↔ CHECK. Каждый закрытый словарь состояний (`STATE_VOCABULARIES`) замкнут
     CHECK живой схемы в обе стороны; состояния `pending`, которые разбор производит только
     при офлайн-входе, CHECK'у неизвестны — «не проверяли» и «не разрешилось» разные ответы
     (прецедент `index_check.state = not_checked` V53). Ограничения согласованности
     (свойства ↔ виновники, ссылка ↔ значение, признак ↔ блок, модуль ↔ дескриптор,
     `module_loaded` ↔ состояние) обязаны существовать и не допускать состояний вне словарей.
  3. ГРАНИЦА КРУГА. Файлы `Bots/*.xml` ↔ верхние записи индекса (`Bot.<Имя>`) ↔ перечень
     `configurations.bots[]` ↔ строки таблицы; отдельной ногой — файл `Ext/Module.bsl` ↔
     дочерняя запись `Bot.<Имя>.Module`. Расхождений ног ноль; у трёх выгрузок каталога нет
     ни одной ногой — это ответ о выгрузке с наблюдением, а не отказ (Q6, M6).
  4. СТРОКА ВИДА ↔ РАЗБОР. Строки таблицы сравниваются с кругом, разобранным ТЕМ ЖЕ модулем
     (`collect_bots`), что и загрузка: свойства, состояния, разложенная ссылка, дескрипторы
     модуля, виновники неизвестных тегов. Подтверждение файла записью индекса — `matched` у
     2 файлов из 2; `file_only` / `uuid_mismatch` / `index_only` — ноль.
  5. ССЫЛКА `Picture`. Обязанные состояниями две строки: `exact` на
     `CommonPicture.ОбщаяКартинка1` (с адресом строки индекса) и `std_picture` на
     `StdPicture.GroupConversation` (без полей индекса — стандартного средства в индексе не
     бывает никогда). Класс цели и состояние проверяются построчно; обратный вопрос «какие
     боты ссылаются на картинку» читается по `picture_full_name` (индекс узла П1).
  6. МОДУЛЬ ВИДА (M5). Состояние двух ног — `file_and_index` у 2 объектов из 2; путь и
     размер дескриптора сверяются с файлом на диске НЕ разбором, а `stat`; строки
     `bsl_modules` принадлежат узлу V47 и не снимаются стадией: их число равно числу строк
     с `module_loaded = true`, а круга снятия `bots` их не содержит.
  7. ВИТРИНЫ, СИРОТЫ И ЧУЖИЕ КРУГИ. Витрина отдаёт ровно строки максимальной ревизии;
     строк без заголовка — ноль; строк вида в чужих кругах (реквизиты, табличные части,
     формы, элементы форм, макеты, команды по `parent_uuid`) — ноль, потому что детей у вида
     нет ни в одной выгрузке (замер 1.1); запись вида обязана существовать в индексе
     состава той же конфигурации.
  8. КОНТРАКТ. Стадия `s4j_bots` стоит сразу после `s4i_scheduled_jobs` и перед
     `s4b_object_modules` (порядок позиций 2.9 → 2.10, модули остаются второй транзакцией);
     зеркало `STAGE_FULL_RELOAD_ONLY` = False (стадия дозакрывается отдельным входом),
     подсказка называет `load_bots_tool`, вид назван в `STORED_META_KINDS` кругом
     `BOTS_TABLES`, а `bots` входит в `FOREIGN_STAGE_TABLES` — иначе стадия S4 сняла бы
     чужие строки (дефект, закрытый константой узла V55).
  9. ИТОГ ПО КОРПУСУ и неприкосновенность чужих кругов: суммы по четырём выгрузкам равны
     разделам 1.1 и 2 плана (2 файла, 2 записи вида и 2 записи модуля в индексе, 2 имени
     перечня у одной выгрузки и `NULL` у трёх, 2 строки таблицы, 1 `exact` + 1 `std_picture`,
     2 `file_and_index`, 662 байта модулей, 3 наблюдения `directory_missing`); прогон
     читающий — число строк чужих таблиц до и после него совпадает, а отсутствующая таблица
     называется, а не пропускается.

Границы проверки (названы, а не промолчаны). Словарь свойств вида корпусом не замкнут
(5 тегов по 2 файлам, XSD нет — раздел 2 плана), поэтому незнакомый тег остаётся состоянием
`unknown_tag` с именем: проверка требует, чтобы на всём круге состояний `unknown_tag` /
`unknown_value` не было (корпус их не давал) и чтобы механизм виновников был живым (CHECK и
колонка), а не того, что их не могло бы быть. Объявленность и тексты модулей вида не
проверяются: их пишет узел V47, а проверка читает только дескрипторы и признак строки
(Q4, M5). Остановка конвейера и продолжение отдельным входом — проба
`_v55_p5_stage_probe.py` и шаг П8, а не этот скрипт: проверка ничего в базу не пишет.
Независимая регулярковая мера файла регистрации (байты, число тегов) здесь не повторяется:
она снята `_v55_p0_probe.py` и `_v55_p3_parse_probe.py`, а скрипт сверяет разбор с базой —
второй независимый путь к тем же числам.

Запуск:
    python tools/check_v55_bots.py [MinCfg|KomMag|BGU2|BP3|all]
Код возврата 0 — провалов нет; 1 — есть. Пропуск называется причиной, а не тишиной. Охват
одной выгрузки — это её граница круга и свои строки; контур сумм корпуса при таком охвате
пропускается с причиной, потому что сравнивать его с планом четырёх выгрузок нельзя (у трёх
из них вида нет вовсе, и нули этих трёх — половина эталона).
"""
from __future__ import annotations

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

from configuration_bots import (  # noqa: E402
    DIR_NAME, INDEX_CHECK_STATES, INDEX_MATCHED, MODULE_DIR_NAME, MODULE_FILE_AND_INDEX,
    MODULE_FILE_NAME, OBJECT_KIND_TAG, OBSERVATION_KINDS, PICTURE_EXACT, PICTURE_PENDING,
    PICTURE_STATES, PICTURE_STD, PROPERTIES_ALL_KNOWN, PROPERTIES_UNKNOWN_TAG,
    PROPERTIES_UNKNOWN_VALUE, STATE_VOCABULARIES, STD_PICTURE_PREFIX, TARGET_COMMON_PICTURE,
    TARGET_STD_PICTURE, collect_bots, module_index_name, state_vocabulary,
)
from configuration_bots_loader import read_index_records, read_loaded_module_names  # noqa: E402
from configuration_load_contract import (  # noqa: E402
    BOTS_DIR, BOTS_META_TAG, BOTS_REMOVE_ORDER, BOTS_TABLES, FOREIGN_STAGE_TABLES,
    STAGE_BOTS, STAGE_FULL_RELOAD_ONLY, STAGE_OBJECT_MODULES, STAGE_SCHEDULED_JOBS, STAGES,
    STORED_META_KINDS, stage_resume_hint, stage_title, stages_after,
)
from configuration_module_slots import resolve_dump_dir  # noqa: E402
from current_revision import CONFIGURATION_VERSIONED_TABLES, current_view  # noqa: E402
from external_db import transaction  # noqa: E402

TABLE_NAME = "bots"
BOT_VIEW = current_view(TABLE_NAME)
HEADER_NAME_COLUMN = "bots"
BSL_MODULES_VIEW = "v_current_bsl_modules"
INDEX_TABLE = "configuration_objects"
INDEX_KIND = "Bot"
INDEX_CHILD = "Module"

# Число колонок таблицы вида — эталон шага П1 (`migrate_v55_bots.sql` и то же зеркало в
# `create_1c_configurations_db.sql`). Второй таблицы у узла нет (M3), поэтому перечень
# одноэлементный, а пустой ответ контура 1 по маске вида является проверкой этого факта.
EXPECTED_COLUMN_COUNTS = {TABLE_NAME: 28}

# Таблицы чужих кругов, в которых строка вида могла бы оставить детей (замер 1.1: детей у
# вида нет ни в одной выгрузке). Перечень читается по колонке `parent_uuid` живой схемы —
# контур 7 требует, чтобы во всех них строк вида было ноль.
CHILD_BEARING_TABLES = ("attributes", "tabular_sections", "forms", "form_ext", "templates",
                       "commands")

# Чужие таблицы для меры «прогон ничего не пишет» (прецедент V54) — соседи по нормативному
# списку и модули V47: узел V55 не снимает и не перезаписывает ни одного их круга.
FOREIGN_TABLES = (
    "configurations", "configuration_objects", "subsystems", "subsystem_content",
    "common_modules", "session_parameters", "roles", "role_rights",
    "role_restriction_templates", "common_attributes", "common_attribute_targets",
    "exchange_plans", "exchange_plan_content", "filter_criteria",
    "filter_criterion_content", "event_subscriptions", "event_subscription_sources",
    "scheduled_jobs", "scheduled_job_schedules", "attributes", "tabular_sections", "forms",
    "form_ext", "templates", "commands", "bsl_modules",
)

# Поля строки вида, сверяемые «разбор ↔ строка базы». `synonym` (jsonb) и
# `unknown_property_names` (массив) сравниваются отдельными проверками: пустой перечень
# виновников обязан быть NULL, а не пустым массивом (CHECK
# `bots_properties_state_matches_unknown`), и сравнивать массив с Python-списком — значит
# сравнивать две разные формы.
ROW_FIELDS = (
    "object_uuid", "object_name", "full_name", "comment", "predefined", "picture_ref",
    "picture_target_class", "picture_full_name", "picture_object_id",
    "picture_object_uuid", "picture_state", "picture_load_transparent",
    "picture_load_transparent_state", "module_state", "module_source_path",
    "module_source_size", "module_loaded", "properties_state", "source_path",
)

DUMP_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
DEFAULT_SCOPE = "all"
MAX_NAMES = 8

PASSED, FAILED, SKIPPED, INFO = [], [], [], []



# ── ожидания (числа плана docs/CONFIGURATION_BOTS_PLAN.md, разделы 1.1, 1.2, 2, 2.1) ────────
# Ключ — каталог выгрузки, а не имя строки заголовка: имя заголовка меняется вместе с
# выгрузкой, а каталог — адрес, по которому проверка находит файлы (прецедент V54).
#   files / subdirs / non_xml — каталог `Bots/` (файл регистрации + подкаталог содержимого;
#            других детей у вида нет — замеры 1.1 и 1.2);
#   module_files — файлы `Ext/Module.bsl` (нога модуля);
#   index_rows / index_children — записи индекса `Bot.<Имя>` и `Bot.<Имя>.Module` (1.2);
#   header_list — заполненный стадией S2 перечень `configurations.bots[]`; header_null —
#            признак `NULL` в колонке: у трёх выгрузок вида нет ни одной ногой, и пустой
#            перечень различается с отсутствующим (M6, прецедент Q9 узлов V48/V50/V52/V53);
#   db_rows — строки `bots` текущего состояния;
#   picture_exact / picture_std — состояния ссылки по замеру 2.1 (по одному на выгрузку);
#   module_file_and_index / props_all_known / loaded_modules — состояния, обязанные быть
#            полными на всём круге (замеры 1.1, 2, 2.2);
#   directory_missing — наблюдение об отсутствующем каталоге вида (Q6): ровно один раз там,
#            где каталога нет, и ноль там, где он есть;
#   module_bytes — байты файлов `Ext/Module.bsl` (замер 1.4: 359 + 303 = 662).
PLAN_EXPECTATIONS: Dict[str, Dict[str, int]] = {
    "MinCfg": {"files": 2, "subdirs": 2, "non_xml": 0, "module_files": 2,
               "index_rows": 2, "index_children": 2, "header_list": 2, "header_null": 0,
               "db_rows": 2, "picture_exact": 1, "picture_std": 1,
               "module_file_and_index": 2, "props_all_known": 2, "loaded_modules": 2,
               "directory_missing": 0, "module_bytes": 662},
    "KomMag": {"files": 0, "subdirs": 0, "non_xml": 0, "module_files": 0,
               "index_rows": 0, "index_children": 0, "header_list": 0, "header_null": 1,
               "db_rows": 0, "picture_exact": 0, "picture_std": 0,
               "module_file_and_index": 0, "props_all_known": 0, "loaded_modules": 0,
               "directory_missing": 1, "module_bytes": 0},
    "BGU2": {"files": 0, "subdirs": 0, "non_xml": 0, "module_files": 0,
             "index_rows": 0, "index_children": 0, "header_list": 0, "header_null": 1,
             "db_rows": 0, "picture_exact": 0, "picture_std": 0,
             "module_file_and_index": 0, "props_all_known": 0, "loaded_modules": 0,
             "directory_missing": 1, "module_bytes": 0},
    "BP3": {"files": 0, "subdirs": 0, "non_xml": 0, "module_files": 0,
            "index_rows": 0, "index_children": 0, "header_list": 0, "header_null": 1,
            "db_rows": 0, "picture_exact": 0, "picture_std": 0,
            "module_file_and_index": 0, "props_all_known": 0, "loaded_modules": 0,
            "directory_missing": 1, "module_bytes": 0},
}

# Ожидания корпуса (четыре выгрузки) — разделы 1.1, 1.2, 1.4, 2.1 плана. Вид существует
# ровно в одной выгрузке, поэтому нули трёх других входят в эталон: сравнить корпус с
# «двумя строками» без них значило бы не заметить, что круг исчез. Наблюдений
# `directory_missing` в эталоне ровно три — по одному на выгрузку без каталога вида (Q6,
# M6): это состояние выгрузки, а не отказ стадии, и ноль здесь означал бы, что прогон
# перестал отличать «вида нет в выгрузке» от «стадия не запускалась».
CORPUS_EXPECTATIONS = {
    "rows": 2, "index_rows": 2, "index_children": 2, "header_names": 2, "header_null": 3,
    "files": 2, "module_files": 2, "directory_missing": 3, "missing_directories": 3,
    "picture_exact": 1, "picture_std": 1, "picture_other_states": 0,
    "module_file_and_index": 2, "module_loaded": 2, "props_all_known": 2,
    "unknown_states": 0, "module_bytes": 662, "bsl_module_rows": 2, "index_matched": 2,
    "circle_discrepancies": 0,
}

# Построчный эталон ссылки `Picture` (замер 2.1): имена файлов регистрации названы планом в
# разделе 1.2 (`Bots/Бот1/Ext/Module.bsl`, `Bots/Бот2/Ext/Module.bsl`). Различие принципиальное:
# `CommonPicture.` — объект конфигурации (слой 2.19 не загружен, но запись индекса состава
# есть), `StdPicture.` — стандартное средство платформы, которого в индексе не бывает НИКОГДА.
PICTURE_ROW_EXPECTATIONS = {
    "Бот1": {"picture_state": PICTURE_EXACT, "picture_target_class": TARGET_COMMON_PICTURE,
             "picture_full_name": "CommonPicture.ОбщаяКартинка1", "index_resolved": True},
    "Бот2": {"picture_state": PICTURE_STD, "picture_target_class": TARGET_STD_PICTURE,
             "picture_full_name": "StdPicture.GroupConversation", "index_resolved": False},
}

# Ограничения согласованности, которые обязан держать живой писатель (DDL узла V55): без них
# состояние ссылалось бы на само себя, а не на значение колонки.
MATCH_CONSTRAINTS = (
    "bots_names_not_blank",
    "bots_properties_state_matches_unknown",
    "bots_all_known_covers_required_parts",
    "bots_picture_state_matches_value",
    "bots_picture_uuid_only_when_resolved",
    "bots_picture_load_transparent_matches_picture",
    "bots_module_state_matches_descriptor",
    "bots_module_loaded_matches_state",
    "bots_revision_no_positive",
    "bots_changed_by_known",
)

# Состояния, которых словарь DDL не держит осознанно: их производит только офлайн-разбор
# шага П3 без индекса состава. В таблицу они не попадают, и CHECK отклоняет их — это
# правильная реакция («не проверяли» и «не разрешилось» разные ответы, прецедент
# `index_check.state = not_checked` V53).
OFFLINE_ONLY_STATES = (PICTURE_PENDING,)



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
                      "JOIN pg_class t ON t.oid = x.indrelid WHERE t.relname = %s", (table,)):
        out[str(row["name"])] = str(row["def"] or "")
    return out


def compact(text):
    """Одна строка для сравнения и вывода: переносы и двойные пробелы схемы не значимы."""
    return " ".join(str(text).split())


def expect_of(tag):
    """Эталон выгрузки; отсутствующего ключа нет — план называет все меры для всех четырёх."""
    return PLAN_EXPECTATIONS[tag]


# ── контур 1: живая схема круга ──────────────────────────────────────────────────────────────
def check_schema(cur):
    section("Контур 1 — живая схема круга")
    if not q(cur, "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
             (TABLE_NAME,)):
        check(f"{TABLE_NAME}: таблица существует", False, "таблицы в схеме нет")
        return
    columns = table_columns(cur, TABLE_NAME)
    check(f"{TABLE_NAME}: таблица существует и держит {EXPECTED_COLUMN_COUNTS[TABLE_NAME]} "
          "колонок (эталон П1)", len(columns) == EXPECTED_COLUMN_COUNTS[TABLE_NAME],
          f"факт: {len(columns)}")

    # M3: второй таблицы у узла нет — обход схемы по маске вида обязан дать ровно `bots`
    # (ни `bot_pictures`, ни `bot_modules`: вариант C отклонён кратностью, вариант B —
    # потерей проверяемости состояний).
    kind_tables = [str(r["table_name"]) for r in q(
        cur, "SELECT table_name FROM information_schema.tables WHERE table_name LIKE %s "
             "ORDER BY table_name", ("bot%",))]
    check(f"таблиц вида по маске `bot%` — ровно одна `{TABLE_NAME}` (M3, Q1 вариант A)",
          kind_tables == [TABLE_NAME], f"найдено: {names(kind_tables)}")

    wanted = "(configuration_uuid, object_name, revision_no)"
    keys = unique_constraints(cur, TABLE_NAME)
    scope = [d for d in keys.values() if compact(d).endswith(wanted)]
    check(f"`{TABLE_NAME}`: ключ области видимости строк узла живой {wanted} (M1)",
          len(scope) == 1, f"ключи схемы: {names(list(keys))}")

    fks = foreign_keys(cur, TABLE_NAME)
    check(f"`{TABLE_NAME}`: внешних ключей нет осознанно — ни на заголовок (прецедент "
          "V20.1), ни на цель ссылки `Picture` (Q3: слой `CommonPictures` не загружен, а "
          "`StdPicture.*` существует только в платформе)", not fks,
          f"ключи: {names(list(fks))}")

    wanted_indexes = {
        "idx_bots_object_uuid_revision": "(object_uuid, revision_no)",
        "idx_bots_picture_full_name": "picture_full_name",
        "idx_bots_picture_object_uuid": "picture_object_uuid",
    }
    found = indexes_of(cur, TABLE_NAME)
    for index_name, fragment in wanted_indexes.items():
        definition = compact(found.get(index_name, ""))
        check(f"`{TABLE_NAME}`: индекс `{index_name}` жив и ведёт по `{fragment}`",
              bool(definition) and fragment in definition,
              "индекса в схеме нет" if not definition else f"определение: {_brief(definition)}")

    try:
        n = scalar(cur, f"SELECT count(*) FROM {BOT_VIEW}")
        check(f"витрина текущего состояния `{BOT_VIEW}` жива и читается", True)
        info(f"витрина `{BOT_VIEW}`: строк {n}")
    except Exception as exc:  # noqa: BLE001 — отсутствующая витрина называется отказом
        cur.connection.rollback()
        check(f"витрина текущего состояния `{BOT_VIEW}` жива и читается", False, str(exc))

    check(f"`{TABLE_NAME}` состоит в реестре версионируемых (цепь узла V19, Q2)",
          TABLE_NAME in CONFIGURATION_VERSIONED_TABLES,
          f"реестр: {names(sorted(CONFIGURATION_VERSIONED_TABLES))}")
    check(f"имя витрины задаёт реестр, а не DDL: `current_view('{TABLE_NAME}')` отдаёт "
          f"`{BOT_VIEW}`", current_view(TABLE_NAME) == BOT_VIEW, current_view(TABLE_NAME))
    check(f"перечень заголовка `configurations.{HEADER_NAME_COLUMN}` жив (его заполняет "
          "стадия S2 узла V43, стадия V55 её не перезаписывает)",
          bool(q(cur, "SELECT 1 FROM information_schema.columns WHERE table_name = "
                      "'configurations' AND column_name = %s", (HEADER_NAME_COLUMN,))))


# ── контур 2: словари состояний ↔ CHECK'ы схемы ──────────────────────────────────────────────
def compare_vocabulary(cur, column, vocabulary):
    """Словарь модуля и замкнутость схемы равны; расхождение называется множествами."""
    constraint = f"{TABLE_NAME}_{column}_known"
    definition = constraint_def(cur, TABLE_NAME, constraint)
    if not definition:
        check(f"{TABLE_NAME}.{column}: CHECK замкнутости `{constraint}` живой схемы", False,
              "ограничения с таким именем в схеме нет — словарь схемы нечем подтвердить")
        return set()
    schema_values = set(literals_of(definition))
    module_values = set(vocabulary)
    check(f"{TABLE_NAME}.{column}: CHECK живой схемы перечисляет словарь модуля "
          f"({len(module_values)} значений)", schema_values == module_values,
          f"в словаре нет: {names(sorted(schema_values - module_values))}; "
          f"CHECK допускает: {names(sorted(module_values - schema_values))}")
    return schema_values


def check_match_constraints(cur, vocabularies):
    """Ограничения согласованности обязаны существовать и не допускать состояний вне
    словарей: состояние, которого разбор не производит, не имеет права появляться в базе, а
    состояние без опоры на значение колонки описывало бы само себя."""
    known = set()
    for vocabulary in vocabularies.values():
        known |= set(vocabulary)
    names_present = {str(r["conname"]) for r in q(
        cur, "SELECT conname FROM pg_constraint WHERE conrelid = %s::regclass",
        (TABLE_NAME,))}
    missing = [c for c in MATCH_CONSTRAINTS if c not in names_present]
    check(f"ограничений согласованности из DDL узла V55 в схеме нет — {len(missing)} "
          f"(ожидаются {len(MATCH_CONSTRAINTS)})", not missing, names(missing))

    admitted = set()
    for constraint in MATCH_CONSTRAINTS:
        literals = set(literals_of(constraint_def(cur, TABLE_NAME, constraint)))
        # служебные литералы (формы имён, пустая строка класса цели) в словари состояний не
        # входят: сравниваются только те, что совпадают с состояниями колонок
        admitted |= {value for value in literals if value in known}
    check(f"match-CHECK'ы допускают состояния только из словарей модуля "
          f"({len(admitted)} значений)", admitted <= known,
          f"вне словарей: {names(sorted(admitted - known))}")

    # Q1 (вариант A) и мера M7: механизм «неизвестное не теряется» обязан быть живым —
    # колонка виновников и её согласование с состоянием свойств.
    columns = set(table_columns(cur, TABLE_NAME))
    check("`bots.unknown_property_names`: колонка виновников жива (Q1 вариант A, M7)",
          "unknown_property_names" in columns, f"колонок: {len(columns)}")
    check("CHECK `bots_properties_state_matches_unknown` связывает состояние с перечнем "
          "виновников: `all_known` не держит имён, `unknown_value`/`unknown_tag` называют "
          "хотя бы одно",
          "bots_properties_state_matches_unknown" in names_present
          and "unknown_property_names" in constraint_def(
              cur, TABLE_NAME, "bots_properties_state_matches_unknown"))

    # Q7 (вариант A): значения свойств замкнуты НЕ были — незнакомое значение обязано
    # оставаться значением с состоянием, а не отказом записи.
    value_checks = [str(r["conname"]) for r in q(
        cur, "SELECT conname FROM pg_constraint WHERE conrelid = %s::regclass "
             "AND (conname LIKE '%%predefined%%' OR conname LIKE '%%synonym%%' "
             "OR conname LIKE '%%comment%%')", (TABLE_NAME,))]
    check("CHECK'ов на ЗНАЧЕНИЯ свойств вида нет осознанно (Q7 вариант A): ограничения "
          "`predefined`/`synonym`/`comment` по значениям в схеме отсутствуют",
          not value_checks, f"найдено: {names(value_checks)}")


def check_state_vocabulary_checks(cur):
    section("Контур 2 — словари состояний против CHECK'ов схемы")
    vocabularies = {}
    for column in sorted(STATE_VOCABULARIES):
        vocabularies[column] = state_vocabulary(column)
        compare_vocabulary(cur, column, vocabularies[column])

    # Состояния офлайн-разбора (без индекса состава) CHECK'у неизвестны: писатель обязан
    # передавать обе ноги всегда, а «не проверяли» не равно «не разрешилось» (прецедент
    # `index_check.state = not_checked` V53).
    picture_definition = constraint_def(cur, TABLE_NAME, "bots_picture_state_known")
    for state in OFFLINE_ONLY_STATES:
        check(f"состояние `{state}` (офлайн-вход разбора) не входит в CHECK "
              f"`bots_picture_state_known` — в таблицу оно не попадает",
              state not in set(literals_of(picture_definition)),
              f"CHECK допускает: {state}")
    check(f"словарь `picture_state` модуля исчерпывается CHECK'ом ({len(PICTURE_STATES)} "
          "значений) и не содержит офлайн-состояний",
          set(PICTURE_STATES) == set(literals_of(picture_definition))
          and not (set(OFFLINE_ONLY_STATES) & set(PICTURE_STATES)),
          f"словарь: {names(sorted(PICTURE_STATES))}")
    check(f"словари состояний разбора покрывают все колонки состояний таблицы "
          f"({len(STATE_VOCABULARIES)} колонок)",
          set(STATE_VOCABULARIES) <= set(table_columns(cur, TABLE_NAME)),
          f"колонок состояний в схеме: {names(sorted(set(table_columns(cur, TABLE_NAME)) & set(STATE_VOCABULARIES)))}")
    check_match_constraints(cur, vocabularies)


# ── независимая мера круга: обход каталога без знания о состояниях разбора ───────────────────
def circle_measures(dump_dir):
    """Число файлов регистрации, подкаталогов, не-XML, файлов `Ext/Module.bsl` и их байты
    обходом каталога. `module_files` считаются только в каталоге `Ext/`: имя `Module.bsl`
    будущая выгрузка могла бы дать и в чужом подкаталоге, а нога модуля — именно
    `Bots/<Имя>/Ext/Module.bsl` (замер 1.2)."""
    root = Path(dump_dir) / DIR_NAME
    totals = {"files": 0, "subdirs": 0, "non_xml": 0, "module_files": 0, "bytes": 0,
              "module_bytes": 0, "directory_exists": 0}
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
    for module in root.rglob(MODULE_FILE_NAME):
        if module.is_file() and module.parent.name == MODULE_DIR_NAME:
            totals["module_files"] += 1
            totals["module_bytes"] += module.stat().st_size
    return totals


def registration_names(dump_dir):
    """Имена видов по файлам регистрации (без расширения) — независимая мера каталога."""
    root = Path(dump_dir) / DIR_NAME
    if not root.exists():
        return set()
    return {entry.stem for entry in root.iterdir()
            if entry.is_file() and entry.suffix.lower() == ".xml"}


def read_index_aggregates(cur, configuration_id):
    """Записи индекса состава вида и его модуля — отдельным SQL, а не памятью разбора.
    Нога вида — строка без родителя (`Bot.<Имя>`, глубина 0), нога модуля — строка с
    родителем (`Bot.<Имя>.Module`, глубина 1): `object_name` детской записи несёт имя
    объекта, а не `.Module`, поэтому ноги различаются родителем (замер 1.2, тот же приём,
    что в разборе через `kind_index_rows`/`module_index_rows`)."""
    rows = q(cur, f"SELECT name, object_name, object_id, uuid::text AS uuid, depth, "
                  f"parent_name FROM {INDEX_TABLE} WHERE configuration_id = %s "
                  f"AND object_type = %s ORDER BY name", (configuration_id, INDEX_KIND))
    kind_rows = [row for row in rows if not row["parent_name"]]
    child_rows = [row for row in rows if row["parent_name"]]
    prefix = f"{INDEX_KIND}."
    return {
        "kind_rows": len(kind_rows),
        "child_rows": len(child_rows),
        "kind_names": {str(row["object_name"])[len(prefix):]
                       if str(row["object_name"]).startswith(prefix)
                       else str(row["object_name"]) for row in kind_rows},
        "child_names": {module_index_name(str(row["object_name"])) for row in child_rows},
        "kind_uuids": {str(row["object_name"]): (row["uuid"] or "").lower()
                       for row in kind_rows},
        "kind_object_ids": {str(row["object_name"]): str(row["object_id"] or "")
                            for row in kind_rows},
    }


def read_header_name_list(cur, cfg_uuid):
    """Перечень заголовка, заполненный стадией S2: имена элементов или NULL (пустой
    перечень различим от отсутствующего — колонка `text[]`, а не jsonb)."""
    row = one(cur, f"SELECT coalesce(array_length({HEADER_NAME_COLUMN}, 1), 0) AS n, "
                   f"({HEADER_NAME_COLUMN} IS NULL) AS is_null, "
                   f"coalesce({HEADER_NAME_COLUMN}, '{{}}') AS items FROM configurations "
                   "WHERE uuid = %s::uuid", (cfg_uuid,))
    items = [str(item) for item in (row.get("items") or [])]
    return int(row.get("n") or 0), bool(row.get("is_null")), items


def read_bot_rows(cur, cfg_uuid):
    """Строки вида текущей ревизии — через витрину, а не прямым чтением версионируемой
    таблицы."""
    return q(cur, f"SELECT * FROM {BOT_VIEW} WHERE configuration_uuid = %s::uuid "
                   "ORDER BY full_name", (cfg_uuid,))


def set_diff(label, left, right, tag):
    """Две стороны одного множества сравниваются попарно; расхождение называется именами."""
    missing, extra = sorted(right - left), sorted(left - right)
    check(f"{tag}: {label} совпадают во все стороны", not missing and not extra,
          f"не названо: {names(missing)}; лишнее: {names(extra)}")


# ── контур 3: граница круга — файлы, индекс состава, перечень заголовка, строки таблицы ──────
def check_circle(cur, header, dump_dir, index_info, expect, parsed, tag):
    raw = circle_measures(dump_dir)
    keys = ("files", "subdirs", "non_xml", "module_files")
    check(f"{tag}: независимые меры `{DIR_NAME}/` (файлы регистрации, подкаталоги, не-XML, "
          "файлы модулей) совпадают с планом раздела 1.1",
          all(raw[k] == expect[k] for k in keys),
          "; ".join(f"{k}: факт {raw[k]}, план {expect[k]}" for k in keys
                    if raw[k] != expect[k]))
    check(f"{tag}: байты файлов `Ext/{MODULE_FILE_NAME}` — {expect['module_bytes']} "
          "(замер 1.4 цены круга)", raw["module_bytes"] == expect["module_bytes"],
          f"факт: {raw['module_bytes']}")

    agg = read_index_aggregates(cur, int(header["id"]))
    check(f"{tag}: записей вида в индексе состава — {expect['index_rows']}, модуля — "
          f"{expect['index_children']} (замер 1.2: единственный ребёнок вида)",
          agg["kind_rows"] == expect["index_rows"]
          and agg["child_rows"] == expect["index_children"],
          f"факт: вид {agg['kind_rows']}, модуль {agg['child_rows']}")
    check(f"{tag}: агрегатный COUNT индекса ↔ построчный обход разбора",
          agg["kind_rows"] == parsed["index_kind_records"]
          and agg["child_rows"] == parsed["index_child_records"],
          f"агрегат: {agg['kind_rows']}/{agg['child_rows']}, разбор: "
          f"{parsed['index_kind_records']}/{parsed['index_child_records']}")

    header_list, header_is_null, header_items = read_header_name_list(cur, str(header["uuid"]))
    check(f"{tag}: перечень заголовка `configurations.{HEADER_NAME_COLUMN}` называет "
          f"{expect['header_list']} имён при признаке NULL {bool(expect['header_null'])} "
          "(ногу перечня стадия V55 не перезаписывает)",
          header_list == expect["header_list"]
          and header_is_null is bool(expect["header_null"]),
          f"факт: элементов {header_list}, NULL-перечень {header_is_null}")

    bot_rows = read_bot_rows(cur, str(header["uuid"]))
    check(f"{tag}: строк вида от разбора — {expect['db_rows']}",
          len(parsed["rows"]) == expect["db_rows"], f"разбор дал {len(parsed['rows'])}")
    check(f"{tag}: строк вида в базе (витрина) — {expect['db_rows']}",
          len(bot_rows) == expect["db_rows"], f"в базе {len(bot_rows)}")

    file_names = registration_names(dump_dir)
    parsed_names = {str(row["object_name"]) for row in parsed["rows"]}
    db_names = {str(row["object_name"]) for row in bot_rows}
    index_names = set(agg["kind_names"])
    header_names = {str(item) for item in header_items}
    set_diff("файлы регистрации ↔ записи индекса состава", file_names, index_names, tag)
    set_diff("записи индекса ↔ перечень заголовка", index_names, header_names, tag)
    set_diff("файлы регистрации ↔ строки таблицы", file_names, db_names, tag)
    set_diff("разбор ↔ строки таблицы", parsed_names, db_names, tag)

    discrepancies = {key: int((parsed.get("counts_by_circle_discrepancy") or {}).get(key, 0))
                     for key in ("index_only", "file_only", "uuid_mismatch")}
    check(f"{tag}: расхождений ног (index_only / file_only / uuid_mismatch) — ноль",
          not any(discrepancies.values()), f"факт: {discrepancies}")
    check(f"{tag}: повторяющихся имён вида в выгрузке — ноль (замер 1.3)",
          not parsed["duplicate_names"], f"факт: {names(parsed['duplicate_names'])}")

    observed = {str(kind) for kind, _base in (parsed.get("observations") or [])}
    outside_observations = sorted(observed - set(OBSERVATION_KINDS))
    check(f"{tag}: наблюдений вне закрытого перечня `OBSERVATION_KINDS` — ноль (прецедент "
          "V54: ответ обязан отличать «наблюдений нет» от «наблюдений не было ни одного "
          "типа»)", not outside_observations, f"вне перечня: {names(outside_observations)}")
    check(f"{tag}: наблюдение `directory_missing` дано ровно тогда, когда каталога вида нет "
          f"(план: {expect['directory_missing']}, каталог на диске: "
          f"{bool(raw['directory_exists'])}) — Q6, M6",
          ("directory_missing" in observed) is bool(expect["directory_missing"])
          and bool(raw["directory_exists"]) is bool(1 - expect["directory_missing"]),
          f"наблюдения: {names(sorted(observed))}, каталог существует: "
          f"{bool(raw['directory_exists'])}")
    check(f"{tag}: отсутствующий каталог вида не является отказом стадии: success=True, "
          f"files_found={expect['files']}, files_read={expect['db_rows']}",
          parsed["success"] is True and parsed["files_found"] == expect["files"]
          and parsed["files_read"] == expect["db_rows"],
          f"success: {parsed['success']}, found: {parsed['files_found']}, "
          f"read: {parsed['files_read']}, failed: {_brief(parsed['files_failed'])}")
    return bot_rows, agg, raw


# ── контур 4: строка таблицы ↔ разбор тем же модулем, что и загрузка ─────────────────────────
def normalize(value):
    """Одна форма сравнения значения разбора и строки базы. Пустая строка НЕ сводится к
    NULL: `comment=''` и «тега нет» различаются состоянием `properties_state`, а не
    подстановкой (прецедент V53/V54)."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if value is None:
        return None
    return str(value)


def compare_rows(parsed, db_rows, expect, tag):
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
        for field in ROW_FIELDS:
            left, right = normalize(parsed_row.get(field)), normalize(db_row.get(field))
            if field.endswith("uuid"):
                left = str(left or "").lower() or None
                right = str(right or "").lower() or None
            if left != right:
                mismatches.append(f"{name}.{field}: разбор {_brief(left)}, база "
                                  f"{_brief(right)}")
    check(f"{tag}: {len(ROW_FIELDS)} полей каждой строки совпадают с разбором",
          not mismatches, "; ".join(mismatches[:6]))

    synonym_diff = []
    for name in sorted(set(by_name) & set(db_by_name)):
        parsed_syn = by_name[name].get("synonym")
        db_syn = db_by_name[name].get("synonym")
        if parsed_syn != db_syn:
            synonym_diff.append(f"{name}: {_brief(parsed_syn)} ↔ {_brief(db_syn)}")
    check(f"{tag}: многоязычный синоним (`synonym` jsonb) сохранён без правок "
          "(замер 2: `Synonym` есть в 2 файлах из 2)", not synonym_diff,
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
          "`bots_properties_state_matches_unknown`)", not culprit_diff,
          "; ".join(culprit_diff[:4]))

    # Состояния из сводки разбора сравниваются с построчным группированием базы: один и тот
    # же круг, посчитанный двумя способами (прецедент V54).
    for column, vocabulary in sorted(STATE_VOCABULARIES.items()):
        parsed_counts = Counter()
        for row in parsed_rows:
            parsed_counts[str(row.get(f"{column}"))] += 1
        db_counts = Counter()
        for row in db_rows:
            db_counts[str(row[column])] += 1
        check(f"{tag}: состояния колонки `{column}` в разборе и в базе совпадают",
              parsed_counts == db_counts, f"разбор: {dict(parsed_counts)}, база: "
              f"{dict(db_counts)}")
        outside = set(db_counts) - set(vocabulary)
        check(f"{tag}: состояний вне замкнутого словаря `{column}` в базе нет",
              not outside, f"вне словаря: {names(sorted(outside))}")
        if column == "picture_state":
            for state_key, plan_key in ((PICTURE_EXACT, "picture_exact"),
                                        (PICTURE_STD, "picture_std")):
                check(f"{tag}: состояние ссылки `{state_key}` дано {expect[plan_key]} раз(а) "
                      "— замер 2.1 плана",
                      db_counts.get(state_key, 0) == expect[plan_key],
                      f"факт: {db_counts.get(state_key, 0)}")


    counts_by_state = Counter()
    for row in db_rows:
        counts_by_state[str(row["properties_state"])] += 1
    check(f"{tag}: все строки разобраны без неизвестных тегов и значений "
          f"(`all_known` = {expect['props_all_known']}; состояний `unknown_tag`/"
          f"`unknown_value` — ноль)",
          counts_by_state.get(PROPERTIES_ALL_KNOWN, 0) == expect["props_all_known"]
          and not (counts_by_state.get(PROPERTIES_UNKNOWN_TAG, 0)
                   or counts_by_state.get(PROPERTIES_UNKNOWN_VALUE, 0)),
          f"факт: {dict(counts_by_state)}")

    index_states = dict(parsed.get("counts_by_index_check_state") or {})
    outside_index = sorted(set(index_states) - set(INDEX_CHECK_STATES))
    check(f"{tag}: состояний сверки с индексом вне закрытого перечня "
          f"`INDEX_CHECK_STATES` — ноль", not outside_index,
          f"вне перечня: {names(outside_index)}")

    matched = int((parsed.get("counts_by_index_check_state") or {}).get(INDEX_MATCHED, 0))
    check(f"{tag}: файл регистрации подтверждён записью индекса состава — `{INDEX_MATCHED}` "
          f"у {expect['files']} файлов из {expect['files']} (правило V43)",
          matched == expect["files"], f"факт: {dict(parsed.get('counts_by_index_check_state') or {})}")
    return index_states


# ── контур 5: ссылка `Picture` — класс цели различается структурой, а не молчанием ───────────
def check_picture_reference(cur, header, db_rows, agg, expect, tag):
    if not db_rows:
        skip(f"{tag}: контур ссылки `Picture`",
             "строк вида нет — сравнивать не с чем (вид существует ровно в одной выгрузке "
             "корпуса, раздел 1 плана)")
        return
    states = Counter(str(row["picture_state"]) for row in db_rows)
    classes = Counter(str(row["picture_target_class"]) for row in db_rows)
    check(f"{tag}: состояния ссылки — `exact` {expect['picture_exact']}, `std_picture` "
          f"{expect['picture_std']}, прочих состояний ноль (замер 2.1)",
          states.get(PICTURE_EXACT, 0) == expect["picture_exact"]
          and states.get(PICTURE_STD, 0) == expect["picture_std"]
          and sum(states.values()) == expect["picture_exact"] + expect["picture_std"],
          f"факт: {dict(states)}")
    check(f"{tag}: класс цели различён структурой строки: `common_picture` "
          f"{expect['picture_exact']}, `std_picture` {expect['picture_std']}, `other` и "
          "пустой адрес — ноль",
          classes.get(TARGET_COMMON_PICTURE, 0) == expect["picture_exact"]
          and classes.get(TARGET_STD_PICTURE, 0) == expect["picture_std"]
          and not classes.get("other", 0) and not classes.get("", 0),
          f"факт: {dict(classes)}")

    by_name = {str(row["object_name"]): row for row in db_rows}
    wrong = []
    for name, wanted in sorted(PICTURE_ROW_EXPECTATIONS.items()):
        row = by_name.get(name)
        if row is None:
            wrong.append(f"{name}: строки вида нет в базе")
            continue
        for field, value in (("picture_state", wanted["picture_state"]),
                             ("picture_target_class", wanted["picture_target_class"]),
                             ("picture_full_name", wanted["picture_full_name"])):
            if str(row[field]) != str(value):
                wrong.append(f"{name}.{field}: факт {_brief(row[field])}, план {_brief(value)}")
        resolved = bool(row["picture_object_id"]) or bool(row["picture_object_uuid"])
        if resolved is not bool(wanted["index_resolved"]):
            wrong.append(f"{name}: разрешение индексом {resolved}, план "
                         f"{bool(wanted['index_resolved'])}")
    check(f"{tag}: построчный эталон ссылки совпадает с замером 2.1 "
          f"({names(sorted(PICTURE_ROW_EXPECTATIONS))})", not wrong, "; ".join(wrong))

    cfg = str(header["uuid"])
    # `StdPicture.*` индексом состава не разрешается НИКОГДА: стандартное средство платформы
    # не может быть записью выгрузки (раздел 2.1, Q3). Поэтому поля индекса у такой строки
    # обязаны отсутствовать, а не читаться нулём состояния.
    std_bad = scalar(
        cur, f"SELECT count(*) FROM {BOT_VIEW} b WHERE b.configuration_uuid = %s::uuid "
             "AND b.picture_state = 'std_picture' AND (b.picture_object_id IS NOT NULL "
             "OR b.picture_object_uuid IS NOT NULL OR b.picture_full_name NOT LIKE "
             "'StdPicture.%%')", (cfg,))
    check(f"{tag}: строка `std_picture` не держит полей индекса состава и ведёт по адресу "
          f"`{STD_PICTURE_PREFIX}…`", not std_bad, f"нарушений: {std_bad}")

    # Разрешённая ссылка обязана ссылаться на ТУ ЖЕ запись индекса состава своей
    # конфигурации, а не на любой `object_id` корпуса (прецедент Q3 узлов V50/V52/V53:
    # цель не утверждается, но указатель обязан быть настоящим).
    exact_bad = scalar(
        cur, f"SELECT count(*) FROM {BOT_VIEW} b JOIN configurations c "
             "ON c.uuid = b.configuration_uuid JOIN configuration_objects o "
             "ON o.configuration_id = c.id AND o.name = b.picture_full_name "
             "WHERE b.configuration_uuid = %s::uuid AND b.picture_state = 'exact' AND ("
             "b.picture_object_id IS DISTINCT FROM o.object_id "
             "OR b.picture_object_uuid IS DISTINCT FROM o.uuid)", (cfg,))
    check(f"{tag}: `exact` держит `object_id`/`uuid` ровно той записи индекса, на которую "
          f"указывает адрес ({expect['picture_exact']} из {expect['picture_exact']})",
          not exact_bad, f"расхождений: {exact_bad}")

    address_bad = scalar(
        cur, f"SELECT count(*) FROM {BOT_VIEW} b WHERE b.configuration_uuid = %s::uuid "
             "AND b.picture_state <> 'absent' AND (b.picture_ref IS NULL OR "
             "b.picture_ref = '' OR replace(b.picture_ref, ' ', '') <> b.picture_full_name)",
        (cfg,))
    check(f"{tag}: адрес ссылки сохранён как в выгрузке, нормализованный адрес — тот же",
          not address_bad, f"расхождений: {address_bad}")

    # Обратный вопрос карточки: «какие боты ссылаются на эту картинку» идёт по
    # нормализованному адресу цели; он задаётся и к стандартному средству (индекс
    # `idx_bots_picture_full_name` контура 1).
    per_target = q(cur, f"SELECT picture_full_name, count(*) AS n FROM {BOT_VIEW} "
                        "WHERE configuration_uuid = %s::uuid GROUP BY picture_full_name "
                        "ORDER BY picture_full_name", (cfg,))
    check(f"{tag}: обратный вопрос по `picture_full_name` даёт "
          f"{len(PICTURE_ROW_EXPECTATIONS)} цели по одной ссылке",
          len(per_target) == len(PICTURE_ROW_EXPECTATIONS)
          and all(int(row["n"]) == 1 for row in per_target),
          f"факт: {[(row['picture_full_name'], row['n']) for row in per_target]}")

    lt_states = Counter(str(row["picture_load_transparent_state"]) for row in db_rows)
    lt_values = Counter(bool(row["picture_load_transparent"]) for row in db_rows)
    check(f"{tag}: признак загрузки прозрачности — значение с состоянием `set` у всех "
          f"{len(db_rows)} строк (замер 2.1: `LoadTransparent=true` в 2/2 файлов)",
          lt_states.get("set", 0) == len(db_rows) and not lt_states.get("absent", 0)
          and lt_values.get(True, 0) == len(db_rows),
          f"состояния: {dict(lt_states)}, значения: {dict(lt_values)}")

    flags = Counter(bool(row["predefined"]) for row in db_rows)
    check(f"{tag}: оба значения флага `Predefined` даны корпусом (замер 2.3: true 1, "
          "false 1); значение флага не читается свойством объекта для поиска (прецедент O1 "
          "узла V49)",
          flags.get(True, 0) == 1 and flags.get(False, 0) == 1, f"факт: {dict(flags)}")


# ── контур 6: модуль вида — дескрипторы, а тексты принадлежат узлу V47 (M5) ──────────────────
def check_module_descriptors(cur, header, dump_dir, db_rows, agg, raw, expect, tag):
    if not db_rows:
        skip(f"{tag}: контур модуля вида",
             "строк вида нет — сравнивать не с чем; каталога `Ext/` у вида тоже нет")
        return 0

    states = Counter(str(row["module_state"]) for row in db_rows)
    check(f"{tag}: состояние модуля — `file_and_index` у {expect['module_file_and_index']} "
          f"объектов из {expect['module_file_and_index']} (замер 1.1: ног без расхождений)",
          states.get(MODULE_FILE_AND_INDEX, 0) == expect["module_file_and_index"]
          and sum(states.values()) == len(db_rows), f"факт: {dict(states)}")

    bad_path, bad_size = [], []
    for row in db_rows:
        rel = str(row["module_source_path"] or "")
        wanted = f"{DIR_NAME}/{row['object_name']}/{MODULE_DIR_NAME}/{MODULE_FILE_NAME}"
        if rel != wanted:
            bad_path.append(f"{row['object_name']}: {_brief(rel)} ≠ {_brief(wanted)}")
            continue
        on_disk = Path(dump_dir) / rel
        if not on_disk.is_file():
            bad_size.append(f"{row['object_name']}: файла на диске нет ({_brief(rel)})")
        elif on_disk.stat().st_size != int(row["module_source_size"] or -1):
            bad_size.append(f"{row['object_name']}: размер {row['module_source_size']} ≠ "
                            f"{on_disk.stat().st_size} байт файла на диске")
    check(f"{tag}: путь дескриптора — `{DIR_NAME}/<Имя>/{MODULE_DIR_NAME}/"
          f"{MODULE_FILE_NAME}` по имени файла регистрации (раскладка замера 1.2)",
          not bad_path, "; ".join(bad_path[:4]))
    check(f"{tag}: размер дескриптора равен байтам файла на диске — мера снята НЕ разбором "
          f"(всего {raw['module_bytes']} байт, план {expect['module_bytes']})",
          not bad_size and raw["module_bytes"] == expect["module_bytes"],
          "; ".join(bad_size[:4]))

    cfg = str(header["uuid"])
    module_rows = q(cur, f"SELECT object_name, module_type, file_path, code_size FROM "
                         f"{BSL_MODULES_VIEW} WHERE configuration_uuid = %s::uuid AND "
                         "object_type = %s ORDER BY object_name", (cfg, OBJECT_KIND_TAG))
    check(f"{tag}: строк модуля вида в витрине `bsl_modules` — {expect['loaded_modules']} "
          "(их написал узел V47; стадия V55 их не читает и не снимает — M5)",
          len(module_rows) == expect["loaded_modules"], f"факт: {len(module_rows)}")

    loaded_info = read_loaded_module_names(cur, cfg)
    loaded_names = set(loaded_info.get("names") or [])
    flag_names = {f"{OBJECT_KIND_TAG}.{row['object_name']}.{INDEX_CHILD}"
                  for row in db_rows if row["module_loaded"]}
    check(f"{tag}: признак `module_loaded` истинен ровно там, где строку V47 подтверждает "
          f"живая БД ({len(loaded_names)} имён), а не там, где файл есть на диске",
          flag_names == loaded_names and len(flag_names) == expect["loaded_modules"],
          f"флаг: {names(sorted(flag_names))}; БД: {names(sorted(loaded_names))}")
    state_bad = scalar(
        cur, f"SELECT count(*) FROM {BOT_VIEW} b WHERE b.configuration_uuid = %s::uuid "
             "AND b.module_loaded AND b.module_state <> 'file_and_index'", (cfg,))
    check(f"{tag}: `module_loaded` не бывает истинным без подтверждения индексом состава "
          "(CHECK `bots_module_loaded_matches_state`)", not state_bad,
          f"нарушений: {state_bad}")

    child_expected = {module_index_name(str(row["object_name"])) for row in db_rows}
    check(f"{tag}: запись индекса `{INDEX_KIND}.<Имя>.{INDEX_CHILD}` подтверждена у каждой "
          f"строки вида ({len(child_expected)} из {len(child_expected)})",
          child_expected <= set(agg["child_names"])
          and len(agg["child_names"]) == expect["index_children"],
          f"индекс: {names(sorted(agg['child_names']))}; строки: "
          f"{names(sorted(child_expected))}")
    check("круг записи и круг снятия стадии V55 НЕ включают `bsl_modules` — тексты модулей "
          "вида принадлежат узлу V47 (M5, Q4 вариант A)",
          "bsl_modules" not in BOTS_TABLES and "bsl_modules" not in BOTS_REMOVE_ORDER,
          f"круг записи: {BOTS_TABLES}; снятие: {BOTS_REMOVE_ORDER}")
    check(f"{tag}: чужих слотов модуля вида (кроме `{INDEX_CHILD}`) корпус не даёт (замер "
          "2.2)",
          all(str(row["module_type"]) == INDEX_CHILD for row in module_rows),
          f"факт: {names(sorted({str(row['module_type']) for row in module_rows}))}")
    return len(module_rows)



# ── контур 7: витрины, сироты и чужие круги ──────────────────────────────────────────────────
def check_revisions_and_views(cur):
    section("Контур 7 — витрины, сироты и чужие круги")
    current_direct = scalar(
        cur, f"SELECT count(*) FROM {TABLE_NAME} b WHERE NOT exists("
             f"SELECT 1 FROM {TABLE_NAME} n WHERE n.configuration_uuid = b.configuration_uuid "
             "AND n.object_name = b.object_name AND n.revision_no > b.revision_no)")
    in_view = scalar(cur, f"SELECT count(*) FROM {BOT_VIEW}")
    check(f"витрина `{BOT_VIEW}` отдаёт ровно строки максимальной ревизии "
          f"({current_direct} строк)", current_direct == in_view,
          f"вне витрины: {current_direct}, в витрине: {in_view}")
    outside = scalar(cur, f"SELECT count(*) FROM {TABLE_NAME} b WHERE NOT exists("
                          f"SELECT 1 FROM {BOT_VIEW} v WHERE v.id = b.id)")
    check("строк таблицы вне витрины текущего состояния — ноль", not outside,
          f"вне витрины: {outside}")

    header_orphans = scalar(
        cur, f"SELECT count(*) FROM {TABLE_NAME} b WHERE NOT exists("
             "SELECT 1 FROM configurations c WHERE c.uuid = b.configuration_uuid)")
    check("строк вида без заголовка конфигурации — ноль (внешнего ключа нет осознанно, "
          "поэтому сироту считает проверка, а не схема — прецедент V20.1)",
          not header_orphans, f"сирот: {header_orphans}")

    index_orphans = scalar(
        cur, f"SELECT count(*) FROM {TABLE_NAME} b WHERE NOT exists("
             f"SELECT 1 FROM configurations c JOIN {INDEX_TABLE} o ON o.configuration_id = c.id "
             f"WHERE c.uuid = b.configuration_uuid AND o.object_type = %s "
             "AND o.parent_name IS NULL AND o.uuid = b.object_uuid)", (INDEX_KIND,))
    check("строка вида обязана соответствовать записи индекса состава той же конфигурации "
          "(подтверждение по живой БД, правило V43) — расхождений ноль",
          not index_orphans, f"без записи индекса: {index_orphans}")

    # Чужие круги: детей у вида нет ни в одной выгрузке (замер 1.1), поэтому ни одна строка
    # чужой таблицы не может ссылаться на uuid вида. Мера идёт по живой схеме: таблица без
    # колонки `parent_uuid` называется отдельно, а не пропускается молча.
    for table in CHILD_BEARING_TABLES:
        if "parent_uuid" not in table_columns(cur, table):
            check(f"чужой круг `{table}`: колонки `parent_uuid` в схеме нет — нулем меру "
                  "назвать нельзя", False, "колонки нет")
            continue
        rows = scalar(cur, f"SELECT count(*) FROM {table} t WHERE t.parent_uuid IN ("
                           f"SELECT object_uuid FROM {TABLE_NAME})")
        check(f"строк вида в чужом круге `{table}` — ноль (детей у вида нет: ни файлов, ни "
              "строк индекса — замер 1.1)", not rows, f"найдено: {rows}")

    deep = scalar(cur, f"SELECT count(*) FROM {TABLE_NAME} WHERE revision_no > 1")
    info(f"строк не первой ревизии в `{TABLE_NAME}`: {deep} (цепь узла V19 жива; "
         "перезагрузки со второй ревизией корпус не давал)")


def check_child_directories(dump_dir, tag):
    """Независимая мера раскладки: под каталогом вида нет каталогов детей общей раскладки
    (`Forms/`, `Templates/`, `Commands/`) и ресурсов справки — то, из-за чего формулировка
    группы A модели правится шагом П7 (тот же приём, что `CHILD_DIRECTORIES` разбора)."""
    root = Path(dump_dir) / DIR_NAME
    if not root.exists():
        return
    found = []
    for entry in root.rglob("*"):
        if not entry.is_dir():
            continue
        if entry.name.lower() in {"forms", "templates", "commands", "help"}:
            found.append(_brief(entry.relative_to(root)))
    check(f"{tag}: каталогов детей общей раскладки (`Forms/`, `Templates/`, `Commands/`, "
          "`Ext/Help/`) под `{DIR_NAME}/` нет ни одного (замер 1.1)", not found,
          f"найдено: {names(found)}")


# ── контур 8: контракт стадии, круга снятия и сохранённых видов ───────────────────────────────
def check_contract():
    section("Контур 8 — контракт стадии и круга снятия")
    ids = [stage for stage, _title in STAGES]
    check(f"стадия `{STAGE_BOTS}` стоит сразу после `{STAGE_SCHEDULED_JOBS}` (позиции "
          "2.9 → 2.10 нормативного списка, а не порядок литер)",
          ids.index(STAGE_BOTS) == ids.index(STAGE_SCHEDULED_JOBS) + 1,
          f"порядок: {ids}")
    check(f"`{STAGE_OBJECT_MODULES}` остаётся последней стадией (вторая транзакция текстов), "
          f"а `{STAGE_BOTS}` стоит перед ней",
          ids[-1] == STAGE_OBJECT_MODULES and ids.index(STAGE_BOTS) == len(ids) - 2,
          f"порядок: {ids}")
    check(f"`stages_after('{STAGE_SCHEDULED_JOBS}')` называет продолжением `{STAGE_BOTS}`",
          stages_after(STAGE_SCHEDULED_JOBS)[:1] == [STAGE_BOTS],
          str(stages_after(STAGE_SCHEDULED_JOBS)))
    check(f"`stages_after('{STAGE_BOTS}')` называет продолжением `{STAGE_OBJECT_MODULES}`",
          stages_after(STAGE_BOTS)[:1] == [STAGE_OBJECT_MODULES],
          str(stages_after(STAGE_BOTS)))
    check(f"у стадии `{STAGE_BOTS}` есть зеркало продолжения (`STAGE_FULL_RELOAD_ONLY` = "
          "False — стадия дозакрывается отдельным входом)",
          STAGE_FULL_RELOAD_ONLY.get(STAGE_BOTS) is False,
          str(STAGE_FULL_RELOAD_ONLY.get(STAGE_BOTS)))
    title = stage_title(STAGE_BOTS)
    hint = stage_resume_hint(STAGE_BOTS)
    check("заголовок стадии называет позицию 2.10 и каталог вида",
          "2.10" in title and DIR_NAME in title, _brief(title))
    check("подсказка продолжения называет отдельный вход `load_bots_tool` и полную "
          "перезагрузку", "load_bots_tool" in hint and "load_1c_catalog_tool" in hint,
          _brief(hint))
    check(f"круг записи стадии — одна таблица вида `{TABLE_NAME}` (M3)",
          tuple(BOTS_TABLES) == (TABLE_NAME,), str(BOTS_TABLES))
    check("круг снятия совпадает с кругом записи: каскадных внешних ключей в таблицу нет, "
          "поэтому снятие держится явным `DELETE` по границе конфигурации",
          tuple(BOTS_REMOVE_ORDER) == (TABLE_NAME,), str(BOTS_REMOVE_ORDER))
    check(f"`{TABLE_NAME}` входит в `FOREIGN_STAGE_TABLES` — иначе стадия S4 снимала бы "
          "чужие строки вида (дефект, закрытый константой `BOTS_TABLES` узла V55)",
          TABLE_NAME in FOREIGN_STAGE_TABLES, f"перечень: {names(FOREIGN_STAGE_TABLES)}")
    entry = STORED_META_KINDS.get(BOTS_META_TAG) or {}
    check(f"вид `{BOTS_META_TAG}` назван сохранённым в реестре `STORED_META_KINDS` кругом "
          f"{tuple(BOTS_TABLES)} и позицией 2.10 — тем же словарём, которым пользуется "
          "карточка загрузки (дефект, вскрытый `_v54_p5_stage_probe.py`)",
          bool(entry) and tuple(entry.get("tables") or ()) == tuple(BOTS_TABLES)
          and str(entry.get("position")) == "2.10",
          f"запись реестра: {_brief(entry)}")
    check(f"словарь вида один: метка `{BOTS_META_TAG}` и каталог `{BOTS_DIR}` контракта "
          "совпадают со словарём разбора",
          BOTS_META_TAG == OBJECT_KIND_TAG == INDEX_KIND and BOTS_DIR == DIR_NAME,
          f"контракт: {BOTS_META_TAG}/{BOTS_DIR}, разбор: {OBJECT_KIND_TAG}/{DIR_NAME}")


# ── контур 9: корпус и чужие таблицы ─────────────────────────────────────────────────────────
# Пары «мера прогона ↔ ключ эталона плана»: суммы по четырём выгрузкам сравниваются с
# разделами 1.1, 1.2, 1.4, 2 плана, а не с числом, выведенным из прогона.
CORPUS_KEYS = (
    ("rows", "rows"), ("index_rows", "index_rows"), ("index_children", "index_children"),
    ("header_names", "header_names"), ("header_null", "header_null"),
    ("files", "files"), ("module_files", "module_files"),
    ("missing_directories", "missing_directories"),
    ("directory_missing", "directory_missing"),
    (PICTURE_EXACT, "picture_exact"), (PICTURE_STD, "picture_std"),
    ("picture_other_states", "picture_other_states"),
    (MODULE_FILE_AND_INDEX, "module_file_and_index"), ("module_loaded", "module_loaded"),
    (PROPERTIES_ALL_KNOWN, "props_all_known"), ("unknown_states", "unknown_states"),
    ("module_bytes", "module_bytes"), ("bsl_module_rows", "bsl_module_rows"),
    (INDEX_MATCHED, "index_matched"), ("circle_discrepancies", "circle_discrepancies"),
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
    if before.get("bsl_modules") is not None and after.get("bsl_modules") is not None:
        check("строк `bsl_modules` в прогоне не снято ни одной — узел V55 не трогает круг "
              "V47 (M5)", before["bsl_modules"] == after["bsl_modules"],
              f"до: {before['bsl_modules']}, после: {after['bsl_modules']}")


def accumulate_corpus(accum, db_rows, parsed, raw, header_list, header_is_null,
                      bsl_module_rows):
    accum["rows"] += len(db_rows)
    accum["index_rows"] += int(parsed.get("index_kind_records") or 0)
    accum["index_children"] += int(parsed.get("index_child_records") or 0)
    accum["header_names"] += int(header_list)
    accum["header_null"] += 1 if header_is_null else 0
    accum["files"] += int(raw.get("files") or 0)
    accum["module_files"] += int(raw.get("module_files") or 0)
    accum["module_bytes"] += int(raw.get("module_bytes") or 0)
    accum["missing_directories"] += 0 if raw.get("directory_exists") else 1
    for kind, _base in (parsed.get("observations") or []):
        accum[f"{kind}"] += 1
    discrepancies = parsed.get("counts_by_circle_discrepancy") or {}
    accum["circle_discrepancies"] += sum(int(value or 0) for value in discrepancies.values())
    index_states = parsed.get("counts_by_index_check_state") or {}
    accum[INDEX_MATCHED] += int(index_states.get(INDEX_MATCHED, 0) or 0)
    accum["bsl_module_rows"] += int(bsl_module_rows)
    for row in db_rows:
        state = str(row["picture_state"])
        accum[state] += 1
        if state not in (PICTURE_EXACT, PICTURE_STD):
            accum["picture_other_states"] += 1
        accum[str(row["module_state"])] += 1
        if row["module_loaded"]:
            accum["module_loaded"] += 1
        properties = str(row["properties_state"])
        accum[properties] += 1
        if properties in (PROPERTIES_UNKNOWN_TAG, PROPERTIES_UNKNOWN_VALUE):
            accum["unknown_states"] += 1


def check_corpus(accum, all_loaded):
    section("Контур 9 — суммы по четырём выгрузкам")
    check("все четыре выгрузки прогнаны (MinCfg, KomMag, BGU2, BP3)", all_loaded,
          "часть выгрузок не прогнана — сравнивать суммы не с чем")
    for measured, plan_key in CORPUS_KEYS:
        plan = CORPUS_EXPECTATIONS[plan_key]
        check(f"корпус: `{measured}` — {plan} (план V55, разделы 1.1–1.4 и 2)",
              accum.get(measured, 0) == plan, f"факт: {accum.get(measured, 0)}")
    check(f"корпус: нули витрин по трём выгрузкам без вида — {CORPUS_EXPECTATIONS['missing_directories']} "
          "выгрузок без каталога и столько же наблюдений",
          accum.get("missing_directories", 0) == CORPUS_EXPECTATIONS["missing_directories"]
          and accum.get("directory_missing", 0) == CORPUS_EXPECTATIONS["directory_missing"],
          f"без каталога: {accum.get('missing_directories', 0)}, наблюдений: "
          f"{accum.get('directory_missing', 0)}")


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
        loaded_info = read_loaded_module_names(cur, str(header["uuid"]))
        if not loaded_info.get("available"):
            info(f"{tag}: признак строк V47 недоступен — {loaded_info.get('reason')}; "
                 "`module_loaded` остаётся False без права утверждать, что строк нет")

        parsed = collect_bots(dump_dir, index_rows=index_info["rows"],
                              loaded_module_names=loaded_info["names"])
        check(f"{tag}: разбор круга завершён без отказа ({expect['files']} файлов)",
              parsed["success"] is True and parsed["files_found"] == expect["files"]
              and parsed["files_read"] == expect["db_rows"],
              f"success: {parsed['success']}, found: {parsed['files_found']}, "
              f"read: {parsed['files_read']}, failed: {_brief(parsed['files_failed'])}")

        bot_rows, agg, raw = check_circle(cur, header, dump_dir, index_info, expect, parsed,
                                          tag)
        compare_rows(parsed, bot_rows, expect, tag)
        check_picture_reference(cur, header, bot_rows, agg, expect, tag)
        bsl_module_rows = check_module_descriptors(cur, header, dump_dir, bot_rows, agg, raw,
                                                   expect, tag)
        check_child_directories(dump_dir, tag)

        header_list, header_is_null, _items = read_header_name_list(cur, str(header["uuid"]))
        accumulate_corpus(accum, bot_rows, parsed, raw, header_list, header_is_null,
                          bsl_module_rows)
        loaded.add(tag)

    check_schema(cur)
    check_state_vocabulary_checks(cur)
    check_revisions_and_views(cur)
    check_contract()
    if scope == DEFAULT_SCOPE:
        check_corpus(accum, loaded == set(PLAN_EXPECTATIONS))
    else:
        skip("Контур 9 — суммы по четырём выгрузкам",
             f"охват `{scope}`: остальные выгрузки не прогнаны, сравнивать суммы не с чем "
             "(у трёх из четырёх вида нет вовсе — его нули входят в эталон)")
    check_non_interference(before, foreign_state(cur))


def main(argv):
    scope = str(argv[1]) if len(argv) > 1 else DEFAULT_SCOPE
    print(f"=== постоянная проверка узла V55 (боты, позиция 2.10) — охват {scope} ===")
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













