#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Шаг П3 узла V48: прогон писателя `session_parameters` в живую схему.

Предмет — путь ЗАПИСИ: контракт разбора П2 (`collect_session_parameters`) проходит через
`SessionParametersRowWriter` в таблицу узла П1. Офлайн-прогон П2 отвечал на вопрос «что мы
знаем о выгрузке»; этот отвечает на «знаемое доходит до таблицы без потерь и без домыслов»:
CHECK'ы по имени, NOT NULL, уникальный индекс цепочки, витрина текущего состояния,
сохранность jsonb-записей `types` и квалификаторов, пустой массив как состояние.

Транзакция в конце ОТКАТЫВАЕТСЯ намеренно: прогон проверяет запись, а не оставляет в базе
строк, которых оператор не просил. Числа читаются внутри той же транзакции, а после отката
новым соединением проверяется, что таблица вернулась к базовому состоянию — с узла V48 (шаг
П4) пустота таблицы целиком инвариантом не является: конвейер пишет в неё реальный состав
загруженных конфигураций, поэтому проверяется равенство числа строк до и после (и всего, и
строк этой конфигурации).

Индекс состава берётся из `ConfigDumpInfo.xml` той же выгрузки (не из V46-помощника: тот
снимает поле `uuid`, а разрешение ссылок без него теряет цель). Поэтому ссылки в строках
разрешаются настоящие, и отдельной проверкой читается GIN-запрос containment по
`target_object_uuid` — именно ради него индекс `jsonb_path_ops` заводился (замер 2.5).

Отдельные проверки, которых нет в `tools/check_v19_revisions.py`:
  * спецификация писателя совпадает с живой схемой: объявленная колонка существует, а каждая
    NOT NULL-колонка без DEFAULT объявлена писателем (иначе вставка упала бы на NULL);
  * строка «типа не было» записывается пустым массивом и состоянием `absent` — состояние
    достижимо через писателя, а не только через DEFAULT колонки;
  * каждое нарушение называется ограничением по имени (замер 2.10 повторяется на пути записи);
  * дубль по ключу цепочки `(configuration_uuid, object_name, revision_no)` отклоняется, а
    то же имя в другой конфигурации принимается (граница ключа Q2);
  * вторая ревизия с ДРУГИМ `object_uuid` продолжает цепочку, и витрина отдаёт только её;
  * строка правки (`changed_by='edit'`) остаётся неподтверждённой (D12);
  * round-trip: записи `types`, квалификаторы, `type_raw`, `synonym` и `source_path`
    возвращаются из таблицы ровно теми, что отдал разбор;
  * ограничения, которых писатель НЕ выражает (не-список в `types`, половина штампа ревизии),
    проверяются прямым `INSERT` (`expect_sql_violation`): писатель их нормализует, и путать
    «писатель отверг» с «схема отвергла» нельзя;
  * containment по цели считает СТРОКИ-параметры, а не вхождения: параметр может ссылаться на
    один тип цели дважды (замер 2.5 — 2 файла с двумя ссылками), и сравнение ведётся с числом
    строк контракта.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v48_p3_writer_probe.py [MinCfg|KomMag|BGU2|BP3]
Код возврата 0 — расхождений нет; после отката таблица возвращена к базовому состоянию
(с узла V48 П4 глобальная пустота таблицы больше не инвариант: конвейер пишет в неё
реальный состав загруженных конфигураций — проверяется равенство состояния до и после).
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

import configuration_session_parameters as SP  # noqa: E402
from config_dump_info_parser import find_config_dump_info, parse_config_dump_info  # noqa: E402
from configuration_root_module_loader import configuration_uuid_from_layout  # noqa: E402
from current_revision import (  # noqa: E402
    CHANGED_BY_EDIT, CHANGED_BY_LOAD, COMMIT_FLAG_COLUMN, CONFIGURATION_VERSIONED_TABLES,
    FIRST_REVISION, REVISION_COLUMNS, current_view, stamp_revision_rows,
)
from external_db import connect  # noqa: E402
from external_table_writer import CONFIGURATION_OBJECT_WRITERS  # noqa: E402

TABLE = "session_parameters"
DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
BASELINE_FILES = {"MinCfg": 2, "KomMag": 6, "BGU2": 101, "BP3": 98}

FIXTURE_DIR = ROOT / "_scratch" / "v48_p3_fixtures"
FIXED_UUID = "11111111-2222-3333-4444-555555555555"
HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" '
    'xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" '
    'xmlns:v8="http://v8.1c.ru/8.1/data/core" '
    'xmlns:xs="http://www.w3.org/2001/XMLSchema">\n'
)

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
                     r"[0-9a-f]{4}-[0-9a-f]{12}$")

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


