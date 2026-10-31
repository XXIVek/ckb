#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/check_v50_common_attributes.py — узел V50: общие реквизиты (шаг П6).

Это постоянная проверка, а не проба шага: она обязана переживать и перезагрузку выгрузок, и
правки кода загрузки. Источник ожиданий — `docs/CONFIGURATION_COMMON_ATTRIBUTES_PLAN.md`
(раздел 2 — замеры базовой линии, раздел 7 — критерии готовности). Числа круга сняты по самим
каталогам выгрузки независимым зондом `_v50_p6_counts_probe.py` (регекспой по тексту файла, без
знания о состояниях разбора) и перенесены в `PLAN_EXPECTATIONS` без правок: сглаживать число
проверкой — значит подтверждать неверное число (прецедент узла V49).

Что сторожится — по контурам:

  1. ГРАНИЦА КРУГА (контур 1; инвариант Q8). Общий реквизит адресуется четырьмя РАЗНЫМИ
     источниками: каталогом `CommonAttributes/` (`<Имя>.xml`), индексом состава
     (`CommonAttribute.<Имя>`), перечнем `configurations.common_attributes[]` и строками таблицы
     `common_attributes`. Агрегатный COUNT индекса сверяется с построчным обходом (приём V48),
     множества имён сравниваются попарно во все четыре стороны. Детей индекса
     (`CommonAttribute.<Имя>.<что-то>`) — ноль (замер 2.9): второго слоя файла содержимого у вида
     нет, и это проверяемое утверждение, а не отсутствие запроса.
  2. СТРОКА РЕКВИЗИТА ↔ РАЗБОР (контур 2). Каждая колонка строки обязана совпадать с кругом,
     разобранным ТЕМ ЖЕ модулем (`collect_common_attributes`), что и загрузка: иначе проверка
     проверяла бы себя, а не то, донёс ли писатель строку.
  3. КЛЮЧ РАЗБОРА ↔ КОЛОНКИ СХЕМЫ (контур 3). Множество ключей строки разбора и множество
     колонок таблицы сверяются в обе стороны с точностью до колонок ревизии: строка разбора не
     носит ключей, которым нет колонки (сказано в комментарии слоя к `read_registration_file`), а
     колонка, которую разбор не заполняет, обязана быть названа. Числа колонок (69 и 15) — эталон
     шага П1.
  4. СТРОКА ПРИМЕНЕНИЯ ↔ ФАЙЛ (контур 4; замер 2.4). Множество (порядок, цель, `use_state`,
     состояние разрешения) строк реквизита равно множеству элементов `<Content>` его файла;
     повторов цели внутри одного реквизита нет (замер: максимум повторности 1 — это и есть
     принятая форма ключа Q2); счётчики `targets_count`/`targets_used_count`/
     `targets_not_used_count` равны числу строк и разбивке по `use_state`; каждая строка
     применения ссылается на CURRENT-ревизию своего реквизита (Q2, вариант A) и несёт его
     `object_uuid`/`full_name`. Дополнительно — НЕЗАВИСИМЫЙ подсчёт по тексту файла (`xr:Item`,
     `xr:Metadata`, `xr:Use`, пустой `<xr:ConditionalSeparation/>`).
  5. РАЗРЕШИМОСТЬ ЦЕЛЕЙ (контур 5; замер 2.6). Каждая сохранённая цель разрешается ЗАНОВО по
     строкам индекса состава (`resolve_target`): состояние, `target_object_id` и
     `target_object_uuid` обязаны совпасть с сохранёнными. На корпусе неразрешимых целей нет
     (1 512 из 1 512 `exact`), и нули `prefix_only`/`unresolved` здесь — проверяемое утверждение,
     а не предположение: состояния нужны как граница (Q3), а не как украшение.
  6. СЛОВАРИ ЗНАЧЕНИЙ (контур 6; замер 2.7). Значения словарных колонок обязаны входить в
     закрытый словарь модуля разбора (`value_dictionary`), а распределение значений по корпусу —
     совпасть с таблицей 2.7. Строки с `unknown_value`/`unknown_tag` отсутствуют, и отсутствие
     проверяется, а не предполагается.
  7. БЛОКИ РАЗДЕЛЕНИЯ (контур 7; замер 2.7). По каждому из трёх блоков число непустых ссылок и
     пустых блоков совпадает с файлом. Пустой блок называется состоянием `empty_value` при пустых
     колонках ссылки, непустой — `parsed` с разрешённой ссылкой `exact`; отдельной таблицы условий
     модель не имеет, и проверка её не выдумывает (Q5, вариант A).
  8. БЛОК `<Type>` (контур 8; замер 2.3). Состояния разбора и кратность совпадают с эталоном;
     `types jsonb` по числу и значениям равен тегам `<v8:Type>` файла, `type_qualifiers` — блокам
     квалификаторов, `type_raw` — блоку `<Type>`, прочитанному слоем.
  9. ПУСТОЙ КРУГ (контур 9; замер 2.9, Q9). У KomMag каталога вида нет: это называется
     состоянием выгрузки (`directory_missing` и нули круга), а не отказом стадии и не ответом
     «реквизитов не было».
 10. ЦЕЛОСТНОСТЬ СХЕМЫ И ЧУЖИХ КРУГОВ (контур 10). Сирот применения нет; ключи
     `UNIQUE (configuration_uuid, object_name, revision_no)` и `UNIQUE (common_attribute_id,
     ordinal)` живые; витрины обеих таблиц дают то же число строк, что и таблицы; строки
     остальных узлов за прогон не меняются — проверка только читает.

Числа, которых план не называл (сняты прогоном П6 и названы, а не сглажены): разбивка значений
`<v8:Type>` по выгрузкам (MinCfg — четыре значения в двух файлах, BGU2 и BP3 — по пять
`xs:string` и два `xs:decimal`) и распределение квалификаторов; план 2.3 давал только итог по
корпусу.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python tools/check_v50_common_attributes.py [MinCfg|KomMag|BGU2|BP3|all]
По умолчанию — `all`: все строки заголовков, для которых находится каталог выгрузки. Код возврата
0 — расхождений нет. Пропуск контура называется причиной (нет строки заголовка, нет выгрузки,
строк узла не загружалось, выгрузка новее записей): ноль проверок не читается как «всё хорошо».
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

from configuration_common_attributes import (  # noqa: E402
    COMMON_ATTRIBUTE_PROPERTIES, COMMON_ATTRIBUTE_PROPERTY_COUNT,
    CONTENT_EMPTY, CONTENT_STATES, CONTENT_WITH, DIR_NAME, INDEX_NAME_SEPARATOR,
    INDEX_OBJECT_TYPE, ITEM_COND_EMPTY, MULT_ABSENT, MULT_COMPOSITE, MULT_SINGLE,
    MULTIPLICITY_VALUES, PROPERTIES_STATES, PROPS_ALL_KNOWN, PROPS_UNKNOWN_TAG,
    PROPS_UNKNOWN_VALUE, PROPERTY_BY_COLUMN, RECORD_STATES, SEPARATION_BLOCKS,
    SEPARATION_STATES, SEP_EMPTY, SEP_PARSED, SEP_UNKNOWN_FORM, STATE_ABSENT,
    STATE_PARTIAL, STATE_PARSED, STATE_UNKNOWN_FORM, TARGET_EXACT, TARGET_PREFIX_ONLY,
    TARGET_RESOLVE_STATES, TARGET_UNRESOLVED, TYPE_CLASS_VALUES, USE_NOT_USED,
    USE_UNKNOWN_FORM, USE_USED, collect_common_attributes, index_row_key, index_rows_by_name,
    iter_registration_files, kind_index_rows, multiplicity_of, property_columns,
    property_kind, raw_type_block, read_text_file, resolve_target, target_kind,
    value_dictionary,
)
from configuration_common_attributes_loader import read_index_records  # noqa: E402
from configuration_load_contract import (  # noqa: E402
    COMMON_ATTRIBUTES_TABLES, COMMON_ATTRIBUTE_TARGETS_TABLE, COMMON_ATTRIBUTE_TABLE,
    STAGE_COMMON_ATTRIBUTES,
)
from configuration_module_slots import resolve_dump_dir  # noqa: E402
from current_revision import current_view  # noqa: E402
from external_db import transaction  # noqa: E402

DUMP_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
DEFAULT_SCOPE = "all"
MAX_NAMES = 10          # сколько расхождений называется именами (дальше — только число)

# Колонки, которые принадлежат цепи ревизий (узел V19), а не узлу V50: их заполняет не разбор,
# и сравнивать их с ключом строки разбора — значит требовать от слоя чужого.
REVISION_COLUMNS = ("id", "configuration_uuid", "created_at", "revision_no", "changed_at",
                    "changed_by", "is_committed")
# Колонки строки применения, которые писатель проставляет сам (связь с ревизией реквизита), а
# не берёт из разбора: они сторожатся контуром 4 отдельно.
TARGET_WRITER_COLUMNS = ("common_attribute_id", "attribute_object_uuid", "attribute_full_name")

# Ожидаемые числа колонок двух таблиц — эталон шага П1 (миграция V50 + зеркало DDL).
EXPECTED_COLUMN_COUNTS = {COMMON_ATTRIBUTE_TABLE: 69, COMMON_ATTRIBUTE_TARGETS_TABLE: 15}

