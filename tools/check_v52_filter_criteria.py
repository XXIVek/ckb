#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/check_v52_filter_criteria.py — узел V52: критерии отбора (позиция 2.7), шаг П6.

Это постоянная проверка, а не проба шага: она обязана переживать и перезагрузку выгрузок, и
правки кода загрузки. Источник ожиданий — `docs/CONFIGURATION_FILTER_CRITERIA_PLAN.md`
(раздел 1 — замеры круга, раздел 2 — словарь свойств и блоков, раздел 7 — план шагов,
раздел 9 — критерии готовности). Числа круга сняты по самим каталогам выгрузки независимым
зондом ElementTree (тот же код, что в функции `raw_measures` ниже, — без знания о состояниях
разбора) и перенесены в `PLAN_EXPECTATIONS` без правок: сглаживать число проверкой — значит
подтверждать неверное число (прецедент узлов V49…V51).

Что сторожится — по контурам:

  1. ГРАНИЦА КРУГА (три ноги). Критерий отбора адресуется каталогом `FilterCriteria/`
     (`<Имя>.xml`), индексом состава (`FilterCriterion.<Имя>`), перечнем
     `configurations.filter_criteria` и строками таблицы `filter_criteria`. Агрегатный COUNT
     индекса сверяется с построчным обходом (приём V48), множества имён сравниваются попарно
     с правилом снятия префикса вида (замер 1.1: нога заголовка хранит ГОЛЫЕ имена, индекс —
     точные). Число объектов по выгрузкам — 1/1/7/6 (замер 1.1), всего 15; переснято 03.11.2026
      после пересбора фикстуры `MinCfg` (шаг П9 узла V54): 2/1/7/6, всего 16.
  2. ДЕТИ ВИДА И ПСЕВДО-ЗАПИСИ (замер 1.2, переснят 03.11.2026). Дочерних строк индекса — 23, из
     них детьми являются 5 (3 формы + 2 команды), а 18 — псевдо-записи (модули, пары `.Form`,
     `Help`); правило пар формы узла V51 подтверждается и здесь: 3 строки `Form` ↔ 3 строки `.Form`.
     Видов детей, кроме `Form` и `Command`, круг не даёт ни одного — в отличие от плана
     обмена, где были реквизиты, табличные части и макеты.
  3. КЛЮЧ РАЗБОРА ↔ КОЛОНКИ СХЕМЫ. Множество ключей строки разбора и множество колонок
     `filter_criteria` (33) и `filter_criterion_content` (14) сверяются в обе стороны с
     точностью до колонок цепи ревизий и колонок, которые писатель берёт из связи строки
     (Q2, вариант A). Для общих таблиц детей (`forms`, `form_ext`, `commands`) сравнение
     идёт в одну сторону: их колонки принадлежат не только V52 — их пишут контур V14,
     узел V51 и этот узел.
  4. СТРОКА ВИДА ↔ РАЗБОР. Каждая колонка строки обязана совпасть с кругом, разобранным ТЕМ
     ЖЕ модулем (`collect_filter_criteria`), что и загрузка: иначе проверка проверяла бы себя,
     а не то, донёс ли писатель строку. Каналы при этом разные, и различия канала называются:
     `uuid[]` psycopg2 отдаёт литералом массива (typecaster'а для массива uuid нет), а `bytea`
     — объектом `memoryview`, поэтому перечень `command_uuids` сравнивается элементами, а
     `ext_bin` — длиной и отпечатком байтов.
  5. СТРОКИ УСЛОВИЯ (блок `Content`) ↔ ФАЙЛ. Элементов `Item` — 1 219 (BGU2 727, BP3 492);
     у MinCfg и KomMag пустой блок назван состоянием `empty_content`, а не нулём строк.
     Порядок `ordinal` непрерывен от нуля, дублей порядка нет, счётчик `content_count` строки
     вида равен числу строк перечня, а константный атрибут элемента (`xsi:type` =
     `xr:MDObjectRef`) назван и он один на весь круг (замер П2 правит утверждение 2.2 плана).
  6. РАЗРЕШИМОСТЬ ЦЕЛЕЙ. Каждая сохранённая цель разрешается ЗАНОВО по строкам индекса
     состава (`resolve_target`): состояние, `target_object_id` и `target_object_uuid` обязаны
     совпасть с сохранёнными. На корпусе неразрешимых целей нет (1 219 из 1 219 `exact`), и
     нули `prefix_only`/`unresolved` — проверяемое утверждение, а не предположение (Q3/Q4).
  7. БЛОК `<Type>` ОБЕИМИ ВЕТКАМИ (Q6). Независимая мера файлов: 430 значений, из них 429 в
     контейнере `Type` и 1 в контейнере `TypeSet` (KomMag); классы, кратность и состояние
     строки обязаны совпасть с разбором и с колонками. Запись `types[].container` названа на
     каждой записи: без неё различие двух контейнеров пропало бы, а состояние строки осталось
     бы тем же словарём, что у V48/V50. `ns_uri` записи измеряется по объявлениям `xmlns`
     самого файла (префикс → URI, прецедент V48 2.4.4), а не по пространству тега-контейнера:
     контейнер всегда в v8-core, и мера по нему не сошлась бы с колонкой при верном значении.
     Ссылка `cfg:DocumentRef` из `TypeSet` уходит в отдельный список ссылок на вид целиком, а
     не в неразрешённые (отличие от разбора V50); инвариант «разрешено + широкая +
     неразрешённое» держится по классу ссылок, а не по всем значениям блока: примитив
     (`xs:string` у MinCfg) индексом не разрешается вообще. Ключ `reason` разрешён у записей,
     объясняющих отсутствие цели, — `unknown_form`, определяемый тип (узла DefinedTypes нет) и
     ссылка на вид целиком; у остальных он называется лишним.
  8. ССЫЛКИ НА ФОРМЫ (замер 2.3, переснят 03.11.2026). `with_reference` — 5 полей на трёх
     файлах (MinCfg обе формы в каждом из двух файлов, KomMag только `DefaultForm`), остальные
     27 названы `empty_value`; пара «значение ↔ состояние» согласована с CHECK схемы, а
     разрешённая ссылка обязана соответствовать строке `Form` индекса состава того же объекта.
  9. СЛОВАРИ СОСТОЯНИЙ. Замкнутость словарей модуля сверяется с перечнями CHECK'ов живой
     схемы (прецедент `STATE_VOCABULARIES` V50/V51), распределение состояний в строках — с
     независимыми мерами файлов. `unknown_value`/`unknown_tag`/`unknown_form` среди строк вида
     — нули, и ноль проверяется; состояние `unknown_value` строки команды (MinCfg, виновник
     `Group`) называется отдельно: значения свойств детей узлом не удерживаются (Q7 узла V50).
 10. ПУСТОЙ КРУГ (`directory_missing`). На четырёх эталонных выгрузках каталог вида есть у
     всех (замер 1.1), поэтому состояние отсутствующего каталога держится отдельной пробой на
     фикстуре без `FilterCriteria/`: `files_found = 0`, наблюдение `directory_missing`,
     `success = True` — это ответ о выгрузке, а не отказ стадии (Q9).
 11. ЦЕЛОСТНОСТЬ СХЕМЫ И ЧУЖИХ КРУГОВ. Сирот перечня и детей нет; ключи `UNIQUE
     (configuration_uuid, object_name, revision_no)` и `UNIQUE (filter_criterion_id, ordinal)`
     живые; витрины `v_current_filter_criteria` и `v_current_filter_criterion_content` дают то
     же число строк, что таблицы; коллизия `СвязанныеДокументы` (один uuid на две
     конфигурации, замер 1.3) НЕ сливается: четыре конфигурации дают четыре строки вида;
     строки чужих узлов за прогон не меняются — проверка только читает.
 12. КОНТРАКТ СТАДИИ И РЕЕСТР ИНСТРУМЕНТОВ. `s4g_filter_criteria` стоит в `STAGES` между
     `s4f_exchange_plans` и `s4b_object_modules`, круг `FILTER_CRITERIA_TABLES` входит в
     `FOREIGN_STAGE_TABLES`, подсказка продолжения стадии названа, а вход позиции
     (`load_filter_criteria_tool`) назван снятым: отдельный вход снят узлом TOOL-DROP
     (05.11.2026), его нет в `EXPECTED_TOOLS`, и имя числится в `DELETED_TOOLS` — иначе
     проверка молчала бы о стадии, в которую конвейер уже не заходит, и о входе, которым её
     повторяют.
 13. ССЫЛКИ ДРУГИХ СЛОЁВ НА ВИД (позиция O1, закрыта замером 02.11.2026). Сами ссылки живут в
     кругах V46 (`subsystem_content`) и V49 (`role_rights`), узел V52 их не пишет. Сторожится
     свойство, а не число: каждая ссылка с uuid обязана иметь запись индекса состава той же
     конфигурации (иначе состояние `resolved`/`exact` врёт), и ни одна «разрешённая» ссылка не
     должна оставаться без строки вида. Числа замера (14 и 17 на четырёх выгрузках) в
     ожидания НЕ переносятся — правило `rules:core-rules:functional:answer-and-evidence`,
     п. 3: числа датированы и друг друга не подменяют. Проверяется и выводность связки: снятие
     круга вида в SAVEPOINT не меняет состояний ссылок, но оставляет их без строки вида; после
     отката точки сохранения круг восстановлен, прогон остаётся читающим.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python tools/check_v52_filter_criteria.py [MinCfg|KomMag|BGU2|BP3|all]
По умолчанию — `all`: все строки заголовков, для которых находится каталог выгрузки. Код возврата
0 — расхождений нет. Пропуск контура называется причиной (нет строки заголовка, нет выгрузки,
строк узла не загружалось, индекс состава не загружен): ноль проверок не читается как
«всё хорошо».
"""

import ast
import hashlib
import json
import re
import sys
import tempfile
import traceback
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

from configuration_filter_criteria import (  # noqa: E402
    AUXILIARY_FORM_STATE_COLUMN, CHILD_EMPTY_CONTENT, CHILD_WITH_CONTENT, CHILD_COMMAND,
    CHILD_FORM, CHILDREN_STATE_COLUMN, CLASS_DEFINED_TYPE_REF, CLASS_OBJECT_REF,
    CLASS_PRIMITIVE, CLASS_UNKNOWN, CONTENT_COUNT_COLUMN, CONTENT_EMPTY_CONTENT,
    CONTENT_ITEM_ATTR, CONTENT_ITEM_TAG, CONTENT_ITEM_TYPE_VALUE, CONTENT_ORDINAL_COLUMN,
    CONTENT_PARENT_COLUMN, CONTENT_RESOLVE_STATE_COLUMN, CONTENT_STATE_COLUMN,
    CONTENT_TABLE_NAME, CONTENT_TARGET_COLUMN, CONTENT_TARGET_ID_COLUMN,
    CONTENT_TARGET_TAG_COLUMN, CONTENT_TARGET_TYPE_COLUMN, CONTENT_TARGET_UUID_COLUMN,
    CONTENT_UNRESOLVED_PATH_COLUMN, CONTENT_WITH_CONTENT, CONTAINER_TYPE, CONTAINER_TYPE_SET,
    DEFAULT_FORM_STATE_COLUMN, DIR_NAME, FORM_REF_COLUMNS, FORM_REF_EMPTY_VALUE,
    FORM_REF_WITH_REFERENCE, INDEX_NAME_SEPARATOR, INDEX_OBJECT_TYPE, MULT_ABSENT,
    MULT_COMPOSITE, MULT_SINGLE, OBSERVATION_DIRECTORY_MISSING, OBSERVATION_HELP_FILE,
    OBSERVATION_HELP_RESOURCES, PROPS_ALL_KNOWN, PROPS_UNKNOWN_VALUE, STATE_VOCABULARIES,
    STATE_VOCABULARY_TABLES, TABLE_NAME, TARGET_EXACT, TARGET_PREFIX_ONLY,
    TARGET_UNRESOLVED, TYPE_ABSENT, TYPE_CLASS_VALUES, TYPE_CONTAINERS, TYPE_ENTRY_KEYS,
    TYPE_ENTRY_REASON_KEY, TYPE_ENTRY_TARGET_KEYS, TYPE_PARSED, TYPE_PARTIAL,
    TYPE_UNKNOWN_FORM, UNKNOWN_NAMES_COLUMN, collect_filter_criteria, index_object_name,
    index_row_key, index_rows_by_name, property_columns, property_records, resolve_target,
    state_vocabulary,
)
from configuration_filter_criteria_loader import (  # noqa: E402
    COMMANDS_TABLE_NAME as LAYER_COMMANDS_TABLE, FORMS_TABLE as LAYER_FORMS_TABLE,
    FORM_EXT_TABLE as LAYER_FORM_EXT_TABLE, REMOVE_ORDER as LAYER_REMOVE_ORDER,
    SHARED_CHILD_TABLES, read_index_records,
)
from configuration_load_contract import (  # noqa: E402
    FILTER_CRITERIA_REMOVE_ORDER, FILTER_CRITERIA_REPEAT_HINT, FILTER_CRITERIA_TABLES,
    FOREIGN_STAGE_TABLES, STAGE_EVENT_SUBSCRIPTIONS, STAGE_EXCHANGE_PLANS,
    STAGE_FILTER_CRITERIA, STAGE_FULL_RELOAD_ONLY, STAGE_OBJECT_MODULES, STAGES,
    filter_criteria_defaults, stage_resume_hint,
)
from configuration_module_slots import resolve_dump_dir  # noqa: E402
from external_db import transaction  # noqa: E402
from external_table_writer import CONFIGURATION_UNVERSIONED_TABLES  # noqa: E402

DUMP_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
DEFAULT_SCOPE = "all"
MAX_NAMES = 10          # сколько расхождений называется именами (дальше — только число)

# Колонки самой цепи ревизий (узел V19) — без ключевых колонок и без `created_at`. Отдельный
# перечень нужен там, где цепь проверяется на ОТСУТСТВИЕ: у безцепочечной таблицы строки
# `id` и `configuration_uuid` есть, и пересечение с `REVISION_COLUMNS` было бы непустым.
REVISION_CHAIN_COLUMNS = ("revision_no", "changed_at", "changed_by", "is_committed")
# Колонки, которые принадлежат цепи ревизий (узел V19), а не узлу V52: их заполняет не
# разбор, и сравнивать их с ключом строки разбора — значит требовать от слоя чужого.
REVISION_COLUMNS = ("id", "configuration_uuid", "created_at") + REVISION_CHAIN_COLUMNS
# Колонки строки условия, которые писатель берёт из связи строки, а не из разбора: FK на id
# конкретной ревизии вида (Q2, вариант A) и нога конфигурации. Их отсутствие в ключе разбора
# — контракт писателя, а не дефект (прецедент `TARGET_WRITER_COLUMNS` узла V50).
CONTENT_LINK_COLUMNS = ("filter_criterion_id", "configuration_uuid")
# Колонки строк условия, которые не принадлежат разбору: `id` и `created_at` пишет писатель,
# две колонки связи — строка родителя (Q2, вариант A). Перечислены явно, потому что «колонки
# нет у разбора» и «колонки нет в базе» — разные утверждения, и первое находит контур 3.
CONTENT_SKIP_COLUMNS = CONTENT_LINK_COLUMNS + ("id", "created_at")
# Число колонок двух таблиц узла — эталон шага П1 (миграция `migrate_v52_filter_criteria.sql`).
# Общих таблиц детей эталон не задаёт: их колонки принадлежат не только этому узлу.
EXPECTED_COLUMN_COUNTS = {TABLE_NAME: 33, CONTENT_TABLE_NAME: 14}
SHARED_CHILD_TABLES = ("forms", "form_ext", "commands")
# Ключи строк детей, которые разбор называет состояниями, а колонок под такие состояния в
# общих таблицах нет (замер 5.6 плана узла V51 — та же граница детей): исключение обязано
# быть перечисленным, иначе «колонки нет» читалось бы потерей знания.
REPORT_ONLY_KEYS = {"forms": ("properties_state", "unknown_property_names"),
                    "commands": ("properties_state", "unknown_property_names", "module_state")}
# Витрины круга (миграция V52): таблица → витрина текущего состояния.
CURRENT_VIEWS = {
    TABLE_NAME: "v_current_filter_criteria",
    CONTENT_TABLE_NAME: "v_current_filter_criterion_content",
    "commands": "v_current_commands",
    "forms": "v_current_forms",
    "form_ext": "v_current_form_ext",
}
# Что проверка трогать не должна (сверяется до и после прогона) — круги других узлов.
# `attributes`/`tabular_sections`/`templates` стоят здесь намеренно: их пишут узлы V51 и V47,
# а круг V52 их не касается ни одной строкой (замер 1.2: нулей по этим видам нет).
FOREIGN_TABLES = ("configurations", "configuration_objects", "session_parameters", "roles",
                  "role_rights", "role_restriction_templates", "role_sources",
                  "common_attributes", "common_attribute_targets", "subsystems",
                  "subsystem_content", "common_modules", "common_module_sources",
                  "bsl_modules", "external_report", "config_aliases", "config_snippets",
                  "config_cross_references", "attributes", "tabular_sections", "templates")

# Независимый словарь тегов `Properties` вида (замер 2.x плана: ровно 11 тегов в одном
# порядке во всех 16 файлах — пересъём 03.11.2026). Проверка держит свой список, чтобы
# сверять его со словарём модуля (`property_records()`), а не повторять его: расхождение
# в именах или порядке — это потерянная позиция свойства, а не деталь реализации.
PROPERTY_NAMES = ("Name", "Synonym", "Comment", "Type", "UseStandardCommands", "Content",
                  "DefaultForm", "AuxiliaryForm", "ListPresentation",
                  "ExtendedListPresentation", "Explanation")
# Значение, у которого префикс не объявлен ни в одном `xmlns` файла. Отдельное имя держится
# проверкой намеренно: пустая строка смешала бы «префикса нет» с «URI пустого префикса», а
# нулевой счётчик — с отсутствием значений (замер V48 2.4.4, прецедент `ns_uri = null`).
NS_UNDECLARED = "<префикс не объявлен в файле>"
# Ключ признака разрешения ссылки внутри записи `types` — первый в перечне ключей цели
# (`TYPE_ENTRY_TARGET_KEYS` слоя). Проверка держит имя своим: именно он различает два случая
# ключей цели — «разрешено, цель названа» и «не разрешено, ключей цели нет вовсе» (D3).
TYPE_TARGET_RESOLVED_KEY = "resolved"
# Дочерние виды, которые даёт круг по замеру 1.2 (нули тоже названы), и те, которых у вида
# нет ни одной строки ни файлом, ни записью индекса — в отличие от плана обмена (V51).
INDEX_CHILD_TYPES = ("Form", "Command", "CommandModule", "ManagerModule", "Help",
                     "Attribute", "TabularSection", "Template", "ObjectModule")

# ── ожидания проверки (числа плана docs/CONFIGURATION_FILTER_CRITERIA_PLAN.md) ──────────
# Ключ — каталог выгрузки, а не имя строки заголовка: имя заголовка меняется вместе с
# выгрузкой, а каталог — адрес, по которому проверка находит файлы (прецедент V50/V51).
#   raw_*   — независимые меры по самим файлам (ElementTree, без знания о состояниях):
#             файлы регистрации и их вес, теги `<Properties>`, элементы `<Content><Item>`,
#             значения блока `<Type>` по контейнерам, дети в `<ChildObjects>`, файлы `Forms/`
#             и файлов модулей;
#   idx_*   — записи индекса состава: верхние, дочерние и по видам детей (вложенный словарь);
#   rows_*  — строки таблиц узла, которые обязана дать загрузка этого круга;
#   parse_* — состояния и счётчики, которые называет разбор (контур 9);
#   прочие  — расхождения круга, которых на эталонных выгрузках нет (нули проверяются).
# Числа `MinCfg` и итог корпуса пересняты 03.11.2026 (шаг П9 узла V54): фикстуру вида
# пересобирали, и круг в `MinCfg` вырос с одного объекта до двух; числа KomMag, BGU2 и BP3
# при этом не изменились ни на единицу — расхождение называет только `MinCfg`.
PLAN_EXPECTATIONS = {
    "MinCfg": {
        "raw_files": 2, "raw_bytes": 8520, "raw_prop_tags": 22, "raw_content_items": 0,
        "raw_type_values": 2, "raw_type_container_Type": 2, "raw_type_container_TypeSet": 0,
        "raw_string_qualifiers": 2, "raw_child_Form": 2, "raw_child_Command": 2,
        "raw_form_desc": 2, "raw_form_ext_xml": 2, "raw_form_ext_bin": 0,
        "raw_form_module": 0, "raw_form_help": 0, "raw_mgr_module": 2, "raw_cmd_module": 2,
        "raw_target_type_Document": 0, "raw_targets_distinct": 0,
        "raw_help_resource_dirs": 0,
        "idx_roots": 2, "idx_children": 11, "header_list": 2,
        "idx_by_type": {"Form": 4, "Command": 2, "CommandModule": 2, "ManagerModule": 2,
                        "Help": 1, "Attribute": 0, "TabularSection": 0, "Template": 0,
                        "ObjectModule": 0},
        "rows_criteria": 2, "rows_content": 0, "rows_forms": 2, "rows_form_ext": 2,
        "rows_commands": 2,
        "parse_props_all_known": 2, "parse_children_with": 2, "parse_children_empty": 0,
        "parse_content_with": 0, "parse_content_empty": 2,
        "parse_type_parsed": 2, "parse_type_absent": 0, "parse_mult_single": 2,
        "parse_mult_composite": 0, "parse_mult_absent": 0,
        "parse_form_default_with": 2, "parse_form_default_empty": 0,
        "parse_form_aux_with": 2, "parse_form_aux_empty": 0,
        "parse_resolve_exact": 0, "parse_view_wide": 0, "parse_module_files": 4,
        "parse_form_ext_xml": 2, "parse_form_ext_bin": 0,
        "pseudo": 7, "declared_children": 4,
        "child_mismatch": 0, "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
        "declaration_mismatch": 0, "files_failed": 0, "directory_missing": 0,
        "command_unknown_value": 2, "command_culprits": ["Group"],
    },
    "KomMag": {
        "raw_files": 1, "raw_bytes": 2257, "raw_prop_tags": 11, "raw_content_items": 0,
        "raw_type_values": 1, "raw_type_container_Type": 0, "raw_type_container_TypeSet": 1,
        "raw_string_qualifiers": 0, "raw_child_Form": 1, "raw_child_Command": 0,
        "raw_form_desc": 1, "raw_form_ext_xml": 0, "raw_form_ext_bin": 1,
        "raw_form_module": 0, "raw_form_help": 1, "raw_mgr_module": 0, "raw_cmd_module": 0,
        "raw_help_resource_dirs": 1,
        "raw_target_type_Document": 0, "raw_targets_distinct": 0,
        "idx_roots": 1, "idx_children": 3, "header_list": 1,
        "idx_by_type": {"Form": 2, "Command": 0, "CommandModule": 0, "ManagerModule": 0,
                        "Help": 1, "Attribute": 0, "TabularSection": 0, "Template": 0,
                        "ObjectModule": 0},
        "rows_criteria": 1, "rows_content": 0, "rows_forms": 1, "rows_form_ext": 1,
        "rows_commands": 0,
        "parse_props_all_known": 1, "parse_children_with": 1, "parse_children_empty": 0,
        "parse_content_with": 0, "parse_content_empty": 1,
        "parse_type_parsed": 1, "parse_type_absent": 0, "parse_mult_single": 1,
        "parse_mult_composite": 0, "parse_mult_absent": 0,
        "parse_form_default_with": 1, "parse_form_default_empty": 0,
        "parse_form_aux_with": 0, "parse_form_aux_empty": 1,
        "parse_resolve_exact": 0, "parse_view_wide": 1, "parse_module_files": 0,
        "parse_form_ext_xml": 0, "parse_form_ext_bin": 1,
        "pseudo": 2, "declared_children": 1,
        "child_mismatch": 0, "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
        "declaration_mismatch": 0, "files_failed": 0, "directory_missing": 0,
        "command_unknown_value": 0, "command_culprits": [],
    },
    "BGU2": {
        "raw_files": 7, "raw_bytes": 156578, "raw_prop_tags": 77, "raw_content_items": 727,
        "raw_type_values": 240, "raw_type_container_Type": 240,
        "raw_type_container_TypeSet": 0, "raw_string_qualifiers": 0,
        "raw_child_Form": 0, "raw_child_Command": 0,
        "raw_form_desc": 0, "raw_form_ext_xml": 0, "raw_form_ext_bin": 0,
        "raw_form_module": 0, "raw_form_help": 0, "raw_mgr_module": 6, "raw_cmd_module": 0,
        "raw_target_type_Document": 727, "raw_targets_distinct": 723,
        "raw_help_resource_dirs": 0,
        "idx_roots": 7, "idx_children": 6, "header_list": 7,
        "idx_by_type": {"Form": 0, "Command": 0, "CommandModule": 0, "ManagerModule": 6,
                        "Help": 0, "Attribute": 0, "TabularSection": 0, "Template": 0,
                        "ObjectModule": 0},
        "rows_criteria": 7, "rows_content": 727, "rows_forms": 0, "rows_form_ext": 0,
        "rows_commands": 0,
        "parse_props_all_known": 7, "parse_children_with": 0, "parse_children_empty": 7,
        "parse_content_with": 7, "parse_content_empty": 0,
        "parse_type_parsed": 7, "parse_type_absent": 0, "parse_mult_single": 6,
        "parse_mult_composite": 1, "parse_mult_absent": 0,
        "parse_form_default_with": 0, "parse_form_default_empty": 7,
        "parse_form_aux_with": 0, "parse_form_aux_empty": 7,
        "parse_resolve_exact": 727, "parse_view_wide": 0, "parse_module_files": 6,
        "parse_form_ext_xml": 0, "parse_form_ext_bin": 0,
        "pseudo": 6, "declared_children": 0,
        "child_mismatch": 0, "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
        "declaration_mismatch": 0, "files_failed": 0, "directory_missing": 0,
        "command_unknown_value": 0, "command_culprits": [],
    },
    "BP3": {
        "raw_files": 6, "raw_bytes": 112223, "raw_prop_tags": 66, "raw_content_items": 492,
        "raw_type_values": 187, "raw_type_container_Type": 187,
        "raw_type_container_TypeSet": 0, "raw_string_qualifiers": 0,
        "raw_child_Form": 0, "raw_child_Command": 0,
        "raw_form_desc": 0, "raw_form_ext_xml": 0, "raw_form_ext_bin": 0,
        "raw_form_module": 0, "raw_form_help": 0, "raw_mgr_module": 3, "raw_cmd_module": 0,
        "raw_target_type_Document": 492, "raw_targets_distinct": 424,
        "raw_help_resource_dirs": 0,
        "idx_roots": 6, "idx_children": 3, "header_list": 6,
        "idx_by_type": {"Form": 0, "Command": 0, "CommandModule": 0, "ManagerModule": 3,
                        "Help": 0, "Attribute": 0, "TabularSection": 0, "Template": 0,
                        "ObjectModule": 0},
        "rows_criteria": 6, "rows_content": 492, "rows_forms": 0, "rows_form_ext": 0,
        "rows_commands": 0,
        "parse_props_all_known": 6, "parse_children_with": 0, "parse_children_empty": 6,
        "parse_content_with": 6, "parse_content_empty": 0,
        "parse_type_parsed": 6, "parse_type_absent": 0, "parse_mult_single": 5,
        "parse_mult_composite": 1, "parse_mult_absent": 0,
        "parse_form_default_with": 0, "parse_form_default_empty": 6,
        "parse_form_aux_with": 0, "parse_form_aux_empty": 6,
        "parse_resolve_exact": 492, "parse_view_wide": 0, "parse_module_files": 3,
        "parse_form_ext_xml": 0, "parse_form_ext_bin": 0,
        "pseudo": 3, "declared_children": 0,
        "child_mismatch": 0, "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
        "declaration_mismatch": 0, "files_failed": 0, "directory_missing": 0,
        "command_unknown_value": 0, "command_culprits": [],
    },
}
# Итог по корпусу (четыре выгрузки): те же величины, что таблицы разделов 1–2 плана
# (16 объектов, 39 строк индекса — 16 верхних и 23 дочерних, 18 псевдо-записей, 3 формы с
# содержимым и 2 команды, 13 файлов модулей, 1 219 целей условия: 727 BGU2 + 492 BP3,
# 430 значений типа: 429 в `Type` и 1 в `TypeSet`). Числа пересняты 03.11.2026 после
# пересбора фикстуры `MinCfg` (шаг П9 узла V54) — круг вида в ней вырос с одного объекта
# до двух. Сверяется только когда прогнаны все четыре выгрузки: сравнивать итог по четырём
# с суммой по меньшему числу — ложное расхождение (прецедент V50/V51).
CORPUS_TOTALS = {
    "raw_files": 16, "raw_bytes": 279578, "raw_prop_tags": 176, "raw_content_items": 1219,
    "raw_type_values": 430, "raw_type_container_Type": 429, "raw_type_container_TypeSet": 1,
    "raw_string_qualifiers": 2, "raw_child_Form": 3, "raw_child_Command": 2,
    "raw_form_desc": 3, "raw_form_ext_xml": 2, "raw_form_ext_bin": 1, "raw_form_module": 0,
    "raw_form_help": 1, "raw_mgr_module": 11, "raw_cmd_module": 2, "raw_help_resource_dirs": 1,
    "raw_target_type_Document": 1219, "raw_targets_distinct": 1147,
    "idx_roots": 16, "idx_children": 23, "pseudo": 18, "declared_children": 5,
    "rows_criteria": 16, "rows_content": 1219, "rows_forms": 3, "rows_form_ext": 3,
    "rows_commands": 2, "parse_module_files": 13,
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


def counts_diff(actual, expected, label, tag, skip_prefixes=("tag_", "type_value_", "type_ns_"),
                only_prefixes=None, only_keys=None):
    """Сравнивает Counter с эталоном по всем ключам эталона и лишним ключам факта.

    `only_prefixes`/`only_keys` ограничивают круг сравниваемых ключей эталона: меры файлов,
    записей индекса, расхождений круга и счётчиков разбора — разные срезы одного плана, и
    сравнивать их одним списком означало бы требовать от счётчика файлов числа записей индекса
    (ложное расхождение).

    Префиксы `skip_prefixes` исключаются из сравнения «лишних» ключей: имена тегов
    (`tag_<Имя>`) сравниваются отдельной проверкой словаря свойств, а значения атрибута
    элемента перечня — проверкой контура 5. Молча выбрасывать их нельзя: исключение
    перечислено здесь.
    """
    wrong = []
    for key, want in expected.items():
        if not isinstance(want, int):
            continue
        if only_keys is not None and key not in only_keys:
            continue
        if only_prefixes and not str(key).startswith(tuple(only_prefixes)):
            continue
        got = actual.get(key, 0)
        if got != want:
            wrong.append(f"{label} {key}: факт {got}, план {want}")
    extra = sorted(key for key, value in actual.items()
                   if key not in expected and value
                   and not str(key).startswith(skip_prefixes))
    for key in extra:
        wrong.append(f"{label} {key}: факт {actual[key]}, в плане такого ключа нет")
    check(f"{tag}: {label} совпадают с планом", not wrong, "; ".join(wrong[:MAX_NAMES]))


def table_columns(cur, table):
    return [row["column_name"] for row in q(
        cur, "SELECT column_name FROM information_schema.columns "
             "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
        (table,))]


def set_diff(label, left, right, tag):
    """Сравнивает два множества адресов; расхождение называется поимённо с обеих сторон."""
    only_left = sorted(left - right)
    only_right = sorted(right - left)
    check(f"{tag}: {label}", not only_left and not only_right,
          "; ".join(filter(None, [
              f"только слева: {names(only_left)}" if only_left else "",
              f"только справа: {names(only_right)}" if only_right else ""])))


def table_check_constraints(cur, table, pattern):
    """Перечни CHECK'ов живой схемы по колонке — второй независимый источник словаря."""
    definitions = [row["condef"] for row in q(
        cur, "SELECT conname, pg_get_constraintdef(oid) AS condef FROM pg_constraint "
             "WHERE conrelid = %s::regclass AND contype='c' ORDER BY conname", (table,))
        if pattern in row["condef"]]
    values = set()
    for definition in definitions:
        source = " ".join(str(definition).split())
        # Перечисление значений колонки — только из формы `col = ANY (ARRAY[...])` или
        # `col IN (...)`. Литералы других мест того же текста (`'array'` внутри `jsonb_typeof`,
        # ссылки на соседние колонки) состояниями не являются: собрать их — значит придумать
        # состояние, которого в словаре нет (замер V52: `type_multiplicity` дала бы четыре
        # значения вместо трёх).
        for match in re.finditer(rf"{re.escape(pattern)}\s*=\s*ANY\s*\(ARRAY\[(.*?)\]",
                                 source, re.IGNORECASE):
            values.update(re.findall(r"'([^']*)'", match.group(1)))
        for match in re.finditer(rf"{re.escape(pattern)}\s+IN\s*\((.*?)\)", source,
                                 re.IGNORECASE):
            values.update(re.findall(r"'([^']*)'", match.group(1)))
    return definitions, values


# ═══ независимая мера круга по файлам (ElementTree, без знания о состояниях) ═══════════
def local(tag):
    return tag.split("}")[-1] if "}" in tag else tag


def named(element, name):
    return [child for child in element if local(child.tag) == name]


def first_named(element, name):
    for child in named(element, name):
        return child
    return None


def file_namespace_map(path):
    """Объявления `xmlns` одного файла — парами «префикс → URI» (мера проверки, не слоя).

    Класс значения блока `<Type>` определяется по URI пространства имён префикса ИЗ ОБЪЯВЛЕНИЯ
    этого файла (прецедент V48 2.4.4: `cfg`, `d4p1`, `d7p1` дают один URI текущей
    конфигурации), а не по имени префикса и не по URI самого тега-контейнера: `<v8:Type>` лежит
    в пространстве v8-core, а значение в нём — `xs:string` или `cfg:CatalogRef.…`. Мера обязана
    брать URI из файла независимо: иначе сверка `ns_uri` была бы сравнением разбора с самим
    собой. Разобранное дерево `ElementTree` своих объявлений не отдаёт (атрибута `nsmap` у
    `Element` нет), поэтому карта собирается событием `start-ns` — собственным каналом
    проверки, независимым от модуля разбора.
    """
    result = {}
    for _event, (prefix, uri) in ET.iterparse(str(path), events=("start-ns",)):
        result.setdefault(prefix, uri)
    return result


def value_namespace(value, ns_map):
    """URI пространства имён значения вида `prefix:local` по объявлениям самого файла.

    Объявленного префикса нет — возвращается `NS_UNDECLARED`: «префикс не объявлен» и
    «префикс объявлен в другом пространстве» — разные состояния, и оба называются мерой.
    """
    prefix = value.split(":", 1)[0] if ":" in value else ""
    uri = (ns_map or {}).get(prefix)
    return uri or NS_UNDECLARED


def measure_registration(path):
    """Мера одного файла регистрации вида: теги свойств, состав, блок типа, дети.

    Словарь тегов (`PROPERTY_NAMES`) проверка держит своим, а не берёт из модуля: сверка
    «теги файла ↔ словарь модуля» и «тега `Help` в `Properties` нет» (Q8) возможны только
    тогда, когда у проверки есть независимый перечень. Теги вне словаря называются числом и
    именами — молчать о них нельзя.

    Цели перечня считаются и текстом элемента `Item`: текст — точное имя объекта метаданных,
    первая точка которой даёт вид объекта. Это независимая мера распределения целей по видам
    (замер П6: 1 219 элементов, все — `Document`, 723 + 424 различных имени): сравнение с
    `targets_by_object_type` разбора иначе была бы сверкой одного и того же разбора с самим
    собой. Различные имена считаются в границах выгрузки — одна и та же цель встречается в
    разных критериях и даже в одном перечне (замер: 492 элемента при 424 различных).
    """
    counts, attributes, outside, targets = Counter(), Counter(), set(), set()
    root = ET.parse(str(path)).getroot()
    # Объявления xmlns читаются отдельным проходом того же файла (см. `file_namespace_map`):
    # без них мера URI значения блока `<Type>` была бы мерой пространства контейнера.
    ns_map = file_namespace_map(path)
    obj = first_named(root, OBJECT_KIND_TAG_NAME)
    if obj is None:
        counts["root_mismatch"] += 1
        return counts, attributes, outside, targets
    props = first_named(obj, "Properties")
    if props is not None:
        for name in PROPERTY_NAMES:
            counts["tag_" + name] = len(named(props, name))
        counts["raw_prop_tags"] = sum(counts["tag_" + name] for name in PROPERTY_NAMES)
        outside.update(local(child.tag) for child in props)
        content = first_named(props, CONTENT_ITEM_TAG_PARENT)
        if content is not None:
            for item in named(content, CONTENT_ITEM_TAG):
                counts["raw_content_items"] += 1
                attribute = None
                for key, value in item.attrib.items():
                    attribute = f"{local(key)}={value}"
                attributes[attribute or "<нет атрибута>"] += 1
                text = (item.text or "").strip()
                if not text:
                    counts["raw_content_empty_text"] += 1
                    continue
                targets.add(text)
                counts["raw_target_type_" + text.split(INDEX_NAME_SEPARATOR)[0]] += 1
        block = first_named(props, "Type")
        if block is not None:
            # Значения блока считаются и текстом: `<v8:Type>xs:string</v8:Type>` и
            # `<v8:TypeSet>cfg:DocumentRef</v8:TypeSet>` дают по одному значению, а контейнер
            # — имя элемента. Без независимой меры значений сверка кратности и класса была бы
            # сравнением разбора с самим собой (Q6).
            # URI значения берётся из объявления префикса в этом же файле (прецедент V48
            # 2.4.4), а не из пространства тега-контейнера: контейнер всегда в v8-core, и
            # мера по нему никогда не сошлась бы с `ns_uri` строки — прогон на MinCfg дал бы
            # «http://v8.1c.ru/8.1/data/core» против «http://www.w3.org/2001/XMLSchema» при
            # верном значении колонки.
            for container in (CONTAINER_TYPE, CONTAINER_TYPE_SET):
                for entry in named(block, container):
                    counts["raw_type_container_" + container] += 1
                    value = (entry.text or "").strip()
                    if not value:
                        continue
                    counts["raw_type_values"] += 1
                    counts["type_value_" + container + "_" + value] += 1
                    counts["type_ns_" + value_namespace(value, ns_map)] += 1
            if named(block, "StringQualifiers"):
                counts["raw_string_qualifiers"] += 1
    children = first_named(obj, "ChildObjects")
    if children is not None:
        for child in children:
            counts["raw_child_" + local(child.tag)] += 1
    counts["outside_property_tags"] = len(outside - set(PROPERTY_NAMES))
    return counts, attributes, outside, targets


def measure_object_dir(directory):
    """Файлы содержимого одного объекта вида — точными относительными путями.

    Точный путь, а не суффикс: `Ext/Help.xml` есть и у вида (его нет — замер 1.1), и у формы
    (он есть — KomMag), и суффиксный поиск смешал бы их (урок раздела 15.2 плана V51).
    Каталог ресурсов справки ищется последовательностью сегментов `Ext/Help`, потому что у
    этого вида он лежит внутри каталога формы, а не на уровне вида (замер 1.1).
    """
    counts = Counter()
    has_help_resources = False
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(directory).as_posix()
        parts = rel.split("/")
        if rel == "Ext/ManagerModule.bsl":
            counts["raw_mgr_module"] += 1
        if len(parts) >= 3 and parts[0] == "Commands" and parts[-1] == "CommandModule.bsl":
            counts["raw_cmd_module"] += 1
        if "Ext/Help" in parts or "Ext/Help" in rel:
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
    if has_help_resources:
        counts["raw_help_resource_dirs"] += 1
    return counts


def raw_measures(dump_dir):
    """Мера круга по файлам: файл регистрации плюс каталог объекта на каждый такой файл.

    Различные имена целей считаются в границах выгрузки: одна цель встречается в нескольких
    перечнях, и «различных по корпусу» было бы числом, которое ни одна нога круга не измеряет.
    """
    root = Path(dump_dir) / DIR_NAME
    totals, per_name, attributes = Counter(), {}, Counter()
    outside_names, targets = set(), set()
    if not root.is_dir():
        return totals, per_name, attributes, outside_names, targets
    for entry in sorted(root.iterdir()):
        if entry.is_dir() or entry.suffix.lower() != ".xml":
            continue
        counts, item_attributes, outside, item_targets = measure_registration(entry)
        counts["raw_bytes"] += entry.stat().st_size
        object_dir = entry.with_suffix("")
        if object_dir.is_dir():
            counts.update(measure_object_dir(object_dir))
        per_name[entry.stem] = counts
        attributes.update(item_attributes)
        outside_names.update(outside)
        targets.update(item_targets)
        for key, value in counts.items():
            totals[key] += value
    totals["raw_files"] = len(per_name)
    totals["raw_targets_distinct"] = len(targets)
    return totals, per_name, attributes, outside_names, targets


OBJECT_KIND_TAG_NAME = "FilterCriterion"
CONTENT_ITEM_TAG_PARENT = "Content"
# Псевдо-записи индекса состава (узел V47): файл есть, отдельной строки вида у него нет.
# Формы дают `Form.<Имя>.Ext/Form`, модули — `ManagerModule`/`CommandModule`, справка вида —
# `Help` (её каталог ресурсов лежит внутри каталога формы — замер 1.1). Множество держится
# проверкой, а не импортом: «псевдо-запись» — утверждение проверки о содержимом выгрузки.
PSEUDO_CHILD_TYPES = ("Ext", "Form", "ManagerModule", "CommandModule", "Help")
# Ключи расхождений круга, которые обязан назвать ответ разбора. На четырёх эталонных
# выгрузках все они нулевые (замер 1.1), и именно ноль здесь проверяется; ключи перечислены,
# потому что «ключа нет в ответе» и «ключа нет в круге» — разные состояния.
DISCREPANCY_KEYS = ("files_failed", "index_only", "file_only", "uuid_mismatch",
                    "child_mismatch", "declaration_mismatch", "directory_missing")




def parse_circle(dump_dir, index_rows=None):
    """Прогон круга разбором модуля — независимым от записи в БД.

    Индекс состава передаётся разбором сознательно: без него разрешение целей перечня
    `<Content>` и сверка детей с индексом невыразимы, и сравнение давало бы `unresolved`
    вместо настоящих состояний (наблюдение `index_not_provided`).

    Отказом считается только состояние `success is False`: отсутствие каталога вида разбор
    отвечает успешно и с наблюдением `directory_missing` (Q9), и это состояние проверяется
    отдельной пробой на фикстуре (контур 10), а не здесь.
    """
    try:
        report = collect_filter_criteria(dump_dir, index_rows=index_rows)
    except Exception as exc:
        return None, f"круг не разобран ({type(exc).__name__}: {exc})"
    if report.get("success") is not True:
        failures = report.get("files_failed") or []
        why = "; ".join(f"{item.get('source_path')}: {item.get('reason')}"
                        for item in failures[:MAX_NAMES])
        return None, f"отказ разбора круга: {why or 'файлы круга не разобраны'}"
    return report, None


def index_aggregates(cur, configuration_id):
    """Записи индекса состава вида — из таблицы `configuration_objects`.

    Источник — строки индекса, а не повторный разбор `ConfigDumpInfo.xml` (приём V44/V46/V48/
    V49/V50/V51). Индекс не загружен — это называется пропуском контура 1, а не нулями.

    Разбор держит СВОЮ классификацию записей (по сегментам точечного имени), а не переиспользует
    `child_type` загрузчика индекса: иначе «файл ↔ запись» сверялась бы одной и той же функцией
    с двух сторон. Псевдо-записью считается запись содержимого: `.ManagerModule`,
    `.Command.<Имя>.CommandModule`, `.Form.<Имя>.Help`, `.Form.<Имя>.Form` (замер 1.1).
    Счётчик `idx_by_type` ведётся по колонке `child_type` и потому включает псевдо-запись тем же
    видом, что её родитель: `Form: 2` — это форма и её содержимое (так число читается прямо из
    таблицы индекса, а не из догадки о структуре имени). Верхняя запись вида в счётчик не входит:
    её `child_type` пуст по определению, а её число уже названо отдельной мерой `idx_roots` —
    ключ `""` в распределении детей был бы вторым счётом одного и того же факта.
    """
    info = read_index_records(cur, int(configuration_id))
    rows = list(info.get("rows") or [])
    if not info.get("available"):
        return None
    kind_rows = [row for row in rows
                 if str(row.get("object_type") or "") == INDEX_OBJECT_TYPE]
    roots, children, pseudo, by_type = [], [], [], Counter()
    for row in kind_rows:
        name = str(row.get("name") or "")
        parent = str(row.get("parent_name") or "")
        if not parent:
            roots.append(row)
            continue
        children.append(row)
        by_type[str(row.get("child_type") or "")] += 1
        segments = [part for part in name.split(INDEX_NAME_SEPARATOR) if part]
        tail = segments[-1] if segments else ""
        previous = segments[-2] if len(segments) >= 2 else ""
        if tail in PSEUDO_CHILD_TYPES or (tail == CHILD_FORM and previous == CHILD_FORM):
            pseudo.append(row)
    return {"info": info, "rows": rows, "kind_rows": kind_rows, "roots": roots,
            "children": children, "pseudo": pseudo, "by_type": by_type,
            "by_name": index_rows_by_name(rows)}


def header_array(element, name):
    """Массив `<xr:<name>>` документа — список строк в порядке файла.

    Тот же приём, что у проверок V50/V51: `helps`/`formAttributes`/`interfaceContent` из
    `Configuration.xml` читаются напрямую, потому что их состояние разрешения ссылки —
    утверждение проверки, а не состояние слоя загрузки (позиция O7 узла V50).
    """
    result = []
    if element is None:
        return result
    for node in element:
        if local(node.tag) != name:
            continue
        item = {}
        for child in node:
            key = local(child.tag)
            text = (child.text or "").strip()
            if key == "Content" or key.endswith("Content"):
                item.setdefault("content", []).append(
                    {"uuid": (child.attrib.get("{http://www.w3.org/2001/03/geoxrdml/dtd"
                                              "/xsddom/xsddom}uuid")
                              or child.attrib.get("uuid") or "").strip()})
            elif text:
                item[key] = text
        result.append(item)
    return result


# ═══ сравнение «база ↔ разбор»: одна нормализация на весь прогон ══════════════════════
def norm_value(value):
    """Одно представление значения для сравнения строки БД со строкой разбора.

    Различия каналов — не различия данных: jsonb отдаётся dict/list, `ARRAY` — списком, uuid —
    объектом `psycopg2`, разбор же кладёт те же значения словарями, списками и строками. Без
    общей нормализации сравнение столбца `types` (430 записей) давало бы расхождение на каждом
    объекте, а проверка перестала бы что-либо доказывать. Пустая строка и NULL здесь равны:
    для колонок вида слой пишет NULL, а не пустое значение (CHECK `*_names_not_blank`
    запрещает пустое только ключевым колонкам).
    """
    if isinstance(value, dict):
        return json.dumps({str(key): norm_value(item) for key, item in
                           sorted(value.items(), key=lambda pair: str(pair[0]))},
                          ensure_ascii=False, sort_keys=True)
    if isinstance(value, (list, tuple, set)):
        return json.dumps([norm_value(item) for item in value], ensure_ascii=False)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, uuid.UUID):
        return str(value).lower()
    if isinstance(value, (bytes, bytearray, memoryview)):
        # Двоичное содержимое формы (`form_ext.ext_bin`): psycopg2 отдаёт `memoryview`, разбор —
        # `bytes`. Сравниваются длина и отпечаток, а не текст: литерал многомегабайтного
        # `Form.bin` в отчёте о расхождении нечитаем, а отпечаток находит любое отличие
        # побайтово — ровно то, что обязана найти проверка переноса содержимого.
        data = bytes(value)
        return f"bytes:{len(data)}:{hashlib.sha1(data).hexdigest()}"
    text = str(value).strip()
    return None if text == "" else text


