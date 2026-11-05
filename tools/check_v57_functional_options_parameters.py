#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/check_v57_functional_options_parameters.py — узел V57: параметры функциональных
опций (позиция 2.12 нормативного списка), шаг П6 — постоянная проверка узла.

Это постоянная проверка, а не проба шага (правило 3 карточки
`rules:core-rules:functional:per-block-table-view-checks`): она обязана переживать и
перезагрузку выгрузок, и правки кода загрузки. Источник ожиданий —
`docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PARAMETERS_PLAN.md` (раздел 1 — круг четырьмя ногами и
его цена, раздел 2 — словарь четырёх тегов, форма элемента `<xr:Item xsi:type="xr:MDObjectRef">`
и две формы адреса цели, раздел 5 — M1…M8, раздел 7 — шаги, раздел 9 — критерии готовности).
Числа перенесены из замеров `_v57_p0_probe.py` (вывод `_scratch/v57_p0_out.txt`) без правок:
сглаживать число проверкой — значит подтверждать неверное число (прецедент узлов V49…V56).
Единственное исправленное число называется отдельной проверкой и правкой плана: план раздела 1.2
писал «16 / 229 / 546» для маски по началу имени, прогон по живой БД даёт 4 / 229 / 546
(MinCfg 2+2, BGU2 224+5, BP3 539+7 — сумма записей двух соседних видов), и разница с точным
предикатом равна ровно записям позиции 2.11 (2 / 224 / 539).

Что сторожится — по контурам:

  1. ГРАНИЦА СХЕМЫ (контур 1). Две таблицы узла (`functional_option_parameters` — свойства
     вида, `functional_option_parameter_targets` — строки перечня `<Use>`), числа колонок
     (17 и 17 — эталон П1), колонки цепи ревизий только у таблицы вида, ключ области видимости
     `(configuration_uuid, object_name, revision_no)` (M1: 5 uuid и 5 имён вида совпадают у
     BGU2 и BP3), ключ применения `(functional_option_parameter_id, ordinal)`, внешний ключ
     применения с `ON DELETE CASCADE` и отсутствие внешнего ключа у таблицы вида (прецедент
     V20.1), индексы круга (именованный состав, а не «какой-нибудь индекс»), витрины, запись
     таблицы вида в реестр версионируемых и исключение таблицы применения из версионности.
  2. СЛОВАРИ СОСТОЯНИЙ ↔ CHECK (контур 2). Каждый словарь модуля разбора сверяется с CHECK
     **конкретной таблицы** по имени колонки (`STATE_VOCABULARY_TABLES`), а не «где-нибудь в
     схеме». Отличие от V56 названо проверкой: для `target_resolve_state` отдельного
     ограничения `..._resolve_state_known` в DDL нет осознанно — замкнутость держит
     `functional_option_parameter_targets_resolve_matches_ref`, где каждое состояние названо
     отдельной ветвью, поэтому словарь сравнивается с этим ограничением. Ограничения
     согласованности состояния со структурой строки обязаны существовать; CHECK на ЗНАЧЕНИЯ
     свойств вида отсутствуют осознанно (Q7, вариант A: XSD вида нет, круг 14 файлов меньше
     порога замыкания в 20 — незнакомое остаётся значением с состоянием). Отдельно сверяется
     связка `COUNT_KEYS` ↔ `COUNT_KEY_STATE_COLUMNS` ↔ колонок: вывод из имени потерял бы
     состояние, а нулевой контракт — словарь.
  3. ГРАНИЦА КРУГА (контур 3). Параметр адресуется ЧЕТЫРЬМЯ ногами: каталогом
     `FunctionalOptionsParameters/` (`<Имя>.xml`), индексом состава
     (`FunctionalOptionsParameter.<Имя>`), перечнем `configurations.functional_options_parameters`
     (стадия S2) и перечислением имён вида в корне `Configuration.xml`; строки таблицы —
     пятая сторона того же множества. Множества сравниваются попарно во все стороны. Две
     отдельные проверки: записей ЧУЖДОГО вида `FunctionalOption` (позиция 2.11, 2/224/539 на
     корпус — замер 1.2) в круг не вошла ни одна, и маска по началу имени (`4 / 229 / 546`)
     отличается от точного предиката (`2 / 5 / 7`) ровно на записи соседнего вида — граница
     держится значением `object_type`, а не префиксом. `NULL` перечня заголовка у KomMag
     отличён от пустого массива (M8, замер 1.1).
  4. СТРОКА ВИДА ↔ РАЗБОР (контур 4). Каждая колонка строки обязана совпадать с кругом,
     разобранным ТЕМ ЖЕ модулем (`collect_functional_options_parameters`), что и загрузка:
     иначе проверка проверяла бы себя, а не то, донёс ли писатель строку. Пустой `Comment`
     (12 файлов из 14 — замер 2 плана) различается с отсутствующим тегом состоянием, а не
     подстановкой.
  5. СТРОКИ ПРИМЕНЕНИЯ ↔ ФАЙЛ (контур 5). Множество `(параметр, ordinal, адрес цели, тег
     элемента, значение `xsi:type` и его состояние, форма адреса, вид цели, состояние
     разрешения, остаток пути)` строк базы равно перечню `<Use>` его файла; есть НЕЗАВИСИМЫЙ
     подсчёт элементов регулярным выражением по тексту файла, без знания о состояниях разбора;
     `targets_count` равен числу строк применения, а `use_state` выводится из счётчика (CHECK
     `functional_option_parameters_use_state_matches_targets`) — нарушение инварианта пары
     называется состоянием, а не потерянной строкой.
  6. РАЗРЕШИМОСТЬ ССЫЛОК (контур 6). Каждая цель разрешается ЗАНОВО по строкам индекса
     состава ЭТОЙ конфигурации (`resolve_reference`, поиск по всем видам — цели ведут на
     `InformationRegister` и `Catalog`): состояние, `object_id`, `object_uuid` и остаток пути
     обязаны совпасть с сохранёнными. На корпусе разрешение полное — 34 из 34 `exact`
     (замер 2.1), и нули `prefix_only`/`unresolved` являются проверяемым утверждением, а не
     предположением (Q3). Вид цели и ФОРМА адреса пересчитываются по адресу и сравниваются с
     эталоном 30 `dimension` / 4 `object` — тем, чем она разрешается (M5).
  7. ВИТРИНЫ, ЦЕПИ И СИРОТЫ (контур 7). Строк вне витрин текущего состояния — ноль; строки
     применения висят на ТЕКУЩЕЙ ревизии вида (Q2, вариант A); сирот применения — ноль;
     дублирующая строка применения (`configuration_uuid`, `parameter_object_uuid`,
     `parameter_full_name`) совпадает со строкой вида; витрина применения связывается с
     витриной вида, а не с версионируемой таблицей; чужих внешних ключей на таблицы узла —
     ноль.
  8. КОНТРАКТ И РЕЕСТРЫ (контур 8, 8.1). Стадия `s4l_functional_options_parameters` стоит
     сразу после `s4k_functional_options` и перед `s4b_object_modules` (порядок нормативного
     списка 2.11 → 2.12, а не порядок литер); круг таблиц и порядок снятия (сначала
     применение — M7); обе таблицы названы в `FOREIGN_STAGE_TABLES`; вид внесён в
     `STORED_META_KINDS` (узел V57, позиция 2.12); нулевой контракт перечисляет все ключи
     сводки и все словари состояний нулями; форматтер называет «стадия не выполнена», отказ
     разбора и круг — три разных ответа (C1). Групп `kinds` у входа нет — это решение Q5
     (вариант A), и проверка называет его отсутствием блока дозагрузки, а не молчанием.
     Отдельный вход `load_functional_options_parameters_tool` зарегистрирован в реестре
     сервера и в `EXPECTED_TOOLS` — реестр читается текстом файла, а не памятью проверки.
  9. КОРПУС И ЧУЖИЕ КРУГИ (контур 9). Суммы по четырём выгрузкам равны замерам разделов 1.1
     и 2.1: 14 файлов, 14 записей индекса, 14 имён перечня заголовка и 14 имён корня, 14
     строк вида, 34 строки применения, 34 `exact`, 30 `dimension` / 4 `object`, классы цели
     `InformationRegister` 30 / `Catalog` 4, максимум 20 целей на вид, 0 пустых `<Use/>`,
     34 `xr:MDObjectRef`, 0 расхождений ног, 0 сирот, 0 строк вне витрин. У `KomMag` каталога
     вида нет ни файлом, ни записями индекса, а перечень заголовка — `NULL` (замер 1.1): ответ
     обязан быть пустым кругом с наблюдением `directory_missing`, а не отказом.

