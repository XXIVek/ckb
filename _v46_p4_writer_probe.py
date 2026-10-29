# -*- coding: utf-8 -*-
"""_v46_p4_writer_probe.py — прогон писателей четырёх таблиц свойств объектов (узел V46, П4).

Предмет — путь ЗАПИСИ: контракт разбора П3 (`collect_subsystems`/`collect_common_modules`)
проходит через писателей `src/external_table_writer.py` в живую схему. Офлайн-прогон П3
отвечал на вопрос «что мы знаем о выгрузке»; этот отвечает на «знаемое проходит в таблицу
без потерь и без домыслов»: CHECK'ы, NOT NULL, уникальные индексы цепочки состояния,
витрины текущего состояния, пары «путь ↔ состояние» и «значение ↔ событие».

Транзакция в конце ОТКАТЫВАЕТСЯ намеренно: прогон проверяет запись, а не оставляет в базе
строки, которых оператор не просил. Поэтому числа читаются внутри той же транзакции, а
после отката проверяется, что таблицы вернулись к базовому состоянию — числу строк, прочитанному
до записи. Формулировка «таблицы снова пусты» с 28.10.2026 этого свойства не выражала: конвейер
(узлы V45/V46 П5, V47, V48 П4) пишет в таблицы стадий реальный состав загруженных конфигураций,
и эти строки остаются в базе намеренно.

`configuration_uuid` берётся из `Configuration.xml` выгрузки (`configuration_uuid_from_layout`
узла V44), а не выдумывается: uuid заголовка знает источник, а не прогон. Внешнего ключа у
четырёх таблиц нет осознанно (прецедент V20.1), поэтому строки существуют и при незагруженном
заголовке — это состояние, и оно называется в выводе.

Отдельные проверки, которых нет в `tools/check_v19_revisions.py`:
  * повторная вставка той же строки отклоняется уникальным индексом цепочки (ключ
    `(configuration_uuid, full_name, revision_no)` — решение D8);
  * вторая ревизия по тому же `full_name` с ДРУГИМ `object_uuid` продолжает цепочку, и
    витрина отдаёт только её (D8 проверяется фактом, а не комментарием);
  * строка правки (`changed_by='edit'`) остаётся неподтверждённой (поправка D12);
  * `file_path` в таблице разрешается ровно состояниям с текстом модуля (поправка C-V46-1),
    а размер из таблицы совпадает с размером файла с диска;
  * пустое значение разбора остаётся NULL, а не `'{}'::jsonb` (контракт `jsonb_nullable`).

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v46_p4_writer_probe.py [MinCfg|BGU2|BP3]
Код возврата 0 — расхождений нет; после отката таблицы возвращены к базовому состоянию
(число строк каждой таблицы равно прочитанному до записи).
"""
import sys
import uuid as uuid_module
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import psycopg2  # noqa: E402

import configuration_object_properties as props  # noqa: E402
# Узел V48 (шаг П4, проба `_v48_p4_loader_probe.py`, 29.10.2026): круг этой пробы — таблицы
# стадии V46, а не весь круг версионности. С регистрации таблицы `session_parameters` (узел П1)
# эти два круга разошлись: чужую таблицу проба ни снимает, ни считает — иначе она проверяла бы
# запись чужой стадии и мешала ей. Реестр писателей ниже по-прежнему сверяется с полным кругом
# `CONFIGURATION_VERSIONED_TABLES`: он обязан покрывать все версионируемые таблицы.
from configuration_load_contract import CHILD_TABLES  # noqa: E402
from configuration_root_module_loader import configuration_uuid_from_layout  # noqa: E402
from current_revision import (  # noqa: E402
    CHANGED_BY_EDIT, CHANGED_BY_LOAD, COMMIT_FLAG_COLUMN, CONFIGURATION_VERSIONED_TABLES,
    FIRST_REVISION, REVISION_COLUMNS, current_view, stamp_revision_rows,
)
from external_db import connect  # noqa: E402
from external_table_writer import CONFIGURATION_OBJECT_WRITERS  # noqa: E402

BASE = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMP_NAMES = ("MinCfg", "BGU2", "BP3")

# Колонки, которых в контракте разбора нет по замыслу: их подставляет вызывающий
# (загрузчик) перед вставкой. uuid заголовка знает вызывающий, а не XML объекта — тот же
# порядок, что у писателей модулей корня (узел V44).
LOADER_SUPPLIED_COLUMNS = frozenset({"configuration_uuid"})

