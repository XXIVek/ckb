#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_v33_probe.py — офлайн-проверка узла V33: индекс объектов конфигурации.

Загружает C:\1C_LLM\LoadDoc\BGU2 общей точкой входа `load_catalog` (Configuration.xml ->
вариант configuration -> register_configuration -> ConfigDumpInfo.xml) и сверяет то, что
легло в `configuration_objects`, с контрактом парсера.

Ожидания выводятся из `counts`/`objects` парсера, а не из магических чисел: SQL повторяет
те же инварианты другой реализацией — так проверка не подтверждает сама себя. Колонки —
реальные для схемы узла V33 (`name`, `object_id`, `parent_name`, `depth`, `child_type`,
`config_version`, `uuid`); колонок `parent_id`, `kind`, `source_path`, `configdumpinfo_id`
в схеме нет, иерархия держится на имени (правило D3).

Что проверяется (DDL узла V33 + правила парсера D1–D6):
  1. карточка загрузки называет индекс (index_found/index_source/index_counts) и число
     записанных строк; предупреждения парсера названы в карточке, а не проглочены;
  2. содержимое таблицы = counts: всего записей, корни/некорневые по имени, max_depth,
     разбивка по глубинам и по object_type;
  3. иерархия по `parent_name`: сирот нет, `parent_name IS NULL` ровно у depth = 0,
     глубина ребёнка = глубина родителя + 1, `child_type` заполнен ровно у некорневых;
  4. идентификаторы (D2): `uuid` заполнен ровно у канонических и совпадает с `object_id`;
     составные `<uuid>.<число>` и суффиксные `<uuid>.1c` хранятся в `object_id` текстом;
     база такого идентификатора совпадает с `object_id` родителя, названного именем
     (ожидаемое число считается офлайн по правилу D3, SQL считает независимо); записи,
     где база НЕ равна id родителя, печатаются поимённо и обязаны объясняться одним:
     предопределённые дети корня `Configuration.<Имя>` с одной общей базой (замер BGU2 — 11);
  5. `config_version` заполнен ровно у `counts.config_versions`, шестнадцатеричный и ни
     разу не попадает в `uuid` (D4);
  6. уникальность имени и идентификатора в пределах конфигурации, FK на заголовок;
  7. известные объекты BGU2 присутствуют, их uuid совпадает с uuid элемента метаданных в
     файле вида (якорь слоя `configuration-object-uuid-location`);
  8. force=True снимает строки индекса до удаления заголовка (FK без ON DELETE) и не
     оставляет сирот; delete_configuration снимает индекс целиком; внешние объекты
     эталонной пары не затронуты.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python _v33_probe.py [--keep]     # --keep — не удалять BGU2 после проверки
Код возврата 0 — расхождений нет, 1 — есть.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from config_dump_info_parser import (  # noqa: E402
    find_config_dump_info, id_form, parse_config_dump_info, split_name,
)
from config_load_router import format_load_result, load_catalog  # noqa: E402
from configuration_loader import delete_configuration  # noqa: E402
from external_db import connect  # noqa: E402

BGU2 = r"C:\1C_LLM\LoadDoc\BGU2"
DOTTED_ID_RE = r"^[0-9a-fA-F-]{36}\."
CONFIG_VERSION_RE = r"^[0-9a-fA-F]{40}$"

FAILED = []
TOTAL = 0