Неприкосновенность чужих кругов: прогон читающий, числа соседних витрин (V48…V56), включая
`v_current_functional_options` и `v_current_functional_option_content` (соседняя позиция 2.11),
и `bsl_modules` в нём не меняются.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python tools/check_v57_functional_options_parameters.py [MinCfg|KomMag|BGU2|BP3|all]
По умолчанию — `all`: все строки заголовков, для которых находится каталог выгрузки. Код
возврата 0 — расхождений нет. Пропуск контура называется причиной (нет строки заголовка, нет
выгрузки, строк узла не загружалось, индекс состава недоступен): ноль проверок не читается
как «всё хорошо».
"""

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

try:  # кириллица в консоли Windows (cp1251) — как в остальных валидаторах
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
from configuration_functional_options_parameters import (  # noqa: E402
    ADDRESS_FORMS, ADDRESS_FORM_ATTRIBUTE, ADDRESS_FORM_DIMENSION, ADDRESS_FORM_EMPTY,
    ADDRESS_FORM_OBJECT, ADDRESS_FORM_OTHER, ADDRESS_FORM_REGISTER_RESOURCE,
    ADDRESS_FORM_TABULAR_SECTION, CIRCLE_DISCREPANCIES, COUNT_KEYS, COUNT_KEY_STATE_COLUMNS,
    DECLARED_PROPERTIES, DIR_NAME, FUNCTIONAL_OPTIONS_PARAMETER_PROPERTIES,
    FUNCTIONAL_OPTIONS_PARAMETER_PROPERTY_COUNT, INDEX_NAME_SEPARATOR, INDEX_OBJECT_TYPE,
    ITEM_TYPE_REF_VALUE, ITEM_TYPE_STATE_ABSENT, ITEM_TYPE_STATE_OTHER, ITEM_TYPE_STATE_REF,
    ITEM_TYPE_STATES, MAX_TARGETS_KEY, OBJECT_KIND_TAG, OBSERVATION_KINDS, PARAMETER_LINK_KEY,
    PARAMETER_UUID_KEY, PROPERTIES_STATES, PROPS_ALL_KNOWN, PROPERTY_BY_COLUMN,
    SIBLING_INDEX_OBJECT_TYPE, STATE_VOCABULARIES, STATE_VOCABULARY_TABLES, SUMMARY_KEYS,
    TABLE_NAME, TARGETS_TABLE_NAME, TARGET_EMPTY_VALUE, TARGET_EXACT, TARGET_PREFIX_ONLY,
    TARGET_RESOLVE_STATES, TARGET_ROW_KEYS, TARGET_UNRESOLVED, USE_ELEMENT_TAG, USE_EMPTY,
    USE_ITEM_TAG, USE_STATE_COLUMNS, USE_STATES, USE_WITH, XML_PROPERTY_NAMES,
    collect_functional_options_parameters,
    index_row_key, index_rows_by_name, property_columns, property_kind, read_text_file,
    resolve_reference, state_columns, target_address_form, target_object_type,
)
from configuration_functional_options_parameters_loader import read_index_records  # noqa: E402
from configuration_load_contract import (  # noqa: E402
    FOREIGN_STAGE_TABLES, FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_BOUNDARY,
    FUNCTIONAL_OPTIONS_PARAMETERS_DIR, FUNCTIONAL_OPTIONS_PARAMETERS_META_TAG,
    FUNCTIONAL_OPTIONS_PARAMETERS_OBSERVATION_KINDS, FUNCTIONAL_OPTIONS_PARAMETERS_REPEAT_HINT,
    FUNCTIONAL_OPTIONS_PARAMETERS_SECTION_HEADER, FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE,
    FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER, FUNCTIONAL_OPTION_PARAMETERS_TABLE,
    FUNCTIONAL_OPTION_PARAMETERS_TABLES, STAGE_FUNCTIONAL_OPTIONS,
    STAGE_FUNCTIONAL_OPTIONS_PARAMETERS, STAGE_FULL_RELOAD_ONLY, STAGE_OBJECT_MODULES, STAGES,
    STORED_META_KINDS, functional_options_parameters_defaults,
    format_functional_options_parameters_lines, stage_resume_hint, stage_title, stages_after,
)
from configuration_module_slots import resolve_dump_dir  # noqa: E402
from current_revision import CONFIGURATION_VERSIONED_TABLES, current_view  # noqa: E402
from external_db import transaction  # noqa: E402
from external_table_writer import (  # noqa: E402
    CONFIGURATION_OBJECT_WRITERS, CONFIGURATION_UNVERSIONED_TABLES,
)

DUMP_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
DEFAULT_SCOPE = "all"
MAX_NAMES = 10          # сколько расхождений называется именами (дальше — только число)

PARAMETER_VIEW = current_view(TABLE_NAME)
# Таблица применения своей цепи ревизий не имеет (Q2, вариант A), поэтому `current_view()`
# для неё не вызывается — имя витрины называется прямо, как у `v_current_role_rights` (V49),
# `v_current_common_attribute_targets` (V50), `v_current_filter_criterion_content` (V52),
# `v_current_scheduled_job_schedules` (V54) и `v_current_functional_option_content` (V56):
# витрина связывается с витриной родителя.
TARGETS_VIEW = "v_current_functional_option_parameter_targets"
INDEX_TABLE = "configuration_objects"
HEADER_NAME_COLUMN = "functional_options_parameters"   # перечень заголовка (стадия S2, узел V43)
# Чужой круг соседнего узла V56 (функциональные опции, позиция 2.11). Имена названы списком,
# а не суженным LIKE: маска `functional_option%` захватывает и их, и граница круга узла должна
# читаться составом чужих таблиц, а не удачным совпадением префикса (прецедент — соседние
# круги V48…V56 в `FOREIGN_TABLES` ниже; граница круга узла держится точным `object_type`,
# отсечение по началу имени даёт 4/229/546 вместо 2/5/7 — замер 1.2 плана V57).
OPTION_CIRCLE_TABLES = ("functional_options", "functional_option_content")

# Колонки, которые принадлежат цепи ревизий (узел V19), а не узлу V57: их заполняет не
# разбор, и сравнивать их с ключом строки разбора — значит требовать от слоя чужого.
REVISION_COLUMNS = ("id", "configuration_uuid", "created_at", "revision_no", "changed_at",
                    "changed_by", "is_committed")
# Колонки строки применения, которые подставляет вызывающий слой (связь с ревизией вида),
# а не разбор: они сторожатся контурами 5 и 7 отдельно.
TARGET_WRITER_COLUMNS = (PARAMETER_LINK_KEY, PARAMETER_UUID_KEY, "configuration_uuid")
# Числовой id ревизии строки вида — колонка связи в SQL. ИМЕНЕМ СВЯЗИ РАЗБОРА
# (`PARAMETER_LINK_KEY` = `parameter_full_name`) она не является осознанно: строка применения
# обязана ссылаться на ревизию, а не на имя (прецедент V50/V52/V56).
PARAMETER_FK_COLUMN = "functional_option_parameter_id"
# Индексное имя вида — префикс, которым строка применения несёт короткое имя строки вида
# (иерархии раскладки у вида нет, замер 1.2 плана V57: `full_name` равен `object_name`).
INDEX_NAME_PREFIX = f"{INDEX_OBJECT_TYPE}{INDEX_NAME_SEPARATOR}"

# Ожидаемые числа колонок двух таблиц — эталон шага П1 (миграция
# `migrate_v57_functional_options_parameters.sql` + зеркало `create_1c_configurations_db.sql`).
EXPECTED_COLUMN_COUNTS = {TABLE_NAME: 17, TARGETS_TABLE_NAME: 17}

# Имена CHECK замкнутости состояний: связка «таблица, колонка → имя ограничения» держится
# словарём, а не выводом из имени (прецедент V52/V54/V56). Отличие от V56 названо здесь же:
# для `target_resolve_state` отдельного ограничения `..._resolve_state_known` в DDL узла нет —
# замкнутость словаря держит `..._resolve_matches_ref`, где каждое состояние является отдельной
# ветвью со своей структурой строки (раздел 5 плана V57, Q3 вариант A).
STATE_CHECK_NAMES = {
    (TABLE_NAME, "properties_state"): "functional_option_parameters_properties_state_known",
    (TABLE_NAME, "use_state"): "functional_option_parameters_use_state_known",
    (TARGETS_TABLE_NAME, "target_resolve_state"):
        "functional_option_parameter_targets_resolve_matches_ref",
    (TARGETS_TABLE_NAME, "target_address_form"):
        "functional_option_parameter_targets_address_form_known",
    (TARGETS_TABLE_NAME, "item_type_state"):
        "functional_option_parameter_targets_item_type_state_known",
}

# Ограничения DDL узла V57 (миграция + зеркало): отсутствие любого из них означает, что
# состояние описывало бы само себя, а не структуру строки, либо порядок перечня `<Use>`
# нечем было бы восстановить.
MATCH_CONSTRAINTS = (
    "functional_option_parameters_names_not_blank",
    "functional_option_parameters_properties_state_known",
    "functional_option_parameters_properties_state_matches_unknown",
    "functional_option_parameters_use_state_known",
    "functional_option_parameters_use_state_matches_targets",
    "functional_option_parameters_revision_no_positive",
    "functional_option_parameters_changed_by_known",
    "functional_option_parameters_changed_pair_check",
    "functional_option_parameters_configuration_object_revision_key",
    "functional_option_parameter_targets_names_not_blank",
    "functional_option_parameter_targets_name_matches_resolve_state",
    "functional_option_parameter_targets_resolve_matches_ref",
    "functional_option_parameter_targets_type_matches_name",
    "functional_option_parameter_targets_address_form_known",
    "functional_option_parameter_targets_form_matches_name",
    "functional_option_parameter_targets_item_type_state_known",
    "functional_option_parameter_targets_item_type_matches_attr",
    "functional_option_parameter_targets_ordinal_non_negative",
    "functional_option_parameter_targets_parameter_ordinal_key",
    "functional_option_parameter_targets_parameter_fkey",
)

# Индексы круга — именованный состав (раздел «Индексы узла V57» миграции): отдельного индекса
# по `configuration_uuid` у таблицы вида нет осознанно (его обслуживает уникальный индекс
# цепочки с ведущей колонкой `configuration_uuid`), отдельного индекса по форме адреса нет
# осознанно (форма выводится из адреса, а вопрос о разрезе объекта идёт по полному адресу).
EXPECTED_INDEXES = {
    TABLE_NAME: sorted([
        "functional_option_parameters_pkey",
        "functional_option_parameters_configuration_object_revision_key",
        "idx_functional_option_parameters_object_uuid_revision",
    ]),
    TARGETS_TABLE_NAME: sorted([
        "functional_option_parameter_targets_pkey",
        "functional_option_parameter_targets_parameter_ordinal_key",
        "idx_functional_option_parameter_targets_configuration_uuid",
        "idx_functional_option_parameter_targets_target_full_name",
        "idx_functional_option_parameter_targets_target_object_uuid",
        "idx_functional_option_parameter_targets_configuration_type",
    ]),
}
INDEX_LEAD_COLUMNS = {
    "idx_functional_option_parameters_object_uuid_revision": "(object_uuid, revision_no)",
    "idx_functional_option_parameter_targets_configuration_uuid": "configuration_uuid",
    "idx_functional_option_parameter_targets_target_full_name": "target_full_name",
    "idx_functional_option_parameter_targets_target_object_uuid": "target_object_uuid",
    "idx_functional_option_parameter_targets_configuration_type":
        "(configuration_uuid, target_object_type)",
}

# Поля строки вида, которые сверяются с разбором дословно (контур 4). `synonym` и
# `unknown_property_names` сравниваются отдельными проверками: jsonb и текстовый массив
# имеют свою форму пустого значения (NULL, а не пустая структура).
PARAMETER_COMPARE_FIELDS = (
    "object_uuid", "object_name", "full_name", "comment", "source_path", "use_state",
    "targets_count", "properties_state",
)
# Поля строки применения (контур 5): всё, что берётся из элемента `<Use>`. Дублирующие колонки
# слоя (`parameter_full_name`, `parameter_object_uuid`, `configuration_uuid`) сравниваются с
# родительской строкой в контуре 7, а не с разбором.
TARGET_COMPARE_FIELDS = (
    "ordinal", "item_tag", "item_type_attr", "item_type_state", "target_full_name",
    "target_object_type", "target_address_form", "target_object_id", "target_object_uuid",
    "target_unresolved_path", "target_resolve_state",
)

# ── ожидания проверки (числа плана docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PARAMETERS_PLAN.md) ──
# Ключ — каталог выгрузки, а не имя строки заголовка: имя заголовка меняется вместе с
# выгрузкой, а каталог — адрес, по которому проверка находит файлы (прецедент V50).
#   files / subdirs / non_xml / bytes — каталог `FunctionalOptionsParameters/` (плоский,
#     только XML, прочего содержимого ноль — замеры 1.1, 1.2, 1.4);
#   index_records — записей `FunctionalOptionsParameter.<Имя>` в индексе состава (замер 1.1);
#   sibling_index — записей ЧУЖДОГО вида `FunctionalOption` (позиция 2.11, замер 1.2): они
#     существуют в индексе и обязаны НЕ входить в круг;
#   prefix_mask — записей той же таблицы по МАСКЕ `object_type LIKE 'FunctionalOption%'`:
#     4 / 229 / 546 (MinCfg 2+2, BGU2 224+5, BP3 539+7). План раздела 1.2 писал про это
#     «16 / 229 / 546» — прогон по живой БД даёт 4, и правка плана сделана этим же шагом П6
#     (число проверкой не сглаживается);
#   root_names — имён вида в перечне корня `Configuration.xml` (четвёртая нога круга);
#   header_names / header_null — элементов перечня `configurations.functional_options_parameters`
#     и признака `NULL` (у KomMag вида нет ни файлами, ни записями — замер 1.1, M8);
#   db_rows / targets — строки витрин текущего состояния узла (замеры 1.1, 2.1);
#   distinct / max_targets — кратность целей внутри выгрузки и максимум на один перечень
#     (замер 2.1: от 1 до 20 целей на файл, параметр `Организация` в BP3);
#   target_exact / dimension / object — состояние разрешения цели и ФОРМА адреса (замер 2.1:
#     `exact` 34 из 34, `dimension` 30, `object` 4 — M5);
#   use_with / use_empty — состояния перечня `<Use>` (замер 2.1: пустых `<Use/>` ноль,
#     состояние `empty_content` остаётся границей разбора — M3);
#   item_ref / item_other_form / item_absent — форма элемента `<Use>` и значение `xsi:type`
#     (замер 2.1: `xr:MDObjectRef` 34 из 34 — M6);
#   empty_comment — пустых `Comment` по файлам (замер 2 плана: 12 из 14, BGU2 5 и BP3 7) и
#     их же число в колонке `comment` (NULL, а не пустая строка);
#   kinds — число классов цели перечня (замер 2.1: `InformationRegister`, `Catalog`).
PLAN_EXPECTATIONS = {
    "MinCfg": {"files": 2, "subdirs": 0, "non_xml": 0, "bytes": 3049, "index_records": 2,
               "sibling_index": 2, "prefix_mask": 4, "root_names": 2, "header_names": 2,
               "header_null": 0, "db_rows": 2, "targets": 2, "distinct": 2, "max_targets": 1,
               "target_exact": 2, "dimension": 1, "object": 1, "use_with": 2, "use_empty": 0,
               "item_ref": 2, "item_other_form": 0, "item_absent": 0, "empty_comment": 0,
               "kinds": 2},
    "KomMag": {"files": 0, "subdirs": 0, "non_xml": 0, "bytes": 0, "index_records": 0,
               "sibling_index": 0, "prefix_mask": 0, "root_names": 0, "header_names": 0,
               "header_null": 1, "db_rows": 0, "targets": 0, "distinct": 0, "max_targets": 0,
               "target_exact": 0, "dimension": 0, "object": 0, "use_with": 0, "use_empty": 0,
               "item_ref": 0, "item_other_form": 0, "item_absent": 0, "empty_comment": 0,
               "kinds": 0},
    "BGU2": {"files": 5, "subdirs": 0, "non_xml": 0, "bytes": 7735, "index_records": 5,
             "sibling_index": 224, "prefix_mask": 229, "root_names": 5, "header_names": 5,
             "header_null": 0, "db_rows": 5, "targets": 6, "distinct": 6, "max_targets": 2,
             "target_exact": 6, "dimension": 5, "object": 1, "use_with": 5, "use_empty": 0,
             "item_ref": 6, "item_other_form": 0, "item_absent": 0, "empty_comment": 5,
             "kinds": 2},
    "BP3": {"files": 7, "subdirs": 0, "non_xml": 0, "bytes": 13647, "index_records": 7,
            "sibling_index": 539, "prefix_mask": 546, "root_names": 7, "header_names": 7,
            "header_null": 0, "db_rows": 7, "targets": 26, "distinct": 26, "max_targets": 20,
            "target_exact": 26, "dimension": 24, "object": 2, "use_with": 7, "use_empty": 0,
            "item_ref": 26, "item_other_form": 0, "item_absent": 0, "empty_comment": 7,
            "kinds": 2},
}

# Классы целей перечня `<Use>` по выгрузкам (замер 2.1 плана): два вида метаданных на весь
# круг — `InformationRegister` 30 и `Catalog` 4. Распределение поимённое, а не только сумма:
# именно класс цели отвечает на вопрос «на какие объекты действует параметр».
EXPECTED_KINDS_BY_DUMP = {
    "MinCfg": {"Catalog": 1, "InformationRegister": 1},
    "BGU2": {"InformationRegister": 5, "Catalog": 1},
    "BP3": {"InformationRegister": 24, "Catalog": 2},
}
EXPECTED_KINDS = {"InformationRegister": 30, "Catalog": 4}

# Суммы по четырём выгрузкам (разделы 1.1, 1.2, 2.1 плана) — они же эталоны живой базы:
# строки витрин обязаны сходиться с файлами и индексом, а не только с разбором.
# `distinct_global` = 29 — мера, названная этим шагом П6 по живой базе: 34 цели дают 29
# различных адресов, потому что 5 адресов общи паре BGU2/BP3 — те же коллизии имён и uuid
# вида (замер 1.3, M1), из-за которых ключ держит `configuration_uuid`. Сумма
# по-выгрузочных `distinct` (2+6+26 = 34) равна числу строк применения: внутри одной
# выгрузки дублей целей корпус не давал (замер 2.1).
CORPUS_TOTALS = {
    "files": 14, "bytes": 24431, "index_records": 14, "sibling_index": 765,
    "prefix_mask": 779, "root_names": 14, "header_names": 14, "header_null": 1,
    "db_rows": 14, "targets": 34, "distinct_sum": 34, "distinct_global": 29,
    "max_targets": 20, "target_exact": 34, "dimension": 30, "object": 4,
    "use_with": 14, "use_empty": 0, "item_ref": 34, "item_other_form": 0, "item_absent": 0,
    "empty_comment": 12, "kinds": 2, "circle_discrepancies": 0, "unknown_states": 0,
    "unresolved_total": 0, "half_resolved": 0, "duplicate_targets": 0,
    "invariant_violations": 0, "orphans": 0, "outside_views": 0,
}

# Чужие круги (соседние узлы V48…V56 и круг модулей V47): прогон проверки читающий, и ни
# одна их строка не имеет права измениться. Круг V56 назван списком таблиц, а не маской:
# имена `functional_options` и `functional_option_parameters` различаются окончанием, и
# широкая маска `functional_option%` захватывает оба круга (замер 1.2 плана V57).
FOREIGN_TABLES = (
    "session_parameters", "roles", "role_rights", "role_restriction_templates",
    "common_attributes", "common_attribute_targets", "exchange_plans",
    "exchange_plan_content", "filter_criteria", "filter_criterion_content",
    "event_subscriptions", "event_subscription_sources", "scheduled_jobs",
    "scheduled_job_schedules", "bots", "bsl_modules", "configuration_objects",
    "configurations",
) + OPTION_CIRCLE_TABLES
# Отдельно — витрины соседней позиции 2.11: критерий готовности П6 называет именно их числа
# (`v_current_functional_options` 765 и `v_current_functional_option_content` 10 063), потому
# что круг 2.12 живёт рядом с кругом 2.11, и путаница в предикате изменила бы их состав.
FOREIGN_VIEWS = ("v_current_functional_options", "v_current_functional_option_content")

PASSED: list = []
FAILED: list = []
SKIPPED: list = []
INFO: list = []


# ── форма выдачи: PASS / FAIL / SKIP / INFO, отказ называется, а не обрывает прогон ──────────
def check(name, ok, detail=""):
    if ok:
        PASSED.append(name)
        print(f"PASS {name}")
    else:
        FAILED.append(name)
        print(f"FAIL {name}" + (f"\n      {detail}" if detail else ""))


def skip(name, reason):
    SKIPPED.append(name)
    print(f"SKIP {name}\n      {reason}")


def info(text):
    INFO.append(text)
    print(f"INFO {text}")


def section(title):
    print(f"\n{title}\n{'-' * len(title)}")


def q(cur, sql, params=None):
    cur.execute(sql, params or ())
    if not cur.description:
        return []
    columns = [d[0] for d in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def one(cur, sql, params=None):
    rows = q(cur, sql, params)
    return rows[0] if rows else {}


def scalar(cur, sql, params=None):
    row = one(cur, sql, params)
    return list(row.values())[0] if row else None


def names(sample, limit=MAX_NAMES):
    shown = list(sample)[:limit]
    tail = "" if len(sample) <= limit else f" … ещё {len(sample) - limit}"
    return ", ".join(str(s) for s in shown) + tail


def _brief(value, limit=120):
    text = str(value).replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + " …"


def table_columns(cur, table):
    """Колонки таблицы по живой схеме (список берётся из схемы, а не из памяти проверки)."""
    return [row["column_name"] for row in q(
        cur, "SELECT column_name FROM information_schema.columns WHERE table_name = %s "
             "ORDER BY ordinal_position", (table,))]


def constraint_def(cur, table, constraint):
    """Текст ограничения живой схемы; отсутствующее ограничение — пустая строка (называется)."""
    return scalar(cur, "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                       "WHERE conrelid = %s::regclass AND conname = %s",
                  (table, constraint)) or ""


def literals_of(definition):
    """Литералы ограничения — закрытый словарь схемы. Кавычек внутри состояний нет."""
    out, raw, i = [], str(definition), 0
    while i < len(raw):
        if raw[i] == "'":
            j = i + 1
            while j < len(raw) and raw[j] != "'":
                j += 1
            out.append(raw[i + 1:j])
            i = j + 1
        else:
            i += 1
    return out


def unique_constraints(cur, table):
    """Ограничения UNIQUE живой схемы: имя → текст (ключ ищется по схеме, не по памяти)."""
    return {str(r["conname"]): str(r["def"]) for r in q(
        cur, "SELECT conname, pg_get_constraintdef(oid) AS def FROM pg_constraint "
             "WHERE conrelid = %s::regclass AND contype IN ('u', 'p')", (table,))}


def foreign_keys(cur, table):
    """Внешние ключи живой схемы: имя → текст."""
    return {str(r["conname"]): str(r["def"]) for r in q(
        cur, "SELECT conname, pg_get_constraintdef(oid) AS def FROM pg_constraint "
             "WHERE conrelid = %s::regclass AND contype = 'f'", (table,))}


def indexes_of(cur, table):
    """Индексы живой схемы: имя → текст определения (не только уникальные)."""
    out = {}
    for row in q(cur, "SELECT i.relname AS name, pg_get_indexdef(i.oid) AS def "
                      "FROM pg_index x JOIN pg_class i ON i.oid = x.indexrelid "
                      "JOIN pg_class t ON t.oid = x.indrelid WHERE t.relname = %s",
                 (table,)):
        out[str(row["name"])] = str(row["def"])
    return out


def compact(text):
    return " ".join(str(text).split())


def expect_of(tag):
    return PLAN_EXPECTATIONS[tag]


def set_diff(label, left, right, tag):
    """Две стороны одного множества сравниваются попарно; расхождение называется именами."""
    missing, extra = sorted(right - left), sorted(left - right)
    check(f"{tag}: {label} совпадают во все стороны", not missing and not extra,
          f"не названо: {names(missing)}; лишнее: {names(extra)}")


# ── контур 1: живая схема круга ──────────────────────────────────────────────────────────────
def check_schema(cur):
    section("Контур 1 — живая схема круга")
    for table in (TABLE_NAME, TARGETS_TABLE_NAME):
        if not q(cur, "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                 (table,)):
            check(f"{table}: таблица существует", False, "таблицы в схеме нет")
            return
    for table in (TABLE_NAME, TARGETS_TABLE_NAME):
        columns = table_columns(cur, table)
        check(f"{table}: таблица существует и держит {EXPECTED_COLUMN_COUNTS[table]} "
              "колонок (эталон П1)", len(columns) == EXPECTED_COLUMN_COUNTS[table],
              f"факт: {len(columns)}")

    # Круг узла — ровно две таблицы (Q1, вариант A): обход схемы по маске вида обязан дать
    # их обе и ничего больше. Границу чужого круга называет список `OPTION_CIRCLE_TABLES`, а
    # не подстановка в LIKE: соседний узел V56 назвал свои таблицы `functional_options` и
    # `functional_option_content`, и широкая маска `functional_option%` их захватывает
    # (замер 1.2 плана V57). Отсутствия этих таблиц в базе отказом узла не является: круг
    # V57 от их наличия или отсутствия не меняется.
    kind_tables = [str(r["table_name"]) for r in q(
        cur, "SELECT table_name FROM information_schema.tables WHERE table_name LIKE %s "
             "ORDER BY table_name", ("functional_option%",))]
    foreign_found = sorted(t for t in kind_tables if t in OPTION_CIRCLE_TABLES)
    node_tables = sorted(t for t in kind_tables if t not in OPTION_CIRCLE_TABLES)
    check("таблиц вида по маске `functional_option%` без чужого круга V56 — ровно две "
          "(Q1 вариант A: свойства вида и перечень применения)",
          node_tables == sorted([TABLE_NAME, TARGETS_TABLE_NAME]),
          f"найдено: {names(kind_tables)}")
    check("таблиц чужого круга V56 в круг узла не вошло — граница названа списком таблиц, "
          "а не совпадением префикса имени (позиция 2.11, узел V56)",
          len(foreign_found) in (0, len(OPTION_CIRCLE_TABLES)),
          f"чужих таблиц: {names(foreign_found)}")

    parameter_columns = set(table_columns(cur, TABLE_NAME))
    targets_columns = set(table_columns(cur, TARGETS_TABLE_NAME))
    absent = sorted(column for column in ("revision_no", "changed_at", "changed_by",
                                          "is_committed") if column in targets_columns)
    check(f"`{TARGETS_TABLE_NAME}`: колонок цепи ревизий нет осознанно (Q2, вариант A) — "
          "текущность читается связкой с родителем, а не собственной цепью", not absent,
          f"лишние колонки: {names(absent)}")
    missing_chain = sorted(c for c in REVISION_COLUMNS if c not in parameter_columns)
    check(f"`{TABLE_NAME}`: колонки цепи ревизий узла V19 живы целиком "
          f"({len(REVISION_COLUMNS)} колонок)", not missing_chain,
          f"нет: {names(missing_chain)}")

    wanted_scope_key = "(configuration_uuid, object_name, revision_no)"
    keys = unique_constraints(cur, TABLE_NAME)
    scope = [d for d in keys.values() if compact(d).endswith(wanted_scope_key)]
    check(f"`{TABLE_NAME}`: ключ области видимости строк узла живой {wanted_scope_key} "
          "(M1: 5 uuid и 5 имён вида совпадают у BGU2 и BP3 — замер 1.3)",
          len(scope) == 1, f"ключи схемы: {names(list(keys))}")

    targets_keys = unique_constraints(cur, TARGETS_TABLE_NAME)
    wanted_targets_key = "(functional_option_parameter_id, ordinal)"
    targets_scope = [d for d in targets_keys.values()
                     if compact(d).endswith(wanted_targets_key)]
    check(f"`{TARGETS_TABLE_NAME}`: ключ применения живой {wanted_targets_key} — порядок "
          "перечня `<Use>` восстанавливается по ordinal; уникального ключа по паре "
          "(параметр, цель) нет осознанно (Q7: он превратил бы незнакомую форму выгрузки в "
          "отказ записи вместо названного состояния)",
          len(targets_scope) == 1, f"ключи схемы: {names(list(targets_keys))}")

    parameter_fks = foreign_keys(cur, TABLE_NAME)
    check(f"`{TABLE_NAME}`: внешних ключей нет осознанно — ни на заголовок (прецедент "
          "V20.1), ни на цель перечня `<Use>` (Q3: слои `InformationRegisters`, `Catalogs` и "
          "прочие не загружены, состояние разрешения называется строкой)", not parameter_fks,
          f"ключи: {names(list(parameter_fks))}")

    targets_fks = foreign_keys(cur, TARGETS_TABLE_NAME)
    cascade = [d for d in targets_fks.values()
               if "ON DELETE CASCADE" in compact(d).upper()
               and "functional_option_parameters" in compact(d)]
    check(f"`{TARGETS_TABLE_NAME}`: ровно один внешний ключ на `{TABLE_NAME}(id)` с "
          "`ON DELETE CASCADE` (снимает применение вместе с ревизией вида — M2)",
          len(targets_fks) == 1 and len(cascade) == 1,
          f"ключи: {names(list(targets_fks))}")

    for table, wanted in EXPECTED_INDEXES.items():
        found = sorted(indexes_of(cur, table))
        check(f"`{table}`: состав индексов круга — ровно {len(wanted)} (миграция V57: "
              "отдельного индекса по `configuration_uuid` у таблицы вида и индекса по форме "
              "адреса нет осознанно)", found == wanted,
              f"нет: {names(sorted(set(wanted) - set(found)))}; лишние: "
              f"{names(sorted(set(found) - set(wanted)))}")
    found_indexes = {}
    for table in (TABLE_NAME, TARGETS_TABLE_NAME):
        found_indexes.update(indexes_of(cur, table))
    for index_name, fragment in INDEX_LEAD_COLUMNS.items():
        definition = compact(found_indexes.get(index_name, ""))
        check(f"индекс `{index_name}` жив и ведёт по `{compact(fragment)}`",
              bool(definition) and compact(fragment) in definition,
              "индекса в схеме нет" if not definition
              else f"определение: {_brief(definition)}")

    for view in (PARAMETER_VIEW, TARGETS_VIEW):
        try:
            count = scalar(cur, f"SELECT count(*) FROM {view}")
            check(f"витрина текущего состояния `{view}` жива и читается", True)
            info(f"витрина `{view}`: строк {count}")
        except Exception as exc:  # noqa: BLE001 — отсутствующая витрина называется отказом
            cur.connection.rollback()
            check(f"витрина текущего состояния `{view}` жива и читается", False, str(exc))

    check(f"`{TABLE_NAME}` состоит в реестре версионируемых (цепь узла V19, Q2)",
          TABLE_NAME in CONFIGURATION_VERSIONED_TABLES,
          f"реестр: {names(sorted(CONFIGURATION_VERSIONED_TABLES))}")
    check(f"`{TARGETS_TABLE_NAME}` НЕ версионируется своей цепью и названа исключением "
          "`CONFIGURATION_UNVERSIONED_TABLES` (Q2, вариант A — прецеденты `role_rights` V49, "
          "`common_attribute_targets` V50, `filter_criterion_content` V52, "
          "`functional_option_content` V56)",
          TARGETS_TABLE_NAME not in CONFIGURATION_VERSIONED_TABLES
          and TARGETS_TABLE_NAME in CONFIGURATION_UNVERSIONED_TABLES,
          f"исключение: {names(list(CONFIGURATION_UNVERSIONED_TABLES))}")
    check(f"имя витрины вида задаёт реестр, а не DDL: `current_view()` отдаёт "
          f"`{PARAMETER_VIEW}`",
          current_view(TABLE_NAME) == PARAMETER_VIEW,
          f"реестр даёт: {current_view(TABLE_NAME)}")
    # Для таблицы применения `current_view()` обязан отказать: своей цепи ревизий у неё нет
    # (Q2, вариант A), поэтому имя витрины называется слоем, а не выводится из реестра.
    try:
        registry_answer = f"реестр версионируемых вернул имя {current_view(TARGETS_TABLE_NAME)}"
        refused = False
    except ValueError as exc:
        registry_answer = str(exc)
        refused = True
    check(f"`current_view()` для `{TARGETS_TABLE_NAME}` отказывает (своей цепи нет), имя "
          f"витрины `{TARGETS_VIEW}` называется слоем прямо",
          refused and "не версионируется" in registry_answer, registry_answer)
    check("писатели обеих таблиц внесены в `CONFIGURATION_OBJECT_WRITERS` (реестр выбирает "
          "писателя по таблице, отсутствие означало бы выбор класса по имени)",
          TABLE_NAME in CONFIGURATION_OBJECT_WRITERS
          and TARGETS_TABLE_NAME in CONFIGURATION_OBJECT_WRITERS,
          f"писатель вида: {CONFIGURATION_OBJECT_WRITERS.get(TABLE_NAME)}, применения: "
          f"{CONFIGURATION_OBJECT_WRITERS.get(TARGETS_TABLE_NAME)}")
    check(f"перечень заголовка `configurations.{HEADER_NAME_COLUMN}` жив (его заполняет "
          "стадия S2 узла V43, стадия V57 её не перезаписывает)",
          bool(q(cur, "SELECT 1 FROM information_schema.columns WHERE table_name = "
                      "'configurations' AND column_name = %s", (HEADER_NAME_COLUMN,))))


# ── контур 2: словари состояний ↔ CHECK'ы конкретной таблицы ────────────────────────────────
def compare_vocabulary(cur, table, column, vocabulary):
    """Словарь модуля и замкнутость схемы равны; расхождение называется множествами.

    CHECK ищется по таблице, которой принадлежит колонка (`STATE_VOCABULARY_TABLES`):
    «где-нибудь в схеме» нашло бы словарь чужого узла с тем же именем состояния
    (`target_resolve_state`, `target_address_form` есть у V50/V52/V56), а проверка узла
    обязана подтверждать словарь своей таблицы. Для `target_resolve_state` замкнутость
    держит ограничение согласованности (`STATE_CHECK_NAMES`) — отдельного `_known` у него
    нет осознанно, и это отличие от V56 названо словарём, а не молчанием.
    """
    constraint = STATE_CHECK_NAMES.get((table, column))
    if not constraint:
        check(f"{table}.{column}: имя CHECK замкнутости названо словарём "
              "`STATE_CHECK_NAMES`", False, "связки «таблица, колонка → имя ограничения» нет")
        return set()
    definition = constraint_def(cur, table, constraint)
    if not definition:
        check(f"{table}.{column}: CHECK замкнутости `{constraint}` живой схемы", False,
              "ограничения с таким именем в схеме нет — словарь схемы нечем подтвердить")
        return set()
    schema_values = set(literals_of(definition))
    module_values = set(vocabulary)
    if "" not in module_values:
        # Пустая строка в тексте CHECK принадлежит другому условию ограничения
        # (`target_full_name = ''` в `..._resolve_matches_ref`), а не словарю состояний:
        # чужую пустоту в словарь не берём. Если же пустая строка состоянием является
        # (`target_address_form` — «адреса нет»), она остаётся и сверяется.
        schema_values.discard("")
    check(f"{table}.{column}: CHECK живой схемы перечисляет словарь модуля "
          f"({len(module_values)} значений)", schema_values == module_values,
          f"в словаре нет: {names(sorted(schema_values - module_values))}; "
          f"CHECK допускает: {names(sorted(module_values - schema_values))}")
    return schema_values


def check_state_vocabulary_checks(cur):
    section("Контур 2 — словари состояний против CHECK'ов конкретной таблицы")
    columns_by_table = {table: set(table_columns(cur, table))
                        for table in (TABLE_NAME, TARGETS_TABLE_NAME)}
    vocabularies = {}
    for column in sorted(STATE_VOCABULARIES):
        table = STATE_VOCABULARY_TABLES.get(column)
        if table is None:
            check(f"колонка состояния `{column}` имеет таблицу в "
                  f"`STATE_VOCABULARY_TABLES`", False,
                  "связки нет — проверка сверяла бы словарь не с той таблицей")
            continue
        vocabularies[column] = STATE_VOCABULARIES[column]
        compare_vocabulary(cur, table, column, vocabularies[column])

    outside = sorted(column for column, table in STATE_VOCABULARY_TABLES.items()
                     if column not in columns_by_table.get(table, set()))
    check(f"словари состояний разбора стоят на колонках своих таблиц "
          f"({len(STATE_VOCABULARY_TABLES)} колонок)", not outside,
          f"колонок в схеме нет: {names(outside)}")
    check(f"`state_columns()` отдаёт ровно замкнутый словарь "
          f"({len(STATE_VOCABULARIES)} колонок) — ответ и проверка перечисляют состояния "
          "списком, а не догадкой",
          tuple(sorted(state_columns())) == tuple(sorted(STATE_VOCABULARIES)),
          f"функция даёт: {names(state_columns())}")

    names_present = set()
    for table in (TABLE_NAME, TARGETS_TABLE_NAME):
        names_present |= {str(r["conname"]) for r in q(
            cur, "SELECT conname FROM pg_constraint WHERE conrelid = %s::regclass", (table,))}
    missing = [c for c in MATCH_CONSTRAINTS if c not in names_present]
    check(f"ограничений DDL узла V57 в схеме нет — {len(missing)} "
          f"(ожидаются {len(MATCH_CONSTRAINTS)})", not missing, names(missing))

    known = set()
    for vocabulary in vocabularies.values():
        known |= set(vocabulary)
    check(f"CHECK'ов по ЗНАЧЕНИЯМ свойств вида нет осознанно (Q7, вариант A): ни одно "
          f"значение словаря состояний ({len(known)} значений) не является именем свойства "
          f"({len(XML_PROPERTY_NAMES)} тегов), и словарей значений в модуле разбора нет",
          not (known & set(XML_PROPERTY_NAMES))
          and len(STATE_VOCABULARIES) == len(STATE_VOCABULARY_TABLES),
          f"пересечение: {names(sorted(known & set(XML_PROPERTY_NAMES)))}")
    check("плейсхолдер перечня в словаре свойств — ОДИН (`use`), и его имени нет среди "
          "колонок схемы: перечень живёт второй таблицей, а в строке вида держатся только "
          "состояние и счётчик",
          property_kind("use") == "use" and "use" not in columns_by_table[TABLE_NAME]
          and property_kind("use_state") is None and property_kind("targets_count") is None
          and USE_STATE_COLUMNS == ("use_state", "targets_count"),
          f"use: {property_kind('use')}, колонок перечня в строке вида: "
          f"{names(sorted({'use'} & columns_by_table[TABLE_NAME]))}")
    check(f"словарь состояний свойств и словарь состояний перечня замкнуты и не пересекаются "
          f"({len(PROPERTIES_STATES)} + {len(USE_STATES)} значений)",
          not (set(PROPERTIES_STATES) & set(USE_STATES))
          and sorted(STATE_VOCABULARIES["properties_state"]) == sorted(PROPERTIES_STATES)
          and sorted(STATE_VOCABULARIES["use_state"]) == sorted(USE_STATES),
          f"properties: {names(PROPERTIES_STATES)}, use: {names(USE_STATES)}")
    check(f"словари разрешения цели ({len(TARGET_RESOLVE_STATES)}), формы адреса "
          f"({len(ADDRESS_FORMS)}, пустая строка — «адреса нет») и формы элемента "
          f"({len(ITEM_TYPE_STATES)}) замкнуты CHECK'ами таблицы применения",
          sorted(STATE_VOCABULARIES["target_resolve_state"]) == sorted(TARGET_RESOLVE_STATES)
          and sorted(STATE_VOCABULARIES["target_address_form"]) == sorted(ADDRESS_FORMS)
          and sorted(STATE_VOCABULARIES["item_type_state"]) == sorted(ITEM_TYPE_STATES)
          and ADDRESS_FORM_EMPTY in ADDRESS_FORMS,
          f"resolve: {names(TARGET_RESOLVE_STATES)}, forms: {names(ADDRESS_FORMS)}, "
          f"item: {names(ITEM_TYPE_STATES)}")

    # Ключ сводки → колонка состояния держится словарём, а не выводом из имени: вывод дал бы
    # для `counts_by_target_address_form` колонку без проверки, что она существует, и нулевой
    # контракт потерял бы словарь (приём V56 с `location_target_form`).
    bad_counts = [f"{key} ≠ {COUNT_KEY_STATE_COLUMNS.get(key)}" for key in COUNT_KEYS
                  if COUNT_KEY_STATE_COLUMNS.get(key) not in STATE_VOCABULARIES]
    check(f"связка `COUNT_KEYS` → `COUNT_KEY_STATE_COLUMNS` → колонок состояния замкнута "
          f"({len(COUNT_KEYS)} ключей)", not bad_counts, "; ".join(bad_counts))
    check(f"словари состояний покрываются ключами сводки целиком: все "
          f"{len(STATE_VOCABULARIES)} колонок состояния названы хотя бы одним ключом",
          set(COUNT_KEY_STATE_COLUMNS.values()) == set(STATE_VOCABULARIES),
          f"ключей: {names(sorted(COUNT_KEY_STATE_COLUMNS.values()))}")
    check(f"наблюдения круга замкнуты ({len(OBSERVATION_KINDS)}): «каталога нет», "
          "«подкаталог/не-XML в каталоге», «индекс не передан» — три разных ответа (Q9, C2)",
          OBSERVATION_KINDS == FUNCTIONAL_OPTIONS_PARAMETERS_OBSERVATION_KINDS
          and set(OBSERVATION_KINDS) == {"directory_missing", "unexpected_dir",
                                          "unexpected_file", "index_not_provided"},
          f"словарь: {names(OBSERVATION_KINDS)}")
    check(f"расхождения ног круга замкнуты ({len(CIRCLE_DISCREPANCIES)}): ключей "
          "`child_mismatches`/`index_pseudo_entries` нет осознанно — записей детей и "
          "псевдозаписей вида в индексе нет ни в одной выгрузке (замер 1.2)",
          CIRCLE_DISCREPANCIES == ("index_only", "file_only", "uuid_mismatch"),
          f"словарь: {names(CIRCLE_DISCREPANCIES)}")


# ── контур 2.1: ключ разбора против колонок схемы ────────────────────────────────────────────
def check_key_columns_match(cur):
    section("Контур 2.1 — ключ разбора против колонок схемы")
    parameter_columns = set(table_columns(cur, TABLE_NAME))
    targets_columns = set(table_columns(cur, TARGETS_TABLE_NAME))

    parse_parameter_columns = (set(property_columns()) | set(USE_STATE_COLUMNS)
                               | {"object_uuid", "full_name", "source_path",
                                  "properties_state", "unknown_property_names"})
    check(f"словарь свойств ({FUNCTIONAL_OPTIONS_PARAMETER_PROPERTY_COUNT} тегов, из них "
          f"{len(property_columns())} колонок) и перечень ({len(USE_STATE_COLUMNS)} колонок "
          f"состояния) дают ровно {len(parse_parameter_columns)} колонок строки вида",
          parse_parameter_columns <= parameter_columns,
          f"ключей без колонки: {names(sorted(parse_parameter_columns - parameter_columns))}")
    unexplained = sorted(parameter_columns - parse_parameter_columns - set(REVISION_COLUMNS))
    check(f"`{TABLE_NAME}`: колонок, которым нет причины, — ноль "
          f"({len(parameter_columns)} = {len(parse_parameter_columns)} разбора + "
          f"{len(REVISION_COLUMNS)} цепи ревизий)", not unexplained, names(unexplained))

    targets_expected = (set(TARGET_ROW_KEYS) | {"functional_option_parameter_id",
                                               "configuration_uuid", "id", "created_at"})
    check(f"`{TARGETS_TABLE_NAME}`: ключ разбора ({len(TARGET_ROW_KEYS)}) + связь слоя + "
          f"служебные колонки равны колонкам таблицы "
          f"({len(targets_expected)} = {len(targets_columns)})",
          targets_expected == targets_columns,
          f"нет в таблице: {names(sorted(targets_expected - targets_columns))}; вне разбора: "
          f"{names(sorted(targets_columns - targets_expected))}")
    check(f"ключи строки применения названы одним местом: `TARGET_ROW_KEYS` держит "
          f"{len(TARGET_ROW_KEYS)} ключей, включая связку слоя "
          f"(`{PARAMETER_LINK_KEY}`, `{PARAMETER_UUID_KEY}`) — имена связок совпадают с "
          "колонками осознанно (Q2, вариант A: лишней подмены колонок писателю не нужно)",
          PARAMETER_LINK_KEY in TARGET_ROW_KEYS and PARAMETER_UUID_KEY in TARGET_ROW_KEYS
          and PARAMETER_LINK_KEY in targets_columns and PARAMETER_UUID_KEY in targets_columns
          and set(TARGET_COMPARE_FIELDS) | {PARAMETER_LINK_KEY, PARAMETER_UUID_KEY}
          == set(TARGET_ROW_KEYS),
          f"ключи: {names(TARGET_ROW_KEYS)}")

    check(f"словарь свойств вида держится ОДНИМ местом: `property_columns()` даёт "
          f"{len(property_columns())} колонок, `XML_PROPERTY_NAMES` — "
          f"{len(XML_PROPERTY_NAMES)} тегов, `PROPERTY_BY_COLUMN` — "
          f"{len(PROPERTY_BY_COLUMN)} связок, реестр свойств — "
          f"{FUNCTIONAL_OPTIONS_PARAMETER_PROPERTY_COUNT} записей",
          len(FUNCTIONAL_OPTIONS_PARAMETER_PROPERTIES)
          == FUNCTIONAL_OPTIONS_PARAMETER_PROPERTY_COUNT
          and len(PROPERTY_BY_COLUMN) == FUNCTIONAL_OPTIONS_PARAMETER_PROPERTY_COUNT
          and len(XML_PROPERTY_NAMES) == FUNCTIONAL_OPTIONS_PARAMETER_PROPERTY_COUNT
          and len(property_columns()) == FUNCTIONAL_OPTIONS_PARAMETER_PROPERTY_COUNT - 1,
          f"связок: {len(PROPERTY_BY_COLUMN)}, колонок: {len(property_columns())}")
    check("виды разбора свойств названы (`property_kind`): текст, многоязычный блок и "
          "плейсхолдер перечня; колонок-плейсхолдеров среди колонок схемы нет, а колонки "
          "перечня возвращают None — они вне словаря свойств",
          property_kind("object_name") == "text" and property_kind("comment") == "text"
          and property_kind("synonym") == "multilang" and property_kind("use") == "use"
          and property_kind("use_state") is None and property_kind("targets_count") is None,
          f"object_name: {property_kind('object_name')}, synonym: "
          f"{property_kind('synonym')}, use: {property_kind('use')}")
    check(f"отсутствующий тег называется состоянием с именем виновника: `DECLARED_PROPERTIES` "
          f"({len(DECLARED_PROPERTIES)} тегов) не держит `Name` — его отсутствие есть отказ "
          "разбора файла, а не состояние строки (прецедент V50, V56)",
          sorted(DECLARED_PROPERTIES) == sorted(
              name for name in XML_PROPERTY_NAMES if name != "Name"),
          f"перечень: {names(DECLARED_PROPERTIES)}")


# ── независимая мера круга: обход каталога и текста файлов без знания о состоянии разбора ────
# Регулярные выражения читают ТЕКСТ файла: проверка не пользуется словарём состояний
# разбора, иначе она подтверждала бы разбор его же утверждением (приём V50/V52/V56).
NAME_RE = re.compile(r"<Name>\s*(.*?)\s*</Name>", re.S)
COMMENT_RE = re.compile(
    r"<(?:[\w.-]+:)?Comment\s*/>|<(?:[\w.-]+:)?Comment\b[^>]*>(.*?)</(?:[\w.-]+:)?Comment\s*>",
    re.S)
USE_BLOCK_RE = re.compile(
    r"<(?:[\w.-]+:)?Use\s*/>|<(?:[\w.-]+:)?Use\b[^>]*>(.*?)</(?:[\w.-]+:)?Use\s*>", re.S)
USE_ITEM_RE = re.compile(r"<(?:[\w.-]+:)?Item\b([^>]*)>(.*?)</(?:[\w.-]+:)?Item\s*>", re.S)
USE_ITEM_SELF_CLOSED_RE = re.compile(r"<(?:[\w.-]+:)?Item\b[^>]*/>")
# Локальное имя элемента перечня — как его хранит колонка `item_tag` (префикс пространства
# имён `xr:` в выгрузке есть, в схеме его нет: DDL держит имя КАК В ВЫГРУЗКЕ без префикса).
ITEM_TAG_RE = re.compile(r"<(?:[\w.-]+:)?(Item)\b")
ITEM_TYPE_RE = re.compile(r"(?:xsi:)?type\s*=\s*\"([^\"]*)\"")
# Перечень корня `Configuration.xml` — четвёртая нога круга (замер `_v57_p0_probe.py`):
# `<FunctionalOptionsParameter>Имя</FunctionalOptionsParameter>` внутри `<MetaDataObject>`.
# Тег берётся точным именем вида: соседний тег `FunctionalOption` начинается с той же строки
# (замер 1.2), и подстрока смешала бы два перечня.
ROOT_ENTRY_RE = re.compile(
    r"<" + OBJECT_KIND_TAG + r">\s*([^<]+?)\s*</" + OBJECT_KIND_TAG + r">")
SIBLING_ROOT_ENTRY_RE = re.compile(
    r"<" + SIBLING_INDEX_OBJECT_TYPE + r">\s*([^<]+?)\s*</" + SIBLING_INDEX_OBJECT_TYPE + r">")

# Маркеры срезов адреса цели — тот же закрытый перечень, что держит CHECK
# `functional_option_parameter_targets_form_matches_name` (M5). Мера считает их по тексту
# адреса независимо от функции разбора.
SLICE_MARKERS = (
    (".Dimension.", ADDRESS_FORM_DIMENSION),
    (".Resource.", ADDRESS_FORM_REGISTER_RESOURCE),
    (".Attribute.", ADDRESS_FORM_ATTRIBUTE),
    (".TabularSection.", ADDRESS_FORM_TABULAR_SECTION),
)


def raw_address_form(target):
    """ФОРМА адреса цели по его тексту — независимо от `target_address_form()` разбора."""
    value = (target or "").strip()
    if not value:
        return ADDRESS_FORM_EMPTY
    for marker, form in SLICE_MARKERS:
        if marker in value:
            return form
    if value.count(".") == 1 and all(part for part in value.split(".")):
        return ADDRESS_FORM_OBJECT
    return ADDRESS_FORM_OTHER


def raw_target_kind(target):
    """Первый сегмент адреса цели — вид метаданных цели (та же мера, что CHECK
    `..._type_matches_name`, но посчитанная по тексту файла)."""
    value = (target or "").strip()
    return value.split(".", 1)[0] if value else ""


def circle_measures(dump_dir):
    """Файлы регистрации, подкаталоги, не-XML, элементы `<Use>`, пустые перечни, пустые
    `Comment`, классы и формы целей, перечень корня `Configuration.xml`.

    `use_items` считается по тексту файла, `empty_use_files` — по файлам, где блок перечня
    пуст (`<Use/>` или `<Use></Use>`): корпус таких файлов не даёт (замер 2.1 — ноль), и
    именно поэтому состояние `empty_content` является границей разбора, а не наблюдением
    (M3). Порядок элементов (`position`) читается позициями совпадений в тексте — тот же
    приём, что в V49/V50/V56.
    """
    root = Path(dump_dir) / DIR_NAME
    totals = {"files": 0, "subdirs": 0, "non_xml": 0, "bytes": 0, "directory_exists": 0,
              "use_blocks": 0, "empty_use_files": 0, "use_items": 0, "empty_comment_files": 0,
              "names": set(), "items_by_name": {}, "item_tags": Counter(),
              "item_types": Counter(), "forms": Counter(), "kinds": Counter(),
              "max_items_per_file": 0, "root_names": set(), "sibling_root_names": set(),
              "root_file": 0}
    # Каталог вида может отсутствовать (KomMag — замер 1.1), и это не повод не читать перечень
    # корня: `<FunctionalOptionsParameter>` в `Configuration.xml` является четвёртой ногой
    # круга, и её отсутствие обязано быть названо собственной мерой, а не следовать из
    # отсутствия каталога молчанием.
    if root.exists():
        totals["directory_exists"] = 1
    for entry in (sorted(root.iterdir()) if root.exists() else ()):
        if entry.is_dir():
            totals["subdirs"] += 1
            continue
        if entry.suffix.lower() != ".xml":
            totals["non_xml"] += 1
            continue
        totals["files"] += 1
        totals["bytes"] += entry.stat().st_size
        text, error = read_text_file(entry)
        if error or text is None:
            continue
        name_match = NAME_RE.search(text)
        parameter_name = name_match.group(1).strip() if name_match else entry.stem
        totals["names"].add(parameter_name)
        comments = COMMENT_RE.findall(text)
        if comments and not any((value or "").strip() for value in comments):
            totals["empty_comment_files"] += 1
        blocks = USE_BLOCK_RE.findall(text)
        items = []
        if blocks:
            totals["use_blocks"] += 1
            for block in blocks:
                if not block:
                    continue
                for position, element in enumerate(USE_ITEM_RE.finditer(block)):
                    attrs, inner = element.group(1), element.group(2)
                    tag_match = ITEM_TAG_RE.match(element.group(0))
                    type_match = ITEM_TYPE_RE.search(attrs)
                    # Ребро перечня несёт адрес цели текстом элемента
                    # (`<xr:Item xsi:type="xr:MDObjectRef">InformationRegister.…​.Dimension.…</xr:Item>`);
                    # вложенных элементов у него корпус не давал (замер 2.1) — снимать теги,
                    # а не искать их, иначе мера называла бы цель пустой.
                    target = re.sub(r"<[^>]+>", "", inner).strip()
                    items.append({"target_full_name": target, "position": position,
                                  "item_tag": tag_match.group(1) if tag_match else "",
                                  "item_type_attr": (type_match.group(1) if type_match
                                                     else None)})
                for element in USE_ITEM_SELF_CLOSED_RE.finditer(block):
                    tag_match = ITEM_TAG_RE.match(element.group(0))
                    items.append({"target_full_name": "", "position": len(items),
                                  "item_tag": tag_match.group(1) if tag_match else "",
                                  "item_type_attr": None})
        totals["use_items"] += len(items)
        totals["max_items_per_file"] = max(totals["max_items_per_file"], len(items))
        totals["items_by_name"][parameter_name] = items
        if blocks and not items:
            totals["empty_use_files"] += 1
        for item in items:
            totals["item_tags"][item["item_tag"]] += 1
            totals["item_types"][item["item_type_attr"]
                                if item["item_type_attr"] is not None
                                else "<absent>"] += 1
            totals["forms"][raw_address_form(item["target_full_name"])] += 1
            totals["kinds"][raw_target_kind(item["target_full_name"])] += 1
    config = Path(dump_dir) / "Configuration.xml"
    if config.is_file():
        text, error = read_text_file(config)
        if not error and text is not None:
            totals["root_file"] = 1
            totals["root_names"] = set(ROOT_ENTRY_RE.findall(text))
            totals["sibling_root_names"] = set(SIBLING_ROOT_ENTRY_RE.findall(text))
    return totals


def registration_names(dump_dir):
    """Имена видов по файлам регистрации (без расширения) — независимая мера каталога."""
    root = Path(dump_dir) / DIR_NAME
    if not root.exists():
        return set()
    return {entry.stem for entry in root.iterdir()
            if entry.is_file() and entry.suffix.lower() == ".xml"}


def index_short_name(row, prefix):
    """Короткое имя объекта по ПОЛНОМУ точечному имени строки индекса (`name`).

    Ключом строки `configuration_objects` служит полное точечное имя, а `object_name` несёт
    короткое имя владельца (урок узла V48, повторённый разбором V50/V52/V56): сверяя
    короткое имя, проверка не увидела бы псевдозаписей срезов и назвала бы круг расходящимся.
    """
    value = index_row_key(row)
    return value[len(prefix):] if value.startswith(prefix) else value


def read_index_aggregates(cur, configuration_id):
    """Записи индекса состава вида, ЧУЖДОГО вида и МАСКИ по началу имени — отдельным SQL.

    Отдельные запросы нужны потому, что граница круга держится ТОЧНЫМ значением
    `object_type`: `FunctionalOptionsParameter` начинается с того же слова, что
    `FunctionalOption`, и наоборот (раздел 1.2 плана V57) — маска `FunctionalOption%`
    даёт 4 / 229 / 546 строк вместо 2 / 5 / 7. Разница равна ровно записям позиции 2.11,
    и проверка называет обе меры, а не одну из них.
    """
    rows = q(cur, f"SELECT name, object_name, object_id, uuid::text AS uuid, depth, "
                  f"parent_name FROM {INDEX_TABLE} WHERE configuration_id = %s "
                  "AND object_type = %s ORDER BY name",
             (configuration_id, INDEX_OBJECT_TYPE))
    prefix = f"{INDEX_OBJECT_TYPE}{INDEX_NAME_SEPARATOR}"
    names = {index_short_name(row, prefix) for row in rows}
    children = [row for row in rows if row["parent_name"]]
    sibling_rows = q(cur, f"SELECT name, object_name FROM {INDEX_TABLE} WHERE "
                          "configuration_id = %s AND object_type = %s ORDER BY name",
                     (configuration_id, SIBLING_INDEX_OBJECT_TYPE))
    sibling_prefix = f"{SIBLING_INDEX_OBJECT_TYPE}{INDEX_NAME_SEPARATOR}"
    sibling_names = {index_short_name(row, sibling_prefix) for row in sibling_rows}
    mask_rows = scalar(cur, f"SELECT count(*) FROM {INDEX_TABLE} WHERE configuration_id = %s "
                            "AND object_type LIKE %s",
                       (configuration_id, f"{SIBLING_INDEX_OBJECT_TYPE}%"))
    return {"kind_rows": len(rows), "child_rows": len(children), "names": names,
            "sibling_rows": len(sibling_names), "sibling_names": sibling_names,
            "mask_rows": int(mask_rows or 0)}


def read_header_name_list(cur, cfg_uuid):
    """Перечень заголовка, заполненный стадией S2: имена элементов или NULL (пустой
    перечень различим от отсутствующего — колонка `text[]`, а не jsonb; M8, замер 1.1:
    у KomMag перечень `NULL`, потому что вида нет ни файлами, ни записями индекса)."""
    row = one(cur, f"SELECT coalesce(array_length({HEADER_NAME_COLUMN}, 1), 0) AS n, "
                   f"({HEADER_NAME_COLUMN} IS NULL) AS is_null, "
                   f"coalesce({HEADER_NAME_COLUMN}, '{{}}') AS items FROM configurations "
                   "WHERE uuid = %s::uuid", (cfg_uuid,))
    items = [str(item) for item in (row.get("items") or [])]
    return int(row.get("n") or 0), bool(row.get("is_null")), items


def read_parameter_rows(cur, cfg_uuid):
    """Строки вида текущей ревизии — через витрину, а не прямым чтением версионируемой
    таблицы."""
    return q(cur, f"SELECT * FROM {PARAMETER_VIEW} WHERE configuration_uuid = %s::uuid "
                   "ORDER BY full_name", (cfg_uuid,))


def read_target_rows(cur, cfg_uuid):
    """Строки применения текущих ревизий — через витрину применения (связка с витриной
    вида, а не с таблицей: иначе строки не-текущей ревизии попали бы в ответ)."""
    return q(cur, f"SELECT * FROM {TARGETS_VIEW} WHERE configuration_uuid = %s::uuid "
                   "ORDER BY parameter_full_name, ordinal", (cfg_uuid,))


# ── контур 3: граница круга — файлы, индекс, перечень заголовка, корень, строки таблицы ──────
def check_circle(cur, header, dump_dir, index_info, expect, parsed, tag):
    section(f"Контур 3 — граница круга ({tag})")
    raw = circle_measures(dump_dir)
    agg = read_index_aggregates(cur, int(header["id"]))
    db_rows = read_parameter_rows(cur, str(header["uuid"]))
    target_rows = read_target_rows(cur, str(header["uuid"]))
    header_count, header_is_null, header_items = read_header_name_list(cur,
                                                                       str(header["uuid"]))

    check(f"{tag}: файлов регистрации — {expect['files']} (замер 1.1)",
          raw["files"] == expect["files"], f"факт: {raw['files']}")
    check(f"{tag}: каталог вида плоский — подкаталогов и не-XML ноль, байтов "
          f"{expect['bytes']} (замеры 1.2, 1.4: форм, макетов, команд и модулей у вида нет)",
          raw["subdirs"] == expect["subdirs"] and raw["non_xml"] == expect["non_xml"]
          and raw["bytes"] == expect["bytes"],
          f"подкаталогов: {raw['subdirs']}, не-XML: {raw['non_xml']}, байтов: "
          f"{raw['bytes']}")
    check(f"{tag}: записей индекса состава вида — {expect['index_records']} (замер 1.1)",
          agg["kind_rows"] == expect["index_records"], f"факт: {agg['kind_rows']}")
    check(f"{tag}: записей детей вида в индексе нет — {expect['index_records']} ног, "
          "детей 0 (расхождений `child_mismatches` в словаре круга нет осознанно, замер 1.2)",
          agg["child_rows"] == 0, f"детских записей: {agg['child_rows']}")
    check(f"{tag}: строк вида в витрине — {expect['db_rows']}, строк применения — "
          f"{expect['targets']} (замеры 1.1, 2.1)",
          len(db_rows) == expect["db_rows"] and len(target_rows) == expect["targets"],
          f"факт: вида {len(db_rows)}, применения {len(target_rows)}")
    check(f"{tag}: перечень заголовка `configurations.{HEADER_NAME_COLUMN}` — "
          f"{expect['header_names']} имён (третью ногу круга пишет стадия S2, стадия S4l её "
          "не перезаписывает)",
          header_count == expect["header_names"], f"факт: {header_count}")
    check(f"{tag}: перечень корня `Configuration.xml` (`<{OBJECT_KIND_TAG}>`) — "
          f"{expect['root_names']} имён (четвёртая нога круга, замер 1.1)",
          raw["root_file"] == 1 and len(raw["root_names"]) == expect["root_names"],
          f"файла корня: {raw['root_file']}, имён: {len(raw['root_names'])}")

    # `NULL` перечня и пустой перечень — разные состояния (M8): у KomMag вида нет ни
    # файлами, ни записями индекса, и перечня нет вовсе.
    if expect["header_null"]:
        check(f"{tag}: перечень заголовка — `NULL`, а не пустой массив (замер 1.1: вида нет "
              "ни файлами, ни записями; «вида нет» и «перечень пуст» различимы в живой схеме)",
              header_is_null and header_count == 0,
              f"is_null: {header_is_null}, элементов: {header_count}")
    else:
        check(f"{tag}: перечень заголовка не `NULL` (вид в выгрузке есть)",
              not header_is_null, f"элементов: {header_count}")

    file_names = registration_names(dump_dir)
    set_diff("файлы каталога и имена индекса состава", file_names, agg["names"], tag)
    set_diff("имена индекса состава и перечень заголовка", agg["names"],
             {str(item) for item in header_items}, tag)
    set_diff("перечень заголовка и перечень корня `Configuration.xml`",
             {str(item) for item in header_items}, raw["root_names"], tag)
    set_diff("перечень корня и строки таблицы", raw["root_names"],
             {str(row["object_name"]) for row in db_rows}, tag)
    set_diff("файлы каталога и строки таблицы", file_names,
             {str(row["object_name"]) for row in db_rows}, tag)

    # Раздел 1.2 плана: `FunctionalOption` — другой вид (позиция 2.11, узел V56 закрыт).
    # Он существует в индексе состава (2/224/539 на корпус) и обязан НЕ попасть в круг:
    # сравнение вида точное, а не по префиксу. Отдельно называется МАСКА: она даёт ровно
    # на записи позиции 2.11 больше, и это та граница, из-за которой предикат держится
    # значением `object_type` (в планe раздела 1.2 число маски было написано как 16 —
    # прогон даёт 4, и правка плана сделана шагом П6).
    check(f"{tag}: записей ЧУЖДОГО вида `{SIBLING_INDEX_OBJECT_TYPE}` в индексе "
          f"{agg['sibling_rows']} (замер 1.2), в круг узла не вошла ни одна — предикат "
          "вида точный, а не по префиксу",
          agg["sibling_rows"] == expect["sibling_index"]
          and not ({str(row["object_name"]) for row in db_rows} & agg["sibling_names"]),
          f"чужих записей: {agg['sibling_rows']}, ожидание: {expect['sibling_index']}, "
          f"пересечение с кругом: "
          f"{names(sorted({str(row['object_name']) for row in db_rows} & agg['sibling_names']))}")
    check(f"{tag}: маска `object_type LIKE '{SIBLING_INDEX_OBJECT_TYPE}%'` даёт "
          f"{agg['mask_rows']} строк вместо точного предиката {agg['kind_rows']} — разница "
          f"равна ровно записям позиции 2.11 ({agg['sibling_rows']}); предикат круга "
          "держится значением `object_type`",
          agg["mask_rows"] == expect["prefix_mask"]
          and agg["mask_rows"] - agg["kind_rows"] == agg["sibling_rows"],
          f"маска: {agg['mask_rows']}, ожидание: {expect['prefix_mask']}, точный предикат: "
          f"{agg['kind_rows']}, чужих: {agg['sibling_rows']}")
    overlap = sorted(name for name in agg["names"] if name in agg["sibling_names"])
    root_overlap = sorted(name for name in raw["root_names"]
                          if name in raw["sibling_root_names"])
    info(f"{tag}: общих имён у вида и у функциональных опций — {len(overlap)} по индексу, "
         f"{len(root_overlap)} по корню; предикат круга различает виды по значению "
         "`object_type` и точным тегам перечня, поэтому пересечение имён на круг не влияет"
         + (f" (примеры: {names(overlap)})" if overlap else ""))

    # Расхождения ног круга обязаны быть названы, а не нулевыми по умолчанию: словарь
    # `CIRCLE_DISCREPANCIES` замкнут, и ответ стадии обязан перечислять его весь.
    discrepancies = {key: len(parsed.get(key) or []) for key in CIRCLE_DISCREPANCIES}
    check(f"{tag}: расхождений файла с индексом состава нет — "
          f"{', '.join(f'{k}={v}' for k, v in discrepancies.items())} (замер 1.1 даёт "
          "равенство ног)",
          all(value == 0 for value in discrepancies.values()),
          f"факт: {discrepancies}")
    observations = {}
    for kind, _detail in (parsed.get("observations") or []):
        observations[str(kind)] = observations.get(str(kind), 0) + 1
    if expect["files"] == 0 and not raw["directory_exists"]:
        check(f"{tag}: каталога вида нет — ответ обязан быть пустым кругом с наблюдением "
              "`directory_missing`, а не отказом стадии (Q9, вариант A; KomMag даёт именно "
              "так)",
              observations.get("directory_missing") == 1 and parsed["success"] is True
              and parsed["files_found"] == 0,
              f"наблюдения: {observations}, success: {parsed['success']}, found: "
              f"{parsed['files_found']}")
    else:
        check(f"{tag}: наблюдений `directory_missing` нет (каталог вида есть)",
              "directory_missing" not in observations, f"наблюдения: {observations}")
    check(f"{tag}: наблюдений о примитивности круга нет — подкаталогов и не-XML в каталоге "
          "вида ноль (замер 1.2: форм, макетов, команд, модулей и каталогов содержимого у "
          "вида нет)",
          observations.get("unexpected_dir", 0) == 0
          and observations.get("unexpected_file", 0) == 0
          and raw["subdirs"] == 0 and raw["non_xml"] == 0,
          f"наблюдения: {observations}, подкаталогов: {raw['subdirs']}, не-XML: "
          f"{raw['non_xml']}")

    # Пустой `Comment` — состояние свойств строки, а не подстановка значения: 12 файлов из
    # 14 дают пустой тег (замер 2 плана: BGU2 5, BP3 7), и в базе это `NULL`, а не пустая
    # строка; отсутствие тега отличается от пустого тега состоянием `properties_state`.
    db_null_comments = sum(1 for row in db_rows if row.get("comment") is None)
    db_empty_comments = sum(1 for row in db_rows if row.get("comment") == "")
    check(f"{tag}: пустых `Comment` по файлам — {expect['empty_comment']}, в строках вида "
          "столько же `NULL` и ни одной пустой строки (CHECK "
          "`functional_option_parameters_names_not_blank` и состояние свойств)",
          raw["empty_comment_files"] == expect["empty_comment"]
          and db_null_comments == expect["empty_comment"] and db_empty_comments == 0,
          f"файлы: {raw['empty_comment_files']}, NULL: {db_null_comments}, "
          f"пустых строк: {db_empty_comments}")
    return db_rows, target_rows, raw, agg, header_count, header_is_null


# ── контур 4: строка таблицы ↔ разбор тем же модулем, что и загрузка ─────────────────────────
def normalize(value):
    """Одна форма сравнения значения разбора и строки базы. Пустая строка НЕ сводится к
    NULL: `comment = ''` и «тега нет» различаются состоянием `properties_state`, а не
    подстановкой (прецедент V52/V53/V55/V56)."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if value is None:
        return None
    return str(value)


