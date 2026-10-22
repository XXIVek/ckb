#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/check_v32_zero_configuration.py — проверка узла V32: «нулевая» конфигурация.

Эталон: C:\1C_LLM\LoadDoc\Configurations\XML_files\Config_NULL — Configuration.xml без объектов
метаданных кроме Language и без модулей. Внешний объект для проверки привязок —
Test3_Otchet_Null; эталонная пара (Test1_Otchet, Test2_Otchet) не трогается.

Что проверяется и почему именно так:
  1. схема: `configurations` живая; колонок провенанса, версионирования и таблиц объектов
     метаданных узел V32 НЕ добавлял (решения D-C и D-D); UNIQUE по имени есть, уникальности
     по uuid нет; ссылки `config_extensions`/`bsl_modules` на заголовок сохранены, а
     `external_report.configuration_id` по-прежнему БЕЗ внешнего ключа (узел V20.1).
     Узел V42 (21.10.2026) снял пять колонок заголовка — `app_module_id`, `session_module_id`,
     `data_proc_module_id`, `ext_conn_module_id`, `mobile_functionality` (свойств
     предопределённых модулей в `<Properties>` нет, а `TEXT[]` терял признак `use`), поэтому
     раздел держит обе стороны: множество колонок V32 без снятых обязано быть на месте, а
     снятые колонки обязаны ОТСУТСТВОВАТЬ — их возврат считается регрессией.
     Узел V43 (22.10.2026) добавил 48 колонок-перечней `TEXT[]` — дочерние свойства
     конфигурации, значение которых даёт индекс состава, а НЕ `<Properties>` корня. Имена и
     порядок этих колонок задаёт единственный словарь `src/configuration_child_properties.py`,
     поэтому раздел читает ожидаемый состав из него, а не из переписанного руками списка:
     48 имён в трёх местах порознь обязательно разъехались бы. Колонок-перечней в таблице
     при этом ровно 49 — 48 узла V43 плюс `main_roles` узла V32 (свойство DefaultRoles);
  2. детекция (R1): Configuration.xml даёт вариант `configuration`; тот же файл с
     `ConfigurationExtensionPurpose` — вариант `extension`, который остаётся заглушкой (R7);
     вложенный Configuration.xml не читается; внешний отчёт не уехал в конфигурацию;
  3. разбор: uuid из атрибута элемента (R3), свойства в колонки, ссылочные значения
     развёрнуты в ИМЯ (Language.Русский → Русский), пустой синоним — NULL (D-D), слепые зоны
     названы прямо (ChildObjects/Language, InternalInfo корня с версиями UUID v1/v4).
     По свойствам корня слепая зона закрыта узлом V42: словарь `CONFIGURATION_FIELDS`
     покрывает все 55 свойств измеренных выгрузок, поэтому раздел требует противоположного
     прежнему — перечень свойств без колонки обязан быть ПУСТЫМ, а четыре свойства, которые
     до V42 назывались слепыми зонами, обязаны читаться в свои колонки. Механизм называния
     слепых зон при этом остаётся живым и проверяется разделом 3c на свойстве, которого в
     словаре нет. `UsedMobileApplicationFunctionalities` с V42 кладётся в jsonb парами
     `functionality`/`use` (прежняя `mobile_functionality TEXT[]` признак `use` теряла);
     пустой или некорректный uuid — отказ с причиной;
  3c. перечень ссылок (дефект разбора `DefaultRoles`, 20.10.2026): детьми перечисных свойств
      бывают и `<v8:Value>` (UsePurposes), и `<xr:Item xsi:type="xr:MDObjectRef">`
      (DefaultRoles) — измеряется по восьми выгрузкам. Разбор обязан читать обе формы,
      снимать префикс вида (`Role.Х` → `Х`), сохранять порядок и не молчать о детях
      неизвестной формы (пустая колонка называется предупреждением); `_has_value` по детям
      `Item` не считает заполненное свойство пустой слепой зоной — после V42 каждое
      измеренное свойство имеет колонку, поэтому механизм проверяется на синтетическом
      свойстве, которого в словаре нет; роль доходит до колонки `main_roles` (TEXT[]) и
      убирается за собой;
  3d. многоязычные свойства заголовка (узел V39, 21.10.2026): шесть свойств — Synonym,
      BriefInformation, DetailedInformation, Copyright, VendorInformationAddress,
      ConfigurationInformationAddress — читаются словарём `{язык: текст}` и пишутся в колонки
      JSONB. До узла доходило ноль из шести значений: пять колонок оставались NULL (разбор
      звал `_text()` на составном `v8:item`), в `synonym` выживал один язык. Проверка держит:
      тип шести колонок jsonb и НЕ переведённые границы (`UpdateCatalogAddress` — простой
      текст по замеру восьми выгрузок, `config_extensions.synonym` — загрузчика расширения
      нет, R7), отсутствие отдельных колонок под язык; словарь по каждому из шести свойств
      без потерь; «значения нет» (NULL) отделено от «значение пустое» (пустой элемент и
      `v8:item` с пустым `v8:content` дают NULL, а не `{}`); ключ `ru` при значении без
      `v8:item` называется неподтверждённым; лимит текстовой колонки остаётся отказом, а
      jsonb-колонка принимает длинное значение целиком; повторное применение миграции ничего
      не меняет, а `'und'` (переходное состояние строк до V39) читается, пока остался в
      строке, и снимается первой же перезагрузкой каталога;
       Узел закрывает НЕ «в выгрузках два языка», а контракт формата: `v8:item` допускает
       любое число пар `v8:lang`/`v8:content`, а текстовая колонка физически держит одну
       форму. Замер восьми выгрузок (`python tools/measure_multilang_properties.py`) называет
       границы честно: элемент есть во всех восьми, заполнен `v8:item` у шести-семи (Synonym —
       7, остальные пять — по 6), языки везде одни и те же — `ru`, строк с двумя и более
       языками — 0, пустого `v8:lang` — 0, текста без `v8:item` — 0. `UpdateCatalogAddress`
       при этом даёт простой текст (заполнен у 6, `v8:item` — ни у одной), поэтому его колонка
       осталась текстовой. То есть в наших выгрузках потеря второй формы невидима: она
       наступает вместе с первой многоязычной конфигурацией, а цена её — молчаливое
       исчезновение формы, которой в колонке не места.


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
import re
import shutil
import sys
import tempfile
import uuid as uuid_lib
import xml.etree.ElementTree as ET
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
from configuration_child_properties import (CHILD_COUNT, CHILD_OBJECT_TYPES,  # noqa: E402
                                           COLUMN_BY_OBJECT_TYPE,
                                           collect_header_arrays,
                                           header_array_columns)
from configuration_loader import (TABLE, bound_external_objects,  # noqa: E402
                                  delete_configuration, find_configuration,
                                  find_configuration_by_name, find_configuration_xml,
                                  register_configuration)
from configuration_meta_parser import (CONFIGURATION_FIELDS, LIST_CHILD_TAGS,  # noqa: E402
                                      NOT_FILLED_COLUMNS,
                                      _has_value, _list_children, _ref_list,
                                      parse_configuration_meta)
from enrichment_generator import (describe_object, generate_enrichment,  # noqa: E402
                                 set_object_configuration)
from enrichment_snippets import enrichment_stats  # noqa: E402
from external_db import connect  # noqa: E402
from external_report_loader import delete_external_object  # noqa: E402

BASE = Path(r"C:\1C_LLM\LoadDoc")
# С 18.10.2026 XML-выгрузки конфигураций консолидованы в Configurations\XML_files\<имя>,
# файлы .cf — в Configurations\. Внешние объекты (Test*, TSD_*) остаются в корне LoadDoc.
CONFIG_CATALOG = BASE / "Configurations" / "XML_files" / "Config_NULL"
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

