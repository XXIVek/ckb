#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/check_v31_provenance.py — проверка узла V31: провенанс источника загрузки.

Модель (принята оператором 16.10.2026): каталог выгрузки — транспорт, а не источник истины.
Чтобы отличить «дубликат того же источника» от «дубликата изменённого источника», загрузчик
кладёт в строку `external_report` провенанс входа: вид входа (origin_kind), путь источника
(origin_path), отпечаток его состава (origin_sha256 + origin_manifest) и время записи
(origin_recorded_at). Снимка имени нет: имя — атрибут содержимого, оно читается своей
колонкой (тот же контракт, что у V20.1). Область отпечатка и причина его отсутствия живут
в манифесте jsonb, а не в отдельных колонках: два разных числа не должны выглядеть
сопоставимыми.

Проверяемые группы (14) и почему именно так:
  1. схема: пять колонок PROVENANCE_COLUMNS, три именованных CHECK (словарь вида, пара
     kind/path, формат sha256) и индекс по origin_sha256; выдуманных колонок
     (origin_size / origin_loaded_at / origin_digest_scope / origin_name_id) в модели нет;
     DDL-источник, миграция и спецификации обоих писателей называют те же имена
     (полную сверку установки с живой БД делает _cmp_ddl.py);
  2. словарь видов и resolve_origin: вид и путь заявляет вызывающий, путь абсолютный,
     неизвестный вид — отказ collect(), а не запись в БД;
  3. отпечаток каталога: детерминирован, правка и переименование файла меняют его, порядок
     обхода — нет; область 'listing'; сверка файла с перечнем — unknown, а не differ;
  4. отпечаток файла: sha256 байтов, область 'file', file_count = 1;
  5. деградация: пустой каталог — отказ; усечённый или слишком длинный перечень — провенанс
     записан БЕЗ отпечатка с причиной (state_of = recorded, origin_sha256 NULL);
  6. загрузка каталога: колонки в ответе загрузчика == колонки в БД == то, что считает
     external_provenance отдельно; карточка печатирует происхождение строки;
  7. манифест в БД == перечень с диска; плоская выборка find_external_object разворачивается
     в ту же структуру (иначе карточка дубликата врала бы про состав источника);
  8. дубликат того же каталога: вердикт same вычислен ДО отказа, карточка ⚠️ называет
     источник совпадающим и печатает путь и отпечаток из строки БД;
  9. копия того же содержимого в другом пути: вердикт тоже same — compare() описывает
     содержимое источника, а не путь загрузки; при этом origin_path различается, и это
     два разных факта, которые нельзя смешивать;
 10. изменённая копия → differ: причина «отпечатки различаются» названа прямо, карточка
     даёт действие (force=True); 10b force=True — вердикт о прежней строке посчитан ДО
     удаления, строка новая, провенанс = новое состояние копии;
 11. строка без провенанса: state_of = not_recorded, вердикт unknown (не same и не differ),
     карточка называет состояние прямо и говорит, как записать провенанс;
 12. двоичный файл (узел V25): сначала провенанс восстановлен загрузкой каталога (он
     пишется при каждой загрузке — в отличие от configuration_id, узел V20), затем тот же
     uuid из .erf даёт differ по виду источника, а force=True записывает вид binary_file,
     путь самого файла и sha256 его байтов. Каталог разбора ibcmd источником не является,
     два разбора одного файла дают одинаковый отпечаток — в этом и был смысл узла V31;
 13. сбой сбора провенанса (подмена collect_provenance в модуле загрузчика): загрузка идёт,
     origin_* NULL, предупреждение называет причину и путь источника, карточка не рисует
     блок провенанса, сравнение даёт unknown;
 14. состояние БД до и после прогона одинаково: строки оператора целы, сирот нет.