# ── статическая часть: круг таблиц, спецификация против живой схемы ────────────────────
def check_registry():
    print("\n=== писатель и круг версионных таблиц конфигурации ===")
    check("словарь писателей покрывает круг версионных таблиц ровно",
          sorted(CONFIGURATION_OBJECT_WRITERS) == sorted(CONFIGURATION_VERSIONED_TABLES),
          ", ".join(sorted(CONFIGURATION_OBJECT_WRITERS)))
    for table in CONFIGURATION_VERSIONED_TABLES:
        writer = CONFIGURATION_OBJECT_WRITERS.get(table)
        if writer is None:
            check(f"{table}: писатель объявлен", False, "в словаре нет класса")
            continue
        check(f"{table}: TABLE писателя совпадает с ключом словаря",
              writer.TABLE == table, writer.TABLE)
        check(f"{table}: таблица версионируется (колонки ревизии в спецификации)",
              writer.versioned() and all(column in writer.COLUMNS for column in REVISION_COLUMNS),
              str(sorted(REVISION_COLUMNS)))
        check(f"{table}: витрина текущего состояния названа точкой доступа",
              current_view(table) != "", current_view(table))
        check(f"{table}: писатель не объяляет вычисляемых колонок (id, tsv)",
              "id" not in writer.COLUMNS and "tsv" not in writer.COLUMNS,
              str(len(writer.COLUMNS)) + " колонок")


def check_writer_matches_schema(cur):
    """Спецификация писателя против живой схемы (information_schema).

    Две ошибки, которые иначе видны только отказом вставки: писатель объявляет колонку,
    которой в схеме нет (опечатка в имени читается как «нет такого столбца»), и писатель НЕ
    объявляет обязательную колонку — тогда вставка падает на NOT NULL, и виновата не выгрузка,
    а спецификация.
    """
    print("\n=== спецификация писателя против живой схемы ===")
    writer = CONFIGURATION_OBJECT_WRITERS[TABLE]
    cur.execute(
        "SELECT column_name, is_nullable, column_default FROM information_schema.columns "
        "WHERE table_name = %s ORDER BY ordinal_position", (TABLE,))
    schema = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
    check("таблица узла П1 существует в живой схеме", bool(schema),
          "%d колонок" % len(schema))
    undeclared = sorted(set(writer.COLUMNS) - set(schema))
    check("писатель не объявляет колонок, которых нет в схеме",
          not undeclared, ", ".join(undeclared) if undeclared else
          "колонок в спецификации: %d" % len(writer.COLUMNS))
    # Колонки, которые схема обязывает заполнить: NOT NULL без DEFAULT. `id` выпущен из
    # правила намеренно — его даёт последовательность, а не писатель.
    required = sorted(name for name, (nullable, default) in schema.items()
                      if nullable == "NO" and default is None and name != "id")
    missing = sorted(name for name in required if name not in writer.COLUMNS)
    check("каждая NOT NULL-колонка без DEFAULT объявлена писателем",
          not missing, "обязательных %d, не объявлено: %s"
          % (len(required), ", ".join(missing) if missing else "нет"))
    note("обязательных колонок без DEFAULT: %d (%s)" % (len(required), ", ".join(required)))
    outside = sorted(name for name in schema if name not in writer.COLUMNS and name != "id")
    note("колонок вне спецификации (их даёт DEFAULT или последовательность): %s"
         % (", ".join(outside) if outside else "нет"))


def check_contract_matches_writer(rows):
    """Ключи контракта разбора против спецификации писателя: расхождение видно по именам.

    `configuration_uuid` из сравнения снята осознанно: её в контракте разбора нет по
    замыслу (uuid заголовка знает загрузчик, а не XML объекта — порядок узла V44), и
    подставляет её вызывающий перед вставкой.
    """
    if not rows:
        check("контракт разбора сопоставлен спецификации", False, "строк нет — проверять нечем")
        return
    writer = CONFIGURATION_OBJECT_WRITERS[TABLE]
    declared = set(writer.COLUMNS) - set(REVISION_COLUMNS) - {"configuration_uuid"}
    produced = set()
    for row in rows:
        produced |= set(row)
    missing = sorted(declared - produced)
    extra = sorted(produced - declared)
    check("контракт разбора покрывает колонки писателя",
          not missing, "колонок без значения: " + (", ".join(missing) if missing else "нет"))
    check("у разбора нет поля вне спецификации писателя",
          not extra, "лишние поля: " + (", ".join(extra) if extra else "нет"))


# ── запись и чтение внутри одной транзакции ───────────────────────────────────────────
def write_all(cur, cfg_uuid, rows):
    """Записать строки писателем; вернуть число вставленных строк и метку события."""
    for row in rows:
        row["configuration_uuid"] = cfg_uuid
    # Один момент на всю загрузку (M2): строки одного события не должны нести разные метки.
    moment = stamp_revision_rows(rows, revision_no=FIRST_REVISION,
                                 changed_by=CHANGED_BY_LOAD)
    written = CONFIGURATION_OBJECT_WRITERS[TABLE].insert_many(cur, rows)
    return written, moment


