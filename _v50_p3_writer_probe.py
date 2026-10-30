#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Шаг П3 узла V50: прогон писателей группы `common_attributes` в живую схему.

Предмет — путь ЗАПИСИ. Офлайн-прогон П2 (`_v50_p2_offline_probe.py`) отвечал на вопрос
«что мы знаем о выгрузке»; этот отвечает на «знаемое доходит до двух таблиц без потерь и без
домыслов». Проверяются обе таблицы узла сразу, потому что круг узла — именно круг (Q1,
вариант A): строка реквизита без строк применения не отвечает на «где применяется», а строка
применения без строки реквизита ниоткуда не берётся.

Отдельные проверки, которых нет в `tools/check_v19_revisions.py`:

  * спецификация каждого из двух писателей совпадает с живой схемой: объявленная колонка
    существует, а каждая NOT NULL-колонка без DEFAULT объявлена писателем (иначе вставка
    упала бы на NULL, и виновата была бы не выгрузка);
  * круг писателей = круг версионных таблиц ПЛЮС именованное исключение
    `CONFIGURATION_UNVERSIONED_TABLES` (`common_attribute_targets`: своей цепи ревизий у неё
    нет — Q2, вариант A). С узла V49 формулировка «ровно» была бы ложью;
  * круг стадии S4 не тронут регистрацией вида: `COMMON_ATTRIBUTES_TABLES` вычтены из
    `CHILD_TABLES` контракта (замер 30.10.2026: без этой константы
    `_v46_p4_writer_probe.py` падает на `KeyError: 'common_attributes'`);
  * закрытые словари состояний вида (`STATE_VOCABULARIES` разбора) сверяются с CHECK живой
    схемы по имени колонки — в обеих формах предиката (`col IN (...)` и
    `col = ANY (ARRAY[...])`), потому что домены `*_resolve_state` в этой схеме живут внутри
    парных `*_ref_matches_state`, а не отдельным ограничением;
  * словарных доменов у свойств вида (`fill_checking`, `auto_use`, `data_separation`,
    `indexing`, …) в схеме НЕТ — это решение Q7 (вариант A), и его отсутствие проверяется
    как свойство, а не предполагается;
  * каждое состояние из словаря записывается ЧЕРЕЗ ПИСАТЕЛЯ и принимается схемой —
    «словарь совпадает» и «словарь достижим» суть разные факта;
  * каждое нарушение называется ограничением по имени (замер 2.10 повторяется на пути
    записи), включая пары «состояние ↔ содержимое» (`common_attributes_value_ref_matches_state`,
    `common_attributes_content_state_matches_targets`,
    `common_attributes_targets_counters_match`, `common_attributes_unknown_names_match_state`,
    `common_attributes_type_multiplicity_matches_types`,
    `common_attribute_targets_resolve_matches_reference`);
  * round-trip: значения возвращаются из таблицы ровно теми, что отдал разбор, по ВСЕМ
    колонкам обеих таблиц и для ВСЕХ строк круга — сравнение идёт по типам спецификации
    писателя (`text`, `bool`, `int`, `uuid`, `jsonb`, `text_array`), потому что иначе
    «значение дошло» проверялось бы только для колонок, которые кто-то вспомнил;
  * цепочка состояния: повтор ревизии отклонён, тот же `object_name` в ДРУГОЙ конфигурации
    принят, тот же `object_uuid` в ДРУГОЙ конфигурации принят (замер 2.8: 7 имён вида имеют
    идентичные uuid в BGU2 и BP3 — ключ без границы по конфигурации принял бы их одной
    строкой), вторая ревизия продолжает цепочку и становится текущей, а витрина строк
    применения перестаёт отдавать применения прежней ревизии — при том что сами строки
    остаются в таблице (Q2, вариант A).