# ── ожидания проверки (числа плана docs/CONFIGURATION_COMMON_ATTRIBUTES_PLAN.md) ──────────
# Разделы 2.1–2.9 и 7. Ключ — каталог выгрузки, а не имя строки заголовка: имя заголовка
# меняется вместе с выгрузкой, а каталог — адрес, по которому проверка находит файлы.
#   files / bytes / subdirs / non_xml — каталог `CommonAttributes/` (плоский, только XML —
#            сторож примитивности вида, замер 2.1);
#   props_block / prop_tags_total / prop_tags_distinct — обёртка `<Properties>` и 38 тегов
#            свойств на файл (замер 2.2: ровно 38, min = max);
#   type_block / v8_type_tags / v8type_<значение> / qualifier_* — блок `<Type>` (замер 2.3);
#   has_content / items / metadata / use_Use / use_DontUse / item_cond_empty / item_cond_any —
#            перечень `<Content>` (замер 2.4);
#   kind_<вид> — виды целей применения (замер 2.5);
#   sep_<блок>_parsed / sep_<блок>_empty / sep_value_<ссылка> — блоки разделения (замер 2.7);
#   index_rows / index_children / header_list — записи индекса состава и перечень заголовка
#            (`header_list: None` — значения нет вовсе, а не «значений ноль»);
#   attr_rows / target_rows / targets_distinct / max_targets_per_file — строки двух таблиц;
#   used / not_used / use_unknown, resolve_exact / resolve_prefix / resolve_unresolved,
#   with_content / empty_content, all_known / unknown_value / unknown_tag,
#   type_parsed / type_partial / type_absent / type_unknown_form,
#   mult_single / mult_composite / mult_absent,
#   sep_parsed_total / sep_empty_total / sep_unknown_total — состояния сохранённых строк;
#   observations / index_only / file_only / uuid_mismatch / name_file_mismatch — круг замкнут
#            во всех четырёх выгрузках (замер 2.9), нули здесь — проверяемое утверждение;
#   directory_missing — KomMag: позиции вида в выгрузке нет (Q9), и это состояние, а не отказ.
PLAN_EXPECTATIONS = {
    "MinCfg": {
        "files": 2, "bytes": 6307, "subdirs": 0, "non_xml": 0,
        "props_block": 2, "prop_tags_total": 76, "prop_tags_distinct": 76,
        "type_block": 2, "v8_type_tags": 4,
        "v8type_xs:string": 1, "v8type_xs:dateTime": 1, "v8type_xs:decimal": 1,
        "v8type_v8:ValueStorage": 1,
        "qualifier_string": 1, "qualifier_number": 1, "qualifier_date": 1,
        "has_content": 2, "items": 3, "metadata": 3,
        "use_Use": 3, "use_DontUse": 0, "item_cond_empty": 3, "item_cond_any": 3,
        "kind_InformationRegister": 1, "kind_Catalog": 1, "kind_Document": 1,
        "sep_data_separation_value_parsed": 0, "sep_data_separation_value_empty": 2,
        "sep_data_separation_use_parsed": 0, "sep_data_separation_use_empty": 2,
        "sep_conditional_separation_parsed": 0, "sep_conditional_separation_empty": 2,
        "index_rows": 2, "index_children": 0, "header_list": 2,
        "attr_rows": 2, "target_rows": 3, "targets_distinct": 3, "max_targets_per_file": 2,
        "used": 3, "not_used": 0, "use_unknown": 0,
        "resolve_exact": 3, "resolve_prefix": 0, "resolve_unresolved": 0,
        "with_content": 2, "empty_content": 0,
        "all_known": 2, "unknown_value": 0, "unknown_tag": 0,
        "type_parsed": 2, "type_partial": 0, "type_absent": 0, "type_unknown_form": 0,
        "mult_single": 1, "mult_composite": 1, "mult_absent": 0,
        "sep_parsed_total": 0, "sep_empty_total": 6, "sep_unknown_total": 0,
        "observations": 0, "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
        "name_file_mismatch": 0, "directory_missing": 0,
    },
    "KomMag": {
        "files": 0, "bytes": 0, "subdirs": 0, "non_xml": 0,
        "props_block": 0, "prop_tags_total": 0, "prop_tags_distinct": 0,
        "type_block": 0, "v8_type_tags": 0, "qualifier_string": 0, "qualifier_number": 0,
        "qualifier_date": 0,
        "has_content": 0, "items": 0, "metadata": 0,
        "use_Use": 0, "use_DontUse": 0, "item_cond_empty": 0, "item_cond_any": 0,
        "index_rows": 0, "index_children": 0, "header_list": None,
        "attr_rows": 0, "target_rows": 0, "targets_distinct": 0, "max_targets_per_file": 0,
        "used": 0, "not_used": 0, "use_unknown": 0,
        "resolve_exact": 0, "resolve_prefix": 0, "resolve_unresolved": 0,
        "with_content": 0, "empty_content": 0,
        "all_known": 0, "unknown_value": 0, "unknown_tag": 0,
        "type_parsed": 0, "type_partial": 0, "type_absent": 0, "type_unknown_form": 0,
        "mult_single": 0, "mult_composite": 0, "mult_absent": 0,
        "sep_parsed_total": 0, "sep_empty_total": 0, "sep_unknown_total": 0,
        "observations": 1, "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
        "name_file_mismatch": 0, "directory_missing": 1,
    },
    "BGU2": {
        "files": 7, "bytes": 163697, "subdirs": 0, "non_xml": 0,
        "props_block": 7, "prop_tags_total": 266, "prop_tags_distinct": 266,
        "type_block": 7, "v8_type_tags": 7,
        "v8type_xs:string": 5, "v8type_xs:decimal": 2,
        "qualifier_string": 5, "qualifier_number": 2, "qualifier_date": 0,
        "has_content": 7, "items": 692, "metadata": 692,
        "use_Use": 127, "use_DontUse": 565, "item_cond_empty": 692, "item_cond_any": 692,
        "kind_InformationRegister": 262, "kind_Constant": 188, "kind_ScheduledJob": 157,
        "kind_Catalog": 78, "kind_ChartOfCharacteristicTypes": 5, "kind_ExchangePlan": 1,
        "kind_IntegrationService": 1,
        "sep_data_separation_value_parsed": 2, "sep_data_separation_value_empty": 5,
        "sep_data_separation_use_parsed": 2, "sep_data_separation_use_empty": 5,
        "sep_conditional_separation_parsed": 2, "sep_conditional_separation_empty": 5,
        "sep_value_SessionParameter.ОбластьДанныхЗначение": 2,
        "sep_value_SessionParameter.ОбластьДанныхИспользование": 2,
        "sep_value_Constant.ИспользоватьРазделениеПоОбластямДанных": 2,
        "index_rows": 7, "index_children": 0, "header_list": 7,
        "attr_rows": 7, "target_rows": 692, "targets_distinct": 584, "max_targets_per_file": 565,
        "used": 127, "not_used": 565, "use_unknown": 0,
        "resolve_exact": 692, "resolve_prefix": 0, "resolve_unresolved": 0,
        "with_content": 7, "empty_content": 0,
        "all_known": 7, "unknown_value": 0, "unknown_tag": 0,
        "type_parsed": 7, "type_partial": 0, "type_absent": 0, "type_unknown_form": 0,
        "mult_single": 7, "mult_composite": 0, "mult_absent": 0,
        "sep_parsed_total": 6, "sep_empty_total": 15, "sep_unknown_total": 0,
        "observations": 0, "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
        "name_file_mismatch": 0, "directory_missing": 0,
    },
    "BP3": {
        "files": 7, "bytes": 189081, "subdirs": 0, "non_xml": 0,
        "props_block": 7, "prop_tags_total": 266, "prop_tags_distinct": 266,
        "type_block": 7, "v8_type_tags": 7,
        "v8type_xs:string": 5, "v8type_xs:decimal": 2,
        "qualifier_string": 5, "qualifier_number": 2, "qualifier_date": 0,
        "has_content": 7, "items": 817, "metadata": 817,
        "use_Use": 129, "use_DontUse": 688, "item_cond_empty": 817, "item_cond_any": 817,
        "kind_InformationRegister": 299, "kind_Constant": 204, "kind_ScheduledJob": 186,
        "kind_Catalog": 121, "kind_ChartOfCharacteristicTypes": 5, "kind_ExchangePlan": 1,
        "kind_IntegrationService": 1,
        "sep_data_separation_value_parsed": 2, "sep_data_separation_value_empty": 5,
        "sep_data_separation_use_parsed": 2, "sep_data_separation_use_empty": 5,
        "sep_conditional_separation_parsed": 2, "sep_conditional_separation_empty": 5,
        "sep_value_SessionParameter.ОбластьДанныхЗначение": 2,
        "sep_value_SessionParameter.ОбластьДанныхИспользование": 2,
        "sep_value_Constant.ИспользоватьРазделениеПоОбластямДанных": 2,
        "index_rows": 7, "index_children": 0, "header_list": 7,
        "attr_rows": 7, "target_rows": 817, "targets_distinct": 706, "max_targets_per_file": 688,
        "used": 129, "not_used": 688, "use_unknown": 0,
        "resolve_exact": 817, "resolve_prefix": 0, "resolve_unresolved": 0,
        "with_content": 7, "empty_content": 0,
        "all_known": 7, "unknown_value": 0, "unknown_tag": 0,
        "type_parsed": 7, "type_partial": 0, "type_absent": 0, "type_unknown_form": 0,
        "mult_single": 7, "mult_composite": 0, "mult_absent": 0,
        "sep_parsed_total": 6, "sep_empty_total": 15, "sep_unknown_total": 0,
        "observations": 0, "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
        "name_file_mismatch": 0, "directory_missing": 0,
    },
}

# ── ожидания по корпусу (все четыре выгрузки, 16 файлов) ─────────────────────────────────
# Распределение значений словарных свойств (план 2.7), булевых флагов, значений `<v8:Type>` и
# квалификаторов (план 2.3), видов целей (план 2.5). Суммирование по выгрузкам осмысленно
# только когда прогону доступны все четыре: сумму по трём сравнивать с итогом по четырём —
# значит получить ложное расхождение, поэтому сравнение включается по полному кругу.
CORPUS_TOTALS = {
    "files": 16, "bytes": 359085, "subdirs": 0, "non_xml": 0,
    "props_block": 16, "prop_tags_total": 608, "prop_tags_distinct": 608,
    "type_block": 16, "v8_type_tags": 18,
    "v8type_xs:string": 11, "v8type_xs:decimal": 5, "v8type_v8:ValueStorage": 1,
    "v8type_xs:dateTime": 1,
    "qualifier_string": 11, "qualifier_number": 5, "qualifier_date": 1,
    "has_content": 16, "items": 1512, "metadata": 1512,
    "use_Use": 259, "use_DontUse": 1253, "item_cond_empty": 1512, "item_cond_any": 1512,
    "kind_InformationRegister": 562, "kind_Constant": 392, "kind_ScheduledJob": 343,
    "kind_Catalog": 200, "kind_ChartOfCharacteristicTypes": 10, "kind_ExchangePlan": 2,
    "kind_IntegrationService": 2, "kind_Document": 1,
    "sep_parsed_total": 12, "sep_empty_total": 36, "sep_unknown_total": 0,
    "sep_data_separation_value_parsed": 4, "sep_data_separation_value_empty": 12,
    "sep_data_separation_use_parsed": 4, "sep_data_separation_use_empty": 12,
    "sep_conditional_separation_parsed": 4, "sep_conditional_separation_empty": 12,
    "sep_value_SessionParameter.ОбластьДанныхЗначение": 4,
    "sep_value_SessionParameter.ОбластьДанныхИспользование": 4,
    "sep_value_Constant.ИспользоватьРазделениеПоОбластямДанных": 4,
    "attr_rows": 16, "target_rows": 1512,
    "used": 259, "not_used": 1253, "use_unknown": 0,
    "resolve_exact": 1512, "resolve_prefix": 0, "resolve_unresolved": 0,
    "with_content": 16, "empty_content": 0,
    "all_known": 16, "unknown_value": 0, "unknown_tag": 0,
    "type_parsed": 16, "type_partial": 0, "type_absent": 0, "type_unknown_form": 0,
    "mult_single": 15, "mult_composite": 1, "mult_absent": 0,
    "index_rows": 16, "index_children": 0, "header_list": 16,
    "observations": 1, "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
    "name_file_mismatch": 0, "directory_missing": 1,
}
# Значения словарных свойств по корпусу (план 2.7, 16 файлов). Пустой перечень в словаре
# модуля — свойство без закрытого словаря значений (KIND_VALUE/KIND_TEXT); его значения здесь
# не сравниваются.
PROPERTY_VALUE_COUNTS = {
    "fill_checking": {"DontCheck": 16},
    "choice_folders_and_items": {"Items": 16},
    "quick_choice": {"Auto": 15, "Use": 1},
    "create_on_input": {"Auto": 16},
    "choice_history_on_input": {"Auto": 15, "DontUse": 1},
    "auto_use": {"DontUse": 14, "Use": 2},
    "data_separation": {"DontUse": 12, "Separate": 4},
    "separated_data_use": {"Independently": 14, "IndependentlyAndSimultaneously": 2},
    "users_separation": {"DontUse": 14, "Separate": 2},
    "authentication_separation": {"DontUse": 14, "Separate": 2},
    "configuration_extensions_separation": {"DontUse": 14, "Separate": 2},
    "indexing": {"DontIndex": 12, "IndexWithAdditionalOrder": 4},
    "full_text_search": {"Use": 16},
    "data_history": {"Use": 16},
}
# Булевые свойства (KIND_BOOL): на корпусе во всех 16 файлах — false (план 2.2).
BOOL_VALUE_COUNTS = {column: {"false": 16} for column in
                     ("password_mode", "mark_negatives", "multi_line", "extended_edit",
                      "fill_from_filling_value")}
