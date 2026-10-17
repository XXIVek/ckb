#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/check_v32_zero_configuration.py — проверка узла V32: «нулевая» конфигурация.

Эталон: C:\1C_LLM\LoadDoc\Config_NULL\Config_NULL_XML — Configuration.xml без объектов
метаданных кроме Language и без модулей. Внешний объект для проверки привязок —
Test3_Otchet_Null; эталонная пара (Test1_Otchet, Test2_Otchet) не трогается.

Что проверяется и почему именно так:
  1. схема: `configurations` живая; колонок провенанса, версионирования и таблиц объектов
     метаданных узел V32 НЕ добавлял (решения D-C и D-D); UNIQUE по имени есть, уникальности
     по uuid нет; ссылки `config_extensions`/`bsl_modules` на заголовок сохранены, а
     `external_report.configuration_id` по-прежнему БЕЗ внешнего ключа (узел V20.1);
  2. детекция (R1): Configuration.xml даёт вариант `configuration`; тот же файл с
     `ConfigurationExtensionPurpose` — вариант `extension`, который остаётся заглушкой (R7);
     вложенный Configuration.xml не читается; внешний отчёт не уехал в конфигурацию;
  3. разбор: uuid из атрибута элемента (R3), свойства в колонки, ссылочные значения
     развёрнуты в ИМЯ (Language.Русский → Русский), пустой синоним — NULL (D-D), слепые зоны
     названы прямо (Properties без колонки, ChildObjects/Language,
     UsedMobileApplicationFunctionalities, InternalInfo корня с версиями UUID v1/v4);
     пустой или некорректный uuid — отказ с причиной;
  4. фикстура `Config_NULL` (её проверяет только этот инструмент): индекс состава пуст —
     общая точка входа удерживает загрузку ДО записи (узел V33: частичного индекса не
     бывает), хотя сам `Configuration.xml` разбирается целиком (раздел 3). Строк ни в
     `configurations`, ни в `configuration_objects` не появляется;
  5. загрузка копии фикстуры с пустым `<Name>` и непустым `ConfigDumpInfo.xml`: ✅ загружено,
     имя заголовка взято из имени каталога (правило V32) и это названо предупреждением;
     строка в `configurations` плюс перечень состава в `configuration_objects`; карточка
     называет вариант, индекс и слепые зоны, НЕ печатает children-счётки внешнего объекта
     и НЕ обещает провенанс (D-C);
  6. ⚠️ уже загружено: карточка конфигурации (не внешнего объекта) показывает привязки и
     связанные строки, называет отсутствие провенанса и отсутствие инструмента удаления
     конфигурации в контракте — и НЕ советует `delete_external_report_tool` (он ищет в
     `external_report`); дубликат ищется по uuid, а не по пути;
  7. ♻️ force=True — одна транзакция: старая строка снята, новая вставлена, uuid тот же,
     `id` новый, связанные `configuration_objects`/`config_extensions`/`bsl_modules` сняты
     явно (каскада нет); журнала попыток в схеме нет — история не ведётся (решение D-C);
  8. name_conflict — отдельный исход: при занятом имени и новом uuid загрузка не выполнена,
     `force=True` НЕ предлагается (иначе удалили бы ДРУГУЮ конфигурацию);
  9. дубликаты uuid в `configurations` (уникальности нет — D-D) названы и в ответе
     загрузчика, и в карточке; uuid, совпадающий с uuid внешнего объекта, конфликтом не
     является (таблицы разные);
 10. привязки внешних объектов: `force=True` и снятие заголовка делают ссылку битой
     (`dangling`), и это называют ответ загрузчика и карточка объекта (модель V20.1);
 11. готовность экспорта живым сервером: `configuration_objects` больше НЕ среди
     отсутствующих таблиц (её создал узел V33), сценарий V18 по-прежнему не реализован;
 12. `delete_configuration` снимает заголовок, перечень состава и связанные строки сам,
     перечисляя то, что стало битой привязкой; после прогона счётчики БД возвращаются к
     исходным.