Транзакция в конце ОТКАТЫВАЕТСЯ намеренно. Инвариант — тот же, что у проб П3 узлов V48 и
V49: пустота таблиц инвариантом не является, поэтому базовое состояние читается ДО записи,
а после отката новым соединением сверяется равенство числа строк — всего и строк этой
конфигурации — по обеим таблицам.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v50_p3_writer_probe.py [MinCfg|KomMag|BGU2|BP3]
Код возврата 0 — расхождений нет. Прогоны, меняющие состояние БД, не паралелятся.
"""

import re
import sys
import uuid as uuid_module
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import psycopg2  # noqa: E402

import configuration_common_attributes as CA  # noqa: E402
from config_dump_info_parser import find_config_dump_info, parse_config_dump_info  # noqa: E402
from configuration_root_module_loader import configuration_uuid_from_layout  # noqa: E402
from current_revision import (  # noqa: E402
    CHANGED_BY_EDIT, CHANGED_BY_LOAD, CHANGED_BY_RESTORE, COMMIT_FLAG_COLUMN,
    CONFIGURATION_VERSIONED_TABLES, FIRST_REVISION, REVISION_COLUMNS, current_view,
    stamp_revision_rows, table_name,
)
from external_db import connect  # noqa: E402
from external_table_writer import (  # noqa: E402
    CONFIGURATION_OBJECT_WRITERS, CONFIGURATION_UNVERSIONED_TABLES,
)

TABLE = CA.TABLE_NAME
TARGETS_TABLE = CA.TARGETS_TABLE_NAME
TABLES = (TABLE, TARGETS_TABLE)
# Круг узла по версионности: свою цепь ведёт строка реквизита, у строк применения её нет
# (Q2, вариант A) — ключ начинается с `common_attribute_id`.
NODE_VERSIONED = (TABLE,)
NODE_UNVERSIONED = (TARGETS_TABLE,)
# Полный круг таблиц без своей цепи, каким его задают узлы V49 и V50: строки права (V49) и
# строки применения (V50). Список общий для всех писателей, поэтому сравнение прогона идёт
# с ним целиком, а не с кругом одного узла: третья таблица в списке означала бы, что чью-то
# версионность сняли молча, а отсутствие в нём строки применения — что её версионность
# кто-то добавил, не назвав причин (Q2, вариант A).
EXPECTED_UNVERSIONED = ("role_rights", TARGETS_TABLE)
VIEWS = dict((table, "v_current_" + table) for table in NODE_VERSIONED)
TARGETS_VIEW = "v_current_" + TARGETS_TABLE

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
ONLY = tuple(arg for arg in sys.argv[1:] if arg in DUMPS)

# Базовая линия записываемых строк — числа плана (docs/CONFIGURATION_COMMON_ATTRIBUTES_PLAN.md,
# разделы 2.1 и 2.4: 16 файлов и 1 512 строк применения на корпус; повторный прогон П2 обязан
# дать те же значения). Проба сверяет с ними то, что отдал разбор, и то, что легло в таблицу и
# в витрину: расхождение видно по имени таблицы. У KomMag позиции вида нет ни файлами, ни
# строками индекса (замер 2.9) — пустой круг является состоянием выгрузки, а не отказом.
BASELINE_ROWS = {
    "MinCfg": {TABLE: 2, TARGETS_TABLE: 3},
    "KomMag": {TABLE: 0, TARGETS_TABLE: 0},
    "BGU2": {TABLE: 7, TARGETS_TABLE: 692},
    "BP3": {TABLE: 7, TARGETS_TABLE: 817},
}

# Колонки, которых в контракте разбора нет по замыслу: их подставляет вызывающий слой.
LOADER_SUPPLIED = {
    TABLE: set(["configuration_uuid"]),
    TARGETS_TABLE: set(["configuration_uuid", "common_attribute_id"]),
}

# Связь разбора остаётся колонкой ОСОЗНАННО (в отличие от `role_name` узла V49, где связь
# колонкой не становилась): `attribute_full_name` и `attribute_object_uuid` — указатель на
# реквизит в форме индекса состава, он читается и тогда, когда строка реквизита снята.
LINK_COLUMNS_OF = {TARGETS_TABLE: ("attribute_full_name", "attribute_object_uuid")}

# Домены состояний, принадлежащие ЦЕПИ СОСТОЯНИЯ, а не виду: их словарь задаёт точка
# доступа `src/current_revision.py`, и сверять его со словарём разбора — значит искать не
# там. Проверка всё равно выполняется: схема обязана разрешать ровно те события, которые
# умеет называть точка доступа.
REVISION_STATE_COLUMNS = frozenset({"changed_by"})
REVISION_STATE_VALUES = (CHANGED_BY_LOAD, CHANGED_BY_EDIT, CHANGED_BY_RESTORE)

# Две формы домена состояний в CHECK. `col = ANY (ARRAY[...])` — форма миграций V46–V49;
# `col IN (...)` — форма, которой написан DDL узла V50 (замер П1), и внутри неё домены
# `*_resolve_state` лежат в составе парных ограничений, а не отдельным предикатом.
DOMAIN_RES = (
    re.compile(r"([a-z_][a-z0-9_]*)\s*=\s*ANY\s*\(\s*ARRAY\[(.*?)\]\s*\)", re.S),
    re.compile(r"([a-z_][a-z0-9_]*)\s+IN\s*\(([^)]*)\)", re.S),
)
VALUE_RE = re.compile(r"'((?:[^']|'')*)'(?:::[A-Za-z_ ]+)?")

PASSED = 0
FAILED = 0
NOTES = []


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


# ── статическая часть: круг писателей и их спецификации ─────────────────────────────
def check_registry():
    print("\n=== писатели узла и круг версионных таблиц ===")
    expected = sorted(set(CONFIGURATION_VERSIONED_TABLES)
                      | set(CONFIGURATION_UNVERSIONED_TABLES))
    check("словарь писателей покрывает круг версионных таблиц плюс именованное исключение",
          sorted(CONFIGURATION_OBJECT_WRITERS) == expected,
          ", ".join(sorted(CONFIGURATION_OBJECT_WRITERS)))
    check("исключение названо и совпадает с полным кругом таблиц без своей цепи (V49+V50)",
          sorted(CONFIGURATION_UNVERSIONED_TABLES) == sorted(EXPECTED_UNVERSIONED),
          ", ".join(CONFIGURATION_UNVERSIONED_TABLES))
    check("строки применения узла названы в этом списке, а не обходятся молча (Q2, A)",
          TARGETS_TABLE in CONFIGURATION_UNVERSIONED_TABLES,
          ", ".join(CONFIGURATION_UNVERSIONED_TABLES))
    for table in TABLES:
        writer = CONFIGURATION_OBJECT_WRITERS.get(table)
        if writer is None:
            check("%s: писатель объявлен" % table, False, "в словаре нет класса")
            continue
        check("%s: TABLE писателя совпадает с ключом словаря" % table,
              writer.TABLE == table, writer.TABLE)
        has_revision = all(column in writer.COLUMNS for column in REVISION_COLUMNS)
        check("%s: версионность спецификации совпадает с кругом узла" % table,
              has_revision == (table in NODE_VERSIONED)
              and writer.versioned() == (table in NODE_VERSIONED),
              "колонок ревизии: %d" % sum(1 for c in REVISION_COLUMNS
                                          if c in writer.COLUMNS))
        check("%s: писатель не объяляет вычисляемых колонок (id)" % table,
              "id" not in writer.COLUMNS, "%d колонок" % len(writer.COLUMNS))
    for table in NODE_VERSIONED:
        check("%s: витрина текущего состояния названа точкой доступа" % table,
              current_view(table) == VIEWS[table], current_view(table))
    for label, call in (("current_view", current_view), ("table_name", table_name)):
        try:
            call(TARGETS_TABLE)
            check("%s для %s отвечает отказом (цепи нет — Q2 A)" % (label, TARGETS_TABLE),
                  False, "значение получено молча")
        except ValueError as exc:
            check("%s для %s отвечает отказом (цепи нет — Q2 A)" % (label, TARGETS_TABLE),
                  True, str(exc).splitlines()[0][:120])
    # Круг стадии S4: регистрация вида в круге версионности не вправе расширять круг чужой
    # стадии — иначе снятие строк и ANALYZE чужих таблиц уходит в стадию S4 (замер П1: без
    # `COMMON_ATTRIBUTES_TABLES` проба `_v46_p4_writer_probe.py` падает на KeyError).
    import configuration_load_contract as CLC
    check("контракт называет круг стадии V50 своими таблицами",
          set(CLC.COMMON_ATTRIBUTES_TABLES) == set(TABLES),
          ", ".join(CLC.COMMON_ATTRIBUTES_TABLES))
    leaked = sorted(table for table in TABLES if table in CLC.CHILD_TABLES)
    check("круг стадии S4 не включает таблиц вида V50", not leaked,
          ", ".join(leaked) if leaked else "CHILD_TABLES: %d таблиц" % len(CLC.CHILD_TABLES))


def check_writer_matches_schema(cur):
    """Спецификации двух писателей против живой схемы (information_schema).

    Две ошибки, которые иначе видны только отказом вставки: писатель объявляет колонку,
    которой в схеме нет (опечатка в имени читается как «нет такого столбца»), и писатель НЕ
    объявляет обязательную колонку — тогда вставка падает на NOT NULL, и виновата не
    выгрузка, а спецификация. Отдельно читается витрина строк применения: своей цепи у
    таблицы нет, поэтому её имя не даёт `current_view()`, а существование связки — предмет
    проверки (прецедент витрины прав узла V49).
    """
    print("\n=== спецификации писателей против живой схемы ===")
    for table in TABLES:
        writer = CONFIGURATION_OBJECT_WRITERS[table]
        cur.execute(
            "SELECT column_name, is_nullable, column_default FROM information_schema.columns "
            "WHERE table_name = %s ORDER BY ordinal_position", (table,))
        schema = {}
        for row in cur.fetchall():
            schema[row[0]] = (row[1], row[2])
        check("%s: таблица узла П1 существует в живой схеме" % table, bool(schema),
              "%d колонок" % len(schema))
        undeclared = sorted(set(writer.COLUMNS) - set(schema))
        check("%s: писатель не объявляет колонок, которых нет в схеме" % table,
              not undeclared, ", ".join(undeclared) if undeclared
              else "колонок в спецификации: %d" % len(writer.COLUMNS))
        required = sorted(name for name, (nullable, default) in schema.items()
                          if nullable == "NO" and default is None and name != "id")
        missing = sorted(name for name in required if name not in writer.COLUMNS)
        check("%s: каждая NOT NULL-колонка без DEFAULT объявлена писателем" % table,
              not missing, "обязательных %d, не объявлено: %s"
              % (len(required), ", ".join(missing) if missing else "нет"))
        outside = sorted(name for name in schema
                         if name not in writer.COLUMNS and name != "id")
        note("%s: обязательных без DEFAULT — %d; вне спецификации (их даёт DEFAULT или "
             "последовательность) — %s"
             % (table, len(required), ", ".join(outside) if outside else "нет"))
    cur.execute("SELECT table_name FROM information_schema.views WHERE table_schema = "
                "current_schema() AND table_name = ANY(%s)",
                (list(VIEWS.values()) + [TARGETS_VIEW],))
    got = set(row[0] for row in cur.fetchall())
    for table in NODE_VERSIONED:
        check("%s: витрина существует" % VIEWS[table], VIEWS[table] in got)
    check("%s: витрина строк применения существует, хотя имя её не даёт current_view "
          "(связка Q2 A)" % TARGETS_VIEW, TARGETS_VIEW in got)
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                (TARGETS_VIEW,))
    view_columns = set(row[0] for row in cur.fetchall())
    missing_link = sorted(set(CONFIGURATION_OBJECT_WRITERS[TARGETS_TABLE].COLUMNS)
                          - view_columns)
    check("%s отдаёт все колонки строки применения, включая `use_state` и порядок"
          % TARGETS_VIEW, not missing_link,
          ", ".join(missing_link) if missing_link else "колонок: %d" % len(view_columns))


def schema_state_domains(cur):
    """Домены состояний из CHECK живой схемы: {таблица: {колонка: [(имя, значения)]}}.

    Значения по одной колонке объединяются из всех ограничений, где она названа: в DDL узла
    V50 домен `*_resolve_state` назван и полным списком (в ветви `parsed` парного
    ограничения), и укороченным (в проверке «ссылка есть только у разрешённого») — сравнение
    по объединению даёт полный домен колонки, а имена ограничений называются ответом, чтобы
    было видно, ГДЕ именно он лежит.
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
    """Словари состояний вида против CHECK схемы — по имени колонки (шаг П3).

    Две стороны одного расхождения: состояние в CHECK, которого разбор не отдаёт никогда, —
    мёртвая ветка ограничения; состояние в словаре разбора, которого нет в CHECK, — отказ
    загрузки круга. Поэтому сравниваются МНОЖЕСТВА значений, а не наличие слова в тексте.
    """
    print("\n=== словари состояний вида против CHECK живой схемы ===")
    domains = schema_state_domains(cur)
    for column, states in sorted(CA.STATE_VOCABULARIES.items()):
        table = CA.STATE_VOCABULARY_TABLES[column]
        found = domains.get(table, {}).get(column, [])
        if not found:
            check("%s.%s: в схеме есть домен состояний этого столбца" % (table, column),
                  False, "предикатов не найдено")
            continue
        values = set()
        for _conname, found_values in found:
            values |= found_values
        check("%s.%s: словарь разбора совпадает с доменом CHECK (%s)"
              % (table, column, ", ".join(sorted(set(n for n, _v in found)))),
              values == set(states),
              "словарь %d, схема %d; только в словаре: %s; только в схеме: %s"
              % (len(states), len(values),
                 ", ".join(sorted(set(states) - values)) or "нет",
                 ", ".join(sorted(values - set(states))) or "нет"))
    extra = []
    for table in TABLES:
        for column, found in domains.get(table, {}).items():
            if column in CA.STATE_VOCABULARIES:
                continue
            if column in REVISION_STATE_COLUMNS:
                # Домен `changed_by` принадлежит цепи состояния, а не виду: его словарь
                # живёт в `src/current_revision.py` (CHANGED_BY_*), и сверяется здесь с ним,
                # а не со словарём разбора. Молча убрать колонку из проверки — значит не
                # заметить, что схема разрешает событие, которого точка доступа не знает.
                values = set()
                for _conname, found_values in found:
                    values |= found_values
                check("%s.%s: домен события цепи совпадает со словарём точки доступа"
                      % (table, column), values == set(REVISION_STATE_VALUES),
                      "схема %s, точка доступа %s"
                      % (sorted(values), sorted(REVISION_STATE_VALUES)))
                continue
            extra.append("%s.%s" % (table, column))
    check("в схемах узла нет домена состояний, которого нет в словаре разбора или точки "
          "доступа цепи",
          not extra, ", ".join(sorted(extra)) if extra
          else "доменов: %d" % sum(len(d) for d in domains.values()))
    # Обратная сторона Q7 (вариант A): у значений СВОЙСТВ вида домена в схеме нет —
    # закрытость замкнута измеренным корпусом (`PROPERTY_VALUE_DICTIONARY`), а значение вне
    # него остаётся значением с состоянием `unknown_value` и именем виновника. Отсутствие
    # проверяется как свойство схемы: «просто нет строки в словаре» не отличило бы
    # задуманное от потерянного при правке миграции.
    dictionary_leaks = sorted(column for column in CA.PROPERTY_VALUE_DICTIONARY
                              if column in domains.get(TABLE, {}))
    check("словарные свойства вида не получают домена CHECK в схеме (Q7, вариант A)",
          not dictionary_leaks,
          ", ".join(dictionary_leaks) if dictionary_leaks
          else "словарных свойств: %d, доменов по ним: 0"
          % len(CA.PROPERTY_VALUE_DICTIONARY))


