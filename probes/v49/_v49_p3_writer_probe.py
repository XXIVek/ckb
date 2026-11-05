#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Шаг П3 узла V49: прогон писателей группы `roles` в живую схему.

Предмет — путь ЗАПИСИ. Офлайн-прогон П2 (`_v49_p2_offline_probe.py`) отвечал на вопрос
«что мы знаем о выгрузке»; этот отвечает на «знаемое доходит до четырёх таблиц без потерь
и без домыслов». Проверяются четыре таблицы узла сразу, потому что круг узла — именно
круг: строка роли без дескриптора содержимого, право без роли, вызов шаблона без текста
и текст без носителя — не «половинки», а сломанный круг. Отсюда вторая часть формулировки
проверки в плане: «круг не пишется частями».

Отдельные проверки, которых нет в `tools/check_v19_revisions.py`:

  * спецификация каждого из четырёх писателей совпадает с живой схемой: объявленная
    колонка существует, а каждая NOT NULL-колонка без DEFAULT объявлена писателем
    (иначе вставка упала бы на NULL, и виновата была бы не выгрузка);
  * круг писателей = круг версионных таблиц ПЛЮС именованное исключение
    `CONFIGURATION_UNVERSIONED_TABLES` (`role_rights`: своей цепи ревизий у неё нет —
    Q2, вариант A). Прежняя формулировка «ровно» с узла V49 стала бы ложью;
  * закрытые словари состояний вида (`STATE_VOCABULARIES` разбора) сверяются с CHECK
    живой схемы по имени колонки: расхождение в одном значении — это либо мёртвая ветка
    CHECK, либо состояние, которое схема отвергнет при загрузке круга;
  * каждое состояние из словаря записывается ЧЕРЕЗ ПИСАТЕЛЯ и принимается схемой —
    «словарь совпадает» и «словарь достижим» суть разные факта;
  * каждое нарушение называется ограничением по имени (замер 2.10 повторяется на пути
    записи), включая пары «состояние ↔ содержимое»
    (`role_rights_condition_matches_state`, `role_rights_target_resolve_matches_reference`,
    `role_sources_size_matches_state`, `roles_counters_match_content_state`);
  * round-trip: значения возвращаются из таблицы ровно теми, что отдал разбор
    (`condition_text` целиком — сверка по md5 и длине, `synonym` остаётся NULL, когда
    синонима не было, `restriction_template_names` остаётся NULL при состояниях без вызова);
  * цепочка состояния: повтор ревизии отклонён, то же имя роли в ДРУГОЙ конфигурации
    принято (позиция O9), вторая ревизия продолжает цепочку и становится текущей, а
    витрина прав перестаёт отдавать права прежней ревизии — при том что строки прав
    остаются в таблице (Q2, вариант A);
  * каскад `role_rights_role_id_fkey`: снятие строки роли снимает её права, а дескриптор
    файла и текст шаблона остаются — это граница модели, а не побочный эффект.

Транзакция в конце ОТКАТЫВАЕТСЯ намеренно. Инвариант — тот же, что у пробы П3 узла V48
после её шага П4: пустота таблиц инвариантом не является, поэтому базовое состояние
читается ДО записи, а после отката новым соединением сверяется равенство числа строк —
всего и строк этой конфигурации — по всем четырём таблицам.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v49_p3_writer_probe.py [MinCfg|KomMag|BGU2|BP3]
Код возврата 0 — расхождений нет. Прогоны, меняющие состояние БД, не паралелятся.
"""

import hashlib
import re
import sys
import uuid as uuid_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import psycopg2  # noqa: E402

import configuration_roles as CR  # noqa: E402
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

ROLE_TABLE = CR.TABLE_NAME
RIGHTS_TABLE = CR.RIGHTS_TABLE_NAME
TEMPLATES_TABLE = CR.TEMPLATES_TABLE_NAME
SOURCES_TABLE = CR.SOURCES_TABLE_NAME
TABLES = (ROLE_TABLE, RIGHTS_TABLE, TEMPLATES_TABLE, SOURCES_TABLE)
# Круг узла по версионности: три таблицы ведут свою цепочку, у строк права её нет (Q2 A).
NODE_VERSIONED = (ROLE_TABLE, TEMPLATES_TABLE, SOURCES_TABLE)
NODE_UNVERSIONED = (RIGHTS_TABLE,)
VIEWS = dict((table, "v_current_" + table) for table in NODE_VERSIONED)
RIGHTS_VIEW = "v_current_role_rights"

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
ONLY = tuple(arg for arg in sys.argv[1:] if arg in DUMPS)

# Базовая линия записываемых строк — числа плана (docs/CONFIGURATION_ROLES_PLAN.md,
# раздел 2.1, замер П0/П2 по файлам выгрузок). Проба сверяет с ними то, что отдал разбор,
# и то, что легло в таблицу и в витрину: расхождение видно по имени таблицы.
BASELINE_ROWS = {
    "MinCfg": {ROLE_TABLE: 2, RIGHTS_TABLE: 362, TEMPLATES_TABLE: 1, SOURCES_TABLE: 2},
    "KomMag": {ROLE_TABLE: 4, RIGHTS_TABLE: 2899, TEMPLATES_TABLE: 0, SOURCES_TABLE: 4},
    "BGU2": {ROLE_TABLE: 514, RIGHTS_TABLE: 60565, TEMPLATES_TABLE: 8, SOURCES_TABLE: 514},
    "BP3": {ROLE_TABLE: 682, RIGHTS_TABLE: 76332, TEMPLATES_TABLE: 9, SOURCES_TABLE: 682},
}

# Колонки, которых в контракте разбора нет по замыслу: их подставляет вызывающий слой.
LOADER_SUPPLIED = {
    ROLE_TABLE: set(["configuration_uuid"]),
    RIGHTS_TABLE: set(["configuration_uuid", "role_id"]),
    TEMPLATES_TABLE: set(["configuration_uuid"]),
    SOURCES_TABLE: set(["configuration_uuid"]),
}

# Связь разбора `role_name` колонкой не становится осознанно (Q2, вариант A).
LINK_COLUMN_OF = {RIGHTS_TABLE: "role_name"}

# Домены состояний, принадлежащие ЦЕПИ СОСТОЯНИЯ, а не виду: их словарь задаёт точка
# доступа `src/current_revision.py`, и сверять его со словарём разбора — значит искать не
# там. Проверка всё равно выполняется: схема обязана разрешать ровно те события, которые
# умеет называть точка доступа.
REVISION_STATE_COLUMNS = frozenset({"changed_by"})
REVISION_STATE_VALUES = (CHANGED_BY_LOAD, CHANGED_BY_EDIT, CHANGED_BY_RESTORE)

DOMAIN_RE = re.compile(r"(\w+)\s*=\s*ANY\s*\(ARRAY\[(.*?)\]\)", re.S)
VALUE_RE = re.compile(r"'((?:[^']|'')*)'(?:::[A-Za-z_ ]+)?")

PASSED = 0
FAILED = 0
NOTES = []


def check(name, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("  [OK]   " + name + ((" — " + str(detail)) if detail else ""))
    else:
        FAILED += 1
        print("  [FAIL] " + name + ((" — " + str(detail)) if detail else ""))


def note(text):
    NOTES.append(text)
    print("  [NOTE] " + text)


def one(cur, sql, params=None):
    cur.execute(sql, params or ())
    row = cur.fetchone()
    return row[0] if row else None


def md5_hex(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest() if text is not None else None


# ── статическая часть: круг писателей и их спецификации ─────────────────────────────
def check_registry():
    print("\n=== писатели узла и круг версионных таблиц ===")
    expected = sorted(set(CONFIGURATION_VERSIONED_TABLES)
                      | set(CONFIGURATION_UNVERSIONED_TABLES))
    check("словарь писателей покрывает круг версионных таблиц плюс именованное исключение",
          sorted(CONFIGURATION_OBJECT_WRITERS) == expected,
          ", ".join(sorted(CONFIGURATION_OBJECT_WRITERS)))
    # Круг таблиц без своей цепи задают три узла: V49 (`role_rights`), V50
    # (`common_attribute_targets`) и V52 (`filter_criterion_content`). Сравнение с кругом
    # одного узла было бы неверно с того момента, как появился второй узел с таким же
    # основанием (Q2, вариант A), и проба это пропустила: эталон правится тем же шагом, что
    # и регистрация новой таблицы, иначе добавление читалось бы молчанием.
    full_unversioned = NODE_UNVERSIONED + ("common_attribute_targets",
                                          "filter_criterion_content")
    check("исключение названо и совпадает с полным кругом таблиц без своей цепи "
          "(V49+V50+V52)",
          sorted(CONFIGURATION_UNVERSIONED_TABLES) == sorted(full_unversioned),
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
            call(RIGHTS_TABLE)
            check("%s для %s отвечает отказом (цепи нет — Q2 A)" % (label, RIGHTS_TABLE),
                  False, "значение получено молча")
        except ValueError as exc:
            check("%s для %s отвечает отказом (цепи нет — Q2 A)" % (label, RIGHTS_TABLE),
                  True, str(exc).splitlines()[0][:120])


def check_writer_matches_schema(cur):
    """Спецификации четырёх писателей против живой схемы (information_schema).

    Две ошибки, которые иначе видны только отказом вставки: писатель объявляет колонку,
    которой в схеме нет (опечатка в имени читается как «нет такого столбца»), и писатель НЕ
    объявляет обязательную колонку — тогда вставка падает на NOT NULL, и виновата не
    выгрузка, а спецификация. Отдельно читается витрина прав: своей цепи у таблицы нет,
    поэтому её имя не даёт `current_view()`, а существование связки — предмет проверки.
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
              not undeclared, ", ".join(undeclared) if undeclared else
              "колонок в спецификации: %d" % len(writer.COLUMNS))
        required = sorted(name for name, (nullable, default) in schema.items()
                          if nullable == "NO" and default is None and name != "id")
        missing = sorted(name for name in required if name not in writer.COLUMNS)
        check("%s: каждая NOT NULL-колонка без DEFAULT объявлена писателем" % table,
              not missing, "обязательных %d, не объявлено: %s"
              % (len(required), ", ".join(missing) if missing else "нет"))
        outside = sorted(name for name in schema
                         if name not in writer.COLUMNS and name != "id")
        note("%s: обязательных без DEFAULT — %d (%s); вне спецификации (их даёт DEFAULT или "
             "последовательность) — %s"
             % (table, len(required), ", ".join(required),
                ", ".join(outside) if outside else "нет"))
    cur.execute("SELECT table_name FROM information_schema.views WHERE table_schema = "
                "current_schema() AND table_name = ANY(%s)",
                (list(VIEWS.values()) + [RIGHTS_VIEW],))
    got = set(row[0] for row in cur.fetchall())
    for table in NODE_VERSIONED:
        check("%s: витрина существует" % VIEWS[table], VIEWS[table] in got)
    check("%s: витрина прав существует, хотя имя её не даёт current_view (связка Q2 A)"
          % RIGHTS_VIEW, RIGHTS_VIEW in got)
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                (RIGHTS_VIEW,))
    view_columns = set(row[0] for row in cur.fetchall())
    missing_link = sorted(set(CONFIGURATION_OBJECT_WRITERS[RIGHTS_TABLE].COLUMNS)
                          - view_columns)
    check("%s отдаёт все колонки строки права, включая поле <field>" % RIGHTS_VIEW,
          not missing_link, ", ".join(missing_link) if missing_link
          else "колонок: %d" % len(view_columns))


