#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/check_v47_configuration_object_modules.py — узел V47: модули объектов конфигурации.

Узел V47 (28.10.2026): стадия `s4b_object_modules` пишет модули объектов конфигурации в
`bsl_modules` (`parent_type = 'configuration_objects'`) второй транзакцией загрузки
(граница D7, решение Q6). Норматив — `docs/CONFIGURATION_OBJECT_MODULES_PLAN.md`
(раздел 2 — замеры, раздел 3 — граница круга, раздел 5 — решения Q1/Q2/Q4/Q6),
основание контуров проверки — `_handoff_object_modules_2026-10-24.md` раздел 9.3.

Проверка строится по образцу `tools/check_v42_configuration_header.py`: три контура
«индекс ↔ файл ↔ строка БД», причём каждый контур считается по своему источнику, а не
по следующему месту. Круг и путь берёт словарь `configuration_module_slots` — проверка
не дублирует его логику (правило одного источника, тот же приём у V43/V44/V46).

Что проверяется и почему именно так:

  1. ГРАНИЦА КРУГА (раздел 3 плана): число записей индекса круга, отданное агрегатным
     `COUNT` по условию словаря, равно числу, отданному построчным обходом того же
     условия. Расхождение этих двух чисел — тот же класс дефекта, что «19 428 вместо
     13 389» пробы П2: условие круга в двух местах разъезжается первым же новым видом.
     Записи слота `Module` общих модулей (`CommonModule`, предмет V46) обязаны остаться
     вне круга и быть названы отдельной строкой: «вне предмета узла» и «не нашли» —
     разные ответы.
  2. КРУГ ↔ ФАЙЛ (словарь, файл не читается): числа плана раздела 2 — записи индекса,
     найденные файлы, `indexed_no_file`, записи с машинным кодом `.bin` рядом (открытая
     позиция O1: она называется строкой, а не молчанием) и остаток подлинно отсутствующих
     файлов. Отказов разрешения пути и дефектов данных — ноль.
  3. ФАЙЛ ↔ СТРОКА БД: строка существует только там, где есть код (решение Q2). Число
     строк равняется числу файлов, в которых после строгого раскодирования есть текст
     (10 874 на четырёх выгрузках — пересъём 03.11.2026, шаг П9 узла V54), а НЕ числу
     файлов (13 344); файлы, где байты есть, а текста нет (одна BOM — 2 470), называются
      отдельной строкой: это состояние выгрузки,
     а не потеря разбора. Каждая строка сверяется с файлом на диске тем же
     `read_module_code`, которым читал писатель, каждая запись круга состояния `file` —
     со строкой в обе стороны; `code_size` равняется `length(code)` в SQL и числу
     символов прочитанного текста. Пустой модуль и отсутствующий модуль выражаются
     ОТСУТСТВИЕМ строки — это решение Q2, и проверка говорит об этом прямо: колонок
     состояния в схеме нет, выводить состояние из них не из чего.
  4. ПОЛНОТА ПО ГРУППАМ (решение Q4): атом полноты — группа верхнего объекта. Незакрытая
     группа называется её видом и именем, а не одним числом; закрытой считается группа,
     каждая запись круга которой либо получила строку, либо названа состоянием
     (`indexed_no_file`, «файл есть, текста нет»).
  5. ССЫЛКА И ВЛАДЕЛЕЦ: `parent_uuid` каждой строки разрешается в запись индекса той же
     конфигурации (связь через конфигурацию, а не через всю таблицу — иначе счёт
     расходится), `object_type`/`object_name` равны колонкам той же записи индекса,
     `module_name`/`module_type` — слоту, `file_path` — пути словаря.
  6. ГРАНИЦА R5: строки обязаны быть свежее файлов выгрузки, иначе сравнение было бы
     сравнением с прошлым состоянием. Это отдельный SKIP с причиной, а не успех.
  7. УБОРКА: проверка только читает. Чужой контур (`parent_type = 'external_report'`),
     эталонная пара внешних объектов и строки обогащения сверяются до и после прогона:
     их изменение означает, что чтение затронуло запись.
  8. КЛЮЧ ЦЕПОЧКИ И ВИТРИНА (шаг П1.1, оператор 28.10.2026): `parent_uuid` — uuid
     метаданных, общий для конфигураций, выросших из общей базы (замер: 42 349 общих
     uuid), поэтому пара (родитель, путь) различает модуль только внутри одной
     конфигурации. Контур читает определения живой схемы: ключ обязан называть четыре
     колонки и не иметь мёртвого предиката, витрина — разрешать цепочку внутри
     конфигурации. Различение двух конфигураций доказывается фактом: строки одной пары
     из разных конфигураций остаются в витрине обе, каждая цепочка имеет ровно одну
     текущую строку. При одной конфигурации в таблице контур называется SKIP-ом.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python tools/check_v47_configuration_object_modules.py [MinCfg|KomMag|BGU2|BP3|all]