def check_contract_matches_writer(report, baseline):
    """Ключи контракта разбора против спецификаций писателей: расхождение видно по именам."""
    print("\n=== ключи контракта разбора против спецификаций писателей ===")
    for table, rows in ((TABLE, report["rows"]), (TARGETS_TABLE, report["targets"])):
        writer = CONFIGURATION_OBJECT_WRITERS[table]
        declared = set(writer.COLUMNS) - set(REVISION_COLUMNS) - LOADER_SUPPLIED[table]
        if not rows:
            # Пустая группа не даёт ни одного ключа, и сравнение множеств молча
            # превратилось бы в «писатель лишён колонок». Пустота называется отдельной
            # строкой и сверяется с базовой линией: «позиции вида в выгрузке нет» и
            # «разбор их не собрал» — разные состояния, и путать их нельзя.
            check("%s: группа пуста в этой выгрузке — ключи не сравниваются, "
                  "пустота совпадает с базовой линией (%d)" % (table, baseline.get(table, 0)),
                  baseline.get(table, 0) == 0, "строк разбора: 0")
            continue
        produced = set()
        for row in rows:
            produced.update(row)
        extra = sorted(produced - declared)
        missing = sorted(declared - produced)
        check("%s: контракт разбора и спецификация писателя совпадают" % table,
              not extra and not missing,
              "лишних: %s; не производятся: %s"
              % (", ".join(extra) if extra else "нет",
                 ", ".join(missing) if missing else "нет"))
        for column in LINK_COLUMNS_OF.get(table, ()):
            check("%s: %s остаётся колонкой осознанно (указатель на реквизит в форме "
                  "индекса состава, Q2 A)" % (table, column),
                  column in produced and column in writer.COLUMNS)
        if table == TARGETS_TABLE:
            check("%s: связь со строкой реквизита идёт через id ревизии, а не только через "
                  "имя (common_attribute_id обязателен)" % table,
                  "common_attribute_id" in writer.COLUMNS
                  and "common_attribute_id" not in produced)


# ── запись круга: тот же контракт, что отдаёт разбор П2 ──────────────────────────────
def write_all(cur, cfg_uuid, report):
    """Записать круг узла одной транзакцией; вернуть числа, момент и связь id ревизии.

    Порядок один для обеих таблиц: снять прежнее состояние этой конфигурации, проставить
    ОДИН штамп ревизии (M2), вставить строки реквизитов и получить их id, подставить id
    ревизии в строки применения. Строки применения существуют только через id строки
    реквизита (Q2, вариант A), поэтому `insert_ids` — часть круга, а не деталь реализации.
    Ключом подстановки служит индексное имя (`CommonAttribute.<Имя>`), а не `object_name`:
    именно в этой форме связь несёт строка применения (прецедент `role_name` узла V49).
    """
    attribute_rows = [dict(row, configuration_uuid=cfg_uuid) for row in report["rows"]]
    moment = stamp_revision_rows(attribute_rows, revision_no=FIRST_REVISION,
                                 changed_by=CHANGED_BY_LOAD)
    ids = CONFIGURATION_OBJECT_WRITERS[TABLE].insert_ids(cur, attribute_rows)
    attribute_ids = {}
    without_id = []
    for row, record_id in zip(attribute_rows, ids):
        if record_id is None:
            without_id.append(row["object_name"])
        else:
            attribute_ids[CA.index_object_name(row["object_name"])] = record_id
    target_rows = []
    unbound = []
    for row in report["targets"]:
        record_id = attribute_ids.get(row["attribute_full_name"])
        if record_id is None:
            unbound.append(row["attribute_full_name"])
            continue
        prepared = dict(row)
        prepared["common_attribute_id"] = record_id
        prepared["configuration_uuid"] = cfg_uuid
        target_rows.append(prepared)
    written = {
        TABLE: len(attribute_rows),
        TARGETS_TABLE: CONFIGURATION_OBJECT_WRITERS[TARGETS_TABLE].insert_many(
            cur, target_rows),
    }
    return written, moment, attribute_ids, target_rows, unbound, without_id


def state_counts(cur, table, column, cfg_uuid):
    """Распределение состояния по таблице для одной конфигурации (нулевые значения не
    включаются: ответ разбора называет нули ключами, таблица — их не хранит)."""
    cur.execute("SELECT %s, count(*) FROM %s WHERE configuration_uuid = %%s GROUP BY 1"
                % (column, table), (cfg_uuid,))
    return dict((row[0], int(row[1])) for row in cur.fetchall() if row[0] is not None)


def distribution_from_rows(rows, column):
    """То же распределение, но по строкам разбора: сравнение идёт с ответом П2, а не с
    собственной выдумкой прогона."""
    counts = {}
    for row in rows:
        value = row.get(column)
        if value is not None:
            counts[value] = counts.get(value, 0) + 1
    return counts