def schema_state_domains(cur):
    """Домены состояний из CHECK живой схемы: {таблица: {колонка: [(имя, значения)]}}."""
    result = {}
    for table in TABLES:
        cur.execute("SELECT con.conname, pg_get_constraintdef(con.oid) FROM pg_constraint con "
                    "JOIN pg_class cls ON cls.oid = con.conrelid "
                    "WHERE cls.relname = %s AND con.contype = 'c' ORDER BY con.conname",
                    (table,))
        domains = {}
        for conname, definition in cur.fetchall():
            for column, body in DOMAIN_RE.findall(definition or ""):
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
    for column, states in sorted(CR.STATE_VOCABULARIES.items()):
        table = CR.STATE_VOCABULARY_TABLES[column]
        found = domains.get(table, {}).get(column, [])
        if len(found) != 1:
            check("%s.%s: в схеме ровно один домен состояний" % (table, column),
                  False, "найдено %d: %s" % (len(found),
                                             ", ".join(name for name, _ in found)))
            continue
        conname, values = found[0]
        check("%s.%s: словарь разбора совпадает с доменом CHECK %s"
              % (table, column, conname), values == set(states),
              "словарь %d, схема %d; только в словаре: %s; только в схеме: %s"
              % (len(states), len(values),
                 ", ".join(sorted(set(states) - values)) or "нет",
                 ", ".join(sorted(values - set(states))) or "нет"))
    extra = []
    for table in TABLES:
        for column, found in domains.get(table, {}).items():
            if column in CR.STATE_VOCABULARIES:
                continue
            if column in REVISION_STATE_COLUMNS:
                # Домен `changed_by` принадлежит цепи состояния, а не виду: его словарь
                # живёт в `src/current_revision.py` (CHANGED_BY_*), и сверяется здесь с
                # ним, а не со словарём разбора. Молча убрать колонку из проверки — значит
                # не заметить, что схема разрешает событие, которого точка доступа не знает.
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


def check_contract_matches_writer(report, baseline):
    """Ключи контракта разбора против спецификаций писателей: расхождение видно по именам."""
    print("\n=== ключи контракта разбора против спецификаций писателей ===")
    for table, rows in ((ROLE_TABLE, report["role_rows"]),
                        (RIGHTS_TABLE, report["right_rows"]),
                        (TEMPLATES_TABLE, report["template_rows"]),
                        (SOURCES_TABLE, report["source_rows"])):
        writer = CONFIGURATION_OBJECT_WRITERS[table]
        declared = set(writer.COLUMNS) - set(REVISION_COLUMNS) - LOADER_SUPPLIED[table]
        if not rows:
            # Пустая группа не даёт ни одного ключа, и сравнение множеств молча
            # превратилось бы в «писатель лишён колонок». Пустота называется отдельной
            # строкой и сверяется с базовой линией: «группы нет в выгрузке» и «разбор её
            # не собрал» — разные состояния, и путать их нельзя.
            check("%s: группа пуста в этой выгрузке — ключи не сравниваются, "
                  "пустота совпадает с базовой линией (%d)" % (table, baseline.get(table, 0)),
                  baseline.get(table, 0) == 0, "строк разбора: 0")
            continue
        produced = set()
        for row in rows:
            produced.update(row)
        link = LINK_COLUMN_OF.get(table)
        extra = sorted(produced - declared - (set([link]) if link else set()))
        missing = sorted(declared - produced)
        check("%s: контракт разбора и спецификация писателя совпадают" % table,
              not extra and not missing,
              "лишних: %s; не производятся: %s"
              % (", ".join(extra) if extra else "нет",
                 ", ".join(missing) if missing else "нет"))
        if link:
            check("%s: %s остаётся связью разбора и колонкой не становится; "
                  "писателю нужен role_id ревизии (Q2 A)" % (table, link),
                  link in produced and link not in writer.COLUMNS
                  and "role_id" in writer.COLUMNS)


# ── запись круга: тот же контракт, что отдаёт разбор П2 ──────────────────────────────
def write_all(cur, cfg_uuid, report):
    """Записать круг узла одной транзакцией; вернуть числа, момент и связь role_id.

    Порядок один для всех четырёх таблиц: снять прежнее состояние этой конфигурации,
    проставить ОДИН штамп ревизии (M2), вставить роли и получить их id, подставить id
    ревизии в строки прав, затем тексты шаблонов и дескрипторы файлов. Строки прав
    существуют только через id строки роли (Q2, вариант A), поэтому `insert_ids` — часть
    круга, а не деталь реализации.
    """
    role_rows = [dict(row, configuration_uuid=cfg_uuid) for row in report["role_rows"]]
    source_rows = [dict(row, configuration_uuid=cfg_uuid) for row in report["source_rows"]]
    template_rows = [dict(row, configuration_uuid=cfg_uuid)
                     for row in report["template_rows"]]
    moment = stamp_revision_rows(role_rows, revision_no=FIRST_REVISION,
                                 changed_by=CHANGED_BY_LOAD)
    stamp_revision_rows(source_rows, revision_no=FIRST_REVISION,
                        changed_by=CHANGED_BY_LOAD, changed_at=moment)
    stamp_revision_rows(template_rows, revision_no=FIRST_REVISION,
                        changed_by=CHANGED_BY_LOAD, changed_at=moment)
    ids = CONFIGURATION_OBJECT_WRITERS[ROLE_TABLE].insert_ids(cur, role_rows)
    role_ids = {}
    without_id = []
    for row, record_id in zip(role_rows, ids):
        if record_id is None:
            without_id.append(row["object_name"])
        else:
            role_ids[row["object_name"]] = record_id
    right_rows = []
    unbound = []
    for row in report["right_rows"]:
        record_id = role_ids.get(row["role_name"])
        if record_id is None:
            unbound.append(row["role_name"])
            continue
        prepared = dict((key, value) for key, value in row.items() if key != "role_name")
        prepared["role_id"] = record_id
        prepared["configuration_uuid"] = cfg_uuid
        right_rows.append(prepared)
    written = {
        ROLE_TABLE: len(role_rows),
        RIGHTS_TABLE: CONFIGURATION_OBJECT_WRITERS[RIGHTS_TABLE].insert_many(
            cur, right_rows),
        TEMPLATES_TABLE: CONFIGURATION_OBJECT_WRITERS[TEMPLATES_TABLE].insert_many(
            cur, template_rows),
        SOURCES_TABLE: CONFIGURATION_OBJECT_WRITERS[SOURCES_TABLE].insert_many(
            cur, source_rows),
    }
    return written, moment, role_ids, right_rows, unbound, without_id