# Колонки-перечни детей строки вида (`form_names TEXT[]`, `command_uuids UUID[]` — Q2 узла
# V51, те же колонки у плана обмена). Различие каналов здесь есть на самом деле: `text[]`
# psycopg2 отдаёт списком, а `uuid[]` — СТРОКОЙ с литералом массива, потому что typecaster'а
# для массива uuid нет (замер пробы П4, `_v52_p4_writer_probe.py:pg_array_items`). Без разбора
# литерала сравнение шло бы по символам строки `'{cdc0f514-…}'` против JSON-списка разбора и
# давало бы ложный отказ при верном значении колонки.
PG_ARRAY_COLUMNS = ("form_names", "command_uuids")


def pg_array_items(value):
    """Элементы перечня Postgres из того, что вернуло соединение, — списком строк или None.

    `None` возвращается и для NULL колонки, и для пустого перечня: слой пишет `NULL`, когда
    детей нет (`[…] or None`), поэтому «перечня нет» и «перечень пустой» в базе неразличимы —
    и проверка обязана читать их одинаково, а не выдумывать второе состояние.
    """
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        items = [str(item).strip().strip('"').lower() for item in value if str(item).strip()]
        return items or None
    text = str(value).strip()
    if text in ("", "{}"):
        return None
    if text.startswith("{") and text.endswith("}"):
        items = [item.strip().strip('"').lower()
                 for item in text[1:-1].split(",") if item.strip()]
        return items or None
    return [text]


