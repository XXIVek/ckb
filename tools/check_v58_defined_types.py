#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/check_v58_defined_types.py — узел V58: определяемые типы (позиция 2.13 нормативного
списка), шаг П6 — постоянная проверка узла.

Это постоянная проверка, а не проба шага (правило 3 карточки
`rules:core-rules:functional:per-block-table-view-checks`): она обязана переживать и
перезагрузку выгрузок, и правки кода загрузки. Источник ожиданий —
`docs/CONFIGURATION_DEFINED_TYPES_PLAN.md` (раздел 1 — круг четырьмя ногами и его цена,
раздел 2 — словарь четырёх тегов, ФОРМЫ значения, квалификаторы и разрешение целей,
раздел 3 — состояние живой схемы до узла, раздел 5 — M1…M8, раздел 9 — критерии
готовности). Числа перенесены из замеров `_v58_p0_probe.py`, `_v58_p0_shape_check.py`,
`_v58_p3_offline_probe.py` и из живой БД без правок: сглаживать число проверкой — значит
подтверждать неверное число (прецедент узлов V49…V57).

Два числа плана требуют разного обращения, и оба названы отдельными проверками:

  * раздел 2.2 плана называет 191 БЛОК квалификаторов при 182 ФАЙЛАХ с ними — проверка
    держит оба числа раздельно, потому что строка `defined_types` одна на файл, а
    `type_qualifiers` хранит блоки этого файла вместе: мерой писателя и витрины является
    182, мерой содержимого — 191;
  * раздел 2.5 плана писал «66 строк BGU2» про записи вида `BusinessProcess` в индексе
    состава — прогон по живой `configuration_objects` даёт 43 (BGU2), 501 (BP3) и 3
    (MinCfg). Смысл абзаца прогон подтверждает: записей, где `object_type` или
    `object_name` содержит `RoutePoint`, — ноль на всех четырёх выгрузках, поэтому
    эталоном становится измеренное число, а расхождение с текстом плана правится этим же
    шагом (прецедент раздела 1.2 плана V57).

Что сторожится — по контурам:

  1. ГРАНИЦА СХЕМЫ (контур 1). Одна таблица узла (`defined_types`) и ровно одна: второй
     таблицы значений у вида нет осознанно (Q1, вариант A), и обход схемы по маске
     `defined_type%` обязан дать её одну. Число колонок (25 — эталон П1), колонки цепи
     ревизий, ключ области видимости `(configuration_uuid, object_name, revision_no)`
     (M1: 247 имён и 243 `uuid` вида совпадают у BGU2 и BP3 — замер 1.3), отсутствие
     внешних ключей (прецедент V20.1), пять именованных индексов — в том числе GIN `types
     jsonb_path_ops` и частичный по `type_id` (обратный вопрос узла V25), витрина
     `v_current_defined_types`, запись таблицы в реестр версионируемых и отсутствие её в
     перечне неверсионируемых.
  2. СЛОВАРИ СОСТОЯНИЙ ↔ CHECK (контур 2). Каждый словарь модуля разбора сверяется с
     CHECK **конкретной таблицы** по имени колонки, а не «где-нибудь в схеме»; держатся
     все четырнадцать ограничений согласованности состояния со структурой строки. Словарь
     записей `types` схемой не выражается (замер V48 2.5: CHECK по элементу массива
     PostgreSQL отклоняет) — проверка называет это, а не ждёт отказа, и закрывает словарь
     разбором живых строк (контуры 4 и 5). Ключи разбора ↔ колонки схемы: ни одного ключа
     разбора без колонки и ни одной колонки круга без ключа разбора.
  3. ГРАНИЦА КРУГА (контур 3). Тип адресуется ЧЕТЫРЬМЯ ногами: каталогом `DefinedTypes/`
     (`<Имя>.xml`), индексом состава (`DefinedType.<Имя>`), перечнем
     `configurations.defined_types` (стадия S2) и перечислением имён вида в корне
     `Configuration.xml`; строки таблицы — пятая сторона того же множества, множества
     сравниваются попарно во все стороны. Предикат круга — точное `object_type =
     'DefinedType'`; маска по началу имени даёт то же число, и это названо проверкой, а не
     выведено из удачного совпадения (в отличие от пары `FunctionalOptions` /
     `FunctionalOptionsParameters`, где префикс совпадал — замер 1.2 плана V58).
  4. СТРОКА ТАБЛИЦЫ ↔ РАЗБОР ТЕМ ЖЕ МОДУЛЕМ, ЧТО И ЗАГРУЗКА (контур 4). Каждое поле живой
     строки сравнивается с полем разбора `read_registration_file`: свойства, `InternalInfo`,
     `type_raw`, `types`, `type_qualifiers`, состояния. Загрузка вызывает тот же слой,
     поэтому расхождение читается дефектом слоя, а не «двумя реализациями».
  5. НЕЗАВИСИМАЯ МЕРА ПОДСТРОКОЙ (контур 5). Значения, контейнеры, блоки квалификаторов и
     префиксы считаются по тексту файла выражениями самой проверки — вторым путём к обходу
     дерева (приём `_v58_p0_shape_check.py`: оба пути дают 17 544). Класс значения
     дополнительно прогоняется словарём слоя по всем значениям круга: ни одной записи вне
     замкнутого словаря ФОРМ.
  6. РАЗРЕШИМОСТЬ ЦЕЛЕЙ ИНДЕКСОМ СОСТАВА ЭТОЙ КОНФИГУРАЦИИ (контур 6). Для записи `exact`
     строка индекса данной конфигурации обязана существовать, для `unresolved` — не
     существовать; шесть неразрешённых целей называются адресами
     `BusinessProcessRoutePoint.*` и объясняются нулём записей `RoutePoint` в индексе. Два
     числа адресов не смешиваются: выведенных из ФОРМЫ — 2 419, подтверждённых индексом —
     2 413 (разница ровно шесть).
  7. ВИТРИНЫ, ЦЕПЬ РЕВИЗИЙ, ГРАНИЦА `configuration_uuid` (контур 7). Витрина отдаёт только
     текущие ревизии; сирот (строк без заголовка) — ноль; имена и `uuid`, общие у BGU2 и
     BP3 (247 и 243 — замер 1.3), существуют в таблице РАЗДЕЛЬНО для каждой конфигурации:
     без границы две выгрузки слились бы в одну строку (M1).
  8. КОНТРАКТ СТАДИИ И РЕЕСТР ИНСТРУМЕНТОВ (контуры 8 и 8.1). Стадия `s4m_defined_types`
     занимает место между `s4l_functional_options_parameters` и `s4b_object_modules`
     (порядок нормативного списка держит `STAGES`), круг снятия — одна таблица, заголовок
     стадии и подсказка продолжения называют позицию 2.13 и отдельный вход; групп запроса
     `kinds` у входа нет (Q5, вариант A); реестр ядра — шестнадцать инструментов.
  9. КОРПУС И ЧУЖИЕ КРУГИ (контур 9 и уборка). Суммы по четырём выгрузкам сравниваются с
     разделами 1.1, 1.4, 2.2, 2.3, 2.5 плана (820 файлов, 3 066 792 байта, 17 544 значения,
     классы 11 385 / 4 906 / 950 / 106 / 197, `exact` 17 341 / `no_target` 197 /
     `unresolved` 6, `single` 433 / `composite` 387, максимум 657 значений в файле). Чужие
     круги (V43, V46, V48–V57, `bsl_modules`) не изменены ни числом строк, ни состояниями:
     класс `defined_type_ref` в слоях V48/V50/V52 остаётся нулём, а 661 значение тех слоёв
     относится к тем же двум классам, что и до узла (мера M5, раздел 3 плана).
 10. ФИКСТУРА ГРАНИЦЫ (контур 10). Случай «выгрузке нечего показать» проверяется фикстурой,
     потому что корпусом он не дан (замер 1.1: вид есть во всех четырёх выгрузках):
     отсутствующий каталог вида даёт `files_found = 0` с наблюдением `directory_missing`
     (не отказ стадии), пустой каталог вида — тот же ноль БЕЗ этого наблюдения, а разбор
     без индекса состава — `unresolved` с наблюдением `index_not_provided` («не
     разрешалось», а не «разрешилось»). Это и есть критерий 4 раздела 9 плана.

Прогоны:
    python tools/check_v58_defined_types.py          # все четыре выгрузки
    python tools/check_v58_defined_types.py BGU2     # одна выгрузка (суммы корпуса
                                                     # пропускаются с причиной)
Код возврата 0 — расхождений нет. Пропуск контура называется причиной (нет строки
заголовка, нет каталога выгрузки, строк узла не загружалось, индекс состава недоступен):
ноль проверок не читается как «всё хорошо».