def compare_parameter_rows(parsed, db_rows, expect, tag):
    section(f"Контур 4 — строка вида против разбора ({tag})")
    parsed_rows = parsed["rows"]
    by_name = {str(row["object_name"]): row for row in parsed_rows}
    db_by_name = {str(row["object_name"]): row for row in db_rows}
    check(f"{tag}: имена разбора и строк базы равны ({len(by_name)})",
          set(by_name) == set(db_by_name),
          f"только в разборе: {names(sorted(set(by_name) - set(db_by_name)))}; только в "
          f"базе: {names(sorted(set(db_by_name) - set(by_name)))}")

    mismatches = []
    for name in sorted(set(by_name) & set(db_by_name)):
        parsed_row, db_row = by_name[name], db_by_name[name]
        for field in PARAMETER_COMPARE_FIELDS:
            left, right = normalize(parsed_row.get(field)), normalize(db_row.get(field))
            if field.endswith("uuid"):
                left = str(left or "").lower() or None
                right = str(right or "").lower() or None
            if left != right:
                mismatches.append(f"{name}.{field}: разбор {_brief(left)}, база "
                                  f"{_brief(right)}")
    check(f"{tag}: {len(PARAMETER_COMPARE_FIELDS)} полей каждой строки совпадают с разбором",
          not mismatches, "; ".join(mismatches[:6]))

    synonym_diff = []
    for name in sorted(set(by_name) & set(db_by_name)):
        if by_name[name].get("synonym") != db_by_name[name].get("synonym"):
            synonym_diff.append(f"{name}: {_brief(by_name[name].get('synonym'))} ↔ "
                                f"{_brief(db_by_name[name].get('synonym'))}")
    check(f"{tag}: многоязычный синоним (`synonym` jsonb) сохранён без правок (замер 2 "
          "плана: `Synonym` есть во всех файлах круга, пустых ноль)", not synonym_diff,
          "; ".join(synonym_diff[:4]))

    culprit_diff = []
    for name in sorted(set(by_name) & set(db_by_name)):
        parsed_culprits = by_name[name].get("unknown_property_names")
        db_culprits = db_by_name[name].get("unknown_property_names")
        if parsed_culprits is None:
            ok = db_culprits is None
        else:
            ok = [str(v) for v in (db_culprits or [])] == [str(v) for v in parsed_culprits]
        if not ok:
            culprit_diff.append(f"{name}: {_brief(parsed_culprits)} ↔ {_brief(db_culprits)}")
    check(f"{tag}: пустой перечень виновников — NULL, а не пустой массив (CHECK "
          "`functional_option_parameters_properties_state_matches_unknown`)", not culprit_diff,
          "; ".join(culprit_diff[:4]))

    # Состояния из сводки разбора сравниваются с построчным группированием базы: один и тот
    # же круг, посчитанный двумя способами (приём V50/V54/V55/V56).
    for column in sorted(STATE_VOCABULARIES):
        if column not in ("properties_state", "use_state"):
            continue   # состояния применения сравнивает контур 5
        parsed_counts = Counter(str(row.get(column)) for row in parsed_rows)
        db_counts = Counter(str(row[column]) for row in db_rows)
        check(f"{tag}: состояния колонки `{column}` в разборе и в базе совпадают",
              parsed_counts == db_counts,
              f"разбор: {dict(parsed_counts)}, база: {dict(db_counts)}")
        outside = set(db_counts) - set(STATE_VOCABULARIES[column])
        check(f"{tag}: состояний колонки `{column}` вне замкнутого словаря в базе нет",
              not outside, f"вне словаря: {names(sorted(outside))}")

    # Индексное имя вида и путь источника — те же ключи, что подтверждают строку выгрузкой
    # (правило V43). Форма ключа различается намеренно: `full_name` строки вида держит
    # короткое имя (иерархии раскладки у вида нет — замер 1.2, прецедент V48/V50/V56), а
    # индексное имя `FunctionalOptionsParameter.<Имя>` несёт строка применения в
    # `parameter_full_name` — её сверяет контур 7.
    naming_diff = []
    for row in db_rows:
        if str(row["full_name"]) != str(row["object_name"]):
            naming_diff.append(f"{row['full_name']!r} ≠ {row['object_name']!r}")
        if not str(row["source_path"]).startswith(DIR_NAME + "/"):
            naming_diff.append(f"{row['object_name']}: путь {_brief(row['source_path'])}")
    check(f"{tag}: `full_name` строки вида равна `object_name` (иерархии раскладки у вида "
          f"нет — замер 1.2), индексное имя `{INDEX_NAME_PREFIX}…` несёт строка применения, "
          f"а `source_path` лежит в каталоге `{DIR_NAME}/` — расхождений ноль",
          not naming_diff, "; ".join(naming_diff[:5]))

    # Состояние свойств корпуса замкнуто измеренным словарём из 14 файлов: незнакомых тегов
    # и значений корпус не давал (замер 2, 1.5), и это проверяемое утверждение, а не
    # предположение. Нули `unknown_*` называются, а не молчат (M7).
    unknown_states = [str(row["properties_state"]) for row in db_rows
                      if str(row["properties_state"]) != PROPS_ALL_KNOWN]
    check(f"{tag}: состояний свойств кроме `{PROPS_ALL_KNOWN}` — ноль (замер 2 плана: "
          f"словарь четырёх тегов во всех {expect['files']} файлах; незнакомый тег остался бы "
          "именем в `unknown_property_names`, а не отказом записи)",
          not unknown_states and int(parsed.get("unknown_properties_total") or 0) == 0
          and not (parsed.get("unknown_properties") or {})
          and not (parsed.get("unexpected_tags") or {}),
          f"состояния: {names(unknown_states)}, сводка разбора: "
          f"{_brief(parsed.get('unknown_properties'))}")

    # Кратность перечня — свойство вида (до 20 целей на параметр, замер 2.1): счётчик
    # `targets_count` обязан равняться числу строк применения, а максимум — эталону.
    counts_by_parameter = Counter()
    for row in db_rows:
        counts_by_parameter[str(row["full_name"])] = int(row["targets_count"] or 0)
    max_count = max(counts_by_parameter.values()) if counts_by_parameter else 0
    sum_counts = sum(counts_by_parameter.values())
    # Различия адресов считаются по разбору (строки применения сравниваются с базой в
    # контуре 5): здесь важно, что счётчик строки вида не расходится с кратностью перечня.
    distinct_targets = {str(row.get("target_full_name") or "")
                        for row in parsed.get("targets") or []}
    check(f"{tag}: максимум целей на параметр — {expect['max_targets']}, сумма счётчиков — "
          f"{expect['targets']}, различных целей — {expect['distinct']} (замер 2.1, M3)",
          max_count == expect["max_targets"] == int(parsed.get(MAX_TARGETS_KEY) or 0)
          and sum_counts == expect["targets"]
          and len(distinct_targets) == expect["distinct"],
          f"максимум: {max_count}, сумма: {sum_counts}, различных: {len(distinct_targets)}, "
          f"разбор: {parsed.get(MAX_TARGETS_KEY)}")
    use_with = sum(1 for row in db_rows if str(row["use_state"]) == USE_WITH)
    use_empty = sum(1 for row in db_rows if str(row["use_state"]) == USE_EMPTY)
    check(f"{tag}: состояний перечня `{USE_WITH}` — {expect['use_with']}, `{USE_EMPTY}` — "
          f"{expect['use_empty']}; пустой перечня был бы строкой вида с состоянием, а не "
          "исчезнувшей строкой (M3, Q6 вариант A)",
          use_with == expect["use_with"] and use_empty == expect["use_empty"]
          and use_with + use_empty == len(db_rows),
          f"with: {use_with}, empty: {use_empty}, строк: {len(db_rows)}")