def row_diff(db_row, parse_row, columns, label, skip_columns=()):
    """Расхождения по столбцам одной строки — списком «колонка: база ↔ разбор».

    Столбцы сравниваются ВСЕ, кроме перечисленных явно (`REVISION_COLUMNS`,
    `CONTENT_SKIP_COLUMNS`): выборка «интересных колонок» оставила бы незакрытый разрез, а
    смысл контура 4 именно в том, чтобы ни одна колонка вида не осталась несравненной.
    """
    problems = []
    for column in columns:
        if column in skip_columns:
            continue
        if column in PG_ARRAY_COLUMNS:
            left = norm_value(pg_array_items(db_row.get(column)))
            right = norm_value(pg_array_items(parse_row.get(column)))
        else:
            left, right = norm_value(db_row.get(column)), norm_value(parse_row.get(column))
        if left != right:
            problems.append(f"{label}.{column}: база {_brief(left)}, разбор {_brief(right)}")
    return problems


def compare_rows(tag, label, db_rows, parse_rows, key_column, columns, skip_columns=()):
    """Сверяет строки базы со строками разбора по общему ключу и по всем общим колонкам.

    Сравнение идёт по пересечению ключей разбора и колонок таблицы: колонки, которых у разбора
    нет (цепь ревизий, колонки связи строки), перечислены явно — молча выбросить их нельзя,
    потому что «колонки нет у разбора» и «колонки нет в базе» разные утверждения: первое
    находит контур 3, второе — контур 4.
    """
    by_db, by_parse, problems = {}, {}, []
    for row in db_rows:
        by_db.setdefault(str(norm_value(row.get(key_column))), row)
    for row in parse_rows:
        by_parse.setdefault(str(norm_value(row.get(key_column))), row)
    only_db = sorted(set(by_db) - set(by_parse))
    only_parse = sorted(set(by_parse) - set(by_db))
    if only_db:
        problems.append(f"в базе без разбора: {names(only_db)}")
    if only_parse:
        problems.append(f"в разборе без базы: {names(only_parse)}")
    shared = sorted(set(by_db) & set(by_parse))
    comparable = sorted((set(parse_rows[0]) if parse_rows else set()) & set(columns)
                        - set(skip_columns) - set(REVISION_COLUMNS))
    for key_value in shared:
        problems.extend(row_diff(by_db[key_value], by_parse[key_value], comparable, key_value))
    check(f"{tag}: {label} совпадают с разбором ({len(shared)} строк, "
          f"{len(comparable)} колонок)", not problems, "; ".join(problems[:MAX_NAMES]))
    return len(shared), len(comparable)


def check_key_shape(cur, parsed, tag):
    """Ключи строк разбора ↔ колонки живой схемы (двусторонне для своих таблиц).

    Для общих таблиц детей сравнение одностороннее: колонок в них больше, чем заполняет этот
    узел, — их пишут внешний контур V14 и вид V51. Ключ разбора без колонки ищется и там:
    потерянная колонка детей означает, что знание разбора никуда не записано. Исключение
    держит `REPORT_ONLY_KEYS` — состояния, для которых колонки в схеме нет сознательно (место
    их — ответ стадии), и перечислено оно именно здесь.
    """
    buckets = {TABLE_NAME: parsed["rows"], CONTENT_TABLE_NAME: parsed["content"],
               "forms": parsed["forms"], "form_ext": parsed["form_ext"],
               "commands": parsed["commands"]}
    for table, rows in buckets.items():
        if not rows:
            continue
        columns = table_columns(cur, table)
        keys = set()
        for row in rows:
            keys.update(row.keys())
        without_column = sorted(keys - set(columns) - set(REPORT_ONLY_KEYS.get(table, ())))
        check(f"{tag}: ключ разбора {table} не несёт имён без колонки", not without_column,
              _brief(without_column))
        if table not in EXPECTED_COLUMN_COUNTS:
            continue
        derived = set(REVISION_COLUMNS)
        if table == CONTENT_TABLE_NAME:
            derived |= set(CONTENT_LINK_COLUMNS)
        never = sorted(set(columns) - keys - derived)
        check(f"{tag}: колонок {table}, которые разбор не заполняет, нет", not never,
              _brief(never))


