#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Узел V57 (параметры функциональных опций, позиция 2.12), шаг П4: писатели и версионность.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python _v57_p4_writer_probe.py [MinCfg|KomMag|BGU2|BP3]
Код возврата 0 — расхождений нет. Прогоны, меняющие состояние БД, не параллелятся (правило
слоя): проба пишет круг внутри одной транзакции и откатывает её, а базовое состояние таблиц
читается ДО записи и сверяется новым соединением после отката.

Что проверяется и почему именно так:

1. Реестры и версионность. Писатель обязан быть в `CONFIGURATION_OBJECT_WRITERS` (реестр
   выбирает класс по таблице, и его отсутствие означало бы выбор по имени), строка вида — в
   `CONFIGURATION_VERSIONED_TABLES` (свою цепь ревизий ведёт `functional_option_parameters`),
   строки применения — в `CONFIGURATION_UNVERSIONED_TABLES` (Q2, вариант A: своей цепи нет,
   ключ начинается с `functional_option_parameter_id`). Объединение двух кругов обязано ровно
   равняться ключам реестра: лишняя таблица в списке версионности означала бы, что чью-то
   версионность сняли молча.
2. Круг стадии. `FOREIGN_STAGE_TABLES` обязан содержать обе таблицы круга, `CHILD_TABLES` —
   не содержать ни одной: без этого стадия S4 снимала и анализировала бы чужие строки (тот же
   дефект, что закрывали записи V48…V56; `_v46_p4_writer_probe.py` падает на `KeyError` по
   этой же причине). Порядок снятия начинается с применения (M7): каскад
   `functional_option_parameter_targets_parameter_fkey` снял бы строки молча, и число в ответе
   было бы неправдой.
3. Спецификации писателей против живой схемы — в обе стороны. NOT NULL-колонка без DEFAULT,
   которой нет в спецификации, дала бы отказ вставки с текстом про NULL, и виноватой выглядела
   бы выгрузка.
4. Словари состояний разбора против CHECK живой схемы — сравнение множеств значений по имени
   колонки. Состояние в CHECK, которого разбор не отдаёт никогда, — мёртвая ветка; состояние в
   словаре, которого нет в CHECK, — отказ загрузки круга.
5. Контракт разбора против спецификации писателя (обе стороны): ключ разбора, которого нет у
   писателя, — потерянный факт; колонка писателя, о которой разбор молчит, — выдуманное
   значение.
6. Живая запись круга: разбор → писатель → таблица → витрина. Числа сверяются с базовой
   линией плана (разделы 1.1 и 2.1: MinCfg 2 файла и 2 цели, KomMag — каталога вида нет,
   BGU2 5 и 6, BP3 7 и 26; итог по корпусу 14 и 34), с содержимым таблиц и с витринами
   `v_current_functional_option_parameters` / `v_current_functional_option_parameter_targets`.
   Связи круга читаются таблицами, а не ответом писателя: `use_state`/`targets_count` строки
   вида обязаны совпадать с числом её строк применения, указатель параметра в строке
   применения — с родительской строкой.
7. Круговая проверка содержимого: каждая колонка спецификации сравнивается с контрактом
   разбора, включая подмены загрузчика (`configuration_uuid`,
   `functional_option_parameter_id`).
8. Что отклоняет схема и как называет: отказ читается именем ограничения (приём V49/V50/V52),
   а не текстом ошибки. Отдельный случай — строка применения с состоянием `empty_value`:
   адрес цели, вид цели и форма адреса держатся ПУСТЫМИ СТРОКАМИ при NOT NULL на этих
   колонках, поэтому писатель обязан нести их как `text_empty_kept`. Та же строка, записанная
   через писателя, принимается схемой — это и есть проверка нового вида колонки.
9. Цепь ревизий: вторая запись круга той же выгрузки даёт ревизию 2, витрина отдаёт только
   её, строки применения старой ревизии из витрины исчезают, а снятое равняется записанному
   (мера идемпотентности M4 на уровне писателей).