# ── контур 5: строки применения против элементов `<Use>` файла (независимая мера) ─────────────
def plain_parameter_name(full_name):
    """Имя вида по индексному имени строки применения: префикс вида снимается тем же
    разделителем, каким он ставится (`INDEX_NAME_SEPARATOR`)."""
    value = str(full_name)
    prefix = f"{INDEX_OBJECT_TYPE}{INDEX_NAME_SEPARATOR}"
    return value[len(prefix):] if value.startswith(prefix) else value


def compare_target_rows(parsed, target_rows, db_rows, raw, expect, tag):
    section(f"Контур 5 — строки применения против перечня `<Use>` файла ({tag})")
    parsed_targets = parsed["targets"]
    raw_items = raw["items_by_name"]
    raw_total = sum(len(v) for v in raw_items.values())
    check(f"{tag}: строк применения — {expect['targets']} (замер 2.1 плана)",
          len(target_rows) == expect["targets"] == len(parsed_targets),
          f"база: {len(target_rows)}, разбор: {len(parsed_targets)}")
    check(f"{tag}: элементов `<Use><{USE_ITEM_TAG}>` по тексту файлов — {raw_total}, строк "
          "применения в базе столько же (мера M2: ни цели, ни порядка не потеряно)",
          raw_total == len(target_rows) == expect["targets"],
          f"файлы: {raw_total}, база: {len(target_rows)}")

    parsed_keys = sorted((str(r[PARAMETER_LINK_KEY]), int(r["ordinal"]),
                          str(r["target_full_name"])) for r in parsed_targets)
    db_keys = sorted((str(r[PARAMETER_LINK_KEY]), int(r["ordinal"]),
                      str(r["target_full_name"])) for r in target_rows)
    only_parsed = [f"{k[0]}#{k[1]}" for k in parsed_keys if k not in set(db_keys)]
    only_db = [f"{k[0]}#{k[1]}" for k in db_keys if k not in set(parsed_keys)]
    check(f"{tag}: ключи строк применения (параметр, порядок, адрес цели) совпадают с "
          "разбором", parsed_keys == db_keys,
          f"только в разборе: {names(only_parsed)}; только в базе: {names(only_db)}")

    parsed_index = {(str(r[PARAMETER_LINK_KEY]), int(r["ordinal"])): r
                    for r in parsed_targets}
    value_diff = []
    for row in target_rows:
        key = (str(row[PARAMETER_LINK_KEY]), int(row["ordinal"]))
        parsed_row = parsed_index.get(key)
        if parsed_row is None:
            value_diff.append(f"{key[0]}#{key[1]}: строки нет в разборе")
            continue
        for field in TARGET_COMPARE_FIELDS:
            left, right = normalize(parsed_row.get(field)), normalize(row.get(field))
            if field.endswith("uuid"):
                left = str(left or "").lower() or None
                right = str(right or "").lower() or None
            if left != right:
                value_diff.append(f"{key[0]}#{key[1]}.{field}: разбор {_brief(left)} ↔ база "
                                  f"{_brief(right)}")
    check(f"{tag}: {len(TARGET_COMPARE_FIELDS)} полей каждой строки применения совпадают с "
          "разбором (порядок, тег элемента, `xsi:type` и его состояние, адрес, вид цели, "
          "форма адреса, ссылка индекса, остаток пути, состояние разрешения)",
          not value_diff, "; ".join(value_diff[:6]))

    # Файл ↔ база: адрес цели и порядок по позициям элементов. Ключ — имя вида из `<Name>`
    # файла против `parameter_full_name` строки применения.
    db_by_parameter = {}
    for row in target_rows:
        db_by_parameter.setdefault(plain_parameter_name(row[PARAMETER_LINK_KEY]),
                                  []).append(row)
    file_diff = []
    for parameter_name, items in sorted(raw_items.items()):
        rows = sorted(db_by_parameter.get(parameter_name, []), key=lambda r: int(r["ordinal"]))
        if len(rows) != len(items):
            file_diff.append(f"{parameter_name}: элементов {len(items)}, строк {len(rows)}")
            continue
        for item, row in zip(items, rows):
            if str(row["target_full_name"]) != item["target_full_name"]:
                file_diff.append(f"{parameter_name}: адрес {_brief(row['target_full_name'])} "
                                 f"↔ {_brief(item['target_full_name'])}")
            if int(row["ordinal"]) != item["position"]:
                file_diff.append(f"{parameter_name}: порядок {row['ordinal']} ≠ позиции "
                                 f"{item['position']} в файле")
            if str(row["item_tag"]) != item["item_tag"]:
                file_diff.append(f"{parameter_name}: тег элемента {_brief(row['item_tag'])} "
                                 f"↔ {_brief(item['item_tag'])}")
            stored_attr = row["item_type_attr"]
            if str(stored_attr or "") != str(item["item_type_attr"] or ""):
                file_diff.append(f"{parameter_name}: `xsi:type` {_brief(stored_attr)} ↔ "
                                 f"{_brief(item['item_type_attr'])}")
    check(f"{tag}: адрес цели, порядок, тег элемента и значение `xsi:type` каждой строки "
          "применения равны элементу файла (признака применения `xr:Use` у элемента нет — "
          "колонок под него узел V57 не заводил, замер 2.1)", not file_diff,
          "; ".join(file_diff[:5]))

    ordinal_diff = []
    for parameter_name, rows in sorted(db_by_parameter.items()):
        orders = [int(row["ordinal"]) for row in rows]
        if orders != list(range(len(orders))):
            ordinal_diff.append(f"{parameter_name}: {orders}")
    check(f"{tag}: порядки целей непрерывны от 0 внутри каждого параметра (CHECK "
          "`functional_option_parameter_targets_parameter_ordinal_key` и порядок перечня "
          "`<Use>`)", not ordinal_diff, "; ".join(ordinal_diff[:5]))

    # Инвариант пары «строка вида ↔ строки применения» (CHECK
    # `functional_option_parameters_use_state_matches_targets`): счётчик и состояние
    # выводятся из числа строк, а не из догадки разбора.
    invariant_diff = []
    for row in db_rows:
        actual = len(db_by_parameter.get(plain_parameter_name(row["full_name"]), []))
        if int(row["targets_count"] or 0) != actual:
            invariant_diff.append(f"{row['full_name']}: счётчик {row['targets_count']}, "
                                  f"строк {actual}")
        expected_state = USE_WITH if actual else USE_EMPTY
        if str(row["use_state"]) != expected_state:
            invariant_diff.append(f"{row['full_name']}: состояние {row['use_state']}, "
                                  f"строк {actual}")
    check(f"{tag}: нарушений инварианта пары (счётчик и состояние против числа строк "
          "применения) — ноль", not invariant_diff, "; ".join(invariant_diff[:5]))
    check(f"{tag}: сводка разбора не сообщает нарушений инварианта (их читает состояние, а "
          "не потерянная строка)",
          int(parsed.get("invariant_violations_total") or 0) == 0
          and not (parsed.get("invariant_violations") or []),
          f"разбор: {_brief(parsed.get('invariant_violations'))}")

    # Состояния применения: разбор ↔ база построчно (один круг, посчитанный двумя
    # способами), и распределение форм адреса / классов цели — по эталонам замера 2.1.
    for column in ("target_resolve_state", "target_address_form", "item_type_state"):
        parsed_counts = Counter(str(row.get(column)) for row in parsed_targets)
        db_counts = Counter(str(row[column]) for row in target_rows)
        check(f"{tag}: состояния колонки `{column}` в разборе и в базе совпадают",
              parsed_counts == db_counts,
              f"разбор: {dict(parsed_counts)}, база: {dict(db_counts)}")
        outside = set(db_counts) - set(STATE_VOCABULARIES[column])
        check(f"{tag}: состояний колонки `{column}` вне замкнутого словаря в базе нет",
              not outside, f"вне словаря: {names(sorted(outside))}")

    resolve_states = Counter(str(row["target_resolve_state"]) for row in target_rows)
    check(f"{tag}: разрешение целей — `{TARGET_EXACT}` {expect['target_exact']}; состояний "
          f"`{TARGET_PREFIX_ONLY}`, `{TARGET_UNRESOLVED}`, `{TARGET_EMPTY_VALUE}` — ноль "
          "(замер 2.1: разрешено индексом 34 из 34; «разрешено индексом» не утверждает "
          "существование объекта в базе — Q3)",
          resolve_states.get(TARGET_EXACT, 0) == expect["target_exact"]
          and resolve_states.get(TARGET_PREFIX_ONLY, 0) == 0
          and resolve_states.get(TARGET_UNRESOLVED, 0) == 0
          and resolve_states.get(TARGET_EMPTY_VALUE, 0) == 0
          and sum(resolve_states.values()) == len(target_rows),
          f"факт: {dict(resolve_states)}")

    forms = Counter(str(row["target_address_form"]) for row in target_rows)
    expected_forms = {ADDRESS_FORM_DIMENSION: expect["dimension"],
                      ADDRESS_FORM_OBJECT: expect["object"]}
    wrong_forms = [f"{form}: {count} ≠ {expected_forms.get(form, 0)}"
                   for form, count in sorted(forms.items())
                   if forms[form] != expected_forms.get(form, 0)]
    check(f"{tag}: формы адреса цели — `{ADDRESS_FORM_DIMENSION}` {expect['dimension']}, "
          f"`{ADDRESS_FORM_OBJECT}` {expect['object']}, прочих форм ноль (замер 2.1, M5: "
          "`InformationRegister.X` и `InformationRegister.X.Dimension.Y` — разные носители "
          "значения параметра)",
          not wrong_forms
          and sum(forms.values()) == len(target_rows)
          and forms.get(ADDRESS_FORM_REGISTER_RESOURCE, 0) == 0
          and forms.get(ADDRESS_FORM_ATTRIBUTE, 0) == 0
          and forms.get(ADDRESS_FORM_TABULAR_SECTION, 0) == 0
          and forms.get(ADDRESS_FORM_OTHER, 0) == 0
          and forms.get(ADDRESS_FORM_EMPTY, 0) == 0,
          f"факт: {dict(forms)}")
    check(f"{tag}: независимая мера по тексту файлов называет те же формы адреса, что и база",
          dict(raw["forms"]) == dict(forms),
          f"файлы: {dict(raw['forms'])}, база: {dict(forms)}")

    kinds = Counter(str(row["target_object_type"]) for row in target_rows)
    expected_kinds = EXPECTED_KINDS_BY_DUMP.get(tag, {})
    wrong_kinds = [f"{kind}: {count} ≠ {expected_kinds.get(kind, 0)}" for kind, count
                   in sorted(kinds.items()) if kinds[kind] != expected_kinds.get(kind, 0)]
    absent_kinds = sorted(kind for kind, count in expected_kinds.items() if not kinds.get(kind))
    check(f"{tag}: классов цели перечня — {len(expected_kinds)} "
          f"({', '.join(f'{k} {v}' for k, v in sorted(expected_kinds.items()))}) — "
          "распределение поимённое (замер 2.1 плана)",
          not wrong_kinds and not absent_kinds and sum(kinds.values()) == len(target_rows),
          f"факт: {dict(kinds)}")
    check(f"{tag}: независимая мера по тексту файлов называет те же классы цели, что и база",
          dict(raw["kinds"]) == dict(kinds),
          f"файлы: {dict(raw['kinds'])}, база: {dict(kinds)}")

    item_tags = Counter(str(row["item_tag"]) for row in target_rows)
    item_states = Counter(str(row["item_type_state"]) for row in target_rows)
    # Ожидаемые словари строятся по замеру выгрузки, а не по факту прогона: пустой круг
    # (KomMag — вида нет ни файлами, ни записями, замер 1.1) обязан читаться пустыми
    # словарями, а не проваливать проверку условием «первый ключ равен Item». Нули состояний
    # в сравнении остаются намеренно: «состояния нет» и «состояние не считалось» — разные
    # ответы (C2), а незнакомый тег или состояние называются отдельным множеством.
    want_tags = {USE_ITEM_TAG: expect["item_ref"]} if expect["item_ref"] else {}
    want_states = {ITEM_TYPE_STATE_REF: expect["item_ref"],
                   ITEM_TYPE_STATE_OTHER: expect["item_other_form"],
                   ITEM_TYPE_STATE_ABSENT: expect["item_absent"]}
    extra_tags = sorted(set(item_tags) - set(want_tags))
    extra_states = sorted(set(item_states) - set(want_states))
    got_states = {state: item_states.get(state, 0) for state in want_states}
    shape_note = (f"элементов перечня в выгрузке нет — ни тегов, ни состояний "
                  f"(пустой круг, замер 1.1)" if not expect["item_ref"] else
                  f"тег `{USE_ITEM_TAG}` с `xsi:type: {ITEM_TYPE_REF_VALUE}` на "
                  f"{expect['item_ref']} строках; иных значений атрибута "
                  f"(`{ITEM_TYPE_STATE_OTHER}` {expect['item_other_form']}) и отсутствующего "
                  f"атрибута (`{ITEM_TYPE_STATE_ABSENT}` {expect['item_absent']}) — ноль")
    check(f"{tag}: форма элемента перечня — {shape_note}; незнакомых тегов и состояний ноль "
          "(замер 2.1, M6: элемент НЕ `<xr:Object>`, как у позиции 2.11 и 2.5, а `<xr:Item "
          "xsi:type=\"xr:MDObjectRef\">` с адресом цели текстом)",
          dict(item_tags) == want_tags and got_states == want_states
          and not extra_tags and not extra_states,
          f"теги: {dict(item_tags)}, состояния: {dict(item_states)}, "
          f"незнакомых тегов: {names(extra_tags)}, состояний: {names(extra_states)}")
    check(f"{tag}: независимая мера по файлам называет тот же тег и то же значение `xsi:type`"
          f", что и база ({expect['item_ref']} элементов)",
          dict(raw["item_tags"]) == ({USE_ITEM_TAG: expect["item_ref"]} if expect["item_ref"]
                                     else {})
          and dict(raw["item_types"]) == ({ITEM_TYPE_REF_VALUE: expect["item_ref"]}
                                          if expect["item_ref"] else {}),
          f"файлы: теги {dict(raw['item_tags'])}, атрибут {dict(raw['item_types'])}")
    check(f"{tag}: максимум элементов `<Use>` в одном файле — {expect['max_targets']} "
          f"(кратность перечня: от 1 до {expect['max_targets']} целей)",
          raw["max_items_per_file"] == expect["max_targets"],
          f"файлы: {raw['max_items_per_file']}")
    check(f"{tag}: пустых перечней `<Use/>` по файлам — {expect['use_empty']}, блоков "
          f"`<Use>` — {expect['use_with']}; состояние `{USE_EMPTY}` остаётся границей "
          "разбора, а не наблюдением (M3, прецедент V53 по пустому блоку источников)",
          raw["empty_use_files"] == expect["use_empty"]
          and raw["use_blocks"] == expect["use_with"],
          f"пустых: {raw['empty_use_files']}, блоков: {raw['use_blocks']}")


