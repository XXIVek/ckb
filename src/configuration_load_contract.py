"""Закрытый контракт результата загрузки конфигурации (узел V45, 22.10.2026).

Конвейер первого слоя загрузки конфигурации: S1 разбор каталога → S2 заголовок (свойства V42 +
перечни имён состава V43 + индекс состава V33) → S3 модули предопределённых программ корня
(V44) → S4 содержимое дочерних объектов (с узла V46 — свойства подсистем, их ссылки `Content`,
свойства и дескрипторы общих модулей; по модели A–H узла V38 это часть групп B и E, а не
группа C — группой C в той модели названы модули предопределённых программ корня, закрытые V44;
тексты модулей — второй транзакцией по решению D7 и только по явной просьбе вызывающего)
→ S4b модули объектов конфигурации (с узла V47 — шесть слотов `Ext/` в `bsl_modules`,
`parent_type = 'configuration_objects'`; второй транзакцией после фиксации содержимого и БЕЗ
флага просьбы: конфигурация без модулей — такая же битая, как без свойств, решения Q4 и Q6
плана `docs/CONFIGURATION_OBJECT_MODULES_PLAN.md`; отдельного инструмента у стадии нет — Q4.1).
Каждая стадия
возвращает состояние выполнения и текст ошибки. Отказ стадии S3 или S4 не отменяет уже
записанный заголовок и называется в ответе отдельно (решения V45 и V46): конвейер
останавливают только отказы разбора каталога и записи заголовка (C5). Отказ стадии S4b —
исключение из этого правила: незавершённая группа объектов загруженной не называется
(решение Q4), поэтому ответ такой загрузки помечен `load_incomplete` и требует полной
перезагрузки `load_1c_catalog_tool(source_path=…, force=True)` (Q4.1). При этом уже
зафиксированные S1–S4 остаются зафиксированными — смысл границы D7 не отменяется.

Номер S4b, а не S5: S5 остаётся за планируемой стадией анализа (см. ниже), и занятый номер
заставил бы карточку стадий и план обогащения называть S5 реализованной.

Узел V48 (29.10.2026, решение Q5): между S4 и S4b стоит стадия S4c — свойства параметров
сеанса (`session_parameters`, позиция 2.3 нормативного списка плана
`docs/CONFIGURATION_SESSION_PARAMETERS_PLAN.md`). Стадия отдельная, а не третий вид S4,
потому что правило C3 требует своего ключа ответа (`session_parameters`), а не разбивки чужого
ключа по видам; порядок `STAGES` при этом повторяет порядок нормативного списка. Отказ стадии
S4c повторяет поведение S3/S4: он не отменяет записанный заголовок и называется
предупреждением; остановка конвейера по первой ошибке (решение Q8, вариант A) — шаг П8 того
же узла. Отдельная точка входа группы есть — `load_session_parameters_tool` (шаг П5 того же
узла, реестр сервера — шесть инструментов): повтор стадии не требует перезагрузки конфигурации.

Узел V49 (30.10.2026, позиция 2.4 нормативного списка) добавил стадию S4d — свойства ролей
(`roles`, `role_rights`, `role_restriction_templates`, `role_sources`), узел V50 (30.10.2026,
позиция 2.5) — стадию S4e — свойства общих реквизитов (`common_attributes`,
`common_attribute_targets`). Обе стоят между S4c и S4b потому, что порядок `STAGES` повторяет
порядок нормативного списка, а правило C3 требует своего ключа ответа (`roles`,
`common_attributes`): разбивать чужой ключ значило бы переименовывать контракт соседнего
узла. Отказ любой из них повторяет поведение S3/S4 (записанный заголовок не отменяется) и
останавливает конвейер по решению Q8 узла V48; отдельный вход группы у каждой свой —
`load_roles_tool` (шаг П5 узла V49) и `load_common_attributes_tool` (шаг П5 узла V50).
Групп запроса (`kinds`) у S4e нет: строка применения существует только через id строки
реквизита (Q1 узла V50, вариант A), поэтому частичная запись круга описывала бы состав,
которого в выгрузке нет.

Запланированная S5 (дополнение оператора 23.10.2026 — НЕ реализована, в `STAGES` её нет): анализ
загруженной конфигурации по уже сохранённым строкам БД, построение необходимых сниппетов по
объектам и при необходимости перекрёстных ссылок на документацию (`config_*`, контракт V17).
До согласования узла конвейер остаётся S1–S4; план зафиксирован разделом 16
`docs/CONFIGURATIONS_ENRICHMENT_PLAN.md`.

Зачем отдельный модуль. Оператор (22.10.2026) сформулировал требование к ответу так: сводные
таблицы ему не нужны — нужен либо итог «конфигурация загружена», либо содержание ошибки, на
которой загрузка остановилась. При этом машинная часть ответа обязана остаться полной: её
читают `tools/check_v32_zero_configuration.py`, `tools/check_v42_configuration_header.py` и
будущий `tools/check_v44_configuration_root_modules.py`. Значит список ключей обязан быть
закрытым и объявленным ОДНИМ местом: карточка, которая придумывает свои ключи, утверждает то,
чего загрузчик не говорил (именно так сломался форматёр V44 — он держал `counts`, `rows`,
`forms`, `TABLE_MODULES`, которых у контракта загрузчика нет).

Правила контракта:

* C1. Незаполненный ключ читается нулём: `0`, `[]`, `{}`, `False`. Ключей «нет» в ответе быть
  не может — отсутствие ключа каждый вызывающий разрешает `.get()`-ом по-своему, и два
  вызывающих разрешат по-разному.
* C2. Стадия, которая не выполнялась, имеет статус `not_run`, а не нули. «Модулей нет» и
  «модули не загружались» — разные факты (тот же контракт, что «манифеста нет» / «манифест
  пуст» у V19 и `===EMPTY` у V39/V42); нули без статуса стадий слили бы их в одно.
* C3. Ответ каждой стадии вложен в свой ключ (`root_modules`, `child_objects`) без
  переименования: standalone-инструмент `load_configuration_root_modules_tool` отдаёт свой
  плоский контракт, и тот же dict не может быть одновременно и плоским, и вложенным.
* C4. Исходы `already_exists` / `name_conflict` / `kind_conflict` — не ошибка стадии, а точка
  остановки диалога (правило R5); их печатает прежний `format_load_result`, этот модуль их не
  трогает.
* C5. Граница «ошибка» (решение оператора 22.10.2026 — «нам нужна конфигурация без ошибок»):
  останавливают конвейер только отказы — нет каталога или `Configuration.xml`, пустой/кривой
  uuid (R3), ошибка записи в БД, файл модуля не раскодирован (`undecoded`), запись индекса
  вне словаря (`index_unmatched`). Состояния конкретной выгрузки (`absent`, `empty_file`,
  `indexed_no_file`) и файлы `Ext/` вне четырёх модулей (`stray_ext_bsl` — модули объектов,
  второй слой) ошибкой НЕ считаются: замер V40 даёт 6/6/7/7 файлов предопределённых модулей
  на восемь выгрузок, то есть у части конфигураций части этих модулей нет вовсе, и строгое
  правило «только file» не пропустило бы ни одну полную выгрузку.
"""
from typing import Any, Dict, List, Tuple

from configuration_object_properties import (
    CONTENT_STATES,
    DECLARATION_STATES,
    KIND_COMMON_MODULES,
    KIND_SUBSYSTEMS,
)
from configuration_root_modules import (
    KINDS,
    MODULE_BY_KIND,
    REPORT_STATES,
    ROOT_MODULE_COUNT,
    STATE_ABSENT,
    TABLES,
    TITLE_BY_KIND,
)
# Узел V48 (стадия S4c, позиция 2.3 списка): словарь состояний и имя таблицы задаёт разбор
# вида (src/configuration_session_parameters.py), а не этот модуль — нулевой контракт стадии,
# сводка разбора и проверка узла (П6) обязаны называть один и тот же круг. Разбор ничего из
# этого контракта не импортирует, поэтому цикл здесь односторонний (тот же порядок, что у
# импорта CONTENT_STATES у V46 выше).
from configuration_session_parameters import (
    DIR_NAME as SESSION_PARAMETER_DIR,
    MULTIPLICITY_VALUES,
    OBJECT_KIND_TAG as SESSION_PARAMETER_META_TAG,
    RECORD_STATES,
    TABLE_NAME as SESSION_PARAMETER_TABLE,
    TYPE_CLASS_VALUES,
)
# Узел V49 (позиция 2.4 нормативного списка, узел Q2 вариант A): имена таблиц вида «роли»
# задаёт разбор (src/configuration_roles.py), а не этот модуль — тот же порядок, что у V48.
# Импорт нужен одному месту: назвать круг таблиц своей стадии, чтобы регистрация вида в круге
# версионности (`CONFIGURATION_VERSIONED_TABLES`) не добавила чужие таблицы к кругу S4.
# Разбор ничего из этого контракта не импортирует, цикл односторонний.
# Словари состояний импортируются с префиксом ROLE_: `CONTENT_STATES` и
# `DECLARATION_STATES` уже приходят из разбора V46 (строки подсистем и общих модулей), и
# переиспользовать их имена для ролей значило бы, что нулевой контракт стадии S4 заполняется
# словарём стадии S4d. Префикс — единственный способ назвать два разных словаря двумя
# именами; сами словари задаёт разбор, повторять их здесь нельзя.
from configuration_roles import (
    CONDITION_STATES as ROLE_CONDITION_STATES,
    CONTENT_STATES as ROLE_CONTENT_STATES,
    DECLARATION_STATES as ROLE_DECLARATION_STATES,
    DIR_NAME as ROLE_DIR,
    OBJECT_KIND_TAG as ROLE_META_TAG,
    RIGHTS_TABLE_NAME as ROLE_RIGHTS_TABLE,
    RIGHT_NAME_STATES as ROLE_RIGHT_NAME_STATES,
    RIGHT_VALUE_STATES as ROLE_RIGHT_VALUE_STATES,
    SOURCES_TABLE_NAME as ROLE_SOURCES_TABLE,
    TABLE_NAME as ROLE_TABLE,
    TARGET_RESOLVE_STATES as ROLE_TARGET_RESOLVE_STATES,
    TEMPLATES_TABLE_NAME as ROLE_TEMPLATES_TABLE,
)
# Узел V50 (позиция 2.5 нормативного списка, Q1 вариант A): имена таблиц вида «общие
# реквизиты» задаёт разбор (src/configuration_common_attributes.py), а не этот модуль — тот
# же порядок, что у V48 и V49. Импорт нужен одному месту: назвать круг таблиц своей стадии,
# чтобы регистрация вида в круге версионности (`CONFIGURATION_VERSIONED_TABLES`) не добавила
# чужие таблицы к кругу S4 — проба `_v46_p4_writer_probe.py` падает на `KeyError` ровно на
# той таблице, которую стадия не объявила (замер 30.10.2026: `KeyError: 'common_attributes'`
# сразу после шага П1 узла V50). Разбор ничего из этого контракта не импортирует, цикл
# односторонний.
from configuration_common_attributes import (
    CONTENT_STATES as CA_CONTENT_STATES,
    DIR_NAME as COMMON_ATTRIBUTES_DIR,
    ITEM_COND_STATES as CA_ITEM_COND_STATES,
    MULTIPLICITY_VALUES as CA_MULTIPLICITY_VALUES,
    OBJECT_KIND_TAG as COMMON_ATTRIBUTE_META_TAG,
    PROPERTIES_STATES as CA_PROPERTIES_STATES,
    RECORD_STATES as CA_TYPE_STATES,
    SEPARATION_BLOCKS as COMMON_ATTRIBUTE_SEPARATION_BLOCKS,
    SEPARATION_STATES as CA_SEPARATION_STATES,
    TABLE_NAME as COMMON_ATTRIBUTE_TABLE,
    TARGET_RESOLVE_STATES as CA_TARGET_RESOLVE_STATES,
    TARGETS_TABLE_NAME as COMMON_ATTRIBUTE_TARGETS_TABLE,
    TYPE_CLASS_VALUES as CA_TYPE_CLASS_VALUES,
    USE_STATES as CA_USE_STATES,
)
from configuration_exchange_plans import (
    AUTO_RECORD_STATES as EXCHANGE_PLAN_AUTO_RECORD_STATES,
    CHILD_STATES as EXCHANGE_PLAN_CHILD_STATES,
    CIRCLE_DISCREPANCIES as EXCHANGE_PLAN_CIRCLE_DISCREPANCIES,
    COMMANDS_TABLE_NAME as EXCHANGE_PLAN_COMMANDS_TABLE,
    CONTENT_TABLE_NAME as EXCHANGE_PLAN_CONTENT_TABLE,
    CONTENT_STATES as EXCHANGE_PLAN_CONTENT_STATES,
    DIR_NAME as EXCHANGE_PLAN_DIR,
    GROUP_ATTRIBUTES as EXCHANGE_PLAN_GROUP_ATTRIBUTES,
    GROUP_COMMANDS as EXCHANGE_PLAN_GROUP_COMMANDS,
    GROUP_CONTENT as EXCHANGE_PLAN_GROUP_CONTENT,
    GROUP_EXCHANGE_PLANS as EXCHANGE_PLAN_GROUP_EXCHANGE_PLANS,
    GROUP_FORMS as EXCHANGE_PLAN_GROUP_FORMS,
    GROUP_SLOTS as EXCHANGE_PLAN_GROUP_SLOTS,
    GROUP_TABULAR_SECTIONS as EXCHANGE_PLAN_GROUP_TABULAR_SECTIONS,
    GROUP_TEMPLATES as EXCHANGE_PLAN_GROUP_TEMPLATES,
    LOAD_GROUPS as EXCHANGE_PLAN_LOAD_GROUPS,
    OBJECT_KIND_TAG as EXCHANGE_PLAN_META_TAG,
    PROPERTIES_STATES as EXCHANGE_PLAN_PROPERTIES_STATES,
    SLOT_STATES as EXCHANGE_PLAN_SLOT_STATES,
    STANDARD_ATTRIBUTE_STATES as EXCHANGE_PLAN_STANDARD_ATTRIBUTE_STATES,
    TABLE_NAME as EXCHANGE_PLAN_TABLE,
    TARGET_STATES as EXCHANGE_PLAN_TARGET_STATES,
    group_tables as exchange_plan_group_tables,
)
# Узел V52 (критерии отбора, 01.11.2026, позиция 2.7 нормативного списка): имена таблиц
# вида, каталог, метка метаданных и закрытые словари состояний задаёт разбор
# (`src/configuration_filter_criteria.py`) — тот же порядок, что у V48, V49, V50 и V51:
# второго перечня таблиц или состояний в проекте нет, а форматёр и проверка узла читают эти
# же словари. Импорт нужен одному месту — назвать круг таблиц своей стадии, чтобы
# регистрация вида в круге версионности (`CONFIGURATION_VERSIONED_TABLES`, шаг П1) не
# добавила чужие таблицы к кругу S4: проба `_v46_p4_writer_probe.py` падает на `KeyError`
# ровно на той таблице, которую стадия не объявила (замер 30.10.2026). Разбор ничего из
# этого контракта не импортирует, цикл односторонний.
from configuration_filter_criteria import (
    CHILD_STATES as FILTER_CRITERIA_CHILD_STATES,
    CIRCLE_DISCREPANCIES as FILTER_CRITERIA_CIRCLE_DISCREPANCIES,
    CONTENT_STATES as FILTER_CRITERIA_CONTENT_STATES,
    CONTENT_TABLE_NAME as FILTER_CRITERIA_CONTENT_TABLE,
    DIR_NAME as FILTER_CRITERIA_DIR,
    FORM_REF_STATES as FILTER_CRITERIA_FORM_REF_STATES,
    MULTIPLICITY_VALUES as FILTER_CRITERIA_MULTIPLICITY_VALUES,
    OBJECT_KIND_TAG as FILTER_CRITERIA_META_TAG,
    PROPERTIES_STATES as FILTER_CRITERIA_PROPERTIES_STATES,
    TABLE_NAME as FILTER_CRITERIA_TABLE,
    TARGET_STATES as FILTER_CRITERIA_TARGET_STATES,
    TYPE_BLOCK_STATES as FILTER_CRITERIA_TYPE_STATES,
    TYPE_CLASS_VALUES as FILTER_CRITERIA_TYPE_CLASS_VALUES,
    TYPE_CONTAINERS as FILTER_CRITERIA_TYPE_CONTAINERS,
)
# Узел V53 (02.11.2026, позиция 2.8 списка): имена таблиц, каталог вида, метка метаданных и
# закрытые словари состояний приходят импортом из разбора
# (`src/configuration_event_subscriptions.py`) — второго перечня таблиц или состояний в проекте
# нет (тот же порядок, что V48…V52). Разбор ничего из контракта не импортирует, цикл
# односторонний.
from configuration_event_subscriptions import (
    CIRCLE_DISCREPANCIES as EVENT_SUBSCRIPTION_CIRCLE_DISCREPANCIES,
    DIR_NAME as EVENT_SUBSCRIPTIONS_DIR,
    EVENT_STATES as EVENT_SUBSCRIPTION_EVENT_STATES,
    HANDLER_STATES as EVENT_SUBSCRIPTION_HANDLER_STATES,
    OBJECT_KIND_TAG as EVENT_SUBSCRIPTION_META_TAG,
    PROPERTIES_STATES as EVENT_SUBSCRIPTION_PROPERTIES_STATES,
    SOURCE_CLASS_META_TYPES as EVENT_SUBSCRIPTION_SOURCE_CLASSES,
    SOURCE_STATES as EVENT_SUBSCRIPTION_SOURCE_STATES,
    SOURCE_TAGS as EVENT_SUBSCRIPTION_SOURCE_TAGS,
    SOURCES_TABLE_NAME as EVENT_SUBSCRIPTION_SOURCES_TABLE,
    TABLE_NAME as EVENT_SUBSCRIPTIONS_TABLE,
    TARGET_FORMS as EVENT_SUBSCRIPTION_TARGET_FORMS,
    TARGET_RESOLVE_STATES as EVENT_SUBSCRIPTION_TARGET_STATES,
)
# Узел V54 (03.11.2026, позиция 2.9 списка): имена двух таблиц, каталог вида, метка
# метаданных и закрытые словари состояний приходят импортом из разбора
# (`src/configuration_scheduled_jobs.py`) — второго перечня таблиц или состояний в проекте нет
# (тот же порядок, что V48…V53). Разбор ничего из контракта не импортирует, цикл
# односторонний. Словарей значений свойств здесь нет намеренно: значения свойств вида CHECK
# схемы не замыкаются (Q6, вариант A по прецеденту Q7 узла V50), поэтому контракт называет
# состояния, а не допустимые значения.
from configuration_scheduled_jobs import (
    ATTRIBUTE_VALUE_STATES as SCHEDULE_ATTRIBUTE_VALUE_STATES,
    CIRCLE_DISCREPANCIES as SCHEDULED_JOB_CIRCLE_DISCREPANCIES,
    DIR_NAME as SCHEDULED_JOBS_DIR,
    METHOD_DECLARED_STATES as SCHEDULED_JOB_METHOD_DECLARED_STATES,
    METHOD_STATES as SCHEDULED_JOB_METHOD_STATES,
    OBJECT_KIND_TAG as SCHEDULED_JOB_META_TAG,
    OBSERVATION_KINDS as SCHEDULED_JOB_OBSERVATION_KINDS,
    PROPERTIES_STATES as SCHEDULED_JOB_PROPERTIES_STATES,
    SCHEDULE_FILE_STATES as SCHEDULED_JOB_FILE_STATES,
    SCHEDULE_KINDS as SCHEDULE_RECORD_KINDS,
    SCHEDULE_STATES as SCHEDULED_JOB_STATES,
    SCHEDULES_TABLE_NAME as SCHEDULED_JOB_SCHEDULES_TABLE,
    SET_STATES as SCHEDULE_SET_STATES,
    TABLE_NAME as SCHEDULED_JOBS_TABLE,
    XML_PROPERTY_NAMES as XML_PROPERTY_NAMES_OF_JOB,
)
# Узел V55 (боты, шаг П4, 04.11.2026, позиция 2.10 нормативного списка): имя каталога вида,
# имя таблицы, метка метаданных и словари состояний приходят импортом из разбора
# (`src/configuration_bots.py`) — второго перечня таблиц или состояний в проекте нет (тот же
# порядок, что V48…V54). Разбор ничего из контракта не импортирует, цикл односторонний.
# Словарей ЗНАЧЕНИЙ свойств здесь нет намеренно: корпус словарь пяти тегов вида не замыкает
# (2 файла одной из четырёх выгрузок, XSD вида нет — замер 1.5 плана), поэтому контракт
# называет состояния (`properties_state` плюс перечень виновников), а не допустимые значения
# (Q1 — решение оператора, вариант A, по прецеденту Q7 узла V50).
from configuration_bots import (
    CIRCLE_DISCREPANCIES as BOTS_CIRCLE_DISCREPANCIES,
    COUNT_KEYS as BOTS_COUNT_KEYS,
    DIR_NAME as BOTS_DIR,
    INDEX_CHECK_STATES as BOTS_INDEX_CHECK_STATES,
    LT_STATES as BOTS_PICTURE_LT_STATES,
    MODULE_STATES as BOTS_MODULE_STATES,
    OBJECT_KIND_TAG as BOTS_META_TAG,
    OBSERVATION_KINDS as BOTS_OBSERVATION_KINDS,
    PICTURE_STATES as BOTS_PICTURE_STATES,
    PROPERTIES_STATES as BOTS_PROPERTIES_STATES,
    TABLE_NAME as BOTS_TABLE,
    TARGET_CLASS_VALUES as BOTS_PICTURE_TARGET_CLASSES,
    state_columns as bots_state_columns,
)
# Узел V56 (функциональные опции, шаг П5, 04.11.2026, позиция 2.11 нормативного списка):
# имена каталога и двух таблиц вида, метка метаданных, словари состояний и ключи сводки
# приходят импортом из разбора (`src/configuration_functional_options.py`) — второго перечня
# таблиц или состояний в проекте нет (тот же порядок, что V48…V55). Разбор ничего из
# контракта не импортирует, цикл односторонний.
# Словарей ЗНАЧЕНИЙ свойств здесь нет намеренно: CHECK на них в схеме нет по решению Q7
# (вариант A, прецедент узла V50) — единственное словарное значение вида является bool-флагом
# `PrivilegedGetMode`, его закрытость держит разбор (значение вне true/false остаётся текстом
# предупреждения, колонка — NULL, строка получает `unknown_value`), а не схема (замер 2.3).
from configuration_functional_options import (
    CIRCLE_DISCREPANCIES as FUNCTIONAL_OPTIONS_CIRCLE_DISCREPANCIES,
    CONTENT_TABLE_NAME as FUNCTIONAL_OPTION_CONTENT_TABLE,
    COUNT_KEYS as FUNCTIONAL_OPTIONS_COUNT_KEYS,
    COUNT_STATE_KEYS as FUNCTIONAL_OPTIONS_COUNT_STATE_KEYS,
    DIR_NAME as FUNCTIONAL_OPTIONS_DIR,
    OBJECT_KIND_TAG as FUNCTIONAL_OPTIONS_META_TAG,
    OBSERVATION_KINDS as FUNCTIONAL_OPTIONS_OBSERVATION_KINDS,
    STATE_VOCABULARIES as FUNCTIONAL_OPTIONS_STATE_VOCABULARIES,
    SUMMARY_KEYS as FUNCTIONAL_OPTIONS_SUMMARY_KEYS,
    TABLE_NAME as FUNCTIONAL_OPTIONS_TABLE,
    state_columns as functional_options_state_columns,
)
# Узел V57 (параметры функциональных опций, шаг П4–П5, 04.11.2026, позиция 2.12 нормативного
# списка): имена каталога и двух таблиц вида, метка метаданных, словари состояний и ключи сводки
# приходят импортом из разбора (`src/configuration_functional_options_parameters.py`) — второго
# перечня таблиц или состояний в проекте нет (тот же порядок, что V48…V56; шаг П4 держал только
# имена двух таблиц круга, потому что стадии ещё не было — шаг П5 добавляет остальное вместе с
# ключом ответа). Имена таблиц двух соседних видов начинаются одинаково —
# `functional_options`/`functional_option_content` у 2.11 и
# `functional_option_parameters`/`functional_option_parameter_targets` у 2.12, — поэтому круг
# держится точными именами таблиц, а не началом имени (раздел 1.2 плана V57: тот же риск,
# что с `FunctionalOption`/`FunctionalOptionsParameter` в индексе состава). Разбор ничего из
# контракта не импортирует, цикл односторонний.
# Словарей ЗНАЧЕНИЙ свойств здесь нет намеренно: CHECK на них в схеме нет по решению Q7
# (вариант A, прецедент узла V50) — словарь замкнут 14 файлами круга при отсутствии XSD
# (замер 1.5), и незнакомое значение остаётся значением с состоянием `unknown_value` и именем
# виновника в `unknown_property_names`, а не отказом записи.
from configuration_functional_options_parameters import (
    CIRCLE_DISCREPANCIES as FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_DISCREPANCIES,
    COUNT_KEYS as FUNCTIONAL_OPTIONS_PARAMETERS_COUNT_KEYS,
    COUNT_KEY_STATE_COLUMNS as FUNCTIONAL_OPTIONS_PARAMETERS_COUNT_STATE_KEYS,
    DIR_NAME as FUNCTIONAL_OPTIONS_PARAMETERS_DIR,
    MAX_TARGETS_KEY as FUNCTIONAL_OPTIONS_PARAMETERS_MAX_TARGETS_KEY,
    OBJECT_KIND_TAG as FUNCTIONAL_OPTIONS_PARAMETERS_META_TAG,
    OBSERVATION_KINDS as FUNCTIONAL_OPTIONS_PARAMETERS_OBSERVATION_KINDS,
    STATE_VOCABULARIES as FUNCTIONAL_OPTIONS_PARAMETERS_STATE_VOCABULARIES,
    SUMMARY_KEYS as FUNCTIONAL_OPTIONS_PARAMETERS_SUMMARY_KEYS,
    TABLE_NAME as FUNCTIONAL_OPTION_PARAMETERS_TABLE,
    TARGETS_TABLE_NAME as FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE,
    state_columns as functional_options_parameters_state_columns,
)
# Узел V58 (05.11.2026, позиция 2.13 нормативного списка — определяемые типы корня
# конфигурации, `defined_types`): имена каталога, таблицы и метки вида, словари состояний,
# ключи сводки и нулевой словарь сводки приходят импортом из слоя разбора
# (`src/configuration_defined_types.py`), а не переписываются здесь — тот же порядок, что у
# V48…V57. Таблица у вида ОДНА (Q1, вариант A — решение оператора от 05.11.2026 по
# прецеденту V48/V50/V52: блок `<Type>` хранится колонками строки вида), поэтому второй
# таблицы круга в импорте нет осознанно, а не потому, что её забыли. Разбор ничего из
# контракта не импортирует, цикл односторонний.
# Словарей ЗНАЧЕНИЙ свойств здесь нет намеренно: CHECK на них в схеме нет по решению Q7
# (вариант A, прецедент узла V50) — словарь четырёх тегов замкнут 820 файлами круга при
# отсутствии XSD (замер 1.5), и незнакомое значение остаётся значением с состоянием
# `unknown_value` и именем виновника в `unknown_property_names`, а не отказом записи.
from configuration_defined_types import (
    CIRCLE_DISCREPANCIES as DEFINED_TYPES_CIRCLE_DISCREPANCIES,
    COUNT_KEYS as DEFINED_TYPES_COUNT_KEYS,
    DIR_NAME as DEFINED_TYPES_DIR,
    OBJECT_KIND_TAG as DEFINED_TYPES_META_TAG,
    OBSERVATION_KINDS as DEFINED_TYPES_OBSERVATION_KINDS,
    RESOLVE_COUNT_KEYS as DEFINED_TYPES_RESOLVE_COUNT_KEYS,
    RESOLVE_STATES as DEFINED_TYPES_RESOLVE_STATES,
    STATE_VOCABULARIES as DEFINED_TYPES_STATE_VOCABULARIES,
    SUMMARY_KEYS as DEFINED_TYPES_SUMMARY_KEYS,
    TABLE_NAME as DEFINED_TYPES_TABLE,
    TYPE_CLASS_VALUES as DEFINED_TYPES_VALUE_CLASS_VALUES,
    zero_counts as defined_types_zero_counts,
)
from current_revision import CONFIGURATION_VERSIONED_TABLES

# ── стадии конвейера: один перечень на контракт, карточку и проверку ───────────────
STAGE_LAYOUT = "s1_layout"
STAGE_HEADER = "s2_header"
STAGE_ROOT_MODULES = "s3_root_modules"
STAGE_CHILD_OBJECTS = "s4_child_objects"
# Узел V48 (29.10.2026, решение Q5): свойства параметров сеанса — отдельная стадия, а не
# третий вид стадии S4. Порядок `STAGES` повторяет порядок нормативного списка
# (docs/CONFIGURATION_SESSION_PARAMETERS_PLAN.md, раздел 2.9): позиция 2.3 идёт сразу за
# 2.1–2.2, то есть между S4 и S4b; существующие стадии не перенумеровываются. Отдельная
# стадия нужна потому, что правило C3 требует своего ключа ответа: разбивать содержимое
# чужого ключа `child_objects` по видам значило бы переименовывать контракт V46.
STAGE_SESSION_PARAMETERS = "s4c_session_parameters"
# Узел V49 (2026-10-30, позиция 2.4 нормативного списка): свойства ролей — отдельная стадия
# по той же причине, что и S4c узла V48: правило C3 требует своего ключа ответа `roles`,
# а разбивать чужой ключ значило бы переименовывать контракт соседнего узла. Порядок
# `STAGES` повторяет порядок нормативного списка (docs/CONFIGURATION_ROLES_PLAN.md,
# раздел 5): позиция 2.4 идёт сразу за 2.3, то есть между S4c и S4b; существующие стадии
# не перенумеровываются, номер S5 по-прежнему зарезервирован за планируемой стадией анализа.
STAGE_ROLES = "s4d_roles"
# Узел V50 (30.10.2026, позиция 2.5 нормативного списка): свойства общих реквизитов —
# отдельная стадия по той же причине, что S4c (V48) и S4d (V49): правило C3 требует своего
# ключа ответа `common_attributes`, а разбивать чужой ключ значило бы переименовывать
# контракт соседнего узла. Порядок `STAGES` повторяет порядок нормативного списка
# (docs/CONFIGURATION_COMMON_ATTRIBUTES_PLAN.md, раздел 5): позиция 2.5 идёт сразу за 2.4,
# то есть между S4d и S4b; существующие стадии не перенумеровываются, номер S5 по-прежнему
# зарезервирован за планируемой стадией анализа. Групп запроса (`kinds`) у вида нет: круг —
# строка реквизита и строки её применения как единое целое (Q1, вариант A), отдельный вход
# дозагружает весь круг сразу (Q10, вариант A: порог раздельной дозыгрузки не замерен).
STAGE_COMMON_ATTRIBUTES = "s4e_common_attributes"
# Узел V51 (31.10.2026, позиция 2.6 нормативного списка): свойства планов обмена —
# отдельная стадия по той же причине, что S4c (V48), S4d (V49) и S4e (V50): правило C3
# требует своего ключа ответа `exchange_plans`, а разбивать чужой ключ значило бы
# переименовывать контракт соседнего узла. Номер S4f, а не S5: S5 остаётся за планируемой
# стадией анализа.
# В `STAGES` ниже стадия внесена шагом П5 (31.10.2026): слой `load_exchange_plans`
# (src/configuration_exchange_plans_loader.py) и точка входа `load_exchange_plans_tool`
# существуют, поэтому конвейер обязан вызывать её в порядке нормативного списка
# (docs/CONFIGURATION_EXCHANGE_PLANS_PLAN.md, раздел 7). Раздел `===TOOLS===` матрицы
# `goal-and-stages` и `EXPECTED_TOOLS` проверки `tools/check_mcp_tool_wiring.py` обновляются
# тем же шагом: реестр становится девятью инструментами. Круг
# таблиц стадии при этом объявлен уже сейчас (`EXCHANGE_PLAN_TABLES`): версионная таблица
# без объявленного круга загрузки означала бы, что чужая стадия её снимает (дефект,
# названный узлами V49 и V50).
STAGE_EXCHANGE_PLANS = "s4f_exchange_plans"
# Узел V52 (01.11.2026, позиция 2.7 нормативного списка): свойства критериев отбора —
# отдельная стадия по той же причине, что S4c (V48), S4d (V49), S4e (V50) и S4f (V51):
# правило C3 требует своего ключа ответа `filter_criteria`, а разбивать чужой ключ значило
# бы переименовывать контракт соседнего узла. Номер S4g, а не S5: S5 остаётся за
# планируемой стадией анализа.
# В `STAGES` ниже стадия вносится шагом П5 (позиция 2.7 идёт сразу за 2.6, то есть между
# S4f и S4b — порядок нормативного списка держит `STAGES`, а не порядок номеров): слой
# `load_filter_criteria` (src/configuration_filter_criteria_loader.py) появляется шагом П4
# этим же, а точка входа `load_filter_criteria_tool` — шагом П5. Круг таблиц стадии
# (`FILTER_CRITERIA_TABLES`) объявлен уже на П4: версионная таблица без объявленного круга
# загрузки означала бы, что чужая стадия её снимает (дефект, названный узлами V49, V50, V51).
# Групп запроса (`kinds`) у вида НЕТ — это решение, а не упущение (Q5, вариант A): строка
# условия существует только через id строки вида (Q1, вариант A), а цена круга не даёт
# порога, при котором раздельная дозагрузка была бы оправдана (замер 1.4: 1 219 целей на
# весь круг, максимум 727 в одном файле) — отдельный вход дозагружает весь круг сразу.
STAGE_FILTER_CRITERIA = "s4g_filter_criteria"
# Узел V53 (02.11.2026, позиция 2.8 нормативного списка): свойства подписок на события —
# отдельная стадия по той же причине, что S4c (V48), S4d (V49), S4e (V50), S4f (V51) и S4g
# (V52): правило C3 требует своего ключа ответа `event_subscriptions`, а разбивать чужой ключ
# значило бы переименовывать контракт соседнего узла. Номер S4h, а не S5: S5 остаётся за
# планируемой стадией анализа. В `STAGES` ниже стадия вносится шагом П5 (позиция 2.8 идёт
# сразу за 2.7, то есть между S4g и S4b — порядок нормативного списка держит `STAGES`, а не
# порядок номеров): слой `load_event_subscriptions`
# (src/configuration_event_subscriptions_loader.py) появляется шагом П4 этим же, а точка входа
# `load_event_subscriptions_tool` — шагом П5. Круг таблиц стадии
# (`EVENT_SUBSCRIPTIONS_TABLES`) объявлен уже на П4: версионная таблица без объявленного круга
# загрузки означала бы, что чужая стадия её снимает (дефект, названный узлами V49, V50, V51,
# V52). Групп запроса (`kinds`) у вида НЕТ — это решение, а не упущение (Q8, вариант A по
# прецеденту Q5 узла V52): строка источника существует только через id строки вида (Q4,
# вариант A), а цена круга не даёт порога, при котором раздельная дозагрузка была бы
# оправдана (замер 2.2: 25 100 записей блока `<Source>` на весь круг, максимум 789 в одном
# файле) — отдельный вход дозагружает весь круг сразу.
STAGE_EVENT_SUBSCRIPTIONS = "s4h_event_subscriptions"
# Узел V54 (03.11.2026, позиция 2.9 нормативного списка): свойства регламентных заданий —
# отдельная стадия по той же причине, что S4c (V48), S4d (V49), S4e (V50), S4f (V51), S4g
# (V52) и S4h (V53): правило C3 требует своего ключа ответа `scheduled_jobs`, а разбивать
# чужой ключ значило бы переименовывать контракт соседнего узла. Номер S4i, а не S5: S5
# остаётся за планируемой стадией анализа. В `STAGES` ниже стадия вносится шагом П5 (позиция
# 2.9 идёт сразу за 2.8, то есть между S4h и S4b — порядок нормативного списка держает
# `STAGES`, а не порядок номеров): слой `load_scheduled_jobs`
# (src/configuration_scheduled_jobs_loader.py) появляется шагом П4 этим же, а точка входа
# `load_scheduled_jobs_tool` — шагом П5. Круг таблиц стадии (`SCHEDULED_JOBS_TABLES`) и его
# включение в `FOREIGN_STAGE_TABLES` объявлены уже на П4: версионная таблица без объявленного
# круга загрузки означала бы, что чужая стадия S4 её снимает (дефект, названный узлами
# V49…V53). Групп запроса (`kinds`) у вида НЕТ — это решение, а не упущение (Q5, вариант A по
# прецеденту Q8 узла V53 и Q10 узла V50): запись расписания существует только через id
# строки вида (Q2, вариант A), а порога цены, при котором круг стоило бы резать, замер 1.1/2.2
# не дал (346 файлов регистрации и 313 записей расписания на весь круг, максимум 3 записи в
# одном файле) — отдельный вход дозагружает весь круг сразу.
STAGE_SCHEDULED_JOBS = "s4i_scheduled_jobs"
# Узел V55 (04.11.2026, позиция 2.10 нормативного списка): свойства ботов — отдельная
# стадия по той же причине, что S4c (V48), S4d (V49), S4e (V50), S4f (V51), S4g (V52),
# S4h (V53) и S4i (V54): правило C3 требует своего ключа ответа `bots`, а разбивать чужой
# ключ значило бы переименовывать контракт соседнего узла. Номер S4j, а не S5: S5 остаётся
# за планируемой стадией анализа. В `STAGES` ниже стадия вносится шагом П5 (позиция 2.10
# идёт сразу за 2.9, то есть между S4i и S4b — порядок нормативного списка держает `STAGES`,
# а не порядок номеров): слой `load_bots` (src/configuration_bots_loader.py) появляется
# шагом П4 этим же, а точка входа `load_bots_tool` — шагом П5. Круг таблиц стадии
# (`BOTS_TABLES`) и его включение в `FOREIGN_STAGE_TABLES` объявлены уже на П4: версионная
# таблица без объявленного круга загрузки означала бы, что чужая стадия S4 её снимает
# (дефект, названный узлами V49…V54). Групп запроса (`kinds`) у вида НЕТ — это решение, а не
# упущение (Q5, вариант A по прецеденту Q8 узла V53, Q10 узла V50 и Q5 узла V54): строка
# вида едина, её состояние свойств, состояние ссылки и состояние модуля неотделимы от неё, а
# порога цены, при котором круг стоило бы резать, замер 1.1 не дал — весь круг четырёх
# выгрузок это 2 файла регистрации одной конфигурации (MinCfg; KomMag, BGU2 и BP3 вида не
# имеют ни файлами, ни строками индекса).
STAGE_BOTS = "s4j_bots"
# Узел V56 (04.11.2026, позиция 2.11 нормативного списка): свойства функциональных опций —
# отдельная стадия по той же причине, что S4c (V48), S4d (V49), S4e (V50), S4f (V51),
# S4g (V52), S4h (V53), S4i (V54) и S4j (V55): правило C3 требует своего ключа ответа
# `functional_options`, а разбивать чужой ключ значило бы переименовывать контракт
# соседнего узла. Номер S4k, а не S5: S5 остаётся за планируемой стадией анализа. В
# `STAGES` ниже стадия вносится шагом П5 (позиция 2.11 идёт сразу за 2.10, то есть между
# S4j и S4b — порядок нормативного списка держит `STAGES`, а не порядок номеров): слой
# `load_functional_options` (src/configuration_functional_options_loader.py) и точка входа
# `load_functional_options_tool` появляются этим же шагом. Круг таблиц стадии
# (`FUNCTIONAL_OPTIONS_TABLES`) и его включение в `FOREIGN_STAGE_TABLES` объявлены этим же
# шагом: версионная таблица без объявленного круга загрузки означала бы, что чужая стадия S4
# её снимает (дефект, названный узлами V49…V55).
# Групп запроса (`kinds`) у вида НЕТ — это решение, а не упущение (Q4 раздела 6 плана V56,
# вариант A по прецеденту Q10 узла V50, Q5 узлов V52, V54 и V55): строка применения
# существует только через id строки опции (Q1, вариант A), поэтому частичная запись круга
# описывала бы состав, которого в выгрузке нет, а порога цены, при котором круг стоило бы
# резать, замер 1.4 не дал (2 467 629 байта файлов регистрации на весь круг, прочего
# содержимого — 0 байт; 765 строк вида и 10 063 строки применения).
STAGE_FUNCTIONAL_OPTIONS = "s4k_functional_options"
# Узел V57 (04.11.2026, позиция 2.12 нормативного списка): свойства параметров функциональных
# опций — отдельная стадия по той же причине, что S4c (V48), S4d (V49), S4e (V50), S4f (V51),
# S4g (V52), S4h (V53), S4i (V54), S4j (V55) и S4k (V56): правило C3 требует своего ключа
# ответа `functional_options_parameters`, а разбивать чужой ключ `functional_options` значило
# бы переименовывать контракт соседнего узла. Номер S4l, а не S5: S5 остаётся за планируемой
# стадией анализа. В `STAGES` ниже стадия вносится этим же шагом П5 (позиция 2.12 идёт сразу
# за 2.11, то есть между S4k и S4b — порядок нормативного списка держит `STAGES`, а не порядок
# номеров): слой `load_functional_options_parameters`
# (src/configuration_functional_options_parameters_loader.py) и точка входа
# `load_functional_options_parameters_tool` появляются этим же шагом. Круг таблиц стадии
# (`FUNCTIONAL_OPTION_PARAMETERS_TABLES`) и его включение в `FOREIGN_STAGE_TABLES` объявлены
# шагом П4: версионная таблица без объявленного круга загрузки означала бы, что чужая стадия S4
# её снимает (дефект, названный узлами V49…V56).
# Групп запроса (`kinds`) у вида НЕТ — это решение, а не упущение (Q5 раздела 6 плана V57,
# вариант A по прецеденту Q10 узла V50, Q5 узлов V52, V54, V55, V56 и Q8 узла V53): строка
# применения существует только через id строки параметра (Q1, вариант A), поэтому частичная
# запись круга описывала бы состав, которого в выгрузке нет, а порога цены, при котором круг
# стоило бы резать, замер 1.4 не дал (весь круг четырёх выгрузок — 14 файлов регистрации и 34
# цели применения, 0 байт прочего содержимого).
STAGE_FUNCTIONAL_OPTIONS_PARAMETERS = "s4l_functional_options_parameters"
# Узел V58 (05.11.2026, позиция 2.13 нормативного списка — определяемые типы корня
# конфигурации, план docs/CONFIGURATION_DEFINED_TYPES_PLAN.md): свойства вида — отдельная
# стадия S4m, а не семнадцатый вид стадии S4. Причина та же, что у V48…V57 (правило C3):
# ответ каждой стадии обязан лежать в своём ключе `defined_types`, а разбивать чужой ключ
# значило бы переименовывать контракт соседнего узла. 2.13 идёт сразу за 2.12, поэтому
# литера `s4m` стоит между S4l и S4b — порядок нормативного списка держит `STAGES`, а не
# порядок литер (прецеденты V52…V57). S4b остаётся последней стадией, потому что является
# второй транзакцией загрузки (Q6 узла V46), а не позицией списка.
# Групп запроса (`kinds`) у вида НЕТ — это решение, а не упущение (Q1 раздела 5 плана V58,
# вариант A по прецеденту Q10 узла V50, Q5 узлов V52, V54, V55, V56, V57 и Q8 узла V53):
# блок `<Type>` является колонками строки вида (Q1), поэтому частичная запись круга
# описывала бы состав, которого в выгрузке нет, а порога цены, при котором круг стоило бы
# резать, замер 2.2 не дал (весь круг четырёх выгрузок — 820 файлов регистрации и 17 544
# значения, прочего содержимого ноль).
STAGE_DEFINED_TYPES = "s4m_defined_types"
# Узел V47 (28.10.2026): тексты модулей объектов конфигурации. Номер S4b, а не S5:
# S5 остаётся за планируемой стадией анализа (дополнение оператора 23.10.2026), которой
# в `STAGES` нет. Стадия идёт сразу за S4 и является второй транзакцией загрузки (Q6,
# граница D7) — в отличие от S3/S4 её отказ останавливает загрузку (Q4), а повторить её
# отдельным инструментом нельзя (Q4.1).
STAGE_OBJECT_MODULES = "s4b_object_modules"

STAGES: Tuple[Tuple[str, str], ...] = (
    (STAGE_LAYOUT, "Разбор каталога выгрузки (Configuration.xml)"),
    (STAGE_HEADER, "Запись заголовка: свойства, перечни состава, индекс состава"),
    (STAGE_ROOT_MODULES, "Модули предопределённых программ корня"),
    (STAGE_CHILD_OBJECTS, "Содержимое дочерних объектов конфигурации"),
    (STAGE_SESSION_PARAMETERS, "Свойства параметров сеанса (SessionParameters, позиция 2.3)"),
    (STAGE_ROLES, "Свойства ролей конфигурации (Roles, позиция 2.4)"),
    (STAGE_COMMON_ATTRIBUTES,
     "Свойства общих реквизитов (CommonAttributes, позиция 2.5)"),
    # Узел V51 (позиция 2.6 списка) — порядок нормативного списка соблюдён: 2.6 идёт сразу
    # за 2.5, а S4b (модули объектов) остаётся последней стадией, потому что является второй
    # транзакцией загрузки (Q6 узла V46), а не позицией списка.
    (STAGE_EXCHANGE_PLANS,
     "Свойства планов обмена (ExchangePlans, позиция 2.6)"),
    # Узел V52 (позиция 2.7 списка, решение Q10 вариант A): 2.7 идёт сразу за 2.6, литера
    # `s4g` в коде свободна — перенумерации прежних стадий нет. S4b остаётся последней,
    # потому что является второй транзакцией загрузки (Q6 узла V46), а не позицией списка.
    (STAGE_FILTER_CRITERIA,
     "Свойства критериев отбора (FilterCriteria, позиция 2.7)"),
    # Узел V53 (позиция 2.8 списка, решение Q8 вариант A): 2.8 идёт сразу за 2.7, литера
    # `s4h` в коде свободна — перенумерации прежних стадий нет. S4b остаётся последней,
    # потому что является второй транзакцией загрузки (Q6 узла V46), а не позицией списка.
    (STAGE_EVENT_SUBSCRIPTIONS,
     "Свойства подписок на события (EventSubscriptions, позиция 2.8)"),
    # Узел V54 (позиция 2.9 списка, решение Q5 вариант A): 2.9 идёт сразу за 2.8, литера
    # `s4i` в коде свободна — перенумерации прежних стадий нет. S4b остаётся последней,
    # потому что является второй транзакцией загрузки (Q6 узла V46), а не позицией списка.
    (STAGE_SCHEDULED_JOBS,
     "Свойства регламентных заданий (ScheduledJobs, позиция 2.9)"),
    # Узел V55 (позиция 2.10 списка, решение Q5 вариант A): 2.10 идёт сразу за 2.9, литера
    # `s4j` в коде свободна — перенумерации прежних стадий нет. S4b остаётся последней,
    # потому что является второй транзакцией загрузки (Q6 узла V46), а не позицией списка.
    (STAGE_BOTS,
     "Свойства ботов конфигурации (Bots, позиция 2.10)"),
    # Узел V56 (позиция 2.11 списка, решение Q4 вариант A): 2.11 идёт сразу за 2.10, литера
    # `s4k` в коде свободна — перенумерации прежних стадий нет. S4b остаётся последней,
    # потому что является второй транзакцией загрузки (Q6 узла V46), а не позицией списка.
    (STAGE_FUNCTIONAL_OPTIONS,
     "Свойства функциональных опций (FunctionalOptions, позиция 2.11)"),
    # Узел V57 (позиция 2.12 списка, решение Q5 вариант A): 2.12 идёт сразу за 2.11, литера
    # `s4l` в коде свободна — перенумерации прежних стадий нет. S4b остаётся последней,
    # потому что является второй транзакцией загрузки (Q6 узла V46), а не позицией списка.
    (STAGE_FUNCTIONAL_OPTIONS_PARAMETERS,
     "Свойства параметров функциональных опций (FunctionalOptionsParameters, позиция 2.12)"),
    # Узел V58 (позиция 2.13 списка, решение Q1 вариант A): 2.13 идёт сразу за 2.12, литера
    # `s4m` в коде свободна — перенумерации прежних стадий нет. S4b остаётся последней,
    # потому что является второй транзакцией загрузки (Q6 узла V46), а не позицией списка.
    (STAGE_DEFINED_TYPES,
     "Свойства определяемых типов (DefinedTypes, позиция 2.13)"),
    (STAGE_OBJECT_MODULES, "Модули объектов конфигурации (тексты Ext/, вторая транзакция)"),
)

STATUS_NOT_RUN = "not_run"
STATUS_OK = "ok"
STATUS_SKIPPED = "skipped"
STATUS_ERROR = "error"

# ── узел V48 (стадия S4c, позиция 2.3 нормативного списка) ─────────────────────────
# Заголовок раздела, подсказка о повторе и граница круга объявлены ДО `CHILD_NOT_IMPLEMENTED`:
# текст незакрытой части ссылается на раздел, где читается отказ стадии, и повторять этот
# заголовок текстом значило бы держать два написания одного заголовка — по той же причине,
# по которой у V45 и V46 форматёр раздела один на карточку и на отдельный инструмент.
# Имя таблицы и словари состояний приходят импортом из разбора вида (см. начало модуля) —
# второго перечня таблицы или состояний в проекте нет.
SESSION_PARAMETERS_SECTION_HEADER = "СВОЙСТВА ПАРАМЕТРОВ СЕАНСА (узел V48, позиция 2.3)"

# Что обязан сказать ответ о повторе стадии. Отдельная точка входа группы —
# `load_session_parameters_tool` (шаг П5 узла, тот же слой, что стадия — прецедент V44/V46);
# ответ обязан называть, чем именно повтор делать можно, а не обещать инструмент, которого в
# реестре нет: строка меняется одним местом, когда состав реестра меняется (проверка
# `tools/check_mcp_tool_wiring.py`).
SESSION_PARAMETERS_REPEAT_HINT = (
    "Повторить стадию можно отдельным входом группы "
    "load_session_parameters_tool(source_path=…) без перезагрузки конфигурации "
    "(узел V48, шаг П5) либо полной перезагрузкой "
    "load_1c_catalog_tool(source_path=…, force=True)"
)

# Граница круга называется и при успехе: «строки свойств записаны» не равно «о виде больше
# ничего нет». Формулировка держится замеров раздела 2 плана — без неё пустой тип читался бы
# как «типа нет в выгрузке», а не как «разбор его не распознал».
SESSION_PARAMETERS_BOUNDARY = (
    f"круг узла — файлы регистрации вида {SESSION_PARAMETER_META_TAG} из каталога "
    f"{SESSION_PARAMETER_DIR}/ (позиция 2.3 списка): сохраняются имя, синоним, комментарий "
    "и блок Type в закрытом словаре записей (`types`, `type_qualifiers`); подкаталогов, "
    "форм, макетов и модулей у вида нет (замер 2.2), поэтому строка одна на файл. "
    "DefinedTypes в выгрузке нет (замер 2.4.4): значение `cfg:DefinedType.*` остаётся "
    "записью класса `defined_type_ref` без ключей цели — узла загрузки определённых типов "
    "нет. Строка в таблице есть только там, где файл разобран: `absent`, `partial` и "
    "`unknown_form` называются ответом стадии, а не строкой с пустым типом — ограничение "
    "`type_parse_state = 'parsed' ⇒ types <> '[]'` (узел П1) не даёт пустому типу "
    "притвориться разобранным"
)


# ── контракт стадии S4d (узел V49, шаг П4, позиция 2.4 списка) ───────────────────
# Заголовок раздела, подсказка о повторе и граница круга объявлены ДО
# `CHILD_NOT_IMPLEMENTED` по той же причине, что у V48: текст незакрытой части ссылается на
# раздел, где читается отказ стадии, и держать два написания одного заголовка нельзя.
# Имена таблиц и словари состояний приходят импортом из разбора вида — второго перечня
# таблиц или состояний в проекте нет (см. начало модуля).
ROLES_SECTION_HEADER = "СВОЙСТВА РОЛЕЙ КОНФИГУРАЦИИ (узел V49, позиция 2.4)"

# Что обязан сказать ответ о повторе стадии. Отдельная точка входа группы —
# `load_roles_tool` (шаг П5 узла, тот же слой, что стадия — прецедент V44/V46/V48); строка
# меняется одним местом, когда состав реестра инструментов меняется
# (`tools/check_mcp_tool_wiring.py`).
ROLES_REPEAT_HINT = (
    "Повторить стадию можно отдельным входом группы "
    "load_roles_tool(source_path=…) без перезагрузки конфигурации "
    "(узел V49, шаг П5) либо полной перезагрузкой "
    "load_1c_catalog_tool(source_path=…, force=True)"
)

# Граница круга называется и при успехе: «строки записаны» не равно «о ролях сохранено всё».
# Формулировка держится замеров раздела 2 плана V49 и решений Q2, Q3, Q5, Q9: без неё пустой
# перечень прав читался бы как «прав нет», а не как «содержимое не разобрано».
ROLES_BOUNDARY = (
    f"круг узла — файлы метаданных вида {ROLE_META_TAG} из каталога {ROLE_DIR}/ и их "
    "содержимое `<Имя>/Ext/Rights.xml` (позиция 2.4 списка): в `roles` идут имя, синоним, "
    "комментарий, три флага содержимого прав и состояние содержимого со счётчиками; в "
    "`role_rights` — цель, имя права, значение, состояние условия и имена вызовов шаблонов "
    "с порядком в файле; в `role_restriction_templates` — текст ограничения на пару "
    "(имя, отпечаток) с перечнем ролей-носителей; в `role_sources` — дескриптор файла "
    "содержимого (путь, размер, состояние объявления), а не его текст: 211 МБ второй "
    "копией в базе не держат (Q9, вариант A), обратная выгрузка не реализована. Права НЕ "
    "версионируются своей цепочкой (Q2, вариант A): своей истории у `role_rights` нет, "
    "текущность читается витриной `v_current_roles` связкой по `role_id`, а каскад "
    "`role_rights_role_id_fkey` снимает права вместе со строкой роли. Цель права — ссылка "
    "на СТРОКУ индекса состава (Q3): внешнего ключа нет, потому что цель бывает "
    "`prefix_only` или `unresolved`, и это состояние ответа, а не потерянная ссылка. "
    "Словаря XSD у вида нет (O5): неизвестное имя права читается состоянием `unknown_name`, "
    "а не свободным текстом. Вызов шаблона опознаётся по сигнатуре имени до первой скобки "
    "(Q5): полное имя вызова с декларацией не совпадает никогда (замер 2.7). Позиции 2.5 "
    "и далее нормативного списка этот узел не трогает"
)


# ── остановка конвейера по отказу стадии (узел V48, шаг П8, решение Q8 вариант A) ────
#
# Норматив: первая ошибка стадии останавливает конвейер, ответ получает `success: false` с
# названием остановленной стадии, последующие стадии не выполняются и читаются `not_run`
# (правило C2). Механизм остановки в загрузчике существовал и раньше — только для слоя
# заголовка (отказ разбора индекса состава даёт `return`); решение Q8 распространило его на
# стадии детей. Перечень стадий, их подсказки продолжения и незакрытые группы лежат здесь,
# одним местом: загрузчик, карточка `load_1c_catalog_tool` и проверка узла читают один и тот
# же словарь (прецедент V45/V46/V47 — два текста об одном отказе разъезжаются).
#
# Отдельного входа для дозагрузки нет только у S4b (решение Q4.1 узла V47) — об этом говорит
# `full_reload_required`, а не догадка читающего. Строка «что осталось в базе» обязательна:
# стадии S3+ идут ПОСЛЕ коммита транзакции заголовка, поэтому остановка не является откатом,
# и `success: false` без неё прочитался бы как «в базе ничего нет».

ROOT_MODULES_REPEAT_HINT = (
    "повторить стадию можно отдельным входом группы "
    "load_configuration_root_modules_tool(source_path=…, configuration_uuid=…) без "
    "перезагрузки конфигурации (узел V45) либо полной перезагрузкой "
    "load_1c_catalog_tool(source_path=…, force=True)"
)

CHILD_OBJECTS_REPEAT_HINT = (
    "повторить стадию можно отдельным входом группы "
    "load_configuration_object_properties_tool(source_path=…, configuration_uuid=…) без "
    "перезагрузки конфигурации (узел V46) либо полной перезагрузкой "
    "load_1c_catalog_tool(source_path=…, force=True)"
)

# Чем продолжить загрузку после остановки на каждой стадии — функция `stage_resume_hint`
# ниже. Словарем на уровне модуля этот перечень не объявить: подсказка S4b живёт в тексте
# стадии V47 (её читает форматёр `format_object_module_lines`), а обращение к ней происходит
# уже во время работы загрузки — так держится один текст об одном действии, а не два.

# Отдельного входа дозагрузки нет у одной стадии — S4b (решение Q4.1). `True` означает
# «продолжить можно только полной перезагрузкой конфигурации».
#
# Узел V50 (шаг П8): ключ каждой стадии детей обязан быть в словаре. Стадии S3, S4, S4c,
# S4d и S4e отдельные входы группы имеют (шаг П5 каждого узла), и отсутствие ключа
# маскируется значением по умолчанию в `build_stopped_stage`: стадия без ключа читается
# стадией без отдельного входа, хотя инструмент в реестре есть. Поэтому перечень — зеркало
# `STAGES`, а не запись про одну S4b.
STAGE_FULL_RELOAD_ONLY: Dict[str, bool] = {
    STAGE_ROOT_MODULES: False,
    STAGE_CHILD_OBJECTS: False,
    STAGE_SESSION_PARAMETERS: False,
    STAGE_ROLES: False,
    STAGE_COMMON_ATTRIBUTES: False,
    # Узел V51 (позиция 2.6): отдельный вход `load_exchange_plans_tool` есть (шаг П5),
    # поэтому остановка на S4f продолжение имеет — полная перезагрузка не требуется.
    STAGE_EXCHANGE_PLANS: False,
    # Узел V52 (позиция 2.7, шаг П4 — урок П8 узла V51): ключ и ветка `stage_resume_hint`
    # вносятся ОДНИМ шагом. Слой `load_filter_criteria` появляется этим же шагом П4, точка
    # входа группы — шагом П5; отсутствие ключа маскировалось бы значением по умолчанию в
    # `build_stopped_stage`: стадия без ключа читается стадией без отдельного входа, хотя
    # продолжение у неё есть. Механика остановки заработает с внесением стадии в `STAGES`
    # (шаг П5), словарь обязан быть её зеркалом уже сейчас.
    STAGE_FILTER_CRITERIA: False,
    # Узел V53 (позиция 2.8, шаг П4 — урок П8 узлов V51 и V52): ключ и ветка
    # `stage_resume_hint` вносятся ОДНИМ шагом. Слой `load_event_subscriptions` появляется
    # этим же шагом П4, точка входа группы — шагом П5; отсутствие ключа маскировалось бы
    # значением по умолчанию в `build_stopped_stage`: стадия без ключа читается стадией без
    # отдельного входа, хотя продолжение у неё есть.
    STAGE_EVENT_SUBSCRIPTIONS: False,
    # Узел V54 (позиция 2.9, шаг П4 — урок П8 узлов V51–V53): ключ и ветка
    # `stage_resume_hint` вносятся ОДНИМ шагом. Слой `load_scheduled_jobs` появляется этим же
    # шагом П4, точка входа группы `load_scheduled_jobs_tool` — шагом П5; отсутствие ключа
    # маскировалось бы значением по умолчанию в `build_stopped_stage`: стадия без ключа
    # читается стадией без отдельного входа, хотя продолжение у неё есть.
    STAGE_SCHEDULED_JOBS: False,
    # Узел V55 (позиция 2.10, шаг П5 — урок П8 узлов V51–V54): ключ словаря и ветка
    # `stage_resume_hint` вносятся ОДНИМ вызовом. Разрыв между ними маскировался бы значением
    # по умолчанию в `build_stopped_stage`: стадия без ключа читается стадией без отдельного
    # входа, хотя продолжение у неё есть (слоем `load_bots` он обеспечен с шага П4, точкой
    # входа группы — этим шагом П5).
    STAGE_BOTS: False,
    # Узел V56 (позиция 2.11, шаг П5 — урок П8 узлов V51–V55): ключ словаря и ветка
    # `stage_resume_hint` вносятся ОДНИМ вызовом. Разрыв между ними маскировался бы значением
    # по умолчанию в `build_stopped_stage`: стадия без ключа читается стадией без отдельного
    # входа, хотя продолжение у неё есть (слоем `load_functional_options` и точкой входа
    # группы `load_functional_options_tool` оба обеспечены этим же шагом П5).
    STAGE_FUNCTIONAL_OPTIONS: False,
    # Узел V57 (позиция 2.12, шаг П5 — урок П8 узлов V51–V56): ключ словаря и ветка
    # `stage_resume_hint` вносятся ОДНИМ вызовом. Разрыв между ними маскировался бы значением
    # по умолчанию в `build_stopped_stage`: стадия без ключа читается стадией без отдельного
    # входа, хотя продолжение у неё есть (слоем `load_functional_options_parameters` и точкой
    # входа группы `load_functional_options_parameters_tool` оба обеспечены этим же шагом П5).
    STAGE_FUNCTIONAL_OPTIONS_PARAMETERS: False,
    # Узел V58 (позиция 2.13, шаг П5 — урок П8 узлов V51–V57): ключ словаря и ветка
    # `stage_resume_hint` вносятся ОДНИМ вызовом. Разрыв между ними маскировался бы значением
    # по умолчанию в `build_stopped_stage`: стадия без ключа читается стадией без отдельного
    # входа, хотя продолжение у неё есть (слоем `load_defined_types` он обеспечен с шага П6,
    # точкой входа группы `load_defined_types_tool` — шагом П7).
    STAGE_DEFINED_TYPES: False,
    STAGE_OBJECT_MODULES: True,
}

# Незакрытая группа состава, которую называет `incomplete_groups` при остановке на стадии.
# Для S4b группу называет ответ стадии (`failed_group` — конкретный вид объектов), поэтому
# словарь даёт только общее имя на случай, когда вид не назван.
#
# Узел V50 (шаг П8): группа называется позицией нормативного списка и группой модели V38 —
# по образцу записей S4c (2.3) и S4d (2.4). Без записи остановка на S4e оставляла бы ответ
# без машиночитаемого признака неполноты: `incomplete_groups` строится из этого словаря
# (`_stage_stop` в загрузчике), а не из текста стадии.
STAGE_INCOMPLETE_GROUPS: Dict[str, str] = {
    STAGE_ROOT_MODULES: "модули предопределённых программ корня (группа C модели V38)",
    STAGE_CHILD_OBJECTS: "свойства подсистем и общих модулей (часть групп B и E модели V38)",
    STAGE_SESSION_PARAMETERS: "свойства параметров сеанса (позиция 2.3 нормативного списка)",
    STAGE_ROLES: "свойства ролей конфигурации (позиция 2.4 нормативного списка, "
                 "группа F модели V38)",
    STAGE_COMMON_ATTRIBUTES: "свойства общих реквизитов (позиция 2.5 нормативного списка, "
                             "группа E модели V38)",
    STAGE_EXCHANGE_PLANS: "свойства планов обмена (позиция 2.6 нормативного списка, "
                          "виды ChildObjects/TabularSection/Forms/Templates/Commands и "
                          "перечень <Content>)",
    # Узел V52 (шаг П4): группа называется позицией нормативного списка и видами детей,
    # которых касается круг, — по образцу записей S4c…S4f. Без записи остановка на S4g
    # оставила бы ответ без машиночитаемого признака неполноты: `incomplete_groups`
    # строится из этого словаря (`_stage_stop` в загрузчике), а не из текста стадии.
    STAGE_FILTER_CRITERIA: "свойства критериев отбора (позиция 2.7 нормативного списка, "
                           "его формы и команды и перечень <Content>)",
    # Узел V53 (шаг П4): группа называется позицией нормативного списка — по образцу записей
    # S4c…S4g. У подписки на события детей нет (замер 1.2), поэтому группа названа её
    # свойствами и кругом блока `<Source>`: без записи остановка на S4h оставила бы ответ без
    # машиночитаемого признака неполноты.
    STAGE_EVENT_SUBSCRIPTIONS: "свойства подписок на события (позиция 2.8 нормативного "
                               "списка и круг целей срабатывания блока <Source>)",
    # Узел V54 (шаг П4): группа называется позицией нормативного списка и её содержимым — по
    # образцу записей S4c…S4h. У регламентного задания нет форм, макетов, команд и модулей
    # (замер 1.2 плана), но есть содержимое — `Ext/Schedule.xml` (303 файла из 346), поэтому
    # группа названа и свойствами, и записями расписания: без записи остановка на S4i оставила
    # бы ответ без машиночитаемого признака неполноты.
    STAGE_SCHEDULED_JOBS: "свойства регламентных заданий (позиция 2.9 нормативного списка, "
                          "её свойства и записи расписания <Schedule> и "
                          "<DetailedDailySchedules> файла Ext/Schedule.xml)",
    # Узел V55 (шаг П5): группа называется позицией нормативного списка и её содержимым — по
    # образцу записей S4c…S4i. У бота нет форм, макетов и команд (замер 1.2), единственный
    # ребёнок вида в индексе состава — модуль Ext/Module.bsl, поэтому группа названа пятью
    # свойствами файла регистрации, ссылкой `Picture` и дескрипторами модуля: без записи
    # остановка на S4j оставила бы ответ без машиночитаемого признака неполноты.
    STAGE_BOTS: "свойства ботов конфигурации (позиция 2.10 нормативного списка, её свойства "
                "файла регистрации, ссылка Picture и дескрипторы модуля Ext/Module.bsl)",
    # Узел V56 (шаг П5): группа называется позицией нормативного списка и её содержимым — по
    # образцу записей S4c…S4j. У функциональной опции нет форм, макетов, команд и модулей
    # (замер 1.2 плана: записей индекса ровно по числу файлов, псевдозаписей и блока
    # ChildObjects ноль), но есть перечень применения `<Content>` (10 063 цели на корпус),
    # поэтому группа названа её свойствами файла регистрации, ссылкой `Location` и кругом
    # целей применения: без записи остановка на S4k оставила бы ответ без машиночитаемого
    # признака неполноты.
    STAGE_FUNCTIONAL_OPTIONS: "свойства функциональных опций (позиция 2.11 нормативного "
                              "списка, её свойства файла регистрации, ссылка Location и "
                              "круг целей применения блока <Content>)",
    # Узел V57 (шаг П5): группа называется позицией нормативного списка и её содержимым — по
    # образцу записей S4c…S4k. У параметра функциональной опции нет форм, макетов, команд и
    # модулей (замер 1.2 плана V57: записей индекса ровно по числу файлов, каталогов содержимого
    # ноль), но есть перечень применения `<Use>` (34 цели на корпус), поэтому группа названа его
    # свойствами файла регистрации и кругом целей применения: без записи остановка на S4l
    # оставила бы ответ без машиночитаемого признака неполноты. Отличие от 2.11 названо
    # позицией: у вида нет ссылки `Location`, есть только перечень `<Use>`.
    STAGE_FUNCTIONAL_OPTIONS_PARAMETERS:
        "свойства параметров функциональных опций (позиция 2.12 нормативного "
        "списка, её свойства файла регистрации и круг целей применения блока <Use>)",
    # Узел V58 (шаг П5): группа называется позицией нормативного списка и её содержимым — по
    # образцу записей S4c…S4l. У определяемого типа нет форм, макетов, команд, модулей и
    # каталогов содержимого (замер 1.2 плана V58: записей индекса ровно по числу файлов,
    # псевдозаписей ноль), но есть блок `<Type>` (17 544 значения на корпус, замер 2.2) и блок
    # `InternalInfo` (820/820 файлов, замер 1.3), поэтому группа названа её свойствами файла
    # регистрации и кругом целей значений блока <Type>: без записи остановка на S4m оставила бы
    # ответ без машиночитаемого признака неполноты.
    STAGE_DEFINED_TYPES:
        "свойства определяемых типов (позиция 2.13 нормативного списка, её свойства файла "
        "регистрации, блок InternalInfo и блок <Type> с кругом целей значений)",
    STAGE_OBJECT_MODULES: "модули объектов конфигурации (группа C модели V38, Ext/)",
}

# Обязательная строка ответа: остановка откатом не является. Заполняется загрузчиком по
# факту выполненного — здесь каркас фразы, чтобы формулировка была одна.
STOPPED_STAGE_WRITTEN_TEMPLATE = (
    "в базе остались: {written}; состав детей неполон — остановка не является откатом "
    "(стадии S3+ выполняются после фиксации заголовка и индекса состава, граница D7)"
)

STOPPED_STAGE_KEYS: Tuple[str, ...] = (
    "stage", "title", "status", "reason", "failed_group", "failed_record",
    "resume_with", "full_reload_required", "not_run_stages", "written_before_stop",
    "incomplete_group",
)

STOP_STAGE_SECTION_HEADER = ("ЗАГРУЗКА ОСТАНОВЛЕНА ПО ОТКАЗУ СТАДИИ "
                            "(узел V48, решение Q8 вариант A)")

# Причина, которую получает стадия, не вызванная конвейером (правило C2). Смысл отдельной
# строки: нулевой ответ стадии S4b несёт статус писателя (`ok`, потому что писатель описывает
# результат записи, а не состояние стадии), и без этой причины пропущенная стадия
# читалась бы как «модулей объектов в конфигурации нет», а не как «стадия не выполнялась».
NOT_RUN_STOPPED_REASON = ("стадия не вызывалась: конвейер остановлен на более ранней стадии "
                          "(решение Q8, вариант A) — «не выполнялась» читается статусом, "
                          "а не нулями выполненной стадии (правило C2)")


def stage_title(stage_id: str) -> str:
    """Название стадии по её адресу из `STAGES` (один перечень на весь слой)."""
    for stage, title in STAGES:
        if stage == stage_id:
            return title
    return stage_id


def stages_after(stage_id: str) -> List[str]:
    """Адресы стадий, идущих после указанной, в порядке `STAGES`.

    Порядок перечня стадий = порядок нормативного списка (раздел 2.9 плана V48): остановка
    имеет смысл только при совпадении порядка, иначе она пропускает группы, стоящие раньше
    ошибки. Поэтому «что не выполнялось» считается из `STAGES`, а не дописывается вручную там,
    где добавили новую стадию.
    """
    ids = [stage for stage, _ in STAGES]
    if stage_id not in ids:
        return []
    return ids[ids.index(stage_id) + 1:]


def stage_resume_hint(stage_id: str) -> str:
    """Чем продолжить загрузку, остановленную на стадии `stage_id`.

    Подсказки берутся из текстов стадий, а не переписываются: S3 и S4 имеют отдельные входы
    групп (узлы V45, V46), S4c — свой вход (шаг П5 того же узла), S4d — свой вход (шаг П5
    узла V49), S4e — свой вход (шаг П5 узла V50), S4f — свой вход `load_exchange_plans_tool`
    (шаг П5 узла V51), S4g — свой вход `load_filter_criteria_tool` (шаг П5 узла V52),
    S4h — свой вход `load_event_subscriptions_tool` (шаг П5 узла V53), S4i — свой вход
    `load_scheduled_jobs_tool` (шаг П5 узла V54),
    S4j — свой вход `load_bots_tool` (шаг П5 узла V55),
    S4k — свой вход `load_functional_options_tool` (шаг П5 узла V56),
    S4l — свой вход `load_functional_options_parameters_tool` (шаг П5 узла V57),
    S4b — не имеет (решение Q4.1). Стадия без
    подсказки была бы ошибкой
    контракта, поэтому ответ по умолчанию — полная перезагрузка, а не пустая строка. Отсутствие
    ветви у стадии с существующим отдельным входом назвало бы её продолжение неправдой:
    оператору предложили бы полный перезапуск там, где есть точечный вход (тот же дефект,
    который проба П8 узла V50 ловит числом через `STAGE_FULL_RELOAD_ONLY`).
    """
    if stage_id == STAGE_ROOT_MODULES:
        return ROOT_MODULES_REPEAT_HINT
    if stage_id == STAGE_CHILD_OBJECTS:
        return CHILD_OBJECTS_REPEAT_HINT
    if stage_id == STAGE_SESSION_PARAMETERS:
        return SESSION_PARAMETERS_REPEAT_HINT
    if stage_id == STAGE_ROLES:
        return ROLES_REPEAT_HINT
    if stage_id == STAGE_COMMON_ATTRIBUTES:
        return COMMON_ATTRIBUTES_REPEAT_HINT
    if stage_id == STAGE_EXCHANGE_PLANS:
        return EXCHANGE_PLAN_REPEAT_HINT
    if stage_id == STAGE_FILTER_CRITERIA:
        return FILTER_CRITERIA_REPEAT_HINT
    if stage_id == STAGE_EVENT_SUBSCRIPTIONS:
        return EVENT_SUBSCRIPTIONS_REPEAT_HINT
    if stage_id == STAGE_SCHEDULED_JOBS:
        return SCHEDULED_JOBS_REPEAT_HINT
    if stage_id == STAGE_BOTS:
        return BOTS_REPEAT_HINT
    if stage_id == STAGE_FUNCTIONAL_OPTIONS:
        return FUNCTIONAL_OPTIONS_REPEAT_HINT
    if stage_id == STAGE_FUNCTIONAL_OPTIONS_PARAMETERS:
        return FUNCTIONAL_OPTIONS_PARAMETERS_REPEAT_HINT
    if stage_id == STAGE_DEFINED_TYPES:
        return DEFINED_TYPES_REPEAT_HINT
    if stage_id == STAGE_OBJECT_MODULES:
        return OBJECT_MODULES_RELOAD_HINT
    return "полная перезагрузка load_1c_catalog_tool(source_path=…, force=True)"


def stopped_stage_defaults() -> Dict[str, Any]:
    """Закрытый словарь остановки с нулями (C1).

    Пустой (нулевой по всем ключам) словарь означает «конвейер не останавливался». Ненулевой
    `stage` — признак остановки, и он обязан называть остановленную стадию, причину, чем
    продолжить и что осталось в базе (решение Q8).
    """
    return {key: ([] if key == "not_run_stages" else
                  (False if key == "full_reload_required" else None))
            for key in STOPPED_STAGE_KEYS}


def build_stopped_stage(stage_id: str, stage_result: Dict[str, Any],
                       written_before_stop: str) -> Dict[str, Any]:
    """Собрать ответ об остановке по закрытому контракту (C1, C3).

    `stage_result` — ответ отказавшей стадии: из него берутся причина и, если стадия их
    назвала, незакрытая группа и запись (`failed_group`/`failed_record` у S4b). Ничего не
    выдумывается: не названо — остаётся `None`, и форматёр скажет об этом прямо.
    """
    stage_result = stage_result or {}
    stopped = stopped_stage_defaults()
    stopped["stage"] = stage_id
    stopped["title"] = stage_title(stage_id)
    stopped["status"] = STATUS_ERROR
    stopped["reason"] = (stage_result.get("error") or stage_result.get("reason")
                        or "загрузчик не назвал причину")
    stopped["failed_group"] = stage_result.get("failed_group")
    stopped["failed_record"] = stage_result.get("failed_record")
    stopped["incomplete_group"] = (stage_result.get("failed_group")
                                  or STAGE_INCOMPLETE_GROUPS.get(stage_id))
    stopped["resume_with"] = stage_resume_hint(stage_id)
    stopped["full_reload_required"] = bool(STAGE_FULL_RELOAD_ONLY.get(stage_id, False))
    stopped["not_run_stages"] = [{"stage": stage, "title": stage_title(stage),
                                  "status": STATUS_NOT_RUN}
                                 for stage in stages_after(stage_id)]
    stopped["written_before_stop"] = STOPPED_STAGE_WRITTEN_TEMPLATE.format(
        written=written_before_stop or "заголовок конфигурации")
    return stopped


def format_stopped_stage_lines(result: Dict[str, Any],
                               indent: str = "") -> List[str]:
    """Текст раздела об остановке конвейера (решение Q8, вариант A).

    Форматёр один — карточный: отдельного инструмента с этим текстом нет, остановку описывает
    ответ конвейера. Раздел обязан назвать и то, чего в базе НЕ стало (`not_run` последующих
    стадий, правило C2), и то, что в базе ОСТАЛОСЬ (заголовок, индекс состава, перечни вида,
    записи выполненных до отказа стадий) — иначе `false` прочитался бы как пустая база.
    """
    lines: List[str] = []
    if not result or not result.get("stage"):
        return lines
    lines.append(
        f"{indent}Остановлено на стадии: {result.get('stage')} — {result.get('title')}"
    )
    lines.append(f"{indent}Причина отказа: {result.get('reason')}")
    group = result.get("failed_group")
    if group:
        record = result.get("failed_record")
        lines.append(
            f"{indent}Незакрытая группа состава: {group}"
            + (f" (запись: {record})" if record else "")
        )
    lines.append(f"{indent}Что осталось в базе: {result.get('written_before_stop')}")
    lines.append(f"{indent}Чем продолжить: {result.get('resume_with')}")
    if result.get("full_reload_required"):
        lines.append(
            f"{indent}Отдельного входа дозагрузки этой стадии нет (решение Q4.1) — "
            "продолжить можно только полной перезагрузкой конфигурации"
        )
    for item in result.get("not_run_stages") or []:
        lines.append(
            f"{indent}Стадия не выполнялась: {item.get('stage')} — {item.get('title')} "
            f"(статус {STATUS_NOT_RUN}: «не выполнялась» читается статусом, а не нулями — C2)"
        )
    return lines


# Что из содержимого дочерних объектов стадия S4 НЕ загружает (узлы V38 и V46) — текст
# `CHILD_NOT_IMPLEMENTED`. С узла V46 стадия реализована частично: свойства подсистем, их
# ссылки `Content`, свойства и дескрипторы общих модулей. По модели A–H узла V38 это часть
# групп B (общие модули) и E (свойства подсистем без дочерней структуры); группой C в модели
# названы модули предопределённых программ корня, их закрыл узел V44 — прежняя формулировка
# «группа C закрыта для подсистем и общих модулей» была неверной именно поэтому. Остальное
# остаётся незакрытым, и текст стадии обязан это
# назвать: сказать «конфигурация загружена целиком», когда реквизитов и форм объектов нет,
# значило бы соврать (решение оператора 22.10.2026 о том, что заглушка не является ни
# ошибкой, ни успехом, сохраняется для неотзакрытой части).
#
# Узел V48 (шаг П4, решение Q5): свойства параметров сеанса закрывает отдельная стадия S4c,
# а не третий вид S4, поэтому в этом тексте параметры сеанса из незакрытой части убраны.
# Круг `CHILD_KINDS` при этом не расширяется (план
# docs/CONFIGURATION_SESSION_PARAMETERS_PLAN.md, раздел 5): карточка слоя не вправе обещать
# то, чего у вида `load_configuration_object_properties_tool` нет. Круг `CHILD_TABLES`
# сужен до таблиц самой стадии V46 — см. комментарий у его определения: таблица V48
# относится стадии S4c и в ответе S4 перечисляться не должна.
#
# Узел V50 (шаг П8): определение перенесено ниже — в блок стадии S4e. Текст незакрытой
# части ссылается на заголовок раздела S4e, объявленный рядом с кругом таблиц вида
# (прецедент V48/V49: заголовок объявляется раньше текста, который на него ссылается, и
# держать второе написание того же заголовка текстом нельзя). Смысл правки одна строка:
# из незакрытой части убраны общие реквизиты — позиция 2.5, закрытая стадией S4e.


# Ключи `index_counts` — контракт разбора `ConfigDumpInfo.xml` (узел V33). Перечень держится
# здесь, потому что нулевой словарь по этому перечню обязан совпадать с настоящим ответом:
# карточка, которая заполняет «свои» семь ключей, через месяц теряет два из них.
INDEX_COUNT_KEYS: Tuple[str, ...] = (
    "entries_total", "root_entries", "child_entries", "max_depth",
    "config_versions", "config_versions_missing", "parent_unresolved",
)


def index_counts_defaults() -> Dict[str, int]:
    return {key: 0 for key in INDEX_COUNT_KEYS}


def header_array_anomalies_defaults() -> Dict[str, Any]:
    """Аномалии перечней V43: `unknown_types` — список видов, остальные — счётчики."""
    return {"unknown_types": [], "overlong": 0, "empty_object_name": 0,
            "top_level_entries": 0}


def root_modules_defaults() -> Dict[str, Any]:
    """Плоский контракт `load_root_modules` с нулями (C1, C3).

    `by_kind` остаётся пустым словарём, а не `{вид: absent}`: «вида нет в конфигурации» — это
    утверждение о выгрузке, которое делает только выполненный разбор. Для невыполненной стадии
    честный ответ — пустой словарь плюс `stages[].status = not_run` (C2).

    Ключ `error` входит в замкнутый перечень: его читает форматёр отказа
    («Стадия не выполнена: …») и кладёт конвейер при пропуске стадии. По C1 ключа
    «нет» в ответе быть не может — причина либо названа строкой, либо `None`.
    """
    return {
        "success": False,
        "error": None,
        "configuration_id": None,
        "configuration_uuid": None,
        "configuration_name": None,
        "tables": list(TABLES),
        "written": 0,
        "written_by_table": {table: 0 for table in TABLES},
        "kinds_total": ROOT_MODULE_COUNT,
        "counts_by_state": {state: 0 for state in REPORT_STATES},
        "by_kind": {},
        "removed_previous": {table: 0 for table in TABLES},
        "index_available": False,
        "index_root_name": None,
        "index_rows": 0,
        "index_matched": 0,
        "index_unmatched": [],
        "stray_ext_bsl": [],
        "warnings": [],
    }


# Мёртвое определение `child_objects_defaults()` (прежний облик V45: четыре ключа `status`,
# `reason`, `objects_written`, `tables`) удалено узлом V48, шаг П8 (позиция O9 плана,
# раздел 5). Живым было единственное определение ниже — закрытый контракт стадии S4 узла V46,
# и именно оно перекрывало это: Python оставляет последнее объявление. Безвредный для
# работающего кода дубль неприемлем здесь: функция задаёт состояние «стадия не выполнялась»
# (`not_run`), а на нём стоит остановка конвейера по решению Q8 — два облика одного
# состояния в модуле контракта значили бы два разных ответа на один вопрос. Проверяется
# отсутствием второго `FunctionDef` с этим именем — `_v48_q8_contract_probe.py`, критерий 6б
# плана `docs/CONFIGURATION_SESSION_PARAMETERS_PLAN.md`.



# ── текст стадии S3: один форматёр на карточку и на отдельный инструмент ────────────

# Заголовок раздела карточки `load_1c_catalog_tool` (вариант `configuration`) и ответа
# `load_configuration_root_modules_tool`. Один на два контура: карточка и инструмент
# описывают один и тот же слой, а заголовок и текст, переписанные порознь, разъезжаются
# при первой же правке контракта — по той же причине, по которой имена 48 перечней V43
# и фильтр карантина Q1 лежат в одном месте.
ROOT_MODULES_SECTION_HEADER = "КОД ПРЕДОПРЕДЕЛЁННЫХ ПРОГРАММ КОРНЯ (узел V44)"


def format_root_modules_lines(result: Dict[str, Any],
                              indent: str = "") -> List[str]:
    """Текст состояния стадии S3 по плоскому контракту `load_root_modules` (C1, C3).

    Формат один для двух контуров: карточки `load_1c_catalog_tool` и ответа
    `load_configuration_root_modules_tool` (решение V45). Отказ стадии форматёр
    называет сам («Стадия не выполнена: …») — вызывающий причину не повторяет: два
    текста об одном отказе разъезжаются (так же сломался прежний форматёр V44,
    державший `counts`, `rows`, `forms`, `TABLE_MODULES`, которых у контракта нет).
    Проблемные строки (несовпавшие записи индекса, файлы `Ext/` вне словаря, снятые
    прежние строки) кладёт в `warnings` сама стадия — форматёр их печатает, а не
    пересобирает по полям. Неперечисленные ключи читаются нулями (C1).
    """
    lines: List[str] = []
    if not result:
        return lines
    if not result.get("success"):
        lines.append(
            f"{indent}Стадия не выполнена: "
            f"{result.get('error') or 'загрузчик не назвал причину'}"
        )
        return lines

    counts_by_state = result.get("counts_by_state") or {}
    lines.append(
        f"{indent}Записано строк: {int(result.get('written') or 0)}; "
        f"ожидаемых видов: {int(result.get('kinds_total') or ROOT_MODULE_COUNT)}; "
        "состояния: "
        + ", ".join(
            f"{state}={int(counts_by_state.get(state) or 0)}"
            for state in REPORT_STATES
        )
    )
    by_kind = result.get("by_kind") or {}
    for kind in KINDS:
        lines.append(
            f"{indent}{MODULE_BY_KIND[kind]} ({TITLE_BY_KIND[kind]}): "
            f"{by_kind.get(kind) or STATE_ABSENT}"
        )
    if result.get("index_available"):
        lines.append(
            f"{indent}Индекс состава: строка корня "
            f"{result.get('index_root_name') or 'не названа'}, подтверждено слотов "
            f"{int(result.get('index_matched') or 0)} из {ROOT_MODULE_COUNT} "
            f"(записей вида: {int(result.get('index_rows') or 0)})"
        )
    else:
        lines.append(
            f"{indent}Индекс состава не читается — состояния называет только файл, "
            "и «модуля нет» от «пустого модуля» этим не отличить"
        )
    for warning in result.get("warnings") or []:
        lines.append(f"{indent}⚠️ {warning}")
    return lines


# ── стадия S4: содержимое дочерних объектов (узел V46, 28.10.2026) ────────────────────

# Круг таблиц стадии задаёт тот же перечень, что и круг версионных таблиц конфигурации
# (`src/current_revision.py`): отдельного списка здесь заводить нельзя — круг разъехался бы
# с кругом версионности, и ровно так появился D11 (круг задаёт признак версии, а не список).
#
# Узел V48 (шаг П4, проба `_v48_p4_loader_probe.py`, замер 29.10.2026): круг был буквально
# равен `CONFIGURATION_VERSIONED_TABLES`, и это совпадало только пока версионируемых таблиц
# конфигурации было ровно четыре и все они принадлежали стадии S4. Регистрация таблицы
# `session_parameters` (узел П1) молча добавила к кругу пятую таблицу: стадия S4 начала
# снимать и анализировать чужую таблицу (`remove_object_properties` и
# `refresh_table_statistics` вызываются кругом по умолчанию), а её ответ перечислял бы
# `session_parameters` в ключе `tables` — то есть обещать содержимое, которого у видов V46
# нет, прямо противореча решению Q5.
#
# Источник круга остаётся один — `CONFIGURATION_VERSIONED_TABLES`; каждая стадия называет
# СВОИ таблицы своей константой, а чужой круг = источник минус чужие стадии. Стадия, которая
# не объявит свои таблицы, попадёт в круг S4 — и проверка П4 это ловит строкой «круг стадии
# S4 не тронут».
SESSION_PARAMETER_TABLES: Tuple[str, ...] = (SESSION_PARAMETER_TABLE,)
# Узел V49 (роли, 30.10.2026): тот же дефект повторился ровно через один узел. Регистрация
# таблиц вида «роли» в круге версионности (шаг П1) молча добавила к кругу S4 четыре таблицы:
# проба `_v46_p4_writer_probe.py` упала на `KeyError: 'roles'`, потому что контракт разбора
# `CHILD_KINDS`/`CHILD_TABLES` стал шире круга стадии, а стадия S4 снимала и анализировала
# бы чужие строки (у BP3 это 682 строки ролей и 76 332 строки прав). Роль — не вид свойств
# V46: своей точки входа у `load_configuration_object_properties_tool` она не имеет. Свою
# стадию `s4d_roles` и свой ключ ответа ей дал шаг П4 этого же узла, но круг S4 от этого не
# расширяется: таблицы вида объявляются здесь своей константой и из круга S4 вычитаются —
# при том что писатели и цепи ревизий у них работают с шага П3 (иначе версионируемая
# таблица осталась бы без писателя, то есть без права на запись).
ROLE_TABLES: Tuple[str, ...] = (
    ROLE_TABLE,
    ROLE_RIGHTS_TABLE,
    ROLE_TEMPLATES_TABLE,
    ROLE_SOURCES_TABLE,
)

# Группы круга S4d — нужны отдельному входу `load_roles_tool` (шаг П5, план раздел 5):
# случай «изменились только файлы прав» или «изменились только шаблоны ограничений» стоит
# дороже всего круга (замер П4: BGU2 11.66 с, BP3 19.01 с на 140 158 прав). Границы групп
# держит схема, а не удобство вызова: `role_rights.role_id` ссылается на строку `roles`
# с `ON DELETE CASCADE` (migration V49), поэтому роли и их права — одна пара, а
# `role_restriction_templates` и `role_sources` на строки других таблиц узла не ссылаются.
# Правила запроса называются отказом загрузки, а не молчаливой деградацией:
#   * `roles` без `role_rights` — отказ: снятие ролей каскадом сняло бы права, и в базе
#     остались бы роли с состоянием `with_rights` без единой строки прав — состав, которого
#     в выгрузке нет (тот же запрет, что «половина круга» у приёмов V12/V46);
#   * `role_rights` без `roles` — разрешено, только если строки ролей этой конфигурации уже
#     есть в базе: права пишутся на их CURRENT-ревизии. Если ролей нет — отказ с указанием
#     запросить `roles`. Это и есть сценарий позиции O8 («права отдельным входом»), но
#     порога, при котором он был бы обязателен, замер П4 не дал;
#   * `role_restrictions` — группа самостоятельна: текст шаблона выводится из условия и на
#     строки прав не ссылается (носители — имена ролей текстом, замер 2.7).
ROLE_KIND_ROLES = "roles"
ROLE_KIND_RIGHTS = "role_rights"
ROLE_KIND_RESTRICTIONS = "role_restrictions"
ROLE_KINDS: Tuple[str, ...] = (ROLE_KIND_ROLES, ROLE_KIND_RIGHTS, ROLE_KIND_RESTRICTIONS)
ROLE_KIND_TITLES: Dict[str, str] = {
    ROLE_KIND_ROLES: "Роли и дескрипторы их файлов",
    ROLE_KIND_RIGHTS: "Права ролей",
    ROLE_KIND_RESTRICTIONS: "Шаблоны ограничений",
}
ROLE_TABLES_BY_KIND: Dict[str, Tuple[str, ...]] = {
    ROLE_KIND_ROLES: (ROLE_TABLE, ROLE_SOURCES_TABLE),
    ROLE_KIND_RIGHTS: (ROLE_RIGHTS_TABLE,),
    ROLE_KIND_RESTRICTIONS: (ROLE_TEMPLATES_TABLE,),
}
# Порядок записи групп держится иерархией данных (роли раньше ссылающихся на них прав),
# а не порядком запроса вызывающего.
ROLE_KIND_WRITE_ORDER: Tuple[str, ...] = (
    ROLE_KIND_ROLES, ROLE_KIND_RIGHTS, ROLE_KIND_RESTRICTIONS,
)
# Узел V50 (общие реквизиты, 30.10.2026): тот же дефект — третьим узлом. Регистрация двух
# таблиц вида в круге версионности (шаг П1) молча добавила к кругу S4 `common_attributes`:
# проба `_v46_p4_writer_probe.py` упала на `KeyError: 'common_attributes'`, потому что
# контракт `CHILD_TABLES` стал шире круга стадии S4, а стадия снимала и анализировала бы
# чужие строки. Групп запроса у вида нет (Q10, вариант A: порог не замерен, отдельный вход
# дозагружает весь круг сразу), поэтому константа называет только круг стадии — без
# `*_TABLES_BY_KIND`, которых у V49 четыре. Строка применения версионируется не своей цепью
# (Q2, вариант A), но в круг версионности она внесена осознанно — её снимает и загружает
# стадия, а писатель у неё есть; отсутствие в круге означало бы, что перезагрузка вида
# оставила бы прежние строки применения.
COMMON_ATTRIBUTES_TABLES: Tuple[str, ...] = (
    COMMON_ATTRIBUTE_TABLE,
    COMMON_ATTRIBUTE_TARGETS_TABLE,
)

# Узел V51 (план обмена, 31.10.2026, позиция 2.6 списка): тот же дефект — четвёртым узлом.
# Регистрация трёх таблиц вида в круге версионности (шаг П1) молча добавила бы к кругу S4
# `exchange_plans`, `exchange_plan_content` и `commands`: проба `_v46_p4_writer_probe.py`
# падает на KeyError, потому что контракт `CHILD_TABLES` становится шире круга стадии, а
# стадия S4 снимала и анализировала бы чужие строки (замеры П0: на BGU2 — 18 строк вида и
# 9 638 строк перечня `<Content>`). Свою стадию `s4f_exchange_plans`, заголовок раздела и
# ключ ответа даёт шаг П4 этого узла (Q8 плана), а круг стадии объявляется здесь:
# версионируемая таблица без объявленного круга означала бы, что чужая стадия её снимает.
# Группы запроса (`kinds`) у вида есть (Q5 закрыт: пустое значение = весь круг); таблицы
# каждой группы называет `GROUP_TABLES` разбора (`group_tables()`), а не второй словарь вида
# вроде `*_TABLES_BY_KIND`: круг стадии и круг группы читаются из одного перечня, и второй
# перечень разъехался бы с первым при первой же правке (так форматёр незапрошенных групп и
# писатель круга говорят об одном составе). Здесь только круг стадии S4f целиком.
EXCHANGE_PLAN_TABLES: Tuple[str, ...] = (
    EXCHANGE_PLAN_TABLE,
    EXCHANGE_PLAN_CONTENT_TABLE,
    EXCHANGE_PLAN_COMMANDS_TABLE,
)

# ── контракт стадии S4f (узел V51, шаг П4, позиция 2.6 списка) ───────────────────────
# Заголовок раздела, подсказка о повторе, названия групп и граница круга объявлены рядом с
# кругом таблиц стадии — по той же причине, что у V48, V49 и V50: текст незакрытой части
# ссылается на раздел, где читается отказ стадии, а держать два написания одного заголовка
# нельзя. Имена таблиц, каталог вида, словари состояний и группы запроса приходят импортом
# из разбора (`src/configuration_exchange_plans.py`) — второго перечня таблиц, состояний или
# групп в проекте нет.
EXCHANGE_PLAN_SECTION_HEADER = "СВОЙСТВА ПЛАНОВ ОБМЕНА (узел V51, позиция 2.6)"

# Что обязан сказать ответ о повторе стадии. Отдельная точка входа группы
# `load_exchange_plans_tool` существует с шага П5 (31.10.2026) и вызвана в реестр MCP тем же
# шагом, поэтому подсказка называет её, а не обещает: прецеденты V48/V49/V50 меняют строку
# одним местом ровно тогда, когда меняется состав реестра
# (`tools/check_mcp_tool_wiring.py`). Называть несуществующий инструмент реальным —
# обещание, которого сервер не выполняет; называть существующий несуществующим — та же
# неправда в обратную сторону.
EXCHANGE_PLAN_REPEAT_HINT = (
    "Повторить круг можно отдельным входом load_exchange_plans_tool(source_path=…, kinds=…) "
    "без перезагрузки конфигурации: идемпотентность держится явным DELETE по "
    "configuration_uuid и по родителям круга, внешнего ключа на configurations и каскада по "
    "нему в схеме нет осознанно (прецедент V20.1). Тот же слой вызывает стадия S4f "
    "конвейера load_1c_catalog_tool — двух кодов, которые могли бы разойтись, в проекте нет."
)

# Названия групп запроса (`kinds`) для ответа стадии. Пустое значение параметра означает
# ВЕСЬ круг (Q5 закрыт, п. 1); незапрошенная группа не снимается и обязана быть названа
# своими таблицами, потому что её нули не означают «детей у вида нет» (правило V49).
EXCHANGE_PLAN_GROUP_TITLES: Dict[str, str] = {
    EXCHANGE_PLAN_GROUP_EXCHANGE_PLANS: "Строки вида и их перечни детей",
    EXCHANGE_PLAN_GROUP_ATTRIBUTES: "Реквизиты вида и колонки табличных частей",
    EXCHANGE_PLAN_GROUP_TABULAR_SECTIONS: "Табличные части вида",
    EXCHANGE_PLAN_GROUP_FORMS: "Формы вида (с их содержимым)",
    EXCHANGE_PLAN_GROUP_TEMPLATES: "Макеты вида (с их содержимым)",
    EXCHANGE_PLAN_GROUP_COMMANDS: "Команды вида",
    EXCHANGE_PLAN_GROUP_CONTENT: "Перечень <Content> плана обмена",
    EXCHANGE_PLAN_GROUP_SLOTS: "Слоты Help и AdditionalIndexes",
}

# Группы, которые образуют ОДНУ строку: строка вида и её слоты. Причина не в удобстве, а в
# двух фактах: Q5, п. 3 (строка вида и её перечни пересчитываются при любом вызове, потому
# что выводятся из индекса состава, а не из записанных детей) и CHECK
# `exchange_plans_slot_content_matches_state` (состояние слота обязано быть названо на
# каждой строке, а состояния «слоты не загружались» в замкнутом словаре нет — его нечем
# было бы отличить от `absent`). Поэтому `slots` неотделима от строки вида так же, как
# `forms` неотделима от `form_ext` (каскад `form_ext_form_id_fkey`).
EXCHANGE_PLAN_ROW_GROUPS: Tuple[str, ...] = (
    EXCHANGE_PLAN_GROUP_EXCHANGE_PLANS, EXCHANGE_PLAN_GROUP_SLOTS,
)
# Группы, неразрывные на уровне таблиц: `form_ext` висит на `forms(id) ON DELETE CASCADE`,
# поэтому «формы без содержимого» схема не допускает (Q5, п. 2).
EXCHANGE_PLAN_INSEPARABLE_GROUPS: Dict[str, Tuple[str, ...]] = {
    EXCHANGE_PLAN_GROUP_FORMS: ("form_ext",),
}

# Что стадия S4f НЕ берёт из содержимого вида. Граница называется текстом ответа, а не
# молчанием (прецедент `COMMON_ATTRIBUTES_BOUNDARY` узла V50): «строки записаны» не равно
# «о плане обмена сохранено всё».
EXCHANGE_PLAN_CIRCLE_BOUNDARY = (
    "тела модулей вида узел НЕ читает: `Ext/ObjectModule.bsl`, `Ext/ManagerModule.bsl` и "
    "`Commands/*/Ext/CommandModule.bsl` принадлежат узлу V47 (`bsl_modules`, "
    "`parent_type='configuration_objects'`), здесь файлы названы дескрипторами — "
    "повторного чтения одного файла два узла не делают (Q8); каталог ресурсов справки "
    "`Ext/Help/` (`ru.html`, `_files/*.bmp`) не хранится: колонок под ресурсы справки в "
    "схеме нет, наличие называется наблюдением `help_resources_dir`; стандартные "
    "реквизиты (блок `Properties/StandardAttributes`, 371 вхождение трёх выгрузок при 9 "
    "уникальных именах — замер 3.3) строками не пишутся: их нет в индексе состава, наличие "
    "называется состоянием `present_not_indexed` (Q7); определённых типов (`DefinedTypes`) "
    "в выгрузке вида нет (замер 2.4.4), узла для них нет; перечень заголовка "
    "`configurations.exchange_plans` — третью ногу круга (узел V43) — стадия S4f не пишет и "
    "не правит: её заполняет стадия S2 по индексу состава, а сходство файлов регистрации, "
    "строк индекса и перечня заголовка проверяет `tools/check_v51_exchange_plans.py` "
    "(шаг П6)"
)

# ── контракт стадии S4e (узел V50, шаг П4, позиция 2.5 списка) ──────────────────────
# Заголовок раздела, подсказка о повторе и граница круга объявлены рядом с кругом таблиц
# стадии — по той же причине, что у V48 и V49: текст незакрытой части ссылается на раздел,
# где читается отказ стадии, а держать два написания одного заголовка нельзя. Имена таблиц,
# каталог вида и словари состояний приходят импортом из разбора
# (`src/configuration_common_attributes.py`) — второго перечня таблиц или состояний в проекте
# нет.
COMMON_ATTRIBUTES_SECTION_HEADER = "СВОЙСТВА ОБЩИХ РЕКВИЗИТОВ (узел V50, позиция 2.5)"

# Что обязан сказать ответ о повторе стадии. Отдельная точка входа группы —
# `load_common_attributes_tool` (шаг П5 узла, тот же слой, что стадия — прецедент
# V44/V46/V48/V49); строка меняется одним местом, когда состав реестра инструментов меняется
# (`tools/check_mcp_tool_wiring.py`).
COMMON_ATTRIBUTES_REPEAT_HINT = (
    "Повторить стадию можно отдельным входом группы "
    "load_common_attributes_tool(source_path=…) без перезагрузки конфигурации "
    "(узел V50, шаг П5) либо полной перезагрузкой "
    "load_1c_catalog_tool(source_path=…, force=True)"
)

# Граница круга называется и при успехе: «строки записаны» не равно «об общих реквизитах
# сохранено всё». Формулировка держится замеров раздела 2 плана V50 и решений Q1–Q3, Q5, Q7:
# без неё пустой блок разделения читался бы как «разделения нет», а неразрешённая цель —
# как потерянная ссылка.
COMMON_ATTRIBUTES_BOUNDARY = (
    f"круг узла — файлы регистрации вида {COMMON_ATTRIBUTE_META_TAG} из каталога "
    f"{COMMON_ATTRIBUTES_DIR}/ (позиция 2.5 списка): в `common_attributes` идут 38 свойств "
    "файла регистрации (имя, синоним, комментарий, флаги, значения словарей), блок `<Type>` "
    "в закрытом словаре записей (`types`, `type_qualifiers`, кратность) и три блока "
    "разделения данных; в `common_attribute_targets` — строки перечня `<Content>` (цель, "
    "порядок в файле, состояние применения, условие разделения позиции). Строка применения "
    "версионируется НЕ своей цепью (Q2, вариант A): своей истории у неё нет, ключ "
    "начинается с `common_attribute_id` — числового id конкретной ревизии строки реквизита, "
    "текущность читается витриной `v_current_common_attributes` связкой по этому id, а "
    "каскад `common_attribute_targets_common_attribute_id_fkey` снимает применение вместе со "
    "строкой реквизита. Цель применения и ссылка разделения — ссылка на СТРОКУ индекса "
    "состава (Q3): внешнего ключа нет, потому что цель бывает `prefix_only` или `unresolved` "
    "(замеры 2.6 и 2.7 дают 1 512 из 1 512 `exact` — состояния обязаны быть названы, а не "
    "подразумеваться). Значения СВОЙСТВ вида CHECK'ом не замкнуты (Q7, вариант A): "
    "закрытость держит измеренный словарь `PROPERTY_VALUE_DICTIONARY`, незнакомое значение "
    "остаётся значением с состоянием `unknown_value` и именем виновника, а не отказом "
    "записи. Непустых блоков разделения на четырёх выгрузках 12 из 48 (замер 2.7): пустой "
    "блок является состоянием `empty_value`, а не пустой строкой; непустая форма "
    "`<xr:ConditionalSeparation>` — позиция O4 плана, узла загрузки нет. Модулей, форм и "
    "макетов у вида нет (замер 2.1); обратных отсылок из объектов-носителей тоже (замер "
    "2.10: ссылки дают подсистемы, роли и функциональные опции, чьи слои не загружены)"
)

# ── контракт стадии S4g (узел V52, шаг П4, позиция 2.7 списка) ───────────────────────
# Круг таблиц стадии и тексты контракта объявлены одним местом — по той же причине, что у
# V48, V49, V50 и V51: текст незакрытой части ссылается на раздел, где читается отказ
# стадии, а держать два написания одного заголовка нельзя. Имена таблиц, каталог вида,
# метка метаданных и словари состояний приходят импортом из разбора
# (`src/configuration_filter_criteria.py`) — второго перечня таблиц или состояний в проекте
# нет.
#
# Дефект, который закрывает эта константа, — тот же, что называли узлы V49, V50 и V51:
# регистрация `filter_criteria` в круге версионности (шаг П1) молча добавила бы её к кругу
# стадии S4, и проба `_v46_p4_writer_probe.py` падает на `KeyError: 'filter_criteria'`,
# потому что контракт `CHILD_TABLES` становится шире круга стадии, а стадия S4 снимала и
# анализировала бы чужие строки (замеры П0: 15 файлов регистрации и 1 219 целей на четыре
# выгрузки). Групп `kinds` нет, поэтому константа называет только круг стадии — без
# `*_TABLES_BY_KIND`, которых у V51 восемь: строка условия неотделима от строки вида (Q1,
# вариант A), а таблицы детей (`forms`, `form_ext`, `commands`) общи с узлом V51 и в круг
# этой стадии НЕ входят — их снимает и пишет предикатом по uuid родителей, и второй
# перечень тех же таблиц появился бы только ради того, чтобы разойтись с первым.
FILTER_CRITERIA_TABLES: Tuple[str, ...] = (
    FILTER_CRITERIA_TABLE,
    FILTER_CRITERIA_CONTENT_TABLE,
)

# Круг снятия и перечень чисел ответа — ПЯТЬ таблиц, а не две. Различение двух утверждений и
# есть ответ на позицию, которую назвал прогон П8 (02.11.2026): «что стадия версионирует»
# (две таблицы вида, ключ `tables`, круг `FOREIGN_STAGE_TABLES`) и «по каким таблицам ответ
# даёт числа» (весь круг снятия). Второе шире первого по одному факту: строки детей (`forms`,
# `form_ext`, `commands`) снимает и пишет ЭТА ЖЕ стадия предикатом по uuid родителей круга,
# поэтому числа по ним — факт стадии, а не чужой загрузки: отдельной стадии детей в конвейере
# нет (`STAGES` закрывается позициями 2.3…2.7 и модулями объектов). Засевать пары двумя
# таблицами значило бы обещать нулевому ответу перечень, которого успешный прогон не даёт:
# потребитель, который перебирает `written_by_table`, в пропущенной стадии видел бы две
# таблицы, а в успешной — пять.
#
# Второго перечня этих таблиц в проекте не появляется — тот же комментарий выше это запрещает:
# `REMOVE_ORDER` загрузчика является алиасом этого кортежа. Имена детей здесь литералы, и их
# совпадение с константами слоя (`FORM_EXT_TABLE`, `FORMS_TABLE`, `COMMANDS_TABLE_NAME`)
# сторожит контур 12 `tools/check_v52_filter_criteria.py`: разъехались бы — проверка назвала
# бы имена, а не молчала (прецедент литерала `"form_ext"` в `EXCHANGE_PLAN_INSEPARABLE_GROUPS`:
# контракт уже называет общие таблицы детей, когда говорит о них).
#
# Порядок — порядок снятия, а не порядок версионности: `form_ext` первой, потому что её FK
# `form_ext_form_id_fkey` объявлен с `ON DELETE CASCADE` и каскад по строке формы снял бы
# описания молча, без точного счётчика (M7); строки вида последними, потому что на числовые id
# последних опираются строки `<Content>` (Q2, вариант A). Тот же приём, что `REMOVE_ORDER`
# узлов V49, V50, V51.
FILTER_CRITERIA_REMOVE_ORDER: Tuple[str, ...] = (
    "form_ext", "forms", "commands",
    FILTER_CRITERIA_CONTENT_TABLE,
    FILTER_CRITERIA_TABLE,
)

FILTER_CRITERIA_SECTION_HEADER = "СВОЙСТВА КРИТЕРИЕВ ОТБОРА (узел V52, позиция 2.7)"

# Что обязан сказать ответ о повторе стадии. Отдельная точка входа группы —
# `load_filter_criteria_tool` (шаг П5 узла, внесена в реестр сервера этим же шагом —
# `tools/check_mcp_tool_wiring.py` сторожит состав). П4 держал формулировку про слой
# `load_filter_criteria`, потому что обещать инструмент, которого в реестре нет, — значит
# дать обещание, которое сервер не выполняет; с десятым инструментом строка меняется одним
# местом (прецеденты V48/V49/V50/V51).
FILTER_CRITERIA_REPEAT_HINT = (
    "Повторить стадию можно отдельным входом группы "
    "load_filter_criteria_tool(source_path=…) без перезагрузки конфигурации "
    "(узел V52, шаг П5) либо полной перезагрузкой "
    "load_1c_catalog_tool(source_path=…, force=True)"
)

# Граница круга называется и при успехе: «строки записаны» не равно «о критериях отбора
# сохранено всё». Формулировка держится замеров разделов 1–2 плана V52 и решений Q1, Q3,
# Q6, Q7, Q8: без неё пустой `<Content>` читался бы как «условий нет», а `TypeSet` — как
# «типа нет».
FILTER_CRITERIA_CIRCLE_BOUNDARY = (
    f"круг узла — файлы регистрации вида {FILTER_CRITERIA_META_TAG} из каталога "
    f"{FILTER_CRITERIA_DIR}/ (позиция 2.7 списка), подтверждённые записями индекса состава, "
    "плюс перечень заголовка `configurations.filter_criteria` как независимая третья нога "
    "(её заполняет стадия S2, стадия S4g её не пишет): в `filter_criteria` идут 11 свойств "
    "файла регистрации (замер 2.1: ровно один набор тегов на всех 15 файлах), блок `<Type>` "
    "в закрытом словаре записей с ключом `container` (`Type` | `TypeSet` — KomMag даёт "
    "`<v8:TypeSet>cfg:DocumentRef</v8:TypeSet>`, собственной ветки парсера у V48/V50 не "
    "было, и значение читалось бы потерянным — Q6) и состояния ссылок на форму; в "
    "`filter_criterion_content` — строки перечня `<Content>` (1 219 целей на четыре "
    "выгрузки: BGU2 727, BP3 492; MinCfg и KomMag дают пустой блок — состояние "
    "`empty_content` строки вида, а не пустая таблица). Строка условия версионируется НЕ "
    "своей цепью (Q2, вариант A): ключ начинается с `filter_criterion_id` — числового id "
    "конкретной ревизии строки вида, текущность читается витриной связкой по этому id, а "
    "каскад `filter_criterion_content_filter_criterion_id_fkey` снимает условие вместе с "
    "ревизией. Детей у вида два вида — формы и команды (замер 1.2: строк `Attribute`, "
    "`TabularSection`, `Template` этого вида в индексе состава нет ни в одной выгрузке); "
    "формы адресуются ИМЕНЕМ, команды — uuid, потому что uuid формы повторяется между "
    "конфигурациями (замер V51 3.2 — 42 349 общих uuid). Псевдо-записи индекса (модули, "
    "пары `.Form`, `Help`) детьми не являются и называются отдельным списком (Q7). Тела "
    "модулей вида узел НЕ читает: файлы названы дескрипторами, тексты принадлежат узлу V47 "
    "(Q8); ресурсы справки формы (`Ext/Help.xml`, каталог `Ext/Help/`) не хранятся — "
    "колонок под них в схеме нет, наличие называется наблюдениями `help_file` и "
    "`help_resources_dir` (Q7); тегов `Help`/`AdditionalIndexes` в `Properties` этого вида "
    "нет ни в одном файле круга (замер П2 — негативный факт держит проверка П6, а не "
    "константная колонка); определённых типов (`DefinedTypes`) в выгрузке вида нет "
    "(замер 2.4.4), узла для них нет"
)

# ── контракт стадии S4h (узел V53, шаг П4, позиция 2.8 списка) ───────────────────────
# Круг таблиц стадии и тексты контракта объявлены одним местом — по той же причине, что у
# V48, V49, V50, V51 и V52: текст незакрытой части ссылается на раздел, где читается отказ
# стадии, а держать два написания одного заголовка нельзя. Имена таблиц, каталог вида, метка
# метаданных и словари состояний приходят импортом из разбора
# (`src/configuration_event_subscriptions.py`) — второго перечня таблиц или состояний в проекте
# нет.
#
# Дефект, который закрывает эта константа, — тот же, что называли узлы V49, V50, V51 и V52:
# регистрация `event_subscriptions` в круге версионности (шаг П1) молча добавила бы её к кругу
# стадии S4, потому что `CHILD_TABLES` строится из `CONFIGURATION_VERSIONED_TABLES` минус
# `FOREIGN_STAGE_TABLES`, а стадия S4 снимала и анализировала бы чужие строки (замеры П0:
# 772 файла регистрации и 25 100 записей блока `<Source>` на четыре выгрузки).
#
# Групп `kinds` нет, поэтому константа называет только круг стадии — без `*_TABLES_BY_KIND`,
# которых у V51 восемь: строка источника неотделима от строки вида (Q4, вариант A), а таблиц
# детей у вида нет вовсе (замер 1.2: ни `Forms/`, ни `Templates/`, ни `Commands/`, ни `Ext/`
# ни в одной выгрузке), поэтому второй перечень тех же таблиц появился бы только ради того,
# чтобы разойтись с первым (прецедент V52).
EVENT_SUBSCRIPTIONS_TABLES: Tuple[str, ...] = (
    EVENT_SUBSCRIPTIONS_TABLE,
    EVENT_SUBSCRIPTION_SOURCES_TABLE,
)

# Круг снятия и перечень чисел ответа — ДВЕ таблицы. Отличия от V51 и V52 названы прямо: у
# плана обмена и критериев отбора круг снятия шире круга версионности, потому что строки детей
# (`forms`, `form_ext`, `commands`) снимает и пишет та же стадия предикатом по uuid родителей;
# у подписки на события детей нет (замер 1.2), поэтому два перечня совпадают, и нулевой ответ
# обещает ровно те же два ключа, что и ответ прогона.
#
# Порядок — порядок снятия, а не порядок версионности: `event_subscription_sources` первой,
# потому что её FK `event_subscription_sources_event_subscription_id_fkey` объявлен с
# `ON DELETE CASCADE` и каскад по строке вида снял бы записи молча, без точного счётчика (M7);
# строки вида последними, потому что на числовые id последних опираются строки блока
# `<Source>` (Q4, вариант A). Тот же приём, что `REMOVE_ORDER` узлов V49, V50, V51, V52.
EVENT_SUBSCRIPTIONS_REMOVE_ORDER: Tuple[str, ...] = (
    EVENT_SUBSCRIPTION_SOURCES_TABLE,
    EVENT_SUBSCRIPTIONS_TABLE,
)

EVENT_SUBSCRIPTIONS_SECTION_HEADER = "СВОЙСТВА ПОДПИСОК НА СОБЫТИЯ (узел V53, позиция 2.8)"

# Что обязан сказать ответ о повторе стадии. Отдельная точка входа группы —
# `load_event_subscriptions_tool` (шаг П5 узла, внесена в реестр сервера этим же шагом —
# `tools/check_mcp_tool_wiring.py` сторожит состав). П4 держит формулировку про слой
# `load_event_subscriptions`, потому что обещать инструмент, которого в реестре нет, — значит
# дать обещание, которое сервер не выполняет (прецеденты V48…V52).
EVENT_SUBSCRIPTIONS_REPEAT_HINT = (
    "Повторить стадию можно отдельным входом группы "
    "load_event_subscriptions_tool(source_path=…) без перезагрузки конфигурации "
    "(узел V53, шаг П5) либо полной перезагрузкой "
    "load_1c_catalog_tool(source_path=…, force=True)"
)

# Граница круга называется и при успехе: «строки записаны» не равно «о подписках на события
# сохранено всё». Формулировка держится замеров разделов 1–2 плана V53 и решений Q1…Q8: без
# неё голую ссылку `cfg:CatalogObject` читали бы как потерянное имя, пустой блок `<Source>` —
# как «целей нет», а состояние `unresolved` обработчика — как «модуля нет в конфигурации».
EVENT_SUBSCRIPTIONS_CIRCLE_BOUNDARY = (
    f"круг узла — файлы регистрации вида {EVENT_SUBSCRIPTION_META_TAG} из каталога "
    f"{EVENT_SUBSCRIPTIONS_DIR}/ (позиция 2.8 списка), подтверждённые записями индекса состава "
    "(две ноги, расхождения `index_only`/`file_only`/`uuid_mismatch` называются ответом); "
    f"в `event_subscriptions` идут 6 свойств файла регистрации (замер 2.0: ровно один набор "
    f"тегов на всех 772 файлах четырёх выгрузок), имя события с состоянием его известности "
    f"(словарь 18 имён замкнут корпусом и держит константа разбора, а не CHECK — Q6), "
    f"обработчик текстом и разложенным на модуль и метод с состоянием разрешения по общим "
    f"модулям текущей ревизии (Q2, решение оператора) и состояние блока <Source> с его "
    f"счётчиком; в `event_subscription_sources` — строки блока <Source> (25 100 записей на "
    f"четыре выгрузки: BGU2 11 706, BP3 13 379, KomMag 10, MinCfg 5; тег элемента — форма "
    f"перечня: Type 24 729 и TypeSet 371), где именованная цель `cfg:<Класс>.<Имя>` "
    f"(24 835) разрешается точным совпадением с индексом состава данной конфигурации, а голая "
    f"цель `cfg:<Класс>` (265) — присутствием вида метаданных: `type_present` 242 и "
    f"`type_absent` 23 называются прямо (M5, Q3 вариант A). Строка источника версионируется НЕ "
    f"своей цепью (Q4, вариант A): ключ начинается с `event_subscription_id` — числового id "
    f"конкретной ревизии строки вида, текущность читается витриной связкой по этому id, а "
    f"каскад `event_subscription_sources_event_subscription_id_fkey` снимает её вместе с "
    f"ревизией. Детей у вида НЕТ вовсе (замер 1.2: запись вида в `ConfigDumpInfo.xml` — "
    f"самозакрывающийся элемент, каталогов содержимого ноль), поэтому колонок "
    f"`children_state`/`form_names`/`command_uuids` в схеме нет осознанно (M2), а ровность "
    f"круга сторожит обход подкаталогов проверкой узла П6. Модулей вида узел НЕ читает: "
    f"тексты принадлежат узлу V47, а обработчик является ссылкой на общий модуль, чьи тексты "
    f"уже загружены (Q8); определённых типов (`DefinedTypes`) в выгрузке вида нет "
    f"(замер 2.4.4), узла для них нет; колонок слотов `Help`/`Interface` нет: соответствующих "
    f"тегов `Properties` в 772 файлах круга ноль (замер 2.0 — негативный факт держит "
    f"проверка П6, а не константная колонка)"
)

# ── контракт стадии S4i (узел V54, шаг П4, позиция 2.9 списка) ───────────────────────
# Круг таблиц стадии и тексты контракта объявлены одним местом — по той же причине, что у
# V48…V53: текст незакрытой части ссылается на раздел, где читается отказ стадии, а держать
# два написания одного заголовка нельзя. Имена двух таблиц, каталог вида, метка метаданных и
# словари состояний приходят импортом из разбора
# (`src/configuration_scheduled_jobs.py`) — второго перечня таблиц или состояний в проекте нет.
#
# Дефект, который закрывает эта константа, — тот же, что называли узлы V49…V53: регистрация
# `scheduled_jobs` в круге версионности (шаг П4, `CONFIGURATION_VERSIONED_TABLES`) молча
# добавила бы её к кругу стадии S4, потому что `CHILD_TABLES` строится из
# `CONFIGURATION_VERSIONED_TABLES` минус `FOREIGN_STAGE_TABLES`, а стадия S4 снимала и
# анализировала бы чужие строки (замеры П0: 346 файлов регистрации и 303 файла расписания на
# четыре выгрузки).
#
# Групп `kinds` нет, поэтому константа называет только круг стадии — без `*_TABLES_BY_KIND`,
# которых у V51 восемь: запись расписания неотделима от строки вида (Q5, вариант A по
# прецеденту Q8 узла V53), а порога цены, при котором круг стоило бы резать, замер не дал
# (весь круг — 346 файла регистрации и 313 записей расписания, максимум 3 записи в одном
# файле). Форм, макетов и команд у вида нет ни в одной выгрузке (замер 1.2), поэтому второго
# перечня общих таблиц детей здесь нет — в отличие от V51 и V52.
SCHEDULED_JOBS_TABLES: Tuple[str, ...] = (
    SCHEDULED_JOBS_TABLE,
    SCHEDULED_JOB_SCHEDULES_TABLE,
)

# Круг снятия и перечень чисел ответа — ДВЕ таблицы, и у этого узла они совпадают с кругом
# версионности: детей у вида нет (замер 1.2), поэтому нулевой ответ обещает ровно те же два
# ключа, что и ответ прогона (в отличие от V51/V52, где круг снятия шире).
#
# Порядок — порядок снятия, а не порядок версионности: `scheduled_job_schedules` первой,
# потому что её FK `scheduled_job_schedules_scheduled_job_id_fkey` объявлен с
# `ON DELETE CASCADE` и каскад по строке вида снял бы записи молча, без точного счётчика
# (мера M7 узла V53); строки вида последними, потому что на числовые id последних опираются
# строки расписания (Q2, вариант A). Тот же приём, что `REMOVE_ORDER` узлов V49…V53.
SCHEDULED_JOBS_REMOVE_ORDER: Tuple[str, ...] = (
    SCHEDULED_JOB_SCHEDULES_TABLE,
    SCHEDULED_JOBS_TABLE,
)

SCHEDULED_JOBS_SECTION_HEADER = "СВОЙСТВА РЕГЛАМЕНТНЫХ ЗАДАНИЙ (узел V54, позиция 2.9)"

# Расхождения ноги содержимого называются ТЕМИ ЖЕ ключами перечней, что даёт разбор
# (`schedule_index_only`/`schedule_file_only`/`schedule_uuid_mismatch` — имена списков
# `collect_scheduled_jobs`), и замыкаются этой константой одним местом: второго перечисления
# имён в контракте и в стадии быть не должно (прецедент `*_CIRCLE_DISCREPANCIES` разбора,
# которые сюда приходят импортом). Отличия от ноги вида два: имя состояния несёт вид ноги
# (у вида состояния общие для круга, у содержимого — свои, потому что файл `Ext/Schedule.xml`
# не является объектом метаданных и в перечень заголовка не входит), и сверка идёт ДВУМЯ
# ногами, а не тремя (замера объявления вида у содержимого нет).
SCHEDULED_JOB_CONTENT_DISCREPANCIES: Tuple[str, ...] = (
    "schedule_index_only",
    "schedule_file_only",
    "schedule_uuid_mismatch",
)

# Что обязан сказать ответ о повторе стадии. Отдельная точка входа группы —
# `load_scheduled_jobs_tool` (шаг П5 узла, внесена в реестр сервера этим же шагом —
# `tools/check_mcp_tool_wiring.py` сторожит состав). П4 держит формулировку про слой
# `load_scheduled_jobs`, потому что обещать инструмент, которого в реестре нет, — значит дать
# обещание, которое сервер не выполняет (прецеденты V48…V53).
SCHEDULED_JOBS_REPEAT_HINT = (
    "Повторить стадию можно отдельным входом группы "
    "load_scheduled_jobs_tool(source_path=…) без перезагрузки конфигурации "
    "(узел V54, шаг П5) либо полной перезагрузкой "
    "load_1c_catalog_tool(source_path=…, force=True)"
)

# Граница круга называется и при успехе: «строки записаны» не равно «о регламентных заданиях
# сохранено всё». Формулировка держится замеров разделов 1–2 плана V54 и решений Q1…Q8: без
# неё задание без расписания читали бы «записей потеряно», стражу `0001-01-01` — реальной
# датой начала, а пустой элемент `<ent:WeekDays/>` — «ни одного дня недели». Текст следует
# за константами круга, потому что ссылается на имена таблиц и каталога, импортированные из
# разбора (прецеденты V48…V53).
SCHEDULED_JOBS_CIRCLE_BOUNDARY = (
    f"круг узла — файлы регистрации вида {SCHEDULED_JOB_META_TAG} из каталога "
    f"{SCHEDULED_JOBS_DIR}/ (позиция 2.9 списка), подтверждённые записями индекса состава "
    "того же вида и перечнем заголовка `configurations.scheduled_jobs` (ТРИ ноги, расхождения "
    "`index_only`/`file_only`/`uuid_mismatch` называются ответом; нога содержимого "
    "`ScheduledJob.<Имя>.Schedule` сверяется отдельно — её расхождения "
    "`schedule_index_only`/`schedule_file_only`/`schedule_uuid_mismatch`); "
    f"в `{SCHEDULED_JOBS_TABLE}` идут 10 свойств файла регистрации (замер 2: ровно один "
    "набор тегов на всех 346 файлах четырёх выгрузок — MinCfg 2, KomMag 1, BGU2 157, "
    "BP3 186), обработчик `CommonModule.<Модуль>.<Метод>` текстом и разложенным на модуль и "
    "метод с состоянием разрешения по общим модулям текущей ревизии (Q3, вариант A: 344 "
    "различные пары при 346 строках — внешнего ключа нет) и состоянием объявления метода "
    "(Q8, вариант A: `text_unavailable` является границей базы, а не свойством выгрузки), а "
    f"также состояние содержимого с его счётчиком и состоянием двух ног; в "
    f"`{SCHEDULED_JOB_SCHEDULES_TABLE}` — строки расписания (313 записи на четыре выгрузки: "
    "MinCfg 5, KomMag 1, BGU2 143, BP3 164; корневая `<Schedule>` 303 и вложенная "
    "`<ent:DetailedDailySchedules>` 10 в шести файлах, глубина ровно 2 — M6), где 12 "
    "типизированных атрибутов держат значения колонками `date`/`time`/`integer`, а "
    "значения-стражи платформенных типов `0001-01-01` и `00:00:00` в эти колонки НЕ "
    "пишутся: они называются состоянием `sentinel` (замер 2.2: sentinel 1441, zero 1449, "
    "set 866 — Q4, вариант A), и два набора целых `WeekDays` (1..7) и `Months` (1..12), "
    "пустой элемент которых означает «все дни/все месяцы» и является состоянием "
    "`empty_element_all`, а не пустым перечнем (по 23 таких элемента на каждый из двух "
    "наборов: 13 корневых и 10 вложенных записей — M5). Строка расписания "
    "версионируется НЕ своей цепью (Q2, вариант A): ключ начинается с `scheduled_job_id` — "
    "числового id конкретной ревизии строки вида, текущность читается витриной связкой по "
    "этому id, а каскад `scheduled_job_schedules_scheduled_job_id_fkey` снимает её вместе с "
    "ревизией; вложенная запись отдельной таблицы не имеет (Q1, вариант A) — её родитель "
    "адресуется колонкой `parent_id` той же таблицы, а композитная ссылка "
    "`scheduled_job_schedules_parent_same_job` запрещает родителем запись другого задания. У "
    "43 заданий (BGU2 19, BP3 24) расписания нет ни файлом, ни индексом — это состояние "
    "`absent` колонки `schedule_state`, а не ноль записей (M4). Форм, макетов, команд, "
    "модулей и каталога справки у вида НЕТ ни в одной выгрузке (замер 1.2), поэтому колонок "
    "`children_state`/`form_names`/`command_uuids` в схеме нет осознанно, а блок "
    "`<ChildObjects>` пуст во всех 346 файлах — его непустая форма называется наблюдением "
    "`child_objects_block`. Элемент `DayTimes` корпусом не давался ни разу (313/313 "
    "`absent`), колонки под него нет, а его появление называется наблюдением "
    "`day_times_present` (граница раздела 8 плана). Тексты модулей вид не читает: у него их "
    "нет, а метод обработчика является ссылкой на общий модуль, чьи тексты пишут узлы V46/V47; "
    "определённых типов (`DefinedTypes`) в выгрузке нет (замер 2.4.4), узла для них нет"
)

# ── контракт стадии S4j (узел V55, шаг П4, позиция 2.10 списка) ───────────────────────
# Круг таблиц стадии и тексты контракта объявлены одним местом — по той же причине, что у
# V48…V54: текст незакрытой части ссылается на раздел, где читается отказ стадии, а держать
# два написания одного заголовка нельзя. Имя таблицы, каталог вида, метка метаданных и
# словари состояний приходят импортом из разбора (`src/configuration_bots.py`) — второго
# перечня таблиц или состояний в проекте нет.
#
# Дефект, который закрывает эта константа, — тот же, что называли узлы V49…V54: регистрация
# `bots` в круге версионности (шаг П4, `CONFIGURATION_VERSIONED_TABLES`) молча добавила бы
# её к кругу стадии S4, потому что `CHILD_TABLES` строится из
# `CONFIGURATION_VERSIONED_TABLES` минус `FOREIGN_STAGE_TABLES`, а стадия S4 снимала и
# анализировала бы чужие строки (замер 1.1: 2 файла регистрации и 2 файла модулей у MinCfg).
#
# Таблиц детей у вида нет, и это названо, а не обойено: форм, макетов и команд у вида нет ни
# файлами, ни строками индекса состава (замер 1.2), а единственный ребёнок вида в индексе
# состава (`Bot.<Имя>.Module`) отдельной таблицы не имеет осознанно — его состояние и
# дескрипторы являются колонками строки вида (Q1, вариант A: кратность ровно одна на
# объект), а тексты пишет узел V47 в `bsl_modules` (мера M5: стадия V55 их не читает и не
# снимает). Поэтому круг стадии — ОДНА таблица, а `BOTS_REMOVE_ORDER` совпадает с кругом
# версионности: нулевой ответ обещает ровно тот же ключ, что и ответ прогона (в отличие от
# V51/V52/V54, где круг снятия шире).
BOTS_TABLES: Tuple[str, ...] = (BOTS_TABLE,)

# Порядок снятия здесь совпадает с порядком записи: таблица одна, каскадных внешних ключей
# в неё нет (прецедент V20.1 — внешний ключ на заголовок конфигурации не ставится
# осознанно), поэтому снятие держится явным `DELETE` по `configuration_uuid`.
BOTS_REMOVE_ORDER: Tuple[str, ...] = (BOTS_TABLE,)

BOTS_SECTION_HEADER = "СВОЙСТВА БОТОВ КОНФИГУРАЦИИ (узел V55, позиция 2.10)"

# Что обязан сказать ответ о повторе стадии. Отдельная точка входа группы —
# `load_bots_tool` (шаг П5 узла, внесена в реестр сервера этим же шагом —
# `tools/check_mcp_tool_wiring.py` сторожит состав). П4 держит формулировку про слой
# `load_bots`, потому что обещать инструмент, которого в реестре нет, — значит дать
# обещание, которое сервер не выполняет (прецеденты V48…V54).
BOTS_REPEAT_HINT = (
    "Повторить стадию можно отдельным входом группы load_bots_tool(source_path=…) без "
    "перезагрузки конфигурации (узел V55, шаг П5) либо полной перезагрузкой "
    "load_1c_catalog_tool(source_path=…, force=True)"
)

# Граница круга называется и при успехе: «строки записаны» не равно «о ботах сохранено всё».
# Формулировка держится замеров разделов 1–2 плана V55 и решения Q1 (вариант A): без неё
# ссылку `StdPicture.*` читали бы как неразрешённую, отсутствие индекса состава — как
# «объектов нет», а незнакомый тег — как потерянное свойство. Текст следует за константами
# круга, потому что ссылается на имена таблицы и каталога, импортированные из разбора
# (прецеденты V48…V54).
BOTS_CIRCLE_BOUNDARY = (
    f"круг узла — файлы регистрации вида {BOTS_META_TAG} из каталога {BOTS_DIR}/ "
    "(позиция 2.10 списка), подтверждённые записями индекса состава того же вида "
    "(`Bot.<Имя>`) и перечнем заголовка `configurations.bots` (ТРИ ноги, расхождения "
    "`index_only`/`file_only`/`uuid_mismatch` называются ответом; нога перечня заголовка "
    "стадией не перезаписывается и сверяется проверкой узла); "
    f"в `{BOTS_TABLE}` идут пять свойств файла регистрации (`Name`, `Synonym`, `Comment`, "
    "`Predefined`, `Picture`) строговыми колонками и состояние разбора "
    "`properties_state` с перечнем незнакомых тегов `unknown_property_names` (Q1 — решение "
    "оператора, вариант A: корпус словарь не замыкает — 2 файла одной выгрузки, XSD вида "
    "нет, поэтому незнакомый тег называется, а не отвергается записью), ссылку `Picture` "
    "двумя разными адресами (`picture_ref` как в выгрузке и `picture_full_name` "
    "нормализованный) с классом цели и состоянием разрешения: `CommonPicture.*` разрешается "
    "индексом состава этой конфигурации, `StdPicture.*` индексом не разрешается НИКОГДА и "
    "не является неразрешённой ссылкой (замер 2.1: 1 + 1 на двух файлах); дескрипторы "
    "модуля вида (`module_state` по двум ногам — файл `Bots/<Имя>/Ext/Module.bsl` и запись "
    "индекса `Bot.<Имя>.Module`, плюс путь и размер) и признак `module_loaded` по строкам "
    "`bsl_modules`, которые пишет узел V47 (Q4, вариант A: текстов стадия V55 не читает и "
    "не снимает — мера M5). Корпус вида даёт ТОЛЬКО MinCfg: 2 файла регистрации и 2 файла "
    "модулей; у KomMag, BGU2 и BP3 вида нет ни файлами, ни строками индекса (замер 1.1) — "
    "отсутствие каталога является наблюдением `directory_missing`, а не нулём строк (Q9, "
    "вариант A). Форм, макетов и команд у вида нет ни в одной выгрузке (замер 1.2), поэтому "
    "колонок под них и общих таблиц детей у узла нет осознанно. Определённых типов "
    "(`DefinedTypes`) в выгрузке вида нет (замер 2.4.4), узла для них нет"
)

# ── контракт стадии S4k (узел V56, шаг П5, позиция 2.11 списка) ───────────────────────
# Круг таблиц стадии и тексты контракта объявлены одним местом — по той же причине, что у
# V48…V55: текст незакрытой части ссылается на раздел, где читается отказ стадии, а держать
# два написания одного заголовка нельзя. Имя каталога, имена двух таблиц вида, метка
# метаданных, словари состояний и ключи сводки приходят импортом из разбора
# (`src/configuration_functional_options.py`) — второго перечня таблиц или состояний в проекте
# нет.
#
# Дефект, который закрывает эта константа, — тот же, что называли узлы V49…V55: таблица
# `functional_options` зарегистрирована в круге версионности шагами П1/П4
# (`CONFIGURATION_VERSIONED_TABLES`, src/current_revision.py), а `CHILD_TABLES` строится из
# `CONFIGURATION_VERSIONED_TABLES` минус `FOREIGN_STAGE_TABLES` — без этой константы стадия S4
# снимала и анализировала бы 765 строк чужого вида (замер 1.1 плана V56).
#
# Круг стадии — ДВЕ таблицы, а не одна: строка опции и строки её перечня `<Content>`
# (Q1, вариант A, прецедент V50). Разрыв круга назван решениями узла: строка применения не
# существует без строки опции — её FK
# `functional_option_content_functional_option_id_fkey` объявлен с `ON DELETE CASCADE`, — а
# строка опции пишется и с пустым перечнем: пустой перечень является состоянием
# `empty_content` строки вида, а не отсутствием строк применения (замер 2.2: 203 файла из 765
# дают пустой перечень). Таблиц детей у вида нет, и это названо, а не обойено: форм, макетов,
# команд и модулей у вида нет ни файлами, ни строками индекса состава (замер 1.2 — записей
# индекса ровно по числу файлов, псевдозаписей и блока `ChildObjects` ноль), поэтому общими
# таблицами `forms`/`form_ext`/`commands`/`templates` круг не расширяется — как у V50, V53,
# V54, V55.
FUNCTIONAL_OPTIONS_TABLES: Tuple[str, ...] = (
    FUNCTIONAL_OPTIONS_TABLE, FUNCTIONAL_OPTION_CONTENT_TABLE,
)

# Порядок снятия круга — НЕ порядок `FUNCTIONAL_OPTIONS_TABLES`:
# `functional_option_content.functional_option_id` ссылается на строку опции с
# `ON DELETE CASCADE`, и каскад снял бы применение молча, без точного счётчика (M7). Явный
# `DELETE` первым держит честное число снятых строк и не зависит от того, поставлен ли каскад
# в данной базе (миграция V56 могла не применяться). Тот же приём, что `REMOVE_ORDER` узлов
# V50 (`common_attribute_targets`), V52 (`filter_criterion_content`) и V54.
FUNCTIONAL_OPTIONS_REMOVE_ORDER: Tuple[str, ...] = (
    FUNCTIONAL_OPTION_CONTENT_TABLE, FUNCTIONAL_OPTIONS_TABLE,
)

FUNCTIONAL_OPTIONS_SECTION_HEADER = (
    "СВОЙСТВА ФУНКЦИОНАЛЬНЫХ ОПЦИЙ КОНФИГУРАЦИИ (узел V56, позиция 2.11)"
)

# Что обязан сказать ответ о повторе стадии. Отдельная точка входа группы —
# `load_functional_options_tool` (шаг П5 узла, внесена в реестр сервера этим же шагом —
# `tools/check_mcp_tool_wiring.py` сторожит состав). Обещать инструмент, которого в реестре
# нет, — значит дать обещание, которое сервер не выполняет, поэтому ключ словаря, ветка
# `stage_resume_hint`, текст подсказки и запись реестра вносятся одним шагом (прецеденты
# V48…V55, урок П8 узлов V51–V54).
FUNCTIONAL_OPTIONS_REPEAT_HINT = (
    "Повторить стадию можно отдельным входом группы "
    "load_functional_options_tool(source_path=…) без перезагрузки конфигурации "
    "(узел V56, шаг П5) либо полной перезагрузкой "
    "load_1c_catalog_tool(source_path=…, force=True)"
)

# Граница круга называется и при успехе: «строки записаны» не равно «о функциональных опциях
# сохранено всё». Формулировка держится замеров разделов 1–2 плана V56 и решений Q1–Q4
# (вариант A): без неё цели перечня читались бы объектами, которых «нет», отсутствие каталога
# вида — нулём строк вместо ответа о выгрузке (так даёт KomMag), а незнакомый тег файла —
# потерянным свойством. Текст следует за константами круга, потому что ссылается на имена
# таблицы и каталога, импортированные из разбора (прецеденты V48…V55).
FUNCTIONAL_OPTIONS_CIRCLE_BOUNDARY = (
    f"круг узла — файлы регистрации вида {FUNCTIONAL_OPTIONS_META_TAG} из каталога "
    f"{FUNCTIONAL_OPTIONS_DIR}/ (позиция 2.11 списка), подтверждённые записями индекса "
    "состава того же вида (`FunctionalOption.<Имя>`) и перечнем заголовка "
    "`configurations.functional_options` (ТРИ ноги круга, расхождения "
    "`index_only`/`file_only`/`uuid_mismatch` называются ответом; нога перечня заголовка "
    "стадией не перезаписывается и сверяется проверкой узла); в "
    f"`{FUNCTIONAL_OPTIONS_TABLE}` идут шесть свойств файла регистрации (`Name`, `Synonym`, "
    "`Comment`, `Location`, `PrivilegedGetMode`, `Content`) колонками и состояние разбора "
    "`properties_state` с перечнем незнакомых тегов `unknown_property_names` (Q7 — решение "
    "оператора, вариант A по прецеденту узла V50: XSD вида нет, корпус словарь не замыкает, "
    "поэтому незнакомый тег называется, а не отвергается записью), ссылка `Location` двумя "
    "адресами (`location_ref` как в выгрузке и `location_full_name` нормализованный) с "
    "формой адреса `location_target_form` (`single` — значение константы, 605; "
    "`register_resource` — ресурс регистра сведений, 154; `attribute` — реквизит справочника, "
    "6 — замер 2.1) и состоянием разрешения индексом состава: по корпусу `exact` 765 из 765, "
    "потому что индекс держит псевдозаписи колонок (замер 2.1, правило V43 — повторный разбор "
    "`ConfigDumpInfo.xml` вторым источником не становится); в "
    f"`{FUNCTIONAL_OPTION_CONTENT_TABLE}` идут строки перечня `<Content>` — цель, её вид, "
    "ссылка на запись индекса, порядок в файле и состояние разрешения (10 063 цели на корпус, "
    "21 вид целей, `exact` 10 063 из 10 063, максимум 438 целей в одном файле — замер 2.2); "
    "внешних ключей на цели нет осознанно (Q3, вариант A по прецедентам Q3 узлов V50, V52, "
    "V53, V55): слои констант, регистров сведений и справочников (группа A модели V38) этой "
    "позицией не загружаются, поэтому цель называется состоянием, а не фактом существования. "
    "Форм, макетов, команд и модулей у вида нет ни в одной выгрузке (замер 1.2), поэтому "
    "колонок под них и общих таблиц детей у узла нет осознанно; каталог вида плоский — "
    "появление подкаталога или файла не-XML называется наблюдениями `unexpected_dir`/"
    "`unexpected_file`. Вид существует в трёх выгрузках корпуса из четырёх: у KomMag каталога "
    "нет ни файлами, ни строками индекса (замер 1.1) — отсутствие каталога является "
    "наблюдением `directory_missing`, а не нулём строк (Q9, вариант A). Определённых типов "
    "(`DefinedTypes`) в выгрузке вида нет (замер 2.4.4 плана V56), узла для них нет"
)

# ── круг стадии S4l (узел V57, шаги П4–П5, позиция 2.12 списка) ───────────────────────
# Круг таблиц был объявлен раньше стадии (шаг П4), потому что таблица
# `functional_option_parameters` зарегистрирована в круге версионности тем же шагом
# (`CONFIGURATION_VERSIONED_TABLES`, src/current_revision.py), а `CHILD_TABLES` строится из
# `CONFIGURATION_VERSIONED_TABLES` минус `FOREIGN_STAGE_TABLES` — без этой константы стадия S4
# снимала и анализировала бы чужие строки вида и его применения (замер 1.1 плана V57: 14
# файлов регистрации и 34 цели применения на корпус; `_v46_p4_writer_probe.py` падает на
# `KeyError` по той же причине, что падал на `filter_criteria` у V52). Тот же приём, что у
# записей V49, V50, V52, V54, V55, V56. С шага П5 круг стоит ДО текстов стадии и до
# `STORED_META_KINDS`: запись вида в этом словаре ссылается на `*_TABLES`, а порядок
# определений модуля определяет и то, что имя уже связано (прецедент V56, где
# `FUNCTIONAL_OPTIONS_TABLES` тоже объявлен до текста карточки).
#
# Круг — ДВЕ таблицы, а не одна (Q1, вариант A — решение оператора; прецедент V50/V56):
# строка применения не существует без строки вида — её FK
# `functional_option_parameter_targets_parameter_fkey` объявлен с `ON DELETE CASCADE`, — а
# строка вида пишется и с пустым перечнем `<Use>`: пустой перечень является состоянием
# `empty_content` строки вида, а не отсутствием строк применения (замер 2.1: пустых перечней
# корпус не давал, состояние в словаре есть). Таблиц детей у вида нет, и это названо, а не
# обойено: форм, макетов, команд и модулей у вида нет ни файлами, ни строками индекса состава
# (замер 1.2 — записей индекса ровно по числу файлов, псевдозаписей и каталогов содержимого
# ноль), поэтому общими таблицами `forms`/`form_ext`/`commands`/`templates` круг не
# расширяется — как у V50, V53, V54, V55, V56.
FUNCTIONAL_OPTION_PARAMETERS_TABLES: Tuple[str, ...] = (
    FUNCTIONAL_OPTION_PARAMETERS_TABLE, FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE,
)

# Порядок снятия круга — НЕ порядок `FUNCTIONAL_OPTION_PARAMETERS_TABLES`:
# `functional_option_parameter_targets.functional_option_parameter_id` ссылается на строку вида
# с `ON DELETE CASCADE`, и каскад снял бы применение молча, без точного счётчика (M7). Явный
# `DELETE` первым держит честное число снятых строк и не зависит от того, поставлен ли каскад
# в данной базе (миграция V57 могла не применяться). Тот же приём, что `REMOVE_ORDER` узлов
# V50, V52, V54, V56.
FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER: Tuple[str, ...] = (
    FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE, FUNCTIONAL_OPTION_PARAMETERS_TABLE,
)

# ── тексты стадии S4l (узел V57, шаг П5, позиция 2.12 списка) ──────────────────────────
# Заголовок раздела, подсказка о повторе и граница круга объявлены ДО `CHILD_NOT_IMPLEMENTED`
# и ДО констант круга S4l: текст незакрытой части ссылается на раздел, где читается отказ
# стадии, а держать два написания одного заголовка нельзя (прецеденты V48…V56). Имена каталога,
# двух таблиц вида и метки метаданных приходят импортом из разбора — второго перечня в проекте
# нет. Граница называется и при успехе: «строки записаны» не равно «о параметрах функциональных
# опций сохранено всё».
FUNCTIONAL_OPTIONS_PARAMETERS_SECTION_HEADER = (
    "СВОЙСТВА ПАРАМЕТРОВ ФУНКЦИОНАЛЬНЫХ ОПЦИЙ КОНФИГУРАЦИИ (узел V57, позиция 2.12)"
)

# Что обязан сказать ответ о повторе стадии. Отдельная точка входа группы —
# `load_functional_options_parameters_tool` (шаг П5 узла, внесена в реестр сервера этим же
# шагом — `tools/check_mcp_tool_wiring.py` сторожит состав). Обещать инструмент, которого в
# реестре нет, — значит дать обещание, которое сервер не выполняет, поэтому ключ словаря,
# ветка `stage_resume_hint`, текст подсказки и запись реестра вносятся одним шагом (прецеденты
# V48…V56, урок П8 узлов V51–V56).
FUNCTIONAL_OPTIONS_PARAMETERS_REPEAT_HINT = (
    "Повторить стадию можно отдельным входом группы "
    "load_functional_options_parameters_tool(source_path=…) без перезагрузки конфигурации "
    "(узел V57, шаг П5) либо полной перезагрузкой "
    "load_1c_catalog_tool(source_path=…, force=True)"
)

# Граница круга держится замеров разделов 1–2 плана V57 и решений Q1–Q3, Q7, Q9. Отличие от
# круга 2.11 называется прямо: у параметра функциональной опции нет ссылки `Location` — есть
# только перечень применения `<Use>`, и его цели ведут на объекты ДРУГИХ видов метаданных
# (измерения регистров, реквизиты справочников), поэтому разрешение идёт по всем строкам
# индекса состава этой конфигурации, а не по строкам своего вида.
FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_BOUNDARY = (
    f"круг узла — файлы регистрации вида {FUNCTIONAL_OPTIONS_PARAMETERS_META_TAG} из каталога "
    f"{FUNCTIONAL_OPTIONS_PARAMETERS_DIR}/ (позиция 2.12 списка), подтверждённые записями "
    "индекса состава того же вида (`FunctionalOptionsParameter.<Имя>`) и перечнем заголовка "
    "`configurations.functional_options_parameters` (ТРИ ноги круга, расхождения "
    "`index_only`/`file_only`/`uuid_mismatch` называются ответом; нога перечня заголовка "
    "стадией не перезаписывается и сверяется проверкой узла). Сверка круга ведётся точным "
    "совпадением `object_type`, а не началом имени: рядом стоит вид "
    "`FunctionalOption` (2.11), имена которого начинаются с той же строки (замер 1.2); "
    f"в `{FUNCTIONAL_OPTION_PARAMETERS_TABLE}` идут четыре свойства файла регистрации "
    "(`Name`, `Synonym`, `Comment`, `Use`) колонками `object_name`/`full_name`, `synonym` "
    "(jsonb-карта языков) и `comment`, состояние разбора `properties_state` с перечнем "
    "незнакомых тегов `unknown_property_names` (Q7, вариант A по прецеденту узла V50: XSD "
    "вида нет, корпус 14 файлов словарь не замыкает, поэтому незнакомое называется, а не "
    "отвергается записью) и состояние перечня `use_state` со счётчиком `targets_count`; "
    f"в `{FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE}` идут строки перечня `<Use>` — порядок "
    "в файле, имя элемента как в выгрузке (`Item`, 34 из 34), значение атрибута `xsi:type` "
    "и его состояние (`md_object_ref`/`other_form`/`absent`), полный адрес цели, вид цели по "
    "первому сегменту и ФОРМА адреса цели (`object` — значение привязано к объекту целиком, "
    "`dimension`/`register_resource`/`attribute`/`tabular_section` — к его срезу), ссылка на "
    "строку индекса состава и состояние разрешения (34 цели на корпус, все `exact`, максимум "
    "20 целей у одного параметра — замер 2.1). Ссылки `Location` у вида нет — в отличие от "
    "круга 2.11 (замер 2 плана), поэтому колонок адреса носителя у узла нет осознанно, а "
    "состояний `location_*` в контракте нет. Внешних ключей на цели нет осознанно (Q3, "
    "вариант A по прецедентам Q3 узлов V50, V52, V53, V55, V56): слои регистров сведений, "
    "справочников и прочих видов (группы A–H модели V38) этой позицией не загружаются, "
    "поэтому цель называется состоянием, а не фактом существования. Форм, макетов, команд, "
    "модулей и каталогов содержимого у вида нет ни в одной выгрузке (замер 1.2), поэтому "
    "общих таблиц детей у узла нет осознанно; каталог вида плоский — появление подкаталога "
    "или файла не-XML называется наблюдениями `unexpected_dir`/`unexpected_file`. Вид "
    "существует в трёх выгрузках корпуса из четырёх: MinCfg 2 файла, BGU2 5, BP3 7, у KomMag "
    "каталога нет ни файлами, ни строками индекса (замер 1.1) — отсутствие каталога "
    "является наблюдением `directory_missing`, а не нулём строк (Q9, вариант A). Пустого "
    "перечня `<Use>` корпус не давал ни разу (замер 2.1: 0 `empty_content`), но состояние "
    "в словаре держится: пустой перечень читается состоянием строки вида, а не отсутствием "
    "строк в таблице применения (Q1, вариант A). Определённых типов (`DefinedTypes`, "
    "позиция 2.13) в выгрузке вида нет (замер 1.2), узла для них нет"
)


# ── узел V58 (стадия S4m, позиция 2.13 нормативного списка) ──────────────────────────
# Круг таблиц стадии объявлен ДО текстов карточки и ДО `STORED_META_KINDS` — тот же порядок,
# что у записей V49…V57: `defined_types` зарегистрирована в круге версионности тем же шагом
# (`CONFIGURATION_VERSIONED_TABLES`, src/current_revision.py), а `CHILD_TABLES` строится из
# `CONFIGURATION_VERSIONED_TABLES` минус `FOREIGN_STAGE_TABLES` — без этой константы стадия S4
# снимала и анализировала бы 820 строк чужого вида (замеры 1.1 плана V58: 2 / 1 / 304 / 513
# файлов регистрации во всех четырёх выгрузках). Тот же приём, что у записей V48…V57.
#
# Круг — ОДНА таблица, и это решение, а не упущение (Q1, вариант A — решение оператора от
# 05.11.2026 по прецедентам `session_parameters` V48, `common_attributes` V50,
# `filter_criteria` V52): блок `<Type>` — единственное содержательное свойство вида
# (820/820 файлов несут его, замер 2.1), и он хранится колонками строки вида
# (`type_raw`/`types`/`type_multiplicity`/`type_parse_state`/`type_qualifiers`). Второй
# таблицы `defined_type_values` узел не заводит: строка значения существовала бы только через
# id строки вида, а обратный запрос («в каких определяемых типах встречается цель
# `Catalog.X`») читается containment-оператором по `types` — GIN-индексом
# `idx_defined_types_types_gin` (тот же приём, что V48/V50/V52). Порога цены, при котором
# круг стоило бы резать, замер 2.2 не дал (максимум 657 значений в файле, 17 544 на круг).
# Таблиц детей у вида нет, и это названо, а не обойено: форм, макетов, команд, модулей и
# каталогов содержимого у него нет ни файлами, ни строками индекса состава (замер 1.2 —
# записей индекса ровно по числу файлов, псевдозаписей ноль), поэтому общими таблицами
# `forms`/`form_ext`/`commands`/`templates`/`bsl_modules` круг не расширяется — как у V50,
# V53, V54, V55, V56, V57.
DEFINED_TYPES_TABLES: Tuple[str, ...] = (DEFINED_TYPES_TABLE,)

# Порядок снятия круга совпадает с кругом: таблицы детей и каскадных внешних ключей у вида нет,
# поэтому порядка «сначала дети» (мера M7 узлов V50, V52, V53, V54, V56) здесь держать нечего,
# и снятое число не может разойтись с каскадом. Константа заведена осознанно: ответ стадии
# обязан называть круг снятия списком таблиц, а не одним числом (прецедент `BOTS_TABLES` V55).
DEFINED_TYPES_REMOVE_ORDER: Tuple[str, ...] = (DEFINED_TYPES_TABLE,)


# ── тексты стадии S4m (узел V58, шаг П5, позиция 2.13 списка) ─────────────────────────
# Заголовок раздела, подсказка о повторе и граница круга объявлены ДО `CHILD_NOT_IMPLEMENTED`
# и ДО констант круга: текст незакрытой части ссылается на раздел, где читается отказ стадии,
# а держать два написания одного заголовка нельзя (прецеденты V48…V57). Имена каталога,
# таблицы вида и метки метаданных приходят импортом из разбора — второго перечня в проекте нет.
# Граница называется и при успехе: «строки записаны» не равно «об определяемых типах сохранено
# всё».
DEFINED_TYPES_SECTION_HEADER = (
    "СВОЙСТВА ОПРЕДЕЛЯЕМЫХ ТИПОВ КОНФИГУРАЦИИ (узел V58, позиция 2.13)"
)

# Что обязан сказать ответ о повторе стадии. Отдельная точка входа группы —
# `load_defined_types_tool` (шаг П5 узла, внесена в реестр сервера этим же шагом —
# `tools/check_mcp_tool_wiring.py` сторожит состав). Обещать инструмент, которого в реестре
# нет, — значит дать обещание, которое сервер не выполняет (прецеденты V48…V57, урок П8
# узлов V51–V57).
DEFINED_TYPES_REPEAT_HINT = (
    "Повторить стадию можно отдельным входом группы "
    "load_defined_types_tool(source_path=…) без перезагрузки конфигурации "
    "(узел V58, шаг П5) либо полной перезагрузкой "
    "load_1c_catalog_tool(source_path=…, force=True)"
)

# Граница круга держится замеров разделов 1–2 плана V58 и решений Q1–Q4, Q6, Q7. Отличие от
# узлов V48/V50/V52 называется прямо: те узлы встречали значение `cfg:DefinedType.*` в чужих
# блоках `<Type>` и оставляли его классом `defined_type_ref` без ключей цели, потому что вида
# в выгрузке не было (замер V48 2.4.4); узел V58 загружает сам вид, а чужие слои не
# переразрешает (мера M5, Q3).
DEFINED_TYPES_CIRCLE_BOUNDARY = (
    f"круг узла — файлы регистрации вида {DEFINED_TYPES_META_TAG} из каталога "
    f"{DEFINED_TYPES_DIR}/ (позиция 2.13 списка), подтверждённые записями индекса состава "
    "того же вида (`DefinedType.<Имя>`) и перечнем заголовка "
    "`configurations.defined_types` (ТРИ ноги круга, расхождения "
    "`index_only`/`file_only`/`uuid_mismatch` называются ответом; нога перечня заголовка "
    "стадией не перезаписывается и сверяется проверкой узла). Вид есть во всех четырёх "
    "выгрузках эталонного набора — 2 / 1 / 304 / 513 файла регистрации, и записей индекса "
    "ровно по числу файлов с совпадающими `uuid` (замеры 1.1, 1.2): расхождений круга нет, и "
    "нули названы числом, а не молчанием. Случай «каталога вида нет» корпусом не дан — он "
    "проверяется фикстурой постоянной проверки узла, а не наблюдением этой выгрузки. "
    f"В `{DEFINED_TYPES_TABLE}` идут четыре свойства файла регистрации (`Name`, `Synonym`, "
    "`Comment`, `Type`) колонками `object_name`/`full_name`, `synonym` (jsonb-карта языков) "
    "и `comment`, состояние разбора `properties_state` с перечнем незнакомых тегов "
    "`unknown_property_names` (Q7, вариант A по прецеденту узла V50: XSD вида нет, корпус 820 "
    "файлов словарь не замыкает, поэтому незнакомое называется, а не отвергается записью), "
    "блок `InternalInfo` четырьмя значениями (`generated_name`, `type_category`, `type_id`, "
    "`value_id`) с состоянием `internal_info_state` (Q4 — значения хранятся, потому что "
    "связывают имя вида с идентификатором из разбора бинарных внешних объектов, узел V25; "
    "ключом они не становятся — 1154 различных идентификатора на 1640 слотов, замер 1.3), и "
    "блок `<Type>` колонками `type_raw`/`types`/`type_multiplicity`/`type_parse_state`/"
    "`type_qualifiers` (Q1, вариант A — второй таблицы нет). Классы значений замкнуты "
    "словарём слоя и отличаются от словаря V48/V50/V52 (Q3): `ref_value` 11 385, "
    "`object_value` 4 906, `record_set` 950, `value_manager` 106, `primitive` 197 на 17 544 "
    "значения (замер 2.3). Разрешение цели значения идёт по СТРОКАМ ИНДЕКСА состава этой "
    "конфигурации (правило V43): `exact` 17 341, `no_target` 197 (примитивы `xs:*`), "
    "`unresolved` 6 (все шесть — `BusinessProcessRoutePoint.*`, вида нет в индексе состава — "
    "замер 2.5, развилка Q6). Адрес выводится из ФОРМЫ значения срезом суффикса `RecordSet`/"
    "`ValueManager`/`Object`/`Ref`, поэтому 2 419 выведенных адресов и 2 413 разрешённых — "
    "два разных числа, и оба называются (раздел 2.5). Внешних ключей на цели нет осознанно "
    "(Q3, вариант A по прецедентам Q3 узлов V50, V52, V53, V55, V56): слои справочников, "
    "регистров и прочих видов (группы A–H модели V38) этой позицией не загружаются, поэтому "
    "цель называется состоянием, а не фактом существования. Форм, макетов, команд, модулей и "
    "каталогов содержимого у вида нет ни в одной выгрузке (замер 1.2), поэтому общих таблиц "
    "детей у узла нет осознанно, а тексты `bsl_modules` (узел V47) стадия не читает и не "
    "снимает (мера M5); каталог вида плоский — появление подкаталога или файла не-XML "
    "называется наблюдениями `unexpected_dir`/`unexpected_file`. Пустого блока `<Type>` и "
    "пустых блоков квалификаторов корпус не давал ни разу (замеры 2.1, 2.2), но состояния "
    "`absent` и `empty_value` в словарях держатся границей разбора. Пустой блок "
    "квалификаторов состоянием строки не становится и называется наблюдением "
    "`empty_qualifier_block` (прецедент `DayTimes` узла V54); контейнер `<v8:TypeSet>` "
    "корпусом не дан (0 файлов, M4) и называется наблюдением `type_set_container`"
)

# Что из содержимого дочерних объектов стадия S4 НЕ загружает — определение перенесено
# в это место узлом V50 (шаг П8): текст ссылается на заголовок раздела S4e, объявленного
# рядом с кругом таблиц вида, поэтому заголовок обязан идти раньше текста (прецедент
# V48/V49). Узел V51 (шаг П8) добавляет в перечень закрытых видов позицию 2.6 — планы
# обмена:
# без строки текст обещал бы, что реквизиты, формы и макеты не загружены вовсе, хотя для
# вида 2.6 они загружены (наблюдение П8, исправлено этим же шагом). Узел V52 (шаг П4)
# закрывает позицию 2.7 — критерии отбора: без строки текст обещал бы то же самое про вид,
# для которого закрыты его свойства, блок `<Type>`, перечень `<Content>`, его формы и его
# команды. Узел V53 (шаг П4) закрывает позицию 2.8 — подписки на события: без строки текст
# обещал бы то же самое про вид, для которого закрыты его свойства и круг целей срабатывания
# блока `<Source>`; детей у этого вида нет ни в одной выгрузке (замер 1.2), поэтому фраза про
# формы, макеты и модулей детей к нему не относится. Узел V54 (шаг П5) закрывает позицию 2.9 —
# регламентные задания: без строки текст обещал бы то же самое про вид, для которого закрыты его
# свойства файла регистрации, записи расписания `<ent:*>` и разрешение обработчика `MethodName`;
# форм, макетов, команд и модулей у вида нет ни в одной выгрузке (замер 1.2), поэтому фраза про
# детей к нему тоже не относится. Обоснование того,
# почему часть групп модели V38 остаётся незакрытой, держится у стадии S4 — см. комментарий
# перед местом, откуда сделан перенос.
CHILD_NOT_IMPLEMENTED = (
    "содержимое дочерних объектов загружено частично: закрыты свойства подсистем и общих "
    "модулей (узел V46, по модели V38 — часть групп B и E), свойства параметров сеанса — "
    "позиция 2.3 нормативного списка (узел V48, стадия S4c, раздел «"
    + SESSION_PARAMETERS_SECTION_HEADER + "» ниже), свойства ролей — позиция 2.4 "
    "(узел V49, стадия S4d, раздел «" + ROLES_SECTION_HEADER
    + "» ниже; группа F модели V38 закрыта рольями и правами, остальные её виды не "
    "закрываются), свойства общих реквизитов — позиция 2.5 "
    "(узел V50, стадия S4e, раздел «" + COMMON_ATTRIBUTES_SECTION_HEADER
    + "» ниже; из группы E модели V38 закрыты подсистемы, параметры сеанса и общие "
    "реквизиты, остальные её виды этой стадией не закрываются), свойства планов обмена — "
    "позиция 2.6 нормативного списка (узел V51, стадия S4f, раздел «"
    + EXCHANGE_PLAN_SECTION_HEADER + "» ниже; для этого вида закрыты его реквизиты, "
    "табличные части, формы с описаниями, макеты, команды и перечень <Content>, а тела "
    "модулей вида берёт узел V47), свойства критериев отбора — позиция 2.7 "
    "нормативного списка (узел V52, стадия S4g, раздел «" + FILTER_CRITERIA_SECTION_HEADER
    + "» ниже; для этого вида закрыты его свойства, блок <Type>, перечень <Content> как "
    "отдельная таблица состава, его формы с описаниями и его команды, а тела модулей вида "
    "берёт тот же узел V47), свойства подписок на события — позиция 2.8 "
    "нормативного списка (узел V53, стадия S4h, раздел «" + EVENT_SUBSCRIPTIONS_SECTION_HEADER
    + "» ниже; для этого вида закрыты его свойства и круг целей срабатывания блока <Source>, "
    "детей у вида нет ни в одной выгрузке — замер 1.2), свойства регламентных заданий — "
    "позиция 2.9 нормативного списка (узел V54, стадия S4i, раздел «"
    + SCHEDULED_JOBS_SECTION_HEADER
    + "» ниже; для этого вида закрыты его свойства файла регистрации, записи расписания "
    "<ent:*> с состояниями стражей и пустых элементов, а также разрешение обработчика "
    "CommonModule.<Модуль>.<Метод> по общим модулям текущей ревизии; форм, макетов, команд и "
    "модулей у вида нет ни в одной выгрузке — замер 1.2), свойства ботов конфигурации — "
    "позиция 2.10 нормативного списка (узел V55, стадия S4j, раздел «"
    + BOTS_SECTION_HEADER
    + "» ниже; для этого вида закрыты его свойства файла регистрации, ссылка Picture и "
    "дескрипторы модуля Ext/Module.bsl — текст модуля вида берёт тот же узел V47, а форм, "
    "макетов и команд у вида нет ни в одной выгрузке — замер 1.2), свойства функциональных "
    "опций — позиция 2.11 нормативного списка (узел V56, стадия S4k, раздел «"
    + FUNCTIONAL_OPTIONS_SECTION_HEADER
    + "» ниже; для этого вида закрыты его свойства файла регистрации, ссылка Location с "
    "тремя формами адреса (константа, ресурс регистра сведений, реквизит справочника) и круг "
    "целей применения блока <Content> двумя таблицами; форм, макетов, команд и модулей у "
    "вида нет ни в одной выгрузке — замер 1.2 плана V56), свойства параметров функциональных "
    "опций — позиция 2.12 нормативного списка (узел V57, стадия S4l, раздел «"
    + FUNCTIONAL_OPTIONS_PARAMETERS_SECTION_HEADER
    + "» ниже; для этого вида закрыты его свойства файла регистрации и круг целей применения "
    "блока <Use> двумя таблицами с формой адреса цели (объект целиком, измерение регистра, "
    "ресурс регистра сведений, реквизит справочника, табличная часть); ссылки Location у вида "
    "нет — в отличие от круга 2.11, а форм, макетов, команд, модулей и каталогов содержимого "
    "у вида нет ни в одной выгрузке — замер 1.2 плана V57), свойства определяемых типов — "
    "позиция 2.13 нормативного списка (узел V58, стадия S4m, раздел «"
    + DEFINED_TYPES_SECTION_HEADER
    + "» ниже; для этого вида закрыты его свойства файла регистрации, блок `InternalInfo` "
    "четырьмя идентификаторами с состоянием и блок <Type> колонками строки вида — второй "
    "таблицы значений у узла нет осознанно (Q1, вариант A), а форм, макетов, команд, модулей "
    "и каталогов содержимого у вида нет ни в одной выгрузке — замер 1.2 плана V58) "
    "и тексты модулей объектов "
    "конфигурации — шесть слотов Ext/ (узел V47, стадия S4b, раздел «"
    "МОДУЛИ ОБЪЕКТОВ КОНФИГУРАЦИИ» ниже); не реализованы реквизиты и "
    "табличные части прочих видов объектов "
    "конфигурации, их формы и модули форм, макеты, значения перечислений и команды — "
    "остальные группы A–H "
    "модели V38, узел V18 остаётся открытым"
)

# ─── круг видов, содержимое которых сохраняется стадиями конвейера (узел V54, П5) ──
# О сохранности содержимого вида карточка загрузки говорит в двух местах: в строке о
# <ChildObjects> (`config_load_router`) и в предупреждении разбора
# (`configuration_meta_parser`). До этого шага круг дописывали по строке на узел только в
# форматаре карточки, а предупреждение разбора знало лишь виды V46: текст строки о
# покрытии остановился на V52, и для CommonAttribute/ExchangePlan/FilterCriterion/
# EventSubscription разбор утверждал «содержимое в БД не сохраняется», хотя слои
# V50/V51/V52/V53 его пишут (замер 03.11.2026 на MinCfg: `ScheduledJob 2` стоял и в
# перечне «остальных объектов … в БД не раскладываются», и в разделе стадии S4i). Круг
# называет один словарь — его читают оба формата. Порядок ключей — порядок нормативного
# списка (2.3…2.12), он же порядок стадий S4c…S4l (строка остановилась на 2.10/S4j — узел V57
# правит этот дрейф тем же шагом, что и внесение записи вида: перечень, который отстаёт от
# регистра, читается как «видов больше нет»). Вид V46 (подсистемы и общие модули,
# позиции 2.1–2.2) здесь не перечислен осознанно: его таблицы держит `LOADED_META_TABLES`
# слоя свойств, и оба формата читают и его. Формулировка «слепая зона V38» к видам этого
# словаря не относится: их содержимое в БД лежит, а незакрытые группы A–H модели V38
# называет `CHILD_NOT_IMPLEMENTED` выше.
STORED_META_KINDS: Dict[str, Dict[str, Any]] = {
    SESSION_PARAMETER_META_TAG: {
        "node": "V48", "stage": "S4c", "position": "2.3",
        "tables": SESSION_PARAMETER_TABLES,
        "section": SESSION_PARAMETERS_SECTION_HEADER,
    },
    ROLE_META_TAG: {
        "node": "V49", "stage": "S4d", "position": "2.4",
        "tables": ROLE_TABLES,
        "section": ROLES_SECTION_HEADER,
    },
    COMMON_ATTRIBUTE_META_TAG: {
        "node": "V50", "stage": "S4e", "position": "2.5",
        "tables": COMMON_ATTRIBUTES_TABLES,
        "section": COMMON_ATTRIBUTES_SECTION_HEADER,
    },
    EXCHANGE_PLAN_META_TAG: {
        "node": "V51", "stage": "S4f", "position": "2.6",
        "tables": EXCHANGE_PLAN_TABLES,
        "section": EXCHANGE_PLAN_SECTION_HEADER,
    },
    FILTER_CRITERIA_META_TAG: {
        "node": "V52", "stage": "S4g", "position": "2.7",
        "tables": FILTER_CRITERIA_TABLES,
        "section": FILTER_CRITERIA_SECTION_HEADER,
    },
    EVENT_SUBSCRIPTION_META_TAG: {
        "node": "V53", "stage": "S4h", "position": "2.8",
        "tables": EVENT_SUBSCRIPTIONS_TABLES,
        "section": EVENT_SUBSCRIPTIONS_SECTION_HEADER,
    },
    SCHEDULED_JOB_META_TAG: {
        "node": "V54", "stage": "S4i", "position": "2.9",
        "tables": SCHEDULED_JOBS_TABLES,
        "section": SCHEDULED_JOBS_SECTION_HEADER,
    },
    # Узел V55 (шаг П5): вид 2.10 тем же порядком — оба формата (строка о <ChildObjects> и
    # предупреждение разбора) читают этот словарь, поэтому без строки `Bot` остался бы в
    # перечне «содержимое в БД не раскладывается», хотя слой S4j его свойства пишет.
    BOTS_META_TAG: {
        "node": "V55", "stage": "S4j", "position": "2.10",
        "tables": BOTS_TABLES,
        "section": BOTS_SECTION_HEADER,
    },
    # Узел V56 (шаг П5): вид 2.11 тем же порядком — без строки `FunctionalOption` вид
    # остался бы в перечне «содержимое в БД не раскладывается», хотя слой S4k пишет его
    # свойства и перечень применения (прецедент V55, дефект `_v54_p5_stage_probe.py`).
    # Круг — две таблицы (`FUNCTIONAL_OPTIONS_TABLES`, Q1 вариант A), порядок — порядок
    # нормативного списка.
    FUNCTIONAL_OPTIONS_META_TAG: {
        "node": "V56", "stage": "S4k", "position": "2.11",
        "tables": FUNCTIONAL_OPTIONS_TABLES,
        "section": FUNCTIONAL_OPTIONS_SECTION_HEADER,
    },
    # Узел V57 (шаг П5): вид 2.12 тем же порядком — без строки `FunctionalOptionsParameter`
    # вид остался бы в перечне «содержимое в БД не раскладывается», хотя слой S4l пишет его
    # свойства и перечень применения (прецеденты V55, V56; дефект назван `_v54_p5_stage_probe.py`).
    # Круг — две таблицы (`FUNCTIONAL_OPTION_PARAMETERS_TABLES`, Q1 вариант A). Имя метки вида
    # отличается от метки 2.11 (`FunctionalOption`) — словарь читается точными ключами, поэтому
    # соседний вид в круг не попадает (замер 1.2 плана V57).
    FUNCTIONAL_OPTIONS_PARAMETERS_META_TAG: {
        "node": "V57", "stage": "S4l", "position": "2.12",
        "tables": FUNCTIONAL_OPTION_PARAMETERS_TABLES,
        "section": FUNCTIONAL_OPTIONS_PARAMETERS_SECTION_HEADER,
    },
    # Узел V58 (шаг П5): вид 2.13 тем же порядком — без строки `DefinedType` вид остался бы в
    # перечне «содержимое в БД не раскладывается», хотя слой S4m пишет его свойства, блок
    # `InternalInfo` и блок `<Type>` (прецеденты V55, V56, V57; дефект назван
    # `_v54_p5_stage_probe.py`). Круг — ОДНА таблица (`DEFINED_TYPES_TABLES`, Q1 вариант A):
    # второй таблицы значений у вида нет, и в отличие от вида 2.12 здесь нет и таблицы
    # применения — цели блока `<Type>` являются колонками строки вида (ключи `target_*`
    # записи jsonb), поэтому второй записью круг не расширяется. Метка вида точная:
    # `DefinedType` (замер 1.1 — записи индекса состава `DefinedType.<Имя>`).
    DEFINED_TYPES_META_TAG: {
        "node": "V58", "stage": "S4m", "position": "2.13",
        "tables": DEFINED_TYPES_TABLES,
        "section": DEFINED_TYPES_SECTION_HEADER,
    },
}

# Таблицы, чьи строки остаются нетронутыми, когда группа не запрошена: ответ обязан назвать
# это, а не отдать нули как «в конфигурации ничего нет» (C2).
# Узел V52 (шаг П4) добавляет круг стадии S4g: без этой строки `CHILD_TABLES` — круг стадии
# S4 — включил бы `filter_criteria`, и стадия S4 снимала и анализировала бы чужие строки
# (тот же дефект, что закрывали записи V48, V49, V50, V51).
# Узел V54 (шаг П4) добавляет круг стадии S4i тем же порядком и раньше, чем стадия входит в
# `STAGES` (шаг П5): таблица уже зарегистрирована в круге версионности
# (`CONFIGURATION_VERSIONED_TABLES`, `src/current_revision.py`), и без этой строки стадия S4
# снимала и анализировала бы 346 строк чужого вида и 313 записей его расписания (замеры П0).
# Узел V55 (шаг П4) добавляет круг стадии S4j тем же порядком: без этой строки стадия S4
# снимала и анализировала бы строки ботов чужого вида (замер 1.1: 2 файла регистрации и 2
# файла модулей у MinCfg; у трёх других выгрузок вида нет).
# Узел V56 (шаг П5) добавляет круг стадии S4k тем же порядком и раньше, чем стадия входит в
# `STAGES`: таблица `functional_options` уже зарегистрирована в круге версионности
# (`CONFIGURATION_VERSIONED_TABLES`, `src/current_revision.py`, шаги П1/П4), и без этой строки
# стадия S4 снимала и анализировала бы 765 строк вида и 10 063 строки его применения (замеры
# 1.1 и 2.2 плана V56). `functional_option_content` в `CONFIGURATION_VERSIONED_TABLES` нет
# осознанно (своей цепи ревизий у таблицы нет — Q2, вариант A), поэтому в круге загрузки её
# держит именно эта константа, а не круг версионности.
# Узел V57 (шаг П4) добавляет круг стадии S4l тем же порядком и раньше, чем стадия входит в
# `STAGES` (шаг П5): таблица `functional_option_parameters` уже зарегистрирована в круге
# версионности (`CONFIGURATION_VERSIONED_TABLES`, `src/current_revision.py`, шаги П1/П4), и без
# этой строки стадия S4 снимала и анализировала бы 14 строк вида и 34 строки его применения
# (замеры 1.1 и 2.1 плана V57). `functional_option_parameter_targets` в
# `CONFIGURATION_VERSIONED_TABLES` нет осознанно (своей цепи ревизий у таблицы нет — Q2,
# вариант A), поэтому в круге загрузки её держит именно эта константа, а не круг версионности.
# Узел V58 (шаг П4) добавляет круг стадии S4m тем же порядком и раньше, чем стадия входит в
# `STAGES` (шаг П5): таблица `defined_types` уже зарегистрирована в круге версионности
# (`CONFIGURATION_VERSIONED_TABLES`, `src/current_revision.py`, шаги П1/П4), и без этой строки
# стадия S4 снимала и анализировала бы 820 строк чужого вида (замеры 1.1 плана V58: 2 / 1 /
# 304 / 513 файлов регистрации во всех четырёх выгрузках корпуса). Второй таблицы у узла нет
# осознанно (Q1, вариант A): блок `<Type>` является колонками строки вида, поэтому круг
# держится одной таблицей — как `bots` узла V55.
FOREIGN_STAGE_TABLES: Tuple[str, ...] = (
    SESSION_PARAMETER_TABLES + ROLE_TABLES + COMMON_ATTRIBUTES_TABLES
    + EXCHANGE_PLAN_TABLES + FILTER_CRITERIA_TABLES + EVENT_SUBSCRIPTIONS_TABLES
    + SCHEDULED_JOBS_TABLES + BOTS_TABLES + FUNCTIONAL_OPTIONS_TABLES
    + FUNCTIONAL_OPTION_PARAMETERS_TABLES + DEFINED_TYPES_TABLES
)

CHILD_TABLES: Tuple[str, ...] = tuple(
    table for table in CONFIGURATION_VERSIONED_TABLES
    if table not in FOREIGN_STAGE_TABLES
)
CHILD_KINDS: Tuple[str, ...] = (KIND_SUBSYSTEMS, KIND_COMMON_MODULES)
CHILD_KIND_TITLES: Dict[str, str] = {
    KIND_SUBSYSTEMS: "Подсистемы",
    KIND_COMMON_MODULES: "Общие модули",
}

# Заголовок раздела карточки `load_1c_catalog_tool` (вариант `configuration`) и ответа
# `load_configuration_object_properties_tool` — один на два контура (решение V45: карточка и
# инструмент описывают один слой одинаково; переписанные порознь, они разъезжаются при первой
# же правке контракта).
CHILD_SECTION_HEADER = "СОДЕРЖИМОЕ ДОЧЕРНИХ ОБЪЕКТОВ: ПОДСИСТЕМЫ И ОБЩИЕ МОДУЛИ (узел V46)"


def child_object_kind_defaults() -> Dict[str, Any]:
    """Одна группа стадии S4 с нулями (C1).

    `requested` отделяет «вид не просили» от «таких объектов в конфигурации нет»: по нулям
    эти два ответа неразличимы (C2), поэтому состояние запрашивания — часть контракта, а не
    домысел вызывающего. Словари состояний заполняются нулями по словарям РАЗБОРА
    (`configuration_object_properties`), а не своим перечнем: два словаря состояний
    разъезжаются, и CHECK схемы (`common_module_sources_content_state_check`) тогда отстаёт
    от кода.
    """
    return {
        "requested": False,
        "written": 0,
        "counts_by_state": {state: 0 for state in DECLARATION_STATES},
        "by_depth": {},
        "content_total": 0,
        "content_resolved": 0,
        "content_unresolved": 0,
        "content_by_form": {},
        "content_by_target_type": {},
        "slots_by_state": {},
        "descriptor_rows": 0,
        "counts_by_content_state": {state: 0 for state in CONTENT_STATES},
        "modules_without_descriptor": 0,
        "index_available": False,
        "index_objects": 0,
        "index_slots": 0,
        "parse_errors": [],
        "layout_outliers": [],
        "removed_previous": 0,
    }


def child_module_content_defaults() -> Dict[str, Any]:
    """Тексты модулей общих модулей — вторая транзакция по D7 (C1).

    `requested` distinguishes «тексты не просили» (`with_module_content=False`, состояние
    по умолчанию замера 2.6: 188–294 МБ на выгрузку) from «просили, и их нет». `skipped`
    считает дескрипторы, у которых текста нет физически (`bin_only`, `indexed_no_file`) —
    их отсутствие в `bsl_modules` не является потерей, но обязано быть названо числом.
    """
    return {
        "requested": False,
        "written": 0,
        "truncated": 0,
        "skipped": 0,
        "code_limit": None,
        "counts_by_state": {state: 0 for state in CONTENT_STATES},
        "removed_previous": 0,
        "errors": [],
    }


def child_objects_defaults() -> Dict[str, Any]:
    """Закрытый контракт стадии S4 (C1, C3).

    Словарь плоский — тот же, что возвращает отдельный инструмент; конвейер вкладывает его
    в свой ключ `child_objects` без переименования (C3). `status` различает «стадия не
    выполнялась» (`not_run`, C2) и «выполнилась с отказом» (`error`): нули без статуса
    слили бы эти два факта в одно.
    """
    return {
        "status": STATUS_NOT_RUN,
        "success": False,
        "error": None,
        "reason": None,
        "configuration_id": None,
        "configuration_uuid": None,
        "configuration_name": None,
        "tables": list(CHILD_TABLES),
        "kinds_requested": [],
        "kinds": {kind: child_object_kind_defaults() for kind in CHILD_KINDS},
        "module_content": child_module_content_defaults(),
        "objects_written": 0,
        "warnings": [],
    }


def format_child_object_lines(result: Dict[str, Any],
                              indent: str = "") -> List[str]:
    """Текст стадии S4 по закрытому контракту `child_objects_defaults()` (C1, C3).

    Формат один для двух контуров: раздела карточки `load_1c_catalog_tool` и ответа
    `load_configuration_object_properties_tool` (решение V45). Отказ форматёр называет сам
    («Стадия не выполнена: …») — вызывающий причину не повторяет, иначе два текста об одном
    отказе разъезжаются. Неперечисленные ключи читаются нулями (C1).

    Строка о незакрытой части содержимого дочерних объектов печатается и при успехе: «свойства
    подсистем и общих
    модулей записаны» не равно «содержимое дочерних объектов загружено» — границы узла V46
    (план, раздел 8) читаются из ответа, а не из молчания.
    """
    lines: List[str] = []
    if not result:
        return lines
    if not result.get("success"):
        reason = result.get("error") or result.get("reason") or "загрузчик не назвал причину"
        prefix = ("Стадия не выполнена" if result.get("status") in (None, STATUS_NOT_RUN)
                  else "Стадия не удалась")
        lines.append(f"{indent}{prefix}: {reason}")
        return lines

    kinds = result.get("kinds") or {}
    removed_by_kind = {
        kind: int((kinds.get(kind) or {}).get("removed_previous") or 0)
        for kind in CHILD_KINDS
    }
    removed_total = sum(removed_by_kind.values())
    lines.append(
        f"{indent}Записано строк свойств: {int(result.get('objects_written') or 0)}; "
        f"таблицы: {', '.join(result.get('tables') or CHILD_TABLES)}"
        + (f"; снято прежних строк: {removed_total} ("
           + ", ".join(f"{kind} {count}" for kind, count in sorted(removed_by_kind.items())
                       if count) + ")"
           if removed_total else "; прежних строк не снималось")
    )

    for kind in CHILD_KINDS:
        title = CHILD_KIND_TITLES[kind]
        part = kinds.get(kind) or {}
        if not part.get("requested"):
            lines.append(
                f"{indent}{title}: вид не запрашивался — нули здесь не означают, что таких "
                "объектов в конфигурации нет"
            )
            continue
        counts_by_state = part.get("counts_by_state") or {}
        line = (
            f"{indent}{title}: строк {int(part.get('written') or 0)}; состояния объявления: "
            + ", ".join(f"{state}={int(counts_by_state.get(state) or 0)}"
                        for state in DECLARATION_STATES)
        )
        by_depth = part.get("by_depth") or {}
        if by_depth:
            try:
                order = sorted(by_depth, key=lambda depth: int(depth))
            except (TypeError, ValueError):
                order = sorted(str(depth) for depth in by_depth)
            line += "; глубина дерева: " + ", ".join(
                f"{depth}={int(by_depth[depth])}" for depth in order
            )
        lines.append(line)
        if not part.get("index_available"):
            lines.append(
                f"{indent}  Индекс состава не читается — состояния называются только по "
                "файлу, и «объекта нет» от «объект не подтверждён индексом» этим не отличить"
            )
        for outlier in part.get("layout_outliers") or []:
            lines.append(f"{indent}  ⚠️ раскладка: {outlier}")
        for failure in part.get("parse_errors") or []:
            lines.append(f"{indent}  ⚠️ файл регистрации: {failure}")

        if kind == KIND_SUBSYSTEMS:
            total = int(part.get("content_total") or 0)
            resolved = int(part.get("content_resolved") or 0)
            unresolved = int(part.get("content_unresolved") or 0)
            by_form = part.get("content_by_form") or {}
            lines.append(
                f"{indent}  Ссылки Content: всего {total}, разрешено {resolved}, "
                f"неразрешено {unresolved} (форма ссылок: "
                + ", ".join(f"{form}={int(count)}" for form, count in sorted(by_form.items()))
                + "); неразрешённые остаются строкой в `content_unresolved` самого объекта, "
                  "а не молчанием (D3)"
            )
            for slot, stats in sorted((part.get("slots_by_state") or {}).items()):
                stats = stats or {}
                lines.append(
                    f"{indent}  Слоты {slot}: записей индекса "
                    f"{int(stats.get('index_records') or 0)}, файлов "
                    f"{int(stats.get('files') or 0)}, объявлено индексом без файла "
                    f"{int(stats.get('indexed_no_file') or 0)}, файл вне индекса "
                    f"{int(stats.get('file_not_in_index') or 0)}; содержимое слота (xtui, "
                    "html) в схеме не хранится — граница узла V46"
                )
        else:
            content_counts = part.get("counts_by_content_state") or {}
            lines.append(
                f"{indent}  Дескрипторы модулей: {int(part.get('descriptor_rows') or 0)}; "
                "состояния текста: "
                + ", ".join(f"{state}={int(content_counts.get(state) or 0)}"
                            for state in CONTENT_STATES)
                + f"; модулей без дескриптора: "
                  f"{int(part.get('modules_without_descriptor') or 0)}"
            )

    module_content = result.get("module_content") or {}
    if not module_content.get("requested"):
        lines.append(
            f"{indent}Тексты модулей общих модулей: не запрашивались "
            "(with_module_content=False; замер 2.6: 188 МБ BGU2, 294 МБ BP3) — в bsl_modules "
            "строк общих модулей этой загрузкой не записано, а "
            "common_module_sources.content_loaded остался false (решения D6, D7)"
        )
    else:
        limit = module_content.get("code_limit")
        lines.append(
            f"{indent}Тексты модулей общих модулей (bsl_modules, вторая транзакция D7): "
            f"записано {int(module_content.get('written') or 0)}, усечено "
            f"{int(module_content.get('truncated') or 0)}, пропущено "
            f"{int(module_content.get('skipped') or 0)} (текста нет физически), снято прежних "
            f"{int(module_content.get('removed_previous') or 0)}; усечение: "
            + ("без лимита (code_limit не задан)" if not limit else f"до {int(limit)} симв.")
            + "; родителем строки выступает uuid самого общего модуля (parent_uuid, "
              "parent_type=common_modules), цепочка "
              "состояний — по пути файла, как у модулей внешнего объекта (M1, M3)"
        )
        for failure in module_content.get("errors") or []:
            lines.append(f"{indent}  ⚠️ текст модуля: {failure}")

    for warning in result.get("warnings") or []:
        lines.append(f"{indent}⚠️ {warning}")
    lines.append(f"{indent}Граница: {CHILD_NOT_IMPLEMENTED}")
    return lines


# ── стадия S4b: модули объектов конфигурации (узел V47, 28.10.2026) ──────────────────

# Таблица одна и она же — цель узла: отдельного реестра таблиц здесь быть не может, его
# задаёт словарь `src/configuration_module_slots.py` (`TARGET_TABLE`, `PARENT_TYPE`).
# Импорт этого словаря в данный модуль закрыт циклом: словарь опирается на
# `configuration_root_module_loader`, который импортирует контракт. Значит имена таблицы
# и слотов называются здесь текстом границы, а числовые ключи ответа приходят от писателя
# (`configuration_module_writer.result_defaults`) — второго перечня ключей в проекте нет.
OBJECT_MODULE_TABLE = "bsl_modules"

# Заголовок раздела карточки `load_1c_catalog_tool` (вариант `configuration`). Отдельного
# инструмента с этим текстом нет (решение Q4.1), поэтому форматёр один — карточный.
OBJECT_MODULES_SECTION_HEADER = "МОДУЛИ ОБЪЕКТОВ КОНФИГУРАЦИИ (узел V47)"

# Что обязан сказать ответ при отказе стадии. Отдельного входа для повтора нет — правило
# оператора одно: «ошибка загрузки влечёт перезагрузку всей конфигурации» (Q4.1).
OBJECT_MODULES_RELOAD_HINT = (
    "Отдельного входа для модулей объектов нет (решение Q4.1, реестр инструментов core "
    "остаётся пятью): ошибка загрузки влечёт полную перезагрузку конфигурации — "
    "load_1c_catalog_tool(source_path=…, force=True)"
)

# Граница круга называется и при успехе: «строки модулей записаны» не равно «других
# модулей конфигурации в базе нет». Перечень слотов повторяет словарь П2 текстом.
OBJECT_MODULES_BOUNDARY = (
    "круг узла — шесть слотов Ext/ записей индекса состава (ObjectModule, ManagerModule, "
    "RecordSetModule, ValueManagerModule, CommandModule; Module — только для WebService, "
    "HTTPService, IntegrationService, Bot, WebSocketClient). Общие модули (CommonModule) "
    "ведёт узел V46, модули форм индексом не моделируются вовсе (узел V40), слоты "
    "вторичных объектов вне предмета (решение Q5). Строка в bsl_modules есть только там, "
    "где файл существует и раскодирован строго (решение Q2), поэтому «пустой модуль» и "
    "«файла нет» в схеме не различимы — их различает только ответ стадии. Машинный код "
    ".bin рядом с отсутствующим исходником остаётся открытой позицией O1"
)


def format_object_module_lines(result: Dict[str, Any],
                               indent: str = "") -> List[str]:
    """Текст стадии S4b по её контракту (C1, C2).

    Отказ форматёр называет сам и обязательно называет группу: атомом полноты является
    группа объектов (решение Q4), а «конфигурация загружена» без строки о незакрытой
    группе утверждало бы состав, которого в базе нет. Нули без статуса успехом не
    читаются: `not_run` (индекс состава не разобран — круг не определён) и `error`
    (круг читался и отказал) — разные факты (C2).
    """
    lines: List[str] = []
    if not result:
        return lines

    if not result.get("success"):
        reason = result.get("error") or result.get("reason") or "загрузчик не назвал причину"
        prefix = ("Стадия не выполнена" if result.get("status") in (None, STATUS_NOT_RUN)
                  else "Стадия не удалась")
        lines.append(f"{indent}{prefix}: {reason}")
        group = result.get("failed_group")
        if group:
            record = result.get("failed_record")
            lines.append(
                f"{indent}Группа объектов не загружена: {group}"
                + (f" (запись: {record})" if record else "")
                + " — атом полноты (решение Q4), конфигурация неполная"
            )
        compensated = int(result.get("compensated_rows") or 0)
        if compensated:
            lines.append(
                f"{indent}Снято строк, вставленных до отказа: {compensated} — "
                "незавершённая группа не оставляет частичных строк независимо от того, "
                "фиксирует вызывающий транзакцию или откатывает"
            )
        removed = int(result.get("removed_previous") or 0)
        if removed:
            lines.append(
                f"{indent}Прежние строки круга узла сняты и остаются снятыми: {removed} — "
                "индекс состава пересоздан этой же загрузкой, старые строки больше не "
                "описывают текущий состав"
            )
        lines.append(f"{indent}{OBJECT_MODULES_RELOAD_HINT}")
        for warning in result.get("warnings") or []:
            lines.append(f"{indent}⚠️ {warning}")
        return lines

    groups = result.get("groups") or {}
    lines.append(
        f"{indent}Записано строк модулей ({OBJECT_MODULE_TABLE}, parent_type = "
        f"'configuration_objects'): {int(result.get('written') or 0)}; символов кода "
        f"{int(result.get('code_chars') or 0)}; время стадии "
        f"{float(result.get('seconds') or 0)} с; групп круга "
        f"{int(groups.get('seen') or 0)}, из них с записанными модулями "
        f"{int(groups.get('with_rows') or 0)}; снято прежних строк узла "
        f"{int(result.get('removed_previous') or 0)}"
    )
    counts = result.get("counts_by_state") or {}
    lines.append(
        f"{indent}Состояния записей круга: "
        + ", ".join(f"{state}={int(count)}" for state, count in sorted(counts.items()))
        + " — «пустой модуль» (empty_file) и «файла нет» (indexed_no_file) строки не "
          "имеют (решение Q2); undecoded — отказ стадии по правилу C5, а не строка"
    )
    empty_after_strip = int(result.get("empty_after_strip") or 0)
    if empty_after_strip:
        lines.append(
            f"{indent}  Файлов без текста после нормализации (одна BOM или пробелы): "
            f"{empty_after_strip} — состояние выгрузки, а не потерянная строка; поэтому "
            "число записанных строк меньше числа файлов круга (замер раздела 2.3 плана)"
        )
    for reason, count in sorted((result.get("refusals") or {}).items()):
        if int(count or 0):
            lines.append(f"{indent}  ⚠️ отказ вывести путь ({reason}): {int(count)}")
    for reason, count in sorted((result.get("defects") or {}).items()):
        if int(count or 0):
            lines.append(f"{indent}  ⚠️ дефект данных ({reason}): {int(count)}")
    bin_side = int(result.get("bin_side") or 0)
    if bin_side:
        examples = ", ".join(str(item) for item in (result.get("bin_side_examples") or []))
        lines.append(
            f"{indent}  Машинный код .bin рядом с отсутствующим исходником: {bin_side} "
            "(открытая позиция O1 — решения о таких модулях узлом не приняты, строк у них "
            "нет)"
            + (f"; примеры: {examples}" if examples else "")
        )
    for sample in result.get("samples") or []:
        lines.append(f"{indent}  ⚠️ запись круга: {sample}")
    refreshed = int(result.get("statistics_refreshed") or 0)
    if refreshed:
        lines.append(
            f"{indent}Статистика таблицы {OBJECT_MODULE_TABLE} пересобрана (ANALYZE): "
            f"{refreshed} — без неё читатели витрин текущего состояния платят минутами "
            "(мера V46)"
        )
    for warning in result.get("warnings") or []:
        lines.append(f"{indent}⚠️ {warning}")
    lines.append(f"{indent}Граница: {OBJECT_MODULES_BOUNDARY}")
    return lines


# ── контракт стадии S4c (узел V48, шаг П4, позиция 2.3 списка) ───────────────────

def session_parameters_defaults() -> Dict[str, Any]:
    """Закрытый контракт стадии S4c с нулями (C1, C2, C3).

    Словарь плоский — тот же, что возвращает слой `load_session_parameters`; конвейер
    вкладывает его в свой ключ `session_parameters` без переименования (C3). `status`
    различает «стадия не выполнялась» (`not_run`, C2) и «выполнилась с отказом» (`error`):
    нули без статуса слили бы эти два факта в одно — иерархии состояний у вида нет, но
    классы расхождений те же, что у V46 и V47.

    Что обязан назвать ответ отдельно (план, раздел 5):

    * `counts_by_state` по типам — «тип не разобран» читается фактом, а не нулём строки;
    * `types_multiplicity` — распределение `single`/`composite`/`absent`: кратность есть
      свойство модели 1С (определение оператора Q4), а не исключение данных;
    * `types_unresolved_total` и примеры — число записей с `resolved = false`: ненулевое
      значение это данные или новое правило перехода, а не молчаливый NULL;
    * `index_only` / `file_only` — записей индекса без файла и файлов без индекса:
      замер 2.2 даёт нули, и нули обязаны быть названы, а не подразумеваны;
    * `unknown_properties` — предупреждение о свойстве вне словаря (приём V43 про «виды
      без колонки» и V46 про имена вне словаря): молча пропущенное свойство отличалось бы
      от «такого свойства в выгрузке нет».
    """
    return {
        "status": STATUS_NOT_RUN,
        "success": False,
        "error": None,
        "reason": None,
        "stage": STAGE_SESSION_PARAMETERS,
        "configuration_id": None,
        "configuration_uuid": None,
        "configuration_name": None,
        "tables": [SESSION_PARAMETER_TABLE],
        "directory": SESSION_PARAMETER_DIR,
        "files_found": 0,
        "files_read": 0,
        "files_failed": [],
        "rows_written": 0,
        "removed_previous": 0,
        "index_available": False,
        "index_records": 0,
        "index_only": [],
        "file_only": [],
        "uuid_mismatch": [],
        "counts_by_state": {state: 0 for state in RECORD_STATES},
        "types_total": 0,
        "types_resolved": 0,
        "types_unresolved_total": 0,
        "types_unresolved": [],
        "types_multiplicity": {mult: 0 for mult in MULTIPLICITY_VALUES},
        "types_by_class": {kind: 0 for kind in TYPE_CLASS_VALUES},
        "unknown_properties": {},
        "unexpected_tags": {},
        "value_tag_mismatch": [],
        "namespace_prefixes": [],
        "observations": [],
        "statistics_refreshed": 0,
        "warnings": [],
    }


def format_session_parameters_lines(result: Dict[str, Any],
                                    indent: str = "") -> List[str]:
    """Текст стадии S4c по закрытому контракту `session_parameters_defaults()` (C1, C3).

    Формат один для двух контуров: раздела карточки `load_1c_catalog_tool` и ответа
    отдельного инструмента, который заводит шаг П5 (прецедент V45/V46). Отказ форматёр
    называет сам («Стадия не выполнена» / «Стадия не удалась»), вызывающий причину не
    повторяет. Граница круга печатается и при успехе: «строки свойств записаны» не равно
    «о виде всё сохранено», а пустой тип без этой строки читался бы как «типа нет».
    Неперечисленные ключи читаются нулями (C1).
    """
    lines: List[str] = []
    if not result:
        return lines

    if not result.get("success"):
        reason = result.get("error") or result.get("reason") or "загрузчик не назвал причину"
        prefix = ("Стадия не выполнена" if result.get("status") in (None, STATUS_NOT_RUN)
                  else "Стадия не удалась")
        lines.append(f"{indent}{prefix}: {reason}")
        lines.append(f"{indent}{SESSION_PARAMETERS_REPEAT_HINT}")
        for warning in result.get("warnings") or []:
            lines.append(f"{indent}⚠️ {warning}")
        return lines

    removed = int(result.get("removed_previous") or 0)
    lines.append(
        f"{indent}Записано строк свойств ({SESSION_PARAMETER_TABLE}): "
        f"{int(result.get('rows_written') or 0)}; файлов разобрано "
        f"{int(result.get('files_read') or 0)} из {int(result.get('files_found') or 0)} "
        f"(каталог {result.get('directory') or SESSION_PARAMETER_DIR}/)"
        + (f"; снято прежних строк: {removed}" if removed else "; прежних строк не снималось")
    )

    counts_by_state = result.get("counts_by_state") or {}
    lines.append(
        f"{indent}Состояния разбора типа: "
        + ", ".join(f"{state}={int(counts_by_state.get(state) or 0)}"
                    for state in RECORD_STATES)
        + " — «блока Type нет» (absent), «блок есть, но форма не распознана» (unknown_form) "
          "и «разобран частично» (partial) различаются ответом стадии, а не пустой строкой"
    )
    multiplicity = result.get("types_multiplicity") or {}
    lines.append(
        f"{indent}Кратность значений типа: "
        + ", ".join(f"{mult}={int(multiplicity.get(mult) or 0)}"
                    for mult in MULTIPLICITY_VALUES)
        + " — кратность называется числом, потому что это свойство модели 1С (определение "
          "оператора Q4), а не исключение данных"
    )

    classes = result.get("types_by_class") or {}
    lines.append(
        f"{indent}Записей значений типа: {int(result.get('types_total') or 0)}; классы: "
        + ", ".join(f"{kind}={int(classes.get(kind) or 0)}" for kind in TYPE_CLASS_VALUES)
        + f"; ссылок разрешено {int(result.get('types_resolved') or 0)}, неразрешено "
          f"{int(result.get('types_unresolved_total') or 0)} (остаются записями без ключей "
          "цели, а не молчанием — приём D3)"
    )
    for sample in (result.get("types_unresolved") or [])[:10]:
        lines.append(
            f"{indent}  ⚠️ неразрешённая ссылка: {sample.get('value')} — "
            f"{sample.get('reason')}"
            + (f" (индексное имя {sample.get('index_name')})"
               if sample.get("index_name") else "")
        )

    if not result.get("index_available"):
        lines.append(
            f"{indent}  Индекс состава не читается — сверка файла регистрации с перечнем "
            "невозможна, и «объекта нет в перечне» от «перечень этой конфигурации не "
            "загружен» этим не отличить"
        )
    else:
        index_only = result.get("index_only") or []
        file_only = result.get("file_only") or []
        uuid_mismatch = result.get("uuid_mismatch") or []
        lines.append(
            f"{indent}Сверка с индексом состава: записей вида "
            f"{int(result.get('index_records') or 0)}; записей перечня без файла "
            f"{len(index_only)}, файлов без записи перечня {len(file_only)}, несовпадений "
            "uuid "
            f"{len(uuid_mismatch)} — нули названы числом, потому что замер 2.2 даёт именно "
            "нули, а подразумевать их нельзя"
        )
        for name in index_only[:10]:
            lines.append(f"{indent}  ⚠️ запись индекса без файла регистрации: {name}")
        for name in file_only[:10]:
            lines.append(f"{indent}  ⚠️ файл регистрации без записи индекса: {name}")
        for item in uuid_mismatch[:10]:
            lines.append(
                f"{indent}  ⚠️ uuid файла {item.get('file_uuid')} не совпадает с uuid "
                f"индекса {item.get('index_uuid')} ({item.get('source_path')})"
            )

    for name, count in sorted((result.get("unknown_properties") or {}).items()):
        lines.append(
            f"{indent}  ⚠️ свойство вне словаря разбора: {name} ({count}) — сохранение "
            "такого свойства требует колонки и решения, молча оно не отбрасывается"
        )
    for tag, count in sorted((result.get("unexpected_tags") or {}).items()):
        lines.append(f"{indent}  ⚠️ незнакомый тег блока Type: {tag} ({count})")
    for item in (result.get("value_tag_mismatch") or [])[:10]:
        lines.append(
            f"{indent}  ⚠️ число тегов значения ({item.get('tags')}) не совпало с числом "
            f"записей ({item.get('entries')}): {item.get('source_path')}"
        )
    for observation in (result.get("observations") or [])[:10]:
        lines.append(f"{indent}  ⚠️ круг каталога: {observation[0]} — {observation[1]}")
    for failure in (result.get("files_failed") or [])[:10]:
        lines.append(f"{indent}  ⚠️ файл не разобран: {failure.get('source_path')} — "
                     f"{failure.get('reason')}")

    refreshed = int(result.get("statistics_refreshed") or 0)
    if refreshed:
        lines.append(
            f"{indent}Статистика таблицы {SESSION_PARAMETER_TABLE} пересобрана (ANALYZE): "
            f"{refreshed} — без неё читатели витрин текущего состояния платят минутами "
            "(мера V46)"
        )
    for warning in result.get("warnings") or []:
        lines.append(f"{indent}⚠️ {warning}")
    lines.append(f"{indent}Граница: {SESSION_PARAMETERS_BOUNDARY}")
    return lines


# ── контракт стадии S4d (узел V49, шаг П4, позиция 2.4 списка) ───────────────────

def role_group_defaults() -> Dict[str, Any]:
    """Одна группа круга S4d с нулями (C1).

    `requested` отделяет «группу не просили» от «строк в конфигурации нет»: по нулям этих
    двух ответов не различить (C2), поэтому признак запрашивания — часть контракта, а не
    домысел вызывающего. Прецедент — `child_object_kind_defaults()` узла V46.
    """
    return {
        "requested": False,
        "written": 0,
        "removed_previous": 0,
    }


def roles_defaults() -> Dict[str, Any]:
    """Закрытый контракт стадии S4d с нулями (C1, C2, C3).

    Словарь плоский — тот же, что возвращает слой `load_roles`; конвейер вкладывает его в
    свой ключ `roles` без переименования (C3). `status` различает «стадия не выполнялась»
    (`not_run`, C2) и «выполнилась с отказом» (`error`).

    Имена ключей сводки совпадают с именами разбора `src/configuration_roles.py` намеренно
    (прецедент `SUMMARY_KEYS` узлов V46/V48): неперечисленный ключ контракта читается
    нулём, а не исчезает, а незнакомый ключ разбора не попадает в ответ, которого карточка
    не обещала. Ключей `role_rows` / `right_rows` / `template_rows` / `source_rows` здесь
    нет намеренно: это строки записи (десятки тысяч), а не сводка состояния — ответ стадии
    обязан называть числа, а не пересылать содержимое таблиц.

    Что обязан назвать ответ отдельно (план, разделы 4 и 5):

    * `removed_by_table` / `written_by_table` — четырьмя таблицами, а не одним числом:
      круг пишется одной транзакцией, но «записано 682» и «записано 682 роли + 76 332
      права» для читателя карточки — разные факты;
    * `counts_by_content_state` — «прав нет» (`empty_content`) и «файла содержимого нет»
      (`indexed_no_file`) различаются состоянием, а не нулём строки (Q6, вариант A);
    * `counts_by_target_resolve_state` — `prefix_only` и `unresolved` являются ответом о
      цели, а не потерянной ссылкой (Q3);
    * `restrictions_called_own_role` / `restrictions_called_other_role` — два круга вызовов
      шаблонов считаются раздельно, потому что круг их деклараций разный (замер 2.7);
    * `template_occurrences` против `template_texts_distinct` — дедупликация по паре
      (имя, отпечаток) видна числом, а не молчанием (замер 2.7: 1 386 вхождений дают
      9 различных текстов);
    * `index_only` / `file_only` / `uuid_mismatch` — расхождения файла и перечня: четыре
      замеренные выгрузки дают нули, и нули обязаны быть названы, а не подразумеваться;
    * `kinds_requested` / `kinds` — какие группы круга просил отдельный вход (шаг П5):
      без признака запрашивания нули незапрошенной группы читались бы как «ролей и прав в
      конфигурации нет» (C2), а строки незапрошенных таблиц при этом не снимались.
    """
    return {
        "status": STATUS_NOT_RUN,
        "success": False,
        "error": None,
        "reason": None,
        "stage": STAGE_ROLES,
        "configuration_id": None,
        "configuration_uuid": None,
        "configuration_name": None,
        "tables": list(ROLE_TABLES),
        "kinds_requested": [],
        "kinds": {kind: role_group_defaults() for kind in ROLE_KINDS},
        "directory": ROLE_DIR,
        "metadata_files_found": 0,
        "rights_files_found": 0,
        "roles_read": 0,
        "files_failed": [],
        "observations": [],
        "rows_written": 0,
        "roles_written": 0,
        "rights_written": 0,
        "templates_written": 0,
        "sources_written": 0,
        "removed_previous": 0,
        "removed_by_table": {table: 0 for table in ROLE_TABLES},
        "written_by_table": {table: 0 for table in ROLE_TABLES},
        "index_available": False,
        "index_role_records": 0,
        "index_rights_records": 0,
        "index_only": [],
        "file_only": [],
        "uuid_mismatch": [],
        "counts_by_content_state": {state: 0 for state in ROLE_CONTENT_STATES},
        "counts_by_target_resolve_state": {state: 0 for state in ROLE_TARGET_RESOLVE_STATES},
        "counts_by_right_name_state": {state: 0 for state in ROLE_RIGHT_NAME_STATES},
        "counts_by_right_value_state": {state: 0 for state in ROLE_RIGHT_VALUE_STATES},
        "counts_by_condition_state": {state: 0 for state in ROLE_CONDITION_STATES},
        "counts_by_declaration_state": {state: 0 for state in ROLE_DECLARATION_STATES},
        "targets_total": 0,
        "targets_distinct": 0,
        "rights_total": 0,
        "restrictions_total": 0,
        "restrictions_with_call": 0,
        "restrictions_no_call": 0,
        "restrictions_with_field": 0,
        "restrictions_called_own_role": 0,
        "restrictions_called_other_role": 0,
        "template_occurrences": 0,
        "template_names_total": 0,
        "template_texts_distinct": 0,
        "unknown_right_names": {},
        "unexpected_tags": {},
        "flag_missing": {},
        "flag_unknown_form": {},
        "duplicate_targets": [],
        "duplicate_right_names": [],
        "empty_condition_elements": 0,
        "targets_without_name": 0,
        "rights_without_name": 0,
        "templates_without_name": 0,
        "templates_without_text": 0,
        "name_file_mismatch": [],
        "roles_without_uuid": [],
        "sources_without_uuid": [],
        "content_file_missing": [],
        "ambiguous_template_calls": [],
        "statistics_refreshed": 0,
        "warnings": [],
    }


def format_roles_lines(result: Dict[str, Any], indent: str = "") -> List[str]:
    """Текст стадии S4d по закрытому контракту `roles_defaults()` (C1, C3).

    Формат один для двух контуров: раздела карточки `load_1c_catalog_tool` и ответа
    отдельного инструмента, который заводит шаг П5 (прецедент V45/V46/V48). Отказ форматёр
    называет сам («Стадия не выполнена» / «Стадия не удалась»), вызывающий причину не
    повторяет. Граница круга печатается и при успехе: «строки записаны» не равно «о ролях
    сохранено всё», а пустой перечень прав без этой строки читался бы как «прав нет».
    Неперечисленные ключи читаются нулями (C1).

    Имя — `format_roles_lines`, а не `format_roles_answer` (план, раздел 5): форматёры
    четырёх стадий слоя называются по одному образцу (`format_root_modules_lines`,
    `format_child_object_lines`, `format_session_parameters_lines`), и пятому дано то же
    имя — два имени у одного действия разъезжаются при первой же правке. Уточнение
    записано планом узла (раздел П4).
    """
    lines: List[str] = []
    if not result:
        return lines

    if not result.get("success"):
        reason = result.get("error") or result.get("reason") or "загрузчик не назвал причину"
        prefix = ("Стадия не выполнена" if result.get("status") in (None, STATUS_NOT_RUN)
                  else "Стадия не удалась")
        lines.append(f"{indent}{prefix}: {reason}")
        lines.append(f"{indent}{ROLES_REPEAT_HINT}")
        for warning in result.get("warnings") or []:
            lines.append(f"{indent}⚠️ {warning}")
        return lines

    removed_by_table = result.get("removed_by_table") or {}
    written_by_table = result.get("written_by_table") or {}
    lines.append(
        f"{indent}Записано строк по таблицам: "
        + ", ".join(f"{table}={int(written_by_table.get(table) or 0)}"
                    for table in ROLE_TABLES)
        + f"; всего {int(result.get('rows_written') or 0)} (ролей "
          f"{int(result.get('roles_read') or 0)}, прав "
          f"{int(result.get('rights_total') or 0)})"
    )
    lines.append(
        f"{indent}Файлов: метаданных {int(result.get('metadata_files_found') or 0)}, "
        f"содержимого прав {int(result.get('rights_files_found') or 0)} "
        f"(каталог {result.get('directory') or ROLE_DIR}/)"
    )

    # Отдельный вход просит не весь круг (шаг П5). Незапрошенная группа обязана быть
    # названа: её нули в перечисленных выше таблицах неотличимы от «в конфигурации нет
    # ни ролей, ни прав» (C2), а строки этих таблиц этим вызовом не снимались.
    kinds = result.get("kinds") or {}
    skipped_kinds = [kind for kind in ROLE_KINDS
                     if not (kinds.get(kind) or {}).get("requested")]
    if skipped_kinds:
        untouched = sorted({table for kind in skipped_kinds
                            for table in ROLE_TABLES_BY_KIND[kind]})
        lines.append(
            f"{indent}Группы круга не запрашивались: "
            + ", ".join(f"{kind} — {ROLE_KIND_TITLES[kind]}" for kind in skipped_kinds)
            + f"; таблицы {', '.join(untouched)} этим вызовом не снимались и не "
              "записывались, и их нули не означают, что в конфигурации нет ролей или прав "
              "(признак `kinds` отдельного входа load_roles_tool)"
        )
    if int(result.get("removed_previous") or 0):
        lines.append(
            f"{indent}Снято прежних строк этой конфигурации: "
            + ", ".join(f"{table}={int(removed_by_table.get(table) or 0)}"
                        for table in ROLE_TABLES)
            + f"; всего {int(result.get('removed_previous') or 0)} — идемпотентность "
              "держится явным DELETE по configuration_uuid: внешнего ключа и каскада по "
              "конфигурации в схеме нет осознанно (прецедент V20.1)"
        )
    else:
        lines.append(f"{indent}Прежних строк этой конфигурации не снималось")

    content_counts = result.get("counts_by_content_state") or {}
    lines.append(
        f"{indent}Состояния содержимого ролей: "
        + ", ".join(f"{state}={int(content_counts.get(state) or 0)}"
                    for state in ROLE_CONTENT_STATES)
        + " — «прав нет» (empty_content), «файла содержимого нет» (indexed_no_file) и "
          "«файл вне перечня» (file_not_in_index) различаются состоянием строки, а не "
          "нулём прав (Q6 узла V49, вариант A)"
    )

    resolve_counts = result.get("counts_by_target_resolve_state") or {}
    lines.append(
        f"{indent}Целей {int(result.get('targets_total') or 0)} "
        f"(различающихся {int(result.get('targets_distinct') or 0)}); состояния "
        "разрешения: "
        + ", ".join(f"{state}={int(resolve_counts.get(state) or 0)}"
                    for state in ROLE_TARGET_RESOLVE_STATES)
        + " — неразрешённая цель остаётся строкой с состоянием и неполным путём, а не "
          "молчанием (Q3)"
    )

    name_counts = result.get("counts_by_right_name_state") or {}
    value_counts = result.get("counts_by_right_value_state") or {}
    lines.append(
        f"{indent}Права {int(result.get('rights_total') or 0)}: имена — "
        + ", ".join(f"{state}={int(name_counts.get(state) or 0)}"
                    for state in ROLE_RIGHT_NAME_STATES)
        + "; значения — "
        + ", ".join(f"{state}={int(value_counts.get(state) or 0)}"
                    for state in ROLE_RIGHT_VALUE_STATES)
        + " — состояния называют текст `<value>` файла прав (true/false), а не правомочие "
          "роли: замер O1 (30.10.2026) даёт у роли `ПолныеПрава` все строки со значением "
          "false при флагах `setForNewObjects=true` / `setForAttributesByDefault=true`, а у "
          "`АдминистраторСистемы` — все со значением true; читать `denied` как «роль не "
          "может» этот замер не позволяет (позиция O1 плана, раздел 9)"
    )
    for name, count in sorted((result.get("unknown_right_names") or {}).items())[:10]:
        lines.append(
            f"{indent}  ⚠️ имя права вне словаря разбора: {name} ({count}) — XSD вида "
            "отсутствует (O5), имя сохраняется текстом и состоянием `unknown_name`"
        )

    condition_counts = result.get("counts_by_condition_state") or {}
    lines.append(
        f"{indent}Ограничений {int(result.get('restrictions_total') or 0)}: состояния — "
        + ", ".join(f"{state}={int(condition_counts.get(state) or 0)}"
                    for state in ROLE_CONDITION_STATES)
        + f"; с опознанным вызовом {int(result.get('restrictions_with_call') or 0)} "
          f"(своей роли {int(result.get('restrictions_called_own_role') or 0)}, чужой "
          f"{int(result.get('restrictions_called_other_role') or 0)}), без вызова "
          f"{int(result.get('restrictions_no_call') or 0)}, с полем <field> "
          f"{int(result.get('restrictions_with_field') or 0)} — два круга вызовов "
          "считаются раздельно, потому что круг их деклараций разный (замер 2.7)"
    )
    lines.append(
        f"{indent}Шаблоны ограничений: вхождений "
        f"{int(result.get('template_occurrences') or 0)}, имён "
        f"{int(result.get('template_names_total') or 0)}, различных текстов "
        f"{int(result.get('template_texts_distinct') or 0)} — строка держится парой "
        "(имя, отпечаток), поэтому «тот же текст под другим именем» и «то же имя с другим "
        "текстом» различимы (Q5, O6)"
    )

    declaration_counts = result.get("counts_by_declaration_state") or {}
    lines.append(
        f"{indent}Дескрипторы файлов содержимого: "
        + ", ".join(f"{state}={int(declaration_counts.get(state) or 0)}"
                    for state in ROLE_DECLARATION_STATES)
        + " — «запись индекса без файла» является отдельной строкой, а не отсутствием "
          "строки (Q8 узла V49, вариант A)"
    )

    if not result.get("index_available"):
        lines.append(
            f"{indent}Индекс состава не читается — сверка файлов с перечнем и разрешение "
            "целей невозможны, и «объекта нет в перечне» от «перечень этой конфигурации не "
            "загружен» этим не отличить"
        )
    else:
        index_only = result.get("index_only") or []
        file_only = result.get("file_only") or []
        uuid_mismatch = result.get("uuid_mismatch") or []
        lines.append(
            f"{indent}Сверка с индексом состава: записей `Role.<Имя>` "
            f"{int(result.get('index_role_records') or 0)}, записей `Role.<Имя>.Rights` "
            f"{int(result.get('index_rights_records') or 0)}; записей перечня без файла "
            f"{len(index_only)}, файлов без записи перечня {len(file_only)}, несовпадений "
            f"uuid {len(uuid_mismatch)} — нули названы числом, потому что четыре "
            "замеренные выгрузки дают именно нули, а подразумевать их нельзя"
        )
        for name in index_only[:10]:
            lines.append(f"{indent}  ⚠️ запись индекса без файла метаданных: {name}")
        for name in file_only[:10]:
            lines.append(f"{indent}  ⚠️ файл метаданных без записи индекса: {name}")
        for item in uuid_mismatch[:10]:
            lines.append(
                f"{indent}  ⚠️ uuid файла роли {item.get('object_name')}: файл "
                f"{item.get('file_uuid')} не совпадает с uuid индекса "
                f"{item.get('index_uuid')}"
            )

    for name in (result.get("content_file_missing") or [])[:10]:
        lines.append(
            f"{indent}  ⚠️ у роли, описанной файлом метаданных, нет ни файла "
            f"содержимого, ни записи индекса: {name}"
        )
    for name, count in sorted((result.get("flag_missing") or {}).items())[:10]:
        lines.append(
            f"{indent}  ⚠️ элемент флага содержимого в файле отсутствует: {name} ({count}) "
            "— NULL означает «флага никогда не было», а не `false`"
        )
    for name, count in sorted((result.get("flag_unknown_form") or {}).items())[:10]:
        lines.append(f"{indent}  ⚠️ флаг в незнакомой форме: {name} ({count})")
    for item in (result.get("ambiguous_template_calls") or [])[:10]:
        lines.append(
            f"{indent}  ⚠️ вызов шаблона разрешился двум декларациям: роль "
            f"{item.get('role')}, цель {item.get('target')}, право {item.get('right')}"
        )
    for item in (result.get("duplicate_targets") or [])[:10]:
        lines.append(f"{indent}  ⚠️ повторяющаяся цель в файле роли: {item}")
    for item in (result.get("duplicate_right_names") or [])[:10]:
        lines.append(f"{indent}  ⚠️ повторяющееся право одной цели: {item}")
    for item in (result.get("name_file_mismatch") or [])[:10]:
        lines.append(
            f"{indent}  ⚠️ <Name> файла {item.get('file')} не совпало с именем файла "
            f"{item.get('name_expected')} (в файле {item.get('name_in_file')})"
        )
    for name, count in sorted((result.get("unexpected_tags") or {}).items())[:10]:
        lines.append(f"{indent}  ⚠️ незнакомый тег файла прав: {name} ({count})")
    for observation in (result.get("observations") or [])[:10]:
        lines.append(f"{indent}  ⚠️ круг каталога: {observation[0]} — {observation[1]}")
    for failure in (result.get("files_failed") or [])[:10]:
        lines.append(f"{indent}  ⚠️ файл не разобран: {failure.get('source_path')} — "
                     f"{failure.get('reason')}")
    for key in ("empty_condition_elements", "targets_without_name", "rights_without_name",
                "templates_without_name", "templates_without_text"):
        if int(result.get(key) or 0):
            lines.append(f"{indent}  ⚠️ {key}: {int(result.get(key) or 0)}")
    for key in ("roles_without_uuid", "sources_without_uuid"):
        if result.get(key):
            lines.append(
                f"{indent}  ⚠️ {key}: "
                + ", ".join(str(item) for item in (result.get(key) or [])[:10])[:200]
            )

    refreshed = int(result.get("statistics_refreshed") or 0)
    if refreshed:
        lines.append(
            f"{indent}Статистика таблиц {', '.join(ROLE_TABLES)} пересобрана (ANALYZE): "
            f"{refreshed} — без неё читатели витрин текущего состояния платят минутами "
            "(мера V46)"
        )
    for warning in result.get("warnings") or []:
        lines.append(f"{indent}⚠️ {warning}")
    lines.append(f"{indent}Граница: {ROLES_BOUNDARY}")
    return lines




def common_attributes_separation_defaults() -> Dict[str, Any]:
    """Один блок разделения данных с нулями (C1).

    Разбивка ведётся по двум осям, а не по одной: `by_parse_state` отвечает на вопрос
    «было ли значение в файле» (`empty_value` — блока нет или он пуст, 12 из 16 файлов на
    каждый блок по замеру 2.7), `by_resolve_state` — на вопрос «найдена ли цель в индексе
    состава» (Q3). Одна ось не отличает «разделения нет» от «разделение есть, цель
    неразрешима», а это разные факты (C2).
    """
    return {
        "by_parse_state": {state: 0 for state in CA_SEPARATION_STATES},
        "by_resolve_state": {state: 0 for state in CA_TARGET_RESOLVE_STATES},
    }


def common_attributes_defaults() -> Dict[str, Any]:
    """Закрытый контракт стадии S4e с нулями (C1, C2, C3).

    Словарь плоский — тот же, что возвращает слой `load_common_attributes`; конвейер
    вкладывает его в свой ключ `common_attributes` без переименования (C3). `status`
    различает «стадия не выполнялась» (`not_run`, C2) и «выполнилась с отказом» (`error`).

    Имена ключей сводки совпадают с именами разбора
    `src/configuration_common_attributes.py` намеренно (прецедент `SUMMARY_KEYS` узлов
    V46/V48/V49): неперечисленный ключ контракта читается нулём, а не исчезает, а
    незнакомый ключ разбора не попадает в ответ, которого карточка не обещала. Ключей
    `rows` / `targets` здесь нет намеренно: это строки записи (до 817 строк применения на
    BP3), а не сводка состояния.

    Что обязан назвать ответ отдельно (план, раздел 5):

    * `removed_by_table` / `written_by_table` — двумя таблицами, а не одним числом: «записано
      7» и «записано 7 реквизитов + 817 применений» для читателя карточки — разные факты;
    * `counts_by_properties_state` с `unknown_value_properties` / `unknown_properties` —
      незнакомое ЗНАЧЕНИЕ словарного свойства и незнакомый ТЕГ файла различаются состоянием и
      именами виновников, потому что второе требует пересмотра круга раньше первого (Q7, A);
    * словари блока `<Type>` (`counts_by_type_state`, `types_multiplicity`, `types_by_class`) —
      `absent` и `unknown_form` различаются: пустой тип не читается как «типа нет в выгрузке»
      (замер 2.3, ограничение `type_parse_state = 'parsed' ⇒ types <> '[]'`);
    * `counts_by_use_state` и `counts_by_target_resolve_state` — «применяется / не применяется»
      и «цель разрешена / нет» являются ответом о цели, а не потерянной строкой (Q3, Q4);
    * `separation_by_block` — по трём блокам отдельно: «блока нет» (`empty_value`, 12 из 16
      файлов) и «блок есть, цель неразрешима» различимы только помесячно (замер 2.7, Q5);
    * `index_only` / `file_only` / `uuid_mismatch` — расхождения файла и перечня: четыре
      замеренные выгрузки дают нули, и нули обязаны быть названы, а не подразумеваться;
    * `max_targets_per_file` — распределение, а не только итог: 688 целей в одном файле BP3 и
      688 целей по разным файлам — разные выгрузки (замер 2.4).
    """
    return {
        "status": STATUS_NOT_RUN,
        "success": False,
        "error": None,
        "reason": None,
        "stage": STAGE_COMMON_ATTRIBUTES,
        "configuration_id": None,
        "configuration_uuid": None,
        "configuration_name": None,
        "tables": list(COMMON_ATTRIBUTES_TABLES),
        "directory": COMMON_ATTRIBUTES_DIR,
        "files_found": 0,
        "files_read": 0,
        "files_failed": [],
        "observations": [],
        "rows_written": 0,
        "attributes_written": 0,
        "targets_written": 0,
        "removed_previous": 0,
        "removed_by_table": {table: 0 for table in COMMON_ATTRIBUTES_TABLES},
        "written_by_table": {table: 0 for table in COMMON_ATTRIBUTES_TABLES},
        "index_available": False,
        "index_kind_records": 0,
        "index_only": [],
        "file_only": [],
        "uuid_mismatch": [],
        "counts_by_properties_state": {state: 0 for state in CA_PROPERTIES_STATES},
        "unknown_properties": {},
        "unknown_value_properties": {},
        "unexpected_tags": {},
        "counts_by_type_state": {state: 0 for state in CA_TYPE_STATES},
        "types_multiplicity": {mult: 0 for mult in CA_MULTIPLICITY_VALUES},
        "types_by_class": {kind: 0 for kind in CA_TYPE_CLASS_VALUES},
        "types_total": 0,
        "types_parsed": 0,
        "types_object_ref_resolved": 0,
        "types_unresolved_total": 0,
        "types_unresolved": [],
        "value_tag_mismatch": [],
        "counts_by_content_state": {state: 0 for state in CA_CONTENT_STATES},
        "targets_total": 0,
        "targets_distinct": 0,
        "max_targets_per_file": 0,
        "counts_by_use_state": {state: 0 for state in CA_USE_STATES},
        "counts_by_target_resolve_state": {state: 0 for state in CA_TARGET_RESOLVE_STATES},
        "counts_by_item_cond_state": {state: 0 for state in CA_ITEM_COND_STATES},
        "targets_by_kind": {},
        "duplicate_targets": [],
        "unresolved_targets": [],
        "separation_parsed": 0,
        "separation_empty": 0,
        "separation_unknown_form": 0,
        "separation_by_block": {
            block: common_attributes_separation_defaults()
            for block in COMMON_ATTRIBUTE_SEPARATION_BLOCKS
        },
        "separation_unresolved_total": 0,
        "separation_unresolved": [],
        "unresolved_refs": [],
        "namespace_prefixes": [],
        "statistics_refreshed": 0,
        "warnings": [],
    }



def format_common_attributes_lines(result: Dict[str, Any], indent: str = "") -> List[str]:
    """Текст стадии S4e по закрытому контракту `common_attributes_defaults()` (C1, C3).

    Формат один для двух контуров: раздела карточки `load_1c_catalog_tool` и ответа
    отдельного инструмента, который заводит шаг П5 (прецедент V45/V46/V48/V49). Отказ
    форматёр называет сам («Стадия не выполнена» / «Стадия не удалась»), вызывающий причину
    не повторяет. Граница круга печатается и при успехе: «строки записаны» не равно «об общих
    реквизитах сохранено всё», а пустой блок разделения без этой строки читался бы как
    «разделения нет». Неперечисленные ключи читаются нулями (C1).

    Имя — `format_common_attributes_lines`, а не `format_common_attributes_answer`: форматёры
    стадий слоя называются по одному образцу (`format_root_modules_lines`,
    `format_child_object_lines`, `format_session_parameters_lines`, `format_roles_lines`),
    и пятому дано то же имя — два имени у одного действия разъезжаются при первой же правке
    (план узла, раздел 5).
    """
    lines: List[str] = []
    if not result:
        return lines

    if not result.get("success"):
        reason = result.get("error") or result.get("reason") or "загрузчик не назвал причину"
        prefix = ("Стадия не выполнена" if result.get("status") in (None, STATUS_NOT_RUN)
                  else "Стадия не удалась")
        lines.append(f"{indent}{prefix}: {reason}")
        lines.append(f"{indent}{COMMON_ATTRIBUTES_REPEAT_HINT}")
        for warning in result.get("warnings") or []:
            lines.append(f"{indent}⚠️ {warning}")
        return lines

    removed_by_table = result.get("removed_by_table") or {}
    written_by_table = result.get("written_by_table") or {}
    lines.append(
        f"{indent}Записано строк по таблицам: "
        + ", ".join(f"{table}={int(written_by_table.get(table) or 0)}"
                    for table in COMMON_ATTRIBUTES_TABLES)
        + f"; всего {int(result.get('rows_written') or 0)} (реквизитов "
          f"{int(result.get('files_read') or 0)}, применений "
          f"{int(result.get('targets_total') or 0)})"
    )
    lines.append(
        f"{indent}Файлов регистрации: {int(result.get('files_found') or 0)} "
        f"(каталог {result.get('directory') or COMMON_ATTRIBUTES_DIR}/, позиция 2.5 списка)"
    )
    if int(result.get("removed_previous") or 0):
        lines.append(
            f"{indent}Снято прежних строк этой конфигурации: "
            + ", ".join(f"{table}={int(removed_by_table.get(table) or 0)}"
                        for table in COMMON_ATTRIBUTES_TABLES)
            + f"; всего {int(result.get('removed_previous') or 0)} — идемпотентность "
              "держится явным DELETE по configuration_uuid: внешнего ключа и каскада по "
              "конфигурации в схеме нет осознанно (прецедент V20.1); строки применения "
              "снимаются раньше строк реквизита, иначе каскад FK снял бы их молча (M7)"
        )
    else:
        lines.append(f"{indent}Прежних строк этой конфигурации не снималось")

    props = result.get("counts_by_properties_state") or {}
    lines.append(
        f"{indent}Состояния свойств: "
        + ", ".join(f"{state}={int(props.get(state) or 0)}"
                    for state in CA_PROPERTIES_STATES)
        + " — незнакомое ЗНАЧЕНИЕ словарного свойства и незнакомый ТЕГ файла различаются "
          "состоянием и именами виновников: второе требует пересмотра круга свойств раньше "
          "первого (Q7, вариант A; CHECK на значения свойств не ставится намеренно)"
    )
    for name, count in sorted((result.get("unknown_value_properties") or {}).items())[:10]:
        lines.append(
            f"{indent}  ⚠️ значение свойства вне измеренного словаря: {name} ({count}) — "
            "значение сохранено текстом, состояние строки `unknown_value`"
        )
    for name, count in sorted((result.get("unknown_properties") or {}).items())[:10]:
        lines.append(f"{indent}  ⚠️ тег свойства вне словаря 38 тегов (замер 2.2): {name} "
                     f"({count}) — круг вида требует пересмотра")
    for tag, count in sorted((result.get("unexpected_tags") or {}).items())[:10]:
        lines.append(f"{indent}  ⚠️ незнакомый тег файла: {tag} ({count})")

    type_states = result.get("counts_by_type_state") or {}
    multiplicity = result.get("types_multiplicity") or {}
    classes = result.get("types_by_class") or {}
    lines.append(
        f"{indent}Блок Type: состояний — "
        + ", ".join(f"{state}={int(type_states.get(state) or 0)}"
                    for state in CA_TYPE_STATES)
        + "; кратность — "
        + ", ".join(f"{mult}={int(multiplicity.get(mult) or 0)}"
                    for mult in CA_MULTIPLICITY_VALUES)
        + f"; записей значений {int(result.get('types_total') or 0)}: "
        + ", ".join(f"{kind}={int(classes.get(kind) or 0)}"
                    for kind in CA_TYPE_CLASS_VALUES)
        + f"; записей распознано {int(result.get('types_parsed') or 0)}, ссылок на объект "
          f"разрешено {int(result.get('types_object_ref_resolved') or 0)}, неразрешённых "
          f"записей {int(result.get('types_unresolved_total') or 0)} — `absent` и "
          "`unknown_form` различаются состоянием строки: пустой тип не читается как «типа "
          "нет в выгрузке» (замер 2.3)"
    )

    for item in (result.get("types_unresolved") or [])[:10]:
        lines.append(
            f"{indent}  ⚠️ запись типа не разрешена: файл {item.get('source_path')}, "
            f"значение {item.get('value')}, класс {item.get('class')} — "
            "ссылка остаётся записью с состоянием, а не пустым типом"
        )
    for item in (result.get("value_tag_mismatch") or [])[:10]:
        lines.append(
            f"{indent}  ⚠️ тегов <v8:Type>/<xs:type> в файле {item.get('tags')}, "
            f"разобранных записей {item.get('entries')} (файл "
            f"{item.get('source_path')}) — расчёт кратности по числу записей требует проверки"
        )

    content_counts = result.get("counts_by_content_state") or {}
    use_counts = result.get("counts_by_use_state") or {}
    resolve_counts = result.get("counts_by_target_resolve_state") or {}
    cond_counts = result.get("counts_by_item_cond_state") or {}
    lines.append(
        f"{indent}Перечни применения: состояний — "
        + ", ".join(f"{state}={int(content_counts.get(state) or 0)}"
                    for state in CA_CONTENT_STATES)
        + f"; строк применения {int(result.get('targets_total') or 0)} (различающихся целей "
          f"{int(result.get('targets_distinct') or 0)}, максимум в одном файле "
          f"{int(result.get('max_targets_per_file') or 0)} — распределение называется, "
          "потому что 688 целей в одном файле и 688 целей по разным файлам это разные "
          "выгрузки, замер 2.4)"
    )
    lines.append(
        f"{indent}Применение: "
        + ", ".join(f"{state}={int(use_counts.get(state) or 0)}" for state in CA_USE_STATES)
        + "; разрешение целей — "
        + ", ".join(f"{state}={int(resolve_counts.get(state) or 0)}"
                    for state in CA_TARGET_RESOLVE_STATES)
        + "; условие разделения позиции — "
        + ", ".join(f"{state}={int(cond_counts.get(state) or 0)}"
                    for state in CA_ITEM_COND_STATES)
        + " — `empty_value` у условия разделения является состоянием пустого "
          "самозакрывающегося тега (замер 2.4: такая форма во всех строках корпуса), "
          "непустая форма — позиция O4 плана, узла загрузки нет"
    )
    kinds = result.get("targets_by_kind") or {}
    if kinds:
        lines.append(
            f"{indent}Цели применения по видам: "
            + ", ".join(f"{kind}={int(count)}" for kind, count in sorted(kinds.items())[:20])
            + f" (видов {len(kinds)}) — виды названы замером 2.5; объекты этих видов этим "
              "узлом не загружаются, связь разрешается именем строки индекса состава (Q3)"
        )
    for item in (result.get("unresolved_targets") or [])[:10]:
        lines.append(
            f"{indent}  ⚠️ цель применения не разрешена: файл {item.get('source_path')}, "
            f"цель {item.get('target_full_name')}, состояние "
            f"{item.get('target_resolve_state')}, неполный путь "
            f"{item.get('unresolved_path')} — строка остаётся с состоянием, а не теряется"
        )
    for item in (result.get("duplicate_targets") or [])[:10]:
        lines.append(
            f"{indent}  ⚠️ повторяющаяся цель в перечне одного реквизита: файл "
            f"{item.get('source_path')}, цель {item.get('target')} — ключ строки применения "
            "держится порядком (`ordinal`), повтор называется, а не схлопывается (замер 2.10 "
            "даёт нули)"
        )

    separation = result.get("separation_by_block") or {}
    for block in COMMON_ATTRIBUTE_SEPARATION_BLOCKS:
        block_state = separation.get(block) or {}
        parse_counts = block_state.get("by_parse_state") or {}
        resolve_state_counts = block_state.get("by_resolve_state") or {}
        lines.append(
            f"{indent}Разделение, блок {block}: "
            + ", ".join(f"{state}={int(parse_counts.get(state) or 0)}"
                        for state in CA_SEPARATION_STATES)
            + "; разрешение — "
            + ", ".join(f"{state}={int(resolve_state_counts.get(state) or 0)}"
                        for state in CA_TARGET_RESOLVE_STATES)
        )
    lines.append(
        f"{indent}Разделение всего: непустых ссылок "
        f"{int(result.get('separation_parsed') or 0)}, пустых блоков "
        f"{int(result.get('separation_empty') or 0)}, незнакомых форм "
        f"{int(result.get('separation_unknown_form') or 0)}, неразрешённых "
        f"{int(result.get('separation_unresolved_total') or 0)} — по замеру 2.7 непустых "
        "блоков 12 из 48 на четырёх выгрузках; пустой блок является состоянием строки, а не "
        "пустой ссылкой"
    )
    for item in (result.get("separation_unresolved")
                 or result.get("unresolved_refs") or [])[:10]:
        lines.append(
            f"{indent}  ⚠️ ссылка разделения не разрешена: файл {item.get('source_path')}, "
            f"свойство {item.get('property')}, текст {item.get('ref_text')}, состояние "
            f"{item.get('state')} — ссылка остаётся текстом и состоянием (Q3)"
        )

    if not result.get("index_available"):
        lines.append(
            f"{indent}Индекс состава не читается — сверка файлов с перечнем и разрешение "
            "целей применения и ссылок разделения невозможны, и «объекта нет в перечне» от "
            "«перечень этой конфигурации не загружен» этим не отличить"
        )
    else:
        index_only = result.get("index_only") or []
        file_only = result.get("file_only") or []
        uuid_mismatch = result.get("uuid_mismatch") or []
        lines.append(
            f"{indent}Сверка с индексом состава: записей `CommonAttribute.<Имя>` "
            f"{int(result.get('index_kind_records') or 0)}; записей перечня без файла "
            f"{len(index_only)}, файлов без записи {len(file_only)}, расхождений uuid "
            f"{len(uuid_mismatch)} — все четыре замеренные выгрузки дают нули (замер 2.9), "
            "и нули обязаны быть названы, а не подразумеваться"
        )
        for name in index_only[:10]:
            lines.append(f"{indent}  ⚠️ запись индекса без файла регистрации: {name}")
        for name in file_only[:10]:
            lines.append(f"{indent}  ⚠️ файл регистрации без записи индекса: {name}")
        for item in uuid_mismatch[:10]:
            lines.append(
                f"{indent}  ⚠️ uuid файла {item.get('source_path')}: файл "
                f"{item.get('file_uuid')} не совпадает с uuid индекса "
                f"{item.get('index_uuid')}"
            )

    prefixes = result.get("namespace_prefixes") or []
    if prefixes:
        lines.append(
            f"{indent}Префиксы пространств имён файлов вида: "
            + ", ".join(str(item) or "(по умолчанию)" for item in prefixes[:20])
            + f" (префиксов {len(prefixes)}) — словарь URI круга назван замером 2.1; "
              "префикс вне этого словаря требует объяснения, а не молчаливой поддержки "
              "(пустой префикс — корневой xmlns файла регистрации, он есть во всех "
              "четырех выгрузках)"
        )
    for observation in (result.get("observations") or [])[:10]:
        lines.append(f"{indent}  ⚠️ круг каталога: {observation[0]} — {observation[1]}")
    for failure in (result.get("files_failed") or [])[:10]:
        lines.append(f"{indent}  ⚠️ файл не разобран: {failure.get('source_path')} — "
                     f"{failure.get('reason')}")

    refreshed = int(result.get("statistics_refreshed") or 0)
    if refreshed:
        lines.append(
            f"{indent}Статистика таблиц {', '.join(COMMON_ATTRIBUTES_TABLES)} пересобрана "
            f"(ANALYZE): {refreshed} — без неё читатели витрин текущего состояния платят "
            "минутами (мера V46)"
        )
    for warning in result.get("warnings") or []:
        lines.append(f"{indent}⚠️ {warning}")
    lines.append(f"{indent}Граница: {COMMON_ATTRIBUTES_BOUNDARY}")
    return lines


# ── узел V51 (стадия S4f, позиция 2.6 нормативного списка), шаг П4 ────────────────────
# Имена ключей сводки совпадают с ключами разбора `src/configuration_exchange_plans.py`
# намеренно (прецедент `SUMMARY_KEYS` узлов V46/V48/V49/V50): неперечисленный ключ
# контракта читается нулём, а не исчезает, а незнакомый ключ разбора не попадает в ответ,
# которого карточка не обещала. Ключей `rows` / `attributes` / `content` нет: это строки
# записи (на три выгрузки — 22 515 строк только перечня `<Content>`), а не сводка состояния.
# Перечней дескрипторов (`object_module_files`, `command_module_files`,
# `standard_attributes`) тоже нет: ответ стадии называет их числом (`*_total`), а не
# содержимым — прецедент `sources` / `source_rows` узла V49.
# Словарей состояний внутри группы нет: состояния считает сводка круга, потому что одна
# строка вида участвует в двух группах (`exchange_plans` и `slots`), и два счётчика одного
# состояния разошлись бы при первой же правке.
def exchange_plan_group_defaults() -> Dict[str, Any]:
    """Одна группа правочного вызова `kinds` с нулями (C1, C2, C3).

    `requested` отделяет «группу не просили» от «таких объектов в выгрузке нет»: по одним
    нулям эти два ответа неразличимы, а строки незапрошенных таблиц этим вызовом не
    снимались (правило V49). Таблиц, которые группа снимает и заполняет, здесь нет: их
    называет форматёр через `group_tables()` разбора — второй перечень таблиц в проекте
    появился бы вместе с этим ключом (прецедент `role_group_defaults()` узла V49).
    """
    return {
        "requested": False,
        "written": 0,
        "removed_previous": 0,
    }


def exchange_plans_defaults() -> Dict[str, Any]:
    """Закрытый контракт стадии S4f с нулями (C1, C2, C3).

    Словарь плоский — тот же, что возвращает слой `load_exchange_plans`; конвейер вкладывает
    его в свой ключ `exchange_plans` без переименования (C3). Отдельно обязаны быть названы:
    числа по таблицам (`removed_by_table`/`written_by_table`), замкнутые словари состояний
    включая нули (`empty_content`, `absent`, `present_not_indexed` различимы состоянием, а не
    нулём), расхождения двух ног круга — файлов регистрации с индексом состава
    (`index_only`/`file_only`/`uuid_mismatch`), детей с индексом (`child_mismatches`,
    `index_pseudo_entries`) и объявления вида с его каталогом (`declaration_mismatches`), а
    также дескрипторы файлов модулей (Q8: тела пишет V47) и признак запрашивания групп.
    Перечнем заголовка `configurations.exchange_plans` (третьей ногой круга, узел V43) ответ
    стадии не оперирует: их сравнение с файлами и индексом — инвариант проверки
    `tools/check_v51_exchange_plans.py` (шаг П6), а не число, которое стадия обязана обещать.
    """
    return {
        "status": STATUS_NOT_RUN,
        "success": False,
        "error": None,
        "reason": None,
        "stage": STAGE_EXCHANGE_PLANS,
        "configuration_id": None,
        "configuration_uuid": None,
        "configuration_name": None,
        "tables": list(EXCHANGE_PLAN_TABLES),
        "kinds_requested": [],
        "kinds": {kind: exchange_plan_group_defaults() for kind in EXCHANGE_PLAN_LOAD_GROUPS},
        "directory": EXCHANGE_PLAN_DIR,
        "files_found": 0,
        "files_read": 0,
        "files_failed": [],
        "observations": [],
        "rows_written": 0,
        "exchange_plans_written": 0,
        "attributes_written": 0,
        "tabular_sections_written": 0,
        "forms_written": 0,
        "form_ext_written": 0,
        "templates_written": 0,
        "commands_written": 0,
        "content_written": 0,
        "removed_previous": 0,
        "removed_by_table": {table: 0 for table in EXCHANGE_PLAN_TABLES},
        "written_by_table": {table: 0 for table in EXCHANGE_PLAN_TABLES},
        "index_available": False,
        "index_kind_records": 0,
        "index_only": [],
        "file_only": [],
        "uuid_mismatch": [],
        "child_mismatch_total": 0,
        "child_mismatches": [],
        "declaration_mismatch_total": 0,
        "declaration_mismatches": [],
        "index_pseudo_entries_total": 0,
        "index_pseudo_entries": [],
        "counts_by_properties_state": {state: 0 for state in EXCHANGE_PLAN_PROPERTIES_STATES},
        "counts_by_children_state": {state: 0 for state in EXCHANGE_PLAN_CHILD_STATES},
        "counts_by_standard_attributes_state": {
            state: 0 for state in EXCHANGE_PLAN_STANDARD_ATTRIBUTE_STATES},
        "counts_by_content_state": {state: 0 for state in EXCHANGE_PLAN_CONTENT_STATES},
        "counts_by_slot_state": {state: 0 for state in EXCHANGE_PLAN_SLOT_STATES},
        "counts_by_target_resolve_state": {state: 0 for state in EXCHANGE_PLAN_TARGET_STATES},
        "counts_by_auto_record_state": {state: 0 for state in EXCHANGE_PLAN_AUTO_RECORD_STATES},
        "counts_by_circle_discrepancy": {
            state: 0 for state in EXCHANGE_PLAN_CIRCLE_DISCREPANCIES},
        "counts_by_child_mismatch": {},
        "counts_by_form_ext_format": {},
        "counts_by_template_ext_format": {},
        "attributes_own": 0,
        "attributes_columns": 0,
        "tabular_sections_total": 0,
        "commands_total": 0,
        "forms_total": 0,
        "form_ext_total": 0,
        "templates_total": 0,
        "object_module_files_total": 0,
        "command_module_files_total": 0,
        "counts_by_object_module_kind": {},
        "content_total": 0,
        "content_unresolved_total": 0,
        "standard_attributes_total": 0,
        "standard_attributes_distinct": 0,
        "standard_attribute_names": {},
        "text_truncated_total": 0,
        "ext_observations_total": 0,
        "counts_by_ext_observation": {},
        "ext_observations": [],
        "unknown_properties": {},
        "unknown_value_properties": {},
        "unexpected_child_tags": {},
        "statistics_refreshed": 0,
        "warnings": [],
    }


def format_exchange_plans_lines(result: Dict[str, Any], indent: str = "") -> List[str]:
    """Текст стадии S4f по закрытому контракту `exchange_plans_defaults()` (C1, C3).

    Формат один для двух контуров: раздела карточки `load_1c_catalog_tool` и ответа
    отдельного входа `load_exchange_plans_tool` (шаг П5) — прецеденты V45/V46/V48/V49/V50.
    Отказ форматёр называет сам, вызывающий причину не повторяет. Граница круга печатается и
    при успехе: «строки записаны» не равно «о плане обмена сохранено всё». Неперечисленные
    ключи читаются нулями (C1). Имя — `format_exchange_plans_lines`: форматёры стадий слоя
    называются по одному образцу.
    """
    lines: List[str] = []
    if not result:
        return lines

    if not result.get("success"):
        reason = result.get("error") or result.get("reason") or "загрузчик не назвал причину"
        prefix = ("Стадия не выполнена" if result.get("status") in (None, STATUS_NOT_RUN)
                  else "Стадия не удалась")
        lines.append(f"{indent}{prefix}: {reason}")
        lines.append(f"{indent}{EXCHANGE_PLAN_REPEAT_HINT}")
        for warning in result.get("warnings") or []:
            lines.append(f"{indent}⚠️ {warning}")
        return lines

    written_by_table = result.get("written_by_table") or {}
    removed_by_table = result.get("removed_by_table") or {}
    lines.append(
        f"{indent}Записано строк по таблицам: "
        + ", ".join(f"{table}={int(written_by_table.get(table) or 0)}"
                    for table in sorted(written_by_table))
        + f"; всего {int(result.get('rows_written') or 0)} (видов "
          f"{int(result.get('files_read') or 0)}, целей перечня "
          f"{int(result.get('content_total') or 0)})"
    )
    lines.append(
        f"{indent}Файлов регистрации вида: {int(result.get('files_found') or 0)} "
        f"(разобрано {int(result.get('files_read') or 0)}, каталог "
        f"{result.get('directory') or EXCHANGE_PLAN_DIR}/)"
    )

    # Отдельный вход просит не весь круг (Q5). Незапрошенная группа обязана быть названа:
    # её нули неотличимы от «планов обмена нет» (C2), а строки этих таблиц не снимались.
    kinds = result.get("kinds") or {}
    skipped = [kind for kind in EXCHANGE_PLAN_LOAD_GROUPS
               if not (kinds.get(kind) or {}).get("requested")]
    if skipped:
        untouched = sorted({table for kind in skipped
                            for table in exchange_plan_group_tables(kind)})
        lines.append(
            f"{indent}Группы круга не запрашивались: "
            + ", ".join(f"{kind} — {EXCHANGE_PLAN_GROUP_TITLES[kind]}" for kind in skipped)
            + f"; таблицы {', '.join(untouched)} этим вызовом не снимались и не "
              "записывались, и их нули не означают, что в конфигурации нет планов обмена "
              "или их детей"
        )
    if int(result.get("removed_previous") or 0):
        lines.append(
            f"{indent}Снято прежних строк этой конфигурации: "
            + ", ".join(f"{table}={int(removed_by_table.get(table) or 0)}"
                        for table in sorted(removed_by_table))
        )
    return _append_exchange_plan_detail(lines, result, indent)


def _append_exchange_plan_detail(lines: List[str], result: Dict[str, Any],
                                indent: str) -> List[str]:
    """Второй блок текста стадии S4f: состояния, дети, перечень, слоты, ноги круга.

    Разделение формата на две функции — только длина текста: форматёр обязан называть всё,
    что есть в контракте, и одно место чтения ответа при этом сохраняется (вызывающий зовёт
    `format_exchange_plans_lines`).
    """
    children_counts = result.get("counts_by_children_state") or {}
    properties_counts = result.get("counts_by_properties_state") or {}
    lines.append(
        f"{indent}Состояния строк вида: свойства — "
        + ", ".join(f"{state}={int(properties_counts.get(state) or 0)}"
                    for state in EXCHANGE_PLAN_PROPERTIES_STATES)
        + "; дети — "
        + ", ".join(f"{state}={int(children_counts.get(state) or 0)}"
                    for state in EXCHANGE_PLAN_CHILD_STATES)
    )
    lines.append(
        f"{indent}Дети вида: реквизиты {int(result.get('attributes_own') or 0)} своих + "
        f"{int(result.get('attributes_columns') or 0)} колонок табличных частей, табличных "
        f"частей {int(result.get('tabular_sections_total') or 0)}, форм "
        f"{int(result.get('forms_total') or 0)} (описаний "
        f"{int(result.get('form_ext_total') or 0)}), макетов "
        f"{int(result.get('templates_total') or 0)}, команд "
        f"{int(result.get('commands_total') or 0)} — сумма по видам обязана совпасть с "
        "записями индекса состава вида и его детей, иначе круг неполный; эталонные числа по "
        "четырём выгрузкам держит проверка `tools/check_v51_exchange_plans.py` (шаг П6)"
    )
    formats = result.get("counts_by_form_ext_format") or {}
    template_formats = result.get("counts_by_template_ext_format") or {}
    lines.append(
        f"{indent}Содержимое форм — "
        + ", ".join(f"{state}={int(formats.get(state) or 0)}"
                    for state in sorted(formats) or ["none"])
        + "; макетов — "
        + ", ".join(f"{state}={int(template_formats.get(state) or 0)}"
                    for state in sorted(template_formats) or ["none"])
        + f"; усечено по порогу слоя V13 {int(result.get('text_truncated_total') or 0)} — "
          "бинарная форма, описание формы и усечённое содержимое являются тремя разными "
          "состояниями, а не одним"
    )

    content_counts = result.get("counts_by_content_state") or {}
    resolve_counts = result.get("counts_by_target_resolve_state") or {}
    auto_counts = result.get("counts_by_auto_record_state") or {}
    lines.append(
        f"{indent}Перечень <Content>: состояний — "
        + ", ".join(f"{state}={int(content_counts.get(state) or 0)}"
                    for state in EXCHANGE_PLAN_CONTENT_STATES)
        + f"; целей {int(result.get('content_total') or 0)}, из них не разрешено "
          f"{int(result.get('content_unresolved_total') or 0)}; разрешение цели — "
        + ", ".join(f"{state}={int(resolve_counts.get(state) or 0)}"
                    for state in EXCHANGE_PLAN_TARGET_STATES)
        + "; AutoRecord — "
        + ", ".join(f"{state}={int(auto_counts.get(state) or 0)}"
                    for state in EXCHANGE_PLAN_AUTO_RECORD_STATES)
    )
    slot_counts = result.get("counts_by_slot_state") or {}
    lines.append(
        f"{indent}Слоты Ext/Help.xml и Ext/AdditionalIndexes.xml — "
        + ", ".join(f"{state}={int(slot_counts.get(state) or 0)}"
                    for state in EXCHANGE_PLAN_SLOT_STATES)
        + " — содержимое сохраняется исходным XML в jsonb (Q4, прецедент subsystems.Content)"
    )
    standard_counts = result.get("counts_by_standard_attributes_state") or {}
    lines.append(
        f"{indent}Стандартные реквизиты: состояний — "
        + ", ".join(f"{state}={int(standard_counts.get(state) or 0)}"
                    for state in EXCHANGE_PLAN_STANDARD_ATTRIBUTE_STATES)
        + f"; вхождений {int(result.get('standard_attributes_total') or 0)}, уникальных имён "
          f"{int(result.get('standard_attributes_distinct') or 0)} — строк по ним в схеме нет "
          "(их нет в индексе состава), наличие называется состоянием "
          "`present_not_indexed` (Q7), а не потерей"
    )
    lines.append(
        f"{indent}Файлы модулей вида (дескрипторы, тела пишет V47): объекта/менеджера "
        f"{int(result.get('object_module_files_total') or 0)}, команд "
        f"{int(result.get('command_module_files_total') or 0)} (Q8)"
    )

    if not result.get("index_available"):
        lines.append(
            f"{indent}Индекс состава не читается — сверка файлов с перечнем и разрешение "
            "целей перечня невозможны, и «объекта нет в перечне» от «перечень этой "
            "конфигурации не загружен» этим не отличить"
        )
    mismatch_counts = result.get("counts_by_circle_discrepancy") or {}
    lines.append(
        f"{indent}Расхождения файлов и индекса состава: "
        + ", ".join(f"{state}={int(mismatch_counts.get(state) or 0)}"
                    for state in EXCHANGE_PLAN_CIRCLE_DISCREPANCIES)
        + f"; расхождения детей с индексом "
          f"{int(result.get('child_mismatch_total') or 0)} (псевдозаписей индекса "
          f"{int(result.get('index_pseudo_entries_total') or 0)}), сверка объявления "
          f"вида с его каталогом — {int(result.get('declaration_mismatch_total') or 0)} — "
          "нули являются ответом, а не подразумеванием"
    )
    ext_counts = result.get("counts_by_ext_observation") or {}
    if ext_counts or result.get("observations"):
        lines.append(
            f"{indent}Наблюдения круга и о прочем в Ext/: "
            + ", ".join(f"{kind}={count}" for kind, count in sorted(ext_counts.items()))
            + "; наблюдений круга "
            + ", ".join(str(kind) for kind, _ in (result.get("observations") or []))
        )
    for failure in (result.get("files_failed") or [])[:10]:
        lines.append(f"{indent}  ⚠️ файл не разобран: {failure.get('source_path')} — "
                     f"{failure.get('reason')}")

    refreshed = int(result.get("statistics_refreshed") or 0)
    if refreshed:
        lines.append(
            f"{indent}Статистика таблиц {', '.join(EXCHANGE_PLAN_TABLES)} пересобрана "
            f"(ANALYZE): {refreshed} — без неё читатели витрин текущего состояния платят "
            "минутами (мера V46)"
        )
    for warning in result.get("warnings") or []:
        lines.append(f"{indent}⚠️ {warning}")
    lines.append(f"{indent}Граница: {EXCHANGE_PLAN_CIRCLE_BOUNDARY}")
    return lines

def format_filter_criteria_lines(result: Dict[str, Any], indent: str = "") -> List[str]:
    """Текст стадии S4g по закрытому контракту `filter_criteria_defaults()` (C1, C3).

    Формат один для двух контуров: раздела карточки `load_1c_catalog_tool` и ответа
    отдельного входа `load_filter_criteria_tool` (шаг П5) — прецеденты V45/V46/V48/V49/V50/V51.
    Отказ форматёр называет сам, вызывающий причину не повторяет. Групп `kinds` у вида нет
    (решение Q5, вариант A), поэтому блока «группы круга не запрашивались» здесь нет: он
    обещал бы раздельный вход дозагрузки, которого у стадии нет (в отличие от V51). Граница
    круга печатается и при успехе: «строки записаны» не равно «о критерии отбора сохранено
    всё». Неперечисленные ключи читаются нулями (C1). Имя —
    `format_filter_criteria_lines`: форматёры стадий слоя называются по одному образцу.
    """
    lines: List[str] = []
    if not result:
        return lines

    if not result.get("success"):
        reason = result.get("error") or result.get("reason") or "загрузчик не назвал причину"
        prefix = ("Стадия не выполнена" if result.get("status") in (None, STATUS_NOT_RUN)
                  else "Стадия не удалась")
        lines.append(f"{indent}{prefix}: {reason}")
        lines.append(f"{indent}{FILTER_CRITERIA_REPEAT_HINT}")
        for warning in result.get("warnings") or []:
            lines.append(f"{indent}⚠️ {warning}")
        return lines

    written_by_table = result.get("written_by_table") or {}
    removed_by_table = result.get("removed_by_table") or {}
    lines.append(
        f"{indent}Записано строк по таблицам: "
        + ", ".join(f"{table}={int(written_by_table.get(table) or 0)}"
                    for table in sorted(written_by_table))
        + f"; всего {int(result.get('rows_written') or 0)} (видов "
          f"{int(result.get('files_read') or 0)}, условий перечня "
          f"{int(result.get('targets_total') or 0)}, форм "
          f"{int(result.get('forms_total') or 0)}, описаний форм "
          f"{int(result.get('form_ext_total') or 0)}, команд "
          f"{int(result.get('commands_total') or 0)})"
    )
    lines.append(
        f"{indent}Файлов регистрации вида: {int(result.get('files_found') or 0)} "
        f"(разобрано {int(result.get('files_read') or 0)}, каталог "
        f"{result.get('directory') or FILTER_CRITERIA_DIR}/, записей индекса состава вида "
        f"{int(result.get('index_kind_records') or 0)})"
    )
    if int(result.get("removed_previous") or 0):
        lines.append(
            f"{indent}Снято прежних строк этой конфигурации: "
            + ", ".join(f"{table}={int(removed_by_table.get(table) or 0)}"
                        for table in sorted(removed_by_table))
        )
    return _append_filter_criteria_detail(lines, result, indent)


def _append_filter_criteria_detail(lines: List[str], result: Dict[str, Any],
                                  indent: str) -> List[str]:
    """Второй блок текста стадии S4g: состояния строк, блок `<Type>`, перечень `<Content>`,
    дети, ноги круга, дескрипторы модулей.

    Разделение формата на две функции — только длина текста: форматёр обязан называть все
    замкнутые словари состояний контракта (M5), иначе `empty_content` (MinCfg, KomMag) и
    `empty_value` (BGU2, BP3 — пустые `DefaultForm`/`AuxiliaryForm`) остались бы
    неразличимы, а нули счётчиков читались бы как «свойств нет».
    """
    prop_counts = result.get("counts_by_properties_state") or {}
    content_counts = result.get("counts_by_content_state") or {}
    child_counts = result.get("counts_by_children_state") or {}
    lines.append(
        f"{indent}Состояния строк вида: свойства — "
        + ", ".join(f"{state}={int(prop_counts.get(state) or 0)}"
                    for state in FILTER_CRITERIA_PROPERTIES_STATES)
        + "; перечень <Content> — "
        + ", ".join(f"{state}={int(content_counts.get(state) or 0)}"
                    for state in FILTER_CRITERIA_CONTENT_STATES)
        + "; дети — "
        + ", ".join(f"{state}={int(child_counts.get(state) or 0)}"
                    for state in FILTER_CRITERIA_CHILD_STATES)
    )
    form_ref = result.get("counts_by_form_ref_state") or {}
    for column in ("default_form_state", "auxiliary_form_state"):
        column_counts = form_ref.get(column) or {}
        lines.append(
            f"{indent}Ссылки на формы `{column}` — "
            + ", ".join(f"{state}={int(column_counts.get(state) or 0)}"
                        for state in FILTER_CRITERIA_FORM_REF_STATES)
            + " — пустое значение слота и отсутствие слота различаются состояниями "
              "`empty_value` и `absent`, а не нулём (замер 2.5: BGU2 и BP3 дают пустые "
              "значения)"
        )

    type_counts = result.get("counts_by_type_state") or {}
    multiplicity = result.get("types_multiplicity") or {}
    by_class = result.get("types_by_class") or {}
    by_container = result.get("types_by_container") or {}
    lines.append(
        f"{indent}Блок <Type>: состояний — "
        + ", ".join(f"{state}={int(type_counts.get(state) or 0)}"
                    for state in FILTER_CRITERIA_TYPE_STATES)
        + "; кратность — "
        + ", ".join(f"{mult}={int(multiplicity.get(mult) or 0)}"
                    for mult in FILTER_CRITERIA_MULTIPLICITY_VALUES)
        + "; классы — "
        + ", ".join(f"{kind}={int(by_class.get(kind) or 0)}"
                    for kind in FILTER_CRITERIA_TYPE_CLASS_VALUES)
        + f"; записей всего {int(result.get('types_total') or 0)}, ссылок, разрешённых по "
          f"индексу {int(result.get('types_object_ref_resolved') or 0)}, неразрешённых "
          f"{int(result.get('types_unresolved_total') or 0)}"
    )
    lines.append(
        f"{indent}Форма контейнера типа — "
        + ", ".join(f"{name}={int(by_container.get(name) or 0)}"
                    for name in FILTER_CRITERIA_TYPE_CONTAINERS)
        + " — `<v8:TypeSet>` (KomMag) читается отдельным состоянием контейнера (Q6): без "
          "него многотипный критерий выглядел бы разобранным как одиночный"
    )

    resolve_counts = result.get("counts_by_target_resolve_state") or {}
    lines.append(
        f"{indent}Перечень <Content>: разрешение цели — "
        + ", ".join(f"{state}={int(resolve_counts.get(state) or 0)}"
                    for state in FILTER_CRITERIA_TARGET_STATES)
        + f"; целей {int(result.get('targets_total') or 0)}, уникальных "
          f"{int(result.get('targets_distinct') or 0)}, не разрешено "
          f"{int(result.get('content_unresolved_total') or 0)}, максимум целей в одном файле "
          f"{int(result.get('max_targets_per_file') or 0)}, дублей "
          f"{len(result.get('duplicate_targets') or [])}"
    )
    by_object_type = result.get("targets_by_object_type") or {}
    if by_object_type:
        lines.append(
            f"{indent}Цели перечня по видам метаданных: "
            + ", ".join(f"{name}={int(count)}"
                        for name, count in sorted(by_object_type.items()))
            + " — вид цели берётся из записи индекса состава, а не из текста ссылки (Q4)"
        )
    item_attributes = result.get("content_item_attributes") or {}
    if item_attributes:
        lines.append(
            f"{indent}Атрибуты элемента `<Item>`: "
            + ", ".join(f"{name}={int(count)}"
                        for name, count in sorted(item_attributes.items()))
            + " — колонок под атрибуты схема не заводит (замер П2: `xsi:type` на всех "
              "записях круга), факт держит ответ стадии и проверка П6"
        )

    form_formats = result.get("form_ext_formats") or {}
    lines.append(
        f"{indent}Дети вида: описаний содержимого форм "
        f"{int(result.get('form_ext_total') or 0)}, форматов содержимого — "
        + (", ".join(f"{name}={int(count)}"
                     for name, count in sorted(form_formats.items())) or "нет")
        + " — таблицы детей (`forms`, `form_ext`, `commands`) общи с внешним контуром и с "
          "видом V51, поэтому и пишутся, и снимаются предикатом по uuid родителей круга, а "
          "не по ноге конфигурации (наблюдение П4 узла V52)"
    )
    lines.append(
        f"{indent}Файлы модулей вида (дескрипторы, тела пишет V47): "
        f"{int(result.get('module_files_total') or 0)}"
        + (", по родам — " + ", ".join(
            f"{name}={int(count)}"
            for name, count in sorted((result.get("module_files_by_kind") or {}).items()))
           if result.get("module_files_by_kind") else "")
        + " (Q8)"
    )

    if not result.get("index_available"):
        lines.append(
            f"{indent}Индекс состава не читается — сверка файлов регистрации с перечнем и "
            "разрешение целей перечня невозможны, и «объекта нет в перечне» от «перечень "
            "этой конфигурации не загружен» этим не отличить"
        )
    mismatch_counts = result.get("counts_by_child_mismatch_state") or {}
    lines.append(
        f"{indent}Расхождения файлов и индекса состава: "
        + ", ".join(f"{state}={int(mismatch_counts.get(state) or 0)}"
                    for state in FILTER_CRITERIA_CIRCLE_DISCREPANCIES)
        + f" (перечислено `index_only` {len(result.get('index_only') or [])}, `file_only` "
          f"{len(result.get('file_only') or [])}, `uuid_mismatch` "
          f"{len(result.get('uuid_mismatch') or [])}); расхождения детей с индексом "
          f"{int(result.get('child_mismatch_total') or 0)} (псевдозаписей слотов индекса "
          f"{int(result.get('index_pseudo_entries_total') or 0)}), сверка объявления вида с "
          f"его каталогом — {int(result.get('declaration_mismatch_total') or 0)} — нули "
          "являются ответом, а не подразумеванием"
    )

    unknown = result.get("unknown_properties") or {}
    unknown_values = result.get("unknown_value_properties") or {}
    unexpected_tags = [("Properties", "unexpected_child_tags"),
                       ("<Type>", "unexpected_type_tags"),
                       ("<Content>", "unexpected_content_tags")]
    named_tags = [(where, result.get(key) or {}) for where, key in unexpected_tags
                  if result.get(key)]
    if unknown or unknown_values or named_tags:
        lines.append(
            f"{indent}Неизвестное в тегах вида: имена — "
            + (", ".join(f"{name}={int(count)}"
                         for name, count in sorted(unknown.items())) or "нет")
            + "; значения — "
            + (", ".join(f"{name}={int(count)}"
                         for name, count in sorted(unknown_values.items())) or "нет")
            + "; дочерние теги — "
            + (", ".join(f"{where}: " + ", ".join(
                f"{name}={int(count)}" for name, count in sorted(values.items()))
                for where, values in named_tags) or "нет")
            + " — незнакомое имя или значение остаётся значением с состоянием "
              "`unknown_value`/`unknown_tag`, а не отказом записи (Q7, вариант A)"
        )
    ext_counts = result.get("counts_by_ext_observation") or {}
    if ext_counts or result.get("observations"):
        lines.append(
            f"{indent}Наблюдения круга и о прочем в Ext/: "
            + ", ".join(f"{kind}={count}" for kind, count in sorted(ext_counts.items()))
            + "; наблюдений круга "
            + ", ".join(str(kind) for kind, _ in (result.get("observations") or []))
            + " — справочные ресурсы формы называются наблюдением, потому что колонок под "
              "них в схеме нет, а «ресурсов нет» и «ресурсы не трогали» — разные ответы (Q7)"
        )
    prefixes = result.get("namespace_prefixes") or []
    if prefixes:
        lines.append(f"{indent}Префиксы пространств имён файлов круга: "
                     + ", ".join(str(name) for name in prefixes))
    for failure in (result.get("files_failed") or [])[:10]:
        lines.append(f"{indent}  ⚠️ файл не разобран: {failure.get('source_path')} — "
                     f"{failure.get('reason')}")

    refreshed = int(result.get("statistics_refreshed") or 0)
    if refreshed:
        lines.append(
            f"{indent}Статистика таблиц {', '.join(FILTER_CRITERIA_TABLES)} пересобрана "
            f"(ANALYZE): {refreshed} — без неё читатели витрин текущего состояния платят "
            "минутами (мера V46)"
        )
    for warning in result.get("warnings") or []:
        lines.append(f"{indent}⚠️ {warning}")
    lines.append(f"{indent}Граница: {FILTER_CRITERIA_CIRCLE_BOUNDARY}")
    return lines


def filter_criteria_defaults() -> Dict[str, Any]:
    """Закрытый контракт стадии S4g с нулями (C1, C2, C3; узел V52, шаг П4).

    Словарь плоский — тот же, что возвращает слой `load_filter_criteria`; конвейер
    вкладывает его в свой ключ `filter_criteria` без переименования (C3). Групп `kinds` в
    контракте нет — это решение Q5 (вариант A), а не пропуск: строка условия существует
    только через id строки вида (Q1, вариант A), поэтому состояния «записать вид без
    условия» в модели нет, а порога цены, при котором круг стоило бы резать, замер 1.4 не
    дал (1 219 целей на весь круг, максимум 727 в одном файле).

    Отдельно обязаны быть названы (план, разделы 2 и 5):

    * числа по таблицам (`removed_by_table`/`written_by_table`) — по кругу снятия, а не одним
      числом: «записано 7» и «записано 7 критериев + 727 условий» для читателя — разные факты.
      Ключ `tables` при этом остаётся кругом версионности (`FILTER_CRITERIA_TABLES` — две
      таблицы вида), а словари пар засеиваются кругом снятия (`FILTER_CRITERIA_REMOVE_ORDER` —
      пять): строки детей (`forms`, `form_ext`, `commands`) снимает и пишет эта же стадия
      предикатом по uuid родителей, поэтому нулевой ответ обязан называть те же пять ключей,
      что и ответ прогона, — иначе потребитель перечня в пропущенной стадии видел бы две
      таблицы, а в успешной пять (позиция, названная прогоном П8, закрыта этим же разведением);
    * замкнутые словари состояний по всем колонкам `STATE_VOCABULARIES` разбора, включая
      нули: `empty_content` (MinCfg, KomMag) и `empty_value` (BGU2, BP3 — пустые
      `DefaultForm`/`AuxiliaryForm`) различимы состоянием, а не нулём (M5);
    * словари блока `<Type>` (`counts_by_type_state`, `types_multiplicity`, `types_by_class`,
      `types_by_container`) — форма контейнера (`Type` | `TypeSet`) является ответом разбора
      (Q6): без отдельного счётчика `TypeSet` KomMag читался бы разобранным как все
      остальные, а потерянного значения этого видно не было бы;
    * `counts_by_target_resolve_state` и `targets_by_object_type` — «цель разрешена / нет» и
      состав целей по видам метаданных являются ответом о круге, а не потерянной строкой
      (Q4): 1 219 целей из 1 219 `exact` — это замер, а не предположение, и нули обязаны
      быть названы;
    * расхождения трёх ног круга — файлов регистрации с индексом состава
      (`index_only`/`file_only`/`uuid_mismatch`), детей с индексом (`child_mismatches`,
      `index_pseudo_entries`) и объявления вида с его каталогом (`declaration_mismatches`):
      четыре выгрузки дают нули, и нули — это ответ, а не молчание;
    * дескрипторы файлов модулей (`module_files_total`, `module_files_by_kind`) — тела
      пишет узел V47 (Q8), и «файлов нет» от «файлы не читали» отличает именно этот
      перечень;
    * `content_item_attributes` — распределение атрибутов элемента `<Item>` (замер П2:
      `xsi:type="xr:MDObjectRef"` на всех 1 219 записях): колонки под атрибут схема не
      заводит, поэтому факт держит ответ стадии и проверка П6.
    """
    return {
        "status": STATUS_NOT_RUN,
        "success": False,
        "error": None,
        "reason": None,
        "stage": STAGE_FILTER_CRITERIA,
        "configuration_id": None,
        "configuration_uuid": None,
        "configuration_name": None,
        "tables": list(FILTER_CRITERIA_TABLES),
        "directory": FILTER_CRITERIA_DIR,
        "files_found": 0,
        "files_read": 0,
        "files_failed": [],
        "observations": [],
        "rows_written": 0,
        "filter_criteria_written": 0,
        "content_written": 0,
        "forms_written": 0,
        "form_ext_written": 0,
        "commands_written": 0,
        "removed_previous": 0,
        "removed_by_table": {table: 0 for table in FILTER_CRITERIA_REMOVE_ORDER},
        "written_by_table": {table: 0 for table in FILTER_CRITERIA_REMOVE_ORDER},
        "index_available": False,
        "index_kind_records": 0,
        "index_only": [],
        "file_only": [],
        "uuid_mismatch": [],
        "child_mismatch_total": 0,
        "child_mismatches": [],
        "counts_by_child_mismatch_state": {
            state: 0 for state in FILTER_CRITERIA_CIRCLE_DISCREPANCIES},
        "index_pseudo_entries_total": 0,
        "index_pseudo_entries": [],
        "declaration_mismatch_total": 0,
        "declaration_mismatches": [],
        "counts_by_properties_state": {
            state: 0 for state in FILTER_CRITERIA_PROPERTIES_STATES},
        "counts_by_content_state": {state: 0 for state in FILTER_CRITERIA_CONTENT_STATES},
        "counts_by_children_state": {state: 0 for state in FILTER_CRITERIA_CHILD_STATES},
        "counts_by_form_ref_state": {
            column: {state: 0 for state in FILTER_CRITERIA_FORM_REF_STATES}
            for column in ("default_form_state", "auxiliary_form_state")},
        "counts_by_type_state": {state: 0 for state in FILTER_CRITERIA_TYPE_STATES},
        "types_multiplicity": {mult: 0 for mult in FILTER_CRITERIA_MULTIPLICITY_VALUES},
        "types_by_class": {kind: 0 for kind in FILTER_CRITERIA_TYPE_CLASS_VALUES},
        "types_by_container": {name: 0 for name in FILTER_CRITERIA_TYPE_CONTAINERS},
        "types_total": 0,
        "types_object_ref_resolved": 0,
        "types_object_ref_view_wide": 0,
        "types_unresolved_total": 0,
        "types_unresolved": [],
        "counts_by_target_resolve_state": {
            state: 0 for state in FILTER_CRITERIA_TARGET_STATES},
        "targets_total": 0,
        "targets_distinct": 0,
        "targets_by_object_type": {},
        "max_targets_per_file": 0,
        "content_item_attributes": {},
        "duplicate_targets": [],
        "unresolved_targets": [],
        "content_unresolved_total": 0,
        "commands_total": 0,
        "forms_total": 0,
        "form_ext_total": 0,
        "form_ext_formats": {},
        "module_files_total": 0,
        "module_files_by_kind": {},
        "ext_observations_total": 0,
        "counts_by_ext_observation": {},
        "ext_observations": {},
        "unknown_properties": {},
        "unknown_value_properties": {},
        "unexpected_child_tags": {},
        "unexpected_type_tags": {},
        "unexpected_content_tags": {},
        "namespace_prefixes": [],
        "statistics_refreshed": 0,
        "warnings": [],
    }




def event_subscriptions_defaults() -> Dict[str, Any]:
    """Закрытый контракт стадии S4h с нулями (C1, C2, C3; узел V53, шаг П4).

    Словарь плоский — тот же, что возвращает слой `load_event_subscriptions`; конвейер
    вкладывает его в свой ключ `event_subscriptions` без переименования (C3). Групп `kinds` в
    контракте нет — это решение Q8 (вариант A), а не пропуск: строка источника существует
    только через id строки вида (Q4, вариант A), поэтому состояния «записать вид без круга
    целей» в модели нет, а порога цены, при котором круг стоило бы резать, замер 2.2 не дал
    (25 100 записей на весь круг, максимум 789 в одном файле).

    Отдельно обязаны быть названы (план, разделы 1–2, 5):

    * числа по таблицам (`removed_by_table`/`written_by_table`) — по кругу снятия
      (`EVENT_SUBSCRIPTIONS_REMOVE_ORDER`), который у этого узла совпадает с кругом
      версионности: детей у вида нет (замер 1.2), поэтому нулевой ответ обещает те же два
      ключа, что и ответ прогона (в отличие от V51/V52, где круг снятия шире);
    * замкнутые словари состояний по всем колонкам `STATE_VOCABULARIES` разбора, включая
      нули: `empty_sources` (граница, которой корпус не давал — M4), `type_absent` (23
      записи — голые ссылки на отсутствующий вид метаданных, M5) и `unresolved` обработчика
      (граница) различимы состоянием, а не нулём;
    * `counts_by_source_tag` и `counts_by_target_form` — форма перечня (`Type`/`TypeSet`) и
      форма цели (`named`/`bare`) являются ответом разбора (M3, M5): без отдельных счётчиков
      TypeSet (371) и голые ссылки (265) читались бы обычными, а потерянного значения этого
      видно не было бы;
    * `sources_by_class` — распределение целей по измеренным классам (30 записей словаря
      разбора): вопрос «какие подписки настроены на этот вид метаданных» отвечает данными
      таблицы источников, и их состав обязан быть назван;
    * `events_by_name` — распределение подписок по именам событий: словарь 18 имён замкнут
      корпусом (замер 2.3), и `unknown_name` обязан отличаться от «имя известно, но редкое»;
    * `handlers_total`/`handlers_distinct` — связь обработчика не один-к-одному (248
      уникальных обработчиков при 311 подписках в BGU2, замер 2.3): это основание отсутствия
      внешнего ключа (Q2), и числа держат ответ стадии, а не комментарий;
    * расхождения двух ног круга (`index_only`/`file_only`/`uuid_mismatch`) и дубли имён
      внутри выгрузки (`duplicate_names`): четыре выгрузки дают нули, и нули — это ответ, а
      не молчание (замер 1.3 даёт уникальность имён внутри выгрузки).
    """
    return {
        "status": STATUS_NOT_RUN,
        "success": False,
        "error": None,
        "reason": None,
        "stage": STAGE_EVENT_SUBSCRIPTIONS,
        "configuration_id": None,
        "configuration_uuid": None,
        "configuration_name": None,
        "tables": list(EVENT_SUBSCRIPTIONS_TABLES),
        "directory": EVENT_SUBSCRIPTIONS_DIR,
        "files_found": 0,
        "files_read": 0,
        "files_failed": [],
        "observations": [],
        "counts_by_observation": {},
        "rows_written": 0,
        "event_subscriptions_written": 0,
        "sources_written": 0,
        "removed_previous": 0,
        "removed_by_table": {table: 0 for table in EVENT_SUBSCRIPTIONS_REMOVE_ORDER},
        "written_by_table": {table: 0 for table in EVENT_SUBSCRIPTIONS_REMOVE_ORDER},
        "index_available": False,
        "index_kind_records": 0,
        "index_only": [],
        "file_only": [],
        "uuid_mismatch": [],
        "counts_by_circle_discrepancy": {
            state: 0 for state in EVENT_SUBSCRIPTION_CIRCLE_DISCREPANCIES},
        "duplicate_names": [],
        "counts_by_properties_state": {
            state: 0 for state in EVENT_SUBSCRIPTION_PROPERTIES_STATES},
        "counts_by_event_state": {state: 0 for state in EVENT_SUBSCRIPTION_EVENT_STATES},
        "counts_by_handler_state": {state: 0 for state in EVENT_SUBSCRIPTION_HANDLER_STATES},
        "counts_by_source_state": {state: 0 for state in EVENT_SUBSCRIPTION_SOURCE_STATES},
        "counts_by_source_tag": {tag: 0 for tag in EVENT_SUBSCRIPTION_SOURCE_TAGS},
        "counts_by_target_form": {form: 0 for form in EVENT_SUBSCRIPTION_TARGET_FORMS},
        "counts_by_target_resolve_state": {
            state: 0 for state in EVENT_SUBSCRIPTION_TARGET_STATES},
        "sources_total": 0,
        "sources_distinct": 0,
        "sources_by_class": {},
        "max_sources_per_subscription": 0,
        "events_by_name": {},
        "unknown_event_names": {},
        "unknown_properties": {},
        "handlers_total": 0,
        "handlers_distinct": 0,
        "handlers_unresolved_total": 0,
        "handlers_unresolved": [],
        "targets_unresolved_total": 0,
        "targets_unresolved": [],
        "common_modules_available": False,
        "namespace_prefixes": [],
        "statistics_refreshed": 0,
        "warnings": [],
    }


def format_event_subscriptions_lines(result: Dict[str, Any], indent: str = "") -> List[str]:
    """Текст стадии S4h по закрытому контракту `event_subscriptions_defaults()` (C1, C3).

    Формат один для двух контуров: раздела карточки `load_1c_catalog_tool` и ответа
    отдельного входа `load_event_subscriptions_tool` (шаг П5) — прецеденты
    V45/V46/V48/V49/V50/V51/V52. Отказ форматёр называет сам, вызывающий причину не
    повторяет. Групп `kinds` у вида нет (решение Q8, вариант A), поэтому блока «группы круга
    не запрашивались» здесь нет: он обещал бы раздельный вход дозагрузки, которого у стадии
    нет (в отличие от V51). Блок детей тоже отсутствует осознанно — у подписки на события
    детей нет (замер 1.2, M2), и печатать нули по формам и командам значило бы утверждать то,
    чего вид не имеет. Граница круга печатается и при успехе: «строки записаны» не равно «о
    подписках на события сохранено всё». Неперечисленные ключи читаются нулями (C1). Имя —
    `format_event_subscriptions_lines`: форматёры стадий слоя называются по одному образцу.
    """
    lines: List[str] = []
    if not result:
        return lines

    if not result.get("success"):
        reason = result.get("error") or result.get("reason") or "загрузчик не назвал причину"
        prefix = ("Стадия не выполнена" if result.get("status") in (None, STATUS_NOT_RUN)
                  else "Стадия не удалась")
        lines.append(f"{indent}{prefix}: {reason}")
        lines.append(f"{indent}{EVENT_SUBSCRIPTIONS_REPEAT_HINT}")
        for warning in result.get("warnings") or []:
            lines.append(f"{indent}⚠️ {warning}")
        return lines

    written_by_table = result.get("written_by_table") or {}
    removed_by_table = result.get("removed_by_table") or {}
    lines.append(
        f"{indent}Записано строк по таблицам: "
        + ", ".join(f"{table}={int(written_by_table.get(table) or 0)}"
                    for table in sorted(written_by_table))
        + f"; всего {int(result.get('rows_written') or 0)} (подписок "
          f"{int(result.get('event_subscriptions_written') or 0)}, записей блока <Source> "
          f"{int(result.get('sources_written') or 0)})"
    )
    lines.append(
        f"{indent}Файлов регистрации вида: {int(result.get('files_found') or 0)} "
        f"(разобрано {int(result.get('files_read') or 0)}, каталог "
        f"{result.get('directory') or EVENT_SUBSCRIPTIONS_DIR}/, записей индекса состава вида "
        f"{int(result.get('index_kind_records') or 0)})"
    )
    if int(result.get("removed_previous") or 0):
        lines.append(
            f"{indent}Снято прежних строк этой конфигурации: "
            + ", ".join(f"{table}={int(removed_by_table.get(table) or 0)}"
                        for table in sorted(removed_by_table))
        )
    return _append_event_subscriptions_detail(lines, result, indent)


def _append_event_subscriptions_detail(lines: List[str], result: Dict[str, Any],
                                      indent: str) -> List[str]:
    """Второй блок текста стадии S4h: состояния строк вида, блок `<Source>`, круг целей,
    обработчики, ноги круга.

    Разделение формата на две функции — только длина текста: форматёр обязан называть все
    замкнутые словари состояний контракта (M4, M5), иначе `empty_sources` (граница, которой
    корпус не давал) и `type_absent` (23 записи — голые ссылки на отсутствующий вид
    метаданных) остались бы неразличимы, а нули счётчиков читались бы как «подписок нет».
    """
    prop_counts = result.get("counts_by_properties_state") or {}
    event_counts = result.get("counts_by_event_state") or {}
    handler_counts = result.get("counts_by_handler_state") or {}
    source_counts = result.get("counts_by_source_state") or {}
    lines.append(
        f"{indent}Свойства подписок: состояний — "
        + ", ".join(f"{state}={int(prop_counts.get(state) or 0)}"
                    for state in EVENT_SUBSCRIPTION_PROPERTIES_STATES)
        + "; состояний имени события — "
        + ", ".join(f"{state}={int(event_counts.get(state) or 0)}"
                    for state in EVENT_SUBSCRIPTION_EVENT_STATES)
        + "; состояний блока <Source> — "
        + ", ".join(f"{state}={int(source_counts.get(state) or 0)}"
                    for state in EVENT_SUBSCRIPTION_SOURCE_STATES)
        + " — пустой блок называется состоянием `empty_sources` со счётчиком 0, а не "
          "отсутствием строк (M4); корпус пустых блоков не давал, поэтому это граница, а не "
          "ожидаемое значение"
    )

    lines.append(
        f"{indent}Обработчики: состояний — "
        + ", ".join(f"{state}={int(handler_counts.get(state) or 0)}"
                    for state in EVENT_SUBSCRIPTION_HANDLER_STATES)
        + f"; всего {int(result.get('handlers_total') or 0)}, уникальных "
          f"{int(result.get('handlers_distinct') or 0)}, неразрешённых "
          f"{int(result.get('handlers_unresolved_total') or 0)} (перечислено "
          f"{len(result.get('handlers_unresolved') or [])}) — связь не один-к-одному "
          "(248 уникальных обработчиков при 311 подписках в BGU2, замер 2.3), поэтому "
          "внешнего ключа на общие модули нет (Q2, решение оператора); разрешение идёт по "
          "витрине общих модулей текущей ревизии"
    )
    if not result.get("common_modules_available"):
        lines.append(
            f"{indent}Перечень общих модулей текущей ревизии не прочитан — состояние "
            "`unresolved` обработчика при этом означает «нечем разрешить», а не «модуля нет в "
            "конфигурации» (правило C2)"
        )

    tag_counts = result.get("counts_by_source_tag") or {}
    form_counts = result.get("counts_by_target_form") or {}
    resolve_counts = result.get("counts_by_target_resolve_state") or {}
    lines.append(
        f"{indent}Блок <Source>: тегов — "
        + ", ".join(f"{tag}={int(tag_counts.get(tag) or 0)}"
                    for tag in EVENT_SUBSCRIPTION_SOURCE_TAGS)
        + "; форм цели — "
        + ", ".join(f"{form}={int(form_counts.get(form) or 0)}"
                    for form in EVENT_SUBSCRIPTION_TARGET_FORMS)
        + "; разрешение цели — "
        + ", ".join(f"{state}={int(resolve_counts.get(state) or 0)}"
                    for state in EVENT_SUBSCRIPTION_TARGET_STATES)
        + f"; записей {int(result.get('sources_total') or 0)}, уникальных целей "
          f"{int(result.get('sources_distinct') or 0)}, максимум в одной подписке "
          f"{int(result.get('max_sources_per_subscription') or 0)}, неразрешённых "
          f"{int(result.get('targets_unresolved_total') or 0)} (перечислено "
          f"{len(result.get('targets_unresolved') or [])}) — голая ссылка `cfg:<Класс>` "
          "разрешается присутствием вида метаданных и называется состояниями "
          "`type_present`/`type_absent` прямо (M5, Q3 вариант A), а не потерянным именем"
    )

    by_class = result.get("sources_by_class") or {}
    if by_class:
        lines.append(
            f"{indent}Цели блока <Source> по классам ссылки: "
            + ", ".join(f"{name}={int(count)}" for name, count in sorted(by_class.items()))
            + " — вид цели выводится из класса ссылки разбором (Q3, вариант A); словарь "
              "классов (30 записей замера 2.2) замкнут измерением и держит константа "
              "разбора, а не CHECK (Q6, вариант A)"
        )

    events_by_name = result.get("events_by_name") or {}
    if events_by_name:
        lines.append(
            f"{indent}Подписки по именам событий: "
            + ", ".join(f"{name}={int(count)}"
                        for name, count in sorted(events_by_name.items(),
                                                 key=lambda pair: (-int(pair[1]), pair[0])))
            + " — словарь имён замкнут корпусом (замер 2.3 даёт 18 имён), значение вне него "
              "остаётся записанным с состоянием `unknown_name` (Q6, вариант A)"
        )

    if not result.get("index_available"):
        lines.append(
            f"{indent}Индекс состава не читается — сверка файлов регистрации с перечнем и "
            "разрешение целей блока <Source> невозможны, и «объекта нет в перечне» от "
            "«перечень этой конфигурации не загружен» этим не отличить"
        )
    mismatch_counts = result.get("counts_by_circle_discrepancy") or {}
    lines.append(
        f"{indent}Расхождения файлов и индекса состава: "
        + ", ".join(f"{state}={int(mismatch_counts.get(state) or 0)}"
                    for state in EVENT_SUBSCRIPTION_CIRCLE_DISCREPANCIES)
        + f" (перечислено `index_only` {len(result.get('index_only') or [])}, `file_only` "
          f"{len(result.get('file_only') or [])}, `uuid_mismatch` "
          f"{len(result.get('uuid_mismatch') or [])}); дублей имён внутри выгрузки "
          f"{len(result.get('duplicate_names') or [])} — нули являются ответом, а не "
          "подразумеванием (замер 1.3 даёт уникальность имён внутри каждой выгрузки)"
    )

    unknown = result.get("unknown_properties") or {}
    unknown_events = result.get("unknown_event_names") or {}
    if unknown or unknown_events:
        lines.append(
            f"{indent}Неизвестное в тегах вида: имена свойств — "
            + (", ".join(f"{name}={int(count)}"
                         for name, count in sorted(unknown.items())) or "нет")
            + "; имена событий — "
            + (", ".join(f"{name}={int(count)}"
                         for name, count in sorted(unknown_events.items())) or "нет")
            + " — незнакомое имя или значение остаётся значением с состоянием "
              "`unknown_value`/`unknown_tag`/`unknown_name`, а не отказом записи "
              "(Q6, вариант A по прецеденту Q7 узла V50)"
        )
    obs_counts = result.get("counts_by_observation") or {}
    if obs_counts or result.get("observations"):
        lines.append(
            f"{indent}Наблюдения круга: "
            + ", ".join(f"{kind}={count}" for kind, count in sorted(obs_counts.items()))
            + "; всего "
            + ", ".join(str(kind) for kind, _ in (result.get("observations") or [])[:20])
            + " — примитивность вида (отсутствие подкаталогов содержимого) является фактом "
              "замера 1.2: каталог или файл вне перечня называется наблюдением, потому что "
              "колонок под них в схеме нет, а «детей нет» и «круг шире разбора» — разные "
              "ответы (M2)"
        )
    prefixes = result.get("namespace_prefixes") or []
    if prefixes:
        lines.append(f"{indent}Префиксы пространств имён файлов круга: "
                     + ", ".join(str(name) for name in prefixes))
    for failure in (result.get("files_failed") or [])[:10]:
        lines.append(f"{indent}  ⚠️ файл не разобран: {failure.get('source_path')} — "
                     f"{failure.get('reason')}")

    refreshed = int(result.get("statistics_refreshed") or 0)
    if refreshed:
        lines.append(
            f"{indent}Статистика таблиц {', '.join(EVENT_SUBSCRIPTIONS_TABLES)} пересобрана "
            f"(ANALYZE): {refreshed} — без неё читатели витрин текущего состояния платят "
            "минутами (мера V46)"
        )
    for warning in result.get("warnings") or []:
        lines.append(f"{indent}⚠️ {warning}")
    lines.append(f"{indent}Граница: {EVENT_SUBSCRIPTIONS_CIRCLE_BOUNDARY}")
    return lines


# ── контракт стадии S4i (узел V54, шаг П4) ────────────────────────────────────────────


def scheduled_jobs_defaults() -> Dict[str, Any]:
    """Закрытый контракт стадии S4i с нулями (C1, C2, C3; узел V54, шаг П4).

    Словарь плоский — тот же, что возвращает слой `load_scheduled_jobs`; конвейер
    вкладывает его в свой ключ `scheduled_jobs` без переименования (C3). Групп `kinds` в
    контракте нет — это решение Q5 (вариант A), а не пропуск: запись расписания существует
    только через id строки вида (Q2, вариант A), поэтому состояния «записать задание без
    расписания» в модели нет, а порога цены, при котором круг стоило бы резать, замер 1.1/2.2
    не дал (346 файлов регистрации и 313 записей расписания на весь круг).

    Отдельно обязаны быть названы (план, разделы 1–2, 5):

    * числа по таблицам (`removed_by_table`/`written_by_table`) — по кругу снятия
      (`SCHEDULED_JOBS_REMOVE_ORDER`), который у этого узла совпадает с кругом версионности:
      детей у вида нет (замер 1.2), поэтому нулевой ответ обещает те же два ключа, что и
      ответ прогона (в отличие от V51/V52, где круг снятия шире);
    * замкнутые словари состояний по всем колонкам `STATE_VOCABULARIES` разбора, включая
      нули: `absent` содержимого (43 задания без расписания — M4), `sentinel` атрибутов
      (1441 стража — Q4), `empty_element_all` наборов (по 23 элемента на каждый — M5) и
      `text_unavailable` объявления метода (граница базы, Q8) различимы состоянием, а не
      нулём;
    * `counts_by_property_presence` и `counts_by_value_form` — наличие тега и ФОРМА его
      значения являются ответом разбора (замер 2: `Key` пустой 228 / числовая строка 25 /
      текст 93, `Description` пустой 252 / текст 92 / числовая строка 2): без отдельных
      счётчиков «свойства нет» читалось бы как «свойство пустое», а числовая строка — как
      текст;
    * `methods_total`/`methods_distinct`/`method_modules_distinct` — связь обработчика не
      один-к-одному (344 различные пары модуль+метод при 346 строках — замер 2.1): это
      основание отсутствия внешнего ключа (Q3), и числа держат ответ стадии, а не комментарий;
    * расхождения обеих ног круга (`index_only`/`file_only`/`uuid_mismatch` ноги вида —
      файл регистрации, индекс состава и перечень заголовка; `schedule_index_only`/
      `schedule_file_only`/`schedule_uuid_mismatch` ноги содержимого) и
      дубли имён внутри выгрузки (`duplicate_names`): четыре выгрузки дают нули, и нули — это
      ответ, а не молчание (замер 1.3 даёт уникальность имён внутри выгрузки);
    * `files_with_schedule`/`files_without_schedule` — деление 303/43 по состоянию содержимого
      (M4): одно число без другого читалось бы как «расписаний не хватает».
    """
    return {
        "status": STATUS_NOT_RUN,
        "success": False,
        "error": None,
        "reason": None,
        "stage": STAGE_SCHEDULED_JOBS,
        "configuration_id": None,
        "configuration_uuid": None,
        "configuration_name": None,
        "tables": list(SCHEDULED_JOBS_TABLES),
        "directory": SCHEDULED_JOBS_DIR,
        "files_found": 0,
        "files_read": 0,
        "files_failed": [],
        "observations": [],
        "counts_by_observation": {},
        "rows_written": 0,
        "scheduled_jobs_written": 0,
        "schedule_records_written": 0,
        "removed_previous": 0,
        "removed_by_table": {table: 0 for table in SCHEDULED_JOBS_REMOVE_ORDER},
        "written_by_table": {table: 0 for table in SCHEDULED_JOBS_REMOVE_ORDER},
        "index_available": False,
        "index_kind_records": 0,
        "index_child_records": 0,
        "index_only": [],
        "file_only": [],
        "uuid_mismatch": [],
        "schedule_index_only": [],
        "schedule_file_only": [],
        "schedule_uuid_mismatch": [],
        "index_child_unexpected": [],
        "duplicate_names": [],
        "counts_by_circle_discrepancy": {
            state: 0 for state in SCHEDULED_JOB_CIRCLE_DISCREPANCIES},
        "counts_by_content_discrepancy": {
            state: 0 for state in SCHEDULED_JOB_CONTENT_DISCREPANCIES},
        "counts_by_properties_state": {
            state: 0 for state in SCHEDULED_JOB_PROPERTIES_STATES},
        "counts_by_method_state": {state: 0 for state in SCHEDULED_JOB_METHOD_STATES},
        "counts_by_method_declared_state": {
            state: 0 for state in SCHEDULED_JOB_METHOD_DECLARED_STATES},
        "counts_by_schedule_state": {state: 0 for state in SCHEDULED_JOB_STATES},
        "counts_by_schedule_file_state": {
            state: 0 for state in SCHEDULED_JOB_FILE_STATES},
        "counts_by_property_presence": {name: 0 for name in XML_PROPERTY_NAMES_OF_JOB},
        "counts_by_value_form": {name: {} for name in XML_PROPERTY_NAMES_OF_JOB},
        "unknown_properties": {},
        "methods_total": 0,
        "methods_distinct": 0,
        "method_modules_distinct": 0,
        "methods_unresolved_total": 0,
        "methods_unresolved": [],
        "methods_not_declared_total": 0,
        "methods_not_declared": [],
        "common_modules_available": False,
        "module_texts_available": False,
        "schedules_total": 0,
        "schedule_jobs_distinct": 0,
        "root_records_total": 0,
        "detailed_records_total": 0,
        "files_with_schedule": 0,
        "files_without_schedule": 0,
        "files_with_detailed": 0,
        "max_detailed_per_record": 0,
        "max_depth_seen": 0,
        "day_times_total": 0,
        "counts_by_record_kind": {kind: 0 for kind in SCHEDULE_RECORD_KINDS},
        "counts_by_attribute_state": {
            state: 0 for state in SCHEDULE_ATTRIBUTE_VALUE_STATES},
        "attribute_states_by_name": {},
        "counts_by_week_days_state": {state: 0 for state in SCHEDULE_SET_STATES},
        "counts_by_months_state": {state: 0 for state in SCHEDULE_SET_STATES},
        "statistics_refreshed": 0,
        "warnings": [],
    }
def format_scheduled_jobs_lines(result: Dict[str, Any], indent: str = "") -> List[str]:
    """Текст стадии S4i по закрытому контракту `scheduled_jobs_defaults()` (C1, C3).

    Формат один для двух контуров: раздела карточки `load_1c_catalog_tool` и ответа
    отдельного входа `load_scheduled_jobs_tool` (шаг П5) — прецеденты
    V45/V46/V48/V49/V50/V51/V52/V53. Отказ форматёр называет сам, вызывающий причину не
    повторяет. Групп `kinds` у вида нет (решение Q5, вариант A), поэтому блока «группы круга
    не запрашивались» здесь нет: он обещал бы раздельный вход дозагрузки, которого у стадии
    нет (в отличие от V51). Блок детей тоже отсутствует осознанно — у регламентного задания
    нет ни форм, ни макетов, ни команд, ни модулей (замер 1.2), и печатать по ним нули
    значило бы утверждать то, чего вид не имеет. Граница круга печатается и при успехе:
    «строки записаны» не равно «о регламентных заданиях сохранено всё». Неперечисленные ключи
    читаются нулями (C1). Имя — `format_scheduled_jobs_lines`: форматёры стадий слоя
    называются по одному образцу.
    """
    lines: List[str] = []
    if not result:
        return lines

    if not result.get("success"):
        reason = result.get("error") or result.get("reason") or "загрузчик не назвал причину"
        prefix = ("Стадия не выполнена" if result.get("status") in (None, STATUS_NOT_RUN)
                  else "Стадия не удалась")
        lines.append(f"{indent}{prefix}: {reason}")
        if result.get("files_failed"):
            # Отказ разбора круга — тот же статус `error`, что и отказ записи (словарь
            # статусов контракта замкнут: not_run/ok/skipped/error, C2), поэтому ветка
            # различается признаком круга, а не новым статусом: перечисленные файлы-виновники
            # есть только у остановки до записи.
            lines.append(
                f"{indent}Стадия остановлена ДО записи (приём V12/V46/V48/V49/V50/V51/V52"
                f"/V53): половина круга читалась бы как полный состав вида; прежние строки "
                f"не сняты — {SCHEDULED_JOBS_TABLE} и {SCHEDULED_JOB_SCHEDULES_TABLE} "
                "содержат прежнее состояние")
            for failure in (result.get("files_failed") or [])[:10]:
                lines.append(f"{indent}  ⚠️ файл не разобран: "
                             f"{failure.get('source_path')} — {failure.get('reason')}")
        lines.append(f"{indent}{SCHEDULED_JOBS_REPEAT_HINT}")
        for warning in result.get("warnings") or []:
            lines.append(f"{indent}⚠️ {warning}")
        return lines

    written_by_table = result.get("written_by_table") or {}
    removed_by_table = result.get("removed_by_table") or {}
    lines.append(
        f"{indent}Записано строк по таблицам: "
        + ", ".join(f"{table}={int(written_by_table.get(table) or 0)}"
                    for table in sorted(written_by_table))
        + f"; всего {int(result.get('rows_written') or 0)} (заданий "
          f"{int(result.get('scheduled_jobs_written') or 0)}, записей расписания "
          f"{int(result.get('schedule_records_written') or 0)})"
    )
    lines.append(
        f"{indent}Файлов регистрации вида: {int(result.get('files_found') or 0)} "
        f"(разобрано {int(result.get('files_read') or 0)}, каталог "
        f"{result.get('directory') or SCHEDULED_JOBS_DIR}/, записей индекса состава вида "
        f"{int(result.get('index_kind_records') or 0)}, файлов содержимого "
        f"Ext/Schedule.xml {int(result.get('index_child_records') or 0)})"
    )
    if int(result.get("removed_previous") or 0):
        lines.append(
            f"{indent}Снято прежних строк этой конфигурации: "
            + ", ".join(f"{table}={int(removed_by_table.get(table) or 0)}"
                        for table in sorted(removed_by_table))
        )
    return _append_scheduled_jobs_detail(lines, result, indent)


def _append_scheduled_jobs_detail(lines: List[str], result: Dict[str, Any],
                                 indent: str) -> List[str]:
    """Второй блок текста стадии S4i: свойства вида и их формы, обработчик, содержимое
    расписания, состояния атрибутов и наборов, ноги круга.

    Разделение формата на две функции — только длина текста: форматёр обязан называть все
    замкнутые словари состояний контракта (M4, M5), иначе `absent` содержимого (43 задания
    без расписания), `sentinel` атрибутов (1441 стража) и `empty_element_all` наборов (13
    записей) остались бы неразличимы, а нули счётчиков читались бы как «расписаний нет».
    """
    prop_counts = result.get("counts_by_properties_state") or {}
    schedule_counts = result.get("counts_by_schedule_state") or {}
    file_counts = result.get("counts_by_schedule_file_state") or {}
    lines.append(
        f"{indent}Свойства заданий: состояний — "
        + ", ".join(f"{state}={int(prop_counts.get(state) or 0)}"
                    for state in SCHEDULED_JOB_PROPERTIES_STATES)
        + "; состояний содержимого — "
        + ", ".join(f"{state}={int(schedule_counts.get(state) or 0)}"
                    for state in SCHEDULED_JOB_STATES)
        + "; состояний двух ног содержимого — "
        + ", ".join(f"{state}={int(file_counts.get(state) or 0)}"
                    for state in SCHEDULED_JOB_FILE_STATES)
        + " — задание без файла `Ext/Schedule.xml` называется состоянием `absent` строки "
          "вида, а не нулём записей расписания (M4: 43 задания из 346 — BGU2 19, BP3 24; "
          "у тех же 43 запись содержимого отсутствует в индексе состава — `file_without_"
          "index` даёт те же числа, замер 1.3)"
    )

    presence = result.get("counts_by_property_presence") or {}
    value_forms = result.get("counts_by_value_form") or {}
    lines.append(
        f"{indent}Тегов свойств из 10 (замер 2: ровно один набор тегов на всех 346 файлах): "
        + ", ".join(f"{name}={int(presence.get(name) or 0)}"
                    for name in XML_PROPERTY_NAMES_OF_JOB)
    )
    for name in XML_PROPERTY_NAMES_OF_JOB:
        forms = value_forms.get(name) or {}
        if not forms:
            continue
        lines.append(
            f"{indent}  формами значений {name}: "
            + ", ".join(f"{form}={int(count)}" for form, count in sorted(forms.items()))
        )
    lines.append(
        f"{indent}Форма значения является ответом разбора: `<Key/>` — пустой 228, "
        "числовая строка 25, текст 93; `<Description/>` — пустой 252, текст 92, числовая "
        "строка 2; `<Comment/>` — пустой 305, текст 41 (замер 2) — без счётчиков "
        "`counts_by_value_form` «свойства нет» читалось бы как «свойство пустое», а числовая "
        "строка описания — как текст"
    )

    method_counts = result.get("counts_by_method_state") or {}
    declared_counts = result.get("counts_by_method_declared_state") or {}
    lines.append(
        f"{indent}Обработчики: состояний разрешения — "
        + ", ".join(f"{state}={int(method_counts.get(state) or 0)}"
                    for state in SCHEDULED_JOB_METHOD_STATES)
        + "; состояний объявления метода — "
        + ", ".join(f"{state}={int(declared_counts.get(state) or 0)}"
                    for state in SCHEDULED_JOB_METHOD_DECLARED_STATES)
        + f"; всего {int(result.get('methods_total') or 0)}, уникальных пар модуль+метод "
          f"{int(result.get('methods_distinct') or 0)}, уникальных модулей "
          f"{int(result.get('method_modules_distinct') or 0)}, неразрешённых "
          f"{int(result.get('methods_unresolved_total') or 0)} (перечислено "
          f"{len(result.get('methods_unresolved') or [])}), необъявленных методов "
          f"{int(result.get('methods_not_declared_total') or 0)} (перечислено "
          f"{len(result.get('methods_not_declared') or [])}) — связь не один-к-одному (344 "
          "различные пары при 346 строках, замер 2.1), поэтому внешнего ключа на общие модули "
          "нет (Q3, вариант A); разрешение идёт по витрине общих модулей текущей ревизии"
    )
    if not result.get("common_modules_available"):
        lines.append(
            f"{indent}Перечень общих модулей текущей ревизии не прочитан — состояние "
            "`unresolved` обработчика при этом означает «нечем разрешить», а не «модуля нет в "
            "конфигурации» (правило C2)"
        )
    if not result.get("module_texts_available"):
        lines.append(
            f"{indent}Тексты общих модулей в базе не загружены — состояние объявления метода "
            "`text_unavailable` означает «нет чем проверить объявление», а не «метода нет» "
            "(Q8, вариант A: узел V46 тексты модулей не читает)"
        )


    kind_counts = result.get("counts_by_record_kind") or {}
    attr_counts = result.get("counts_by_attribute_state") or {}
    week_counts = result.get("counts_by_week_days_state") or {}
    month_counts = result.get("counts_by_months_state") or {}
    lines.append(
        f"{indent}Расписание: записей {int(result.get('schedules_total') or 0)} у "
          f"{int(result.get('schedule_jobs_distinct') or 0)} заданий, kinds — "
        + ", ".join(f"{kind}={int(kind_counts.get(kind) or 0)}"
                    for kind in SCHEDULE_RECORD_KINDS)
        + f"; файлов с расписанием {int(result.get('files_with_schedule') or 0)}, без него "
          f"{int(result.get('files_without_schedule') or 0)}, с вложенной записью "
          f"{int(result.get('files_with_detailed') or 0)}, максимум вложенных в одной записи "
          f"{int(result.get('max_detailed_per_record') or 0)}, наибольшая глубина "
          f"{int(result.get('max_depth_seen') or 0)} (замер 2.5 даёт ровно 2 — M6), "
          f"`DayTimes` встречалось {int(result.get('day_times_total') or 0)} раз — колонки "
          "под него нет, а его появление называется наблюдением `day_times_present` (граница "
          "раздела 8 плана)"
    )
    lines.append(
        f"{indent}Атрибуты записи расписания (12 типизированных): состояний значений — "
        + ", ".join(f"{state}={int(attr_counts.get(state) or 0)}"
                    for state in SCHEDULE_ATTRIBUTE_VALUE_STATES)
        + " — страж `0001-01-01` и страж `00:00:00` в колонки `date`/`time` не пишутся: "
          "значение называется состоянием `sentinel` (замер 2.2: sentinel 1441, zero 1449, "
          "set 866 — Q4, вариант A), а `zero` является настоящим нулевым значением атрибута "
          "и отличается от стража состоянием"
    )
    by_name = result.get("attribute_states_by_name") or {}
    for name in sorted(by_name):
        states = by_name.get(name) or {}
        lines.append(
            f"{indent}  {name}: "
            + ", ".join(f"{state}={int(count)}" for state, count in sorted(states.items()))
        )
    lines.append(
        f"{indent}Наборы целых: дней недели — "
        + ", ".join(f"{state}={int(week_counts.get(state) or 0)}"
                    for state in SCHEDULE_SET_STATES)
        + "; месяцев — "
        + ", ".join(f"{state}={int(month_counts.get(state) or 0)}"
                    for state in SCHEDULE_SET_STATES)
        + " — пустой элемент `<ent:WeekDays/>` означает «все дни недели» и является "
          "состоянием `empty_element_all` с пустым перечнем значений, а не «ни одного дня» "
          "(по 23 таких элемента на каждый набор: 13 корневых и 10 вложенных записей — M5); "
          "значение вне диапазонов 1..7 и 1..12 прерывает разбор файла с виновником, потому "
          "что колонка его не примет (CHECK диапазона), а текст, не разбираемый целыми, "
          "остаётся состоянием `non_numeric` с NULL в колонке"
    )


    if not result.get("index_available"):
        lines.append(
            f"{indent}Индекс состава не читается — сверка файлов регистрации и файлов "
            "содержимого с перечнем невозможна, и «объекта нет в перечне» от «перечень этой "
            "конфигурации не загружен» этим не отличить"
        )
    mismatch_counts = result.get("counts_by_circle_discrepancy") or {}
    content_counts = result.get("counts_by_content_discrepancy") or {}
    lines.append(
        f"{indent}Расхождения ноги вида (файл регистрации ↔ индекс состава ↔ перечень "
        "заголовка): "
        + ", ".join(f"{state}={int(mismatch_counts.get(state) or 0)}"
                    for state in SCHEDULED_JOB_CIRCLE_DISCREPANCIES)
        + f" (перечислено `index_only` {len(result.get('index_only') or [])}, `file_only` "
          f"{len(result.get('file_only') or [])}, `uuid_mismatch` "
          f"{len(result.get('uuid_mismatch') or [])}); записей индекса вне круга вида "
          f"{len(result.get('index_child_unexpected') or [])}; дублей имён внутри выгрузки "
          f"{len(result.get('duplicate_names') or [])}"
    )
    lines.append(
        f"{indent}Расхождения ноги содержимого (файл Ext/Schedule.xml ↔ запись индекса "
        "состава `ScheduledJob.<Имя>.Schedule`): "
        + ", ".join(f"{state}={int(content_counts.get(state) or 0)}"
                    for state in SCHEDULED_JOB_CONTENT_DISCREPANCIES)
        + f" (перечислено `schedule_index_only` "
          f"{len(result.get('schedule_index_only') or [])}, `schedule_file_only` "
          f"{len(result.get('schedule_file_only') or [])}, `schedule_uuid_mismatch` "
          f"{len(result.get('schedule_uuid_mismatch') or [])}) — 43 задания дают "
          "`schedule_file_only` одновременно с состоянием содержимого `absent`: файл "
          "расписания есть, записи в индексе состава нет (замер 1.3), и это называется "
          "обеими ногами, а не одной; нули остальных пар являются ответом, а не "
          "подразумеванием (замер 1.3 даёт уникальность имён внутри каждой выгрузки)"
    )

    unknown = result.get("unknown_properties") or {}
    if unknown:
        lines.append(
            f"{indent}Неизвестные теги свойств вида: "
            + ", ".join(f"{name}={int(count)}"
                        for name, count in sorted(unknown.items()))
            + " — незнакомый тег остаётся записанным с состоянием `unknown_tag`, а не "
              "отказом записи (Q7, вариант A по прецеденту Q7 узла V50); корпус таких тегов "
              "не давал ни разу (замер 2)"
        )
    obs_counts = result.get("counts_by_observation") or {}
    if obs_counts or result.get("observations"):
        lines.append(
            f"{indent}Наблюдения круга: "
            + ", ".join(f"{kind}={count}" for kind, count in sorted(obs_counts.items()))
            + "; всего "
            + ", ".join(str(kind) for kind, _ in (result.get("observations") or [])[:20])
            + " — каталог или файл вне перечня вида (например `Forms/` или файл модуля) "
              "является наблюдением, а не строкой круга: у вида таких каталогов в четырёх "
              "выгрузках нет (замер 1.2), поэтому колонок под них в схеме нет, и молчать о "
              "них нельзя (M2)"
        )

    refreshed = int(result.get("statistics_refreshed") or 0)
    if refreshed:
        lines.append(
            f"{indent}Статистика таблиц {', '.join(SCHEDULED_JOBS_TABLES)} пересобрана "
            f"(ANALYZE): {refreshed} — без неё читатели витрин текущего состояния платят "
            "минутами (мера V46)"
        )
    for warning in result.get("warnings") or []:
        lines.append(f"{indent}⚠️ {warning}")
    lines.append(f"{indent}Граница: {SCHEDULED_JOBS_CIRCLE_BOUNDARY}")
    return lines


# ── закрытый контракт стадии S4j (узел V55, шаг П4, позиция 2.10) ─────────────────────
def bots_defaults() -> Dict[str, Any]:
    """Закрытый контракт стадии S4j с нулями (C1, C2, C3; узел V55, шаг П4).

    Словарь плоский — тот же, что возвращает слой `load_bots` и что собирает сводка
    разбора `collect_bots` (один словарь на разбор и на ответ — приём `SUMMARY_KEYS`
    загрузчика V48); конвейер вкладывает его в свой ключ `bots` без переименования (C3).
    Групп `kinds` в контракте нет — это решение Q5 (вариант A), а не пропуск: строка вида
    едина, её состояние свойств, состояние ссылки и состояние модуля неотделимы от неё, а
    порога цены, при котором круг стоило бы резать, замер 1.1 не дал (весь круг четырёх
    выгрузок — 2 файла регистрации одной конфигурации).

    Отдельно обязаны быть названы (план, разделы 1–2, 5):

    * числа по таблицам (`removed_by_table`/`written_by_table`) — по кругу снятия
      (`BOTS_REMOVE_ORDER`), который у этого узла совпадает с кругом версионности: таблиц
      детей у вида нет (замер 1.2), поэтому нулевой ответ обещает ровно тот же ключ, что и
      ответ прогона (в отличие от V51/V52/V54, где круг снятия шире);
    * замкнутые словари состояний по всем колонкам `state_columns()` разбора, включая нули:
      `std_picture` (1 из 2 файлов — ссылка на стандартное средство платформы, индексом не
      разрешается никогда), `unresolved` и `empty_value` (границы, которых корпус не давал),
      `file_only`/`index_only`/`absent` модуля и `unknown_tag`/`unknown_value` свойств
      различимы состоянием, а не нулём;
    * `picture_pending`/`module_pending` — ОТДЕЛЬНЫЕ счётчики: состояние `pending` означает
      «разрешение не проверялось» (индекс состава или признак V47 не входили во вход
      разбора), в словари DDL не входит и CHECK'ами схемы отклоняется. Называть его
      `unresolved` нельзя — «не проверяли» и «не разрешилось» разные ответы (шаг П3);
    * `picture_total`/`picture_resolved` — разрешение ссылки не равно её наличию: блок
      `Picture` есть в 2/2 файлов, разрешена индексом 1 из 2 (замер 2.1), и одно число без
      другого читалось бы как «ссылок не хватает»;
    * `counts_by_observation` — замкнутый перечень `OBSERVATION_KINDS` разбора: отсутствие
      каталога вида (`directory_missing`, три из четырёх выгрузок — Q9 вариант A) является
      наблюдением, а не нулём строк;
    * `unknown_properties` — виновники состояния `unknown_tag`/`unknown_value` поимённо:
      корпус словарь пяти тегов не замыкает (Q1, решение оператора — вариант A), поэтому
      ответ обязан называть незнакомое, а не терять его;
    * расхождения ног круга (`index_only`/`file_only`/`uuid_mismatch`) и дубли имён внутри
      выгрузки (`duplicate_names`): четыре выгрузки дают нули, и нули — это ответ, а не
      молчание (замер 1.3 даёт уникальность имён внутри выгрузки).
    """
    return {
        "status": STATUS_NOT_RUN,
        "success": False,
        "error": None,
        "reason": None,
        "stage": STAGE_BOTS,
        "configuration_id": None,
        "configuration_uuid": None,
        "configuration_name": None,
        "tables": list(BOTS_TABLES),
        "directory": BOTS_DIR,
        "state_columns": list(bots_state_columns()),
        "files_found": 0,
        "files_read": 0,
        "files_failed": [],
        "observations": [],
        "duplicate_names": [],
        "rows_written": 0,
        "bots_written": 0,
        "removed_previous": 0,
        "removed_by_table": {table: 0 for table in BOTS_REMOVE_ORDER},
        "written_by_table": {table: 0 for table in BOTS_REMOVE_ORDER},
        "index_available": False,
        "index_kind_records": 0,
        "index_child_records": 0,
        "index_only": [],
        "file_only": [],
        "uuid_mismatch": [],
        "counts_by_circle_discrepancy": {
            state: 0 for state in BOTS_CIRCLE_DISCREPANCIES},
        "counts_by_index_check_state": {
            state: 0 for state in BOTS_INDEX_CHECK_STATES},
        "counts_by_observation": {kind: 0 for kind in BOTS_OBSERVATION_KINDS},
        "counts_by_properties_state": {
            state: 0 for state in BOTS_PROPERTIES_STATES},
        "counts_by_picture_state": {state: 0 for state in BOTS_PICTURE_STATES},
        "counts_by_picture_target_class": {
            value: 0 for value in BOTS_PICTURE_TARGET_CLASSES},
        "counts_by_picture_load_transparent_state": {
            state: 0 for state in BOTS_PICTURE_LT_STATES},
        "counts_by_module_state": {state: 0 for state in BOTS_MODULE_STATES},
        "picture_pending": 0,
        "module_pending": 0,
        "picture_total": 0,
        "picture_resolved": 0,
        "unknown_properties": {},
        # Ключ добавлен шагом П5, а не П4: он нужен ответу, а не записи. Разрешение
        # обработчика идёт по витрине общих модулей текущей ревизии (слой V46), и при её
        # недоступности `method_name` всё равно записывается текстом из файла — ответ обязан
        # назвать, что проверять было нечем (правило C2), а не молчать (прецедент ключа
        # `common_modules_available` стадии S4i).
        "common_modules_available": False,
        "statistics_refreshed": 0,
        "warnings": [],
    }


def format_bots_lines(result: Dict[str, Any], indent: str = "") -> List[str]:
    """Текст стадии S4j по закрытому контракту `bots_defaults()` (C1, C3).

    Формат один для двух контуров: раздела карточки `load_1c_catalog_tool` и ответа
    отдельного входа `load_bots_tool` (шаг П5) — прецеденты
    V45/V46/V48/V49/V50/V51/V52/V53/V54. Отказ форматёр называет сам, вызывающий причину не
    повторяет. Групп `kinds` у вида нет (решение Q5, вариант A), поэтому блока «группы круга
    не запрашивались» здесь нет: он обещал бы раздельный вход дозагрузки, которого у стадии
    нет. Блок детей отсутствует осознанно — форм, макетов и команд у бота нет ни в одной
    выгрузке (замер 1.2), единственный ребёнок вида в индексе состава — файл модуля
    `Ext/Module.bsl`, и он называется состоянием модуля строки вида, а не отдельной таблицей.
    Граница круга печатается и при успехе: «строки записаны» не равно «о ботах сохранено
    всё» — тексты модулей вида берёт узел V47, здесь лежат только дескрипторы. Состояния
    `pending` печатаются отдельными счётчиками: в словари DDL они не входят и CHECK'ами
    схемы отклоняются, поэтому их нельзя показывать вместе с `unresolved` (шаг П3).
    Имя — `format_bots_lines`: форматёры стадий слоя называются по одному образцу.
    """
    lines: List[str] = []
    if not result:
        return lines

    if not result.get("success"):
        reason = result.get("error") or result.get("reason") or "загрузчик не назвал причину"
        prefix = ("Стадия не выполнена" if result.get("status") in (None, STATUS_NOT_RUN)
                  else "Стадия не удалась")
        lines.append(f"{indent}{prefix}: {reason}")
        if result.get("files_failed"):
            # Отказ разбора круга — тот же статус `error`, что и отказ записи (словарь
            # статусов контракта замкнут: not_run/ok/skipped/error, C2), поэтому ветка
            # различается признаком круга, а не новым статусом: перечисленные файлы-виновники
            # есть только у остановки до записи.
            lines.append(
                f"{indent}Стадия остановлена ДО записи (приём V12/V46/V48/V49/V50/V51/V52"
                f"/V53/V54): половина круга читалась бы как полный состав вида; прежние "
                f"строки не сняты — {BOTS_TABLE} содержит прежнее состояние")
            for failure in (result.get("files_failed") or [])[:10]:
                lines.append(f"{indent}  ⚠️ файл не разобран: "
                             f"{failure.get('source_path')} — {failure.get('reason')}")
        lines.append(f"{indent}{BOTS_REPEAT_HINT}")
        for warning in result.get("warnings") or []:
            lines.append(f"{indent}⚠️ {warning}")
        return lines

    written_by_table = result.get("written_by_table") or {}
    removed_by_table = result.get("removed_by_table") or {}
    lines.append(
        f"{indent}Записано строк по таблицам: "
        + ", ".join(f"{table}={int(written_by_table.get(table) or 0)}"
                    for table in sorted(written_by_table))
        + f"; всего {int(result.get('rows_written') or 0)} (ботов "
          f"{int(result.get('bots_written') or 0)}) — таблиц круга одна, детей у вида нет "
          "(замер 1.2)"
    )
    lines.append(
        f"{indent}Файлов регистрации вида: {int(result.get('files_found') or 0)} "
        f"(разобрано {int(result.get('files_read') or 0)}, каталог "
        f"{result.get('directory') or BOTS_DIR}/, записей индекса состава вида "
        f"{int(result.get('index_kind_records') or 0)}, файлов модулей Ext/Module.bsl по "
        f"индексу {int(result.get('index_child_records') or 0)}) — индекс состава для этой "
        "стадии обязателен: состояния `pending` отклоняют CHECK'и `bots_picture_state_known` "
        "и `bots_module_state_known`, поэтому недоступный индекс называется отказом стадии, а "
        "не наблюдением (отличие от V48/V53/V54 названо слоем П4)"
    )
    if int(result.get("removed_previous") or 0):
        lines.append(
            f"{indent}Снято прежних строк этой конфигурации: "
            + ", ".join(f"{table}={int(removed_by_table.get(table) or 0)}"
                        for table in sorted(removed_by_table))
            + " — история состояний не заводится (D8), новой ревизии повтор не создаёт"
        )

    observations = result.get("counts_by_observation") or {}
    lines.append(
        f"{indent}Наблюдения круга: "
        + ", ".join(f"{kind}={int(observations.get(kind) or 0)}"
                    for kind in BOTS_OBSERVATION_KINDS)
        + " — отсутствие каталога вида является наблюдением `directory_missing`, а не нулём "
          "строк (Q9, вариант A: три из четырёх выгрузок вида не имеют ни файлами, ни "
          "записями индекса — замер 1.1)"
    )
    if result.get("observations"):
        lines.append(f"{indent}  фактические наблюдения прогона: "
                     + ", ".join(sorted(str(item) for item in result["observations"])))
    if result.get("duplicate_names"):
        lines.append(f"{indent}  ⚠️ повторяющиеся имена внутри выгрузки: "
                     + ", ".join(str(name) for name in result["duplicate_names"]))

    circle = result.get("counts_by_circle_discrepancy") or {}
    index_check = result.get("counts_by_index_check_state") or {}
    lines.append(
        f"{indent}Расхождения ног круга: "
        + ", ".join(f"{state}={int(circle.get(state) or 0)}"
                    for state in BOTS_CIRCLE_DISCREPANCIES)
        + "; состояний сверки с индексом — "
        + ", ".join(f"{state}={int(index_check.get(state) or 0)}"
                    for state in BOTS_INDEX_CHECK_STATES)
        + " — нули являются ответом, а не молчанием (замер 1.3 даёт уникальность имён и "
          "полное совпадение двух ног на единственной выгрузке с видом)"
    )
    if result.get("index_only"):
        lines.append(f"{indent}  запись индекса без файла: "
                     + ", ".join(str(item) for item in result["index_only"]))
    if result.get("file_only"):
        lines.append(f"{indent}  файл вне индекса: "
                     + ", ".join(str(item) for item in result["file_only"]))
    if result.get("uuid_mismatch"):
        lines.append(f"{indent}  ⚠️ несовпадение uuid файла и индекса: "
                     + ", ".join(str(item) for item in result["uuid_mismatch"]))

    prop_counts = result.get("counts_by_properties_state") or {}
    lines.append(
        f"{indent}Свойства файла регистрации (пять тегов — замер 2.2 даёт ровно один набор "
        "тегов на всех файлах круга): состояний — "
        + ", ".join(f"{state}={int(prop_counts.get(state) or 0)}"
                    for state in BOTS_PROPERTIES_STATES)
        + " — незнакомое значение остаётся значением с состоянием `unknown_value` и именем "
          "виновника, а не отказом записи (Q1, вариант A: корпус словарь пяти тегов не "
          "замыкает); пустой тег `<Name/>` не читается отсутствием свойства — состоянием "
          "называется и форма значения, и его отсутствие"
    )
    unknown_properties = result.get("unknown_properties") or {}
    for name in sorted(unknown_properties):
        lines.append(f"{indent}  ⚠️ незнакомое свойство: {name} = "
                     f"{unknown_properties[name]}")

    picture_counts = result.get("counts_by_picture_state") or {}
    picture_classes = result.get("counts_by_picture_target_class") or {}
    picture_lt = result.get("counts_by_picture_load_transparent_state") or {}
    lines.append(
        f"{indent}Ссылка `Picture`: состояний — "
        + ", ".join(f"{state}={int(picture_counts.get(state) or 0)}"
                    for state in BOTS_PICTURE_STATES)
        + f"; блоков {int(result.get('picture_total') or 0)}, разрешено индексом "
          f"{int(result.get('picture_resolved') or 0)} (замер 2.1: блок есть в 2/2 файлов, "
          "разрешена 1 из 2 — разрешение ссылки не равно её наличию); классов цели — "
        + ", ".join(f"{value}={int(picture_classes.get(value) or 0)}"
                    for value in BOTS_PICTURE_TARGET_CLASSES)
        + "; состояний `loadTransparent` — "
        + ", ".join(f"{state}={int(picture_lt.get(state) or 0)}"
                    for state in BOTS_PICTURE_LT_STATES)
        + f"; состоянием `pending` {int(result.get('picture_pending') or 0)}"
    )
    lines.append(
        f"{indent}Состояние `pending` означает «разрешение не проверялось» (индекс состава не "
        "вошёл во вход разбора), `unresolved` — «разрешали и не нашли»; состояния `absent` "
        "(блока нет), `empty_value` (пустой `<xr:Content/>` — замер 2.1) и `std_picture` "
        "(ссылка на стандартное средство платформы, индексом не разрешается никогда) "
        "различимы состоянием, а не нулём; в словари DDL `pending` не входит и отклоняется "
        "CHECK'ом `bots_picture_state_known` (шаг П3)"
    )

    module_counts = result.get("counts_by_module_state") or {}
    lines.append(
        f"{indent}Модуль вида: состояний — "
        + ", ".join(f"{state}={int(module_counts.get(state) or 0)}"
                    for state in BOTS_MODULE_STATES)
        + f"; состоянием `pending` {int(result.get('module_pending') or 0)} — дескрипторы "
        "файла модуля (путь, размер, хэш) пишет этот узел, ТЕКСТ модуля пишет узел V47 в "
        "`bsl_modules`, строки которого данный прогон не трогает (мера M5); `file_and_index` "
        "означает наличие и файла, и записи индекса состава, `file_only`/`index_only` "
        "называют расхождение ног, `absent` — отсутствие обеих (замер 1.2: других состояний "
        "корпус не даёт)"
    )
    if not result.get("common_modules_available"):
        lines.append(
            f"{indent}Перечень общих модулей текущей ревизии не прочитан — имя обработчика "
            "записывается текстом из тега `MethodName`, но проверять его было нечем: "
            "«обработчика нет» и «не чем проверить» — разные ответы (правило C2)"
        )
    for warning in result.get("warnings") or []:
        lines.append(f"{indent}⚠️ {warning}")
    lines.append(f"{indent}{BOTS_CIRCLE_BOUNDARY}")
    return lines


def functional_options_defaults() -> Dict[str, Any]:
    """Закрытый контракт стадии S4k с нулями (C1, C2, C3; узел V56, шаг П5).

    Словарь плоский — тот же, что возвращает слой `load_functional_options` и что собирает
    сводка разбора `collect_functional_options` (один словарь на разбор и на ответ — приём
    `SUMMARY_KEYS` загрузчиков V46/V48…V55); конвейер вкладывает его в свой ключ
    `functional_options` без переименования (C3). Групп `kinds` в контракте нет — это решение
    Q4 (вариант A), а не пропуск: строка применения существует только через id строки опции
    (Q1, вариант A), а порога цены, при котором круг стоило бы резать, замер 1.4 не дал.

    Отдельно обязаны быть названы (план V56, разделы 1–2, 5):

    * числа по таблицам (`removed_by_table`/`written_by_table`) — ДВУМЯ таблицами круга снятия
      (`FUNCTIONAL_OPTIONS_REMOVE_ORDER`), а не одним числом: «записано 539» и «записано 539
      опций + 6 789 применения» для читателя карточки — разные факты (прецедент V50);
    * замкнутые словари состояний по всем колонкам `functional_options_state_columns()` —
      строки `counts_by_*` строятся comprehension'ом по `STATE_VOCABULARIES` разбора, потому
      что второй перечень состояний в проекте нарушил бы и сверку с CHECK живой схемы (П6), и
      обещание C1: неперечисленное состояние читалось бы нулём, которого в словаре нет;
    * `targets_total`/`targets_distinct`/`max_targets_per_file` — распределение, а не только
      итог: 438 целей в одном файле BP3 и 438 целей по разным файлам — разные выгрузки, а
      кратность целей внутри перечня нормальна (замер 2.2, M6), поэтому `targets_distinct`
      называется отдельно от `targets_total`;
    * `targets_by_kind` — распределение целей по видам метаданных (21 вид по замеру 2.2):
      ответ «опция применяется к документу» не зависит от того, загружено ли содержимое этого
      вида (круг V38 шире круга V56), поэтому словарь открытый по ключам и закрытый по смыслу
      — он строится из фактических целей, а нулями не заполняется;
    * `unresolved_targets_total`/`unresolved_locations_total` — целые числа, а не длина
      примеров: примеры обрезаны до `MAX_EXAMPLES`, и «неразрешённых нет» обязано отличаться
      от «примеры обрезаны»;
    * расхождения ног круга (`index_only`/`file_only`/`uuid_mismatch`) — четыре выгрузки дают
      нули (замер 1.1), и нули обязаны быть названы, а не подразумеваться;
    * `unexpected_tags`/`unknown_properties`/`unknown_value_properties` — виновники состояний
      `unknown_tag`/`unknown_value` поимённо: XSD вида нет (замер 1.5), поэтому ответ обязан
      называть незнакомое, а не терять его (Q7, вариант A).
    """
    return {
        "status": STATUS_NOT_RUN,
        "success": False,
        "error": None,
        "reason": None,
        "stage": STAGE_FUNCTIONAL_OPTIONS,
        "configuration_id": None,
        "configuration_uuid": None,
        "configuration_name": None,
        "tables": list(FUNCTIONAL_OPTIONS_REMOVE_ORDER),
        "directory": FUNCTIONAL_OPTIONS_DIR,
        "state_columns": list(functional_options_state_columns()),
        "files_found": 0,
        "files_read": 0,
        "files_failed": [],
        "observations": [],
        "rows_written": 0,
        "options_written": 0,
        "targets_written": 0,
        "removed_previous": 0,
        "removed_by_table": {table: 0 for table in FUNCTIONAL_OPTIONS_REMOVE_ORDER},
        "written_by_table": {table: 0 for table in FUNCTIONAL_OPTIONS_REMOVE_ORDER},
        "index_available": False,
        "index_kind_records": 0,
        "index_only": [],
        "file_only": [],
        "uuid_mismatch": [],
        "counts_by_circle_discrepancy": {
            state: 0 for state in FUNCTIONAL_OPTIONS_CIRCLE_DISCREPANCIES},
        "counts_by_observation": {
            kind: 0 for kind in FUNCTIONAL_OPTIONS_OBSERVATION_KINDS},
        # Словари состояний — одна строка на каждое состояние замкнутого словаря разбора
        # (C1): нулевое состояние остаётся ключом, потому что «состояния не было» и
        # «состояние не считалось» являются разными ответами (C2). Соответствие «ключ сводки →
        # колонка состояния» читается словарём `COUNT_STATE_KEYS` разбора, а не выводится из
        # имени: `counts_by_location_form` считает колонку `location_target_form`.
        **{key: {state: 0 for state in FUNCTIONAL_OPTIONS_STATE_VOCABULARIES[
                FUNCTIONAL_OPTIONS_COUNT_STATE_KEYS[key]]}
           for key in FUNCTIONAL_OPTIONS_COUNT_KEYS},
        "targets_total": 0,
        "targets_distinct": 0,
        "max_targets_per_file": 0,
        "targets_by_kind": {},
        "target_kinds_total": 0,
        "unknown_properties": {},
        "unknown_value_properties": {},
        "unexpected_tags": {},
        "duplicate_targets": [],
        "unresolved_targets_total": 0,
        "unresolved_targets": [],
        "unresolved_locations_total": 0,
        "unresolved_locations": [],
        "statistics_refreshed": 0,
        "warnings": [],
    }


def format_functional_options_lines(result: Dict[str, Any], indent: str = "") -> List[str]:
    """Текст стадии S4k по закрытому контракту `functional_options_defaults()` (C1, C3).

    Формат один для двух контуров: раздела карточки `load_1c_catalog_tool` и ответа
    отдельного входа `load_functional_options_tool` (шаг П5) — прецеденты
    V45/V46/V48/V49/V50/V51/V52/V53/V54/V55. Отказ форматёр называет сам, вызывающий причину
    не повторяет. Групп `kinds` у вида нет (решение Q4, вариант A), поэтому блока «группы
    круга не запрашивались» здесь нет: он обещал бы раздельный вход дозагрузки, которого у
    стадии нет. Блок детей отсутствует осознанно — форм, макетов, команд и модулей у вида нет
    ни в одной выгрузке (замер 1.2 плана V56). Граница круга печатается и при успехе: «строки
    записаны» не равно «о функциональных опциях сохранено всё» — внешнего ключа на цели
    перечня в схеме нет осознанно (Q3), и цель называется состоянием разрешения.
    """
    lines: List[str] = []
    if not result:
        return lines

    if not result.get("success"):
        reason = result.get("error") or result.get("reason") or "загрузчик не назвал причину"
        prefix = ("Стадия не выполнена" if result.get("status") in (None, STATUS_NOT_RUN)
                  else "Стадия не удалась")
        lines.append(f"{indent}{prefix}: {reason}")
        if result.get("files_failed"):
            # Отказ разбора круга — тот же статус `error`, что и отказ записи (словарь
            # статусов контракта замкнут: not_run/ok/skipped/error, C2), поэтому ветка
            # различается признаком круга, а не новым статусом: перечисленные файлы-виновники
            # есть только у остановки до записи.
            lines.append(
                f"{indent}Стадия остановлена ДО записи (приём "
                f"V12/V46/V48/V49/V50/V51/V52/V53/V54/V55): половина круга читалась бы как "
                f"полный состав вида; прежние строки не сняты — "
                f"{FUNCTIONAL_OPTIONS_TABLE} содержит прежнее состояние")
            for failure in (result.get("files_failed") or [])[:10]:
                lines.append(f"{indent}  ⚠️ файл не разобран: "
                             f"{failure.get('source_path')} — {failure.get('reason')}")
        lines.append(f"{indent}{FUNCTIONAL_OPTIONS_REPEAT_HINT}")
        for warning in result.get("warnings") or []:
            lines.append(f"{indent}⚠️ {warning}")
        return lines

    written_by_table = result.get("written_by_table") or {}
    removed_by_table = result.get("removed_by_table") or {}
    lines.append(
        f"{indent}{FUNCTIONAL_OPTIONS_SECTION_HEADER}: записано "
        + ", ".join(f"{table}={int(written_by_table.get(table) or 0)}"
                    for table in FUNCTIONAL_OPTIONS_REMOVE_ORDER)
        + f" (всего {int(result.get('rows_written') or 0)})"
    )
    lines.append(
        f"{indent}Файлов регистрации вида: {int(result.get('files_found') or 0)} "
        f"(разобрано {int(result.get('files_read') or 0)}, каталог "
        f"{result.get('directory') or FUNCTIONAL_OPTIONS_DIR}/, записей индекса состава вида "
        f"{int(result.get('index_kind_records') or 0)}) — круг подтверждается индексом "
        "состава этой конфигурации (правило V43: повторный разбор `ConfigDumpInfo.xml` "
        "вторым источником не становится)"
    )
    if int(result.get("removed_previous") or 0):
        lines.append(
            f"{indent}Снято прежних строк этой конфигурации: "
            + ", ".join(f"{table}={int(removed_by_table.get(table) or 0)}"
                        for table in sorted(removed_by_table))
            + " — снятие начинается со строк применения, иначе каскад "
              "`functional_option_content_functional_option_id_fkey` снял бы их молча, и "
              "число в ответе было бы неправдой (M7); история состояний не заводится (D8)"
        )

    observations = result.get("counts_by_observation") or {}
    lines.append(
        f"{indent}Наблюдения круга: "
        + ", ".join(f"{kind}={int(observations.get(kind) or 0)}"
                    for kind in FUNCTIONAL_OPTIONS_OBSERVATION_KINDS)
        + " — отсутствие каталога вида является наблюдением `directory_missing`, а не нулём "
          "строк (Q6 раздела 6 плана, прецедент Q9 узлов V48/V50/V52–V55: одна из четырёх "
          "выгрузок вида не имеет ни файлами, ни "
          "записями индекса — замер 1.1); `index_not_provided` означает, что индекс состава "
          "в ход разбора не входил, и цели при этом остаются `unresolved` — это другой "
          "ответ, чем «цели нет в перечне»"
    )
    if result.get("observations"):
        lines.append(f"{indent}  фактические наблюдения прогона: "
                     + ", ".join(sorted(str(item) for item in result["observations"])))

    circle = result.get("counts_by_circle_discrepancy") or {}
    lines.append(
        f"{indent}Расхождения ног круга: "
        + ", ".join(f"{state}={int(circle.get(state) or 0)}"
                    for state in FUNCTIONAL_OPTIONS_CIRCLE_DISCREPANCIES)
        + " — нули являются ответом, а не молчанием (замер 1.1 даёт полное совпадение файлов "
          "и записей индекса на тех выгрузках, где вид есть)"
    )
    if result.get("index_only"):
        lines.append(f"{indent}  запись индекса без файла: "
                     + ", ".join(str(item) for item in result["index_only"]))
    if result.get("file_only"):
        lines.append(f"{indent}  файл вне индекса: "
                     + ", ".join(str(item) for item in result["file_only"]))
    if result.get("uuid_mismatch"):
        lines.append(f"{indent}  ⚠️ несовпадение uuid файла и индекса: "
                     + ", ".join(str(item) for item in result["uuid_mismatch"]))

    prop_counts = result.get("counts_by_properties_state") or {}
    lines.append(
        f"{indent}Свойства файла регистрации (шесть тегов — замер 2 плана): состояний — "
        + ", ".join(f"{state}={int(prop_counts.get(state) or 0)}"
                    for state in FUNCTIONAL_OPTIONS_STATE_VOCABULARIES["properties_state"])
        + " — незнакомое значение остаётся значением с состоянием `unknown_value` и именем "
          "виновника, а не отказом записи (Q7, вариант A по прецеденту узла V50: XSD вида "
          "нет, корпус словарь не замыкает); отсутствие тега `PrivilegedGetMode` называется "
          "состоянием `absent`, а не значением `false`"
    )
    for name, count in sorted((result.get("unknown_properties") or {}).items()):
        lines.append(f"{indent}  ⚠️ незнакомый тег файла: {name} = {count}")
    for name, count in sorted((result.get("unknown_value_properties") or {}).items()):
        lines.append(f"{indent}  ⚠️ незнакомое значение свойства: {name} = {count}")
    for tag, count in sorted((result.get("unexpected_tags") or {}).items()):
        lines.append(f"{indent}  ⚠️ неожиданный тег перечня: {tag} = {count}")

    location_counts = result.get("counts_by_location_state") or {}
    form_counts = result.get("counts_by_location_form") or {}
    lines.append(
        f"{indent}Ссылка `Location`: состояний разрешения — "
        + ", ".join(f"{state}={int(location_counts.get(state) or 0)}"
                    for state in FUNCTIONAL_OPTIONS_STATE_VOCABULARIES["location_state"])
        + "; форм адреса — "
        + ", ".join(f"{form or 'EMPTY'}={int(form_counts.get(form) or 0)}"
                    for form in
                    FUNCTIONAL_OPTIONS_STATE_VOCABULARIES["location_target_form"])
        + " — `single` (значение константы, 605), `register_resource` (ресурс регистра "
          "сведений, 154) и `attribute` (реквизит справочника, 6) различаются формой, потому "
          "что разрешение идёт по псевдозаписям колонок индекса состава (замер 2.1); пустая "
          "форма означает «адреса нет», а не «форма не распознана» — для этого служит "
          "состояние `other`"
    )
    if result.get("unresolved_locations"):
        lines.append(f"{indent}  неразрешённых адресов носителя: "
                     f"{int(result.get('unresolved_locations_total') or 0)} — примеры: "
                     + "; ".join(str(item) for item in result["unresolved_locations"]))

    content_counts = result.get("counts_by_content_state") or {}
    resolve_counts = result.get("counts_by_target_resolve_state") or {}
    lines.append(
        f"{indent}Перечень применения `<Content>`: состояний строки вида — "
        + ", ".join(f"{state}={int(content_counts.get(state) or 0)}"
                    for state in FUNCTIONAL_OPTIONS_STATE_VOCABULARIES["content_state"])
        + f"; целей {int(result.get('targets_total') or 0)} "
          f"(различных {int(result.get('targets_distinct') or 0)}, максимум в одном файле "
          f"{int(result.get('max_targets_per_file') or 0)}, видов цели "
          f"{int(result.get('target_kinds_total') or 0)}); состояний разрешения цели — "
        + ", ".join(f"{state}={int(resolve_counts.get(state) or 0)}"
                    for state in
                    FUNCTIONAL_OPTIONS_STATE_VOCABULARIES["target_resolve_state"])
        + " — пустой перечень является состоянием `empty_content` строки вида (замер 2.2: 203 "
          "файла из 765), а не отсутствием строк в таблице применения (Q1, вариант A)"
    )
    targets_by_kind = result.get("targets_by_kind") or {}
    if targets_by_kind:
        lines.append(f"{indent}  целей по видам метаданных: "
                     + ", ".join(f"{kind}={count}" for kind, count in
                                 sorted(targets_by_kind.items(),
                                      key=lambda item: (-item[1], item[0]))))
    if result.get("unresolved_targets"):
        lines.append(f"{indent}  неразрешённых целей: "
                     f"{int(result.get('unresolved_targets_total') or 0)} — примеры: "
                     + "; ".join(str(item) for item in result["unresolved_targets"]))
    if result.get("duplicate_targets"):
        lines.append(f"{indent}  ⚠️ повторяющиеся цели внутри одного перечня: "
                     + "; ".join(str(item) for item in result["duplicate_targets"][:10]))
    if not result.get("index_available"):
        lines.append(
            f"{indent}Индекс состава этой конфигурации не прочитан — сверка файлов с "
            "перечнем и разрешение адресов невозможны: «объекта нет в перечне» и «перечень "
            "не загружен» являются разными ответами (правило C2, Q3)"
        )
    for warning in result.get("warnings") or []:
        lines.append(f"{indent}⚠️ {warning}")
    lines.append(f"{indent}{FUNCTIONAL_OPTIONS_CIRCLE_BOUNDARY}")
    return lines


def functional_options_parameters_defaults() -> Dict[str, Any]:
    """Закрытый контракт стадии S4l с нулями (C1, C2, C3; узел V57, шаг П5).

    Словарь плоский — тот же, что возвращает слой `load_functional_options_parameters` и что
    собирает сводка разбора `collect_functional_options_parameters` (один словарь на разбор и
    на ответ — приём `SUMMARY_KEYS` загрузчиков V46/V48…V56); конвейер вкладывает его в свой
    ключ `functional_options_parameters` без переименования (C3). Групп `kinds` в контракте нет
    — это решение Q5 раздела 6 плана V57 (вариант A), а не пропуск: строка применения
    существует только через id строки параметра (Q1, вариант A), а порога цены, при котором
    круг стоило бы резать, замер 1.4 не дал (14 файлов и 34 цели на весь круг).

    Отдельно обязаны быть названы (план V57, разделы 1–2, 5, 8) — иначе нули читаются как
    «в конфигурации параметров нет»:

    * числа по таблицам (`removed_by_table`/`written_by_table`) — ДВУМЯ таблицами круга снятия
      (`FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER`), а не одним числом: «записано 7» и «записано
      7 параметров + 26 целей применения» — разные факты (прецедент V50, V56);
    * словари состояний по всем колонкам `functional_options_parameters_state_columns()` —
      строки `counts_by_*` строятся comprehension'ом по `STATE_VOCABULARIES` разбора: второй
      перечень состояний нарушил бы и сверку с CHECK живой схемы (П6), и обещание C1; связь
      «ключ сводки → колонка состояния» читается словарём `COUNT_KEY_STATE_COLUMNS` разбора, а
      не выводится из имени;
    * `targets_total`/`targets_distinct`/`max_targets_per_file` — распределение, а не итог:
      20 целей у одного параметра в BP3 и 20 целей по разным параметрам — разные выгрузки
      (замер 2.1, M3);
    * `targets_by_kind` — распределение целей по видам метаданных (круг V38 шире круга V57),
      словарь открытый по ключам и закрытый по смыслу;
    * `counts_by_target_address_form` — форма адреса цели: без неё `InformationRegister.X` и
      `InformationRegister.X.Dimension.Y` стали бы одним свойством (M5, вариант C отклонён Q1);
    * `counts_by_item_type_state` — состояние атрибута `xsi:type` («не проверяли» и
      «не разрешилось» — разные ответы, шаг П3 узла V55);
    * `invariant_violations_total`/`invariant_violations` — нарушение инвариантов пары
      «строка вида ↔ строки применения» (CHECK
      `functional_option_parameters_use_state_matches_targets`, согласованность
      `parameter_full_name`): в отличие от V56 связность проверяется разбором до записи, и
      нарушение называется состоянием, а не потерянной строкой;
    * `unknown_properties`/`unknown_value_properties`/`unexpected_tags`/
      `unexpected_item_types` — виновники состояний поимённо: XSD вида нет (замер 1.5),
      поэтому ответ обязан называть незнакомое, а не терять его (Q7, вариант A);
    * расхождения двух ног круга — ДВУМЯ ключами: словарём `counts_by_circle_discrepancy`
      (числа по замкнутому словарю `index_only`/`file_only`/`uuid_mismatch`) и списками тех
      же имён (виновники поимённо). Пустой список — «расхождений нет» (замер 1.1 даёт полное
      совпадение ног), а отсутствующий ключ — «мы не смотрели», что ответом о выгрузке не
      является (C1, C2; прецедент контрактов V48…V56);
    * `unresolved_targets_total` — целое число, а не длина примеров: примеры обрезаны до
      `MAX_EXAMPLES` (замер 2.1 даёт 34 `exact`, и ноль обязан быть назван).
    """
    return {
        "status": STATUS_NOT_RUN,
        "success": False,
        "error": None,
        "reason": None,
        "stage": STAGE_FUNCTIONAL_OPTIONS_PARAMETERS,
        "configuration_id": None,
        "configuration_uuid": None,
        "configuration_name": None,
        "tables": list(FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER),
        "directory": FUNCTIONAL_OPTIONS_PARAMETERS_DIR,
        "state_columns": list(functional_options_parameters_state_columns()),
        "files_found": 0,
        "files_read": 0,
        "files_failed": [],
        "observations": [],
        "rows_written": 0,
        "parameters_written": 0,
        "targets_written": 0,
        "removed_previous": 0,
        "removed_by_table": {table: 0
                             for table in FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER},
        "written_by_table": {table: 0
                             for table in FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER},
        "index_available": False,
        "index_kind_records": 0,
        # Расхождения ног круга называются ДВУМЯ ключами осознанно: словарь
        # `counts_by_circle_discrepancy` даёт числа (их печатает форматёр), а списки
        # `index_only`/`file_only`/`uuid_mismatch` — виновников поимённо (их печатает
        # форматёр отдельной строкой). Нулевой список означает «расхождений нет», отсутствие
        # ключа — «мы не смотрели»; второе не является ответом о выгрузке (C1, C2; прецедент
        # контрактов V48…V56).
        "index_only": [],
        "file_only": [],
        "uuid_mismatch": [],
        "counts_by_circle_discrepancy": {
            state: 0 for state in FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_DISCREPANCIES},
        "counts_by_observation": {
            kind: 0 for kind in FUNCTIONAL_OPTIONS_PARAMETERS_OBSERVATION_KINDS},
        # Словари состояний — одна строка на каждое состояние замкнутого словаря разбора
        # (C1): нулевое состояние остаётся ключом, потому что «состояния не было» и
        # «состояние не считалось» являются разными ответами (C2).
        **{key: {state: 0 for state in FUNCTIONAL_OPTIONS_PARAMETERS_STATE_VOCABULARIES[
                FUNCTIONAL_OPTIONS_PARAMETERS_COUNT_STATE_KEYS[key]]}
           for key in FUNCTIONAL_OPTIONS_PARAMETERS_COUNT_KEYS},
        "targets_total": 0,
        "targets_distinct": 0,
        FUNCTIONAL_OPTIONS_PARAMETERS_MAX_TARGETS_KEY: 0,
        "targets_by_kind": {},
        "target_kinds_total": 0,
        "unknown_properties": {},
        "unknown_value_properties": {},
        "unexpected_tags": {},
        "unexpected_item_types": {},
        "duplicate_targets": [],
        "unresolved_targets_total": 0,
        "unresolved_targets": [],
        "invariant_violations_total": 0,
        "invariant_violations": [],
        "statistics_refreshed": 0,
        "warnings": [],
    }


def format_functional_options_parameters_lines(result: Dict[str, Any],
                                               indent: str = "") -> List[str]:
    """Текст стадии S4l по закрытому контракту `functional_options_parameters_defaults()`
    (C1, C3; узел V57, шаг П5).

    Формат один для двух контуров: раздела карточки `load_1c_catalog_tool` и ответа
    отдельного входа `load_functional_options_parameters_tool` (шаг П5) — прецеденты
    V45/V46/V48…V56. Отказ форматёр называет сам, вызывающий причину не повторяет. Групп
    `kinds` у вида нет (решение Q5 раздела 6 плана V57, вариант A), поэтому блока «группы
    круга не запрашивались» здесь нет: он обещал бы раздельный вход дозагрузки, которого у
    стадии нет. Блок детей отсутствует осознанно — форм, макетов, команд, модулей и каталогов
    содержимого у вида нет ни в одной выгрузке (замер 1.2 плана V57). Блок `Location`
    отсутствует тоже осознанно: в отличие от круга 2.11 адреса носителя у вида нет (замер 2
    плана), есть только перечень `<Use>` — поэтому вместо него печатается форма адреса цели.
    Граница круга печатается и при успехе: «строки записаны» не равно «о параметрах сохранено
    всё» — внешнего ключа на цели перечня в схеме нет осознанно (Q3), и цель называется
    состоянием разрешения.
    """
    lines: List[str] = []
    if not result:
        return lines

    if not result.get("success"):
        reason = result.get("error") or result.get("reason") or "загрузчик не назвал причину"
        prefix = ("Стадия не выполнена" if result.get("status") in (None, STATUS_NOT_RUN)
                  else "Стадия не удалась")
        lines.append(f"{indent}{prefix}: {reason}")
        if result.get("files_failed"):
            # Отказ разбора круга — тот же статус `error`, что и отказ записи (словарь
            # статусов контракта замкнут: not_run/ok/skipped/error, C2), поэтому ветка
            # различается признаком круга, а не новым статусом: перечисленные файлы-виновники
            # есть только у остановки до записи.
            lines.append(
                f"{indent}Стадия остановлена ДО записи (приём "
                f"V12/V46/V48…V56): половина круга читалась бы как полный состав вида; "
                f"прежние строки не сняты — "
                f"{FUNCTIONAL_OPTION_PARAMETERS_TABLE} содержит прежнее состояние")
            for failure in (result.get("files_failed") or [])[:10]:
                lines.append(f"{indent}  ⚠️ файл не разобран: "
                             f"{failure.get('source_path')} — {failure.get('reason')}")
        if result.get("invariant_violations"):
            lines.append(
                f"{indent}⚠️ инварианты пары «строка вида ↔ строки применения» нарушены в "
                f"{int(result.get('invariant_violations_total') or 0)} файлах — круг не "
                "записан, потому что состояние `use_state` обязано выводиться из строк "
                "применения (CHECK "
                "`functional_option_parameters_use_state_matches_targets`), а не из догадки")
        lines.append(f"{indent}{FUNCTIONAL_OPTIONS_PARAMETERS_REPEAT_HINT}")
        for warning in result.get("warnings") or []:
            lines.append(f"{indent}⚠️ {warning}")
        return lines

    written_by_table = result.get("written_by_table") or {}
    removed_by_table = result.get("removed_by_table") or {}
    lines.append(
        f"{indent}{FUNCTIONAL_OPTIONS_PARAMETERS_SECTION_HEADER}: записано "
        + ", ".join(f"{table}={int(written_by_table.get(table) or 0)}"
                    for table in FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER)
        + f" (всего {int(result.get('rows_written') or 0)})"
    )
    lines.append(
        f"{indent}Файлов регистрации вида: {int(result.get('files_found') or 0)} "
        f"(разобрано {int(result.get('files_read') or 0)}, каталог "
        f"{result.get('directory') or FUNCTIONAL_OPTIONS_PARAMETERS_DIR}/, записей индекса "
        f"состава вида {int(result.get('index_kind_records') or 0)}) — круг подтверждается "
        "индексом состава этой конфигурации точным `object_type = "
        f"{FUNCTIONAL_OPTIONS_PARAMETERS_META_TAG}` (правило V43: повторный разбор "
        "`ConfigDumpInfo.xml` вторым источником не становится; соседний вид `FunctionalOption` "
        "в круг не берётся — замер 1.2)"
    )
    if int(result.get("removed_previous") or 0):
        lines.append(
            f"{indent}Снято прежних строк этой конфигурации: "
            + ", ".join(f"{table}={int(removed_by_table.get(table) or 0)}"
                        for table in sorted(removed_by_table))
            + " — снятие начинается со строк применения, иначе каскад "
              "`functional_option_parameter_targets_parameter_fkey` снял бы их молча, и число "
              "в ответе было бы неправдой (M7); история состояний не заводится (D8)"
        )

    observations = result.get("counts_by_observation") or {}
    lines.append(
        f"{indent}Наблюдения круга: "
        + ", ".join(f"{kind}={int(observations.get(kind) or 0)}"
                    for kind in FUNCTIONAL_OPTIONS_PARAMETERS_OBSERVATION_KINDS)
        + " — отсутствие каталога вида является наблюдением `directory_missing`, а не нулём "
          "строк (Q9, прецедент Q9 узлов V48/V50/V52–V56: одна из четырёх выгрузок вида не "
          "имеет ни файлами, ни записями индекса — замер 1.1); `index_not_provided` означает, "
          "что индекс состава в ход разбора не входил, и цели при этом остаются `unresolved` "
          "— это другой ответ, чем «цели нет в перечне»"
    )
    if result.get("observations"):
        lines.append(f"{indent}  фактические наблюдения прогона: "
                     + ", ".join(sorted(str(item) for item in result["observations"])))

    circle = result.get("counts_by_circle_discrepancy") or {}
    lines.append(
        f"{indent}Расхождения ног круга: "
        + ", ".join(f"{state}={int(circle.get(state) or 0)}"
                    for state in FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_DISCREPANCIES)
        + " — нули являются ответом, а не молчанием (замер 1.1 даёт полное совпадение файлов "
          "и записей индекса на тех выгрузках, где вид есть); ключей `child_mismatches`/"
          "`index_pseudo_entries` в словаре нет осознанно: детей и псевдозаписей вида индекс "
          "не держит (замер 1.2)"
    )
    if result.get("index_only"):
        lines.append(f"{indent}  запись индекса без файла: "
                     + ", ".join(str(item) for item in result["index_only"]))
    if result.get("file_only"):
        lines.append(f"{indent}  файл вне индекса: "
                     + ", ".join(str(item) for item in result["file_only"]))
    if result.get("uuid_mismatch"):
        lines.append(f"{indent}  ⚠️ несовпадение uuid файла и индекса: "
                     + ", ".join(str(item) for item in result["uuid_mismatch"]))


    prop_counts = result.get("counts_by_properties_state") or {}
    lines.append(
        f"{indent}Свойства файла регистрации (`Name`, `Synonym`, `Comment`, `Use`): "
        "состояний разбора — "
        + ", ".join(f"{state}={int(prop_counts.get(state) or 0)}"
                    for state in FUNCTIONAL_OPTIONS_PARAMETERS_STATE_VOCABULARIES[
                        "properties_state"])
        + " — словаря значений свойств ни схемой, ни разборным словарём круг не замкнут "
          "(Q7, вариант A: XSD вида нет — замер 1.5, корпус 14 файлов), поэтому незнакомое "
          "остаётся состоянием `unknown_value`/`unknown_tag` с именем виновника"
    )
    unknown_properties = result.get("unknown_properties") or {}
    unknown_values = result.get("unknown_value_properties") or {}
    unexpected_tags = result.get("unexpected_tags") or {}
    if unknown_properties or unknown_values or unexpected_tags:
        lines.append(
            f"{indent}  ⚠️ незнакомые имена свойств: "
            + (", ".join(f"{name}={count}"
                         for name, count in sorted(unknown_properties.items())) or "нет")
            + "; незнакомые значения: "
            + (", ".join(f"{name}={count}"
                         for name, count in sorted(unknown_values.items())) or "нет")
            + "; незнакомые теги: "
            + (", ".join(f"{tag}={count}"
                         for tag, count in sorted(unexpected_tags.items())) or "нет"))

    use_counts = result.get("counts_by_use_state") or {}
    resolve_counts = result.get("counts_by_target_resolve_state") or {}
    form_counts = result.get("counts_by_target_address_form") or {}
    item_type_counts = result.get("counts_by_item_type_state") or {}
    lines.append(
        f"{indent}Перечень применения `<Use>`: состояний строки вида — "
        + ", ".join(f"{state}={int(use_counts.get(state) or 0)}"
                    for state in FUNCTIONAL_OPTIONS_PARAMETERS_STATE_VOCABULARIES["use_state"])
        + f"; целей {int(result.get('targets_total') or 0)} "
          f"(различных {int(result.get('targets_distinct') or 0)}, максимум в одном файле "
          f"{int(result.get(FUNCTIONAL_OPTIONS_PARAMETERS_MAX_TARGETS_KEY) or 0)}, видов цели "
          f"{int(result.get('target_kinds_total') or 0)}); состояний разрешения цели — "
        + ", ".join(f"{state}={int(resolve_counts.get(state) or 0)}"
                    for state in
                    FUNCTIONAL_OPTIONS_PARAMETERS_STATE_VOCABULARIES["target_resolve_state"])
        + "; форм адреса цели — "
        + ", ".join(f"{form or 'EMPTY'}={int(form_counts.get(form) or 0)}"
                    for form in
                    FUNCTIONAL_OPTIONS_PARAMETERS_STATE_VOCABULARIES["target_address_form"])
        + "; состояний атрибута `xsi:type` — "
        + ", ".join(f"{state}={int(item_type_counts.get(state) or 0)}"
                    for state in
                    FUNCTIONAL_OPTIONS_PARAMETERS_STATE_VOCABULARIES["item_type_state"])
        + " — пустой перечень является состоянием `empty_content` строки вида (замер 2.1: "
          "пустых перечней корпус не давал), а не отсутствием строк в таблице применения "
          "(Q1, вариант A); форма адреса различает объект целиком (`object`) и его срезы "
          "(`dimension`/`register_resource`/`attribute`/`tabular_section`), потому что иначе "
          "`InformationRegister.X` и `InformationRegister.X.Dimension.Y` стали бы одним "
          "свойством (M5, вариант C отклонён Q1)"
    )
    targets_by_kind = result.get("targets_by_kind") or {}
    if targets_by_kind:
        lines.append(f"{indent}  целей по видам метаданных: "
                     + ", ".join(f"{kind}={count}" for kind, count in
                                 sorted(targets_by_kind.items(),
                                      key=lambda item: (-item[1], item[0]))))
    if result.get("unresolved_targets"):
        lines.append(f"{indent}  неразрешённых целей: "
                     f"{int(result.get('unresolved_targets_total') or 0)} — примеры: "
                     + "; ".join(str(item) for item in result["unresolved_targets"]))
    if result.get("duplicate_targets"):
        lines.append(f"{indent}  ⚠️ повторяющиеся цели внутри одного перечня: "
                     + "; ".join(str(item) for item in result["duplicate_targets"][:10]))
    unexpected_item_types = result.get("unexpected_item_types") or {}
    if unexpected_item_types:
        lines.append(f"{indent}  ⚠️ незнакомые значения `xsi:type`: "
                     + ", ".join(f"{value or 'EMPTY'}={count}" for value, count in
                                 sorted(unexpected_item_types.items())))
    if int(result.get("invariant_violations_total") or 0):
        lines.append(f"{indent}  ⚠️ нарушений инвариантов пары: "
                     f"{int(result.get('invariant_violations_total') or 0)} — примеры: "
                     + "; ".join(str(item) for item in result["invariant_violations"]))
    if not result.get("index_available"):
        lines.append(
            f"{indent}Индекс состава этой конфигурации не прочитан — сверка файлов с "
            "перечнем и разрешение целей невозможны: «объекта нет в перечне» и «перечень не "
            "загружен» являются разными ответами (правило C2, Q3). Отличие от V55 названо "
            "слоем: состояний `pending` в схеме вида нет, поэтому недоступный индекс является "
            "предупреждением, а не отказом стадии"
        )
    for warning in result.get("warnings") or []:
        lines.append(f"{indent}⚠️ {warning}")
    lines.append(f"{indent}{FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_BOUNDARY}")
    return lines


def defined_types_defaults() -> Dict[str, Any]:
    """Закрытый контракт стадии S4m с нулями (C1, C2, C3; узел V58, шаг П5).

    Словарь плоский — тот же, что возвращает слой `load_defined_types` и что собирает сводка
    разбора `collect_defined_types` (один словарь на разбор и на ответ — приём `SUMMARY_KEYS`
    загрузчиков V46/V48…V57); нулевая часть строится импортом `zero_counts()` слоя разбора,
    потому что второй перечень состояний нарушил бы и сверку с CHECK живой схемы (П6), и
    обещание C1. Конвейер вкладывает словарь в свой ключ `defined_types` без переименования
    (C3). Групп `kinds` в контракте нет — это решение Q1 раздела 5 плана V58 (вариант A), а не
    пропуск: блок `<Type>` является колонками строки вида, поэтому состояния «записать свойства
    без типа» в модели нет, а порога цены замер 2.2 не дал (820 файлов и 17 544 значения на
    весь круг).

    Отдельно обязаны быть названы (план V58, разделы 1–2, 5, 8) — иначе нули читаются как
    «в конфигурации определяемых типов нет»:

    * числа по таблицам (`removed_by_table`/`written_by_table`) — списком таблиц круга снятия
      (`DEFINED_TYPES_REMOVE_ORDER`), а не одним числом: ответ обязан называть, каким кругом
      он работал, даже когда круг — одна таблица (прецедент `BOTS_TABLES` V55);
    * словари состояний по всем колонкам `DEFINED_TYPES_STATE_VOCABULARIES` — строки
      `counts_by_*` строятся comprehension'ом по словарю разбора (C1);
    * `counts_by_class` и `counts_by_container` — распределение значений блока `<Type>` по
      классам и по форме контейнера: без них `ref_value` и `object_value` стали бы одним
      свойством, а `<v8:TypeSet>` — молчанием (замеры 2.3, M4);
    * `resolve_exact`/`resolve_no_target`/`resolve_unresolved` — состояния разрешения цели
      значения («не разрешено индексом» и «цели нет по определению» — разные ответы,
      прецедент V48/V50/V52);
    * `distinct_target_addresses` — число РАЗРЕШЁнных различных адресов целей; выведенных из
      формы значения адресов больше (2 419 против 2 413, раздел 2.5), и обе величины называются
      форматаром раздельно, потому что смешение читалось бы как «шесть целей потеряно»;
    * `types_total`/`max_values_per_file` — распределение, а не итог: 657 значений в одном
      файле и 657 по разным файлам — разные выгрузки (замер 2.2);
    * `rows_with_qualifiers` — число СТРОК вида с квалификаторами (182), а не число блоков
      (191): строка одна на файл, и девять файлов несут по два блока (раздел 2.2);
    * `row_problems` — число самопроверок строки (`row_problems()` слоя повторяет CHECK'ы
      схемы): нуль обязан быть назван, потому что «самопроверок нет» и «самопроверок не
      считали» — разные ответы;
    * расхождения ног круга — ДВУМЯ ключами: словарём `counts_by_circle_discrepancy` (числа по
      замкнутому словарю `index_only`/`file_only`/`uuid_mismatch`) и списками тех же имён
      (виновники поимённо). Пустой список — «расхождений нет» (замеры 1.1, 1.2 дают полное
      совпадение трёх ног на 820 файлов), а отсутствующий ключ — «мы не смотрели» (C1, C2);
    * `observations` — словарь наблюдений по закрытому перечню `OBSERVATION_KINDS` слоя:
      `directory_missing` (корпусом не дан — проверяется фикстурой П6), `unexpected_dir`,
      `unexpected_file`, `type_set_container`, `empty_qualifier_block`, `index_not_provided`;
    * `failures`/`duplicate_names`/`examples` — виновники поимённо, а не только счётчики.
    """
    return {
        "status": STATUS_NOT_RUN,
        "success": False,
        "error": None,
        "reason": None,
        "stage": STAGE_DEFINED_TYPES,
        "configuration_id": None,
        "configuration_uuid": None,
        "configuration_name": None,
        "tables": list(DEFINED_TYPES_REMOVE_ORDER),
        "directory": DEFINED_TYPES_DIR,
        "state_columns": list(DEFINED_TYPES_STATE_VOCABULARIES),
        "rows_written": 0,
        "defined_types_written": 0,
        "removed_previous": 0,
        "removed_by_table": {table: 0 for table in DEFINED_TYPES_REMOVE_ORDER},
        "written_by_table": {table: 0 for table in DEFINED_TYPES_REMOVE_ORDER},
        "index_available": False,
        "index_kind_records": 0,
        "statistics_refreshed": 0,
        # Словари наблюдений и расхождений — по закрытым перечням слоя разбора: нулевой ключ
        # отличается от отсутствующего (C1, C2).
        "counts_by_circle_discrepancy": {
            state: 0 for state in DEFINED_TYPES_CIRCLE_DISCREPANCIES},
        "index_only": [],
        "file_only": [],
        "uuid_mismatch": [],
        "duplicate_names": [],
        "failures": [],
        "examples": [],
        # Числа круга, словари состояний, классы, контейнеры, состояния разрешения и
        # наблюдения — ОДНИМ словарём слоя разбора (его же заполняет `collect_defined_types`):
        # второй перечень состояний разошёлся бы с CHECK живой схемы (П6).
        **defined_types_zero_counts(),
        "warnings": [],
    }



def format_defined_types_lines(result: Dict[str, Any], indent: str = "") -> List[str]:
    """Строки отчёта стадии S4m — числа по замкнутым словарям, а не только ненулевые (C1;
    узел V58, шаг П5).

    Формат тот же, что у `format_functional_options_parameters_lines` (V57) и
    `format_bots_lines` (V55): словарь состояний печатается по перечню слоя comprehension'ом,
    поэтому состояние с нулём видно в ответе, а не пропадает; виновники (отказанные файлы,
    расхождения ног, неразрешённые цели) перечисляются поимённо, потому что счётчик без имени
    не говорит, что чинить.

    Границы, которые форматар обязан назвать текстом (план V58, разделы 2, 5, 8):

    * `unresolved` ≠ «типа нет»: у цели `unresolved` адрес есть — строки индекса состава данной
      выгрузки нет (замер 2.5: шесть `BusinessProcessRoutePoint.*`), а `no_target` — это
      примитив `xs:*`, у которого цели нет по определению (197 значений);
    * `derived_target_addresses` и `distinct_target_addresses` печатаются раздельно (2 419
      против 2 413) — иначе разница читается как потерянные строки (раздел 2.5);
    * `rows_with_qualifiers` (182) и число блоков квалификаторов (191) — разные величины:
      строка одна на файл, девять файлов несут по два блока `Length/Precision` (раздел 2.2);
    * пустой каталог вида — НЕ отказ: `files_found = 0` с наблюдением `directory_missing`
      (Q9, вариант A). Корпус такой выгрузки не даёт (вид есть во всех четырёх — 2 / 1 / 304 /
      513 файла), поэтому случай проверяется фикстурой постоянной проверки узла;
    * индекс состава, не участвовавший в разборе, — предупреждение с наблюдением
      `index_not_provided` (отличие от V55, где `pending` отклоняется CHECK'ом и недоступный
      индекс является отказом стадии);
    * текст границы круга (что узел НЕ делает: чужие слои `<Type>` с `cfg:DefinedType.*` не
      переразрешает — мера M5; тексты `bsl_modules` узла V47 не читает и не снимает; existence
      целей не утверждает — Q3) печатается последней строкой.
    """
    lines: List[str] = []
    if result.get("status") not in (STATUS_OK, STATUS_SKIPPED):
        error = result.get("error") or result.get("reason") or "стадия не выполнялась"
        lines.append(f"{indent}⚠️ {STAGE_DEFINED_TYPES}: {error}")
        for failure in result.get("failures") or []:
            lines.append(f"{indent}  ⚠️ {failure}")
        return lines
    if result.get("status") == STATUS_SKIPPED:
        lines.append(
            f"{indent}{STAGE_DEFINED_TYPES}: {result.get('reason') or 'вид не запрошен'}")
        return lines

    lines.append(
        f"{indent}{STAGE_DEFINED_TYPES}: конфигурация id="
        f"{result.get('configuration_id')} uuid={result.get('configuration_name')}, "
        f"строк {int(result.get('defined_types_written') or 0)} "
        f"(снято прежних {int(result.get('removed_previous') or 0)}), "
        f"файлов найдено {int(result.get('files_found') or 0)}, "
        f"разобрано {int(result.get('files_parsed') or 0)}, "
        f"отказов {int(result.get('files_failed') or 0)}"
    )
    lines.append(
        f"{indent}  по таблицам: "
        + ", ".join(
            f"{table}:снято="
            f"{int((result.get('removed_by_table') or {}).get(table) or 0)}/записано="
            f"{int((result.get('written_by_table') or {}).get(table) or 0)}"
            for table in DEFINED_TYPES_REMOVE_ORDER)
        + f"; статистика обновлена: {int(result.get('statistics_refreshed') or 0)}"
    )
    if int(result.get("files_failed") or 0):
        lines.append(f"{indent}  ⚠️ отказавшие файлы: "
                     + "; ".join(str(item) for item in (result.get("failures") or [])[:10]))
    if result.get("duplicate_names"):
        lines.append(f"{indent}  ⚠️ повторные имена вида внутри выгрузки: "
                     + "; ".join(str(item)
                                 for item in (result.get("duplicate_names") or [])[:10]))

    vocabulary = DEFINED_TYPES_STATE_VOCABULARIES

    def counts_of(column: str) -> Dict[str, int]:
        return result.get("counts_by_" + column) or {}

    def state_line(column: str) -> str:
        counts = counts_of(column)
        return column + ": " + ", ".join(
            f"{state}={int(counts.get(state) or 0)}" for state in vocabulary[column])

    lines.append(
        f"{indent}Свойства файла регистрации — " + state_line("properties_state")
        + "; незнакомые имена свойств — "
        + (", ".join(f"{name}={count}" for name, count in
                     sorted((result.get("unknown_properties") or {}).items())) or "нет")
        + "; " + state_line("internal_info_state")
        + " — блок `InternalInfo` хранится четырьмя значениями с состоянием (Q4): он связывает "
          "имя вида с идентификатором разбора бинарных внешних объектов (узел V25), но ключом "
          "не является, потому что 1 154 различных идентификатора приходятся на 1 640 слотов "
          "(замер 1.3)")
    lines.append(
        f"{indent}Блок `<Type>`: состояний разбора — "
        + ", ".join(f"{state}={int(counts_of('type_parse_state').get(state) or 0)}"
                    for state in vocabulary["type_parse_state"])
        + "; кратности — "
        + ", ".join(f"{state}={int(counts_of('type_multiplicity').get(state) or 0)}"
                    for state in vocabulary["type_multiplicity"])
        + f"; значений {int(result.get('types_total') or 0)} (максимум в одном файле "
          f"{int(result.get('max_values_per_file') or 0)})"
    )
    class_counts = result.get("counts_by_class") or {}
    container_counts = result.get("counts_by_container") or {}
    lines.append(
        f"{indent}  классов значения — "
        + ", ".join(f"{value}={int(class_counts.get(value) or 0)}"
                    for value in DEFINED_TYPES_VALUE_CLASS_VALUES)
        + "; форм контейнера — "
        + (", ".join(f"{form}={int(count)}" for form, count in sorted(container_counts.items()))
           or "нет")
    )
    lines.append(
        f"{indent}  разрешений цели значения — "
        + ", ".join(f"{state}={int(result.get(key) or 0)}" for key, state in
                    zip(DEFINED_TYPES_RESOLVE_COUNT_KEYS, DEFINED_TYPES_RESOLVE_STATES))
        + f"; адресов целей выведено {int(result.get('derived_target_addresses') or 0)}, "
          f"подтверждено индексом состава {int(result.get('distinct_target_addresses') or 0)} — "
          "разница является целью, у которой адрес выведен из формы значения, но строки индекса "
          "состава данной выгрузки нет (`unresolved`), и это НЕ потерянные строки; `no_target` "
          "— примитивы `xs:*`, у которых цели нет по определению (раздел 2.5 плана)"
    )
    if result.get("unresolved_targets"):
        lines.append(f"{indent}  ⚠️ неразрешённых целей: "
                     f"{int(result.get('unresolved_targets_total') or 0)} — примеры: "
                     + "; ".join(str(item) for item in result["unresolved_targets"]))
    lines.append(
        f"{indent}Квалификаторы: строк вида с квалификаторами "
        f"{int(result.get('rows_with_qualifiers') or 0)} — число блоков квалификаторов больше "
        "(191 против 182 по замеру 2.2), потому что строка одна на файл, а файл может нести "
        "два блока `Length`/`Precision`; содержимое блоков лежит колонкой `type_qualifiers` "
        "строки вида (Q1, вариант A), отдельной таблицы и словаря состояний квалификаторов у "
        "узла нет осознанно — пустой блок называется наблюдением `empty_qualifier_block`"
    )
    lines.append(
        f"{indent}Самопроверок строки (повтор CHECK'ов схемы слоем разбора без PostgreSQL): "
        f"{int(result.get('row_problems') or 0)} — нуль обязан быть назван, потому что "
        "«самопроверок нет» и «самопроверок не считали» являются разными ответами"
    )
    for example in result.get("examples") or []:
        lines.append(f"{indent}  ⚠️ {example.get('source_path')}: "
                     + "; ".join(str(item)
                                 for item in (example.get("warnings") or [])[:3]))

    discrepancy_counts = result.get("counts_by_circle_discrepancy") or {}
    lines.append(
        f"{indent}Сверка круга с индексом состава (записей вида в индексе "
        f"{int(result.get('index_kind_records') or 0)}): "
        + ", ".join(f"{state}={int(discrepancy_counts.get(state) or 0)}"
                    for state in DEFINED_TYPES_CIRCLE_DISCREPANCIES)
    )
    for key in ("index_only", "file_only", "uuid_mismatch"):
        if result.get(key):
            lines.append(f"{indent}  ⚠️ {key}: "
                         + "; ".join(str(item) for item in (result.get(key) or [])[:10]))

    observations = result.get("observations") or {}
    lines.append(
        f"{indent}Наблюдения круга: "
        + ", ".join(f"{kind}={int(observations.get(kind) or 0)}"
                    for kind in DEFINED_TYPES_OBSERVATION_KINDS)
        + " — отсутствующий каталог вида является состоянием выгрузки, а не отказом стадии (Q9, "
          "вариант A); `type_set_container` и `empty_qualifier_block` корпусом не даны и "
          "называются наблюдением, а не состоянием строки (M4, прецедент `DayTimes` V54)"
    )
    if not result.get("index_available"):
        lines.append(
            f"{indent}Индекс состава этой конфигурации не прочитан — сверка файлов с перечнем и "
            "разрешение целей значения невозможны: «цели нет в перечне» и «перечень не "
            "загружен» являются разными ответами (правило C2, Q3). Отличие от V55 названо "
            "слоем: состояний `pending` в схеме вида нет, поэтому недоступный индекс является "
            "предупреждением, а не отказом стадии"
        )
    for warning in result.get("warnings") or []:
        lines.append(f"{indent}⚠️ {warning}")
    lines.append(f"{indent}{DEFINED_TYPES_CIRCLE_BOUNDARY}")
    return lines