# ─── многоязычные свойства заголовка (узел V39, 21.10.2026) ───
#
# Узел V39 (21.10.2026). Замер 20.10.2026 по восьми XML-выгрузкам (BGU2, BP3, KomMag, UNF3, UT11, ZUP31,
# Config_NULL, MinCfg): шесть свойств корня заполнены у шести из восьми и ВСЕГДА имеют форму
# `v8:item / v8:lang / v8:content` — значений без `v8:item` проход по файлам не дал ни одного.
# В текстовой колонке такой словарь необратим: пять колонок оставались NULL при заполненных
# значениях (разбор звал `_text()` на составном элементе — дефект, названный слоем знаний
# `property-configuration-development`), а в `synonym` выживал один язык. Словарь `{язык: текст}`
# и тип jsonb — тот же контракт, которым шесть писателей внешнего объекта пишут `synonym` с узла
# V12; отдельной колонки под язык нет: язык — часть значения, а не отдельный факт.
MULTILANG_COLUMNS = {
    "synonym": "Synonym",
    "short_info": "BriefInformation",
    "detailed_info": "DetailedInformation",
    "copyright": "Copyright",
    "vendor_url": "VendorInformationAddress",
    "config_url": "ConfigurationInformationAddress",
}
# Границы узла по тому же замеру восьми выгрузок. Свойства дают в выгрузке простой текст —
# вложенности `v8:item` в них нет, поэтому колонки остаются текстовыми и лимит длины у них
# остаётся. `config_extensions.synonym` — по другой причине: загрузчика расширения нет (правило
# R7, `config_extensions` пуста), менять тип нечем и проверять нечем — граница названа, а не
# промолчана.
SIMPLE_TEXT_COLUMNS = {
    "update_url": "UpdateCatalogAddress",
    "vendor_name": "Vendor",
    "version": "Version",
    "comment": "Comment",
    "default_language": "DefaultLanguage",
}
TEXT_TYPES = {"text", "character varying", "varchar"}
# Длинное языковое значение: раньше оно упиралось в лимит текстовой колонки (varchar(500) у
# update_url / vendor_url / config_url). 1200 символов — больше любого из этих лимитов; у jsonb
# лимита нет, и проверка называет это прямым запросом.
LONG_TEXT_LEN = 1200
DDL_BOOTSTRAP = ROOT / "create_1c_configurations_db.sql"
V39_MIGRATION = ROOT / "migrate_v39_multilang_configuration_text.sql"

# ─── узел V42 (21.10.2026): словарь свойств корня замкнут ───
#
# Основание — слой знаний `property-profile-configuration` (замер 55 свойств по восьми
# выгрузкам). До V42 `CONFIGURATION_FIELDS` знал 22 свойства из 55: 33 свойства назывались
# слепой зоной, а пять колонок (`app_module_id`, `session_module_id`, `data_proc_module_id`,
# `ext_conn_module_id`, `mobile_functionality`) не имели источника — свойств предопределённых
# модулей в `Configuration.xml` нет вовсе (замер: `ChildObjects` даёт только `Language`), и
# `UsedMobileApplicationFunctionalities` писался в `TEXT[]` с потерей признака `use`.
# С узла V42: словарь покрывает все 55 свойств (проверка «словарь = число свойств фикстуры»
# ниже), пять колонок сняты `migrate_v42_configuration_header_fields.sql`, признаки мобильного
# интерфейса лежат в jsonb парами `{"functionality": …, "use": "true"|"false"}`.
V42_MIGRATION = ROOT / "migrate_v42_configuration_header_fields.sql"
V42_REMOVED_COLUMNS = (
    "app_module_id", "session_module_id", "data_proc_module_id",
    "ext_conn_module_id", "mobile_functionality",
)
# Состав таблицы заголовка по живой схеме — замер 21.10.2026 (`information_schema.columns`,
# только схема public): 59 колонок, из них 13 jsonb (шесть языковых V39 + семь списочных V42),
# 3 boolean, остальные — текст/uuid/число/метки времени. Список назван здесь, потому что
# раздел 1 обязан ловить и снятие колонок: живая схема без `app_module_id` — это другой
# контракт, а не «то же самое». Полноту схемы целиком сторожит `python _cmp_ddl.py`.
CONFIGURATION_COLUMNS_V42 = {
    # ключ и идентификация
    "id", "name", "synonym", "comment", "version", "vendor_name", "uuid",
    # свойства, существовавшие до V42 (имена не менялись)
    "main_mode", "usage_purpose", "embedded_language", "main_roles",
    "default_language", "short_info", "detailed_info", "copyright", "vendor_url",
    "config_url", "update_url", "help_included", "lock_mode_default", "modality_mode",
    "ext_comp_sync_mode", "interface_compat_mode", "compatibility_mode",
    "created_at", "updated_at",
    # слоты V42: свойства, которые раньше назывались слепой зоной
    "configuration_extension_compatibility_mode", "database_tablespaces_use_mode",
    "main_client_application_window_mode", "object_autonumeration_mode",
    "use_managed_form_in_ordinary_application", "use_ordinary_form_in_managed_application",
    "mobile_application_functionalities", "allowed_incoming_share_request_types",
    "common_settings_storage", "reports_variants_storage",
    "reports_user_settings_storage", "form_data_settings_storage",
    "dynamic_lists_user_settings_storage", "default_report_form",
    "default_report_variant_form", "default_report_settings_form", "default_style",
    "default_interface", "default_constants_form", "default_search_form",
    "default_dynamic_list_settings_form",
    "default_collaboration_system_users_choice_form",
    "default_data_history_change_history_form",
    "default_data_history_version_data_form",
    "default_data_history_version_differences_form",
    "default_report_appearance_template", "url_external_data_storage", "name_prefix",
    "mobile_application_urls", "required_mobile_application_permissions",
    "standalone_configuration_restriction_roles",
    "additional_full_text_search_dictionaries", "content",
}
# Число свойств корня по замеру восьми выгрузок (слой `property-profile-configuration`):
# словарь обязан покрывать ровно столько же, иначе закрытая слепая зона — иллюзия.
ROOT_PROPERTIES_MEASURED = 55
# Списочные jsonb-колонки узла V42 (значение — массив записей или qualified-имя): тип
# проверяется по живой схеме, а не по памяти: смена типа без миграции — тот дефект,
# который V39 лечил.
V42_JSONB_COLUMNS = (
    "mobile_application_functionalities", "allowed_incoming_share_request_types",
    "mobile_application_urls", "required_mobile_application_permissions",
    "standalone_configuration_restriction_roles",
    "additional_full_text_search_dictionaries", "content",
)
# jsonb-колонки V39 (многоязычные) — их тип проверяет раздел 3d; здесь они нужны, чтобы
# посчитать jsonb-состав таблицы целиком и не спорить с самим собой.
V39_JSONB_COLUMNS = tuple(MULTILANG_COLUMNS)
# Логические свойства корня (замер: `true`/`false` токеном) — колонка boolean, а не текст:
# «истина» и «ложь» в текстовой колонке различимы только по строке, а пустое значение
# сливается с `false`.
V42_BOOLEAN_COLUMNS = (
    "use_managed_form_in_ordinary_application",
    "use_ordinary_form_in_managed_application",
)

# ─── узел V43 (22.10.2026): 48 дочерних свойств — массивы имён объектов ───
#
# Основание — файл оператора «Дочерние свойства для конфигурации.txt» (48 свойств, каждое —
# «список значений, тип строка макс. 80») и замер живой БД (`_child_arrays_probe.sql`,
# 274 141 строка индекса): K1 — на `depth = 0` индекс отдаёт ровно 48 видов файла плюс
# `Configuration`; K3 — граница 80 достигнута, строк длиннее 0; K4 — дублей имени внутри
# вида 0; K5 — `DocumentNumerator`/`Sequence` индекс моделирует ВЕРХНИМИ записями.
# Имена и порядок колонок задаёт единственный словарь `src/configuration_child_properties.py`,
# поэтому ожидаемый состав таблицы читается здесь из него, а не переписан руками: 48 имён,
# разложенных по трём местам порознь, обязательно разъезжаются (тот же класс дефекта, что
# собственный `max(revision_no)` в модуле-вызывателе до узла V19).
V43_MIGRATION = ROOT / "migrate_v43_configuration_child_arrays.sql"
V43_CHILD_COLUMNS = tuple(header_array_columns())
# Состав таблицы после V43 = состав V42 + 48 перечней. Множество V42 сохранено как замер
# своего дня: раздел обязан ловить и возврат снятых V42-колонок, и пропажу любого перечня V43.
CONFIGURATION_COLUMNS_V43 = CONFIGURATION_COLUMNS_V42 | set(V43_CHILD_COLUMNS)
# Единственный перечень, появившийся до V43: `main_roles` (свойство `DefaultRoles`, узел V32).
# Число ARRAY-колонок в таблице потому 49, а не 48 — и это названо, а не округлено.
PRE_V43_ARRAY_COLUMNS = ("main_roles",)


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


def try_text_update(cfg_id, column, value):
    """Попытка записать текст в колонку: None при успехе, текст ошибки при отказе.

    Нужна там, где отказ — ожидаемый ответ (лимит текстовой колонки): sql_write фиксирует
    ошибку как провал проверки, а здесь ошибка и есть предмет проверки.
    """
    conn = None
    try:
        conn = connect()
        cur = conn.cursor()
        cur.execute(f"UPDATE {TABLE} SET {column} = %s WHERE id = %s", (value, cfg_id))
        conn.commit()
        return None
    except Exception as exc:
        if conn is not None:
            conn.rollback()
        return str(exc)
    finally:
        if conn is not None:
            conn.close()