# Ссылки разделения по корпусу (план 2.7): по четыре на каждую из трёх целей.
SEPARATION_REF_COUNTS = {
    "SessionParameter.ОбластьДанныхЗначение": 4,
    "SessionParameter.ОбластьДанныхИспользование": 4,
    "Constant.ИспользоватьРазделениеПоОбластямДанных": 4,
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


def counts_diff(actual, expected, label, tag, ignore_prefixes=("tag_",)):
    """Сравнивает Counter с эталоном по всем ключам эталона и лишним ключам факта.

    Префиксы `ignore_prefixes` — ключи, которые эталон не перечисляет поимённо, потому что
    они замкнуты константой модуля разбора (38 тегов свойств): их сторожит отдельная
    проверка `check_property_tags`, а не перечень чисел.
    """
    wrong = []
    for key, want in expected.items():
        got = actual.get(key, 0)
        if got != want:
            wrong.append(f"{label} {key}: факт {got}, план {want}")
    extra = sorted(key for key, value in actual.items()
                   if key not in expected and value
                   and not key.startswith(ignore_prefixes))
    if extra:
        wrong.append(f"{label} вне эталона: " + names(extra))
    check(f"{tag}: {label} равны плану", not wrong, "; ".join(wrong))
    return not wrong


def raw_expectations(expect):
    """Ключи эталона, которые относятся к независимой мере файлов, а не к строкам БД."""
    selected = {}
    for key, value in expect.items():
        if key in RAW_TOTAL_KEYS:
            selected[key] = value
        elif key.startswith(("kind_", "v8type_", "sep_value_")):
            selected[key] = value
        elif key.startswith("sep_") and (key.endswith("_parsed") or
                                         key.endswith("_empty")):
            selected[key] = value
    return selected


def check_property_tags(per_name, tag):
    """Состав свойств файла: ровно 38 тегов, каждый ровно по одному разу (замер 2.2).

    Перечень тегов замкнут словарём модуля разбора, поэтому числа по именам в эталон не
    переносятся — здесь сторожится именно инвариант «min = max = 38», а не список значений.
    """
    wrong = []
    for name, counts in sorted(per_name.items()):
        if counts["prop_tags_total"] != COMMON_ATTRIBUTE_PROPERTY_COUNT:
            wrong.append(f"{name}: тегов свойств {counts['prop_tags_total']}, "
                         f"ждём {COMMON_ATTRIBUTE_PROPERTY_COUNT}")
        if counts["prop_tags_distinct"] != COMMON_ATTRIBUTE_PROPERTY_COUNT:
            wrong.append(f"{name}: различных тегов свойств "
                         f"{counts['prop_tags_distinct']}")
        if counts["props_block"] != 1:
            wrong.append(f"{name}: обёртки <Properties> нет")
        repeated = [key[4:] for key, value in counts.items()
                    if key.startswith("tag_") and value != 1]
        if repeated:
            wrong.append(f"{name}: теги вне нормы «ровно один раз»: " +
                         names(sorted(repeated)))
    check(f"{tag}: состав свойств файла — ровно {COMMON_ATTRIBUTE_PROPERTY_COUNT} тегов "
          f"по одному разу (замер 2.2)", not wrong, names(wrong))


# ── имена витрин берутся реестром, а не литералом (приём V48) ────────────────────────────
ATTRIBUTES_VIEW = current_view(COMMON_ATTRIBUTE_TABLE)
# Строки применения версий не имеют (Q2, вариант A): витрина строится связкой с CURRENT-
# ревизиями реквизита, своей цепи у таблицы нет — тот же порядок, что у role_rights (V49).
TARGETS_VIEW = "v_current_common_attribute_targets"

# Колонки-uuid нормализуются при сравнении: psycopg2 отдаёт uuid.UUID, разбор — строку.
def norm_value(column, value):
    if value is None:
        return None
    if column.endswith("_uuid"):
        return str(value).lower()
    return value


def read_attribute_rows(cur, cfg_uuid):
    """Строки CURRENT-состояния реквизитов этой конфигурации (полный набор колонок)."""
    return q(cur, f"SELECT * FROM {ATTRIBUTES_VIEW} WHERE configuration_uuid = %(uuid)s::uuid "
                  f"ORDER BY object_name", {"uuid": str(cfg_uuid)})


def read_target_rows(cur, cfg_uuid):
    return q(cur, f"SELECT * FROM {TARGETS_VIEW} WHERE configuration_uuid = %(uuid)s::uuid "
                  f"ORDER BY attribute_full_name, ordinal", {"uuid": str(cfg_uuid)})


def read_header_name_list(cur, configuration_uuid):
    """Перечень имён вида из строки заголовка (колонка `configurations.common_attributes`).

    Иначе сравнение множеств сравнивало бы один набор с самим собой: инвариант Q8 существует
    ровно потому, что источник здесь другой. NULL перечня — состояние «значения нет» (KomMag),
    оно возвращается отдельным признаком, а не пустым списком: «перечня нет» и «перечень пуст»
    — разные состояния выгрузки.
    """
    row = one(cur, "SELECT coalesce(common_attributes, '{}'::text[]) AS names, "
                   "(common_attributes IS NULL) AS is_null FROM configurations "
                   "WHERE uuid = %(uuid)s::uuid", {"uuid": str(configuration_uuid)})
    return [str(item) for item in (row.get("names") or [])], bool(row.get("is_null"))


def table_columns(cur, table):
    """Колонки таблицы по живой схеме.

    Список берётся из схемы, а не из памяти проверки: проверка обязана назвать колонку,
    которой нет, а не молча получить пустой словарь.
    """
    return [row["column_name"] for row in q(
        cur, "SELECT column_name FROM information_schema.columns WHERE table_name = %s "
             "ORDER BY ordinal_position", (table,))]


# ── независимая мера круга: регулярки по ТЕКСТУ файла регистрации ─────────────────────────
# Сравнение строки БД с разбором проверяет ПИСАТЕЛЯ; этот подсчёт проверяет САМ РАЗБОР:
# совпадение двух реализаций и есть доказательство, что в строку легло то, что в файле, а не
# то, что ожидалось. Приём заимствован у `tools/check_v49_roles.py` (контур 4).
# Теги свойств и блоков разделения в файле — без префикса (`DataSeparationValue`), элементы
# перечня — с префиксом `xr:` (`<xr:Item>`); имена тегов свойств и блоков берутся словарём
# модуля разбора, а не литералом, иначе перечень разъехался бы при переименовании колонки.
PROPS_BLOCK_RE = re.compile(r"<Properties>(.*?)</Properties>", re.S)
CONTENT_BLOCK_RE = re.compile(r"<Content>(.*?)</Content>", re.S)
TYPE_BLOCK_RE = re.compile(r"<Type>(.*?)</Type>", re.S)
PROPERTY_TAG_RE = {name: re.compile(r"<%s[\s/>]" % re.escape(name))
                   for name, _column, _kind in COMMON_ATTRIBUTE_PROPERTIES}
RE_ITEM = re.compile(r"<xr:Item[\s/>]")
RE_USE_VALUE = re.compile(r"<xr:Use>\s*(.*?)\s*</xr:Use>", re.S)
RE_ITEM_COND_EMPTY = re.compile(r"<xr:ConditionalSeparation\s*/>")
# И любой тег (самозакрывающийся или с содержимым): `[\s/>]`, иначе закрытый `<…/>` не
# считался бы, и «непустых нет» читалось бы как «тегов нет вообще».
RE_ITEM_COND_ANY = re.compile(r"<xr:ConditionalSeparation[\s/>]")
RE_METADATA = re.compile(r"<xr:Metadata>\s*(.*?)\s*</xr:Metadata>", re.S)
RE_V8_TYPE = re.compile(r"<v8:Type>\s*(.*?)\s*</v8:Type>", re.S)
RE_QUALIFIERS = {
    "string": re.compile(r"<v8:StringQualifiers[\s/>]"),
    "number": re.compile(r"<v8:NumberQualifiers[\s/>]"),
    "date": re.compile(r"<v8:DateQualifiers[\s/>]"),
}
SEP_EMPTY_RE = {block: re.compile(r"<%s\s*/>" % PROPERTY_BY_COLUMN[block])
                for block in SEPARATION_BLOCKS}
SEP_VALUE_RE = {block: re.compile(r"<%s>\s*([^<]+?)\s*</%s>"
                                  % (PROPERTY_BY_COLUMN[block], PROPERTY_BY_COLUMN[block]))
                for block in SEPARATION_BLOCKS}


def measure_file(text: str) -> Counter:
    """Меры одного файла регистрации, не знающие ничего о состояниях разбора."""
    c = Counter()
    props = PROPS_BLOCK_RE.search(text)
    props_text = props.group(1) if props else ""
    c["props_block"] = 1 if props else 0
    for name, pattern in PROPERTY_TAG_RE.items():
        c["tag_%s" % name] = len(pattern.findall(props_text))
    c["prop_tags_total"] = sum(c["tag_%s" % name] for name in PROPERTY_TAG_RE)
    c["prop_tags_distinct"] = sum(1 for name in PROPERTY_TAG_RE if c["tag_%s" % name])
    for block in SEPARATION_BLOCKS:
        values = SEP_VALUE_RE[block].findall(props_text)
        c["sep_%s_parsed" % block] = len(values)
        c["sep_%s_empty" % block] = len(SEP_EMPTY_RE[block].findall(props_text))
        for value in values:
            c["sep_value_" + value] += 1
    content = CONTENT_BLOCK_RE.search(text)
    content_text = content.group(1) if content else ""
    c["has_content"] = 1 if content else 0
    c["items"] = len(RE_ITEM.findall(content_text))
    for value in RE_USE_VALUE.findall(content_text):
        c["use_" + value] += 1
    c["item_cond_empty"] = len(RE_ITEM_COND_EMPTY.findall(content_text))
    c["item_cond_any"] = len(RE_ITEM_COND_ANY.findall(content_text))
    c["metadata"] = len(RE_METADATA.findall(content_text))
    for full_name in RE_METADATA.findall(content_text):
        c["kind_" + full_name.split(".")[0]] += 1
    type_block = TYPE_BLOCK_RE.search(props_text)
    type_text = type_block.group(1) if type_block else ""
    c["type_block"] = 1 if type_block else 0
    values = RE_V8_TYPE.findall(type_text)
    c["v8_type_tags"] = len(values)
    for value in values:
        c["v8type_" + value] += 1
    for key, pattern in RE_QUALIFIERS.items():
        c["qualifier_" + key] = len(pattern.findall(type_text))
    return c


def raw_measures(dump_dir):
    """Подсчёт по тексту файлов вида: итоги, меры по каждому файлу и блоки `<Type>` как текст."""
    entries, observations = iter_registration_files(Path(dump_dir))
    totals = Counter()
    per_name = {}
    raw_blocks = {}
    unreadable = []
    for entry in entries:
        text, reason = read_text_or_none(entry["path"])
        if text is None:
            unreadable.append((entry["file_name"], reason))
            continue
        counts = measure_file(text)
        counts["bytes"] = entry["path"].stat().st_size
        name = Path(entry["file_name"]).stem
        per_name[name] = counts
        raw_blocks[name] = raw_type_block(text) or ""
        for key, value in counts.items():
            totals[key] += value
    totals["files"] = len(entries)
    totals["unreadable_files"] = len(unreadable)
    for kind, _detail in observations:
        totals["obs_" + kind] += 1
    return totals, per_name, raw_blocks, unreadable, observations


def read_text_or_none(path):
    """Текст файла тем же чтением, что и слой загрузки.

    Независимость меры — в регулярках по содержимому, а не в способе чтения байтов:
    собственный `Path.read_text` переводит окончания строк, и сравнение `type_raw` с блоком
    файла давало бы ложное расхождение из-за `\r\n` (проверка спотыкалась бы о формат
    файла, а не о знании).
    """
    return read_text_file(Path(path))


# ── круг на диске: разбор ТЕМ ЖЕ модулем, что и загрузка, и запись индекса ────────────────
def parse_circle(dump_dir, index_rows):
    """Разобрать круг модулем загрузки.

    Сравнение строки с файлом идёт по разбору, а не по второй реализации чтения XML: иначе
    проверка проверяла бы саму себя, а не то, донёс ли писатель строку.
    """
    return collect_common_attributes(Path(dump_dir), index_rows)


def short_index_name(object_name):
    """Имя реквизита по ключу индекса состава (`CommonAttribute.<Имя>`, замер 2.9).

    Дочерних записей вида нет, поэтому суффикс снимать нечего; число детей считается отдельно
    (контур 1), иначе «детей нет» осталось бы отсутствием запроса, а не проверкой.
    """
    prefix = INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR
    key = str(object_name or "")
    return key[len(prefix):] if key.startswith(prefix) else ""


def index_aggregates(cur, configuration_id):
    """Две меры записей индекса состава: агрегатным COUNT и построчным обходом (приём V48)."""
    aggregate = int(one(cur, "SELECT count(*) AS c FROM configuration_objects "
                             "WHERE configuration_id = %s AND object_type = %s "
                             "AND (child_type IS NULL OR child_type = '')",
                        (int(configuration_id), INDEX_OBJECT_TYPE)).get("c") or 0)
    children = int(one(cur, "SELECT count(*) AS c FROM configuration_objects "
                            "WHERE configuration_id = %s AND object_type = %s "
                            "AND child_type IS NOT NULL AND child_type <> ''",
                       (int(configuration_id), INDEX_OBJECT_TYPE)).get("c") or 0)
    return aggregate, children


def dump_newer_than_rows(dump_dir, attribute_rows):
    """True, если файлы круга новее строк узла (правило R5); None — если мерить нечем."""
    stamps = [row["changed_at"] for row in attribute_rows if row.get("changed_at")]
    if not stamps:
        return None
    directory = Path(dump_dir) / DIR_NAME
    if not directory.is_dir():
        return None
    newest_file = max((item.stat().st_mtime for item in directory.rglob("*")
                      if item.is_file()), default=None)
    if newest_file is None:
        return None
    return newest_file > max(stamp.timestamp() for stamp in stamps)


def foreign_state(cur):
    """Снимок того, что узел V50 трогать не должен (сверяется до и после прогона)."""
    watched = ["configurations", "configuration_objects", "session_parameters", "roles",
               "role_rights", "subsystems", "subsystem_content", "common_modules",
               "common_module_sources", "bsl_modules", "external_report", "config_aliases",
               "config_snippets", "config_cross_references", "attributes", "forms"]
    state = {}
    for table in watched:
        try:
            state[table] = int(one(cur, f"SELECT count(*) AS c FROM {table}").get("c") or 0)
        except Exception:  # noqa: BLE001 — таблицы других узлов могут отсутствовать в базе
            state[table] = None
    for table in COMMON_ATTRIBUTES_TABLES:
        try:
            state[table] = int(one(cur, f"SELECT count(*) AS c FROM {table}").get("c") or 0)
        except Exception:  # noqa: BLE001
            state[table] = None
    return state


def check_untouched(before, after):
    changed = [table for table, value in before.items()
               if table not in COMMON_ATTRIBUTES_TABLES and after.get(table) != value]
    check("прогон ничего не изменил в чужих кругах", not changed,
          "изменились строки таблиц: " + names(changed))


def set_diff(label, left, right, tag):
    """Парное сравнение множеств имён — в обе стороны и поимённо."""
    missing = sorted(right - left)
    extra = sorted(left - right)
    ok = not missing and not extra
    detail = ""
    if missing:
        detail += f"есть только в правой части: {names(missing)}"
    if extra:
        detail += ("; " if detail else "") + f"есть только в левой части: {names(extra)}"
    check(f"{tag}: {label}", ok, detail)
    return ok


# ── контур 1: граница круга (инвариант Q8) ────────────────────────────────────────────────
def check_circle(cur, header, dump_dir, index_info, expect, tag):
    """Каталог ↔ индекс состава ↔ перечень заголовка ↔ строки таблиц (четыре источника)."""
    cfg_uuid = str(header["uuid"])
    attribute_rows = read_attribute_rows(cur, cfg_uuid)
    target_rows = read_target_rows(cur, cfg_uuid)
    header_names, header_is_null = read_header_name_list(cur, cfg_uuid)
    aggregate, children = index_aggregates(cur, int(header["id"]))
    index_records = kind_index_rows(index_info["rows"])
    index_names = {short_index_name(index_row_key(row)) for row in index_records}
    index_names.discard("")
    index_uuids = {short_index_name(index_row_key(row)):
                   str(row.get("uuid") or "").lower() or None for row in index_records}

    file_entries, _observations = iter_registration_files(Path(dump_dir))
    file_stems = {Path(entry["file_name"]).stem for entry in file_entries}
    parsed = parse_circle(dump_dir, index_info["rows"])
    parsed_names = {row["object_name"] for row in parsed["rows"]}
    table_names = {row["object_name"] for row in attribute_rows}

    check(f"{tag}: файлы круга разбираются без отказов", not parsed["files_failed"],
          _brief(parsed["files_failed"][:MAX_NAMES]))
    check(f"{tag}: файлов каталога ровно столько, сколько названо планом",
          len(file_stems) == expect["files"],
          f"файлов: {len(file_stems)}, план: {expect['files']}")
    check(f"{tag}: записей индекса состава вида — и агрегатом, и обходом, и планом",
          aggregate == len(index_records) == expect["index_rows"],
          f"агрегат: {aggregate}, обход: {len(index_records)}, план: {expect['index_rows']}")
    check(f"{tag}: дочерних записей индекса вида нет (замер 2.9)",
          children == expect["index_children"],
          f"детей: {children}, план: {expect['index_children']}")
    if expect["header_list"] is None:
        check(f"{tag}: перечень заголовка отсутствует значением NULL (состояние выгрузки)",
              header_is_null and not header_names,
              f"NULL: {header_is_null}, значений: {len(header_names)}")
    else:
        check(f"{tag}: значений перечня заголовка ровно столько, сколько названо планом",
              len(header_names) == expect["header_list"],
              f"значений: {len(header_names)}, план: {expect['header_list']}")
    check(f"{tag}: строк таблицы реквизитов ровно столько, сколько названо планом",
          len(attribute_rows) == expect["attr_rows"],
          f"строк: {len(attribute_rows)}, план: {expect['attr_rows']}")
    check(f"{tag}: строк таблицы применения ровно столько, сколько названо планом",
          len(target_rows) == expect["target_rows"],
          f"строк: {len(target_rows)}, план: {expect['target_rows']}")

    # Четыре источника сравниваются попарно во все шесть сторон: сравнение одного множества
    # с самим собой инвариант не сторожит.
    set_diff("каталог файлов ↔ записи индекса", file_stems, index_names, tag)
    set_diff("каталог файлов ↔ перечень заголовка", file_stems, set(header_names), tag)
    set_diff("каталог файлов ↔ строки таблицы", file_stems, table_names, tag)
    set_diff("записи индекса ↔ перечень заголовка", index_names, set(header_names), tag)
    set_diff("записи индекса ↔ строки таблицы", index_names, table_names, tag)
    set_diff("перечень заголовка ↔ строки таблицы", set(header_names), table_names, tag)

    check(f"{tag}: имя файла равно свойству `Name` разбора (замер 2.9)",
          file_stems == parsed_names,
          f"расхождение: {names(sorted(file_stems ^ parsed_names))}")

    obs_counts = Counter(kind for kind, _detail in parsed["observations"])
    expected_obs = {}
    if expect["directory_missing"]:
        expected_obs["directory_missing"] = expect["directory_missing"]
    check(f"{tag}: наблюдений о круге нет, кроме названных планом",
          dict(obs_counts) == expected_obs,
          f"факт: {dict(obs_counts)}, план: {expected_obs}")
    for key in ("index_only", "file_only", "uuid_mismatch"):
        got = len(parsed[key]) if isinstance(parsed[key], list) else 0
        check(f"{tag}: расхождений круга `{key}` — {expect[key]}", got == expect[key],
              f"факт: {got}, план: {expect[key]}; {_brief(parsed[key][:MAX_NAMES])}")

    # uuid файла регистрации = uuid записи индекса = uuid строки таблицы (замер 2.9).
    uuid_wrong = []
    for row in attribute_rows:
        want = index_uuids.get(row["object_name"])
        if want is None:
            uuid_wrong.append(f"{row['object_name']}: записи индекса без uuid")
        elif str(row["object_uuid"]).lower() != want:
            uuid_wrong.append(f"{row['object_name']}: строка {row['object_uuid']} ≠ индекс {want}")
    check(f"{tag}: uuid строки совпадает с uuid записи индекса состава", not uuid_wrong,
          names(uuid_wrong))

    return {"attribute_rows": attribute_rows, "target_rows": target_rows, "parsed": parsed,
            "header_names": header_names, "index_uuids": index_uuids,
            "file_stems": file_stems, "index_rows": len(index_records),
            "index_children": children, "header_is_null": header_is_null}


# ── контур 2: строка реквизита ↔ разбор того же файла ────────────────────────────────────
def check_attribute_rows(parsed, attribute_rows, attribute_columns, tag):
    """Каждая колонка строки равна значению, которое даёт разбор того же файла."""
    rows_by_name = {row["object_name"]: row for row in attribute_rows}
    parse_rows = {row["object_name"]: row for row in parsed["rows"]}
    set_diff("разбор ↔ строки таблицы (набор имён)", set(parse_rows), set(rows_by_name), tag)

    parse_keys = set()
    for row in parse_rows.values():
        parse_keys.update(row)
    fields = sorted((set(attribute_columns) & parse_keys) - set(REVISION_COLUMNS))
    mismatched = []
    for name, parse_row in sorted(parse_rows.items()):
        db_row = rows_by_name.get(name)
        if db_row is None:
            continue
        for field in fields:
            if field not in parse_row:
                continue
            db_value = norm_value(field, db_row.get(field))
            parse_value = norm_value(field, parse_row.get(field))
            if db_value != parse_value:
                mismatched.append(f"{name}.{field}: строка {_brief(db_value)} ≠ "
                                  f"разбор {_brief(parse_value)}")
    check(f"{tag}: каждая колонка строки равна разбору того же файла "
          f"(полей сравнения: {len(fields)})", not mismatched, names(mismatched))

    # Состояния перечня и свойств называются словарём, а не нулём счётчика (Q4, Q7 A).
    states_wrong = []
    for name, db_row in sorted(rows_by_name.items()):
        if db_row["content_state"] not in CONTENT_STATES:
            states_wrong.append(f"{name}: content_state {db_row['content_state']!r}")
        if db_row["properties_state"] not in PROPERTIES_STATES:
            states_wrong.append(f"{name}: properties_state {db_row['properties_state']!r}")
        if db_row["type_parse_state"] not in RECORD_STATES:
            states_wrong.append(f"{name}: type_parse_state {db_row['type_parse_state']!r}")
        if db_row["type_multiplicity"] not in MULTIPLICITY_VALUES:
            states_wrong.append(f"{name}: type_multiplicity {db_row['type_multiplicity']!r}")
        for block in SEPARATION_BLOCKS:
            if db_row[block + "_parse_state"] not in SEPARATION_STATES:
                states_wrong.append(f"{name}: {block}_parse_state "
                                    f"{db_row[block + '_parse_state']!r}")
        if (db_row["properties_state"] == PROPS_ALL_KNOWN) == bool(
                db_row["unknown_property_names"] or []):
            states_wrong.append(f"{name}: состояние свойств и перечень виновников разошлись")
    check(f"{tag}: состояния строки — из замкнутых словарей слоя, виновники названы",
          not states_wrong, names(states_wrong))
    return rows_by_name, parse_rows


# ── контур 3: ключ разбора ↔ колонки живой схемы ──────────────────────────────────────────
def check_key_shape(cur, parsed, tag):
    """Числа колонок (эталон П1) и сверка ключей разбора с колонками — в обе стороны.

    Строка разбора не носит ключей, которым нет колонки (сказано в комментарии слоя к
    `read_registration_file`), а колонка, которую слой не заполняет, обязана быть названа:
    иначе «колонка есть, данных нет» читалось бы как «данных в выгрузке нет».
    """
    for table, want in EXPECTED_COLUMN_COUNTS.items():
        got = table_columns(cur, table)
        check(f"{tag}: колонок таблицы `{table}` — {want} (эталон шага П1)",
              len(got) == want, f"колонок: {len(got)}, план: {want}")

    attribute_columns = set(table_columns(cur, COMMON_ATTRIBUTE_TABLE))
    target_columns = set(table_columns(cur, COMMON_ATTRIBUTE_TARGETS_TABLE))

    parse_keys = set()
    for row in parsed["rows"]:
        parse_keys.update(row)
    content_columns = attribute_columns - set(REVISION_COLUMNS)
    if not parsed["rows"]:
        # Пустой круг (KomMag): сравнивать ключ разбора с колонками нечем. Это называется
        # пропуском, а не PASS: «ключей нет» у пустого круга — состояние выгрузки, а не
        # подтверждение формы строки.
        skip(f"{tag}: ключ строки разбора и колонки `{COMMON_ATTRIBUTE_TABLE}`",
             "файлов вида в выгрузке нет — формы строки разбора не существует, сравнивать "
             "не с чем; числа колонок проверены выше")
        skip(f"{tag}: ключ строки применения и колонки "
             f"`{COMMON_ATTRIBUTE_TARGETS_TABLE}`",
             "строк применения в разборе нет — того же круга")
    else:
        missing = sorted(parse_keys - content_columns)
        unfilled = sorted(content_columns - parse_keys)
        check(f"{tag}: ключ строки разбора и колонки `{COMMON_ATTRIBUTE_TABLE}` совпадают",
              not missing and not unfilled,
              f"ключей без колонки: {names(missing)}; "
              f"колонок без значения разбора: {names(unfilled)}")

        target_keys = set()
        for target in parsed["targets"]:
            target_keys.update(target)
        target_expected = (target_columns - set(REVISION_COLUMNS)
                           - {"common_attribute_id"})
        missing = sorted(target_keys - target_expected)
        unfilled = sorted(target_expected - target_keys)
        check(f"{tag}: ключ строки применения и колонки "
              f"`{COMMON_ATTRIBUTE_TARGETS_TABLE}` совпадают", not missing and not unfilled,
              f"ключей без колонки: {names(missing)}; "
              f"колонок без значения разбора: {names(unfilled)}")

    # Плейсхолдеры перечня свойств (Type, Content, три ссылки разделения) колонками не являются:
    # у них свои группы колонок. Перечень плейсхолдеров замкнут — иначе словарь свойств тихо
    # вырос бы, не будучи ни моделью, ни проверкой.
    placeholders = set(property_columns()) - attribute_columns
    allowed = {"type_block", "content"} | set(SEPARATION_BLOCKS)
    check(f"{tag}: плейсхолдеры словаря свойств замкнуты ({len(allowed)})",
          placeholders == allowed,
          f"факт: {names(sorted(placeholders))}, допустимо: {names(sorted(allowed))}")
    filled = set(property_columns()) - placeholders
    check(f"{tag}: свойств вида заполняется ровно {COMMON_ATTRIBUTE_PROPERTY_COUNT - len(allowed)}",
          len(filled) == COMMON_ATTRIBUTE_PROPERTY_COUNT - len(allowed),
          f"факт: {len(filled)}")


def expect_state(actual, mapping, label, expect, tag):
    """Сравнивает счётчик состояний с эталоном плана по указанному соответствию ключей."""
    wrong = [f"{label} {ekey}: факт {actual.get(ckey, 0)}, план {expect[ekey]}"
             for ekey, ckey in mapping.items() if actual.get(ckey, 0) != expect[ekey]]
    check(f"{tag}: {label} соответствуют плану", not wrong, "; ".join(wrong))
    return not wrong


# ── контур 4: строки применения ↔ файл и CURRENT-ревизия реквизита ────────────────────────
def short_attribute_name(full_name):
    """Имя файла регистрации по колонке `attribute_full_name` (`CommonAttribute.<Имя>`).

    Меры файлов ключуются именем файла (регекспой по тексту), а строки применения — полным
    индексным именем; без этой связки сравнение двух namespace читалось бы как «строк нет».
    """
    prefix = INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR
    key = str(full_name or "")
    return key[len(prefix):] if key.startswith(prefix) else key


def check_targets(parsed, attribute_rows, target_rows, raw_per_name, expect, tag):
    by_attr = {}
    for row in target_rows:
        by_attr.setdefault(row["attribute_full_name"], []).append(row)
    # Меры файлов ключуются именем файла, а строки — индексным именем реквизита: без второй
    # группировки сравнение «файл ↔ строки применения» читалось бы как «строк применения нет».
    by_short_name = {}
    for row in target_rows:
        by_short_name.setdefault(short_attribute_name(row["attribute_full_name"]),
                                 []).append(row)
    parse_by_attr = {}
    for target in parsed["targets"]:
        parse_by_attr.setdefault(target["attribute_full_name"], []).append(target)

    # 4.1 набор (порядок, цель, состояние применения, состояние разрешения, вид) = разбор.
    wrong = []
    for name, parse_list in sorted(parse_by_attr.items()):
        want = [(t["ordinal"], t["target_full_name"], t["use_state"],
                 t["target_resolve_state"], t["target_kind"])
                for t in sorted(parse_list, key=lambda t: t["ordinal"])]
        got = [(t["ordinal"], t["target_full_name"], t["use_state"],
                t["target_resolve_state"], t["target_kind"])
               for t in sorted(by_attr.get(name, []), key=lambda t: t["ordinal"])]
        if want != got:
            at = next((i for i, (a, b) in enumerate(zip(want, got)) if a != b),
                      min(len(want), len(got)))
            wrong.append(f"{name}: расхождение с позиции {at} (разбор {len(want)} строк, "
                         f"строка {len(got)}): {_brief(want[at:at + 2])} / "
                         f"{_brief(got[at:at + 2])}")
    check(f"{tag}: строки применения равны разбору перечня каждого файла",
          not wrong, names(wrong))

    # 4.2 независимая мера по тексту файла: число `<xr:Item>` = число строк применения.
    per_file_wrong = []
    for name, counts in sorted(raw_per_name.items()):
        got = len(by_short_name.get(name, []))
        if got != counts["items"]:
            per_file_wrong.append(f"{name}: строк применения {got}, тегов xr:Item в файле "
                                  f"{counts['items']}")
    check(f"{tag}: строк применения у реквизита ровно столько, сколько элементов в его файле",
          not per_file_wrong, names(per_file_wrong))

    # 4.3 порядок непрерывный, дубликатов нет (замер 2.4: повторов цели 0 — форма ключа Q2).
    gaps = []
    duplicates = []
    for name, rows in sorted(by_attr.items()):
        ordinals = sorted(row["ordinal"] for row in rows)
        if ordinals != list(range(len(ordinals))):
            gaps.append(name)
        if len({row["target_full_name"] for row in rows}) != len(rows):
            duplicates.append(name)
    check(f"{tag}: порядковые номера применения непрерывны от нуля", not gaps, names(gaps))
    check(f"{tag}: повторов цели внутри одного реквизита нет (замер 2.4)", not duplicates,
          names(duplicates))
    check(f"{tag}: диагностика повторов разбора пуста (замер 2.4)",
          not parsed["duplicate_targets"], _brief(parsed["duplicate_targets"][:MAX_NAMES]))

    # 4.4 счётчики строки согласованы с числом строк и состоянием перечня.
    counter_wrong = []
    for row in attribute_rows:
        rows = by_short_name.get(row["object_name"], [])
        used = sum(1 for item in rows if item["use_state"] == USE_USED)
        not_used = sum(1 for item in rows
                       if item["use_state"] in (USE_NOT_USED, USE_UNKNOWN_FORM))
        stored = (row["targets_count"], row["targets_used_count"],
                  row["targets_not_used_count"])
        if stored != (len(rows), used, not_used):
            counter_wrong.append(f"{row['object_name']}: счётчики {stored} ≠ "
                                 f"строк ({len(rows)}, {used}, {not_used})")
        want_state = CONTENT_WITH if rows else CONTENT_EMPTY
        if row["content_state"] != want_state:
            counter_wrong.append(f"{row['object_name']}: content_state "
                                 f"{row['content_state']!r} при {len(rows)} строках")
    check(f"{tag}: счётчики и состояние перечня согласованы со строками применения",
          not counter_wrong, names(counter_wrong))

    # 4.5 ссылка строки применения — на CURRENT-ревизию своего реквизита (Q2, вариант A).
    current_by_id = {row["id"]: row for row in attribute_rows}
    link_wrong = []
    for row in target_rows:
        parent = current_by_id.get(row["common_attribute_id"])
        if parent is None:
            link_wrong.append(f"{row['target_full_name']}: common_attribute_id "
                              f"{row['common_attribute_id']} не является CURRENT-строкой")
            continue
        if short_attribute_name(row["attribute_full_name"]) != parent["object_name"]:
            link_wrong.append(f"{row['target_full_name']}: attribute_full_name "
                              f"{row['attribute_full_name']!r} ≠ индекного имени родителя "
                              f"{parent['object_name']!r}")
        if str(parent["object_uuid"]).lower() != str(row["attribute_object_uuid"]).lower():
            link_wrong.append(f"{row['target_full_name']}: attribute_object_uuid ≠ родителя")
        if str(parent["configuration_uuid"]) != str(row["configuration_uuid"]):
            link_wrong.append(f"{row['target_full_name']}: configuration_uuid разошёлся с "
                              f"родителем")
    check(f"{tag}: каждая строка применения ведёт на CURRENT-ревизию своего реквизита",
          not link_wrong, names(link_wrong))

    # 4.6 разбивка состояний применения и видов целей — эталон плана (замеры 2.4, 2.5).
    use_counts = Counter(row["use_state"] for row in target_rows)
    expect_state({USE_USED: use_counts.get(USE_USED, 0),
                  USE_NOT_USED: use_counts.get(USE_NOT_USED, 0),
                  USE_UNKNOWN_FORM: use_counts.get(USE_UNKNOWN_FORM, 0)},
                 {"used": USE_USED, "not_used": USE_NOT_USED,
                  "use_unknown": USE_UNKNOWN_FORM}, "состояния применения", expect, tag)
    kind_counts = Counter(row["target_kind"] for row in target_rows)
    wrong = []
    for key, want in expect.items():
        if not key.startswith("kind_"):
            continue
        got = kind_counts.get(key[5:], 0)
        if got != want:
            wrong.append(f"вид цели {key[5:]}: факт {got}, план {want}")
    extra = sorted(kind for kind, value in kind_counts.items()
                   if f"kind_{kind}" not in expect and value)
    if extra:
        wrong.append("виды целей вне эталона: " + names(extra))
    check(f"{tag}: виды целей применения соответствуют плану (замер 2.5)", not wrong,
          "; ".join(wrong))

    # 4.7 состояние `<xr:ConditionalSeparation/>` внутри элемента: на корпусе пустой тег —
    # 1 512 из 1 512 (замер 2.4), и это проверяется, а не предполагается.
    cond_counts = Counter(row["conditional_separation_state"] for row in target_rows)
    check(f"{tag}: непустых `<xr:ConditionalSeparation/>` внутри перечня нет (замер 2.4)",
          all(key == ITEM_COND_EMPTY for key in cond_counts),
          _brief(dict(cond_counts)))
    return by_attr


# ── контур 5: разрешимость целей — повторное разрешение по индексу ────────────────────────
def check_target_resolution(parsed, target_rows, index_info, expect, tag):
    """Каждая сохранённая цель разрешается заново, независимо от сохранённого результата."""
    index_by_name = index_rows_by_name(index_info["rows"])
    wrong = []
    for row in target_rows:
        resolution = resolve_target(row["target_full_name"], index_by_name)
        if resolution["state"] != row["target_resolve_state"]:
            wrong.append(f"{row['target_full_name']}: состояние "
                         f"{row['target_resolve_state']!r} ≠ повторного "
                         f"{resolution['state']!r}")
        want_id = resolution["object_id"] or None
        if want_id != (row["target_object_id"] or None):
            wrong.append(f"{row['target_full_name']}: object_id "
                         f"{row['target_object_id']!r} ≠ индекса {want_id!r}")
        want_uuid = (resolution["object_uuid"] or "").lower() or None
        stored_uuid = (str(row["target_object_uuid"]).lower()
                       if row["target_object_uuid"] else None)
        if want_uuid != stored_uuid:
            wrong.append(f"{row['target_full_name']}: object_uuid {stored_uuid} ≠ "
                         f"индекса {want_uuid}")
        if target_kind(row["target_full_name"]) != row["target_kind"]:
            wrong.append(f"{row['target_full_name']}: target_kind "
                         f"{row['target_kind']!r} ≠ первого сегмента имени")
    check(f"{tag}: каждая цель разрешается индексом заново так же, как сохранена",
          not wrong, names(wrong))

    # Граница состояний: `exact` несёт ключ цели, `prefix_only`/`unresolved` — остаток пути
    # и пустой ключ (Q3: «не разрешилось» и «не было» различимы).
    shape_wrong = []
    for row in target_rows:
        state = row["target_resolve_state"]
        if state == TARGET_EXACT:
            if not row["target_object_id"]:
                shape_wrong.append(f"{row['target_full_name']}: exact без object_id")
            if row["target_unresolved_path"]:
                shape_wrong.append(f"{row['target_full_name']}: exact с остатком пути")
        elif state in (TARGET_PREFIX_ONLY, TARGET_UNRESOLVED):
            if row["target_object_uuid"] or row["target_object_id"]:
                shape_wrong.append(f"{row['target_full_name']}: {state} с ключом цели")
            if not row["target_unresolved_path"]:
                shape_wrong.append(f"{row['target_full_name']}: {state} без остатка пути")
        else:
            shape_wrong.append(f"{row['target_full_name']}: состояние {state!r} "
                               f"вне словаря {TARGET_RESOLVE_STATES}")
    check(f"{tag}: форма строк разрешения соответствует состоянию (Q3)", not shape_wrong,
          names(shape_wrong))

    resolve_counts = Counter(row["target_resolve_state"] for row in target_rows)
    expect_state({TARGET_EXACT: resolve_counts.get(TARGET_EXACT, 0),
                  TARGET_PREFIX_ONLY: resolve_counts.get(TARGET_PREFIX_ONLY, 0),
                  TARGET_UNRESOLVED: resolve_counts.get(TARGET_UNRESOLVED, 0)},
                 {"resolve_exact": TARGET_EXACT, "resolve_prefix": TARGET_PREFIX_ONLY,
                  "resolve_unresolved": TARGET_UNRESOLVED},
                 "разрешение целей (замер 2.6)", expect, tag)
    check(f"{tag}: диагностики неразрешённых целей разбора нет (замер 2.6)",
          not parsed["unresolved_targets"],
          _brief(parsed["unresolved_targets"][:MAX_NAMES]))
    distinct = len({row["target_full_name"] for row in target_rows})
    check(f"{tag}: мера различных целей равна плану (замер 2.4)",
          distinct == expect["targets_distinct"],
          f"факт: {distinct}, план: {expect['targets_distinct']}")


# ── контур 6: словари значений свойств ────────────────────────────────────────────────────
def check_dictionaries(attribute_rows, expect, tag, corpus=False):
    """Значения словарных свойств — внутри замкнутого словаря слоя (замер 2.7).

    Сравнение распределения значений с таблицей 2.7 включается только по полному кругу:
    словарь мерился по 16 файлам четырёх выгрузок, сумма по трём дала бы ложное расхождение.
    """
    enum_columns = [column for _name, column, _kind in COMMON_ATTRIBUTE_PROPERTIES
                    if property_kind(column) == "enum"]
    bool_columns = [column for _name, column, _kind in COMMON_ATTRIBUTE_PROPERTIES
                    if property_kind(column) == "bool"]
    outside = []
    value_counts = Counter()
    for row in attribute_rows:
        for column in enum_columns:
            value = row[column]
            dictionary = value_dictionary(column)
            if value is None:
                outside.append(f"{row['object_name']}.{column}: значения нет")
            elif value not in dictionary:
                outside.append(f"{row['object_name']}.{column}: {value!r} вне словаря "
                               f"{list(dictionary)}")
            else:
                value_counts[(column, value)] += 1
        for column in bool_columns:
            value = row[column]
            if not isinstance(value, bool):
                outside.append(f"{row['object_name']}.{column}: {value!r} — не boolean")
            else:
                value_counts[(column, "true" if value else "false")] += 1
    check(f"{tag}: значения свойств внутри замкнутого словаря слоя "
          f"(колонок со словарём: {len(enum_columns)})", not outside, names(outside))

    # Состояния свойств и перечня: `unknown_value`/`unknown_tag` отсутствуют (раздел 7 плана).
    state_counts = Counter(row["properties_state"] for row in attribute_rows)
    expect_state({PROPS_ALL_KNOWN: state_counts.get(PROPS_ALL_KNOWN, 0),
                  PROPS_UNKNOWN_VALUE: state_counts.get(PROPS_UNKNOWN_VALUE, 0),
                  PROPS_UNKNOWN_TAG: state_counts.get(PROPS_UNKNOWN_TAG, 0)},
                 {"all_known": PROPS_ALL_KNOWN, "unknown_value": PROPS_UNKNOWN_VALUE,
                  "unknown_tag": PROPS_UNKNOWN_TAG}, "состояния свойств", expect, tag)
    content_counts = Counter(row["content_state"] for row in attribute_rows)
    expect_state({CONTENT_WITH: content_counts.get(CONTENT_WITH, 0),
                  CONTENT_EMPTY: content_counts.get(CONTENT_EMPTY, 0)},
                 {"with_content": CONTENT_WITH, "empty_content": CONTENT_EMPTY},
                 "состояния перечня (замер 2.4)", expect, tag)

    if not corpus:
        return value_counts
    wrong = []
    for column, expected in list(PROPERTY_VALUE_COUNTS.items()) + \
            list(BOOL_VALUE_COUNTS.items()):
        for value, want in expected.items():
            got = value_counts.get((column, value), 0)
            if got != want:
                wrong.append(f"{column}={value}: факт {got}, план {want}")
        for col, value in value_counts:
            if col == column and value not in expected:
                wrong.append(f"{column}={value}: значение вне эталона "
                             f"({value_counts[(col, value)]})")
    check(f"{tag}: распределение значений свойств равно таблице 2.7 по корпусу",
          not wrong, "; ".join(wrong))
    return value_counts


# ── контур 7: блоки разделения данных ─────────────────────────────────────────────────────
def check_separation(parsed, attribute_rows, raw_per_name, index_info, expect, tag):
    """Пустой блок называется состоянием, непустой — разрешённой ссылкой (замер 2.7)."""
    index_by_name = index_rows_by_name(index_info["rows"])
    state_counts = Counter()
    ref_counts = Counter()
    wrong = []
    for row in attribute_rows:
        for block in SEPARATION_BLOCKS:
            state = row[block + "_parse_state"]
            state_counts[state] += 1
            ref_text = row[block + "_ref_text"]
            object_id = row[block + "_object_id"]
            object_uuid = row[block + "_object_uuid"]
            resolve_state = row[block + "_resolve_state"]
            if state not in SEPARATION_STATES:
                wrong.append(f"{row['object_name']}.{block}: состояние {state!r}")
                continue
            if state == SEP_EMPTY:
                if any(value is not None
                       for value in (ref_text, object_id, object_uuid, resolve_state)):
                    wrong.append(f"{row['object_name']}.{block}: пустой блок несёт ссылку")
                continue
            if not ref_text:
                wrong.append(f"{row['object_name']}.{block}: {state} без текста ссылки")
                continue
            ref_counts[ref_text] += 1
            resolution = resolve_target(ref_text, index_by_name)
            if resolution["state"] != TARGET_EXACT:
                wrong.append(f"{row['object_name']}.{block}: цель {ref_text!r} разрешена "
                             f"состоянием {resolution['state']!r}")
            if resolve_state != resolution["state"]:
                wrong.append(f"{row['object_name']}.{block}: состояние разрешения "
                             f"{resolve_state!r} ≠ повторного {resolution['state']!r}")
            if (object_id or None) != (resolution["object_id"] or None):
                wrong.append(f"{row['object_name']}.{block}: object_id ≠ индекса состава")
            stored_uuid = (str(object_uuid).lower() if object_uuid else None)
            want_uuid = (resolution["object_uuid"] or "").lower() or None
            if stored_uuid != want_uuid:
                wrong.append(f"{row['object_name']}.{block}: object_uuid ≠ индекса состава")
    check(f"{tag}: блоки разделения названы состоянием, непустые — разрешённой ссылкой",
          not wrong, names(wrong))

    # Независимая мера по файлам: пустой тег против тега со значением (замер 2.7).
    file_wrong = []
    for name, counts in sorted(raw_per_name.items()):
        row = next((item for item in attribute_rows if item["object_name"] == name), None)
        if row is None:
            continue
        for block in SEPARATION_BLOCKS:
            want_parsed = counts.get("sep_%s_parsed" % block, 0)
            want_empty = counts.get("sep_%s_empty" % block, 0)
            got_parsed = 1 if row[block + "_parse_state"] == SEP_PARSED else 0
            got_empty = 1 if row[block + "_parse_state"] == SEP_EMPTY else 0
            if (got_parsed, got_empty) != (want_parsed, want_empty):
                file_wrong.append(f"{name}.{block}: в файле parsed={want_parsed} "
                                  f"empty={want_empty}, в строке parsed={got_parsed} "
                                  f"empty={got_empty}")
            if want_parsed > 1:
                file_wrong.append(f"{name}.{block}: в файле {want_parsed} значений блока — "
                                  f"модель ждёт одно (замер 2.7)")
    check(f"{tag}: пустые и непустые блоки разделения равны файлу (замер 2.7)",
          not file_wrong, names(file_wrong))

    expect_state({SEP_PARSED: state_counts.get(SEP_PARSED, 0),
                  SEP_EMPTY: state_counts.get(SEP_EMPTY, 0),
                  SEP_UNKNOWN_FORM: state_counts.get(SEP_UNKNOWN_FORM, 0)},
                 {"sep_parsed_total": SEP_PARSED, "sep_empty_total": SEP_EMPTY,
                  "sep_unknown_total": SEP_UNKNOWN_FORM},
                 "состояния блоков разделения (замер 2.7)", expect, tag)
    check(f"{tag}: диагностики неразрешённых ссылок разделения нет (замер 2.7)",
          not parsed["unresolved_refs"], _brief(parsed["unresolved_refs"][:MAX_NAMES]))
    return ref_counts


# ── контур 8: блок `<Type>` ───────────────────────────────────────────────────────────────
QUALIFIER_KEYS = {"string": "StringQualifiers", "number": "NumberQualifiers",
                  "date": "DateQualifiers"}


def file_type_values(counts):
    """Мультмножество значений `<v8:Type>` файла по независимому подсчёту."""
    values = []
    for key, value in counts.items():
        if key.startswith("v8type_"):
            values.extend([key[len("v8type_"):]] * value)
    return sorted(values)


def check_type_blocks(attribute_rows, raw_per_name, raw_blocks, expect, tag):
    """Состояния, кратность и содержимое блока типа равны файлу (замер 2.3)."""
    state_counts = Counter()
    mult_counts = Counter()
    value_counts = Counter()
    qualifier_counts = Counter()
    wrong = []
    for row in attribute_rows:
        state_counts[row["type_parse_state"]] += 1
        mult_counts[row["type_multiplicity"]] += 1
        entries = row["types"] or []
        if multiplicity_of(len(entries)) != row["type_multiplicity"]:
            wrong.append(f"{row['object_name']}: кратность {row['type_multiplicity']!r} при "
                         f"{len(entries)} записях типа")
        if (not entries) != (row["type_parse_state"] == STATE_ABSENT):
            wrong.append(f"{row['object_name']}: пустой массив `types` и состояние "
                         f"{row['type_parse_state']!r} разошлись")
        for entry in entries:
            value_counts[str(entry.get("value"))] += 1
            if entry.get("class") not in TYPE_CLASS_VALUES:
                wrong.append(f"{row['object_name']}: класс записи {entry.get('class')!r} "
                             f"вне словаря слоя")
        for key in (row["type_qualifiers"] or {}):
            qualifier_counts[str(key)] += 1
    check(f"{tag}: состояния, кратность и классы записей типа согласованы внутри строки",
          not wrong, names(wrong))

    # Сравнение с файлом: записи `types` = теги `<v8:Type>`, квалификаторы = блоки
    # квалификаторов, `type_raw` = блок `<Type>` файла.
    file_wrong = []
    for name, counts in sorted(raw_per_name.items()):
        row = next((item for item in attribute_rows if item["object_name"] == name), None)
        if row is None:
            continue
        entries = row["types"] or []
        if len(entries) != counts["v8_type_tags"]:
            file_wrong.append(f"{name}: записей типа {len(entries)}, тегов v8:Type в файле "
                              f"{counts['v8_type_tags']}")
        stored_values = sorted(str(entry.get("value")) for entry in entries)
        if stored_values != file_type_values(counts):
            file_wrong.append(f"{name}: значения типа {_brief(stored_values)} ≠ файлу "
                              f"{_brief(file_type_values(counts))}")
        for key, qualifier_tag in QUALIFIER_KEYS.items():
            want = counts.get("qualifier_" + key, 0)
            got = 1 if qualifier_tag in (row["type_qualifiers"] or {}) else 0
            if want != got:
                file_wrong.append(f"{name}: квалификаторов {key} в файле {want}, в строке "
                                  f"{got}")
        if (row["type_raw"] or "") != (raw_blocks.get(name) or ""):
            file_wrong.append(f"{name}: type_raw ≠ блоку `<Type>` файла")
    check(f"{tag}: содержимое блока типа равно тегам `<v8:Type>` и квалификаторам файла",
          not file_wrong, names(file_wrong))

    expect_state({STATE_PARSED: state_counts.get(STATE_PARSED, 0),
                  STATE_PARTIAL: state_counts.get(STATE_PARTIAL, 0),
                  STATE_ABSENT: state_counts.get(STATE_ABSENT, 0),
                  STATE_UNKNOWN_FORM: state_counts.get(STATE_UNKNOWN_FORM, 0)},
                 {"type_parsed": STATE_PARSED, "type_partial": STATE_PARTIAL,
                  "type_absent": STATE_ABSENT, "type_unknown_form": STATE_UNKNOWN_FORM},
                 "состояния блока типа (замер 2.3)", expect, tag)
    expect_state({MULT_SINGLE: mult_counts.get(MULT_SINGLE, 0),
                  MULT_COMPOSITE: mult_counts.get(MULT_COMPOSITE, 0),
                  MULT_ABSENT: mult_counts.get(MULT_ABSENT, 0)},
                 {"mult_single": MULT_SINGLE, "mult_composite": MULT_COMPOSITE,
                  "mult_absent": MULT_ABSENT}, "кратность блока типа (замер 2.3)", expect, tag)
    return value_counts, qualifier_counts


# ── контур 9: пустой круг — состояние выгрузки, а не отказ ────────────────────────────────
def check_empty_circle(cur, header, dump_dir, index_info, expect, tag):
    """У позиции вида в выгрузке нет ни файлов, ни строк индекса, ни перечня (замер 2.9, Q9).

    Нули здесь — проверяемое утверждение о выгрузке, а не отсутствие данных: наблюдение
    `directory_missing` обязано быть названо, иначе пустой круг читался бы как «общих
    реквизитов в конфигурации нет», чего выгрузки с каталогом не подтверждают.
    """
    directory = Path(dump_dir) / DIR_NAME
    check(f"{tag}: каталога вида нет — это состояние выгрузки (замер 2.9)",
          not directory.exists(), f"каталог существует: {directory}")
    parsed = parse_circle(dump_dir, index_info["rows"])
    check(f"{tag}: файлов вида найдено ноль", parsed["files_found"] == 0,
          f"найдено: {parsed['files_found']}")
    kinds = Counter(kind for kind, _detail in parsed["observations"])
    check(f"{tag}: круг описан наблюдением `directory_missing` (Q9)",
          kinds.get("directory_missing", 0) == expect["directory_missing"] and
          len(kinds) == 1, _brief(dict(kinds)))
    found_index = len(kind_index_rows(index_info["rows"]))
    check(f"{tag}: записей индекса состава вида — ноль",
          found_index == expect["index_rows"], f"факт: {found_index}")
    header_names, header_is_null = read_header_name_list(cur, str(header["uuid"]))
    check(f"{tag}: перечня вида в заголовке нет значением NULL",
          header_is_null and not header_names, f"значений: {len(header_names)}")
    attribute_rows = read_attribute_rows(cur, str(header["uuid"]))
    target_rows = read_target_rows(cur, str(header["uuid"]))
    check(f"{tag}: строк вида в обеих таблицах — ноль",
          not attribute_rows and not target_rows,
          f"реквизитов: {len(attribute_rows)}, применения: {len(target_rows)}")
    info(f"{tag}: пустой круг назван состоянием выгрузки; стадия `{STAGE_COMMON_ATTRIBUTES}` "
         f"при этом не отказывает, отдельный вход группы — `load_common_attributes_tool`")
    return {"attribute_rows": [], "target_rows": [], "parsed": parsed,
            "header_names": [], "index_rows": found_index, "index_children": 0,
            "file_stems": set(), "header_is_null": header_is_null}


# ── контур 10: целостность схемы, витрин и цепи ревизий ──────────────────────────────────
def check_orphans(cur):
    """Ссылок вникуда быть не должно: сироты применения и осиротевшие строки вида."""
    orphans = q(cur, f"SELECT t.id, t.target_full_name FROM {COMMON_ATTRIBUTE_TARGETS_TABLE} t "
                     f"LEFT JOIN {ATTRIBUTES_VIEW} a ON a.id = t.common_attribute_id "
                     f"WHERE a.id IS NULL ORDER BY t.id LIMIT {MAX_NAMES}")
    check("сирот применения (строка не ведёт на CURRENT-ревизию реквизита) нет",
          not orphans, _brief(orphans))
    stray = q(cur, f"SELECT a.id, a.object_name FROM {COMMON_ATTRIBUTE_TABLE} a "
                   f"LEFT JOIN configurations c ON c.uuid = a.configuration_uuid "
                   f"WHERE c.uuid IS NULL ORDER BY a.id LIMIT {MAX_NAMES}")
    check("строк вида без строки заголовка конфигурации нет", not stray, _brief(stray))
    cross = q(cur, f"SELECT t.id FROM {COMMON_ATTRIBUTE_TARGETS_TABLE} t "
                   f"JOIN {COMMON_ATTRIBUTE_TABLE} a ON a.id = t.common_attribute_id "
                   f"WHERE a.configuration_uuid <> t.configuration_uuid "
                   f"ORDER BY t.id LIMIT {MAX_NAMES}")
    check("строк применения чужой конфигурации нет", not cross, _brief(cross))


def check_key_definitions(cur):
    """Ключи узла живые: `UNIQUE (configuration_uuid, object_name, revision_no)` и
    `UNIQUE (common_attribute_id, ordinal)`; индекс по `target_full_name` — это и есть запрос
    «какие общие реквизиты у этого объекта» (модель раздела 4 плана)."""
    wanted = {
        COMMON_ATTRIBUTE_TABLE: ["configuration_uuid", "object_name", "revision_no"],
        COMMON_ATTRIBUTE_TARGETS_TABLE: ["common_attribute_id", "ordinal"],
    }
    for table, columns in wanted.items():
        defs = [row["indexdef"] for row in q(cur, "SELECT indexdef FROM pg_indexes "
                                                  "WHERE tablename = %s", (table,))]
        unique_defs = [definition for definition in defs
                       if definition.startswith("CREATE UNIQUE INDEX")]
        found = any(all(column in definition for column in columns)
                    for definition in unique_defs)
        check(f"ключ UNIQUE {columns} таблицы `{table}` объявлен", found,
              _brief(unique_defs))
    indexed = q(cur, "SELECT indexname FROM pg_indexes WHERE tablename = %s "
                     "AND indexdef LIKE %s", (COMMON_ATTRIBUTE_TARGETS_TABLE,
                                              "%target_full_name%"))
    check("индекс по `target_full_name` живётся (запрос «какие реквизиты у объекта»)",
          bool(indexed), _brief(indexed))


def check_views(cur, headers):
    """Витрины текущего состояния дают ровно то же, что таблицы по CURRENT-ревизиям."""
    for header in headers:
        cfg_uuid = str(header["uuid"])
        table_attrs = int(one(cur, f"SELECT count(*) AS c FROM {COMMON_ATTRIBUTE_TABLE} "
                                  f"WHERE configuration_uuid = %s::uuid",
                              (cfg_uuid,)).get("c") or 0)
        view_attrs = int(one(cur, f"SELECT count(*) AS c FROM {ATTRIBUTES_VIEW} "
                                  f"WHERE configuration_uuid = %s::uuid",
                             (cfg_uuid,)).get("c") or 0)
        table_targets = int(one(cur, f"SELECT count(*) AS c FROM "
                                    f"{COMMON_ATTRIBUTE_TARGETS_TABLE} "
                                    f"WHERE configuration_uuid = %s::uuid",
                               (cfg_uuid,)).get("c") or 0)
        view_targets = int(one(cur, f"SELECT count(*) AS c FROM {TARGETS_VIEW} "
                                    f"WHERE configuration_uuid = %s::uuid",
                               (cfg_uuid,)).get("c") or 0)
        check(f"{header['name']}: витрина `{ATTRIBUTES_VIEW}` равна строкам таблицы",
              view_attrs == table_attrs, f"витрина: {view_attrs}, таблица: {table_attrs}")
        check(f"{header['name']}: витрина `{TARGETS_VIEW}` равна строкам таблицы",
              view_targets == table_targets,
              f"витрина: {view_targets}, таблица: {table_targets}")
        duplicates = q(cur, f"SELECT object_name, count(*) AS c FROM {ATTRIBUTES_VIEW} "
                            f"WHERE configuration_uuid = %s::uuid "
                            f"GROUP BY object_name HAVING count(*) > 1 "
                            f"ORDER BY object_name LIMIT {MAX_NAMES}", (cfg_uuid,))
        check(f"{header['name']}: у имени в витрине ровно одна CURRENT-ревизия",
              not duplicates, _brief(duplicates))
        broken = q(cur, f"SELECT object_name, min(revision_no) AS min_rev "
                        f"FROM {COMMON_ATTRIBUTE_TABLE} "
                        f"WHERE configuration_uuid = %s::uuid AND revision_no < 1 "
                        f"GROUP BY object_name ORDER BY object_name LIMIT {MAX_NAMES}",
                   (cfg_uuid,))
        check(f"{header['name']}: номера ревизий вида не нулевые", not broken, _brief(broken))


# ── итог по корпусу: сумма по четырём выгрузкам равна разделу 2 плана ─────────────────────
DB_TOTAL_KEYS = ("attr_rows", "target_rows", "used", "not_used", "use_unknown",
                 "resolve_exact", "resolve_prefix", "resolve_unresolved",
                 "with_content", "empty_content", "all_known", "unknown_value", "unknown_tag",
                 "type_parsed", "type_partial", "type_absent", "type_unknown_form",
                 "mult_single", "mult_composite", "mult_absent",
                 "sep_parsed_total", "sep_empty_total", "sep_unknown_total",
                 "index_rows", "index_children", "header_list",
                 "observations", "index_only", "file_only", "uuid_mismatch",
                 "name_file_mismatch", "directory_missing")
RAW_TOTAL_KEYS = ("files", "bytes", "subdirs", "non_xml", "props_block", "prop_tags_total",
                  "prop_tags_distinct", "type_block", "v8_type_tags", "qualifier_string",
                  "qualifier_number", "qualifier_date", "has_content", "items", "metadata",
                  "use_Use", "use_DontUse", "item_cond_empty", "item_cond_any")
PREFIX_TOTAL_KEYS = ("kind_", "v8type_", "sep_")


def check_aggregate(totals, run_tags, skipped_tags):
    """Сумма по всем четырём выгрузкам равна итогам раздела 2 (мера — по корпусу 16 файлов)."""
    if set(run_tags) != set(PLAN_EXPECTATIONS):
        skip("итог по корпусу (разделы 2.1–2.9, 7)",
             f"прогону доступны выгрузки {names(sorted(run_tags))}, а итог плана снят по "
             f"четыём ({names(sorted(PLAN_EXPECTATIONS))}); сравнивать сумму по меньшему "
             f"числу выгрузок с итогом по корпусу — значит получить ложное расхождение. "
             f"Пропущено: {names(sorted(skipped_tags))}")
        return
    wrong = []
    for key, want in CORPUS_TOTALS.items():
        got = totals.get(key, 0)
        if got != want:
            wrong.append(f"{key}: факт {got}, план {want}")
    extra = sorted(key for key, value in totals.items()
                   if key not in CORPUS_TOTALS and value and
                   (key in DB_TOTAL_KEYS or key in RAW_TOTAL_KEYS or
                    any(key.startswith(p) for p in PREFIX_TOTAL_KEYS)))
    if extra:
        wrong.append("величины вне эталона: " + names(extra))
    check("итог по четырём выгрузкам равен итогам раздела 2 плана", not wrong,
          "; ".join(wrong))


def add_totals(totals, raw_totals, circle):
    """Суммирует меры одной выгрузки в общий итог по корпусу."""
    parsed = circle["parsed"]
    attribute_rows = circle["attribute_rows"]
    target_rows = circle["target_rows"]
    for key in RAW_TOTAL_KEYS:
        totals[key] += raw_totals.get(key, 0)
    for key, value in raw_totals.items():
        if any(key.startswith(prefix) for prefix in PREFIX_TOTAL_KEYS):
            totals[key] += value
    totals["attr_rows"] += len(attribute_rows)
    totals["target_rows"] += len(target_rows)
    use_counts = Counter(row["use_state"] for row in target_rows)
    totals["used"] += use_counts.get(USE_USED, 0)
    totals["not_used"] += use_counts.get(USE_NOT_USED, 0)
    totals["use_unknown"] += use_counts.get(USE_UNKNOWN_FORM, 0)
    resolve_counts = Counter(row["target_resolve_state"] for row in target_rows)
    totals["resolve_exact"] += resolve_counts.get(TARGET_EXACT, 0)
    totals["resolve_prefix"] += resolve_counts.get(TARGET_PREFIX_ONLY, 0)
    totals["resolve_unresolved"] += resolve_counts.get(TARGET_UNRESOLVED, 0)
    content_counts = Counter(row["content_state"] for row in attribute_rows)
    totals["with_content"] += content_counts.get(CONTENT_WITH, 0)
    totals["empty_content"] += content_counts.get(CONTENT_EMPTY, 0)
    properties_counts = Counter(row["properties_state"] for row in attribute_rows)
    totals["all_known"] += properties_counts.get(PROPS_ALL_KNOWN, 0)
    totals["unknown_value"] += properties_counts.get(PROPS_UNKNOWN_VALUE, 0)
    totals["unknown_tag"] += properties_counts.get(PROPS_UNKNOWN_TAG, 0)
    type_counts = Counter(row["type_parse_state"] for row in attribute_rows)
    totals["type_parsed"] += type_counts.get(STATE_PARSED, 0)
    totals["type_partial"] += type_counts.get(STATE_PARTIAL, 0)
    totals["type_absent"] += type_counts.get(STATE_ABSENT, 0)
    totals["type_unknown_form"] += type_counts.get(STATE_UNKNOWN_FORM, 0)
    mult_counts = Counter(row["type_multiplicity"] for row in attribute_rows)
    totals["mult_single"] += mult_counts.get(MULT_SINGLE, 0)
    totals["mult_composite"] += mult_counts.get(MULT_COMPOSITE, 0)
    totals["mult_absent"] += mult_counts.get(MULT_ABSENT, 0)
    sep_counts = Counter(row[block + "_parse_state"] for row in attribute_rows
                         for block in SEPARATION_BLOCKS)
    totals["sep_parsed_total"] += sep_counts.get(SEP_PARSED, 0)
    totals["sep_empty_total"] += sep_counts.get(SEP_EMPTY, 0)
    totals["sep_unknown_total"] += sep_counts.get(SEP_UNKNOWN_FORM, 0)
    totals["index_rows"] += circle["index_rows"]
    totals["index_children"] += circle["index_children"]
    totals["header_list"] += len(circle["header_names"])
    totals["observations"] += len(parsed["observations"])
    totals["index_only"] += len(parsed["index_only"])
    totals["file_only"] += len(parsed["file_only"])
    totals["uuid_mismatch"] += len(parsed["uuid_mismatch"])
    totals["name_file_mismatch"] += len(circle["file_stems"] ^
                                        {row["object_name"] for row in parsed["rows"]})
    totals["directory_missing"] += sum(1 for kind, _detail in parsed["observations"]
                                      if kind == "directory_missing")


def run(cur, scope):
    headers = q(cur, "SELECT id, uuid::text AS uuid, name FROM configurations ORDER BY id")
    if not headers:
        print("FAIL строк заголовков конфигураций в базе нет — сравнивать не с чем")
        FAILED.append("нет строк заголовков")
        return
    attribute_columns = table_columns(cur, COMMON_ATTRIBUTE_TABLE)
    before = foreign_state(cur)
    totals = Counter()
    run_tags, skipped_tags = [], []
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
                 f"выгрузки надо переснять и записать в план прежде, чем сравнивать с ними")
            continue
        index_info = read_index_records(cur, int(header["id"]))
        if not index_info["available"]:
            skipped_tags.append(tag)
            skip(f"{tag}: контуры круга, разрешения целей и словаря состояний",
                 index_info.get("reason") or "индекс состава этого заголовка не загружен: "
                                            "сверка файлов с перечнем и разрешение целей "
                                            "невыразимы")
            continue
        if expect["directory_missing"]:
            circle = check_empty_circle(cur, header, dump_dir, index_info, expect, tag)
            raw_totals, _per_name, _raw_blocks, _unreadable, _obs = raw_measures(dump_dir)
            check_key_shape(cur, circle["parsed"], tag)
            add_totals(totals, raw_totals, circle)
            run_tags.append(tag)
            continue
        circle = check_circle(cur, header, dump_dir, index_info, expect, tag)
        attribute_rows = circle["attribute_rows"]
        if not attribute_rows:
            skipped_tags.append(tag)
            skip(f"{tag}: контуры «файл ↔ строка», применения, словарей и блоков",
                 "строк вида в таблице нет — конфигурацию не перезагружали после узла V50 "
                 "(стадия `s4e_common_attributes` входит в загрузку каталога, отдельный вход "
                 "группы — `load_common_attributes_tool`)")
            continue
        if dump_newer_than_rows(dump_dir, attribute_rows):
            skipped_tags.append(tag)
            skip(f"{tag}: контуры «файл ↔ строка» и мер файла",
                 "файлы выгрузки новее строк узла (правило R5): сохранённые строки описывают "
                 "прошлое состояние, сравнение с ним было бы сравнением с прошлым")
            continue
        raw_totals, per_name, raw_blocks, unreadable, _obs = raw_measures(dump_dir)
        check(f"{tag}: файлов круга, которые не удалось прочитать, нет", not unreadable,
              _brief(unreadable[:MAX_NAMES]))
        check(f"{tag}: круг файлов измерен полностью",
              raw_totals["files"] == expect["files"],
              f"измерено файлов: {raw_totals['files']}, ожидается: {expect['files']}")
        check_property_tags(per_name, tag)
        counts_diff(raw_totals, raw_expectations(expect), "независимые меры файлов", tag)
        check_key_shape(cur, circle["parsed"], tag)
        check_attribute_rows(circle["parsed"], attribute_rows, attribute_columns, tag)
        check_targets(circle["parsed"], attribute_rows, circle["target_rows"], per_name,
                      expect, tag)
        check_target_resolution(circle["parsed"], circle["target_rows"], index_info,
                                expect, tag)
        check_dictionaries(attribute_rows, expect, tag)
        check_separation(circle["parsed"], attribute_rows, per_name, index_info, expect, tag)
        check_type_blocks(attribute_rows, per_name, raw_blocks, expect, tag)
        add_totals(totals, raw_totals, circle)
        run_tags.append(tag)

    after = foreign_state(cur)
    section("Итог узла V50")
    check_orphans(cur)
    check_key_definitions(cur)
    check_views(cur, headers)
    check_untouched(before, after)
    if set(run_tags) == set(PLAN_EXPECTATIONS):
        # Распределение значений свойств (таблица 2.7) мерилось по 16 файлам четырёх
        # выгрузок: сравнивать его с суммой по меньшему числу выгрузок — ложное расхождение.
        all_rows = []
        for header in headers:
            all_rows.extend(read_attribute_rows(cur, str(header["uuid"])))
        check_dictionaries(all_rows, CORPUS_TOTALS, "корпус", corpus=True)
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