# Колонки, где пустое значение разбора обязано остаться NULL, а не превратиться в '{}'
# (контракт `jsonb_nullable`, узел V31): «свойства нет» и «свойство есть, но пустое».
NULLABLE_JSONB_COLUMNS = {
    "subsystems": ("synonym", "content", "content_unresolved", "picture"),
    "common_modules": ("synonym",),
}

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
    print("       " + text)


def one(cur, sql, params=None):
    cur.execute(sql, params or ())
    row = cur.fetchone()
    return row[0] if row else None


# ── статическая часть: круг таблиц и спецификации ─────────────────────────────────────
def check_registry():
    print("\n=== писатели и круг версионных таблиц ===")
    check("словарь писателей покрывает круг версионных таблиц конфигурации ровно",
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


def check_contract_matches_writer(rows_by_table):
    """Ключи контракта разбора против спецификации писателя: расхождение видно по именам.

    `configuration_uuid` из сравнения снята осознанно: её в контракте разбора нет по
    замыслу (uuid заголовка знает загрузчик, а не XML объекта — порядок узла V44), и
    подставляет её вызывающий перед вставкой. То, что подстановка сделана, проверяется
    счётчиком строк по `configuration_uuid` в `check_written`: строка без значения в этот
    счётчик не попала бы.
    """
    for table, rows in rows_by_table.items():
        if not rows:
            continue
        writer = CONFIGURATION_OBJECT_WRITERS[table]
        declared = set(writer.COLUMNS) - set(REVISION_COLUMNS) - LOADER_SUPPLIED_COLUMNS
        produced = set()
        for row in rows:
            produced |= set(row)
        missing = sorted(declared - produced)
        extra = sorted(produced - declared)
        check(f"{table}: контракт разбора покрывает колонки писателя",
              not missing, "колонок без значения: " + (", ".join(missing) if missing else "нет"))
        check(f"{table}: у разбора нет поля вне спецификации писателя",
              not extra, "лишние поля: " + (", ".join(extra) if extra else "нет"))


# ── запись и чтение внутри одной транзакции ───────────────────────────────────────────
def write_all(cur, cfg_uuid, collected):
    """Записать четыре группы писателями; вернуть {таблица: записано} и общий момент."""
    moment = None
    written = {}
    for table, rows in collected.items():
        writer = CONFIGURATION_OBJECT_WRITERS[table]
        for row in rows:
            row["configuration_uuid"] = cfg_uuid
        # Один момент на всю загрузку (M2): строки одного события не должны нести разные метки.
        moment = stamp_revision_rows(rows, revision_no=FIRST_REVISION,
                                     changed_by=CHANGED_BY_LOAD, changed_at=moment)
        written[table] = writer.insert_many(cur, rows)
    return written, moment


def check_written(cur, cfg_uuid, collected, written):
    print("\n--- записанные строки ---")
    for table in CHILD_TABLES:
        expected = len(collected[table])
        view = current_view(table)
        total = one(cur, "SELECT count(*) FROM " + table + " WHERE configuration_uuid = %s",
                    (cfg_uuid,))
        current = one(cur, "SELECT count(*) FROM " + view
                      + " WHERE configuration_uuid = %s", (cfg_uuid,))
        check(f"{table}: записано ровно по контракту разбора",
              total == expected and written[table] == expected,
              f"контракт {expected}, писатель {written[table]}, в таблице {total}")
        check(f"{table}: витрина текущего состояния отдаёт все строки первой ревизии",
              current == expected, f"{current} из {expected}")

        by_load = one(cur, "SELECT count(*) FROM " + table
                      + " WHERE configuration_uuid = %s AND changed_by = %s",
                      (cfg_uuid, CHANGED_BY_LOAD))
        confirmed = one(cur, "SELECT count(*) FROM " + table + " WHERE configuration_uuid = %s AND "
                        + COMMIT_FLAG_COLUMN, (cfg_uuid,))
        check(f"{table}: каждая строка — событие загрузки и подтверждена (D12)",
              by_load == expected and confirmed == expected,
              f"changed_by='load' {by_load}, подтверждено {confirmed}")
        moments = one(cur, "SELECT count(DISTINCT changed_at) FROM " + table
                      + " WHERE configuration_uuid = %s", (cfg_uuid,))
        check(f"{table}: одна метка события на всю загрузку (M2)",
              moments == (1 if expected else 0), f"разных меток: {moments}")
        other = one(cur, "SELECT count(*) FROM " + table
                    + " WHERE configuration_uuid = %s AND revision_no <> %s",
                    (cfg_uuid, FIRST_REVISION))
        check(f"{table}: ревизия первой загрузки — {FIRST_REVISION}, других нет",
              other == 0, f"строк с другой ревизией: {other}")
        # Колонку заголовка подставляет вызывающий (порядок V44); без неё строка не попала
        # бы в счётчик выше, но проверить это надо явно: NULL в NOT NULL-колонке — отказ.
        supplied = sum(1 for row in collected[table] if row.get("configuration_uuid"))
        null_uuid = int(one(cur, "SELECT count(*) FROM " + table
                                 + " WHERE configuration_uuid IS NULL") or 0)
        check(f"{table}: вызывающий подставил configuration_uuid в каждую строку",
              supplied == expected and null_uuid == 0,
              f"строк со значением: {supplied} из {expected}")


def check_constraints(cur, cfg_uuid, collected):
    """CHECK'ы и пары состояний читаются фактом, а не следствием исключения."""
    print("\n--- ограничения схемы ---")
    violations = {
        "subsystems": [
            ("глубина дерева вне 1…5",
             "SELECT count(*) FROM subsystems WHERE configuration_uuid = %s"
             " AND tree_depth NOT BETWEEN 1 AND 5"),
            ("источник родительства вне словаря",
             "SELECT count(*) FROM subsystems WHERE configuration_uuid = %s"
             " AND parent_source NOT IN ('layout','declared','index_name')"),
        ],
        "subsystem_content": [
            ("форма ссылки вне словаря",
             "SELECT count(*) FROM subsystem_content WHERE configuration_uuid = %s"
             " AND ref_form NOT IN ('qualified_name','uuid')"),
        ],
        "common_modules": [
            ("return_values_reuse вне словаря",
             "SELECT count(*) FROM common_modules WHERE configuration_uuid = %s"
             " AND return_values_reuse IS NOT NULL AND return_values_reuse"
             " NOT IN ('DontUse','DuringSession','DuringRequest')"),
        ],
        "common_module_sources": [
            ("состояние текста вне словаря",
             "SELECT count(*) FROM common_module_sources WHERE configuration_uuid = %s"
             " AND content_state NOT IN ('file','bin_only','indexed_no_file','file_not_in_index')"),
            ("путь у состояния без текста (нарушение пары, C-V46-1)",
             "SELECT count(*) FROM common_module_sources WHERE configuration_uuid = %s"
             " AND file_path IS NOT NULL AND content_state NOT IN ('file','file_not_in_index')"),
            ("текст помечен загруженным до второй стадии (D7)",
             "SELECT count(*) FROM common_module_sources WHERE configuration_uuid = %s"
             " AND content_loaded"),
        ],
    }
    for table, items in violations.items():
        for name, sql in items:
            bad = int(one(cur, sql, (cfg_uuid,)) or 0)
            check(f"{table}: {name}", bad == 0, f"строк: {bad}")

    # Пара «путь ↔ состояние» должна быть и полной: у каждого состояния с текстом путь есть.
    with_path = int(one(cur, "SELECT count(*) FROM common_module_sources"
                             " WHERE configuration_uuid = %s"
                             " AND content_state IN ('file','file_not_in_index')",
                        (cfg_uuid,)) or 0)
    path_set = int(one(cur, "SELECT count(*) FROM common_module_sources"
                            " WHERE configuration_uuid = %s AND file_path IS NOT NULL",
                       (cfg_uuid,)) or 0)
    check("common_module_sources: путь есть у каждого состояния с текстом",
          with_path == path_set, f"состояний с текстом {with_path}, путей {path_set}")

    # Порядок детей (D8) читается из таблицы, а не из памяти разбора.
    ordered = int(one(cur,
                      "SELECT count(*) FROM subsystems s WHERE s.configuration_uuid = %s"
                      " AND s.parent_full_name IS NOT NULL AND s.ordinal > 0",
                      (cfg_uuid,)) or 0)
    declared = len([row for row in collected["subsystems"] if row.get("ordinal", 0) > 0])
    check("subsystems: ordinal детей дошёл до таблицы в порядке объявления родителя",
          ordered == declared, f"строк с порядком: {ordered}")

    # Ссылки относятся к ревизии родителя (прецедент form_ext): витрина их отдаёт.
    links_view = int(one(cur, "SELECT count(*) FROM " + current_view("subsystem_content")
                             + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0)
    unresolved = int(one(cur, "SELECT count(*) FROM subsystem_content"
                              " WHERE configuration_uuid = %s AND NOT resolved",
                         (cfg_uuid,)) or 0)
    expected_links = len(collected["subsystem_content"])
    expected_unresolved = len([row for row in collected["subsystem_content"]
                               if not row.get("resolved")])
    check("subsystem_content: витрина отдаёт каждую ссылку своей подсистемы",
          links_view == expected_links, f"{links_view} из {expected_links}")
    check("subsystem_content: неразрешённая ссылка остаётся строкой с resolved=false (D9)",
          unresolved == expected_unresolved,
          f"в таблице {unresolved}, в контракте {expected_unresolved}")


def check_nullable_jsonb(cur, cfg_uuid, collected):
    """Пустое значение разбора остаётся NULL, а не `'{}'::jsonb` (контракт V31)."""
    print("\n--- пустое значение против '{}' ---")
    for table, columns in NULLABLE_JSONB_COLUMNS.items():
        for column in columns:
            expected_null = sum(1 for row in collected[table] if not row.get(column))
            actual_null = int(one(cur, "SELECT count(*) FROM " + table
                                       + " WHERE configuration_uuid = %s AND " + column
                                       + " IS NULL", (cfg_uuid,)) or 0)
            as_empty = int(one(cur, "SELECT count(*) FROM " + table
                                      + " WHERE configuration_uuid = %s AND " + column
                                      + " = '{}'::jsonb", (cfg_uuid,)) or 0)
            check(f"{table}.{column}: пустое значение разбора остаётся NULL",
                  expected_null == actual_null and as_empty == 0,
                  f"пустых в контракте {expected_null}, NULL в таблице {actual_null}, "
                  f"'{{}}' в таблице {as_empty}")


def check_paths_resolve(cur, cfg_uuid, dump_dir, limit=5):
    """Путь и размер из таблицы читаются с диска: дескриптор не выдуман."""
    cur.execute(
        "SELECT file_path, file_size, content_state FROM common_module_sources"
        " WHERE configuration_uuid = %s AND file_path IS NOT NULL"
        " ORDER BY file_size DESC LIMIT %s", (cfg_uuid, limit))
    records = cur.fetchall()
    if not records:
        check("common_module_sources: путь указывает на реальный файл",
              False, "ни одной строки с путём — проверять нечем")
        return
    bad = []
    for file_path, file_size, _state in records:
        candidate = Path(dump_dir) / str(file_path)
        if not candidate.is_file():
            bad.append(f"{file_path}: файла нет на диске")
            continue
        actual = candidate.stat().st_size
        if int(file_size or -1) != actual:
            bad.append(f"{file_path}: в таблице {file_size}, на диске {actual}")
    check(f"common_module_sources: путь и размер прочитаны с диска ({len(records)} строк)",
          not bad, "; ".join(bad[:3]) if bad else "совпадает")


def check_duplicate_rejected(cur, cfg_uuid, collected):
    """Ключ цепочки существует фактом: повтор той же строки отклонён."""
    print("\n--- ключ цепочки состояния ---")
    for table in CHILD_TABLES:
        if not collected[table]:
            continue
        writer = CONFIGURATION_OBJECT_WRITERS[table]
        row = collected[table][0]
        cur.execute("SAVEPOINT probe_dup")
        try:
            writer.insert(cur, row)
            cur.execute("ROLLBACK TO SAVEPOINT probe_dup")
            check(f"{table}: повтор строки той же ревизии отклонён уникальным ключом",
                  False, "вставка прошла — ключ цепочки не работает")
        except psycopg2.errors.UniqueViolation as exc:
            cur.execute("ROLLBACK TO SAVEPOINT probe_dup")
            constraint = ""
            diag = getattr(exc, "diag", None)
            if diag is not None:
                constraint = str(diag.constraint_name or "")
            check(f"{table}: повтор строки той же ревизии отклонён уникальным ключом",
                  True, constraint)
        except psycopg2.Error as exc:
            cur.execute("ROLLBACK TO SAVEPOINT probe_dup")
            check(f"{table}: повтор строки той же ревизии отклонён уникальным ключом",
                  False, "не UniqueViolation: " + str(exc).splitlines()[0][:120])


def check_second_revision(cur, cfg_uuid, collected):
    """Цепочка идёт по full_name, а не по object_uuid (D8); правка не подтверждена (D12)."""
    print("\n--- вторая ревизия по full_name ---")
    subsystems = collected["subsystems"]
    # Берётся лист. Предпочтение — строке без ссылок: ссылка относится к ревизии родителя
    # (прецедент form_ext), и вторая ревизия без новых ссылок оставила бы их не текущими.
    # Если таких строк в выгрузке нет (MinCfg: единственная подсистема со 100% ссылок),
    # берётся любая — и следствие для ссылок проверяется отдельным фактом, а не обходится.
    linked = {row["subsystem_object_uuid"] for row in collected["subsystem_content"]}
    parents = {row["parent_full_name"] for row in subsystems if row.get("parent_full_name")}
    leaves = [row for row in subsystems
              if row["object_uuid"] not in linked
              and row["full_name"] not in parents
              and row.get("parent_source") == "layout"]
    leaf = next(iter(leaves), None)
    if leaf is None:
        leaf = next((row for row in subsystems
                     if row["full_name"] not in parents
                     and row.get("parent_source") == "layout"), None)
    if leaf is None:
        check("subsystems: есть лист для проверки цепочки", False, "подходящей строки нет")
    else:
        leaf_links = [row for row in collected["subsystem_content"]
                      if row["subsystem_object_uuid"] == leaf["object_uuid"]]
        first_uuid = leaf["object_uuid"]
        second = dict(leaf)
        second_uuid = str(uuid_module.uuid4())
        second["object_uuid"] = second_uuid
        stamp_revision_rows([second], revision_no=FIRST_REVISION + 1,
                            changed_by=CHANGED_BY_EDIT)
        CONFIGURATION_OBJECT_WRITERS["subsystems"].insert(cur, second)
        current_rows = int(one(cur, "SELECT count(*) FROM " + current_view("subsystems")
                                  + " WHERE configuration_uuid = %s AND full_name = %s",
                               (cfg_uuid, leaf["full_name"])) or 0)
        cur.execute("SELECT revision_no, object_uuid, " + COMMIT_FLAG_COLUMN + ", changed_by"
                    " FROM " + current_view("subsystems")
                    + " WHERE configuration_uuid = %s AND full_name = %s",
                    (cfg_uuid, leaf["full_name"]))
        revision, object_uuid, is_committed, changed_by = cur.fetchone()
        check("subsystems: витрина отдаёт одну текущую строку имени",
              current_rows == 1, f"строк: {current_rows}")
        check("subsystems: текущей стала вторая ревизия (max revision_no, решение A1)",
              int(revision) == FIRST_REVISION + 1, f"revision_no: {revision}")
        check("subsystems: цепочка продолжилась с ДРУГИМ object_uuid (решение D8)",
              str(object_uuid) == second_uuid and str(object_uuid) != str(first_uuid),
              f"первый {first_uuid}, второй {second_uuid}")
        check("subsystems: строка правки не подтверждена (поправка D12)",
              is_committed is False and changed_by == CHANGED_BY_EDIT,
              f"is_committed={is_committed}, changed_by={changed_by}")
        total_rows = int(one(cur, "SELECT count(*) FROM subsystems"
                                  " WHERE configuration_uuid = %s AND full_name = %s",
                             (cfg_uuid, leaf["full_name"])) or 0)
        check("subsystems: первая ревизия осталась в таблице (история не снимается)",
              total_rows == 2, f"строк в базовой таблице: {total_rows}")
        if leaf_links:
            current_links = int(one(cur, "SELECT count(*) FROM "
                                        + current_view("subsystem_content")
                                        + " WHERE configuration_uuid = %s"
                                        " AND subsystem_object_uuid = %s",
                                   (cfg_uuid, first_uuid)) or 0)
            check("subsystem_content: ссылки принадлежат ревизии родителя (прецедент form_ext)",
                  current_links == 0,
                  f"ссылок у снятой ревизии {len(leaf_links)}, текущих {current_links}")
            note("вторая ревизия подсистемы делает её ссылки не текущими: витрина связывает "
                 "ссылку с родителем парой (object_uuid, revision_no). Записать ссылки той же "
                 "ревизией обязан загрузчик (П5) — писатель ссылки сам не создаёт.")

    # Дескриптор модуля: его цепочка идёт по object_uuid — фактическая граница модели П1.
    modules = collected["common_modules"]
    sources = collected["common_module_sources"]
    if not modules or not sources:
        check("common_module_sources: цепочка дескриптора проверена", False,
              "строк модулей нет — проверять нечем")
        return
    module = modules[0]
    descriptor = next((row for row in sources
                       if row["object_uuid"] == module["object_uuid"]), None)
    if descriptor is None:
        check("common_module_sources: цепочка дескриптора проверена", False,
              f"у модуля {module['full_name']} нет дескриптора")
        return
    second_module = dict(module)
    second_module["object_uuid"] = str(uuid_module.uuid4())
    stamp_revision_rows([second_module], revision_no=FIRST_REVISION + 1,
                        changed_by=CHANGED_BY_EDIT)
    CONFIGURATION_OBJECT_WRITERS["common_modules"].insert(cur, second_module)
    stale = int(one(cur,
                    "SELECT count(*) FROM " + current_view("common_module_sources") + " cs"
                    " WHERE cs.configuration_uuid = %s AND cs.module_name = %s"
                    " AND NOT EXISTS (SELECT 1 FROM " + current_view("common_modules") + " cm"
                    " WHERE cm.configuration_uuid = cs.configuration_uuid"
                    " AND cm.object_uuid = cs.object_uuid)",
                    (cfg_uuid, descriptor["module_name"])) or 0)
    check("common_module_sources: цепочка идёт по object_uuid — старый дескриптор остаётся текущим",
          stale == 1, f"дескрипторов вне текущей цепочки свойств: {stale}")
    note("цепочки двух таблиц одного объекта идут по РАЗНЫМ ключам: `common_modules` по"
         " full_name (D8), `common_module_sources` по object_uuid (уникальный индекс П1)."
         " Пересоздание модуля с новым uuid продолжает цепочку свойств и начинает цепочку"
         " дескриптора — прежний дескриптор остаётся в витрине текущего состояния. Это"
         " граница модели П1, а не дефект записи: вопрос снимается решением по П5/П6, а не"
         " молчанием прогона.")


def run_dump(name):
    dump_dir = BASE / name
    print("\n" + "=" * 78)
    print("ПРЕДМЕТ: " + str(dump_dir))
    print("=" * 78)
    if not dump_dir.is_dir():
        check(f"{name}: каталог выгрузки существует", False, str(dump_dir))
        return

    uuid_info = configuration_uuid_from_layout(str(dump_dir))
    if "uuid" not in uuid_info:
        check(f"{name}: uuid конфигурации прочитан из Configuration.xml", False,
              uuid_info.get("error"))
        return
    cfg_uuid = uuid_info["uuid"]
    check(f"{name}: uuid конфигурации прочитан из Configuration.xml", True, cfg_uuid)

    index_rows, index_reason = props.index_rows_from_dump(str(dump_dir))
    check(f"{name}: индекс состава прочитан", bool(index_rows), index_reason or "ok")

    subsystems = props.collect_subsystems(str(dump_dir), index_rows=index_rows)
    modules = props.collect_common_modules(str(dump_dir), index_rows=index_rows)
    collected = {
        "subsystems": subsystems["rows"],
        "subsystem_content": subsystems["content_rows"],
        "common_modules": modules["rows"],
        "common_module_sources": modules["source_rows"],
    }
    for table, result in (("subsystems", subsystems), ("common_modules", modules)):
        check(f"{table}: файлы регистрации разбираются без ошибок", not result["parse_errors"],
              "; ".join(result["parse_errors"][:3]) if result["parse_errors"] else "0")
    check_contract_matches_writer(collected)
    note("контракт разбора: " + ", ".join(f"{table} {len(rows)}"
                                          for table, rows in collected.items()))

    # Инвариант «таблицы пусты» перестал выражать то же самое с 28.10.2026: конвейер
    # (узлы V45/V46 П5, V47, V48 П4) пишет в таблицы стадий реальный состав загруженных
    # конфигураций, и строки эти остаются в базе намеренно — снять их после загрузки значит
    # оставить конфигурацию без её содержимого. Проверяемое свойство пробы не менялось: прогон
    # ничего не меняет в базе. Значит базовое состояние читается ДО записи (сколько строк
    # всего и сколько строк этой конфигурации), запись идёт в снятом внутри транзакции круге
    # этой конфигурации, а откат обязан вернуть ровно это состояние. Без этой правки проба
    # падала на duplicate key по `uq_subsystems_configuration_full_name_revision` на
    # конфигурациях, загруженных раньше (замер 29.10.2026: строки подсистем BP3/BGU2/KomMag
    # от 28.10.2026), — то есть проверяла совпадение со своим предположением о пустоте.
    baseline = {}
    baseline_cfg = {}
    conn_base = connect()
    try:
        cur_base = conn_base.cursor()
        for table in CHILD_TABLES:
            baseline[table] = int(one(cur_base, "SELECT count(*) FROM " + table) or 0)
            baseline_cfg[table] = int(one(cur_base, "SELECT count(*) FROM " + table
                                              + " WHERE configuration_uuid = %s",
                                         (cfg_uuid,)) or 0)
    finally:
        conn_base.close()
    if any(baseline_cfg.values()):
        note("%s: в таблицах уже есть строки этой конфигурации (%s) — они снимаются внутри "
             "транзакции пробы и возвращаются откатом: проба не пишет поверх реального состава "
             "и не считает чужие строки своими" % (name, baseline_cfg))

    conn = connect()
    try:
        cur = conn.cursor()
        # Строки пробы не зафиксированы, а планировщик строит план по статистике: о
        # незафиксированных строках он не знает ничего — ANALYZE видит только зафиксированное
        # (замер 28.10.2026: счётчик `v_current_subsystem_content` на 13 757 ссылках BGU2 при
        # пустой статистике выполняется 8 мин 25 с, после ANALYZE — 7 мс). Проверки пробы
        # считают строки, а не план, поэтому план задаёт сама проба: `SET LOCAL` живёт ровно
        # в её транзакции и в код загрузчика не попадает.
        cur.execute("SET LOCAL enable_nestloop = off")
        removed_pre = {}
        for table in CHILD_TABLES:
            cur.execute("DELETE FROM " + table + " WHERE configuration_uuid = %s", (cfg_uuid,))
            removed_pre[table] = cur.rowcount
        check("прежние строки этой конфигурации сняты внутри транзакции (запись начинается "
              "с чистого круга)",
              all(removed_pre[table] == baseline_cfg[table] for table in CHILD_TABLES),
              str(removed_pre))
        written, moment = write_all(cur, cfg_uuid, collected)
        check("метка события одна и та же для всех четырёх групп (M2)", bool(moment), str(moment))
        check_written(cur, cfg_uuid, collected, written)
        check_constraints(cur, cfg_uuid, collected)
        check_nullable_jsonb(cur, cfg_uuid, collected)
        check_paths_resolve(cur, cfg_uuid, dump_dir)
        check_duplicate_rejected(cur, cfg_uuid, collected)
        check_second_revision(cur, cfg_uuid, collected)
        conn.rollback()
        check("транзакция откатана", True, "строк в базу не попало")
    except psycopg2.Error as exc:
        conn.rollback()
        check("запись прошла без ошибки схемы", False, str(exc).splitlines()[0][:300])
    finally:
        conn.close()

    conn_after = connect()
    try:
        cur_after = conn_after.cursor()
        drift = {}
        for table in CHILD_TABLES:
            count = int(one(cur_after, "SELECT count(*) FROM " + table) or 0)
            if count != baseline[table]:
                drift[table] = f"{baseline[table]} → {count}"
        check("после отката таблицы вернулись к базовому состоянию", not drift,
              "; ".join(f"{table}: {where}" for table, where in drift.items())
              or "состояние всех четырёх таблиц не изменилось: " + str(baseline))
    finally:
        conn_after.close()


def main():
    print("ПРОГОН V46 (П4): писатели свойств подсистем и общих модулей")
    wanted = tuple(arg for arg in sys.argv[1:] if arg in DUMP_NAMES) or DUMP_NAMES
    check_registry()
    for name in wanted:
        run_dump(name)
    print("\nИТОГ: пройдено " + str(PASSED) + ", провалено " + str(FAILED)
          + ", заметок " + str(len(NOTES)))
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())