# ── контур 6: разрешимость целей индексом состава ЭТОЙ конфигурации ───────────────────────────
def check_resolution(cur, target_rows, header, expect, tag):
    section(f"Контур 6 — разрешение целей перечня индексом состава ({tag})")
    index_info = read_index_records(cur, int(header["id"]))
    if not index_info["available"]:
        skip(f"{tag}: разрешимость целей перепроверяется строками индекса состава",
             str(index_info.get("reason") or "индекс состава недоступен"))
        return
    by_name = index_rows_by_name(index_info["rows"])
    check(f"{tag}: индекс состава прочитан из `configuration_objects` ({index_info['row_count']} "
          f"строк, {index_info['kind_count']} видов) — повторный разбор `ConfigDumpInfo.xml` "
          "вторым источником не становится (правило V43); ключом служит полное точечное имя",
          index_info["row_count"] == len(index_info["rows"]) and len(by_name) > 0,
          f"строк: {index_info['row_count']}, ключей: {len(by_name)} "
          "(различие — коллизии полных имён внутри выгрузки)")

    resolve_diff = []
    matched_index_rows = []
    for row in target_rows:
        target = str(row["target_full_name"])
        got = resolve_reference(target, by_name)
        matched_index_rows.append((target, by_name.get(target)))
        if got["state"] != str(row["target_resolve_state"]):
            resolve_diff.append(f"{target}: состояние {got['state']} ↔ "
                                f"{row['target_resolve_state']}")
        if str(got["object_id"] or "") != str(row["target_object_id"] or ""):
            resolve_diff.append(f"{target}: `object_id` {_brief(got['object_id'])} ↔ "
                                f"{_brief(row['target_object_id'])}")
        got_uuid = str(got["object_uuid"] or "").lower() or None
        db_uuid = str(row["target_object_uuid"] or "").lower() or None
        if got_uuid != db_uuid:
            resolve_diff.append(f"{target}: `object_uuid` {_brief(got_uuid)} ↔ "
                                f"{_brief(db_uuid)}")
        if str(got["unresolved_path"] or "") != str(row["target_unresolved_path"] or ""):
            resolve_diff.append(f"{target}: остаток пути {_brief(got['unresolved_path'])} ↔ "
                                f"{_brief(row['target_unresolved_path'])}")
    check(f"{tag}: каждая цель разрешена ЗАНОВО по строкам индекса этой конфигурации — "
          "состояние, `object_id`, `object_uuid` и остаток пути совпадают с сохранёнными",
          not resolve_diff, "; ".join(resolve_diff[:6]))
    check(f"{tag}: разрешение полное — {expect['target_exact']} целей состоянием "
          f"`{TARGET_EXACT}`; `{TARGET_PREFIX_ONLY}` и `{TARGET_UNRESOLVED}` — ноль (замер "
          "2.1: 34 из 34). Нули называются, а не молчат: они и есть утверждение Q3 о том, "
          "что срез `.Dimension.` индексируется псевдозаписью",
          all(str(row["target_resolve_state"]) == TARGET_EXACT for row in target_rows)
          and len(target_rows) == expect["target_exact"],
          f"факт: {Counter(str(row['target_resolve_state']) for row in target_rows)}")

    # Верхний сегмент адреса обязан совпадать с видом разрешившей строки индекса: иначе
    # колонка `target_object_type` описывала бы адрес, а не то, чем цель разрешается. Ключом
    # строки индекса служит ПОЛНОЕ точечное имя (`name`), а не короткое `object_name` —
    # урок узла V48, повторённый разбором V50/V52/V56: по короткому имени псевдозапись среза
    # читалась бы как «записи индекса нет».
    kind_mismatch = []
    for target, index_row in matched_index_rows:
        if index_row is None:
            kind_mismatch.append(f"{target}: строки индекса нет")
            continue
        if index_row_key(index_row) != target:
            kind_mismatch.append(f"{target}: ключ индекса "
                                 f"{_brief(index_row_key(index_row))}")
        if str(index_row["object_type"]) != target.split(INDEX_NAME_SEPARATOR)[0]:
            kind_mismatch.append(f"{target}: вид индекса {_brief(index_row['object_type'])}")
    check(f"{tag}: каждая цель разрешена строкой индекса с тем же полным именем и тем же "
          "верхним сегментом вида, что и `target_object_type`", not kind_mismatch,
          "; ".join(kind_mismatch[:6]))

    # Форма адреса и вид цели пересчитываются по адресу цели ЗАНОВО — теми же функциями,
    # которыми они вычислялись при загрузке, и сравниваются со строкой: колонки обязаны
    # описывать адрес, а не сохраняться как написание из файла (CHECK
    # `..._targets_type_matches_name` и `..._targets_form_matches_name` держат это в схеме).
    form_diff = []
    kind_diff = []
    for row in target_rows:
        target = str(row["target_full_name"])
        if target_address_form(target) != str(row["target_address_form"]):
            form_diff.append(f"{target}: {_brief(target_address_form(target))} ↔ "
                             f"{_brief(row['target_address_form'])}")
        if target_object_type(target) != str(row["target_object_type"]):
            kind_diff.append(f"{target}: {_brief(target_object_type(target))} ↔ "
                             f"{_brief(row['target_object_type'])}")
    check(f"{tag}: форма адреса цели пересчитана по адресу и совпадает с колонкой "
          "`target_address_form`", not form_diff, "; ".join(form_diff[:6]))
    check(f"{tag}: вид цели пересчитан по верхнему сегменту и совпадает с колонкой "
          "`target_object_type`", not kind_diff, "; ".join(kind_diff[:6]))

    # Псевдозаписи срезов — то, чем разрешается цель вида 2.12: без них 30 целей из 34
    # остались бы `prefix_only`. Мера называется отдельной строкой, потому что именно она
    # объясняет, почему разрешение ведётся по ВСЕМ строкам индекса, а не по строкам своего
    # вида (отличие от V56, где цели перечня `.Resource.`/`.Attribute.` вёли на те же срезы).
    slice_markers = tuple(marker for marker, _form in SLICE_MARKERS)
    slice_targets = [target for target, _row in matched_index_rows
                     if any(marker in target for marker in slice_markers)]
    check(f"{tag}: целей-срезов (адрес содержит маркер {names(sorted(slice_markers), 4)}) — "
          f"{len(slice_targets)}, и каждая разрешена псевдозаписью индекса состоянием "
          f"`{TARGET_EXACT}` (замер 2.1 плана: срез `.Dimension.` — {expect['dimension']} "
          "целей)",
          len(slice_targets) == expect["dimension"]
          and all(by_name.get(target) is not None for target in slice_targets),
          f"срезов: {len(slice_targets)}, ожидание: {expect['dimension']}")
    whole_objects = [str(row["target_full_name"]) for row in target_rows
                     if str(row["target_address_form"]) == ADDRESS_FORM_OBJECT]
    check(f"{tag}: целей «сам объект» (форма `{ADDRESS_FORM_OBJECT}`, ровно два сегмента) — "
          f"{expect['object']}, и каждая разрешена строкой индекса самого объекта",
          len(whole_objects) == expect["object"]
          and all(by_name.get(target) is not None for target in whole_objects),
          f"факт: {len(whole_objects)}, ожидание: {expect['object']}")