# ═══ контур 4: строки вида и детей против разбора ══════════════════════════════════════
def check_row_values(cur, circle, expect, tag):
    """Каждая колонка каждой строки обязана совпасть с ответом того же разбора.

    Разбор в этом контуре — тот же `collect_filter_criteria`, что и у загрузки: контур отвечает
    на вопрос «донёс ли писатель строку», а не «правильно ли разобрал файл» — за это отвечают
    контуры 1, 2 и 5–8 со своими измерителями по самим файлам.
    """
    parsed, db = circle["parsed"], circle["db"]
    section(f"Контур 4 — строки вида и детей против разбора ({tag})")
    check_key_shape(cur, parsed, tag)
    compare_rows(tag, "строки вида", db["criteria"], parsed["rows"], "object_uuid",
                 table_columns(cur, TABLE_NAME), REVISION_COLUMNS)
    buckets = {"forms": (parsed["forms"], "uuid", "rows_forms"),
               "form_ext": (parsed["form_ext"], "form_uuid", "rows_form_ext"),
               "commands": (parsed["commands"], "uuid", "rows_commands")}
    for table, (rows, key_column, expect_key) in buckets.items():
        db_rows = db[table]
        check(f"{tag}: строк детей {table} — {expect[expect_key]} (замер 1.1/1.2), и в базе, "
              f"и в разборе столько же", len(db_rows) == expect[expect_key]
              and len(rows) == len(db_rows),
              f"в базе {len(db_rows)}, в разборе {len(rows)}, план {expect[expect_key]}")
        if not rows:
            continue
        compare_rows(tag, f"строки детей {table}", db_rows, rows, key_column,
                     table_columns(cur, table))


# ═══ контур 5: строки условия (блок `Content`) против файла ════════════════════════════
def check_content_rows(cur, circle, expect, tag):
    """Элементы `<Content><Item>` ↔ строки `filter_criterion_content`.

    Порядок `ordinal` непрерывен от нуля и без дублей: строка условия версионируется родителем
    (Q2, вариант A), а порядок в файле — единственное, что различает два элемента с одной и той
    же целью. Счётчик `content_count` строки вида обязан равняться числу строк перечня:
    расхождение счётчика и строк читалось бы «перечень неполон» там, где он полон. Атрибут
    элемента (`xsi:type` = `xr:MDObjectRef`, замер П2 правит утверждение 2.2 плана) назван и
    он один на весь круг: «атрибута нет» — другое состояние, и оно тоже названо.
    """
    parsed, db, raw_attributes = circle["parsed"], circle["db"], circle["attributes"]
    section(f"Контур 5 — строки условия против файла ({tag})")
    check(f"{tag}: строк условия — {expect['rows_content']} в базе и {len(parsed['content'])} "
          f"в разборе (замер 1.1: элементов `Item` {expect['raw_content_items']})",
          len(db["content"]) == expect["rows_content"]
          and len(parsed["content"]) == expect["raw_content_items"],
          f"база {len(db['content'])}, разбор {len(parsed['content'])}, "
          f"файлы {expect['raw_content_items']}")
    # Пустой круг перечня — отдельное состояние, а не нарушение: у MinCfg и KomMag элементов
    # `Item` нет (замер 1.1: 0 и 0), поэтому требование «атрибут один на весь круг» к ним не
    # применимо — применимо требование «атрибутов тоже ноль». Молча пропустить проверку
    # означало бы не заметить потерю атрибута на непустом круге.
    expected_attribute = f"{CONTENT_ITEM_ATTR}={CONTENT_ITEM_TYPE_VALUE}"
    attribute_ok = ((expect["raw_content_items"] == 0 and not raw_attributes)
                    or set(raw_attributes) == {expected_attribute})
    check(f"{tag}: атрибут элемента `Item` один на весь круг — {expected_attribute} "
          f"(замер П2)"
          + ("" if expect["raw_content_items"] else "; элементов перечня нет — и атрибутов ноль"),
          attribute_ok, f"атрибуты файлов: {_brief(sorted(raw_attributes))}")
    by_criterion = {}
    for row in db["content"]:
        by_criterion.setdefault(str(row["criterion_full_name"]), []).append(row)
    ordinal_bad, order_bad, count_bad = [], [], []
    counters = {str(row["full_name"]): row for row in db["criteria"]}
    for full_name, rows in sorted(by_criterion.items()):
        ordinals = sorted(int(row[CONTENT_ORDINAL_COLUMN]) for row in rows)
        if ordinals != list(range(len(ordinals))):
            ordinal_bad.append(f"{full_name}: {names(ordinals[:MAX_NAMES])}")
        if len(set(ordinals)) != len(ordinals):
            order_bad.append(full_name)
        parent = counters.get(full_name)
        if parent is None or int(parent[CONTENT_COUNT_COLUMN] or 0) != len(rows):
            count_bad.append(f"{full_name}: строк {len(rows)}, счётчик "
                             f"{None if parent is None else parent[CONTENT_COUNT_COLUMN]}")
    check(f"{tag}: порядок `{CONTENT_ORDINAL_COLUMN}` непрерывен от нуля на каждом перечне",
          not ordinal_bad, "; ".join(ordinal_bad[:MAX_NAMES]))
    check(f"{tag}: дублей порядка строк условия нет", not order_bad, names(order_bad))
    check(f"{tag}: `{CONTENT_COUNT_COLUMN}` строки вида равен числу строк перечня",
          not count_bad, "; ".join(count_bad[:MAX_NAMES]))
    empty_named = sorted(str(row["full_name"]) for row in db["criteria"]
                         if row[CONTENT_STATE_COLUMN] == CONTENT_EMPTY_CONTENT
                         and int(row[CONTENT_COUNT_COLUMN] or 0) == 0
                         and not by_criterion.get(str(row["full_name"])))
    check(f"{tag}: пустой перечень назван состоянием `{CONTENT_EMPTY_CONTENT}`, а не нулём "
          f"строк ({expect['parse_content_empty']} строк вида — MinCfg и KomMag)",
          len(empty_named) == expect["parse_content_empty"],
          f"названо состоянием: {names(empty_named)}")
    parsed_by_key = {(str(item["criterion_full_name"]), int(item[CONTENT_ORDINAL_COLUMN])): item
                     for item in parsed["content"]}
    db_by_key = {(str(row["criterion_full_name"]), int(row[CONTENT_ORDINAL_COLUMN])): row
                 for row in db["content"]}
    set_diff("строки условия разбора ↔ строки базы (пара «критерий + порядок»)",
             set(parsed_by_key), set(db_by_key), tag)
    problems = []
    for key in sorted(set(parsed_by_key) & set(db_by_key)):
        problems.extend(row_diff(db_by_key[key], parsed_by_key[key],
                                 table_columns(cur, CONTENT_TABLE_NAME), ".".join(map(str, key)),
                                 skip_columns=CONTENT_SKIP_COLUMNS))
    check(f"{tag}: колонки строк условия совпадают с разбором", not problems,
          "; ".join(problems[:MAX_NAMES]))


# ═══ контур 6: разрешение целей перечня индексом состава ══════════════════════════════
def check_target_resolution(circle, expect, tag):
    """Каждая сохранённая цель разрешается ЗАНОВО строками индекса состава.

    Разрешение вызывается проверкой повторно (`resolve_target`), а состояние, `target_object_id`
    и `target_object_uuid` сравниваются с сохранёнными: проверка не принимает разрешение на веру,
    а переживает его по той же ноге круга. Неразрешимых целей на корпусе нет (замер Q4: 1 219
    из 1 219 `exact`), поэтому нули `prefix_only` и `unresolved` — проверяемое утверждение, а не
    предположение; сами состояния остаются в словаре как граница (Q3, вариант A).

    Распределение целей по видам объектов сравнивается с мерой файлов (текст `Item` даёт имя
    объекта, первая точка — вид): иначе сверка была бы сравнением разбора с самим собой.
    """
    parsed, db, index, raw = circle["parsed"], circle["db"], circle["index"], circle["raw"]
    section(f"Контур 6 — разрешение целей перечня ({tag})")
    raw_types = {key[len("raw_target_type_"):]: value for key, value in raw.items()
                 if key.startswith("raw_target_type_")}
    check(f"{tag}: целей перечня — {expect['raw_content_items']} (мера файлов), и разбор, и база "
          "называют столько же",
          int(parsed.get("targets_total") or 0) == expect["raw_content_items"]
          and len(db["content"]) == expect["raw_content_items"],
          f"разбор {parsed.get('targets_total')}, база {len(db['content'])}")
    check(f"{tag}: различных целей — {expect['raw_targets_distinct']} (мера файлов), разбор — "
          f"{parsed.get('targets_distinct')}",
          int(parsed.get("targets_distinct") or 0) == expect["raw_targets_distinct"],
          f"разбор {parsed.get('targets_distinct')}")
    check(f"{tag}: целей по видам объектов — как в файлах ({_brief(raw_types)})",
          dict(parsed.get("targets_by_object_type") or {}) == raw_types,
          f"разбор: {_brief(parsed.get('targets_by_object_type'))}")
    set_diff("имён целей базы ↔ имён целей из файлов",
             {str(row["target_full_name"]) for row in db["content"]}, circle["targets"], tag)
    state_bad, id_bad, uuid_bad, type_bad, path_bad = [], [], [], [], []
    for row in db["content"]:
        target = str(row["target_full_name"])
        resolved = resolve_target(target, index["by_name"])
        label = f"{row['criterion_full_name']}#{row[CONTENT_ORDINAL_COLUMN]}"
        if resolved["state"] != str(row["target_resolve_state"]):
            state_bad.append(f"{label}: база {row['target_resolve_state']}, "
                             f"разрешение заново {resolved['state']}")
        if norm_value(resolved["object_id"]) != norm_value(row["target_object_id"]):
            id_bad.append(f"{label}: {_brief(resolved['object_id'])} против "
                          f"{_brief(row['target_object_id'])}")
        if norm_value(resolved["object_uuid"]) != norm_value(row["target_object_uuid"]):
            uuid_bad.append(f"{label}: {_brief(resolved['object_uuid'])} против "
                            f"{_brief(row['target_object_uuid'])}")
        if str(row["target_object_type"]) != target.split(INDEX_NAME_SEPARATOR)[0]:
            type_bad.append(f"{label}: вид {_brief(row['target_object_type'])} против имени "
                            f"{_brief(target)}")
        if (norm_value(resolved["unresolved_path"])
                != norm_value(row[CONTENT_UNRESOLVED_PATH_COLUMN])):
            path_bad.append(f"{label}: {_brief(resolved['unresolved_path'])} против "
                            f"{_brief(row[CONTENT_UNRESOLVED_PATH_COLUMN])}")
    check(f"{tag}: состояние разрешения каждой цели совпадает с повторным разрешением",
          not state_bad, "; ".join(state_bad[:MAX_NAMES]))
    check(f"{tag}: `target_object_id` каждой цели совпадает с записью индекса",
          not id_bad, "; ".join(id_bad[:MAX_NAMES]))
    check(f"{tag}: `target_object_uuid` каждой цели совпадает с записью индекса",
          not uuid_bad, "; ".join(uuid_bad[:MAX_NAMES]))
    check(f"{tag}: `target_object_type` равен виду из точного имени цели",
          not type_bad, "; ".join(type_bad[:MAX_NAMES]))
    check(f"{tag}: `{CONTENT_UNRESOLVED_PATH_COLUMN}` названа так же, как её даёт разрешение",
          not path_bad, "; ".join(path_bad[:MAX_NAMES]))
    states = Counter(str(row["target_resolve_state"]) for row in db["content"])
    others = {state: count for state, count in states.items() if state != TARGET_EXACT}
    check(f"{tag}: состояний разрешения — `{TARGET_EXACT}` {expect['parse_resolve_exact']}, "
          f"`{TARGET_PREFIX_ONLY}` и `{TARGET_UNRESOLVED}` — нули (замер Q4)",
          states.get(TARGET_EXACT, 0) == expect["parse_resolve_exact"] and not others,
          f"факт: {_brief(dict(states))}")
    pairs = Counter((str(item["criterion_full_name"]), str(item["target_full_name"]))
                   for item in parsed["content"])
    duplicates = sum(count - 1 for count in pairs.values() if count > 1)
    named_duplicates = list(parsed.get("duplicate_targets") or [])
    check(f"{tag}: дублей пары «критерий + цель» названо {duplicates} — сколько их в перечне "
          "(повтор той же цели в разных перечнях дублем не является)",
          len(named_duplicates) == duplicates,
          f"разбор называет {len(named_duplicates)}: {names(named_duplicates[:MAX_NAMES])}, "
          f"подсчёт проверки {duplicates}")


def raw_type_values(file_counts):
    """Значения блока `<Type>` одного файла — парами (контейнер, значение).

    Имя ключа строится как `type_value_<Контейнер>_<Значение>`; контейнеры проверяются
    первыми и буквально (`TypeSet` раньше `Type`), потому что `Type` — префикс `TypeSet` и
    обратный порядок смешал бы две ветки одного блока (Q6).
    """
    values = Counter()
    for key, count in file_counts.items():
        if not key.startswith("type_value_"):
            continue
        rest = key[len("type_value_"):]
        for container in (CONTAINER_TYPE_SET, CONTAINER_TYPE):
            prefix = container + "_"
            if rest.startswith(prefix):
                values[(container, rest[len(prefix):])] += count
                break
    return values


def expected_type_class(value):
    """Класс значения по самому значению — правило проверки, а не слоя.

    `xs:` — примитив XML Schema, `cfg:` — ссылка на объект метаданных или на определённый тип;
    всё прочее обязано быть названо `unknown`, а не подтянуто под ближайший известный класс.
    """
    if value.startswith("xs:"):
        return CLASS_PRIMITIVE
    if value.startswith("cfg:"):
        return CLASS_DEFINED_TYPE_REF if "DefinedTypeRef" in value else CLASS_OBJECT_REF
    return CLASS_UNKNOWN


def expected_type_multiplicity(values):
    """Кратность блока по числу значений: 0 — `absent`, 1 — `single`, больше — `composite`."""
    if not values:
        return MULT_ABSENT
    return MULT_SINGLE if len(values) == 1 else MULT_COMPOSITE


def expected_view_wide(values):
    """Широкая ссылка вида `cfg:<Вид>Ref` без имени объекта — их мерой по файлам.

    Именно таких значений не разрешить индексом состава (цель не названа), и для KomMag это
    единственное значение блока. Разбор обязан назвать их отдельным счётчиком, а не молчать и
    не считать неразрешёнными (замер Q6: 1 из 430).
    """
    return sum(1 for _container, value in values
               if value.startswith("cfg:") and value.endswith("Ref"))


