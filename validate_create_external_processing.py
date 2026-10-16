"""Проверка узла V29 (шаг 1): создать внешний объект с пустым содержимым из XML.

Два режима:

    python validate_create_external_processing.py --fast   # офлайн: структура XML, без ibcmd и БД
    python validate_create_external_processing.py          # полный прогон: ibcmd import + загрузка в БД

Полный режим принимает критерии A1–A8 из docs/PROMPT_2026-10-16_v29_zero_external_processing.md.
Скрипт работает через те же модули, что и MCP (src/ibcmd_bridge.py, src/config_load_router.py),
но не через stdio-транспорт MCP; живые вызовы инструментов — отдельный шаг (см. план узла V29).

Офлайн половина (A1–A5) проверяет автора и маршрут: корневой элемент и пустые составляющие
(A1), идентификаторы и их уникальность (A2), отсутствие `<xr:ContainedObject>` (A3),
побайтовая детерминированность сборки (A4), отклонение идентификатора не-версии 4 (A5) и
маршрутизацию файла внешней
обработки точкой входа. Живая половина (`run_full`) проверяет сам цикл: B1 — ИБ подготовлена
и переиспользуется (её состояние относительно конфигурации печатается как факт прогона);
B2 — автор отдаёт раскладку пары `<Имя>.xml` + `<Имя>/Ext|Forms|Templates/` (так даёт
`config export`, так её читает загрузчик) и детерминирован; B3 — `ibcmd config import`
собирает `.epf`; B4 — файл является контейнером 1С (общая часть заголовка `00 02 00 00`;
байты 0..3 различаются производителем: конфигуратор — `ff ff ff 7f`, `ibcmd import` — длина
полезной нагрузки); B5 — та же
раскладка принимается точкой входа как внешняя обработка; B6–B7 — строка заголовка
совпадает со спецификацией (`object_kind='external_processing'`, привязка к конфигурации
не заявлена), детей ноль; B8 — обогащение: self-цель `ExternalProcessing`, сниппетов нет
(нет содержимого); B9 — обратный `config export` собранного `.epf` сохраняет uuid, имя и
вид и показывает, какие элементы добавляет платформа; B10 — уборка: объект и его
обогащение сняты, сирот нет, число строк в `external_report` вернулось к исходному.

Скрипт убирает за собой: снятый объект, каталог разбора `_ibcmd_work/v29_create`, строки
объекта во всех таблицах. Эталонная пара (Test1_Otchet / Test2_Otchet) не трогается:
список имён и число строк в external_report сверяются до и после.
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
from uuid import uuid4

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

import external_object_author as author  # noqa: E402
import config_load_router as router  # noqa: E402
from config_load_router import load_catalog  # noqa: E402
from enrichment_generator import generate_enrichment  # noqa: E402
from external_db import connect  # noqa: E402
from external_object_author import normalize_spec, write_layout  # noqa: E402
from external_report_loader import delete_external_object  # noqa: E402
from ibcmd_bridge import (configuration_state, ensure_infobase, export_to_layout,  # noqa: E402
                         find_ibcmd, import_from_layout, load_configuration)

WORK_DIR = os.path.join(ROOT, "_ibcmd_work", "v29_create")
LAYOUT_DIR = os.path.join(WORK_DIR, "layout")
PROBE_DIR = os.path.join(WORK_DIR, "probes")
# Каталог обратного разбора (B9): его даёт `ibcmd config export` по собранному нами .epf.
RT_DIR = os.path.join(WORK_DIR, "roundtrip")
REFERENCE = r"C:\1C_LLM\LoadDoc\Test0_ processing_Null"
# Рабочая ИБ по умолчанию та же, что у моста (_ibcmd_work/ib): пустая, создаётся один раз
# и переиспользуется. ИБ с конфигурацией БП3 (_ibcmd_work/ib_bp3) — отдельный прогон
# параметром --db (проба P4: нужен ли для нулевого объекта загруженный заголовок).
IBCMD_DB = os.path.join(ROOT, "_ibcmd_work", "ib")

# Имя объекта валидатора: латиница — чтобы путь каталога разбора и вывод psql не зависели
# от кодовой консоли. Правило имени держит генератор (NAME_RE), импорт принимает и другое.
V29_NAME = "V29ZeroEPF"
# Канонический UUID версии 1: проба A5 проверяет, что генератор различает «не UUID» и
# «UUID другой версии». Значение взято не из выгрузки — это просто корректная строка v1.
CANONICAL_V1_UUID = "02d1629f-0746-11d6-92ef-0050ba30e747"

results = []


def check(ok, label, detail=""):
    results.append((bool(ok), label, detail))
    print(("  [ok]   " if ok else "  [FAIL] ") + label + (f" :: {detail}" if detail else ""))
    return bool(ok)


def section(title):
    print("\n" + title)


def _rows(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def _count(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchone()[0]


def db_counts(conn):
    tables = ("external_report", "attributes", "tabular_sections", "forms", "form_ext",
              "templates", "bsl_modules", "config_aliases", "config_snippets",
              "config_snippet_dependencies", "config_cross_references")
    out = {}
    with conn.cursor() as cur:
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            out[table] = cur.fetchone()[0]
    return out


# ---------------------------------------------------------------------------
# офлайн: что генерирует автор (без ibcmd, без БД)
# ---------------------------------------------------------------------------

def root_open_line(text):
    """Строка корневого элемента <MetaDataObject ...> — из неё читается версия формата."""
    for line in text.splitlines():
        if line.startswith("<MetaDataObject"):
            return line
    return ""


def ns_map(root_line):
    """Пространства имён корневого элемента: {'': url, 'xr': url, ...} — сравнение наборов."""
    out = {}
    for match in re.finditer(r'xmlns(?::([A-Za-z0-9_\-]+))?="([^"]+)"', root_line):
        out[match.group(1) or ""] = match.group(2)
    return out


def reference_root_xml():
    """Корневой XML эталонной нулевой обработки: он один в каталоге и зовётся не по имени каталога."""
    for name in sorted(os.listdir(REFERENCE)):
        if name.endswith(".xml"):
            return os.path.join(REFERENCE, name)
    return None


def used_prefixes(text):
    """Префиксы, реально использованные в именах элементов и атрибутов (xml/xmlns не считаем)."""
    used = set(re.findall(r"<\s*([A-Za-z][A-Za-z0-9_.\-]*):", text))
    used |= set(re.findall(r"[\s\"']([A-Za-z][A-Za-z0-9_.\-]*):[A-Za-z][A-Za-z0-9_.\-]*=", text))
    return {p for p in used if p not in ("xml", "xmlns")}


def declared_prefixes(text):
    """Префиксы, объявленные через xmlns:? — по всему документу, а не только в корне."""
    return {m.group(1) for m in re.finditer(r"xmlns:([A-Za-z0-9_\-]+)=", text)} - {""}


def check_xml_structure(xml_text, ids):
    """A1 (структура XML), A2 (без ContainedObject), A6 (detected_kind), A7 (детерминированность)."""
    section("A1/A2/A6/A7 — офлайн: структура сгенерированного XML")

    header = root_open_line(xml_text)
    check(xml_text.startswith('<?xml version="1.0" encoding="UTF-8"?>'),
          "A1: декларация XML (UTF-8) первой строкой", xml_text[:60])
    check(bool(header) and 'version="2.20"' in header,
          "A1: корень MetaDataObject с версией формата 2.20", header[:120])
    # Набор пространств имён сравнивается с эталонной выгрузкой, а не с ожиданием из головы:
    # автор обязан отдавать тот же заголовок, что даёт `config export` (иначе импорт читает
    # префиксы иначе, и проверка «набор совпадает» была бы самообманом).
    ref_path = reference_root_xml()
    ref_header = root_open_line(read_root_xml(ref_path)) if ref_path else ""
    mine_ns, ref_ns = ns_map(header), ns_map(ref_header)
    check(bool(mine_ns) and bool(ref_ns) and mine_ns == ref_ns,
          "A1: набор пространств имён корня совпадает с эталоном выгрузки",
          f"автор: {len(mine_ns)} объявлений; эталон ({ref_path}): {len(ref_ns)}; "
          f"расхождение: {sorted(set(mine_ns.items()) ^ set(ref_ns.items()))[:4]}")
    check('xmlns="http://v8.1c.ru/8.3/MDClasses"' in header,
          "A1: default-пространство MDClasses объявлено в корне", header[:160])
    # Литерал URI xr угадывать нельзя (в выгрузке это http://v8.1c.ru/8.3/xcf/readable):
    # проверяется отношение — префикс используется и он объявлен. Несовпадение URI с
    # эталоном уже ловит сравнение наборов пространств имён выше.
    used, declared = used_prefixes(xml_text), declared_prefixes(xml_text)
    check(used <= declared and bool(used),
          "A1: каждый использованный префикс объявлен в документе",
          f"используются: {sorted(used)}; объявления: {sorted(declared)}")
    check("xr" in used and "xr" in declared,
          "A1: префикс xr (InternalInfo/GeneratedType) использован и объявлен",
          f"used={sorted(used)} declared={sorted(declared)}")
    check(
        f'<ExternalDataProcessor uuid="{ids["uuid"]}">' in xml_text,
        "A1: uuid объекта в атрибуте корневого элемента",
    )
    order = re.search(
        r"<InternalInfo>.*</InternalInfo>\s*<Properties>.*</Properties>\s*<ChildObjects/>",
        xml_text,
        re.S,
    )
    check(bool(order), "A1: порядок InternalInfo -> Properties -> ChildObjects")
    check(
        f'<xr:GeneratedType name="ExternalDataProcessorObject.{ids["name"]}" '
        f'category="Object">' in xml_text,
        "A1: GeneratedType category=Object + имя ExternalDataProcessorObject.<Имя>",
    )
    check("<xr:ContainedObject" not in xml_text and "<xr:ClassId" not in xml_text,
          "A2: ContainedObject/ClassId не пишутся (доставляет платформа)")
    check(
        re.search(r"<ChildObjects>\s*<Form>", xml_text) is None
        and "<ChildObjects/>" in xml_text,
        "A1: пустой объект — закрытый тег <ChildObjects/>",
    )
    check("<Name>" + ids["name"] in xml_text, "A1: Name объекта на месте")

    # A6 (офлайн-часть): эталонный каталог нулевой обработки описан тем же корневым
    # элементом, который генерирует автор. Если роутер определяет его как
    # external_processing, наш XML попадёт в тот же загрузчик. Свой каталог разбора
    # проверяется в полном прогоне (run_full), потому что офлайн его ещё нет.
    detected = router.detect_load_variant(REFERENCE)
    check(bool(detected.get("success")) and detected.get("variant") == "external_processing",
          "A6: эталон нулевой обработки определяется как external_processing",
          f"variant={detected.get('variant')} title={detected.get('title')} "
          f"reason={detected.get('error') or ''}")

    # A7: два свойства генератора. Первое — детерминированность: та же спецификация даёт
    # тот же текст (иначе diff round-trip и повторная загрузка сравнивали бы разное).
    # Второе — состав файла: TypeId/ValueId, синоним и комментарий в файл входят (иначе
    # карточка БД нечем заполнять), поэтому другие идентификаторы обязаны дать ДРУГОЙ файл,
    # а uuid объекта при этом остаётся заявленным.
    again = author.build_external_processing_xml(dict(ids))
    check(again == xml_text, "A7: детерминированность — та же спецификация даёт тот же XML",
          f"длины: {len(xml_text)} против {len(again)}")
    check(f"<xr:TypeId>{ids['type_id']}</xr:TypeId>" in xml_text
          and f"<xr:ValueId>{ids['value_id']}</xr:ValueId>" in xml_text,
          "A7: TypeId/ValueId записаны в InternalInfo своими v4")
    syn_text = ids["synonym"].get("ru", "") if isinstance(ids["synonym"], dict) else str(ids["synonym"])
    check(bool(syn_text) and syn_text in xml_text and str(ids["comment"]) in xml_text,
          "A7: синоним и комментарий записаны в Properties",
          f"синоним в файле: {bool(syn_text and syn_text in xml_text)}; "
          f"комментарий в файле: {str(ids['comment']) in xml_text}")
    changed = author.build_external_processing_xml(
        {**ids, "type_id": uuid4(), "value_id": uuid4()}
    )
    check(changed != xml_text
          and f'<ExternalDataProcessor uuid="{ids["uuid"]}">' in changed
          and f"<xr:TypeId>{ids['type_id']}</xr:TypeId>" not in changed,
          "A7: другие TypeId/ValueId дают другой файл, uuid объекта остаётся заявленным",
          f"совпало={changed == xml_text}")
    check(author.normalize_spec(dict(ids)) == ids,
          "A7: normalize_spec идемпотентна (повторная нормализация ничего не меняет)")

    # негативные случаи генератора: имя и идентификаторы
    for bad_name, why in (("", "пустое"), ("9Внешняя", "начинается с цифры"),
                          ("Внешняя Обработка", "содержит пробел")):
        try:
            author.build_external_processing_xml({"name": bad_name})
            check(False, f"A1: имя отклонено ({why})", "исключения не было")
        except author.AuthorError as exc:
            check(True, f"A1: имя отклонено ({why})", str(exc)[:120])

    # A5 (позитив): генератор выдал три РАЗНЫХ канонических v4
    for key in ("uuid", "type_id", "value_id"):
        value = str(ids[key])
        check(bool(re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-"
                            r"[0-9a-f]{12}$", value)),
              f"A5: {key} — канонический UUID v4", value)
    check(len({str(ids[k]) for k in ("uuid", "type_id", "value_id")}) == 3,
          "A5: uuid, TypeId, ValueId — три разных значения")

    # A5 (негатив): генератор различает «UUID другой версии» и «это не UUID»
    try:
        author.build_external_processing_xml({"name": "Тест", "uuid": CANONICAL_V1_UUID})
        check(False, "A5: канонический UUID v1 отклонён", "исключения не было")
    except author.AuthorError as exc:
        msg = str(exc)
        check("не версии 4" in msg, "A5: канонический UUID v1 отклонён", msg[:160])
    try:
        author.build_external_processing_xml({"name": "Тест", "uuid": "не uuid"})
        check(False, "A5: не-UUID идентификатор отклонён", "исключения не было")
    except author.AuthorError as exc:
        check("не является каноническим" in str(exc),
              "A5: не-UUID идентификатор отклонён", str(exc)[:160])


# ---------------------------------------------------------------------------
# живая половина: автор -> ibcmd import -> точка входа загрузки -> БД -> обогащение
# ---------------------------------------------------------------------------

# Контейнер 1С: байты 0..3 различаются производителем (конфигуратор — `ff ff ff 7f`;
# `ibcmd import` — LittleEndian-длина полезной нагрузки, замер 16.10.2026 по шести .epf:
# 460, 464, 484, 548, 540, 611 — разница ровно 67 байт, длина служебной части), байты
# 4..7 — общие для обоих производителей (`00 02 00 00`). Признаком «это файл внешнего
# объекта, а не текст» служит общая часть заголовка, а не расширение и не магия конфигуратора.
CONTAINER_INVARIANT = bytes.fromhex("00020000")
CHILD_TABLES = ("attributes", "tabular_sections", "forms", "form_ext", "templates",
                "bsl_modules")
ENRICH_TABLES = ("config_aliases", "config_snippets")
# Имена элементов без префикса пространства имён: сопоставление авторского XML с разбором
# платформы показывает, какие узлы добавляет ibcmd (B9).
TAG_RE = re.compile(r"<(?:[A-Za-z0-9_.\-]+:)?([A-Za-z0-9_.\-]+)")
SYNONYM_TEXT = "Нулевая внешняя обработка V29"
COMMENT_TEXT = "Создана автором V29 (шаг 1): содержимого нет, идентификаторы новые v4"


def read_root_xml(path):
    """Прочитать XML разбора: автор пишет UTF-8 с BOM, платформа отдаёт и UTF-8, и cp1251."""
    with open(path, "rb") as handle:
        raw = handle.read()
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def q(sql, params=()):
    with connect() as conn:
        return _rows(conn, sql, params)


def q1(sql, params=()):
    rows = q(sql, params)
    return rows[0][0] if rows else None


def failure(res):
    """Причина отказа — текст инструмента, а не догадка (L3)."""
    parts = [str(part) for part in (res.get("error"), res.get("hint"), res.get("reason")) if part]
    return " :: ".join(parts) or "причины нет"


def step_infobase(db_path, cf):
    section("B1 — контекст ibcmd: информационная база")
    prepared = ensure_infobase(db_path)
    state = configuration_state(db_path)
    ready = check(bool(prepared.get("success")),
                  "B1: ИБ подготовлена (создаётся один раз и переиспользуется)",
                  f"db={db_path}; создана_сейчас={prepared.get('created')}; "
                  f"секунд={prepared.get('seconds', 0.0)}; метка конфигурации={state}"
                  if prepared.get("success") else failure(prepared))
    if not ready:
        return False
    if cf:
        loaded = load_configuration(db_path, cf)
        check(bool(loaded.get("success")), "B1b: конфигурация загружена в ИБ (--cf)",
              f"секунд={loaded.get('seconds')}" if loaded.get("success") else failure(loaded))
    else:
        print("  [info] --cf не задан: конфигурацию в этом прогоне не загружали; метка ИБ = "
              f"{state}. Проба P4 (нужен ли нулевому объекту загруженный заголовок) отвечает "
              "шагом B3 — он печатает фактический исход импорта.")
    return True


def step_author(spec):
    section("B2 — автор: раскладка разбора и детерминированность записи")
    if os.path.isdir(LAYOUT_DIR):
        shutil.rmtree(LAYOUT_DIR)
    paths = write_layout(spec, LAYOUT_DIR)
    nested = (os.path.isfile(paths["root_xml"])
              and paths["content_dir"] == os.path.join(LAYOUT_DIR, spec["name"])
              and all(os.path.isdir(paths[key])
                      for key in ("ext_dir", "forms_dir", "templates_dir")))
    check(nested, "B2a: раскладка = `<Имя>.xml` + каталог `<Имя>/Ext|Forms|Templates`",
          f"root_xml={paths['root_xml']}\n         содержимое: {paths['content_dir']}")
    again = write_layout(spec, PROBE_DIR)
    same = read_root_xml(again["root_xml"]) == read_root_xml(paths["root_xml"])
    check(same, "B2b: детерминированность и при записи в каталог (байт-в-байт)",
          f"первый={paths['root_xml']}\n         второй={again['root_xml']}")
    shutil.rmtree(PROBE_DIR, ignore_errors=True)
    return paths


def step_import(paths, spec, db_path):
    section("B3/B4 — ibcmd import: платформа собирает .epf")
    res = import_from_layout(paths["root_xml"],
                             os.path.join(LAYOUT_DIR, f"{spec['name']}.epf"), db_path=db_path)
    accepted = check(bool(res.get("success")),
                     "B3: `ibcmd config import` принял XML нулевой обработки",
                     f"секунд={res.get('seconds')}; rc={res.get('rc')}"
                     if res.get("success") else failure(res))
    if not accepted:
        return None
    with open(res["binary"], "rb") as handle:
        head = handle.read(8)
    # Проверка по общей части заголовка (байты 4..7 = `00 02 00 00`), а не по магии
    # конфигуратора: файл собран `ibcmd import`, а не конфигуратором — байты 0..3 у него
    # означают длину полезной нагрузки (замер выше). Инвариант обязателен для обоих.
    check(head[4:8] == CONTAINER_INVARIANT,
          "B4: собранный файл — контейнер 1С (общая часть заголовка 00 02 00 00)",
          f"байт={os.path.getsize(res['binary'])}; заголовок={head.hex()}")
    print(f"  [info] заголовок: байты 0..3 = {head[:4].hex()} (у ibcmd — длина полезной "
          f"нагрузки), байты 4..7 = {head[4:8].hex()} — общая часть с конфигуратором.")
    return res["binary"]


def step_load(spec):
    section("B5 — точка входа загрузки принимает созданный разбор")
    started = time.time()
    res = load_catalog(LAYOUT_DIR, force=True)
    seconds = round(time.time() - started, 2)
    status = res.get("status")
    check(status in ("loaded", "reloaded"), "B5: load_catalog загрузил каталог (не отказал)",
          f"status={status}; секунд={seconds}; uuid={res.get('uuid')}"
          if status in ("loaded", "reloaded") else f"status={status} :: {failure(res)}")
    check(res.get("variant") == "external_processing",
          "B5b: вариант определён как внешняя обработка (R1 по файлам корневого каталога)",
          f"variant={res.get('variant')}; title={res.get('variant_title')}")
    for warn in res.get("warnings") or []:
        print(f"  [warn] {warn}")
    return res


def step_db(spec):
    section("B6/B7 — состояние объекта в БД")
    rows = q("SELECT id, name, object_kind, synonym ->> 'ru', comment, configuration_id, "
             "containedobject_classid, generatedtype_name, generatedtype_category "
             "FROM external_report WHERE uuid = %s", (spec["uuid"],))
    if not check(bool(rows), "B6: строка заголовка external_report создана по uuid автора",
                 f"uuid={spec['uuid']}"):
        return None
    obj_id, name, kind, synonym, comment, cfg_id, class_id, gen_name, gen_cat = rows[0]
    check(name == spec["name"], "B6a: имя совпадает со спецификацией", f"БД={name!r}")
    check(kind == "external_processing",
          "B6b: object_kind = external_processing (вид заявляет писатель, V22)", f"БД={kind!r}")
    check(synonym == spec["synonym"]["ru"], "B6c: синоним сохранён (jsonb ->> 'ru')",
          f"БД={synonym!r}")
    check(comment == spec["comment"], "B6d: комментарий сохранён", f"БД={comment!r}")
    check(cfg_id is None,
          "B6e: привязка к конфигурации не заявлена (NULL ≠ «универсальный», V20.1)",
          f"configuration_id={cfg_id}")
    check(gen_name == f"ExternalDataProcessorObject.{spec['name']}" and gen_cat == "Object",
          "B6f: генерируемый тип прочитан из InternalInfo автора",
          f"БД name={gen_name!r} category={gen_cat!r}")
    # Автор блок <xr:ContainedObject> не пишет вовсе (замер v15_no_containedobject), поэто-
    # му ClassId в строке БД отсутствует — это следствие раскладки автора, а не дефект: вид
    # строки задаёт писатель, а не ClassId. Куда блок девляет платформа — отвечает B9d.
    check(not class_id, "B6g: containedobject_classid пуст (автор блок не пишет)",
          f"БД={class_id!r}; ожидание: пустое; доставляет платформа (B9d)")
    sql = "SELECT " + ", ".join(
        "(SELECT COUNT(*) FROM %s WHERE parent_uuid = %%s)" % table for table in CHILD_TABLES)
    counts = dict(zip(CHILD_TABLES, q(sql, (spec["uuid"],) * len(CHILD_TABLES))[0]))
    check(all(value == 0 for value in counts.values()),
          "B7: содержимого нет — детей во всех дочерних таблицах ноль",
          json.dumps(counts, ensure_ascii=False))
    return obj_id


def step_enrichment(spec):
    section("B8 — обогащение объекта без содержимого")
    gen = generate_enrichment(uuid=spec["uuid"])
    check(bool(gen.get("success")), "B8a: генерация обогащения прошла",
          json.dumps({key: value for key, value in gen.items() if isinstance(value, int)},
                     ensure_ascii=False) if gen.get("success") else failure(gen))
    for warn in gen.get("warnings") or []:
        print(f"  [warn] {warn}")
    by_target = dict(q("SELECT target_type, COUNT(*) FROM config_aliases WHERE parent_uuid = %s "
                       "GROUP BY target_type", (spec["uuid"],)))
    check(sum(by_target.values()) > 0, "B8b: алиасы объекта созданы (имя, синоним, комментарий)",
          json.dumps(by_target, ensure_ascii=False))
    check(by_target.get("ExternalProcessing", 0) > 0,
          "B8c: self-цель обогащения — ExternalProcessing (инвариант V22)",
          json.dumps(by_target, ensure_ascii=False))
    check("ExternalReport" not in by_target, "B8d: целей ExternalReport у обработки нет",
          json.dumps(by_target, ensure_ascii=False))
    snippets = q1("SELECT COUNT(*) FROM config_snippets WHERE parent_uuid = %s", (spec["uuid"],))
    check(snippets == 0, "B8e: сниппетов нет — модулей, форм и макетов у объекта нет",
          f"snippets={snippets}")


def step_round_trip(epf, spec, db_path, generated_xml):
    section("B9 — обратный разбор собранного .epf: что добавляет платформа")
    rt = export_to_layout(epf, os.path.join(RT_DIR, spec["name"]), db_path=db_path)
    if not check(bool(rt.get("success")), "B9a: собранный .epf разобран обратно мостом",
                 f"секунд={rt.get('seconds')}; файлов содержимого={rt.get('content_files')}"
                 if rt.get("success") else failure(rt)):
        return
    text = read_root_xml(rt["root_xml"])
    check('uuid="%s"' % spec["uuid"] in text, "B9b: uuid автора вернулся из платформы",
          f"root_xml={rt['root_xml']}")
    check(bool(re.search(r"<[\w:.-]*Name>\s*%s\s*</" % re.escape(spec["name"]), text)),
          "B9c: имя объекта сохранено платформой", f"разбор: {rt['root_xml']}")
    class_id = author.CLASS_IDS.get("external_processing", "")
    # Тег в разборе — с префиксом (`<xr:ClassId>`), искать подстроку `<ClassId` бессмысленно:
    # имя ищём в любом пространстве имён (тот же принцип, что во всём разборе выгрузки).
    check(bool(re.search(r"<[\w:.-]*ClassId\b", text)) and class_id in text,
          "B9d: платформа доставила ContainedObject/ClassId = константа класса обработки",
          f"ожидаемая константа={class_id}; root_xml={rt['root_xml']}")
    mine = set(TAG_RE.findall(read_root_xml(generated_xml)))
    theirs = set(TAG_RE.findall(text))
    added, removed = sorted(theirs - mine), sorted(mine - theirs)
    print(f"  [info] имён элементов: автор {len(mine)} -> разбор платформы {len(theirs)}")
    print(f"  [info] добавлено платформой: {', '.join(added) if added else 'нет'}")
    print(f"  [info] пропало: {', '.join(removed) if removed else 'нет'}")
    names = rt.get("type_names") or {}
    print(f"  [info] имена типов в разборе: cfg: — {names.get('cfg_type_names')}, "
          f"<v8:TypeId> — {names.get('type_id_elements')} (у объекта без реквизитов своих "
          f"типов нет — это ожидаемо, а не дефект контекста)")
    check(not removed, "B9e: авторские элементы не потеряны (разбор — надмножество)",
          f"пропало: {removed}")


def step_cleanup(spec, baseline, keep):
    section("B10 — уборка за собой")
    if keep:
        print(f"  [warn] --keep: объект uuid={spec['uuid']}, .epf и каталоги разбора оставлены")
        return
    removed = delete_external_object(uuid_val=spec["uuid"], obj_type="external_processing")
    check(bool(removed), "B10a: объект снят контрактной операцией удаления",
          json.dumps(removed, ensure_ascii=False, default=str)[:300])
    check(q("SELECT id FROM external_report WHERE uuid = %s", (spec["uuid"],)) == [],
          "B10b: строка заголовка снята", f"uuid={spec['uuid']}")
    left = {table: q1("SELECT COUNT(*) FROM %s WHERE parent_uuid = %%s" % table, (spec["uuid"],))
            for table in ENRICH_TABLES}
    check(all(value == 0 for value in left.values()),
          "B10c: строки обогащения сняты вместе с объектом", json.dumps(left, ensure_ascii=False))
    orphans = q1("SELECT COUNT(*) FROM config_aliases a WHERE a.parent_uuid IS NOT NULL "
                 "AND NOT EXISTS (SELECT 1 FROM external_report e WHERE e.uuid = a.parent_uuid)")
    check(orphans == 0, "B10d: сирот обогащения по всей БД нет", f"сирот={orphans}")
    with connect() as conn:
        after = db_counts(conn)
    diff = {table: {"до": baseline[table], "после": value}
            for table, value in after.items() if value != baseline.get(table)}
    check(not diff, "B10e: счётчики всех таблиц вернулись к исходным (эталоны не тронуты)",
          json.dumps(diff, ensure_ascii=False)[:400])
    shutil.rmtree(WORK_DIR, ignore_errors=True)


def build_spec():
    """Спецификация нулевой обработки: имя фиксировано, идентификаторы — новые v4 на прогон."""
    return normalize_spec({"name": V29_NAME, "object_kind": "external_processing",
                           "synonym": {"ru": SYNONYM_TEXT}, "comment": COMMENT_TEXT})


def run_full(args, spec):
    ib = find_ibcmd()
    if not check(bool(ib.get("success")), "B0: ibcmd доступен",
                 f"{ib.get('path')} (версия {ib.get('version')})"
                 if ib.get("success") else failure(ib)):
        print("  [info] живая половина требует платформу 8.3; офлайн-половина — режим --fast")
        return summarize()
    print(f"  спецификация: name={spec['name']} uuid={spec['uuid']}")
    with connect() as conn:
        baseline = db_counts(conn)
    print(f"  счётчиков до прогона: external_report={baseline['external_report']}, "
          f"config_aliases={baseline['config_aliases']}")
    if not step_infobase(args.db, args.cf):
        return summarize()
    paths = step_author(spec)
    epf = step_import(paths, spec, args.db)
    step_load(spec)
    step_db(spec)
    step_enrichment(spec)
    if epf:
        step_round_trip(epf, spec, args.db, paths["root_xml"])
    else:
        section("B9 — пропущено: .epf не собран, обратного разбора нет")
    step_cleanup(spec, baseline, args.keep)
    return summarize()


def summarize():
    failed = [label for ok, label, _ in results if not ok]
    print("\n" + "=" * 72)
    print(f"ИТОГ: проверок {len(results)}, провалено {len(failed)}")
    for label in failed:
        print(f"  [FAIL] {label}")
    print("=" * 72)
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(
        description="Узел V29 (шаг 1): создать внешнюю обработку с пустым содержимым из XML")
    parser.add_argument("--fast", action="store_true",
                        help="только офлайн-половина (A1–A5): без ibcmd и без БД")
    parser.add_argument("--db", default=IBCMD_DB,
                        help="каталог файловой ИБ ibcmd (по умолчанию переиспользуемая пустая; "
                             "ИБ с конфигурацией БП3 — _ibcmd_work/ib_bp3)")
    parser.add_argument("--cf", default=None,
                        help="файл .cf для загрузки в ИБ (нужен для cfg:-имён типов)")
    parser.add_argument("--keep", action="store_true",
                        help="не удалять созданный объект и каталоги разбора")
    args = parser.parse_args()

    print("=" * 72)
    print("УЗЕЛ V29 (ШАГ 1): ВНЕШНЯЯ ОБРАБОТКА С ПУСТЫМ СОДЕРЖИМЫМ — АВТОР -> ИМПОРТ -> БД")
    print("=" * 72)

    # Одна спецификация на оба полу-прогона: офлайн проверяет тот же текст, который живая
    # половина отдаёт импорту (иначе A-серия проверяла бы другой объект).
    spec = build_spec()
    xml_text = author.build_external_processing_xml(spec)
    check_xml_structure(xml_text, spec)

    if args.fast:
        print("\n  [info] пропущено (--fast): шаги B1–B10 с реальным импортом ibcmd и БД")
        return summarize()
    return run_full(args, spec)


if __name__ == "__main__":
    sys.exit(main())