def check_written(cur, cfg_uuid, rows, written):
    print("\n--- записанные строки ---")
    expected = len(rows)
    view = current_view(TABLE)
    total = int(one(cur, "SELECT count(*) FROM " + TABLE
                    + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0)
    current = int(one(cur, "SELECT count(*) FROM " + view
                       + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0)
    check("записано ровно по контракту разбора",
          total == expected and written == expected,
          "контракт %d, писатель %d, в таблице %d" % (expected, written, total))
    check("витрина текущего состояния отдаёт все строки первой ревизии",
          current == expected, "%d из %d" % (current, expected))
    by_load = int(one(cur, "SELECT count(*) FROM " + TABLE
                      + " WHERE configuration_uuid = %s AND changed_by = %s",
                      (cfg_uuid, CHANGED_BY_LOAD)) or 0)
    confirmed = int(one(cur, "SELECT count(*) FROM " + TABLE
                        + " WHERE configuration_uuid = %s AND " + COMMIT_FLAG_COLUMN,
                        (cfg_uuid,)) or 0)
    check("каждая строка — событие загрузки и подтверждена (D12)",
          by_load == expected and confirmed == expected,
          "changed_by='load' %d, подтверждено %d" % (by_load, confirmed))
    moments = int(one(cur, "SELECT count(DISTINCT changed_at) FROM " + TABLE
                           + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0)
    check("одна метка события на всю загрузку (M2)",
          moments == (1 if expected else 0), "разных меток: %d" % moments)
    other = int(one(cur, "SELECT count(*) FROM " + TABLE
                    + " WHERE configuration_uuid = %s AND revision_no <> %s",
                    (cfg_uuid, FIRST_REVISION)) or 0)
    check("ревизия первой загрузки — %d, других нет" % FIRST_REVISION,
          other == 0, "строк с другой ревизией: %d" % other)
    supplied = sum(1 for row in rows if row.get("configuration_uuid"))
    null_uuid = int(one(cur, "SELECT count(*) FROM " + TABLE
                             + " WHERE configuration_uuid IS NULL") or 0)
    check("вызывающий подставил configuration_uuid в каждую строку",
          supplied == expected and null_uuid == 0,
          "строк со значением: %d из %d" % (supplied, expected))


def check_round_trip(cur, cfg_uuid, rows):
    """Содержимое доходит до таблицы и возвращается из неё ровно тем, что отдал разбор.

    Сравнение идёт по колонкам, а не числами строк: `types` обязан вернуться записью с теми
    же ключами и в том же порядке, пустой `synonym` — остаться NULL (контракт
    `jsonb_nullable`), а не превратиться в `'{}'::jsonb`, `type_raw` — содержать столько
    тегов значений, сколько записей в массиве (текст не обрезан писателем).
    """
    print("\n--- круговая проверка содержимого ---")
    cur.execute(
        "SELECT object_name, object_uuid, full_name, comment, synonym, type_raw, "
        "type_multiplicity, type_parse_state, types, type_qualifiers, source_path "
        "FROM " + TABLE + " WHERE configuration_uuid = %s", (cfg_uuid,))
    stored = {row[0]: row for row in cur.fetchall()}
    problems = []
    wanted = {row["object_name"] for row in rows}
    for name in sorted(wanted - set(stored)):
        problems.append("строки %s в таблице нет" % name)
    for name in sorted(set(stored) - wanted):
        problems.append("в таблице появилась строка %s" % name)
    for row in rows:
        got = stored.get(row["object_name"])
        if not got:
            continue
        who = row["object_name"]
        if str(got[1]).lower() != str(row["object_uuid"]).lower():
            problems.append("%s: object_uuid изменён записью" % who)
        if got[2] != row["full_name"]:
            problems.append("%s: full_name не совпал с контрактом" % who)
        if got[3] != ((row["comment"] or "").strip() or None):
            problems.append("%s: comment потерян или изменён" % who)
        if got[4] != (row["synonym"] or None):
            problems.append("%s: synonym стал не тем (пустой обязан остаться NULL)" % who)
        expected_raw = (row["type_raw"] or "").strip() or None
        if got[5] != expected_raw:
            problems.append("%s: type_raw обрезан или изменён" % who)
        if got[6] != row["type_multiplicity"] or got[7] != row["type_parse_state"]:
            problems.append("%s: состояния кратности/разбора изменены" % who)
        if got[8] != row["types"]:
            problems.append("%s: записи types не совпали с контрактом" % who)
        if got[9] != (row["type_qualifiers"] or None):
            problems.append("%s: type_qualifiers потерян или изменён" % who)
        if got[10] != row["source_path"]:
            problems.append("%s: source_path изменён" % who)
        # Текст блока в таблице обязан нести столько тегов значений, сколько записей:
        # тот же guard, что нашёл дефект TYPE_BLOCK_RE на шаге П2, но на пути записи.
        if got[5] is not None and SP.count_value_type_tags(got[5]) != len(got[8] or []):
            problems.append("%s: в записанном type_raw тегов не по числу записей" % who)
    check("каждая строка возвращается из таблицы содержимым один-в-один",
          not problems, problems[:6])
    return stored


def check_aggregates(cur, cfg_uuid, stored, report):
    """Агрегаты по таблице против сводки разбора: потеря состояния видна числом."""
    print("\n--- сводка таблицы против сводки разбора ---")
    by_state, by_mult, by_class = {}, {}, {}
    for got in stored.values():
        by_state[got[7]] = by_state.get(got[7], 0) + 1
        by_mult[got[6]] = by_mult.get(got[6], 0) + 1
        for entry in got[8] or []:
            by_class[entry.get("class")] = by_class.get(entry.get("class"), 0) + 1
    check("состояния разбора в таблице совпадают со сводкой разбора",
          by_state == {k: v for k, v in report["counts_by_state"].items() if v},
          "в таблице %s, разбор %s" % (by_state, report["counts_by_state"]))
    check("кратность типов в таблице совпадает со сводкой разбора",
          by_mult == {k: v for k, v in report["types_multiplicity"].items() if v},
          "в таблице %s, разбор %s" % (by_mult, report["types_multiplicity"]))
    check("классы значений типа в таблице совпадают со сводкой разбора",
          by_class == {k: v for k, v in report["types_by_class"].items() if v},
          "в таблице %s, разбор %s" % (by_class, report["types_by_class"]))
    # Равенство full_name и object_name — факт замера 2.2; в CHECK его нет намеренно
    # (появление вложенных параметров отклонялась бы схема, которой этого не обещали).
    differ = int(one(cur, "SELECT count(*) FROM " + TABLE
                        + " WHERE configuration_uuid = %s"
                        " AND full_name IS DISTINCT FROM object_name", (cfg_uuid,)) or 0)
    check("full_name совпадает с object_name в каждой строке (замер 2.2)",
          differ == 0, "расхождений: %d" % differ)


def check_gin_and_paths(cur, cfg_uuid, rows, dump_dir):
    """Путь поиска по цели ссылки и путь файла: то, ради чего колонки и заведены."""
    print("\n--- индекс по цели ссылки и путь файла ---")
    refs = sum(1 for row in rows for entry in row["types"]
               if entry.get("class") == SP.CLASS_OBJECT_REF)
    resolved_all = sum(1 for row in rows for entry in row["types"]
                       if entry.get("resolved") is True)
    if refs:
        check("каждое ссылочное значение разрешено индексом своей выгрузки (замер 2.5)",
              resolved_all == refs, "разрешено %d из %d" % (resolved_all, refs))
    else:
        check("ссылочных значений в этой выгрузке нет — разрешать нечего",
              resolved_all == 0, "refs=0, resolved=%d" % resolved_all)
    resolved = [str(entry["target_object_uuid"]).lower() for row in rows
                for entry in row["types"]
                if entry.get("resolved") is True
                and UUID_RE.match(str(entry.get("target_object_uuid") or "").lower())]
    if not resolved:
        # Два разных состояния, и путать их нельзя: ссылок нет вовсе — и ссылки есть, но
        # индекс состава этой выгрузки не даёт uuid цели (запись `object_id` формы `dotted`,
        # старые выгрузки). В первом случае проверять нечем, во втором — нечем построить
        # ключ containment. Оба называются заметкой, потому что это состояние выгрузки,
        # а не отказ записи.
        if not refs:
            note("ссылочных значений в этой выгрузке нет — containment по uuid цели "
                 "проверять нечем")
        else:
            note("%d ссылочных значений, но ни одно не даёт uuid цели: запись индекса "
                 "состава этой выгрузки не несёт uuid (`object_id` формы `dotted`) — "
                 "ключ containment построит нечем" % refs)
    else:
        check("разрешённая ссылка несёт uuid цели формы uuid (ключ GIN-запроса)",
              len(resolved) > 0,
              "uuid-целей: %d из %d разрешённых (всего ссылок %d)"
              % (len(resolved), resolved_all, refs))
        checked = min(5, len(resolved))
        found = 0
        for target in resolved[:checked]:
            hit = int(one(cur, "SELECT count(*) FROM " + TABLE
                          + " WHERE configuration_uuid = %s AND types @> %s::jsonb",
                          (cfg_uuid, '[{"target_object_uuid": "%s"}]' % target)) or 0)
            if hit:
                found += 1
        check("containment-запрос по uuid цели находит строку (путь GIN-индекса)",
              found == checked, "найдено %d из %d" % (found, checked))
    # Containment считает СТРОКИ, а не вхождения: параметр может ссылаться на два каталога,
    # и в запросе по типу цели он будет один раз. Ответ запроса — «какие параметры ссылаются»,
    # а не «сколько ссылок»; сравнивать нужно с числом строк контракта, а не с числом записей.
    expected_catalog_rows = sum(1 for row in rows if any(
        entry.get("target_object_type") == "Catalog" for entry in row["types"]))
    catalog_entries = sum(1 for row in rows for entry in row["types"]
                         if entry.get("target_object_type") == "Catalog")
    multi = [(row["object_name"], sum(1 for entry in row["types"]
                                      if entry.get("target_object_type") == "Catalog"))
             for row in rows]
    multi = [(name, cnt) for name, cnt in multi if cnt >= 2]
    if catalog_entries != expected_catalog_rows:
        note("есть параметры с несколькими ссылками на один тип цели: %s — "
             "разница вхождений (%d) и строк (%d) объясняется ими"
             % (", ".join("%s (%d)" % (name, cnt) for name, cnt in multi),
                catalog_entries, expected_catalog_rows))
    by_type = int(one(cur, "SELECT count(*) FROM " + TABLE
                      + " WHERE configuration_uuid = %s AND types @> %s::jsonb",
                      (cfg_uuid, '[{"target_object_type": "Catalog"}]')) or 0)
    check("запрос по типу цели (`Catalog`) считает строки-параметры, а не вхождения",
          by_type == expected_catalog_rows,
          "в таблице строк %d, по контракту %d (вхождений %d)"
          % (by_type, expected_catalog_rows, catalog_entries))
    cur.execute("SELECT indexname FROM pg_indexes WHERE tablename = %s", (TABLE,))
    indexes = {str(row[0]) for row in cur.fetchall()}
    check("индекс цепочки и GIN по содержимому существуют фактом схемы",
          {"idx_session_parameters_object_uuid_revision",
           "idx_session_parameters_types_gin"} <= indexes, ", ".join(sorted(indexes)))
    missing = [row["source_path"] for row in rows
               if not (Path(dump_dir) / row["source_path"]).is_file()]
    check("source_path разрешается файлом от корня выгрузки",
          not missing, missing[:3] if missing else "путей: %d" % len(rows))
    outside = [row["source_path"] for row in rows
               if not row["source_path"].startswith(SP.DIR_NAME + "/")]
    check("путь задаётся от КОРНЯ выгрузки, а не от каталога вида (поправка V46)",
          not outside, outside[:3] if outside else "все пути вида %s/<Имя>.xml" % SP.DIR_NAME)


# ── ограничения: каждое называется по имени (замер 2.10 на пути записи) ────────────────
def expect_violation(cur, label, row, constraints):
    """Нарушение читается именованным ограничением, а не текстом ошибки.

    Имя ограничения psycopg2 отдаёт в `diag` (`constraint_name` на самом объекте исключения
    отсутствует), поэтому сравнивается именно оно — иначе прогон принимал бы любой отказ.
    `constraints` — имя или множество имён: пара значений может нарушать сразу два
    ограничения согласованности, и какое из них отчитывается первым, решает планировщик.
    """
    allowed = {constraints} if isinstance(constraints, str) else set(constraints)
    cur.execute("SAVEPOINT v48_p3")
    try:
        CONFIGURATION_OBJECT_WRITERS[TABLE].insert(cur, row)
        check(label, False, "строка принята — ограничение не сработало")
    except psycopg2.Error as exc:
        name = getattr(getattr(exc, "diag", None), "constraint_name", None) \
            or getattr(exc, "constraint_name", None)
        check(label + " — имя из ожидаемого набора", name in allowed,
              "нарушено: " + (name or str(exc).splitlines()[0][:200])
              + "; ожидалось одно из " + ", ".join(sorted(allowed)))
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v48_p3")


def expect_sql_violation(cur, label, sql, params, constraint):
    """Ограничение схемы проверяется прямым SQL, когда писатель его не выражает.

    Писатель нормализует значения под спецификацию (`jsonb_array` из не-списка даёт `[]`,
    `revision_row` дополняет половину штампа ревизии), поэтому часть состояний до таблицы
    просто не доходит — их проверяет схема, и проверяется она прямым вставлением.
    """
    cur.execute("SAVEPOINT v48_p3_sql")
    try:
        cur.execute(sql, params)
        check(label, False, "строка принята — ограничение не сработало")
    except psycopg2.Error as exc:
        name = getattr(getattr(exc, "diag", None), "constraint_name", None) \
            or getattr(exc, "constraint_name", None)
        check(label, name == constraint,
              "нарушено: " + (name or str(exc).splitlines()[0][:200]))
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v48_p3_sql")



def expect_rejected(cur, label, row, marker):
    """Отказ без именованного ограничения (NOT NULL): проверяется текстом ошибки."""
    cur.execute("SAVEPOINT v48_p3")
    try:
        CONFIGURATION_OBJECT_WRITERS[TABLE].insert(cur, row)
        check(label, False, "строка принята")
    except psycopg2.Error as exc:
        text = str(exc).splitlines()[0]
        check(label, marker in text, text[:200])
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v48_p3")


def raw_insert_sql(changed_at="now()", changed_by="'load'"):
    """Прямой INSERT строки узла П1 — проверка ограничений схемы, а не писателя.

    Колонки перечислены явно: видно, какая из них участвует в проверке. `types` идёт
    параметром (`::jsonb`), а `changed_at`/`changed_by` — литералами SQL, потому что ровно
    пара «половина штампа» и есть предмет проверки. Порядок параметров —
    `RAW_INSERT_PARAMS_ORDER`.
    """
    return ("INSERT INTO " + TABLE + " (configuration_uuid, object_uuid, object_name, "
            "full_name, type_multiplicity, type_parse_state, types, source_path, "
            "revision_no, changed_at, changed_by, is_committed) "
            "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s::jsonb, %s, 1, "
            + changed_at + ", " + changed_by + ", true)")


RAW_INSERT_PARAMS_ORDER = ("configuration_uuid", "object_uuid", "object_name", "full_name",
                           "type_multiplicity", "type_parse_state", "types", "source_path")


def check_named_constraints(cur, cfg_uuid, rows):
    print("\n--- нарушения называются ограничениями по имени ---")
    if not rows:
        check("отрицательные случаи построены", False, "строк разбора нет — базовой строки нет")
        return
    base = dict(rows[0])

    def variant(**changes):
        row = dict(base)
        row["object_name"] = "ПробаОграничений"
        row["full_name"] = "ПробаОграничений"
        row["source_path"] = SP.DIR_NAME + "/ПробаОграничений.xml"
        row["object_uuid"] = FIXED_UUID
        row.update(changes)
        return row

    entry = dict(base["types"][0]) if base["types"] else {
        "index": 0, "value": "xs:boolean", "ns_uri": SP.NS_XML_SCHEMA,
        "class": SP.CLASS_PRIMITIVE, "state": SP.ENTRY_STATE_PARSED, "resolved": False}
    two = [entry, dict(entry, index=1)]
    expect_violation(cur, "две записи при кратности single отклоняется",
                     variant(types=two, type_multiplicity=SP.MULT_SINGLE),
                     "session_parameters_type_multiplicity_matches_types")
    # Пустой массив при кратности `single` нарушает сразу два ограничения согласованности
    # («пустой массив — только когда блока нет» и «пустого массива при кратности нет»);
    # какое из них отчитывается — решает порядок проверки, поэтому ожидается любое из
    # набора, а не выдуманное одно.
    expect_violation(cur, "пустой массив при кратности single отклоняется",
                     variant(types=[], type_multiplicity=SP.MULT_SINGLE,
                             type_parse_state=SP.STATE_UNKNOWN_FORM, type_raw=None),
                     {"session_parameters_types_absent_matches_no_block",
                      "session_parameters_type_multiplicity_matches_types"})
    expect_violation(cur, "пустой массив при состоянии parsed отклоняется",
                     variant(types=[], type_multiplicity=SP.MULT_ABSENT,
                             type_parse_state=SP.STATE_PARSED, type_raw=None),
                     "session_parameters_types_absent_matches_no_block")
    expect_violation(cur, "кратность вне словаря отклоняется",
                     variant(type_multiplicity="many"),
                     "session_parameters_type_multiplicity_known")
    expect_violation(cur, "состояние разбора вне словаря отклоняется",
                     variant(type_parse_state="unknown"),
                     "session_parameters_type_parse_state_known")
    # Писатель не пропускает в jsonb-колонку не-список: вид `jsonb_array` приводит его к
    # `[]`, поэтому в таблицу приходит пара «пустой массив + single», и её отклоняет
    # ограничение кратности. Само ограничение формы массива проверяется схемой прямым
    # вставлением (замер 2.10, случай 6): через писатель не-массив не проходит.
    expect_violation(cur, "не-список в types писатель приводит к пустому массиву, и строка отклоняется кратностью",
                     variant(types={"index": 0}),
                     "session_parameters_type_multiplicity_matches_types")
    expect_sql_violation(
        cur, "types не-массивом схема отклоняет с именем, а не внутренней ошибкой",
        raw_insert_sql(),
        (cfg_uuid, FIXED_UUID, "ПробаНеМассив", "ПробаНеМассив",
         SP.MULT_SINGLE, SP.STATE_PARSED, '{"index": 0}',
         SP.DIR_NAME + "/ПробаНеМассив.xml"),
        "session_parameters_types_is_array")
    expect_violation(cur, "revision_no = 0 отклоняется",
                     variant(revision_no=0),
                     "session_parameters_revision_no_positive")
    expect_rejected(cur, "пустого object_name схема не принимает (строку нечем ключить)",
                    variant(object_name=None), 'null value in column "object_name"')
    expect_rejected(cur, "пустого object_uuid схема не принимает",
                    variant(object_uuid=None), 'null value in column "object_uuid"')

    # Половину штампа ревизии писатель дополняет сам (`revision_row`, документированное
    # поведение): в таблицу не приходит `changed_at` без `changed_by`. Проверяется фактом —
    # какой штамп лёг в строку, а не комментарием о поведении класса.
    cur.execute("SAVEPOINT v48_p3_pair")
    try:
        CONFIGURATION_OBJECT_WRITERS[TABLE].insert(cur, variant(changed_by=None))
        cur.execute("SELECT changed_by, changed_at IS NOT NULL, is_committed FROM " + TABLE
                    + " WHERE configuration_uuid = %s AND object_name = %s",
                    (cfg_uuid, "ПробаОграничений"))
        pair = cur.fetchall()
        check("половину штампа ревизии писатель дополняет значением загрузки (revision_row)",
              len(pair) == 1 and pair[0][0] == CHANGED_BY_LOAD and pair[0][1] is True,
              str(pair))
    except psycopg2.Error as exc:
        check("половину штампа ревизии писатель дополняет значением загрузки (revision_row)",
              False, str(exc).splitlines()[0][:200])
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v48_p3_pair")
    expect_sql_violation(
        cur, "половину штампа (changed_at без changed_by) схема отклоняет сама (пара M2)",
        raw_insert_sql(changed_at="now()", changed_by="NULL"),
        (cfg_uuid, FIXED_UUID, "ПробаПара", "ПробаПара",
         SP.MULT_ABSENT, SP.STATE_ABSENT, "[]", SP.DIR_NAME + "/ПробаПара.xml"),
        "session_parameters_changed_pair_check")


    # Состояние «типа не было» достижимо через писателя, а не только через DEFAULT колонки:
    # пустой массив обязан дойти до таблицы массивом, а не NULL.
    cur.execute("SAVEPOINT v48_p3_absent")
    try:
        absent = variant(types=[], type_multiplicity=SP.MULT_ABSENT,
                         type_parse_state=SP.STATE_ABSENT, type_raw=None,
                         type_qualifiers=None, synonym=None, comment=None)
        CONFIGURATION_OBJECT_WRITERS[TABLE].insert(cur, absent)
        cur.execute("SELECT types, type_multiplicity, type_parse_state, synonym, "
                    "jsonb_typeof(types), type_raw FROM " + TABLE
                    + " WHERE configuration_uuid = %s AND object_name = %s",
                    (cfg_uuid, "ПробаОграничений"))
        stored = cur.fetchall()
        check("строка «типа не было» записывается пустым массивом и состоянием absent",
              len(stored) == 1 and stored[0][0] == [] and stored[0][1] == SP.MULT_ABSENT
              and stored[0][2] == SP.STATE_ABSENT and stored[0][3] is None
              and stored[0][4] == "array" and stored[0][5] is None,
              str(stored))
        in_view = int(one(cur, "SELECT count(*) FROM " + current_view(TABLE)
                              + " WHERE configuration_uuid = %s AND object_name = %s",
                          (cfg_uuid, "ПробаОграничений")) or 0)
        check("витрина текущего состояния отдаёт строку состояния absent",
              in_view == 1, in_view)
    except psycopg2.Error as exc:
        check("строка «типа не было» записывается пустым массивом и состоянием absent",
              False, str(exc).splitlines()[0][:200])
        check("витрина текущего состояния отдаёт строку состояния absent", False, "строки нет")
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v48_p3_absent")


# ── цепочка состояния: ключ (configuration_uuid, object_name, revision_no) ─────────────
def check_chain(cur, cfg_uuid, rows):
    print("\n--- цепочка состояния и граница ключа (Q2) ---")
    if not rows:
        check("случаи цепочки построены", False, "строк разбора нет")
        return
    first = dict(rows[0])
    name = first["object_name"]
    expect_violation(
        cur, "повторная вставка той же ревизии отклоняется уникальным индексом цепочки",
        dict(first, object_uuid=str(uuid_module.uuid4())),
        "session_parameters_configuration_object_revision_key")

    # Граница ключа Q2: тот же object_name в ДРУГОЙ конфигурации — не дубль.
    other_cfg = str(uuid_module.uuid4())
    cur.execute("SAVEPOINT v48_p3_other")
    try:
        CONFIGURATION_OBJECT_WRITERS[TABLE].insert(cur, dict(first, configuration_uuid=other_cfg))
        hit = int(one(cur, "SELECT count(*) FROM " + TABLE
                      + " WHERE configuration_uuid = %s AND object_name = %s",
                      (other_cfg, name)) or 0)
        check("то же имя в другой конфигурации принимается (граница ключа Q2)",
              hit == 1, "строк: %d" % hit)
    except psycopg2.Error as exc:
        check("то же имя в другой конфигурации принимается (граница ключа Q2)",
              False, str(exc).splitlines()[0][:200])
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v48_p3_other")

    # Вторая ревизия с ДРУГИМ object_uuid продолжает цепочку: ключ — имя, а не uuid (Q2).
    second = dict(first)
    second["object_uuid"] = str(uuid_module.uuid4())
    stamp_revision_rows([second], revision_no=FIRST_REVISION + 1, changed_by=CHANGED_BY_EDIT)
    CONFIGURATION_OBJECT_WRITERS[TABLE].insert(cur, second)
    view = current_view(TABLE)
    cur.execute(
        "SELECT revision_no, object_uuid, is_committed FROM " + view
        + " WHERE configuration_uuid = %s AND object_name = %s", (cfg_uuid, name))
    got = cur.fetchall()
    check("витрина текущего состояния отдаёт одну строку — вторую ревизию",
          len(got) == 1 and got[0][0] == FIRST_REVISION + 1
          and str(got[0][1]).lower() == second["object_uuid"].lower(),
          str(got))
    history = int(one(cur, "SELECT count(*) FROM " + TABLE
                        + " WHERE configuration_uuid = %s AND object_name = %s",
                      (cfg_uuid, name)) or 0)
    check("прежняя ревизия остаётся в таблице историей (снимается только текущность)",
          history == 2, "строк в цепочке: %d" % history)
    edit_committed = int(one(cur, "SELECT count(*) FROM " + TABLE
                             + " WHERE configuration_uuid = %s AND object_name = %s"
                             " AND changed_by = %s AND " + COMMIT_FLAG_COLUMN,
                             (cfg_uuid, name, CHANGED_BY_EDIT)) or 0)
    check("строка правки остаётся неподтверждённой (D12)",
          edit_committed == 0, "подтверждённых строк правки: %d" % edit_committed)
    note("цепочка идёт по object_name: вторая ревизия с новым object_uuid продолжает её, а "
         "не начинает заново — uuid вида повторяется в разных конфигурациях (82 из 125, "
         "замер _v48_q2_key_probe.py), поэтому ключом он быть не может.")


# ── прогон по выгрузке ────────────────────────────────────────────────────────────────
def index_rows_of(dump_dir):
    """Записи `ConfigDumpInfo.xml` выгрузки — свои, а не из V46-помощника.

    Помощник V46 (`configuration_object_properties.index_rows_from_dump`) отдаёт строки без
    поля `uuid` (для подсистем цель разрешается именем), а разрешение ссылочного типа
    параметра сеанса обязано получить uuid цели — иначе ключ `target_object_uuid` в jsonb
    остаётся пустым и GIN-индекс некому проверять.
    """
    path = find_config_dump_info(str(dump_dir))
    if path is None:
        return [], "ConfigDumpInfo.xml не найден в корне выгрузки"
    parsed = parse_config_dump_info(str(path))
    if not parsed.get("success"):
        return [], str(parsed.get("error") or "индекс не разобран")
    return list(parsed.get("objects") or []), None


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

    report = SP.collect_session_parameters(str(dump_dir), index_rows=index_rows)
    check("%s: файлы регистрации разбираются без ошибок" % name, not report["files_failed"],
          report["files_failed"][:2] if report["files_failed"] else 0)
    check("%s: круг совпадает с замером 2.1 (%d)" % (name, BASELINE_FILES[name]),
          report["files_found"] == BASELINE_FILES[name],
          "файлов %d, строк %d" % (report["files_found"], len(report["rows"])))
    check("%s: файл регистрации и перечень индекса состава совпадают" % name,
          not report["file_only"] and not report["index_only"] and not report["uuid_mismatch"],
          "file_only %d, index_only %d, uuid_mismatch %d"
          % (len(report["file_only"]), len(report["index_only"]), len(report["uuid_mismatch"])))
    check_contract_matches_writer(report["rows"])
    note("контракт разбора: строк %d, значений %d, состояний %s"
         % (len(report["rows"]), report["types_total"], report["counts_by_state"]))

    conn = connect()
    try:
        cur = conn.cursor()
        # Инвариант пробы меняет формулировку с узла V48 (шаг П4): таблица больше не пустуется
        # глобально — стадии конвейера пишут в неё реальный состав загруженных конфигураций
        # (замер 29.10.2026: строки MinCfg записал конвейер в пробе `_v48_p4_loader_probe.py`).
        # Проверяемое свойство то же: проба ничего не меняет в базе. Значит базовое состояние
        # читается ДО записи (сколько строк этой конфигурации и сколько строк всего), запись
        # идёт в снятом круге этой конфигурации, а откат обязан вернуть ровно это состояние.
        baseline_total = int(one(cur, "SELECT count(*) FROM " + TABLE) or 0)
        baseline_cfg = int(one(cur, "SELECT count(*) FROM " + TABLE
                                   + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0)
        if baseline_cfg:
            note("%s: в таблице уже есть %d строк этой конфигурации — они сняты внутри "
                 "транзакции пробы и вернутся после отката: проба не пишет поверх реального "
                 "состава и не считает чужие строки своими" % (name, baseline_cfg))
        cur.execute("DELETE FROM " + TABLE + " WHERE configuration_uuid = %s", (cfg_uuid,))
        removed_pre = cur.rowcount
        check("%s: прежние строки этой конфигурации сняты внутри транзакции" % name,
              removed_pre == baseline_cfg, "снято %d" % removed_pre)
        written, moment = write_all(cur, cfg_uuid, report["rows"])
        check("метка события названа (M2)", bool(moment), str(moment))
        check_written(cur, cfg_uuid, report["rows"], written)
        stored = check_round_trip(cur, cfg_uuid, report["rows"])
        check_aggregates(cur, cfg_uuid, stored, report)
        check_gin_and_paths(cur, cfg_uuid, report["rows"], str(dump_dir))
        check_named_constraints(cur, cfg_uuid, report["rows"])
        check_chain(cur, cfg_uuid, report["rows"])
        conn.rollback()
        check("транзакция откатана", True, "строк в базу не попало")
    except psycopg2.Error as exc:
        conn.rollback()
        check("запись прошла без ошибки схемы", False, str(exc).splitlines()[0][:300])
    finally:
        conn.close()

    conn_after = connect()
    try:
        left = int(one(conn_after.cursor(), "SELECT count(*) FROM " + TABLE) or 0)
        left_cfg = int(one(conn_after.cursor(), "SELECT count(*) FROM " + TABLE
                               + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0)
        check("после отката таблица вернулась к базовому состоянию",
              left == baseline_total and left_cfg == baseline_cfg,
              "всего %d (было %d), этой конфигурации %d (было %d)"
              % (left, baseline_total, left_cfg, baseline_cfg))
    finally:
        conn_after.close()


def main():
    print("ПРОГОН V48 (П3): писатель свойств параметров сеанса")
    print("писатель: SessionParametersRowWriter (src/external_table_writer.py); "
          "разбор: src/configuration_session_parameters.py")
    wanted = tuple(arg for arg in sys.argv[1:] if arg in DUMPS) or DUMPS
    check_registry()
    conn = connect()
    try:
        check_writer_matches_schema(conn.cursor())
    finally:
        conn.close()
    for name in wanted:
        run_dump(name)
    print("\nИТОГ: пройдено " + str(PASSED) + ", провалено " + str(FAILED)
          + ", заметок " + str(len(NOTES)))
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())