Записи в базу — только фикстуры. Контур 10 перезагружает круг по временному каталогу:
отсутствующий каталог снимает строки выгрузки и не пишет новых, пустой каталог даёт тот же ответ
без наблюдения `directory_missing`, полный круг возвращает строки к эталонному числу. Транзакция
прогона фиксируется (прецедент `external_db.transaction`), поэтому возврат круга является частью
проверки: снятие и запись называются числами, а финальное число строк витрины сверяется с
эталоном (мера M7). Фикстура цепи ревизий контура 7 (вставка ревизии 2, повтор ключа, откат)
существует только внутри своей транзакции и откатывает её сама. Остальные контуры читающие:
прогон не меняет состояние базы (сверено отдельным запросом — 820 строк в таблице и 820 в
витрине, все на ревизии 1).
"""

import inspect
import json
import re
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

try:  # кириллица в консоли Windows (cp1251) — как в остальных валидаторах
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001 — переуконфигурация вывода не обязана быть доступной
    pass

from config_dump_info_parser import parse_config_dump_info  # noqa: E402
from configuration_defined_types import (  # noqa: E402
    CIRCLE_DISCREPANCIES, CONTAINER_TYPE_TAG, CONTAINER_TYPESET_TAG, COUNT_KEYS, DIR_NAME,
    ENTRY_STATE_PARSED, ENTRY_STATE_UNKNOWN_FORM,
    INDEX_NAME_SEPARATOR, INDEX_OBJECT_TYPE, INTERNAL_ABSENT, INTERNAL_FULL,
    INTERNAL_INFO_STATES, INTERNAL_PARTIAL, MULT_ABSENT, MULT_COMPOSITE, MULT_SINGLE,
    MULTIPLICITY_VALUES, OBJECT_KIND_TAG, OBSERVATION_KINDS, OBSERVATION_TYPE_SET,
    PROPS_ALL_KNOWN, PROPS_ABSENT, PROPS_UNKNOWN_TAG, PROPS_UNKNOWN_VALUE,
    PROPERTIES_STATES, RECORD_STATES, RESOLVE_COUNT_KEYS, RESOLVE_EXACT, RESOLVE_NO_TARGET,
    RESOLVE_STATES, RESOLVE_UNRESOLVED, STATE_ABSENT, STATE_PARSED, STATE_PARTIAL,
    STATE_UNKNOWN_FORM, STATE_VOCABULARIES, STATE_VOCABULARY_TABLES, TABLE_NAME,
    TYPE_CLASS_VALUES, TYPE_ENTRY_KEYS, TYPE_ENTRY_TARGET_KEYS,
    classify_type_value, collect_defined_types, file_namespace_map, index_row_key,
    index_rows_by_name, kind_index_rows, read_text_file, row_keys, row_problems,
    split_qname, state_columns, type_value_form, zero_counts,
)
from configuration_defined_types_loader import (  # noqa: E402
    SUMMARY_KEYS as LOADER_SUMMARY_KEYS, load_defined_types, remove_defined_types,
)
from configuration_load_contract import (  # noqa: E402
    is_last_stage,
    DEFINED_TYPES_COUNT_KEYS, DEFINED_TYPES_DIR, DEFINED_TYPES_META_TAG,
    DEFINED_TYPES_OBSERVATION_KINDS, DEFINED_TYPES_REMOVE_ORDER, DEFINED_TYPES_REPEAT_HINT,
    DEFINED_TYPES_CIRCLE_BOUNDARY, DEFINED_TYPES_SECTION_HEADER,
    DEFINED_TYPES_STATE_VOCABULARIES, DEFINED_TYPES_TABLE,
    DEFINED_TYPES_TABLES, FOREIGN_STAGE_TABLES, STAGES, STAGE_DEFINED_TYPES,
    STAGE_FULL_RELOAD_ONLY, STAGE_FUNCTIONAL_OPTIONS_PARAMETERS, STAGE_OBJECT_MODULES,
    STORED_META_KINDS, defined_types_defaults, format_defined_types_lines,
    stage_resume_hint, stage_title, stages_after,
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

VIEW = current_view(TABLE_NAME)
INDEX_TABLE = "configuration_objects"
HEADER_NAME_COLUMN = "defined_types"      # перечень заголовка (стадия S2, узел V43)
# Вторая таблица круга, которой узел НЕ заводит (Q1, вариант A): блок `<Type>` описывает
# тип, а не перечень целей, и строка значения существовала бы только через строку вида.
# Имя называется явно, потому что проверка обязана искать именно его, а не «что-то похожее
# по маске» (прецедент `defined_type_values` — план V58, Q1 раздела 6).
VALUES_TABLE_NAME = "defined_type_values"
# Маска круга узла по имени таблицы: она обязана дать ровно таблицу вида. Колонки с
# подстрокой `defined` в публичной схеме — `configurations.defined_types`,
# `bots.predefined`, `scheduled_jobs.predefined` и их отражения в витринах (замер раздела 3
# плана: пять колонок, к виду отношения не имеют) — в обход таблиц не попадают.
CIRCLE_MASK = "defined_type%"

# Ожидаемое число колонок таблицы узла — эталон шага П1 (миграция
# `migrate_v58_defined_types.sql` + зеркало `create_1c_configurations_db.sql`).
EXPECTED_COLUMN_COUNTS = {TABLE_NAME: 25}

# Колонки, которые принадлежат цепи ревизий (узел V19), а не узлу V58: их заполняет не
# разбор, и сравнивать их с ключом строки разбора — значит требовать от слоя чужого.
REVISION_COLUMNS = ("id", "configuration_uuid", "created_at", "revision_no", "changed_at",
                    "changed_by", "is_committed")

# Имена CHECK замкнутости состояний: связка «таблица, колонка → имя ограничения» держится
# словарём, а не выводом из имени (прецедент V52/V54/V56/V57).
STATE_CHECK_NAMES = {
    (TABLE_NAME, "properties_state"): "defined_types_properties_state_known",
    (TABLE_NAME, "internal_info_state"): "defined_types_internal_info_state_known",
    (TABLE_NAME, "type_parse_state"): "defined_types_type_parse_state_known",
    (TABLE_NAME, "type_multiplicity"): "defined_types_type_multiplicity_known",
}

# Ограничения DDL узла V58 (миграция + зеркало): отсутствие любого из них означает, что
# состояние описывало бы само себя, а не структуру строки, либо кратность расходилась бы с
# числом записей `types`.
MATCH_CONSTRAINTS = (
    "defined_types_names_not_blank",
    "defined_types_properties_state_known",
    "defined_types_properties_state_matches_unknown",
    "defined_types_all_known_covers_required_parts",
    "defined_types_internal_info_state_known",
    "defined_types_internal_info_matches_values",
    "defined_types_type_multiplicity_known",
    "defined_types_type_parse_state_known",
    "defined_types_types_is_array",
    "defined_types_types_absent_matches_no_block",
    "defined_types_type_multiplicity_matches_types",
    "defined_types_revision_no_positive",
    "defined_types_changed_by_known",
    "defined_types_changed_pair_check",
)
# Ключ области видимости строк узла — отдельное ограничение UNIQUE (не CHECK), и оно же
# обслуживает поиск по конфигурации: отдельного индекса по `configuration_uuid` нет
# осознанно (раздел «Индексы узла V58» миграции — ведущая колонка ключа).
SCOPE_KEY_NAME = "defined_types_configuration_object_revision_key"
# Две формы одного и того же ключа: `pg_get_constraintdef` отдаёт ограничение UNIQUE,
# `pg_indexes` — индекс, которым это ограничение обслуживается. Смешивать формы — значит
# потерять либо ограничение, либо индекс (проверка держит обе).
SCOPE_KEY_UNIQUE = "UNIQUE (configuration_uuid, object_name, revision_no)"
SCOPE_KEY_DEFINITION = "USING btree (configuration_uuid, object_name, revision_no)"

# Индексы круга — именованный состав (пять, включая первичный и индекс ключа). GIN по
# `types jsonb_path_ops` — практический вопрос блока `<Type>` (тот же приём, что V48/V50/
# V52), частичный индекс по `type_id` — обратный вопрос узла V25 (идентификатор
# `<v8:TypeId>` из разбора `.erf`/`.epf` → имя вида).
EXPECTED_INDEXES = {
    TABLE_NAME: sorted([
        "defined_types_pkey",
        SCOPE_KEY_NAME,
        "idx_defined_types_object_uuid_revision",
        "idx_defined_types_types_gin",
        "idx_defined_types_type_id",
    ]),
}
INDEX_LEAD_COLUMNS = {
    "idx_defined_types_object_uuid_revision": "USING btree (object_uuid, revision_no)",
    "idx_defined_types_types_gin": "USING gin (types jsonb_path_ops)",
    "idx_defined_types_type_id": "USING btree (type_id) WHERE (type_id IS NOT NULL)",
    SCOPE_KEY_NAME: SCOPE_KEY_DEFINITION,
}
# Как ищут цель значения блока `<Type>`: полным индексным именем — тем же ключом, что строки
# индекса состава (`index_row_key`). Короткого имени цели в модели узла нет, поэтому пример
# держится текстом: он же цитируется контуром 6, а не пересказывается.
GIN_EXAMPLE = "types @> '[{\"target_full_name\": \"Catalog.Организации\"}]'::jsonb"
# Литерал probe-запроса плана (контур 1): тот же containment-вид, что и пример выше, но по
# полю, которое есть у каждой записи с целью, — план обязан показать GIN, а не Seq Scan.
GIN_PROBE_CONTAINMENT = "[{\"target_object_type\":\"Catalog\"}]'::jsonb"

# Колонки jsonb и текстового массива сравниваются отдельными проверками: у них своя форма
# пустого значения (NULL, а не пустая структура), и общая сверка скрыла бы разницу «блока
# нет» и «блок пустой» (правило C2).
JSON_COLUMNS = ("synonym", "types", "type_qualifiers")
ARRAY_COLUMNS = ("unknown_property_names",)

PASSED: list = []
FAILED: list = []
SKIPPED: list = []
INFO: list = []


# ── эталоны прогона (docs/CONFIGURATION_DEFINED_TYPES_PLAN.md, разделы 1 и 2) ───────────────
# Ключ — каталог выгрузки, а не имя строки заголовка: имя заголовка берётся из
# `Configuration.xml` и меняется вместе с выгрузкой, а каталог — адрес, по которому
# проверка находит файлы (прецедент V50/V57).
#   files / bytes — каталог `DefinedTypes/` (плоский, только XML, прочего содержимого
#     ноль — замеры 1.1, 1.2, 1.4);
#   index_records — записей `DefinedType.<Имя>` в индексе состава (замер 1.1);
#   header_names / header_null — элементов перечня `configurations.defined_types` и
#     признака `NULL` (замер 1.1: перечень заполнен во всех четырёх выгрузках — отличие от
#     V56/V57, где KomMag давал `NULL`, потому что вида у него не было ни файлами, ни
#     записями индекса);
#   root_names — имён вида в перечне корня `Configuration.xml` (четвёртая нога круга);
#   db_rows / values — строки витрины текущего состояния и записей `types` в них
#     (замеры 1.1 и 1.4: значения 5 / 1 / 10 904 / 6 634 на 17 544 корпуса);
#   prefix_cfg / prefix_xs — префиксы значений (план 2.2 называет корпус 17 347 / 197;
#     разбивки по выгрузкам план не перечисляет, поэтому они измерены независимым путём
#     самой проверки — сумма обязана сойтись с корпусом);
#   typeset — записей контейнера `<v8:TypeSet>` (замер 2.2: ноль — держится наблюдением,
#     а не состоянием строки);
#   qual_files / qual_blocks — файлы с квалификаторами и блоки квалификаторов (замер 2.2:
#     182 и 191 — ДВА разных числа, девять файлов несут по два блока);
#   no_target / unresolved — состояния разрешения (план 2.5: `no_target` равен числу
#     примитивов, все шесть `unresolved` — `cfg:BusinessProcessRoutePointRef.*`, и по
#     живой БД они приходятся на BP3).
PLAN_EXPECTATIONS = {
    "MinCfg": {"files": 2, "bytes": 3974, "index_records": 2, "header_names": 2,
               "header_null": 0, "root_names": 2, "db_rows": 2, "values": 5,
               "prefix_cfg": 1, "prefix_xs": 4, "typeset": 0, "qual_files": 2,
               "qual_blocks": 4, "no_target": 4, "unresolved": 0},
    "KomMag": {"files": 1, "bytes": 1685, "index_records": 1, "header_names": 1,
               "header_null": 0, "root_names": 1, "db_rows": 1, "values": 1,
               "prefix_cfg": 0, "prefix_xs": 1, "typeset": 0, "qual_files": 1,
               "qual_blocks": 1, "no_target": 1, "unresolved": 0},
    "BGU2": {"files": 304, "bytes": 1529303, "index_records": 304, "header_names": 304,
             "header_null": 0, "root_names": 304, "db_rows": 304, "values": 10904,
             "prefix_cfg": 10814, "prefix_xs": 90, "typeset": 0, "qual_files": 89,
             "qual_blocks": 89, "no_target": 90, "unresolved": 0},
    "BP3": {"files": 513, "bytes": 1531830, "index_records": 513, "header_names": 513,
            "header_null": 0, "root_names": 513, "db_rows": 513, "values": 6634,
            "prefix_cfg": 6532, "prefix_xs": 102, "typeset": 0, "qual_files": 90,
            "qual_blocks": 97, "no_target": 102, "unresolved": 6},
}

# Суммы по четырём выгрузкам — разделы 1.1, 1.4, 2.2, 2.3, 2.5 плана. Отдельно держатся
# нули: `defined_type_ref` и `unknown` корпус не давал, но состояния в словаре класса
# остаются (прецедент `defined_type_ref` узлов V48/V50/V52 — нуль является наблюдением, а
# не свойством вида, и ответ обязан назвать ноль, а не молчать).
CORPUS_EXPECTATIONS = {
    "files": 820, "bytes": 3066792, "index_records": 820, "header_names": 820,
    "header_null": 0, "root_names": 820, "db_rows": 820, "values": 17544,
    "prefix_cfg": 17347, "prefix_xs": 197, "typeset": 0, "qual_files": 182,
    "qual_blocks": 191, "no_target": 197, "unresolved": 6, "exact": 17341,
    "max_values_per_file": 657, "derived_addresses": 2419, "resolved_addresses": 2413,
    "class_ref_value": 11385, "class_object_value": 4906, "class_record_set": 950,
    "class_value_manager": 106, "class_primitive": 197, "class_defined_type_ref": 0,
    "class_unknown": 0,
    "mult_absent": 0, "mult_single": 433, "mult_composite": 387,
    "internal_full": 820, "internal_partial": 0, "internal_absent": 0,
    "props_all_known": 820, "props_unknown_value": 0, "props_unknown_tag": 0,
    "props_absent": 0,
    "state_parsed": 820, "state_partial": 0, "state_absent": 0, "state_unknown_form": 0,
    "circle_discrepancies": 0, "duplicate_names": 0, "files_failed": 0,
    "row_problems": 0, "unknown_properties": 0, "observations_total": 0,
    # M1 (замер 1.3) — границы цепи ревизий: различные имена и `uuid` по корпусу, число
    # тех и других, встречающихся в двух и более выгрузках, повторов внутри выгрузки.
    "distinct_names": 573, "distinct_uuids": 577, "shared_names": 247,
    "shared_uuids": 243, "duplicate_names_inside": 0,
}

# Классы значения и состояния строки переводятся в меры корпуса словарём: вывод ключа из
# имени состояния скрыл бы незнакомое состояние (правило C2, прецедент `USE_MEASURE_KEYS`
# проверки V57).
CLASS_MEASURE_KEYS = {
    "ref_value": "class_ref_value", "object_value": "class_object_value",
    "record_set": "class_record_set", "value_manager": "class_value_manager",
    "primitive": "class_primitive", "defined_type_ref": "class_defined_type_ref",
    "unknown": "class_unknown",
}
MULT_MEASURE_KEYS = {MULT_ABSENT: "mult_absent", MULT_SINGLE: "mult_single",
                     MULT_COMPOSITE: "mult_composite"}
INTERNAL_MEASURE_KEYS = {INTERNAL_FULL: "internal_full",
                        INTERNAL_PARTIAL: "internal_partial",
                        INTERNAL_ABSENT: "internal_absent"}
PROPS_MEASURE_KEYS = {PROPS_ALL_KNOWN: "props_all_known",
                      PROPS_UNKNOWN_VALUE: "props_unknown_value",
                      PROPS_UNKNOWN_TAG: "props_unknown_tag",
                      PROPS_ABSENT: "props_absent"}
STATE_MEASURE_KEYS = {STATE_PARSED: "state_parsed", STATE_PARTIAL: "state_partial",
                      STATE_ABSENT: "state_absent",
                      STATE_UNKNOWN_FORM: "state_unknown_form"}
RESOLVE_MEASURE_KEYS = {RESOLVE_EXACT: "exact", RESOLVE_NO_TARGET: "no_target",
                        RESOLVE_UNRESOLVED: "unresolved"}

# Шесть неразрешённых целей обязаны называться адресами, а не сводиться к счётчику
# (раздел 2.5 плана, развилка Q6): все шесть — форма `BusinessProcessRoutePointRef.*`.
UNRESOLVED_VALUE_PREFIX = "cfg:BusinessProcessRoutePointRef."
UNRESOLVED_ADDRESS_PREFIX = "BusinessProcessRoutePoint."
# Живые числа чужого индекса состава. Число плана («66 строк BGU2») прогон не подтвердил —
# эталоном становятся измеренные числа (43 / 501 / 3), а расхождение правится планом; смысл
# абзаца держит второй эталон: записей, несущих `RoutePoint` в типе или имени, — ноль.
BUSINESS_PROCESS_INDEX_ROWS = {"MinCfg": 3, "KomMag": 0, "BGU2": 43, "BP3": 501}
ROUTE_POINT_INDEX_ROWS = 0

# Чужие круги (мера M5, раздел 3 плана и критерий 5 раздела 9): их числа обязан сохранить
# прогон. Класс `defined_type_ref` в слоях V48/V50/V52 остаётся нулём — узел V58 их не
# переразрешает и не меняет их словари (граница названа карточкой инструмента).
FOREIGN_TABLES = (
    "configurations", "configuration_objects", "subsystems", "common_modules",
    "session_parameters", "roles", "role_rights", "role_restriction_templates",
    "common_attributes", "common_attribute_targets", "exchange_plans",
    "exchange_plan_content", "filter_criteria", "filter_criterion_content",
    "event_subscriptions", "event_subscription_sources", "scheduled_jobs",
    "scheduled_job_schedules", "bots", "functional_options",
    "functional_option_content", "functional_option_parameters",
    "functional_option_parameter_targets", "bsl_modules",
)
FOREIGN_VIEWS = ("v_current_session_parameters", "v_current_common_attributes",
                 "v_current_filter_criteria", "v_current_functional_options",
                 "v_current_functional_option_content",
                 "v_current_functional_option_parameters",
                 "v_current_functional_option_parameter_targets", "v_current_bots",
                 "v_current_scheduled_jobs")
# Числа витрин соседних позиций, которые прогон не имеет права менять (прецедент
# `FOREIGN_VIEW_EXPECTATIONS` проверки V57: круги живут рядом, и путаница в предикате
# изменила бы состав соседа).
FOREIGN_VIEW_EXPECTATIONS = {"v_current_functional_options": 765,
                             "v_current_functional_option_content": 10063,
                             "v_current_functional_option_parameters": 14,
                             "v_current_functional_option_parameter_targets": 34}
# Классы значений в трёх загруженных слоях, где ссылка на определяемый тип могла бы жить
# (замер раздела 3 плана: 661 значение — `primitive` 209 и `object_ref` 452, других
# классов живые слои не содержат; `defined_type_ref` — ноль, и узел его не снимает).
FOREIGN_TYPE_TABLES = ("session_parameters", "common_attributes", "filter_criteria")
FOREIGN_TYPE_CLASS_EXPECTATIONS = {"primitive": 209, "object_ref": 452,
                                   "defined_type_ref": 0}
FOREIGN_TYPE_VALUES_TOTAL = 661

# Реестр инструментов ядра после узла TOOL-DROP (05.11.2026) — три: единая точка входа
# загрузки каталога, разбор бинарного .erf/.epf и удаление внешнего объекта. Прежние
# шестнадцать включали тринадцать позиционных входов дозагрузки; сняты только обёртки,
# стадии конвейера (S3, S4, S4b…S4m) живут в src/configuration_loader.py. Состав сторожит
# `tools/check_mcp_tool_wiring.py`, здесь сверяются тексты объявления и `DELETED_TOOLS`.
EXPECTED_CORE_TOOL_COUNT = 3
TOOL_NAME = "load_defined_types_tool"
LOADER_MODULE = "src/configuration_defined_types_loader.py"
PARSE_MODULE = "src/configuration_defined_types.py"

# ── независимая мера по тексту файла (второй путь к обходу дерева) ──────────────────────────
# Приём `_v58_p0_shape_check.py`: значения считаются и обходом дерева (слой разбора), и
# подстрокой по тексту (эти выражения). Расхождение читалось бы «потерянными значениями».
# Внешний блок `<Type>` и значения различаются префиксом: значения в корпусе — `v8:Type`.
VALUE_RE = re.compile(r"<v8:Type>\s*(.*?)\s*</v8:Type>", re.S)
TYPESET_RE = re.compile(r"<v8:TypeSet>")
QUALIFIER_RE = re.compile(r"<v8:(StringQualifiers|NumberQualifiers|DateQualifiers)>")
INTERNAL_INFO_RE = re.compile(r"<InternalInfo[^>]*>(.*?)</InternalInfo>", re.S)
GENERATED_TYPE_RE = re.compile(r"<GeneratedType\b([^>]*)>(?:\s*</GeneratedType>)?")
TYPE_ID_RE = re.compile(r"<TypeId>\s*([0-9a-fA-F-]+)\s*</TypeId>")
VALUE_ID_RE = re.compile(r"<ValueId>\s*([0-9a-fA-F-]+)\s*</ValueId>")
OBJECT_ELEMENT_RE = re.compile(r"<(?:[A-Za-z0-9]+:)?DefinedType\s+([^>]*uuid=\"([0-9a-fA-F-]+)\"[^>]*)>")
ROOT_ENTRY_RE = re.compile(r"<" + OBJECT_KIND_TAG + r">\s*([^<]+?)\s*</" + OBJECT_KIND_TAG
                           + r">")
CHILD_DIR_NAMES = ("Forms", "Templates", "Commands", "Ext")


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


def _brief(value, limit=160):
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
    """Ограничения UNIQUE и PRIMARY KEY живой схемы: имя → текст."""
    return {str(r["conname"]): str(r["def"]) for r in q(
        cur, "SELECT conname, pg_get_constraintdef(oid) AS def FROM pg_constraint "
             "WHERE conrelid = %s::regclass AND contype IN ('u', 'p')", (table,))}


def check_constraints(cur, table):
    """CHECK-ограничения живой схемы: имя → текст."""
    return {str(r["conname"]): str(r["def"]) for r in q(
        cur, "SELECT conname, pg_get_constraintdef(oid) AS def FROM pg_constraint "
             "WHERE conrelid = %s::regclass AND contype = 'c'", (table,))}


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


def as_json(value):
    """Значение jsonb колонки приводится к сравниваемой форме (psycopg отдаёт dict/list)."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def canon_json(value):
    """Каноническая форма jsonb для сравнения: ключи сортируются, пустое — None."""
    if value in (None, {}, [], ""):
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def canon_array(value):
    """Текстовый массив: NULL и пустой массив — разные состояния, поэтому сравнение строгое."""
    if value is None:
        return None
    return list(value)


