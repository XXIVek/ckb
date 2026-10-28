#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_v47_p3_writer_probe.py — проба писателя модулей объектов (узел V47, шаг П3).

Норматив: `docs/CONFIGURATION_OBJECT_MODULES_PLAN.md`, шаг П3 (его проверяющая команда —
«проба писателя на пустом круге узла»). Проверяются решения Q2 (строка только там, где
есть раскодированный код), Q4 (атом полноты — группа объектов, отказ называет группу),
Q6 (граница второй транзакции: писатель работает курсором вызывающего) и правило C5
(нечитаемый файл — отказ стадии, а не потерянная строка).

В базе проба не оставляет ничего: все записи — внутри одной транзакции, которая в конце
откатывается, а после отката на новом соединении проверяется то же состояние, что и до
прогона (круг узла по каждой строке заголовка не изменился, строки внешнего контура на
месте). До узла П4 (28.10.2026) круг узла в живой базе был пуст и проверялся нулём; с тех
пор конвейер загрузки сам пишет строки узла (стадия S4b), и ноль в этой таблице — уже не
«состояние до пробы», а «конфигурация без модулей». Гарантия пробы другая: она ничего не
меняет, поэтому базовое состояние называется по каждой конфигурации и с ним же сравнивается.

Контуры:

  A. политика чтения `read_module_code` на синтетических файлах: BOM снимается, текст
     нормализуется, `code_size` равен числу символов `code`; байты, не являющиеся
     UTF-8 (в том числе cp1251), — состояние `undecoded`, а не «раскодовано как
     получилось»; файл из пробелов или одной BOM — `empty_file`; исчезнувший файл —
     `indexed_no_file` с причиной `file_disappeared`;
  B. запись MinCfg (круг 79, файл 79 — раздел 5 плана) внутри транзакции: форма строк,
     инварианты колонок (`code_size = length(code)`, `revision_no = 1`,
     `changed_by = 'load'`, `is_committed = true`, один штамп времени, `truncated =
     false`, `report_id IS NULL`), разрешение родителя по индексу той же конфигурации,
     совпадение `object_type`/`object_name` с колонками записи индекса, снятие прежних
     строк и отсутствие удвоения при повторном вызове;
  C. ключ цепочки состояния: повторная вставка той же строки падает на
     `uq_bsl_modules_parent_file_revision` — тотальность ключа после П1;
  D. KomMag: записи индекса без файла (38, из них 9 с `.bin` — открытая позиция O1) не
     считаются отказом и не получают строк; строки пишутся только для 111 файлов;
  E. C5: байты вне UTF-8 в файле ПОСЛЕДНЕГО по имени модуля копии MinCfg → отказ
     стадии с именем группы; `abandon_written_rows` снимает уже вставленное;
  F. файл из пробелов в копии → строки нет (Q2), состояние названо `empty_after_strip`;
  G. каталог выгрузки другой конфигурации и отсутствующая строка заголовка → отказ с
     причиной, ни одной строки не записано;
  H. время записи (MinCfg, KomMag) — полный замер модульной стадии делает П4.