def section(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def check(name, ok, detail=""):
    global TOTAL
    TOTAL += 1
    mark = "OK  " if ok else "FAIL"
    print(f"[{mark}] {name}" + (f"\n       -> {detail}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)
    return ok


def sql_rows(query, params=None):
    if params is None:
        args = None
    elif isinstance(params, (list, tuple)):
        args = tuple(params)
    else:
        # Одиночный скалярный параметр (`sql_one(q, DOTTED_ID_RE)`) нельзя пропускать через
        # tuple(): строка разложилась бы по символам, и psycopg2 ответил бы
        # «not all arguments converted during string formatting» (замер 17.10.2026).
        args = (params,)
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(query, args)
        rows = [tuple(r) for r in cur.fetchall()]
        cur.close()
        conn.commit()
        return rows
    finally:
        conn.close()


def sql_one(query, params=None):
    rows = sql_rows(query, params)
    return rows[0][0] if rows else None


def sql_map(query, params=None):
    return {row[0]: row[1] for row in sql_rows(query, params)}


def main():
    keep = "--keep" in sys.argv[1:]

    section("0. ОФЛАЙН-РАЗБОР ИНДЕКСА (без БД) — с чем сравниваем БД")
    index_path = find_config_dump_info(BGU2)
    if not check("ConfigDumpInfo.xml найден в КОРНЕ каталога (правило R1)",
                 bool(index_path), str(index_path)):
        return 1
    started = time.perf_counter()
    offline = parse_config_dump_info(str(index_path))
    parse_seconds = time.perf_counter() - started
    if not check("разбор успешен", offline.get("success"), str(offline.get("error"))[:500]):
        return 1
    oc = offline["counts"]
    print(f"       файл {index_path} ({Path(index_path).stat().st_size} байт), "
          f"разбор {parse_seconds:.1f} с, записей передано {len(offline['objects'])}")
    for key in ("entries_total", "metadata_direct", "metadata_nested", "root_entries",
                "child_entries", "max_depth", "config_versions", "config_versions_missing",
                "config_versions_bad_form", "parent_unresolved"):
        print(f"       {key} = {oc[key]}")
    print(f"       id_forms = {oc['id_forms']}")
    print(f"       id_suffixes = {oc['id_suffixes']}")
    print(f"       depth_hist = {oc['depth_hist']}")
    print(f"       by_xml_parent = {json.dumps(oc['by_xml_parent'], ensure_ascii=False)}")
    print(f"       видов = {len(oc['types'])}, unknown_attributes = {oc['unknown_attributes']}, "
          f"unknown_elements = {oc['unknown_elements']}")
    check("оба уровня <Metadata> посчитаны (правило D1)",
          oc["metadata_direct"] + oc["metadata_nested"] == oc["entries_total"]
          and len(offline["objects"]) == oc["entries_total"],
          str((oc["metadata_direct"], oc["metadata_nested"], oc["entries_total"])))
    check("родитель разрешается по имени у всех некорневых (правило D3)",
          oc["parent_unresolved"] == 0, str(oc["parent_unresolved"]))
    check("счётчик раскладки называет реальных тегов-родителей, не выдуманный атрибут (D6)",
          set(oc["by_xml_parent"]) == {"ConfigVersions", "Metadata"},
          str(sorted(oc["by_xml_parent"])))
    check("глубина и корни считаются по имени согласованно (D3)",
          sum(oc["depth_hist"].values()) == oc["entries_total"]
          and oc["depth_hist"].get(0, 0) == oc["root_entries"]
          and max(oc["depth_hist"]) == oc["max_depth"],
          str((oc["depth_hist"], oc["root_entries"], oc["max_depth"])))

    section("1. ЗАГРУЗКА BGU2 ОБЩЕЙ ТОЧКОЙ ВХОДА (configuration -> индекс состава)")
    ext_before = sql_one("SELECT COUNT(*) FROM external_report")
    started = time.perf_counter()
    res = load_catalog(BGU2)
    load_seconds = time.perf_counter() - started
    print(format_load_result(res)[:3000])
    print(f"       загрузка {load_seconds:.1f} с")
    if not check("загрузка конфигурации пройдена", res.get("status") == "loaded",
                 str(res.get("error") or res)[:600]):
        return 1
    cfg_id = res.get("id")
    check("карточка назвала индекс состава (index_found + путь к ConfigDumpInfo.xml)",
          res.get("index_found") is True and bool(res.get("index_source")),
          str((res.get("index_found"), res.get("index_source")))[:200])
    check("карточка назвала число записанных строк индекса = entries_total",
          res.get("configuration_objects_written") == oc["entries_total"],
          str(res.get("configuration_objects_written")))
    ic = res.get("index_counts") or {}
    mismatches = {key: (oc[key], ic.get(key)) for key in
                  ("entries_total", "root_entries", "child_entries", "max_depth",
                   "config_versions", "config_versions_missing", "parent_unresolved")
                  if oc[key] != ic.get(key)}
    check("index_counts в карточке совпадают с офлайн-разбором", not mismatches, str(mismatches))
    # карточка отдаёт ЧИСЛО видов (len(types)) и сам словарь форм идентификаторов;
    # полная разбивка по object_type сверяется с таблицей независимо в разделе 2,
    # поэтому здесь проверяется только счётчик карточки, а не словарь целиком.
    check("index_types/index_id_forms в карточке совпадают с офлайн-разбором",
          res.get("index_types") == len(oc["types"]) and res.get("index_id_forms") == oc["id_forms"],
          str((res.get("index_types"), len(oc["types"]),
               res.get("index_id_forms") == oc["id_forms"])))
    text = " | ".join(str(item) for item in (res.get("warnings") or []))
    non_uuid = oc["entries_total"] - oc["id_forms"].get("uuid", 0)
    check("предупреждение об отсутствующих configVersion названо агрегатом (D4)",
          "configVersion" in text and str(oc["config_versions_missing"]) in text, text[:400])
    check("предупреждение о неканонических идентификаторах названо агрегатом (D2)",
          "неканонические" in text and str(non_uuid) in text, text[:400])
    check("предупреждение о раскладке индекса названо и опирается на теги (D1, D6)",
          "раскладка индекса" in text and "ConfigVersions" in text, text[:300])
    check("никакого предупреждения об отсутствии индекса нет",
          "ConfigDumpInfo.xml отсутствует" not in text, text[:300])

    section("2. СОДЕРЖИМОЕ ТАБЛИЦЫ ПРОТИВ counts ПАРСЕРА")
    total = sql_one("SELECT COUNT(*) FROM configuration_objects")
    check(f"строк в configuration_objects = {oc['entries_total']}", total == oc["entries_total"],
          str(total))
    cfg_count = sql_one("SELECT COUNT(DISTINCT configuration_id) FROM configuration_objects")
    check("строки относятся ровно к одному заголовку конфигурации", cfg_count == 1, str(cfg_count))
    roots = sql_one("SELECT COUNT(*) FROM configuration_objects WHERE parent_name IS NULL")
    kids = sql_one("SELECT COUNT(*) FROM configuration_objects WHERE parent_name IS NOT NULL")
    check(f"корней по имени = {oc['root_entries']}, некорневых = {oc['child_entries']}",
          roots == oc["root_entries"] and kids == oc["child_entries"], str((roots, kids)))
    db_depth = {int(key): value for key, value in
                sql_map("SELECT depth, COUNT(*) FROM configuration_objects GROUP BY depth").items()}
    check("разбивка по глубинам совпадает с depth_hist парсера",
          db_depth == {int(k): v for k, v in oc["depth_hist"].items()},
          str((db_depth, oc["depth_hist"])))
    db_max = sql_one("SELECT MAX(depth) FROM configuration_objects")
    check("max_depth совпадает с парсером", db_max == oc["max_depth"], str((db_max, oc["max_depth"])))
    db_types = sql_map("SELECT object_type, COUNT(*) FROM configuration_objects GROUP BY object_type")
    type_diff = {key: (db_types.get(key), oc["types"].get(key))
                 for key in set(db_types) | set(oc["types"])
                 if db_types.get(key) != oc["types"].get(key)}
    check(f"разбивка по object_type совпадает ({len(oc['types'])} видов)",
          not type_diff, str(type_diff)[:600])
    check("вид метаданных = первая часть имени (парсер его не переименовывает)",
          sql_one("SELECT COUNT(*) FROM configuration_objects "
                  "WHERE split_part(name, '.', 1) <> object_type") == 0,
          str(sql_one("SELECT COUNT(*) FROM configuration_objects "
                      "WHERE split_part(name, '.', 1) <> object_type")))

    section("3. ИЕРАХИЯ ПО ИМЕНИ (parent_name; колонки parent_id в схеме нет, D3)")
    orphans = sql_one(
        "SELECT COUNT(*) FROM configuration_objects c WHERE c.parent_name IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM configuration_objects p "
        "WHERE p.configuration_id = c.configuration_id AND p.name = c.parent_name)")
    check("сирот (parent_name без родителя в той же конфигурации) нет", orphans == 0, str(orphans))
    null_mismatch = sql_one("SELECT COUNT(*) FROM configuration_objects "
                            "WHERE (parent_name IS NULL) <> (depth = 0)")
    check("parent_name IS NULL ровно у записей depth = 0", null_mismatch == 0, str(null_mismatch))
    bad_step = sql_one(
        "SELECT COUNT(*) FROM configuration_objects c JOIN configuration_objects p "
        "ON p.configuration_id = c.configuration_id AND p.name = c.parent_name "
        "WHERE c.depth <> p.depth + 1")
    check("глубина ребёнка = глубина родителя + 1 у всех некорневых", bad_step == 0, str(bad_step))
    bad_child = sql_one("SELECT COUNT(*) FROM configuration_objects "
                        "WHERE (child_type IS NOT NULL) <> (depth > 0)")
    check("child_type заполнен ровно у некорневых записей", bad_child == 0, str(bad_child))
    bad_prefix = sql_one(
        "SELECT COUNT(*) FROM configuration_objects c JOIN configuration_objects p "
        "ON p.configuration_id = c.configuration_id AND p.name = c.parent_name "
        "WHERE strpos(c.name, p.name || '.') <> 1")
    check("родитель — строгий префикс имени ребёнка по сегментам", bad_prefix == 0,
          str(bad_prefix))

    section("4. ИДЕНТИФИКАТОРЫ (D2) И configVersion (D4)")
    canonical = oc["id_forms"].get("uuid", 0)
    uuid_filled = sql_one("SELECT COUNT(*) FROM configuration_objects WHERE uuid IS NOT NULL")
    check(f"uuid заполнен ровно у канонических записей ({canonical})",
          uuid_filled == canonical, str(uuid_filled))
    uuid_mismatch = sql_one("SELECT COUNT(*) FROM configuration_objects "
                            "WHERE uuid IS NOT NULL AND uuid::text <> object_id")
    check("uuid — тот же object_id, а не другое значение", uuid_mismatch == 0, str(uuid_mismatch))
    dotted = sql_one("SELECT COUNT(*) FROM configuration_objects WHERE object_id ~ %s",
                     DOTTED_ID_RE)
    check(f"составных/суффиксных идентификаторов в object_id = {oc['entries_total'] - canonical}",
          dotted == oc["entries_total"] - canonical, str(dotted))

    by_name = {entry["name"]: entry["object_id"] for entry in offline["objects"]}
    base_ok = base_differs = parent_absent = 0
    base_mismatch = []
    for entry in offline["objects"]:
        if id_form(entry["object_id"]) == "uuid":
            continue
        base = entry["object_id"].split(".", 1)[0]
        parent = split_name(entry["name"])["parent_name"]
        if parent in by_name:
            if by_name[parent] == base:
                base_ok += 1
            else:
                base_differs += 1
                base_mismatch.append((entry["name"], entry["object_id"], parent, by_name[parent]))
        else:
            parent_absent += 1
    sql_base = sql_rows(
        "SELECT COUNT(*) FILTER (WHERE p.object_id = split_part(c.object_id, '.', 1)), "
        "COUNT(*) FILTER (WHERE p.object_id IS NOT NULL "
        "AND p.object_id <> split_part(c.object_id, '.', 1)), "
        "COUNT(*) FILTER (WHERE p.object_id IS NULL) "
        "FROM configuration_objects c LEFT JOIN configuration_objects p "
        "ON p.configuration_id = c.configuration_id AND p.name = c.parent_name "
        "WHERE c.object_id ~ %s", [DOTTED_ID_RE])[0]
    print(f"       офлайн (правило D3): база совпала {base_ok}, разошлась {base_differs}, "
          f"родителя нет {parent_absent}")
    print(f"       SQL (независимая реализация): база совпала {sql_base[0]}, "
          f"разошлась {sql_base[1]}, родителя нет {sql_base[2]}")
    check("база составного идентификатора = object_id родителя, названного именем (D2 + D3)",
          (base_ok, base_differs, parent_absent) == tuple(sql_base),
          str(((base_ok, base_differs, parent_absent), tuple(sql_base))))
    check("большинство неканонических идентификаторов объяснено иерархией",
          base_ok >= base_differs + parent_absent, str((base_ok, base_differs, parent_absent)))
    # Расхождение базы — не шум, а названный факт. У BGU2 таких записей 11, и все они —
    # предопределённые дети корня `Configuration.<Имя>` (SessionModule, Splash,
    # CommandInterface, ParentConfigurations, …): у них ОДНА общая база, отличная от
    # ObjectId самой конфигурации. Это то же семейство предопределённых ссылок платформы,
    # которое парсер заголовка считает в InternalInfo корня (слой xml-format, якорь
    # identifier-profile-classid-objectid-typeid-valueid). Оставить их без объяснения —
    # значит оставить в замере 11 необъяснённых записей.
    mismatch_parents = sorted({parent for (_name, _oid, parent, _poid) in base_mismatch})
    mismatch_bases = sorted({oid.split(".", 1)[0] for (_n, oid, _p, _q) in base_mismatch})
    for name, object_id, parent, parent_object_id in base_mismatch[:15]:
        print(f"       база НЕ равна object_id родителя: {name}\n"
              f"           id={object_id}, родитель={parent}, id_родителя={parent_object_id}")
    explained = (not base_mismatch) or (
        len(mismatch_parents) == 1
        and mismatch_parents[0].split(".", 1)[0] == "Configuration"
        and len(mismatch_bases) == 1
    )
    check("расхождения базы объяснимы: только дети корня Configuration с одной общей базой",
          explained, str((mismatch_parents[:3], mismatch_bases[:3], len(base_mismatch))))

    cv_filled = sql_one("SELECT COUNT(*) FROM configuration_objects "
                        "WHERE config_version IS NOT NULL")
    check(f"config_version заполнен ровно у {oc['config_versions']} записей (D4)",
          cv_filled == oc["config_versions"], str(cv_filled))
    cv_bad = sql_one("SELECT COUNT(*) FROM configuration_objects "
                     "WHERE config_version IS NOT NULL AND config_version !~ %s",
                     CONFIG_VERSION_RE)
    check("config_version шестнадцатеричный (40 символов) у всех заполненных", cv_bad == 0,
          str(cv_bad))
    cv_in_uuid = sql_one("SELECT COUNT(*) FROM configuration_objects "
                         "WHERE uuid IS NOT NULL AND uuid::text = config_version")
    check("config_version ни разу не попал в uuid (D4)", cv_in_uuid == 0, str(cv_in_uuid))

    dup_names = sql_one("SELECT COUNT(*) FROM (SELECT configuration_id, name "
                        "FROM configuration_objects GROUP BY 1,2 HAVING COUNT(*) > 1) d")
    check("дублей имени в пределах конфигурации нет (configuration_objects_name_unique)",
          dup_names == 0, str(dup_names))
    dup_ids = sql_one("SELECT COUNT(*) FROM (SELECT configuration_id, object_id "
                      "FROM configuration_objects GROUP BY 1,2 HAVING COUNT(*) > 1) d")
    check("дублей object_id в пределах конфигурации нет (object_id_unique)", dup_ids == 0,
          str(dup_ids))
    dup_uuid = sql_one("SELECT COUNT(*) FROM (SELECT uuid FROM configuration_objects "
                       "WHERE uuid IS NOT NULL GROUP BY 1 HAVING COUNT(*) > 1) d")
    print(f"       дублей uuid: {dup_uuid} (замер BGU2 — 0; уникального индекса по uuid нет, "
          f"строка справочная, а не проверка)")
    fk_bad = sql_one("SELECT COUNT(*) FROM configuration_objects c "
                     "LEFT JOIN configurations g ON g.id = c.configuration_id WHERE g.id IS NULL")
    check("внешний ключ на заголовок разрешается у всех строк", fk_bad == 0, str(fk_bad))

    section("5. ИЗВЕСТНЫЕ ОБЪЕКТЫ BGU2 ПРОТИВ ФАЙЛОВ МЕТАДАННЫХ")
    # якорь слоя знаний configuration-object-uuid-location: uuid из ConfigDumpInfo.xml
    # обязан совпадать с uuid элемента метаданных в файле вида.
    probes = [
        ("Catalog", "ОсновныеСредства", Path(BGU2) / "Catalogs" / "ОсновныеСредства.xml"),
        ("CommonModule", "АвтоматическоеПолучениеЭДО",
         Path(BGU2) / "CommonModules" / "АвтоматическоеПолучениеЭДО.xml"),
    ]
    for kind, name, meta_file in probes:
        rows = sql_rows("SELECT uuid::text, object_id, depth, child_type, parent_name "
                        "FROM configuration_objects WHERE configuration_id=%s "
                        "AND object_type=%s AND object_name=%s AND depth=0", (cfg_id, kind, name))
        if not check(f"объект {kind}.{name} есть в индексе верхнего уровня (depth = 0)",
                     bool(rows), ""):
            continue
        db_uuid, object_id, depth, child_type, parent_name = rows[0]
        text = meta_file.read_text(encoding="utf-8", errors="replace") if meta_file.is_file() else ""
        check(f"uuid индекса = uuid элемента метаданных в файле {meta_file.name}",
              f'<{kind} uuid="{db_uuid}"' in text,
              f"uuid={db_uuid}, файл прочитан: {bool(text)}")
        check(f"object_id = uuid, child_type/parent_name пустые (запись верхнего уровня)",
              object_id == db_uuid and child_type is None and parent_name is None,
              repr((object_id, child_type, parent_name)))
        full = sql_one("SELECT COUNT(*) FROM configuration_objects WHERE configuration_id=%s "
                       "AND name=%s", (cfg_id, f"{kind}.{name}"))
        check(f"имя записи в индексе = {kind}.{name} (без пути каталога)", full == 1, str(full))

    section("6. force=True: FK без ON DELETE требует явной чистки индекса")
    before = sql_one("SELECT COUNT(*) FROM configuration_objects")
    res2 = load_catalog(BGU2)
    after_dup = sql_one("SELECT COUNT(*) FROM configuration_objects")
    check("повтор без force — ⚠️ уже загружено, индекс не меняется",
          res2.get("status") == "duplicate" and after_dup == before,
          f"статус={res2.get('status')} строк={after_dup}")
    res3 = load_catalog(BGU2, force=True)
    print(format_load_result(res3)[:1500])
    check("force=True — ♻️ перезагружено", res3.get("status") == "reloaded",
          str(res3.get("error") or "")[:400])
    after_force = sql_one("SELECT COUNT(*) FROM configuration_objects")
    check("старые строки сняты, новых ровно entries_total (дублей нет)",
          after_force == oc["entries_total"], str(after_force))
    new_id = res3.get("id")
    check("строки указывают на новую строку заголовка",
          sql_one("SELECT COUNT(*) FROM configuration_objects WHERE configuration_id=%s", new_id)
          == oc["entries_total"], str(new_id))
    replaced = res3.get("replaced") or {}
    removed = replaced.get("children_deleted") or {}
    check("карточка перезагрузки назвала снятые строки индекса",
          removed.get("configuration_objects") == before, str(removed))
    orphans_after = sql_one(
        "SELECT COUNT(*) FROM configuration_objects c WHERE c.parent_name IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM configuration_objects p "
        "WHERE p.configuration_id = c.configuration_id AND p.name = c.parent_name)")
    check("после force=True сирот по-прежнему нет", orphans_after == 0, str(orphans_after))

    section("7. УДАЛЕНИЕ КОНФИГУРАЦИИ: индекс снимается явным DELETE")
    if keep:
        check("--keep задан: BGU2 оставлен в БД, ветка удаления пропущена", True)
    else:
        check("до удаления индекс на месте",
              sql_one("SELECT COUNT(*) FROM configuration_objects") == oc["entries_total"], "")
        out = delete_configuration(cfg_id=new_id)
        print(json.dumps(out, ensure_ascii=False)[:1200])
        check("удаление по id конфигурации выполнено", out.get("success") is True,
              str(out.get("error"))[:300])
        dropped = out.get("children_deleted") or {}
        check("отчёт удаления называет снятые строки индекса (явный DELETE, FK без ON DELETE)",
              dropped.get("configuration_objects") == oc["entries_total"], str(dropped))
        left_objects = sql_one("SELECT COUNT(*) FROM configuration_objects")
        left_cfg = sql_one("SELECT COUNT(*) FROM configurations")
        check("строки индекса сняты вместе с заголовком (сирот не остаётся)",
              left_objects == 0 and left_cfg == 0,
              f"configuration_objects={left_objects} configurations={left_cfg}")
        check("BSL-модулей конфигурации не осталось",
              sql_one("SELECT COUNT(*) FROM bsl_modules WHERE configuration_id=%s", new_id) == 0, "")
    check("внешние объекты эталонной пары не затронуты",
          sql_one("SELECT COUNT(*) FROM external_report") == ext_before,
          f"до={ext_before} после={sql_one('SELECT COUNT(*) FROM external_report')}")

    print(f"\n{'=' * 78}\nИТОГ: проверок {TOTAL}, провалено {len(FAILED)}\n{'=' * 78}")
    for name in FAILED:
        print(f"  ✗ {name}")
    return 0 if not FAILED else 1


if __name__ == "__main__":
    raise SystemExit(main())