# ── контур 1: живая схема круга ──────────────────────────────────────────────────────────────
def check_schema(cur):
    section("Контур 1 — живая схема круга")
    if not q(cur, "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
             (TABLE_NAME,)):
        check(f"{TABLE_NAME}: таблица существует", False, "таблицы в схеме нет")
        return
    columns = table_columns(cur, TABLE_NAME)
    check(f"{TABLE_NAME}: таблица существует и держит {EXPECTED_COLUMN_COUNTS[TABLE_NAME]} "
          "колонок (эталон П1: свойства вида + `InternalInfo` + блок `<Type>` + состояния + "
          "`source_path` + цепь ревизий)",
          len(columns) == EXPECTED_COLUMN_COUNTS[TABLE_NAME],
          f"факт: {len(columns)}")

    # Круг узла — ровно ОДНА таблица (Q1, вариант A): обход схемы по маске вида обязан дать
    # её одну и не дать второй таблицы значений. `defined_type_values` названа именем,
    # потому что именно её узел не заводит осознанно (блок `<Type>` описывает тип, а не
    # перечень целей: строка значения существовала бы только через строку вида).
    kind_tables = sorted(str(r["table_name"]) for r in q(
        cur, "SELECT table_name FROM information_schema.tables WHERE table_name LIKE %s",
        (CIRCLE_MASK,)))
    check(f"таблиц круга по маске `{CIRCLE_MASK}` — ровно одна `{TABLE_NAME}` (Q1, "
          "вариант A: второй таблицы значений у вида нет)",
          kind_tables == [TABLE_NAME], f"найдено: {names(kind_tables)}")
    check(f"таблицы `{VALUES_TABLE_NAME}` в схеме нет осознанно (значение не имеет "
          "собственной идентифицируемой цели — в отличие от перечней `<Content>`/`<Source>`/"
          "`<Use>` узлов V50/V52/V53/V56/V57)",
          VALUES_TABLE_NAME not in kind_tables, f"найдено: {names(kind_tables)}")

    missing_chain = sorted(c for c in REVISION_COLUMNS if c not in set(columns))
    check(f"`{TABLE_NAME}`: колонки цепи ревизий узла V19 живы целиком "
          f"({len(REVISION_COLUMNS)} колонок)", not missing_chain,
          f"нет: {names(missing_chain)}")
    parsed_missing = sorted(key for key in row_keys() if key not in set(columns))
    check(f"каждый ключ разбора `{PARSE_MODULE}` (`row_keys()`, {len(row_keys())} ключей) "
          "имеет колонку таблицы — писатель не может принять то, куда нечего писать",
          not parsed_missing, f"ключей без колонки: {names(parsed_missing)}")

    keys = unique_constraints(cur, TABLE_NAME)
    scope = [d for d in keys.values() if SCOPE_KEY_UNIQUE in compact(d)]
    check(f"`{TABLE_NAME}`: ключ области видимости строк узла живой `{SCOPE_KEY_UNIQUE}` "
          f"(M1: 247 имён и 243 `uuid` вида совпадают у BGU2 и BP3 — без границы "
          "конфигурации две выгрузки слились бы в одну строку)",
          len(scope) == 1 and SCOPE_KEY_NAME in keys,
          f"ключи схемы: {names(list(keys))}")

    fks = foreign_keys(cur, TABLE_NAME)
    check(f"`{TABLE_NAME}`: внешних ключей нет осознанно — ни на заголовок (прецедент "
          "V20.1), ни на цель значения блока `<Type>` (Q3 раздела 6 плана: слои `Catalogs`, "
          "`InformationRegisters`, `Constants` и прочие не загружены, а состояние разрешения "
          "называет запись `types`)", not fks, f"ключи: {names(list(fks))}")

    for table, wanted in EXPECTED_INDEXES.items():
        found = sorted(indexes_of(cur, table))
        check(f"`{table}`: состав индексов круга — ровно {len(wanted)} (миграция V58: "
              "первичный, ключ цепи, `(object_uuid, revision_no)`, GIN `types "
              "jsonb_path_ops`, частичный по `type_id`; отдельного индекса по "
              "`configuration_uuid` нет осознанно — его обслуживает ведущая колонка ключа)",
              found == wanted,
              f"нет: {names(sorted(set(wanted) - set(found)))}; лишние: "
              f"{names(sorted(set(found) - set(wanted)))}")
    found_indexes = indexes_of(cur, TABLE_NAME)
    for index_name, fragment in INDEX_LEAD_COLUMNS.items():
        definition = compact(found_indexes.get(index_name, ""))
        check(f"индекс `{index_name}` жив и ведёт по `{compact(fragment)}`",
              bool(definition) and compact(fragment) in definition,
              "индекса в схеме нет" if not definition
              else f"определение: {_brief(definition)}")

    # GIN по `types` обязан читаться планом: проверка «индекс существует» не отличает
    # индекс от неиспользуемого (тот же контур, что `_v58_p1_ddl_probe.py` шага П2).
    probe_sql = ("EXPLAIN SELECT count(*) FROM " + VIEW + " WHERE types @> '"
                 + GIN_PROBE_CONTAINMENT)
    try:
        plan_rows = q(cur, probe_sql)
        plan_text = " ".join(str(row.get("QUERY PLAN", "")) for row in plan_rows)
        check(f"containment-запрос по `{VIEW}` планирует использование "
              "`idx_defined_types_types_gin` (практика блока `<Type>` — V48/V50/V52)",
              "idx_defined_types_types_gin" in plan_text, _brief(plan_text, 300))
    except Exception as exc:  # noqa: BLE001 — план называется отказом, а не молчанием
        cur.connection.rollback()
        check("containment-запрос по витрине разбирается планировщиком", False, str(exc))

    view_rows = scalar(cur, f"SELECT count(*) FROM {VIEW}")
    check(f"витрина текущего состояния `{VIEW}` жива и читается", view_rows is not None)
    info(f"витрина `{VIEW}`: строк {view_rows}")
    check(f"`{TABLE_NAME}` состоит в реестре версионируемых (цепь узла V19, Q2 — одна "
          "запись в `CONFIGURATION_VERSIONED_TABLES`, из которой выводятся имя витрины и "
          "колонки цепи)", TABLE_NAME in CONFIGURATION_VERSIONED_TABLES,
          f"реестр: {names(sorted(CONFIGURATION_VERSIONED_TABLES))}")
    check(f"`{TABLE_NAME}` НЕ названа в `CONFIGURATION_UNVERSIONED_TABLES` (у узла нет "
          "таблицы, версионируемой не своей цепью: второй таблицы круга нет — Q1 вариант A)",
          TABLE_NAME not in CONFIGURATION_UNVERSIONED_TABLES,
          f"перечень: {names(sorted(CONFIGURATION_UNVERSIONED_TABLES))}")
    check(f"`current_view('{TABLE_NAME}')` даёт ровно `{VIEW}` — имя витрины выводится из "
          "реестра, а не придумывается вызывающим (правило A1 узла V19)",
          current_view(TABLE_NAME) == VIEW, current_view(TABLE_NAME))
    check("круг записи контракта — одна таблица (`DEFINED_TYPES_TABLES`), и она же — круг "
          "снятия `DEFINED_TYPES_REMOVE_ORDER` (каскада нет, поэтому круг снятия назван, а "
          "не выведен из записи)",
          tuple(DEFINED_TYPES_TABLES) == (TABLE_NAME,)
          and tuple(DEFINED_TYPES_REMOVE_ORDER) == (TABLE_NAME,),
          f"запись: {DEFINED_TYPES_TABLES}, снятие: {DEFINED_TYPES_REMOVE_ORDER}")
    check(f"таблица круга названа в `FOREIGN_STAGE_TABLES` — иначе стадия S4 снимала бы "
          "чужие строки вида", TABLE_NAME in FOREIGN_STAGE_TABLES,
          f"перечень: {names(FOREIGN_STAGE_TABLES)}")
    check("писатель таблицы зарегистрирован в `CONFIGURATION_OBJECT_WRITERS` (шаг П4: "
          "свой класс строки плюс запись в реестр писателей)",
          CONFIGURATION_OBJECT_WRITERS.get(TABLE_NAME) is not None,
          "писателя в реестре нет")
    mirror = STORED_META_KINDS.get(DEFINED_TYPES_META_TAG) or {}
    check(f"вид `{DEFINED_TYPES_META_TAG}` внесён в реестр сохранённых видов "
          f"`STORED_META_KINDS` со своим кругом таблиц и секцией ответа",
          tuple(mirror.get("tables") or ()) == (TABLE_NAME,)
          and bool(mirror.get("section")),
          f"запись реестра: {_brief(mirror)}")
    check("зеркальные имена таблиц и меток контракта совпадают со словарём разбора (один "
          "круг, а не два перечня)",
          DEFINED_TYPES_TABLE == TABLE_NAME and DEFINED_TYPES_DIR == DIR_NAME
          and DEFINED_TYPES_META_TAG == INDEX_OBJECT_TYPE == OBJECT_KIND_TAG,
          f"контракт: {DEFINED_TYPES_TABLE}/{DEFINED_TYPES_DIR}/{DEFINED_TYPES_META_TAG}")


# ── контур 2: словари состояний ↔ CHECK'ы конкретной таблицы ────────────────────────────────
def compare_vocabulary(cur, table, column, vocabulary):
    """Словарь модуля разбора против литералов CHECK конкретной таблицы."""
    constraint = STATE_CHECK_NAMES.get((table, column))
    definition = constraint_def(cur, table, constraint) if constraint else ""
    if not definition:
        check(f"`{table}.{column}`: ограничение замкнутости `{constraint}` живое", False,
              "ограничения в схеме нет")
        return
    literals = set(literals_of(definition))
    wanted = set(vocabulary)
    check(f"`{table}.{column}`: словарь разбора ({len(wanted)} состояний) и CHECK "
          f"`{constraint}` замкнуты одним кругом", literals == wanted,
          f"в CHECK нет: {names(sorted(wanted - literals))}; в словаре нет: "
          f"{names(sorted(literals - wanted))}")


def check_state_vocabulary_checks(cur):
    section("Контур 2 — словари состояний ↔ CHECK конкретной таблицы")
    check("словари состояний слоя разбора и контракта стадии — ОДИН круг (замкнутый "
          "перечень состояний перечисляется одним местом: нулевой контракт, сводка разбора "
          "и эта проверка — приём `STATE_VOCABULARIES` узлов V50/V52/V56/V57)",
          {column: tuple(values) for column, values in
           DEFINED_TYPES_STATE_VOCABULARIES.items()} == {column: tuple(values)
                                                        for column, values in
                                                        STATE_VOCABULARIES.items()},
          f"контракт: {list(DEFINED_TYPES_STATE_VOCABULARIES)}; разбор: "
          f"{list(STATE_VOCABULARIES)}")
    check("связка `STATE_VOCABULARY_TABLES` указывает на таблицу узла для каждой колонки "
          "состояния — словарь сверяется с CHECK конкретной таблицы, а не «где-нибудь в "
          "схеме»", set(STATE_VOCABULARY_TABLES) == set(STATE_VOCABULARIES)
          and all(table == TABLE_NAME for table in STATE_VOCABULARY_TABLES.values()),
          f"связка: {STATE_VOCABULARY_TABLES}")
    check(f"число колонок состояний — {len(STATE_VOCABULARIES)} и оно равно числу "
          "ограничений замкнутости в `STATE_CHECK_NAMES` и числу `state_columns()`",
          len(STATE_VOCABULARIES) == len(STATE_CHECK_NAMES) == len(state_columns()),
          f"словарь: {list(STATE_VOCABULARIES)}; ограничения: "
          f"{names(sorted(STATE_CHECK_NAMES))}")
    for (table, column), constraint in sorted(STATE_CHECK_NAMES.items()):
        compare_vocabulary(cur, table, column, STATE_VOCABULARIES[column])

    found = check_constraints(cur, TABLE_NAME)
    missing = sorted(name for name in MATCH_CONSTRAINTS if name not in found)
    check(f"все {len(MATCH_CONSTRAINTS)} ограничений согласованности состояния со "
          "структурой строки живые (миграция V58 + зеркало чистой установки)", not missing,
          f"нет: {names(missing)}")

    # Инварианты, которые держат конкретные ограничения: без них состояние строки
    # описывало бы само себя. Тексты читаются живой схемой, а не памятью проверки.
    invariants = {
        "defined_types_type_multiplicity_matches_types": "jsonb_array_length",
        "defined_types_types_absent_matches_no_block": "'absent'",
        "defined_types_types_is_array": "jsonb_typeof",
        "defined_types_internal_info_matches_values": "generated_name",
        "defined_types_all_known_covers_required_parts": "type_parse_state",
        "defined_types_properties_state_matches_unknown": "unknown_property_names",
    }
    for constraint, fragment in sorted(invariants.items()):
        definition = compact(constraint_def(cur, TABLE_NAME, constraint))
        check(f"ограничение `{constraint}` держит инвариант (`{fragment}` в его тексте)",
              fragment in definition, f"текст: {_brief(definition, 300) or 'пустой'}")

    # Словарь записей `types` схемой не выражается: CHECK по элементу массива jsonb
    # PostgreSQL отклоняет (замер V48 2.5), а отдельной таблицы значений узел не заводит
    # (Q1, вариант A). Проверка называет это, а не ждёт отказа: полноту записей держат
    # `entry_problems`/`row_problems` слоя разбора, и они прогоняются на живых строках
    # (контуры 4 и 5) и на фикстурах (контур 10).
    entry_check = constraint_def(cur, TABLE_NAME, "defined_types_types_is_array")
    check("CHECK по `types` в схеме есть только как проверка типа значения "
          "(`jsonb_typeof(types) = 'array'`) — полноту записей держит слой разбора, и это "
          "названо, а не ожидается отказом", "jsonb_typeof" in compact(entry_check),
          _brief(entry_check, 300))
    check(f"закрытый словарь записи `types` — {len(TYPE_ENTRY_KEYS)} ключей состояния плюс "
          f"{len(TYPE_ENTRY_TARGET_KEYS)} ключей цели только у `exact` (прецедент D3 V39/"
          "V46: отсутствие ключа читается как «цели нет или она не найдена»)",
          set(TYPE_ENTRY_KEYS) == {"index", "container", "value", "ns_uri", "class", "state",
                                   "resolve_state"}
          and set(TYPE_ENTRY_TARGET_KEYS) == {"target_full_name", "target_object_type",
                                             "target_object_uuid"},
          f"запись: {TYPE_ENTRY_KEYS} + {TYPE_ENTRY_TARGET_KEYS}")
    check(f"словарь классов значения замкнут {len(TYPE_CLASS_VALUES)} формами раздела 2.3 "
          "плана и держит границы `defined_type_ref` и `unknown`",
          set(TYPE_CLASS_VALUES) == set(CLASS_MEASURE_KEYS),
          f"словарь: {names(TYPE_CLASS_VALUES)}")
    check("словари состояний разрешения цели, кратности, `InternalInfo`, свойств и состояния "
          "разбора совпадают с измерительными словарями проверки (иначе мера корпуса "
          "не досчитала бы состояние)",
          set(RESOLVE_STATES) == set(RESOLVE_MEASURE_KEYS)
          and set(MULTIPLICITY_VALUES) == set(MULT_MEASURE_KEYS)
          and set(INTERNAL_INFO_STATES) == set(INTERNAL_MEASURE_KEYS)
          and set(PROPERTIES_STATES) == set(PROPS_MEASURE_KEYS)
          and set(RECORD_STATES) == set(STATE_MEASURE_KEYS),
          f"разрешение: {RESOLVE_STATES}; кратность: {MULTIPLICITY_VALUES}; InternalInfo: "
          f"{INTERNAL_INFO_STATES}; свойства: {PROPERTIES_STATES}; состояние: "
          f"{RECORD_STATES}")
    check(f"наблюдения круга замкнуты {len(OBSERVATION_KINDS)} именами и совпадают со "
          "словарём контракта (ненаблюдаемое держится наблюдением, а не состоянием — "
          "прецедент `DayTimes` узла V54)",
          tuple(OBSERVATION_KINDS) == tuple(DEFINED_TYPES_OBSERVATION_KINDS),
          f"разбор: {names(OBSERVATION_KINDS)}; контракт: "
          f"{names(DEFINED_TYPES_OBSERVATION_KINDS)}")
    check(f"расхождения ног круга замкнуты {len(CIRCLE_DISCREPANCIES)} именами",
          tuple(CIRCLE_DISCREPANCIES) == ("index_only", "file_only", "uuid_mismatch"),
          f"словарь: {names(CIRCLE_DISCREPANCIES)}")


# ── контур 2.1: ключ разбора против колонок схемы ───────────────────────────────────────────
def check_key_columns_match(cur):
    section("Контур 2.1 — ключ разбора против колонок схемы")
    columns = set(table_columns(cur, TABLE_NAME))
    if not columns:
        check("колонки таблицы читаются живой схемой", False, "таблицы нет")
        return
    parsed = set(row_keys())
    structural = parsed | set(REVISION_COLUMNS)
    extra = sorted(columns - structural)
    check(f"колонок, не относящихся ни разбору ({len(parsed)}), ни цепи ревизий "
          f"({len(REVISION_COLUMNS)}), — ноль: писатель не принимает то, куда нечего "
          "писать, и незаполненных колонок круга не остаётся", not extra,
          f"лишние колонки: {names(extra)}")
    check(f"число колонок таблицы равно {len(parsed)} + {len(REVISION_COLUMNS)} = "
          f"{len(structural)} — вывод из ключей разбора и реестра цепей, а не из памяти "
          "проверки", columns == structural,
          f"факт: {len(columns)}; вывод: {len(structural)}; расхождение: "
          f"{names(sorted(columns ^ structural))}")
    state_missing = sorted(column for column in STATE_VOCABULARIES if column not in columns)
    check(f"каждая колонка состояния из словаря существует в таблице "
          f"({len(STATE_VOCABULARIES)} колонок)", not state_missing,
          f"нет: {names(state_missing)}")
    json_missing = sorted(column for column in JSON_COLUMNS if column not in columns)
    check(f"колонки jsonb `{names(JSON_COLUMNS)}` живые — сравнение содержимого блока "
          "проводится по ним, а не по пересказу", not json_missing,
          f"нет: {names(json_missing)}")
    # Колонок-счётчиков разрешения, классов и формы контейнера в схеме нет осознанно: класс,
    # состояние и цель живут внутри записей `types`, а колонка с их распределением была бы
    # вторым источником знания (правило V43; распределения называют замеры и эта проверка).
    counter_columns = {"counts_by_class", "target_state", "defined_type_ref_count",
                       "self_ref_count", "container_state"}
    check("колонок-счётчиков разрешения и классов (`counts_by_class`, `target_state`, "
          "`defined_type_ref_count`, `self_ref_count`) и колонки формы контейнера "
          "(`container_state`) в схеме нет осознанно — их распределение называют замеры "
          "плана и эта проверка", not (columns & counter_columns),
          f"лишние: {names(sorted(columns & counter_columns))}")
    child_columns = sorted(c for c in columns
                           if c.startswith(("form", "template", "module", "command")))
    check("колонок детей группы A (`form*`, `template*`, `module*`, `command*`) у таблицы "
          "нет осознанно: детей у вида нет ни файлами, ни индексом состава (замер 1.2)",
          not child_columns, f"лишние: {names(child_columns)}")
    check(f"нулевой контракт разбора `zero_counts()` называет {len(COUNT_KEYS)} счётчиков и "
          f"словари состояний по всем колонкам: нуль отличается от «не считали» наличием "
          "ключа (правило C1)",
          set(zero_counts()) >= set(COUNT_KEYS)
          | {("counts_by_" + column) for column in STATE_VOCABULARIES}
          | set(RESOLVE_COUNT_KEYS) | set(DEFINED_TYPES_COUNT_KEYS),
          f"контракт разбора: {names(sorted(zero_counts()))}")
    defaults = defined_types_defaults()
    check("нулевой контракт ответа стадии (`defined_types_defaults()`) покрывает ключи "
          "слоя `load_defined_types` (`SUMMARY_KEYS` слоя) — неперечисленный ключ ответа "
          "читался бы нулём, которого слой не обещал (C1/C2)",
          set(defaults) >= set(LOADER_SUMMARY_KEYS),
          f"нет в контракте: {names(sorted(set(LOADER_SUMMARY_KEYS) - set(defaults)))}")
    check("число предупреждений (`warning_count`) в замкнутом контракте ответа нет "
          "осознанно: ответ уже несёт список `warnings`, а число было бы второй половиной "
          "той же пары (прецедент V55/V57)",
          "warning_count" not in defaults, "ключ есть")
    check(f"нулевой контракт называет колонки состояний списком `state_columns()` "
          f"({len(state_columns())}) — то же множество, что словарь разбора",
          tuple(defaults.get("state_columns") or ()) == state_columns(),
          f"контракт: {names(defaults.get('state_columns') or ())}")