Запуск: python _v47_p3_writer_probe.py
"""
from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for path in (str(ROOT), str(ROOT / "src")):
    if path not in sys.path:
        sys.path.insert(0, path)

from external_db import connect  # noqa: E402

import configuration_module_slots as slots  # noqa: E402
import configuration_module_writer as writer  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
WORK_DIR = ROOT / "_scratch" / "_v47_p3_work"

# Ожидания раздела 5 плана, исправленные замером `_v47_p3_text_measure.py` (28.10.2026).
# Различие названо прямо: П2 измерял состояние по размеру файла (`file` там, где байт
# больше нуля), а строку узел пишет только там, где раскодированный текст непуст
# (решение Q2). Файлов круга — 13 342, строк — 10 872: 2 470 файлов круга содержат
# одну BOM (`ef bb bf`, 3 байта) — так выгрузка записывает пустой модуль.
# `empty_after_strip` — число файлов, которые по размеру файлом-содержимым выглядят, но
# текста не дают; `empty_file` включает их вместе с нулевыми файлами (их на этих
# выгрузках ноль).
EXPECT = {
    "MinCfg": {"in_scope": 79, slots.STATE_FILE: 79,
               slots.STATE_INDEXED_NO_FILE: 0, slots.STATE_EMPTY_FILE: 0,
               "empty_after_strip": 0, "bin_side": 0, "written": 79},
    "XXI_Коммерческий_магазин_8_редакция_1_0_3": {
        "in_scope": 149, slots.STATE_FILE: 93,
        slots.STATE_INDEXED_NO_FILE: 38, slots.STATE_EMPTY_FILE: 18,
        "empty_after_strip": 18, "bin_side": 9, "written": 93},
}


FAILURES = []
PASSED = 0


def check(title: str, ok: bool, detail: str = "") -> bool:
    global PASSED
    print(f"  [{'OK' if ok else 'FAIL'}]   {title}" + (f" — {detail}" if detail else ""))
    if ok:
        PASSED += 1
    else:
        FAILURES.append(title)
    return bool(ok)


def note(text: str) -> None:
    print("       " + text)


def one(cur, sql: str, params=None):
    cur.execute(sql, params or {})
    row = cur.fetchone()
    return row[0] if row else None


def scope_params(configuration_uuid: str) -> dict:
    return {"configuration_uuid": str(configuration_uuid),
            "parent_type": slots.PARENT_TYPE}


def scope_count(cur, configuration_uuid: str, extra: str = "", params=None) -> int:
    """Счётчик строк узла с дополнительным условием (одна граница на весь прогон)."""
    merged = dict(scope_params(configuration_uuid))
    merged.update(params or {})
    return int(one(cur, "SELECT count(*) FROM bsl_modules m WHERE "
                        + writer.scope_where() + extra, merged) or 0)


def headers(cur) -> dict:
    """Строки заголовков по имени (uuid в тексте плана нет — имена печатает карточка)."""
    cur.execute("SELECT id, uuid::text AS uuid, name FROM configurations ORDER BY name")
    columns = [desc[0] for desc in cur.description]
    out = {}
    for values in cur.fetchall():
        card = dict(zip(columns, values))
        out[str(card["name"])] = card
    return out


# ── контур A: политика чтения (правило C5) ─────────────────────────────────────────
def check_reader(work: Path) -> None:
    print("\n=== A. read_module_code: строгое раскодирование ===")
    cases = [
        ("bom_crlf.bsl", "\ufeff&НаКлиенте\r\nПроцедура МодульЗагружен()\r\n"
                         "КонецПроцедуры\r\n".encode("utf-8"), writer.STATE_FILE),
        ("bad_utf8.bsl", b"\xff\xfe\x00\x01\x80\x81\xff", writer.STATE_UNDECODED),
        ("cp1251.bsl", "Процедура Тест()\r\nКонецПроцедуры".encode("cp1251"),
         writer.STATE_UNDECODED),
        ("spaces.bsl", b"   \r\n\t\r\n", writer.STATE_EMPTY_FILE),
        ("bom_only.bsl", "\ufeff".encode("utf-8"), writer.STATE_EMPTY_FILE),
    ]
    for file_name, raw, want_state in cases:
        path = work / file_name
        path.write_bytes(raw)
        read = writer.read_module_code(str(path))
        check(f"{file_name}: состояние {want_state}",
              read.get("state") == want_state,
              f"получено {read.get('state')}, причина {read.get('reason')}")

    text_read = writer.read_module_code(str(work / "bom_crlf.bsl"))
    code = text_read.get("code") or ""
    check("BOM и обрамляющая пустота сняты",
          not code.startswith("\ufeff") and code.startswith("&НаКлиенте")
          and not code.endswith(("\r", "\n")),
          repr(code[:12]) + "…" + repr(code[-8:]))
    check("code_size = число символов code (на этом стоит проверка П5)",
          text_read.get("code_size") == len(code),
          f"code_size={text_read.get('code_size')}, len(code)={len(code)}")
    check("нечитаемый файл назван причиной, а не молчанием",
          bool((writer.read_module_code(str(work / "bad_utf8.bsl")) or {}).get("reason")))
    check("запасной кодировки нет: cp1251 остаётся нечитаемым (политика V47)",
          writer.read_module_code(str(work / "cp1251.bsl")).get("state")
          == writer.STATE_UNDECODED)
    missing = writer.read_module_code(str(work / "нет_такого.bsl"))
    check("исчезнувший файл — indexed_no_file с причиной file_disappeared",
          missing.get("state") == slots.STATE_INDEXED_NO_FILE
          and missing.get("reason") == writer.REASON_FILE_DISAPPEARED,
          f"{missing.get('state')} / {missing.get('reason')}")
    empty = writer.read_module_code(str(work / "spaces.bsl"))
    check("пустой после нормализации — empty_file без кода",
          empty.get("state") == slots.STATE_EMPTY_FILE and empty.get("code") is None
          and empty.get("code_size") == 0)


# ── контуры B/D: запись и её инварианты ───────────────────────────────────────────
def scope_groups(cur, configuration_uuid: str) -> set:
    """Группы объектов круга узла по индексу (атом полноты, Q4)."""
    return {slots.object_group(str(record.get("name") or ""))
            for record in slots.iter_index_records(cur, configuration_uuid)}


def check_written_rows(cur, configuration_uuid: str, written: int) -> None:
    print("\n--- записанные строки: инварианты колонок и разрешения ---")
    bad = scope_count(cur, configuration_uuid,
                      " AND (m.code IS NULL OR m.code = '' OR m.code_size IS NULL"
                      " OR m.code_size <> length(m.code))")
    check("code непустой и code_size = length(code)", bad == 0,
          f"строк с расхождением: {bad}")
    bad = scope_count(cur, configuration_uuid,
                      " AND (m.truncated IS DISTINCT FROM FALSE OR m.report_id IS NOT NULL"
                      " OR m.module_name IS DISTINCT FROM m.module_type)")
    check("truncated = false, report_id NULL, module_name = module_type = слот",
          bad == 0, f"строк с расхождением: {bad}")
    bad = scope_count(cur, configuration_uuid,
                      " AND (m.revision_no <> 1 OR m.changed_by IS DISTINCT FROM 'load'"
                      " OR m.is_committed IS DISTINCT FROM TRUE OR m.changed_at IS NULL)")
    check("ревизия 1, changed_by = 'load', is_committed = true, штамп времени есть",
          bad == 0, f"строк с расхождением: {bad}")
    distinct = int(one(cur, "SELECT count(DISTINCT m.changed_at) FROM bsl_modules m WHERE "
                            + writer.scope_where(), scope_params(configuration_uuid)) or 0)
    check("один штамп времени на строки одной ревизии", distinct <= 1,
          f"различных changed_at: {distinct}")
    bad = scope_count(cur, configuration_uuid,
                      " AND (m.file_path IS NULL OR m.file_path NOT LIKE"
                      " '%%/Ext/%%' || m.module_name || '.bsl')")
    check("file_path — выводимый путь вида <Каталог>/…/Ext/<Слот>.bsl", bad == 0,
          f"строк с расхождением: {bad}")
    # Разрешение строки индексом — тем же способом, каким его строит словарь (П2):
    # запись модуля находится по `parent_name` + `child_type`, а её родитель и есть
    # `parent_uuid`. Сравнивать `child_type` родителя со слотом нельзя: у записи-владельца
    # свой `child_type` (`Command`, `Catalog`), и проверка стала бы пустой — этот дефект
    # поймала проба П3 (79 «неразрешённых» строк при корректных данных).
    matched = int(one(cur, """
        SELECT count(*) FROM bsl_modules m
          JOIN configurations c ON c.uuid = m.configuration_uuid
          JOIN configuration_objects p
            ON p.configuration_id = c.id AND p.uuid = m.parent_uuid
          JOIN configuration_objects o
            ON o.configuration_id = c.id AND o.parent_name = p.name
           AND o.child_type = m.module_type
         WHERE """ + writer.scope_where(), scope_params(configuration_uuid)) or 0)
    check("каждая строка узла сопоставлена записи индекса той же конфигурации",
          matched == written, f"сопоставлено {matched}, строк {written}")
    unresolved = scope_count(cur, configuration_uuid,
                             " AND NOT EXISTS (SELECT 1 FROM configuration_objects o"
                             " JOIN configurations c ON c.id = o.configuration_id"
                             " JOIN configuration_objects p"
                             "   ON p.configuration_id = o.configuration_id"
                             "  AND p.name = o.parent_name"
                             " WHERE o.child_type = m.module_type"
                             " AND p.uuid = m.parent_uuid"
                             " AND c.uuid = m.configuration_uuid)")
    check("parent_uuid разрешается записью индекса той же конфигурации", unresolved == 0,
          f"неразрешённых строк: {unresolved}")
    mismatch = int(one(cur, """
        SELECT count(*) FROM bsl_modules m
          JOIN configurations c ON c.uuid = m.configuration_uuid
          JOIN configuration_objects p
            ON p.configuration_id = c.id AND p.uuid = m.parent_uuid
          JOIN configuration_objects o
            ON o.configuration_id = c.id AND o.parent_name = p.name
           AND o.child_type = m.module_type
         WHERE """ + writer.scope_where() + """
           AND (o.object_type IS DISTINCT FROM m.object_type
                OR o.object_name IS DISTINCT FROM m.object_name)""",
        scope_params(configuration_uuid)) or 0)
    check("object_type/object_name = колонки записи индекса (вид и имя объекта)",
          mismatch == 0, f"строк с расхождением: {mismatch}")
    total = scope_count(cur, configuration_uuid)
    check("число строк узла в таблице = число записанных", total == written,
          f"в таблице {total}, записано {written}")


def check_result(result: dict, expect: dict, cur, configuration_uuid: str) -> None:
    """Сверка результата стадии с ожиданиями плана и с кругом по индексу."""
    check("стадия не отказала", result.get("status") == "ok"
          and not result.get("error") and not result.get("refusal"),
          f"{result.get('refusal')}: {result.get('error')}")
    counts = result.get("counts_by_state") or {}
    states = {slots.STATE_FILE, slots.STATE_EMPTY_FILE, slots.STATE_INDEXED_NO_FILE}
    check("сумма состояний = круг узла (одна запись — один итог)",
          sum(counts.get(state, 0) for state in states) == expect["in_scope"],
          f"{ {state: counts.get(state, 0) for state in states} } против "
          f"{expect['in_scope']}")
    for state in (slots.STATE_FILE, slots.STATE_EMPTY_FILE, slots.STATE_INDEXED_NO_FILE):
        check(f"состояние {state} = {expect[state]}", counts.get(state, 0) == expect[state],
              f"получено {counts.get(state, 0)}")
    check("отказов словаря и дефектов данных нет",
          not any(result.get("refusals", {}).values())
          and not any(result.get("defects", {}).values()),
          f"refusals={result.get('refusals')}, defects={result.get('defects')}")
    check(f"машинный код рядом (O1) назван: {expect['bin_side']}",
          result.get("bin_side") == expect["bin_side"],
          f"получено {result.get('bin_side')}, примеры "
          f"{(result.get('bin_side_examples') or [])[:3]}")
    check(f"файлов без текста (одна BOM) названо: {expect['empty_after_strip']}",
          result.get("empty_after_strip") == expect["empty_after_strip"],
          f"получено {result.get('empty_after_strip')}")
    check(f"записано строк = {expect['written']} (строки П6 плана)",
          result.get("written") == expect["written"], f"получено {result.get('written')}")
    groups = scope_groups(cur, configuration_uuid)
    check(f"группы круга посчитаны (атом полноты, Q4): {len(groups)}",
          result.get("groups", {}).get("seen") == len(groups),
          f"получено {result.get('groups')}")
    note(f"время стадии: {result.get('seconds')} с, символов кода: "
         f"{result.get('code_chars')}, строк снято перед записью: "
         f"{result.get('removed_previous')}")


def run_dump(cur, header: dict, dump_dir: Path, expect: dict, cache: dict,
             page_size: int = None) -> dict:
    """Запись одной конфигурации и её проверка (контуры B/D).

    `page_size` — сколько строк писатель вставляет одной командой. Проба гоняет и
    страницу по умолчанию (одна команда), и маленькую страницу: путь пакетной вставки
    не должен менять ни число строк, ни их содержимое.
    """
    uuid = str(header["uuid"])
    name = str(header["name"])
    print(f"\n=== запись {name}: круг {expect['in_scope']}, "
          f"файл {expect[slots.STATE_FILE]}, страница {page_size or 'по умолчанию'} ===")
    previous_page = writer.PAGE_SIZE
    if page_size:
        writer.PAGE_SIZE = page_size
    try:
        result = writer.write_object_modules(cur, uuid, dump_dir=str(dump_dir),
                                             cache=cache)
    finally:
        writer.PAGE_SIZE = previous_page
    check_result(result, expect, cur, uuid)
    check_written_rows(cur, uuid, int(result.get("written") or 0))
    return result


def check_second_call(cur, header: dict, expect: dict, dump_dir: Path,
                      cache: dict) -> None:
    """Второй вызов той же транзакции: прежние строки сняты, удвоения нет."""
    print("\n--- повторный вызов (снятие прежних строк, идемпотентность) ---")
    uuid = str(header["uuid"])
    again = writer.write_object_modules(cur, uuid, dump_dir=str(dump_dir), cache=cache)
    check(f"прежние строки узла сняты перед повторной записью ({expect['written']})",
          again.get("removed_previous") == expect["written"],
          f"снято {again.get('removed_previous')}")
    left = writer.count_scope_rows(cur, uuid)
    check("число строк узла не удвоилось", left == expect["written"], f"строк: {left}")


def check_duplicate_key(cur, configuration_uuid: str) -> None:
    """Ключ цепочки состояния после П1 тотален: второй такой же путь отклоняется."""
    print("\n--- ключ (parent_uuid, file_path, revision_no) ---")
    columns = ("module_name, file_path, code, object_type, object_name, parent_uuid, "
               "parent_type, module_type, code_size, truncated, revision_no, changed_at, "
               "changed_by, is_committed, configuration_uuid")
    sql = (f"INSERT INTO bsl_modules ({columns}) SELECT {columns} FROM bsl_modules m "
           "WHERE " + writer.scope_where() + " LIMIT 1")
    rejected = False
    cur.execute("SAVEPOINT v47_p3_dup")
    try:
        cur.execute(sql, scope_params(configuration_uuid))
    except Exception as exc:  # UniqueViolation — имя ограничения и есть ответ
        text = " ".join(str(exc).split())
        rejected = "uq_bsl_modules_parent_file_revision" in text
        note(text[:160])
    cur.execute("ROLLBACK TO SAVEPOINT v47_p3_dup")
    check("повторная строка того же пути и ревизии отклонена ключом", rejected)


# ── контуры E/F/G: копия выгрузки и состояния отказа ───────────────────────────────
def copy_dump(source: Path, target: Path) -> Path:
    """Копия выгрузки в рабочем каталоге пробы (исходник проба не меняет)."""
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(source), str(target))
    return target



def edge_module(cur, configuration_uuid: str, dump_copy: Path, last: bool = True):
    """Первый (или последний) по имени читаемый модуль круга в копии выгрузки."""
    found = None
    cache = {}
    for record in slots.iter_index_records(cur, configuration_uuid):
        derived = slots.derive_module_path(record, str(dump_copy), cache)
        if not derived["ok"]:
            continue
        absolute = Path(derived["abs_path"])
        if not absolute.is_file():
            continue
        found = (record, derived)
        if not last:
            return found
    return found


def check_c5(cur, header: dict, dump_copy: Path, cache: dict) -> None:
    """E: нечитаемый файл — отказ стадии, называющий группу (правило C5, Q4)."""
    uuid = str(header["uuid"])
    print("\n=== E. C5: файл вне UTF-8 — отказ стадии с именем группы ===")
    edge = edge_module(cur, uuid, dump_copy, last=True)
    if not check("в копии выгрузки найден модуль круга", bool(edge)):
        return
    record, derived = edge
    path = Path(derived["abs_path"])
    original = path.read_bytes()
    path.write_bytes(b"\xff\xfe" + original[:64])
    previous_page = writer.PAGE_SIZE
    writer.PAGE_SIZE = 10  # строки обязаны реально лечь до отказа
    try:
        result = writer.write_object_modules(cur, uuid, dump_dir=str(dump_copy),
                                             cache=cache)
    finally:
        writer.PAGE_SIZE = previous_page
    check("стадия отказала (C5), а не потеряла модуль молча",
          result.get("status") == "error", f"status={result.get('status')}")
    check("отказ называет незакрытую группу (критерий 8 плана)",
          bool(result.get("failed_group")),
          f"группа {result.get('failed_group')}, запись {result.get('failed_record')}")
    check("отказ названа раскодированием файла",
          "не раскодирован" in str(result.get("error")), str(result.get("error"))[:150])
    check("отказана именно испорченная запись (последняя по имени)",
          result.get("failed_record") == record.get("name"),
          f"испорчена: {record.get('name')}")
    in_table = writer.count_scope_rows(cur, uuid)
    check("до компенсирующего снятия часть строк уже в таблице", in_table > 0,
          f"строк: {in_table}, result.written={result.get('written')}")
    removed = writer.abandon_written_rows(cur, uuid, result)
    check("компенсирующий DELETE снимает вставленное (половины группы не остаётся)",
          removed == in_table and result.get("compensated_rows") == in_table,
          f"снято {removed}")
    check("после отказа строк узла — ноль", writer.count_scope_rows(cur, uuid) == 0)
    path.write_bytes(original)


def check_blank(cur, header: dict, expect: dict, dump_copy: Path, cache: dict) -> None:
    """F: файл без текста — строки нет (Q2), состояние названо отдельным числом."""
    uuid = str(header["uuid"])
    print("\n=== F. файл без текста: строки нет, состояние названо (Q2) ===")
    edge = edge_module(cur, uuid, dump_copy, last=False)
    if not check("в копии выгрузки найден модуль круга", bool(edge)):
        return
    record, derived = edge
    path = Path(derived["abs_path"])
    original = path.read_bytes()
    path.write_bytes("   \r\n\t".encode("utf-8"))
    result = writer.write_object_modules(cur, uuid, dump_dir=str(dump_copy), cache=cache)
    path.write_bytes(original)
    want = int(expect["written"]) - 1
    check("стадия не отказала: пустой модуль — штатное состояние выгрузки",
          result.get("status") == "ok", str(result.get("error")))
    check(f"записано {want} строк (пустой модуль строки не получил)",
          result.get("written") == want, f"получено {result.get('written')}")
    counts = result.get("counts_by_state") or {}
    check("состояние пустого файла названо",
          counts.get(slots.STATE_EMPTY_FILE, 0) == 1
          and counts.get(slots.STATE_FILE, 0) == want, str(counts))
    check("файл без текста отличается от нулевого файла числом empty_after_strip",
          result.get("empty_after_strip") == 1, f"получено {result.get('empty_after_strip')}")
    left = writer.count_scope_rows(cur, uuid)
    check("строк узла в таблице = записано", left == want, f"строк: {left}")
    by_path = int(one(cur, "SELECT count(*) FROM bsl_modules m WHERE "
                            + writer.scope_where() + " AND m.file_path = %(file_path)s",
                      dict(scope_params(uuid), file_path=derived["rel_path"])) or 0)
    check("строки испорченной записи в таблице нет", by_path == 0, f"строк: {by_path}")


def check_refusals(cur, header: dict, other: dict, dump_copy: Path,
                   baseline: dict) -> None:
    """G: чужой каталог выгрузки, несуществующий каталог, чужой заголовок."""
    print("\n=== G. отказ принять не свой источник ===")
    if other:
        other_uuid = str(other["uuid"])
        other_before = int(baseline.get(other_uuid) or 0)
        result = writer.write_object_modules(cur, other_uuid,
                                             dump_dir=str(dump_copy))
        check("каталог другой конфигурации отклонён (причина dump_dir_mismatch)",
              result.get("status") == "error"
              and result.get("refusal") == writer.REFUSAL_DUMP_DIR_MISMATCH,
              f"{result.get('refusal')}: {str(result.get('error'))[:120]}")
        # Отказ произошёл ДО снятия прежних строк (`remove_previous_rows` идёт после
        # сверки источника), поэтому круг чужой конфигурации остаётся базовым — и это
        # проверяется сравнением с базовым числом, а не с нулём: у загруженной
        # конфигурации строк узла ровно столько, сколько записал конвейер.
        left_other = writer.count_scope_rows(cur, other_uuid)
        check("ни одной строки другой конфигурации не записано и прежние не сняты",
              left_other == other_before, f"строк: {left_other}, базовое: {other_before}")
    result = writer.write_object_modules(cur, str(header["uuid"]),
                                         dump_dir=str(WORK_DIR / "нет_такого"))
    check("несуществующий каталог выгрузки назван отказом",
          result.get("status") == "error"
          and "Каталог выгрузки" in str(result.get("error")),
          str(result.get("error"))[:120])
    result = writer.write_object_modules(
        cur, "00000000-0000-0000-0000-000000000000", dump_dir=str(dump_copy))
    check("отсутствующая строка заголовка названа причиной, а не нулём строк",
          result.get("status") == "error"
          and "Строка заголовка" in str(result.get("error")),
          str(result.get("error"))[:120])


def other_contour_rows(cur):
    """Снимок строк чужих контуров таблицы (внешний контур, V46) — для неприкосновенности."""
    cur.execute("SELECT id, parent_type, file_path, code_size FROM bsl_modules "
                "WHERE parent_type <> %s ORDER BY id", (slots.PARENT_TYPE,))
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, values)) for values in cur.fetchall()]


def circle_rows_by_header(cur) -> dict:
    """Сколько строк круга узла лежит у каждой строки заголовка ДО пробы.

    Писатель снимает прежние строки своей конфигурации сам (`remove_previous_rows`),
    поэтому «пустой круг» внутри транзакции пробы создаётся им же, а не состоянием базы.
    Значит проверять надо не ноль, а неизменность: базовое число каждой конфигурации
    называется и сравнивается с ним же после отката.
    """
    cur.execute("SELECT c.uuid::text, count(b.id) FROM configurations c LEFT JOIN "
                "bsl_modules b ON b.configuration_uuid = c.uuid AND b.parent_type = %s "
                "GROUP BY c.uuid", (slots.PARENT_TYPE,))
    return {str(uuid): int(count or 0) for uuid, count in cur.fetchall()}


def main() -> int:
    print("ПРОГОН V47 (П3): писатель модулей объектов конфигурации в bsl_modules")
    if not DUMP_ROOT.is_dir():
        print(f"Каталог выгрузок не найден: {DUMP_ROOT}")
        return 2
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    (WORK_DIR / "_reader").mkdir(parents=True, exist_ok=True)

    started = time.time()
    cache = {}
    with connect() as conn:
        cur = conn.cursor()
        heads = headers(cur)
        contour_before = other_contour_rows(cur)
        total_before = int(one(cur, "SELECT count(*) FROM bsl_modules") or 0)
        circle_before = circle_rows_by_header(cur)
        note(f"базовое состояние круга узла по строкам заголовков: {circle_before}; "
             "строк таблицы всего: " + str(total_before))
        mincfg = heads.get("MinCfg")
        kommag = heads.get("XXI_Коммерческий_магазин_8_редакция_1_0_3")
        bgu = heads.get("БухгалтерияГосударственногоУчреждения")
        if not check("строки заголовков MinCfg и KomMag найдены в базе",
                     bool(mincfg) and bool(kommag)):
            conn.rollback()
            return 1

        check_reader(WORK_DIR / "_reader")

        resolved = {}
        for header in (mincfg, kommag):
            found = slots.resolve_dump_dir(str(header["uuid"]), DUMP_ROOT)
            if check(f"каталог выгрузки {header['name']} разрешён по uuid корня",
                     bool(found.get("path")), str(found.get("reason"))):
                resolved[str(header["uuid"])] = Path(found["path"])

        for header, expect in ((mincfg, EXPECT["MinCfg"]),
                               (kommag, EXPECT["XXI_Коммерческий_магазин_8_редакция_1_0_3"])):
            uuid = str(header["uuid"])
            dump_dir = resolved.get(uuid)
            if not dump_dir:
                continue
            empty_now = writer.count_scope_rows(cur, uuid)
            if not check(f"круг узла {header['name']} до записи назван и равен базовому "
                         f"(пуст он или заполнен конвейером — не меняет дела)",
                         empty_now == circle_before.get(uuid, 0),
                         f"строк: {empty_now}, базовое: {circle_before.get(uuid, 0)}"):
                continue
            run_dump(cur, header, dump_dir, expect, cache)
            check_second_call(cur, header, expect, dump_dir, cache)
            check_duplicate_key(cur, uuid)

        mincfg_dir = resolved.get(str(mincfg["uuid"]))
        if mincfg_dir:
            check_blank(cur, mincfg, EXPECT["MinCfg"],
                        copy_dump(mincfg_dir, WORK_DIR / "MinCfg_blank"), cache)
            check_c5(cur, mincfg, copy_dump(mincfg_dir, WORK_DIR / "MinCfg_corrupt"), cache)
            check_refusals(cur, mincfg, bgu,
                           copy_dump(mincfg_dir, WORK_DIR / "MinCfg_refusal"),
                           circle_before)

        conn.rollback()
        note("транзакция пробы откатана — в базе не изменилось ни одной строки узла "
             "(ни записанного, ни снятого)")

    with connect() as conn:
        cur = conn.cursor()
        total_after = int(one(cur, "SELECT count(*) FROM bsl_modules") or 0)
        check("после отката в таблице то же число строк, что и до пробы",
              total_after == total_before, f"до {total_before}, после {total_after}")
        contour_after = other_contour_rows(cur)
        check("строки чужих контуров таблицы (внешний контур, V46) не тронуты",
              contour_after == contour_before,
              f"до {len(contour_before)}, после {len(contour_after)}")
        left = {str(header["uuid"]): writer.count_scope_rows(cur, str(header["uuid"]))
                for header in heads.values()}
        check("после отката круг узла по всем строкам заголовков равен базовому",
              {uuid: count for uuid, count in left.items() if count}
              == {uuid: count for uuid, count in circle_before.items() if count},
              f"базовое: {circle_before}, после: {left}")

    shutil.rmtree(WORK_DIR, ignore_errors=True)
    print(f"\nИТОГ: пройдено {PASSED}, провалено {len(FAILURES)} "
          f"(время прогона {time.time() - started:.1f} с)")
    for title in FAILURES:
        print("  ПРОВАЛ: " + title)
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    sys.exit(main())





