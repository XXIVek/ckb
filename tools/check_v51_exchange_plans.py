#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/check_v51_exchange_plans.py — узел V51: свойства планов обмена (шаг П6).

Это постоянная проверка, а не проба шага: она обязана переживать и перезагрузку выгрузок, и
правки кода загрузки. Источник ожиданий — `docs/CONFIGURATION_EXCHANGE_PLANS_PLAN.md`
(разделы 1.1, 2.6, 3, 5.5, 7). Числа круга сняты по самим каталогам выгрузки независимым
подсчётом (`_v51_p6_counts_probe.py`, раздел 15 плана) и перенесены в `PLAN_EXPECTATIONS`
без правок: сглаживать число проверкой — значит подтверждать неверное число (прецедент
узлов V49 и V50). Независимость меры — в отдельной реализации: здесь файл читается
`xml.etree.ElementTree` и считается по ЛОКАЛЬНЫМ именам элементов, тогда как слой разбора
(`src/configuration_exchange_plans.py`) читает тот же файл таблицами свойств и словарями
состояний. Совпадение двух разных реализаций и есть доказательство, что в строку БД легло
содержание файла, а не намерение разбора.

Что сторожится — по контурам:

  1. ГРАНИЦА КРУГА (инвариант Q8 и замера 3.1). План обмена адресуется четырьмя РАЗНЫМИ
     источниками: каталогом `ExchangePlans/` (`<Имя>.xml`), индексом состава
     (`ExchangePlan.<Имя>`), перечнем `configurations.exchange_plans[]` и строками таблицы
     `exchange_plans`. Множества имён сравниваются попарно во все стороны; агрегатный COUNT
     индекса сверяется с построчным обходом (приём V48). Дети вида — вторая нога: записей
     индекса с точечным именем обязано быть ровно `подтверждено_файлом +
     псевдо-записи_слотов_и_модулей` (замер 3.1: `Content`/`Help`/`AdditionalIndexes`/
     `*Module` детьми не являются).
  2. СТРОКА ВИДА ↔ РАЗБОР. Каждая колонка строки обязана совпадать с кругом, разобранным
     ТЕМ ЖЕ модулем (`collect_exchange_plans`), что и загрузка: иначе проверка проверяла бы
     себя, а не то, донёс ли писатель строку.
  3. ДЕТИ ↔ РАЗБОР. Реквизиты вида и колонки его табличных частей, табличные части, формы с
     содержимым, макеты и команды сверяются по uuid с разбором и с независимым подсчётом
     файлов подкаталогов (`Forms/<Имя>.xml` ↔ описание формы, `Ext/Form.xml` ↔ содержимое,
     `Templates/…`, `Ext/*Module.bsl`). Отдельно — инвариант замера 3.2: общие uuid детей
     между конфигурациями не обязаны давать одну строку, потому что предикат области
     видимости включает конфигурацию.
  4. КЛЮЧ РАЗБОРА ↔ КОЛОНКИ СХЕМЫ. Для своих таблиц узла — в обе стороны с точностью до
     колонок цепи ревизий; для общих таблиц детей (`attributes`, `tabular_sections`, `forms`,
     `form_ext`, `templates`) — в одну: колонки этих таблиц принадлежат не только V51, и
     требовать от узла заполнения чужих колонок нельзя.
  5. СТРОКИ ПЕРЕЧНЯ ↔ ФАЙЛ (Q4). `exchange_plan_content` обязана совпадать с
     `ExchangePlans/<Имя>/Ext/Content.xml`: порядок, цель, тег, состояние разрешения и
     `AutoRecord` по каждой строке; `content_count` строки вида равен числу строк перечня
     этой ревизии; `AutoRecord` Allow+Deny равен числу целей (замеры раздела 3). Строки
     перечня версионируются не своей цепью (Q2 вариант A) — ссылка обязана вести на
     CURRENT-ревизию своего плана.
  6. РАЗРЕШИМОСТЬ ЦЕЛЕЙ. Каждая сохранённая цель разрешается ЗАНОВО по строкам индекса
     состава (`resolve_target`): состояние, `target_object_id` и `target_object_uuid` обязаны
     совпасть с сохранёнными. На корпусе неразрешимых целей нет (22 515 из 22 515 `exact`),
     и нули `prefix_only`/`unresolved` здесь — проверяемое утверждение, а не предположение.
  7. СЛОВАРИ СОСТОЯНИЙ. Значения состояний обязаны входить в закрытые словари модуля
     разбора, а распределение по выгрузкам — совпасть с таблицей раздела 2.6
     (`properties_state`, `children_state`, `standard_attributes_state`, `content_state`,
     состояния слотов, `target_resolve_state`, `auto_record_state`, форматы `ext`). Строки с
     `unknown_*` отсутствуют, и отсутствие проверяется, а не предполагается.
  8. ПУСТОЙ КРУГ (Q9). У KomMag каталога вида нет ни файлами, ни строками индекса: это
     состояние выгрузки (`directory_missing`), а не отказ, и ноль строк восьми таблиц обязан
     быть назван именно так.
  9. ВИТРИНЫ, ЦЕПЬ РЕВИЗИЙ, КЛЮЧИ. Витрины `v_current_*` отдают ровно CURRENT-ревизии теми
     же числами, что таблицы; у загруженного круга ревизия первая и единственная; сирот
     (дети без строки вида, перечень без строки вида, `form_ext` без формы) — ноль.
  10. НЕПРИКОСНОВЕННОСТЬ ЧУЖИХ КРУГОВ. Прогон проверки ничего не пишет в таблицы других
      узлов: снимок числа строк до и после сравнивается, свои таблицы исключены явно.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python tools/check_v51_exchange_plans.py [MinCfg|KomMag|BGU2|BP3|all]