# ═══ контур 7: блок `<Type>` обеих веток (Q6) ═════════════════════════════════════════
def check_type_block(circle, expect, tag):
    """Значения, контейнеры, классы, кратность и состояния блока `<Type>` — против файлов.

    Ветка `TypeSet` на корпусе есть только у KomMag (`cfg:DocumentRef` без имени объекта), и
    именно она проверяет вторую ветку словаря контейнеров. Класс значения, кратность блока и
    число широких ссылок выводятся проверкой из текста значений и URI из файла — иначе каждая
    из этих величин была бы сравнением разбора с самим собой.
    """
    parsed, db = circle["parsed"], circle["db"]
    section(f"Контур 7 — блок `<Type>` обеих веток ({tag})")
    raw_values, raw_ns = Counter(), Counter()
    for _name, file_counts in circle["per_name"].items():
        raw_values.update(raw_type_values(file_counts))
        for key, count in file_counts.items():
            if key.startswith("type_ns_"):
                raw_ns[key[len("type_ns_"):]] += count
    containers = Counter()
    for (container, _value), count in raw_values.items():
        containers[container] += count
    check(f"{tag}: значений типа в файлах {expect['raw_type_values']}, и разбор называет "
          f"{parsed.get('types_total')}",
          int(parsed.get("types_total") or 0) == expect["raw_type_values"]
          and sum(raw_values.values()) == expect["raw_type_values"],
          f"мера файлов {sum(raw_values.values())}, разбор {parsed.get('types_total')}")
    check(f"{tag}: значений по контейнерам в файлах — Type {expect['raw_type_container_Type']}, "
          f"TypeSet {expect['raw_type_container_TypeSet']}",
          containers.get(CONTAINER_TYPE, 0) == expect["raw_type_container_Type"]
          and containers.get(CONTAINER_TYPE_SET, 0) == expect["raw_type_container_TypeSet"]
          and set(containers) <= set(TYPE_CONTAINERS),
          f"мера файлов: {_brief(dict(containers))}")
    # Сравнение словарей — с нулями с обеих сторон по закрытому словарю: разбор называет
    # каждую ветку явно (`{'Type': 1, 'TypeSet': 0}`), а Counter меры молчает о нулевых
    # ключах. Голое сравнение словарей проваливало бы верный круг на MinCfg, где `TypeSet`
    # нет ни файлом, ни записью.
    want_containers = {name: int(containers.get(name) or 0) for name in TYPE_CONTAINERS}
    got_containers = {name: int((parsed.get("types_by_container") or {}).get(name) or 0)
                      for name in TYPE_CONTAINERS}
    check(f"{tag}: разбор называет значения по контейнерам как в файлах",
          got_containers == want_containers and set(containers) <= set(TYPE_CONTAINERS),
          f"файлы: {_brief(want_containers)}, разбор: {_brief(got_containers)}")
    got_ns = Counter()
    for row in db["criteria"]:
        for entry in (row.get("types") or []):
            got_ns[str(entry["ns_uri"]) if entry.get("ns_uri") else NS_UNDECLARED] += 1
    check(f"{tag}: URI пространств имён значений типа — те же, что в файлах "
          f"({_brief(dict(raw_ns))})", dict(got_ns) == dict(raw_ns),
          f"разбор: {_brief(dict(got_ns))}")
    value_bad, class_bad, container_bad, mult_bad, key_bad = [], [], [], [], []
    base_keys = set(TYPE_ENTRY_KEYS)
    target_keys = set(TYPE_ENTRY_TARGET_KEYS)
    for row in db["criteria"]:
        name = str(row["object_name"])
        want = raw_type_values(circle["per_name"].get(name) or Counter())
        got = Counter()
        for entry in (row.get("types") or []):
            got[(str(entry.get("container")), str(entry.get("value")))] += 1
            if str(entry.get("container")) not in TYPE_CONTAINERS:
                container_bad.append(f"{name}: контейнер {_brief(entry.get('container'))}")
            want_class = expected_type_class(str(entry.get("value") or ""))
            if str(entry.get("class")) != want_class:
                class_bad.append(f"{name}: значение {_brief(entry.get('value'))} — класс "
                                 f"{_brief(entry.get('class'))}, по правилу проверки "
                                 f"{want_class}")
            # Запись `types` — закрытый словарь (Q6): без ключей `index`/`ns_uri`/`container`
            # различие двух контейнеров и двух пространств имён пропало бы, а ключи цели или
            # `reason` вне случая читались бы «цель есть» там, где её нет.
            entry_keys = set(entry.keys())
            absent_keys = sorted(base_keys - entry_keys)
            if absent_keys:
                key_bad.append(f"{name}: ключей записи типа не хватает: {names(absent_keys)}")
            entry_value = str(entry.get("value") or "")
            entry_class = str(entry.get("class"))
            allowed = set()
            if entry_class == CLASS_OBJECT_REF:
                allowed |= target_keys
                if TYPE_TARGET_RESOLVED_KEY not in entry_keys:
                    key_bad.append(f"{name}: ссылка `{entry_value}` без ключа "
                                   f"`{TYPE_TARGET_RESOLVED_KEY}` — «не разрешено» и "
                                   f"«не проверялось» неразличимы")
                elif entry.get(TYPE_TARGET_RESOLVED_KEY) is True:
                    missing = sorted(target_keys - entry_keys)
                    if missing:
                        key_bad.append(f"{name}: разрешённая ссылка `{entry_value}` без ключей "
                                       f"цели: {names(missing)}")
                else:
                    held = sorted((target_keys - {TYPE_TARGET_RESOLVED_KEY}) & entry_keys)
                    if held:
                        key_bad.append(f"{name}: неразрешённая ссылка `{entry_value}` держит "
                                       f"ключи цели — прецедент D3 (их нет вовсе, а не null): "
                                       f"{names(held)}")
            # `reason` называет, почему цели нет, и случаем является НЕ только `unknown_form`:
            # определяемый тип (узла загрузки DefinedTypes нет — прецедент V48 2.4.4) и ссылка
            # на вид целиком `cfg:<Вид>Ref` без имени объекта (замер П2, Q6) остаются
            # распознанными записями с названным основанием. Каждый случай выводится из самой
            # формы значения — иначе правило было бы повторением словаря слоя.
            reason_case = (str(entry.get("state")) == TYPE_UNKNOWN_FORM
                           or entry_class == CLASS_DEFINED_TYPE_REF
                           or (entry_class == CLASS_OBJECT_REF
                               and expected_view_wide([("", entry_value)])))
            if TYPE_ENTRY_REASON_KEY in entry_keys and not reason_case:
                key_bad.append(f"{name}: `reason` у записи состояния "
                               f"{_brief(entry.get('state'))} класса {_brief(entry_class)} — "
                               f"основания нет")
            extra = sorted(entry_keys - base_keys - allowed
                           - ({TYPE_ENTRY_REASON_KEY} if reason_case else set()))
            if extra:
                key_bad.append(f"{name}: ключи записи типа вне своего случая: {names(extra)}")
        if got != want:
            value_bad.append(f"{name}: база {_brief(dict(got))}, файл {_brief(dict(want))}")
        want_mult = expected_type_multiplicity(want)
        if str(row["type_multiplicity"]) != want_mult:
            mult_bad.append(f"{name}: база {row['type_multiplicity']}, по числу значений "
                            f"{want_mult}")
    check(f"{tag}: значения и контейнеры каждой строки совпадают с её файлом",
          not value_bad, "; ".join(value_bad[:MAX_NAMES]))
    check(f"{tag}: класс каждого значения выведен из самого значения (Q6)",
          not class_bad, "; ".join(class_bad[:MAX_NAMES]))
    check(f"{tag}: контейнеры замкнуты словарём {sorted(TYPE_CONTAINERS)}",
          not container_bad, "; ".join(container_bad[:MAX_NAMES]))
    check(f"{tag}: ключи записей `types` замкнуты словарём и соответствуют своему случаю "
          f"(ключи цели — только у разрешённого `{CLASS_OBJECT_REF}`, "
          f"`{TYPE_TARGET_RESOLVED_KEY}` — у любой ссылки, `reason` — только у записи, "
          f"объясняющей отсутствие цели)",
          not key_bad, "; ".join(key_bad[:MAX_NAMES]))
    check(f"{tag}: кратность блока выведена из числа значений (Q6)",
          not mult_bad, "; ".join(mult_bad[:MAX_NAMES]))
    view_wide = expected_view_wide(raw_values)
    check(f"{tag}: широких ссылок `cfg:<Вид>Ref` без имени объекта — {view_wide} (мера файлов), "
          f"разбор — {parsed.get('types_object_ref_view_wide')}",
          int(parsed.get("types_object_ref_view_wide") or 0) == view_wide,
          f"разбор: {parsed.get('types_object_ref_view_wide')}")
    resolved = int(parsed.get("types_object_ref_resolved") or 0)
    unresolved = int(parsed.get("types_unresolved_total") or 0)
    total = int(parsed.get("types_total") or 0)
    # Инвариант относится к классу ссылок, а не ко всем значениям блока: примитив
    # (`xs:string` у MinCfg) и ссылка на определяемый тип индексом состава не разрешаются
    # вообще, и требовать от них одного из трёх состояний — значит придумывать состояние,
    # которого в словаре нет. Мера класса держится проверкой своя, по тексту значений (Q6).
    references = sum(count for (_container, value), count in raw_values.items()
                     if expected_type_class(value) == CLASS_OBJECT_REF)
    check(f"{tag}: каждое значение класса `{CLASS_OBJECT_REF}` отнесено ровно к одному "
          f"состоянию: разрешено {resolved} + широкая "
          f"{parsed.get('types_object_ref_view_wide')} + неразрешённое {unresolved} = ссылок "
          f"{references} (значений вне класса — {total - references})",
          resolved + view_wide + unresolved == references,
          f"сумма {resolved + view_wide + unresolved} против ссылок {references} "
          f"из {total} значений")
    states = Counter(str(row["type_parse_state"]) for row in db["criteria"])
    check(f"{tag}: состояний разбора блока — `{TYPE_PARSED}` {expect['parse_type_parsed']}, "
          f"`{TYPE_ABSENT}` {expect['parse_type_absent']}; `{TYPE_PARTIAL}` и "
          f"`{TYPE_UNKNOWN_FORM}` — нули (замер Q6)",
          states.get(TYPE_PARSED, 0) == expect["parse_type_parsed"]
          and states.get(TYPE_ABSENT, 0) == expect["parse_type_absent"]
          and states.get(TYPE_PARTIAL, 0) == 0 and states.get(TYPE_UNKNOWN_FORM, 0) == 0,
          f"факт: {_brief(dict(states))}")
    mults = Counter(str(row["type_multiplicity"]) for row in db["criteria"])
    check(f"{tag}: кратности — `single` {expect['parse_mult_single']}, "
          f"`composite` {expect['parse_mult_composite']}, "
          f"`absent` {expect['parse_mult_absent']}",
          mults.get(MULT_SINGLE, 0) == expect["parse_mult_single"]
          and mults.get(MULT_COMPOSITE, 0) == expect["parse_mult_composite"]
          and mults.get(MULT_ABSENT, 0) == expect["parse_mult_absent"],
          f"факт: {_brief(dict(mults))}")
    qualifier_rows = sum(1 for row in db["criteria"] if (row.get("type_qualifiers") or {}))
    parse_qualifier_rows = sum(1 for row in parsed["rows"] if (row.get("type_qualifiers") or {}))
    check(f"{tag}: блоков квалификаторов в файлах — {expect['raw_string_qualifiers']} (замер 2.4: "
          "он один, у MinCfg), строк с непустой колонкой `type_qualifiers` — столько же, и в "
          "базе, и в разборе",
          qualifier_rows == expect["raw_string_qualifiers"]
          and parse_qualifier_rows == expect["raw_string_qualifiers"],
          f"в базе {qualifier_rows}, в разборе {parse_qualifier_rows}")
    # Распределение по классам — тоже с нулями по закрытому словарю с обеих сторон
    # (тот же приём, что со словарём контейнеров): разбор называет все четыре класса явно.
    class_want = {name: 0 for name in TYPE_CLASS_VALUES}
    for (_container, value), count in raw_values.items():
        class_want[expected_type_class(value)] += count
    class_got = {name: int((parsed.get("types_by_class") or {}).get(name) or 0)
                 for name in TYPE_CLASS_VALUES}
    check(f"{tag}: значений по классам — как их выводит правило проверки по значениям файлов "
          f"({_brief(class_want)})", class_got == class_want,
          f"разбор: {_brief(class_got)}")


def read_db_circle(cur, header_uuid):
    """Строки круга вида, относящиеся к одной конфигурации, — общими предикатами.

    Источник — витрины текущего состояния (канал узла V19), а не базовые таблицы: перезагрузка
    выгрузки (проба П8) оставляет историю ревизий, и счётчик по базовой таблице читался бы как
    удвоение круга. `forms`/`form_ext`/`commands` — таблицы общие (их пишут внешний контур V14
    и вид V51), поэтому граница круга идёт по uuid родителей вида плюс нога `configuration_uuid`
    и `parent_type`, а не по одной ноге: `configuration_uuid` собрал бы детей всех объектов
    конфигурации. `form_ext` ноги конфигурации не имеет (наблюдение П6 узла V51) — она читается
    связкой по строке формы.
    """
    cfg = str(header_uuid)
    criteria_view = CURRENT_VIEWS[TABLE_NAME]
    parents = (f"(SELECT object_uuid FROM {criteria_view} WHERE configuration_uuid = %s::uuid)")
    criteria = q(cur, f"SELECT * FROM {criteria_view} WHERE configuration_uuid = %s::uuid",
                 (cfg,))
    content = q(cur, f"SELECT * FROM {CURRENT_VIEWS[CONTENT_TABLE_NAME]} "
                     f"WHERE configuration_uuid = %s::uuid ORDER BY criterion_full_name, "
                     f"{CONTENT_ORDINAL_COLUMN}", (cfg,))
    # `parents` сам содержит `%s` (подзапрос по uuid вида), поэтому параметров у запроса два:
    # с одним psycopg2 даёт «IndexError: tuple index out of range» — текст SQL об этом не
    # говорит, и об этом стоит сказать здесь, а не искать по стеку.
    forms = q(cur, f"SELECT * FROM {CURRENT_VIEWS['forms']} WHERE configuration_uuid = %s::uuid "
                   f"AND parent_type = 'configuration_objects' AND parent_uuid IN {parents} "
                   "ORDER BY name", (cfg, cfg))
    commands = q(cur, f"SELECT * FROM {CURRENT_VIEWS['commands']} "
                      f"WHERE configuration_uuid = %s::uuid "
                      f"AND parent_type = 'configuration_objects' AND parent_uuid IN {parents} "
                      "ORDER BY name", (cfg, cfg))
    form_ext = q(cur, f"SELECT x.* FROM {CURRENT_VIEWS['form_ext']} x "
                      f"JOIN {CURRENT_VIEWS['forms']} fo ON fo.id = x.form_id "
                      f"WHERE fo.configuration_uuid = %s::uuid "
                      f"AND fo.parent_type = 'configuration_objects' "
                      f"AND fo.parent_uuid IN (SELECT object_uuid FROM {criteria_view} "
                      "WHERE configuration_uuid = %s::uuid) ORDER BY fo.name", (cfg, cfg))
    return {"criteria": criteria, "content": content, "forms": forms, "commands": commands,
            "form_ext": form_ext}


def index_child_names(index_rows, object_full_name, child_kind):
    """Имена записей индекса состава — дети одного вида и одного вида-ребёнка."""
    prefix = object_full_name + INDEX_NAME_SEPARATOR + child_kind + INDEX_NAME_SEPARATOR
    return sorted(str(row.get("name") or "") for row in index_rows
                  if str(row.get("name") or "").startswith(prefix))


def declared_children(dump_dir, name):
    """Дети, объявленные `<ChildObjects>` файла регистрации, — именами и точным составом.

    Объявление держится у проверки своим измерителем: сравнение «объявлено ↔ запись индекса ↔
    файл на диске» требует трёх независимых сторон, и третья сторона (разбор слоя) в этом
    сравнении участвует только как проверяемый.
    """
    path = Path(dump_dir) / DIR_NAME / f"{name}.xml"
    if not path.is_file():
        return {}
    root = ET.parse(str(path)).getroot()
    obj = first_named(root, OBJECT_KIND_TAG_NAME)
    result = {}
    if obj is None:
        return result
    container = first_named(obj, "ChildObjects")
    if container is None:
        return result
    for child in container:
        # Имя ребёнка читается по-разному в двух формах объявления (замер файла MinCfg):
        # `<Form>ФормаСписка</Form>` даёт имя текстом, а `<Command uuid="…">` держит вложенный
        # блок `<Properties><Name>`, и текст такого элемента пуст. Мера, читающая только текст,
        # посчитала бы объявленную команду нулём — и сравнение «объявлено ↔ запись индекса ↔
        # файл на диске» провалилось бы при верном круге (прогон 01.11.2026 дал 1 вместо 2).
        name = (child.text or "").strip()
        if not name:
            props = first_named(child, "Properties")
            if props is not None:
                name_element = first_named(props, "Name")
                if name_element is not None:
                    name = (name_element.text or "").strip()
        result.setdefault(local(child.tag), []).append(name)
    return result


# ═══ контур 1: граница круга — файл, индекс состава, объявленные дети ══════════════════
def check_circle(cur, header, dump_dir, expect, tag):
    """Граница круга: файлы круга ↔ записи индекса ↔ объявления `<ChildObjects>`.

    Три стороны сравниваются независимыми измерителями: файлы считает проверка (ElementTree и
    обход каталога), записи индекса — таблица `configuration_objects`, объявления детей —
    снова проверка. Разбор слоя в этом контуре — проверяемый: он обязан назвать тот же круг
    (`files_found`, `index_only`, `file_only`, `uuid_mismatch`, `child_mismatches`,
    псевдо-записи). Расхождений на четырёх выгрузках нет (замер 1.1), и ноль здесь —
    проверяемое утверждение, а не предположение.
    """
    index = index_aggregates(cur, int(header["id"]))
    if index is None:
        skip(f"{tag}: контур границы круга", "индекс состава этого заголовка не загружен")
        return None
    parsed, failure = parse_circle(dump_dir, index_rows=index["rows"])
    if failure:
        check(f"{tag}: круг разбирается без отказа", False, failure)
        return None
    raw, per_name, item_attributes, outside, targets = raw_measures(dump_dir)
    circle = {"parsed": parsed, "raw": raw, "per_name": per_name, "attributes": item_attributes,
              "outside": outside, "targets": targets, "index": index, "dump_dir": dump_dir,
              "db": read_db_circle(cur, header["uuid"])}

    section(f"Контур 1 — граница круга ({tag})")
    counts_diff(raw, expect, f"независимые меры `{DIR_NAME}/` (файлы, теги, значения, дети)",
                tag, only_prefixes=("raw_",))
    check(f"{tag}: словарь свойств вида совпадает с тегами файлов (11 позиций, порядок файла)",
          tuple(record[0] for record in property_records()) == PROPERTY_NAMES,
          _brief([record[0] for record in property_records()]))
    outside_tags = sorted(outside - set(PROPERTY_NAMES))
    check(f"{tag}: тегов `<Properties>` вне словаря свойств — ноль (замер 2.x: 11 тегов, "
          "тега `Help` среди них нет)", not outside_tags and not raw.get("outside_property_tags"),
          f"вне словаря: {_brief(outside_tags)}")
    check(f"{tag}: записей вида в индексе состава — {expect['idx_roots']}, детей — "
          f"{expect['idx_children']} (замер 1.1)",
          len(index["roots"]) == expect["idx_roots"]
          and len(index["children"]) == expect["idx_children"],
          f"верхних {len(index['roots'])}, детей {len(index['children'])}")
    counts_diff(index["by_type"], expect["idx_by_type"], "записи индекса по `child_type`", tag,
                skip_prefixes=())
    set_diff("файлы регистрации ↔ верхние записи индекса состава",
             {index_object_name(name) for name in per_name},
             {index_row_key(row) for row in index["roots"]}, tag)
    check(f"{tag}: разбором назван тот же круг файлов — {raw['raw_files']}",
          parsed["files_found"] == raw["raw_files"] and parsed["files_read"] == raw["raw_files"],
          f"разбор: files_found={parsed['files_found']}, files_read={parsed['files_read']}, "
          f"файлов на диске {raw['raw_files']}")
    counts_diff({"files_failed": len(parsed["files_failed"]),
                 "index_only": len(parsed["index_only"]),
                 "file_only": len(parsed["file_only"]),
                 "uuid_mismatch": len(parsed["uuid_mismatch"]),
                 "child_mismatch": len(parsed["child_mismatches"]),
                 "declaration_mismatch": len(parsed["declaration_mismatches"]),
                 "directory_missing": int(any(kind == OBSERVATION_DIRECTORY_MISSING
                                             for kind, _detail in parsed["observations"]))},
                expect, "расхождений круга (их нулей)", tag, skip_prefixes=(),
                only_keys=DISCREPANCY_KEYS)
    if parsed["index_only"] or parsed["file_only"] or parsed["uuid_mismatch"]:
        info(f"{tag}: расхождения файла и индекса названы: index_only="
             f"{names(parsed['index_only'])}, file_only={names(parsed['file_only'])}, "
             f"uuid_mismatch={names([str(item.get('source_path')) for item in parsed['uuid_mismatch']])}")
    check(f"{tag}: строк вида от разбора — {expect['rows_criteria']} (замер 1.1)",
          len(parsed["rows"]) == expect["rows_criteria"], f"разбор дал {len(parsed['rows'])}")
    check(f"{tag}: строк вида в базе — {expect['rows_criteria']}",
          len(circle["db"]["criteria"]) == expect["rows_criteria"],
          f"в базе {len(circle['db']['criteria'])}")
    return circle