# ── контур 7: витрины текущего состояния, цепь ревизий, сироты, дублирующие колонки ───────────
def view_definition(cur, view):
    row = one(cur, "SELECT pg_get_viewdef(%s::regclass, true) AS def", (view,))
    return str(row.get("def") or "") if row else ""


def check_revisions_and_views(cur):
    section("Контур 7 — витрины текущего состояния, цепь ревизий и сироты")
    current_direct = scalar(
        cur, f"SELECT count(*) FROM {TABLE_NAME} o WHERE NOT exists("
             f"SELECT 1 FROM {TABLE_NAME} n WHERE n.configuration_uuid = o.configuration_uuid "
             f"AND n.object_name = o.object_name AND n.revision_no > o.revision_no)")
    in_view = int(scalar(cur, f"SELECT count(*) FROM {PARAMETER_VIEW}") or 0)
    check(f"витрина `{PARAMETER_VIEW}` отдаёт ровно строки максимальной ревизии по ключу "
          f"цепочки ({current_direct} строк) — правило узла V19, а не `max()` вызывающего",
          current_direct == in_view,
          f"максимальных ревизий: {current_direct}, в витрине: {in_view}")
    outside = scalar(cur, f"SELECT count(*) FROM {TABLE_NAME} o WHERE NOT exists("
                          f"SELECT 1 FROM {PARAMETER_VIEW} v WHERE v.id = o.id)")
    check(f"строк `{TABLE_NAME}` вне витрины текущего состояния — ноль (мера "
          f"{CORPUS_TOTALS['outside_views']} плана раздела 7)", not outside,
          f"вне витрины: {outside}")

    header_orphans = scalar(
        cur, f"SELECT count(*) FROM {TABLE_NAME} o WHERE NOT exists("
             "SELECT 1 FROM configurations c WHERE c.uuid = o.configuration_uuid)")
    check("строк вида без заголовка конфигурации — ноль (внешнего ключа нет осознанно — "
          "прецеденты V20.1, V44, V46, V48…V56; сироту считает проверка, а не схема)",
          not header_orphans, f"сирот: {header_orphans}")

    index_orphans = scalar(
        cur, f"SELECT count(*) FROM {TABLE_NAME} o WHERE NOT exists("
              "SELECT 1 FROM configurations c "
              f"JOIN {INDEX_TABLE} i ON i.configuration_id = c.id "
              "WHERE c.uuid = o.configuration_uuid AND i.object_type = %s "
              "AND i.parent_name IS NULL AND i.uuid = o.object_uuid)", (INDEX_OBJECT_TYPE,))
    check("строка вида обязана соответствовать записи индекса состава той же конфигурации "
          "(подтверждение по живой БД, правило V43) — расхождений ноль", not index_orphans,
          f"без записи индекса: {index_orphans}")

    # Строка применения версионируется НЕ своей цепью (Q2, вариант A): ключ начинается с
    # числового id конкретной ревизии вида. Значит она обязана висеть на ТЕКУЩЕЙ ревизии —
    # иначе витрина применения показала бы состав, которого в выгрузке нет, а каскад не
    # сработал бы при снятии строки вида (M7).
    stale_children = scalar(
        cur, f"SELECT count(*) FROM {TARGETS_TABLE_NAME} c JOIN {TABLE_NAME} o "
             f"ON o.id = c.{PARAMETER_FK_COLUMN} WHERE exists(SELECT 1 FROM {TABLE_NAME} n "
             "WHERE n.configuration_uuid = o.configuration_uuid "
             "AND n.object_name = o.object_name AND n.revision_no > o.revision_no)")
    check(f"строк применения, висящих на не-текущей ревизии вида, — ноль (связь держит id "
          "конкретной ревизии, а не пару uuid+имя — Q2, вариант A)", not stale_children,
          f"таких строк: {stale_children}")
    child_orphans = scalar(
        cur, f"SELECT count(*) FROM {TARGETS_TABLE_NAME} c WHERE NOT exists("
             f"SELECT 1 FROM {TABLE_NAME} o WHERE o.id = c.{PARAMETER_FK_COLUMN})")
    check(f"сирот в `{TARGETS_TABLE_NAME}` (строка применения без строки вида) — ноль (мера "
          f"{CORPUS_TOTALS['orphans']} плана)", not child_orphans, f"сирот: {child_orphans}")
    targets_outside = scalar(
        cur, f"SELECT count(*) FROM {TARGETS_TABLE_NAME} c WHERE NOT exists("
             f"SELECT 1 FROM {TARGETS_VIEW} v WHERE v.id = c.id)")
    check(f"строк `{TARGETS_TABLE_NAME}` вне витрины `{TARGETS_VIEW}` — ноль",
          not targets_outside, f"вне витрины: {targets_outside}")

    # Дублирующие колонки слоя: `configuration_uuid`, `parameter_object_uuid` и
    # `parameter_full_name` строки применения обязаны совпадать с родительской строкой —
    # по ним читатель ищет круг, не проходя через родителя (Q2, вариант A). Форма указателя
    # при этом различается намеренно: строка применения несёт ИНДЕКСНОЕ имя
    # `FunctionalOptionsParameter.<Имя>`, а строка вида — короткое `full_name` (замер 1.2);
    # мост между двумя формами держит префикс разбора, а не догадка проверки.
    link_mismatch = scalar(
        cur, f"SELECT count(*) FROM {TARGETS_TABLE_NAME} c JOIN {TABLE_NAME} o "
             f"ON o.id = c.{PARAMETER_FK_COLUMN} "
             "WHERE c.configuration_uuid IS DISTINCT FROM o.configuration_uuid "
             "OR c.parameter_object_uuid IS DISTINCT FROM o.object_uuid "
             "OR c.parameter_full_name IS DISTINCT FROM %s || o.full_name",
        (INDEX_NAME_PREFIX,))
    check("дублирующие колонки строки применения (`configuration_uuid`, "
          "`parameter_object_uuid`, `parameter_full_name`) совпадают со строкой вида; "
          "`parameter_full_name` — индексное имя вида с префиксом разбора",
          not link_mismatch, f"расхождений: {link_mismatch}")

    # Повторной цели внутри одного перечня корпус не давал (замер 2.1: 34 адреса при 34
    # строках). Отдельного ограничения на уникальность цели в DDL нет осознанно: порядок
    # перечня (`ordinal`) является частью ключа, а повтор цели в файле был бы составом,
    # которого в выгрузке нет, — поэтому мера называется проверкой, а не схемой.
    repeated = q(cur, f"SELECT {PARAMETER_FK_COLUMN} AS parameter_id, target_full_name, "
                      f"count(*) AS n FROM {TARGETS_TABLE_NAME} GROUP BY {PARAMETER_FK_COLUMN}, "
                      "target_full_name HAVING count(*) > 1 ORDER BY count(*) DESC, "
                      f"{PARAMETER_FK_COLUMN}")
    check(f"повторов одного адреса цели внутри одного параметра — ноль (мера "
          f"{CORPUS_TOTALS['duplicate_targets']} плана; ключ держит порядок, а не адрес)",
          not repeated, "; ".join(f"параметр {row['parameter_id']}: {row['target_full_name']} "
                                  f"× {row['n']}" for row in repeated[:5]))

    # Состав витрин: витрина применения читается через витрину вида, а не через версионируемую
    # таблицу. Иначе строки не-текущей ревизии попали бы в ответ — тот же дефект, из-за
    # которого порядок снятия круга начинается с детей (M7).
    parameter_view_def = view_definition(cur, PARAMETER_VIEW)
    targets_view_def = view_definition(cur, TARGETS_VIEW)
    check(f"витрина `{PARAMETER_VIEW}` держится предиката «нет строки той же пары "
          "(`configuration_uuid`, `object_name`) с большим `revision_no`» (правило узла V19)",
          "revision_no" in parameter_view_def and "EXISTS" in parameter_view_def.upper(),
          _brief(parameter_view_def[:200]))
    check(f"витрина `{TARGETS_VIEW}` связывается с витриной `{PARAMETER_VIEW}`, а не с "
          f"версионируемой таблицей `{TABLE_NAME}`",
          PARAMETER_VIEW in targets_view_def
          and not re.search(r"(?<!v_current_)functional_option_parameters\b", targets_view_def),
          _brief(targets_view_def[:200]))
    for view in (PARAMETER_VIEW, TARGETS_VIEW):
        columns = table_columns(cur, view)
        check(f"`{view}`: колонка `configuration_uuid` открыта — предикат выбора круга "
              "читателя", "configuration_uuid" in columns, names(columns))
    exposed = set(table_columns(cur, PARAMETER_VIEW)) - set(table_columns(cur, TABLE_NAME))
    check(f"витрина вида не привносит колонок, которых нет в таблице (состав читается одним "
          "словарём)", not exposed, names(sorted(exposed)))
    exposed_targets = set(table_columns(cur, TARGETS_VIEW)) - set(
        table_columns(cur, TARGETS_TABLE_NAME))
    check(f"витрина применения не привносит колонок, которых нет в `{TARGETS_TABLE_NAME}`",
          not exposed_targets, names(sorted(exposed_targets)))

    # Чужие ключи: детей у вида, кроме собственной таблицы применения, нет; внешний ключ на
    # таблицы узла из чужих слоёв не заявлен ни одним узлом (позиция O1 плана).
    parents = q(cur, "SELECT conrelid::regclass::text AS child, conname FROM pg_constraint "
                     "WHERE contype = 'f' AND confrelid = %s::regclass "
                     "AND conrelid::regclass::text <> %s ORDER BY conname",
                (TABLE_NAME, TARGETS_TABLE_NAME))
    check(f"внешних ключей чужих таблиц на `{TABLE_NAME}` — ноль (ссылки других слоёв на вид "
          "разбирается отдельным узлом — позиция O1 плана V56)", not parents,
          "; ".join(f"{row['child']}.{row['conname']}" for row in parents[:5]))
    parents_targets = q(cur, "SELECT conrelid::regclass::text AS child, conname "
                             "FROM pg_constraint WHERE contype = 'f' "
                             "AND confrelid = %s::regclass ORDER BY conname",
                        (TARGETS_TABLE_NAME,))
    check(f"внешних ключей чужих таблиц на `{TARGETS_TABLE_NAME}` — ноль", not parents_targets,
          "; ".join(f"{row['child']}.{row['conname']}" for row in parents_targets[:5]))
    child_tables = sorted(str(row["child"]) for row in q(
        cur, "SELECT conrelid::regclass::text AS child FROM pg_constraint WHERE contype = 'f' "
             "AND confrelid = %s::regclass ORDER BY conrelid::regclass::text", (TABLE_NAME,)))
    check(f"таблиц, ссылающихся на `{TABLE_NAME}`, — ровно {len(child_tables)}: "
          f"`{TARGETS_TABLE_NAME}` (связь слоя держит FK с каскадом — Q11 узла V56)",
          child_tables == [TARGETS_TABLE_NAME], f"факт: {names(child_tables)}")

    deep = scalar(cur, f"SELECT count(*) FROM {TABLE_NAME} WHERE revision_no > 1")
    info(f"строк не первой ревизии в `{TABLE_NAME}`: {deep} (цепь узла V19 жива; перезагрузки "
         "со второй ревизией корпус не давал — замеры узла V57 делались одной загрузкой)")