# ── независимые меры круга (текст файла, обход каталога, живой индекс, строки таблицы) ──────
def circle_measures(dump_dir):
    """Меры каталога `DefinedTypes/` и корня `Configuration.xml` — путём самой проверки.

    Обход дерева (слой разбора) и подстрока по тексту (эти выражения) — два независимых
    счёта одного множества значений (приём `_v58_p0_shape_check.py`: расхождений по файлам
    ноль). Отсутствующий каталог вида и пустой каталог различаются признаком
    `directory_present`, потому что корпус такого случая не даёт (замер 1.1).
    """
    totals = {"files": 0, "subdirs": 0, "non_xml": 0, "bytes": 0, "unreadable": [],
              "names": set(), "values": 0, "max_values_per_file": 0,
              "prefixes": Counter(), "typeset": 0, "qual_files": 0, "qual_blocks": 0,
              "qual_tags": Counter(), "file_uuids": {}, "generated_names": 0,
              "type_ids": 0, "value_ids": 0, "child_dirs": Counter(),
              "directory_present": 0, "root_file": 0, "root_names": set(),
              "per_file": {}}
    root = Path(dump_dir) / DIR_NAME
    if root.is_dir():
        totals["directory_present"] = 1
        for entry in sorted(root.iterdir()):
            if entry.is_dir():
                totals["subdirs"] += 1
                totals["child_dirs"][entry.name] += 1
                continue
            if entry.suffix.lower() != ".xml":
                totals["non_xml"] += 1
                continue
            totals["files"] += 1
            totals["bytes"] += entry.stat().st_size
            text, error = read_text_file(entry)
            if error or text is None:
                totals["unreadable"].append(f"{entry.name}: {error}")
                continue
            object_name = entry.stem
            totals["names"].add(object_name)
            values = [match.group(1) for match in VALUE_RE.finditer(text)]
            totals["values"] += len(values)
            totals["max_values_per_file"] = max(totals["max_values_per_file"], len(values))
            for value in values:
                totals["prefixes"][value.split(":", 1)[0] if ":" in value
                                else "<none>"] += 1
            totals["typeset"] += len(TYPESET_RE.findall(text))
            tags = QUALIFIER_RE.findall(text)
            totals["qual_blocks"] += len(tags)
            if tags:
                totals["qual_files"] += 1
            for tag in tags:
                totals["qual_tags"][tag] += 1
            element = OBJECT_ELEMENT_RE.search(text)
            if element:
                totals["file_uuids"][object_name] = element.group(2).lower()
            totals["generated_names"] += len(GENERATED_TYPE_RE.findall(text))
            totals["type_ids"] += len(TYPE_ID_RE.findall(text))
            totals["value_ids"] += len(VALUE_ID_RE.findall(text))
            totals["per_file"][object_name] = {"values": values,
                                               "qual_blocks": len(tags)}
    config = Path(dump_dir) / "Configuration.xml"
    if config.is_file():
        text, error = read_text_file(config)
        if not error and text is not None:
            totals["root_file"] = 1
            totals["root_names"] = set(ROOT_ENTRY_RE.findall(text))
    return totals


def registration_names(dump_dir):
    """Имена видов по файлам регистрации (без расширения) — независимая мера каталога."""
    root = Path(dump_dir) / DIR_NAME
    if not root.is_dir():
        return set()
    return {entry.stem for entry in root.iterdir()
            if entry.is_file() and entry.suffix.lower() == ".xml"}


def index_short_name(row):
    """Короткое имя объекта по ПОЛНОМУ точечному имени строки индекса (`name`).

    Ключом строки `configuration_objects` служит полное точечное имя, а `object_name` несёт
    короткое имя владельца (урок узла V48, повторённый разбором V50/V52/V56/V57): сверяя
    короткое имя с `name`, проверка потеряла бы половину круга.
    """
    full = str(row.get("name") or "")
    prefix = f"{INDEX_OBJECT_TYPE}{INDEX_NAME_SEPARATOR}"
    if full.startswith(prefix):
        return full[len(prefix):]
    return str(row.get("object_name") or "")


def read_index_aggregates(cur, configuration_id):
    """Агрегаты индекса состава этой конфигурации: свой круг, маска, чужие позиции."""
    info = {"available": False, "reason": None, "rows": [], "kind_rows": 0,
            "mask_rows": 0, "total_rows": 0, "business_process_rows": 0,
            "route_point_rows": 0, "kind_names": set(), "kind_uuids": {}}
    try:
        info["total_rows"] = int(scalar(
            cur, f"SELECT count(*) FROM {INDEX_TABLE} WHERE configuration_id = %s",
            (configuration_id,)) or 0)
    except Exception as exc:  # noqa: BLE001 — недоступный индекс называется причиной
        cur.connection.rollback()
        info["reason"] = f"чтение {INDEX_TABLE} не удалось: {exc}"
        return info
    if not info["total_rows"]:
        info["reason"] = (f"в {INDEX_TABLE} нет записей для configuration_id="
                          f"{configuration_id}: индекс состава этого заголовка не загружен")
        return info
    info["available"] = True
    rows = q(cur, "SELECT name, object_id, object_type, object_name, child_type, "
                  "parent_name, depth, uuid::text AS uuid FROM " + INDEX_TABLE +
                  " WHERE configuration_id = %s", (configuration_id,))
    info["rows"] = rows
    for row in kind_index_rows(rows):
        short = index_short_name(row)
        info["kind_names"].add(short)
        info["kind_uuids"][short] = str(row.get("uuid") or "").lower()
    info["kind_rows"] = len(info["kind_names"])
    info["mask_rows"] = len([row for row in rows
                             if str(row.get("object_type") or "").startswith(
                                 INDEX_OBJECT_TYPE)])
    info["business_process_rows"] = len([row for row in rows
                                         if row.get("object_type") == "BusinessProcess"])
    info["route_point_rows"] = len([
        row for row in rows
        if "RoutePoint" in str(row.get("object_type") or "")
        or "RoutePoint" in str(row.get("object_name") or "")])
    return info


def read_header_name_list(cur, cfg_uuid):
    """Перечень `configurations.defined_types` (стадия S2, узел V43) — третья нога круга."""
    row = one(cur, "SELECT coalesce(array_length(" + HEADER_NAME_COLUMN +
                   ", 1), -1) AS element_count, " + HEADER_NAME_COLUMN +
                   " AS names FROM configurations WHERE uuid = %s::uuid", (cfg_uuid,))
    if not row:
        return {"present": False, "count": 0, "is_null": False, "names": set()}
    return {"present": True, "count": int(row.get("element_count") or 0),
            "is_null": row.get("element_count") == -1,
            "names": {str(item) for item in (row.get("names") or [])}}


def read_type_rows(cur, cfg_uuid):
    """Строки витрины текущего состояния этой конфигурации (пятая сторона круга)."""
    return q(cur, "SELECT * FROM " + VIEW + " WHERE configuration_uuid = %s::uuid",
             (cfg_uuid,))


# ── контур 3: граница круга — файлы, индекс, перечень заголовка, корень, строки таблицы ─────
def check_circle(cur, header, dump_dir, index_info, expect, parsed, tag):
    section(f"Контур 3 — граница круга ({tag})")
    raw = circle_measures(dump_dir)
    file_names = registration_names(dump_dir)
    db_rows = read_type_rows(cur, str(header["uuid"]))
    header_list = read_header_name_list(cur, str(header["uuid"]))

    check(f"{tag}: каталог `{DIR_NAME}/` найден и плоский (подкаталогов, форм, макетов, "
          f"команд и модулей у вида нет — замер 1.2): подкаталогов {raw['subdirs']}, "
          f"файлов не-XML {raw['non_xml']}",
          raw["directory_present"] == 1 and raw["subdirs"] == 0 and raw["non_xml"] == 0,
          f"подкаталоги: {names(raw['child_dirs'])}; не-XML: {raw['non_xml']}")
    check(f"{tag}: файлов регистрации — эталону замера 1.1 ({expect['files']}), байтов — "
          f"эталону замера 1.4 ({expect['bytes']})",
          raw["files"] == expect["files"] and raw["bytes"] == expect["bytes"],
          f"файлов: {raw['files']}, байтов: {raw['bytes']}")
    check(f"{tag}: разбор круга завершён без отказа и без потерянных файлов (найдено "
          f"{parsed['files_found']}, разобрано {parsed['files_parsed']}; отказ файла "
          "называется причиной и останавливает стадию ДО записи — приём V12/V46)",
          parsed["success"] is True and parsed["files_found"] == expect["files"]
          and parsed["files_parsed"] == expect["files"]
          and int(parsed["files_failed"] or 0) == 0,
          f"success: {parsed['success']}, found: {parsed['files_found']}, read: "
          f"{parsed['files_parsed']}, failed: {_brief(parsed['failures'])}")
    check(f"{tag}: повторных имён вида внутри выгрузки нет (замер 1.1: ноль; иначе строки "
          "круга нарушили бы ключ цепи, и отказ называется списком имён, а не отдаётся на "
          "откуп планировщику БД)", not (parsed["duplicate_names"] or []),
          _brief(parsed["duplicate_names"]))

    # Четыре ноги круга плюс строки таблицы — пять сторон одного множества.
    index_names = set(index_info["kind_names"])
    table_names = {str(row["object_name"]) for row in db_rows}
    set_diff("файлы регистрации и индекс состава", file_names, index_names, tag)
    set_diff("файлы регистрации и перечень заголовка", file_names, header_list["names"], tag)
    set_diff("файлы регистрации и перечень корня `Configuration.xml`", file_names,
             raw["root_names"], tag)
    set_diff("файлы регистрации и строки таблицы", file_names, table_names, tag)
    set_diff("индекс состава и перечень заголовка", index_names, header_list["names"], tag)
    set_diff("индекс состава и строки таблицы", index_names, table_names, tag)

    check(f"{tag}: предикат круга — точное `object_type = '{INDEX_OBJECT_TYPE}'`; записей "
          f"по МАСКЕ начала имени столько же ({index_info['mask_rows']}), и это названо "
          "проверкой, а не выведено из совпадения префикса (в отличие от пары "
          "`FunctionalOptions`/`FunctionalOptionsParameters` — замер 1.2 плана V58)",
          index_info["kind_rows"] == expect["index_records"]
          and index_info["mask_rows"] == expect["index_records"],
          f"точных: {index_info['kind_rows']}, по маске: {index_info['mask_rows']}")
    check(f"{tag}: расхождений ног круга нет — {list(CIRCLE_DISCREPANCIES)} называются "
          "нулями, а не молчанием (замеры 1.1, 1.2: файлы и записи индекса с совпадающими "
          "uuid)", not any(parsed.get(state) for state in CIRCLE_DISCREPANCIES),
          "; ".join(f"{state}: {_brief(parsed.get(state))}"
                    for state in CIRCLE_DISCREPANCIES))
    uuid_diff = sorted(name for name in file_names
                       if raw["file_uuids"].get(name) != index_info["kind_uuids"].get(name))
    check(f"{tag}: uuid файла регистрации совпадают с uuid записей индекса состава "
          "(правило R3: не-uuid и пустой uuid — отказ файла, а не пустая строка)",
          not uuid_diff, f"расхождение: {names(uuid_diff)}")
    values_total = sum(len(as_json(row.get("types")) or []) for row in db_rows)
    check(f"{tag}: строк витрины — эталону замера 1.1 ({expect['db_rows']}), записей "
          f"значений `types` — эталону замера 1.4 ({expect['values']})",
          len(db_rows) == expect["db_rows"] and values_total == expect["values"],
          f"строк: {len(db_rows)}, значений: {values_total}")
    check(f"{tag}: перечень заголовка `configurations.{HEADER_NAME_COLUMN}` заполнен "
          f"({expect['header_names']} элементов) и не является `NULL` — в отличие от V56/"
          "V57, где KomMag давал `NULL`, потому что вида у него не было ни файлами, ни "
          "записями индекса",
          header_list["present"] and header_list["count"] == expect["header_names"]
          and header_list["is_null"] == bool(expect["header_null"]),
          f"элементов: {header_list['count']}, NULL: {header_list['is_null']}")
    check(f"{tag}: записей вида `BusinessProcess` в индексе состава — измеренному эталону "
          f"({BUSINESS_PROCESS_INDEX_ROWS[tag]}), записей с `RoutePoint` — "
          f"{ROUTE_POINT_INDEX_ROWS}: индекс знает бизнес-процесс, но не его точку маршрута, "
          "поэтому адрес `BusinessProcessRoutePoint.<Имя>` разрешён быть не может (число "
          "плана «66» прогон не подтвердил — названо измеренное)",
          index_info["business_process_rows"] == BUSINESS_PROCESS_INDEX_ROWS[tag]
          and index_info["route_point_rows"] == ROUTE_POINT_INDEX_ROWS,
          f"BusinessProcess: {index_info['business_process_rows']}, RoutePoint: "
          f"{index_info['route_point_rows']}")
    return raw, db_rows, header_list


# ── контур 4: строка таблицы против разбора того же слоя, что и загрузка ────────────────────
def compare_rows(parsed, db_rows, expect, tag):
    section(f"Контур 4 — строка таблицы против разбора того же слоя ({tag})")
    parse_rows = {str(row["object_name"]): row for row in parsed["rows"]}
    table_rows = {str(row["object_name"]): row for row in db_rows}
    check(f"{tag}: строк разбора и строк таблицы — одинаковое число ({len(parse_rows)}), "
          "имена совпадают (писатель пишет ровно тот круг, который разобрал)",
          len(parse_rows) == len(table_rows) == expect["db_rows"]
          and set(parse_rows) == set(table_rows),
          f"разбор: {len(parse_rows)}, таблица: {len(table_rows)}; расхождение: "
          f"{names(sorted(set(parse_rows) ^ set(table_rows)))}")

    scalar_columns = [key for key in row_keys()
                      if key not in JSON_COLUMNS and key not in ARRAY_COLUMNS]
    scalar_bad, json_bad, array_bad = {}, {}, {}
    for name, parse_row in sorted(parse_rows.items()):
        table_row = table_rows.get(name)
        if table_row is None:
            continue
        for column in scalar_columns:
            if parse_row.get(column) != table_row.get(column):
                scalar_bad.setdefault(column, []).append(
                    (name, _brief(parse_row.get(column), 80),
                     _brief(table_row.get(column), 80)))
        for column in JSON_COLUMNS:
            if canon_json(as_json(parse_row.get(column))) != canon_json(
                    as_json(table_row.get(column))):
                json_bad.setdefault(column, []).append(
                    (name, _brief(canon_json(as_json(parse_row.get(column))), 120),
                     _brief(canon_json(as_json(table_row.get(column))), 120)))
        for column in ARRAY_COLUMNS:
            if canon_array(parse_row.get(column)) != canon_array(
                    table_row.get(column)):
                array_bad.setdefault(column, []).append(
                    (name, _brief(parse_row.get(column), 80),
                     _brief(table_row.get(column), 80)))

    def report(group, label, universe):
        check(f"{tag}: {label} — расхождений нет ({sum(len(v) for v in group.values())} "
              f"расхождений по {len(group)} колонкам из {len(universe)} проверенных)",
              not group, "; ".join(
                  f"{column}: {names([f'{n} ({exp} ≠ {act})' for n, exp, act in issues[:3]])}"
                  for column, issues in sorted(group.items())))

    report(scalar_bad, f"скалярные колонки строки вида — свойства, `InternalInfo`, "
                       "`type_raw`, состояния, `source_path`", scalar_columns)
    report(json_bad, "колонки jsonb (`synonym`, `types`, `type_qualifiers`) — блок `<Type>` "
                     "с ключами цели и блоки квалификаторов совпадают дословно",
           list(JSON_COLUMNS))
    report(array_bad, "текстовый массив `unknown_property_names` (NULL и пустой массив — "
                      "разные состояния)", list(ARRAY_COLUMNS))

    # Самопроверка слоя: `row_problems` офлайн повторяет все CHECK'ы схемы. Ноль
    # самопроверок на живом круге — то же знание, что ACCEPT-тесты схемы, но без БД.
    problems = {name: row_problems(row) for name, row in sorted(parse_rows.items())}
    bad_problems = {name: issues for name, issues in problems.items() if issues}
    check(f"{tag}: самопроверка `row_problems` (повтор {len(MATCH_CONSTRAINTS)} CHECK'ов "
          f"схемы офлайн) не дала нарушений на {len(parse_rows)} строках",
          not bad_problems,
          "; ".join(f"{name}: {names(issues[:3])}"
                    for name, issues in sorted(bad_problems.items())[:5]))
    check(f"{tag}: сводка разбора называет число самопроверок нулём "
          f"(`row_problems` = {int(parsed.get('row_problems') or 0)}) — нуль является "
          "ответом, а не молчанием", int(parsed.get("row_problems") or 0) == 0,
          _brief(parsed.get("row_problems")))

    # Закрытость записей `types` на живом круге: схемой она не выражается (замер V48 2.5),
    # поэтому проверяется здесь — ключи записи, ключи цели только у `exact`, класс и
    # состояние из замкнутого словаря, кратность ↔ число записей (тот же инвариант, что
    # CHECK `defined_types_type_multiplicity_matches_types`).
    allowed = set(TYPE_ENTRY_KEYS) | set(TYPE_ENTRY_TARGET_KEYS)
    entry_bad, state_bad, class_bad, mult_bad, container_bad = [], [], [], [], []
    for name, parse_row in sorted(parse_rows.items()):
        entries = parse_row.get("types") or []
        for entry in entries:
            extra = sorted(set(entry) - allowed)
            missing = sorted(set(TYPE_ENTRY_KEYS) - set(entry))
            if extra or missing:
                entry_bad.append((name, f"лишние {names(extra)}; нет {names(missing)}"))
            target_keys = [key for key in TYPE_ENTRY_TARGET_KEYS if key in entry]
            if entry.get("resolve_state") == RESOLVE_EXACT and not target_keys:
                entry_bad.append((name, "exact без ключей цели"))
            if entry.get("resolve_state") != RESOLVE_EXACT and target_keys:
                entry_bad.append((name, f"ключи цели у состояния "
                                        f"{entry.get('resolve_state')}"))
            if entry.get("state") not in {ENTRY_STATE_PARSED, ENTRY_STATE_UNKNOWN_FORM}:
                state_bad.append((name, entry.get("state")))
            if entry.get("class") not in set(TYPE_CLASS_VALUES):
                class_bad.append((name, entry.get("class")))
            if entry.get("container") not in {CONTAINER_TYPE_TAG, CONTAINER_TYPESET_TAG}:
                container_bad.append((name, entry.get("container")))
        expected_mult = (MULT_SINGLE if len(entries) == 1
                         else MULT_COMPOSITE if len(entries) > 1 else MULT_ABSENT)
        if parse_row.get("type_multiplicity") != expected_mult:
            mult_bad.append((name, f"{parse_row.get('type_multiplicity')} ≠ "
                                   f"{expected_mult} при {len(entries)} записях"))
    for label, issues in (
            ("ключи записи `types` вне замкнутого словаря", entry_bad),
            ("состояние записи значения вне словаря", state_bad),
            ("класс значения вне словаря ФОРМ", class_bad),
            ("форма контейнера вне словаря", container_bad),
            ("кратность не согласована с числом записей `types`", mult_bad)):
        check(f"{tag}: {label} — ноль (CHECK по элементу массива jsonb PostgreSQL "
              "отклоняет, поэтому замкнутость держат слой разбора и эта проверка)",
              not issues, "; ".join(f"{name}: {detail}" for name, detail in issues[:5]))
    return parse_rows