# ═══ контур 2: дети вида и псевдо-записи индекса ═════════════════════════════════════
def check_children_circle(circle, expect, tag):
    """Дети: объявление ↔ запись индекса ↔ файл на диске; псевдо-записи названы.

    Псевдо-запись (содержимое формы, модуль, справка) — не ребёнок вида в смысле строк таблиц:
    отдельной строки вида у неё нет (узел V47). Разбор обязан назвать их списком, и список
    обязан совпасть с тем, что считает проверка по таблице индекса: иначе «детей нет»
    читалось бы как «содержимого нет», а 18 псевдо-записей корпуса пропали бы.

    Файлы модулей и содержимое форм — третья сторона того же круга: их счётчик в ответе
    (`module_files_by_kind`, `form_ext_formats`) обязан совпасть с обходом каталога, который
    делает проверка. Именно на этих счётчиках прогон П4 слоя дал квадратичное завышение
    (27 против 6 на BGU2), поэтому сравнение с независимым обходом — не формальность.
    """
    parsed, index, raw = circle["parsed"], circle["index"], circle["raw"]
    section(f"Контур 2 — дети, псевдо-записи и файлы содержимого ({tag})")
    declared_total = 0
    for name in sorted(circle["per_name"]):
        declared = declared_children(circle["dump_dir"], name)
        full_name = index_object_name(name)
        for kind in (CHILD_FORM, CHILD_COMMAND):
            titles = sorted(title for title in declared.get(kind, []) if title)
            declared_total += len(titles)
            wanted = [full_name + INDEX_NAME_SEPARATOR + kind + INDEX_NAME_SEPARATOR + title
                      for title in titles]
            present = index_child_names(index["rows"], full_name, kind)
            missing = sorted(item for item in wanted if item not in present)
            check(f"{tag}: {full_name}: детей `{kind}` объявлено {len(titles)}, каждый "
                  "подтверждён записью индекса", not missing,
                  f"без записей индекса: {names(missing)}")
    check(f"{tag}: объявленных детей по файлам — {expect['declared_children']} (замер 1.2)",
          declared_total == expect["declared_children"], f"факт: {declared_total}")
    foreign_kinds = sorted({kind for name in circle["per_name"]
                            for kind in declared_children(circle["dump_dir"], name)
                            if kind not in (CHILD_FORM, CHILD_COMMAND)})
    check(f"{tag}: `<ChildObjects>` не объявляет видов, которых у вида нет "
          "(реквизитов, ТЧ, макетов, модуля объекта — замер 1.2)", not foreign_kinds,
          _brief(foreign_kinds))
    parse_pseudo = sorted(str(item.get("index_name") or "")
                          for item in parsed["index_pseudo_entries"])
    own_pseudo = sorted(str(row.get("name") or "") for row in index["pseudo"])
    check(f"{tag}: псевдо-записей индекса — {expect['pseudo']} (замер 1.1)",
          len(own_pseudo) == expect["pseudo"] and len(parse_pseudo) == expect["pseudo"],
          f"проверка: {len(own_pseudo)}, разбор: {len(parse_pseudo)}")
    set_diff("псевдо-записи, названные разбором ↔ посчитанные проверкой",
             set(parse_pseudo), set(own_pseudo), tag)
    for kind, want in ((OBSERVATION_HELP_RESOURCES, raw["raw_help_resource_dirs"]),
                       (OBSERVATION_HELP_FILE, raw["raw_form_help"])):
        got = int((parsed.get("ext_observations") or {}).get(kind, 0))
        check(f"{tag}: наблюдение `{kind}` — {want} (файлы круга)", got == want,
              f"разбор: {got}, обход каталога: {want}")
    module_total = raw["raw_mgr_module"] + raw["raw_cmd_module"] + raw["raw_form_module"]
    check(f"{tag}: файлов модулей названо — {module_total} (обход каталога)",
          int(parsed.get("module_files_total") or 0) == module_total,
          f"разбор: {parsed.get('module_files_total')}")
    by_kind = parsed.get("module_files_by_kind") or {}
    check(f"{tag}: файлов модулей — по видам без завышения (дефект счётчика, найденный П4)",
          sum(int(value) for value in by_kind.values()) == int(parsed.get("module_files_total") or 0),
          f"{_brief(by_kind)} против total {parsed.get('module_files_total')}")
    formats = parsed.get("form_ext_formats") or {}
    check(f"{tag}: содержимое форм разобрано в тех же форматах, что на диске "
          f"(xml {raw['raw_form_ext_xml']}, bin {raw['raw_form_ext_bin']})",
          int(formats.get("xml", 0)) == raw["raw_form_ext_xml"]
          and int(formats.get("bin", 0)) == raw["raw_form_ext_bin"],
          f"разбор: {_brief(formats)}")


# ═══ контур 3: живая схема — круг колонок и ключей узла ═══════════════════════════════
# Колонки, которые обязан заполнить разбор (моя формулировка круга, а не список модуля):
# сравнение «ключа разбора нет в таблице» ловит расхождение словаря слоя и миграции — ровно
# то, что не ловит ни один прогон загрузки, если писатель молча пропускает колонку.
PARSER_ROW_KEYS = {
    TABLE_NAME: ("object_uuid", "object_name", "full_name", "source_path",
                 "type_raw", "type_multiplicity", "type_parse_state", "types",
                 "type_qualifiers", DEFAULT_FORM_STATE_COLUMN, AUXILIARY_FORM_STATE_COLUMN,
                 "form_names", "command_uuids", CONTENT_STATE_COLUMN, CONTENT_COUNT_COLUMN,
                 CHILDREN_STATE_COLUMN, UNKNOWN_NAMES_COLUMN),
    CONTENT_TABLE_NAME: (CONTENT_ORDINAL_COLUMN, CONTENT_TARGET_TAG_COLUMN,
                         CONTENT_TARGET_COLUMN, CONTENT_TARGET_TYPE_COLUMN,
                         CONTENT_TARGET_ID_COLUMN, CONTENT_TARGET_UUID_COLUMN,
                         CONTENT_RESOLVE_STATE_COLUMN, CONTENT_UNRESOLVED_PATH_COLUMN,
                         "criterion_object_uuid", "criterion_full_name"),
}
# Колонки общих детских таблиц, без которых строка круга вида не выражается. Обратное
# утверждение (что этих колонок в таблице достаточно) здесь не проверяется сознательно:
# `forms`/`form_ext`/`commands` пишут и внешний контур (V14), и вид V51, и будущие узлы —
# лишние колонки в них не являются дефектом узла V52.
SHARED_REQUIRED_COLUMNS = {
    "forms": ("uuid", "parent_uuid", "name", "configuration_uuid", "parent_type"),
    "commands": ("uuid", "parent_uuid", "name", "configuration_uuid", "parent_type",
                 "command_group", "properties_state", "unknown_property_names"),
    "form_ext": ("form_id", "form_uuid", "parent_uuid", "parent_type", "name", "ext",
                 "ext_size", "ext_truncated", "ext_bin", "ext_format", "ext_path",
                 "items", "attributes", "events", "commands"),
}
# Ключи, которые обязан держать узел: пара «конфигурация + имя + ревизия» и порядок строк
# перечня (Q2 вариант A — строка условия версионируется родителем, своей цепи у неё нет).
REQUIRED_KEYS = {
    TABLE_NAME: ("configuration_uuid", "object_name", "revision_no"),
    CONTENT_TABLE_NAME: (CONTENT_PARENT_COLUMN, CONTENT_ORDINAL_COLUMN),
}


def check_schema(cur):
    """Живая схема круга: колонки двух таблиц, колонки общих детей, ключи и витрины."""
    section("Контур 3 — живая схема круга")
    for table, want in EXPECTED_COLUMN_COUNTS.items():
        columns = table_columns(cur, table)
        check(f"{table}: таблица существует и держит {want} колонок (эталон П1)",
              len(columns) == want, f"колонок: {len(columns)}")
    property_target = table_columns(cur, TABLE_NAME)
    missing_columns = sorted(set(property_columns()) - set(property_target))
    check(f"{TABLE_NAME}: каждая колонка словаря свойств существует в таблице",
          not missing_columns, _brief(missing_columns))
    for table, keys in PARSER_ROW_KEYS.items():
        columns = set(table_columns(cur, table))
        absent = sorted(set(keys) - columns)
        check(f"{table}: ключи строк разбора ⊆ колонок таблицы", not absent, _brief(absent))
    for table, columns in SHARED_REQUIRED_COLUMNS.items():
        present = set(table_columns(cur, table))
        absent = sorted(set(columns) - present)
        check(f"{table}: колонок, нужных строке круга вида, нет — ноль (сверка односторонняя: "
              "таблицу пишут и другие узлы)", not absent, _brief(absent))
    for table, parts in REQUIRED_KEYS.items():
        rows = q(cur, "SELECT pg_get_constraintdef(oid) AS def FROM pg_constraint "
                      "WHERE conrelid = %s::regclass AND contype IN ('u','p')", (table,))
        definitions = " ".join(str(row["def"]) for row in rows)
        missing = [part for part in parts if f"{part}" not in definitions]
        check(f"{table}: ключ области видимости строк узла живой ({', '.join(parts)})",
              not missing, f"в определениях ключей нет: {_brief(missing)}")
    fk = q(cur, "SELECT pg_get_constraintdef(oid) AS def FROM pg_constraint "
                "WHERE conrelid = %s::regclass AND contype='f'", (CONTENT_TABLE_NAME,))
    cascade = any(CONTENT_PARENT_COLUMN in str(row["def"]) and "ON DELETE CASCADE" in str(row["def"])
                  for row in fk)
    check(f"{CONTENT_TABLE_NAME}: строка условия снимается каскадом со строкой вида "
          f"(FK `{CONTENT_PARENT_COLUMN}`)", cascade, _brief([row["def"] for row in fk]))
    missing_views = [view for view in CURRENT_VIEWS.values() if not q(
        cur, "SELECT 1 FROM information_schema.views WHERE table_name = %s", (view,))]
    check("витрины текущего состояния круга объявлены (миграция V52)", not missing_views,
          _brief(missing_views))


# ═══ контур 8: ссылки на формы (замер 2.3) ════════════════════════════════════════════
def value_column_of(state_column):
    """Колонка значения по колонке состояния: `default_form_state` → `default_form`.

    Пара колонок принадлежит одной позиции словаря свойств (состояние и значение разделяются
    именно для того, чтобы пустое значение было отличимо от ссылки), и проверка берёт имена из
    `FORM_REF_COLUMNS`, а не держит свой список колонок.
    """
    return state_column[: -len("_state")]


def check_form_references(circle, expect, tag):
    """Пара «значение ↔ состояние» и разрешимость ссылки индексом состава того же объекта.

    Независимая мера — текст тега `DefaultForm`/`AuxiliaryForm` из файла регистрации:
    `with_reference` обязан стоять там и только там, где текст есть (пересъём 03.11.2026:
    5 полей на трёх файлах, остальные 27 — `empty_value`). Ссылка обязана быть записью
    индекса состава того же объекта: ссылка на форму другого объекта — другое знание, чем
    ссылка на форму, которой нет. Перечень `form_names` строки вида сверяется с объявленными
    `<ChildObjects><Form>`, иначе «формы нет» и «форма не объявлена» читались бы одинаково.
    """
    db, index = circle["db"], circle["index"]
    section(f"Контур 8 — ссылки на формы ({tag})")
    want = {DEFAULT_FORM_STATE_COLUMN: (expect["parse_form_default_with"],
                                        expect["parse_form_default_empty"]),
            AUXILIARY_FORM_STATE_COLUMN: (expect["parse_form_aux_with"],
                                          expect["parse_form_aux_empty"])}
    file_refs = {}
    for property_name, state_column in FORM_REF_COLUMNS:
        refs = set()
        for name in sorted(circle["per_name"]):
            path = Path(circle["dump_dir"]) / DIR_NAME / f"{name}.xml"
            root = ET.parse(str(path)).getroot()
            obj = first_named(root, OBJECT_KIND_TAG_NAME)
            props = first_named(obj, "Properties") if obj is not None else None
            node = first_named(props, property_name) if props is not None else None
            text = (node.text or "").strip() if node is not None else ""
            if text:
                refs.add((name, text))
        file_refs[state_column] = refs
        with_want, empty_want = want[state_column]
        states = Counter(str(row[state_column]) for row in db["criteria"])
        check(f"{tag}: состояний `{state_column}` — `{FORM_REF_WITH_REFERENCE}` {with_want}, "
              f"`{FORM_REF_EMPTY_VALUE}` {empty_want} (замер 2.3)",
              states.get(FORM_REF_WITH_REFERENCE, 0) == with_want
              and states.get(FORM_REF_EMPTY_VALUE, 0) == empty_want
              and sum(states.values()) == len(db["criteria"]),
              f"факт: {_brief(dict(states))}")
        got = {(str(row["object_name"]), str(row[value_column_of(state_column)]))
               for row in db["criteria"] if row.get(value_column_of(state_column))}
        set_diff(f"непустых ссылок `{state_column}` по файлам ↔ названных базой", refs, got, tag)
    pair_bad = []
    for row in db["criteria"]:
        for _property_name, state_column in FORM_REF_COLUMNS:
            value = row.get(value_column_of(state_column))
            state = str(row[state_column])
            if value and state != FORM_REF_WITH_REFERENCE:
                pair_bad.append(f"{row['object_name']}: значение при состоянии {state}")
            if not value and state != FORM_REF_EMPTY_VALUE:
                pair_bad.append(f"{row['object_name']}: пустое значение при состоянии {state}")
    check(f"{tag}: пары «значение ↔ состояние» согласованы (пустое значение — только "
          f"`{FORM_REF_EMPTY_VALUE}`)", not pair_bad, "; ".join(pair_bad[:MAX_NAMES]))
    bad_ref = []
    for row in db["criteria"]:
        for _property_name, state_column in FORM_REF_COLUMNS:
            value = row.get(value_column_of(state_column))
            if not value:
                continue
            target = str(value)
            if index["by_name"].get(target) is None:
                bad_ref.append(f"{row['object_name']}: ссылке {_brief(target)} нет записи "
                               "индекса состава")
                continue
            own = index_object_name(str(row["object_name"])) + INDEX_NAME_SEPARATOR
            if not target.startswith(own):
                bad_ref.append(f"{row['object_name']}: ссылка {_brief(target)} ведёт не в этот "
                               f"объект (префикс {_brief(own)})")
    check(f"{tag}: каждая непустая ссылка подтверждена записью индекса состава того же объекта",
          not bad_ref, "; ".join(bad_ref[:MAX_NAMES]))
    names_bad = []
    for row in db["criteria"]:
        declared = sorted(title for title in declared_children(
            circle["dump_dir"], str(row["object_name"])).get(CHILD_FORM, []) if title)
        stored = sorted(str(title) for title in (row.get("form_names") or []))
        if stored != declared:
            names_bad.append(f"{row['object_name']}: база {names(stored)}, "
                             f"файл {names(declared)}")
    check(f"{tag}: `form_names` строки вида совпадает с объявленными `<ChildObjects><Form>`",
          not names_bad, "; ".join(names_bad[:MAX_NAMES]))


# ═══ контур 9: словари состояний и их распределение в строках ═════════════════════════
def check_state_vocabulary(cur):
    """Замкнутость словарей модуля сверяется с перечнями CHECK'ов живой схемы.

    Двусторонняя сверка: значение словаря модуля без строки в CHECK означает, что состояние
    могло бы записаться без ограничения, а значение CHECK без словаря модуля — что состояние
    появилось бы из кода, которого нет (прецедент `STATE_VOCABULARIES` узлов V50/V51).
    """
    section("Контур 9 (часть 1) — словари состояний против CHECK'ов схемы")
    for column, vocabulary in STATE_VOCABULARIES.items():
        table = STATE_VOCABULARY_TABLES[column]
        definitions, live = table_check_constraints(cur, table, column)
        check(f"{table}.{column}: CHECK живой схемы перечисляет словарь модуля "
              f"({len(vocabulary)} значений)", bool(definitions) and live == set(vocabulary),
              f"CHECK: {_brief(sorted(live))}, модуль: {_brief(sorted(vocabulary))}")