def try_sql_script(script):
    """Выполнить SQL-скрипт целиком: None при успехе, текст ошибки при отказе.

    Отличие от `sql_write` — здесь важен сам факт выполнения, а не число строк:
    rowcount у `DO`-блока в psycopg2 равен -1, и по нему нельзя судить об отказе
    (иначе повторная миграция, которая обязана быть пустой, читалась бы провалом).
    """
    conn = None
    try:
        conn = connect()
        cur = conn.cursor()
        cur.execute(script)
        conn.commit()
        return None
    except Exception as exc:
        if conn is not None:
            conn.rollback()
        return str(exc)
    finally:
        if conn is not None:
            conn.close()


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
    # Состав таблицы называется списком, а не «несколькими колонками»: узел V42 не только
    # добавил слоты, но и снял пять колонок без источника. Проверка «все прежние на месте»
    # такое изменение не ловила бы вовсе — она бы прошла, потому что удалённое не спрашивали.
    expected = CONFIGURATION_COLUMNS_V43
    if not check(f"состав таблицы заголовка равен измеренному "
                 f"(V42 + V43, {len(expected)} колонок)",
                 set(cols) == expected,
                 f"нет: {sorted(expected - set(cols))} "
                 f"лишние: {sorted(set(cols) - expected)}"):
        note("расхождение состава — предмет раздела 1: живая схема, бутстрап шага 2 и "
             "миграции V42/V43 обязаны совпадать (полноту схемы целиком сверяет _cmp_ddl.py)")

    # Узел V43: имена и порядок 48 перечней читаются из единственного словаря. Если живая
    # схема, бутстрап и писатель разошлись бы по именам, загрузчик и слой обогащения
    # описывали бы одну и ту же конфигурацию по-разному, а бэкфилл миграции писал бы
    # колонки, которых писатель не касается.
    check(f"словарь дочерних свойств называет ровно {CHILD_COUNT} колонок без дублей "
          "(единственный источник имён)",
          len(V43_CHILD_COLUMNS) == CHILD_COUNT == len(set(V43_CHILD_COLUMNS))
          and len(CHILD_OBJECT_TYPES) == CHILD_COUNT,
          repr([len(V43_CHILD_COLUMNS), CHILD_COUNT, len(set(V43_CHILD_COLUMNS))]))
    array_columns = sorted(c for c, kind in cols.items() if kind == "ARRAY")
    check(f"колонок-перечней в схеме ровно {CHILD_COUNT + len(PRE_V43_ARRAY_COLUMNS)}: "
          f"{CHILD_COUNT} узла V43 плюс {', '.join(PRE_V43_ARRAY_COLUMNS)} узла V32",
          array_columns == sorted(set(V43_CHILD_COLUMNS) | set(PRE_V43_ARRAY_COLUMNS)),
          repr(sorted(set(array_columns)
                      ^ (set(V43_CHILD_COLUMNS) | set(PRE_V43_ARRAY_COLUMNS)))))
    check("тип каждого перечня — массив текста (TEXT[]), а не jsonb и не varchar: контракт "
          "файла оператора «поле — всегда список значений, тип строка»",
          all(cols.get(column) == "ARRAY" for column in V43_CHILD_COLUMNS),
          repr({column: cols.get(column) for column in V43_CHILD_COLUMNS
                if cols.get(column) != "ARRAY"}))

    gone = sorted(column for column in V42_REMOVED_COLUMNS if column in cols)
    check("пять колонок без источника сняты (V42): app_module_id, session_module_id, "
          "data_proc_module_id, ext_conn_module_id, mobile_functionality",
          not gone, f"колонки ещё в схеме: {gone}")

    check("списочные значения V42 лежат в jsonb, а не в TEXT[]: признак use у признака "
          "мобильного интерфейса сохраняется",
          all(cols.get(column) == "jsonb" for column in V42_JSONB_COLUMNS),
          repr({column: cols.get(column) for column in V42_JSONB_COLUMNS}))
    check("логические свойства корня — колонки boolean (замер восьми выгрузок: true/false токеном)",
          all(cols.get(column) == "boolean" for column in V42_BOOLEAN_COLUMNS),
          repr({column: cols.get(column) for column in V42_BOOLEAN_COLUMNS}))

    # Ключевая проверка узла V42: у каждой колонки значения есть источник в словаре разбора.
    # До V42 четыре колонки заголовка (модули предопределённых программ) и mobile_functionality
    # не имели XML-источника, а 33 свойства не имели колонки — теперь ни того, ни другого нет.
    # С узла V43 у 48 перечней источника в словаре СВОЙСТВ корня нет и быть не может: их
    # заполняет индекс состава (`configuration_objects`, узел V33), а не `<Properties>`.
    # Поэтому покрытие проверяется двумя утверждениями: словарь свойств покрывает всё
    # остальное, а разрыв «схема минус словарь» — ровно перечни V43 и ничего больше.
    technical = {"id", "uuid", "created_at", "updated_at"}
    mapped = {field[0] for field in CONFIGURATION_FIELDS.values() if field[0]}
    value_columns = set(cols) - technical
    check("словарь разбора свойств покрывает все колонки значений, кроме перечней V43",
          mapped == value_columns - set(V43_CHILD_COLUMNS),
          repr(sorted((value_columns - set(V43_CHILD_COLUMNS)) ^ mapped)))
    check("разрыв «схема минус словарь» — ровно 48 перечней V43: их источник — индекс состава",
          (value_columns - mapped) == set(V43_CHILD_COLUMNS),
          repr(sorted((value_columns - mapped) - set(V43_CHILD_COLUMNS))))
    check("число свойств словаря равно измеренному числу свойств корня (замер восьми выгрузок)",
          len(CONFIGURATION_FIELDS) == ROOT_PROPERTIES_MEASURED,
          repr([len(CONFIGURATION_FIELDS), ROOT_PROPERTIES_MEASURED]))
    check("список «не заполняется осознанно» пуст: V42 снял основание для него",
          not NOT_FILLED_COLUMNS, repr(sorted(NOT_FILLED_COLUMNS)))
    declared = ddl_declared_columns(TABLE)
    check("бутстрап шага 2 не объявляет снятых колонок и объявляет новые (правка идёт парой, п. 17)",
          bool(declared)
          and not any(column in declared for column in V42_REMOVED_COLUMNS)
          and all(declared.get(column) == "jsonb" for column in V42_JSONB_COLUMNS),
          repr({column: declared.get(column) for column in
                (*V42_REMOVED_COLUMNS, *V42_JSONB_COLUMNS)}))
    # Узел V43: та же пара «миграция + бутстрап». Живая схема с 48 колонками и бутстрап без
    # них означала бы, что чистая установка БД вернулась к состоянию до узла, а `_cmp_ddl.py`
    # поймал бы это только как расхождение всей схемы, без указания на причину.
    check("бутстрап шага 2 объявляет все 48 перечней типом text[] (V43: правка схемы идёт парой)",
          bool(declared)
          and all(declared.get(column) == "text[]" for column in V43_CHILD_COLUMNS),
          repr({column: declared.get(column) for column in V43_CHILD_COLUMNS
                if declared.get(column) != "text[]"}))
    check("миграция V43 существует и заполняет колонки из configuration_objects (бэкфилл живых БД)",
          V43_MIGRATION.exists()
          and "configuration_objects" in (V43_MIGRATION.read_text(encoding="utf-8", errors="replace")
                                         if V43_MIGRATION.exists() else ""),
          repr(str(V43_MIGRATION)))

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
    section("3. РАЗБОР: uuid из атрибута, ref -> имя, пустой синоним = NULL; "
            "слепых зон по свойствам нет (V42), остальное названо")
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

    # ── счётчики и слепые зоны (узел V42 закрыл словарь свойств) ──
    # До V42 `CONFIGURATION_FIELDS` знал 22 свойства из 55, и предупреждения называли 33 имени
    # поимённо, а пустые значения — числом. С узла V42 словарь покрывает все 55 свойств, поэтому
    # у фикстуры слепых зон не остаётся: пустой перечень — это результат проверки, а не молчание.
    # Механизм называния слепых зон обязан оставаться живым (раздел 3c: свойство, которого нет в
    # словаре, называется по имени), иначе «закрытая зона» означала бы, что любое новое свойство
    # будет промолчано.
    check("счётчик свойств: разобранное и не имеющее колонки не путаются",
          counts["properties_total"] == ROOT_PROPERTIES_MEASURED
          and counts["properties_mapped"] == len(CONFIGURATION_FIELDS) == ROOT_PROPERTIES_MEASURED
          and counts["properties_filled"] >= 8
          and counts["properties_unstored"]
          == (len(counts["properties_unstored_nonempty"])
              + counts["properties_unstored_empty"]),
          repr({key: counts[key] for key in
                ("properties_total", "properties_mapped", "properties_filled",
                 "properties_unstored")}))
    check("свойств без колонки у фикстуры не осталось: словарь V42 покрывает все 55",
          counts["properties_unstored"] == 0
          and not counts["properties_unstored_nonempty"]
          and counts["properties_unstored_empty"] == 0,
          repr({key: counts[key] for key in
                ("properties_unstored", "properties_unstored_nonempty",
                 "properties_unstored_empty")}))
    check("предупреждений о слепых зонах свойств нет: основание снято, а не подавлен вывод",
          not [w for w in warnings if w.startswith("Properties/")],
          repr([w[:90] for w in warnings if w.startswith("Properties/")][:6]))
    check("состав ChildObjects назван как есть: одна языковая конфигурация",
          counts["child_objects"] == {"Language": 1}, repr(counts["child_objects"]))
    check("ChildObjects/Language остаётся слепой зоной: свойства языка в словаре корня нет",
          any("ChildObjects/Language" in w and "Русский" in w for w in warnings),
          repr([w[:90] for w in warnings][:6]))
    # Узел V42 сохранил признак `use`: прежняя колонка TEXT[] его теряла, и «признак
    # используется» было нечем отличить от «признак перечислен со use=false». Числа берутся
    # из разбора, а не из литерала: фикстуру оператор менял (MinCfg расширён 21.10.2026),
    # литерал бы отстал и начал врать.
    records = row["mobile_application_functionalities"] or []
    check("UsedMobileApplicationFunctionalities разобран парами functionality/use (V42)",
          len(records) == counts["mobile_functionalities_total"]
          == counts["mobile_functionalities_stored"] > 0
          and all(set(item) == {"functionality", "use"} for item in records)
          and {"OSBackup"} <= set(counts["mobile_functionalities_use_true"])
          and any(item["use"] == "false" for item in records),
          repr([len(records), counts["mobile_functionalities_use_true"],
                counts["mobile_functionalities_stored"]]))
    check("предупреждение D-D («признаки не сохраняются») снято: значение ложится в jsonb",
          not any("UsedMobileApplicationFunctionalities" in w for w in warnings),
          repr([w[:90] for w in warnings][:6]))

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

    # V39: вторая языковая форма не теряется — в текстовой колонке она терялась, jsonb-колонка
    # хранит словарь по каждой v8:lang. Проверка называет ровно то, что обязан делать разбор.
    multi = new_catalog()
    edit_xml(multi / "Configuration.xml",
             [("<Synonym/>",
               '<Synonym><v8:item><v8:lang>ru</v8:lang><v8:content>Нулевая</v8:content>'
               '</v8:item><v8:item><v8:lang>en</v8:lang><v8:content>Null</v8:content>'
               "</v8:item></Synonym>")])
    res = parse_configuration_meta(str(multi / "Configuration.xml"))
    check("многоязычный синоним: обе формы (ru + en) разобраны словарём, "
          "предупреждения о потере формы больше нет",
          res.get("success")
          and res["configuration"]["synonym"] == {"ru": "Нулевая", "en": "Null"}
          and not any("многоязыч" in w for w in res.get("warnings", [])),
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
    check("синоним только на en: ключ 'en' и ничего больше — язык 'ru' не подставляется",
          res.get("success") and res["configuration"]["synonym"] == {"en": "Null"},
          repr(res["configuration"].get("synonym")))


# ─────── 3c. перечень ссылок: дети Value и Item (дефект разбора DefaultRoles) ───────

# Форма детей перечисных свойств задаёт ВЫГРУЗКА, а не память о схеме. Замер 20.10.2026 по
# восьми XML-выгрузкам (BGU2, BP3, KomMag, UNF3, UT11, ZUP31, Config_NULL, MinCfg): у
# Properties/UsePurposes дети называются `v8:Value` (xsi:type "app:ApplicationUsePurpose"),
# у Properties/DefaultRoles — `xr:Item` (xsi:type="xr:MDObjectRef"). Прежний разбор вида
# `ref_list` искал только `Value`, поэтому при непустом <DefaultRoles> колонка main_roles
# оставалась пустой: роли теряли 6 из 8 конфигураций (пустой перечень давали только две
# фикстуры с <DefaultRoles/>). Проверка держит обе измеренные формы детей, чтобы возврат к
# «только Value» был виден сразу, а не по пустой колонке у читателя карточки.
ROLES_ITEM = '<xr:Item xsi:type="xr:MDObjectRef">Role.{}</xr:Item>'
ROLES_VALUE = "<v8:Value>Role.{}</v8:Value>"

# Свойство, которого нет в словаре `CONFIGURATION_FIELDS`: слепую зону задаёт тест, а не
# выгрузка (с узла V42 словарь покрывает все 55 измеренных свойств корня). Имя намеренно
# не похоже ни на одно измеренное — иначе проверка проверяла бы словарь, а не механизм.
# Дети — подразделы с признаком `use`: узкий признак значения (только Value/Item) отнёс бы
# такое свойство к пустым, и счётчик пустых начал бы врать.
UNKNOWN_PROPERTY = "V42ProbeUnknownRootProperty"
UNKNOWN_PROPERTY_XML = (f'<{UNKNOWN_PROPERTY}><SubSection use="true">Значение</SubSection>'
                        f"</{UNKNOWN_PROPERTY}>")


def roles_property_xml(names, tag="DefaultRoles", child="item"):
    """Перечень свойства по измеренной форме детей: `item` — как в выгрузке, `value` — иная."""
    if not names:
        return f"<{tag}/>"
    template = ROLES_VALUE if child == "value" else ROLES_ITEM
    inner = "".join(template.format(name) for name in names)
    return f"<{tag}>{inner}</{tag}>"


def check_roles():
    """Перечни ссылок: обе формы детей, порядок, снятие префикса вида, запись в TEXT[]."""
    section("3c. перечень ссылок: дети Item и Value (дефект разбора DefaultRoles)")
    before = db_counts()
    roles = ["ТестоваяРольПробы", "ВтораяРольПробы"]

    # ── уровень разбора: форма детей из выгрузки (xr:Item) ──
    catalog = synth_catalog("v32_roles_item", name_mode="fixed",
                           name_value=PROBE + "roles_item")
    xml = catalog / "Configuration.xml"
    edit_xml(xml, [("<DefaultRoles/>", roles_property_xml(roles))])
    parsed = parse_configuration_meta(str(xml))
    if not check("копия фикстуры с непустым <DefaultRoles> разобрана",
                 parsed.get("success"), repr(parsed)[:300]):
        return
    row, counts = parsed["configuration"], parsed["counts"]
    check('роли из <xr:Item xsi:type="xr:MDObjectRef"> прочитаны (дефект: ждали только Value)',
          row["main_roles"] == roles, repr(row.get("main_roles")))
    check("префикс вида метаданных Role. снят: колонка main_roles хранит имя роли",
          all("." not in role for role in (row["main_roles"] or [])),
          repr(row.get("main_roles")))
    check("порядок выгрузки сохранён", row["main_roles"] == roles,
          repr(row.get("main_roles")))
    empty_counts = parse_configuration_meta(str(CONFIG_XML))["counts"]
    # С узла V42 пустых свойств без колонки у фикстуры нет. Проверка держит ровно то, что
    # держала и раньше — непустый перечень не должен попадать в список пустых, — но обязана
    # показать и нулевой базис: сравнить два нуля, ничего не утверждая, было бы той же
    # слепой зоной, что молчаливый нулевой счётчик в карточке.
    check("непустый перечень не прибавляется к списку пустых свойств без колонки",
          counts["properties_unstored_empty"] == empty_counts["properties_unstored_empty"] == 0
          and "DefaultRoles" not in (counts.get("properties_unstored_nonempty") or []),
          repr([counts["properties_unstored_empty"],
                empty_counts["properties_unstored_empty"],
                counts.get("properties_unstored_nonempty")]))

    # ── вторая измеренная форма детей того же свойства (v8:Value) ──
    edit_xml(xml, [(roles_property_xml(roles), roles_property_xml(roles, child="value"))])
    alt = parse_configuration_meta(str(xml))
    check("иная форма детей того же свойства (v8:Value) читается тем же разбором",
          alt.get("success") and alt["configuration"]["main_roles"] == roles,
          repr((alt.get("configuration") or {}).get("main_roles")))

    # ── неизвестная форма детей: пустая колонка обязана быть названа ──
    edit_xml(xml, [(roles_property_xml(roles, child="value"),
                    "<DefaultRoles><Bogus>Role.НеизвестнаяФорма</Bogus></DefaultRoles>")])
    unknown = parse_configuration_meta(str(xml))
    check("дети неизвестной формы не теряются молча: пустая колонка названа предупреждением",
          unknown.get("success") and not unknown["configuration"]["main_roles"]
          and any("значений извлечено 0" in w and "Bogus" in w
                  for w in unknown["warnings"]),
          repr([w[:160] for w in unknown.get("warnings", []) if "DefaultRoles" in w]))

    # ── `_has_value` шире списка известных детей: дети-подразделы тоже значение ──
    # С узла V42 словарь `CONFIGURATION_FIELDS` покрывает все 55 измеренных свойств корня,
    # поэтому слепую зону в прогоне задаёт сам тест: в Properties кладётся свойство, которого
    # в словаре нет. Платформа добавит новое свойство — и оно обязано быть названным по имени,
    # а не промолчанным; закрытая зона фикстуры не означает, что механизм называния не нужен.
    # Дети — подразделы с признаком `use`, а не Value/Item: узкий признак значения относил бы
    # такое свойство к пустым (замер 20.10.2026 по восьми выгрузкам: единственной такой формой
    # детей был UsedMobileApplicationFunctionalities).
    edit_xml(xml, [("<StandaloneConfigurationRestrictionRoles/>",
                    "<StandaloneConfigurationRestrictionRoles/>" + UNKNOWN_PROPERTY_XML)])
    blind = parse_configuration_meta(str(xml))
    blind_counts = blind.get("counts") or {}
    blind_names = set(blind_counts.get("properties_unstored_nonempty") or [])
    check("свойство без колонки с детьми-подразделами названо непустой слепой зоной",
          blind.get("success") and UNKNOWN_PROPERTY in blind_names,
          repr(sorted(blind_names)[:12]))
    check("непустая слепая зона названа в предупреждении по имени",
          any(f"Properties/{UNKNOWN_PROPERTY}" in w and "слепая зона V32" in w
              for w in blind.get("warnings") or []),
          repr([w[:160] for w in blind.get("warnings") or []
                if UNKNOWN_PROPERTY in w]))
    check("оно же не попало в счётчик пустых: широкий признак значения держится",
          blind_counts.get("properties_unstored") == len(blind_names) == 1
          and blind_counts.get("properties_unstored_empty") == 0,
          repr({key: blind_counts.get(key) for key in
                ("properties_unstored", "properties_unstored_nonempty",
                 "properties_unstored_empty")}))

    # ── V42: единственное измеренное свойство с детьми-подразделами получило колонку ──
    # До V42 `UsedMobileApplicationFunctionalities` назывался непустой слепой зоной; с узла
    # V42 у него есть колонка `mobile_application_functionalities` jsonb, поэтому слепой зоной
    # он быть не может. Названная слепая зона = словарь отстал от выгрузки.
    fixture = parse_configuration_meta(str(CONFIG_XML))
    fixture_counts = fixture.get("counts") or {}
    fixture_nonempty = set(fixture_counts.get("properties_unstored_nonempty") or [])
    fixture_pairs = len((fixture.get("configuration") or {})
                        .get("mobile_application_functionalities") or [])
    check("свойство с детьми-подразделами больше не слепая зона: пары читаются в jsonb (V42)",
          "UsedMobileApplicationFunctionalities" not in fixture_nonempty
          and not any("UsedMobileApplicationFunctionalities" in w
                      for w in fixture.get("warnings") or [])
          and fixture_pairs == fixture_counts.get("mobile_functionalities_total") > 0,
          repr([sorted(fixture_nonempty)[:14], fixture_pairs,
                fixture_counts.get("mobile_functionalities_total")]))
    check("слепых зон по свойствам у измеримой фикстуры нет и счётчик сходится",
          fixture_counts.get("properties_unstored", -1) == 0
          == (len(fixture_counts.get("properties_unstored_nonempty") or [])
              + (fixture_counts.get("properties_unstored_empty") or 0)),
          repr({key: fixture_counts.get(key) for key in
                ("properties_unstored", "properties_unstored_nonempty",
                 "properties_unstored_empty")}))

    # ── реестр имён детей один, а не разбросанный литерал в вызовах ──
    check("реестр имён детей перечисных свойств = value + item",
          tuple(LIST_CHILD_TAGS) == ("value", "item"), repr(LIST_CHILD_TAGS))
    xr_ns = ('xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" '
             'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"')
    prefixed = ET.fromstring(f"<r {xr_ns}>" + ROLES_ITEM.format("Одна") + "</r>")
    plain = ET.fromstring("<r><Item>Role.Две</Item><Value>Role.Три</Value>"
                          "<item>Role.Четыре</item></r>")
    check("дети с префиксом пространства имён читаются так же, как без префикса",
          _ref_list(prefixed) == ["Одна"] and len(_list_children(prefixed)) == 1,
          repr(_ref_list(prefixed)))
    check("регистр имени ребёнка не важен (Item, Value, item — одна форма детей)",
          _ref_list(plain) == ["Две", "Три", "Четыре"] and _has_value(plain),
          repr(_ref_list(plain)))
    check("пустой элемент и xsi:nil дают пустой перечень, а не ошибку разбора",
          _ref_list(ET.fromstring("<r/>")) == []
          and _ref_list(ET.fromstring('<r xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                                      'xsi:nil="true"/>')) == [],
          repr(_ref_list(ET.fromstring("<r/>"))))
    check("разбор ничего не записывает в БД: чтение отделено от записи",
          db_counts() == before, f"{before} -> {db_counts()}")

    # ── путь записи: роли доходят до TEXT[] в configurations ──
    # XML к этому моменту испорчен намеренно (Bogus-форма перечня ролей и неизвестное
    # свойство с детьми-подразделами), поэтому перед загрузком перечень возвращается к
    # измеренной форме — иначе проверка записи сверялась бы с пустой колонкой и не
    # проверяла бы ничего. Неизвестное свойство остаётся: загрузка обязана принять файл с
    # незнакомым свойством и назвать его, а не отказать.
    edit_xml(xml, [("<DefaultRoles><Bogus>Role.НеизвестнаяФорма</Bogus></DefaultRoles>",
                    roles_property_xml(roles))])
    res = load_catalog(str(catalog))
    text = format_load_result(res)
    cfg_id = int(res.get("id") or 0)
    if not check("исход ✅ загружено: непустый перечень ролей загрузке не мешает",
                 res.get("status") == "loaded", text[:400]):
        return
    stored = sql_one("SELECT main_roles FROM configurations WHERE id = %s", (cfg_id,))
    check("роли записаны в колонку main_roles (TEXT[]) без префикса и по порядку",
          list(stored or []) == roles, repr(stored))
    check("число ролей в БД равно числу из разбора",
          sql_one("SELECT COALESCE(array_length(main_roles, 1), 0) FROM configurations "
                  "WHERE id = %s", (cfg_id,)) == len(roles), repr(stored))

    removed = delete_configuration(cfg_id=cfg_id)
    check("прогон убирает за собой: заголовок снят вместе с составом",
          removed.get("success") is True, repr(removed)[:300])
    check("после уборки счётники БД равны началу раздела",
          db_counts() == before, repr([before, db_counts()]))
    note("Граница: читаются ИМЕНА ролей из Properties/DefaultRoles; сами объекты Role.* в "
         "схеме не хранятся — перечень остаётся списком имён (роль как объект метаданных "
         "появится только вместе со сниманием слепых зоны V38 группы A).")


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
    # Узел V42: список «не заполняется» стал пустым (сознательных NULL-колонок нет),
    # поэтому прежняя проверка («карточка печатает app_module_id») стала ложью: колонки
    # в схеме больше нет. Проверка не снята, а переведена в актуальную форму: карточка
    # не должна называть ни одной снятой колонки и не должна обещать SQL-файл, которого
    # нет на диске (прежняя ссылка вела на check_configuration_inventory.sql).
    check("карточка V42 не называет снятых колонок и не ссылается на несуществующий SQL",
          all(f"не заполняется: {column}" not in text
              for column in V42_REMOVED_COLUMNS)
          and "не заполняется:" not in text
          and "check_configuration_inventory.sql" not in text, text[:400])
    check("карточка называет свойства числом: без колонки не осталось ни одного (V42)",
          "без колонки 0" in text, text[:400])

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
    # Узел V42: прежняя проверка перечисляла пять колонок, которых в схеме больше нет
    # (модули предопределённых программ и mobile_functionality). Смысл её тот же: чего
    # нет в разборе — того нет и в строке (NULL, а не пустая строка/пустой массив).
    # Список колонок больше не пишется руками: он выводится из разницы живой схемы и
    # ключей контракта, поэтому проверка не устареет при следующем изменении DDL.
    check("V42: снятых колонок в строке нет",
          not (set(row) & set(V42_REMOVED_COLUMNS)),
          repr(sorted(set(row) & set(V42_REMOVED_COLUMNS))))
    never_written = sorted((set(row) - set(contract))
                           - {"id", "created_at", "updated_at", "name"}
                           - set(V43_CHILD_COLUMNS))
    note(f"колонок вне разбора свойств в этой фикстуре: {len(never_written)} — они обязаны "
         f"быть NULL; {len(V43_CHILD_COLUMNS)} колонок-перечней заполняет другой контур "
         "(индекс состава), их значение сверяется отдельной проверкой ниже")
    check("V42: колонок, которых нет в разборе, остались NULL, а не пустыми значениями",
          all(row.get(column) is None for column in never_written),
          repr({column: row.get(column) for column in never_written[:8]}))
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

    # ── узел V43: строка заголовка несёт перечни имён объектов состава ──────────────
    # Значения 48 колонок даёт ТОТ ЖЕ разбор индекса, что и строки `configuration_objects`
    # (второго чтения ConfigDumpInfo.xml у загрузчика нет). Проверяются три границы узла:
    # имена колонок чтения берутся из канонического словаря (своего перечня у проверки нет),
    # Python-агрегация совпадает с SQL-агрегацией, которую дословно повторяет бэкфилл
    # `migrate_v43_configuration_child_arrays.sql`, и пустой перечень остаётся NULL, а не
    # пустым массивом (K2: «вида в конфигурации нет» — это ответ о конфигурации).
    child_rows = sql_rows(
        f"SELECT {', '.join(V43_CHILD_COLUMNS)} FROM configurations WHERE id = %s",
        (cfg_id,))
    check(f"{CHILD_COUNT} перечней прочитаны из строки по именам канонического словаря",
          len(child_rows) == 1 and len(child_rows[0]) == CHILD_COUNT,
          repr([len(child_rows), len(child_rows[0]) if child_rows else None]))
    header_db = ({column: child_rows[0][at] for at, column in enumerate(V43_CHILD_COLUMNS)}
                 if child_rows else {})
    filled_db = {column: names for column, names in header_db.items() if names is not None}

    header_agg = collect_header_arrays(index["objects"])
    check("значения перечней = значения того же разбора индекса (второго источника нет)",
          filled_db == header_agg["values"],
          repr([filled_db, header_agg["values"]]))

    sql_arrays = sql_rows(
        'SELECT object_type, array_agg(object_name ORDER BY name COLLATE "C") '
        "FROM configuration_objects WHERE configuration_id = %s AND depth = 0 "
        "AND object_type <> %s GROUP BY object_type", (cfg_id, "Configuration"))
    sql_by_column = {COLUMN_BY_OBJECT_TYPE[type_name]: names for type_name, names in sql_arrays
                     if type_name in COLUMN_BY_OBJECT_TYPE}
    check("K1/K5/K6: Python-агрегация совпадает с SQL-агрегацией по той же таблице "
          "(бэкфилл миграции повторяет то же правило)",
          sql_by_column == filled_db, repr([sql_by_column, filled_db]))

    check("K2: вида в индексе нет — колонка NULL, а не пустой перечень; заполнен только вид из индекса",
          all(header_db.get(column) is None for column in V43_CHILD_COLUMNS
              if column not in header_agg["values"])
          and all(isinstance(header_db.get(column), list) and header_db.get(column)
                  for column in header_agg["values"]),
          repr({column: header_db.get(column) for column in header_agg["values"]}))
    check("карточка называет заполнение перечней числом N из 48 — по нулям граница K2 читаема",
          f"заполнено {header_agg['columns_filled']} колонок из {CHILD_COUNT}" in text
          and res.get("header_arrays_filled") == header_agg["columns_filled"]
          and res.get("header_array_columns_total") == CHILD_COUNT
          and res.get("header_array_items") == header_agg["objects_total"],
          repr([res.get("header_arrays_filled"), res.get("header_array_columns_total"),
                res.get("header_array_items"), header_agg["columns_filled"],
                header_agg["objects_total"]]))

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

# ─────── 3d. многоязычные свойства заголовка: v8:item -> JSONB (узел V39) ───────

def multilang_property_xml(tag, forms):
    """Значение свойства в замерной форме выгрузки: `v8:item / v8:lang / v8:content`."""
    if not forms:
        return f"<{tag}/>"
    inner = "".join(f"<v8:item><v8:lang>{lang}</v8:lang>"
                    f"<v8:content>{text}</v8:content></v8:item>" for lang, text in forms)
    return f"<{tag}>{inner}</{tag}>"


def fill_multilang(xml_path, values):
    """Заменить пустые элементы копии фикстуры замерной формой (пустой элемент по каждому есть).

    Возвращает число пустых элементов, которые реально были в XML: без этого раздел
    проверял бы вакуум — шесть отсутствующих элементов дали бы шесть NULL, и фразу
    «словарь не теряет форму» было бы нечем проверить.
    """
    text = xml_path.read_text(encoding="utf-8")
    found = sum(1 for tag in values if f"<{tag}/>" in text)
    edit_xml(xml_path, [(f"<{tag}/>", multilang_property_xml(tag, forms))
                        for tag, forms in values.items()])
    return found


def multilang_probe_values():
    """По две языковые формы на каждое из шести свойств; тексты разные — проверка на потерю.

    Языки — настоящие коды `v8:lang` (`ru`, `en`), а не метки свойств: проверки
    «ключ читается оператором `->>`» и «ключа `de` нет» имеют смысл только на кодах
    языка, каких-то других в выгрузке не бывает (замер восьми выгрузок).
    """
    return {tag: [("ru", f"{tag} — форма на русском"),
                  ("en", f"{tag} form in English")]
            for tag in MULTILANG_COLUMNS.values()}


def multilang_expected(values):
    """Ожидаемые колонки {колонка: {язык: текст}} — из тех же значений, что и XML."""
    return {column: dict(values[tag]) for column, tag in MULTILANG_COLUMNS.items()}


def column_types(table):
    """Типы колонок таблицы из живой схемы: сравнивать контракт нужно со схемой, а не с памятью."""
    return {row[0]: row[1] for row in sql_rows(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s", (table,))}


def ddl_declared_columns(table):
    """Колонки и типы, объявленные в бутстрапе шага 2 (`create_1c_configurations_db.sql`).

    Правка схемы идёт парой «миграция + бутстрап» (п. 17): живая схема без бутстрапа даёт
    половину правки, и чистая установка БД возвращается к прежнему контракту. Разбор один на
    два раздела (1 и 3d), чтобы они не описывали один файл по-разному.
    """
    ddl = DDL_BOOTSTRAP.read_text(encoding="utf-8", errors="replace")
    block = re.search(r"(?is)CREATE TABLE IF NOT EXISTS %s\s*\((.*?)\n\);" % table, ddl)
    if not block:
        check(f"бутстрап шага 2 содержит CREATE TABLE {table}", False, "блок не найден")
        return {}
    return {name.lower(): kind.lower() for name, kind in re.findall(
        # `\b` на конце здесь невозможен: после `text[]` следующий символ — `,` или перевод
        # строки, то есть границы слова нет, и регулярка откатывалась к ветке `text`, отдавая
        # ARRAY-колонку как текстовую (замер 22.10.2026: 48 колонок V43 прочитались типом
        # `text`, и проверка пары «миграция + бутстрап» провалилась бы на верном DDL).
        # Граница типа — «дальше не буква/цифра/подчёркивание»: она пропускает `[]`, `(`,
        # пробел и конец строки и не даёт `text` совпасть с началом длинного имени типа.
        r"(?mi)^\s*(\w+)\s+(jsonb|text\[\]|text|varchar|boolean|uuid|integer|timestamp)"
        r"(?![\w])", block.group(1))}



def multilang_stored(cfg_id):
    """Значения шести колонок одной строки как есть: psycopg2 читает jsonb словарём."""
    return sql_dict(f"SELECT {', '.join(MULTILANG_COLUMNS)} FROM {TABLE} WHERE id = %s",
                    (cfg_id,)) or {}


def multilang_shape_case(column):
    """CASE: значение есть, но словарём не является (строка, массив, пустой объект)."""
    return ("CASE WHEN {0} IS NOT NULL AND (jsonb_typeof({0}) <> 'object' "
            "OR {0} = '{{}}'::jsonb) THEN 1 ELSE 0 END").format(column)


def bad_multilang_values(cfg_id=None):
    """Сколько значений шести колонок не являются словарём по языку (0 = контракт цел)."""
    where = f"WHERE id = {int(cfg_id)}" if cfg_id else ""
    total = " + ".join(multilang_shape_case(column) for column in MULTILANG_COLUMNS)
    return int(sql_one(f"SELECT {total} FROM {TABLE} {where}") or 0)


def check_multilang_properties():
    """Схема, парсер, запись, длинное значение и миграция: шесть свойств как словарь по языку."""
    section("3d. МНОГОЯЗЫЧНЫЕ СВОЙСТВА: v8:item -> словарь {язык: текст}, колонка JSONB (V39)")
    # Имена заголовков пробы фиксированы: на них проверяется и force=True (перенос имени),
    # и отказ на не-jsonb значении. Цена фиксации — остаток после прерванного прогона:
    # строка справочника пережила бы аварию, и первая загрузка раздела дала бы name_conflict,
    # т. е. прогон проверял бы чужое состояние вместо своего. Остатки снимаются до базовой
    # линии и называются — молча перезаписать их force=True значит скрыть аварию прошлого запуска.
    probe_names = [f"{PROBE}multi", f"{PROBE}long"]
    leftovers = sql_rows(f"SELECT id, name FROM {TABLE} WHERE name = ANY(%s)", (probe_names,))
    if leftovers:
        note(f"в справочнике остались строки прерванного прогона ({len(leftovers)}): они сняты "
             "до базовой линии, иначе первая загрузка раздела ответила бы name_conflict "
             "на чужой строке, а не своим исходом")
        for left in leftovers:
            delete_configuration(cfg_id=int(left[0]))
    before = db_counts()

    # ── А. тип колонок и границы, которые V39 не трогал ──
    types = column_types(TABLE)
    want_jsonb = {column: "jsonb" for column in MULTILANG_COLUMNS}
    got = {column: types.get(column) for column in MULTILANG_COLUMNS}
    if not check("шесть свойств заголовка — колонки jsonb: словарь по языку в текст не кладётся",
                 got == want_jsonb, repr(got)):
        return
    check("свойства, дающие в выгрузке простой текст, остались текстовыми (замер восьми выгрузок)",
          all(types.get(column) in TEXT_TYPES for column in SIMPLE_TEXT_COLUMNS),
          repr({column: types.get(column) for column in SIMPLE_TEXT_COLUMNS}))
    extension_types = column_types("config_extensions")
    check("config_extensions.synonym остался text: загрузчика расширения нет (R7) — граница названа",
          extension_types.get("synonym") in TEXT_TYPES, repr(extension_types.get("synonym")))
    extra_lang = sorted(column for column in types
                        if column not in MULTILANG_COLUMNS
                        and any(column.startswith(base) for base in MULTILANG_COLUMNS))
    check("под языковые формы не заводили отдельных колонок (synonym_en, short_info_lang): "
          "язык — часть значения", not extra_lang, repr(extra_lang))
    check("в живых строках нет значений шести колонок, не являющихся словарём по языку",
          bad_multilang_values() == 0, repr(bad_multilang_values()))
    # Правка схемы идёт парой «миграция + бутстрап» (п. 17): иначе _cmp_ddl.py зафиксирует
    # расхождение, а чистая установка БД вернётся к текстовым колонкам.
    declared = ddl_declared_columns(TABLE)
    check("бутстрап шага 2 объявляет те же jsonb-колонки, что живая схема (правка идёт парой)",
          bool(declared)
          and all(declared.get(column) == "jsonb" for column in MULTILANG_COLUMNS),
          repr({column: declared.get(column) for column in MULTILANG_COLUMNS}))
    text_limit = sql_one("SELECT character_maximum_length FROM information_schema.columns "
                         "WHERE table_schema = 'public' AND table_name = %s "
                         "AND column_name = 'update_url'", (TABLE,))
    check("лимит оставшейся текстовой колонки назван и не снят: update_url varchar(500)",
          text_limit == 500, repr(text_limit))
    # ── Б. парсер: словарь по каждой v8:lang, без потерь и без выдуманного языка ──
    values = multilang_probe_values()
    # Многострочное значение: текстовая колонка сохраняла его как есть, jsonb не должен резать
    # перенос — иначе многострочная справка (DetailedInformation) потерялась бы и здесь.
    values["DetailedInformation"] = [("ru", "Первая строка\nвторая строка"),
                                    ("en", "line one\nline two")]
    catalog = synth_catalog("v39_multi", name_mode="fixed", name_value=probe_names[0])
    replaced = fill_multilang(catalog / "Configuration.xml", values)
    check("копия фикстуры получила шесть заполненных свойств: иначе проверка была бы вакуумной",
          replaced == len(MULTILANG_COLUMNS), repr(replaced))
    parsed = parse_configuration_meta(str(catalog / "Configuration.xml"))
    if not check("копия фикстуры с шестью заполненными свойствами разобрана",
                 parsed.get("success"), repr(parsed)[:300]):
        return
    row, counts, warnings = parsed["configuration"], parsed["counts"], parsed["warnings"]
    expected = multilang_expected(values)
    for column, tag in MULTILANG_COLUMNS.items():
        check(f"{tag} → {column}: обе языковые формы разобраны словарём, форма не потеряна",
              row.get(column) == expected[column], repr(row.get(column)))
    fixture = parse_configuration_meta(str(CONFIG_XML))
    check("заполненное свойство не считается пустым: счётчик заполненных вырос ровно на шесть",
          counts["properties_filled"] == (fixture["counts"]["properties_filled"] + 6),
          repr([fixture["counts"]["properties_filled"], counts["properties_filled"]]))
    check("предупреждения «значение многоязычно, форма потеряна» больше нет: словарь не теряет",
          not any("многоязыч" in w for w in warnings),
          repr([w[:90] for w in warnings][:4]))

    # «значения нет» отделено от «значение пустое»; язык не выдумывается
    check("пустой элемент по шести свойствам даёт NULL по шести колонкам: пустой словарь "
          "в контракт не кладётся",
          all(fixture["configuration"][column] is None for column in MULTILANG_COLUMNS),
          repr({column: fixture["configuration"].get(column)
                for column in ("synonym", "short_info")}))

    empty_item = new_catalog()
    edit_xml(empty_item / "Configuration.xml",
             [("<Copyright/>", "<Copyright><v8:item><v8:lang>ru</v8:lang>"
                               "<v8:content></v8:content></v8:item></Copyright>")])
    res = parse_configuration_meta(str(empty_item / "Configuration.xml"))
    check("v8:item с пустым v8:content — NULL, а не {'ru': ''} и не {}: пустое значение и "
          "отсутствие значения в колонке неразличимы осознанно",
          res.get("success") and res["configuration"]["copyright"] is None,
          repr(res["configuration"].get("copyright")))

    nil_item = new_catalog()
    edit_xml(nil_item / "Configuration.xml",
             [("<ConfigurationInformationAddress/>",
               '<ConfigurationInformationAddress><v8:item><v8:lang>ru</v8:lang>'
               '<v8:content xsi:nil="true"/></v8:item></ConfigurationInformationAddress>')])
    res = parse_configuration_meta(str(nil_item / "Configuration.xml"))
    check("xsi:nil на v8:content — NULL: тот же ответ, что у пустого значения",
          res.get("success") and res["configuration"]["config_url"] is None,
          repr(res["configuration"].get("config_url")))

    plain = new_catalog()
    edit_xml(plain / "Configuration.xml",
             [("<BriefInformation/>", "<BriefInformation>текст без v8:item</BriefInformation>")])
    res = parse_configuration_meta(str(plain / "Configuration.xml"))
    check("значение без v8:item не теряется: общий разбор даёт ключ 'ru' И называет его "
          "неподтверждённым (в восьми выгрузках такой формы нет)",
          res.get("success")
          and res["configuration"]["short_info"] == {"ru": "текст без v8:item"}
          and any("BriefInformation" in w and "не подтверждён" in w for w in res["warnings"]),
          repr([res["configuration"].get("short_info"),
                [w[:90] for w in res.get("warnings", [])][:3]]))

    nolang = new_catalog()
    edit_xml(nolang / "Configuration.xml",
             [("<BriefInformation/>",
               "<BriefInformation><v8:item><v8:content>без языка</v8:content>"
               "</v8:item></BriefInformation>")])
    res = parse_configuration_meta(str(nolang / "Configuration.xml"))
    check("v8:item без v8:lang: язык не выдумывается, в колонку ничего не пишется, "
          "но потеря названа предупреждением",
          res.get("success") and res["configuration"]["short_info"] is None
          and any("BriefInformation" in w and "v8:lang" in w for w in res["warnings"]),
          repr([res["configuration"].get("short_info"),
                [w[:90] for w in res.get("warnings", [])][:3]]))

    only_en = new_catalog()
    edit_xml(only_en / "Configuration.xml",
             [("<VendorInformationAddress/>",
               multilang_property_xml("VendorInformationAddress",
                                     [("en", "http://example.invalid/only-en")]))])
    res = parse_configuration_meta(str(only_en / "Configuration.xml"))
    check("значение только на en: ключ 'en' и ничего больше — язык 'ru' не подставляется",
          res.get("success")
          and res["configuration"]["vendor_url"] == {"en": "http://example.invalid/only-en"},
          repr(res["configuration"].get("vendor_url")))

    dup = new_catalog()
    edit_xml(dup / "Configuration.xml",
             [("<VendorInformationAddress/>",
               multilang_property_xml("VendorInformationAddress",
                                     [("ru", "первая"), ("ru", "вторая")]))])
    res = parse_configuration_meta(str(dup / "Configuration.xml"))
    check("повтор одного языка: один ключ, молчаливого склеивания двух форм нет",
          res.get("success") and res["configuration"]["vendor_url"] == {"ru": "вторая"},
          repr(res["configuration"].get("vendor_url")))
    # ── В. запись: jsonb принимает словарь целиком ──
    res = load_catalog(str(catalog))
    cfg_id = int(res.get("id") or 0)
    state.setdefault("multilang_cfgs", []).append(cfg_id)
    if not check("исход «загружено»: многоязычные значения загрузке не мешают",
                 res.get("status") == "loaded" and cfg_id > 0,
                 format_load_result(res)[:400]):
        return
    kinds = dict(zip(MULTILANG_COLUMNS, sql_rows(
        "SELECT " + ", ".join(f"coalesce(jsonb_typeof({column}), 'NULL')"
                              for column in MULTILANG_COLUMNS)
        + f" FROM {TABLE} WHERE id = %s", (cfg_id,))[0]))
    check("jsonb-колонки хранят объект (jsonb_typeof = 'object'), а не строку и не массив",
          all(kind == "object" for kind in kinds.values()), repr(kinds))
    stored = multilang_stored(cfg_id)
    check("значение прочитано из БД целиком и совпадает с разбором: обе формы каждого свойства",
          {column: stored.get(column) for column in MULTILANG_COLUMNS} == expected,
          repr({column: stored.get(column)
                for column in ("synonym", "detailed_info")})[:400])
    pair = sql_rows(f"SELECT synonym->>'ru', synonym->>'en', synonym ? 'de' FROM {TABLE} "
                    "WHERE id = %s", (cfg_id,))
    check("ключи читаются операторами jsonb: ->> по ru и en отдают обе формы, ключа de нет",
          bool(pair) and pair[0][0] == expected["synonym"]["ru"]
          and pair[0][1] == expected["synonym"]["en"] and pair[0][2] is False,
          repr(pair))
    check("в записанной строке нет значений, не являющихся словарём (ни строки, ни массива, ни {})",
          bad_multilang_values(cfg_id) == 0, repr(bad_multilang_values(cfg_id)))

    # ── Г. длинное значение: у jsonb-колонки лимита нет, у текстовой он остался ──
    long_id = 0
    long_catalog = synth_catalog("v39_long", name_mode="fixed", name_value=probe_names[1])
    address = "http://example.invalid/" + "u" * LONG_TEXT_LEN
    edit_xml(long_catalog / "Configuration.xml",
             [("<BriefInformation/>",
               multilang_property_xml("BriefInformation", [("ru", "Д" * LONG_TEXT_LEN)])),
              ("<ConfigurationInformationAddress/>",
               multilang_property_xml("ConfigurationInformationAddress", [("ru", address)]))])
    res_long = load_catalog(str(long_catalog))
    long_id = int(res_long.get("id") or 0)
    state.setdefault("multilang_cfgs", []).append(long_id)
    if check("загружена копия с длинными языковыми формами",
             res_long.get("status") == "loaded" and long_id > 0,
             format_load_result(res_long)[:300]):
        sizes = sql_rows("SELECT length(short_info->>'ru'), length(config_url->>'ru') "
                         f"FROM {TABLE} WHERE id = %s", (long_id,))
        check(f"длины дошли целиком ({LONG_TEXT_LEN} симв.): лимит текстовой колонки "
              "jsonb-колонке не нужен, обрезки нет",
              bool(sizes) and sizes[0][0] == LONG_TEXT_LEN and sizes[0][1] == len(address),
              repr(sizes))
        too_long = try_text_update(long_id, "update_url", "u" * (LONG_TEXT_LEN + 1))
        fits = try_text_update(long_id, "update_url", "u" * (text_limit or 500))
        check("текстовой колонке лимит оставлен: значение длиннее varchar(500) отклоняется, "
              "ровно в лимит — проходит",
              too_long is not None and "too long" in too_long and fits is None,
              repr([too_long[:120] if too_long else None, fits]))
    # ── Д. миграция: повторное применение ничего не меняет, 'und' — переходное состояние ──
    mig_sql = (V39_MIGRATION.read_text(encoding="utf-8", errors="replace")
               if V39_MIGRATION.exists() else "")
    check("миграция V39 существует и пропускает уже jsonb-колонку (повтор не переупаковывает)",
          bool(mig_sql) and "col_type = 'jsonb' THEN" in mig_sql and "CONTINUE;" in mig_sql,
          repr(V39_MIGRATION.exists()))
    check("прежний текст упаковывается ключом 'und': язык снятых до V39 строк не выдумывается",
          "jsonb_build_object(''und''" in mig_sql,
          repr([line.strip() for line in mig_sql.splitlines()
                if "jsonb_build_object" in line]))
    check("пробел до узла не становится значением: btrim → THEN NULL",
          "btrim(" in mig_sql and "THEN NULL" in mig_sql, "")
    check("граница R7 названа самим файлом миграции и SQL её не трогает",
          "config_extensions.synonym" in mig_sql and "R7" in mig_sql
          and "public.config_extensions" not in mig_sql,
          repr([line.strip() for line in mig_sql.splitlines()
                if "config_extensions" in line][:2]))

    seeded = sql_write(f"UPDATE {TABLE} SET synonym = synonym || %s::jsonb WHERE id = %s",
                       ('{"und": "текст до V39"}', cfg_id))
    check("переходное состояние строк до V39 читается: ключ 'und' дописан к существующему словарю",
          seeded == 1 and sql_one(f"SELECT synonym ? 'und' FROM {TABLE} WHERE id = %s",
                                  (cfg_id,)) is True,
          repr([seeded, sql_one(f"SELECT synonym::text FROM {TABLE} WHERE id = %s", (cfg_id,))]))
    before_mig = multilang_stored(cfg_id)
    types_before = column_types(TABLE)
    applied = try_sql_script(mig_sql)
    check("повторное применение миграции к прогретой БД не падает (тип уже jsonb)",
          applied is None, repr(applied)[:300])
    check("повторная миграция не меняет ни типа колонок, ни значений: 'und' остаётся ровно "
          "там, где записан",
          column_types(TABLE) == types_before
          and multilang_stored(cfg_id) == before_mig,
          repr({column: (multilang_stored(cfg_id).get(column) or {})
                for column in ("synonym", "short_info")}))

    again = load_catalog(str(catalog), force=True)
    again_id = int(again.get("id") or 0)
    state.setdefault("multilang_cfgs", []).append(again_id)
    und_keys = " OR ".join(f"{column} ? 'und'" for column in MULTILANG_COLUMNS)
    check("force=True снимает переходное состояние: ключей 'und' в новой строке нет",
          again.get("status") == "reloaded" and again_id > 0
          and sql_one(f"SELECT COUNT(*) FROM {TABLE} WHERE id = %s AND ({und_keys})",
                      (again_id,)) == 0,
          repr([again.get("status"), again_id,
                sql_one(f"SELECT synonym::text FROM {TABLE} WHERE id = %s", (again_id,))]))
    check("после перезагрузки словари равны разбору: 'und' — состояние строки, а не тип колонки",
          {column: multilang_stored(again_id).get(column)
           for column in MULTILANG_COLUMNS} == expected,
          repr(multilang_stored(again_id))[:400])

    # jsonb-колонка не принимает не-jsonb: отказ ловит база, а не код писателя. Без этой
    # проверки утверждение «колонка jsonb» было бы пустым — ту же строку правят иначе,
    # и мусор лёг бы в неё молча (строка вместо словаря по языку).
    garbage = try_text_update(again_id, "copyright", "<не json>")
    check("не-jsonb значение в jsonb-колонку не кладётся: UPDATE отклонён базой",
          garbage is not None, repr(garbage)[:200])
    check("после отказа значение осталось словарём по языку: неудавшаяся правка не испортила строку",
          (multilang_stored(again_id).get("copyright") or {}) == expected["copyright"],
          repr(multilang_stored(again_id).get("copyright"))[:200])

    for cfg in (cfg_id, again_id, long_id):
        delete_configuration(cfg_id=cfg)
    check("раздел убирает за собой: счётники БД равны началу прогона",
          db_counts() == before, repr([before, db_counts()]))
    note("граница узла: V39 меняет ХРАНЕНИЕ, а не создаёт обратную операцию — выгрузить словарь "
         "обратно в v8:item можно только сборкой XML из строк БД (узлы V18/V29), её нет. "
         "Ключ 'und' — переходное состояние строк, снятых до V39: он остаётся, пока строку не "
         "перезагрузили из выгрузки (force=True); проверка называет это прямым запросом.")


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
    for header_id in state.get("multilang_cfgs", []):
        # Раздел 3d снимает свои строки сам. Здесь — страховка для прогона, прерванного
        # до его уборки: без неё в справочнике остаётся заголовок пробы, и следующий запуск
        # отвечает name_conflict на чужой строке. Снимается инструментом, а не SQL: у строки
        # есть состав, и его снимает каскад загрузчика — внешнего ключа с ON DELETE нет.
        if header_id:
            delete_configuration(cfg_id=int(header_id))
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
    ("roles", "3c. перечень ссылок: дети Item и Value", check_roles, ()),
    ("multilang", "3d. многоязычные свойства: v8.item -> jsonb (V39)",
     check_multilang_properties, ()),
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