# ── контур 5: независимая мера подстрокой и закрытость словаря ФОРМ ─────────────────────────
def compare_raw_measures(raw, parse_rows, parsed, db_rows, expect, tag):
    section(f"Контур 5 — независимая мера подстрокой, два числа квалификаторов ({tag})")
    check(f"{tag}: записей значений `<v8:Type>` по тексту файла — эталону замера 1.4 "
          f"({expect['values']}); обход дерева (слой разбора) и подстрока (эта проверка) "
          "считают одно множество независимо — приём `_v58_p0_shape_check.py`",
          raw["values"] == expect["values"]
          and int(parsed["types_total"]) == expect["values"]
          and sum(len(row.get("types") or []) for row in db_rows) == expect["values"],
          f"подстрока: {raw['values']}, разбор: {parsed['types_total']}, база: "
          f"{sum(len(row.get('types') or []) for row in db_rows)}")

    # Два независимых счёта сходятся пофайлово, а не только суммой: расхождение «в одном
    # файле на одно значение меньше» суммой не видно.
    per_file_bad = []
    for name, info in sorted(raw["per_file"].items()):
        entries = (parse_rows.get(name) or {}).get("types") or []
        values = [str(entry.get("value") or "") for entry in entries]
        if values != list(info["values"]):
            per_file_bad.append((name, f"подстрока {len(info['values'])}, разбор "
                                        f"{len(values)}"))
    check(f"{tag}: пофайловые списки значений совпадают во всех {len(raw['per_file'])} "
          "файлах круга (число и порядок)", not per_file_bad,
          "; ".join(f"{name}: {detail}" for name, detail in per_file_bad[:5]))

    check(f"{tag}: префиксы значений — эталону замера 2.2 (`cfg` {expect['prefix_cfg']}, "
          f"`xs` {expect['prefix_xs']}); других префиксов круг не даёт, и класс ставится по "
          "URI пространства имён префикса этого файла, а не по имени префикса (правило "
          "V48 2.4.4)",
          raw["prefixes"].get("cfg", 0) == expect["prefix_cfg"]
          and raw["prefixes"].get("xs", 0) == expect["prefix_xs"]
          and sum(raw["prefixes"].values()) == expect["values"],
          f"факт: {dict(raw['prefixes'])}")
    check(f"{tag}: контейнеров `<v8:TypeSet>` — эталону замера 2.2 ({expect['typeset']}): "
          "форма контейнера называется записью `types[].container`, отдельной колонки нет, "
          "а появление `TypeSet` держится наблюдением `type_set_container` (прецедент "
          "`DayTimes` узла V54)",
          raw["typeset"] == expect["typeset"]
          and int(parsed["observations"].get(OBSERVATION_TYPE_SET, 0)) == expect["typeset"]
          and set(parsed["counts_by_container"] or {}) <= {CONTAINER_TYPE_TAG,
                                                          CONTAINER_TYPESET_TAG},
          f"подстрока: {raw['typeset']}, разбор: "
          f"{parsed['observations'].get(OBSERVATION_TYPE_SET)}, словари: "
          f"{parsed['counts_by_container']}")

    # ДВА числа квалификаторов: файлов (мерой писателя и витрины) и блоков (мерой
    # содержимого). Девять файлов несут по два блока — составной тип строка+число.
    db_qual_rows = [row for row in db_rows if as_json(row.get("type_qualifiers"))]
    db_qual_blocks = sum(len((as_json(row.get("type_qualifiers")) or {}))
                         for row in db_qual_rows)
    check(f"{tag}: файлов с квалификаторами — эталону замера 2.2 ({expect['qual_files']}), "
          f"блоков квалификаторов — эталону замера 2.2 ({expect['qual_blocks']}); оба числа "
          "называются раздельно: строка одна на файл, а `type_qualifiers` хранит блоки "
          "этого файла вместе (разница — девять файлов с двумя блоками)",
          raw["qual_files"] == expect["qual_files"]
          and raw["qual_blocks"] == expect["qual_blocks"]
          and int(parsed["rows_with_qualifiers"]) == expect["qual_files"]
          and len(db_qual_rows) == expect["qual_files"]
          and db_qual_blocks == expect["qual_blocks"],
          f"подстрока: файлов {raw['qual_files']}, блоков {raw['qual_blocks']}; разбор: "
          f"{parsed['rows_with_qualifiers']}; база: строк {len(db_qual_rows)}, блоков "
          f"{db_qual_blocks}")
    check(f"{tag}: имена квалификаторов — тот же словарь, что у V48/V50/V52 (новый блок "
          "имя не вносит, замер 2.2)",
          set(raw["qual_tags"]) <= {"StringQualifiers", "NumberQualifiers",
                                    "DateQualifiers"}
          and all(set((as_json(row.get("type_qualifiers")) or {})) <=
                  {"StringQualifiers", "NumberQualifiers", "DateQualifiers"}
                  for row in db_qual_rows),
          f"подстрока: {dict(raw['qual_tags'])}")
    check(f"{tag}: пустых блоков квалификаторов ноль — пустой блок состоянием строки не "
          "является и назывался бы наблюдением `empty_qualifier_block` (прецедент пустого "
          "блока разделения данных узла V50)",
          int(parsed["observations"].get("empty_qualifier_block", 0)) == 0,
          _brief(parsed["observations"]))
    return db_qual_rows


def check_form_dictionary(dump_dir, parse_rows, expect, tag):
    """Словарь ФОРМ значения прогоняется по независимому списку значений (контур 5.1).

    Значения берутся из текста файла выражениями проверки, а класс и адрес — из слоя
    разбора: путь `_v58_p0_shape_check.py` и раздела 2.4 плана (по значениям круга
    прогонялась настоящая функция классификации узла V48). Расхождение читалось бы
    «значением, которое разбор не увидел».
    """
    root = Path(dump_dir) / DIR_NAME
    class_bad, address_bad, ns_bad = [], [], []
    values_seen = 0
    for entry_path in sorted(root.glob("*.xml")) if root.is_dir() else []:
        text, error = read_text_file(entry_path)
        if error or text is None:
            continue
        ns_map, _warnings = file_namespace_map(text)
        rows = parse_rows.get(entry_path.stem) or {}
        entries = rows.get("types") or []
        raw_values = [match.group(1) for match in VALUE_RE.finditer(text)]
        values_seen += len(raw_values)
        for position, value in enumerate(raw_values):
            entry = entries[position] if position < len(entries) else {}
            probe = classify_type_value(value, ns_map)
            if probe.get("class") not in set(TYPE_CLASS_VALUES):
                class_bad.append((entry_path.name, value, probe.get("class")))
            if probe.get("class") != entry.get("class"):
                class_bad.append((entry_path.name, value,
                                  f"{probe.get('class')} ≠ {entry.get('class')}"))
            _prefix, local = split_qname(value)
            _class, address, _reason = type_value_form(local)
            if address and address != entry.get("target_full_name") and entry.get(
                    "resolve_state") != RESOLVE_UNRESOLVED:
                address_bad.append((entry_path.name, value,
                                    f"{address} ≠ {entry.get('target_full_name')}"))
            if probe.get("ns_uri") is None and value.startswith(("cfg:", "xs:")):
                ns_bad.append((entry_path.name, value))
    check(f"{tag}: словарь ФОРМ замкнут на {values_seen} значениях, прогнанных независимым "
          f"путём: класс каждой записи — из {len(TYPE_CLASS_VALUES)} значений словаря и "
          "совпадает с записанной строкой (замер 2.3: 25 форм)",
          not class_bad and values_seen == expect["values"],
          f"значений прогнано: {values_seen}; расхождения: "
          f"{names([f'{n} {v} → {c}' for n, v, c in class_bad[:5]])}")
    check(f"{tag}: адрес цели, выведенный из ФОРМЫ значения, совпадает с записанным "
          "`target_full_name` у всех разрешённых записей (суффикс формы `Ref`/`Object`/"
          "`RecordSet`/`ValueManager` снимается ОДИН раз, текст значения индексом не "
          "ищется — прецедент V48)", not address_bad,
          names([f"{n} {v} → {a}" for n, v, a in address_bad[:5]]))
    check(f"{tag}: префикс каждого значения `cfg`/`xs` объявлен в этом файле (URI "
          "пространства имён читается из объявления файла, а не из общего словаря префиксов "
          "— правило V48 2.4.4)", not ns_bad, names(ns_bad[:5]))


# ── контур 6: разрешимость целей индексом состава ЭТОЙ конфигурации ─────────────────────────
def check_resolution(cur, db_rows, parsed, index_info, expect, tag):
    section(f"Контур 6 — разрешение целей индексом состава этой конфигурации ({tag})")
    index_by_name = index_rows_by_name(index_info["rows"])
    expected_exact = expect["values"] - expect["no_target"] - expect["unresolved"]
    derived, resolved = set(), set()
    exact_bad, unresolved_bad, no_target_bad, uuid_bad, type_bad = [], [], [], [], []
    counts = Counter()
    for row in db_rows:
        for entry in (as_json(row.get("types")) or []):
            state = entry.get("resolve_state")
            counts[state] += 1
            address = entry.get("target_full_name")
            _prefix, local = split_qname(entry.get("value"))
            _class, derived_address, _reason = type_value_form(local)
            if derived_address:
                derived.add(derived_address)
            if state == RESOLVE_EXACT:
                resolved.add(address)
                if address not in index_by_name:
                    exact_bad.append((row["object_name"], address))
                    continue
                index_row = index_by_name[address]
                if str(entry.get("target_object_uuid") or "").lower() != \
                        str(index_row.get("uuid") or "").lower():
                    uuid_bad.append((row["object_name"], address))
                if entry.get("target_object_type") != index_row.get("object_type"):
                    type_bad.append((row["object_name"], address,
                                     f"{entry.get('target_object_type')} ≠ "
                                     f"{index_row.get('object_type')}"))
            elif state == RESOLVE_UNRESOLVED:
                if address:
                    if address in index_by_name:
                        unresolved_bad.append((row["object_name"], address))
                    if not str(entry.get("value") or "").startswith(
                            UNRESOLVED_VALUE_PREFIX):
                        unresolved_bad.append(
                            (row["object_name"],
                             f"вне границы {UNRESOLVED_VALUE_PREFIX}: {entry.get('value')}"))
            elif state == RESOLVE_NO_TARGET:
                if address:
                    no_target_bad.append((row["object_name"], entry.get("value")))
            else:
                no_target_bad.append((row["object_name"], f"состояние {state}"))

    check(f"{tag}: состояний разрешения — эталону замера 2.5 (`exact` {expected_exact}, "
          f"`no_target` {expect['no_target']}, `unresolved` {expect['unresolved']}); "
          "`no_target` — примитивы, у которых цели нет по определению, `unresolved` — адрес "
          "выведен, но строки индекса нет",
          counts[RESOLVE_EXACT] == expected_exact
          and counts[RESOLVE_NO_TARGET] == expect["no_target"]
          and counts[RESOLVE_UNRESOLVED] == expect["unresolved"]
          and sum(counts.values()) == expect["values"],
          f"факт: {dict(counts)}")
    check(f"{tag}: `no_target` равен числу примитивов `xs:*` ({expect['prefix_xs']}) — то "
          "же множество названо двумя способами, а не одним (замер 2.5: 197 на корпус)",
          counts[RESOLVE_NO_TARGET] == expect["prefix_xs"]
          and int(parsed["resolve_no_target"]) == expect["prefix_xs"],
          f"no_target: {counts[RESOLVE_NO_TARGET]}, xs: {expect['prefix_xs']}")
    check(f"{tag}: записям `exact` соответствует строка индекса состава ЭТОЙ конфигурации "
          "(ключ — полное точечное имя `index_row_key`); `exact` означает «строка индекса "
          "найдена», а не «объект существует в базе» — формулировка названа ещё в схеме "
          "V50/V52)", not exact_bad, names([f"{n} → {a}" for n, a in exact_bad[:5]]))
    check(f"{tag}: ключи цели `target_object_uuid`/`target_object_type` совпадают со "
          "строкой индекса; цель называется ПОЛНЫМ индексным именем — тот же ключ, что у "
          f"GIN-запроса {GIN_EXAMPLE}",
          not uuid_bad and not type_bad,
          f"uuid: {names([f'{n} → {a}' for n, a in uuid_bad[:5]])}; тип: "
          f"{names([f'{n} → {a} {why}' for n, a, why in type_bad[:5]])}")
    check(f"{tag}: неразрешённых целей — эталону замера 2.5 ({expect['unresolved']}), и "
          f"все они лежат вне индекса состава и несут адрес `{UNRESOLVED_ADDRESS_PREFIX}…` "
          "(шесть называются адресами, а не сводятся к счётчику — развилка Q6)",
          counts[RESOLVE_UNRESOLVED] == expect["unresolved"] and not unresolved_bad,
          f"факт: {counts[RESOLVE_UNRESOLVED]}; расхождения: "
          f"{names([f'{n} → {a}' for n, a in unresolved_bad[:5]])}")
    check(f"{tag}: у записей `no_target` и вне словаря классов ключей цели нет вовсе "
          "(прецедент D3 V39/V46: отсутствие ключа читается как «цели нет или она не "
          "найдена»), и состояний разрешения вне замкнутого словаря нет",
          not no_target_bad, names([f"{n} → {v}" for n, v in no_target_bad[:5]]))
    check(f"{tag}: ДВА числа адресов названы раздельно — выведенных из ФОРМЫ "
          f"({len(derived)}) и подтверждённых индексом ({len(resolved)}); разница равна "
          "числу неразрешённых целей (пересчёт `_v58_p3_offline_probe.py`: 2 419 против "
          "2 413 на корпус; смешение читалось бы «потерянными целями»)",
          len(derived) - len(resolved) == counts[RESOLVE_UNRESOLVED]
          and int(parsed["derived_target_addresses"]) == len(derived)
          and int(parsed["distinct_target_addresses"]) == len(resolved)
          and int(parsed["types_resolved"]) == counts[RESOLVE_EXACT]
          and int(parsed["types_unresolved"]) == counts[RESOLVE_UNRESOLVED],
          f"выведенных: {len(derived)}, разрешено: {len(resolved)}; разбор: "
          f"{parsed['derived_target_addresses']}/{parsed['distinct_target_addresses']}")
    class_counts = Counter(str(entry.get("class")) for row in db_rows
                           for entry in (as_json(row.get("types")) or []))
    multiplicity = Counter(str(row.get("type_multiplicity")) for row in db_rows)
    internal = Counter(str(row.get("internal_info_state")) for row in db_rows)
    properties = Counter(str(row.get("properties_state")) for row in db_rows)
    parse_state = Counter(str(row.get("type_parse_state")) for row in db_rows)
    check(f"{tag}: словари состояний ответа разбора выводятся из тех же записей, что и "
          "колонки строк (второго источника знания у узла нет — правило V43)",
          all(int(parsed["counts_by_type_multiplicity"].get(state, 0))
              == multiplicity.get(state, 0) for state in MULTIPLICITY_VALUES)
          and all(int(parsed["counts_by_internal_info_state"].get(state, 0))
                  == internal.get(state, 0) for state in INTERNAL_INFO_STATES)
          and all(int(parsed["counts_by_properties_state"].get(state, 0))
                  == properties.get(state, 0) for state in PROPERTIES_STATES)
          and all(int(parsed["counts_by_type_parse_state"].get(state, 0))
                  == parse_state.get(state, 0) for state in RECORD_STATES),
          f"база: {dict(multiplicity)} {dict(internal)} {dict(properties)} "
          f"{dict(parse_state)}; ответ: {parsed['counts_by_type_multiplicity']} "
          f"{parsed['counts_by_internal_info_state']} "
          f"{parsed['counts_by_properties_state']} {parsed['counts_by_type_parse_state']}")
    check(f"{tag}: классы значений строк таблицы равны словарям ответа разбора по всем "
          f"{len(TYPE_CLASS_VALUES)} значениям словаря (в том числе нулями границ "
          "`defined_type_ref` и `unknown`)",
          all(int(parsed["counts_by_class"].get(value, 0)) == class_counts.get(value, 0)
              for value in TYPE_CLASS_VALUES),
          f"база: {dict(class_counts)}; ответ: {parsed['counts_by_class']}")
    return counts, class_counts, derived, resolved


# ── контур 7: витрина текущего состояния, цепь ревизий и граница configuration_uuid ──────────
# Цепь узла V19 читается одним шаблоном: строка текущая, если для той же области видимости нет
# строки с большим `revision_no`. Область видимости — ровно ключ M1 (`configuration_uuid,
# object_name`), поэтому проверка держит ТЕКСТ шаблона, а не только числа: ключ без границы
# конфигурации слил бы BGU2 и BP3 в одну «текущую» строку, потому что 247 имён и 243 `uuid`
# вида у этих двух выгрузок совпадают (замер 1.3, M1).
VIEW_CHAIN_MARKERS = (
    "not (exists",
    "h.configuration_uuid = dt.configuration_uuid",
    "h.object_name = dt.object_name",
    "h.revision_no > dt.revision_no",
)


def view_definition(cur):
    """Текст витрины из живой схемы — нормализованный (переносы pg_get_viewdef не значат)."""
    text = scalar(cur, "SELECT pg_get_viewdef(%s::regclass, true)", (VIEW,)) or ""
    return compact(text).lower()