Эталонная пара (Test1_Otchet, Test2_Otchet) не трогается: загрузка и удаление идут на
Test3_Otchet_Null — тот же выбор, что у tools/check_v20_config_link.py. Двоичный эталон
группы 12 — Test3_ОтчетПустой.erf: его uuid совпадает с uuid тестового каталога, поэтому
двоичный маршрут проходит по той же тестовой строке и не снимает запись оператора. Совпадение
uuid проверяется перед прогоном (uuids_in_binary): при расхождении группа пропускается.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python tools/check_v31_provenance.py
Код возврата 0 — все проверки пройдены.
"""

import hashlib
import os
import re
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

try:  # кириллица и эмодзи в консоли Windows (cp1251) — как в остальных валидаторах
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from config_load_router import format_load_result, load_catalog  # noqa: E402
from external_db import transaction  # noqa: E402
import external_provenance as provenance  # noqa: E402  # пороги меняются на месте (группа 5)
from external_provenance import (ORIGIN_AUTHORED_LAYOUT, ORIGIN_BINARY_FILE,  # noqa: E402
                                 ORIGIN_CATALOG, PROVENANCE_COLUMNS, STATE_NOT_RECORDED,
                                 STATE_RECORDED, collect, columns_of, compare,
                                 is_known_kind, listing_of_directory, canonical_listing,
                                 manifest_from_flat, resolve_origin, sha256_of_file, state_of)
import external_report_loader  # noqa: E402  # подмена сбора провенанса (группа 13)
from external_report_loader import (delete_external_object,  # noqa: E402
                                   find_external_object)
from ibcmd_bridge import convert_and_load  # noqa: E402  # маршрут .erf/.epf (узел V25)

TEST_CATALOG = r"C:\1C_LLM\LoadDoc\Test3_Otchet_Null"
# Эталон двоичного файла (узел V25) — Test3_ОтчетПустой.erf. Выбор не случайный: замером
# подтверждено, что uuid внутри файла совпадает с uuid тестового каталога Test3_Otchet_Null,
# поэтому двоичный маршрут проходит по ТОЙ ЖЕ тестовой строке и не трогает строки оператора
# (у БП3\СравнениеУСНИ90_2.erf uuid занят строкой external_report, и force=True снял бы
# чужой объект вместе с его содержимым). Файл лежит вне проекта и может отсутствовать на
# другой машине — тогда группа пропускается с явной причиной, а не «падает» и не молчит.
SOURCE_ROOT = r"C:\1C_LLM\LoadDoc"
BINARY_REFERENCE = os.path.join(SOURCE_ROOT, "Test3_ОтчетПустой.erf")
BRIDGE_SOURCE = ROOT / "src" / "ibcmd_bridge.py"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
# Имена, которых в модели нет: их предлагала первая постановка узла. Область отпечатка и
# причина живут в манифесте jsonb, размер — в перечне файлов, снимок имени не заводится.
INVENTED_COLUMNS = ("origin_size", "origin_loaded_at", "origin_digest_scope",
                    "origin_digest_reason", "origin_name_id")
CHECK_NAMES = ("external_report_origin_kind_check", "external_report_origin_pair_check",
               "external_report_origin_sha256_check")

PASSED, FAILED = [], []
SKIPPED = 0


def check(name, ok, detail=""):
    (PASSED if ok else FAILED).append(name)
    print(("PASS " if ok else "FAIL ") + name + ((" — " + str(detail)) if detail else ""))


def skip(name, reason):
    """Проверку нельзя выполнить: внешний эталон недоступен. Промолчать — значит соврать."""
    global SKIPPED
    SKIPPED += 1
    print("SKIP " + name + " — " + str(reason))


def q(sql, params=None):
    with transaction() as cur:
        cur.execute(sql, params if isinstance(params, dict) else tuple(params or ()))
        if not cur.description:
            return []
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def write_text(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


def origin_row(uuid):
    """Колонки провенанса одной строки (jsonb psycopg2 отдаёт dict) плюс её id."""
    rows = q("SELECT id, " + ", ".join(PROVENANCE_COLUMNS)
             + " FROM external_report WHERE uuid = %(u)s::uuid", {"u": uuid})
    return rows[0] if rows else None


def db_snapshot(exclude_uuid=None):
    """Снимок того, что трогать нельзя: строки оператора, их провенанс и обогащение.

    `exclude_uuid` — тестовый объект прогона: он принадлежит скрипту (группа 14 его снимает),
    а до прогона мог остаться в БД от предыдущего запуска. Учитывать его в сравнении «до/после»
    значит получить расхождение там, где прогон ничего не менял.
    """
    sql = ("SELECT er.id, er.uuid, er.name, er.configuration_id, er.object_kind, "
           "       er.origin_kind, "
           "       (SELECT count(*) FROM attributes a WHERE a.parent_uuid = er.uuid) AS attrs, "
           "       (SELECT count(*) FROM forms f WHERE f.parent_uuid = er.uuid) AS forms, "
           "       (SELECT count(*) FROM bsl_modules m WHERE m.parent_uuid = er.uuid) AS modules, "
           "       (SELECT count(*) FROM config_aliases ca WHERE ca.parent_uuid = er.uuid) AS aliases, "
           "       (SELECT count(*) FROM config_snippets cs WHERE cs.parent_uuid = er.uuid) AS snippets, "
           "       (SELECT count(*) FROM config_cross_references cr WHERE cr.parent_uuid = er.uuid) AS links "
           "FROM external_report er")
    params = {}
    if exclude_uuid:
        sql += " WHERE er.uuid <> %(ex)s::uuid"
        params["ex"] = str(exclude_uuid)
    rows = q(sql + " ORDER BY er.id", params)
    for row in rows:
        row["uuid"] = str(row["uuid"])
    return rows


def card_of(result):
    """Карточка исхода тем же форматтером, который использует MCP-инструмент."""
    return format_load_result(result).splitlines()


def card_has(card, marker):
    return any(marker in line for line in card)


def root_xml_of(catalog):
    """Корневой XML каталога выгрузки (имя файла — имя объекта, его задаёт выгрузка)."""
    for path in sorted(Path(catalog).glob("*.xml")):
        return path
    return None


def uuid_of_root_xml(root_xml):
    """uuid внешнего объекта из корневого XML — он же ключ строки БД (правило R3)."""
    text = read_text(root_xml)
    match = re.search(r'External(?:Report|DataProcessor)[^>]*uuid="([0-9a-fA-F-]{36})"', text)
    return match.group(1) if match else None


def uuids_in_binary(path):
    """uuid, встречающиеся в двоичном файле внешнего объекта (три кодировки на выбор).

    Нужно ровно для одного: убедиться, что двоичный эталон относится к ТЕСТОВОЙ строке, а
    не к строке оператора. Двоичный вход с чужим uuid дал бы не дубликат, а новый объект —
    и проверка «провенанс указывает на сам файл» прошла бы за счёт чужой записи, которую
    прогон потом удалил бы вместе с содержимым.
    """
    data = Path(path).read_bytes()
    pattern = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
    found = set()
    for encoding in ("utf-8", "utf-16-le", "utf-16-be"):
        found |= {match.group(0).lower() for match in pattern.finditer(data.decode(encoding, "ignore"))}
    return found


def file_entries(manifest):
    """Файлы манифеста как отсортированные кортежи (path, sha256, bytes) — для сверки."""
    return sorted((str(item.get("path")), item.get("sha256"), item.get("bytes"))
                  for item in (manifest or {}).get("files") or [])


def copy_catalog_source(source, target):
    """Копия каталога выгрузки в другой путь — та же выгрузка, ДРУГОЙ источник.

    Нужна ровно для одного вопроса: сравнивает ли провенанс содержимое или путь. Копия
    даёт тот же отпечаток перечня (пути в перечне относительные), поэтому вердикт по
    содержимому обязан быть `same`; различие пути при этом видно в колонке origin_path.
    """
    try:
        shutil.copytree(source, target)
        return True
    except OSError as exc:
        print(f"не удалось скопировать каталог {source} → {target}: {exc}")
        return False


def main():
    print("=" * 78)
    print("УЗЕЛ V31 — провенанс источника загрузки (origin_* в external_report)")
    print("=" * 78)

    root_xml = root_xml_of(TEST_CATALOG)
    if not root_xml:
        print(f"❌ корневой XML эталона не найден: {TEST_CATALOG}")
        return 1
    uuid_test = uuid_of_root_xml(root_xml)
    if not uuid_test:
        print(f"❌ в корневом XML нет uuid: {root_xml}")
        return 1
    print(f"эталон прогона: {TEST_CATALOG} (uuid {uuid_test})")
    # Снимок «чего трогать нельзя» — БЕЗ тестового объекта: он принадлежит прогону (группа 14
    # его снимает), а до прогона мог остаться в базе от предыдущего запуска.
    if origin_row(uuid_test):
        print("ℹ️ тестовый объект уже был в БД (остался от предыдущего прогона) — прогон "
              "считает его своим и снимет в конце")
    before = db_snapshot(exclude_uuid=uuid_test)
    print(f"строк оператора до прогона: {len(before)}")
    print()

    tmp = Path(tempfile.mkdtemp(prefix="v31_prov_"))
    # Копия эталона — ВНУТРИ временного каталога: уборка за собой одна (tmp), и путь копии
    # заведомо отличается от пути источника.
    copy_catalog = str(tmp / "copy_catalog")

    try:
        # ── 1. схема: колонки, CHECK, индекс; выдуманных имён нет ───────────────────
        cols = {row["column_name"]: row["data_type"] for row in q(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'external_report'")}
        absent = [column for column in PROVENANCE_COLUMNS if column not in cols]
        check("пять колонок провенанса в живой схеме есть", not absent, absent)
        check("типы колонок соответствуют модели (text + jsonb + timestamp)",
              cols.get("origin_kind") == "text" and cols.get("origin_path") == "text"
              and cols.get("origin_sha256") == "text"
              and cols.get("origin_manifest") == "jsonb"
              and str(cols.get("origin_recorded_at", "")).startswith("timestamp"),
              {column: cols.get(column) for column in PROVENANCE_COLUMNS})
        invented = [column for column in INVENTED_COLUMNS if column in cols]
        check("выдуманных колонок в схеме нет (область и причина живут в манифесте jsonb)",
              not invented, invented)
        constraints = {row["conname"] for row in q(
            "SELECT conname FROM pg_constraint WHERE conrelid = 'external_report'::regclass")}
        check("три именованных CHECK есть: словарь вида, пара kind/path, формат sha256",
              all(name in constraints for name in CHECK_NAMES),
              sorted(set(CHECK_NAMES) - constraints))
        check("индекс по origin_sha256 есть — обратный поиск источника штатный",
              bool(q("SELECT indexname FROM pg_indexes WHERE tablename = 'external_report' "
                     "AND indexname = 'idx_external_report_origin_sha256'")))
        ddl = read_text(ROOT / "src" / "generate_ddl.py")
        migration = read_text(ROOT / "migrate_v31_provenance.sql")
        writer = read_text(ROOT / "src" / "external_table_writer.py")
        check("один словарь колонок: DDL-источник, миграция и писатели называют те же имена",
              all(all(column in text for column in PROVENANCE_COLUMNS)
                  for text in (ddl, migration, writer)))
        check("CHECK в DDL-источнике и миграции названы одними именами",
              all(all(name in text for name in CHECK_NAMES) for text in (ddl, migration)))
        check("проверка вида источника выполняется до записи (is_known_kind), а не падением CHECK",
              is_known_kind(ORIGIN_CATALOG) and is_known_kind(ORIGIN_BINARY_FILE)
              and is_known_kind(ORIGIN_AUTHORED_LAYOUT) and not is_known_kind("binary_fle"))

        # ── 2. resolve_origin: источник заявляет вызывающий ─────────────────────────
        path, kind = resolve_origin(None, None, TEST_CATALOG)
        check("по умолчанию источник — сам каталог выгрузки (вид catalog)",
              kind == ORIGIN_CATALOG and path == os.path.abspath(TEST_CATALOG), (kind, path))
        erf = tmp / "obj.erf"
        write_text(erf, "erf-bytes")
        path, kind = resolve_origin(str(erf), ORIGIN_BINARY_FILE, tmp / "conv" / "obj")
        check("для двоичного файла источник — сам файл, а не каталог разбора",
              kind == ORIGIN_BINARY_FILE and path == os.path.abspath(str(erf)), (kind, path))
        path, _ = resolve_origin(str(tmp / "conv" / ".." / "obj"), ORIGIN_CATALOG, None)
        check("путь нормализуется до абсолютного (карточка и сверка называют одно)",
              path == os.path.abspath(str(tmp / "obj")), path)
        bad = collect("binary_fle", str(erf))
        check("неизвестный вид — отказ collect() с прямым перечнем допустимых",
              not bad.get("success") and "неизвестный вид источника" in str(bad.get("reason")),
              bad.get("reason"))
        check("отказ по пустому пути назван прямо",
              not collect(ORIGIN_CATALOG, "").get("success"))

        # ── 3. отпечаток каталога: состав, а не путь и не порядок обхода ────────────
        tree = tmp / "tree"
        write_text(tree / "a.xml", "<a/>")
        write_text(tree / "Forms" / "b.xml", "<b/>")
        write_text(tree / "Forms" / "c.xml", "<c/>")
        first = collect(ORIGIN_CATALOG, str(tree))
        again = collect(ORIGIN_CATALOG, str(tree))
        check("отпечаток каталога детерминирован (повторный обход совпадает)",
              first.get("success") and first["sha256"] == again["sha256"],
              (first.get("sha256"), again.get("sha256")))
        manifest = first["manifest"]
        sizes = sum(p.stat().st_size for p in tree.rglob("*") if p.is_file())
        check("манифест каталога: область listing, полное число файлов и байт",
              manifest["digest_scope"] == "listing" and manifest["file_count"] == 3
              and manifest["truncated"] is False and manifest["total_bytes"] == sizes,
              {key: manifest.get(key) for key in
               ("digest_scope", "file_count", "total_bytes", "truncated")})
        names = [entry["path"] for entry in manifest["files"]]
        check("перечень хранит относительные пути с прямыми слэшами и берётся целиком из каталога",
              len(names) == 3 and "Forms/b.xml" in names
              and all(not os.path.isabs(name) and "\\" not in name for name in names)
              and names == [entry["path"] for entry in listing_of_directory(str(tree))[0]],
              names)
        # Порядок строк в манифесте — порядок обхода (os.walk с сортировкой имён по каталогам),
        # а отпечаток считается по КАНОНИЧЕСКОМУ списку, отсортированному по пути. Поэтому
        # «порядок обхода не влияет» проверяется через canonical_listing, а не через sorted()
        # от имён: сортировка Python учитывает регистр ( 'Forms/…' встанет раньше 'a.xml'),
        # обход — нет, и сравнивать эти два порядка было бы неверно по смыслу.
        canonical = canonical_listing(manifest["files"])
        check("отпечаток каталога = sha256 канонического перечня (порядок обхода не влияет)",
              first["sha256"] == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
              and [line.split("\t")[0] for line in canonical.splitlines()]
                  == sorted(line.split("\t")[0] for line in canonical.splitlines()),
              canonical.splitlines())
        write_text(tree / "a.xml", "<a edited/>")
        edited = collect(ORIGIN_CATALOG, str(tree))
        check("правка файла меняет отпечаток каталога", edited["sha256"] != first["sha256"],
              (first["sha256"][:12], edited["sha256"][:12]))
        shutil.move(str(tree / "a.xml"), str(tree / "a-renamed.xml"))
        renamed = collect(ORIGIN_CATALOG, str(tree))
        check("переименование файла меняет отпечаток (состав входит в перечень)",
              renamed["sha256"] != edited["sha256"], (edited["sha256"][:12], renamed["sha256"][:12]))
        single = collect(ORIGIN_BINARY_FILE, str(tree / "a-renamed.xml"))
        check("область отпечатка различает файл и перечень каталога",
              single["manifest"]["digest_scope"] == "file"
              and single["sha256"] != renamed["sha256"],
              (single["manifest"]["digest_scope"], single["sha256"][:12]))
        mixed = compare(single, {"origin_kind": ORIGIN_BINARY_FILE,
                                 "origin_path": str(tree / "a-renamed.xml"),
                                 "origin_sha256": renamed["sha256"],
                                 "origin_manifest": renamed["manifest"]})
        check("несовпадающие области отпечатков дают unknown, а не differ",
              mixed["verdict"] == "unknown" and "области отпечатков" in mixed["reason"], mixed)
        wrong_kind = compare(single, {"origin_kind": ORIGIN_CATALOG,
                                      "origin_path": str(tree), "origin_sha256": renamed["sha256"],
                                      "origin_manifest": renamed["manifest"]})
        check("разный вид источника — differ с прямым указанием, что записано",
              wrong_kind["verdict"] == "differ" and "вид источника другой" in wrong_kind["reason"],
              wrong_kind)

        # ── 4. отпечаток файла ──────────────────────────────────────────────────────
        data = b"\xff\xfe erf container bytes \x00"
        Path(erf).write_bytes(data)
        file_prov = collect(ORIGIN_BINARY_FILE, str(erf))
        check("sha256 файла = sha256 его байтов",
              file_prov["sha256"] == hashlib.sha256(data).hexdigest(), file_prov.get("sha256"))
        check("манифест файла: file_count = 1, total_bytes = размер, область file",
              file_prov["manifest"]["file_count"] == 1
              and file_prov["manifest"]["total_bytes"] == len(data)
              and file_prov["manifest"]["digest_scope"] == "file",
              {key: file_prov["manifest"].get(key)
               for key in ("file_count", "total_bytes", "digest_scope")})
        check("формат отпечатка — 64 hex (CHECK схемы не обмануть)",
              bool(SHA_RE.match(str(file_prov["sha256"]))))
        missing = collect(ORIGIN_BINARY_FILE, str(tmp / "нет-такого.erf"))
        check("несуществующий файл — отказ с названным путём",
              not missing.get("success") and "файл источника не найден" in str(missing.get("reason")),
              missing.get("reason"))

        # ── 5. деградация: пустой каталог, усечённый и слишком длинный перечень ─────
        empty = tmp / "empty"
        empty.mkdir()
        empty_prov = collect(ORIGIN_CATALOG, str(empty))
        check("пустой каталог — отказ «нет ни одного файла», а не пустой отпечаток",
              not empty_prov.get("success")
              and "нет ни одного файла" in str(empty_prov.get("reason")), empty_prov.get("reason"))
        provenance.MAX_MANIFEST_FILES = 1
        try:
            cut = collect(ORIGIN_CATALOG, str(tree))
        finally:
            provenance.MAX_MANIFEST_FILES = 2000
        check("усечённый перечень: провенанс записан, отпечатка нет, причина названа",
              cut.get("success") and cut["sha256"] is None
              and cut["manifest"]["truncated"] is True and cut["manifest"].get("digest_reason")
              and any("Провенанс записан без отпечатка" in w for w in cut.get("warnings") or []),
              cut["manifest"].get("digest_reason"))
        check("state_of различает «записан без отпечатка» и «провенанса нет»",
              state_of(columns_of(cut)) == STATE_RECORDED
              and state_of(columns_of(empty_prov)) == STATE_NOT_RECORDED)
        provenance.MAX_LISTING_CHARS = 10
        try:
            long_listing = collect(ORIGIN_CATALOG, str(tree))
        finally:
            provenance.MAX_LISTING_CHARS = 200000
        check("слишком длинный перечень — отпечатка нет, причина названа",
              long_listing.get("success") and long_listing["sha256"] is None
              and "перечень длиннее" in str(long_listing["manifest"].get("digest_reason")),
              long_listing["manifest"].get("digest_reason"))

        # ── 6. загрузка каталога: ответ == строка БД == отдельный разбор ────────────
        if origin_row(uuid_test):
            delete_external_object(uuid_val=uuid_test, obj_type="external_report")
        fresh = collect(ORIGIN_CATALOG, TEST_CATALOG)
        loaded = load_catalog(TEST_CATALOG)
        check("эталон Test3_Otchet_Null загружен (исход loaded)",
              loaded.get("success") and loaded.get("status") == "loaded",
              loaded.get("error") or loaded.get("status"))
        row = origin_row(uuid_test)
        answer = loaded.get("origin_columns") or {}
        check("ответ загрузчика и строка БД содержат один и тот же провенанс",
              answer.get("origin_kind") == row.get("origin_kind")
              and answer.get("origin_path") == row.get("origin_path")
              and answer.get("origin_sha256") == row.get("origin_sha256")
              and (answer.get("origin_manifest") or {}).get("file_count")
              == (row.get("origin_manifest") or {}).get("file_count"),
              {key: answer.get(key) for key in ("origin_kind", "origin_path", "origin_sha256")})
        check("колонки провенанса легли в строку (вид, путь, отпечаток, метка времени)",
              row["origin_kind"] == ORIGIN_CATALOG
              and row["origin_path"] == os.path.abspath(TEST_CATALOG)
              and row["origin_sha256"] == fresh["sha256"]
              and row["origin_recorded_at"] is not None,
              {key: row.get(key) for key in ("origin_kind", "origin_path", "origin_sha256")})
        card = card_of(loaded)
        check("карточка загрузки печатирует происхождение строки (вид, путь, отпечаток, состав)",
              card_has(card, "Провенанс:") and card_has(card, os.path.abspath(TEST_CATALOG))
              and card_has(card, "Отпечаток (") and card_has(card, "Состав источника:")
              and card_has(card, "Записано:"),
              [line for line in card if "ровенанс" in line or "тпечаток" in line][:3])
        first_id = loaded.get("id")

        # ── 7. манифест в БД = перечень с диска; плоская выборка разрешается ────────
        stored = row["origin_manifest"] or {}
        disk, truncated, reason = listing_of_directory(TEST_CATALOG)
        check("манифест в БД = перечень с диска (пути, sha256, размеры)",
              file_entries(stored) == file_entries({"files": disk}) and bool(disk),
              (len(file_entries(stored)), len(disk), truncated, reason))
        flat = find_external_object(uuid_test, "external_report") or {}
        subset = {key: stored.get(key) for key, _ in provenance.FLAT_MANIFEST_FIELDS
                  if key in stored}
        check("плоская выборка find_external_object разворачивается в ту же структуру",
                bool(subset) and manifest_from_flat(flat) == subset,
                {"flat": manifest_from_flat(flat), "stored": subset})
        check("карточка дубликата получает манифест из строки БД, а не из файлов",
              compare(fresh, flat)["verdict"] == "same", compare(fresh, flat))

        # ── 8. дубликат: тот же источник — вердикт same, запись не меняется ─────────
        dup = load_catalog(TEST_CATALOG)
        dup_row = origin_row(uuid_test)
        check("повторная загрузка того же каталога — исход duplicate, строка не изменена",
              dup.get("success") is False and dup.get("status") == "duplicate"
              and (dup.get("existing") or {}).get("id") == first_id
              and dup_row["id"] == first_id
              and dup_row["origin_sha256"] == fresh["sha256"],
              {key: dup.get(key) for key in ("status", "error")}
              | {"id": dup_row["id"], "was": dup_row["origin_sha256"]})
        dup_card = card_of(dup)
        check("карточка дубликата называет вид и путь источника из строки БД",
              card_has(dup_card, "Провенанс: каталог выгрузки (origin_kind='catalog')")
              and card_has(dup_card, "Источник: " + os.path.abspath(TEST_CATALOG)),
              [line for line in dup_card if "ровенанс" in line or "Источник" in line][:3])
        check("карточка дубликата показывает отпечаток и состав источника из строки БД",
              card_has(dup_card, "Отпечаток (sha256 перечня файлов каталога): " + fresh["sha256"])
              and card_has(dup_card, "Состав источника: файлов "),
              [line for line in dup_card if "тпечаток" in line or "Состав" in line])
        verdict = dup.get("provenance_match") or {}
        check("вердикт посчитан загрузчиком ДО отказа и лежит в ответе отдельным ключом",
              isinstance(dup.get("provenance_match"), dict) and verdict.get("verdict") == "same",
              dup.get("provenance_match"))
        check("тот же источник — карточка говорит «совпадает», а не «различается»",
              card_has(dup_card, "✅ Источник совпадает с записанным")
              and not card_has(dup_card, "НЕ совпадает")
              and not card_has(dup_card, "Сверить источник не удалось"),
              [line for line in dup_card if "овпадает" in line or "Сверить" in line])
        check("вердикт карточки дубликата — same, а не differ (ложного различия нет)",
              compare(fresh, dup.get("existing"))["verdict"] == "same",
              compare(fresh, dup.get("existing")))

        # ── 9. копия того же содержимого в другом пути: вердикт о содержимом, а не о пути
        other = {}
        if not copy_catalog_source(TEST_CATALOG, copy_catalog):
            check("копия эталона для проверки различия источников создана", False, copy_catalog)
        else:
            other = collect(ORIGIN_CATALOG, copy_catalog)
            check("копия даёт тот же отпечаток перечня (пути в перечне относительные)",
                  other["sha256"] == fresh["sha256"],
                  (str(other["manifest"].get("digest_scope")), other["sha256"][:12]))
            dup2 = load_catalog(copy_catalog)
            check("тот же uuid из другого каталога — тоже исход duplicate, запись не изменена",
                  dup2.get("success") is False and dup2.get("status") == "duplicate"
                  and (dup2.get("existing") or {}).get("id") == first_id
                  and origin_row(uuid_test)["origin_path"] == os.path.abspath(TEST_CATALOG),
                  {key: dup2.get(key) for key in ("status", "error")}
                  | {"row_path": origin_row(uuid_test)["origin_path"]})
            check("вердикт описывает содержимое источника, а не путь: копия даёт same",
                  (dup2.get("provenance_match") or {}).get("verdict") == "same"
                  and compare(other, dup2.get("existing"))["verdict"] == "same",
                  dup2.get("provenance_match"))
            dup2_card = card_of(dup2)
            check("путь при этом не прячется: карточка называет путь, записанный в строку",
                  card_has(dup2_card, "Источник: " + os.path.abspath(TEST_CATALOG))
                  and not card_has(dup2_card, "Источник: " + os.path.abspath(copy_catalog)),
                  [line for line in dup2_card if "Источник" in line])

            # ── 10. содержимое копии менялось при том же uuid — differ, причина названа ─
            extra = Path(copy_catalog) / "v31-extra.txt"
            extra.write_text("содержимое выгрузки менялось при том же uuid" + chr(10),
                             encoding="utf-8")
            changed = collect(ORIGIN_CATALOG, copy_catalog)
            check("изменение состава каталога меняет отпечаток перечня",
                  changed["sha256"] != other["sha256"],
                  (other["sha256"][:12], changed["sha256"][:12]))
            dup3 = load_catalog(copy_catalog)
            check("дубликат с изменённым содержимым — вердикт differ, а не same",
                  dup3.get("status") == "duplicate"
                  and (dup3.get("provenance_match") or {}).get("verdict") == "differ",
                  dup3.get("provenance_match"))
            check("причина различия названа прямо: сравниваются отпечатки, а не версия",
                  "отпечатки различаются" in str((dup3.get("provenance_match") or {}).get("reason")),
                  (dup3.get("provenance_match") or {}).get("reason"))
            dup3_card = card_of(dup3)
            check("карточка дубликата называет расхождение и путь, и отпечаток из строки БД",
                  card_has(dup3_card, "⚠️ Источник НЕ совпадает с записанным в строку")
                  and card_has(dup3_card, "Источник: " + os.path.abspath(TEST_CATALOG))
                  and card_has(dup3_card, "Отпечаток (sha256 перечня файлов каталога): "
                                          + fresh["sha256"]),
                  [line for line in dup3_card if "овпадает" in line or "тпечаток" in line][:4])
            check("карточка объясняет, что это тот же случай R5, и предлагает force=True",
                  card_has(dup3_card, "менялось при том же uuid")
                  and card_has(dup3_card, "force=True"),
                  [line for line in dup3_card if "R5" in line or "uuid" in line][:3])


        # ── 10b. force=True: старая строка удалена, провенанс новой — новый источник ─
        forced = load_catalog(copy_catalog, force=True)
        forced_row = origin_row(uuid_test)
        check("force=True даёт исход reloaded и снимает прежнюю запись",
              forced.get("success") and forced.get("status") == "reloaded"
              and (forced.get("replaced") or {}).get("old_id") == first_id
              and forced.get("id") != first_id and forced_row["id"] == forced.get("id"),
              {key: forced.get(key) for key in ("status", "id")}
              | {"replaced": forced.get("replaced"), "row_id": forced_row["id"]})
        check("провенанс новой строки — новый источник (путь копии с изменённым содержимым)",
              forced_row["origin_path"] == os.path.abspath(copy_catalog)
              and forced_row["origin_sha256"] == changed["sha256"],
              {key: forced_row.get(key) for key in ("origin_path", "origin_sha256")})
        check("ответ перезагрузки несёт тот же провенанс, что и строка БД",
              (forced.get("origin_columns") or {}).get("origin_path") == forced_row["origin_path"]
              and (forced.get("origin_columns") or {}).get("origin_sha256") == forced_row["origin_sha256"],
              forced.get("origin_columns"))
        forced_card = card_of(forced)
        check("карточка перезагрузки показывает провенанс новой строки: вид, путь, отпечаток",
              card_has(forced_card, "Провенанс: каталог выгрузки (origin_kind='catalog')")
              and card_has(forced_card, "Источник: " + os.path.abspath(copy_catalog))
              and card_has(forced_card, changed["sha256"]),
              [line for line in forced_card if "ровенанс" in line or "тпечаток" in line][:5])
        # Вердикт считается ДО удаления прежней строки: после delete_external_object
        # сравнивать было бы не с чем, и карточка потеряла бы ответ на вопрос «что изменилось».
        check("вердикт о провенансе прежней строки назван до подтверждения: differ, а не same",
              ((forced.get("replaced") or {}).get("provenance_match") or {}).get("verdict") == "differ",
              forced.get("replaced"))
        check("карточка перезагрузки называет и новый источник, и различие прежнего",
              card_has(forced_card, "Источник НЕ совпадает с записанным в строку")
              and card_has(forced_card, "отпечатки различаются"),
              [line for line in forced_card if "овпадает" in line][:3])

        # ── 11. провенанс не записан — вердикт unknown, а не differ и не same ───────
        q("UPDATE external_report SET origin_kind = NULL, origin_path = NULL, "
          "origin_sha256 = NULL, origin_recorded_at = NULL, origin_manifest = NULL "
          "WHERE uuid = %(u)s::uuid", {"u": uuid_test})
        blank = origin_row(uuid_test)
        check("строка без колонок источника — легальное состояние (снять провенанс можно)",
              all(blank.get(key) is None for key in PROVENANCE_COLUMNS), blank)
        check("state_of строки без провенанса — not_recorded",
              state_of(blank) == STATE_NOT_RECORDED, state_of(blank))
        check("сравнение с пустым провенансом — unknown: ни «совпадает», ни «различается»",
              compare(fresh, blank)["verdict"] == "unknown"
              and "в строке БД провенанс не записан" in compare(fresh, blank)["reason"],
              compare(fresh, blank))
        dup_blank = load_catalog(TEST_CATALOG)
        blank_card = card_of(dup_blank)
        check("карточка дубликата без провенанса называет состояние прямо: «НЕ записан»",
              dup_blank.get("status") == "duplicate"
              and card_has(blank_card, "Провенанс: НЕ записан")
              and card_has(blank_card, "Сверить источник не удалось"),
              [line for line in blank_card if "ровенанс" in line or "Сверить" in line])
        check("отсутствие провенанса не выдаётся ни за совпадение, ни за различие",
              not card_has(blank_card, "Источник совпадает с записанным")
              and not card_has(blank_card, "Источник НЕ совпадает с записанным в строку"),
              [line for line in blank_card if "овпадает" in line])
        check("карточка называет действие: как записать провенанс и чем это безопасно",
              card_has(blank_card, "Как записать:")
              and card_has(blank_card, "пишется при каждой загрузке заново"),
              [line for line in blank_card if "Как записать" in line or "заново" in line])

        # ── 12. двоичный файл: провенанс = сам файл, а не каталог разбора ibcmd ─────
        erf_file = BINARY_REFERENCE
        binary_id, binary_loaded = None, False
        if not os.path.isfile(erf_file):
            skip("провенанс двоичного файла указывает на сам .erf", f"нет эталона: {erf_file}")
        elif uuids_in_binary(erf_file) != {uuid_test.lower()}:
            skip("двоичный эталон проходит по тестовой строке, а не по строке оператора",
                 f"uuid в файле {sorted(uuids_in_binary(erf_file))} != тестовый {uuid_test}")
        else:
            # Провенанс строки снят группой 11. Сначала восстанавливаем его загрузкой каталога:
            # в отличие от configuration_id (узел V20, force=True переносит) провенанс описывает
            # ТЕКУЩИЙ вызов загрузки и пишется заново — это отдельное свойство модели.
            restored = load_catalog(TEST_CATALOG, force=True)
            restored_row = origin_row(uuid_test)
            check("провенанс пишется при каждой загрузке: force=True восстановил колонки источника",
                  restored.get("success") and restored.get("status") == "reloaded"
                  and restored_row["origin_sha256"] == fresh["sha256"],
                  {key: restored.get(key) for key in ("status", "error")})
            # Дальше — двоичный вход того же объекта. Смысл узла V31 здесь ровно в одном:
            # источником записывается сам .erf, а не каталог разбора, который ibcmd собрал
            # и снял после успеха. Отпечаток считается по байтам файла, поэтому два разбора
            # одного файла в разные каталоги дают одно и то же число.
            file_digest = sha256_of_file(erf_file)[0]
            again = collect(ORIGIN_BINARY_FILE, erf_file)
            check("отпечаток файла детерминирован: повторный разбор даёт то же число",
                  again.get("success") and again.get("sha256") == file_digest,
                  (str(again.get("sha256"))[:16], str(file_digest)[:16]))
            conv_dup = convert_and_load(erf_file)
            check("тот же uuid из двоичного файла — исход duplicate, строка не изменена",
                  conv_dup.get("status") == "duplicate"
                  and (conv_dup.get("existing") or {}).get("id") == restored_row["id"]
                  and origin_row(uuid_test)["origin_sha256"] == fresh["sha256"],
                  {key: conv_dup.get(key) for key in ("status", "error")})
            v_kind = conv_dup.get("provenance_match") or {}
            check("каталог в строке против файла на входе — differ, причина названа про вид",
                  v_kind.get("verdict") == "differ"
                  and "вид источника другой" in str(v_kind.get("reason")), v_kind)
            conv = convert_and_load(erf_file, force=True)
            binary_id = conv.get("id")
            binary_loaded = bool(binary_id)
            if not binary_id:
                skip("провенанс двоичного файла указывает на сам .erf",
                     f"разбор не выполнен: status={conv.get('status')} error={conv.get('error')}")
            else:
                brow = origin_row(uuid_test) or {}
                check("провенанс двоичного файла — вид binary_file, путь = сам файл",
                      brow.get("origin_kind") == ORIGIN_BINARY_FILE
                      and brow.get("origin_path") == os.path.abspath(erf_file),
                      {key: brow.get(key) for key in ("origin_kind", "origin_path")})
                check("отпечаток = sha256 самого файла (совпадает с отдельным разбором)",
                      brow.get("origin_sha256") == file_digest
                      == provenance.sha256_of_file(erf_file)[0],
                      {"stored": brow.get("origin_sha256"), "recount": file_digest})
                bmanifest = brow.get("origin_manifest") or {}
                check("манифест описывает один файл (имя, размер, отпечаток), а не каталог",
                      bmanifest.get("file_count") == 1 and bmanifest.get("digest_scope") == "file"
                      and bmanifest.get("root") == os.path.abspath(erf_file)
                      and file_entries(bmanifest) == [(
                          os.path.basename(erf_file), file_digest, os.path.getsize(erf_file))],
                      {key: bmanifest.get(key)
                       for key in ("file_count", "digest_scope", "root", "total_bytes")})
                # Каталог разбора — рабочая директория ibcmd, и после успешной загрузки он снят
                # (узел V25). Именно поэтому источником обязан быть записан сам файл: ссылка на
                # каталог разбора вела бы в несуществующую директорию.
                conv_info = conv.get("conversion") or {}
                layout_dir = os.path.dirname(str(conv_info.get("root_xml") or ""))
                check("провенанс не указывает на каталог разбора ibcmd: источник — файл",
                      bool(layout_dir) and conv_info.get("layout_removed") is True
                      and brow.get("origin_path") == os.path.abspath(erf_file)
                      and brow.get("origin_path") != layout_dir,
                      {"origin_path": brow.get("origin_path"), "layout_dir": layout_dir,
                       "layout_removed": conv_info.get("layout_removed")})
                check("отпечаток файла отличается от отпечатка каталога той же выгрузки",
                      file_digest != fresh["sha256"],
                      (str(file_digest)[:16], str(fresh["sha256"])[:16]))
                check("карточка перезагрузки называет источник — файл, а не каталог разбора",
                      card_has(card_of(conv), "двоичный файл внешнего объекта")
                      and card_has(card_of(conv), os.path.abspath(erf_file))
                      and not card_has(card_of(conv), layout_dir),
                      [line for line in card_of(conv)
                       if "ровенанс" in line or "Источник" in line][:4])

        # ── 13. сбой провенанса: объект загружается, колонки NULL, причина названа ───
        if origin_row(uuid_test):
            delete_external_object(uuid_val=uuid_test, obj_type="external_report")
        real_collect = external_report_loader.collect_provenance
        external_report_loader.collect_provenance = lambda kind, path: {
            "success": False, "reason": "источник недоступен: каталог снят с диска",
            "sha256": None, "manifest": {}}
        try:
            broken = load_catalog(TEST_CATALOG)
        finally:
            external_report_loader.collect_provenance = real_collect
        broken_row = origin_row(uuid_test)
        check("при сбое провенанса загрузка не отменяется — объект в БД есть",
              broken.get("success") and broken.get("status") == "loaded"
              and broken_row is not None,
              {key: broken.get(key) for key in ("status", "error")})
        check("колонки провенанса при сбое остаются NULL — ложного значения нет",
              bool(broken_row) and all(broken_row.get(key) is None for key in PROVENANCE_COLUMNS),
              broken_row)
        check("причина сбоя названа прямо: предупреждение загрузчика с видом и путём источника",
              any("Провенанс НЕ записан" in str(w)
                  and "источник недоступен: каталог снят с диска" in str(w)
                  and os.path.abspath(TEST_CATALOG) in str(w)
                  for w in broken.get("warnings") or []),
              broken.get("warnings"))
        # Карточка загрузки не рисует блок провенанса, которого нет (форматтер печатает
        # describe_lines только для записанного состояния) — но предупреждение в ней видно.
        broken_card = card_of(broken)
        check("карточка загрузки при сбое не выдумывает провенанс, но называет причину",
              not card_has(broken_card, "Провенанс:")
              and not card_has(broken_card, "Отпечаток (")
              and card_has(broken_card, "Провенанс НЕ записан"),
              [line for line in broken_card if "ровенанс" in line or "тпечаток" in line])
        check("состояние строки после сбоя — not_recorded, сравнение — unknown",
              bool(broken_row) and state_of(broken_row) == STATE_NOT_RECORDED
              and compare(fresh, broken_row)["verdict"] == "unknown",
              state_of(broken_row) if broken_row else None)
        check("сборщик возвращён на место: мок не остаётся в модуле загрузчика",
              external_report_loader.collect_provenance is real_collect)

        # ── 14. уборка за собой и неизменность того, чего узел не касался ───────────
        if origin_row(uuid_test):
            delete_external_object(uuid_val=uuid_test, obj_type="external_report")
        if binary_id and binary_loaded:
            delete_external_object(obj_id=binary_id, obj_type="external_report")
        left = q("SELECT count(*) AS n FROM external_report WHERE uuid = %(u)s::uuid",
                 {"u": uuid_test})
        check("тестовый объект убран: валидатор не оставляет мусора", left[0]["n"] == 0, left[0])
        left = q("SELECT count(*) AS n FROM external_report "
                 "WHERE (origin_path IS NULL) <> (origin_kind IS NULL)")
        check("нарушений пары origin_kind / origin_path в БД нет", left[0]["n"] == 0, left[0])
        left = q("SELECT count(*) AS n FROM external_report "
                 "WHERE origin_sha256 IS NOT NULL AND origin_kind IS NULL")
        check("отпечатка без вида провенанса в БД нет", left[0]["n"] == 0, left[0])
        after = db_snapshot(exclude_uuid=uuid_test)
        check("строки оператора не изменились: эталоны, привязки, дети, обогащение",
              after == before,
              {"before": len(before), "after": len(after),
               "diff": [row for row in after if row not in before]
                       + [row for row in before if row not in after]})
        # Что осталось в базе — печатается, а не проверяется: наличие эталонной пары относится
        # к состоянию базы (её восстанавливают tools/restore_reference_pair.py после
        # очистительных регрессов), а не к гарантиям этого узла.
        print("строки оператора после прогона: "
              + (", ".join(f"{row['id']}:{row['name']}" for row in after) or "нет"))
    except Exception as exc:
        check("скрипт выполнен без исключения", False, f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    total = len(PASSED) + len(FAILED)
    print("\n" + "=" * 78)
    print(f"ИТОГ: проверок {total}, пройдено {len(PASSED)}, провалено {len(FAILED)}, "
          f"пропущено {SKIPPED}")
    for name in FAILED:
        print("  FAILED: " + name)
    print("=" * 78)
    return 0 if not FAILED else 1


if __name__ == "__main__":
    raise SystemExit(main())