# ── контур 8: контракт стадии, круга снятия и реестра сохранённых видов ────────────────────────
def check_contract():
    section("Контур 8 — контракт стадии, круга снятия и реестра сохранённых видов")
    ids = [stage for stage, _title in STAGES]
    check(f"стадия `{STAGE_FUNCTIONAL_OPTIONS_PARAMETERS}` стоит сразу после "
          f"`{STAGE_FUNCTIONAL_OPTIONS}` (позиции 2.11 → 2.12 нормативного списка, а не "
          "порядок литер)",
          ids.index(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS)
          == ids.index(STAGE_FUNCTIONAL_OPTIONS) + 1, f"порядок: {ids}")
    check(f"`{STAGE_OBJECT_MODULES}` остаётся последней стадией (вторая транзакция текстов), а "
          f"`{STAGE_FUNCTIONAL_OPTIONS_PARAMETERS}` стоит перед ней",
          ids[-1] == STAGE_OBJECT_MODULES
          and ids.index(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS) == len(ids) - 2,
          f"порядок: {ids}")
    check(f"`stages_after('{STAGE_FUNCTIONAL_OPTIONS}')` называет продолжением "
          f"`{STAGE_FUNCTIONAL_OPTIONS_PARAMETERS}`",
          stages_after(STAGE_FUNCTIONAL_OPTIONS)[:1] == [STAGE_FUNCTIONAL_OPTIONS_PARAMETERS],
          str(stages_after(STAGE_FUNCTIONAL_OPTIONS)))
    check(f"`stages_after('{STAGE_FUNCTIONAL_OPTIONS_PARAMETERS}')` называет продолжением "
          f"`{STAGE_OBJECT_MODULES}`",
          stages_after(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS)[:1] == [STAGE_OBJECT_MODULES],
          str(stages_after(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS)))
    check(f"у стадии `{STAGE_FUNCTIONAL_OPTIONS_PARAMETERS}` есть зеркало продолжения "
          "(`STAGE_FULL_RELOAD_ONLY` = False — стадия дозакрывается отдельным входом)",
          STAGE_FULL_RELOAD_ONLY.get(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS) is False,
          str(STAGE_FULL_RELOAD_ONLY.get(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS)))
    title = stage_title(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS)
    hint = stage_resume_hint(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS)
    check("заголовок стадии называет позицию 2.12 и каталог вида",
          "2.12" in title and DIR_NAME in title, _brief(title))
    check("подсказка продолжения называет отдельный вход "
          "`load_functional_options_parameters_tool` и полную перезагрузку",
          "load_functional_options_parameters_tool" in hint
          and "load_1c_catalog_tool" in hint, _brief(hint))
    check("подсказка продолжения равна константе круга (текст один, а не пересказ)",
          hint == FUNCTIONAL_OPTIONS_PARAMETERS_REPEAT_HINT, _brief(hint))
    check(f"круг записи стадии — две таблицы (`{TABLE_NAME}`, `{TARGETS_TABLE_NAME}`) — Q1, "
          "вариант A: строка применения существует только через строку параметра",
          tuple(FUNCTIONAL_OPTION_PARAMETERS_TABLES) == (TABLE_NAME, TARGETS_TABLE_NAME),
          str(FUNCTIONAL_OPTION_PARAMETERS_TABLES))
    check("круг снятия начинается с таблицы применения: FK объявлен с `ON DELETE CASCADE`, и "
          "каскад снял бы строки молча без точного счётчика (M7, прецеденты V50/V52/V54/V56)",
          tuple(FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER)
          == (TARGETS_TABLE_NAME, TABLE_NAME), str(FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER))
    check("обе таблицы круга названы в `FOREIGN_STAGE_TABLES` — иначе стадия S4 снимала бы "
          "чужие строки вида",
          all(table in FOREIGN_STAGE_TABLES
              for table in FUNCTIONAL_OPTION_PARAMETERS_TABLES),
          f"перечень: {names(FOREIGN_STAGE_TABLES)}")
    check("зеркальные имена таблиц контракта совпадают со словарём разбора (один круг, а не "
          "два перечня)",
          FUNCTIONAL_OPTION_PARAMETERS_TABLE == TABLE_NAME
          and FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE == TARGETS_TABLE_NAME,
          f"контракт: {FUNCTIONAL_OPTION_PARAMETERS_TABLE}/"
          f"{FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE}")
    entry = STORED_META_KINDS.get(FUNCTIONAL_OPTIONS_PARAMETERS_META_TAG) or {}
    check(f"вид `{FUNCTIONAL_OPTIONS_PARAMETERS_META_TAG}` назван сохранённым в реестре "
          f"`STORED_META_KINDS` кругом {tuple(FUNCTIONAL_OPTION_PARAMETERS_TABLES)} и "
          "позицией 2.12 — тем же словарём, которым пользуется карточка загрузки (прецедент "
          "V55, V56)",
          bool(entry)
          and tuple(entry.get("tables") or ()) == tuple(FUNCTIONAL_OPTION_PARAMETERS_TABLES)
          and str(entry.get("position")) == "2.12" and str(entry.get("node")) == "V57",
          f"запись реестра: {_brief(entry)}")
    check(f"словарь вида один: метка `{FUNCTIONAL_OPTIONS_PARAMETERS_META_TAG}` и каталог "
          f"`{FUNCTIONAL_OPTIONS_PARAMETERS_DIR}` контракта совпадают со словарём разбора; "
          "метка отличается от метки соседнего вида 2.11",
          FUNCTIONAL_OPTIONS_PARAMETERS_META_TAG == OBJECT_KIND_TAG == INDEX_OBJECT_TYPE
          and FUNCTIONAL_OPTIONS_PARAMETERS_DIR == DIR_NAME
          and FUNCTIONAL_OPTIONS_PARAMETERS_META_TAG != SIBLING_INDEX_OBJECT_TYPE,
          f"контракт: {FUNCTIONAL_OPTIONS_PARAMETERS_META_TAG}/"
          f"{FUNCTIONAL_OPTIONS_PARAMETERS_DIR}, разбор: {OBJECT_KIND_TAG}/{DIR_NAME}")
    check("граница круга называется константой, которую читают оба формата ответа: текст "
          "называет обе таблицы, точный `object_type` и расхождения ног",
          TABLE_NAME in FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_BOUNDARY
          and TARGETS_TABLE_NAME in FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_BOUNDARY
          and "2.12" in FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_BOUNDARY
          and all(key in FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_BOUNDARY
                  for key in CIRCLE_DISCREPANCIES),
          _brief(FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_BOUNDARY[:200]))
    check("заголовок раздела карточки называет узел V57 и позицию 2.12",
          "V57" in FUNCTIONAL_OPTIONS_PARAMETERS_SECTION_HEADER
          and "2.12" in FUNCTIONAL_OPTIONS_PARAMETERS_SECTION_HEADER,
          _brief(FUNCTIONAL_OPTIONS_PARAMETERS_SECTION_HEADER))

    # Закрытый контракт ответа (C1, C2, C3): нули обязаны быть названы по полному словарю,
    # иначе «стадия не выполнена» читается как «строк нет».
    defaults = functional_options_parameters_defaults()
    needed = set(SUMMARY_KEYS) | set(COUNT_KEYS)
    missing = sorted(key for key in needed if key not in defaults)
    check(f"нулевой контракт перечисляет все ключи сводки разбора ({len(needed)} ключей "
          "`SUMMARY_KEYS` и `COUNT_KEYS`)", not missing, names(missing))
    check("нулевой контракт называет круг снятия, стадию и каталог — ответ не зависит от удачи "
          "выгрузки",
          defaults.get("tables") == list(FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER)
          and defaults.get("stage") == STAGE_FUNCTIONAL_OPTIONS_PARAMETERS
          and defaults.get("directory") == DIR_NAME,
          f"tables: {_brief(defaults.get('tables'))}, stage: {defaults.get('stage')}")
    bad_counts = [f"{key} ≠ {COUNT_KEY_STATE_COLUMNS[key]}" for key in COUNT_KEYS
                  if sorted((defaults.get(key) or {}).keys())
                  != sorted(STATE_VOCABULARIES[COUNT_KEY_STATE_COLUMNS[key]])]
    check(f"словари состояний нулевого контракта построены по полному словарю колонок "
          f"({len(COUNT_KEYS)} словарей, включая `counts_by_target_address_form` → "
          "`target_address_form` и `counts_by_item_type_state` → `item_type_state`)",
          not bad_counts, "; ".join(bad_counts))
    check("нулевой контракт называет состояния колонок целиком: `state_columns()` равна "
          "перечню контракта",
          sorted(defaults.get("state_columns") or []) == sorted(STATE_VOCABULARIES),
          f"контракт: {names(sorted(defaults.get('state_columns') or []))}")
    numbers = {key: value for key, value in defaults.items()
               if isinstance(value, int) and not isinstance(value, bool)}
    check(f"числовые поля нулевого контракта равны нулю ({len(numbers)} полей) — «не "
          "выполнялась» не читается как «строк нет»",
          all(value == 0 for value in numbers.values()),
          f"ненулевые: {names(sorted(key for key, value in numbers.items() if value))}")
    check("нулевой контракт помечает стадию невыполненной (`success` False, статус ≠ успех)",
          defaults.get("success") is False and defaults.get("status") not in ("ok", True),
          f"status: {defaults.get('status')}")
    check("словари наблюдений и расхождений круга нулевого контракта построены по закрытым "
          "перечням слоя (отсутствие каталога — наблюдение, а не ноль строк — Q9)",
          sorted(defaults.get("counts_by_observation") or {}) == sorted(OBSERVATION_KINDS)
          and sorted(defaults.get("counts_by_circle_discrepancy") or {})
          == sorted(CIRCLE_DISCREPANCIES),
          f"наблюдения: {names(sorted(defaults.get('counts_by_observation') or []))}")

    # Три разных ответа форматтера (C1): «стадия не выполнена», «отказ разбора круга» и
    # «круг записан». Отличие от V56 названо отдельной проверкой: блока «группы круга не
    # запрашивались» у формата нет, потому что групп `kinds` у входа нет (Q5, вариант A).
    not_run = [str(line) for line in
               (format_functional_options_parameters_lines(defaults) or [])]
    check("форматтер невыполненной стадии называет сам факт («Стадия не выполнена») и чем "
          "продолжить, а не нули строк (C1)",
          bool(not_run) and any("Стадия не выполнена" in line for line in not_run)
          and any("load_functional_options_parameters_tool" in line for line in not_run),
          _brief(compact(not_run[:3])))
    check("форматтер невыполненной стадии не приписывает кругу строк: текст не утверждает "
          "«записано N» при N больше нуля",
          not any("записано" in line and any(digit in line for digit in "123456789")
                  for line in not_run), _brief(compact(not_run[:6])))
    failure = dict(functional_options_parameters_defaults())
    failure.update({"status": "error", "success": False,
                    "error": "Круг не записан: 2 файла каталога не разобраны",
                    "reason": "отказ разбора",
                    "files_failed": [{"source_path": f"{DIR_NAME}/Параметр.xml",
                                      "reason": "не читается XML"}]})
    failure_lines = [str(line) for line in
                     (format_functional_options_parameters_lines(failure) or [])]
    check("форматтер отказа разбора называет причину, останов ДО записи и файл-виновник: «не "
          "записано» и «нечего записывать» — разные ответы (C1, приём V12/V46…V56)",
          any("не разобраны" in line for line in failure_lines)
          and any("ДО записи" in line and TABLE_NAME in line for line in failure_lines)
          and any("Параметр.xml" in line for line in failure_lines),
          _brief(compact(failure_lines[:4])))
    invariant = dict(failure)
    invariant["files_failed"] = []
    invariant["invariant_violations"] = ["Параметр: счётчик 3, строк 2"]
    invariant["invariant_violations_total"] = 1
    invariant_lines = [str(line) for line in
                       (format_functional_options_parameters_lines(invariant) or [])]
    check("форматтер нарушения инварианта пары называет его отдельной строкой со ссылкой на "
          "CHECK `..._use_state_matches_targets`: связность круга проверяется ДО записи, и "
          "нарушение является состоянием, а не потерянной строкой (отличие от V56)",
          any("инвариант" in line.lower()
              and "functional_option_parameters_use_state_matches_targets" in line
              for line in invariant_lines), _brief(compact(invariant_lines[:5])))
    success = dict(functional_options_parameters_defaults())
    success.update({"status": "ok", "success": True})
    success_lines = [str(line) for line in
                     (format_functional_options_parameters_lines(success) or [])]
    check("форматтер называет каталог круга и обе таблицы с нулями даже при пустом ответе "
          "успеха: «записано 0» отличается от «стадия не выполнялась»",
          any(DIR_NAME in line for line in success_lines)
          and all(TABLE_NAME in line and TARGETS_TABLE_NAME in line
                  for line in success_lines if "записано" in line),
          _brief(compact(success_lines[:3])))
    check("форматтер печатает границу круга и при успехе: чужой вид `FunctionalOption` назван "
          "не входящим в круг, а разрешение цели не утверждается по факту записи (Q3)",
          any("FunctionalOption" in line and "в круг не берётся" in line
              for line in success_lines), _brief(compact(success_lines[:4])))
    kinds_block = [line for line in success_lines + not_run
                   if "группы круга" in line or "группы не запрашивались" in line]
    check("блока «группы круга не запрашивались» в формате нет — это решение Q5 (вариант A), "
          "а не пропуск: раздельного входа дозагрузки по группам у стадии нет",
          not kinds_block and "kinds" not in defaults,
          _brief(compact(kinds_block[:3])))


# ── контур 8.1: отдельный вход группы — регистрация в реестре MCP ─────────────────────────────
TOOL_NAME = "load_functional_options_parameters_tool"


def read_repo_text(rel_path):
    """Текст файла репозитория — реестр инструментов читается текстом, а не импортом.

    Импортировать `server_configurations_core.py` нельзя: импорт поднимает сервер MCP и его
    зависимости, а проверка обязана работать и без запущенного сервера. Состав реестра сторожит
    `tools/check_mcp_tool_wiring.py`, поэтому здесь сверяются два текста: объявление инструмента
    и запись в `EXPECTED_TOOLS`.
    """
    path = ROOT / rel_path
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def check_tool_registration():
    section("Контур 8.1 — регистрация отдельного входа в реестре MCP")
    server_text = read_repo_text("server_configurations_core.py")
    check(f"`{TOOL_NAME}` объявлен инструментом сервера `server_configurations_core.py` "
          "(`@mcp.tool()` — реестр, а не память)",
          f"def {TOOL_NAME}(" in server_text and "@mcp.tool" in server_text,
          _brief(f"def {TOOL_NAME}(: {'есть' if f'def {TOOL_NAME}(' in server_text else 'нет'}"
                 f", @mcp.tool: {'есть' if '@mcp.tool' in server_text else 'нет'})"))
    signature = ""
    marker = f"def {TOOL_NAME}("
    if marker in server_text:
        start = server_text.index(marker)
        signature = server_text[start:start + 600]
    check("сигнатура отдельного входа — `source_path` и необязательный `configuration_uuid`; "
          "параметра `kinds` у входа нет (Q5, вариант A: строка применения существует только "
          "через id строки параметра, порога цены для разреза круга замер 1.4 не дал)",
          "source_path" in signature and "configuration_uuid" in signature
          and "kinds" not in signature, _brief(signature[:300]))
    wiring_text = read_repo_text("tools/check_mcp_tool_wiring.py")
    check(f"`{TOOL_NAME}` внесён в `EXPECTED_TOOLS` файла `tools/check_mcp_tool_wiring.py` — "
          "состав реестра сторожит она, а не обещание подсказки продолжения",
          TOOL_NAME in wiring_text, f"файл: {ROOT / 'tools/check_mcp_tool_wiring.py'}")
    loader_text = read_repo_text("src/configuration_functional_options_parameters_loader.py")
    check("отдельный вход реализован слоем "
          "`src/configuration_functional_options_parameters_loader.py` "
          "(`load_functional_options_parameters`)",
          "def load_functional_options_parameters(" in loader_text,
          f"файл: {ROOT / 'src/configuration_functional_options_parameters_loader.py'}")
    pipeline_text = read_repo_text("src/configuration_loader.py")
    check(f"конвейер вызывает стадию `{STAGE_FUNCTIONAL_OPTIONS_PARAMETERS}` тем же слоем — "
          "отдельный вход и конвейер не два разных разбора. Стадия в конвейере названа "
          "константой контракта `STAGE_FUNCTIONAL_OPTIONS_PARAMETERS`, а не литералом: "
          "литерал имени стадии живёт одним местом — в `configuration_load_contract.py` "
          "(порядок `STAGES` сверяет контур 8)",
          "load_functional_options_parameters(" in pipeline_text
          and re.search(r"\bSTAGE_FUNCTIONAL_OPTIONS_PARAMETERS\b", pipeline_text)
          and f"'{STAGE_FUNCTIONAL_OPTIONS_PARAMETERS}'" not in pipeline_text
          and f'"{STAGE_FUNCTIONAL_OPTIONS_PARAMETERS}"' not in pipeline_text,
          f"файл: {ROOT / 'src/configuration_loader.py'}")
    router_text = read_repo_text("src/config_load_router.py")
    check("карточка загрузки печатает раздел стадии (заголовок и форматтер читаются из "
          "контракта, а не пересказываются)",
          "FUNCTIONAL_OPTIONS_PARAMETERS_SECTION_HEADER" in router_text
          and "format_functional_options_parameters_lines" in router_text,
          f"файл: {ROOT / 'src/config_load_router.py'}")


