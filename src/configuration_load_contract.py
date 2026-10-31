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
    узла V49), S4b — не имеет (решение Q4.1). Стадия без подсказки была бы ошибкой контракта,
    поэтому ответ по умолчанию — полная перезагрузка, а не пустая строка.
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

# Что из содержимого дочерних объектов стадия S4 НЕ загружает — определение перенесено
# в это место узлом V50 (шаг П8): текст ссылается на заголовок раздела S4e, объявленного
# рядом с кругом таблиц вида, поэтому заголовок обязан идти раньше текста (прецедент
# V48/V49). Обоснование того, почему часть групп модели V38 остаётся незакрытой, держится
# у стадии S4 — см. комментарий перед местом, откуда сделан перенос.
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
    "реквизиты, остальные её виды этой стадией не закрываются) и тексты модулей объектов "
    "конфигурации — шесть слотов Ext/ (узел V47, стадия S4b, раздел «"
    "МОДУЛИ ОБЪЕКТОВ КОНФИГУРАЦИИ» ниже); не реализованы реквизиты и "
    "табличные части объектов "
    "конфигурации, формы и их модули, макеты, значения перечислений и команды — "
    "остальные группы A–H "
    "модели V38, узел V18 остаётся открытым"
)

# Таблицы, чьи строки остаются нетронутыми, когда группа не запрошена: ответ обязан назвать
# это, а не отдать нули как «в конфигурации ничего нет» (C2).
FOREIGN_STAGE_TABLES: Tuple[str, ...] = (
    SESSION_PARAMETER_TABLES + ROLE_TABLES + COMMON_ATTRIBUTES_TABLES
    + EXCHANGE_PLAN_TABLES
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