Путь записи проверяется на КОПИИ фикстуры, а не на самой `Config_NULL`: у неё индекс пуст,
и загрузка удержана на разборе индекса (п. 4). Копия отличается ровно двумя правками —
пустой `<Name>` (главное поведение узла V32: имя из имени каталога) и непустой
`ConfigDumpInfo.xml` (позволяет пройти маршрут записи и проверить `configuration_objects`).

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python tools/check_v32_zero_configuration.py [--only РАЗДЕЛ[,...]] [--keep] | --list
`--list` печатает разделы; `--only` запускает раздел и его зависимости (параметр повторяется
или принимает список ключей через запятую); `--keep` оставляет
тестовые каталоги и строки (по умолчанию всё снимается).
Код возврата 0 — все проверки пройдены, 1 — есть расхождения.
"""
import argparse
import shutil
import sys
import tempfile
import uuid as uuid_lib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

# Эмодзи исходов (✅ ♻️ ⚠️ ❌) не влазят в cp1251 консоль Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from config_dump_info_parser import (find_config_dump_info,  # noqa: E402
                                    parse_config_dump_info)
from config_load_router import (VARIANT_CONFIGURATION, VARIANT_EXTENSION,  # noqa: E402
                                detect_load_variant, format_load_result, load_catalog)
from configuration_loader import (TABLE, bound_external_objects,  # noqa: E402
                                  delete_configuration, find_configuration,
                                  find_configuration_by_name, find_configuration_xml,
                                  register_configuration)
from configuration_meta_parser import (CONFIGURATION_FIELDS,  # noqa: E402
                                      parse_configuration_meta)  # noqa: E402
from enrichment_generator import (describe_object, generate_enrichment,  # noqa: E402
                                 set_object_configuration)
from enrichment_snippets import enrichment_stats  # noqa: E402
from external_db import connect  # noqa: E402
from external_report_loader import delete_external_object  # noqa: E402

BASE = Path(r"C:\1C_LLM\LoadDoc")
CONFIG_CATALOG = BASE / "Config_NULL" / "Config_NULL_XML"
CONFIG_XML = CONFIG_CATALOG / "Configuration.xml"
NULL_REPORT = BASE / "Test3_Otchet_Null"
PROBE = "__v32_probe__"
# uuid корня фикстуры (`<Configuration uuid=...>` в Configuration.xml). Он берётся из
# файла, а не выдумывается: на него опираются ожидания разбора (раздел 3) и сверка
# «строка не создана» (раздел 4). Держать ту же строку в двух местах — значит рассориться
# при первой же новой фикстуре.
CONFIG_UUID = "fd71e6e8-38a4-4210-8c73-79b07d9e5cff"

# Граница объёма по таблицам схемы. `configuration_objects` узел V33 ЗАВОДИТ — это первая
# таблица объектов метаданных, и требовать её отсутствия больше нельзя (раздел 11 проверяет
# прямо обратное: её нет в перечне отсутствующих таблиц экспорта). Остальные таблицы, о которых
# идёт речь в разделах 1 и 11, не заведены ни V32, ни V33: словарь языков и таблица модулей
# конфигурации (слепые зоны разбора), таблицы изменений и журнала экспорта (узел V18).
V33_CREATED_TABLES = ["configuration_objects"]
NOT_CREATED_TABLES = ["config_languages", "config_modules",
                     "modified_objects", "config_export_log"]

failures = []
counters = {"checks": 0}
temp_dirs = []
state = {}


def check(name, ok, detail=""):
    counters["checks"] += 1
    print(("[OK  ] " if ok else "[FAIL] ") + name
          + (f" — {detail}" if (detail and not ok) else ""))
    if not ok:
        failures.append(name)
    return bool(ok)


def section(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def sql_rows(query, params=None):
    """Одна выборка через psycopg2 (тот же доступ к БД, что у загрузчика)."""
    conn = None
    try:
        conn = connect()
        cur = conn.cursor()
        cur.execute(query, tuple(params) if params else None)
        rows = [tuple(r) for r in cur.fetchall()]
        cur.close()
        conn.commit()
        return rows
    except Exception as exc:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        check(f"SQL-запрос: {query[:70]}...", False, str(exc))
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def sql_one(query, params=None):
    rows = sql_rows(query, params)
    return rows[0][0] if rows else None


def sql_write(query, params=None):
    conn = None
    try:
        conn = connect()
        cur = conn.cursor()
        cur.execute(query, tuple(params) if params else None)
        count = cur.rowcount
        cur.close()
        conn.commit()
        return count
    except Exception as exc:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        check(f"SQL-запись: {query[:70]}...", False, str(exc))
        return -1
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ───────────────── вспомогательное: снимки и фикстуры ─────────────────

def db_counts():
    """Счётчики всех таблиц, которых касается узел V32 (для сверки «до/после»).

    Узел V33 добавил `configuration_objects`: заголовок конфигурации теперь пишется вместе
    с перечнем состава, поэтому снимок «до/после» обязан считать и её — иначе тест,
    оставивший строки состава, прошёл бы незамеченным.
    """
    return {
        "configurations": sql_one(f"SELECT COUNT(*) FROM {TABLE}"),
        "configuration_objects": sql_one("SELECT COUNT(*) FROM configuration_objects"),
        "config_extensions": sql_one("SELECT COUNT(*) FROM config_extensions"),
        "bsl_modules": sql_one("SELECT COUNT(*) FROM bsl_modules"),
        "external_report": sql_one("SELECT COUNT(*) FROM external_report"),
        "bound": sql_one("SELECT COUNT(*) FROM external_report "
                         "WHERE configuration_id IS NOT NULL"),
    }


def probe_uuid():
    return str(uuid_lib.uuid4())


def new_catalog():
    """Каталог с копией эталонного Configuration.xml (для правки uuid/имени/атрибутов)."""
    d = Path(tempfile.mkdtemp(prefix="v32_cat_"))
    temp_dirs.append(d)
    shutil.copy2(str(CONFIG_XML), str(d / "Configuration.xml"))
    return d


def edit_xml(path, pairs):
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            check(f"фикстура: подстрока найдена в XML: {old[:60]}", False, "не найдена")
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    return path


def probe_header(name=None, uuid_value=None):
    """Тестовый заголовок конфигурации (его id кладётся в список уборки)."""
    name = name or f"{PROBE}{uuid_lib.uuid4().hex[:8]}"
    cfg_uuid = uuid_value or probe_uuid()
    cfg_id = sql_one(f"INSERT INTO {TABLE} (name, uuid) VALUES (%s, %s) RETURNING id",
                     (name, cfg_uuid))
    state.setdefault("probe_headers", []).append(int(cfg_id))
    return int(cfg_id), name, cfg_uuid


# ───────────────── 1. схема ─────────────────

def check_schema():
    section("1. СХЕМА: configurations живая; провенанса и версионирования нет (D-C, D-D)")
    cols = {r[0]: r[1] for r in sql_rows(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s", (TABLE,))}
    if not check("таблица configurations существует в public", bool(cols), f"колонок: {len(cols)}"):
        return
    expected = {"id", "name", "synonym", "comment", "version", "vendor_name", "uuid",
                "main_mode", "usage_purpose", "embedded_language", "main_roles",
                "app_module_id", "session_module_id", "data_proc_module_id",
                "ext_conn_module_id", "mobile_functionality", "default_language",
                "short_info", "detailed_info", "copyright", "vendor_url", "config_url",
                "update_url", "help_included", "lock_mode_default", "modality_mode",
                "ext_comp_sync_mode", "interface_compat_mode", "compatibility_mode",
                "created_at", "updated_at"}
    missing = sorted(expected - set(cols))
    check(f"колонок заголовка конфигурации на месте ({len(expected)}) — узел V32 схему не менял",
          not missing, f"нет колонок: {missing}")

    absent = sorted(c for c in cols
                    if c.startswith("origin_") or c.endswith("_source")
                    or c in {"revision_no", "changed_at", "changed_by", "source_path",
                             "layout_path", "containedobject_classid"})
    check("колонок провенанса и версионирования нет (D-C/D-D: узел V32 их не заводил)",
          not absent, f"найдены: {absent}")

    cons = {r[0]: r[1] for r in sql_rows(
        "SELECT conname, contype FROM pg_constraint c "
        "JOIN pg_namespace n ON n.oid = c.connamespace "
        "WHERE n.nspname='public' AND c.conrelid = 'configurations'::regclass")}
    check("PRIMARY KEY на id есть", any(t == "p" for t in cons.values()), str(cons))
    check("UNIQUE по имени конфигурации есть (по нему опознаётся дубль каталога)",
          any(t == "u" for t in cons.values()), str(cons))
    check("внешних ключей у самой configurations нет (ссылки идут от детей к заголовку)",
          not any(t == "f" for t in cons.values()),
          str({k: v for k, v in cons.items() if v == "f"}))
    keyed = sql_rows(
        "SELECT conname, pg_get_constraintdef(c.oid) FROM pg_constraint c "
        "JOIN pg_namespace n ON n.oid = c.connamespace "
        "WHERE n.nspname='public' AND c.conrelid='configurations'::regclass "
        "AND c.contype IN ('u','p')")
    uuid_key = [d for (_n, d) in keyed if "uuid" in d.lower()]
    check("уникальности по uuid в configurations нет (D-D: uuid не ключ, ключ — имя)",
          not uuid_key, f"ограничения: {keyed}")

    inbound = sql_rows(
        "SELECT conrelid::regclass::text FROM pg_constraint "
        "WHERE contype='f' AND confrelid = 'configurations'::regclass ORDER BY 1")
    check("ссылки детей на заголовок сохранены (config_extensions, bsl_modules)",
          len(inbound) >= 2, f"внешних ключей на configurations: {len(inbound)} {inbound}")

    er_cols = {r[0] for r in sql_rows(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='external_report'")}
    if check("external_report.configuration_id есть", "configuration_id" in er_cols,
             "нет колонки — состояние схемы другое"):
        er_fk = sql_rows(
            "SELECT conname FROM pg_constraint c "
            "JOIN pg_namespace n ON n.oid = c.connamespace "
            "WHERE n.nspname='public' AND c.conrelid='external_report'::regclass "
            "AND contype='f' AND conname LIKE '%%configuration%%'")
        check("внешнего ключа к конфигурации нет (узел V20.1: справочник ведётся свободно)",
              not er_fk, str(er_fk))
        idx = sql_rows("SELECT indexname FROM pg_indexes WHERE schemaname='public' "
                       "AND tablename='external_report' AND indexname=%s",
                       ("idx_external_report_configuration_id",))
        check("индекс обратного поиска привязок сохранён (по нему ищут перепривязку)",
              bool(idx), "индекса нет")

    created = {r[0] for r in sql_rows(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' "
        "AND table_name = ANY(%s)", ([*V33_CREATED_TABLES, *NOT_CREATED_TABLES],))}
    # Прежняя проверка требовала отсутствия `configuration_objects` — она была верна до V33.
    # Оставлять её нельзя: она падала бы на верной схеме; молча убрать — не ответить.
    check("configuration_objects заведена узлом V33: слепая зона индекса состава закрыта",
          set(V33_CREATED_TABLES) <= created, f"в схеме из проверяемых: {sorted(created)}")
    check("словаря языков, таблицы модулей, таблиц изменений и журнала экспорта нет",
          not (created & set(NOT_CREATED_TABLES)),
          f"неожиданно есть: {sorted(created & set(NOT_CREATED_TABLES))}")


# ───────────────── 2. детекция варианта (R1) ─────────────────

def check_detection():
    section("2. ДЕТЕКЦИЯ: Configuration.xml -> configuration; extension остаётся заглушкой (R7)")
    d = detect_load_variant(str(CONFIG_CATALOG))
    if not check("Configuration.xml в корне даёт вариант configuration",
                 d.get("success") and d.get("variant") == VARIANT_CONFIGURATION, str(d)[:300]):
        return
    check("вариант указывает на справочник configurations (не на external_report)",
          d.get("table") == TABLE, f"table={d.get('table')}")
    check("xml_path указывает на файл корневого каталога",
          Path(d.get("xml_path", "")).name == "Configuration.xml", d.get("xml_path"))

    # расширение: тот же корневой файл + ConfigurationExtensionPurpose => extension (заглушка)
    ext_dir = new_catalog()
    edit_xml(ext_dir / "Configuration.xml",
             [("<DefaultRunMode>",
               "<v8:ConfigurationExtensionPurpose>ManagedApplication"
               "</v8:ConfigurationExtensionPurpose><DefaultRunMode>")])
    de = detect_load_variant(str(ext_dir))
    check("ConfigurationExtensionPurpose переводит тот же файл в вариант extension",
          de.get("success") and de.get("variant") == VARIANT_EXTENSION, str(de)[:300])
    check("purpose прочитан и назван в ответе детектора",
          bool(de.get("extension_purpose")), str(de.get("extension_purpose")))
    before = db_counts()
    res = load_catalog(str(ext_dir))
    text = format_load_result(res)
    check("extension остаётся заглушкой (R7): исход not_implemented с одной причиной",
          res.get("status") == "not_implemented" and "не реализован" in text, text[:300])
    check("заглушка ничего не записала в configurations",
          db_counts()["configurations"] == before["configurations"],
          f"было {before['configurations']}, стало {db_counts()['configurations']}")
    check("ответ заглушки называет реализованные варианты и остающийся заглушкой extension",
          "расширение" in text and "конфигураци" in text, text[:300])

    # вложенный Configuration.xml не читается (R1: только корень)
    nested = Path(tempfile.mkdtemp(prefix="v32_nested_"))
    temp_dirs.append(nested)
    (nested / "inner").mkdir()
    shutil.copy2(str(CONFIG_XML), str(nested / "inner" / "Configuration.xml"))
    dn = detect_load_variant(str(nested))
    check("вложенный Configuration.xml не просматривается: каталог не подходит",
          dn.get("status") == "error" and "не подходит" in dn.get("error", ""), str(dn)[:300])
    check("find_configuration_xml находит только корневой файл",
          find_configuration_xml(str(nested)) is None, "нашёл вложенный")

    # внешний объект не уехал в конфигурацию
    dr = detect_load_variant(str(BASE / "Test1_Otchet"))
    check("каталог внешнего отчёта остаётся внешним отчётом (маршрут V22 не сломан)",
          dr.get("success") and dr.get("variant") not in (VARIANT_CONFIGURATION, VARIANT_EXTENSION),
          str(dr)[:300])
    dnop = detect_load_variant(str(ROOT / "нет_такого_каталога"))
    check("несуществующий путь — отказ «каталог не найден»",
          "не найден" in dnop.get("error", ""), str(dnop)[:200])


# ───────────────── 3. разбор Configuration.xml ─────────────────

def check_parser():
    section("3. РАЗБОР: uuid из атрибута, ref -> имя, пустой синоним = NULL, слепые зоны названы")
    before = db_counts()
    parsed = parse_configuration_meta(str(CONFIG_XML))
    if not check("Configuration.xml разобран", parsed.get("success"), str(parsed)[:300]):
        return
    row, counts, warnings = parsed["configuration"], parsed["counts"], parsed["warnings"]

    check("uuid взят из атрибута <Configuration uuid=...>, а не из Properties",
          parsed["uuid"] == CONFIG_UUID and row["uuid"] == CONFIG_UUID, parsed.get("uuid"))
    check("имя взято из <Name>", row["name"] == "Конфигурация", repr(row.get("name")))
    check("пустой <Synonym/> -> NULL (D-D: состояния «пустой синоним» в модели нет)",
          row["synonym"] is None, repr(row.get("synonym")))
    check("пустые <Comment/> <Vendor/> <Version/> -> NULL", row["comment"] is None
          and row["vendor_name"] is None and row["version"] is None,
          repr([row.get("comment"), row.get("vendor_name"), row.get("version")]))
    check("скалярные свойства разложены по своим колонкам",
          row["main_mode"] == "ManagedApplication"
          and row["embedded_language"] == "Russian"
          and row["compatibility_mode"] == "Version8_3_27"
          and row["interface_compat_mode"] == "Taxi"
          and row["modality_mode"] == "DontUse"
          and row["ext_comp_sync_mode"] == "DontUse"
          and row["lock_mode_default"] == "Managed",
          repr({k: row.get(k) for k in ("main_mode", "embedded_language",
                                        "compatibility_mode", "interface_compat_mode")}))
    check("ссылочное значение развёрнуто в ИМЯ: Language.Русский -> Русский",
          row["default_language"] == "Русский", repr(row.get("default_language")))
    check("перечень v8:Value из одного значения пишется как есть",
          row["usage_purpose"] == "PlatformApplication", repr(row.get("usage_purpose")))
    check("пустой <DefaultRoles/> -> пустой перечень (не строка «[]»)",
          not row["main_roles"], repr(row.get("main_roles")))
    check("bool-свойство читается как boolean, а не как текст",
          row["help_included"] is False, repr(row.get("help_included")))
    # Список колонок берётся из живой схемы, а не из литерала в этом файле: литерал
    # разошёлся бы с DDL при первом же изменении схемы, и проверка «писатель уместится
    # в таблицу» стала бы вакуумной (состав схемы как таковой проверяет раздел 1).
    live_columns = configurations_columns()
    check("колонки configurations прочитаны из живой схемы", bool(live_columns),
          f"{len(live_columns)} колонок")
    extra = sorted(set(row) - live_columns)
    check("ключи контракта = имена колонок configurations (писатель не упадёт)",
          not extra, f"лишние ключи: {extra}")
    check("разбор ничего не записывает в БД: чтение отделено от записи",
          db_counts() == before, f"{before} -> {db_counts()}")

    # ── счётчики и слепые зоны ──
    check("счётчик свойств: разобранное и не имеющее колонки не путаются",
          counts["properties_total"] >= counts["properties_mapped"]
          and counts["properties_mapped"] == len(CONFIGURATION_FIELDS)
          and counts["properties_filled"] >= 8
          and counts["properties_unstored"]
          == (len(counts["properties_unstored_nonempty"])
              + counts["properties_unstored_empty"]),
          repr(counts))
    nonempty = set(counts["properties_unstored_nonempty"])
    check("свойства без колонки с НЕПУСТЫМ значением названы поимённо",
          {"ConfigurationExtensionCompatibilityMode", "MainClientApplicationWindowMode",
           "ObjectAutonumerationMode", "DatabaseTablespacesUseMode"} <= nonempty,
          repr(sorted(nonempty)))
    check("пустые свойства без колонки не попадают в перечень непустых",
          counts["properties_unstored_empty"] > 0
          and not (nonempty & {"NamePrefix", "CommonSettingsStorage", "Content"}),
          f"empty={counts['properties_unstored_empty']} nonempty={sorted(nonempty)[:8]}")
    check("непустые слепые зоны названы в предупреждениях поимённо",
          all(any(f"Properties/{name}" in w and "слепая зона V32" in w for w in warnings)
              for name in ("ConfigurationExtensionCompatibilityMode",
                           "MainClientApplicationWindowMode")),
          repr([w[:90] for w in warnings][:6]))
    check("пустые слепые зоны названы числом и не притворяются потерянными",
          any("имеют пустые значения" in w for w in warnings),
          repr([w[:90] for w in warnings][:6]))
    check("ChildObjects/Language: одна языковая конфигурация названа слепой зоной",
          counts["child_objects"] == {"Language": 1}
          and any("ChildObjects/Language" in w and "Русский" in w for w in warnings),
          repr(counts["child_objects"]))
    check("UsedMobileApplicationFunctionalities: решение D-D названо, use=true перечислен",
          counts["mobile_functionality_total"] > 0
          and "OSBackup" in counts["mobile_functionality_use_true"]
          and any("UsedMobileApplicationFunctionalities" in w and "D-D" in w
                  for w in warnings),
          repr([counts["mobile_functionality_total"],
                counts["mobile_functionality_use_true"]]))
    versions = counts["root_identifier_versions"]
    check("InternalInfo корня: пары ClassId/ObjectId посчитаны и названы (колонок нет)",
          counts["root_identifier_pairs"] == 7
          and sum(versions.values()) == 2 * counts["root_identifier_pairs"]
          and any("InternalInfo корня" in w for w in warnings),
          repr([counts["root_identifier_pairs"], versions]))
    check("версии UUID названы: часть идентификаторов корня — v1, «всё это v4» неверно",
          versions.get("v1") == 2 and versions.get("v4") == 12, repr(versions))


def check_parser_negatives():
    section("3b. РАЗБОР: отказ с причиной, а не пустой контракт; теряемое — названо")
    for label, edits, want in (
        ("пустой uuid элемента Configuration",
         [(f'<Configuration uuid="{CONFIG_UUID}">', "<Configuration>")], "Пустой uuid"),
        ("некорректный uuid элемента Configuration",
         [(f'<Configuration uuid="{CONFIG_UUID}">', '<Configuration uuid="не-id">')],
         "Некорректный uuid"),
        ("в файле нет элемента Configuration",
         [("<Configuration ", "<NotConfiguration "),
          ("</Configuration>", "</NotConfiguration>")],
         "нет элемента"),
    ):
        catalog = new_catalog()
        edit_xml(catalog / "Configuration.xml", edits)
        res = parse_configuration_meta(str(catalog / "Configuration.xml"))
        ok = (not res.get("success")) and want in str(res.get("error", "")) and res.get("hint")
        check(f"{label}: отказ с причиной и подсказкой, контракта нет",
              ok and not res.get("configuration"), repr(res)[:260])

    broken = new_catalog()
    text = (broken / "Configuration.xml").read_text(encoding="utf-8")
    (broken / "Configuration.xml").write_text(text[: text.index("<ChildObjects>")],
                                              encoding="utf-8")
    res = parse_configuration_meta(str(broken / "Configuration.xml"))
    check("битый (обрезанный) XML: отказ «не разобран», а не пустая строка заголовка",
          not res.get("success") and "не разобран" in str(res.get("error", "")), repr(res)[:260])

    # многоязычный синоним: вторая языковая форма теряется — это называется
    multi = new_catalog()
    edit_xml(multi / "Configuration.xml",
             [("<Synonym/>",
               '<Synonym><v8:item><v8:lang>ru</v8:lang><v8:content>Нулевая</v8:content>'
               '</v8:item><v8:item><v8:lang>en</v8:lang><v8:content>Null</v8:content>'
               "</v8:item></Synonym>")])
    res = parse_configuration_meta(str(multi / "Configuration.xml"))
    check("многоязычный синоним: сохранён язык ru, потеря второй формы названа предупреждением",
          res.get("success") and res["configuration"]["synonym"] == "Нулевая"
          and any("Synonym многоязычен" in w and "en" in w for w in res["warnings"]),
          repr([res["configuration"].get("synonym"),
                [w[:80] for w in res.get("warnings", [])][:4]]))

    # перечень v8:Value из нескольких значений в скалярной колонке — тоже называется
    purposes = new_catalog()
    edit_xml(purposes / "Configuration.xml",
             [('<v8:Value xsi:type="app:ApplicationUsePurpose">PlatformApplication</v8:Value>',
               '<v8:Value xsi:type="app:ApplicationUsePurpose">PlatformApplication</v8:Value>'
               '<v8:Value xsi:type="app:ApplicationUsePurpose">MobileApplication</v8:Value>')])
    res = parse_configuration_meta(str(purposes / "Configuration.xml"))
    check("два значения UsePurposes: перечень сохранён через запятую И назван слепой зоной",
          res.get("success")
          and res["configuration"]["usage_purpose"] == "PlatformApplication, MobileApplication"
          and any("UsePurposes" in w and "скалярная" in w for w in res["warnings"]),
          repr([res["configuration"].get("usage_purpose"),
                [w[:80] for w in res.get("warnings", [])][:4]]))

    # односторонний синоним без ru: берётся первый доступный, и это называется
    en_only = new_catalog()
    edit_xml(en_only / "Configuration.xml",
             [("<Synonym/>",
               '<Synonym><v8:item><v8:lang>en</v8:lang><v8:content>Null</v8:content>'
               "</v8:item></Synonym>")])
    res = parse_configuration_meta(str(en_only / "Configuration.xml"))
    check("синоним только на en: значение сохранено как есть (первый доступный язык)",
          res.get("success") and res["configuration"]["synonym"] == "Null",
          repr(res["configuration"].get("synonym")))


# ───────────────── общая часть второй половины: снимки и копия фикстуры ─────────────────

OBJECTS_TABLE = "configuration_objects"
INDEX_XML = CONFIG_CATALOG / "ConfigDumpInfo.xml"
# Тот же uuid корня фикстуры, что в шапке: раздел 4 сверяет по нему «строки нет»,
# раздел 5 меняет его в копии — держать две копии одной строки нельзя.
FIXTURE_UUID = CONFIG_UUID

# Колонки строки заголовка для снимка «до/после» берутся из ЖИВОЙ схемы, а не из текста теста:
# жёсткий перечень разошёлся бы с DDL сразу же — в нём значилась `main_server_base_language`,
# которой в `configurations` нет (проверка падала с «столбец не существует»). Служебные колонки
# исключены явно и с причиной: `id` меняется при force=True, `uuid` сверяется отдельной
# проверкой, `created_at`/`updated_at` меняются при каждой вставке.
SNAPSHOT_EXCLUDED = {"id", "uuid", "created_at", "updated_at"}

# Состояние прогона: id/uuid созданной конфигурации, внешнего объекта, временных каталогов.
probe = {}


def note(text):
    """Строка-пояснение, не проверка: границу или пробел молчать нельзя."""
    print("[NOTE] " + text)


def header_columns():
    """Читаемые колонки заголовка из information_schema (порядок — по ordinal_position)."""
    return [r[0] for r in sql_rows(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (TABLE,))
        if r[0] not in SNAPSHOT_EXCLUDED]


def header_snapshot(cfg_id):
    """Снимок строки заголовка по читаемым колонкам (сверка до и после перезагрузки).

    Пустой список колонок — не «пустой снимок», а отсутствие схемы: он возвращает None,
    чтобы сравнение двух None не притворялось совпадением (проверяющий обязан проверить None).
    """
    columns = header_columns()
    if not columns:
        return None
    rows = sql_rows(f"SELECT {', '.join(columns)} FROM {TABLE} WHERE id = %s", (cfg_id,))
    return rows[0] if rows else None


def sql_dict(query, params=None):
    """Одна строка как dict: колонки заголовка нужны поимённо, а не по позиции."""
    conn = None
    try:
        conn = connect()
        cur = conn.cursor()
        cur.execute(query, tuple(params) if params else None)
        cols = [d[0] for d in cur.description] if cur.description else []
        row = cur.fetchone()
        cur.close()
        conn.commit()
        return dict(zip(cols, row)) if row else None
    except Exception as exc:
        check(f"SQL-выборка строкой: {query[:70]}...", False, str(exc))
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def configurations_columns():
    """Колонки `configurations` из живой схемы.

    Собственный список колонок в файле проверки держать нельзя: он разошёлся бы со схемой
    при первом же узле, меняющем DDL, а смысл имеет утверждение «ключи контракта
    умещаются в таблицу» — оно проверяется против живой схемы (сам состав схемы
    проверяет раздел 1).
    """
    return {r[0] for r in sql_rows(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s", (TABLE,))}


# Узел V33: минимальный ConfigDumpInfo.xml для копии фикстуры. Формат — тот же, что у живой
# выгрузки (контейнер <ConfigVersions> и <Metadata name id configVersion>); запись одна с
# вложенной дочерней, чтобы проверить и иерархию, и разрешение родителя.
INDEX_XML_TEMPLATE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<ConfigDumpInfo xmlns="http://v8.1c.ru/8.3/xcf/dumpinfo" '
    'xmlns:xs="http://www.w3.org/2001/XMLSchema" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'format="Hierarchical" version="2.20">\n'
    "\t<ConfigVersions>\n"
    '\t\t<Metadata name="Catalog.{tag}" id="{root_id}" configVersion="{config_version}"'
    ">\n"
    '\t\t\t<Metadata name="Catalog.{tag}.Form" id="{child_id}"/>\n'
    "\t\t</Metadata>\n"
    "\t</ConfigVersions>\n"
    "</ConfigDumpInfo>\n"
)


def write_index(path, tag):
    """Положить в каталог непустой ConfigDumpInfo.xml (2 записи: корень + ребёнок)."""
    path.write_text(INDEX_XML_TEMPLATE.format(
        tag=tag,
        root_id=probe_uuid(),
        child_id=probe_uuid(),
        config_version=uuid_lib.uuid4().hex + uuid_lib.uuid4().hex[:8],
    ), encoding="utf-8")
    return path


def synth_catalog(dir_name, name_mode="empty", name_value=None, uuid_value=None,
                  with_index=True):
    """Копия фикстуры с правкой `<Name>` и непустым индексом состава.

    `Config_NULL` не проходит путь записи: её `ConfigDumpInfo.xml` пуст, и загрузчик
    держит отказ до транзакции (раздел 4). Копия отличается ровно двумя правками, и обе —
    предмет узлов V32/V33: пустой `<Name>` (имя берётся из имени каталога) и непустой индекс
    (маршрут записи в `configuration_objects`). Остальные байты файла — фикстура.
    """
    base = Path(tempfile.mkdtemp(prefix="ckb_v32_"))
    temp_dirs.append(base)
    catalog = base / dir_name
    catalog.mkdir()
    xml = catalog / "Configuration.xml"
    shutil.copy2(str(CONFIG_XML), str(xml))
    edit_xml(xml, [(f'<Configuration uuid="{FIXTURE_UUID}"',
                   f'<Configuration uuid="{uuid_value or probe_uuid()}"')])
    if name_mode == "empty":
        edit_xml(xml, [("<Name>Конфигурация</Name>", "<Name></Name>")])
    elif name_mode == "fixed":
        edit_xml(xml, [("<Name>Конфигурация</Name>", f"<Name>{name_value}</Name>")])
    if with_index:
        write_index(catalog / "ConfigDumpInfo.xml", f"{PROBE}{dir_name}")
    return catalog


def objects_rows(cfg_id):
    """Строки индекса состава данной конфигурации (сверка разбора и записи)."""
    return sql_rows(
        "SELECT name, parent_name, depth, object_type, object_id FROM configuration_objects "
        "WHERE configuration_id = %s ORDER BY depth, name", (cfg_id,))


# ─────────────── 4. фикстура Config_NULL: пустой индекс и граница узла V33 ───────────────

def check_null_fixture():
    """`Config_NULL` проверяется ровно на том объёме, который она пройти может."""
    section("ФИКСТУРА Config_NULL: индекс состава пуст — загрузка удержана до записи")
    if not check("фикстура на месте: Configuration.xml и ConfigDumpInfo.xml",
                 CONFIG_XML.is_file() and INDEX_XML.is_file(),
                 f"{CONFIG_XML} | {INDEX_XML}"):
        return
    before = db_counts()

    found = find_config_dump_info(str(CONFIG_CATALOG))
    check("индекс находится по месту в корне каталога (не вложенный файл)",
          found is not None and Path(found).name == "ConfigDumpInfo.xml", repr(found))

    parsed = parse_config_dump_info(str(INDEX_XML))
    check("пустой индекс — не «успех с нулём записей», а отказ с причиной",
          parsed.get("success") is False and "ни одной записи" in str(parsed.get("error")),
          repr(parsed)[:300])
    check("отказ парсера называет файл и не придумывает записей",
          "ConfigDumpInfo.xml" in str(parsed.get("error")) and not parsed.get("objects"),
          repr(parsed.get("error"))[:300])

    res = load_catalog(str(CONFIG_CATALOG))
    text = format_load_result(res)
    check("общая точка входа на пустом индексе — ❌ (заголовок не пишется)",
          res.get("status") == "error", text[:400])
    check("причина называет индекс состава, а не заголовок и не вариант загрузки",
          "Индекс состава не разобран" in str(res.get("error", "")),
          repr(res.get("error"))[:300])
    check("ответ начинается с ❌ и называет разобранный файл",
          text.startswith("❌") and "ConfigDumpInfo.xml" in text, text[:300])
    check("hint объясняет, что частичного индекса узел V33 не делает",
          "частично" in str(res.get("hint", "")), repr(res.get("hint"))[:300])
    check("отказ ничего не записал: снимок счётчиков не изменился",
          db_counts() == before, f"{before} -> {db_counts()}")
    check("отказ не оставил половины состава (решение принимается до транзакции)",
          not sql_rows("SELECT id FROM configurations WHERE uuid = %s::uuid",
                       (FIXTURE_UUID,)),
          repr(sql_rows("SELECT id FROM configurations WHERE uuid = %s::uuid",
                        (FIXTURE_UUID,))))
    check("отказ индекса не превращает каталог в «не подходит»: вариант читается",
          detect_load_variant(str(CONFIG_CATALOG)).get("variant") == VARIANT_CONFIGURATION,
          repr(detect_load_variant(str(CONFIG_CATALOG)))[:300])
    note("Граница узла V33: у Config_NULL пустой ConfigDumpInfo.xml, поэтому заголовок НЕ "
         "пишется — частичной конфигурации («заголовок есть, состава нет») модель не "
         "допускает. Путь записи проверяется на копии фикстуры с непустым индексом "
         "(раздел 5); сама фикстура остаётся проверкой разбора (раздел 3) и этой границы.")


# ─────────────── 5. копия фикстуры: путь записи заголовка и состава ───────────────

def check_load_path():
    """Маршрут записи: пустой `<Name>` → имя каталога, заголовок + `configuration_objects`."""
    section("ЗАГРУЗКА КОПИИ ФИКСТУРЫ: пустой <Name> и непустой индекс (маршрут записи)")
    catalog = synth_catalog("v32_cfg_a")
    before = db_counts()

    parsed = parse_configuration_meta(str(catalog / "Configuration.xml"))
    if not check("копия фикстуры разобрана (дальше строка БД сверяется с контрактом)",
                 parsed.get("success"), repr(parsed)[:300]):
        return
    contract = parsed["configuration"]

    res = load_catalog(str(catalog))
    text = format_load_result(res)
    cfg_id = int(res.get("id") or 0)
    cfg_uuid = res.get("uuid") or ""
    probe.update(cfg_id=cfg_id, cfg_uuid=cfg_uuid, cfg_catalog=catalog)

    check("исход ✅ загружено (status=loaded)", res.get("status") == "loaded", text[:400])
    check("пустой <Name>: имя заголовка взято из имени каталога выгрузки (правило V32)",
          res.get("name") == catalog.name, repr(res.get("name")))
    check("фолбэк имени назван предупреждением, а не подставлен молча",
          any("<Name> пуст" in w and catalog.name in w for w in res.get("warnings") or []),
          repr([w[:80] for w in res.get("warnings") or []][:4]))
    check("граница провенанса названа самим ответом, а не опущена (D-C)",
          any("Провенанс строки конфигурации не ведётся" in w
              for w in res.get("warnings") or []),
          repr([w[:80] for w in res.get("warnings") or []][:4]))
    check("uuid заголовка — атрибут элемента копии, а не uuid самой фикстуры",
          cfg_uuid == contract["uuid"] and cfg_uuid != FIXTURE_UUID,
          repr([cfg_uuid, contract.get("uuid"), FIXTURE_UUID]))

    check("карточка называет вариант «конфигурация» и таблицу configurations",
          "Тип: конфигурация (таблица configurations)" in text, text[:300])
    check("карточка НЕ печатает children-счётки внешнего объекта (их у конфигурации нет)",
          "Сохранено: реквизитов" not in text, text[:300])
    check("карточка называет индекс состава и число записанных строк (узел V33)",
          "Индекс состава (ConfigDumpInfo.xml): разобрано записей 2, "
          "записано в configuration_objects 2" in text, text[:400])
    check("карточка различает источники: <ChildObjects> не раскладываются, индекс — да",
          "Состав из <ChildObjects> Configuration.xml" in text
          and "таблиц объектов метаданных по ним в схеме нет" in text, text[:400])
    check("карточка печатает перечень незаполненных колонок, а не указатель вникуда",
          "не заполняется: app_module_id" in text
          and "check_configuration_inventory.sql" not in text, text[:400])

    row = sql_dict("SELECT * FROM configurations WHERE id = %s", (cfg_id,))
    if not check("строка заголовка создана и читается по id", bool(row), repr(cfg_id)):
        return
    # `name` сравнивается только когда <Name> непустой: пустой <Name> — предмет узла V32,
    # значение в БД даёт фолбэк (имя каталога), и его проверяет отдельная проверка ниже.
    # Молча исключить `name` из сравнения нельзя: тогда из контроля пропали бы все колонки,
    # а не только эта — исключение названо и ограничено условием.
    fallback_only = set() if contract.get("name") else {"name"}
    common = sorted((set(row) & set(contract)) - fallback_only)
    mismatch = [key for key in common
                if not ((contract[key] in (None, "", [], {})
                         and row[key] in (None, [], "", {}))
                        or contract[key] == row[key])]
    check("значения из разбора легли в те же колонки без изменений",
          not mismatch, repr(mismatch[:6]))
    if fallback_only:
        note("`name` исключён из сравнения осознанно: <Name> пуст, в БД значение даёт фолбэк "
             "(имя каталога) — его проверяет следующая проверка")
    check("ни один ключ контракта не остался без колонки (писатель не теряет значения)",
          not (set(contract) - set(row)), repr(sorted(set(contract) - set(row))))
    check("имя в БД равно имени каталога: фолбэк дошёл и до записи",
          row["name"] == catalog.name, repr(row.get("name")))
    check("колонки, не заполняемые осознанно, остались NULL, а не пустыми строками",
          all(row.get(column) is None for column in
              ("app_module_id", "session_module_id", "data_proc_module_id",
               "ext_conn_module_id", "mobile_functionality")),
          repr({column: row.get(column) for column in
                ("app_module_id", "mobile_functionality")}))
    check("с этим uuid ровно одна строка, с именем из каталога тоже одна (UNIQUE name)",
          sql_one("SELECT COUNT(*) FROM configurations WHERE uuid = %s::uuid",
                  (cfg_uuid,)) == 1
          and sql_one("SELECT COUNT(*) FROM configurations WHERE name = %s",
                      (catalog.name,)) == 1,
          repr([sql_one("SELECT COUNT(*) FROM configurations WHERE uuid = %s::uuid",
                        (cfg_uuid,)),
                sql_one("SELECT COUNT(*) FROM configurations WHERE name = %s",
                        (catalog.name,))]))

    index = parse_config_dump_info(str(catalog / "ConfigDumpInfo.xml"))
    total = (index.get("counts") or {}).get("entries_total", 0)
    rows = objects_rows(cfg_id)
    check("строк состава в БД ровно столько, сколько записей разобранного индекса",
          len(rows) == total == 2, f"бд={len(rows)} разбор={total}")
    check("корневая запись без родителя и с depth 0, дочерняя ссылается на неё (depth 1)",
          rows and rows[0][1] is None and rows[0][2] == 0
          and rows[1][1] == rows[0][0] and rows[1][2] == 1, repr(rows))
    check("тип метаданных разложен из имени, object_id совпадает с id из индекса",
          all(item[3] == "Catalog" for item in rows)
          and sorted(item[4] for item in rows)
          == sorted(entry["object_id"] for entry in index["objects"]),
          repr([(item[3], item[4]) for item in rows]))
    check("uuid записи состава заполнен, когда id индекса — канонический uuid",
          all(entry["uuid"] for entry in index["objects"])
          and sql_one("SELECT COUNT(*) FROM configuration_objects "
                      "WHERE configuration_id = %s AND uuid IS NOT NULL", (cfg_id,)) == 2,
          repr([entry.get("uuid") for entry in index["objects"]]))
    check("config_version сохранён там, где он был в файле, и только там",
          sql_one("SELECT COUNT(*) FROM configuration_objects WHERE configuration_id = %s "
                  "AND config_version IS NOT NULL", (cfg_id,)) == 1,
          repr(sql_one("SELECT config_version FROM configuration_objects "
                       "WHERE configuration_id = %s ORDER BY depth", (cfg_id,))))

    after = db_counts()
    untouched = ("config_extensions", "bsl_modules", "external_report", "bound")
    check("дочерние таблицы внешнего объекта не тронуты (у конфигурации их нет)",
          {key: after[key] for key in untouched} == {key: before[key] for key in untouched},
          repr([before, after]))
    check("прибавился ровно один заголовок и ровно строки состава, ничего лишнего",
          after["configurations"] == before["configurations"] + 1
          and after["configuration_objects"] == before["configuration_objects"] + total,
          repr([before, after]))


# ─────────── 6. ⚠️ уже загружено: карточка конфигурации, а не внешнего объекта ───────────

def check_duplicate():
    """R5: дубликат ищется по uuid; карточка обязана быть карточкой конфигурации."""
    cfg_id, cfg_uuid = probe["cfg_id"], probe["cfg_uuid"]
    catalog = probe["cfg_catalog"]
    section("ДУБЛИКАТ БЕЗ force (R5): ⚠️ уже загружено, карточка конфигурации")
    snapshot = header_snapshot(cfg_id)
    before = db_counts()

    res = load_catalog(str(catalog))
    text = format_load_result(res)
    check("повтор того же каталога — ⚠️ уже загружено, загрузка НЕ выполнена",
          res.get("status") == "duplicate" and text.startswith("⚠️"), text[:400])
    check("ответ говорит «конфигурация с UUID», а не общая формулировка внешнего объекта",
          "конфигурация с UUID" in text and "объект с UUID" not in text, text[:300])
    check("карточка показывает id, uuid, имя, версию и дату существующей строки",
          f"ID существующей записи: {cfg_id}" in text and cfg_uuid in text
          and "Дата загрузки:" in text and "Версия:" in text, text[:400])
    existing = res.get("existing") or {}
    check("числа привязок и связанных строк взяты из БД, а не выдуманы карточкой",
          f"Привязано внешних объектов: {existing.get('bound_external_objects')}" in text
          and f"Расширений в config_extensions: {existing.get('extensions_count')}" in text
          and f"BSL-модулей с configuration_id={cfg_id}" in text, text[:500])
    check("провенанс назван НЕ ведущимся (D-C), а не промолчан и не обещан",
          "Провенанс: для строк конфигурации НЕ ведётся" in text
          and "origin_*" in text, text[:500])
    check("не советует delete_external_report_tool: для конфигурации его нет (D-B)",
          "delete_external_report_tool" not in text
          and "Инструмента удаления конфигурации в контракте нет" in text, text[:500])
    check("подсказка force=True называет снимаемую запись и её расширения/модули",
          "force=True" in text and f"запись ID={cfg_id}" in text
          and "расширения и BSL-модули будут удалены" in text, text[:500])
    check("битые привязки после force названы заранее, до отказа (V20.1)",
          "числятся битыми до перепривязки" in text
          and "set_object_configuration_tool" in text, text[:500])

    copy = synth_catalog("v32_cfg_a_copy", name_mode="fixed", name_value=catalog.name,
                         uuid_value=cfg_uuid)
    res_copy = load_catalog(str(copy))
    check("дубликат ищется по uuid, а не по пути: другой каталог с тем же uuid — тоже ⚠️",
          res_copy.get("status") == "duplicate"
          and (res_copy.get("existing") or {}).get("id") == cfg_id,
          repr(res_copy)[:400])

    check("ничего не записано: ни новой строки, ни строк состава",
          db_counts() == before, f"{before} -> {db_counts()}")
    check("существующая строка заголовка не изменена ни в одной читаемой колонке",
          snapshot is not None and header_snapshot(cfg_id) == snapshot,
          repr([header_snapshot(cfg_id), snapshot]))


# ───────────── 7. ♻️ force=True: uuid тот же, id новый, состав перезаписан ─────────────

def check_force():
    """R4/R5: снятие и вставка — одна транзакция; связанные строки снимаются явно."""
    cfg_id, cfg_uuid = probe["cfg_id"], probe["cfg_uuid"]
    catalog = probe["cfg_catalog"]
    section("ПЕРЕЗАГРУЗКА force=True (R4/R5): ♻️, uuid тот же, id новый, состав заново")
    snapshot = header_snapshot(cfg_id)
    objects_before = objects_rows(cfg_id)
    before = db_counts()

    res = load_catalog(str(catalog), force=True)
    text = format_load_result(res)
    new_id = int(res.get("id") or 0)
    probe["cfg_id"] = new_id
    replaced = res.get("replaced") or {}

    check("исход ♻️ перезагружено (status=reloaded)", res.get("status") == "reloaded",
          text[:400])
    check("ответ называет снятую запись и счётчики снятия из ответа загрузчика",
          f"♻️ Удалена предыдущая запись ID={cfg_id}" in text
          and f"ID: {new_id}" in text, text[:400])
    check("old_id и old_uuid возвращены в структурированном ответе",
          replaced.get("old_id") == cfg_id and replaced.get("old_uuid") == cfg_uuid,
          repr(replaced)[:300])
    check("создана новая строка (id изменился), uuid объекта остался тем же",
          new_id != cfg_id and res.get("uuid") == cfg_uuid,
          repr([cfg_id, new_id, cfg_uuid, res.get("uuid")]))
    check("старая строка снята, с этим uuid ровно одна строка (дубля нет)",
          sql_one("SELECT COUNT(*) FROM configurations WHERE id = %s", (cfg_id,)) == 0
          and sql_one("SELECT COUNT(*) FROM configurations WHERE uuid = %s::uuid",
                      (cfg_uuid,)) == 1,
          repr([sql_one("SELECT COUNT(*) FROM configurations WHERE id = %s", (cfg_id,)),
                sql_one("SELECT COUNT(*) FROM configurations WHERE uuid = %s::uuid",
                        (cfg_uuid,))]))
    check("содержимое заголовка совпадает со снимком до перезагрузки (состав не разъехался)",
          snapshot is not None and header_snapshot(new_id) == snapshot,
          repr([header_snapshot(new_id), snapshot]))
    check("связанные строки сняты явно: состав, расширения и модули (каскада нет)",
          replaced.get("children_deleted", {}).get("configuration_objects")
          == len(objects_before)
          and replaced.get("children_deleted", {}).get("config_extensions") == 0
          and replaced.get("children_deleted", {}).get("bsl_modules") == 0,
          repr(replaced.get("children_deleted")))
    check("состав перезаписан под новым id, под старым id строк не осталось",
          len(objects_rows(new_id)) == len(objects_before)
          and objects_rows(cfg_id) == [],
          repr([len(objects_rows(new_id)), objects_rows(cfg_id)]))
    check("снимок состава побайтово тот же, что до перезагрузки",
          objects_rows(new_id) == objects_before,
          repr([objects_rows(new_id), objects_before]))
    check("число заголовков не выросло, строки состава не удвоились",
          db_counts()["configurations"] == before["configurations"]
          and db_counts()["configuration_objects"] == before["configuration_objects"],
          repr([before, db_counts()]))
    check("журнала попыток в схеме нет: история загрузок конфигурации не ведётся (D-C)",
          sql_one("SELECT to_regclass('public.config_load_log')") is None,
          repr(sql_one("SELECT to_regclass('public.config_load_log')")))
    note("Узел V19 (версионность строк) не реализован: force=True безвозвратен, прежнего "
         "состояния в базе не остаётся. Поэтому карточка ♻️ обязана назвать снятую запись — "
         "это единственное, что оператор видит после перезагрузки.")


# ────────────── 8. КОНФЛИКТ ИМЕНИ (F7): тот же name, другой uuid ──────────────

def check_name_conflict():
    """`name` уникален (`configurations_name_key`), дубликат ищется по uuid — отсюда исход."""
    cfg_id, cfg_uuid = probe["cfg_id"], probe["cfg_uuid"]
    catalog = probe["cfg_catalog"]
    section("КОНФЛИКТ ИМЕНИ (F7): тот же name при другом uuid — загрузка не выполнена")
    snapshot = header_snapshot(cfg_id)
    before = db_counts()
    other_uuid = probe_uuid()
    rival = synth_catalog("v32_cfg_rival", name_mode="fixed", name_value=catalog.name,
                          uuid_value=other_uuid)

    res = load_catalog(str(rival))
    text = format_load_result(res)
    check("тот же name и другой uuid — отдельный исход name_conflict, а не вторая строка",
          res.get("status") == "name_conflict" and text.startswith("❌"), text[:400])
    check("причина называет занятую строку (id и uuid) и UNIQUE (name)",
          f"id={cfg_id}" in str(res.get("error")) and cfg_uuid in str(res.get("error"))
          and "UNIQUE (name)" in str(res.get("error")), repr(res.get("error"))[:300])
    check("hint объясняет, почему force здесь не предлагается (сняли бы чужой заголовок)",
          "force=True здесь не предлагается" in str(res.get("hint", ""))
          and "чужой строки" in str(res.get("hint", "")), repr(res.get("hint"))[:300])
    # Проверяется отсутствие ПРЕДЛОЖЕНИЯ подтвердить перезагрузку, а не строки «force=True»:
    # карточка сама объясняет, почему force здесь не предлагается, — отрицание там обязано быть.
    # Прежняя проверка «force=True не встречается нигде» противоречила проверке hint выше.
    check("перезагрузка не предлагается: нет формулировки «Подтвердите перезагрузку»",
          "Подтвердите перезагрузку" not in text, text[:400])
    check("показана карточка занятой строки, включая границу провенанса",
          f"ID существующей записи: {cfg_id}" in text
          and "Провенанс: для строк конфигурации НЕ ведётся" in text, text[:500])
    check("названо действие: правка <Name> или снятие занявшей строки delete_configuration",
          "delete_configuration" in text and "<Name>" in text, text[:500])
    check("новая строка не создана: ни заголовка, ни строк состава",
          sql_one("SELECT COUNT(*) FROM configurations WHERE uuid = %s::uuid",
                  (other_uuid,)) == 0 and db_counts() == before,
          repr([before, db_counts()]))
    check("занятая строка не изменена: uuid, имя и содержимое прежние",
          snapshot is not None and header_snapshot(cfg_id) == snapshot,
          repr([header_snapshot(cfg_id), snapshot]))


# ─────────── 9. ДУБЛИ UUID: уникален name, а не uuid; дубль обязан быть назван ───────────

def check_uuid_duplicates():
    """D-D: уникальности по uuid нет — выборка обязана показать все строки, а не одну молча."""
    section("ДУБЛИ UUID В configurations (D-D): uuid не ключ, и это видно в ответе")
    dup_uuid = probe_uuid()
    first_id, first_name, _ = probe_header(f"{PROBE}dup_a", dup_uuid)
    second_id, second_name, _ = probe_header(f"{PROBE}dup_b", dup_uuid)

    found = find_configuration(dup_uuid)
    check("выборка по uuid отдаёт первую по id строку и ЧИСЛО строк с тем же uuid",
          isinstance(found, dict) and found.get("id") == first_id
          and found.get("duplicate_rows") == 2
          and set(found.get("duplicate_ids") or []) == {int(first_id), int(second_id)},
          repr(found)[:400])
    check("разные имена при одном uuid живут в таблице свободно (ключ — name, не uuid)",
          first_name != second_name
          and (find_configuration_by_name(first_name) or {}).get("id") == first_id
          and (find_configuration_by_name(second_name) or {}).get("id") == second_id,
          repr([first_name, second_name]))

    catalog = synth_catalog("v32_cfg_dupuuid", uuid_value=dup_uuid)
    res = load_catalog(str(catalog))
    text = format_load_result(res)
    check("каталог с занятым uuid — ⚠️ дубликат, а не третья строка с тем же uuid",
          res.get("status") == "duplicate", text[:400])
    check("карточка называет дубль: число строк с тем же uuid и их id (молчать нельзя)",
          "В таблице 2 строк с тем же uuid" in text
          and str(first_id) in text and str(second_id) in text, text[:500])
    check("строки дубля не созданы заново: их по-прежнему ровно две",
          sql_one("SELECT COUNT(*) FROM configurations WHERE uuid = %s::uuid",
                  (dup_uuid,)) == 2,
          repr(sql_one("SELECT COUNT(*) FROM configurations WHERE uuid = %s::uuid",
                       (dup_uuid,))))

    ext_uuid = sql_one("SELECT uuid::text FROM external_report ORDER BY id LIMIT 1")
    if not ext_uuid:
        note("В базе нет ни одного внешнего объекта: проверку «uuid совпадает с uuid "
             "внешнего объекта — это не конфликт» пропустить нечем (эталонная пара "
             "выгружена регрессом).")
    else:
        check("uuid внешнего объекта конфигурацией не считается: таблицы разные",
              find_configuration(ext_uuid) is None, repr(ext_uuid))
        same = synth_catalog("v32_cfg_shared_uuid", uuid_value=ext_uuid)
        res_same = load_catalog(str(same))
        check("тот же uuid у заголовка конфигурации и у внешнего объекта допустим: ✅",
              res_same.get("status") == "loaded", format_load_result(res_same)[:400])
        probe["cfg2_id"] = int(res_same.get("id") or 0)
        probe["cfg2_uuid"] = ext_uuid
        check("строки внешнего объекта при этом не тронуты",
              sql_one("SELECT COUNT(*) FROM external_report WHERE uuid = %s::uuid",
                      (ext_uuid,)) == 1, repr(ext_uuid))


# ───────── 10. ПРИВЯЗКИ ВНЕШНИХ ОБЪЕКТОВ: снятие заголовка делает их битыми ─────────

def check_bindings():
    """V20.1: внешнего ключа нет — состояние читается при чтении и называется прямо."""
    cfg_id = probe["cfg_id"]
    section("ПРИВЯЗКИ ВНЕШНИХ ОБЪЕКТОВ: force и снятие заголовка делают ссылку битой")
    if not NULL_REPORT.exists():
        check("эталон внешнего объекта для проверки привязок на месте", False,
              str(NULL_REPORT))
        return
    res = load_catalog(str(NULL_REPORT))
    if res.get("status") == "duplicate":
        ext_id = (res.get("existing") or {}).get("id")
        ext_uuid = (res.get("existing") or {}).get("uuid")
        note("Test3_Otchet_Null уже был в базе — проверка привязок идёт по существующей "
             f"строке id={ext_id}, она будет снята при уборке.")
    else:
        ext_id, ext_uuid = res.get("id"), res.get("uuid")
    if not check("внешний объект для проверки привязок загружен", bool(ext_uuid),
                 format_load_result(res)[:300]):
        return
    probe.update(ext_id=ext_id, ext_uuid=ext_uuid)

    bind = set_object_configuration(uuid=ext_uuid, configuration_id=cfg_id)
    check("привязку заявляет только оператор: инструмент принимает id существующего заголовка",
          bind.get("success") and bind.get("mode") == "bound"
          and bind.get("configuration_state") == "bound"
          and bind.get("configuration_id") == cfg_id, repr(bind)[:300])
    check("имя заголовка разрешается живым JOIN'ом, снимка имени не заводится",
          bind.get("configuration_name") == probe["cfg_catalog"].name,
          repr([bind.get("configuration_name"), probe["cfg_catalog"].name]))
    check("несуществующий id отклоняется, привязка при этом не меняется",
          set_object_configuration(uuid=ext_uuid, configuration_id=999999999).get("success")
          is False and sql_one("SELECT configuration_id FROM external_report "
                               "WHERE uuid = %s::uuid", (ext_uuid,)) == cfg_id,
          repr(sql_one("SELECT configuration_id FROM external_report WHERE uuid = %s::uuid",
                       (ext_uuid,))))

    card = describe_object(uuid=ext_uuid, limit=0)
    check("карточка объекта называет состояние привязки bound и разрешает заголовок",
          ((card.get("object") or {}).get("configuration_state") == "bound"
           and (card.get("object") or {}).get("configuration_id") == cfg_id),
          repr({key: (card.get("object") or {}).get(key)
                for key in ("configuration_state", "configuration_id",
                            "configuration_name")}))

    dup = format_load_result(load_catalog(str(probe["cfg_catalog"])))
    check("карточка дубликата показывает число привязанных внешних объектов (живой счёт)",
          "Привязано внешних объектов: 1" in dup, dup[:500])
    check("связь видна и в БД, и в перечне привязок заголовка",
          [row["id"] for row in bound_external_objects(cfg_id)] == [ext_id],
          repr(bound_external_objects(cfg_id)))

    force = load_catalog(str(probe["cfg_catalog"]), force=True)
    force_text = format_load_result(force)
    new_id = int(force.get("id") or 0)
    old_id = probe["cfg_id"]
    probe["cfg_id"] = new_id
    check("после force=True карточка предупреждает: привязка станет битой и называет объект",
          f"⚠️ Привязка к конфигурации станет битой: привязано внешних объектов 1"
          in force_text and str(ext_id) in force_text, force_text[:600])
    check("там же назван инструмент перепривязки и новый id заголовка",
          "set_object_configuration_tool" in force_text
          and f"configuration_id={new_id}" in force_text, force_text[:600])
    check("число и имена привязок взяты из ответа загрузчика, а не выдуманы карточкой",
          (force.get("replaced") or {}).get("bound_external_objects") == 1
          and probe["cfg_catalog"].name not in str(
              (force.get("replaced") or {}).get("bound_external_object_names")),
          repr((force.get("replaced") or {}).get("bound_external_object_names")))
    card_after = describe_object(uuid=ext_uuid, limit=0)
    check("после снятия строки состояние читается как dangling, а не как «не заявлена»",
          (card_after.get("object") or {}).get("configuration_state") == "dangling",
          repr((card_after.get("object") or {}).get("configuration_state")))
    check("число привязок после force не изменилось: осталась та же строка с битым id",
          sql_one("SELECT configuration_id FROM external_report WHERE uuid = %s::uuid",
                  (ext_uuid,)) == old_id,
          repr(sql_one("SELECT configuration_id FROM external_report WHERE uuid = %s::uuid",
                       (ext_uuid,))))

    cleared = set_object_configuration(uuid=ext_uuid, configuration_id=None)
    check("привязка снимается тем же инструментом: состояние снова not_declared",
          cleared.get("success") and cleared.get("mode") == "cleared"
          and cleared.get("configuration_state") == "not_declared", repr(cleared)[:300])
    check("после снятия поле NULL, а не ноль или пустая строка",
          sql_one("SELECT configuration_id FROM external_report WHERE uuid = %s::uuid",
                  (ext_uuid,)) is None,
          repr(sql_one("SELECT configuration_id FROM external_report WHERE uuid = %s::uuid",
                       (ext_uuid,))))
    note("Состояния ровно три: not_declared / bound / dangling. Состояния «универсальный» "
         "в модели нет, и ни один ответ его не выдаёт — это проверяет регресс V20.1 "
         "(tools/check_v20_config_link.py), здесь проверяется связь с заголовком V32.")


# ─────── 11. ГОТОВНОСТЬ ЭКСПОРТА: таблица V33 больше не отсутствует, V18 не снят ───────

def check_readiness():
    """Ответ берётся живым сервером экспорта: пересказывать его правилами нельзя."""
    section("ГОТОВНОСТЬ ЭКСПОРТА: configuration_objects есть (V33), сценарий V18 не реализован")
    try:
        sys.path.insert(0, str(ROOT))
        from server_configurations_export import (REQUIRED_TABLES,  # noqa: E402
                                                  export_readiness_tool)
    except Exception as exc:
        check("сервер экспорта импортируется: ответ проверяется живым кодом, а не пересказом",
              False, str(exc))
        return
    text = export_readiness_tool()
    configs = sql_one("SELECT COUNT(*) FROM configurations")
    reports = sql_one("SELECT COUNT(*) FROM external_report")
    missing_line = next((line for line in text.splitlines()
                         if line.startswith("Отсутствующие таблицы:")), "")

    check("готовность отдаётся живым инструментом и честно говорит об отказе сценария",
          text.startswith("❌") and "не реализован" in text, text[:300])
    check("configuration_objects больше НЕ среди отсутствующих таблиц (её создал V33)",
          "configuration_objects" not in missing_line, repr(missing_line))
    check("отсутствующие таблицы V18 названы прямым списком, а не выдумкой",
          "modified_objects" in missing_line and "config_export_log" in missing_line,
          repr(missing_line))
    check("список отсутствующих совпадает с REQUIRED_TABLES сервера и живой схемой",
          [table for table in REQUIRED_TABLES if table in missing_line]
          == ["modified_objects", "config_export_log"], repr([REQUIRED_TABLES, missing_line]))
    check("числа конфигураций и внешних объектов в ответе соответствуют живой БД",
          f"строк {configs}" in text and f"внешних объектов в базе: {reports}" in text,
          repr([configs, reports, text[:300]]))
    check("прежний отказ «нет ни одной строки» не возвращается: конфигурация в базе есть",
          configs > 0 and "нет ни одной строки" not in text, repr([configs, text[:300]]))
    check("текст называет, что нужно для V18, и куда идти за загрузкой и обогащением",
          "узел V18" in text and "load_1c_catalog_tool" in text
          and "1c-configurations-enrichment" in text, text[:700])
    note("Узел V33 создал configuration_objects — первую таблицу объектов конфигурации. "
         "Экспорт (V18) от этого не становится: нужны ещё отслеживание изменений и сборка "
         "XML; сервер называет недостающее списком, а не общим обещанием.")


# ───────────────────── 12. УБОРКА: инструмент снимает всё своё ─────────────────────

def cleanup_rows():
    """Снять строки, которые создал прогон (работает и при --only, и после него)."""
    for key in ("cfg_id", "cfg2_id"):
        cfg_id = probe.get(key)
        if cfg_id:
            delete_configuration(cfg_id=cfg_id)
    for header_id in state.get("probe_headers", []):
        sql_write("DELETE FROM configurations WHERE id = %s", (header_id,))
    if probe.get("ext_uuid"):
        delete_external_object(uuid_val=probe["ext_uuid"], obj_type="external_report")


def check_cleanup():
    """Удаление — инструмент, а не SQL: и счётчики снятого, и возврат к базовой линии."""
    section("УБОРКА: delete_configuration снимает заголовок и состав, чужое не трогает")
    baseline = probe["baseline"]
    cfg_id, cfg_uuid = probe["cfg_id"], probe["cfg_uuid"]
    objects_before = len(objects_rows(cfg_id))

    res = delete_configuration(cfg_id=cfg_id)
    check("заголовок снимается инструментом (success, а не not_found)",
          res.get("success") and res.get("id") == cfg_id, repr(res)[:300])
    check("состав снимается вместе с заголовком, число взято из children_deleted",
          res.get("children_deleted", {}).get("configuration_objects") == objects_before
          and objects_rows(cfg_id) == [], repr(res.get("children_deleted")))
    check("расширений и модулей у прогона не было — снято ровно то, что было",
          res.get("children_deleted", {}).get("config_extensions") == 0
          and res.get("children_deleted", {}).get("bsl_modules") == 0,
          repr(res.get("children_deleted")))
    again = delete_configuration(cfg_id=cfg_id)
    check("повторное удаление отвечает «строка не найдена», а не молчит",
          again.get("success") is False and "не найдена" in str(again.get("error")),
          repr(again)[:300])
    check("по uuid прогона строк не осталось",
          sql_one("SELECT COUNT(*) FROM configurations WHERE uuid = %s::uuid",
                  (cfg_uuid,)) == 0,
          repr(sql_one("SELECT COUNT(*) FROM configurations WHERE uuid = %s::uuid",
                       (cfg_uuid,))))

    cleanup_rows()
    after = db_counts()
    check("после уборки счётники всех затронутых таблиц равны началу прогона",
          after == baseline, repr([baseline, after]))
    check("сирот состава нет: таблица состава привязана к живым заголовкам",
          sql_one("SELECT COUNT(*) FROM configuration_objects o LEFT JOIN "
                  "configurations c ON c.id = o.configuration_id WHERE c.id IS NULL") == 0,
          repr(sql_one("SELECT COUNT(*) FROM configuration_objects o LEFT JOIN "
                       "configurations c ON c.id = o.configuration_id WHERE c.id IS NULL")))
    check("тестовых заголовков прогона в справочнике не осталось",
          sql_one("SELECT COUNT(*) FROM configurations WHERE name LIKE %s",
                  (PROBE + "%",)) == 0,
          repr(sql_one("SELECT COUNT(*) FROM configurations WHERE name LIKE %s",
                       (PROBE + "%",))))


# ───────────────────────────── порядок прогонов и запуск ─────────────────────────────

# Зависимости перечислены здесь, а не внутри разделов: раздел 5 создаёт заголовок пробы,
# из которого растут 6-8 и 10-12. Без зависимости `--only force` проверял бы чужое
# состояние, а не своё, и прошёл бы «зелёным» на пустой базе.
# Порядок списка — порядок выполнения: раздел 11 читает строку пробы, раздел 12 её снимает
# и сверяет возврат к базовой линии, поэтому 12 обязан идти последним.
SECTIONS = [
    ("schema", "1. схема", check_schema, ()),
    ("detection", "2. детекция варианта (R1)", check_detection, ()),
    ("parser", "3. разбор Configuration.xml", check_parser, ()),
    ("parser-negatives", "3b. отказ разбора с причиной", check_parser_negatives, ()),
    ("null-index", "4. фикстура Config_NULL: пустой индекс", check_null_fixture, ()),
    ("load", "5. загрузка копии: путь записи", check_load_path, ()),
    ("duplicate", "6. дубликат без force (R5)", check_duplicate, ("load",)),
    ("force", "7. перезагрузка force=True", check_force, ("load",)),
    ("name-conflict", "8. конфликт имени (F7)", check_name_conflict, ("load",)),
    ("uuid-duplicates", "9. дубли uuid (D-D)", check_uuid_duplicates, ()),
    ("bindings", "10. привязки внешних объектов (V20.1)", check_bindings, ("load",)),
    ("readiness", "11. готовность экспорта (V18/V33)", check_readiness, ("load",)),
    ("cleanup", "12. уборка: delete_configuration", check_cleanup, ("load",)),
]
SECTION_INDEX = {key: (title, func, deps) for key, title, func, deps in SECTIONS}


def resolve_sections(requested):
    """Запрошенные разделы вместе с зависимостями — в порядке SECTIONS.

    Разрешены обе формы: повторяемый `--only КЛЮЧ` и список через запятую
    (`--only load,force`) — первая описана в `--help`, вторую ожидают в shell-строках;
    отказать во второй, когда первая есть, было бы произволом.

    Зависимости снимаются транзитивно (`bindings` тянет `load`). Неизвестное имя раздела
    отвечает None: выполнить половину запроса молча — тот же самообман, что и пропустить
    раздел.
    """
    if not requested:
        return [key for key, _, _, _ in SECTIONS]
    keys = [part.strip() for value in requested for part in value.split(",")]
    keys = [key for key in keys if key]
    if not keys:
        return None
    wanted, pending = set(), list(keys)
    while pending:
        key = pending.pop()
        if key not in SECTION_INDEX:
            return None
        if key in wanted:
            continue
        wanted.add(key)
        pending.extend(SECTION_INDEX[key][2])
    return [key for key, _, _, _ in SECTIONS if key in wanted]


def print_sections():
    print("Разделы (ключ — параметр --only; требует — что будет дотянуто автоматически):")
    for key, title, _, deps in SECTIONS:
        print(f"  {key:<16} {title}"
              + (f"   требует: {', '.join(deps)}" if deps else ""))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="tools/check_v32_zero_configuration.py",
        description="Регрессия узлов V32/V33: нулевая конфигурация и загрузка "
                    "индекса состава в configuration_objects")
    parser.add_argument("--list", action="store_true", help="перечислить разделы и выйти")
    parser.add_argument("--only", action="append", default=[], metavar="КЛЮЧ",
                        help="запустить раздел и его зависимости; параметр повторяется "
                             "или принимает список КЛЮЧЕЙ через запятую")
    parser.add_argument("--keep", action="store_true",
                        help="оставить тестовые каталоги и строки БД (по умолчанию снимаются)")
    args = parser.parse_args(argv)

    if args.list:
        print_sections()
        return 0

    keys = resolve_sections(args.only)
    if keys is None:
        print("❌ Неизвестный раздел. Доступны:")
        print_sections()
        return 2

    # Снимок «до» берётся до первой записи и всегда: раздел 12 сверяет им возврат к
    # базовой линии, а прогон без снимка оставил бы после себя непонятно что.
    probe["baseline"] = db_counts()
    print("=" * 72)
    print("БАЗОВАЯ ЛИНИЯ (до прогона): " + ", ".join(
        f"{key}={probe['baseline'][key]}" for key in probe["baseline"]))
    print(f"Разделов к прогону: {len(keys)} из {len(SECTIONS)}"
          + (f" (запрошены: {', '.join(args.only)})" if args.only else " (полный прогон)"))

    try:
        for key in keys:
            _, func, _ = SECTION_INDEX[key]
            before = len(failures)
            func()
            if len(failures) > before:
                print(f"--- раздел {key}: провалено проверок {len(failures) - before} ---")
    finally:
        # Уборка за собой и при провале раздела: оставленные строки превращают следующий
        # прогон в проверку дубликата вместо чистого кейса (раздел 6 читает чужое).
        # `--keep` — единственный случай, когда строки остаются намеренно.
        if args.keep:
            print(f"Сохранено (--keep): каталогов {len(temp_dirs)}, "
                  f"строки БД не снимались")
        else:
            cleanup_rows()
            for path in temp_dirs:
                shutil.rmtree(str(path), ignore_errors=True)
            del temp_dirs[:]

    print()
    print("=" * 72)
    print(f"ИТОГ: проверок {counters['checks']}, провалено {len(failures)}")
    if failures:
        for name in failures:
            print(f"  FAIL: {name}")
        print("Результат: ЕСТЬ РАСХОЖДЕНИЯ")
        return 1
    print("Результат: расхождений нет")
    return 0


if __name__ == "__main__":
    sys.exit(main())