def check_written(cur, cfg_uuid, dump_name, report, written, unbound, without_id):
    """Запись равна разбору: числа четырёх таблиц и базовая линия замера П3."""
    print("\n--- запись равна разбору (числа по четырём таблицам) ---")
    expected = {
        ROLE_TABLE: len(report["role_rows"]),
        RIGHTS_TABLE: len(report["right_rows"]),
        TEMPLATES_TABLE: len(report["template_rows"]),
        SOURCES_TABLE: len(report["source_rows"]),
    }
    baseline = BASELINE_ROWS[dump_name]
    for table in TABLES:
        check("%s: писатель вернул строк ровно сколько отдал разбор" % table,
              written[table] == expected[table],
              "%d против %d" % (written[table], expected[table]))
        stored = int(one(cur, "SELECT count(*) FROM " + table
                             + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0)
        check("%s: в таблице строк этой конфигурации ровно столько же" % table,
              stored == expected[table], stored)
        check("%s: круг совпадает с базовой линией замера П3 (%d)" % (table, baseline[table]),
              expected[table] == baseline[table], expected[table])
    check("прав не осталось без строки роли (связь role_name → role_id полная)",
          not unbound and not without_id,
          "без id: %d; без строки: %d" % (len(unbound), len(without_id)))
    null_uuid = int(one(cur, "SELECT count(*) FROM " + RIGHTS_TABLE
                             + " WHERE configuration_uuid IS NULL") or 0)
    check("uuid конфигурации подставлен в каждую строку права (дублирование осознанно)",
          null_uuid == 0, "строк с NULL: %d" % null_uuid)
    for table in NODE_VERSIONED:
        other = int(one(cur, "SELECT count(*) FROM " + table
                            + " WHERE configuration_uuid = %s AND revision_no <> %s",
                            (cfg_uuid, FIRST_REVISION)) or 0)
        check("%s: ревизия первой загрузки — %d, других нет" % (table, FIRST_REVISION),
              other == 0, "строк с другой ревизией: %d" % other)
        moments = int(one(cur, "SELECT count(DISTINCT changed_at) FROM " + table
                              + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0)
        check("%s: метка события одна на загрузку (M2)" % table,
              moments == (1 if expected[table] else 0), "разных меток: %d" % moments)
        unconfirmed = int(one(cur, "SELECT count(*) FROM " + table
                                  + " WHERE configuration_uuid = %s AND "
                                  + COMMIT_FLAG_COLUMN + " IS NOT TRUE", (cfg_uuid,)) or 0)
        check("%s: каждая строка подтверждена как загрузка (D12)" % table,
              unconfirmed == 0, "неподтверждённых: %d" % unconfirmed)


def right_rows_of(cur, cfg_uuid):
    """Строки прав этой конфигурации (для счётчиков пробы — только число)."""
    return int(one(cur, "SELECT count(*) FROM " + RIGHTS_TABLE
                       + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0)


def state_counts(cur, table, column, cfg_uuid):
    """Распределение состояний по строкам этой конфигурации (для сверки с ответом разбора)."""
    cur.execute("SELECT " + column + ", count(*) FROM " + table
                + " WHERE configuration_uuid = %s GROUP BY 1", (cfg_uuid,))
    return dict((row[0], int(row[1])) for row in cur.fetchall())


def check_link_integrity(cur, cfg_uuid, report):
    """Круг не пишется частями: связи четырёх таблиц и согласованность счётчиков.

    Проверки построены так, чтобы частичная запись была видна фактом, а не числом:
    «роль без дескриптора», «право без роли», «вызов без текста шаблона», «текст без
    носителя», «счётчик не сходится со строками» — каждое своим запросом. Счётчики
    `roles` сверяются с фактическими строками прав, а ответ разбора — с распределением
    состояний в таблицах: так выглядит «запись равна разбору» для круга, а не для одной
    таблицы.
    """
    print("\n--- круг не пишется частями: связи четырёх таблиц ---")
    missing_source = int(one(cur,
        "SELECT count(*) FROM " + ROLE_TABLE + " r LEFT JOIN " + SOURCES_TABLE + " s "
        "ON s.configuration_uuid = r.configuration_uuid "
        "AND s.object_name = r.object_name WHERE r.configuration_uuid = %s "
        "AND s.id IS NULL", (cfg_uuid,)) or 0)
    check("каждая строка роли имеет дескриптор содержимого "
          "(кроме названных разбором content_file_missing)",
          missing_source == len(report["content_file_missing"]),
          "без дескриптора: %d, названо: %d"
          % (missing_source, len(report["content_file_missing"])))
    orphans = int(one(cur,
        "SELECT count(*) FROM " + SOURCES_TABLE + " s WHERE s.configuration_uuid = %s "
        "AND NOT EXISTS (SELECT 1 FROM " + ROLE_TABLE + " r WHERE r.configuration_uuid = "
        "s.configuration_uuid AND r.object_name = s.object_name)", (cfg_uuid,)) or 0)
    check("дескрипторов без строки роли нет (дескриптор не живёт отдельно от роли)",
          orphans == 0, "сирот: %d" % orphans)
    counters = int(one(cur,
        "SELECT count(*) FROM " + ROLE_TABLE + " r LEFT JOIN (SELECT role_id, "
        "count(*) AS rights, count(DISTINCT target_full_name) AS targets, "
        "count(*) FILTER (WHERE condition_state <> 'no_condition') AS conditions "
        "FROM " + RIGHTS_TABLE + " GROUP BY role_id) x ON x.role_id = r.id "
        "WHERE r.configuration_uuid = %s AND (COALESCE(x.rights, 0) <> r.rights_count "
        "OR COALESCE(x.targets, 0) <> r.targets_count "
        "OR COALESCE(x.conditions, 0) <> r.conditions_count)", (cfg_uuid,)) or 0)
    check("счётчики роли совпадают с фактическими строками её прав",
          counters == 0, "расхождений: %d" % counters)
    cur.execute("SELECT COALESCE(sum(targets_count), 0), COALESCE(sum(rights_count), 0), "
                "COALESCE(sum(conditions_count), 0), COALESCE(sum(templates_count), 0) FROM "
                + ROLE_TABLE + " WHERE configuration_uuid = %s", (cfg_uuid,))
    sums = cur.fetchone()
    got = tuple(int(value) for value in (sums or (0, 0, 0, 0)))
    wanted = (int(report["targets_total"]), int(report["rights_total"]),
              int(report["restrictions_total"]), int(report["template_occurrences"]))
    check("суммы счётчиков совпадают с ответом разбора (цели/права/условия/шаблоны)",
          got == wanted, "таблица %s, разбор %s" % (got, wanted))
    dangling = int(one(cur,
        "SELECT count(*) FROM " + RIGHTS_TABLE + " rr, "
        "unnest(rr.restriction_template_names) AS nm WHERE rr.configuration_uuid = %s "
        "AND NOT EXISTS (SELECT 1 FROM " + TEMPLATES_TABLE + " t WHERE "
        "t.configuration_uuid = rr.configuration_uuid AND t.name = nm)", (cfg_uuid,)) or 0)
    check("каждое имя шаблона из вызова права имеет строку текста той же конфигурации",
          dangling == 0, "висячих имён: %d" % dangling)
    uncalled = int(one(cur,
        "SELECT count(*) FROM " + TEMPLATES_TABLE + " t, unnest(t.holder_role_names) AS nm "
        "WHERE t.configuration_uuid = %s AND NOT EXISTS (SELECT 1 FROM " + ROLE_TABLE
        + " r WHERE r.configuration_uuid = t.configuration_uuid AND r.object_name = nm)",
        (cfg_uuid,)) or 0)
    check("каждый носитель текста шаблона — роль этой же конфигурации",
          uncalled == 0, "носителей без роли: %d" % uncalled)
    holders = int(one(cur,
        "SELECT count(*) FROM " + TEMPLATES_TABLE + " WHERE configuration_uuid = %s "
        "AND holders_count <> COALESCE(array_length(holder_role_names, 1), 0)",
        (cfg_uuid,)) or 0)
    check("число носителей текста совпадает с его перечнем (CHECK работает на данных круга)",
          holders == 0, "расхождений: %d" % holders)
    mixed = int(one(cur,
        "SELECT count(*) FROM (SELECT role_id, target_full_name FROM " + RIGHTS_TABLE
        + " WHERE configuration_uuid = %s GROUP BY 1, 2 HAVING "
        "count(DISTINCT target_resolve_state) > 1) x", (cfg_uuid,)) or 0)
    check("одна цель не получает двух разных состояний разрешения",
          mixed == 0, "целей: %d" % mixed)
    fields = int(one(cur, "SELECT count(*) FROM " + RIGHTS_TABLE
                         + " WHERE configuration_uuid = %s "
                         "AND restriction_field_name IS NOT NULL", (cfg_uuid,)) or 0)
    check("прав с полем <field> ровно столько, сколько насчитал разбор",
          fields == int(report["restrictions_with_field"]),
          "таблица %d, разбор %d" % (fields, report["restrictions_with_field"]))
    # распределения состояний: ответ разбора обязан совпасть с таблицей по всем значениям
    pairs = ((ROLE_TABLE, "content_state", report["counts_by_content_state"]),
             (SOURCES_TABLE, "declaration_state", report["counts_by_declaration_state"]),
             (RIGHTS_TABLE, "condition_state", report["counts_by_condition_state"]),
             (RIGHTS_TABLE, "right_name_state", report["counts_by_right_name_state"]),
             (RIGHTS_TABLE, "right_value_state", report["counts_by_right_value_state"]))
    for table, column, expected in pairs:
        stored = state_counts(cur, table, column, cfg_uuid)
        wanted_states = dict((state, int(count))
                             for state, count in expected.items() if int(count))
        check("%s.%s: распределение состояний совпадает с ответом разбора" % (table, column),
              stored == wanted_states, "таблица %s, разбор %s" % (stored, wanted_states))
    cur.execute("SELECT target_resolve_state, count(*) FROM (SELECT DISTINCT role_id, "
                "target_full_name, target_resolve_state FROM " + RIGHTS_TABLE
                + " WHERE configuration_uuid = %s) x GROUP BY 1", (cfg_uuid,))
    resolved = dict((row[0], int(row[1])) for row in cur.fetchall())
    wanted_resolved = dict((state, int(count))
                           for state, count
                           in report["counts_by_target_resolve_state"].items() if int(count))
    check("разрешение целей совпадает с ответом разбора (цели, а не строки прав)",
          resolved == wanted_resolved, "таблица %s, разбор %s"
          % (resolved, wanted_resolved))


def expected_text(value):
    """Как писатель вида `text` вернёт строку: пустое значение становится NULL."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def expected_jsonb(value):
    """Как писатель вида `jsonb_nullable` вернёт запись: пустая остаётся NULL."""
    return value or None


def check_round_trip(cur, cfg_uuid, report, role_ids):
    """Содержимое четырёх таблиц возвращается из них ровно тем, что отдал разбор.

    Сравнение идёт по колонкам, а не числами строк: `synonym` обязан остаться NULL, если
    синонима не было (контракт `jsonb_nullable`), `restriction_template_names` — NULL при
    состояниях без вызова, `condition_text` — вернуться целым (сверка по отпечатку и
    длине, чтобы не гнать мегабайты текста через клиент), порядки цели и права —
    сохраниться. Для прав сравниваются ВСЕ строки круга: именно их число (60 565 в BGU2)
    и есть причина, по которой срез по выборке ничего не доказывал бы.
    """
    print("\n--- круговая проверка содержимого (четыре таблицы) ---")
    # ── роли ───────────────────────────────────────────────────────────────────────────
    cur.execute(
        "SELECT object_name, object_uuid, full_name, comment, synonym, "
        "set_for_new_objects, set_for_attributes_by_default, "
        "independent_rights_of_child_objects, content_state, source_path, targets_count, "
        "rights_count, conditions_count, templates_count FROM " + ROLE_TABLE
        + " WHERE configuration_uuid = %s", (cfg_uuid,))
    stored = dict((row[0], row) for row in cur.fetchall())
    problems = []
    wanted = set(row["object_name"] for row in report["role_rows"])
    for name in sorted(wanted - set(stored)):
        problems.append("роли %s в таблице нет" % name)
    for name in sorted(set(stored) - wanted):
        problems.append("в таблице появилась роль %s" % name)
    for row in report["role_rows"]:
        got = stored.get(row["object_name"])
        if not got:
            continue
        who = row["object_name"]
        if str(got[1]).lower() != str(row["object_uuid"]).lower():
            problems.append("%s: object_uuid изменён записью" % who)
        if got[2] != row["full_name"]:
            problems.append("%s: full_name не совпал с контрактом" % who)
        if got[3] != expected_text(row["comment"]):
            problems.append("%s: comment потерян или изменён" % who)
        if got[4] != expected_jsonb(row["synonym"]):
            problems.append("%s: synonym стал не тем (пустой обязан остаться NULL)" % who)
        for position, column in ((5, "set_for_new_objects"),
                                 (6, "set_for_attributes_by_default"),
                                 (7, "independent_rights_of_child_objects")):
            if got[position] != row[column]:
                problems.append("%s: флаг %s изменён (NULL обязан остаться NULL)"
                                % (who, column))
        if got[8] != row["content_state"]:
            problems.append("%s: состояние содержимого изменено" % who)
        if got[9] != row["source_path"]:
            problems.append("%s: source_path изменён" % who)
        for position, column in ((10, "targets_count"), (11, "rights_count"),
                                 (12, "conditions_count"), (13, "templates_count")):
            if got[position] != row[column]:
                problems.append("%s: счётчик %s переписан записью" % (who, column))
    check("роли возвращаются из таблицы ровно теми значениями, что отдал разбор",
          not problems, problems[:3] if problems else "строк: %d" % len(stored))

    # ── дескрипторы файлов содержимого ────────────────────────────────────────────────
    cur.execute("SELECT object_name, object_uuid, source_path, file_size, declaration_state "
                "FROM " + SOURCES_TABLE + " WHERE configuration_uuid = %s", (cfg_uuid,))
    stored = dict((row[0], row) for row in cur.fetchall())
    problems = []
    wanted = set(row["object_name"] for row in report["source_rows"])
    for name in sorted(wanted ^ set(stored)):
        problems.append("дескриптор %s есть только в одной из сторон" % name)
    for row in report["source_rows"]:
        got = stored.get(row["object_name"])
        if not got:
            continue
        who = row["object_name"]
        if str(got[1]).lower() != str(row["object_uuid"]).lower():
            problems.append("%s: object_uuid дескриптора изменён" % who)
        if got[2] != row["source_path"]:
            problems.append("%s: source_path дескриптора изменён" % who)
        if got[3] != row["file_size"]:
            problems.append("%s: file_size изменён (состояние без файла обязано быть NULL)" % who)
        if got[4] != row["declaration_state"]:
            problems.append("%s: состояние описания файла изменено" % who)
    check("дескрипторы возвращаются ровно теми значениями, что отдал разбор",
          not problems, problems[:3] if problems else "строк: %d" % len(stored))

    # ── тексты ограничений шаблонов ───────────────────────────────────────────────────
    cur.execute("SELECT name, digest, name_signature, condition_text, condition_length, "
                "holder_role_names, holders_count FROM " + TEMPLATES_TABLE
                + " WHERE configuration_uuid = %s", (cfg_uuid,))
    stored = dict(((row[0], row[1]), row) for row in cur.fetchall())
    problems = []
    wanted = set((row["name"], row["digest"]) for row in report["template_rows"])
    for key in sorted(wanted ^ set(stored), key=lambda pair: str(pair)):
        problems.append("текст %s/%s есть только в одной из сторон" % (key,))
    for row in report["template_rows"]:
        got = stored.get((row["name"], row["digest"]))
        if not got:
            continue
        who = row["name"]
        if got[2] != row["name_signature"]:
            problems.append("%s: name_signature изменён" % who)
        if got[3] != row["condition_text"]:
            problems.append("%s: текст условия обрезан или изменён" % who)
        if got[4] != row["condition_length"] or got[4] != len(row["condition_text"]):
            problems.append("%s: длина текста не совпала" % who)
        if list(got[5] or []) != list(row["holder_role_names"]):
            problems.append("%s: перечень носителей изменён" % who)
        if got[6] != row["holders_count"]:
            problems.append("%s: число носителей изменено" % who)
    check("тексты ограничений возвращаются целиком, носители — в порядке разбора",
          not problems, problems[:3] if problems else "строк: %d" % len(stored))

    # ── строки прав: весь круг, текст условия по отпечатку ────────────────────────────
    cur.execute(
        "SELECT rr.role_id, rr.target_full_name, rr.right_name, rr.target_kind, "
        "rr.target_object_id, rr.target_object_uuid, rr.target_resolve_state, "
        "rr.target_unresolved_path, rr.right_name_state, rr.right_value_state, "
        "rr.restriction_field_name, md5(rr.condition_text), char_length(rr.condition_text), "
        "rr.condition_state, rr.restriction_template_names, rr.target_ordinal, "
        "rr.right_ordinal FROM " + RIGHTS_TABLE + " rr JOIN " + ROLE_TABLE
        + " r ON r.id = rr.role_id WHERE rr.configuration_uuid = %s", (cfg_uuid,))
    stored = dict(((int(row[0]), row[1], row[2]), row) for row in cur.fetchall())
    problems = []
    seen = set()
    for row in report["right_rows"]:
        role_id = role_ids.get(row["role_name"])
        if role_id is None:
            continue
        key = (role_id, row["target_full_name"], row["right_name"])
        seen.add(key)
        got = stored.get(key)
        if not got:
            problems.append("права %s у цели %s в таблице нет"
                            % (row["right_name"], row["target_full_name"]))
            continue
        if got[3] != row["target_kind"]:
            problems.append("%s: target_kind изменён" % row["target_full_name"])
        if got[4] != expected_text(row["target_object_id"]):
            problems.append("%s: ссылка на строку индекса потеряна" % row["target_full_name"])
        stored_uuid = str(got[5]).lower() if got[5] is not None else None
        wanted_uuid = (str(row["target_object_uuid"]).lower()
                       if row["target_object_uuid"] else None)
        if stored_uuid != wanted_uuid:
            problems.append("%s: uuid цели изменён" % row["target_full_name"])
        if got[6] != row["target_resolve_state"] or got[7] != row["target_unresolved_path"]:
            problems.append("%s: состояние разрешения цели изменено" % row["target_full_name"])
        if got[8] != row["right_name_state"] or got[9] != row["right_value_state"]:
            problems.append("%s: состояния имени/значения права изменены" % row["right_name"])
        if got[10] != expected_text(row["restriction_field_name"]):
            problems.append("%s: поле <field> потеряно или изменено" % row["right_name"])
        if got[11] != md5_hex(row["condition_text"]):
            problems.append("%s: текст условия не совпал по отпечатку" % row["right_name"])
        wanted_length = (len(row["condition_text"])
                         if row["condition_text"] is not None else None)
        if got[12] != wanted_length:
            problems.append("%s: длина условия не совпала" % row["right_name"])
        if got[13] != row["condition_state"]:
            problems.append("%s: состояние условия изменено" % row["right_name"])
        if list(got[14] or []) != list(row["restriction_template_names"] or []):
            problems.append("%s: имена вызываемых шаблонов изменены или появились зря"
                            % row["right_name"])
        if got[15] != row["target_ordinal"] or got[16] != row["right_ordinal"]:
            problems.append("%s: порядок цели/права изменён" % row["right_name"])
    for key in sorted(set(stored) - seen, key=lambda item: str(item))[:3]:
        problems.append("в таблице появилось право %s без строки разбора" % (key,))
    check("каждое право круга возвращается из таблицы ровно тем, что отдал разбор",
          not problems and len(stored) == len(seen),
          problems[:3] if problems else "сравнено строк: %d" % len(seen))


# ── ограничения: каждое называется по имени (замер 2.10 на пути записи) ───────────────
def expect_violation(cur, label, table, row, constraints):
    """Нарушение читается именованным ограничением, а не текстом ошибки.

    Имя ограничения psycopg2 отдаёт в `diag`, поэтому сравнивается именно оно — иначе
    прогон принимал бы любой отказ. `constraints` — имя или набор имён: пара значений
    может нарушать сразу два ограничения согласованности, и какое из них отчитывается,
    решает порядок проверки ограничений, а не замысел узла.
    """
    allowed = set([constraints]) if isinstance(constraints, str) else set(constraints)
    cur.execute("SAVEPOINT v49_p3")
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
        cur.execute("ROLLBACK TO SAVEPOINT v49_p3")


def expect_sql_violation(cur, label, sql, params, constraints):
    """Ограничение схемы проверяется прямым SQL, когда писатель его не выражает.

    Писатель нормализует значения под спецификацию (`text` из пустой строки даёт NULL,
    `revision_row` дополняет половину штампа ревизии), поэтому часть состояний до таблицы
    просто не доходит — их проверяет схема, и проверяется она прямым вставлением.
    """
    allowed = set([constraints]) if isinstance(constraints, str) else set(constraints)
    cur.execute("SAVEPOINT v49_p3_sql")
    try:
        cur.execute(sql, params)
        check(label, False, "строка принята — ограничение не сработало")
    except psycopg2.Error as exc:
        name = getattr(getattr(exc, "diag", None), "constraint_name", None) \
            or getattr(exc, "constraint_name", None)
        check(label, name in allowed,
              "нарушено: " + (name or str(exc).splitlines()[0][:200])
              + "; ожидалось одно из " + ", ".join(sorted(allowed)))
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v49_p3_sql")


def expect_not_null(cur, label, sql, params, column):
    """Отказ NOT NULL читается текстом ошибки, а не именем ограничения.

    В этой базе кластер поднят `pg_upgrade`-ом с прежней версии, и ограничений NOT NULL в
    `pg_constraint` у таблиц нет (замер 30.10.2026: `SELECT conname, contype FROM
    pg_constraint WHERE conrelid = 'role_sources'::regclass` даёт только `c/p/u`) —
    поэтому имя колонки ищется в тексте. Придумывать имя ограничения, которого в каталоге
    нет, значит проверить выдумку вместо схемы.
    """
    cur.execute("SAVEPOINT v49_p3_notnull")
    try:
        cur.execute(sql, params)
        check(label, False, "строка принята — NOT NULL не сработал")
    except psycopg2.Error as exc:
        text = str(exc).splitlines()[0]
        check(label, ('null value in column "%s"' % column) in text
              and "not-null constraint" in text, text[:200])
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v49_p3_notnull")


def role_variant(cfg_uuid, name, **over):
    """Синтетическая строка роли: базовые значения валидны, отклонение добавляет `over`."""
    row = {
        "configuration_uuid": cfg_uuid, "object_uuid": str(uuid_module.uuid4()),
        "object_name": name, "full_name": "Role." + name, "comment": None, "synonym": None,
        "set_for_new_objects": None, "set_for_attributes_by_default": None,
        "independent_rights_of_child_objects": None, "content_state": CR.CONTENT_EMPTY,
        "source_path": "Roles/%s.xml" % name, "targets_count": 0, "rights_count": 0,
        "conditions_count": 0, "templates_count": 0,
    }
    row.update(over)
    return row


def source_variant(cfg_uuid, name, **over):
    row = {
        "configuration_uuid": cfg_uuid, "object_name": name,
        "object_uuid": str(uuid_module.uuid4()),
        "source_path": "Roles/%s/Ext/Rights.xml" % name, "file_size": 123,
        "declaration_state": CR.DECLARATION_FILE_AND_INDEX,
    }
    row.update(over)
    return row


def template_variant(cfg_uuid, name, **over):
    text = over.get("condition_text") or "#ДляОбъекта(ПолеОбъекта)"
    row = {
        "configuration_uuid": cfg_uuid, "name": name,
        "name_signature": name.split("(")[0], "digest": CR.condition_digest(text),
        "condition_text": text, "condition_length": len(text),
        "holder_role_names": ["_Проба_P3_"], "holders_count": 1,
    }
    row.update(over)
    return row


def right_variant(role_id, cfg_uuid, **over):
    row = {
        "role_id": role_id, "configuration_uuid": cfg_uuid, "target_kind": "Catalog",
        "target_full_name": "Catalog._Проба_P3_",
        "target_object_id": "00000000-0000-0000-0000-000000000000.0",
        "target_object_uuid": None, "target_resolve_state": CR.TARGET_EXACT,
        "target_unresolved_path": None, "right_name": "Read",
        "right_name_state": CR.RIGHT_NAME_KNOWN, "right_value_state": CR.VALUE_GRANTED,
        "restriction_field_name": None, "condition_text": None,
        "condition_state": CR.CONDITION_NONE, "restriction_template_names": None,
        "target_ordinal": 0, "right_ordinal": 0,
    }
    row.update(over)
    return row


def constraint_cases(cfg_uuid, role_id):
    """Пары значений, каждая из которых отклоняется СВОИМ ограничением схемы.

    Проверка строится списком, а не набором разрозненных вызовов: список видно целиком, и
    в нём видно, какое состояние пары относится к какому решению узла (Q3, Q5, Q7, Q8).
    """
    return [
        # `roles` — состояние содержимого и согласованность счётчиков (Q7)
        ("роль с состоянием содержимого вне словаря отклоняется", ROLE_TABLE,
         role_variant(cfg_uuid, "_Проба_P3_", content_state="file"),
         "roles_content_state_known"),
        ("состояние with_rights без прав отклоняется", ROLE_TABLE,
         role_variant(cfg_uuid, "_Проба_P3_", content_state=CR.CONTENT_WITH_RIGHTS,
                      rights_count=0), "roles_counters_match_content_state"),
        ("роль без прав с ненулевым счётчиком отклоняется", ROLE_TABLE,
         role_variant(cfg_uuid, "_Проба_P3_", content_state=CR.CONTENT_EMPTY,
                      rights_count=5, targets_count=5, conditions_count=5,
                      templates_count=5), "roles_counters_match_content_state"),
        # `role_sources` — пара «файл ↔ запись индекса» (Q8)
        ("дескриптор с состоянием вне словаря отклоняется", SOURCES_TABLE,
         source_variant(cfg_uuid, "_Проба_P3_", declaration_state="file"),
         "role_sources_declaration_state_known"),
        ("ожидаемого файла нет — размера быть не может", SOURCES_TABLE,
         source_variant(cfg_uuid, "_Проба_P3_",
                        declaration_state=CR.DECLARATION_INDEXED_NO_FILE, file_size=123),
         "role_sources_size_matches_state"),
        ("файл есть — размер обязан быть указан", SOURCES_TABLE,
         source_variant(cfg_uuid, "_Проба_P3_",
                        declaration_state=CR.DECLARATION_FILE_AND_INDEX, file_size=None),
         "role_sources_size_matches_state"),
        # Пустые имена вида `text` писатель превращает в NULL, поэтому CHECK пустоты
        # (`role_sources_names_not_blank`) до таблицы от писателя не доходит — его
        # проверяет схема прямым вставлением, а NOT NULL — отдельной проверкой текста.
        # `role_rights` — пары «состояние ↔ содержимое» (Q3, Q5)
        ("вызов без имени шаблона отклоняется", RIGHTS_TABLE,
         right_variant(role_id, cfg_uuid, condition_state=CR.CONDITION_WITH_CALL,
                       condition_text='#ДляОбъекта("")'),
         "role_rights_condition_matches_state"),
        ("условие без вызова с именем шаблона отклоняется", RIGHTS_TABLE,
         right_variant(role_id, cfg_uuid, condition_state=CR.CONDITION_NO_CALL,
                       condition_text="текст без вызова",
                       restriction_template_names=["ДляОбъекта(ПолеОбъекта)"]),
         "role_rights_condition_matches_state"),
        ("состояние без условия с текстом отклоняется", RIGHTS_TABLE,
         right_variant(role_id, cfg_uuid, condition_text="текст условия"),
         "role_rights_condition_matches_state"),
        ("состояние имени права вне словаря отклоняется", RIGHTS_TABLE,
         right_variant(role_id, cfg_uuid, right_name_state="guess"),
         "role_rights_right_name_state_known"),
        ("состояние значения права вне словаря отклоняется", RIGHTS_TABLE,
         right_variant(role_id, cfg_uuid, right_value_state="maybe"),
         "role_rights_right_value_state_known"),
        ("состояние разрешения цели вне словаря отклоняется", RIGHTS_TABLE,
         right_variant(role_id, cfg_uuid, target_resolve_state="fuzzy"),
         set(["role_rights_target_resolve_state_known",
              "role_rights_target_resolve_matches_reference"])),
        ("состояние условия вне словаря отклоняется", RIGHTS_TABLE,
         right_variant(role_id, cfg_uuid, condition_state="empty"),
         set(["role_rights_condition_state_known",
              "role_rights_condition_matches_state"])),
        ("prefix_only без остатка пути отклоняется", RIGHTS_TABLE,
         right_variant(role_id, cfg_uuid, target_resolve_state=CR.TARGET_PREFIX_ONLY,
                       target_unresolved_path=None),
         "role_rights_target_resolve_matches_reference"),
        ("unresolved со ссылкой на индекс отклоняется", RIGHTS_TABLE,
         right_variant(role_id, cfg_uuid, target_resolve_state=CR.TARGET_UNRESOLVED,
                       target_unresolved_path="StandardAttribute.Active"),
         "role_rights_target_resolve_matches_reference"),
        ("отрицательный порядок цели отклоняется", RIGHTS_TABLE,
         right_variant(role_id, cfg_uuid, target_ordinal=-1),
         "role_rights_ordinals_non_negative"),
        ("право со ссылкой на несуществующую ревизию роли отклоняется", RIGHTS_TABLE,
         right_variant(999999999, cfg_uuid), "role_rights_role_id_fkey"),
        # `role_restriction_templates` — форма отпечатка, длина, сигнатура, носители
        ("текст шаблона с отпечатком не sha1 отклоняется", TEMPLATES_TABLE,
         template_variant(cfg_uuid, "_Проба_P3_(Поле)", digest="zz"),
         "role_restriction_templates_digest_shape"),
        ("текст шаблона с длиной не совпадающей с текстом отклоняется", TEMPLATES_TABLE,
         template_variant(cfg_uuid, "_Проба_P3_(Поле)", condition_length=3),
         "role_restriction_templates_length_matches_text"),
        ("сигнатура не являющаяся началом имени отклоняется", TEMPLATES_TABLE,
         template_variant(cfg_uuid, "_Проба_P3_(Поле)", name_signature="ДругоеИмя"),
         "role_restriction_templates_signature_is_name_prefix"),
        ("перечень носителей не совпадающий с их числом отклоняется", TEMPLATES_TABLE,
         template_variant(cfg_uuid, "_Проба_P3_(Поле)", holders_count=2),
         "role_restriction_templates_holders_match_count"),
        ("шаблон без носителя отклоняется", TEMPLATES_TABLE,
         template_variant(cfg_uuid, "_Проба_P3_(Поле)", holder_role_names=[],
                          holders_count=0),
         "role_restriction_templates_holders_match_count"),
    ]


def check_named_constraints(cur, cfg_uuid, role_ids):
    """Каждое ограничение узла отклоняет свою пару значений — по имени ограничения."""
    print("\n--- ограничения: каждое называется по имени ---")
    if not role_ids:
        check("есть реальная строка роли для проверок FK и уникальности прав", False,
              "role_ids пуст")
        return
    role_id = sorted(role_ids.values())[0]
    for label, table, row, constraints in constraint_cases(cfg_uuid, role_id):
        expect_violation(cur, label, table, row, constraints)
    # Ограничения, которых писатель не выражает: он нормализует значения, и пустая
    # строка до таблицы не доходит вовсе. Их проверяет схема — прямым вставлением.
    expect_sql_violation(
        cur, "пустое имя поля <field> отклоняется схемой (писатель даёт NULL)",
        "INSERT INTO " + RIGHTS_TABLE + " (role_id, configuration_uuid, target_kind, "
        "target_full_name, target_resolve_state, right_name, right_name_state, "
        "right_value_state, restriction_field_name, condition_state, target_ordinal, "
        "right_ordinal) VALUES (%s, %s::uuid, 'Catalog', 'Catalog._Проба_P3_', 'exact', "
        "'Read', 'known', 'granted', '', 'no_condition', 0, 0)",
        (role_id, cfg_uuid), "role_rights_field_name_not_blank")
    expect_sql_violation(
        cur, "пустой текст условия отклоняется схемой (писатель даёт NULL)",
        "INSERT INTO " + TEMPLATES_TABLE + " (configuration_uuid, name, name_signature, "
        "digest, condition_text, condition_length, holder_role_names, holders_count, "
        "revision_no, changed_at, changed_by, is_committed) VALUES (%s::uuid, "
        "'_Проба_P3_', '_Проба_P3_', '0000000000000000000000000000000000000000', '', 0, "
        "ARRAY['_Проба_P3_'], 1, 1, now(), 'load', true)",
        (cfg_uuid,), "role_restriction_templates_condition_not_blank")
    expect_sql_violation(
        cur, "половина штампа ревизии отклоняется (CHECK пары, а не DEFAULT колонки)",
        "INSERT INTO " + ROLE_TABLE + " (configuration_uuid, object_uuid, object_name, "
        "full_name, content_state, source_path, revision_no, changed_at, changed_by, "
        "is_committed) VALUES (%s::uuid, %s::uuid, '_Проба_P3_', 'Role._Проба_P3_', "
        "'empty_content', 'Roles/_Проба_P3_.xml', 1, now(), NULL, true)",
        (cfg_uuid, str(uuid_module.uuid4())), "roles_changed_pair_check")
    expect_sql_violation(
        cur, "полупустой дескриптор отклоняется CHECK пустоты имён",
        "INSERT INTO " + SOURCES_TABLE + " (configuration_uuid, object_name, object_uuid, "
        "source_path, file_size, declaration_state, revision_no, changed_at, changed_by, "
        "is_committed) VALUES (%s::uuid, '', %s::uuid, 'Roles/_Проба_P3_/Ext/Rights.xml', "
        "NULL, 'indexed_no_file', 1, now(), 'load', true)",
        (cfg_uuid, str(uuid_module.uuid4())), "role_sources_names_not_blank")
    expect_sql_violation(
        cur, "дескриптор с пустым путём файла отклоняется CHECK пустоты имён",
        "INSERT INTO " + SOURCES_TABLE + " (configuration_uuid, object_name, object_uuid, "
        "source_path, file_size, declaration_state, revision_no, changed_at, changed_by, "
        "is_committed) VALUES (%s::uuid, '_Проба_P3_', %s::uuid, '', NULL, "
        "'indexed_no_file', 1, now(), 'load', true)",
        (cfg_uuid, str(uuid_module.uuid4())), "role_sources_names_not_blank")
    # NOT NULL этой базы в каталоге ограничений не значится (кластер поднят pg_upgrade-ом,
    # см. expect_not_null), поэтому читается текстом ошибки с именем колонки.
    expect_not_null(
        cur, "дескриптор без пути файла отклоняется NOT NULL (путь обязателен)",
        "INSERT INTO " + SOURCES_TABLE + " (configuration_uuid, object_name, object_uuid, "
        "source_path, file_size, declaration_state, revision_no, changed_at, changed_by, "
        "is_committed) VALUES (%s::uuid, '_Проба_P3_', %s::uuid, NULL, NULL, "
        "'indexed_no_file', 1, now(), 'load', true)",
        (cfg_uuid, str(uuid_module.uuid4())), "source_path")
    expect_not_null(
        cur, "дескриптор без имени роли отклоняется NOT NULL (ключ цепочки обязателен)",
        "INSERT INTO " + SOURCES_TABLE + " (configuration_uuid, object_name, object_uuid, "
        "source_path, file_size, declaration_state, revision_no, changed_at, changed_by, "
        "is_committed) VALUES (%s::uuid, NULL, %s::uuid, "
        "'Roles/_Проба_P3_/Ext/Rights.xml', NULL, 'indexed_no_file', 1, now(), 'load', true)",
        (cfg_uuid, str(uuid_module.uuid4())), "object_name")


def check_state_reachability(cur, cfg_uuid, role_ids):
    """Каждое состояние словаря вида записывается ЧЕРЕЗ ПИСАТЕЛЯ и принимается схемой.

    Сверка словарей с CHECK отвечает на «значения совпадают»; эта проверка отвечает на
    «значения достижимы»: состояние может быть записано строкой, которую собрал писатель,
    а не только литералом из миграции. Иначе «словарь есть в двух местах» не отличалось бы
    от «словари в двух местах расходятся при загрузке круга».
    """
    print("\n--- каждое состояние словаря записывается через писателя ---")
    if not role_ids:
        check("есть реальная строка роли для записи состояний права", False, "role_ids пуст")
        return
    role_id = sorted(role_ids.values())[0]
    variants = []
    for state in CR.CONTENT_STATES:
        counters = {"rights_count": 1, "targets_count": 1} \
            if state == CR.CONTENT_WITH_RIGHTS else {}
        variants.append((ROLE_TABLE, "roles.content_state=" + state,
                         role_variant(cfg_uuid, "_Проба_P3_" + state,
                                      content_state=state, **counters)))
    for state in CR.DECLARATION_STATES:
        size = 123 if state == CR.DECLARATION_FILE_AND_INDEX else None
        variants.append((SOURCES_TABLE, "role_sources.declaration_state=" + state,
                         source_variant(cfg_uuid, "_Проба_P3_" + state,
                                        declaration_state=state, file_size=size)))
    for state in CR.TARGET_RESOLVE_STATES:
        over = {"target_resolve_state": state}
        if state == CR.TARGET_EXACT:
            over["target_unresolved_path"] = None
        elif state == CR.TARGET_PREFIX_ONLY:
            over["target_unresolved_path"] = "StandardAttribute.Active"
        else:
            over["target_object_id"] = None
            over["target_unresolved_path"] = "Прочая.Цель"
        variants.append((RIGHTS_TABLE, "role_rights.target_resolve_state=" + state,
                         right_variant(role_id, cfg_uuid,
                                       target_full_name="Catalog._Проба_" + state, **over)))
    for state in CR.RIGHT_NAME_STATES:
        variants.append((RIGHTS_TABLE, "role_rights.right_name_state=" + state,
                         right_variant(role_id, cfg_uuid,
                                       target_full_name="Catalog._Проба_" + state,
                                       right_name_state=state)))
    for state in CR.RIGHT_VALUE_STATES:
        variants.append((RIGHTS_TABLE, "role_rights.right_value_state=" + state,
                         right_variant(role_id, cfg_uuid,
                                       target_full_name="Catalog._Проба_" + state,
                                       right_value_state=state)))
    for state in CR.CONDITION_STATES:
        over = {"condition_state": state}
        if state == CR.CONDITION_WITH_CALL:
            over.update({"condition_text": '#ДляОбъекта("")',
                         "restriction_template_names": ["ДляОбъекта(ПолеОбъекта)"]})
        elif state == CR.CONDITION_NO_CALL:
            over.update({"condition_text": "условие без вызова шаблона"})
        variants.append((RIGHTS_TABLE, "role_rights.condition_state=" + state,
                         right_variant(role_id, cfg_uuid,
                                       target_full_name="Catalog._Проба_" + state, **over)))
    for table, label, row in variants:
        cur.execute("SAVEPOINT v49_p3_state")
        try:
            CONFIGURATION_OBJECT_WRITERS[table].insert(cur, row)
            check("состояние %s записано писателем и принято схемой" % label, True)
        except psycopg2.Error as exc:
            check("состояние %s записано писателем и принято схемой" % label, False,
                  str(exc).splitlines()[0][:200])
        finally:
            cur.execute("ROLLBACK TO SAVEPOINT v49_p3_state")


def check_chain(cur, cfg_uuid, report, role_ids):
    """Цепочка состояния роли и граница её ключа; текущность прав следует за ролью.

    Все вставки группы идут в SAVEPOINT и откатываются: проба не оставляет в транзакции
    второй ревизии, из-за которых последующие проверки круга считали бы не тот состав.
    """
    print("\n--- цепочка состояния и граница ключа (Q2, O9) ---")
    if not report["role_rows"]:
        check("случаи цепочки построены", False, "строк разбора нет")
        return
    cur.execute("SAVEPOINT v49_p3_chain")
    try:
        first = dict(report["role_rows"][0], configuration_uuid=cfg_uuid)
        name = first["object_name"]
        role_id = role_ids[name]
        duplicate = dict(first, object_uuid=str(uuid_module.uuid4()))
        stamp_revision_rows([duplicate], revision_no=FIRST_REVISION,
                            changed_by=CHANGED_BY_LOAD)
        expect_violation(
            cur, "повтор той же ревизии отклоняется уникальным индексом цепочки",
            ROLE_TABLE, duplicate, "roles_configuration_object_revision_key")

        other_cfg = str(uuid_module.uuid4())
        other = dict(first, configuration_uuid=other_cfg,
                     object_uuid=str(uuid_module.uuid4()))
        stamp_revision_rows([other], revision_no=FIRST_REVISION, changed_by=CHANGED_BY_LOAD)
        cur.execute("SAVEPOINT v49_p3_other")
        try:
            CONFIGURATION_OBJECT_WRITERS[ROLE_TABLE].insert(cur, other)
            hit = int(one(cur, "SELECT count(*) FROM " + ROLE_TABLE
                              + " WHERE configuration_uuid = %s AND object_name = %s",
                              (other_cfg, name)) or 0)
            check("то же имя роли в ДРУГОЙ конфигурации принимается (граница ключа, O9)",
                  hit == 1, "строк: %d" % hit)
        except psycopg2.Error as exc:
            check("то же имя роли в ДРУГОЙ конфигурации принимается (граница ключа, O9)",
                  False, str(exc).splitlines()[0][:200])
        finally:
            cur.execute("ROLLBACK TO SAVEPOINT v49_p3_other")

        second = dict(first, object_uuid=str(uuid_module.uuid4()))
        stamp_revision_rows([second], revision_no=FIRST_REVISION + 1,
                            changed_by=CHANGED_BY_EDIT)
        CONFIGURATION_OBJECT_WRITERS[ROLE_TABLE].insert(cur, second)
        cur.execute("SELECT revision_no, object_uuid, " + COMMIT_FLAG_COLUMN + " FROM "
                    + VIEWS[ROLE_TABLE] + " WHERE configuration_uuid = %s "
                    "AND object_name = %s", (cfg_uuid, name))
        got = cur.fetchall()
        check("витрина текущего состояния отдаёт одну строку — вторую ревизию",
              len(got) == 1 and got[0][0] == FIRST_REVISION + 1
              and str(got[0][1]).lower() == second["object_uuid"].lower(), str(got))
        history = int(one(cur, "SELECT count(*) FROM " + ROLE_TABLE
                             + " WHERE configuration_uuid = %s AND object_name = %s",
                             (cfg_uuid, name)) or 0)
        check("прежняя ревизия остаётся в таблице историей", history == 2,
              "строк в цепочке: %d" % history)
        confirmed = int(one(cur, "SELECT count(*) FROM " + ROLE_TABLE
                                + " WHERE configuration_uuid = %s AND object_name = %s "
                                "AND changed_by = %s AND " + COMMIT_FLAG_COLUMN,
                                (cfg_uuid, name, CHANGED_BY_EDIT)) or 0)
        check("строка правки остаётся неподтверждённой (D12)", confirmed == 0, confirmed)

        old_rights = int(one(cur, "SELECT count(*) FROM " + RIGHTS_TABLE
                                 + " WHERE role_id = %s", (role_id,)) or 0)
        current_rights = int(one(cur, "SELECT count(*) FROM " + RIGHTS_VIEW
                                     + " WHERE role_id = %s", (role_id,)) or 0)
        check("прав первой ревизии в витрине не осталось — она следует за ролью (Q2 A)",
              current_rights == 0, "строк в витрине: %d" % current_rights)
        check("строки прав первой ревизии остаются в таблице историей, а не удаляются",
              old_rights > 0, "строк в таблице: %d" % old_rights)

        cur.execute("SAVEPOINT v49_p3_cascade")
        cur.execute("DELETE FROM " + ROLE_TABLE + " WHERE id = %s", (role_id,))
        left_rights = int(one(cur, "SELECT count(*) FROM " + RIGHTS_TABLE
                                  + " WHERE role_id = %s", (role_id,)) or 0)
        left_sources = int(one(cur, "SELECT count(*) FROM " + SOURCES_TABLE
                                   + " WHERE configuration_uuid = %s AND object_name = %s",
                                   (cfg_uuid, name)) or 0)
        check("снятие строки роли снимает её права (FK role_id ON DELETE CASCADE)",
              left_rights == 0 and old_rights > 0,
              "прав до: %d, после: %d" % (old_rights, left_rights))
        check("дескриптор файла при этом остаётся: внешнего ключа к роли у него нет (Q8 A)",
              left_sources == 1, "дескрипторов: %d" % left_sources)
        cur.execute("ROLLBACK TO SAVEPOINT v49_p3_cascade")

        if report["template_rows"]:
            template = dict(report["template_rows"][0], configuration_uuid=cfg_uuid)
            stamp_revision_rows([template], revision_no=FIRST_REVISION,
                                changed_by=CHANGED_BY_LOAD)
            expect_violation(
                cur, "повтор текста шаблона той же ревизии отклоняется ключом (name, digest)",
                TEMPLATES_TABLE, template,
                "role_restriction_templates_config_name_digest_revision_key")
            template_next = dict(template, revision_no=FIRST_REVISION + 1,
                                 changed_by=CHANGED_BY_EDIT)
            CONFIGURATION_OBJECT_WRITERS[TEMPLATES_TABLE].insert(cur, template_next)
            shown = int(one(cur, "SELECT count(*) FROM " + VIEWS[TEMPLATES_TABLE]
                                + " WHERE configuration_uuid = %s AND name = %s "
                                "AND digest = %s",
                                (cfg_uuid, template["name"], template["digest"])) or 0)
            check("цепочка текста продолжается по паре (имя, отпечаток), текущей становится "
                  "вторая ревизия", shown == 1, "строк в витрине: %d" % shown)
        else:
            note("текстов ограничений в этой выгрузке нет — цепочка пары (имя, отпечаток) "
                 "проверяется на выгрузках, где они есть (MinCfg, BGU2, BP3)")

        if report["source_rows"]:
            source = dict(report["source_rows"][0], configuration_uuid=cfg_uuid)
            stamp_revision_rows([source], revision_no=FIRST_REVISION + 1,
                                changed_by=CHANGED_BY_EDIT)
            CONFIGURATION_OBJECT_WRITERS[SOURCES_TABLE].insert(cur, source)
            shown = int(one(cur, "SELECT count(*) FROM " + VIEWS[SOURCES_TABLE]
                                + " WHERE configuration_uuid = %s AND object_name = %s",
                                (cfg_uuid, source["object_name"])) or 0)
            check("цепочка дескриптора файла продолжается по имени роли",
                  shown == 1, "строк в витрине: %d" % shown)
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v49_p3_chain")


def index_rows_of(dump_dir):
    """Записи `ConfigDumpInfo.xml` выгрузки — свои, а не из помощника другой группы.

    Разрешение цели права требует `object_id` и `uuid` строки индекса целиком: помощник,
    который снимает поле, дал бы состояния `unresolved` там, где цель разрешима.
    """
    path = find_config_dump_info(str(dump_dir))
    if path is None:
        return [], "ConfigDumpInfo.xml не найден в корне выгрузки"
    parsed = parse_config_dump_info(str(path))
    if not parsed.get("success"):
        return [], str(parsed.get("error") or "индекс не разобран")
    return list(parsed.get("objects") or []), None


def table_baseline(cur, cfg_uuid):
    """Базовое состояние четырёх таблиц: {таблица: (всего строк, строк этой конфигурации)}."""
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

    report = CR.collect_roles(str(dump_dir), index_rows=index_rows)
    check("%s: файлы вида разбираются без отказов" % name, report["success"],
          report["files_failed"][:2] if report["files_failed"] else 0)
    baseline = BASELINE_ROWS[name]
    check("%s: круг ролей совпадает с базовой линией замера П3 (%d)"
          % (name, baseline[ROLE_TABLE]),
          len(report["role_rows"]) == baseline[ROLE_TABLE], len(report["role_rows"]))
    check("%s: файлы вида и записи индекса состава совпадают" % name,
          not report["file_only"] and not report["index_only"]
          and not report["uuid_mismatch"] and not report["roles_without_uuid"],
          "file_only %d, index_only %d, uuid_mismatch %d, без uuid %d"
          % (len(report["file_only"]), len(report["index_only"]),
             len(report["uuid_mismatch"]), len(report["roles_without_uuid"])))
    check_contract_matches_writer(report, baseline)
    note("контракт разбора: ролей %d, прав %d, целей %d, вхождений шаблонов %d, "
         "текстов %d, дескрипторов %d"
         % (report["roles_read"], report["rights_total"], report["targets_total"],
            report["template_occurrences"], len(report["template_rows"]),
            len(report["source_rows"])))

    before = None
    conn = connect()
    try:
        cur = conn.cursor()
        # Инвариант тот же, что у пробы П3 узла V48 после её шага П4: таблицы больше не
        # пустуют глобально — стадии конвейера пишут реальный состав загруженных
        # конфигураций. Проверяемое свойство не изменилось: проба ничего не меняет в базе.
        # Поэтому базовое состояние читается ДО записи, снятие идёт по кругу этой
        # конфигурации (сначала дети, потом роль — порядок, обратный записи), а откат
        # обязан вернуть ровно прочитанное до состояние.
        before = table_baseline(cur, cfg_uuid)
        for table in TABLES:
            if before[table][1]:
                note("%s: в таблице уже есть %d строк этой конфигурации — они сняты внутри "
                     "транзакции пробы и вернутся после отката"
                     % (table, before[table][1]))
        removed = {}
        cur.execute("DELETE FROM " + RIGHTS_TABLE + " WHERE configuration_uuid = %s",
                    (cfg_uuid,))
        removed[RIGHTS_TABLE] = cur.rowcount
        for table in (TEMPLATES_TABLE, SOURCES_TABLE, ROLE_TABLE):
            cur.execute("DELETE FROM " + table + " WHERE configuration_uuid = %s",
                        (cfg_uuid,))
            removed[table] = cur.rowcount
        for table in TABLES:
            check("%s: прежние строки этой конфигурации сняты внутри транзакции" % table,
                  removed[table] == before[table][1], "снято %d" % removed[table])
        written, moment, role_ids, right_rows, unbound, without_id = write_all(
            cur, cfg_uuid, report)
        check("метка события названа (M2)", bool(moment), str(moment))
        check_written(cur, cfg_uuid, name, report, written, unbound, without_id)
        check_link_integrity(cur, cfg_uuid, report)
        check_round_trip(cur, cfg_uuid, report, role_ids)
        check_named_constraints(cur, cfg_uuid, role_ids)
        check_state_reachability(cur, cfg_uuid, role_ids)
        check_chain(cur, cfg_uuid, report, role_ids)
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
        check("после отката четыре таблицы вернулись к базовому состоянию", not bad,
              "; ".join("%s: всего %d (было %d), этой конфигурации %d (было %d)"
                        % (table, after[table][0], before[table][0], after[table][1],
                           before[table][1]) for table in bad) or "состояние совпадает")
    finally:
        conn_after.close()


def main():
    print("ПРОГОН V49 (П3): писатели содержимого ролей")
    print("писатели: RolesRowWriter, RoleRightsRowWriter, "
          "RoleRestrictionTemplatesRowWriter, RoleSourcesRowWriter "
          "(src/external_table_writer.py); разбор: src/configuration_roles.py")
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