def check_written(cur, cfg_uuid, name, report, written, unbound, without_id):
    """Числа записанного круга и распределения состояний — против ответа разбора."""
    print("\n--- записанный круг: числа и распределения состояний ---")
    baseline = BASELINE_ROWS[name]
    for table, key in ((TABLE, "rows"), (TARGETS_TABLE, "targets")):
        expected_rows = baseline[table]
        check("%s: писатель вернул число строк, равное базовой линии (%d)"
              % (table, expected_rows), written[table] == expected_rows,
              "писатель %d" % written[table])
        stored = int(one(cur, "SELECT count(*) FROM " + table
                            + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0)
        parsed = len(report[key])
        check("%s: в таблице строк этой конфигурации ровно столько, сколько отдал разбор"
              % table, stored == parsed and stored == expected_rows,
              "таблица %d, разбор %d, базовая линия %d"
              % (stored, parsed, expected_rows))
        view = VIEWS[table] if table in VIEWS else TARGETS_VIEW
        shown = int(one(cur, "SELECT count(*) FROM " + view
                          + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0)
        check("%s: витрина %s отдаёт весь круг этой конфигурации (первая ревизия — "
              "текущая)" % (table, view), shown == expected_rows,
              "витрина %d, таблица %d" % (shown, stored))
    check("каждой строке применения подобрана строка реквизита (связь id не потерялась)",
          not unbound, "без связи: %d" % len(unbound))
    check("писатель вернул id для каждой строки реквизита (insert_ids)",
          not without_id, "без id: %s" % ", ".join(without_id))
    # Распределения состояний: ответ разбора обязан совпасть с таблицей по всем значениям
    # каждого закрытого словаря. Нули при этом различимы: «состояния нет» и «состояние
    # есть, но строк с ним ноль» — разные ответы, и пустой словарь здесь означает первое.
    for column, states in sorted(CA.STATE_VOCABULARIES.items()):
        table = CA.STATE_VOCABULARY_TABLES[column]
        rows = report["rows"] if table == TABLE else report["targets"]
        stored = state_counts(cur, table, column, cfg_uuid)
        wanted = distribution_from_rows(rows, column)
        check("%s.%s: распределение состояний совпадает с ответом разбора" % (table, column),
              stored == wanted, "таблица %s, разбор %s" % (stored, wanted))
        outside = sorted(set(stored) - set(states))
        check("%s.%s: таблица не содержит состояния вне словаря вида" % (table, column),
              not outside, ", ".join(outside) if outside
              else "значений: %d" % len(stored))


def check_link_integrity(cur, cfg_uuid, report):
    """Круг читается связками: применение висит на своей ревизии, счётчики сходятся."""
    print("\n--- целостность круга: связки и счётчики ---")
    broken = int(one(cur,
        "SELECT count(*) FROM " + TARGETS_TABLE + " t LEFT JOIN " + TABLE
        + " a ON a.id = t.common_attribute_id WHERE t.configuration_uuid = %s "
        "AND (a.id IS NULL OR a.configuration_uuid <> t.configuration_uuid)", (cfg_uuid,)) or 0)
    check("каждая строка применения ссылается на строку реквизита той же конфигурации",
          broken == 0, "связей вникуда: %d" % broken)
    mismatch = int(one(cur,
        "SELECT count(*) FROM " + TARGETS_TABLE + " t JOIN " + TABLE
        + " a ON a.id = t.common_attribute_id WHERE t.configuration_uuid = %s "
        "AND (lower(t.attribute_object_uuid::text) <> lower(a.object_uuid::text) "
        "OR t.attribute_full_name <> 'CommonAttribute.' || a.object_name)", (cfg_uuid,)) or 0)
    check("указатель реквизита в строке применения совпадает с его строкой "
          "(uuid и индексное имя)", mismatch == 0, "расхождений: %d" % mismatch)
    wrong_count = int(one(cur,
        "SELECT count(*) FROM " + TABLE + " a WHERE a.configuration_uuid = %s AND "
        "a.targets_count <> (SELECT count(*) FROM " + TARGETS_TABLE + " t WHERE "
        "t.common_attribute_id = a.id)", (cfg_uuid,)) or 0)
    # Число применений сверяется с перечнем строки реквизита. CHECK схемы связывает
    # счётчики между собой (`targets_counters_match`), но не их со строками применения —
    # такой связки в схеме нет осознанно (те же соображения, что у счётчиков `roles`
    # узла V49: ограничение требовало бы подзапроса к дочерней таблице в предикате
    # родительской). Равенство `targets_count` и числа строк применения сторожит
    # загрузчик, поэтому проверяется здесь, а не ограничением схемы.
    check("число применений совпадает с перечнем строки реквизита (связку держит "
          "загрузчик, CHECK на неё в схеме нет)", wrong_count == 0, "строк: %d" % wrong_count)
    wrong_use = int(one(cur,
        "SELECT count(*) FROM " + TABLE + " a WHERE a.configuration_uuid = %s AND "
        "(a.targets_used_count <> (SELECT count(*) FROM " + TARGETS_TABLE + " t WHERE "
        "t.common_attribute_id = a.id AND t.use_state = 'used') OR "
        "a.targets_not_used_count <> (SELECT count(*) FROM " + TARGETS_TABLE + " t WHERE "
        "t.common_attribute_id = a.id AND t.use_state = 'not_used'))", (cfg_uuid,)) or 0)
    check("счётчики `used`/`not_used` совпадают с числом строк применения (Q4 A)",
          wrong_use == 0, "строк: %d" % wrong_use)
    bad_types = int(one(cur,
        "SELECT count(*) FROM " + TABLE + " WHERE configuration_uuid = %s AND "
        "jsonb_array_length(types) = 1 AND type_multiplicity <> 'single'", (cfg_uuid,)) or 0)
    check("кратность типа согласована с числом записей `types` на данных круга",
          bad_types == 0, "строк: %d" % bad_types)
    separated = int(one(cur,
        "SELECT count(*) FROM " + TABLE + " WHERE configuration_uuid = %s AND "
        "data_separation_value_parse_state = 'parsed'", (cfg_uuid,)) or 0)
    wanted_separated = sum(1 for row in report["rows"]
                           if row["data_separation_value_parse_state"] == CA.SEP_PARSED)
    check("непустых ссылок разделения ровно столько, сколько насчитал разбор (замер 2.7)",
          separated == wanted_separated, "таблица %d, разбор %d"
          % (separated, wanted_separated))
    unresolved = int(one(cur,
        "SELECT count(*) FROM " + TARGETS_TABLE + " WHERE configuration_uuid = %s AND "
        "target_resolve_state <> 'exact'", (cfg_uuid,)) or 0)
    if unresolved:
        note("целей, разрешённых не целиком: %d (замер 2.6 на базовой линии даёт 0 — "
             "состояния `prefix_only`/`unresolved` остаются границей схемы)" % unresolved)
    else:
        check("на базовой линии все цели разрешаются индексом целиком (замер 2.6)", True,
              "строк с неразрешённой целью: 0")


def fetch_dicts(cur, sql, params=None):
    """Строки запроса словарями по именам колонок — сравнение идёт по колонкам, а не по
    позициям кортежа."""
    cur.execute(sql, tuple(params or ()))
    columns = [d[0] for d in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def expected_value(kind, value):
    """Что должно лежать в таблице по виду спецификации — своей независимой реализацией.

    Сверять себя с `_adapt` писателя бессмысленно: проверка сравнивает контракт разбора с
    содержимым таблицы, а не две копии одного кода. Пустые значения при этом ведут себя как
    в писателе: пустой перечень остаётся NULL (V43), пустой jsonb — NULL (V31), пустая
    строка — NULL.
    """
    if kind in ("text", "uuid"):
        if value is None:
            return None
        return (str(value).strip() or None)
    if kind == "bool":
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in ("true", "1"):
            return True
        if text in ("false", "0"):
            return False
        return None
    if kind == "jsonb_array":
        return list(value) if isinstance(value, list) else []
    if kind == "jsonb_object":
        return dict(value) if isinstance(value, dict) else {}
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
    строкой в нижнем регистре (прецедент V49)."""
    if kind == "uuid" and value is not None:
        return str(value).lower()
    return value


def check_round_trip(cur, cfg_uuid, report, attribute_ids):
    """Круговая проверка содержимого обеих таблиц (шаг 3, узел V49): каждая колонка
    писателя сравнивается с контрактом разбора.

    Сравнение идёт по колонкам спецификации, а не по ключам строки: именно так видна
    колонка, которую писатель читает, а разбор не отдаёт (она осталась бы NULL и не
    участвовала бы в сравнении по ключам строк).
    """
    print("\n--- круговая проверка содержимого (обе таблицы, все колонки) ---")
    compared = 0
    problems = []
    for table, key in ((TABLE, "rows"), (TARGETS_TABLE, "targets")):
        writer = CONFIGURATION_OBJECT_WRITERS[table]
        columns = sorted(set(writer.COLUMNS) - set(REVISION_COLUMNS))
        stored = {}
        for row in fetch_dicts(cur, "SELECT %s FROM %s WHERE configuration_uuid = %%s"
                                  % (", ".join(columns), table), (cfg_uuid,)):
            stored[row_key(table, row)] = row
        for parser_row in report[key]:
            got = stored.get(row_key(table, parser_row))
            if got is None:
                problems.append("%s: строки %s нет в таблице"
                                % (table, row_key(table, parser_row)))
                continue
            for column in columns:
                kind = writer.COLUMNS[column]
                if column in LOADER_SUPPLIED[table]:
                    want = expected_loader_value(column, cfg_uuid, parser_row, attribute_ids)
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
    print("  сравнение: %s колонок, %s колонок, значений %d"
          % (len(set(CONFIGURATION_OBJECT_WRITERS[TABLE].COLUMNS) - set(REVISION_COLUMNS)),
             len(set(CONFIGURATION_OBJECT_WRITERS[TARGETS_TABLE].COLUMNS)
                 - set(REVISION_COLUMNS)), compared))


def row_key(table, row):
    """Ключ, по которому строку разбора ищут в таблице: имя позиции вида для строк
    реквизита, пара (указатель, порядковый номер) для строк применения — строк применения у
    реквизита несколько, и по одному имени они слились бы в одну (прецедент V49, где ключом
    служила пара `role_name` + `ordinal`)."""
    if table == TABLE:
        return row["object_name"]
    return (row["attribute_full_name"], row["ordinal"])



def expected_loader_value(column, cfg_uuid, parser_row, attribute_ids):
    """Что подставляет загрузчик, а не разбор: uuid конфигурации и id строки реквизита."""
    if column == "configuration_uuid":
        return str(cfg_uuid).lower()
    if column == "common_attribute_id":
        return attribute_ids.get(parser_row["attribute_full_name"])
    raise KeyError("загрузчик подставляет только эти две колонки: %s" % column)


# ── случаи отказа: нарушение называется ограничением по имени ─────────────────────────
def probe_uuid(tag):
    """Устойчивый uuid пробной строки (один и тот же на повторных прогонах)."""
    return str(uuid_module.uuid5(uuid_module.UUID(int=0), "v50-p3-" + tag))


def probe_attribute_row(base, cfg_uuid, tag, **overrides):
    """Пробная строка реквизита: копия реальной с новой личностью и заданными полями.

    Копия, а не составленная с нуля строка: только так видно, что отклоняет ИМЕННО
    проверяемое сочетание полей, а не отсутствие чего-то, о чём прогон забыл подумать.
    """
    name = "_Проба_V50_" + tag
    row = dict(base)
    row.update({
        "configuration_uuid": cfg_uuid,
        "object_name": name,
        "full_name": name,
        "object_uuid": probe_uuid(tag),
        "source_path": "CommonAttributes/_Проба_V50_%s.xml" % tag,
    })
    row.update(overrides)
    stamp_revision_rows([row], revision_no=FIRST_REVISION, changed_by=CHANGED_BY_LOAD)
    return row


def probe_target_row(base, cfg_uuid, attribute_ids, tag, ordinal=9000, **overrides):
    """Пробная строка применения: копия реальной с другим порядковым номером.

    Номер меняется на заведомо свободный: копия строки применения с её же `ordinal`
    нарушила бы ключ `(common_attribute_id, ordinal)` раньше проверяемого ограничения, и
    прогон отчитался бы не о том отказе.
    """
    row = dict(base)
    row.update({
        "configuration_uuid": cfg_uuid,
        "common_attribute_id": attribute_ids.get(row["attribute_full_name"]),
        "ordinal": ordinal,
    })
    row.update(overrides)
    return row


def expect_violation(cur, label, table, row, constraints):
    """Нарушение читается именованным ограничением, а не текстом ошибки (приём V49).

    Имя ограничения psycopg2 отдаёт в `diag`, поэтому сравнивается именно оно: иначе
    прогон принимал бы любой отказ. `constraints` — имя или набор имён: пара значений
    может нарушать два ограничения согласованности, и какой из них отчитывается решает
    порядок проверки ограничений, а не замысел узла.
    """
    allowed = set([constraints]) if isinstance(constraints, str) else set(constraints)
    cur.execute("SAVEPOINT v50_p3_case")
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
        cur.execute("ROLLBACK TO SAVEPOINT v50_p3_case")


def expect_not_null(cur, label, table, row, column):
    """Отказ по обязательности колонки читается классом ошибки и именем колонки.

    Имени ограничения у такого отказа нет: `NOT NULL` в DDL узла живёт атрибутом колонки
    (`pg_attribute.attnotnull`), а не строкой `pg_constraint` — замеры 17.2 показывают,
    что ограничений с именем `<таблица>_<колонка>_not_null` в схеме нет ни у одной таблицы
    узла. Требовать имени значило бы выдумывать то, чего схема не даёт; при этом колонка
    в сообщении называется, и именно она является предметом отказа.
    """
    cur.execute("SAVEPOINT v50_p3_not_null")
    try:
        CONFIGURATION_OBJECT_WRITERS[table].insert(cur, row)
        check(label, False, "строка принята — обязательность колонки не сработала")
    except psycopg2.Error as exc:
        text = str(exc).splitlines()[0]
        ok = isinstance(exc, psycopg2.errors.NotNullViolation) and ('"%s"' % column) in text
        check(label + " — отказ назван колонкой", ok,
              "%s: %s" % (type(exc).__name__, text[:200]))
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v50_p3_not_null")


def expect_update_violation(cur, label, sql, params, constraints):
    """Ограничение схемы проверяется правкой уже записанной строки.

    Часть предикатов писатель не выражает: `text` из пустой строки даёт NULL, и
    `common_attributes_names_not_blank` до таблицы не доходит. Тогда ограничение
    проверяется прямой правкой — но правкой строки круга, а не отдельной вставкой, чтобы
    не пришлось заново собирать все остальные предикаты строки.
    """
    allowed = set([constraints]) if isinstance(constraints, str) else set(constraints)
    cur.execute("SAVEPOINT v50_p3_update")
    try:
        cur.execute(sql, params)
        check(label, False, "правка принята — ограничение не сработало")
    except psycopg2.Error as exc:
        name = getattr(getattr(exc, "diag", None), "constraint_name", None) \
            or getattr(exc, "constraint_name", None)
        check(label + " — имя из ожидаемого набора", name in allowed,
              "нарушено: " + (name or str(exc).splitlines()[0][:200])
              + "; ожидалось одно из " + ", ".join(sorted(allowed)))
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v50_p3_update")



def check_named_constraints(cur, cfg_uuid, name, baseline, report, attribute_ids):
    """Что отклоняет схема и как она это называет (шаг П3, узел V50)."""
    print("\n--- что отклоняет схема: нарушение называется ограничением ---")
    if not report["rows"] or not report["targets"]:
        if not baseline[TABLE] and not baseline[TARGETS_TABLE]:
            # Пустой круг является состоянием выгрузки (замер 2.9: у KomMag позиций вида нет
            # ни файлами, ни строками индекса), а не отказом прогона. Случаи здесь строить
            # не из чего — это называется, а не проходит молча, и называется, где именно они
            # проверяются.
            note("%s: позиций вида в этой выгрузке нет — случаи отказа здесь не строятся; "
                 "они проверяются на выгрузках, где круг есть (MinCfg, BGU2, BP3)" % name)
            return
        check("случаи отказа построены", False,
              "строк разбора нет: реквизитов %d, применений %d"
              % (len(report["rows"]), len(report["targets"])))
        return
    base = report["rows"][0]
    base_target = report["targets"][0]
    stored_id = int(one(cur, "SELECT id FROM " + TABLE
                           + " WHERE configuration_uuid = %s AND object_name = %s",
                           (cfg_uuid, base["object_name"])))
    stored_target_id = int(one(cur, "SELECT id FROM " + TARGETS_TABLE
                                  + " WHERE configuration_uuid = %s "
                                  "AND attribute_full_name = %s AND ordinal = %s",
                                  (cfg_uuid, base_target["attribute_full_name"],
                                   base_target["ordinal"])))

    # Круг писателя: строка применения без своей строки реквизита ниоткуда не берётся.
    expect_not_null(cur, "строка применения без id строки реквизита отклоняется",
                    TARGETS_TABLE,
                    probe_target_row(base_target, cfg_uuid, attribute_ids, "no_link",
                                     common_attribute_id=None),
                    "common_attribute_id")
    expect_violation(cur, "строка применения на несуществующую ревизию реквизита "
                          "отклоняется внешним ключом",
                     TARGETS_TABLE,
                     probe_target_row(base_target, cfg_uuid, attribute_ids, "bad_fk",
                                      common_attribute_id=999999999),
                     "common_attribute_targets_common_attribute_id_fkey")
    # Счётчики перечня применения (Q4, вариант A): равенство остаётся CHECK'ом схемы.
    expect_violation(cur, "несогласованные счётчики перечня отклоняются",
                     TABLE,
                     probe_attribute_row(base, cfg_uuid, "counters",
                                         targets_count=3, targets_used_count=2,
                                         targets_not_used_count=0,
                                         content_state=CA.CONTENT_WITH),
                     "common_attributes_targets_counters_match")
    expect_violation(cur, "состояние «есть применения» без применений отклоняется",
                     TABLE,
                     probe_attribute_row(base, cfg_uuid, "content",
                                         content_state=CA.CONTENT_WITH, targets_count=0,
                                         targets_used_count=0, targets_not_used_count=0),
                     "common_attributes_content_state_matches_targets")
    expect_violation(cur, "состояние «нет применений» с применениями отклоняется",
                     TABLE,
                     probe_attribute_row(base, cfg_uuid, "content_empty",
                                         content_state=CA.CONTENT_EMPTY, targets_count=2,
                                         targets_used_count=2, targets_not_used_count=0),
                     "common_attributes_content_state_matches_targets")
    # Виновник состояния свойств называется (Q7, вариант A).
    expect_violation(cur, "`all_known` с названными неизвестными свойствами отклоняется",
                     TABLE,
                     probe_attribute_row(base, cfg_uuid, "props_all",
                                         properties_state=CA.PROPS_ALL_KNOWN,
                                         unknown_property_names=["КакоеТоСвойство"]),
                     "common_attributes_unknown_names_match_state")
    expect_violation(cur, "состояние вне словаря свойств без виновника отклоняется",
                     TABLE,
                     probe_attribute_row(base, cfg_uuid, "props_unknown",
                                         properties_state=CA.PROPS_UNKNOWN_VALUE,
                                         unknown_property_names=None),
                     "common_attributes_unknown_names_match_state")
    # Тип: кратность против числа записей и пустой блок против состояния `absent`.
    entries = list(base.get("types") or [])
    if not entries:
        entries = [{"index": 0, "value": "xs:string", "ns_uri": CA.NS_XML_SCHEMA,
                    "class": CA.CLASS_PRIMITIVE, "state": CA.ENTRY_STATE_PARSED}]
    second = dict(entries[0])
    second["index"] = 1
    expect_violation(cur, "кратность `single` при двух записях типа отклоняется",
                     TABLE,
                     probe_attribute_row(base, cfg_uuid, "multiplicity",
                                         types=entries[:1] + [second],
                                         type_multiplicity=CA.MULT_SINGLE,
                                         type_parse_state=CA.STATE_PARSED),
                     "common_attributes_type_multiplicity_matches_types")
    expect_violation(cur, "пустой массив типов при кратности не `absent` отклоняется",
                     TABLE,
                     probe_attribute_row(base, cfg_uuid, "empty_types",
                                         types=[], type_multiplicity=CA.MULT_SINGLE,
                                         type_parse_state=CA.STATE_PARSED),
                     ("common_attributes_types_absent_matches_no_block",
                      "common_attributes_type_multiplicity_matches_types"))
    # Ссылка разделения: состояние и её содержимое согласуются (замер 2.7).
    expect_violation(cur, "пустое состояние разделения с текстом ссылки отклоняется",
                     TABLE,
                     probe_attribute_row(base, cfg_uuid, "sep_empty",
                                         data_separation_value_parse_state=CA.SEP_EMPTY,
                                         data_separation_value_ref_text="Catalog.Товары",
                                         data_separation_value_resolve_state=None,
                                         data_separation_value_object_id=None,
                                         data_separation_value_object_uuid=None),
                     "common_attributes_value_ref_matches_state")
    expect_violation(cur, "разрешённая ссылка разделения без идентификатора отклоняется",
                     TABLE,
                     probe_attribute_row(base, cfg_uuid, "sep_exact",
                                         data_separation_value_parse_state=CA.SEP_PARSED,
                                         data_separation_value_ref_text="Catalog.Товары",
                                         data_separation_value_resolve_state=CA.TARGET_EXACT,
                                         data_separation_value_object_id=None,
                                         data_separation_value_object_uuid=None),
                     "common_attributes_value_ref_matches_state")
    # Цель применения: состояние против её же отсылки.
    expect_violation(cur, "состояние `exact` с неразрешённым путём отклоняется",
                     TARGETS_TABLE,
                     probe_target_row(base_target, cfg_uuid, attribute_ids, "exact_path",
                                      target_resolve_state=CA.TARGET_EXACT,
                                      target_unresolved_path="Прочая.Путь"),
                     "common_attribute_targets_resolve_matches_reference")
    expect_violation(cur, "состояние `unresolved` с идентификатором цели отклоняется",
                     TARGETS_TABLE,
                     probe_target_row(base_target, cfg_uuid, attribute_ids, "unresolved",
                                      target_resolve_state=CA.TARGET_UNRESOLVED,
                                      target_object_id="Catalog.Товары",
                                      target_unresolved_path="Прочая.Путь"),
                     "common_attribute_targets_resolve_matches_reference")

    # Предикаты, которых писатель не выражает: пустые имена, нулевая ревизия, чужое
    # событие, не-массив в `types`, состояние вне закрытого словаря вида. Правка строки
    # круга называется каждой из них — молчаливого отказа здесь нет ни в одном случае.
    for label, column, value, expected in (
        ("пустое имя позиции вида отклоняется", "object_name", "",
         "common_attributes_names_not_blank"),
        ("пустое индексное имя позиции вида отклоняется", "full_name", "",
         "common_attributes_names_not_blank"),
        ("ревизия с номером ноль отклоняется", "revision_no", 0,
         "common_attributes_revision_no_positive"),
        ("событие вне словаря цепи состояния отклоняется", "changed_by", "import",
         "common_attributes_changed_by_known"),
        ("содержимое `types` не массивом отклоняется", "types", "{}",
         "common_attributes_types_is_array"),
        ("состояние разбора типа вне словаря вида отклоняется", "type_parse_state",
         "bogus", "common_attributes_type_parse_state_known"),
        ("состояние свойств вне словаря вида отклоняется", "properties_state", "bogus",
         "common_attributes_properties_state_known"),
        ("кратность типа вне словаря вида отклоняется", "type_multiplicity", "many",
         ("common_attributes_type_multiplicity_known",
          "common_attributes_type_multiplicity_matches_types")),
        ("состояние разделения вне словаря вида отклоняется",
         "data_separation_use_parse_state", "bogus",
         "common_attributes_separation_parse_states_known"),
    ):
        expect_update_violation(cur, label,
                                "UPDATE " + TABLE + " SET " + column + " = %s WHERE id = %s",
                                (value, stored_id), expected)
    for label, column, value, expected in (
        ("пустое имя цели применения отклоняется", "target_full_name", "",
         "common_attribute_targets_names_not_blank"),
        ("пустой вид цели применения отклоняется", "target_kind", "",
         "common_attribute_targets_names_not_blank"),
        ("пустой указатель позиции вида в строке применения отклоняется",
         "attribute_full_name", "", "common_attribute_targets_names_not_blank"),
        ("отрицательный порядковый номер применения отклоняется", "ordinal", -1,
         "common_attribute_targets_ordinal_non_negative"),
        ("состояние применения вне словаря вида отклоняется", "use_state", "bogus",
         "common_attribute_targets_use_state_known"),
        ("состояние цели вне словаря вида отклоняется", "target_resolve_state", "bogus",
         # Чужое состояние нарушает и домен, и парный предикат «состояние ↔ отсылка»:
         # какое из двух ограничений отчитается, решает порядок их проверки в схеме, а не
         # замысел узла, поэтому ожидаемый набор — оба (приём пары `types_absent_*`).
         ("common_attribute_targets_resolve_state_known",
          "common_attribute_targets_resolve_matches_reference")),
        ("состояние условия разделения вне словаря вида отклоняется",
         "conditional_separation_state", "bogus",
         "common_attribute_targets_conditional_state_known"),
    ):
        expect_update_violation(cur, label,
                                "UPDATE " + TARGETS_TABLE + " SET " + column
                                + " = %s WHERE id = %s", (value, stored_target_id),
                                expected)
    expect_update_violation(cur, "половина штампа ревизии отклоняется",
                            "UPDATE " + TABLE + " SET changed_by = NULL WHERE id = %s",
                            (stored_id,), "common_attributes_changed_pair_check")


def check_state_reachability(cur, cfg_uuid, name, baseline, report, attribute_ids):
    """Каждое состояние словаря вида записывается ЧЕРЕЗ ПИСАТЕЛЯ и принимается схемой.

    Сверка словарей с CHECK отвечает на «значения совпадают»; эта проверка отвечает на
    «значения достижимы»: состояние записывается строкой, которую собрал писатель, а не
    литералом из миграции. Иначе «словарь есть в двух местах» не отличалось бы от
    «словари расходятся при загрузке круга». Парные состояния (разрешение ссылки,
    счётчики, виновник свойств) задаются вместе с проверяемым — иначе отказ приписался бы
    проверяемому значению, а не отсутствию его пары.
    """
    print("\n--- каждое состояние словаря записывается через писателя ---")
    if not report["rows"] or not report["targets"]:
        if not baseline[TABLE] and not baseline[TARGETS_TABLE]:
            note("%s: позиций вида в этой выгрузке нет — состояния словарей через "
                 "писателя записываются на выгрузках, где круг есть (MinCfg, BGU2, BP3)"
                 % name)
            return
        check("состояния записываются через писателя", False,
              "строк разбора нет: реквизитов %d, применений %d"
              % (len(report["rows"]), len(report["targets"])))
        return
    base = report["rows"][0]
    base_target = report["targets"][0]
    entry = {"index": 0, "value": "xs:string", "ns_uri": CA.NS_XML_SCHEMA,
             "class": CA.CLASS_PRIMITIVE, "state": CA.ENTRY_STATE_PARSED}
    second_entry = dict(entry, index=1)
    variants = []

    # Тип: состояние разбора и кратность — парные с содержимым `types` (CHECK
    # `types_absent_matches_no_block` и `type_multiplicity_matches_types`).
    for state in CA.STATE_VOCABULARIES["type_parse_state"]:
        absent = state == CA.STATE_ABSENT
        variants.append((TABLE, "type_parse_state=" + state,
                         probe_attribute_row(base, cfg_uuid, "tps_" + state,
                                             type_parse_state=state,
                                             type_multiplicity=(CA.MULT_ABSENT if absent
                                                                else CA.MULT_SINGLE),
                                             types=[] if absent else [entry],
                                             type_qualifiers=None)))
    for multiplicity in CA.STATE_VOCABULARIES["type_multiplicity"]:
        count = {CA.MULT_ABSENT: 0, CA.MULT_SINGLE: 1}.get(multiplicity, 2)
        variants.append((TABLE, "type_multiplicity=" + multiplicity,
                         probe_attribute_row(base, cfg_uuid, "tm_" + multiplicity,
                                             type_multiplicity=multiplicity,
                                             type_parse_state=(CA.STATE_ABSENT
                                                               if not count
                                                               else CA.STATE_PARSED),
                                             types=[] if not count
                                             else [entry, second_entry][:count],
                                             type_qualifiers=None)))
    # Содержимое перечня применения: состояние и число названы вместе.
    for state in CA.STATE_VOCABULARIES["content_state"]:
        count = 1 if state == CA.CONTENT_WITH else 0
        variants.append((TABLE, "content_state=" + state,
                         probe_attribute_row(base, cfg_uuid, "cs_" + state,
                                             content_state=state, targets_count=count,
                                             targets_used_count=count,
                                             targets_not_used_count=0)))
    # Свойства: состояние и его виновник (Q7, вариант A).
    for state in CA.STATE_VOCABULARIES["properties_state"]:
        variants.append((TABLE, "properties_state=" + state,
                         probe_attribute_row(base, cfg_uuid, "ps_" + state,
                                             properties_state=state,
                                             unknown_property_names=(
                                                 None if state == CA.PROPS_ALL_KNOWN
                                                 else ["КакоеТоСвойство"]))))
    # Разделение: три блока, состояние разбора и состояние разрешения — попарно
    # (CHECK `*_ref_matches_state` связывает их с содержимым ссылки).
    for prefix in ("data_separation_value", "data_separation_use",
                   "conditional_separation"):
        state_column = prefix + "_parse_state"
        resolve_column = prefix + "_resolve_state"
        for state in CA.STATE_VOCABULARIES[state_column]:
            if state == CA.SEP_PARSED:
                pairs = [("Catalog.Товары", CA.TARGET_EXACT),
                         ("Catalog.Товар", CA.TARGET_PREFIX_ONLY),
                         (None, CA.TARGET_UNRESOLVED)]
            else:
                pairs = [(None, None)]
            for object_id, resolve in pairs:
                variants.append((TABLE, "%s=%s+%s"
                                     % (state_column, state, resolve or "без ссылки"),
                                 probe_attribute_row(
                                     base, cfg_uuid,
                                     "%s_%s_%s" % (prefix, state, resolve or "none"),
                                     **{state_column: state,
                                        prefix + "_ref_text":
                                            ("Catalog.Товары"
                                             if state == CA.SEP_PARSED
                                             else ("Что-то неразбираемое"
                                                   if state == CA.SEP_UNKNOWN_FORM
                                                   else None)),
                                        prefix + "_object_id": object_id,
                                        prefix + "_object_uuid":
                                            (probe_uuid("цель")
                                             if resolve == CA.TARGET_EXACT else None),
                                        resolve_column: resolve})))
    # Применение: состояние цели против её собственной отсылки, состояние применения,
    # условие разделения. Порядковые номера берутся из заведомо свободного диапазона,
    # чтобы копия не нарушила ключ `(common_attribute_id, ordinal)`.
    for offset, resolve in enumerate(CA.STATE_VOCABULARIES["target_resolve_state"]):
        over = {"target_resolve_state": resolve}
        if resolve == CA.TARGET_EXACT:
            over["target_unresolved_path"] = None
        elif resolve == CA.TARGET_PREFIX_ONLY:
            over["target_unresolved_path"] = "StandardAttribute.Active"
        else:
            over["target_object_id"] = None
            over["target_unresolved_path"] = "Прочая.Цель"
        variants.append((TARGETS_TABLE, "target_resolve_state=" + resolve,
                         probe_target_row(base_target, cfg_uuid, attribute_ids,
                                          "trs_" + resolve, ordinal=9100 + offset, **over)))
    for start, column in ((9200, "use_state"), (9300, "conditional_separation_state")):
        for offset, state in enumerate(CA.STATE_VOCABULARIES[column]):
            variants.append((TARGETS_TABLE, column + "=" + state,
                             probe_target_row(base_target, cfg_uuid, attribute_ids,
                                              column + "_" + state,
                                              ordinal=start + offset, **{column: state})))

    for table, label, row in variants:
        cur.execute("SAVEPOINT v50_p3_state")
        try:
            CONFIGURATION_OBJECT_WRITERS[table].insert(cur, row)
            check("состояние %s записано писателем и принято схемой" % label, True)
        except psycopg2.Error as exc:
            check("состояние %s записано писателем и принято схемой" % label, False,
                  str(exc).splitlines()[0][:200])
        finally:
            cur.execute("ROLLBACK TO SAVEPOINT v50_p3_state")


def check_chain(cur, cfg_uuid, name, baseline, report, attribute_ids):
    """Цепочка состояния строки реквизита и граница её ключа; текущность следует за ней.

    Все вставки группы идут в SAVEPOINT и откатываются: проба не оставляет в транзакции
    вторых ревизий, из-за которых последующие проверки круга считали бы не тот состав.

    Граница ключа названа замером 2.8: семь имён вида имеют идентичные uuid в BGU2 и BP3.
    Ключ без границы по конфигурации принял бы их одной строкой, и вопрос «как этот общий
    реквизит устроен в другой конфигурации» остался бы без ответа.
    """
    print("\n--- цепочка состояния и граница ключа (Q2, вариант A) ---")
    if not report["rows"]:
        if not baseline[TABLE]:
            note("%s: позиций вида в этой выгрузке нет — цепочка состояния и граница её "
                 "ключа проверяются на выгрузках, где круг есть (MinCfg, BGU2, BP3)" % name)
            return
        check("случаи цепочки построены", False, "строк разбора нет")
        return
    cur.execute("SAVEPOINT v50_p3_chain")
    try:
        first = dict(report["rows"][0], configuration_uuid=cfg_uuid)
        name = first["object_name"]
        attribute_id = attribute_ids[CA.index_object_name(name)]

        duplicate = dict(first, object_uuid=probe_uuid("дубль"))
        stamp_revision_rows([duplicate], revision_no=FIRST_REVISION,
                            changed_by=CHANGED_BY_LOAD)
        expect_violation(cur, "повтор той же ревизии отклоняется уникальным индексом "
                              "цепочки", TABLE, duplicate,
                              "common_attributes_configuration_object_revision_key")

        other_cfg = str(uuid_module.uuid4())
        # То же имя И тот же uuid в другой конфигурации — принимается: границей ключа
        # является конфигурация, а не идентичность объекта метаданных (замер 2.8).
        other = dict(first, configuration_uuid=other_cfg)
        stamp_revision_rows([other], revision_no=FIRST_REVISION, changed_by=CHANGED_BY_LOAD)
        uuid_before = int(one(cur, "SELECT count(*) FROM " + TABLE
                                 + " WHERE object_uuid = %s",
                                 (first["object_uuid"],)) or 0)
        cur.execute("SAVEPOINT v50_p3_other")
        try:
            other_id = CONFIGURATION_OBJECT_WRITERS[TABLE].insert_ids(cur, [other])[0]
            hit = int(one(cur, "SELECT count(*) FROM " + TABLE
                              + " WHERE configuration_uuid = %s AND object_name = %s",
                              (other_cfg, name)) or 0)
            uuid_after = int(one(cur, "SELECT count(*) FROM " + TABLE
                                    + " WHERE object_uuid = %s",
                                    (first["object_uuid"],)) or 0)
            check("то же имя и тот же uuid позиции вида в ДРУГОЙ конфигурации "
                  "принимаются (граница ключа, замер 2.8)",
                  hit == 1 and uuid_after == uuid_before + 1 and other_id is not None,
                  "строк другой конфигурации: %d, строк с этим uuid: было %d, стало %d"
                  % (hit, uuid_before, uuid_after))
            if other_id is not None:
                target = dict(report["targets"][0], common_attribute_id=other_id,
                              configuration_uuid=other_cfg,
                              attribute_object_uuid=first["object_uuid"],
                              attribute_full_name=CA.index_object_name(name))
                CONFIGURATION_OBJECT_WRITERS[TARGETS_TABLE].insert(cur, target)
                cur.execute("DELETE FROM " + TABLE + " WHERE id = %s", (other_id,))
                left = int(one(cur, "SELECT count(*) FROM " + TARGETS_TABLE
                                  + " WHERE common_attribute_id = %s", (other_id,)) or 0)
                check("снятие строки реквизита снимает её применения "
                      "(FK common_attribute_id ON DELETE CASCADE)",
                      left == 0, "строк применения осталось: %d" % left)
        except psycopg2.Error as exc:
            check("то же имя и тот же uuid позиции вида в ДРУГОЙ конфигурации "
                  "принимаются (граница ключа, замер 2.8)", False,
                  str(exc).splitlines()[0][:200])
        finally:
            cur.execute("ROLLBACK TO SAVEPOINT v50_p3_other")

        second = dict(first)
        stamp_revision_rows([second], revision_no=FIRST_REVISION + 1,
                            changed_by=CHANGED_BY_EDIT)
        CONFIGURATION_OBJECT_WRITERS[TABLE].insert(cur, second)
        cur.execute("SELECT revision_no, object_uuid, " + COMMIT_FLAG_COLUMN + " FROM "
                    + VIEWS[TABLE] + " WHERE configuration_uuid = %s AND object_name = %s",
                    (cfg_uuid, name))
        got = cur.fetchall()
        check("витрина текущего состояния отдаёт одну строку — вторую ревизию",
              len(got) == 1 and got[0][0] == FIRST_REVISION + 1
              and str(got[0][1]).lower() == str(second["object_uuid"]).lower(), str(got))
        history = int(one(cur, "SELECT count(*) FROM " + TABLE
                             + " WHERE configuration_uuid = %s AND object_name = %s",
                             (cfg_uuid, name)) or 0)
        check("прежняя ревизия остаётся в таблице историей", history == 2,
              "строк в таблице: %d" % history)
        current_targets = int(one(cur, "SELECT count(*) FROM " + TARGETS_VIEW
                                    + " WHERE common_attribute_id = %s",
                                    (attribute_id,)) or 0)
        old_targets = int(one(cur, "SELECT count(*) FROM " + TARGETS_TABLE
                                + " WHERE common_attribute_id = %s", (attribute_id,)) or 0)
        check("витрина строк применения перестаёт отдавать применения прежней ревизии",
              current_targets == 0, "строк в витрине: %d" % current_targets)
        check("сами строки применения прежней ревизии остаются в таблице (Q2, вариант A): "
              "своей цепи у них нет, они снимаются вместе со своей ревизией",
              old_targets > 0, "строк в таблице: %d" % old_targets)
        cur.execute("SAVEPOINT v50_p3_undo")
        try:
            cur.execute("DELETE FROM " + TABLE + " WHERE configuration_uuid = %s AND "
                        "object_name = %s AND revision_no = %s",
                        (cfg_uuid, name, FIRST_REVISION + 1))
            back = int(one(cur, "SELECT count(*) FROM " + TARGETS_VIEW
                             + " WHERE common_attribute_id = %s", (attribute_id,)) or 0)
            check("снятие второй ревизии возвращает витрину к первой и её применениям",
                  back == old_targets, "строк в витрине: %d, в таблице: %d"
                  % (back, old_targets))
        finally:
            cur.execute("ROLLBACK TO SAVEPOINT v50_p3_undo")
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v50_p3_chain")


def index_rows_of(dump_dir):
    """Записи `ConfigDumpInfo.xml` выгрузки — свои, а не из помощника другой группы.

    Разрешение цели применения и ссылки разделения требует `object_id` и `uuid` строки
    индекса целиком: помощник, который снимает поле, дал бы состояния `unresolved` там,
    где цель разрешима (замер 2.6: 1 512 целей из 1 512 разрешаются именно индексом).
    """
    path = find_config_dump_info(str(dump_dir))
    if path is None:
        return [], "ConfigDumpInfo.xml не найден в корне выгрузки"
    parsed = parse_config_dump_info(str(path))
    if not parsed.get("success"):
        return [], str(parsed.get("error") or "индекс не разобран")
    return list(parsed.get("objects") or []), None


def table_baseline(cur, cfg_uuid):
    """Базовое состояние двух таблиц: {таблица: (всего строк, строк этой конфигурации)}."""
    state = {}
    for table in TABLES:
        state[table] = (int(one(cur, "SELECT count(*) FROM " + table) or 0),
                        int(one(cur, "SELECT count(*) FROM " + table
                                   + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0))
    return state


def run_dump(name):
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

    index_rows, index_reason = index_rows_of(dump_dir)
    check("%s: индекс состава прочитан" % name, bool(index_rows),
          index_reason or ("%d записей" % len(index_rows)))

    report = CA.collect_common_attributes(str(dump_dir), index_rows=index_rows)
    check("%s: файлы вида разбираются без отказов" % name, report["success"],
          report["files_failed"][:2] if report["files_failed"] else 0)
    baseline = BASELINE_ROWS[name]
    check("%s: круг вида совпадает с базовой линией замера П3 (%d + %d)"
          % (name, baseline[TABLE], baseline[TARGETS_TABLE]),
          len(report["rows"]) == baseline[TABLE]
          and len(report["targets"]) == baseline[TARGETS_TABLE],
          "реквизитов %d, применений %d" % (len(report["rows"]), len(report["targets"])))
    check("%s: файлы вида и записи индекса состава совпадают" % name,
          not report["file_only"] and not report["index_only"]
          and not report["uuid_mismatch"],
          "file_only %d, index_only %d, uuid_mismatch %d"
          % (len(report["file_only"]), len(report["index_only"]),
             len(report["uuid_mismatch"])))
    check_contract_matches_writer(report, baseline)
    note("контракт разбора: файлов %d, прочитано %d, реквизитов %d, применений %d "
         "(целей различных %d, максимум на файл %d), неразрешимых целей %d"
         % (report["files_found"], report["files_read"], len(report["rows"]),
            report["targets_total"], report["targets_distinct"],
            report["max_targets_per_file"], len(report["unresolved_targets"])))

    before = None
    conn = connect()
    try:
        cur = conn.cursor()
        # Инвариант тот же, что у проб П3 узлов V48 и V49: таблицы больше не пустуют
        # глобально — стадии конвейера пишут реальный состав загруженных конфигураций.
        # Проверяемое свойство не изменилось: проба ничего не меняет в базе. Поэтому
        # базовое состояние читается ДО записи, снятие идёт по кругу этой конфигурации
        # (сначала применения, потом реквизиты — порядок, обратный записи), а откат обязан
        # вернуть ровно прочитанное до состояние.
        before = table_baseline(cur, cfg_uuid)
        for table in TABLES:
            if before[table][1]:
                note("%s: в таблице уже есть %d строк этой конфигурации — они сняты внутри "
                     "транзакции пробы и вернутся после отката"
                     % (table, before[table][1]))
        removed = {}
        for table in (TARGETS_TABLE, TABLE):
            cur.execute("DELETE FROM " + table + " WHERE configuration_uuid = %s",
                        (cfg_uuid,))
            removed[table] = cur.rowcount
        for table in TABLES:
            check("%s: прежние строки этой конфигурации сняты внутри транзакции" % table,
                  removed[table] == before[table][1], "снято %d" % removed[table])
        written, moment, attribute_ids, target_rows, unbound, without_id = write_all(
            cur, cfg_uuid, report)
        check("метка события названа (M2)", bool(moment), str(moment))
        check_written(cur, cfg_uuid, name, report, written, unbound, without_id)
        check_link_integrity(cur, cfg_uuid, report)
        check_round_trip(cur, cfg_uuid, report, attribute_ids)
        check_named_constraints(cur, cfg_uuid, name, baseline, report, attribute_ids)
        check_state_reachability(cur, cfg_uuid, name, baseline, report, attribute_ids)
        check_chain(cur, cfg_uuid, name, baseline, report, attribute_ids)
        conn.rollback()
        check("транзакция откатана", True, "строк в базу не попало")
    except psycopg2.Error as exc:
        conn.rollback()
        check("запись круга прошла без ошибки схемы", False, str(exc).splitlines()[0][:300])
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
    print("ПРОГОН V50 (П3): писатели содержимого общих реквизитов")
    print("писатели: CommonAttributesRowWriter, CommonAttributeTargetsRowWriter "
          "(src/external_table_writer.py); разбор: "
          "src/configuration_common_attributes.py")
    wanted = ONLY or DUMPS
    check_registry()
    conn = connect()
    try:
        cursor = conn.cursor()
        check_writer_matches_schema(cursor)
        check_state_vocabularies(cursor)
    finally:
        conn.close()
    for name in wanted:
        run_dump(name)
    print("\nИТОГ: пройдено " + str(PASSED) + ", провалено " + str(FAILED)
          + ", заметок " + str(len(NOTES)))
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())

