# ── контур 9: корпус, чужие круги и соседняя позиция 2.11 ─────────────────────────────────────
# Пары «мера прогона ↔ ключ эталона плана»: суммы по четырём выгрузкам сравниваются с
# разделами 1.1, 1.2 и 2.1 плана V57, а не с числом, выведенным из самого прогона.
CORPUS_KEYS = (
    ("files", "files"), ("bytes", "bytes"),
    ("index_records", "index_records"), ("sibling_index", "sibling_index"),
    ("prefix_mask", "prefix_mask"), ("root_names", "root_names"),
    ("header_names", "header_names"), ("header_null", "header_null"),
    ("db_rows", "db_rows"), ("targets", "targets"),
    ("distinct_sum", "distinct_sum"), ("max_targets", "max_targets"),
    ("target_exact", "target_exact"), ("dimension", "dimension"), ("object", "object"),
    ("use_with", "use_with"), ("use_empty", "use_empty"), ("item_ref", "item_ref"),
    ("empty_comment", "empty_comment"), ("circle_discrepancies", "circle_discrepancies"),
    ("unknown_states", "unknown_states"), ("unresolved_total", "unresolved_total"),
    ("invariant_violations", "invariant_violations"),
    ("duplicate_targets", "duplicate_targets"),
)

# Формы адреса — открытым именем, потому что пустая форма (`''`) в счётчике базы именно
# пустая строка: «адреса нет» и «формы нет» различаются состоянием, а не подстановкой.
FORM_MEASURE_KEYS = {
    ADDRESS_FORM_DIMENSION: "dimension",
    ADDRESS_FORM_OBJECT: "object",
    ADDRESS_FORM_REGISTER_RESOURCE: "register_resource",
    ADDRESS_FORM_ATTRIBUTE: "attribute",
    ADDRESS_FORM_TABULAR_SECTION: "tabular_section",
    ADDRESS_FORM_EMPTY: "empty_form",
}

# Состояния перечня `<Use>` переводятся в меры корпуса словарём: в базе состояние строки вида
# называется `with_content`/`empty_content`, а ключ эталона — `use_with`/`use_empty`. Вывод
# ключа из имени состояния (`use_` + значение) дал бы ключ, которого в эталоне нет, а
# подстановка именем скрыла бы незнакомое состояние (C2).
USE_MEASURE_KEYS = {USE_WITH: "use_with", USE_EMPTY: "use_empty"}

# Чужие витрины позиции 2.11 — их числа называет критерий готовности П6 плана V57: круг 2.12
# живёт рядом, и путаница в предикате изменила бы состав соседа.
FOREIGN_VIEW_EXPECTATIONS = {"v_current_functional_options": 765,
                            "v_current_functional_option_content": 10063}


def foreign_state(cur):
    """Число строк чужих таблиц и витрин — одно число на объект, отсутствующий — None."""
    state = {}
    for table in tuple(FOREIGN_TABLES) + tuple(FOREIGN_VIEWS):
        try:
            state[table] = scalar(cur, f"SELECT count(*) FROM {table}")
        except Exception:  # noqa: BLE001 — отсутствующую таблицу назовёт отдельная проверка
            cur.connection.rollback()
            state[table] = None
    return state


def check_non_interference(before, after):
    """Снимок чужих таблиц и витрин до прогона и после него — одно число на объект.

    Чужой круг индекса состава (записи позиции 2.11 и маску по началу имени) сверяет контур 3
    по каждой выгрузке отдельно, а суммы по корпусу — контур 9: здесь же держится только
    вывод «прогон ничего не пишет», поэтому снимок читается двумя словарями, а не запросом —
    запрос внутри этой функции мерил бы всю базу, а не прогнанный охват.
    """
    section("Уборка за чужими таблицами (прогон читающий)")
    touched = [table for table in tuple(FOREIGN_TABLES) + tuple(FOREIGN_VIEWS)
               if before.get(table) != after.get(table)]
    check(f"чужих таблиц и витрин затронуто — {len(touched)} (прогон ничего не пишет)",
          not touched, f"изменились: {names(touched)}")
    missing = [table for table in tuple(FOREIGN_TABLES) + tuple(FOREIGN_VIEWS)
               if after.get(table) is None]
    check(f"отсутствующих чужих таблиц и витрин в базе — {len(missing)} (названы, а не "
          "пропущены)", not missing, names(missing))
    if before.get("bsl_modules") is not None and after.get("bsl_modules") is not None:
        check("строк `bsl_modules` в прогоне не снято ни одной — узел V57 не трогает круг V47 "
              "(текстов модулей у вида нет — замер 1.2 плана)",
              before["bsl_modules"] == after["bsl_modules"],
              f"до: {before['bsl_modules']}, после: {after['bsl_modules']}")
    view_wrong = [f"{view}: {after.get(view)} ≠ {expected}" for view, expected
                  in sorted(FOREIGN_VIEW_EXPECTATIONS.items())
                  if after.get(view) != expected]
    check("числа витрин соседней позиции 2.11 — 765 опций и 10 063 целей применения (план "
          "V56, раздел 2.2): прогон V57 их не меняет и в свой круг не берёт", not view_wrong,
          "; ".join(view_wrong))


def accumulate_corpus(accum, kind_totals, global_targets, db_rows, target_rows, parsed, raw,
                      agg, header_count, header_is_null):
    """Суммы прогона по четырём выгрузкам — мерой прогона, а не числом плана."""
    accum["files"] += int(raw.get("files") or 0)
    accum["bytes"] += int(raw.get("bytes") or 0)
    accum["index_records"] += int(agg.get("kind_rows") or 0)
    accum["sibling_index"] += int(agg.get("sibling_rows") or 0)
    accum["prefix_mask"] += int(agg.get("mask_rows") or 0)
    accum["root_names"] += len(raw.get("root_names") or ())
    accum["header_names"] += int(header_count or 0)
    accum["header_null"] += 1 if header_is_null else 0
    accum["empty_comment"] += int(raw.get("empty_comment_files") or 0)
    accum["db_rows"] += len(db_rows)
    accum["targets"] += len(target_rows)
    accum["distinct_sum"] += int(parsed.get("targets_distinct") or 0)
    accum["max_targets"] = max(accum["max_targets"], int(parsed.get(MAX_TARGETS_KEY) or 0))
    for key in CIRCLE_DISCREPANCIES:
        accum["circle_discrepancies"] += len(parsed.get(key) or [])
    accum["unresolved_total"] += int(parsed.get("unresolved_targets_total") or 0)
    accum["invariant_violations"] += int(parsed.get("invariant_violations_total") or 0)
    accum["duplicate_targets"] += len(parsed.get("duplicate_targets") or [])
    for row in db_rows:
        if str(row["properties_state"]) != PROPS_ALL_KNOWN:
            accum["unknown_states"] += 1
        accum[USE_MEASURE_KEYS.get(str(row["use_state"]), "use_unknown")] += 1
    for row in target_rows:
        kind_totals[str(row["target_object_type"] or "")] += 1
        global_targets.add(str(row["target_full_name"]))
        if str(row["target_resolve_state"]) == TARGET_EXACT:
            accum["target_exact"] += 1
        accum[FORM_MEASURE_KEYS.get(str(row["target_address_form"]), "other")] += 1
        if str(row["item_type_state"]) == ITEM_TYPE_STATE_REF:
            accum["item_ref"] += 1


def check_corpus(cur, accum, kind_totals, global_targets, all_loaded):
    section("Контур 9 — суммы по четырём выгрузкам")
    check("все четыре выгрузки прогнаны (MinCfg, KomMag, BGU2, BP3)", all_loaded,
          "часть выгрузок не прогнана — сравнивать суммы не с чем")
    for measured, plan_key in CORPUS_KEYS:
        plan = CORPUS_TOTALS[plan_key]
        check(f"корпус: `{measured}` — {plan} (план V57, разделы 1.1, 1.2, 2.1)",
              accum.get(measured, 0) == plan, f"факт: {accum.get(measured, 0)}")
    check(f"корпус: различных адресов цели на всём круге — {CORPUS_TOTALS['distinct_global']} "
          f"(мера, названная шагом П6: 34 цели дают 29 адресов, потому что 5 адресов общи "
          f"паре BGU2/BP3 — те же коллизии имён и uuid вида, из-за которых ключ держит "
          f"`configuration_uuid`); сумма по-выгрузочных различных — "
          f"{CORPUS_TOTALS['distinct_sum']} равна числу строк применения (внутри выгрузки "
          "дублей целей корпус не давал)",
          len(global_targets) == CORPUS_TOTALS["distinct_global"]
          and accum.get("distinct_sum", 0) == accum.get("targets", 0)
          == CORPUS_TOTALS["targets"],
          f"различных по корпусу: {len(global_targets)}, сумма по выгрузкам: "
          f"{accum.get('distinct_sum', 0)}, строк: {accum.get('targets', 0)}")
    check(f"корпус: классов цели — {len(EXPECTED_KINDS)} (замер 2.1), сумма значений — "
          f"{sum(EXPECTED_KINDS.values())} целей",
          len(kind_totals) == len(EXPECTED_KINDS)
          and sum(kind_totals.values()) == CORPUS_TOTALS["targets"],
          f"факт: классов {len(kind_totals)}, целей {sum(kind_totals.values())}")
    wrong = [f"{kind}: {count} ≠ {EXPECTED_KINDS.get(kind)}" for kind, count
             in sorted(kind_totals.items())
             if kind not in EXPECTED_KINDS or count != EXPECTED_KINDS[kind]]
    absent = sorted(kind for kind in EXPECTED_KINDS if kind not in kind_totals)
    check("распределение целей по видам метаданных совпадает с замером 2.1 поимённо "
          "(`InformationRegister` 30, `Catalog` 4 — а не только сумма)",
          not wrong and not absent,
          "; ".join(wrong[:6] + ([f"нет классов: {names(absent)}"] if absent else [])))
    check(f"корпус: пустых перечней `<Use/>` — {CORPUS_TOTALS['use_empty']}, состояний "
          f"`{USE_WITH}` — {CORPUS_TOTALS['use_with']}; состояние пустого перечня остаётся "
          "границей разбора, а строка вида — строкой (M3); незнакомых состояний перечня ноль "
          "(словарь `use_state` замкнут CHECK `functional_option_parameters_use_state_known`)",
          accum.get("use_with", 0) + accum.get("use_empty", 0)
          == accum.get("db_rows", 0) == CORPUS_TOTALS["db_rows"]
          and not accum.get("use_unknown"),
          f"с непустым: {accum.get('use_with', 0)}, с пустым: {accum.get('use_empty', 0)}, "
          f"незнакомых состояний: {accum.get('use_unknown', 0)}, "
          f"строк вида: {accum.get('db_rows', 0)}")
    check(f"корпус: форм адреса цели — `{ADDRESS_FORM_DIMENSION}` "
          f"{CORPUS_TOTALS['dimension']}, `{ADDRESS_FORM_OBJECT}` {CORPUS_TOTALS['object']}, "
          "прочих форм ноль (сумма по четырём выгрузкам)",
          accum.get("dimension", 0) == CORPUS_TOTALS["dimension"]
          and accum.get("object", 0) == CORPUS_TOTALS["object"]
          and not any(accum.get(key, 0) for key in ("register_resource", "attribute",
                                                    "tabular_section", "other", "empty_form")),
          f"факт: {dict((key, accum.get(key, 0)) for key in FORM_MEASURE_KEYS.values())}")
    # Две меры по живой базе на всём круге — «сироты» и «вне витрин» считаются по всем
    # конфигурациям, а не по прогнанной выгрузке: сирота могла остаться от прежней загрузки.
    orphans = scalar(cur, f"SELECT count(*) FROM {TARGETS_TABLE_NAME} c WHERE NOT exists("
                          f"SELECT 1 FROM {TABLE_NAME} o WHERE o.id = c.{PARAMETER_FK_COLUMN})")
    check("корпус: сирот применения (строка без строки вида) — ноль по всей базе",
          not orphans, f"сирот: {orphans}")
    outside = scalar(
        cur, f"SELECT (SELECT count(*) FROM {TABLE_NAME} o WHERE NOT exists("
             f"SELECT 1 FROM {PARAMETER_VIEW} v WHERE v.id = o.id)) + "
             f"(SELECT count(*) FROM {TARGETS_TABLE_NAME} c WHERE NOT exists("
             f"SELECT 1 FROM {TARGETS_VIEW} v WHERE v.id = c.id))")
    check("корпус: строк обеих таблиц вне витрин текущего состояния — ноль (цепь V19 и связка "
          "применения даются одной миграцией — M4)", not outside, f"вне витрин: {outside}")
    kind_rows = scalar(cur, f"SELECT count(*) FROM {INDEX_TABLE} i WHERE i.object_type = %s",
                       (INDEX_OBJECT_TYPE,))
    check(f"корпус: записей вида `{INDEX_OBJECT_TYPE}` во всех индексах состава — "
          f"{CORPUS_TOTALS['index_records']} (мера M1: сравнение по всему кругу)",
          kind_rows == CORPUS_TOTALS["index_records"], f"факт: {kind_rows}")
    # Пара «точный предикат ↔ маска» измеряется по всей живой таблице индекса: именно она
    # показывает, что соседний круг 2.11 (765 записей `FunctionalOption`) в круг V57 не вошёл.
    sibling_rows = scalar(cur, f"SELECT count(*) FROM {INDEX_TABLE} i "
                               "WHERE i.object_type = %s", (SIBLING_INDEX_OBJECT_TYPE,))
    mask_rows = scalar(cur, f"SELECT count(*) FROM {INDEX_TABLE} i WHERE i.object_type LIKE %s",
                       (f"{SIBLING_INDEX_OBJECT_TYPE}%",))
    check(f"корпус: записей ЧУЖДОГО вида `{SIBLING_INDEX_OBJECT_TYPE}` — "
          f"{CORPUS_TOTALS['sibling_index']} (позиция 2.11, узел V56), по МАСКЕ "
          f"`object_type LIKE '{SIBLING_INDEX_OBJECT_TYPE}%'` — {CORPUS_TOTALS['prefix_mask']}; "
          f"разница равна ровно записям вида {INDEX_OBJECT_TYPE} "
          f"({CORPUS_TOTALS['index_records']}) — предикат круга держится точным значением "
          "`object_type` (замер 1.2; план раздела 1.2 писал «16» по MinCfg, живой прогон даёт "
          "4, и правка плана сделана этим же шагом П6)",
          sibling_rows == CORPUS_TOTALS["sibling_index"]
          and mask_rows == CORPUS_TOTALS["prefix_mask"]
          and mask_rows - sibling_rows == CORPUS_TOTALS["index_records"]
          == kind_rows,
          f"точных: {sibling_rows}, маска: {mask_rows}, вида: {kind_rows}")
    header_lists = scalar(cur, f"SELECT count(*) FROM configurations WHERE "
                               f"{HEADER_NAME_COLUMN} IS NOT NULL")
    check(f"корпус: заголовков с заполненным перечнем `{HEADER_NAME_COLUMN}` — "
          f"{len(PLAN_EXPECTATIONS) - CORPUS_TOTALS['header_null']} из "
          f"{len(PLAN_EXPECTATIONS)}; у KomMag перечень `NULL`, и это различается ответом (M8)",
          header_lists == len(PLAN_EXPECTATIONS) - CORPUS_TOTALS["header_null"],
          f"факт: {header_lists}")


def run(cur, scope):
    headers = q(cur, "SELECT id, uuid::text AS uuid, name FROM configurations ORDER BY id")
    if not headers:
        FAILED.append("строк заголовков конфигураций в базе нет — сравнивать не с чем")
        print("FAIL строк заголовков конфигураций в базе нет — сравнивать не с чем")
        return
    before = foreign_state(cur)
    accum = Counter()
    kind_totals = Counter()
    global_targets = set()
    loaded = set()
    for header in headers:
        resolved = resolve_dump_dir(header["uuid"], DUMP_ROOT)
        dump_dir = resolved.get("path") or ""
        tag = Path(dump_dir).name if dump_dir else str(header["name"])
        if scope not in (DEFAULT_SCOPE, tag, str(header["name"])):
            continue
        section(f"Конфигурация {tag} (uuid {header['uuid']})")
        if not dump_dir:
            skip(f"{tag}: прогон выгрузки",
                 f"каталог выгрузки по uuid не найден ({resolved.get('reason', 'нет причины')})")
            continue
        if tag not in PLAN_EXPECTATIONS:
            skip(f"{tag}: сравнение с эталоном",
                 "PLAN_EXPECTATIONS этой выгрузки не называет — числа пришлось бы придумывать")
            continue
        expect = expect_of(tag)
        index_info = read_index_records(cur, int(header["id"]))
        if not index_info.get("available"):
            skip(f"{tag}: сверка круга с индексом состава",
                 f"индекс состава недоступен: {index_info.get('reason')}")
        parsed = collect_functional_options_parameters(dump_dir,
                                                      index_rows=index_info["rows"])
        check(f"{tag}: разбор круга завершён без отказа ({expect['files']} файлов)",
              parsed["success"] is True and parsed["files_found"] == expect["files"]
              and parsed["files_read"] == expect["db_rows"],
              f"success: {parsed['success']}, found: {parsed['files_found']}, read: "
              f"{parsed['files_read']}, failed: {_brief(parsed['files_failed'])}")
        check(f"{tag}: разбор завершён без нарушения инварианта пары (связность круга "
              "проверяется ДО записи — отличие от V56)",
              int(parsed.get("invariant_violations_total") or 0) == 0,
              _brief(parsed.get("invariant_violations")))

        db_rows, target_rows, raw, agg, header_count, header_is_null = check_circle(
            cur, header, dump_dir, index_info, expect, parsed, tag)
        compare_parameter_rows(parsed, db_rows, expect, tag)
        compare_target_rows(parsed, target_rows, db_rows, raw, expect, tag)
        check_resolution(cur, target_rows, header, expect, tag)
        accumulate_corpus(accum, kind_totals, global_targets, db_rows, target_rows, parsed,
                          raw, agg, header_count, header_is_null)
        loaded.add(tag)

    check_schema(cur)
    check_key_columns_match(cur)
    check_state_vocabulary_checks(cur)
    check_revisions_and_views(cur)
    check_contract()
    check_tool_registration()
    if scope == DEFAULT_SCOPE:
        check_corpus(cur, accum, kind_totals, global_targets,
                     loaded == set(PLAN_EXPECTATIONS))
    else:
        skip("Контур 9 — суммы по четырём выгрузкам",
             f"охват `{scope}`: остальные выгрузки не прогнаны, сравнивать суммы не с чем "
             "(у KomMag каталога вида нет — его нули входят в эталон)")
    check_non_interference(before, foreign_state(cur))


def main(argv):
    scope = str(argv[1]) if len(argv) > 1 else DEFAULT_SCOPE
    print("=== постоянная проверка узла V57 (параметры функциональных опций, позиция 2.12) — "
          f"охват {scope} ===")
    try:
        with transaction() as cur:
            run(cur, scope)
    except Exception as exc:  # noqa: BLE001 — отказ прогона обязан быть назван
        FAILED.append(f"прогон прерван исключением: {exc}")
        import traceback
        traceback.print_exc()
    print(f"\nИТОГО: проверок {len(PASSED) + len(FAILED)}, PASS {len(PASSED)}, "
          f"FAIL {len(FAILED)}, SKIP {len(SKIPPED)}, INFO {len(INFO)}")
    if FAILED:
        print("ПРОВАЛЫ:")
        for name in FAILED:
            print(f"  — {name}")
        return 1
    print("ПРОВАЛОВ НЕТ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