def _revision_fixture(cur, expected_rows):
    """Вторая ревизия одной строки — в транзакции прогона, которая откатывается после мерки.

    Живой корпус второй ревизии не даёт (четыре выгрузки загружались по одному разу), поэтому
    цепь проверяется фикстурой: строка копируется с `revision_no = 2`, витрина обязана отдать
    новую строку СВОЕЙ конфигурации и не тронуть строку той же позиции в другой конфигурации.
    Откат возвращает круг к эталону: проверка не оставляет в базе состояний, которых в ней не
    было.
    """
    shared = q(cur, "SELECT object_name FROM " + VIEW + " GROUP BY object_name "
                    "HAVING count(DISTINCT configuration_uuid) > 1 "
                    "ORDER BY object_name LIMIT 1")
    if not shared:
        skip("фикстура второй ревизии цепи",
             "имён вида, общих для двух конфигураций, в базе нет — границу цепи сравнить "
             "не с чем (эталон замера 1.3 называет 247 таких имён)")
        return
    object_name = str(shared[0]["object_name"])
    rows = q(cur, "SELECT id, configuration_uuid::text AS configuration_uuid, revision_no "
                  "FROM " + VIEW + " WHERE object_name = %s ORDER BY configuration_uuid",
             (object_name,))
    if len(rows) < 2:
        skip("фикстура второй ревизии цепи",
             "имя `%s` в витрине отдано %d конфигурациями, а нужно две — границу цепи чем "
             "сравнивать, не названо" % (object_name, len(rows)))
        return
    target, twin = rows[0], rows[1]
    columns = [c for c in table_columns(cur, TABLE_NAME) if c != "id"]
    select_list = ", ".join("%s" if c == "revision_no" else c for c in columns)
    insert_sql = ("INSERT INTO " + TABLE_NAME + " (" + ", ".join(columns) + ") SELECT "
                  + select_list + " FROM " + TABLE_NAME + " WHERE id = %s "
                  "RETURNING id, revision_no")
    try:
        inserted = q(cur, insert_sql, [2, target["id"]])
        check("фикстура: вторая ревизия строки круга записана — цепь узла V19 живая, "
              "`revision_no = 2` проходит CHECK положительной ревизии",
              len(inserted) == 1 and int(inserted[0]["revision_no"]) == 2, _brief(inserted))
        current = q(cur, "SELECT id, revision_no FROM " + VIEW + " WHERE configuration_uuid = "
                         "%s::uuid AND object_name = %s",
                    (target["configuration_uuid"], object_name))
        check("фикстура: витрина текущего состояния отдаёт ОДНУ строку области видимости, и "
              "ей является старшая ревизия (прежняя остаётся в истории, а не в ответе)",
              len(current) == 1 and int(current[0]["revision_no"]) == 2
              and int(current[0]["id"]) == int(inserted[0]["id"]), _brief(current))
        twin_rows = q(cur, "SELECT revision_no, id FROM " + VIEW + " WHERE object_name = %s "
                           "AND configuration_uuid = %s::uuid",
                      (object_name, twin["configuration_uuid"]))
        check("фикстура: та же позиция вида в ДРУГОЙ конфигурации не затронута — 247 общих "
              "имён существуют раздельно (M1: цепь ограничена `configuration_uuid`, Q2 "
              "раздела 5 плана)",
              len(twin_rows) == 1 and int(twin_rows[0]["revision_no"])
              == int(twin["revision_no"]) and int(twin_rows[0]["id"]) == int(twin["id"]),
              "сосед: " + _brief(twin_rows) + ", ожидалось: revision_no "
              + str(twin["revision_no"]) + ", id " + str(twin["id"]))
        held = scalar(cur, "SELECT count(*) FROM " + TABLE_NAME
                      + " WHERE configuration_uuid = %s::uuid AND object_name = %s",
                      (target["configuration_uuid"], object_name))
        check("фикстура: базовая таблица держит обе ревизии — запись новой не снимает прежнюю "
              "(историю даёт цепь ревизий, а не таблица состояния)", held == 2,
              "строк в базовой таблице: %s" % held)
        # Повтор пары (конфигурация, имя, ревизия) — отказ ключа, а не вторая строка: без него
        # одна выгрузка с двумя файлами одного имени дала бы две «текущие» строки.
        cur.execute("SAVEPOINT v58_fixture_duplicate_key")
        rejected = False
        try:
            cur.execute(insert_sql.replace("RETURNING id, revision_no", "RETURNING id"),
                        [1, target["id"]])
            cur.fetchall()
        except Exception:  # noqa: BLE001 — отказ ключа и есть ожидаемый результат
            rejected = True
        cur.execute("ROLLBACK TO SAVEPOINT v58_fixture_duplicate_key")
        check("фикстура: повтор пары (`configuration_uuid`, `object_name`, `revision_no`) "
              "отклоняется ключом `%s` — повторное имя внутри одной выгрузки называется "
              "состоянием `duplicate_names` слоем разбора ДО записи, а не второй текущей "
              "строкой" % SCOPE_KEY_NAME, rejected,
              "повтор принят — ключ цепи не держит область видимости")
    finally:
        cur.connection.rollback()
    restored = scalar(cur, "SELECT count(*) FROM " + TABLE_NAME)
    check("фикстура откатана: строк круга снова равны эталону корпуса — проверка не оставляет "
          "в базе состояний, которых в ней не было",
          restored == CORPUS_EXPECTATIONS["db_rows"],
          "после отката: %s, эталон: %s" % (restored, CORPUS_EXPECTATIONS["db_rows"]))


def check_views(cur):
    section("Контур 7 — витрина текущего состояния, цепь ревизий и граница configuration_uuid")
    definition = view_definition(cur)
    if not definition:
        check("витрина `%s` существует и читается схемой" % VIEW, False,
              "текста определения нет")
        return
    missing = [marker for marker in VIEW_CHAIN_MARKERS if marker not in definition]
    check("витрина собрана шаблоном цепи узла V19: строка текущая, когда для той же области "
          "видимости (%s) нет старшей ревизии; область видимости названа текстом, потому что "
          "подмена ключа слила бы две выгрузки в одну «текущую» строку (247 общих имён, M1)"
          % ", ".join(VIEW_CHAIN_MARKERS[1:]), not missing,
          "нет фрагментов: %s" % names(missing))

    base_rows = scalar(cur, "SELECT count(*) FROM " + TABLE_NAME)
    view_rows = scalar(cur, "SELECT count(*) FROM " + VIEW)
    corpus_rows = CORPUS_EXPECTATIONS["db_rows"]
    check("строк витрины — эталону корпуса (%d), и он равен числу строк базовой таблицы: "
          "корпус второй ревизии не даёт, поэтому все строки таблицы являются текущими"
          % corpus_rows, view_rows == base_rows == corpus_rows,
          "витрина: %s, таблица: %s" % (view_rows, base_rows))
    duplicates = q(cur, "SELECT object_name, count(*) AS rows_count FROM " + VIEW
                   + " GROUP BY configuration_uuid, object_name HAVING count(*) > 1")
    check("областей видимости с двумя «текущими» строками — ноль (иначе читатель карточки "
          "увидел бы один вид дважды)", not duplicates,
          "области: " + names(["%s×%s" % (d["object_name"], d["rows_count"])
                               for d in duplicates[:5]]))
    outside = scalar(cur, "SELECT count(*) FROM " + TABLE_NAME + " d WHERE NOT exists("
                          "SELECT 1 FROM " + VIEW + " v WHERE v.id = d.id)")
    check("строк базовой таблицы вне витрины — ноль: цепь V19 и витрина даются одной миграцией, "
          "а висящая строка означала бы, что карточка конфигурации её не покажет", not outside,
          "вне витрины: %s" % outside)
    orphans = scalar(cur, "SELECT count(*) FROM " + TABLE_NAME + " d WHERE NOT exists("
                          "SELECT 1 FROM configurations c WHERE c.uuid = d.configuration_uuid)")
    check("сирот вида (строка свойств без строки заголовка) — ноль: внешнего ключа в схеме нет "
          "осознанно (прецедент V20.1), поэтому связность держится снятием по "
          "`configuration_uuid` слоем `remove_defined_types`", not orphans,
          "сирот: %s" % orphans)

    # M1 (замер 1.3): имена и uuid вида пересекаются между выгрузками, но строки раздельны.
    distinct_names = scalar(cur, "SELECT count(DISTINCT object_name) FROM " + VIEW)
    distinct_uuids = scalar(cur, "SELECT count(DISTINCT object_uuid) FROM " + VIEW)
    shared_names = scalar(cur, "SELECT count(*) FROM (SELECT object_name FROM " + VIEW
                               + " GROUP BY object_name HAVING count(DISTINCT configuration_uuid) "
                                 "> 1) t")
    shared_uuids = scalar(cur, "SELECT count(*) FROM (SELECT object_uuid FROM " + VIEW
                               + " GROUP BY object_uuid HAVING count(DISTINCT configuration_uuid) "
                                 "> 1) t")
    wanted = CORPUS_EXPECTATIONS
    check("граница цепи — измеренным числам замера 1.3: различных имён %d, различных `uuid` "
          "%d, из них встречаются в двух и более выгрузках %d имён и %d `uuid`; при этом "
          "строк корпуса %d, то есть пересечение имён не означает слияния строк"
          % (wanted["distinct_names"], wanted["distinct_uuids"], wanted["shared_names"],
             wanted["shared_uuids"], wanted["db_rows"]),
          distinct_names == wanted["distinct_names"]
          and distinct_uuids == wanted["distinct_uuids"]
          and shared_names == wanted["shared_names"]
          and shared_uuids == wanted["shared_uuids"],
          "имена: %s (общих %s), uuid: %s (общих %s)"
          % (distinct_names, shared_names, distinct_uuids, shared_uuids))
    per_name = scalar(cur, "SELECT count(*) FROM (SELECT configuration_uuid, object_name, "
                           "count(*) AS c FROM " + VIEW
                           + " GROUP BY 1, 2 HAVING count(*) > 1) t")
    check("внутри одной конфигурации имя вида встречается один раз — повторов внутри выгрузки "
          "корпус не даёт (%d), и повторное имя остановил бы стадию до записи"
          % wanted["duplicate_names_inside"], not per_name,
          "областей с повтором: %s" % per_name)
    deep = scalar(cur, "SELECT count(*) FROM " + TABLE_NAME + " WHERE revision_no > 1")
    info("строк не первой ревизии в `%s`: %s (цепь узла V19 жива; перезагрузки со второй "
         "ревизией корпус не давал — замеры узла V58 делались одной загрузкой, поэтому цепь "
         "проверяется фикстурой ниже)" % (TABLE_NAME, deep))
    _revision_fixture(cur, wanted["db_rows"])



# ── контур 8: контракт стадии, порядка позиций и нулевого ответа ─────────────────────────────
def check_contract():
    section("Контур 8 — контракт стадии S4m, порядка позиций нормативного списка и нулевого "
            "ответа")
    ids = [stage for stage, _title in STAGES]
    check("стадия `%s` стоит сразу после `%s` — позиции 2.12 → 2.13 нормативного списка "
          "«Структура конфигурации.txt», а не порядок литер"
          % (STAGE_DEFINED_TYPES, STAGE_FUNCTIONAL_OPTIONS_PARAMETERS),
          ids.index(STAGE_DEFINED_TYPES) == ids.index(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS) + 1,
          "порядок: %s" % ids)
    check("`%s` остаётся последней стадией (вторая транзакция текстов модулей), а `%s` стоит "
          "перед ней" % (STAGE_OBJECT_MODULES, STAGE_DEFINED_TYPES),
          ids[-1] == STAGE_OBJECT_MODULES
          and stages_after(STAGE_DEFINED_TYPES)[:1] == [STAGE_OBJECT_MODULES]
          and is_last_stage(STAGE_OBJECT_MODULES), "порядок: %s" % ids)
    check("stages_after('%s') называет продолжением `%s` — дозагрузка вида не теряется в "
          "перечне стадий" % (STAGE_FUNCTIONAL_OPTIONS_PARAMETERS, STAGE_DEFINED_TYPES),
          stages_after(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS)[:1] == [STAGE_DEFINED_TYPES],
          str(stages_after(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS)))
    check("stages_after('%s') называет продолжением `%s`" % (STAGE_DEFINED_TYPES,
                                                             STAGE_OBJECT_MODULES),
          stages_after(STAGE_DEFINED_TYPES)[:1] == [STAGE_OBJECT_MODULES],
          str(stages_after(STAGE_DEFINED_TYPES)))
    check(f"у стадии `{STAGE_DEFINED_TYPES}` отдельного входа дозагрузки БОЛЬШЕ НЕТ: продолжение только "
          "полной перезагрузкой единой точки входа (узел TOOL-DROP, 05.11.2026) — "
          "зеркало STAGE_FULL_RELOAD_ONLY обязано называть это состоянием",
          STAGE_FULL_RELOAD_ONLY.get(STAGE_DEFINED_TYPES) is True,
          str(STAGE_FULL_RELOAD_ONLY.get(STAGE_DEFINED_TYPES)))
    title = stage_title(STAGE_DEFINED_TYPES)
    hint = stage_resume_hint(STAGE_DEFINED_TYPES)
    check("заголовок стадии называет позицию 2.13 и каталог вида `%s/`" % DIR_NAME,
          "2.13" in title and DIR_NAME in title, _brief(title))
    check("подсказка продолжения называет полную перезагрузку единой точки входа "
            "(отдельный вход позиции снят узлом TOOL-DROP, 05.11.2026)",
            "load_1c_catalog_tool" in hint and "TOOL-DROP" in hint, _brief(hint))
    check("подсказка продолжения равна константе круга (текст один, а не пересказ)",
          hint == DEFINED_TYPES_REPEAT_HINT, _brief(hint))
    check("заголовок раздела карточки называет узел V58 и позицию 2.13",
          "V58" in DEFINED_TYPES_SECTION_HEADER and "2.13" in DEFINED_TYPES_SECTION_HEADER,
          _brief(DEFINED_TYPES_SECTION_HEADER))
    check("текст границы круга называет таблицу вида, позицию 2.13, три ноги круга и словарь "
          "расхождений — карточка обязана описывать круг, а не только числа",
          TABLE_NAME in DEFINED_TYPES_CIRCLE_BOUNDARY
          and "2.13" in DEFINED_TYPES_CIRCLE_BOUNDARY
          and DIR_NAME in DEFINED_TYPES_CIRCLE_BOUNDARY
          and all(state in DEFINED_TYPES_CIRCLE_BOUNDARY for state in CIRCLE_DISCREPANCIES),
          _brief(DEFINED_TYPES_CIRCLE_BOUNDARY))
    check("текст границы круга называет то, чего узел НЕ делает: чужие слои `<Type>` с "
          "`cfg:DefinedType.*` не переразрешает (мера M5) и существование целей не утверждает "
          "(Q3 раздела 6 плана)",
          "DefinedType." in DEFINED_TYPES_CIRCLE_BOUNDARY
          and ("bsl_modules" in DEFINED_TYPES_CIRCLE_BOUNDARY
               or "тексты модулей" in DEFINED_TYPES_CIRCLE_BOUNDARY),
          _brief(DEFINED_TYPES_CIRCLE_BOUNDARY))
    check("словари наблюдений и расхождений контракта равны словарям слоя разбора (одна "
          "классификация, а не два перечня)",
          tuple(DEFINED_TYPES_OBSERVATION_KINDS) == tuple(OBSERVATION_KINDS)
          and tuple(DEFINED_TYPES_COUNT_KEYS) == tuple(COUNT_KEYS),
          "наблюдения: %s; count-ключи: %s" % (names(DEFINED_TYPES_OBSERVATION_KINDS),
                                               names(DEFINED_TYPES_COUNT_KEYS)))
    check("зеркало состояний контракта построено по словарю разбора: `state_columns()` равна "
          "перечню контракта, а круг колонок состояний — одной таблице круга",
          tuple(DEFINED_TYPES_STATE_VOCABULARIES) == tuple(state_columns())
          and set(STATE_VOCABULARY_TABLES.values()) == {TABLE_NAME},
          "контракт: %s; таблица: %s" % (names(DEFINED_TYPES_STATE_VOCABULARIES),
                                         names(STATE_VOCABULARY_TABLES)))


    # Закрытый контракт ответа (C1, C2, C3): нули обязаны быть названы по полному словарю,
    # иначе «стадия не выполнена» читается как «определяемых типов нет».
    defaults = defined_types_defaults()
    needed = (set(LOADER_SUMMARY_KEYS) | set(COUNT_KEYS) | set(RESOLVE_COUNT_KEYS)
              | {"counts_by_circle_discrepancy", "removed_by_table", "written_by_table",
                 "stage", "tables", "directory", "state_columns", "index_available",
                 "index_kind_records", "statistics_refreshed"})
    absent = sorted(key for key in needed if key not in defaults)
    check("нулевой контракт перечисляет все ключи сводки разбора, ключей круга снятия, стадии "
          "и состояния индекса (%d ключей) — ответ не зависит от удачи выгрузки" % len(needed),
          not absent, "ключей нет: %s" % names(absent))
    check("нулевой контракт называет круг снятия, стадию и каталог круга",
          defaults.get("tables") == list(DEFINED_TYPES_REMOVE_ORDER)
          and defaults.get("stage") == STAGE_DEFINED_TYPES
          and defaults.get("directory") == DIR_NAME,
          "tables: %s, stage: %s" % (_brief(defaults.get("tables")), defaults.get("stage")))
    bad_counts = []
    for column, vocabulary in DEFINED_TYPES_STATE_VOCABULARIES.items():
        got = sorted((defaults.get("counts_by_" + column) or {}).keys())
        if got != sorted(vocabulary):
            bad_counts.append("%s → %s" % (column, names(got)))
    check("словари состояний нулевого контракта построены по полному словарю колонок "
          "(%d словарей: %s)" % (len(DEFINED_TYPES_STATE_VOCABULARIES),
                                 names(DEFINED_TYPES_STATE_VOCABULARIES)),
          not bad_counts, "; ".join(bad_counts))
    check("нулевой контракт называет распределение значений по классам полным словарём (в том "
          "числе `defined_type_ref` и `unknown` — нулём, а не молчанием), наблюдения круга — "
          "всем словарём, расхождения ног — всем перечнем",
          sorted((defaults.get("counts_by_class") or {}).keys())
          == sorted(TYPE_CLASS_VALUES)
          and sorted((defaults.get("observations") or {}).keys()) == sorted(OBSERVATION_KINDS)
          and sorted((defaults.get("counts_by_circle_discrepancy") or {}).keys())
          == sorted(CIRCLE_DISCREPANCIES),
          "классы: %s" % names(sorted((defaults.get("counts_by_class") or {}).keys())))
    numbers = {key: value for key, value in defaults.items()
               if isinstance(value, int) and not isinstance(value, bool)}
    check("числовые поля нулевого контракта равны нулю (%d полей) — «не выполнялась» не "
          "читается как «строк нет»" % len(numbers),
          all(value == 0 for value in numbers.values()),
          "ненулевые: %s" % names(sorted(k for k, v in numbers.items() if v)))
    check("нулевой контракт помечает стадию невыполненной (`success` False, статус не успех)",
          defaults.get("success") is False and defaults.get("status") not in ("ok", True),
          "status: %s" % defaults.get("status"))
    check("групп `kinds` у контракта нет — это решение Q1 раздела 5 плана V58 (вариант A), а "
          "не пропуск: блок `<Type>` является колонками строки вида, состояния «записать "
          "свойства без типа» в модели нет, а порога цены замер 2.2 не дал",
          "kinds" not in defaults, "ключи: %s" % names(sorted(defaults)))
    signature = inspect.signature(load_defined_types)
    check("сигнатура слоя `load_defined_types` — `source_path` и необязательные "
          "`configuration_uuid`/`changed_at`; параметра `kinds` нет (тот же ответ, что у "
          "контракта)",
          set(signature.parameters) == {"source_path", "configuration_uuid", "changed_at"},
          "параметры: %s" % names(list(signature.parameters)))

    # Три разных ответа форматтера (C1): «стадия не выполнена», «отказ разбора круга» и
    # «круг записан». Четвёртым называется состояние индекса — предупреждение, а не отказ.
    not_run = [str(line) for line in (format_defined_types_lines(defaults) or [])]
    check("форматтер невыполненной стадии называет сам факт (стадия + «стадия не выполнялась») "
          "и не приписывает кругу строк (C1)",
          bool(not_run) and any(STAGE_DEFINED_TYPES in line and "стадия не выполнялась" in line
                                for line in not_run)
          and not any("строк " in line and any(digit in line for digit in "123456789")
                      for line in not_run), _brief(compact(not_run[:3])))
    failure = dict(defaults)
    failure.update({"status": "error", "success": False,
                    "error": "Круг не записан: 2 файла каталога не разобраны",
                    "reason": "отказ разбора",
                    "failures": [{"source_path": "DefinedTypes/Вид.xml",
                                  "reason": "не читается XML"}]})
    failure_lines = [str(line) for line in (format_defined_types_lines(failure) or [])]
    check("форматтер отказа разбора называет причину и файл-виновник: «не записано» и «нечего "
          "записывать» — разные ответы (C1, приём V12/V46…V57)",
          any("не разобраны" in line for line in failure_lines)
          and any("Вид.xml" in line for line in failure_lines),
          _brief(compact(failure_lines[:4])))
    success = dict(defaults)
    success.update({"status": "ok", "success": True, "configuration_id": 1,
                    "configuration_name": "Probe", "index_available": True,
                    "index_kind_records": CORPUS_EXPECTATIONS["index_records"],
                    "files_found": CORPUS_EXPECTATIONS["files"],
                    "files_parsed": CORPUS_EXPECTATIONS["files"],
                    "types_total": CORPUS_EXPECTATIONS["values"],
                    "max_values_per_file": CORPUS_EXPECTATIONS["max_values_per_file"],
                    "derived_target_addresses": CORPUS_EXPECTATIONS["derived_addresses"],
                    "distinct_target_addresses": CORPUS_EXPECTATIONS["resolved_addresses"],
                    "rows_with_qualifiers": CORPUS_EXPECTATIONS["qual_files"],
                    "row_problems": 0, "defined_types_written": 0})
    ok_lines = [str(line) for line in (format_defined_types_lines(success) or [])]
    check("форматтер успеха называет таблицу круга с нулями («записано 0» отличается от «стадия "
          "не выполнялась») и печатает последним строкой текст границы круга",
          any(TABLE_NAME in line and "снято=0/записано=0" in line for line in ok_lines)
          and DEFINED_TYPES_CIRCLE_BOUNDARY in compact(ok_lines[-1]),
          _brief(compact(ok_lines[:2])))
    two_numbers = [line for line in ok_lines
                   if str(CORPUS_EXPECTATIONS["derived_addresses"]) in line
                   and str(CORPUS_EXPECTATIONS["resolved_addresses"]) in line]
    check("форматтер печатает ДВА числа адресов раздельно (%d выведено из формы значения, %d "
          "подтверждено индексом) и объясняет, что разница — не потерянные строки (раздел 2.5)"
          % (CORPUS_EXPECTATIONS["derived_addresses"],
             CORPUS_EXPECTATIONS["resolved_addresses"]),
          bool(two_numbers) and any("не потерянные" in line.lower() for line in two_numbers),
          _brief(compact(two_numbers[:2])))
    qualifier_lines = [line for line in ok_lines
                       if str(CORPUS_EXPECTATIONS["qual_files"]) in line
                       and str(CORPUS_EXPECTATIONS["qual_blocks"]) in line]
    check("форматтер различает число СТРОК вида с квалификаторами (%d) и число БЛОКОВ "
          "квалификаторов (%d): строка одна на файл, девять файлов несут по два блока "
          "(раздел 2.2)" % (CORPUS_EXPECTATIONS["qual_files"],
                            CORPUS_EXPECTATIONS["qual_blocks"]),
          bool(qualifier_lines), _brief(compact(qualifier_lines[:2])))
    selfcheck = [line for line in ok_lines if "Самопроверок строки" in line]
    check("форматтер называет нуль самопроверок строки отдельной строкой: «самопроверок нет» и "
          "«самопроверок не считали» — разные ответы", bool(selfcheck),
          _brief(compact(selfcheck[:2])))
    defaults_lines = [str(line) for line in (format_defined_types_lines(defaults) or [])]
    index_warning = [line for line in defaults_lines if "Индекс состава" in line]
    ok_index_warning = [line for line in ok_lines if "Индекс состава" in line
                        and "не прочитан" in line]
    check("состояние индекса состава называется ответом: при недоступном индексе форматар "
          "печатает предупреждение, при доступном — не печатает (в отличие от V55, где "
          "недоступный индекс является отказом стадии)",
          bool(index_warning) or not ok_index_warning,
          _brief(compact(ok_index_warning[:2] + index_warning[:2])))
    kinds_block = [line for line in ok_lines + not_run
                   if "группы круга" in line or "группы не запрашивались" in line]
    check("блока «группы круга не запрашивались» в формате нет — групп `kinds` у входа нет "
          "(Q1 варианта A), а не пропущенный пункт формата",
          not kinds_block, _brief(compact(kinds_block[:3])))