def check_row_states(circle, expect, tag):
    """Распределение состояний в строках круга — против плана и мер файлов.

    Неизвестные состояния среди строк вида — нули, и ноль проверяется, а не подразумевается.
    Отдельно называется состояние `unknown_value` строки команды (MinCfg, виновник `Group`):
    значения свойств детей узлом не удерживаются (решение Q7 узла V50), и это названная
    граница круга, а не дефект разбора — поэтому она сверяется с планом, а не с нулём.
    """
    parsed, db = circle["parsed"], circle["db"]
    section(f"Контур 9 (часть 2) — распределение состояний в строках ({tag})")
    props = Counter(str(row["properties_state"]) for row in db["criteria"])
    check(f"{tag}: свойств вида разобрано без неизвестных — {expect['parse_props_all_known']} "
          f"(строк вида {expect['rows_criteria']})",
          props.get(PROPS_ALL_KNOWN, 0) == expect["parse_props_all_known"]
          and len(db["criteria"]) == expect["rows_criteria"],
          f"факт: {_brief(dict(props))}")
    children = Counter(str(row[CHILDREN_STATE_COLUMN]) for row in db["criteria"])
    check(f"{tag}: состояний детей — `{CHILD_WITH_CONTENT}` "
          f"{expect['parse_children_with']}, `{CHILD_EMPTY_CONTENT}` "
          f"{expect['parse_children_empty']}",
          children.get(CHILD_WITH_CONTENT, 0) == expect["parse_children_with"]
          and children.get(CHILD_EMPTY_CONTENT, 0) == expect["parse_children_empty"],
          f"факт: {_brief(dict(children))}")
    content = Counter(str(row[CONTENT_STATE_COLUMN]) for row in db["criteria"])
    check(f"{tag}: состояний перечня — `{CONTENT_WITH_CONTENT}` {expect['parse_content_with']}, "
          f"`{CONTENT_EMPTY_CONTENT}` {expect['parse_content_empty']} (пустой блок назван "
          "состоянием, а не нулём строк)",
          content.get(CONTENT_WITH_CONTENT, 0) == expect["parse_content_with"]
          and content.get(CONTENT_EMPTY_CONTENT, 0) == expect["parse_content_empty"],
          f"факт: {_brief(dict(content))}")
    for column in ("properties_state", CHILDREN_STATE_COLUMN, CONTENT_STATE_COLUMN,
                   "type_parse_state", "type_multiplicity", DEFAULT_FORM_STATE_COLUMN,
                   AUXILIARY_FORM_STATE_COLUMN):
        outside = sorted({str(row[column]) for row in db["criteria"]}
                         - set(state_vocabulary(column)))
        check(f"{tag}: состояний вне словаря колонки `{column}` — ноль", not outside,
              _brief(outside))
    unknown_tags = parsed.get("unknown_properties") or {}
    check(f"{tag}: неизвестных тегов `<Properties>` вида — ноль (замер 2.x: 11 известных)",
          not unknown_tags, _brief(dict(unknown_tags)))
    unknown_values = parsed.get("unknown_value_properties") or {}
    check(f"{tag}: агрегата неизвестных значений свойств вида — ноль (значения свойств детей "
          "называются отдельно, строкой ребёнка)", not unknown_values, _brief(unknown_values))
    offender_bad = []
    for row in db["criteria"]:
        offenders = list(row.get(UNKNOWN_NAMES_COLUMN) or [])
        state = str(row["properties_state"])
        if state == PROPS_ALL_KNOWN and offenders:
            offender_bad.append(f"{row['object_name']}: виновники при `{PROPS_ALL_KNOWN}`: "
                                f"{names(offenders)}")
        if state != PROPS_ALL_KNOWN and not offenders:
            offender_bad.append(f"{row['object_name']}: состояние {state} без виновника")
    check(f"{tag}: каждая строка вида называет виновника своего состояния свойств "
          f"(или `{PROPS_ALL_KNOWN}` — без перечня)", not offender_bad,
          "; ".join(offender_bad[:MAX_NAMES]))
    commands = Counter(str(row["properties_state"]) for row in db["commands"])
    check(f"{tag}: строк команды с состоянием `{PROPS_UNKNOWN_VALUE}` — "
          f"{expect['command_unknown_value']} (значения свойств детей узлом не удерживаются — "
          "Q7 узла V50)",
          commands.get(PROPS_UNKNOWN_VALUE, 0) == expect["command_unknown_value"],
          f"факт: {_brief(dict(commands))}")
    # Виновником состояния ребёнка является имя свойства из его файла — его называют строки
    # разбора (`unknown_property_names` команды) и строки базы тем же списком; агрегат вида к
    # детям не относится (прецедент пробы П3: сбор по `result["commands"]`).
    parse_culprits = sorted({str(name) for row in (parsed.get("commands") or [])
                             for name in (row.get(UNKNOWN_NAMES_COLUMN) or [])})
    db_culprits = sorted({str(name) for row in db["commands"]
                          for name in (row.get(UNKNOWN_NAMES_COLUMN) or [])})
    check(f"{tag}: виновников неизвестного значения названо — "
          f"{names(expect['command_culprits'])} (разбор и база — одним списком)",
          parse_culprits == sorted(expect["command_culprits"]) and db_culprits == parse_culprits,
          f"разбор: {names(parse_culprits)}, база: {names(db_culprits)}")


# ═══ контур 11: витрины, ревизии, сироты, коллизия имён ═══════════════════════════════
def check_views(cur, headers):
    """Витрина текущего состояния отдаёт ровно CURRENT-ревизии строк круга вида.

    Предикаты различаются по таблицам осознанно: у `forms`/`commands` нога области видимости
    — `configuration_uuid` ПЛЮС родители вида (иначе в выборку попали бы дети всех объектов
    конфигурации), у `form_ext` ноги конфигурации нет вовсе (наблюдение П6 узла V51), поэтому
    она читается связкой по строке формы. Сравнение таблицы с витриной идёт одним и тем же
    предикатом с двух сторон — иначе сравнивались бы разные выборки.
    """
    section("Контур 11 — витрины, ревизии, сироты, коллизия имён")
    uuids = [str(header["uuid"]) for header in headers]
    if not uuids:
        skip("витрины круга", "строк заголовков конфигураций в базе нет")
        return
    parents = (f"(SELECT object_uuid FROM {CURRENT_VIEWS[TABLE_NAME]} "
               "WHERE configuration_uuid = ANY(%s::uuid[]))")
    own_scope = "WHERE configuration_uuid = ANY(%s::uuid[])"
    child_scope = ("WHERE configuration_uuid = ANY(%s::uuid[]) AND parent_type = "
                   f"'configuration_objects' AND parent_uuid IN {parents}")
    for table, view, predicate, params in (
            (TABLE_NAME, CURRENT_VIEWS[TABLE_NAME], own_scope, [uuids]),
            (CONTENT_TABLE_NAME, CURRENT_VIEWS[CONTENT_TABLE_NAME], own_scope, [uuids]),
            ("forms", CURRENT_VIEWS["forms"], child_scope, [uuids, uuids]),
            ("commands", CURRENT_VIEWS["commands"], child_scope, [uuids, uuids])):
        base = int(one(cur, f"SELECT count(*) AS c FROM {table} {predicate}",
                       params).get("c") or 0)
        current = int(one(cur, f"SELECT count(*) AS c FROM {view} {predicate}",
                          params).get("c") or 0)
        check(f"витрина {view} отдаёт строки круга в том же числе, что {table}",
              base == current, f"таблица {base}, витрина {current}")
    join = (f"JOIN {CURRENT_VIEWS['forms']} fo ON fo.id = x.form_id "
            f"WHERE fo.configuration_uuid = ANY(%s::uuid[]) AND fo.parent_type = "
            f"'configuration_objects' AND fo.parent_uuid IN {parents}")
    base = int(one(cur, f"SELECT count(*) AS c FROM form_ext x {join}",
                   [uuids, uuids]).get("c") or 0)
    current = int(one(cur, f"SELECT count(*) AS c FROM {CURRENT_VIEWS['form_ext']} x {join}",
                      [uuids, uuids]).get("c") or 0)
    check(f"витрина {CURRENT_VIEWS['form_ext']} отдаёт содержимое форм вида в том же числе, "
          "что таблица `form_ext` (связка по строке формы)", base == current,
          f"таблица {base}, витрина {current}")


def check_revisions(cur, headers):
    """У загруженного круга ревизия первая и единственная; исторических строк нет.

    Отдельный вход группы (перезагрузка только позиции 2.7) — тот же узел V19, и прогон П8
    обязан это пережить: после второй загрузки строки сняты, а не удвоены.

    Строка перечня своей цепи ревизий не имеет (Q2, вариант A), поэтому колонок цепи у
    `filter_criterion_content` в схеме нет — запрос к ней падал с `UndefinedColumn` (прогон
    01.11.2026). Это не слепой пропуск таблицы: отсутствие цепи называется исключением
    `CONFIGURATION_UNVERSIONED_TABLES` и сверяется с живой схемой, а не подразумевается.
    """
    uuids = [str(header["uuid"]) for header in headers]
    for table in (TABLE_NAME, CONTENT_TABLE_NAME):
        if table in CONFIGURATION_UNVERSIONED_TABLES:
            columns = set(table_columns(cur, table))
            chain = sorted(columns & set(REVISION_CHAIN_COLUMNS))
            check(f"{table}: цепи ревизий нет — таблица названа исключением "
                  f"`CONFIGURATION_UNVERSIONED_TABLES` (Q2, вариант A), и колонок цепи у неё "
                  f"в живой схеме нет", not chain, f"колонки цепи: {_brief(chain)}")
            continue
        bad = int(one(cur, f"SELECT count(*) AS c FROM {table} "
                            "WHERE configuration_uuid = ANY(%s::uuid[]) "
                            "AND (revision_no <> 1 OR is_committed IS NOT TRUE)",
                       [uuids]).get("c") or 0)
        check(f"{table}: каждая строка круга — первая и единственная ревизия (V19)",
              bad == 0, f"строк с другой ревизией: {bad}")


def check_orphans(cur):
    """Сирот перечня и детей — ноль: каждая строка висит на строке вида.

    Основанием «строка обязана быть» служит индекс состава вида: строка ребёнка или перечня,
    чей родитель назван индексом (`FilterCriterion.*`), обязан иметь и строку вида. Иначе
    снятие круга по ноге области видимости оставила бы детей сиротами — тот же дефект, который
    узлы V44…V51 закрывают явным `DELETE`.
    """
    parents = ("SELECT uuid FROM configuration_objects "
               "WHERE object_type = %s AND (child_type IS NULL OR child_type = '')")
    for table, column in (("forms", "parent_uuid"), ("commands", "parent_uuid"),
                          (CONTENT_TABLE_NAME, "criterion_object_uuid")):
        orphans = int(one(cur, f"SELECT count(*) AS c FROM {table} "
                               f"WHERE {column} IN ({parents}) "
                               f"AND {column} NOT IN (SELECT object_uuid FROM {TABLE_NAME})",
                           [INDEX_OBJECT_TYPE]).get("c") or 0)
        check(f"{table}: строк детей или перечня без строки вида нет", orphans == 0,
              f"сирот: {orphans}")
    broken_forms = int(one(cur, "SELECT count(*) AS c FROM form_ext x "
                                 "LEFT JOIN forms fo ON fo.id = x.form_id "
                                 "WHERE x.parent_type = 'configuration_objects' "
                                 "AND fo.id IS NULL").get("c") or 0)
    check("form_ext: строк без строки формы нет (каскад `form_ext_form_id_fkey`)",
          broken_forms == 0, f"сирот: {broken_forms}")


def check_name_collision(cur):
    """Коллизия имени вида не сливает строки разных конфигураций (замер 1.3).

    `СвязанныеДокументы` есть у MinCfg и KomMag, и записи индекса обеих выгрузок дают один и
    тот же uuid. Область видимости строки — пара «конфигурация + имя» (узел V19), поэтому
    каждая конфигурация обязана держать СВОЮ строку: одна строка на два имени означала бы, что
    загрузка второй конфигурации сняла строку первой.
    """
    rows = q(cur, f"SELECT object_name, count(*) AS rows_total, "
                  f"count(DISTINCT configuration_uuid) AS configs "
                  f"FROM {CURRENT_VIEWS[TABLE_NAME]} GROUP BY object_name "
                  "HAVING count(DISTINCT configuration_uuid) > 1 ORDER BY object_name")
    merged = [f"{row['object_name']}: строк {row['rows_total']} на {row['configs']} "
              "конфигураций" for row in rows if int(row["rows_total"]) != int(row["configs"])]
    check(f"{TABLE_NAME}: имя вида под несколькими конфигурациями даёт по строке на "
          "конфигурацию (коллизия не сливается)", not merged, "; ".join(merged))
    if rows:
        info("коллизия имени названа и сохранена раздельно: "
             + names([str(row["object_name"]) for row in rows]))

# ═══ контур 13: ссылки других слоёв на вид — свойство, а не число (позиция O1) ═════════
# Позиция O1 плана (Q9, вариант A) закрыта замером `_v52_o1_link_semantics.py` (02.11.2026):
# ссылки перечней подсистем (узел V46) и прав ролей (узел V49) на вид разрешаются индексом
# состава той же конфигурации и связываются со строкой вида по паре (`configuration_uuid`,
# `object_uuid`), но самой связи нет ни в выгрузке, ни в схеме. Числа замера (14 и 17 ссылок
# на четырёх выгрузках) в ожидания контура НЕ переносятся: правило
# `rules:core-rules:functional:answer-and-evidence`, пункт 3 — числа в правилах датированы и
# друг друга не подменяют; живое число, записанное ожиданием, перестало бы быть живым, а при
# расширении корпуса стало бы ложным провалом. Здесь сторожатся только инварианты.
CROSS_LAYER_LINKS_CTE = f"""
WITH links AS (
    SELECT 'subsystem_content' AS source, sc.configuration_uuid,
           sc.target_object_uuid AS target_uuid,
           CASE WHEN sc.resolved THEN 'resolved=true' ELSE 'resolved=false' END AS link_state
    FROM subsystem_content sc
    WHERE sc.target_object_type = '{INDEX_OBJECT_TYPE}'
    UNION ALL
    SELECT 'role_rights', rr.configuration_uuid, rr.target_object_uuid,
           'target_resolve_state=' || rr.target_resolve_state
    FROM role_rights rr
    WHERE rr.target_kind = '{INDEX_OBJECT_TYPE}'
)"""
# Состояния, которые утверждают «разрешено»: `resolved` ноги подсистем (V46) и `exact` ноги
# прав (V49). Словари разные, потому что таблицы пишут разные узлы; объединяет их то, что оба
# означают разрешение по индексу состава, а не наличие строки вида.
LINK_RESOLVED_STATES = ("resolved=true", "target_resolve_state=exact")
CROSS_LAYER_LINK_TABLES = ("subsystem_content", "role_rights")


def check_link_state_independence(cur):
    """Состояние ссылки не зависит от наличия строки вида: снятие круга в SAVEPOINT и откат.

    Единственный способ наблюдать выводность связки в живой базе — снять строки вида и
    посмотреть, изменятся ли состояния ссылок. Не изменятся (позиция O1 закрыта этим фактом),
    но связка пропадёт: «разрешено, а строки вида нет» становится ненулевым. Запись делается
    внутри SAVEPOINT и откатывается, поэтому прогон остаётся читающим и `check_untouched` не
    видит изменений ни в круге вида, ни в чужих кругах.
    """
    target = one(cur, f"""
        SELECT c.uuid, c.name,
               (SELECT count(*) FROM {CURRENT_VIEWS[TABLE_NAME]} fc
                 WHERE fc.configuration_uuid = c.uuid) AS view_rows
        FROM configurations c
        WHERE EXISTS (SELECT 1 FROM {CURRENT_VIEWS[TABLE_NAME]} fc
                       WHERE fc.configuration_uuid = c.uuid)
          AND (EXISTS (SELECT 1 FROM subsystem_content sc
                        WHERE sc.target_object_type = '{INDEX_OBJECT_TYPE}'
                          AND sc.configuration_uuid = c.uuid)
               OR EXISTS (SELECT 1 FROM role_rights rr
                           WHERE rr.target_kind = '{INDEX_OBJECT_TYPE}'
                             AND rr.configuration_uuid = c.uuid))
        ORDER BY c.name LIMIT 1""")
    if not target:
        skip("состояние ссылки против наличия строки вида",
             "нет конфигурации, где есть и строки вида, и ссылки на него: круг вида или круг "
             "ссылок в этой базе не загружен — это состояние базы, а не пропуск проверки")
        return
    cfg_uuid = str(target["uuid"])
    info(f"эксперимент на конфигурации {target['name']}: строк вида {target['view_rows']}")

    def states():
        return sorted((str(row["source"]), int(row["links"]), int(row["resolved"]))
                      for row in q(cur, CROSS_LAYER_LINKS_CTE + f"""
            SELECT l.source, count(*) AS links,
                   count(*) FILTER (WHERE l.link_state IN {LINK_RESOLVED_STATES}) AS resolved
            FROM links l
            WHERE l.configuration_uuid = %s
            GROUP BY 1""", [cfg_uuid]))

    def without_row():
        return int(one(cur, CROSS_LAYER_LINKS_CTE + f"""
            SELECT count(*) AS c FROM links l
            LEFT JOIN {CURRENT_VIEWS[TABLE_NAME]} fc
                   ON fc.configuration_uuid = l.configuration_uuid
                  AND fc.object_uuid = l.target_uuid
            WHERE l.configuration_uuid = %s AND fc.object_uuid IS NULL""",
            [cfg_uuid]).get("c") or 0)

    def view_rows():
        return int(one(cur, f"SELECT count(*) AS c FROM {CURRENT_VIEWS[TABLE_NAME]} "
                            "WHERE configuration_uuid = %s", [cfg_uuid]).get("c") or 0)

    before = states()
    cur.execute("SAVEPOINT v52_cross_layer_probe")
    try:
        cur.execute(f"DELETE FROM {TABLE_NAME} WHERE configuration_uuid = %s", [cfg_uuid])
        during = states()
        lost = without_row()
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v52_cross_layer_probe")
    after, restored = states(), view_rows()
    check("эксперимент откатан точкой сохранения: круг вида восстановлен, прогон читающий",
          restored == int(target["view_rows"]) and before == after,
          f"строк вида было {target['view_rows']}, после отката {restored}")
    check("состояния ссылок после снятия строк вида НЕ изменились, а связка пропала: "
          "`resolved`/`exact` описывают разрешение индексом состава, а не наличие строки вида",
          before == during and lost > 0,
          f"состояний до {before}, в эксперименте {during}; без строки вида осталось {lost}")