По умолчанию — `all`: все строки заголовков, для которых находится каталог выгрузки. Код
возврата 0 — расхождений нет. Пропуск контура называется причиной (нет строки заголовка, нет
выгрузки, строк узла не загружалось, выгрузка новее записей): ноль проверок не читается как
«всё хорошо».
"""


import ast
import json
import sys
import uuid
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

try:  # кириллица в консоли Windows (cp1251) — как в остальных валидаторах
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from configuration_exchange_plans import (  # noqa: E402
    AUTO_RECORD_ALLOW, AUTO_RECORD_DENY, AUTO_RECORD_STATES, CHILD_KINDS,
    CHILD_STATES, CHILD_TABLE_BY_KIND, CIRCLE_DISCREPANCIES, COMMANDS_TABLE_NAME,
    CONTENT_TABLE_NAME, CONTENT_STATES,
    DIR_NAME, INDEX_NAME_SEPARATOR, INDEX_OBJECT_TYPE,
    OBSERVATION_DIRECTORY_MISSING, PROPERTIES_STATES, SLOT_STATES,
    STANDARD_ATTRIBUTE_STATES, TABLE_NAME, TARGET_EXACT, TARGET_STATES, XML_PROPERTY_NAMES,
    collect_exchange_plans, index_object_name, index_row_key, kind_root_index_rows,
    resolve_target,
)
from configuration_exchange_plans_loader import FORM_EXT_TABLE, read_index_records  # noqa: E402
from configuration_load_contract import EXCHANGE_PLAN_TABLES  # noqa: E402
from configuration_module_slots import resolve_dump_dir  # noqa: E402
from current_revision import current_view  # noqa: E402
from external_db import transaction  # noqa: E402

DUMP_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
DEFAULT_SCOPE = "all"
MAX_NAMES = 10          # сколько расхождений называется именами (дальше — только число)

# Колонки, которые принадлежат цепи ревизий (узел V19), а не узлу V51: их заполняет не
# разбор, и сравнивать их с ключом строки разбора — значит требовать от слоя чужого.
REVISION_COLUMNS = ("id", "configuration_uuid", "created_at", "revision_no", "changed_at",
                    "changed_by", "is_committed")
# Число колонок трёх своих таблиц узла — эталон шага П1 (миграция V51 + зеркало DDL).
# Общих таблиц детей здесь нет: их колонки принадлежат не только V51 (замер 5.6 плана).
EXPECTED_COLUMN_COUNTS = {TABLE_NAME: 65, CONTENT_TABLE_NAME: 18,
                          COMMANDS_TABLE_NAME: 24}
# Колонки своих таблиц, которые писатель получает не из свойств файла, а из обхода
# подкаталогов, из слотов или из перечня детей: ключ строки разбора их не носит в тех же
# именах, поэтому контур 4 называет их отдельно, а не считает провалом.
DERIVED_PLAN_COLUMNS = ("help_content", "additional_indexes_content", "help_state",
                        "additional_indexes_state", "content_count", "content_state",
                        "standard_attributes_state", "children_state",
                        "unknown_property_names", "source_path", "attribute_uuids",
                        "tabular_section_uuids", "command_uuids", "form_names",
                        "template_names")
# Ключи строки разбора, которые писатель НЕ переносит в таблицу. Причина названа прямо:
# состояние свойств ребёнка, неизвестные имена свойств и состояние модуля команды живут в
# ответе стадии, а не в колонках — общих таблиц детей (`attributes`, `tabular_sections`,
# `forms`, `templates`) колонок под такие состояния нет (замер 5.6 плана), а тексты модулей
# пишет узел V47 (Q8 — граница детей узла V51). Молча исключить их нельзя: исключение
# обязано быть перечисленным, иначе «колонки нет» читалось бы потерей знания.
REPORT_ONLY_KEYS = {
    "attributes": ("properties_state", "unknown_property_names"),
    "tabular_sections": ("properties_state", "unknown_property_names"),
    "forms": ("properties_state", "unknown_property_names"),
    "templates": ("properties_state", "unknown_property_names"),
    COMMANDS_TABLE_NAME: ("module_state",),
}
# Колонки, которые писатель берёт из связи строки, а не из разбора: их отсутствие в ключе
# разбора — не дефект, а контракт писателя (прецедент `TARGET_WRITER_COLUMNS` узла V50).
WRITER_SET_COLUMNS = {CONTENT_TABLE_NAME: ("exchange_plan_object_uuid",)}
# Общие таблицы детей: узел V51 пишет в них только свои колонки (замер 5.6 плана), поэтому
# сравнение ключа разбора с колонками идёт в одну сторону.
SHARED_CHILD_TABLES = ("attributes", "tabular_sections", "forms", FORM_EXT_TABLE,
                       "templates")
CHILD_TABLES = tuple(CHILD_TABLE_BY_KIND.values())
# Витрины круга (миграция V51): таблица → витрина текущего состояния.
CURRENT_VIEWS = {
    TABLE_NAME: "v_current_exchange_plans",
    CONTENT_TABLE_NAME: "v_current_exchange_plan_content",
    COMMANDS_TABLE_NAME: "v_current_commands",
    "attributes": "v_current_attributes",
    "tabular_sections": "v_current_tabular_sections",
    "forms": "v_current_forms",
    FORM_EXT_TABLE: "v_current_form_ext",
    "templates": "v_current_templates",
}
# Что проверка трогать не должна (сверяется до и после прогона) — круги других узлов.
FOREIGN_TABLES = ("configurations", "configuration_objects", "session_parameters", "roles",
                  "role_rights", "common_attributes", "common_attribute_targets",
                  "subsystems", "subsystem_content", "common_modules",
                  "common_module_sources", "bsl_modules", "external_report",
                  "config_aliases", "config_snippets", "config_cross_references")

# ── ожидания проверки (числа плана docs/CONFIGURATION_EXCHANGE_PLANS_PLAN.md) ──────────
# Ключ — каталог выгрузки, а не имя строки заголовка: имя заголовка меняется вместе с
# выгрузкой, а каталог — адрес, по которому проверка находит файлы (прецедент V50).
#   raw_*      — независимые меры по самим файлам (раздел 15 плана, `_v51_p6_counts_probe.py`):
#                files / bytes — каталог `ExchangePlans/` (файлы регистрации вида);
#                prop_tags — теги `<Properties>` суммарно по файлам (замер 2.6: ровно 40
#                тегов, у MinCfg один файл без `StandardAttributes` → 39);
#                child_<вид> — дети в `<ChildObjects>`; child_ts_Attribute — колонки
#                табличных частей из вложенного `<ChildObjects>` (замер 3.3: 106 + 21 = 127);
#                standard_total — вхождения `<StandardAttributes>` (замер 3.3: 135 + 18 = 153);
#                content_files / content_items — слот `Ext/Content.xml` и его цели;
#                auto_Allow / auto_Deny — значения `AutoRecord` (сумма обязана равняться
#                content_items: это и есть проверка полноты перечня);
#                help_files / help_bytes, addidx_files / addidx_bytes — слоты `Help` и
#                `AdditionalIndexes` (замер 5.3: 2 / 4 / 1 файла, 1624 байта на корпус);
#                help_resource_dirs — каталоги `Ext/Help/` (наблюдение `help_resources_dir`);
#                form_desc / form_ext_xml / form_ext_bin / form_module / form_help —
#                `Forms/<Имя>.xml`, `Forms/<Имя>/Ext/Form.xml|.bin`, `Module.bsl`,
#                `Ext/Help.xml` формы (слот формы — НЕ слот вида, раздел 15.2);
#                tpl_desc / tpl_ext_xml / tpl_ext_txt — `Templates/<Имя>.xml` и содержимое;
#                obj_module / mgr_module / cmd_module — файлы модулей вида и команд;
#   rows_*     — строки восьми таблиц, которые обязан дать узел (реквизиты вида и колонки его
#                табличных частей считаются вместе: в `attributes` они лежат одной таблицей);
#   idx_*      — записи индекса состава вида (их пишет узел V43, а не V51: третья нога круга;
#                `idx_Form`/`idx_Template` дают по две записи на ребёнка — описание и
#                содержимое, замер 3.1); `header_list: None` — значения колонки нет вовсе;
#   parse_*    — то, что обязан сообщить разбор круга С индексом состава (состояния слоя, а
#                не строки БД);
#   pseudo / child_mismatch / index_only / file_only / uuid_mismatch / declaration_mismatch /
#   files_failed — расхождения круга: на четырёх выгрузках их ноль, и ноль здесь —
#                проверяемое утверждение, а не предположение; `pseudo` — псевдо-записи индекса
#                (слоты и модули), их число обязано равняться разнице записей индекса вида и
#                подтверждённых файлом детей (замер 3.1);
#   directory_missing — KomMag: позиции вида в выгрузке нет (Q9), и это состояние, а не отказ.
PLAN_EXPECTATIONS = {
    "MinCfg": {
        "raw_files": 2, "raw_bytes": 28972, "raw_prop_tags": 79,
        "raw_child_Attribute": 3, "raw_child_ts_Attribute": 1,
        "raw_child_TabularSection": 1, "raw_child_Form": 3, "raw_child_Template": 1,
        "raw_child_Command": 1, "raw_standard_total": 9,
        "raw_content_files": 2, "raw_content_items": 9,
        "raw_auto_Allow": 9, "raw_auto_Deny": 0,
        "raw_help_files": 2, "raw_help_bytes": 464,
        "raw_addidx_files": 1, "raw_addidx_bytes": 662, "raw_help_resource_dirs": 2,
        "raw_form_desc": 3, "raw_form_ext_xml": 3, "raw_form_ext_bin": 0,
        "raw_form_module": 2, "raw_form_help": 0,
        "raw_tpl_desc": 1, "raw_tpl_ext_xml": 0, "raw_tpl_ext_txt": 1,
        "raw_obj_module": 2, "raw_mgr_module": 2, "raw_cmd_module": 1,
        "rows_plans": 2, "rows_attributes": 4, "rows_tabular_sections": 1,
        "rows_forms": 3, "rows_form_ext": 3, "rows_templates": 1, "rows_commands": 1,
        "rows_content": 9,
        "idx_roots": 2, "idx_children": 26,
        "idx_Attribute": 4, "idx_TabularSection": 1, "idx_Form": 6, "idx_Template": 2,
        "idx_Command": 1, "idx_Content": 2, "idx_Help": 4, "idx_AdditionalIndexes": 1,
        "idx_ObjectModule": 2, "idx_ManagerModule": 2, "idx_CommandModule": 1,
        "header_list": 2,
        "parse_props_all_known": 1, "parse_props_absent": 1,
        "parse_children_with": 2, "parse_children_empty": 0,
        "parse_std_present": 1, "parse_std_absent": 1,
        "parse_content_with": 2, "parse_content_empty": 0,
        "parse_resolve_exact": 9, "parse_auto_Allow": 9, "parse_auto_Deny": 0,
        "parse_form_ext_xml": 3, "parse_form_ext_bin": 0,
        "parse_tpl_ext_txt": 1, "parse_tpl_ext_xml": 0,
        "parse_obj_module": 2, "parse_mgr_module": 2, "parse_cmd_module": 1,
        "parse_std_entries": 9, "parse_std_distinct": 9,
        "pseudo": 16, "child_mismatch": 0, "index_only": 0, "file_only": 0,
        "uuid_mismatch": 0, "declaration_mismatch": 0, "files_failed": 0,
        "directory_missing": 0,
    },
    "KomMag": {
        "raw_files": 0, "raw_bytes": 0, "raw_prop_tags": 0,
        "raw_child_Attribute": 0, "raw_child_ts_Attribute": 0,
        "raw_child_TabularSection": 0, "raw_child_Form": 0, "raw_child_Template": 0,
        "raw_child_Command": 0, "raw_standard_total": 0,
        "raw_content_files": 0, "raw_content_items": 0,
        "raw_auto_Allow": 0, "raw_auto_Deny": 0,
        "raw_help_files": 0, "raw_help_bytes": 0, "raw_addidx_files": 0,
        "raw_addidx_bytes": 0, "raw_help_resource_dirs": 0,
        "raw_form_desc": 0, "raw_form_ext_xml": 0, "raw_form_ext_bin": 0,
        "raw_form_module": 0, "raw_form_help": 0,
        "raw_tpl_desc": 0, "raw_tpl_ext_xml": 0, "raw_tpl_ext_txt": 0,
        "raw_obj_module": 0, "raw_mgr_module": 0, "raw_cmd_module": 0,
        "rows_plans": 0, "rows_attributes": 0, "rows_tabular_sections": 0,
        "rows_forms": 0, "rows_form_ext": 0, "rows_templates": 0, "rows_commands": 0,
        "rows_content": 0,
        "idx_roots": 0, "idx_children": 0, "header_list": None,
        "parse_props_all_known": 0, "parse_props_absent": 0,
        "parse_children_with": 0, "parse_children_empty": 0,
        "parse_std_present": 0, "parse_std_absent": 0,
        "parse_content_with": 0, "parse_content_empty": 0,
        "parse_resolve_exact": 0, "parse_auto_Allow": 0, "parse_auto_Deny": 0,
        "parse_form_ext_xml": 0, "parse_form_ext_bin": 0,
        "parse_tpl_ext_txt": 0, "parse_tpl_ext_xml": 0,
        "parse_obj_module": 0, "parse_mgr_module": 0, "parse_cmd_module": 0,
        "parse_std_entries": 0, "parse_std_distinct": 0,
        "pseudo": 0, "child_mismatch": 0, "index_only": 0, "file_only": 0,
        "uuid_mismatch": 0, "declaration_mismatch": 0, "files_failed": 0,
        "directory_missing": 1,
    },
    "BGU2": {
        "raw_files": 18, "raw_bytes": 459040, "raw_prop_tags": 720,
        "raw_child_Attribute": 106, "raw_child_ts_Attribute": 21,
        "raw_child_TabularSection": 18, "raw_child_Form": 34, "raw_child_Template": 35,
        "raw_child_Command": 0, "raw_standard_total": 153,
        "raw_content_files": 18, "raw_content_items": 9638,
        "raw_auto_Allow": 311, "raw_auto_Deny": 9327,
        "raw_help_files": 4, "raw_help_bytes": 928,
        "raw_addidx_files": 0, "raw_addidx_bytes": 0, "raw_help_resource_dirs": 4,
        "raw_form_desc": 34, "raw_form_ext_xml": 34, "raw_form_ext_bin": 0,
        "raw_form_module": 30, "raw_form_help": 4,
        "raw_tpl_desc": 35, "raw_tpl_ext_xml": 9, "raw_tpl_ext_txt": 26,
        "raw_obj_module": 11, "raw_mgr_module": 17, "raw_cmd_module": 0,
        "rows_plans": 18, "rows_attributes": 127, "rows_tabular_sections": 18,
        "rows_forms": 34, "rows_form_ext": 34, "rows_templates": 35, "rows_commands": 0,
        "rows_content": 9638,
        "idx_roots": 18, "idx_children": 357,
        "idx_Attribute": 127, "idx_TabularSection": 18, "idx_Form": 68, "idx_Template": 70,
        "idx_Command": 0, "idx_Content": 18, "idx_Help": 28, "idx_AdditionalIndexes": 0,
        "idx_ObjectModule": 11, "idx_ManagerModule": 17, "idx_CommandModule": 0,
        "header_list": 18,
        "parse_props_all_known": 18, "parse_props_absent": 0,
        "parse_children_with": 18, "parse_children_empty": 0,
        "parse_std_present": 18, "parse_std_absent": 0,
        "parse_content_with": 18, "parse_content_empty": 0,
        "parse_resolve_exact": 9638, "parse_auto_Allow": 311, "parse_auto_Deny": 9327,
        "parse_form_ext_xml": 34, "parse_form_ext_bin": 0,
        "parse_tpl_ext_txt": 26, "parse_tpl_ext_xml": 9,
        "parse_obj_module": 11, "parse_mgr_module": 17, "parse_cmd_module": 0,
        "parse_std_entries": 153, "parse_std_distinct": 9,
        "pseudo": 143, "child_mismatch": 0, "index_only": 0, "file_only": 0,
        "uuid_mismatch": 0, "declaration_mismatch": 0, "files_failed": 0,
        "directory_missing": 0,
    },
    "BP3": {
        "raw_files": 26, "raw_bytes": 632707, "raw_prop_tags": 1040,
        "raw_child_Attribute": 162, "raw_child_ts_Attribute": 24,
        "raw_child_TabularSection": 21, "raw_child_Form": 31, "raw_child_Template": 30,
        "raw_child_Command": 0, "raw_standard_total": 209,
        "raw_content_files": 26, "raw_content_items": 12868,
        "raw_auto_Allow": 21, "raw_auto_Deny": 12847,
        "raw_help_files": 1, "raw_help_bytes": 232,
        "raw_addidx_files": 0, "raw_addidx_bytes": 0, "raw_help_resource_dirs": 1,
        "raw_form_desc": 31, "raw_form_ext_xml": 30, "raw_form_ext_bin": 1,
        "raw_form_module": 23, "raw_form_help": 1,
        "raw_tpl_desc": 30, "raw_tpl_ext_xml": 9, "raw_tpl_ext_txt": 21,
        "raw_obj_module": 20, "raw_mgr_module": 25, "raw_cmd_module": 0,
        "rows_plans": 26, "rows_attributes": 186, "rows_tabular_sections": 21,
        "rows_forms": 31, "rows_form_ext": 31, "rows_templates": 30, "rows_commands": 0,
        "rows_content": 12868,
        "idx_roots": 26, "idx_children": 405,
        "idx_Attribute": 186, "idx_TabularSection": 21, "idx_Form": 62, "idx_Template": 60,
        "idx_Command": 0, "idx_Content": 26, "idx_Help": 5, "idx_AdditionalIndexes": 0,
        "idx_ObjectModule": 20, "idx_ManagerModule": 25, "idx_CommandModule": 0,
        "header_list": 26,
        "parse_props_all_known": 26, "parse_props_absent": 0,
        "parse_children_with": 25, "parse_children_empty": 1,
        "parse_std_present": 26, "parse_std_absent": 0,
        "parse_content_with": 21, "parse_content_empty": 5,
        "parse_resolve_exact": 12868, "parse_auto_Allow": 21, "parse_auto_Deny": 12847,
        "parse_form_ext_xml": 30, "parse_form_ext_bin": 1,
        "parse_tpl_ext_txt": 21, "parse_tpl_ext_xml": 9,
        "parse_obj_module": 20, "parse_mgr_module": 25, "parse_cmd_module": 0,
        "parse_std_entries": 209, "parse_std_distinct": 9,
        "pseudo": 137, "child_mismatch": 0, "index_only": 0, "file_only": 0,
        "uuid_mismatch": 0, "declaration_mismatch": 0, "files_failed": 0,
        "directory_missing": 0,
    },
}
# Итог по корпусу (четыре выгрузки): те же величины, что таблица раздела 3 и таблица П6 плана
# (46 файлов, 317 реквизитов вместе с колонками табличных частей, 40 табличных частей,
# 68 форм, 66 макетов, 1 команда, 371 вхождение стандартных реквизитов, 22 515 целей
# перечня). Сверяется только когда прогнал все четыре выгрузки: сравнивать итог по четырём с
# суммой по меньшему числу выгрузок — ложное расхождение (прецедент V50).
CORPUS_TOTALS = {
    "raw_files": 46, "raw_bytes": 1120719, "raw_prop_tags": 1839,
    "raw_child_Attribute": 271, "raw_child_ts_Attribute": 46,
    "raw_child_TabularSection": 40, "raw_child_Form": 68, "raw_child_Template": 66,
    "raw_child_Command": 1, "raw_standard_total": 371,
    "raw_content_files": 46, "raw_content_items": 22515,
    "raw_auto_Allow": 341, "raw_auto_Deny": 22174,
    "raw_help_files": 7, "raw_help_bytes": 1624, "raw_addidx_files": 1,
    "raw_addidx_bytes": 662, "raw_help_resource_dirs": 7,
    "raw_form_desc": 68, "raw_form_ext_xml": 67, "raw_form_ext_bin": 1,
    "raw_form_module": 55, "raw_form_help": 5, "raw_tpl_desc": 66, "raw_tpl_ext_xml": 18,
    "raw_tpl_ext_txt": 48, "raw_obj_module": 33, "raw_mgr_module": 44,
    "raw_cmd_module": 1,
    "rows_plans": 46, "rows_attributes": 317, "rows_tabular_sections": 40,
    "rows_forms": 68, "rows_form_ext": 68, "rows_templates": 66, "rows_commands": 1,
    "rows_content": 22515,
    "idx_roots": 46, "idx_children": 788, "pseudo": 296,
    "parse_std_entries": 371,
}


PASSED, FAILED, SKIPPED, INFO = [], [], [], []


def check(name, ok, detail=""):
    (PASSED if ok else FAILED).append(name)
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or not detail else f"\n      {detail}"))


def skip(name, reason):
    SKIPPED.append(name)
    print(f"SKIP {name}\n      {reason}")


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


def names(sample):
    """Сколько расхождений называется именами — дальше только число."""
    shown = list(sample)[:MAX_NAMES]
    tail = "" if len(sample) <= MAX_NAMES else f" … ещё {len(sample) - MAX_NAMES}"
    return ", ".join(str(item) for item in shown) + tail


def _brief(value):
    text = repr(value)
    return text if len(text) <= 200 else text[:200] + "…"


def counts_diff(actual, expected, label, tag):
    """Сравнивает Counter с эталоном по всем ключам эталона и лишним ключам факта."""
    wrong = []
    for key, want in expected.items():
        got = actual.get(key, 0)
        if got != want:
            wrong.append(f"{label} {key}: факт {got}, план {want}")
    extra = sorted(key for key, value in actual.items()
                   if key not in expected and value and not key.startswith("tag_"))
    for key in extra:
        wrong.append(f"{label} {key}: факт {actual[key]}, в плане такого ключа нет")
    check(f"{tag}: {label} совпадают с планом", not wrong, "; ".join(wrong[:MAX_NAMES]))


def table_columns(cur, table):
    rows = q(cur, "SELECT column_name FROM information_schema.columns "
                  "WHERE table_schema='public' AND table_name=%s "
                  "ORDER BY ordinal_position", (table,))
    return [row["column_name"] for row in rows]


# ═══ независимая мера круга по самим файлам (раздел 15 плана) ══════════════════════════
# Реализация намеренно НЕ совпадает со слоем разбора: файл читается ElementTree и считается
# по локальным именам элементов, состояния не выводятся вовсе. Слоты вида ищутся точным
# относительным путём, а не суффиксом: у форм и команд есть свои `Ext/Help.xml` (замер BGU2:
# 4 слота вида + 4 слота формы), и суффиксный поиск смешал бы их (раздел 15.2 плана).

SLOT_FILE_KEYS = (
    ("raw_obj_module", ("Ext/ObjectModule.bsl",)),
    ("raw_mgr_module", ("Ext/ManagerModule.bsl",)),
    ("raw_content_files", ("Ext/Content.xml",)),
)


def local(tag):
    """Локальное имя элемента без префикса пространства имён (`{urn}Name` → `Name`)."""
    return str(tag).rsplit("}", 1)[-1]


def named(elem, name):
    return [child for child in elem if local(child.tag) == name]


def first_named(elem, name):
    found = named(elem, name)
    return found[0] if found else None


def text_of(elem, name):
    node = first_named(elem, name)
    return (node.text or "").strip() if node is not None and node.text else ""


def measure_children(container, prefix, counts):
    """Число детей каждого вида; вызов — по одному на блок `<ChildObjects>`, счёт складывается."""
    for kind_name in CHILD_KINDS:
        counts[f"{prefix}{kind_name}"] += len(named(container, kind_name))


def measure_content_slot(path, counts):
    """Слот `Ext/Content.xml`: цели перечня и значения `AutoRecord` (таблица перечня Q4)."""
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    for item in (el for el in root.iter() if local(el.tag) == "Item"):
        if not named(item, "Metadata"):
            continue
        counts["raw_content_items"] += 1
        for node in named(item, "AutoRecord"):
            counts["raw_auto_" + (node.text or "").strip()] += 1


def measure_registration(path):
    counts = Counter()
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    obj = next((el for el in root.iter() if local(el.tag) == "ExchangePlan"), None)
    if obj is None:
        return counts
    props = first_named(obj, "Properties")
    if props is not None:
        for prop_name in XML_PROPERTY_NAMES:
            counts["tag_" + prop_name] = len(named(props, prop_name))
    counts["raw_prop_tags"] = sum(counts["tag_" + name] for name in XML_PROPERTY_NAMES)
    children = first_named(obj, "ChildObjects")
    if children is not None:
        measure_children(children, "raw_child_", counts)
        for tabular in named(children, "TabularSection"):
            inner = first_named(tabular, "ChildObjects")
            if inner is not None:
                measure_children(inner, "raw_child_ts_", counts)
    for block in (el for el in root.iter() if local(el.tag) == "StandardAttributes"):
        counts["raw_standard_total"] += len(list(block))
    return counts


def measure_object_dir(directory):
    """Файлы содержимого одного плана обмена (вызов — по одному на каталог вида).

    Слоты вида (`Ext/…`) ищутся точным относительным путём, а не суффиксом: у форм и команд
    есть свои `Ext/Help.xml` (замер BGU2: 4 слота вида + 4 слота формы), и суффиксный поиск
    смешал бы их — ровно та ошибка, из-за которой первый замер П0 назвал 8 вместо 4
    (раздел 15.2 плана).
    """
    counts = Counter()
    has_help_resources = False
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(directory).as_posix()
        parts = rel.split("/")
        for key, slots in SLOT_FILE_KEYS:
            if rel in slots:
                counts[key] += 1
        if rel == "Ext/Help.xml":
            counts["raw_help_files"] += 1
            counts["raw_help_bytes"] += path.stat().st_size
        if rel == "Ext/AdditionalIndexes.xml":
            counts["raw_addidx_files"] += 1
            counts["raw_addidx_bytes"] += path.stat().st_size
        if len(parts) >= 3 and parts[0] == "Ext" and parts[1] == "Help":
            has_help_resources = True
        if len(parts) >= 2 and parts[0] == "Forms":
            if parts[-1] == "Form.xml":
                counts["raw_form_ext_xml"] += 1
            elif parts[-1] == "Form.bin":
                counts["raw_form_ext_bin"] += 1
            elif parts[-1] == "Module.bsl":
                counts["raw_form_module"] += 1
            elif len(parts) == 2 and rel.endswith(".xml"):
                counts["raw_form_desc"] += 1
            elif len(parts) >= 3 and parts[-1] == "Help.xml":
                counts["raw_form_help"] += 1
        if len(parts) >= 2 and parts[0] == "Templates":
            if len(parts) == 2 and rel.endswith(".xml"):
                counts["raw_tpl_desc"] += 1
            elif parts[-1] == "Template.txt":
                counts["raw_tpl_ext_txt"] += 1
            elif parts[-1] == "Template.xml":
                counts["raw_tpl_ext_xml"] += 1
        if len(parts) >= 3 and parts[0] == "Commands" and parts[-1] == "CommandModule.bsl":
            counts["raw_cmd_module"] += 1
        if rel == "Ext/Content.xml":
            measure_content_slot(path, counts)
    if has_help_resources:
        # Наблюдение `help_resources_dir` считается на план, а не на файл: именно его называет
        # ответ стадии (число планов с каталогом ресурсов — 2 / 4 / 1, раздел 15 плана).
        counts["raw_help_resource_dirs"] += 1
    return counts


def raw_measures(dump_dir):
    """Мера круга по файлам: файл регистрации плюс каталог объекта на каждый такой файл."""
    root = Path(dump_dir) / DIR_NAME
    totals, per_name, unreadable = Counter(), {}, []
    if not root.is_dir():
        return totals, per_name, unreadable
    for entry in sorted(root.iterdir()):
        if entry.is_dir() or entry.suffix.lower() != ".xml":
            continue
        try:
            counts = measure_registration(entry)
        except ET.ParseError as exc:
            unreadable.append((entry.name, str(exc)))
            continue
        counts["raw_bytes"] += entry.stat().st_size
        object_dir = entry.with_suffix("")
        if object_dir.is_dir():
            counts.update(measure_object_dir(object_dir))
        per_name[entry.stem] = counts
        for key, value in counts.items():
            totals[key] += value
    totals["raw_files"] = len(per_name)
    return totals, per_name, unreadable


def parse_circle(dump_dir, index_rows):
    """Разобрать круг ТЕМ ЖЕ модулем, что и загрузка.

    Сравнение строки с файлом идёт по разбору, а не по второй реализации чтения XML: иначе
    проверка проверяла бы сама себя, а не то, донёс ли писатель строку.
    """
    return collect_exchange_plans(Path(dump_dir), index_rows=index_rows)


# ═══ строки БД ═════════════════════════════════════════════════════════════════════════
def read_plan_rows(cur, configuration_uuid):
    return q(cur, f"SELECT * FROM {TABLE_NAME} WHERE configuration_uuid = %s::uuid",
             [str(configuration_uuid)])


def read_content_rows(cur, configuration_uuid):
    return q(cur, f"SELECT * FROM {CONTENT_TABLE_NAME} WHERE configuration_uuid = %s::uuid",
             [str(configuration_uuid)])


def read_child_rows(cur, table, parents, configuration_uuid):
    """Строки детей круга вида: `parent_type` + `parent_uuid` + нога конфигурации.

    Предикат обязан быть ограничен кругом, а не всей таблицей: в `attributes`, `forms`,
    `templates` лежат и строки внешних отчётов (замер 5.6 плана). Нога `configuration_uuid`
    обязательна и по второй причине: uuid детей повторяются между конфигурациями
    (замер 3.2: 9 общих uuid реквизитов и 2 общих uuid описаний форм), поэтому выборка
    только по `parent_uuid` захватила бы строки чужого круга — тот же дефект, который узел
    V47 закрывает в снятии круга.
    """
    if not parents:
        return []
    return q(cur, f"SELECT * FROM {table} WHERE parent_type = 'configuration_objects' "
                  "AND parent_uuid = ANY(%s::uuid[]) AND configuration_uuid = %s::uuid",
             [list(parents), str(configuration_uuid)])


def read_form_ext_rows(cur, parents):
    """Строки `form_ext` круга: своей колонки конфигурации у таблицы нет (узел V14).

    Область видимости — нога детей (`parent_type` + `parent_uuid`); `configuration_uuid`
    читается витриной `v_current_form_ext` через связь со строкой формы. Дублировать ногу
    здесь значит выдумать колонку, которой в живой схеме нет.
    """
    if not parents:
        return []
    return q(cur, f"SELECT * FROM {FORM_EXT_TABLE} WHERE parent_type = "
                  "'configuration_objects' AND parent_uuid = ANY(%s::uuid[])",
             [list(parents)])


def index_aggregates(cur, configuration_id):
    """Записи индекса состава вида: агрегатным COUNT и построчным обходом (приём V48)."""
    roots = q(cur, "SELECT object_name, uuid::text AS uuid FROM configuration_objects "
                   "WHERE configuration_id = %s AND object_type = %s "
                   "AND (child_type IS NULL OR child_type = '')",
              (int(configuration_id), INDEX_OBJECT_TYPE))
    children = q(cur, "SELECT object_name, child_type FROM configuration_objects "
                      "WHERE configuration_id = %s AND object_type = %s "
                      "AND child_type IS NOT NULL AND child_type <> ''",
                 (int(configuration_id), INDEX_OBJECT_TYPE))
    by_type = Counter(str(row["child_type"]) for row in children)
    return roots, children, by_type


def header_array(cur, configuration_id):
    """Перечень вида в заголовке (`configurations.exchange_plans`, узел V43).

    Различает «значения нет вовсе» (None) и «перечень пуст»: нулём перечня быть не может,
    это разные состояния колонки (тот же контракт различимого нуля, что у V46/V50).
    """
    row = one(cur, "SELECT exchange_plans FROM configurations WHERE id = %s",
              (int(configuration_id),))
    value = row.get("exchange_plans")
    if value is None:
        return None
    return [str(item) for item in value]


# ═══ сравнение строки БД со строкой разбора ═══════════════════════════════════════════
# Колонки, где контракт писателя сглаживает состояние: сравнение обязано это называть, а не
# считать расхождением и не молчать. Перечислены обе такие колонки круга V51 с указанием,
# какое состояние при этом теряет различимость и где оно называется вместо колонки.
SMOOTHED_EMPTY_JSON_OBJECT_COLUMNS = ("synonym",)
# Писатель `jsonb_object` (external_table_writer) отсутствующее значение приводит к `{}`;
# «синонима нет» и «синоним пустой» в колонке неразличимы. Различие держит состояние
# `properties_state` строки и отсутствие имени в словаре свойств — их проверяют контуры 7 и 4.
SMOOTHED_EMPTY_TEXT_COLUMNS = ("ext",)
# Колонка `text` не различает пустую строку и NULL. Пустота содержимого формулы или макета
# называется парой `ext_size` / `ext_truncated` и форматом `ext_format`, их проверяет
# отдельная проверка контура 7, а не сравнение значений.


def norm_value(value):
    """Одно представление для одного значения: uuid, булево, целое, jsonb — каноническая форма.

    `None` остаётся `None`: пустая строка и отсутствие значения — РАЗНЫЕ состояния, и
    сглаживать их нельзя (на этом различии построен словарь состояний слоя разбора).
    Нормализуется только представление: `uuid.UUID` против строки, `bool` против `true/false`,
    `int` против строки, `dict`/`list` против строки JSON.
    """
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, uuid.UUID):
        return str(value).lower()
    if value is None:
        return None
    text = str(value).strip()
    # Колонки блока (`attributes.type`, `attributes.tooltip` — text по живой схеме, см. замер
    # 5.6 плана) хранят сериализованное значение, а разбор держит его структурой; писатель
    # для текстовой колонки берёт Python-представление (`{'ru': '…'}`), для jsonb — JSON.
    # Сравнивать текст со структурой напрямую — значит выдумывать расхождение формата файла,
    # поэтому текст читается любым из двух представлений и приводится к той же канонической
    # форме. Прочитать не удалось — сравнивается текст как есть.
    if text[:1] in "[{":
        for loader in (json.loads, ast.literal_eval):
            try:
                return json.dumps(loader(text), ensure_ascii=False, sort_keys=True)
            except (ValueError, SyntaxError, TypeError):
                continue
    return text


def values_equal(db_value, parsed_value, column):
    """Равны ли значения колонки и строки разбора, с названными сглаживаниями контракта."""
    db, parsed = norm_value(db_value), norm_value(parsed_value)
    if db == parsed:
        return True
    if column in SMOOTHED_EMPTY_JSON_OBJECT_COLUMNS and parsed is None and db in ("{}", ""):
        return True
    if column in SMOOTHED_EMPTY_TEXT_COLUMNS and parsed in ("", None) and db is None:
        return True
    return False


def compare_rows(tag, label, db_rows, parsed_rows, key, ignore, columns):
    """Сверяет строки БД со строками разбора по общему ключу и по всем общим колонкам.

    Сравнение идёт по пересечению ключей разбора и колонок таблицы: колонки, которых у
    разбора нет (цепь ревизий, служебные колонки писателя), перечислены в `ignore`; ключ
    разбора без колонки находит контур 4, а не эта функция.
    """
    by_db, by_parsed, problems = {}, {}, []
    for row in db_rows:
        by_db.setdefault(str(row.get(key) or ""), row)
    for row in parsed_rows:
        by_parsed.setdefault(str(row.get(key) or ""), row)
    only_db = sorted(set(by_db) - set(by_parsed))
    only_parsed = sorted(set(by_parsed) - set(by_db))
    if only_db:
        problems.append(f"в базе без разбора: {names(only_db)}")
    if only_parsed:
        problems.append(f"в разборе без базы: {names(only_parsed)}")
    shared = sorted(set(by_db) & set(by_parsed))
    comparable = sorted((set(parsed_rows[0]) if parsed_rows else set()) & set(columns)
                        - set(ignore) - set(REVISION_COLUMNS))
    for key_value in shared:
        db_row, parsed_row = by_db[key_value], by_parsed[key_value]
        for column in comparable:
            if column not in parsed_row:
                continue
            if not values_equal(db_row.get(column), parsed_row[column], column):
                problems.append(f"{key_value}: {column} — база "
                                f"{_brief(db_row.get(column))}, "
                                f"разбор {_brief(parsed_row[column])}")
    check(f"{tag}: {label} совпадают с разбором ({len(shared)} строк, "
          f"{len(comparable)} колонок)", not problems, "; ".join(problems[:MAX_NAMES]))
    return len(shared)


# ═══ контур 1: граница круга ═══════════════════════════════════════════════════════════
def set_diff(label, left, right, tag):
    """Сравнивает два множества адресов; расхождение называется поимённо с обеих сторон."""
    only_left = sorted(left - right)
    only_right = sorted(right - left)
    check(f"{tag}: {label}", not only_left and not only_right,
          "; ".join(filter(None, [
              f"только слева: {names(only_left)}" if only_left else "",
              f"только справа: {names(only_right)}" if only_right else ""])))


def check_circle(cur, header, dump_dir, index_info, expect, tag):
    """Четыре ноги адреса плана обмена и две ноги детей (инвариант Q8, замер 3.1)."""
    plan_uuid = str(header["uuid"])
    raw_totals, per_name, unreadable = raw_measures(dump_dir)
    parsed = parse_circle(dump_dir, index_info["rows"])
    db_plans = read_plan_rows(cur, plan_uuid)
    roots, idx_children, by_type = index_aggregates(cur, int(header["id"]))

    check(f"{tag}: файлов круга, которые не удалось прочитать, нет", not unreadable,
          _brief(unreadable[:MAX_NAMES]))
    check(f"{tag}: файлов регистрации вида измерено {expect['raw_files']}",
          raw_totals.get("raw_files", 0) == expect["raw_files"],
          f"измерено: {raw_totals.get('raw_files', 0)}")
    check(f"{tag}: разбор назвал столько же файлов, сколько измерено",
          parsed["files_found"] == raw_totals.get("raw_files", 0),
          f"разбор: {parsed['files_found']}")
    aggregate = int(one(cur, "SELECT count(*) AS c FROM configuration_objects "
                             "WHERE configuration_id = %s AND object_type = %s "
                             "AND (child_type IS NULL OR child_type = '')",
                        (int(header["id"]), INDEX_OBJECT_TYPE)).get("c") or 0)
    check(f"{tag}: записей индекса состава вида — агрегат и построчно равны",
          aggregate == len(roots) == expect["idx_roots"],
          f"агрегат {aggregate}, обход {len(roots)}, план {expect['idx_roots']}")
    check(f"{tag}: строк вида в таблице ровно {expect['rows_plans']}",
          len(db_plans) == expect["rows_plans"], f"факт: {len(db_plans)}")

    prefix = INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR
    file_stems = set(per_name)
    index_names = {str(row["object_name"])[len(prefix):]
                   if str(row["object_name"]).startswith(prefix)
                   else str(row["object_name"]) for row in roots}
    db_names = {str(row["object_name"]) for row in db_plans}
    listed = header_array(cur, int(header["id"]))
    set_diff("файлы круга и записи индекса состава называют одни имена",
             file_stems, index_names, tag)
    set_diff("записи индекса и строки таблицы называют одни имена",
             index_names, db_names, tag)
    if expect["header_list"] is None:
        check(f"{tag}: перечня вида в заголовке нет (значение колонки отсутствует)",
              listed is None, f"факт: {_brief(listed)}")
    else:
        check(f"{tag}: перечень вида в заголовке назван и совпадает с числом",
              listed is not None and len(listed) == expect["header_list"],
              f"факт: {_brief(listed)}")
        set_diff("перечень заголовка и строки таблицы называют одни имена",
                 {str(item) for item in (listed or [])}, db_names, tag)
    index_uuids = {str(row["uuid"]).lower() for row in roots}
    set_diff("uuid записей индекса и uuid строк таблицы совпадают",
             index_uuids, {str(row["object_uuid"]).lower() for row in db_plans}, tag)

    idx_total = int(one(cur, "SELECT count(*) AS c FROM configuration_objects "
                             "WHERE configuration_id = %s AND object_type = %s "
                             "AND child_type IS NOT NULL AND child_type <> ''",
                        (int(header["id"]), INDEX_OBJECT_TYPE)).get("c") or 0)
    check(f"{tag}: записей индекса о детях вида — агрегат и построчно равны",
          idx_total == len(idx_children) == expect["idx_children"],
          f"агрегат {idx_total}, обход {len(idx_children)}, план {expect['idx_children']}")
    wrong_types = [f"{key}: факт {by_type.get(key[4:], 0)}, план {want}"
                   for key, want in expect.items()
                   if key.startswith("idx_") and key not in ("idx_roots", "idx_children")
                   and by_type.get(key[4:], 0) != want]
    extra_types = sorted(kind for kind in by_type
                         if f"idx_{kind}" not in expect and by_type[kind])
    for kind in extra_types:
        wrong_types.append(f"idx_{kind}: факт {by_type[kind]}, в плана такого вида нет")
    check(f"{tag}: записи индекса по видам детей совпадают с планом", not wrong_types,
          "; ".join(wrong_types[:MAX_NAMES]))

    counts_diff(raw_totals, {key: value for key, value in expect.items()
                             if key.startswith("raw_")}, "независимые меры файлов", tag)
    return {"parsed": parsed, "db_plans": db_plans, "per_name": per_name,
            "raw_totals": raw_totals, "index_roots": roots, "index_all_rows": index_info["rows"],
            "index_children": idx_children, "index_by_type": by_type}



def check_children_circle(circle, expect, tag):
    """Вторая нога круга: дети вида против записей индекса (замер 3.1) и чистота круга."""
    parsed = circle["parsed"]
    declared = (parsed["attributes_own"] + parsed["attributes_columns"]
                + parsed["tabular_sections_total"] + parsed["forms_total"]
                + parsed["templates_total"] + parsed["commands_total"])
    want_declared = (expect["rows_attributes"] + expect["rows_tabular_sections"]
                     + expect["rows_forms"] + expect["rows_templates"]
                     + expect["rows_commands"])
    check(f"{tag}: детей подтверждено файлом ровно {want_declared}",
          declared == want_declared, f"подтверждено: {declared}")
    check(f"{tag}: attributes_own + attributes_columns = {expect['rows_attributes']} "
          "(реквизиты вида и колонки его табличных частей)",
          parsed["attributes_own"] + parsed["attributes_columns"]
          == expect["rows_attributes"],
          f"своих {parsed['attributes_own']} + колонок {parsed['attributes_columns']}")
    # Арифметика замера 3.1: каждая запись индекса о детях вида либо подтверждена файлом,
    # либо является псевдо-записью слота или модуля. Третьего состояния круг не даёт.
    check(f"{tag}: записи индекса о детях разложены на подтверждённые и псевдо",
          len(circle["index_children"]) == declared + parsed["index_pseudo_entries_total"],
          f"индекс {len(circle['index_children'])}, подтверждено {declared}, "
          f"псевдо {parsed['index_pseudo_entries_total']}")
    check(f"{tag}: псевдо-записей индекса ровно {expect['pseudo']}",
          parsed["index_pseudo_entries_total"] == expect["pseudo"],
          f"факт: {parsed['index_pseudo_entries_total']}")
    discrepancies = parsed["counts_by_circle_discrepancy"]
    check(f"{tag}: словарь расхождений круга замкнут перечнем слоя",
          sorted(discrepancies) == sorted(CIRCLE_DISCREPANCIES),
          _brief(sorted(discrepancies)))
    for state in CIRCLE_DISCREPANCIES:
        check(f"{tag}: расхождений круга `{state}` — {expect[state]}",
              discrepancies.get(state) == expect[state],
              f"факт: {discrepancies.get(state)} {_brief(parsed[state])}")
    check(f"{tag}: детей, описанных файлом без записи индекса и наоборот, нет",
          parsed["child_mismatch_total"] == expect["child_mismatch"]
          and parsed["counts_by_child_mismatch"] == {},
          f"факт: {parsed['child_mismatch_total']} "
          f"{_brief(parsed['counts_by_child_mismatch'])}")
    check(f"{tag}: расхождений объявления вида с его каталогом нет",
          parsed["declaration_mismatch_total"] == expect["declaration_mismatch"],
          _brief(parsed["declaration_mismatches"][:MAX_NAMES]))
    check(f"{tag}: файлов круга, разбор которых не удался, нет",
          len(parsed["files_failed"]) == expect["files_failed"],
          _brief(parsed["files_failed"][:MAX_NAMES]))
    observed = dict(parsed["counts_by_ext_observation"])
    check(f"{tag}: наблюдений о каталоге ресурсов справки — "
          f"{expect['raw_help_resource_dirs']}",
          observed.get("help_resources_dir", 0) == expect["raw_help_resource_dirs"],
          f"факт: {_brief(observed)}")
    missing = sum(1 for kind, _detail in parsed["observations"]
                  if kind == OBSERVATION_DIRECTORY_MISSING)
    check(f"{tag}: наблюдение об отсутствующем каталоге вида — "
          f"{expect['directory_missing']}",
          missing == expect["directory_missing"], f"факт: {missing}")
    check(f"{tag}: неизвестных свойств, неизвестных значений и неизвестных тегов нет",
          not parsed["unknown_properties"] and not parsed["unknown_value_properties"]
          and not parsed["unexpected_child_tags"],
          f"unknown={_brief(parsed['unknown_properties'])} "
          f"values={_brief(parsed['unknown_value_properties'])} "
          f"tags={_brief(parsed['unexpected_child_tags'])}")



def check_parse_states(circle, expect, tag):
    """Состояния и счётчики, их называет разбор (контур 7, сторона слоя).

    Сравнение с эталоном идёт по всему замкнутому словарю состояний: отсутствие ключа в
    ответе и ноль — разные состояния (прецедент V46 и V50), поэтому словарь строится из
    констант слоя, а не из того, что случайно непустое.
    """
    parsed = circle["parsed"]
    parse_counts = {
        "parse_props_all_known": parsed["counts_by_properties_state"].get("all_known", 0),
        "parse_props_absent": parsed["counts_by_properties_state"].get("absent", 0),
        "parse_children_with": parsed["counts_by_children_state"].get("with_children", 0),
        "parse_children_empty": parsed["counts_by_children_state"].get("empty_content", 0),
        "parse_std_present": parsed["counts_by_standard_attributes_state"].get(
            "present_not_indexed", 0),
        "parse_std_absent": parsed["counts_by_standard_attributes_state"].get("absent", 0),
        "parse_content_with": parsed["counts_by_content_state"].get("with_content", 0),
        "parse_content_empty": parsed["counts_by_content_state"].get("empty_content", 0),
        "parse_resolve_exact": parsed["counts_by_target_resolve_state"].get(TARGET_EXACT, 0),
        "parse_auto_Allow": parsed["counts_by_auto_record_state"].get(AUTO_RECORD_ALLOW, 0),
        "parse_auto_Deny": parsed["counts_by_auto_record_state"].get(AUTO_RECORD_DENY, 0),
        "parse_form_ext_xml": parsed["counts_by_form_ext_format"].get("xml", 0),
        "parse_form_ext_bin": parsed["counts_by_form_ext_format"].get("bin", 0),
        "parse_tpl_ext_txt": parsed["counts_by_template_ext_format"].get("txt", 0),
        "parse_tpl_ext_xml": parsed["counts_by_template_ext_format"].get("xml", 0),
        "parse_obj_module": parsed["counts_by_object_module_kind"].get("ObjectModule", 0),
        "parse_mgr_module": parsed["counts_by_object_module_kind"].get("ManagerModule", 0),
        "parse_cmd_module": parsed["command_module_files_total"],
        "parse_std_entries": parsed["standard_attributes_total"],
        "parse_std_distinct": parsed["standard_attributes_distinct"],
        "pseudo": parsed["index_pseudo_entries_total"],
    }
    counts_diff(parse_counts, {key: value for key, value in expect.items()
                               if key.startswith("parse_") or key == "pseudo"},
               "состояния и счётчики разбора", tag)
    closed = (
        ("состояний свойств", parsed["counts_by_properties_state"], PROPERTIES_STATES),
        ("состояний детей", parsed["counts_by_children_state"], CHILD_STATES),
        ("состояний стандартных реквизитов",
         parsed["counts_by_standard_attributes_state"], STANDARD_ATTRIBUTE_STATES),
        ("состояний перечня", parsed["counts_by_content_state"], CONTENT_STATES),
        ("состояний слотов", parsed["counts_by_slot_state"], SLOT_STATES),
        ("состояний разрешения целей", parsed["counts_by_target_resolve_state"],
         TARGET_STATES),
        ("состояний AutoRecord", parsed["counts_by_auto_record_state"], AUTO_RECORD_STATES),
    )
    for label, counter, vocabulary in closed:
        unknown = sorted(key for key in counter if key not in vocabulary)
        missing = sorted(key for key in vocabulary if key not in counter)
        check(f"{tag}: словарь {label} замкнут перечнем слоя", not unknown,
              _brief(unknown))
        check(f"{tag}: словарь {label} назван по всему перечню слоя", not missing,
              _brief(missing))




# ═══ контур 4: ключ разбора против колонок живой схемы ════════════════════════════════
def parsed_buckets(parsed):
    """Строки разбора по таблицам — тот же круг, что пишет загрузчик."""
    return {
        TABLE_NAME: parsed["rows"],
        CONTENT_TABLE_NAME: parsed["content"],
        COMMANDS_TABLE_NAME: parsed["commands"],
        "attributes": parsed["attributes"] + parsed["columns"],
        "tabular_sections": parsed["tabular_sections"],
        "forms": parsed["forms"],
        FORM_EXT_TABLE: parsed["form_ext"],
        "templates": parsed["templates"],
    }


def check_key_shape(cur, parsed, tag):
    """Ключ строки разбора и колонки таблицы сверяются в обе стороны (свои таблицы узла).

    Для общих таблиц детей сравнение идёт в одну сторону: их колонки принадлежат не только
    V51 (замер 5.6 плана), и требовать, чтобы узел заполнил чужие колонки, нельзя.
    """
    for table, rows in parsed_buckets(parsed).items():
        columns = table_columns(cur, table)
        check(f"{tag}: таблицы {table} нет в живой схеме", bool(columns), "0 колонок")
        if not rows:
            continue
        keys = set()
        for row in rows:
            keys.update(row.keys())
        without_column = sorted(keys - set(columns)
                                - set(REPORT_ONLY_KEYS.get(table, ())))
        check(f"{tag}: ключ разбора {table} не несёт имён без колонки",
              not without_column, _brief(without_column))
        if table not in EXPECTED_COLUMN_COUNTS:
            continue
        check(f"{tag}: колонок {table} ровно {EXPECTED_COLUMN_COUNTS[table]} (эталон П1)",
              len(columns) == EXPECTED_COLUMN_COUNTS[table], f"факт: {len(columns)}")
        derived = set(WRITER_SET_COLUMNS.get(table, ()))
        if table == TABLE_NAME:
            derived |= set(DERIVED_PLAN_COLUMNS)
        never = sorted(set(columns) - keys - set(REVISION_COLUMNS) - derived)
        check(f"{tag}: колонок {table}, которые разбор не заполняет, нет", not never,
              _brief(never))


# ═══ контуры 2 и 3: строки вида и детей против разбора ════════════════════════════════
def check_plan_rows(cur, circle, tag):
    check_key_shape(cur, circle["parsed"], tag)
    compare_rows(tag, "строки вида", circle["db_plans"], circle["parsed"]["rows"],
                 "object_uuid", DERIVED_PLAN_COLUMNS, table_columns(cur, TABLE_NAME))


def check_children_rows(cur, header, circle, tag):
    """Каждая строка ребёнка обязана совпасть с разбором и с числом файлов подкаталога."""
    parsed = circle["parsed"]
    plan_uuids = [str(row["object_uuid"]) for row in circle["db_plans"]]
    # Колонки табличных частей висят на строке табличной части, а не на строке вида
    # (замер 3.4: индекс держит колонку под точечным именем табличной части), поэтому
    # предикат области видимости для `attributes` обязан включать и uuid табличных частей
    # этого круга — иначе колонки читались бы потерянными (проверка споткнулась бы о
    # собственную область выборки, а не о содержимое базы).
    scope_uuids = plan_uuids + [str(row["uuid"]) for row in parsed["tabular_sections"]]
    bucket_table = {
        "attributes": ("attributes", parsed["attributes"] + parsed["columns"], "uuid",
                       scope_uuids),
        "tabular_sections": ("tabular_sections", parsed["tabular_sections"], "uuid",
                             plan_uuids),
        "forms": ("forms", parsed["forms"], "uuid", plan_uuids),
        FORM_EXT_TABLE: (FORM_EXT_TABLE, parsed["form_ext"], "form_uuid", plan_uuids),
        "templates": ("templates", parsed["templates"], "uuid", plan_uuids),
        "commands": (COMMANDS_TABLE_NAME, parsed["commands"], "uuid", plan_uuids),
    }
    for label, (table, rows, key, parents) in bucket_table.items():
        db_rows = (read_form_ext_rows(cur, plan_uuids) if table == FORM_EXT_TABLE
                   else read_child_rows(cur, table, parents, header["uuid"]))
        check(f"{tag}: строк детей {table} — {len(rows)} (столько же, сколько в разборе)",
              len(db_rows) == len(rows), f"в базе {len(db_rows)}, в разборе {len(rows)}")
        if not rows:
            continue
        compare_rows(tag, f"строки детей {table}", db_rows, rows, key,
                     (), table_columns(cur, table))
    check(f"{tag}: состояние стандартных реквизитов названо на каждой строке вида",
          all(row.get("standard_attributes_state") for row in circle["db_plans"]),
          "состояние блока не названо — наличие читалось бы потерянным")


def check_shared_child_uuids(cur):
    """Инвариант замера 3.2: общие uuid детей между конфигурациями — не одна строка.

    uuid описания формы или макета повторяется между выгрузками (замер: 42 349 общих uuid),
    но предикат области видимости детей включает конфигурацию, поэтому повтор uuid обязан
    давать РАЗНЫЕ строки. Если бы предикат был только по uuid, чужие строки попали бы в
    снятие своего круга (дефект, названный узлом V47).
    """
    duplicates = q(cur, "SELECT configuration_uuid, parent_uuid, name, count(*) AS c "
                        "FROM forms WHERE parent_type = 'configuration_objects' "
                        "AND uuid IN (SELECT uuid FROM forms WHERE parent_type = "
                        "'configuration_objects' GROUP BY uuid HAVING count(*) > 1) "
                        "GROUP BY configuration_uuid, parent_uuid, name "
                        "HAVING count(*) > 1")
    check("общий uuid ребёнка не даёт дублей внутри одной области видимости",
          not duplicates, _brief(duplicates[:MAX_NAMES]))
    shared = int(one(cur, "SELECT count(*) AS c FROM (SELECT uuid FROM forms "
                          "WHERE parent_type = 'configuration_objects' GROUP BY uuid "
                          "HAVING count(DISTINCT configuration_uuid) > 1) s").get("c") or 0)
    check("общие uuid детей между конфигурациями названы (замер 3.2 их ожидает)",
          shared > 0, f"общих uuid форм: {shared}")



# ═══ контур 5: строки перечня против файла слота и против строки вида ═════════════════
def check_content(cur, header, circle, expect, tag):
    """`Ext/Content.xml` → `exchange_plan_content`: порядок, цель, `AutoRecord`, ссылка.

    Ключ строки — пара (точное имя вида, порядок): своей цепи ревизий у строки перечня нет
    (Q2, вариант A), она версионируется вместе с видом, поэтому сравнение идёт по составному
    ключу, а не по одному uuid.
    """
    parsed = circle["parsed"]
    db_rows = read_content_rows(cur, str(header["uuid"]))
    check(f"{tag}: строк перечня — {expect['rows_content']}",
          len(db_rows) == expect["rows_content"], f"факт: {len(db_rows)}")
    check(f"{tag}: целей перечня в разборе — {expect['raw_content_items']}",
          len(parsed["content"]) == expect["raw_content_items"],
          f"факт: {len(parsed['content'])}")
    columns = set(table_columns(cur, CONTENT_TABLE_NAME)) - set(REVISION_COLUMNS)
    by_db = {(str(row["exchange_plan_full_name"]), int(row["ordinal"])): row
             for row in db_rows}
    by_parsed = {(str(row["exchange_plan_full_name"]), int(row["ordinal"])): row
                 for row in parsed["content"]}
    problems = []
    for key in sorted(set(by_db) - set(by_parsed)):
        problems.append(f"в базе без файла: {_brief(key)}")
    for key in sorted(set(by_parsed) - set(by_db)):
        problems.append(f"в файле без базы: {_brief(key)}")
    for key in sorted(set(by_db) & set(by_parsed)):
        db_row, parsed_row = by_db[key], by_parsed[key]
        for column in sorted(columns - {"configuration_uuid", "exchange_plan_object_uuid",
                                        "exchange_plan_full_name", "ordinal"}):
            if column not in parsed_row:
                continue
            if not values_equal(db_row.get(column), parsed_row[column], column):
                problems.append(f"{_brief(key)}: {column} — база "
                                f"{_brief(db_row.get(column))}, "
                                f"разбор {_brief(parsed_row[column])}")
    check(f"{tag}: строки перечня совпадают с разбором ({len(by_db)} строк)",
          not problems, "; ".join(problems[:MAX_NAMES]))

    per_plan = Counter(str(row["exchange_plan_full_name"]) for row in db_rows)
    declared = {str(row["full_name"]): int(row["content_count"] or 0)
                for row in circle["db_plans"]}
    wrong_counts = [f"{name}: строк {count}, счётчик {declared.get(name)}"
                    for name, count in per_plan.items()
                    if declared.get(name) != count]
    missing = sorted(name for name, value in declared.items()
                     if value and name not in per_plan)
    check(f"{tag}: счётчик `content_count` строки вида равен числу строк перечня",
          not wrong_counts and not missing,
          "; ".join((wrong_counts + [f"строк нет у вида {name}" for name in missing])
                    [:MAX_NAMES]))
    auto_counts = Counter(str(row["auto_record_state"]) for row in db_rows)
    check(f"{tag}: `AutoRecord` сохранённых строк равен мерам файла "
          f"(Allow {expect['raw_auto_Allow']} / Deny {expect['raw_auto_Deny']})",
          auto_counts.get(AUTO_RECORD_ALLOW, 0) == expect["raw_auto_Allow"]
          and auto_counts.get(AUTO_RECORD_DENY, 0) == expect["raw_auto_Deny"],
          f"факт: {_brief(dict(auto_counts))}")
    check(f"{tag}: сумма `AutoRecord` равна числу целей перечня",
          auto_counts.get(AUTO_RECORD_ALLOW, 0) + auto_counts.get(AUTO_RECORD_DENY, 0)
          == len(db_rows),
          f"сумма: {sum(auto_counts.values())}, строк: {len(db_rows)}")
    unknown_auto = sorted(key for key in auto_counts if key not in AUTO_RECORD_STATES)
    check(f"{tag}: словарь `auto_record_state` замкнут перечнем слоя", not unknown_auto,
          _brief(unknown_auto))
    orphans = int(one(cur, f"SELECT count(*) AS c FROM {CONTENT_TABLE_NAME} c "
                           f"LEFT JOIN {CURRENT_VIEWS[TABLE_NAME]} p "
                           "ON p.object_uuid = c.exchange_plan_object_uuid "
                           "AND p.configuration_uuid = c.configuration_uuid "
                           "WHERE c.configuration_uuid = %s::uuid AND p.id IS NULL",
                      [str(header["uuid"])]).get("c") or 0)
    check(f"{tag}: каждая строка перечня ссылается на CURRENT-ревизию своего вида (Q2 A)",
          orphans == 0, f"ссылок вникуда: {orphans}")


# ═══ контур 6: повторное разрешение целей перечня индексом состава ═════════════════════
def check_target_resolution(cur, header, circle, expect, tag):
    """Каждая сохранённая цель разрешается заново: состояние и ссылки обязаны совпасть."""
    index_by_name = {index_row_key(row): row for row in circle["index_all_rows"]}
    db_rows = read_content_rows(cur, str(header["uuid"]))
    problems, states = [], Counter()
    for row in db_rows:
        resolved = resolve_target(str(row["target_full_name"] or ""), index_by_name)
        states[resolved["state"]] += 1
        if resolved["state"] != row["target_resolve_state"]:
            problems.append(f"{row['target_full_name']}: сохранено "
                            f"{row['target_resolve_state']}, разрешение — "
                            f"{resolved['state']}")
            continue
        if norm_value(row.get("target_object_uuid")) != norm_value(resolved["object_uuid"]):
            problems.append(f"{row['target_full_name']}: uuid цели — база "
                            f"{_brief(row.get('target_object_uuid'))}, индекс — "
                            f"{_brief(resolved['object_uuid'])}")
        if norm_value(row.get("target_object_id")) != norm_value(resolved["object_id"]):
            problems.append(f"{row['target_full_name']}: object_id — база "
                            f"{_brief(row.get('target_object_id'))}, индекс — "
                            f"{_brief(resolved['object_id'])}")
    check(f"{tag}: цели перечня разрешаются индексом заново без расхождений",
          not problems, "; ".join(problems[:MAX_NAMES]))
    check(f"{tag}: состояний разрешения — точных {expect['parse_resolve_exact']}, "
          "префиксных и неразрешимых ноль",
          states.get(TARGET_EXACT, 0) == expect["parse_resolve_exact"]
          and not (set(states) - {TARGET_EXACT}),
          f"факт: {_brief(dict(states))}")


# ═══ контур 7: словари состояний сохранённых строк ════════════════════════════════════
def check_db_states(cur, header, circle, expect, tag):
    """Распределение состояний в строках обязано давать тот же круг, что и файлы.

    Сравнение идёт по замкнутому словарю слоя: `unknown_value`/`unknown_tag`/`unknown_form`
    обязаны быть нулями, и ноль проверяется, а не предполагается (прецедент V50).
    """
    rows = circle["db_plans"]
    plan_uuids = [str(row["object_uuid"]) for row in rows]
    state_columns = {
        "properties_state": ("all_known", "unknown_value", "unknown_tag", "absent"),
        "children_state": ("with_children", "empty_content"),
        "standard_attributes_state": ("present_not_indexed", "absent"),
        "content_state": ("with_content", "empty_content"),
        "help_state": ("with_content", "absent", "unknown_form"),
        "additional_indexes_state": ("with_content", "absent", "unknown_form"),
    }
    for column, vocabulary in state_columns.items():
        values = Counter(str(row.get(column)) for row in rows)
        unknown = sorted(key for key in values if key not in vocabulary)
        check(f"{tag}: состояния `{column}` входят в словарь слоя", not unknown,
              _brief(unknown))
    distributions = {
        "properties_state": {"all_known": expect["parse_props_all_known"],
                             "absent": expect["parse_props_absent"]},
        "children_state": {"with_children": expect["parse_children_with"],
                           "empty_content": expect["parse_children_empty"]},
        "standard_attributes_state": {
            "present_not_indexed": expect["parse_std_present"],
            "absent": expect["parse_std_absent"]},
        "content_state": {"with_content": expect["parse_content_with"],
                          "empty_content": expect["parse_content_empty"]},
    }
    for column, want in distributions.items():
        got = Counter(str(row.get(column)) for row in rows)
        wrong = [f"{state}: факт {got.get(state, 0)}, разбор {count}"
                 for state, count in want.items() if got.get(state, 0) != count]
        extra = sorted(key for key in got if want.get(key, 0) != got[key])
        for key in extra:
            wrong.append(f"{key}: факт {got[key]}, в разборе такого состояния нет")
        check(f"{tag}: распределение `{column}` равно разбору", not wrong,
              "; ".join(wrong[:MAX_NAMES]))
    for column, want in (("help_state", expect["raw_help_files"]),
                         ("additional_indexes_state", expect["raw_addidx_files"])):
        got_with = sum(1 for row in rows if str(row.get(column)) == "with_content")
        got_absent = sum(1 for row in rows if str(row.get(column)) == "absent")
        check(f"{tag}: слотов `{column}` с содержимым — {want}, без содержимого — "
              f"{len(rows) - want}",
              got_with == want and got_absent == len(rows) - want,
              f"факт: with {got_with}, absent {got_absent}")
    form_ext_rows = read_form_ext_rows(cur, plan_uuids)
    formats = Counter(str(row.get("ext_format")) for row in form_ext_rows)
    check(f"{tag}: форматов `ext` форм совпадают с разбором "
          f"(xml {expect['parse_form_ext_xml']} / bin {expect['parse_form_ext_bin']})",
          formats.get("xml", 0) == expect["parse_form_ext_xml"]
          and formats.get("bin", 0) == expect["parse_form_ext_bin"],
          f"факт: {_brief(dict(formats))}")
    tpl_formats = Counter(str(row.get("ext_format"))
                          for row in read_child_rows(cur, "templates", plan_uuids,
                                                     header["uuid"]))
    check(f"{tag}: форматов макетов совпадают с разбором "
          f"(txt {expect['parse_tpl_ext_txt']} / xml {expect['parse_tpl_ext_xml']})",
          tpl_formats.get("txt", 0) == expect["parse_tpl_ext_txt"]
          and tpl_formats.get("xml", 0) == expect["parse_tpl_ext_xml"],
          f"факт: {_brief(dict(tpl_formats))}")
    check(f"{tag}: пустых и непустых слотов вида достаточно, чтобы описать их содержимым",
          all((row.get("help_content") is None) == (str(row.get("help_state")) !=
                                                    "with_content")
              and (row.get("additional_indexes_content") is None) ==
              (str(row.get("additional_indexes_state")) != "with_content")
              for row in rows),
          "состояние слота и его содержимое расходятся (CHECK узла)")


# ═══ контур 8: пустой круг (Q9) ═══════════════════════════════════════════════════════
def check_empty_circle(cur, header, dump_dir, index_info, expect, tag):
    """У конфигурации без планов обмена ноль обязан быть назван состоянием выгрузки."""
    raw_totals, _per_name, unreadable = raw_measures(dump_dir)
    parsed = parse_circle(dump_dir, index_info["rows"])
    roots, idx_children, _by_type = index_aggregates(cur, int(header["id"]))
    check(f"{tag}: файлов вида нет ни каталогом, ни разбором",
          not raw_totals and parsed["files_found"] == 0 and not unreadable,
          f"меры {_brief(dict(raw_totals))}, разбор {parsed['files_found']}")
    check(f"{tag}: записей индекса состава вида нет",
          not roots and not idx_children,
          f"корней {len(roots)}, детей {len(idx_children)}")
    check(f"{tag}: пустой круг назван наблюдением `directory_missing`",
          any(kind == OBSERVATION_DIRECTORY_MISSING for kind, _ in parsed["observations"]),
          _brief(parsed["observations"][:MAX_NAMES]))
    check(f"{tag}: разбора, который не удался, нет", not parsed["files_failed"],
          _brief(parsed["files_failed"][:MAX_NAMES]))
    for table in (TABLE_NAME, CONTENT_TABLE_NAME, COMMANDS_TABLE_NAME, "attributes",
                  "tabular_sections", "forms", "templates"):
        rows = q(cur, f"SELECT id FROM {table} WHERE configuration_uuid = %s::uuid",
                 [str(header["uuid"])])
        check(f"{tag}: строк {table} — 0 (позиции вида нет в выгрузке)", not rows,
              f"факт: {len(rows)}")
    return {"parsed": parsed, "db_plans": [], "raw_totals": raw_totals,
            "index_all_rows": index_info["rows"], "empty": True}


# ═══ контур 9: витрины, цепь ревизий, сироты ═════════════════════════════════════════
def check_views(cur, headers):
    """Витрина текущего состояния обязана отдавать ровно CURRENT-ревизии своих строк."""
    uuids = [str(header["uuid"]) for header in headers]
    plan_uuids = [str(row["u"]) for row in q(cur, "SELECT object_uuid AS u FROM "
                                                 f"{TABLE_NAME}")]
    for table, view in CURRENT_VIEWS.items():
        if table == FORM_EXT_TABLE:
            # У `form_ext` своей колонки конфигурации нет (узел V14): область видимости
            # читается по ноге детей, а витрина текущего состояния ту же ногу отдаёт
            # собственным столбцом `parent_uuid` — предикаты различаются, и путать их
            # нельзя: сравнение витрины с таблицей было бы сравнением разных выборок.
            source, predicate = f"{table} f", ("WHERE f.parent_type = "
                                               "'configuration_objects' "
                                               "AND f.parent_uuid = ANY(%s::uuid[])")
            view_source, view_predicate = view, ("WHERE parent_type = "
                                                "'configuration_objects' "
                                                "AND parent_uuid = ANY(%s::uuid[])")
            params = [plan_uuids]
        else:
            predicate = "WHERE configuration_uuid = ANY(%s::uuid[])"
            params = [uuids]
            source, view_source, view_predicate = table, table, predicate
        base = int(one(cur, f"SELECT count(*) AS c FROM {source} {predicate}",
                       params).get("c") or 0)
        current = int(one(cur, f"SELECT count(*) AS c FROM {view_source} {view_predicate}",
                          params).get("c") or 0)
        check(f"витрина {view} отдаёт строки круга вида в том же числе, что {table}",
              base == current, f"таблица {base}, витрина {current}")


def check_revisions(cur, headers):
    """У загруженного круга ревизия первая и единственная; исторических строк нет."""
    uuids = [str(header["uuid"]) for header in headers]
    for table in (TABLE_NAME, CONTENT_TABLE_NAME, COMMANDS_TABLE_NAME):
        bad = int(one(cur, f"SELECT count(*) AS c FROM {table} "
                            "WHERE configuration_uuid = ANY(%s::uuid[]) "
                            "AND (revision_no <> 1 OR is_committed IS NOT TRUE)",
                       [uuids]).get("c") or 0)
        check(f"{table}: каждая строка круга — первая и единственная ревизия (V19)",
              bad == 0, f"строк с другой ревизией: {bad}")


def check_orphans(cur):
    """Сирот круга — ноль: дети и перечень обязаны висеть на строке вида.

    Основанием «строка обязана быть» служит индекс состава вида: строка ребёнка или
    перечня, чей родитель назван индексом (`ExchangePlan.*`), обязана иметь и строку вида.
    Иначе снятие круга по ноге области видимости оставила бы детей сиротами — ровно тот
    дефект, который узлы V44…V50 закрывают явным `DELETE`.
    """
    parents = ("SELECT uuid FROM configuration_objects "
               "WHERE object_type = %s AND (child_type IS NULL OR child_type = '')")
    checks = (
        ("attributes", "parent_uuid"), ("tabular_sections", "parent_uuid"),
        ("forms", "parent_uuid"), ("templates", "parent_uuid"),
        (COMMANDS_TABLE_NAME, "parent_uuid"), (CONTENT_TABLE_NAME,
                                               "exchange_plan_object_uuid"),
    )
    for table, column in checks:
        orphans = int(one(cur, f"SELECT count(*) AS c FROM {table} "
                              f"WHERE {column} IN ({parents}) "
                              f"AND {column} NOT IN (SELECT object_uuid FROM {TABLE_NAME})",
                          [INDEX_OBJECT_TYPE]).get("c") or 0)
        check(f"{table}: строк детей или перечня без строки вида нет", orphans == 0,
              f"сирот: {orphans}")
    broken_forms = int(one(cur, f"SELECT count(*) AS c FROM {FORM_EXT_TABLE} f "
                                "LEFT JOIN forms fo ON fo.id = f.form_id "
                                "WHERE f.parent_type = 'configuration_objects' "
                                "AND fo.id IS NULL").get("c") or 0)
    check(f"{FORM_EXT_TABLE}: строк без строки формы нет (каскад `form_ext_form_id_fkey`)",
          broken_forms == 0, f"сирот: {broken_forms}")


# ═══ контур 10: неприкосновенность чужих кругов ══════════════════════════════════════
def foreign_state(cur):
    """Снимок того, что узел V51 трогать не должен (сверяется до и после прогона)."""
    state = {}
    for table in list(FOREIGN_TABLES) + list(EXCHANGE_PLAN_TABLES) + list(CHILD_TABLES):
        try:
            state[table] = int(one(cur, f"SELECT count(*) AS c FROM {table}").get("c") or 0)
        except Exception:  # noqa: BLE001 — таблицы других узлов могут отсутствовать в базе
            state[table] = None
    return state


def check_untouched(before, after):
    own = set(EXCHANGE_PLAN_TABLES) | set(CHILD_TABLES)
    changed = [table for table, value in before.items()
               if table not in own and after.get(table) != value]
    check("прогон ничего не изменил в чужих кругах", not changed,
          "изменились строки таблиц: " + names(changed))


def add_totals(totals, circle):
    parsed = circle["parsed"]
    for key, value in (circle.get("raw_totals") or Counter()).items():
        totals[key] += value
    totals["rows_plans"] += len(circle["db_plans"])
    totals["rows_content"] += len(parsed["content"])
    totals["rows_attributes"] += len(parsed["attributes"]) + len(parsed["columns"])
    totals["rows_tabular_sections"] += len(parsed["tabular_sections"])
    totals["rows_forms"] += len(parsed["forms"])
    totals["rows_form_ext"] += len(parsed["form_ext"])
    totals["rows_templates"] += len(parsed["templates"])
    totals["rows_commands"] += len(parsed["commands"])
    totals["idx_roots"] += len(circle.get("index_roots") or [])
    totals["idx_children"] += len(circle.get("index_children") or [])
    totals["pseudo"] += parsed["index_pseudo_entries_total"]
    totals["parse_std_entries"] += parsed["standard_attributes_total"]


def check_aggregate(totals, run_tags, skipped_tags):
    section("Итог по корпусу")
    if set(run_tags) != set(PLAN_EXPECTATIONS):
        skip("итоги по корпусу",
             f"прогнаны не все выгрузки: {names(run_tags)}; пропущены: "
             f"{names(skipped_tags)}. Итог по четырём выгрузкам сравнивать с суммой по "
             "меньшему числу — ложное расхождение")
        return
    counts_diff(totals, CORPUS_TOTALS, "итог по корпусу", "корпус")


def run(cur, scope):
    headers = q(cur, "SELECT id, uuid::text AS uuid, name FROM configurations "
                     "ORDER BY id")
    if not headers:
        print("FAIL строк заголовков конфигураций в базе нет — сравнивать не с чем")
        FAILED.append("нет строк заголовков")
        return
    before = foreign_state(cur)
    totals, run_tags, skipped_tags = Counter(), [], []
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
                 f"каталога `{tag}` нет в перечне ожиданий проверки — числа круга этой "
                 "выгрузки надо переснять и записать в план прежде, чем сравнивать с ними")
            continue
        index_info = read_index_records(cur, int(header["id"]))
        if not index_info["available"]:
            skipped_tags.append(tag)
            skip(f"{tag}: контуры круга, разрешения целей и состояний",
                 index_info.get("reason") or "индекс состава этого заголовка не загружен: "
                                            "сверка файлов с перечнем и разрешение целей "
                                            "невыразимы")
            continue
        if expect["directory_missing"]:
            circle = check_empty_circle(cur, header, dump_dir, index_info, expect, tag)
            add_totals(totals, circle)
            run_tags.append(tag)
            continue
        circle = check_circle(cur, header, dump_dir, index_info, expect, tag)
        if not circle["db_plans"]:
            skipped_tags.append(tag)
            skip(f"{tag}: контуры «файл ↔ строка», детей, перечня и состояний",
                 "строк вида в таблице нет — конфигурацию не перезагружали после узла V51 "
                 "(стадия `s4f_exchange_plans` входит в загрузку каталога, отдельный вход "
                 "группы — `load_exchange_plans_tool`)")
            continue
        check_children_circle(circle, expect, tag)
        check_parse_states(circle, expect, tag)
        check_plan_rows(cur, circle, tag)
        check_children_rows(cur, header, circle, tag)
        check_content(cur, header, circle, expect, tag)
        check_target_resolution(cur, header, circle, expect, tag)
        check_db_states(cur, header, circle, expect, tag)
        add_totals(totals, circle)
        run_tags.append(tag)

    after = foreign_state(cur)
    section("Итог узла V51")
    check_views(cur, headers)
    check_revisions(cur, headers)
    check_orphans(cur)
    check_shared_child_uuids(cur)
    check_untouched(before, after)
    check_aggregate(totals, run_tags, skipped_tags)


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