# ── контур 8.1: отдельный вход группы — регистрация в реестре MCP ────────────────────────────
TOOL_DECORATOR_RE = re.compile(r"@mcp\.tool\([^)]*\)\s*(?:async\s+)?def\s+(\w+)\(")


def read_repo_text(rel_path):
    """Текст файла репозитория: реестр инструментов читается текстом, а не импортом.

    Импортировать `server_configurations_core.py` нельзя — импорт поднимает сервер MCP и его
    зависимости, а проверка обязана работать и без запущенного сервера. Состав реестра сторожит
    `tools/check_mcp_tool_wiring.py`, поэтому здесь сверяются два текста: объявление инструмента
    и запись в реестре ожиданий.
    """
    try:
        return (ROOT / rel_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def check_tool_registration():
    section("Контур 8.1 — отдельного входа `%s` в реестре MCP БОЛЬШЕ НЕТ (узел TOOL-DROP)" % TOOL_NAME)
    server_text = read_repo_text("server_configurations_core.py")
    declared = TOOL_DECORATOR_RE.findall(server_text)
    check(f"`{TOOL_NAME}` БОЛЬШЕ НЕ объявлен инструментом сервера "
          "`server_configurations_core.py` (снят узлом TOOL-DROP, 05.11.2026)",
          f"def {TOOL_NAME}(" not in server_text,
          _brief("def %s(: %s)"
                 % (TOOL_NAME, "ЕСТЬ" if f"def {TOOL_NAME}(" in server_text else "нет")))
    check("реестр инструментов ядра — %d после узла TOOL-DROP (было 16, снято тринадцать "
          "позиционных входов): состав читается декораторами сервера, а не списком в проверке"
          % EXPECTED_CORE_TOOL_COUNT,
          len(declared) == EXPECTED_CORE_TOOL_COUNT,
          "факт: %d — %s" % (len(declared), names(declared)))
    marker = "def %s(" % TOOL_NAME
    check("сигнатура и docstring отдельного входа в тексте сервера отсутствуют — вход снят "
          "целиком, а не спрятан в регистр",
          marker not in server_text, _brief(server_text[:160]))
    wiring_text = read_repo_text("tools/check_mcp_tool_wiring.py")
    check("`%s` числится снятым в `DELETED_TOOLS` файла `tools/check_mcp_tool_wiring.py` — "
          "состав реестра сторожит она, а не обещание подсказки продолжения" % TOOL_NAME,
          TOOL_NAME in wiring_text.split("DELETED_TOOLS = [")[1],
          "файл: %s" % (ROOT / "tools/check_mcp_tool_wiring.py"))
    loader_text = read_repo_text(LOADER_MODULE)
    check("отдельный вход реализован слоем `%s` (`load_defined_types`)" % LOADER_MODULE,
          "def load_defined_types(" in loader_text, "файл: %s" % (ROOT / LOADER_MODULE))
    pipeline_text = read_repo_text("src/configuration_loader.py")
    check("конвейер вызывает стадию `%s` тем же слоем — отдельный вход и конвейер не два разных "
          "разбора. Имя стадии в конвейере названо константой контракта, а не литералом: "
          "литерал имени стадии живёт одним местом — в `configuration_load_contract.py` (порядок "
          "`STAGES` сверяет контур 8)" % STAGE_DEFINED_TYPES,
          "load_defined_types(" in pipeline_text
          and re.search(r"\bSTAGE_DEFINED_TYPES\b", pipeline_text) is not None
          and "'%s'" % STAGE_DEFINED_TYPES not in pipeline_text
          and '"%s"' % STAGE_DEFINED_TYPES not in pipeline_text,
          "файл: %s" % (ROOT / "src/configuration_loader.py"))
    router_text = read_repo_text("src/config_load_router.py")
    check("карточка загрузки печатает раздел стадии (заголовок и форматтер читаются из "
          "контракта, а не пересказываются)",
          "DEFINED_TYPES_SECTION_HEADER" in router_text
          and "format_defined_types_lines" in router_text,
          "файл: %s" % (ROOT / "src/config_load_router.py"))
    plan_text = read_repo_text("docs/CONFIGURATION_DEFINED_TYPES_PLAN.md")
    check("план узла называет постоянной проверкой файл `tools/check_v58_defined_types.py` — "
          "проверка входит в состав узла, а не остаётся разовой меркой",
          "check_v58_defined_types.py" in plan_text,
          "файл: %s" % (ROOT / "docs/CONFIGURATION_DEFINED_TYPES_PLAN.md"))


# ── контур 9: корпус по четырём выгрузкам, чужие круги и соседние позиции ────────────────────
# Пары «мера прогона ↔ ключ эталона»: суммы по четырём выгрузкам сравниваются с разделами 1.1,
# 1.2, 1.4, 2.2, 2.3 и 2.5 плана, а не с числом, выведенным из самого прогона.
# Отдельно держатся величины, которые НЕ являются суммой по выгрузкам: множества адресов целей
# считаются объединением (адрес `Catalog.Организации` в двух выгрузках — один адрес), а имена и
# `uuid` вида по всей базе — их проверяет контур 7.
GLOBAL_CORPUS_KEYS = ("derived_addresses", "resolved_addresses", "distinct_names",
                      "distinct_uuids", "shared_names", "shared_uuids",
                      "duplicate_names_inside")
CORPUS_SCALAR_KEYS = tuple(key for key in CORPUS_EXPECTATIONS
                           if key not in GLOBAL_CORPUS_KEYS)
# Колонка состояний ↔ словарь перевода в меры корпуса: вывод ключа из имени состояния скрыл бы
# незнакомое состояние (правило C2, прецедент `USE_MEASURE_KEYS` проверки V57).
STATE_MEASURE_COLUMNS = (
    ("properties_state", PROPS_MEASURE_KEYS),
    ("internal_info_state", INTERNAL_MEASURE_KEYS),
    ("type_parse_state", STATE_MEASURE_KEYS),
    ("type_multiplicity", MULT_MEASURE_KEYS),
)


def accumulate_corpus(accum, db_rows, parsed, raw, index_info, header_list):
    """Суммы прогона по четырём выгрузкам — мерой прогона, а не числом плана."""
    accum["files"] += int(raw.get("files") or 0)
    accum["bytes"] += int(raw.get("bytes") or 0)
    accum["index_records"] += int(index_info.get("kind_rows") or 0)
    count = int(header_list.get("count") or 0)
    accum["header_names"] += count if count > 0 else 0
    accum["header_null"] += 1 if header_list.get("is_null") else 0
    accum["root_names"] += len(raw.get("root_names") or ())
    accum["db_rows"] += len(db_rows)
    accum["values"] += sum(len(as_json(row.get("types")) or []) for row in db_rows)
    prefixes = raw.get("prefixes") or Counter()
    accum["prefix_cfg"] += int(prefixes.get("cfg") or 0)
    accum["prefix_xs"] += int(prefixes.get("xs") or 0)
    accum["typeset"] += int(raw.get("typeset") or 0)
    accum["qual_files"] += int(raw.get("qual_files") or 0)
    accum["qual_blocks"] += int(raw.get("qual_blocks") or 0)
    accum["max_values_per_file"] = max(accum["max_values_per_file"],
                                       int(parsed.get("max_values_per_file") or 0))
    for state, corpus_key in RESOLVE_MEASURE_KEYS.items():
        accum[corpus_key] += int(parsed.get("resolve_" + state) or 0)
    for value, corpus_key in CLASS_MEASURE_KEYS.items():
        accum[corpus_key] += int((parsed.get("counts_by_class") or {}).get(value) or 0)
    for column, mapping in STATE_MEASURE_COLUMNS:
        counts = parsed.get("counts_by_" + column) or {}
        for state, corpus_key in mapping.items():
            accum[corpus_key] += int(counts.get(state) or 0)
    for state in CIRCLE_DISCREPANCIES:
        accum["circle_discrepancies"] += len(parsed.get(state) or [])
    accum["duplicate_names"] += len(parsed.get("duplicate_names") or [])
    accum["files_failed"] += int(parsed.get("files_failed") or 0)
    accum["row_problems"] += int(parsed.get("row_problems") or 0)
    accum["unknown_properties"] += sum(int(value) for value in
                                      (parsed.get("unknown_properties") or {}).values())
    accum["observations_total"] += sum(int(value) for value in
                                      (parsed.get("observations") or {}).values())


def foreign_state(cur):
    """Число строк чужих таблиц и витрин — одно число на объект, отсутствующий — None."""
    state = {}
    for table in tuple(FOREIGN_TABLES) + tuple(FOREIGN_VIEWS):
        try:
            state[table] = scalar(cur, "SELECT count(*) FROM " + table)
        except Exception:  # noqa: BLE001 — отсутствующую таблицу назовёт отдельная проверка
            cur.connection.rollback()
            state[table] = None
    return state


def foreign_type_classes(cur):
    """Классы значений блоков `<Type>` трёх чужих слоёв (V48/V50/V52).

    Узел V58 их не переразрешает (мера M5): класс `defined_type_ref` в этих слоях остаётся
    нулём, а тексты `cfg:DefinedType.*` — текстом с названным состоянием. Меняющееся число
    означает, что узел полез в чужой круг.
    """
    counts = Counter()
    for table in FOREIGN_TYPE_TABLES:
        try:
            for row in q(cur, "SELECT e->>'class' AS class FROM " + table
                            + " t, jsonb_array_elements(t.types) e"):
                counts[str(row.get("class"))] += 1
        except Exception:  # noqa: BLE001 — отсутствующий слой называется отдельной проверкой
            cur.connection.rollback()
            counts["missing:" + table] += 1
    return counts

def check_corpus(cur, accum, addresses, all_loaded):
    section("Контур 9 — суммы по четырём выгрузкам и чужие круги")
    if not all_loaded:
        skip("корпус: суммы по четырём выгрузкам",
             "прогнаны не все четыре выгрузки эталона (MinCfg / KomMag / BGU2 / BP3) — "
             "сравнивать суммы не с чем")
        return
    wanted = CORPUS_EXPECTATIONS
    wrong = ["%s: %s ≠ %s" % (key, accum.get(key, 0), wanted[key])
             for key in CORPUS_SCALAR_KEYS
             if int(accum.get(key) or 0) != int(wanted[key])]
    check("корпус: %d мер прогона (файлы, байты, записи индекса, перечень заголовка, перечень "
          "корня, строки таблицы, значения и их префиксы, классы, состояния, квалификаторы, "
          "разрешения целей) — эталонам разделов 1 и 2 плана" % len(CORPUS_SCALAR_KEYS),
          not wrong, "; ".join(wrong))
    derived, resolved = set(addresses.get("derived") or ()), set(addresses.get("resolved") or ())
    check("корпус: ДВА числа адресов целей — выведенных из ФОРМЫ значения %d и подтверждённых "
          "индексом %d (объединение множеств по четырём выгрузкам, а не сумма: один и тот же "
          "`Catalog.*` встречается в нескольких выгрузках); разница равна %d неразрешённым "
          "целям" % (wanted["derived_addresses"], wanted["resolved_addresses"],
                     wanted["unresolved"]),
          len(derived) == wanted["derived_addresses"]
          and len(resolved) == wanted["resolved_addresses"]
          and len(derived) - len(resolved) == wanted["unresolved"],
          "выведено: %d, подтверждено: %d" % (len(derived), len(resolved)))
    check("корпус: нули состояний и наблюдений названы нулями прогона, а не молчанием — "
          "`<v8:TypeSet>` (0), расхождений ног (0), повторных имён (0), отказов файлов (0), "
          "самопроверок строки (0), незнакомых свойств (0), наблюдений круга (0)",
          not any(accum.get(key) for key in ("typeset", "circle_discrepancies",
                                             "duplicate_names", "files_failed", "row_problems",
                                             "unknown_properties", "observations_total")),
          "ненулевые: %s" % names(sorted("%s=%s" % (key, accum.get(key))
                                         for key in ("typeset", "circle_discrepancies",
                                                    "duplicate_names", "files_failed",
                                                    "row_problems", "unknown_properties",
                                                    "observations_total")
                                         if accum.get(key))))
    kind_rows = scalar(cur, "SELECT count(*) FROM " + INDEX_TABLE
                       + " WHERE object_type = %s", (INDEX_OBJECT_TYPE,))
    check("корпус: записей вида `%s` во всех индексах состава — %d (мера M1: сравнение по "
          "всему кругу, а не по прогнанной выгрузке)"
          % (INDEX_OBJECT_TYPE, wanted["index_records"]),
          kind_rows == wanted["index_records"], "факт: %s" % kind_rows)
    header_lists = scalar(cur, "SELECT count(*) FROM configurations WHERE "
                               + HEADER_NAME_COLUMN + " IS NOT NULL")
    check("корпус: заголовков с заполненным перечнем `%s` — %d из %d: в отличие от V56/V57, "
          "где KomMag давал NULL потому, что вида у него не было, позиция 2.13 есть во всех "
          "четырёх выгрузках"
          % (HEADER_NAME_COLUMN, len(PLAN_EXPECTATIONS) - wanted["header_null"],
             len(PLAN_EXPECTATIONS)),
          header_lists == len(PLAN_EXPECTATIONS) - wanted["header_null"],
          "факт: %s" % header_lists)
    outside = scalar(cur, "SELECT count(*) FROM " + TABLE_NAME
                     + " d WHERE NOT exists(SELECT 1 FROM " + VIEW + " v WHERE v.id = d.id)")
    check("корпус: строк таблицы вне витрины текущего состояния — ноль по всей базе (цепь V19 "
          "и витрина даются одной миграцией — M4)", not outside, "вне витрин: %s" % outside)

def check_non_interference(before, after, classes_before, classes_after):
    """Снимок чужих таблиц, витрин и классов до прогона и после него — по одному числу."""
    section("Уборка за чужими кругами (мера M5: прогон не трогает соседние позиции)")
    objects = tuple(FOREIGN_TABLES) + tuple(FOREIGN_VIEWS)
    touched = [table for table in objects if before.get(table) != after.get(table)]
    check("чужих таблиц и витрин затронуто — %d (кроме фикстуры контура 10 прогон ничего не "
          "пишет)" % len(touched), not touched, "изменились: %s" % names(touched))
    missing = [table for table in objects if after.get(table) is None]
    check("отсутствующих чужих таблиц и витрин в базе — %d (названы, а не пропущены)"
          % len(missing), not missing, names(missing))
    if before.get("bsl_modules") is not None and after.get("bsl_modules") is not None:
        check("строк `bsl_modules` в прогоне не снято ни одной — узел V58 не трогает круг V47 "
              "(текстов модулей у вида нет, а дескрипторов файла модуля у вида нет вовсе — "
              "замер 1.2)", before["bsl_modules"] == after["bsl_modules"],
              "до: %s, после: %s" % (before["bsl_modules"], after["bsl_modules"]))
    view_wrong = ["%s: %s ≠ %s" % (view, after.get(view), expected)
                  for view, expected in sorted(FOREIGN_VIEW_EXPECTATIONS.items())
                  if after.get(view) != expected]
    check("числа витрин соседних позиций (2.11 — 765 опций и 10 063 целей, 2.12 — 14 параметров "
          "и 34 цели, 2.4/2.5/2.7 — роли, общие реквизиты, критерии отбора) прогон не меняет и "
          "в свой круг не берёт", not view_wrong, "; ".join(view_wrong))
    classes_wrong = [f"{value}: {classes_after.get(value, 0)} ≠ {expected}"
                     for value, expected in sorted(FOREIGN_TYPE_CLASS_EXPECTATIONS.items())
                     if int(classes_after.get(value) or 0) != int(expected)]
    total = sum(int(count) for value, count in classes_after.items()
                if not str(value).startswith("missing:"))
    check("классы значений блоков `<Type>` трёх чужих слоёв (V48/V50/V52) — измеренным "
          "эталонам: %s; всего значений %d. Класс `defined_type_ref` остаётся нулём: узел V58 "
          "не переразрешает ссылки `cfg:DefinedType.*` в чужих слоях и не меняет их словари "
          "(мера M5, граница названа карточкой инструмента)"
          % (", ".join("%s %d" % (value, count)
                       for value, count in sorted(FOREIGN_TYPE_CLASS_EXPECTATIONS.items())),
             FOREIGN_TYPE_VALUES_TOTAL),
          not classes_wrong and total == FOREIGN_TYPE_VALUES_TOTAL,
          "факт: %s (всего %d)" % (dict(classes_after), total))
    classes_drift = [
        f"{value}: {classes_before.get(value, 0)} → {classes_after.get(value, 0)}"
        for value in sorted(set(classes_before) | set(classes_after))
        if int(classes_before.get(value) or 0) != int(classes_after.get(value) or 0)]
    check("классов значений чужих слоёв сдвинулось за прогон — ноль (снимок до и после)",
          not classes_drift, "; ".join(classes_drift))

# ── контур 10: фикстуры границ (отсутствующий каталог, пустой каталог, чужой `uuid`) ─────────
# Случаи, которых корпус не даёт (Q9 варианта A, план раздела 1): каталога `DefinedTypes/` нет ни
# у одной из четырёх выгрузок, а чужой `uuid` заголовка корпусом не встречается. Фикстура
# вызывается слоем загрузки на временном каталоге — тем же кодом, что и прогоном, а не подделкой
# словаря состояний. Порядок фикстур держит восстановление: после снятия строк MinCfg круг
# обязательно возвращается загрузкой эталонного каталога, и возврат сверяется с базовым числом.
FIXTURE_DUMP = "MinCfg"


def dump_path(tag):
    """Абсолютный путь каталога выгрузки: фикстура вызывается слоем по тому же адресу, что и прогон."""
    return str(Path(DUMP_ROOT) / tag)


def fixture_circle(tmp_dir, dump, kind):
    """Круг фикстуры: `Configuration.xml` + `ConfigDumpInfo.xml` и круг вида по `kind`.

    `missing` — каталога вида нет вовсе, `empty` — каталог есть, файлов в нём нет, `full` — круг
    вида целиком. Индекс состава копируется всегда: отсутствующий индекс у этого входа состоянием
    `pending` не выражается (отличие от V55 названо слоем), а фикстура проверяет наблюдение
    `directory_missing`, а не состояние индекса.
    """
    source = Path(DUMP_ROOT) / dump
    (tmp_dir / "Configuration.xml").write_bytes((source / "Configuration.xml").read_bytes())
    (tmp_dir / "ConfigDumpInfo.xml").write_bytes(
        (source / "ConfigDumpInfo.xml").read_bytes())
    if kind == "empty":
        (tmp_dir / DIR_NAME).mkdir()
    elif kind == "full":
        shutil.copytree(source / DIR_NAME, tmp_dir / DIR_NAME)


def fixture_rows(cur, cfg_uuid):
    return int(scalar(cur, "SELECT count(*) FROM " + VIEW
                      + " WHERE configuration_uuid = %s::uuid", (cfg_uuid,)) or 0)


def check_boundary_fixtures(cur, baseline):
    section("Контур 10 — фикстуры границ: отсутствующий и пустой каталог, чужой `uuid`")
    if FIXTURE_DUMP not in baseline:
        skip("фикстуры границ",
             f"выгрузки {FIXTURE_DUMP} нет среди прогнанных — базового числа строк нет")
        return
    cfg_uuid = str(baseline[FIXTURE_DUMP]["uuid"])
    base_rows = int(baseline[FIXTURE_DUMP]["rows"])
    with tempfile.TemporaryDirectory(prefix="v58_fixture_") as tmp_name:
        tmp_dir = Path(tmp_name)
        fixture_circle(tmp_dir, FIXTURE_DUMP, "missing")
        missing = load_defined_types(str(tmp_dir))
        check("фикстура `отсутствующий каталог DefinedTypes/` — не отказ стадии, а ответ о "
              "выгрузке: `files_found` 0 и наблюдение `directory_missing` (Q9 варианта A: "
              "отсутствующий каталог является состоянием выгрузки, а не ошибкой разбора)",
              missing.get("files_found") == 0
              and (missing.get("observations") or {}).get("directory_missing") == 1
              and not missing.get("files_parsed")
              and missing.get("files_failed") == 0,
              "files_found: %s, observations: %s"
              % (missing.get("files_found"), _brief(missing.get("observations"))))
        rows_after_missing = fixture_rows(cur, cfg_uuid)
        check("фикстура `отсутствующий каталог` называет снятие прежних строк круга числом (%d) "
              "и не оставляет строк в таблице: «записано 0» отличается от «стадия не "
              "выполнялась»" % base_rows,
              int(missing.get("removed_previous") or 0) == base_rows
              and int(missing.get("defined_types_written") or 0) == 0
              and rows_after_missing == 0,
              "снято: %s, записано: %s, строк: %s"
              % (missing.get("removed_previous"), missing.get("defined_types_written"),
                 rows_after_missing))
        fixture_circle(tmp_dir, FIXTURE_DUMP, "empty")
        empty = load_defined_types(str(tmp_dir))
        check("фикстура `пустой каталог DefinedTypes/` отличается от отсутствующего: файлов "
              "ноль, наблюдения `directory_missing` НЕТ (каталог существует — выгрузка иная); "
              "оба состояния называются, а не сливаются в одну ноль-строку",
              empty.get("files_found") == 0
              and not (empty.get("observations") or {}).get("directory_missing"),
              "observations: %s" % _brief(empty.get("observations")))

    restored = load_defined_types(dump_path(FIXTURE_DUMP))
    rows_restored = fixture_rows(cur, cfg_uuid)
    check("круг возвращается повторной загрузкой эталонного каталога: записано %d, строк в "
          "витрине %d — базовому числу прогона (фикстура не оставила за собой снятых строк)"
          % (base_rows, base_rows),
          int(restored.get("defined_types_written") or 0) == base_rows
          and rows_restored == base_rows,
          "записано: %s, строк: %s, базовое число: %s"
          % (restored.get("defined_types_written"), rows_restored, base_rows))
    again = load_defined_types(dump_path(FIXTURE_DUMP))
    rows_again = fixture_rows(cur, cfg_uuid)
    check("повторной загрузкой круг снимается и пишется заново: снято %d и записано %d равны, "
          "строк в витрине по-прежнему %d, дублей нет; снятое названо числом (M7), история "
          "состояний не заводится (D8 — её даёт узел правки объекта, которого в схеме ещё нет)"
          % (base_rows, base_rows, base_rows),
          int(again.get("removed_previous") or 0) == base_rows
          and int(again.get("defined_types_written") or 0) == base_rows
          and rows_again == base_rows,
          "снято: %s, записано: %s, строк: %s"
          % (again.get("removed_previous"), again.get("defined_types_written"), rows_again))
    revisions = q(cur, "SELECT revision_no, count(*) AS cnt FROM " + TABLE_NAME
                  + " WHERE configuration_uuid = %s::uuid GROUP BY revision_no "
                    "ORDER BY revision_no", (cfg_uuid,))
    check("повтор не плодит вторую ревизию: строки круга остаются на ревизии 1 (`FIRST_REVISION`, "
          "`changed_by` — загрузка): цепь состояния одна на позицию, а не журнал загрузок",
          len(revisions) == 1 and int(revisions[0]["revision_no"]) == 1
          and int(revisions[0]["cnt"]) == base_rows, _brief(revisions))
    no_index = collect_defined_types(dump_path(FIXTURE_DUMP), index_rows=None)
    check("фикстура `разбор без индекса состава` отличается от `цели не разрешились`: круг "
          "разобран целиком (%d файлов), наблюдение `index_not_provided` названо, а записи "
          "значений остаются `unresolved` — «перечня не было» и «цели в перечне нет» являются "
          "разными ответами (правило C2, отличие от V55, где недоступный индекс есть отказ "
          "стадии)" % no_index.get("files_parsed"),
          no_index.get("success") is True
          and (no_index.get("observations") or {}).get("index_not_provided") == 1
          and int(no_index.get("resolve_unresolved") or 0) > 0
          and not no_index.get("index_only") and not no_index.get("file_only")
          and not no_index.get("uuid_mismatch"),
          "observations: %s, unresolved: %s" % (_brief(no_index.get("observations")),
                                               no_index.get("resolve_unresolved")))
    index_contract = parse_config_dump_info(
        str(Path(dump_path(FIXTURE_DUMP)) / "ConfigDumpInfo.xml"))
    with_index = collect_defined_types(
        dump_path(FIXTURE_DUMP), index_rows=index_contract.get("objects") or [])
    check("та же выгрузка с индексом состава даёт ДРУГОЙ ответ: наблюдения `index_not_provided` "
          "нет, неразрешённых целей %d — ноль для этой выгрузки (мера замера 2.5: шесть "
          "неразрешённых целей приходятся на BP3); сравнение двух прогонов одной выгрузки и "
          "есть смысл проверки, а не число" % int(with_index.get("resolve_unresolved") or 0),
          index_contract.get("success") is True
          and not (with_index.get("observations") or {}).get("index_not_provided")
          and with_index.get("success") is True
          and int(with_index.get("files_parsed") or 0) == int(no_index.get("files_parsed") or 0)
          and int(with_index.get("resolve_unresolved") or 0) == 0,
          "observations: %s, unresolved: %s" % (_brief(with_index.get("observations")),
                                               with_index.get("resolve_unresolved")))
    other_uuid = next((str(item["uuid"]) for name, item in baseline.items()
                       if name != FIXTURE_DUMP), None)
    if not other_uuid:
        skip("несовпадение `configuration_uuid`",
             "среди прогнанных выгрузок нет второй — чужого `uuid` сравнить не с чем")
        return
    with tempfile.TemporaryDirectory(prefix="v58_uuid_fixture_") as tmp_name:
        tmp_dir = Path(tmp_name)
        fixture_circle(tmp_dir, FIXTURE_DUMP, "full")
        mismatch = load_defined_types(str(tmp_dir), configuration_uuid=other_uuid)
    check("несовпадение `configuration_uuid` с `Configuration.xml` называется отказом, а не "
          "разрешается молча: строки свойств ушли бы чужой конфигурации (карточка инструмента "
          "говорит об этом прямо)",
          mismatch.get("success") is False
          and "uuid" in compact(str(mismatch.get("error") or "")
                                + str(mismatch.get("reason") or "")),
          "ответ: %s" % _brief(compact([mismatch.get("error"), mismatch.get("reason")])))
    rows_kept = fixture_rows(cur, cfg_uuid)
    check("отказ из-за чужого `uuid` не снимает и не пишет строк: круг %d остаётся нетронутым "
          "(отказ до записи, приём V12/V46…V57)" % base_rows, rows_kept == base_rows,
          "строк: %s" % rows_kept)


def run(cur, scope):
    headers = q(cur, "SELECT id, uuid::text AS uuid, name FROM configurations ORDER BY id")
    if not headers:
        FAILED.append("строк заголовков конфигураций в базе нет — сравнивать не с чем")
        print("FAIL строк заголовков конфигураций в базе нет — сравнивать не с чем")
        return
    before = foreign_state(cur)
    classes_before = foreign_type_classes(cur)
    accum = Counter()
    addresses = {"derived": set(), "resolved": set()}
    baseline = {}
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
        index_info = read_index_aggregates(cur, int(header["id"]))
        if not index_info.get("available"):
            skip(f"{tag}: сверка круга с индексом состава и разрешимость целей",
                 f"индекс состава недоступен: {index_info.get('reason')}")
        parsed = collect_defined_types(dump_dir, index_rows=index_info["rows"])
        check(f"{tag}: разбор круга завершён без отказа ({expect['files']} файлов)",
              parsed["success"] is True and parsed["files_found"] == expect["files"]
              and parsed["files_parsed"] == expect["db_rows"],
              f"success: {parsed['success']}, found: {parsed['files_found']}, parsed: "
              f"{parsed['files_parsed']}, failed: {_brief(parsed['files_failed'])}")
        check(f"{tag}: разбор круга завершён без самопроверок строки (`row_problems` ноль): "
              "состояние кратности выводится из числа записей `types`, а не из догадки разбора",
              int(parsed.get("row_problems") or 0) == 0, _brief(parsed.get("row_problems")))

        raw, db_rows, header_list = check_circle(cur, header, dump_dir, index_info, expect,
                                                 parsed, tag)
        parse_rows = {str(row["object_name"]): row for row in parsed["rows"]}
        compare_rows(parsed, db_rows, expect, tag)
        compare_raw_measures(raw, parse_rows, parsed, db_rows, expect, tag)
        check_form_dictionary(dump_dir, parse_rows, expect, tag)
        if index_info.get("available"):
            _, _, derived, resolved_addresses = check_resolution(cur, db_rows, parsed,
                                                                index_info, expect, tag)
            addresses["derived"].update(derived)
            addresses["resolved"].update(resolved_addresses)
        else:
            skip(f"{tag}: контур 6 — разрешимость целей индексом состава",
                 "индекс состава этой конфигурации в базе не загружен: разрешать не по чему")
        accumulate_corpus(accum, db_rows, parsed, raw, index_info, header_list)
        # `uuid` строки заголовка берётся из базы, а не из перечня плана: фикстура чужого
        # `uuid` обязана сравнивать настоящие идентификаторы двух конфигураций (M1).
        baseline[tag] = {"rows": len(db_rows), "uuid": str(header["uuid"])}
        loaded.add(tag)

    check_schema(cur)
    check_state_vocabulary_checks(cur)
    check_key_columns_match(cur)
    check_views(cur)
    check_contract()
    check_tool_registration()
    if scope == DEFAULT_SCOPE:
        check_corpus(cur, accum, addresses, loaded == set(PLAN_EXPECTATIONS))
    else:
        skip("корпус: суммы по четырём выгрузкам",
             f"охват `{scope}`: остальные выгрузки не прогнаны, сравнивать суммы не с чем "
             "(позиция 2.13 есть во всех четырёх выгрузках — её нули в эталон не входят)")
    check_non_interference(before, foreign_state(cur), classes_before,
                           foreign_type_classes(cur))
    check_boundary_fixtures(cur, baseline)


def main(argv):
    scope = str(argv[1]) if len(argv) > 1 else DEFAULT_SCOPE
    print("=== постоянная проверка узла V58 (определяемые типы, позиция 2.13) — "
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