По умолчанию — `all`: все строки заголовков, для которых находится каталог выгрузки.
Код возврата 0 — расхождений нет. Пропуск контуров называется причиной (нет строки
заголовка, нет выгрузки, строк узла не загружалось, выгрузка новее записи): ноль
проверок не читается как «всё хорошо».
"""
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

try:  # кириллица в консоли Windows (cp1251) - как в остальных валидаторах
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from configuration_module_slots import (  # noqa: E402
    PARENT_TYPE, SCOPE_V46, SCOPE_V47, SCOPE_OUT, STATE_EMPTY_FILE, STATE_FILE,
    STATE_INDEXED_NO_FILE, TARGET_TABLE, iter_index_records, iter_module_rows,
    object_group, resolve_dump_dir, scope_condition_sql, scope_of, scope_params,
)
from configuration_module_writer import (  # noqa: E402
    STATE_UNDECODED, read_module_code,
)
from external_db import transaction  # noqa: E402

DUMP_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
DEFAULT_SCOPE = "all"
# Сколько строк сверяется текстом целиком (остальные — размером, см. контур 3).
TEXT_SAMPLE_ROWS = 12
# Сколько незакрытых групп называется именами (дальше — только число).
MAX_UNCLOSED_NAMES = 15

# ── ожидания проверки (числа плана docs/CONFIGURATION_OBJECT_MODULES_PLAN.md) ───────
# Раздел 2.1–2.3 и раздел 12 (замеры 28.10.2026; `MinCfg` переснят 03.11.2026 — шаг П9
# узла V54, фикстуру пересобирали): круг, найденные файлы, отсутствующие
# файлы, машинный код `.bin` рядом, строки (файлы с текстом) и файлы без текста (BOM).
# Числа названы по каталогу выгрузки, а не по имени строки заголовка: имя строки
# меняется вместе с выгрузкой, каталог — адрес, по которому проверка находит файлы.
PLAN_EXPECTATIONS = {
    "MinCfg": {"records": 81, "files": 81, "indexed_no_file": 0, "bin_side": 0,
               "rows": 81, "no_text": 0},
    "KomMag": {"records": 149, "files": 111, "indexed_no_file": 38, "bin_side": 9,
               "rows": 93, "no_text": 18},
    "BGU2": {"records": 5403, "files": 5399, "indexed_no_file": 4, "bin_side": 4,
             "rows": 4461, "no_text": 938},
    "BP3": {"records": 7758, "files": 7753, "indexed_no_file": 5, "bin_side": 5,
            "rows": 6239, "no_text": 1514},
}
# Записей слота `Module` общих модулей (предмет V46) — вне круга узла (раздел 3 плана).
V46_MODULE_RECORDS = 6039

PASSED, FAILED, SKIPPED, INFO = [], [], [], []


def check(name, ok, detail=""):
    (PASSED if ok else FAILED).append(name)
    print(("PASS " if ok else "FAIL ") + name + ((" - " + str(detail)) if detail else ""))


def skip(name, reason):
    SKIPPED.append(name)
    print(f"SKIP {name} - {reason}")


def info(text):
    INFO.append(text)
    print("INFO " + text)


def section(title):
    print("\n" + title)
    print("-" * len(title))


def q(cur, sql, params=None):
    cur.execute(sql, params or ())
    if not cur.description:
        return []
    columns = [d[0] for d in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def one(cur, sql, params=None):
    rows = q(cur, sql, params)
    return rows[0] if rows else {}


# ── обход источников: круг (словарь) и строки БД (таблица узла) ────────────────────
def collect_circle(cur, configuration_uuid, dump_dir):
    """Обойти круг узла словарём и собрать его состояние без чтения файлов.

    Возвращает словарь с числами состояний, множествами групп и отпечатком каждой
    записи (`file` / `indexed_no_file` / отказ). Файлы не читаются: это контур 2,
    дорогое чтение относится к контуру 3.
    """
    circle = {
        "records": 0, "states": Counter(), "refusals": Counter(), "defects": Counter(),
        "slots": Counter(), "pathless": [], "bin_side": [], "groups": {},
        "expected_rows": {}, "names_by_state": {}, "paths": {},
    }
    for item in iter_module_rows(cur, configuration_uuid, DUMP_ROOT, dump_dir=dump_dir):
        circle["records"] += 1
        name = str(item.get("name") or "")
        group = str(item.get("group") or "") or object_group(name)
        state = item.get("state")
        refusal = item.get("refusal")
        circle["slots"][str(item.get("slot") or "")] += 1
        if not item.get("derived") and not refusal:
            # Ни пути, ни названной причины — запись круга осталась бы необъяснённой.
            circle["pathless"].append(name)
        if item.get("bin_side"):
            circle["bin_side"].append(name)
        if state:
            circle["states"][state] += 1
            circle["names_by_state"].setdefault(state, []).append(name)
        if refusal:
            bucket = circle["defects"] if _is_defect(refusal) else circle["refusals"]
            bucket[refusal] += 1
        entry = circle["groups"].setdefault(
            group, {"records": 0, "rows": 0, "states": Counter()})
        entry["records"] += 1
        if state:
            entry["states"][state] += 1
        if state == STATE_FILE and item.get("row"):
            row = item["row"]
            circle["expected_rows"][row["file_path"]] = {
                "name": name, "group": group, "slot": row["module_name"],
                "parent_uuid": row["parent_uuid"], "object_type": row["object_type"],
                "object_name": row["object_name"],
                "abs_path": (item.get("derived") or {}).get("abs_path", ""),
            }
            entry["rows"] += 1
            circle["paths"][row["file_path"]] = name
    return circle


def _is_defect(reason):
    """Относится ли причина к дефекту данных (а не к отказу разрешения пути)."""
    from configuration_module_slots import DEFECTS
    return reason in DEFECTS


def read_db_rows(cur, configuration_uuid):
    """Прочитать строки круга узла в `bsl_modules` (граница снятия — та же, что у писателя)."""
    return q(cur, f"""
        SELECT id, parent_uuid::text AS parent_uuid, parent_type, module_name,
               module_type, file_path, object_type, object_name, code_size,
               length(code) AS code_chars, octet_length(code) AS code_bytes,
               code IS NULL AS code_is_null, truncated, configuration_uuid::text
               AS configuration_uuid, changed_at
          FROM {TARGET_TABLE}
         WHERE configuration_uuid = %(configuration_uuid)s::uuid
           AND parent_type = %(parent_type)s
         ORDER BY file_path, id
    """, {"configuration_uuid": str(configuration_uuid),
          "parent_type": PARENT_TYPE})


# ── контур 1: граница круга (индекс) ───────────────────────────────────────────────
def check_scope_boundary(cur, cfg_uuid, circle, tag):
    """Число записей круга по агрегатному COUNT = число по построчному обходу.

    Оба числа берутся из одного условия словаря (`scope_condition_sql`), но разными
    способами: агрегатом и обходом. Совпадение означает, что обход не теряет и не
    добавляет записей; расхождение проба П2 видела как «19 428 вместо 13 389».
    """
    params = scope_params()
    params["configuration_uuid"] = str(cfg_uuid)
    aggregate = one(cur, f"""
        SELECT count(*) AS records
          FROM configuration_objects o
          JOIN configurations c ON c.id = o.configuration_id
         WHERE c.uuid = %(configuration_uuid)s::uuid
           AND {scope_condition_sql()}
    """, params).get("records", 0)
    check(f"{tag}: записей круга по COUNT равно числу построчного обхода словаря",
          aggregate == circle["records"],
          f"COUNT: {aggregate}, обход: {circle['records']}")

    # Записи слота `Module` разбираются словарём по видам: предмет V47, предмет V46,
    # вне предмета. Граница называется числом по каждому ответу, а не молчанием.
    kinds = q(cur, """
        SELECT o.object_type AS kind, count(*) AS records
          FROM configuration_objects o
          JOIN configurations c ON c.id = o.configuration_id
         WHERE c.uuid = %(configuration_uuid)s::uuid
           AND o.child_type = 'Module'
         GROUP BY 1 ORDER BY 2 DESC, 1
    """, {"configuration_uuid": str(cfg_uuid)})
    by_scope = Counter()
    for row in kinds:
        by_scope[scope_of(row["kind"], "Module")] += row["records"]
    check(f"{tag}: записей слота `Module` по видам разделено тем же словарём, каким "
          f"задан круг",
          by_scope.get(SCOPE_V47, 0) == circle["slots"].get("Module", 0),
          f"словарь по видам: {by_scope.get(SCOPE_V47, 0)}, обход круга: "
          f"{circle['slots'].get('Module', 0)}")
    check(f"{tag}: записей слота `Module` видов, не перечисленных словарём, нет",
          by_scope.get(SCOPE_OUT, 0) == 0,
          f"вне предмета: {by_scope.get(SCOPE_OUT, 0)} — словарь обязан назвать такой "
          f"вид прежде, чем круг изменится")

    # Каждую запись, пускаемую SQL-условием, `scope_of` обязан отнести к кругу узла.
    # Два способа задать границу (условие запроса и функция словаря) расходятся первым
    # же новым видом — тот класс дефекта, что «19 428 вместо 13 389».
    off_scope = []
    for record in iter_index_records(cur, cfg_uuid):
        if scope_of(record.get("object_type"), record.get("child_type")) != SCOPE_V47:
            off_scope.append(f"{record.get('name')} [{record.get('child_type')} / "
                             f"{record.get('object_type')}]")
    check(f"{tag}: граница круга SQL-условием и функцией `scope_of` совпадают",
          not off_scope, f"{len(off_scope)}: {off_scope[:3]}")
    info(f"{tag}: слот `Module` — предмет V47 {by_scope.get(SCOPE_V47, 0)}, "
         f"предмет V46 {by_scope.get(SCOPE_V46, 0)}, вне предмета "
         f"{by_scope.get(SCOPE_OUT, 0)}")
    return dict(by_scope)


# ── контур 2: круг ↔ файл (словарь, содержимое не читается) ────────────────────────
def check_circle_on_disk(circle, expect, tag):
    """Числа круга и состояний файла против замеров плана (раздел 2)."""
    states = circle["states"]
    found = states.get(STATE_FILE, 0) + states.get(STATE_EMPTY_FILE, 0)
    missing = states.get(STATE_INDEXED_NO_FILE, 0)
    check(f"{tag}: записей индекса круга равно ожиданию плана ({expect['records']})",
          circle["records"] == expect["records"],
          f"факт: {circle['records']}, план: {expect['records']}")
    check(f"{tag}: файлов круга найдено равно ожиданию плана ({expect['files']})",
          found == expect["files"], f"факт: {found}, план: {expect['files']}")
    check(f"{tag}: записей без файла названо числом и оно равно ожиданию плана "
          f"({expect['indexed_no_file']})",
          missing == expect["indexed_no_file"],
          f"факт: {missing}, план: {expect['indexed_no_file']}")
    check(f"{tag}: открытая позиция O1 названа отдельной строкой: рядом `.bin` "
          f"{expect['bin_side']}",
          len(circle["bin_side"]) == expect["bin_side"],
          f"факт: {len(circle['bin_side'])}, план: {expect['bin_side']}")
    truly_missing = missing - len(circle["bin_side"])
    check(f"{tag}: подлинно пустых модулей = записей без файла минус машинный код",
          truly_missing == expect["indexed_no_file"] - expect["bin_side"],
          f"факт: {truly_missing}, план: {expect['indexed_no_file'] - expect['bin_side']}")
    check(f"{tag}: отказов разрешения пути нет", not circle["refusals"],
          dict(circle["refusals"]))
    check(f"{tag}: дефектов данных индекса нет", not circle["defects"],
          dict(circle["defects"]))
    check(f"{tag}: у каждой записи круга есть вывод пути или названная причина",
          not circle["pathless"], f"записей без пути и без причины: "
          f"{len(circle['pathless'])} {circle['pathless'][:3]}")
    info(f"{tag}: круг {circle['records']}, файлов {found}, без файла {missing} "
         f"(рядом .bin {len(circle['bin_side'])}), групп {len(circle['groups'])}")
    return {"found": found, "missing": missing, "truly_missing": truly_missing}


# ── контур 3: файл ↔ строка БД (решение Q2) ────────────────────────────────────────
def check_rows_against_disk(cur, cfg_uuid, dump_dir, circle, db_rows, expect, tag):
    """Каждый файл круга читается, каждая строка таблицы сверяется с файлом и индексом.

    Чтение — то же, что у писателя (`read_module_code`, `utf-8-sig` строго, без
    запасной кодировки и без усечения): проверка не задаёт свою политику чтения, иначе
    она сверяла бы строку со своим представлением файла, а не с тем, что писал узел.
    """
    disk = {}
    reading = Counter()
    for file_path, entry in circle["expected_rows"].items():
        outcome = read_module_code(entry["abs_path"] or
                                   Path(dump_dir) / file_path)
        reading[outcome["state"]] += 1
        if outcome["state"] == STATE_FILE:
            disk[file_path] = outcome
    with_text = reading.get(STATE_FILE, 0)
    no_text = reading.get(STATE_EMPTY_FILE, 0)
    undecoded = reading.get(STATE_UNDECODED, 0)
    disappeared = reading.get(STATE_INDEXED_NO_FILE, 0)

    check(f"{tag}: файлов с текстом после строгого раскодирования равно ожиданию "
          f"плана ({expect['rows']}) — это и есть число строк узла (Q2)",
          with_text == expect["rows"], f"факт: {with_text}, план: {expect['rows']}")
    check(f"{tag}: файлов, где байты есть, а текста нет (одна BOM), названо числом "
          f"({expect['no_text']}) — это состояние выгрузки, а не потеря разбора",
          no_text == expect["no_text"], f"факт: {no_text}, план: {expect['no_text']}")
    check(f"{tag}: не раскодированных строго файлов круга нет (правило C5)",
          undecoded == 0, f"факт: {undecoded}")
    check(f"{tag}: файл не исчез между обходом словаря и чтением",
          disappeared == 0, f"факт: {disappeared}")

    db_by_path = {str(row["file_path"]): row for row in db_rows}
    check(f"{tag}: строк узла в таблице равно числу файлов с текстом (Q2: строка "
          f"только там, где есть код)",
          len(db_rows) == with_text,
          f"строк: {len(db_rows)}, файлов с текстом: {with_text}")
    invented = sorted(set(db_by_path) - set(disk))
    lost = sorted(set(disk) - set(db_by_path))
    check(f"{tag}: строк, у которых нет файла с текстом, нет (выводимый круг шире "
          f"таблицы)", not invented, f"{len(invented)}: {invented[:3]}")
    check(f"{tag}: файлов с текстом без строки нет (таблица шире выводимого круга)",
          not lost, f"{len(lost)}: {lost[:3]}")
    return disk, db_by_path, {"with_text": with_text, "no_text": no_text}


# ── контур 4: строка ↔ индекс и файл (колонки и код) ───────────────────────────────
def check_row_fields(cur, cfg_uuid, circle, disk, db_by_path, tag):
    """Колонки каждой строки сверяются с записью индекса и с файлом на диске."""
    rows = list(db_by_path.values())
    matched = one(cur, f"""
        SELECT count(*) AS matched
          FROM {TARGET_TABLE} m
          JOIN configurations c ON c.uuid = m.configuration_uuid
          JOIN configuration_objects o
            ON o.configuration_id = c.id AND o.uuid = m.parent_uuid
         WHERE m.configuration_uuid = %(configuration_uuid)s::uuid
           AND m.parent_type = %(parent_type)s
    """, {"configuration_uuid": str(cfg_uuid),
          "parent_type": PARENT_TYPE}).get("matched", 0)
    check(f"{tag}: `parent_uuid` каждой строки разрешается в запись индекса той же "
          f"конфигурации", matched == len(rows),
          f"разрешилось: {matched} из {len(rows)} — JOIN без границы по конфигурации "
          f"дал бы число больше")

    mismatched = []
    for path, row in db_by_path.items():
        entry = circle["expected_rows"].get(path)
        if not entry:
            continue  # отсутствие файла уже названо контуром 3
        problems = []
        if row["parent_uuid"] != entry["parent_uuid"]:
            problems.append(f"parent_uuid: {row['parent_uuid']} ≠ "
                            f"{entry['parent_uuid']}")
        if row["module_name"] != entry["slot"] or row["module_type"] != entry["slot"]:
            problems.append(f"модуль: {row['module_name']}/{row['module_type']} ≠ "
                            f"{entry['slot']}")
        if row["object_type"] != entry["object_type"]:
            problems.append(f"object_type: {row['object_type']} ≠ "
                            f"{entry['object_type']}")
        if row["object_name"] != entry["object_name"]:
            problems.append(f"object_name: {row['object_name']} ≠ "
                            f"{entry['object_name']}")
        if problems:
            mismatched.append(f"{path}: {'; '.join(problems)}")
    check(f"{tag}: колонок, расходящихся с записью индекса (владелец, слот, вид, имя), "
          f"нет", not mismatched, f"{len(mismatched)}: {mismatched[:3]}")

    wrong_size = []
    for path, row in db_by_path.items():
        outcome = disk.get(path)
        if not outcome:
            continue
        if row["code_size"] != outcome["code_size"]:
            wrong_size.append(f"{path}: code_size {row['code_size']} ≠ "
                              f"файл {outcome['code_size']}")
        if row["code_size"] != row["code_chars"]:
            wrong_size.append(f"{path}: code_size {row['code_size']} ≠ "
                              f"length(code) {row['code_chars']}")
    check(f"{tag}: `code_size` каждой строки равен числу символов файла и "
          f"`length(code)`", not wrong_size, f"{len(wrong_size)}: {wrong_size[:3]}")

    bad_shape = one(cur, f"""
        SELECT count(*) AS bad
          FROM {TARGET_TABLE}
         WHERE configuration_uuid = %(configuration_uuid)s::uuid
           AND parent_type = %(parent_type)s
           AND (code IS NULL OR btrim(code) = '' OR truncated IS NOT FALSE
                OR code_size IS NULL OR code_size <> length(code)
                OR configuration_uuid IS NULL OR file_path IS NULL
                OR parent_uuid IS NULL)
    """, {"configuration_uuid": str(cfg_uuid),
          "parent_type": PARENT_TYPE}).get("bad", 0)
    check(f"{tag}: пустого или усечённого кода, пустых обязательных колонок нет "
          f"(Q2: `truncated` у строк узла всегда `false`, усечения нет)",
          bad_shape == 0, f"строк с нарушением формы: {bad_shape}")

    duplicates = one(cur, f"""
        SELECT count(*) - count(DISTINCT (parent_uuid, file_path)) AS dups
          FROM {TARGET_TABLE}
         WHERE configuration_uuid = %(configuration_uuid)s::uuid
           AND parent_type = %(parent_type)s
    """, {"configuration_uuid": str(cfg_uuid),
          "parent_type": PARENT_TYPE}).get("dups", 0)
    check(f"{tag}: троек `(configuration_uuid, parent_uuid, file_path)` внутри "
          f"конфигурации без повторов нет и витрина текущего множества остаётся "
          f"тотальной", duplicates == 0, f"повторов: {duplicates}")

    sample = _text_sample(db_by_path)
    wrong_text = []
    for path in sample:
        row = db_by_path[path]
        code = one(cur, f"SELECT code FROM {TARGET_TABLE} WHERE id = %(id)s",
                   {"id": row["id"]}).get("code")
        if code != disk[path]["code"]:
            wrong_text.append(path)
    check(f"{tag}: текст модуля совпадает с файлом (выборка {len(sample)} строк: "
          f"первая, последняя, самая длинная)", not wrong_text,
          f"расхождений: {len(wrong_text)} {wrong_text[:3]}")


def _text_sample(db_by_path):
    """Отбор строк для сверки текстом: первая, последняя и самые длинные по объёму."""
    paths = sorted(db_by_path)
    if not paths:
        return []
    longest = sorted(paths, key=lambda p: db_by_path[p]["code_size"] or 0, reverse=True)
    chosen = [paths[0], paths[-1]] + longest
    unique, seen = [], set()
    for path in chosen:
        if path not in seen:
            seen.add(path)
            unique.append(path)
        if len(unique) >= TEXT_SAMPLE_ROWS:
            break
    return unique


# ── контур 5: полнота по группам объектов (атом полноты — Q4) ──────────────────────
def check_group_closure(circle, disk, db_by_path, tag):
    """Каждая запись группы объяснена строкой или состоянием; незакрытые — по именам."""
    per_group = defaultdict(Counter)
    for path, entry in circle["expected_rows"].items():
        counter = per_group[entry["group"]]
        if path in disk:
            counter["text"] += 1
            counter["row" if path in db_by_path else "lost_row"] += 1
        else:
            counter["no_text"] += 1
            if path in db_by_path:
                counter["invented_row"] += 1

    unclosed = []
    for group, entry in sorted(circle["groups"].items()):
        counter = per_group.get(group, Counter())
        missing_file = entry["states"].get(STATE_INDEXED_NO_FILE, 0)
        accounted = (counter.get("row", 0) + counter.get("lost_row", 0)
                     + counter.get("no_text", 0) + missing_file)
        if accounted != entry["records"] or counter.get("invented_row", 0):
            kind, _, name = group.partition(".")
            unclosed.append({
                "group": group, "kind": kind or group, "name": name or group,
                "записей": entry["records"], "объяснено": accounted,
                "строк": counter.get("row", 0), "текста нет": counter.get("no_text", 0),
                "файла нет": missing_file,
                "строки нет, хотя файл с текстом": counter.get("lost_row", 0),
                "строка есть, хотя текста нет": counter.get("invented_row", 0),
            })
    check(f"{tag}: незакрытых групп нет — каждая запись круга объяснена строкой или "
          f"названным состоянием (Q4)", not unclosed,
          f"{len(unclosed)} групп")
    for item in unclosed[:MAX_UNCLOSED_NAMES]:
        print(f"       незакрытая группа: вид={item['kind']} имя={item['name']} — "
              f"{item['записей']} записей, объяснено {item['объяснено']} (строк "
              f"{item['строк']}, текста нет {item['текста нет']}, файла нет "
              f"{item['файла нет']}, строки нет при файле с текстом "
              f"{item['строки нет, хотя файл с текстом']}, строка есть при отсутствии "
              f"текста {item['строка есть, хотя текста нет']})")
    if len(unclosed) > MAX_UNCLOSED_NAMES:
        print(f"       ещё {len(unclosed) - MAX_UNCLOSED_NAMES} групп не называются")

    db_groups = set()
    for path in db_by_path:
        entry = circle["expected_rows"].get(path)
        if entry:
            db_groups.add(entry["group"])
    # Круг групп с текстом — НЕ `entry["rows"]` (это найденные файлы, а в них бывает
    # одна BOM: BGU2 — 938 таких файлов, BP3 — 1 514). Строка появляется только там,
    # где есть текст (Q2), поэтому и группа считается «со строками» только там, где
    # хотя бы один её файл содержит текст. Иначе сравнение множеств сравнивало бы
    # разные множества и проваливалось бы на любой выгрузке с пустыми модулями.
    circle_groups = {entry["group"]
                     for path, entry in circle["expected_rows"].items() if path in disk}
    check(f"{tag}: групп со строками в таблице ровно столько, сколько групп с файлами, "
          f"содержащими текст", db_groups == circle_groups,
          f"таблица: {len(db_groups)}, круг: {len(circle_groups)}, "
          f"разница: {sorted(db_groups ^ circle_groups)[:3]}")
    info(f"{tag}: групп круга {len(circle['groups'])}, с текстом "
         f"{len(circle_groups)}, незакрытых {len(unclosed)}")
    return len(unclosed)


# ── контур 6: чужой контур и эталонная пара ────────────────────────────────────────
def foreign_state(cur):
    """Снимок того, что узел трогать не должен (сверяется до и после прогона)."""
    state = {}
    state["external_module_rows"] = one(
        cur, f"SELECT count(*) AS c FROM {TARGET_TABLE} "
             f"WHERE parent_type = 'external_report'").get("c", 0)
    state["other_parent_types"] = one(
        cur, f"SELECT count(*) AS c FROM {TARGET_TABLE} WHERE parent_type <> ALL("
             f"ARRAY['external_report', %(parent_type)s])",
        {"parent_type": PARENT_TYPE}).get("c", 0)
    for table in ("external_report", "configurations", "configuration_objects",
                  "common_modules", "common_module_sources", "config_aliases",
                  "config_snippets", "config_cross_references"):
        state[table] = one(cur, f"SELECT count(*) AS c FROM {table}").get("c", 0)
    return state


def check_untouched(before, after):
    """Ни одна чужая строка за прогон не изменилась: проверка только читает."""
    changed = {key: (before[key], after[key]) for key in before
               if before[key] != after.get(key)}
    check("чужой контур (внешние объекты, обогащение, индекс состава) за прогон не "
          "изменён", not changed, f"{len(changed)}: {changed}")
    check("строк `bsl_modules` с иным `parent_type`, чем два контура, нет",
          after["other_parent_types"] == 0,
          f"иных parent_type: {after['other_parent_types']}. "
          f"Внешний контур: {after['external_module_rows']} строк")


# ── контур 8: ключ цепочки и витрина называют конфигурацию (шаг П1.1) ──────────────
KEY_INDEX = "uq_bsl_modules_parent_file_revision"
KEY_COLUMNS = "(configuration_uuid, parent_uuid, file_path, revision_no)"
SUBSYSTEM_KEY = "subsystem_content_object_revision_ordinal_key"
SUBSYSTEM_KEY_COLUMNS = "(configuration_uuid, subsystem_object_uuid, revision_no, ordinal)"
VIEW_BOUNDARY = "n.configuration_uuid = m.configuration_uuid"
DEAD_VIEW_BRANCH = "m.parent_uuid IS NULL"


def check_key_scope(cur):
    """Состояние ключа цепочки состояния и витрина (шаг П1.1, оператор 28.10.2026).

    Дефект, из-за которого контур появился: `parent_uuid` — uuid метаданных, общий для
    конфигураций, выросших из общей базы (замер 28.10.2026: 42 349 общих uuid), поэтому
    пара (родитель, путь) различает модуль только внутри одной конфигурации. При второй
    загрузке 2 015 пар BP3 оказались заняты строками BGU2, и вставка падала на индексе
    V19 посреди транзакции группы — ответ терял имя группы (контракт Q4).

    Контур читает ОПРЕДЕЛЕНИЯ живой схемы (не файл DDL — их сверяет `_cmp_ddl.py`) и
    различает две конфигурации фактом: строки одной пары `(parent_uuid, file_path)` из
    разных конфигураций обязаны остаться в витрине обе. Различение называется SKIP-ом,
    если в таблице одна конфигурация: пустая проверка не читается как успех.
    """
    index = str(one(cur, "SELECT indexdef AS def FROM pg_indexes WHERE indexname = %s",
                    (KEY_INDEX,)).get("def") or "")
    normalized = " ".join(index.split()).lower()
    check(f"ключ цепочки состояния `{KEY_INDEX}` называет четыре колонки",
          KEY_COLUMNS in normalized, f"живое определение: {index[:200]}")
    check(f"мёртвого предиката `WHERE parent_uuid IS NOT NULL` в определении ключа нет "
          f"(после NOT NULL шага П1 он истинен на каждой строке)",
          " where " not in normalized, f"живое определение: {index[:200]}")

    view = " ".join(str(one(
        cur, "SELECT pg_get_viewdef(%s::regclass, true) AS def",
        ("v_current_bsl_modules",)).get("def") or "").split())
    check(f"витрина `v_current_bsl_modules` разрешает цепочку внутри конфигурации "
          f"(граница {VIEW_BOUNDARY})", VIEW_BOUNDARY in view,
          f"определение витрины: {view[:200]}")
    check(f"мёртвой ветви `{DEAD_VIEW_BRANCH}` в витрине нет",
          DEAD_VIEW_BRANCH not in view, f"определение витрины: {view[:200]}")

    constraint = " ".join(str(one(
        cur, "SELECT pg_get_constraintdef(oid) AS def FROM pg_constraint "
             "WHERE conname = %s", (SUBSYSTEM_KEY,)).get("def") or "").split()).lower()
    check(f"ключ ссылок включения подсистем `{SUBSYSTEM_KEY}` называет конфигурацию "
          f"(дефект того же класса узла V46, закрыт этой же миграцией)",
          SUBSYSTEM_KEY_COLUMNS in constraint, f"живое определение: {constraint[:200]}")

    shared = one(cur, """
        SELECT count(*) AS pairs FROM (
            SELECT parent_uuid, file_path FROM bsl_modules
             GROUP BY 1, 2 HAVING count(DISTINCT configuration_uuid) > 1) s
    """)
    configs = one(cur, "SELECT count(DISTINCT configuration_uuid) AS c FROM bsl_modules"
                       " WHERE parent_type = %(parent_type)s",
                  {"parent_type": PARENT_TYPE}).get("c", 0)
    pairs = int(shared.get("pairs", 0))
    if pairs == 0 or configs < 2:
        skip("одна и та же пара (родитель, путь) из двух конфигураций различается "
             "витриной", f"в таблице конфигураций узла: {configs}, общих пар: {pairs} — "
                         "различать нечего, контур был бы пустым")
    else:
        lost = one(cur, """
            WITH shared AS (
                SELECT parent_uuid, file_path FROM bsl_modules
                 GROUP BY 1, 2 HAVING count(DISTINCT configuration_uuid) > 1),
            chains AS (
                SELECT configuration_uuid, parent_uuid, file_path,
                       max(revision_no) AS newest
                  FROM bsl_modules GROUP BY 1, 2, 3)
            SELECT (SELECT count(*) FROM bsl_modules m JOIN shared s
                      ON s.parent_uuid = m.parent_uuid AND s.file_path = m.file_path
                     WHERE NOT EXISTS (SELECT 1 FROM v_current_bsl_modules v
                                       WHERE v.id = m.id)) AS dropped,
                   (SELECT count(*) FROM chains c WHERE NOT EXISTS (
                        SELECT 1 FROM v_current_bsl_modules v
                         WHERE v.configuration_uuid = c.configuration_uuid
                           AND v.parent_uuid = c.parent_uuid
                           AND v.file_path = c.file_path
                           AND v.revision_no = c.newest)) AS chain_without_current
        """)
        dropped = int(lost.get("dropped", 0))
        without_current = int(lost.get("chain_without_current", 0))
        check(f"общих пар (родитель, путь) между конфигурациями названо числом и ни "
              f"одна из их строк не потеряна", dropped == 0,
              f"общих пар: {pairs}, конфигураций узла: {configs}, потеряно строк: {dropped}")
        check("каждая цепочка (конфигурация, родитель, путь) имеет ровно одну текущую "
              "строку витрины (тотальность M1 после расширения ключа)",
              without_current == 0, f"цепочек без текущей строки: {without_current}")
        info(f"граница П1.1: общих пар (родитель, путь) между конфигурациями — {pairs}, "
             f"конфигураций узла в таблице — {configs}; витрина различает их по "
             "configuration_uuid")


# ── граница R5: строки обязаны быть свежее файлов выгрузки ──────────────────────────
def dump_newer_than_rows(dump_dir, db_rows):
    """Время маркера выгрузки (`ConfigDumpInfo.xml`), если оно новее строк узла."""
    marker = Path(dump_dir) / "ConfigDumpInfo.xml"
    if not marker.is_file():
        return None
    stamp = datetime.fromtimestamp(marker.stat().st_mtime)
    newest = max((row["changed_at"] for row in db_rows if row["changed_at"]),
                 default=None)
    if newest is None:
        return None
    return stamp if stamp > newest else None


# ── прогон по строкам заголовков ───────────────────────────────────────────────────
def run(cur, scope):
    headers = q(cur, "SELECT id, uuid::text AS uuid, name FROM configurations "
                     "ORDER BY id")
    if not headers:
        print("FAIL строк заголовков конфигураций в базе нет — сравнивать не с чем")
        FAILED.append("нет строк заголовков")
        return
    before = foreign_state(cur)
    totals = Counter()
    run_tags = []
    skipped_tags = []
    for header in headers:
        resolved = resolve_dump_dir(header["uuid"], DUMP_ROOT)
        dump_dir = resolved.get("path") or ""
        tag = Path(dump_dir).name if dump_dir else str(header["name"])
        if scope not in (DEFAULT_SCOPE, tag, str(header["name"])):
            continue
        section(f"Конфигурация {tag} (uuid {header['uuid']})")
        if not dump_dir:
            skipped_tags.append(tag)
            skip(f"{tag}: все контуры узла",
                 resolved.get("reason") or "каталог выгрузки не найден")
            continue
        expect = PLAN_EXPECTATIONS.get(tag)
        if expect is None:
            skipped_tags.append(tag)
            skip(f"{tag}: все контуры узла",
                 f"каталога `{tag}` нет в перечне ожиданий проверки — числа круга "
                 f"этой выгрузки надо переснять и записать в план прежде, чем "
                 f"сравнивать с ними")
            continue
        circle = collect_circle(cur, header["uuid"], dump_dir)
        v46 = check_scope_boundary(cur, header["uuid"], circle, tag)
        check_circle_on_disk(circle, expect, tag)

        db_rows = read_db_rows(cur, header["uuid"])
        if not db_rows:
            skipped_tags.append(tag)
            skip(f"{tag}: контуры «файл ↔ строка» и полноты по группам",
                 "строк узла в таблице нет — конфигурацию не перезагружали после "
                 "узла V47 (стадия `s4b_object_modules` входит в загрузку каталога)")
            continue
        newer = dump_newer_than_rows(dump_dir, db_rows)
        if newer is not None:
            skipped_tags.append(tag)
            skip(f"{tag}: контуры «файл ↔ строка» и полноты по группам",
                 f"файлы выгрузки новее строк узла (правило R5): сохранённый код "
                 f"описывает прошлое состояние, сравнение с ним было бы сравнением "
                 f"с прошлым")
            continue

        disk, db_by_path, reading = check_rows_against_disk(
            cur, header["uuid"], dump_dir, circle, db_rows, expect, tag)
        check_row_fields(cur, header["uuid"], circle, disk, db_by_path, tag)
        check_group_closure(circle, disk, db_by_path, tag)

        totals["records"] += circle["records"]
        totals["files"] += reading["with_text"] + reading["no_text"]
        totals["rows"] += len(db_rows)
        totals["no_text"] += reading["no_text"]
        totals["indexed_no_file"] += circle["states"].get(STATE_INDEXED_NO_FILE, 0)
        totals["bin_side"] += len(circle["bin_side"])
        totals["v46_module_records"] += v46.get(SCOPE_V46, 0)
        totals["code_chars"] += sum(row["code_size"] or 0 for row in db_rows)
        # В перечень сравнения конфигурация входит только после того, как её числа
        # действительно легли в суммы: иначе итог сравнивает суммы по четырём строкам
        # плана с фактом по трём и проваливается на любой пропущенной выгрузке.
        run_tags.append(tag)

    after = foreign_state(cur)
    section("Итог узла V47")
    check_untouched(before, after)
    check_key_scope(cur)
    check_aggregate(totals, run_tags, skipped_tags)
    return


def check_aggregate(totals, run_tags, skipped_tags=()):
    """Сумма по проверенным конфигурациям равна суммам ожиданий плана (раздел 2)."""
    if not run_tags:
        skip("итог по узлу", "ни одной конфигурации не проверялось")
        return
    expected = Counter()
    for tag in run_tags:
        for key, value in PLAN_EXPECTATIONS[tag].items():
            expected[key] += value
    compared = {key: totals[key] for key in
                ("records", "files", "rows", "no_text", "indexed_no_file", "bin_side")}
    wanted = {key: expected[key] for key in compared}
    named_skipped = (f"; не сравнивались: {', '.join(skipped_tags)}"
                     if skipped_tags else "")
    check(f"итог по {len(run_tags)} проверенным конфигурациям ({', '.join(run_tags)}) "
          f"равен суммам ожиданий плана{named_skipped}", compared == wanted,
          f"факт: {compared}, план: {wanted}")
    if len(run_tags) == len(PLAN_EXPECTATIONS):
        check(f"записей слота `Module` общих модулей (предмет V46) названо "
              f"{V46_MODULE_RECORDS} и они вне круга",
              totals["v46_module_records"] == V46_MODULE_RECORDS,
              f"факт: {totals['v46_module_records']}, план: {V46_MODULE_RECORDS}")
    else:
        # Одиночный прогон тоже обязан сказать, чего он не проверяет: молчание
        # читалось бы как «число предместа сошлось». Называются и те каталоги плана,
        # которых не было в этом прогоне, — их снимает сам вызов по scope.
        not_compared = sorted(set(PLAN_EXPECTATIONS) - set(run_tags))
        info(f"записей слота `Module` общих модулей (предмет V46) посчитано по "
             f"сравненным конфигурациям {totals['v46_module_records']}; сверка с числом "
             f"плана {V46_MODULE_RECORDS} требует прогона по всем выгрузкам плана "
             f"({len(PLAN_EXPECTATIONS)}), в этом прогоне сравнены {len(run_tags)}; "
             f"вне сравнения: {', '.join(not_compared) if not_compared else 'нет'}"
             + (f"; не сравнивались: {', '.join(skipped_tags)}" if skipped_tags else ""))
    info(f"проверено конфигураций: {len(run_tags)}; записей круга "
         f"{totals['records']}, файлов {totals['files']}, строк узла "
         f"{totals['rows']} (решение Q2), без текста {totals['no_text']}, без файла "
         f"{totals['indexed_no_file']} (рядом .bin {totals['bin_side']} — O1, "
         f"подлинно пустых {totals['indexed_no_file'] - totals['bin_side']}), "
         f"символов кода {totals['code_chars']}")
    info("граница Q2: пустой модуль и отсутствующий модуль выражаются ОТСУТСТВИЕМ "
         "строки; состояний в схеме нет, и выводиться из них нечего")


def main(argv):
    scope = str(argv[1]) if len(argv) > 1 else DEFAULT_SCOPE
    try:
        with transaction() as cur:
            run(cur, scope)
    except Exception as exc:  # отказ прогона обязан быть назван, а не оборвать вывод
        FAILED.append(f"прогон прерван исключением: {exc}")
        print(f"FAIL прогон прерван исключением: {type(exc).__name__}: {exc}")
    print("\n" + "=" * 72)
    print(f"ИТОГ: пройдено {len(PASSED)}, провалено {len(FAILED)}, "
          f"пропущено {len(SKIPPED)}, заметок {len(INFO)}")
    for name in FAILED:
        print("  ПРОВАЛ: " + name)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