Границы пробы. Формат ответа стадии (`format_*_lines`), ключи сводки и стадия конвейера —
шаг П5 того же узла, здесь они не проверяются; в `STAGES` стадии ещё нет, и это называется
заметкой, а не провалом. Тексты модулей вида узлу не нужны — их у вида нет (замер 1.2).
Нулевой круг KomMag (каталога вида нет ни файлом, ни строкой индекса) проверяется как пустой
ответ, а не как отказ (Q9, вариант A).
"""

import re
import sys
import uuid as uuid_module
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import psycopg2  # noqa: E402

import configuration_functional_options_parameters as FOP  # noqa: E402
from configuration_functional_options_loader import read_index_records  # noqa: E402
from configuration_load_contract import (  # noqa: E402
    CHILD_TABLES as S4_CHILD_TABLES,
    FOREIGN_STAGE_TABLES,
    FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER,
    FUNCTIONAL_OPTION_PARAMETERS_TABLES,
    STAGES as CONTRACT_STAGES,
)
from configuration_root_module_loader import configuration_uuid_from_layout  # noqa: E402
from current_revision import (  # noqa: E402
    CHANGED_BY_EDIT, CHANGED_BY_LOAD, CHANGED_BY_RESTORE,
    CONFIGURATION_VERSIONED_TABLES, FIRST_REVISION, REVISION_COLUMNS, current_view,
    stamp_revision_rows,
)
from external_db import connect  # noqa: E402
from external_table_writer import (  # noqa: E402
    CONFIGURATION_OBJECT_WRITERS, CONFIGURATION_UNVERSIONED_TABLES,
    FunctionalOptionParameterTargetRowWriter, FunctionalOptionsParametersRowWriter,
)

TABLE = FOP.TABLE_NAME
TARGETS_TABLE = FOP.TARGETS_TABLE_NAME
TABLES = (TABLE, TARGETS_TABLE)
# Круг узла по версионности: свою цепь ревизий ведёт строка параметра, у строк применения
# своей цепи нет (Q2, вариант A) — ключ начинается с `functional_option_parameter_id`.
NODE_VERSIONED = (TABLE,)
NODE_UNVERSIONED = (TARGETS_TABLE,)
# Полный круг таблиц без своей цепи, каким его задают узлы V49, V50, V52, V53, V54, V56.
# Список общий для всех писателей, поэтому сравнение прогона идёт с ним целиком: лишняя
# таблица в списке означала бы, что чью-то версионность сняли молча.
EXPECTED_UNVERSIONED = (
    "role_rights", "common_attribute_targets", "filter_criterion_content",
    "event_subscription_sources", "scheduled_job_schedules", "functional_option_content",
    TARGETS_TABLE,
)
VIEW = current_view(TABLE)
# Имя витрины строк применения названо явно, а не спросом у `current_view`: своей цепи у
# таблицы нет, и точка доступа отвечает отказом (прецедент `CONTENT_VIEW` узла V52,
# `TARGETS_VIEW` узла V50). Текущность читается связкой по `functional_option_parameter_id`.
TARGETS_VIEW = "v_current_" + TARGETS_TABLE

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
ONLY = tuple(arg for arg in sys.argv[1:] if arg in DUMPS) or DUMPS

# Базовая линия круга — числа плана (docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PARAMETERS_PLAN.md,
# разделы 1.1 и 2.1): 2/0/5/7 файлов регистрации и 2/0/6/26 целей применения, итог по корпусу
# 14 и 34. Проба сверяет с ними то, что отдал разбор, и то, что легло в таблицы и в витрины:
# расхождение видно по имени таблицы. KomMag даёт пустой круг с наблюдением
# `directory_missing` (Q9, вариант A).
BASELINE_ROWS = {
    "MinCfg": {TABLE: 2, TARGETS_TABLE: 2},
    "KomMag": {TABLE: 0, TARGETS_TABLE: 0},
    "BGU2": {TABLE: 5, TARGETS_TABLE: 6},
    "BP3": {TABLE: 7, TARGETS_TABLE: 26},
}
CORPUS_TOTALS = {TABLE: 14, TARGETS_TABLE: 34}

# Колонки, которых в контракте разбора нет по замыслу: их подставляет вызывающий слой
# (прецедент `LOADER_SUPPLIED` узла V52). `functional_option_parameter_id` — числовой id
# конкретной ревизии строки вида, его даёт `insert_ids`; `parameter_full_name` и
# `parameter_object_uuid` остаются колонками применения намеренно (указатель читается и
# тогда, когда строка вида снята перезагрузкой).
LOADER_SUPPLIED = {
    TABLE: set(["configuration_uuid"]),
    TARGETS_TABLE: set(["configuration_uuid", "functional_option_parameter_id"]),
}

# Связь разбора остаётся колонкой ОСОЗНАННО: `parameter_full_name` и
# `parameter_object_uuid` — указатель на параметр в форме индекса состава, он читается и
# тогда, когда строка вида снята (прецедент `criterion_full_name` узла V52,
# `attribute_full_name` V50).
LINK_COLUMNS_OF = {TARGETS_TABLE: (FOP.PARAMETER_LINK_KEY, FOP.PARAMETER_UUID_KEY)}

# Домены состояний, принадлежащие ЦЕПИ СОСТОЯНИЯ, а не виду: их словарь задаёт точка
# доступа `src/current_revision.py`, и сверять его со словарём разбора — значит искать не
# там. Проверка всё равно выполняется: схема обязана разрешать ровно те события, которые
# умеет называть точка доступа.
REVISION_STATE_VALUES = (CHANGED_BY_LOAD, CHANGED_BY_EDIT, CHANGED_BY_RESTORE)

# Две формы домена состояний в CHECK. `col = ANY (ARRAY[...])` — форма миграций V46–V51;
# `col IN (...)` — форма, которой написан DDL узлов V52…V57, и внутри неё домены
# `target_address_form` и `target_resolve_state` лежат в составе парных ограничений, а не
# отдельным предикатом. Третья форма — ветвы парного ограничения, записанные равенством
# (`target_resolve_state = 'exact' AND ...`): у колонки `target_resolve_state` узла V57
# отдельного перечня значений в CHECK нет вовсе, словарь образует объединение её ветвей.
# Равенство читается именно `=`, а не `<>`: отрицание называет исключение, а не значение.
DOMAIN_RES = (
    re.compile(r"([a-z_][a-z0-9_]*)\s*=\s*ANY\s*\(\s*ARRAY\[(.*?)\]\s*\)", re.S),
    re.compile(r"([a-z_][a-z0-9_]*)\s+IN\s*\(([^)]*)\)", re.S),
    re.compile(r"(?<![<>!])\b([a-z_][a-z0-9_]*)\s*=\s*('[^']*')"),
)
# Замкнутый словарь с пустым значением: CHECK
# `functional_option_parameter_targets_address_form_known` перечисляет формы через IN, и
# пустая форма записана как `''` — пустая строка является значением состояния, а не
# отсутствием значения (M5, вариант C отклонён Q1).
VALUE_RE = re.compile(r"'((?:[^']|'')*)'(?:::[A-Za-z_ ]+)?")

PASSED = 0
FAILED = 0
NOTES: List[str] = []


def check(name, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("  [OK]   " + name + (((" — " + str(detail)) if detail else "")))
    else:
        FAILED += 1
        print("  [FAIL] " + name + (((" — " + str(detail)) if detail else "")))


def note(text):
    NOTES.append(text)
    print("  [NOTE] " + text)


def one(cur, sql, params=None):
    cur.execute(sql, params or ())
    row = cur.fetchone()
    return row[0] if row else None


def fetch_dicts(cur, sql, params=None):
    cur.execute(sql, params or ())
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def probe_uuid(tag):
    """Устойчивый uuid пробной строки (один и тот же на повторных прогонах)."""
    return str(uuid_module.uuid5(uuid_module.UUID(int=0), "v57-p4-" + tag))



# ─── реестры писателей, версионность и круг стадии ─────────────────────────────
def check_registries():
    print("\n=== реестры писателей и версионность (шаг П4) ===")
    for table in TABLES:
        check("%s: писатель таблицы зарегистрирован в `CONFIGURATION_OBJECT_WRITERS`" % table,
              table in CONFIGURATION_OBJECT_WRITERS,
              "класс: " + (CONFIGURATION_OBJECT_WRITERS[table].__name__
                           if table in CONFIGURATION_OBJECT_WRITERS else "нет"))
    check("строку вида пишет `FunctionalOptionsParametersRowWriter` (второго писателя нет)",
          CONFIGURATION_OBJECT_WRITERS.get(TABLE) is FunctionalOptionsParametersRowWriter)
    check("строки применения пишет `FunctionalOptionParameterTargetRowWriter`",
          CONFIGURATION_OBJECT_WRITERS.get(TARGETS_TABLE)
          is FunctionalOptionParameterTargetRowWriter)
    check("%s: таблица строки вида входит в круг версионности (своя цепь ревизий, узел V19)"
          % TABLE, TABLE in CONFIGURATION_VERSIONED_TABLES)
    check("%s: таблицы строк применения в круге версионности нет (Q2, вариант A — ключ "
          "начинается с `functional_option_parameter_id`)" % TARGETS_TABLE,
          TARGETS_TABLE not in CONFIGURATION_VERSIONED_TABLES)
    check("%s: строки применения названы в `CONFIGURATION_UNVERSIONED_TABLES` — исключение "
          "названо, а не обойено" % TARGETS_TABLE,
          TARGETS_TABLE in CONFIGURATION_UNVERSIONED_TABLES)
    check("исключение версионности совпадает с перечнем узлов V49…V57 целиком (лишняя или "
          "снятая таблица видна по имени)",
          set(CONFIGURATION_UNVERSIONED_TABLES) == set(EXPECTED_UNVERSIONED),
          "в реестре слоя: " + ", ".join(sorted(CONFIGURATION_UNVERSIONED_TABLES))
          + "; ожидалось: " + ", ".join(sorted(EXPECTED_UNVERSIONED)))
    covered = set(CONFIGURATION_VERSIONED_TABLES) | set(CONFIGURATION_UNVERSIONED_TABLES)
    check("объединение круга версионности и исключения ровно равно ключам реестра писателей",
          covered == set(CONFIGURATION_OBJECT_WRITERS),
          "лишние: " + (", ".join(sorted(covered - set(CONFIGURATION_OBJECT_WRITERS)))
                        or "нет")
          + "; без писателя: "
          + (", ".join(sorted(set(CONFIGURATION_OBJECT_WRITERS) - covered)) or "нет"))
    # Имена двух таблиц узла не являются началом друг друга: круг и индекс состава держатся
    # точными именами (раздел 1.2 плана — тот же риск, что `FunctionalOption` /
    # `FunctionalOptionsParameter`).
    check("имена двух таблиц круга не являются началом друг друга (точная адресация)",
          not TABLE.startswith(TARGETS_TABLE) and not TARGETS_TABLE.startswith(TABLE),
          "%s / %s" % (TABLE, TARGETS_TABLE))
    check("своей цепью ревизий обеспечена только строка вида (граница Q2 читается и по "
          "спецификации писателя)",
          FunctionalOptionsParametersRowWriter.versioned()
          and not FunctionalOptionParameterTargetRowWriter.versioned())
    check("витрина текущего состояния строки вида называется точкой доступа",
          VIEW == "v_current_" + TABLE, VIEW)
    try:
        view_of_targets = current_view(TARGETS_TABLE)
        check("у таблицы применения витрины своей цепи нет — точка доступа обязана ответить "
              "отказом", False, "вернула " + str(view_of_targets))
    except Exception as exc:  # noqa: BLE001
        check("у таблицы применения витрины своей цепи нет — точка доступа отвечает отказом "
              "(Q2, вариант A)", True, type(exc).__name__)


def check_stage_circle():
    print("\n=== круг стадии: снятие, исключение из стадии S4, порядок круга ───")
    check("круг стадии назван контрактом — обе таблицы круга (Q1, вариант A)",
          FUNCTIONAL_OPTION_PARAMETERS_TABLES == TABLES,
          ", ".join(FUNCTIONAL_OPTION_PARAMETERS_TABLES))
    check("имена таблиц круга приходят из разбора — второго перечня в контракте нет",
          FUNCTIONAL_OPTION_PARAMETERS_TABLES == (FOP.TABLE_NAME, FOP.TARGETS_TABLE_NAME))
    check("круг снятия начинается со строк применения и заканчивается строками вида (M7)",
          FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER == (TARGETS_TABLE, TABLE),
          ", ".join(FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER))
    check("обе таблицы круга исключены из круга стадии S4 (`CHILD_TABLES`)",
          not (set(FUNCTIONAL_OPTION_PARAMETERS_TABLES) & set(S4_CHILD_TABLES)),
          ", ".join(sorted(set(S4_CHILD_TABLES)
                           & set(FUNCTIONAL_OPTION_PARAMETERS_TABLES)))
          or "пересечения нет")
    check("круг узла входит в `FOREIGN_STAGE_TABLES`",
          set(FUNCTIONAL_OPTION_PARAMETERS_TABLES) <= set(FOREIGN_STAGE_TABLES))
    check("чужие круги не пересекаются с кругом узла (одну таблицу не пишут две стадии)",
          not ((set(FOREIGN_STAGE_TABLES) - set(FUNCTIONAL_OPTION_PARAMETERS_TABLES))
               & set(FUNCTIONAL_OPTION_PARAMETERS_TABLES)))
    # Стадия ещё не внесена в `STAGES` — это шаг П5 того же узла. Проверяемое свойство —
    # идентификатор не занимает чужую позицию перечня (формулировка «стадии нет в `STAGES`»
    # после П5 читалась бы вечным провалом; замечено узлом V52 при регрессе).
    stage_ids = [str(stage_id) for stage_id, _ in CONTRACT_STAGES]
    check("в перечне стадий нет идентификатора, который относился бы к этому виду",
          not [stage_id for stage_id in stage_ids
               if "functional_option_parameter" in stage_id.lower()],
          ", ".join(stage_ids) if stage_ids else "перечня нет")
    note("стадия S4l (`s4l_functional_options_parameters`) в `STAGES` ЕЩЁ НЕ внесена — "
         "внесение является шагом П5 того же узла (позиция 2.12 идёт сразу за S4k)")



# ─── спецификации писателей против живой схемы ─────────────────────────────────
def schema_columns(cur, table):
    """Колонки живой таблицы: {имя: (тип, is_nullable, default)} — источник сравнения."""
    cur.execute(
        "SELECT column_name, data_type, is_nullable, column_default "
        "FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position",
        (table,))
    return {row[0]: (row[1], row[2], row[3]) for row in cur.fetchall()}


def check_writer_specs(cur):
    """Спецификация писателя против живой схемы: объявленное существует, обязательное
    объявлено.

    Обратная половина проверки важнее прямой: NOT NULL-колонка без DEFAULT, которой нет в
    спецификации, даёт отказ вставки с текстом про NULL, и виноватой выглядела бы выгрузка,
    хотя колонку не описал писатель (прецедент проб П3/P4 узлов V48–V56).
    """
    print("\n=== спецификации писателей против живой схемы ===")
    for table in TABLES:
        writer = CONFIGURATION_OBJECT_WRITERS[table]
        schema = schema_columns(cur, table)
        if not schema:
            check("%s: таблица существует в живой схеме" % table, False, "колонок нет")
            continue
        declared = set(writer.COLUMNS)
        unknown = sorted(declared - set(schema))
        check("%s: писатель не объявляет колонок, которых нет в схеме" % table, not unknown,
              ", ".join(unknown) if unknown else "колонок спецификации: %d" % len(declared))
        missing = sorted(column for column, (_type, nullable, default) in schema.items()
                         if column not in declared and nullable == "NO" and default is None
                         and column != "id")
        check("%s: каждая NOT NULL-колонка без DEFAULT описана писателем" % table, not missing,
              ", ".join(missing) if missing else "колонок схемы: %d" % len(schema))
        # Колонки ревизии — только у версионируемой таблицы, и только у неё.
        has_revision = set(REVISION_COLUMNS) <= declared
        check("%s: колонки цепи ревизий объявлены согласно версионности" % table,
              has_revision == (table in CONFIGURATION_VERSIONED_TABLES),
              "колонок цепи: %d, в круге версионности: %s"
              % (len(set(REVISION_COLUMNS) & declared),
                 table in CONFIGURATION_VERSIONED_TABLES))
    # Пустая строка как значение состояния — предмет отдельной проверки: `text_empty_kept`
    # существует ровно потому, что у состояния `empty_value` три NOT NULL-колонки держат
    # пустые строки (CHECK `..._targets_name_matches_resolve_state`,
    # `..._targets_resolve_matches_ref`, `..._targets_type_matches_name`,
    # `..._targets_form_matches_name`). Вид `text` превратил бы `''` в NULL, и корректная
    # строка выгрузки была бы отклонена писателем.
    targets_spec = CONFIGURATION_OBJECT_WRITERS[TARGETS_TABLE].COLUMNS
    want_empty = {"target_full_name", "target_object_type", "target_address_form"}
    check("%s: колонки состояния `empty_value` описаны видом `text_empty_kept`"
          % TARGETS_TABLE,
          all(targets_spec.get(column) == "text_empty_kept" for column in want_empty),
          ", ".join("%s=%s" % (column, targets_spec.get(column))
                    for column in sorted(want_empty)))
    check("видом `text_empty_kept` не описана чужая колонка (пустое значение не становится "
          "нормой там, где его нет)",
          {column for column, kind in targets_spec.items()
           if kind == "text_empty_kept"} == want_empty,
          ", ".join(sorted(column for column, kind in targets_spec.items()
                           if kind == "text_empty_kept")))
    # Связь применения остаётся колонкой таблицы применения, а не подменяется именем вида.
    for table, columns in LINK_COLUMNS_OF.items():
        spec = CONFIGURATION_OBJECT_WRITERS[table].COLUMNS
        check("%s: указатель строки вида (%s) остаётся колонкой таблицы применения"
              % (table, ", ".join(columns)),
              all(column in spec for column in columns))

# ─── словари состояний разбора против CHECK живой схемы ────────────────────────
def schema_state_domains(cur):
    """Домены состояний из CHECK живой схемы: {таблица: {колонка: [(имя, значения)]}}.

    Значения по одной колонке объединяются из всех ограничений, где она названа: в DDL узлов
    V52…V57 домены `target_resolve_state` и `target_address_form` названы и полным списком, и
    в составе парных ограничений — сравнение по объединению даёт полный домен колонки, а имена
    ограничений называются ответом, чтобы было видно, ГДЕ именно он лежит.
    """
    result = {}
    for table in TABLES:
        cur.execute("SELECT con.conname, pg_get_constraintdef(con.oid) FROM pg_constraint con "
                    "JOIN pg_class cls ON cls.oid = con.conrelid "
                    "WHERE cls.relname = %s AND con.contype = 'c' ORDER BY con.conname",
                    (table,))
        domains = {}
        for conname, definition in cur.fetchall():
            for pattern in DOMAIN_RES:
                for column, body in pattern.findall(definition or ""):
                    values = set(match.group(1).replace("''", "'")
                                 for match in VALUE_RE.finditer(body))
                    if values:
                        domains.setdefault(column, []).append((conname, values))
        result[table] = domains
    return result


def check_state_vocabularies(cur):
    """Словари состояний вида против CHECK живой схемы — по имени колонки (шаг П4).

    Две стороны одного расхождения: состояние в CHECK, которого разбор не отдаёт никогда, —
    мёртвая ветка ограничения; состояние в словаре разбора, которого нет в CHECK, — отказ
    загрузки круга. Поэтому сравниваются МНОЖЕСТВА значений, а не наличие слова в тексте.
    """
    print("\n=== словари состояний вида против CHECK живой схемы ===")
    domains = schema_state_domains(cur)
    for column, states in sorted(FOP.STATE_VOCABULARIES.items()):
        table = FOP.STATE_VOCABULARY_TABLES[column]
        found = domains.get(table, {}).get(column, [])
        if not found:
            check("%s.%s: в схеме есть домен состояний этого столбца" % (table, column),
                  False, "предикатов не найдено")
            continue
        values = set()
        for _conname, part in found:
            values |= part
        names = ", ".join(sorted(set(conname for conname, _ in found)))
        check("%s.%s: словарь разбора и домен CHECK совпадают" % (table, column),
              values == set(states),
              "CHECK: %s; словарь: %s; ограничения: %s"
              % (sorted(values)[:8], sorted(states)[:8], names))
    # Домен события цепи — у схемы, а не у разбора: точка доступа называет три значения.
    for table in NODE_VERSIONED:
        found = domains.get(table, {}).get("changed_by", [])
        values = set()
        for _conname, part in found:
            values |= part
        check("%s: домен `changed_by` схемы совпадает со словарём точки доступа" % table,
              values == set(REVISION_STATE_VALUES), ", ".join(sorted(values)))
    # Словарей значений СВОЙСТВ вида в схеме нет — это решение Q7 (вариант A): незнакомое
    # значение остаётся значением с состоянием `unknown_value` и виновником, а не отказом.
    property_columns = sorted(set(FOP.property_columns()) - set(FOP.STATE_VOCABULARIES))
    enforced = sorted(column for column in property_columns
                      if column in domains.get(TABLE, {}))
    check("%s: у свойств вида нет словарных доменов CHECK (Q7, вариант A)" % TABLE,
          not enforced,
          "домены у колонок: %s" % ", ".join(enforced) if enforced
          else "свойств без доменов: %d" % len(property_columns))
    return domains


def check_contract_matches_writer(collected):
    """Контракт разбора и спецификация писателя совпадают в обе стороны.

    Ключ разбора, которого нет в писателе, — потерянный факт: разбор его отдал, а в таблицу он
    не пойдёт, и карточка конфигурации не узнает о нём никогда. Колонка писателя, которой нет у
    разбора, — выдуманное значение: колонка осталась бы NULL, и читатель отличал бы «значения
    нет» от «слоя не спрашивали» только по имени колонки. Поэтому сравниваются МНОЖЕСТВА.
    """
    print("\n=== контракт разбора против спецификации писателя (обе стороны) ===")
    for table, key in ((TABLE, "rows"), (TARGETS_TABLE, "targets")):
        writer = CONFIGURATION_OBJECT_WRITERS[table]
        declared = set(writer.COLUMNS) - set(REVISION_COLUMNS) - LOADER_SUPPLIED[table]
        rows = collected.get(key) or []
        if not rows:
            note("%s: строк разбора нет — сравнение контракта с писателем даёт выгрузка, "
                 "где круг есть (MinCfg, BGU2, BP3)" % table)
            continue
        given = set()
        for row in rows:
            given |= {name for name in row if name != "configuration_uuid"}
        dropped = sorted(given - declared)
        check("%s: ни один ключ разбора не теряется перед записью" % table, not dropped,
              ", ".join(dropped) if dropped else "ключей разбора: %d" % len(given))
        invented = sorted(declared - given)
        check("%s: писатель не объявляет колонок, о которых разбор молчит" % table,
              not invented, ", ".join(invented) if invented
              else "колонок спецификации: %d" % len(declared))

# ─── запись круга: тот же порядок, что стадия ─────────────────────────────────
def index_rows_of(cur, configuration_id):
    """Записи индекса состава из `configuration_objects` — тем же слоем, что и загрузка.

    Источник — строки БД, а не повторный разбор `ConfigDumpInfo.xml` (приём `read_index_records`
    узлов V46, V48–V56): разрешение целей перечня `<Use>` идёт по индексному `object_id` и
    `uuid`, и проба обязана проверять тот же путь, которым идёт стадия. Без индекса цели
    остались бы `unresolved` — проба молча сравнивала бы не то состояние (правило C2).
    """
    info = read_index_records(cur, configuration_id)
    return list(info.get("rows") or []), info


def table_baseline(cur, cfg_uuid):
    """Базовое состояние двух таблиц: {таблица: (всего строк, строк этой конфигурации)}."""
    state = {}
    for table in TABLES:
        state[table] = (int(one(cur, "SELECT count(*) FROM " + table) or 0),
                        int(one(cur, "SELECT count(*) FROM " + table
                                   + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0))
    return state


def write_all(cur, cfg_uuid, collected, moment=None):
    """Записать круг той же очерёдностью, что стадия, и вернуть связи для проверок.

    Порядок держится иерархией данных, а не удобством (Q1, вариант A): строка применения
    ссылается на ЧИСЛОВОЙ id конкретной ревизии строки вида, поэтому сначала идут параметры
    (`insert_ids` с `RETURNING id`), затем строки применения. Снятие круга предшествует
    вставкам и идёт по `REMOVE_ORDER` (M7): каскад
    `functional_option_parameter_targets_parameter_fkey` не должен снять строки молча — иначе
    число снятых строк в ответе было бы неправдой.

    Ключом связи служит индексное имя `FunctionalOptionsParameter.<Имя>` — его несёт строка
    применения (`PARAMETER_LINK_KEY`), а строка вида держит короткое имя в `object_name`
    (иерархии раскладки у вида нет, замер 1.2). Тот же ключ держит стадия слоя V56
    (`index_object_name` в `configuration_functional_options_loader.py`) и слои V49/V50.
    Порядок `insert_ids` совпадает с порядком строк разбора — связь держится им.
    """
    parameter_rows = [dict(row) for row in (collected.get("rows") or [])]
    target_rows = [dict(row) for row in (collected.get("targets") or [])]
    for rows in (parameter_rows, target_rows):
        for row in rows:
            row["configuration_uuid"] = cfg_uuid

    # Один штамп на всё событие (M2): версионируемые таблицы одной загрузки несут одну метку.
    # Строки применения метки не получают — колонок ревизии у них нет (Q2, вариант A).
    moment = stamp_revision_rows(parameter_rows, revision_no=FIRST_REVISION,
                                 changed_by=CHANGED_BY_LOAD, changed_at=moment)

    removed = {}
    for table in FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER:
        cur.execute("DELETE FROM " + table + " WHERE configuration_uuid = %s", (cfg_uuid,))
        removed[table] = cur.rowcount

    written = {table: 0 for table in FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER}
    link_keys = [FOP.index_object_name(str(row.get("object_name") or ""))
                 for row in parameter_rows]
    if len(set(link_keys)) != len(link_keys):
        raise ValueError("строки вида даны с повторяющимися именами: "
                         + ", ".join(sorted({key for key in link_keys
                                             if link_keys.count(key) > 1})[:10]))
    parameter_ids = (FunctionalOptionsParametersRowWriter.insert_ids(cur, parameter_rows)
                     if parameter_rows else [])
    written[TABLE] = len(parameter_ids)
    ids_by_key = dict(zip(link_keys, parameter_ids))
    orphan_names = sorted({str(row.get(FOP.PARAMETER_LINK_KEY)) for row in target_rows
                           if ids_by_key.get(str(row.get(FOP.PARAMETER_LINK_KEY))) is None})
    if orphan_names:
        raise ValueError("строки применения остались без строки вида: "
                         + ", ".join(orphan_names[:10]))
    for row in target_rows:
        row["functional_option_parameter_id"] = ids_by_key[
            str(row.get(FOP.PARAMETER_LINK_KEY))]
    written[TARGETS_TABLE] = (FunctionalOptionParameterTargetRowWriter
                              .insert_many(cur, target_rows) if target_rows else 0)
    return written, removed, moment, ids_by_key


def parse_counts_of(collected):
    """Сколько строк отдал разбор — источник для сравнения с писателем и таблицами."""
    return {
        TABLE: len(collected.get("rows") or []),
        TARGETS_TABLE: len(collected.get("targets") or []),
    }

def check_written(cur, cfg_uuid, name, collected, written, moment):
    """Сколько строк дошло до таблиц и витрин (шаг П4): писатель, таблица, витрина — три числа."""
    print("\n--- что записано: писатель, таблица, витрина ---")
    expected = BASELINE_ROWS[name]
    parse_counts = parse_counts_of(collected)
    for table in FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER:
        check("%s: писатель записал столько же строк, сколько отдал разбор" % table,
              written.get(table) == parse_counts[table],
              "писатель: %s, разбор: %d" % (written.get(table), parse_counts[table]))
    for table in TABLES:
        check("%s: базовая линия плана соблюдена" % table,
              parse_counts[table] == expected[table],
              "разбор: %d, план: %d" % (parse_counts[table], expected[table]))
    views_of = {TABLE: VIEW, TARGETS_TABLE: TARGETS_VIEW}
    for table in TABLES:
        stored = int(one(cur, "SELECT count(*) FROM " + table
                            + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0)
        current = int(one(cur, "SELECT count(*) FROM " + views_of[table]
                             + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0)
        check("%s: таблица содержит строки этого круга" % table,
              stored == parse_counts[table],
              "в таблице %d, разбора %d" % (stored, parse_counts[table]))
        check("%s: витрина текущего состояния отдаёт весь круг (первая ревизия — текущая)"
              % views_of[table], current == parse_counts[table],
              "в витрине %d, круга %d" % (current, parse_counts[table]))
    if not parse_counts[TABLE]:
        note("%s: круга вида в этой выгрузке нет — каталога `FunctionalOptionsParameters` нет "
             "ни файлом, ни строкой индекса (замер 1.1); пустой ответ является состоянием "
             "выгрузки, а не отказом (Q9, вариант A)" % name)
        return
    check("метка события названа (M2)", bool(moment), str(moment))
    distinct = int(one(cur, "SELECT count(DISTINCT changed_at) FROM " + TABLE
                      + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0)
    check("все строки вида этой загрузки несут одну метку (M2)", distinct == 1,
          "различных меток: %d" % distinct)
    note("записано: параметров %d, целей применения %d"
         % (written[TABLE], written[TARGETS_TABLE]))


def check_link_integrity(cur, cfg_uuid, name):
    """Связи круга: состояние строки вида согласовано с её строками применения.

    Проверки идут таблицами, а не списком разбора: именно так виден расход между тем, что
    утверждает строка вида (`use_state`, `targets_count`), и тем, что действительно лежит в
    таблице применения. Расход называет себя числом строк, а не молчанием: CHECK его не ловит,
    потому что второй таблицы он не видит (тот же приём, что у проб V50/V52/V56).
    """
    print("\n--- связи круга: состояние строки вида против её строк применения ---")
    orphans = int(one(cur, "SELECT count(*) FROM " + TARGETS_TABLE + " t LEFT JOIN " + TABLE
                        + " p ON p.id = t.functional_option_parameter_id "
                          "WHERE t.configuration_uuid = %s AND p.id IS NULL",
                        (cfg_uuid,)) or 0)
    check("каждая строка применения указывает на строку вида этой конфигурации "
          "(Q1, вариант A)", orphans == 0, "сирот: %d" % orphans)
    # Форма ключа связи различается намеренно: `full_name` строки вида держит короткое имя
    # (иерархии раскладки у вида нет, замер 1.2), а строка применения несёт индексное имя
    # `FunctionalOptionsParameter.<Имя>` (`PARAMETER_LINK_KEY`). Префикс берётся из функции
    # разбора, а не пишется в запросе: иначе проба проверяла бы собственную догадку.
    index_prefix = FOP.index_object_name("")
    mismatched = int(one(cur, "SELECT count(*) FROM " + TARGETS_TABLE + " t JOIN " + TABLE
                         + " p ON p.id = t.functional_option_parameter_id "
                           "WHERE t.configuration_uuid = %s AND (t.parameter_object_uuid <> "
                           "p.object_uuid OR t.parameter_full_name <> %s || p.full_name OR "
                           "t.configuration_uuid <> p.configuration_uuid)",
                         (cfg_uuid, index_prefix)) or 0)
    check("указатель параметра в строке применения совпадает со строкой вида "
          "(uuid, индексное имя, конфигурация)", mismatched == 0,
          "расхождений: %d" % mismatched)
    inconsistent = int(one(cur,
        "SELECT count(*) FROM (SELECT p.id, p.use_state, p.targets_count, "
        "count(t.id) AS actual FROM " + TABLE + " p LEFT JOIN " + TARGETS_TABLE
        + " t ON t.functional_option_parameter_id = p.id WHERE p.configuration_uuid = %s "
        "GROUP BY p.id, p.use_state, p.targets_count) s WHERE s.actual <> s.targets_count "
        "OR (s.use_state = %s AND s.actual = 0) OR (s.use_state = %s AND s.actual <> 0)",
        (cfg_uuid, FOP.USE_WITH, FOP.USE_EMPTY)) or 0)
    check("состояние перечня и его счётчик согласованы с числом строк применения "
          "(CHECK этого не видит)", inconsistent == 0, "строк вида с расходом: %d"
          % inconsistent)
    order_bad = int(one(cur,
        "SELECT count(*) FROM (SELECT t.functional_option_parameter_id, min(t.ordinal) AS lo, "
        "max(t.ordinal) AS hi, count(DISTINCT t.ordinal) AS distinct_count, count(*) AS total "
        "FROM " + TARGETS_TABLE + " t JOIN " + TABLE + " p ON p.id = t.functional_option_"
        "parameter_id WHERE t.configuration_uuid = %s GROUP BY t.functional_option_parameter_id"
        ") s WHERE s.lo <> 0 OR s.distinct_count <> s.total OR s.hi + 1 <> s.total",
        (cfg_uuid,)) or 0)
    check("позиции перечня `<Use>` не пропущены и не повторены (порядок файла сохранён, "
          "ключ `(functional_option_parameter_id, ordinal)`)", order_bad == 0,
          "параметров с расходом: %d" % order_bad)
    stale = int(one(cur, "SELECT count(*) FROM " + TARGETS_TABLE + " t WHERE "
                        "t.configuration_uuid = %s AND t.id NOT IN "
                        "(SELECT id FROM " + TARGETS_VIEW + ")", (cfg_uuid,)) or 0)
    check("витрина применения не отдаёт строк не текущей ревизии (текущность — связкой, Q2)",
          stale == 0, "строк вне витрины: %d" % stale)

# ─── круговая проверка содержимого ─────────────────────────────────────────────
def pg_array_items(value):
    """Элементы массива Postgres из того, что вернуло соединение."""
    if isinstance(value, (list, tuple)):
        return [str(item).strip().strip('"') for item in value]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("{") and text.endswith("}"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip('"') for item in inner.split(",")]
    return [text]


def expected_value(kind, value):
    """Как писатель превращает значение контракта разбора в параметр запроса."""
    if kind in ("text", "uuid"):
        if value is None:
            return None
        text = str(value).strip()
        return text or None
    if kind == "text_empty_kept":
        # Узел V57: пустая строка здесь является значением состояния (`empty_value`), а не
        # отсутствием значения — сравнение обязано различать `''` и NULL, иначе круговая
        # проверка не видела бы именно того, ради чего введён этот вид колонки.
        if value is None:
            return None
        return str(value).strip()
    if kind == "jsonb_nullable":
        if not value:
            return None
        return value if isinstance(value, (dict, list)) else None
    if kind == "int":
        if value is None or value == "":
            return None
        return int(value)
    if kind == "text_array_nullable":
        if value is None or value == "" or value == []:
            return None
        items = [str(item) for item in value if str(item).strip()]
        return items or None
    return value


def stored_value(kind, value):
    """Как то же значение вернёт таблица: `uuid` psycopg отдаёт объектом, сравнение идёт
    строкой в нижнем регистре (прецедент V49); элементы массива — разбор литерала."""
    if kind == "uuid" and value is not None:
        return str(value).lower()
    if kind == "text_array_nullable" and value is not None:
        return pg_array_items(value)
    return value


def row_key(table, row):
    """Ключ, по которому строку разбора ищут в таблице: имя позиции вида для строк вида,
    пара (указатель параметра, порядковый номер) для строк применения — у параметра их
    несколько (до 20 целей на файл по замеру 2.1), и по одному имени они слились бы в одну
    (прецеденты V49/V50/V52/V56)."""
    if table == TABLE:
        return row["object_name"]
    return (row[FOP.PARAMETER_LINK_KEY], row["ordinal"])


def expected_loader_value(column, cfg_uuid, parser_row, parameter_ids):
    """Что подставляет загрузчик, а не разбор: uuid конфигурации и id строки вида."""
    if column == "configuration_uuid":
        return str(cfg_uuid).lower()
    if column == "functional_option_parameter_id":
        return parameter_ids.get(parser_row[FOP.PARAMETER_LINK_KEY])
    raise KeyError("загрузчик подставляет только эти две колонки: %s" % column)


def check_round_trip(cur, cfg_uuid, collected, parameter_ids):
    """Круговая проверка содержимого обеих таблиц: каждая колонка писателя сравнивается с
    контрактом разбора.

    Сравнение идёт по колонкам спецификации, а не по ключам строк: именно так видна колонка,
    которую писатель читает, а разбор не отдаёт (она осталась бы NULL и не участвовала бы в
    сравнении по ключам строк).
    """
    print("\n--- круговая проверка содержимого (обе таблицы, все колонки) ---")
    compared = 0
    problems = []
    views_of = {TABLE: TABLE, TARGETS_TABLE: TARGETS_TABLE}
    for table, key in ((TABLE, "rows"), (TARGETS_TABLE, "targets")):
        writer = CONFIGURATION_OBJECT_WRITERS[table]
        columns = sorted(set(writer.COLUMNS) - set(REVISION_COLUMNS))
        stored = {}
        for row in fetch_dicts(cur, "SELECT %s FROM %s WHERE configuration_uuid = %%s"
                                  % (", ".join(columns), views_of[table]), (cfg_uuid,)):
            stored[row_key(table, row)] = row
        for parser_row in collected.get(key) or []:
            got = stored.get(row_key(table, parser_row))
            if got is None:
                problems.append("%s: строки %s нет в таблице"
                                % (table, row_key(table, parser_row)))
                continue
            for column in columns:
                kind = writer.COLUMNS[column]
                if column in LOADER_SUPPLIED[table]:
                    want = expected_loader_value(column, cfg_uuid, parser_row, parameter_ids)
                else:
                    want = expected_value(kind, parser_row.get(column))
                have = stored_value(kind, got[column])
                if have != want:
                    problems.append("%s.%s колонка %s: ожидалось %r, в таблице %r"
                                    % (table, row_key(table, parser_row), column, want, have))
                compared += 1
    check("содержимое круга совпадает с контрактом разбора по всем колонкам писателя",
          not problems, "сравнено значений %d, расхождений %d: %s"
          % (compared, len(problems), "; ".join(problems[:10])))
    print("  сравнение: %s колонок вида, %s колонок применения, значений %d"
          % (len(set(CONFIGURATION_OBJECT_WRITERS[TABLE].COLUMNS) - set(REVISION_COLUMNS)),
             len(set(CONFIGURATION_OBJECT_WRITERS[TARGETS_TABLE].COLUMNS)), compared))

# ─── случаи отказа: нарушение называется ограничением по имени ─────────────────
def probe_parameter_row(base, cfg_uuid, tag, **overrides):
    """Пробная строка вида: копия реальной с новой личностью и заданными полями.

    Копия, а не составленная с нуля строка: только так видно, что отклоняет ИМЕННО
    проверяемое сочетание полей, а не отсутствие чего-то, о чём прогон забыл подумать
    (прецедент `probe_criterion_row` узла V52).
    """
    name = "_Проба_V57_" + tag
    row = dict(base)
    row.update({
        "configuration_uuid": cfg_uuid,
        "object_name": name,
        "full_name": FOP.index_object_name(name),
        "object_uuid": probe_uuid(tag),
        "source_path": "%s/_Проба_V57_%s.xml" % (FOP.DIR_NAME, tag),
    })
    row.update(overrides)
    stamp_revision_rows([row], revision_no=FIRST_REVISION, changed_by=CHANGED_BY_LOAD)
    return row


def probe_target_row(base, cfg_uuid, parameter_id, tag, ordinal=9000, **overrides):
    """Пробная строка применения: копия реальной с другим порядковым номером.

    Номер меняется на заведомо свободный: копия строки применения с её же `ordinal`
    нарушила бы ключ `(functional_option_parameter_id, ordinal)` раньше проверяемого
    ограничения, и прогон отчитался бы не о том отказе (прецедент V50/V52).
    """
    row = dict(base)
    row.update({
        "configuration_uuid": cfg_uuid,
        "functional_option_parameter_id": parameter_id,
        "ordinal": ordinal,
    })
    row.update({"parameter_full_name": row.get("parameter_full_name") or "",
                "parameter_object_uuid": row.get("parameter_object_uuid") or ""})
    row["parameter_full_name"] = FOP.index_object_name("_Проба_V57_" + tag)
    row["parameter_object_uuid"] = probe_uuid(tag)
    row.update(overrides)
    return row


def expect_violation(cur, label, table, row, constraints):
    """Нарушение читается именованным ограничением, а не текстом ошибки (приём V49).

    Имя ограничения psycopg2 отдаёт в `diag`, поэтому сравнивается именно оно: иначе прогон
    принимал бы любой отказ. `constraints` — имя или набор имён: пара значений может нарушать
    два ограничения согласованности, и какой из них отчитывается решает порядок проверки
    ограничений, а не замысел узла.
    """
    allowed = set([constraints]) if isinstance(constraints, str) else set(constraints)
    cur.execute("SAVEPOINT v57_p4_case")
    try:
        CONFIGURATION_OBJECT_WRITERS[table].insert(cur, row)
        check(label, False, "строка принята — ограничение не сработало")
    except psycopg2.Error as exc:
        name = getattr(getattr(exc, "diag", None), "constraint_name", None) \
            or getattr(exc, "constraint_name", None)
        check(label + " — имя из ожидаемого набора", name in allowed,
              "нарушено: " + (name or str(exc).splitlines()[0][:200])
              + "; ожидалось одно из " + ", ".join(sorted(allowed)))
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v57_p4_case")


def expect_accepted(cur, label, table, row):
    """Обратная сторона: согласованная строка принимается ЧЕРЕЗ ПИСАТЕЛЯ.

    Для узла V57 это проверка нового вида колонки `text_empty_kept`: строка применения с
    состоянием `empty_value` держит пустые строки в трёх NOT NULL-колонках, и писатель не
    имеет права превращать их в NULL.
    """
    cur.execute("SAVEPOINT v57_p4_accept")
    try:
        CONFIGURATION_OBJECT_WRITERS[table].insert(cur, row)
        check(label, True, "строка записана через писателя")
    except psycopg2.Error as exc:
        check(label, False, str(exc).splitlines()[0][:300])
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v57_p4_accept")


def expect_update_violation(cur, label, sql, params, constraints):
    """Отказ правки записанной строки читается именем ограничения (приём V50/V52)."""
    allowed = set([constraints]) if isinstance(constraints, str) else set(constraints)
    cur.execute("SAVEPOINT v57_p4_update")
    try:
        cur.execute(sql, params)
        check(label, False, "правка прошла — ограничение не сработало")
    except psycopg2.Error as exc:
        name = getattr(getattr(exc, "diag", None), "constraint_name", None) \
            or getattr(exc, "constraint_name", None)
        check(label + " — имя из ожидаемого набора", name in allowed,
              "нарушено: " + (name or str(exc).splitlines()[0][:200])
              + "; ожидалось одно из " + ", ".join(sorted(allowed)))
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v57_p4_update")


def expect_not_null(cur, label, table, row, column):
    """Отказ по обязательности колонки читается классом ошибки и именем колонки.

    Имени ограничения у такого отказа нет: `NOT NULL` в DDL живёт атрибутом колонки, а не
    строкой `pg_constraint` (замеры узлов V49/V50). Требовать имени значило бы выдумывать то,
    чего схема не даёт; при этом колонка в сообщении называется, и именно она является
    предметом отказа.
    """
    cur.execute("SAVEPOINT v57_p4_not_null")
    try:
        CONFIGURATION_OBJECT_WRITERS[table].insert(cur, row)
        check(label, False, "строка принята — обязательность колонки не сработала")
    except psycopg2.Error as exc:
        text = str(exc).splitlines()[0]
        ok = isinstance(exc, psycopg2.errors.NotNullViolation) and ('"%s"' % column) in text
        check(label + " — отказ назван колонкой", ok,
              "%s: %s" % (type(exc).__name__, text[:200]))
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v57_p4_not_null")

def check_named_constraints(cur, cfg_uuid, name, collected, parameter_ids):
    """Что отклоняет схема и как она это называет (шаг П4, узел V57)."""
    print("\n--- что отклоняет схема: нарушение называется ограничением ---")
    rows = collected.get("rows") or []
    target_rows = collected.get("targets") or []
    if not rows:
        note("%s: строк вида в этой выгрузке нет — случаи отказа строятся на выгрузках, "
             "где круг есть (MinCfg, BGU2, BP3)" % name)
        return
    base = rows[0]
    stored_id = one(cur, "SELECT id FROM " + TABLE + " WHERE configuration_uuid = %s "
                         "ORDER BY id LIMIT 1", (cfg_uuid,))

    # Состояние перечня и его счётчик согласованы (M3): «пустой перечень» и «перечень не
    # разбирали» — разные ответы, третьего состояния в замкнутом CHECK нет.
    expect_violation(cur, "`with_content` без строк применения отклоняется",
                     TABLE, probe_parameter_row(base, cfg_uuid, "use_with0",
                                               use_state=FOP.USE_WITH, targets_count=0),
                     "functional_option_parameters_use_state_matches_targets")
    expect_violation(cur, "`empty_content` со счётчиком целей отклоняется",
                     TABLE, probe_parameter_row(base, cfg_uuid, "use_empty3",
                                               use_state=FOP.USE_EMPTY, targets_count=3),
                     "functional_option_parameters_use_state_matches_targets")
    # Виновник свойств: «всё известно» не держит списка, «неизвестное» называет его (Q7 A).
    expect_violation(cur, "`all_known` со списком неизвестных свойств отклоняется",
                     TABLE, probe_parameter_row(base, cfg_uuid, "un_all",
                                               properties_state=FOP.PROPS_ALL_KNOWN,
                                               unknown_property_names=["UnknownTag"]),
                     "functional_option_parameters_properties_state_matches_unknown")
    expect_violation(cur, "`unknown_value` без виновника отклоняется",
                     TABLE, probe_parameter_row(base, cfg_uuid, "un_none",
                                               properties_state=FOP.PROPS_UNKNOWN_VALUE,
                                               unknown_property_names=None),
                     "functional_option_parameters_properties_state_matches_unknown")
    # Незнакомое состояние словаря отклоняется, а не записывается текстом.
    expect_violation(cur, "состояния перечня вне словаря отклоняется",
                     TABLE, probe_parameter_row(base, cfg_uuid, "use_unknown",
                                               use_state="not_a_state", targets_count=1),
                     "functional_option_parameters_use_state_known")
    # Писатель не заполнит обязательное: отказ называется колонкой, а не ограничением.
    expect_not_null(cur, "строка вида без `object_uuid` отклоняется",
                    TABLE, probe_parameter_row(base, cfg_uuid, "no_uuid", object_uuid=None),
                    "object_uuid")

    if stored_id:
        expect_update_violation(
            cur, "пустое имя позиции вида отклоняется",
            "UPDATE " + TABLE + " SET object_name = '' WHERE id = %s", (stored_id,),
            "functional_option_parameters_names_not_blank")
        expect_update_violation(
            cur, "нулевой номер ревизии отклоняется",
            "UPDATE " + TABLE + " SET revision_no = 0 WHERE id = %s", (stored_id,),
            "functional_option_parameters_revision_no_positive")
        expect_update_violation(
            cur, "метка события без события отклоняется",
            "UPDATE " + TABLE + " SET changed_by = NULL WHERE id = %s", (stored_id,),
            "functional_option_parameters_changed_pair_check")

    if not target_rows:
        note("%s: строк применения в этой выгрузке нет — случаи отказа таблицы применения "
             "строятся там, где круг есть (замер 2.1: 2/0/6/26 целей)" % name)
        return


    tbase_raw = target_rows[0]
    anchor_id = stored_id or parameter_ids.get(str(tbase_raw.get(FOP.PARAMETER_LINK_KEY)))
    if anchor_id is None:
        note("%s: строки вида, к которой можно привязать копию элемента перечня, в этой "
             "транзакции нет — случаи отказа таблицы применения строятся там, где круг "
             "записан (MinCfg, BGU2, BP3)" % name)
        return
    # Основой случаев служит строка применения, записанная ЧЕРЕЗ ПИСАТЕЛЬ: колонки,
    # которые подставляет слой (`configuration_uuid`, `functional_option_parameter_id`),
    # в контракте разбора отсутствуют, и копия «сырой» строки разбора падала бы на NOT
    # NULL этих колонок, а не на проверяемое ограничение (приём V52 `probe_content_row`).
    # Порядковый номер берётся из заведомо свободного диапазона, чтобы копия не нарушила
    # ключ `(functional_option_parameter_id, ordinal)` раньше времени.
    tbase = probe_target_row(tbase_raw, cfg_uuid, anchor_id, "base", ordinal=9100)
    # КЛЮЧЕВОЙ случай узла V57: пустой адрес цели держится состоянием `empty_value`, а
    # пустые строки колонок NOT NULL писатель обязан сохранить пустыми, а не превратить в
    # NULL (вид `text_empty_kept`).
    empty_row = probe_target_row(
        tbase_raw, cfg_uuid, anchor_id, "empty_value", ordinal=9000,
        target_resolve_state=FOP.TARGET_EMPTY_VALUE, target_full_name="",
        target_object_type="", target_address_form=FOP.ADDRESS_FORM_EMPTY,
        target_object_id=None, target_object_uuid=None, target_unresolved_path=None)
    expect_accepted(cur, "строка применения с состоянием `empty_value` записывается через "
                         "писателя (пустая строка остаётся пустой)",
                    TARGETS_TABLE, empty_row)
    # Пустой адрес без состояния отклоняется: пустая строка без состояния — не ответ.
    # Нарушаются два согласования сразу — адрес без состояния и пустая форма адреса при
    # состоянии, которого нет; какое из них отчитывается, решает порядок проверки.
    empty_pair = {"functional_option_parameter_targets_name_matches_resolve_state",
                  "functional_option_parameter_targets_form_matches_name"}
    expect_violation(cur, "пустого адреса без состояния `empty_value` нет",
                     TARGETS_TABLE, dict(empty_row,
                                        target_resolve_state=FOP.TARGET_UNRESOLVED),
                     empty_pair)
    # Состояние `empty_value` с непустым адресом — два ограничения согласованности сразу:
    # какое из них отчитывается, решает порядок проверки (приём V49/V50/V52).
    pair = {"functional_option_parameter_targets_name_matches_resolve_state",
            "functional_option_parameter_targets_resolve_matches_ref"}
    expect_violation(cur, "`empty_value` с непустым адресом отклоняется",
                     TARGETS_TABLE, dict(empty_row, target_full_name="Catalog.Контракты",
                                         target_object_type="Catalog",
                                         target_address_form=FOP.ADDRESS_FORM_OBJECT),
                     pair)
    # Вид цели = первый сегмент адреса; `exact` обязан держать ссылку индекса.
    expect_violation(cur, "`exact` без вида цели отклоняется",
                     TARGETS_TABLE, dict(tbase, target_object_type=""),
                     {"functional_option_parameter_targets_resolve_matches_ref",
                      "functional_option_parameter_targets_type_matches_name"})
    # Форма адреса различает носителя значения (M5): срез обязан называться в адресе.
    expect_violation(cur, "формы среза измерения при адресе без среза отклоняется",
                     TARGETS_TABLE, dict(tbase, target_full_name="Catalog.Контракты",
                                         target_object_type="Catalog",
                                         target_address_form=FOP.ADDRESS_FORM_DIMENSION),
                     "functional_option_parameter_targets_form_matches_name")
    # Атрибут `xsi:type` не отбрасывается и не подставляется (M6): состояние
    # «атрибута нет» при наблюдаемом значении атрибута — противоречие строки.
    expect_violation(cur, "`absent` при значении атрибута `xsi:type` отклоняется",
                     TARGETS_TABLE,
                     dict(tbase, item_type_state=FOP.ITEM_TYPE_STATE_ABSENT,
                          item_type_attr=FOP.ITEM_TYPE_REF_VALUE),
                     "functional_option_parameter_targets_item_type_matches_attr")
    # Локальное имя элемента перечня пустым не бывает: колонка ведёт себя как все текстовые
    # колонки писателя (вид `text`, пустое значение гасится в NULL), поэтому отказ называет
    # NOT NULL колонки, а не согласование имён. Это названо, а не спрятано: пустое имя
    # выгрузка не отдаёт (замер 2.1), и до CHECK строка не доходит.
    expect_not_null(cur, "пустого локального имени элемента перечня нет (писатель гасит "
                         "пустое значение колонки `text` как отсутствующее)",
                    TARGETS_TABLE, dict(tbase, item_tag=""), "item_tag")
    # Пустого указателя параметра — та же граница: колонка ведётся видом `text`, пустое
    # значение гасится в NULL, и отказ называет NOT NULL. Согласование `names_not_blank`
    # сторожит строку, записанную мимо писателя (правка объекта, прямой SQL), — для пути
    # загрузки оно достижимо только как отказ колонки, и проба называет это, а не ждёт
    # имени CHECK, которого на этом пути не бывает.
    expect_not_null(cur, "пустого указателя параметра нет (пустое значение колонки `text` "
                         "гасится как отсутствующее)",
                    TARGETS_TABLE, dict(tbase, parameter_full_name=""),
                    "parameter_full_name")
    expect_violation(cur, "отрицательная позиция перечня отклоняется",
                     TARGETS_TABLE, dict(tbase, ordinal=-1),
                     "functional_option_parameter_targets_ordinal_non_negative")
    if anchor_id:
        duplicate = dict(tbase)
        duplicate["functional_option_parameter_id"] = anchor_id
        duplicate["ordinal"] = int(one(cur, "SELECT ordinal FROM " + TARGETS_TABLE
                                         + " WHERE functional_option_parameter_id = %s "
                                         + "ORDER BY ordinal LIMIT 1", (anchor_id,)) or 0)
        expect_violation(cur, "повтора позиции перечня в одной ревизии вида нет (Q2, "
                              "вариант A)", TARGETS_TABLE, duplicate,
                         "functional_option_parameter_targets_parameter_ordinal_key")


def check_chain(cur, cfg_uuid, name, collected, ids_by_key):
    """Цепь ревизий строки вида и текущность строк применения; всё в SAVEPOINT и откатано.

    Вторая ревизия вставляется копией, а не второй записью круга: повторная ЗАГРУЗКА снимает
    круг целиком и пишет его заново ревизией 1 (историю состояний даёт узел правки объекта,
    которого в схеме ещё нет — D8), поэтому цепь продолжает ровно тот же шаг, что узел V52.
    Иначе проба проверяла бы не цепь ревизий, а перезапись круга.

    Факты читаются таблицами и витринами, а не ответом писателя: витрина отдаёт одну строку
    второй ревизии; прежняя ревизия остаётся в таблице историей; витрина применения перестаёт
    отдавать строки прежней ревизии, оставив их в таблице (своей цепи у них нет — Q2,
    вариант A); снятие второй ревизии возвращает витрины к первой.
    """
    print("\n--- цепь ревизий строки вида и текущность применения (Q2, вариант A) ---")
    parameter_rows = collected.get("rows") or []
    target_rows = collected.get("targets") or []
    if not parameter_rows:
        note("%s: круга вида нет — цепь ревизий читается там, где круг есть (замер 1.1: "
             "2/0/5/7 файлов регистрации)" % name)
        return
    cur.execute("SAVEPOINT v57_p4_chain")
    try:
        # Копия строки вида обязана нести колонки слоя (`configuration_uuid`), которых нет
        # в контракте разбора: иначе вторая ревизия падала бы на NOT NULL, а не на цепь.
        first = dict(parameter_rows[0], configuration_uuid=cfg_uuid)
        object_name = str(first.get("object_name") or "")
        link_key = FOP.index_object_name(object_name)
        first_id = ids_by_key[link_key]
        second = dict(first, object_uuid=probe_uuid("ревизия-2"))
        stamp_revision_rows([second], revision_no=FIRST_REVISION + 1,
                            changed_by=CHANGED_BY_EDIT)
        second_ids = FunctionalOptionsParametersRowWriter.insert_ids(cur, [second])
        second_id = second_ids[0] if second_ids else None
        held = int(one(cur, "SELECT count(*) FROM " + TABLE
                         + " WHERE configuration_uuid = %s AND object_name = %s "
                           "AND revision_no = %s",
                         (cfg_uuid, object_name, FIRST_REVISION + 1)) or 0)
        check("второй ревизии строки вида хватает места в цепи "
              "`configuration_uuid, object_name, revision_no`",
              held == 1 and second_id is not None, "строк ревизии 2: %d" % held)
        second_targets = [dict(row, configuration_uuid=cfg_uuid,
                               functional_option_parameter_id=second_id)
                          for row in target_rows
                          if str(row.get(FOP.PARAMETER_LINK_KEY)) == link_key]
        if second_targets and second_id is not None:
            FunctionalOptionParameterTargetRowWriter.insert_many(cur, second_targets)
        cur.execute("SELECT revision_no, object_uuid FROM " + VIEW
                    + " WHERE configuration_uuid = %s AND object_name = %s",
                    (cfg_uuid, object_name))
        got = cur.fetchall()
        check("%s: витрина текущего состояния отдаёт одну строку — вторую ревизию" % VIEW,
              len(got) == 1 and int(got[0][0]) == FIRST_REVISION + 1
              and str(got[0][1]).lower() == str(second["object_uuid"]).lower(),
              str(got)[:200])
        history = int(one(cur, "SELECT count(*) FROM " + TABLE
                           + " WHERE configuration_uuid = %s AND object_name = %s",
                           (cfg_uuid, object_name)) or 0)
        check("%s: прежняя ревизия остаётся в таблице историей (снимается круг загрузки, "
              "а не цепь ревизий)" % TABLE, history == 2, "строк в таблице: %d" % history)
        old_table_rows = int(one(cur, "SELECT count(*) FROM " + TARGETS_TABLE
                                   + " WHERE functional_option_parameter_id = %s",
                                   (first_id,)) or 0)
        if second_targets and second_id is not None:
            current_view_rows = int(one(cur, "SELECT count(*) FROM " + TARGETS_VIEW
                                          + " WHERE functional_option_parameter_id = %s",
                                          (second_id,)) or 0)
            old_view_rows = int(one(cur, "SELECT count(*) FROM " + TARGETS_VIEW
                                     + " WHERE functional_option_parameter_id = %s",
                                     (first_id,)) or 0)
            check("%s: витрина применения отдаёт строки второй ревизии (текущность держится "
                  "связкой по id строки вида, Q2 вариант A)" % TARGETS_VIEW,
                  current_view_rows == len(second_targets),
                  "в витрине: %d, вставлено: %d" % (current_view_rows, len(second_targets)))
            check("%s: витрина применения перестаёт отдавать строки прежней ревизии"
                  % TARGETS_VIEW, old_view_rows == 0, "строк в витрине: %d" % old_view_rows)
            check("%s: строки применения прежней ревизии остаются в таблице — своей цепи у "
                  "них нет, они снимаются вместе со своей ревизией" % TARGETS_TABLE,
                  old_table_rows == len(second_targets),
                  "строк в таблице: %d" % old_table_rows)
        else:
            note("%s: у первой строки круга нет строк применения — витрина применения и "
                 "сохранение строк прежней ревизии читаются на выгрузке, где применение "
                 "есть (замер 2.1: 2/0/6/26 целей)" % name)
        cur.execute("SAVEPOINT v57_p4_undo")
        try:
            cur.execute("DELETE FROM " + TABLE + " WHERE configuration_uuid = %s "
                        "AND object_name = %s AND revision_no = %s",
                        (cfg_uuid, object_name, FIRST_REVISION + 1))
            back = int(one(cur, "SELECT count(*) FROM " + TARGETS_VIEW
                             + " WHERE functional_option_parameter_id = %s",
                             (first_id,)) or 0)
            check("снятие второй ревизии возвращает витрину параметров к первой ревизии, а "
                  "витрину применения — к её строкам", back == old_table_rows,
                  "в витрине: %d, в таблице: %d" % (back, old_table_rows))
        finally:
            cur.execute("ROLLBACK TO SAVEPOINT v57_p4_undo")
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v57_p4_chain")


def run_dump(name):
    """Прогон одной выгрузки: разбор → запись круга → сверка с таблицами и витринами → откат.

    Транзакция откатывается, а базовое состояние таблиц сверяется НОВЫМ соединением: проба
    П4 не имеет права оставить в базе строки, потому что их записывает стадия П5, и два
    источника одного круга — это два ответа об одном круге (правило V43).
    """
    dump_dir = DUMP_ROOT / name
    print("\n" + "=" * 78)
    print("ПРЕДМЕТ: " + str(dump_dir))
    print("=" * 78)
    if not dump_dir.is_dir():
        check("%s: каталог выгрузки существует" % name, False, str(dump_dir))
        return
    uuid_info = configuration_uuid_from_layout(str(dump_dir))
    if "uuid" not in uuid_info:
        check("%s: uuid конфигурации прочитан из Configuration.xml" % name, False,
              uuid_info.get("error"))
        return
    cfg_uuid = uuid_info["uuid"]
    check("%s: uuid конфигурации прочитан из Configuration.xml" % name, True, cfg_uuid)

    before = None
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM configurations WHERE uuid = %s", (cfg_uuid,))
        header_row = cur.fetchone()
        if not header_row:
            check("%s: заголовок конфигурации загружен (порог слоя V57)" % name, False,
                  "строки заголовка в `configurations` нет — свойства круга остались бы ни "
                  "на что не указывающими (узел V20.1)")
            return
        configuration_id = int(header_row[0])
        check("%s: заголовок конфигурации загружен" % name, True,
              "id=%d name=%s" % (configuration_id, header_row[1]))
        # Индекс состава читается тем же слоем, что и стадия: разрешение целей `<Use>` идёт
        # по строкам `configuration_objects`, а не по повторному разбору XML.
        index_rows, index_info = index_rows_of(cur, configuration_id)
        check("%s: индекс состава читается из `configuration_objects`" % name,
              bool(index_rows), index_info.get("reason")
              or ("записей %d, вида %d" % (len(index_rows), index_info.get("kind_count", 0))))
        collected = FOP.collect_functional_options_parameters(str(dump_dir),
                                                             index_rows=index_rows)
        check("%s: файлы вида разбираются без отказов" % name, collected["success"],
              collected["files_failed"][:2] if collected["files_failed"] else 0)
        counts = parse_counts_of(collected)
        expected = BASELINE_ROWS[name]
        check("%s: круг вида совпадает с базовой линией плана (%d + %d)"
              % (name, expected[TABLE], expected[TARGETS_TABLE]),
              counts[TABLE] == expected[TABLE]
              and counts[TARGETS_TABLE] == expected[TARGETS_TABLE],
              "разбор: %d + %d, план: %d + %d"
              % (counts[TABLE], counts[TARGETS_TABLE], expected[TABLE],
                 expected[TARGETS_TABLE]))
        check("%s: неразрешённых целей применения нет (замер 2.1: 34/34 `exact`)" % name,
              collected["unresolved_targets_total"] == 0,
              "неразрешённых: %d" % collected["unresolved_targets_total"])
        if name == "KomMag":
            observed = set(str(item[0]) for item in (collected.get("observations") or []))
            check("KomMag: пустой круг назван наблюдением `directory_missing`, а не нулями "
                  "и не отказом (Q9, вариант A)", "directory_missing" in observed,
                  ", ".join(sorted(observed)) or "наблюдений нет")
        check_contract_matches_writer(collected)


        # Инвариант тот же, что у проб П3/P4 узлов V48–V56: таблицы не пустуют — стадии
        # конвейера и проба П6 пишут реальный состав. Проверяемое свойство не изменилось:
        # проба ничего не меняет в базе. Базовое состояние читается ДО записи, снятие идёт
        # по кругу этой конфигурации, откат обязан вернуть ровно прочитанное до состояние.
        before = table_baseline(cur, cfg_uuid)
        for table in TABLES:
            if before[table][1]:
                note("%s: в таблице уже есть %d строк этой конфигурации — они сняты внутри "
                     "транзакции пробы и вернутся после отката" % (table, before[table][1]))
        written, removed, moment, ids_by_key = write_all(cur, cfg_uuid, collected)
        for table in TABLES:
            check("%s: прежние строки этой конфигурации сняты внутри транзакции" % table,
                  removed.get(table) == before[table][1],
                  "снято %d, ожидалось %d" % (removed.get(table, 0), before[table][1]))
        check_written(cur, cfg_uuid, name, collected, written, moment)
        check_link_integrity(cur, cfg_uuid, name)
        check_round_trip(cur, cfg_uuid, collected, ids_by_key)
        check_named_constraints(cur, cfg_uuid, name, collected, ids_by_key)
        check_chain(cur, cfg_uuid, name, collected, ids_by_key)
        conn.rollback()
        check("транзакция откатана", True, "строк в базу не попало")
    except psycopg2.Error as exc:
        conn.rollback()
        # Отказ называется запросом, а не только сообщением: без текста SQL проба
        # осталась бы описанием ошибки, а не местом, где она возникла.
        query_text = ""
        if getattr(exc, "query", None):
            query_text = str(exc.query).replace("\n", " ")[:400]
        check("запись круга прошла без ошибки схемы", False,
              str(exc).splitlines()[0][:300] + (" | SQL: " + query_text if query_text else ""))
    finally:
        conn.close()

    if before is None:
        return
    conn_after = connect()
    try:
        after = table_baseline(conn_after.cursor(), cfg_uuid)
        bad = [table for table in TABLES if after[table] != before[table]]
        check("после отката обе таблицы вернулись к базовому состоянию", not bad,
              "; ".join("%s: всего %d (было %d), этой конфигурации %d (было %d)"
                        % (table, after[table][0], before[table][0], after[table][1],
                           before[table][1]) for table in bad) or "состояние совпадает")
    finally:
        conn_after.close()


def main():
    print("ПРОГОН V57 (П4): писатели круга параметров функциональных опций")
    print("писатели: FunctionalOptionsParametersRowWriter, "
          "FunctionalOptionParameterTargetRowWriter (src/external_table_writer.py); "
          "разбор: src/configuration_functional_options_parameters.py; "
          "круг контракта: FUNCTIONAL_OPTION_PARAMETERS_TABLES / _REMOVE_ORDER")
    check_registries()
    check_stage_circle()
    conn = connect()
    try:
        cursor = conn.cursor()
        check_writer_specs(cursor)
        check_state_vocabularies(cursor)
    finally:
        conn.close()
    for name in ONLY:
        run_dump(name)
    print("\nИТОГ: пройдено " + str(PASSED) + ", провалено " + str(FAILED)
          + ", заметок " + str(len(NOTES)))
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())