def check_cross_layer_links(cur):
    """Ссылки кругов V46 и V49 на вид: разрешимость индексом и отсутствие висящих ссылок.

    Инвариант держит связку, а не её размер: ссылок может быть сколько угодно (KomMag даёт
    ноль при одной строке вида), но ни одна «разрешённая» ссылка не обязана оставаться без
    строки вида. Это то, что ломает регрессия — например снятие круга вида без снятия ссылок.
    """
    section("Контур 13 — ссылки других слоёв на вид (позиция O1)")
    missing = [table for table in CROSS_LAYER_LINK_TABLES
               if not one(cur, "SELECT count(*) AS c FROM information_schema.tables "
                               "WHERE table_name = %s", [table]).get("c")]
    if missing:
        skip("контур 13 целиком",
             f"таблиц чужих кругов в живой базе нет: {names(missing)} — круги узлов V46 и V49 "
             "в этой базе не загружались, сравнивать не с чем")
        return
    per_leg = q(cur, CROSS_LAYER_LINKS_CTE + """
        SELECT source, count(*) AS links,
               count(*) FILTER (WHERE target_uuid IS NOT NULL) AS with_uuid
        FROM links GROUP BY 1 ORDER BY 1""")
    total = sum(int(row["links"]) for row in per_leg)
    for row in per_leg:
        info(f"{row['source']}: ссылок на вид {row['links']}, uuid заполнен у {row['with_uuid']}")
    info("числа контура — живой замер и эталоном не являются; закрытие позиции и числа "
         "замера держат `_v52_o1_link_semantics.py` (02.11.2026) и раздел 6 Q9 плана")
    if total == 0:
        skip("сверки контура 13",
             "ссылок на вид в базе нет — это состояние выгрузки (у конфигурации без включений "
             "вида в подсистемы и без прав на вид их действительно нет), а не потеря строк")
        return
    broken_index = int(one(cur, CROSS_LAYER_LINKS_CTE + """
        SELECT count(*) AS c FROM links l
        JOIN configurations c ON c.uuid = l.configuration_uuid
        LEFT JOIN configuration_objects co
               ON co.configuration_id = c.id AND co.uuid = l.target_uuid
        WHERE l.target_uuid IS NOT NULL AND co.uuid IS NULL""").get("c") or 0)
    check("ссылка на вид с uuid имеет запись индекса состава той же конфигурации "
          "(иначе состояние `resolved`/`exact` врёт)", broken_index == 0,
          f"без записи индекса: {broken_index}")
    dangling = int(one(cur, CROSS_LAYER_LINKS_CTE + f"""
        SELECT count(*) AS c FROM links l
        LEFT JOIN {CURRENT_VIEWS[TABLE_NAME]} fc
               ON fc.configuration_uuid = l.configuration_uuid
              AND fc.object_uuid = l.target_uuid
        WHERE l.link_state IN {LINK_RESOLVED_STATES} AND fc.object_uuid IS NULL""").get("c") or 0)
    check("висящих ссылок на вид нет: каждая разрешённая цель имеет строку вида текущего "
          "состояния по паре configuration_uuid + object_uuid", dangling == 0,
          f"висящих: {dangling}")
    check_link_state_independence(cur)


# ═══ контур 10: пустой круг — ответ о выгрузке, а не отказ стадии (Q9) ════════════════
def check_empty_circle():
    """Каталога `FilterCriteria/` нет — разбор отвечает успешно и называет это наблюдением.

    На четырёх эталонных выгрузках каталог вида есть у всех (замер 1.1), поэтому состояние
    пустого круга проверяется на фикстуре — пустом каталоге выгрузки. Нули `files_found` и
    пустые списки без наблюдения читались бы как «круг пуст, всё хорошо» там, где выгрузку
    просто не нашли; отказом это состояние называть нельзя — стадия не обязана требовать
    наличия каждой позиции нормативного списка.
    """
    section("Контур 10 — пустой круг (каталога вида нет)")
    with tempfile.TemporaryDirectory(prefix="v52_empty_circle_") as fixture:
        parsed, failure = parse_circle(fixture)
    if failure:
        check("фикстура без каталога вида разбирается без отказа (Q9)", False, failure)
        return
    check("фикстура без каталога вида: `success` — истина, отказа нет",
          parsed.get("success") is True, _brief(parsed.get("files_failed")))
    check(f"наблюдение `{OBSERVATION_DIRECTORY_MISSING}` названо, файлов круга — ноль",
          any(kind == OBSERVATION_DIRECTORY_MISSING for kind, _detail in parsed["observations"])
          and parsed["files_found"] == 0 and parsed["files_read"] == 0,
          f"наблюдения: {names([kind for kind, _ in parsed['observations']])}")
    check("пустой круг назван пустым списком строк, а не отсутствием ключей ответа",
          parsed["rows"] == [] and parsed["content"] == [] and parsed["forms"] == []
          and parsed["commands"] == [],
          f"строк: rows={len(parsed['rows'])}, content={len(parsed['content'])}")


# ═══ контур 12: контракт стадии и реестр инструментов ══════════════════════════════════
def registry_expected_tools():
    """Реестр `EXPECTED_TOOLS` — снятый синтаксически, без импорта модуля-валидатора.

    Импорт `tools/check_mcp_tool_wiring.py` выполнил бы его прогон ради одного словаря, а
    `ast.literal_eval` берёт значение как есть: реестр — закрытый список, а не вычисление.
    """
    source = (ROOT / "tools" / "check_mcp_tool_wiring.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if getattr(target, "id", "") == "EXPECTED_TOOLS":
                return ast.literal_eval(node.value)
    return {}


def registry_deleted_tools():
    """Имена снятых инструментов из `DELETED_TOOLS` — тем же снятием синтаксиса, что и реестр.

    Подстрока по тексту после `DELETED_TOOLS = [` не годится: в комментариях этого блока
    названа единая точка входа `load_1c_catalog_tool` (чем заменён снятый вход), и проверка
    считала бы её снятой. Список снимается значением, а не текстом.
    """
    source = (ROOT / "tools" / "check_mcp_tool_wiring.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if getattr(target, "id", "") == "DELETED_TOOLS":
                return list(ast.literal_eval(node.value))
    return []


def check_contract():
    """Стадия, круг снятия, подсказка продолжения и вход группы — на местах.

    Порядок стадий — порядок нормативного списка (2.7 сразу за 2.6, модули объектов остаются
    второй транзакцией), незакрытый круг снятия означал бы, что перезагрузка позиции 2.7
    оставила бы прежние строки, а подсказка продолжения — то, чем оператор повторяет стадию.
    """
    section("Контур 12 — контракт стадии и реестр инструментов")
    order = [stage for stage, _title in STAGES]
    check(f"`{STAGE_FILTER_CRITERIA}` стоит сразу за `{STAGE_EXCHANGE_PLANS}` и перед "
          f"`{STAGE_EVENT_SUBSCRIPTIONS}` (порядок позиций 2.6 → 2.7 → 2.8, узлы V52 и V53; "
          "`модули Ext/` — вторая транзакция, она идёт последней среди стадий детей)",
          order.index(STAGE_FILTER_CRITERIA) == order.index(STAGE_EXCHANGE_PLANS) + 1
          and order.index(STAGE_EVENT_SUBSCRIPTIONS)
          == order.index(STAGE_FILTER_CRITERIA) + 1
          and order.index(STAGE_OBJECT_MODULES) == len(order) - 1,
          f"порядок стадий: {names(order)}")
    outside = [table for table in FILTER_CRITERIA_TABLES
               if table not in FOREIGN_STAGE_TABLES]
    check(f"круг снятия стадии назван закрытым: {names(list(FILTER_CRITERIA_TABLES))} входят в "
          f"`FOREIGN_STAGE_TABLES`", not outside, f"вне круга: {names(outside)}")
    # ── форма нулевого ответа: перечень чисел совпадает с перечнем ответа прогона ─────────
    # Позиция, названная прогоном П8 (02.11.2026): нулевой словарь контракта засеивал словари
    # пар `removed_by_table`/`written_by_table` двумя таблицами вида, тогда как ответ загрузчика
    # заполняет их пятью. Состоянием это не было (неперечисленные ключи читаются нулями — C1),
    # но форма payload'а пропущенной стадии отличалась от формы успешного ответа. Разведение
    # держится двумя разными перечнями: `tables` — круг версионности (две таблицы вида),
    # словари пар — круг снятия (пять), потому что детей снимает и пишет эта же стадия.
    zero = filter_criteria_defaults()
    seeded_written = list(zero.get("written_by_table") or {})
    seeded_removed = list(zero.get("removed_by_table") or {})
    check("нулевой ответ называет те же таблицы и в том же порядке, что и ответ прогона: "
          "словари пар засеяны кругом снятия, а не кругом версионности",
          seeded_written == list(FILTER_CRITERIA_REMOVE_ORDER)
          and seeded_removed == list(FILTER_CRITERIA_REMOVE_ORDER)
          and list(FILTER_CRITERIA_REMOVE_ORDER) == list(LAYER_REMOVE_ORDER),
          f"written: {names(seeded_written)}; removed: {names(seeded_removed)}; "
          f"слой: {names(list(LAYER_REMOVE_ORDER))}")
    check("ключ `tables` остаётся кругом версионности — двумя таблицами вида (что версионируется "
          "и по каким таблицам ответ даёт числа — разные утверждения)",
          list(zero.get("tables") or []) == list(FILTER_CRITERIA_TABLES),
          names(list(zero.get("tables") or [])))
    check("литералы круга снятия в контракте совпадают с константами таблиц слоя "
          "(разойдутся — проверка назовёт имена, а не молча сравнит два разных круга)",
          tuple(FILTER_CRITERIA_REMOVE_ORDER) == (
              LAYER_FORM_EXT_TABLE, LAYER_FORMS_TABLE, LAYER_COMMANDS_TABLE,
              CONTENT_TABLE_NAME, TABLE_NAME),
          names(list(FILTER_CRITERIA_REMOVE_ORDER)))
    wider = sorted(set(FILTER_CRITERIA_REMOVE_ORDER) - set(FILTER_CRITERIA_TABLES))
    check("разность круга снятия и круга версионности — ровно общие таблицы детей "
          "(`form_ext`, `forms`, `commands`), других таблиц в круге стадии нет",
          wider == sorted(SHARED_CHILD_TABLES), names(wider))
    hint = stage_resume_hint(STAGE_FILTER_CRITERIA)
    check("подсказка продолжения стадии названа и совпадает с контрактом",
          hint == FILTER_CRITERIA_REPEAT_HINT and bool(str(hint).strip()), _brief(hint))
    check(f"у стадии `{STAGE_FILTER_CRITERIA}` отдельного входа дозагрузки БОЛЬШЕ НЕТ: продолжение только "
          "полной перезагрузкой единой точки входа (узел TOOL-DROP, 05.11.2026) — "
          "зеркало STAGE_FULL_RELOAD_ONLY обязано называть это состоянием",
          STAGE_FULL_RELOAD_ONLY.get(STAGE_FILTER_CRITERIA) is True,
          str(STAGE_FULL_RELOAD_ONLY.get(STAGE_FILTER_CRITERIA)))
    registry = registry_expected_tools()
    core_tools = registry.get("server_configurations_core.py", [])
    # Узел TOOL-DROP (05.11.2026) снял позиционные входы дозагрузки: их имён в реестре быть не
    # может, а снятыми их называет `DELETED_TOOLS` того же файла. Числовой эталон состава здесь
    # больше не держится второй копией — состав сторожит `tools/check_mcp_tool_wiring.py`.
    wiring_deleted = set(registry_deleted_tools())
    check("вход группы `load_filter_criteria_tool` БОЛЬШЕ НЕ входит в реестр "
          "`EXPECTED_TOOLS` ядра (снят узлом TOOL-DROP, 05.11.2026) и назван снятым в "
          "`DELETED_TOOLS` того же файла",
          "load_filter_criteria_tool" not in core_tools
          and "load_filter_criteria_tool" in wiring_deleted,
          _brief(sorted(core_tools)))
    check("среди инструментов ядра нет позиционных входов дозагрузки, а единая точка входа "
          "`load_1c_catalog_tool` на месте — повтор позиции делается полной перезагрузкой "
          "(узел TOOL-DROP)",
          bool(core_tools) and "load_1c_catalog_tool" in core_tools
          and not [name for name in core_tools if name in wiring_deleted],
          f"в реестре {len(core_tools)}: {names(core_tools)}")


# ═══ контур 11 (продолжение): неприкосновенность чужих кругов ═════════════════════════
def foreign_state(cur):
    """Число строк чужих кругов и круга вида — до и после прогона одной строкой на таблицу.

    Таблицы других узлов могут отсутствовать в живой базе (выгрузка ещё не загружалась), и это
    называется состоянием `None`, а не нулём: сравнение нуля с отсутствующей таблицей дало бы
    ложное «ничего не изменилось».
    """
    state = {}
    for table in (list(FOREIGN_TABLES) + [TABLE_NAME, CONTENT_TABLE_NAME]
                  + list(SHARED_CHILD_TABLES)):
        try:
            state[table] = int(one(cur, f"SELECT count(*) AS c FROM {table}").get("c") or 0)
        except Exception:  # noqa: BLE001 — таблицы других узлов могут отсутствовать в базе
            state[table] = None
    return state


def check_untouched(before, after):
    own = {TABLE_NAME, CONTENT_TABLE_NAME} | set(SHARED_CHILD_TABLES)
    changed = [table for table, value in before.items()
               if table not in own and after.get(table) != value]
    check("прогон ничего не изменил в чужих кругах", not changed,
          "изменились строки таблиц: " + names(changed))


def add_totals(totals, circle):
    """Счётчики одной выгрузки — в итог по корпусу.

    Меры файлов берутся из той же меры, что и построчные сравнения (иначе итог корпуса
    описывал бы другой круг), строки — из витрин текущего состояния, а не из базовых таблиц:
    история ревизий удвоила бы итог.
    """
    parsed, db, index = circle["parsed"], circle["db"], circle["index"]
    for key, value in (circle.get("raw") or Counter()).items():
        if str(key).startswith("raw_"):
            totals[key] += value
    totals["idx_roots"] += len(index["roots"])
    totals["idx_children"] += len(index["children"])
    totals["pseudo"] += len(index["pseudo"])
    totals["declared_children"] += sum(
        len([title for title in declared_children(circle["dump_dir"], name).get(kind, []) if title])
        for name in circle["per_name"] for kind in (CHILD_FORM, CHILD_COMMAND))
    totals["rows_criteria"] += len(db["criteria"])
    totals["rows_content"] += len(db["content"])
    totals["rows_forms"] += len(db["forms"])
    totals["rows_form_ext"] += len(db["form_ext"])
    totals["rows_commands"] += len(db["commands"])
    totals["parse_module_files"] += int(parsed.get("module_files_total") or 0)


def check_aggregate(totals, run_tags, skipped_tags):
    """Итог по четырём выгрузкам сверяется с суммой плана только когда прогнаны все четыре.

    Сравнение итога по меньшему числу выгрузок с суммой по четырём — ложное расхождение
    (прецедент V50/V51), поэтому пропущенные выгрузки называются причиной, а не молчат.
    """
    section("Итог по корпусу")
    if set(run_tags) != set(PLAN_EXPECTATIONS):
        skip("итоги по корпусу",
             f"прогнаны не все выгрузки: {names(run_tags)}; пропущены: {names(skipped_tags)}. "
             "Итог по четырём выгрузкам сравнивать с суммой по меньшему числу — ложное "
             "расхождение")
        return
    counts_diff(totals, CORPUS_TOTALS, "итог по корпусу", "корпус")


# ═══ прогон ═══════════════════════════════════════════════════════════════════════════
def run(cur, scope):
    """Порядок прогона: схема один раз, потом круг каждой выгрузки, потом итог узла.

    Живая схема проверяется одна на прогон: она не зависит от выгрузки, и повторять её по
    числу конфигураций — значит множить один и тот же вопрос. Пропуск выгрузки называется
    причиной (нет каталога, нет строки плана, нет строк узла в базе, не загружен индекс
    состава): пустой ответ не читается как «расхождений нет».
    """
    headers = q(cur, "SELECT id, uuid::text AS uuid, name FROM configurations "
                     "ORDER BY id")
    if not headers:
        print("FAIL строк заголовков конфигураций в базе нет — сравнивать не с чем")
        FAILED.append("нет строк заголовков")
        return
    before = foreign_state(cur)
    check_schema(cur)
    check_state_vocabulary(cur)
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
        circle = check_circle(cur, header, dump_dir, expect, tag)
        if circle is None:
            skipped_tags.append(tag)
            continue
        if not circle["db"]["criteria"]:
            skipped_tags.append(tag)
            skip(f"{tag}: контуры «файл ↔ строка», детей, перечня, целей и блока типа",
                 "строк вида в таблице нет — конфигурацию не перезагружали после узла V52 "
                 f"(стадия `{STAGE_FILTER_CRITERIA}` входит в загрузку каталога, отдельный "
                 "вход группы — `load_filter_criteria_tool`)")
            continue
        check_children_circle(circle, expect, tag)
        check_row_values(cur, circle, expect, tag)
        check_content_rows(cur, circle, expect, tag)
        check_target_resolution(circle, expect, tag)
        check_type_block(circle, expect, tag)
        check_form_references(circle, expect, tag)
        check_row_states(circle, expect, tag)
        add_totals(totals, circle)
        run_tags.append(tag)

    check_cross_layer_links(cur)
    after = foreign_state(cur)
    section("Итог узла V52")
    check_empty_circle()
    check_contract()
    check_views(cur, headers)
    check_revisions(cur, headers)
    check_orphans(cur)
    check_name_collision(cur)
    check_untouched(before, after)
    check_aggregate(totals, run_tags, skipped_tags)


def main(argv):
    scope = str(argv[1]) if len(argv) > 1 else DEFAULT_SCOPE
    try:
        with transaction() as cur:
            run(cur, scope)
    except Exception as exc:  # noqa: BLE001 — отказ прогона обязан быть назван, а не оборвать вывод
        FAILED.append(f"прогон прерван исключением: {exc}")
        print(f"FAIL прогон прерван исключением: {type(exc).__name__}: {exc}")
        # Стек печатается: без него отказ прогона — строка вида «tuple index out of range»,
        # по которой не видно, какой из контуров её дал (прецедент check_v31_provenance).
        traceback.print_exc()
    print("\n" + "=" * 72)
    print(f"ИТОГ: пройдено {len(PASSED)}, провалено {len(FAILED)}, "
          f"пропущено {len(SKIPPED)}, заметок {len(INFO)}")
    for name in FAILED:
        print("  ПРОВАЛ: " + name)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))











