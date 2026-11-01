#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Загрузчик свойств планов обмена (узел V51, шаг П5, 31.10.2026).

Стадия S4f конвейера первого слоя: файлы вида `ExchangePlans` (позиция 2.6 нормативного
списка плана `docs/CONFIGURATION_EXCHANGE_PLANS_PLAN.md`) в таблицы вида `exchange_plans`,
`exchange_plan_content`, `commands` и в таблицы её детей `attributes`, `tabular_sections`,
`forms`, `form_ext`, `templates`. Норматив — тот же план (решения Q1–Q8, правила C1–C3);
разбор файлов вида — отдельный модуль `src/configuration_exchange_plans.py` (шаг П3),
писатели строк — реестр `CONFIGURATION_OBJECT_WRITERS` и четыре писателя-наследника детей
вида (шаг П4).

Почему стадия отдельная, а не седьмой вид S4 и не расширение S4e (прецеденты Q5 узлов
V48–V50): правило C3 требует своего ключа ответа `exchange_plans`; порядок `STAGES`
повторяет порядок нормативного списка (2.6 идёт сразу за 2.5), поэтому S4f стоит между
S4e и S4b. Круг стадии S4 (`CHILD_TABLES`) от круга версионности отделён шагом П3:
регистрация таблиц вида в `CONFIGURATION_VERSIONED_TABLES` молча добавила бы их к чужой
стадии.

Почему стадия является одновременно слоем (прецедент V44/V46/V48/V49/V50):

* ключ строки — `configuration_uuid`, а не `id` заголовка: `force=True` меняет id, uuid
  остаётся прежним;
* стадия вызывается ПОСЛЕ коммита транзакции заголовка: `transaction()` каждый раз
  открывает новое соединение, и в собственной транзакции заголовка слой не увидел бы ни
  строки заголовка, ни строк индекса состава, по которым разрешаются цели перечня
  `<Content>` (Q4);
* отдельный MCP-инструмент `load_exchange_plans_tool` нужен для случая «изменились только
  файлы `ExchangePlans/`»: заголовок и индекс состава при этом не меняются. Стадия
  конвейера и этот инструмент вызывают одну и ту же функцию слоя — двух кодов, которые
  могли бы разойтись, в проекте нет.

Группы правочного вызова (`kinds`) у вида есть — в отличие от V50 — и это тоже решение, а
не упущение (Q5, раздел 5.4 плана): круг вида несимметричен по цене (46 строк свойств
против 22 515 строк `<Content>` и 33.2 МБ текстов макетов), а риск V50 здесь отсутствует
физически: перечни детей строятся из атрибутов `uuid` выгрузки, а не из записанных строк
детей. Пустое значение параметра означает ВЕСЬ круг. Границы запроса называются отказом:
`slots` неотделима от строки вида (CHECK `exchange_plans_slot_content_matches_state`
требует называть состояние слота на каждой строке), `forms` неотделима от `form_ext`
(каскад `form_ext_form_id_fkey`).

Что здесь происходит и чего здесь нет:

* круг задают каталог `ExchangePlans/` (файл регистрации вида и его подкаталоги `Forms/`,
  `Templates/`, `Commands/`, `Ext/`) и записи индекса состава того же вида
  (`ExchangePlan.<Имя>`); расхождение двух источников называется `index_only` /
  `file_only` / `uuid_mismatch`, расхождения детей с индексом — `child_mismatches`,
  объявления вида с его каталогом — `declaration_mismatches`; нули обязаны быть названы, а
  не подразумеваемы;
* строки вида пишутся `insert_many`, а не `insert_ids`: ссылка перечня `<Content>` держится
  парой (`exchange_plan_object_uuid`, `revision_no`), а не числовым id строки вида
  (спецификация `ExchangePlanContentRowWriter`, ключ
  `exchange_plan_content_plan_revision_ordinal_key`); внешнего ключа на `exchange_plans(id)`
  в схеме нет ни у одной таблицы — это называет зонд шага П5;
* строки форм пишутся `insert_ids`, потому что `form_ext` ссылается на числовой `form_id`
  (прецедент V13/V14 внешнего контура); описание формы относится к ревизии самой формы,
  поэтому `form_ext` получает тот же `revision_no`, что и строка формы;
* колонки табличных частей пишутся в ту же таблицу `attributes`, но их `parent_uuid` равен
  uuid табличной части, а не вида (замер 3.4 — так же их описывает индекс состава);
* тела модулей объекта/менеджера и модулей команд этим узлом НЕ читаются: `bsl_modules` с
  `parent_type='configuration_objects'` пишет V47 (Q8), здесь файлы называются
  дескрипторами и в ответ идут числом `*_total`; стандартные реквизиты строк не имеют
  (их нет в индексе состава) и называются состоянием `present_not_indexed` (Q7); каталог
  ресурсов справки `Ext/Help/` не хранится — наблюдение `help_resources_dir`.

Идемпотентность держится явным `DELETE` по `configuration_uuid` (внешнего ключа на
`configurations` и каскада по нему в схеме нет осознанно — прецеденты V20.1, V44, V46, V48,
V49, V50), а не новой ревизией: повтор той же выгрузки не создаёт истории, снятые строки
названы в ответе (`removed_previous`, `removed_by_table`). Ключом цепочки состояния
версионируемых таблиц является (`configuration_uuid`, `object_name`, `revision_no`) —
позиция O9 и замер 3.2: имя вида совпадает в BGU2 и BP3 при разных uuid, а 14 uuid детей
совпадают между конфигурациями.

Снятие детей ограничено кругом вида, а не всей ногой конфигурации: таблицы `attributes`,
`tabular_sections`, `forms`, `templates` общие для внешнего контура и для выгрузки
конфигурации, и `DELETE ... WHERE configuration_uuid = …` снял бы строки детей всех
объектов конфигурации — тех, которых в схеме ещё нет, но которые появятся следующими
узлами. Поэтому предикат держится родителями круга: uuid видов из разбора и из таблицы вида
плюс uuid их табличных частей. Тот же приём держит честный счётчик снятых строк (M7):
`form_ext` имеет FK `form_ext_form_id_fkey` с `ON DELETE CASCADE`, и каскад снял бы
описания форм молча (приём `REMOVE_ORDER` узлов V49/V50).

Круг пишется одной транзакцией, и отказ разбора любого файла круга останавливает стадию ДО
записи: в базе не остаётся половины строк (приём V12/V46/V48/V49/V50). Отсутствие каталога
`ExchangePlans/` — не отказ, а ответ о выгрузке: `files_found = 0` с наблюдением
`directory_missing` (у KomMag позиции вида нет ни файлами, ни строками индекса).

После фиксации загрузчик пересобирает статистику затронутых таблиц
(`refresh_table_statistics` — мера V46): без статистики планировщик не знает о строках
собственной загрузки, и счётчики витрин текущего состояния на большой выгрузке выполняются
минутами (замер 28.10.2026 на BGU2: 8 мин 25 с против 7 мс). Отказ этой операции —
предупреждение ответа, а не отказ загрузки: строки зафиксированы.

Прогон шага: `python _scratch/_v51_p5_loader_probe.py MinCfg KomMag`, затем отдельно BGU2
и BP3 (прогоны, меняющие общее состояние БД, не параллелят). Постоянная проверка узла —
`tools/check_v51_exchange_plans.py` (шаг П6).
"""
from typing import Any, Dict, List, Optional, Sequence, Tuple

from configuration_exchange_plans import (
    COMMANDS_TABLE_NAME,
    CONTENT_TABLE_NAME,
    GROUP_ATTRIBUTES,
    GROUP_COMMANDS,
    GROUP_CONTENT,
    GROUP_EXCHANGE_PLANS,
    GROUP_FORMS,
    GROUP_SLOTS,
    GROUP_TABULAR_SECTIONS,
    GROUP_TEMPLATES,
    LOAD_GROUPS,
    OBSERVATION_DIRECTORY_MISSING,
    PARENT_TYPE_CONFIGURATION,
    TABLE_NAME,
    collect_exchange_plans,
    group_tables,
    kind_root_index_rows,
)
from configuration_load_contract import (
    EXCHANGE_PLAN_REPEAT_HINT,
    EXCHANGE_PLAN_ROW_GROUPS,
    STATUS_ERROR,
    STATUS_OK,
    exchange_plan_group_defaults,
    exchange_plans_defaults,
)
from configuration_object_properties_loader import refresh_table_statistics
from configuration_root_module_loader import configuration_uuid_from_layout
from current_revision import (
    CHANGED_BY_LOAD,
    FIRST_REVISION,
    current_view,
    stamp_revision_rows,
)
from external_db import transaction
from external_table_writer import (
    CONFIGURATION_OBJECT_WRITERS,
    ExchangePlanAttributesRowWriter,
    ExchangePlanFormsRowWriter,
    ExchangePlanTabularSectionsRowWriter,
    ExchangePlanTemplatesRowWriter,
    FormExtRowWriter,
)

OBJECTS_TABLE = "configuration_objects"

# Таблицы круга. Три таблицы вида берутся общим реестром `CONFIGURATION_OBJECT_WRITERS`,
# четыре таблицы детей — импортом классов: реестр выбирает писателя по таблице, а таблица у
# двух контуров одна (строка детей внешнего объекта и строка детей плана обмена различаются
# ногой области видимости и видом родителя), поэтому записей детей в реестре нет намеренно
# и стадия выбирает их по имени класса (приём `ConfigurationObjectModuleRowWriter` узла
# V47). `form_ext` своего писателя не имеет вовсе: ноги у таблицы нет, область видимости
# задаёт строка формы, а описания пишет общий `FormExtRowWriter`.
FORM_EXT_TABLE = "form_ext"
FORMS_TABLE = "forms"
TEMPLATES_TABLE = "templates"
ATTRIBUTES_TABLE = "attributes"
TABULAR_SECTIONS_TABLE = "tabular_sections"

TABLE_WRITERS: Dict[str, Any] = {
    TABLE_NAME: CONFIGURATION_OBJECT_WRITERS[TABLE_NAME],
    CONTENT_TABLE_NAME: CONFIGURATION_OBJECT_WRITERS[CONTENT_TABLE_NAME],
    COMMANDS_TABLE_NAME: CONFIGURATION_OBJECT_WRITERS[COMMANDS_TABLE_NAME],
    ATTRIBUTES_TABLE: ExchangePlanAttributesRowWriter,
    TABULAR_SECTIONS_TABLE: ExchangePlanTabularSectionsRowWriter,
    FORMS_TABLE: ExchangePlanFormsRowWriter,
    TEMPLATES_TABLE: ExchangePlanTemplatesRowWriter,
    FORM_EXT_TABLE: FormExtRowWriter,
}

# Таблицы детей, которых касается круг вида (в отличие от трёх таблиц вида они общие для
# двух контуров — отсюда ограниченный предикат снятия, см. `remove_exchange_plans`).
CHILD_TABLES: Tuple[str, ...] = (
    ATTRIBUTES_TABLE, TABULAR_SECTIONS_TABLE, FORMS_TABLE, TEMPLATES_TABLE,
    COMMANDS_TABLE_NAME,
)

# Порядок снятия круга — не порядок `EXCHANGE_PLAN_TABLES` и не порядок групп `kinds`:
# `form_ext` снимается первой, потому что её FK `form_ext_form_id_fkey` объявлен с
# `ON DELETE CASCADE`, и каскад по строке формы снял бы описания молча, без точного
# счётчика (M7). Строки вида — последними: на пару (uuid вида, `revision_no`) опираются
# строки перечня `<Content>`, и снятие вида раньше перечня оставило бы в базе перечень без
# строки вида хотя бы на время внутри транзакции. Тот же приём, что `REMOVE_ORDER` узлов
# V49/V50.
REMOVE_ORDER: Tuple[str, ...] = (
    FORM_EXT_TABLE, FORMS_TABLE, TEMPLATES_TABLE, ATTRIBUTES_TABLE,
    TABULAR_SECTIONS_TABLE, COMMANDS_TABLE_NAME, CONTENT_TABLE_NAME, TABLE_NAME,
)

# Колонки индекса состава, которые нужны разбору вида: `name`/`object_name` — ключ сверки
# (`ExchangePlan.<Имя>`, `ExchangePlan.<Имя>.Form.<ИмяФормы>` и т.д.), `uuid` — цель
# ссылочного типа перечня и сверка uuid файла с записью, `child_type`/`parent_name`/`depth`
# — различение записей вида, его детей и псевдозаписей слотов (замер 3.1). Фильтра по типу
# вида здесь нет намеренно: разрешение целей перечня `<Content>` обязано видеть записи
# ЛЮБОГО вида (цели ведут на справочники, документы, планы обмена), а свой круг вида
# отбирает сам разбор (`kind_index_rows`, а записей самого вида — `kind_root_index_rows`).
# Тот же приём, что `read_index_records` узлов
# V46, V48, V49, V50: источник — строки БД, а не повторный разбор `ConfigDumpInfo.xml`.
INDEX_ROW_COLUMNS: Tuple[str, ...] = (
    "name", "object_id", "object_type", "object_name", "child_type", "parent_name", "depth",
    "uuid",
)

# Ключи сводки разбора, совпадающие с ключами контракта по имени (один словарь на разбор и
# на ответ): копируются только они — неперечисленный ключ контракта читается нулём (C1), а
# незнакомый ключ разбора не попадает в ответ, которого карточка не обещала (прецедент
# `SUMMARY_KEYS` узлов V46/V48/V49/V50). Ключей строк записи (`rows`, `attributes`,
# `columns`, `content`, …) здесь нет: они идут в писатели, а не в ответ стадии;
# `success`/`warnings` разбора — внутренние признаки круга, стадия отвечает своими.
SUMMARY_KEYS: Tuple[str, ...] = (
    "directory", "files_found", "files_read", "files_failed", "observations",
    "index_only", "file_only", "uuid_mismatch",
    "counts_by_properties_state", "counts_by_children_state",
    "counts_by_standard_attributes_state", "counts_by_content_state",
    "counts_by_slot_state", "counts_by_target_resolve_state",
    "counts_by_auto_record_state", "counts_by_circle_discrepancy",
    "counts_by_child_mismatch", "counts_by_form_ext_format",
    "counts_by_template_ext_format",
    "attributes_own", "attributes_columns", "tabular_sections_total", "commands_total",
    "forms_total", "form_ext_total", "templates_total",
    "object_module_files_total", "command_module_files_total",
    "counts_by_object_module_kind", "content_total", "content_unresolved_total",
    "standard_attributes_total", "standard_attributes_distinct",
    "standard_attribute_names", "text_truncated_total",
    "ext_observations_total", "counts_by_ext_observation", "ext_observations",
    "unknown_properties", "unknown_value_properties", "unexpected_child_tags",
)


def read_index_records(cur, configuration_id: int) -> Dict[str, Any]:
    """Записи индекса состава этой конфигурации из `configuration_objects` (Н6).

    Пустой ответ означает «индекс недоступен», а не «объектов нет»: при недоступном индексе
    сверка файлов с перечнем и разрешение целей перечня `<Content>` невыразимы, и
    вызывающий обязан назвать это состоянием загрузки, а не нулями (тот же контракт, что у
    слоёв V46, V47, V48, V49, V50).

    Число записей своего вида (`ExchangePlan.<Имя>`) считается отдельно: оно сравнивается с
    числом файлов регистрации, и расхождение обязан назвать ответ стадии (замер 2.9 для
    V50 дал равенство на четырёх выгрузках, здесь — 2/18/26 по замеру П0). Считаются только
    строки вида, без детей: индекс держит детей тем же `object_type` и точечным именем
    (замер 3.1), поэтому та же нога на MinCfg даёт 28 строк против 2 планов обмена —
    сравнение с числом файлов при таком подсчёте врало бы (проба П5 поймала это на первом
    же прогоне; отбор без детей даёт `kind_root_index_rows`).
    """
    info: Dict[str, Any] = {"available": False, "row_count": 0, "kind_count": 0,
                            "reason": None}
    columns = ", ".join(INDEX_ROW_COLUMNS)
    try:
        cur.execute(
            f"SELECT {columns} FROM {OBJECTS_TABLE} WHERE configuration_id = %s",
            [int(configuration_id)],
        )
    except Exception as exc:  # noqa: BLE001 — слой обязан назвать причину, а не ноль
        info["reason"] = f"чтение {OBJECTS_TABLE} не удалось: {exc}"
        return {"rows": [], **info}
    records = [dict(zip(INDEX_ROW_COLUMNS, row)) for row in cur.fetchall()]
    if not records:
        info["reason"] = (
            f"в {OBJECTS_TABLE} нет записей для configuration_id={configuration_id}: индекс "
            "состава этого заголовка не загружен, поэтому сверка файлов с перечнем и "
            "разрешение целей перечня `<Content>` невозможны"
        )
        return {"rows": [], **info}
    info.update({
        "available": True,
        "row_count": len(records),
        "kind_count": len(kind_root_index_rows(records)),
    })
    return {"rows": records, **info}


def existing_plan_revisions(cur, configuration_uuid: str) -> Dict[str, int]:
    """Строки вида этой конфигурации, которые уже лежат в базе: uuid → высшая ревизия.

    Держит два разных факта:

    * перечень uuid нужен предикату снятия (см. `remove_exchange_plans`): детей обязан снять
      и у тех планов обмена, которых в этой выгрузке больше нет (файл удалён), но строка
      вида в базе ещё осталась — иначе снятие по uuid из разбора оставило бы детей
      удалённого вида сиротами, то есть ровно тот дефект, который узлы V44…V50 закрывают
      явным `DELETE` по ноге области видимости;
    * номер ревизии нужен строкам перечня `<Content>`, когда группа `exchange_plans` этим
      вызовом не записывается: ключ `exchange_plan_content_plan_revision_ordinal_key`
      держится пары (uuid вида, `revision_no`), и выдуманный номер повесил бы перечень на
      ревизию, которой нет (прецедент `existing_ids` узла V49 — права дописываются к
      CURRENT-ревизиям ролей).

    Высшая ревизия считается по таблице, а не по витрине текущего состояния: загрузчик
    пишет `revision_no = FIRST_REVISION` и снимает прежние строки явно, поэтому различать
    «текущую» и «историческую» ревизию здесь нечем; витрина нужна читателям, а не этому
    предикату.
    """
    try:
        cur.execute(
            f"SELECT object_uuid, MAX(revision_no) FROM {TABLE_NAME} "
            "WHERE configuration_uuid = %s::uuid GROUP BY object_uuid",
            [str(configuration_uuid)],
        )
    except Exception:  # noqa: BLE001 — пустой ответ означает «строк вида в базе нет»
        return {}
    return {str(row[0]): int(row[1] or 0) for row in cur.fetchall() if row[0]}


def existing_section_uuids(cur, parents: Sequence[str]) -> List[str]:
    """uuid табличных частей тех планов обмена, что уже лежат в базе.

    Колонки табличных частей висят на строке табличной части, а не на виде (замер 3.4 — так
    же их держит индекс состава), поэтому предикату снятия детей вида нужны ОБЕ ноги: uuid
    видов и uuid их частей. Одних видов довольно для реквизитов, форм, макетов и команд, но
    не для колонок: снятие по одним видам оставило бы колонки сиротами — проба П5 поймала
    это на снятии заголовка, где `attributes` сняла 3 строки из 4.

    Пустой перечень родителей — отсутствие строк вида в базе, а не ошибка: ответ — пустой
    список, и вызывающий снимает ровно то, что названо родителями из разбора.
    """
    scope = [str(item) for item in parents if item]
    if not scope:
        return []
    try:
        cur.execute(
            f"SELECT uuid FROM {TABULAR_SECTIONS_TABLE} "
            "WHERE parent_type = %s AND parent_uuid = ANY(%s::uuid[])",
            [PARENT_TYPE_CONFIGURATION, scope],
        )
    except Exception:  # noqa: BLE001 — строк вида в базе нет, значит нечего снимать и ниже
        return []
    return [str(row[0]) for row in cur.fetchall() if row[0]]



def remove_exchange_plans(cur, configuration_uuid: str, parents: Sequence[str],
                          tables: Tuple[str, ...] = REMOVE_ORDER) -> Dict[str, int]:
    """Снять строки круга вида этой конфигурации (внутри текущей транзакции).

    Очистка обязана быть явной: внешнего ключа на `configurations` и каскада по нему в
    схеме нет осознанно (прецеденты V20.1, V44, V46, V48, V49, V50), иначе строки пережили
    бы снятие заголовка и стали бы сиротами, которые нельзя ни показать в карточке
    конфигурации, ни отличить от строк другой конфигурации. Этим же фильтром
    (`configuration_uuid`) держится снятие в `_remove_rows` конвейера — иначе `force=True`
    оставил бы в базе прежний состав вида.

    Предикат детей ограничен кругом вида (`parent_type` + `parent_uuid = ANY(…)`), а не
    всей ногой конфигурации: таблицы `attributes`, `tabular_sections`, `forms`, `templates`
    общие для внешнего контура и для выгрузки конфигурации, и `DELETE` только по ноге снял бы
    строки детей всех объектов конфигурации — тех, которых в схеме ещё нет, но которые
    появятся следующими узлами. `form_ext` ноги не имеет вовсе (область видимости задаёт
    строка формы), поэтому она снимается по тем же родителям.
    """
    removed: Dict[str, int] = {}
    scope = [str(item) for item in parents if item]
    for table in tables:
        if table == TABLE_NAME:
            cur.execute(f"DELETE FROM {table} WHERE configuration_uuid = %s::uuid",
                        [str(configuration_uuid)])
        elif table == CONTENT_TABLE_NAME:
            cur.execute(
                f"DELETE FROM {table} WHERE configuration_uuid = %s::uuid "
                "AND exchange_plan_object_uuid = ANY(%s::uuid[])",
                [str(configuration_uuid), scope],
            )
        elif table == FORM_EXT_TABLE:
            cur.execute(
                f"DELETE FROM {table} WHERE parent_type = %s "
                "AND parent_uuid = ANY(%s::uuid[])",
                [PARENT_TYPE_CONFIGURATION, scope],
            )
        else:
            cur.execute(
                f"DELETE FROM {table} WHERE configuration_uuid = %s::uuid "
                "AND parent_type = %s AND parent_uuid = ANY(%s::uuid[])",
                [str(configuration_uuid), PARENT_TYPE_CONFIGURATION, scope],
            )
        removed[table] = cur.rowcount
    return removed


# ---------------------------------------------------------------------------
# Круг детей вида для сторонних проверок (узел V52, наблюдение П8)
# ---------------------------------------------------------------------------
# Общая часть предиката, по которой строки детей относятся к кругу вида. Таблицы
# `attributes`, `tabular_sections`, `forms`, `form_ext`, `templates`, `commands` пишут и
# другие узлы: внешние объекты (V13/V14), модули (V47) и критерии отбора (V52). Поэтому
# подсчёт по одной ноге `configuration_uuid` не различает виды — строки детей ЧУЖИХ видов
# читались бы как круг стадии S4f (замер узла V52 на MinCfg: в `commands` появилась строка
# команды критерия отбора, и пробы `_v48_p8_stop_probe.py`, `_v49_p8_stop_probe.py`,
# `_v50_p8_stop_probe.py`, `_v51_p8_stop_probe.py` сообщили бы, что круг стадии S4f снят не
# полностью, хотя стадия S4f ни снимала, ни писала эти строки).
#
# Проверка обязана мерить ровно тот же круг, что и снятие (`remove_exchange_plans`), поэтому
# условие живёт рядом со снятием, а не в четырёх пробах. Родители берутся из витрины
# текущего состояния таблицы вида: у строк вида есть цепь ревизий, и подсчёт по самой таблице
# посчитал бы детей удалённой ревизии. Имя витрины даёт `current_view` — второго написания
# имён в проекте нет.
SHARED_CHILD_TABLES = (ATTRIBUTES_TABLE, TABULAR_SECTIONS_TABLE, FORMS_TABLE,
                      FORM_EXT_TABLE, TEMPLATES_TABLE, COMMANDS_TABLE_NAME)


def count_circle_child_rows(cur, configuration_uuid: str, table: str,
                            other_configurations: bool = False) -> int:
    """Сколько строк общей таблицы детей относится к кругу вида «план обмена».

    `other_configurations=False` — круг своей конфигурации (нога `configuration_uuid` плюс
    родители круга вида). `other_configurations=True` — дети ЧУЖИХ конфигураций,
    неприкосновенность чужого круга: родителем считается план ТОЙ ЖЕ конфигурации, к которой
    принадлежит строка ребёнка. Связывать родителя с uuid прогона нельзя: предикат
    `configuration_uuid <> %s` вместе с `plans.configuration_uuid = %s` дал бы пустой ответ
    при любом состоянии базы, и сравнение «до/после» перестало бы что-либо доказывать.

    `form_ext` ноги `configuration_uuid` не имеет (область видимости задаёт строка формы —
    наблюдение П6 узла V51), поэтому она считается связкой по `forms`. Вид родителя и имя
    таблицы вида — единственные источники этих имён; для таблиц, не общих с другими узлами,
    ответ даёт обычный подсчёт по ноге конфигурации.
    """
    if table in (TABLE_NAME, CONTENT_TABLE_NAME):
        if other_configurations:
            sql = (f"SELECT count(*) FROM {table} WHERE configuration_uuid IS NOT NULL "
                   "AND configuration_uuid <> %s::uuid")
            params = [str(configuration_uuid)]
        else:
            sql = f"SELECT count(*) FROM {table} WHERE configuration_uuid = %s::uuid"
            params = [str(configuration_uuid)]
        cur.execute(sql, params)
        return int(cur.fetchone()[0] or 0)

    if table not in SHARED_CHILD_TABLES:
        raise ValueError(
            f"таблица {table!r} не входит в круг детей вида {TABLE_NAME!r}: "
            f"перечень общий с снятием — {', '.join(SHARED_CHILD_TABLES)}"
        )

    view = current_view(TABLE_NAME)
    if table == FORM_EXT_TABLE:
        from_sql = f"FROM {FORM_EXT_TABLE} fe JOIN {FORMS_TABLE} f ON f.id = fe.form_id"
        alias = "f"
    else:
        from_sql = f"FROM {table}"
        alias = table
    if other_configurations:
        where = (
            f"{alias}.configuration_uuid IS NOT NULL "
            f"AND {alias}.configuration_uuid <> %s::uuid "
            f"AND {alias}.parent_type = %s AND {alias}.parent_uuid IN "
            f"(SELECT object_uuid FROM {view} ep "
            f"WHERE ep.configuration_uuid = {alias}.configuration_uuid)"
        )
        params = [str(configuration_uuid), PARENT_TYPE_CONFIGURATION]
    else:
        where = (
            f"{alias}.configuration_uuid = %s::uuid AND "
            f"{alias}.parent_type = %s AND {alias}.parent_uuid IN "
            f"(SELECT object_uuid FROM {view} WHERE configuration_uuid = %s::uuid)"
        )
        params = [str(configuration_uuid), PARENT_TYPE_CONFIGURATION,
                  str(configuration_uuid)]
    cur.execute(f"SELECT count(*) {from_sql} WHERE {where}", params)
    return int(cur.fetchone()[0] or 0)


def _require_header(configuration_uuid: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Найти строку заголовка по uuid; вернуть карточку или причину отказа.

    Заголовок обязателен: свойства вида — второй шаг того же первого слоя, и строки без
    заголовка нельзя ни показать в карточке конфигурации, ни снять вместе с ней (внешний
    ключ в схеме не поставлен осознанно — V20.1). Ленивый импорт — тот же обход цикла, что
    у слоёв V44/V46/V48/V49/V50.
    """
    from configuration_loader import find_configuration  # ленивый импорт — круг узла V44

    card = find_configuration(configuration_uuid)
    if isinstance(card, dict) and card.get("error"):
        return None, f"Ошибка запроса: {card['error']}"
    if not card:
        return None, (
            f"Строка заголовка конфигурации с uuid {configuration_uuid} в базе не найдена. "
            "Сначала загрузите каталог точкой входа load_1c_catalog_tool(source_path=…): "
            "иначе свойства планов обмена остались бы ни на что не указывающими, а внешний "
            "ключ в схеме не поставлен осознанно (узел V20.1)."
        )
    return card, None


def _stage_failure(reason: str, header: Optional[Dict] = None,
                   status: str = STATUS_ERROR,
                   extra: Optional[List[str]] = None) -> Dict[str, Any]:
    """Отказ стадии в форме закрытого контракта (C1, C3).

    Причина кладётся в ключ `error` замкнутого словаря `exchange_plans_defaults()`, а статус
    — в `status`: вызывающий отличает «стадия не выполнялась» от «слой отказал» (C2). Если
    заголовок к моменту отказа уже разрешён, он называется: по `configuration_id` карточка
    отличает «заголовка нет» от «заголовок есть, слой отказал по файлам». Подсказка о том,
    чем продолжить, кладётся и в отказ, и в успех: у стадии есть отдельный вход
    `load_exchange_plans_tool` (шаг П5), и вызывающий обязан знать это из ответа, а не из
    молчания (прецедент `*_REPEAT_HINT` узлов V48–V50).
    """
    result = exchange_plans_defaults()
    result["status"] = status
    result["error"] = reason
    result["reason"] = reason
    if header:
        result["configuration_id"] = header.get("id")
        result["configuration_uuid"] = header.get("uuid")
        result["configuration_name"] = header.get("name")
    result["warnings"].append(EXCHANGE_PLAN_REPEAT_HINT)
    for warning in extra or []:
        result["warnings"].append(warning)
    return result


def normalize_kinds(kinds) -> Tuple[Tuple[str, ...], Optional[str]]:
    """Разобрать запрос групп круга S4f в замкнутом словаре `LOAD_GROUPS` (Q5).

    `None` — весь круг, то есть ровно то, что делает стадия конвейера: два входа
    (конвейер и отдельный инструмент) не должны расходиться значением по умолчанию
    (прецедент `normalize_kinds` узлов V46/V49).

    Каждая граница запроса называется текстом отказа, а не молчаливой деградацией:

    * неизвестная группа — с перечнем допустимых: «такой группы нет» и «группу не просили»
      — разные ответы, и второй нельзя получать из первого;
    * пустой список — отказ: вызов, который ничего не пишет, неотличим от вызова, который
      ничего не нашёл (C2);
    * `exchange_plans` без `slots` и `slots` без `exchange_plans` — отказ: слоты
      `Help`/`AdditionalIndexes` лежат колонками строки вида, а CHECK
      `exchange_plans_slot_content_matches_state` требует называть состояние слота на каждой
      строке; состояния «слоты не загружались» в замкнутом словаре нет, и его нечем было бы
      отличить от `absent` (Q5, п. 3).

    Остальные группы разрешены по отдельности: перечни детей строятся из атрибутов `uuid`
    выгрузки, а не из записанных строк детей (Q5, п. 2), поэтому запись детей к уже лежащим
    в базе строкам вида — не состав, которого в выгрузке нет. Отказом это становится только
    тогда, когда строк вида в базе нет (проверка `existing_plan_revisions` в теле стадии).
    """
    if kinds is None:
        return LOAD_GROUPS, None
    # Строка разбирается по запятым здесь, а не в инструменте: разбор групп один на слой,
    # поэтому стадия конвейера и отдельный вход не могут разойтись в том, как понимать
    # `kinds="forms,templates"` (прецедент `normalize_kinds` узлов V46/V49, где разбор
    # строки держит слой).
    items = ([part for part in kinds.split(",")] if isinstance(kinds, str)
             else list(kinds))
    wanted = set()
    unknown: List[str] = []
    for item in items:
        name = str(item or "").strip()
        if not name:
            continue
        if name in LOAD_GROUPS:
            wanted.add(name)
        else:
            unknown.append(name)
    if unknown:
        return (), ("Запрошены группы круга планов обмена, которых нет: "
                    + ", ".join(sorted(unknown)) + ". Реализованы: "
                    + ", ".join(LOAD_GROUPS)
                    + " (и весь круг без параметра kinds).")
    if not wanted:
        return (), ("Пустой kinds: не запрошена ни одна группа круга. Укажите хотя бы одну "
                    "из " + ", ".join(LOAD_GROUPS) + " или уберите kinds, чтобы записать "
                    "весь круг.")
    asked = [group for group in EXCHANGE_PLAN_ROW_GROUPS if group in wanted]
    if asked and len(asked) < len(EXCHANGE_PLAN_ROW_GROUPS):
        missing = [group for group in EXCHANGE_PLAN_ROW_GROUPS if group not in wanted]
        return (), (f"Группы {', '.join(asked)} и {', '.join(missing)} образуют одну строку "
                    "вида: слоты `Help`/`AdditionalIndexes` лежат её колонками, а CHECK "
                    "`exchange_plans_slot_content_matches_state` согласует состояние слота с "
                    "наличием тела на каждой строке. Состояния «слоты не загружались» в "
                    "замкнутом словаре нет, поэтому половина строки читалась бы состоянием "
                    "`absent` (Q5, п. 3).")
    return tuple(group for group in LOAD_GROUPS if group in wanted), None


def load_exchange_plans(source_path: str,
                        configuration_uuid: Optional[str] = None,
                        kinds=None,
                        changed_at=None) -> Dict[str, Any]:
    """Загрузить свойства планов обмена конфигурации (узел V51, стадия S4f).

    Порядок: каталог → uuid из `Configuration.xml` (или сверка переданного) → проверка, что
    заголовок загружен → разбор запроса групп `kinds` → индекс состава из
    `configuration_objects` (сверка файлов с перечнем и разрешение целей перечня, Н6) →
    разбор каталога вида → **одна транзакция**: `DELETE` круга + вставки таблиц →
    отдельной транзакцией `ANALYZE` затронутых таблиц (мера V46).

    Порядок записи держится иерархией данных, а не удобством: строки вида → строки детей
    (`attributes` с колонками табличных частей, `tabular_sections`, `forms`, `templates`,
    `commands`) → `form_ext` (ссылка на числовой `form_id` строки формы) → строки перечня
    `<Content>` (ссылка на пару uuid+ревизия строки вида). Всё это одной транзакцией:
    отказ на середине оставил бы в базе состав, которого в выгрузке нет.

    Подкаталоги `Forms/`, `Templates/`, `Commands/` читаются только когда запрошены группы
    `forms` или `templates` (цена — 877 КБ содержимого форм и 33.2 МБ текстов макетов по
    замеру 5.3): при `kinds=exchange_plans,slots,attributes,…` разбор строится по файлу
    регистрации, а расхождение объявления вида с его каталогом называется состоянием
    `not_checked`, а не молчит (контракт `read_object_file`).

    `changed_at` передаёт конвейер: строки одной загрузки обязаны нести одну метку (M2), а не
    время своей транзакции. Пустое значение — своя метка вызова (одиночный прогон слоя).
    Строки `form_ext` и `<Content>` своей цепи ревизий не имеют: их текущность читается
    связкой по строке формы и по паре (uuid вида, `revision_no`) соответственно.
    """
    uuid_info = configuration_uuid_from_layout(source_path)
    if "uuid" not in uuid_info:
        return _stage_failure(uuid_info.get("error")
                             or f"Каталог выгрузки не читается: {source_path}")
    layout_uuid = str(uuid_info["uuid"])
    if configuration_uuid and str(configuration_uuid).strip().lower() != layout_uuid.lower():
        # Два источника одного факта указали на разные конфигурации: молча выбрать один —
        # значит записать свойства чужой конфигурации (тот же отказ, что у слоёв
        # V44/V46/V48/V49/V50).
        return _stage_failure(
            f"Передан configuration_uuid={configuration_uuid}, а каталог {source_path} "
            f"описывает конфигурацию с uuid={layout_uuid}. Загрузка не выполнена: укажите "
            "путь каталога этой конфигурации или уберите configuration_uuid."
        )
    configuration_uuid = layout_uuid

    header, reason = _require_header(configuration_uuid)
    if header is None:
        return _stage_failure(reason)

    wanted_kinds, kinds_error = normalize_kinds(kinds)
    if kinds_error:
        # Граница запроса называется до чтения выгрузки: «такой группы нет» и «группу не
        # просили» — разные состояния, и второй не выводится из первого (прецедент V49).
        return _stage_failure(kinds_error, header=header)

    warnings: List[str] = []
    index_info: Dict[str, Any] = {"available": False, "row_count": 0, "kind_count": 0,
                                  "reason": None}
    existing: Dict[str, int] = {}
    existing_sections: List[str] = []
    try:
        with transaction() as cur:
            index_info = read_index_records(cur, int(header["id"]))
            existing = existing_plan_revisions(cur, configuration_uuid)
            existing_sections = existing_section_uuids(cur, sorted(existing))
    except Exception as exc:  # noqa: BLE001 — индекс читается до записи, отказ называется им
        index_info["reason"] = f"чтение {OBJECTS_TABLE} не удалось: {exc}"

    # Цена круга несимметрична (Q5, раздел 5.4): 46 строк свойств против 22 515 строк
    # перечня и 33.2 МБ текстов. Содержимое подкаталогов читается ровно тогда, когда его
    # просят; иначе разбор строится по файлу регистрации, и это называется состоянием
    # `not_checked`, а не пустым перечнем детей.
    read_subdirs = (GROUP_FORMS in wanted_kinds) or (GROUP_TEMPLATES in wanted_kinds)
    collected = collect_exchange_plans(source_path, index_rows=index_info["rows"],
                                      with_subdirs=read_subdirs)
    if not collected["success"]:
        failures = collected.get("files_failed") or []
        detail = "; ".join(f"{item.get('source_path')}: {item.get('reason')}"
                           for item in failures[:10])
        return _stage_failure(
            f"Круг не записан: {len(failures)} файл(ов) каталога "
            f"{collected.get('directory')} не разобраны — {detail}. Ни одной строки круга "
            "в базу не записано: половина круга читалась бы как полный состав вида (приём "
            "V12/V46), прежние строки этой конфигурации не сняты",
            header=header,
        )

    # ── строки круга ───────────────────────────────────────────────────────────────
    plan_rows = list(collected.get("rows") or [])
    tabular_rows = list(collected.get("tabular_sections") or [])
    # Реквизиты вида и колонки его табличных частей пишутся одной таблицей `attributes`, но
    # `parent_uuid` колонки равен uuid табличной части, а не вида (замер 3.4: индекс состава
    # держит колонку под точечным именем табличной части) — разбор это и сохраняет.
    attribute_rows = (list(collected.get("attributes") or [])
                      + list(collected.get("columns") or []))
    form_rows = list(collected.get("forms") or [])
    form_ext_rows = list(collected.get("form_ext") or [])
    template_rows = list(collected.get("templates") or [])
    command_rows = list(collected.get("commands") or [])
    content_rows = list(collected.get("content") or [])

    write_plan = GROUP_EXCHANGE_PLANS in wanted_kinds
    write_attributes = GROUP_ATTRIBUTES in wanted_kinds
    write_sections = GROUP_TABULAR_SECTIONS in wanted_kinds
    write_forms = GROUP_FORMS in wanted_kinds
    write_templates = GROUP_TEMPLATES in wanted_kinds
    write_commands = GROUP_COMMANDS in wanted_kinds
    write_content = GROUP_CONTENT in wanted_kinds

    # Таблицы этого вызова — объединение таблиц запрошенных групп (`group_tables` разбора,
    # второго перечня таблиц в проекте нет), приведённое к порядку `REMOVE_ORDER`: он же
    # держит порядок снятия и перечень таблиц для `ANALYZE`. Незапрошенные группы в этот
    # список не попадают и обязаны быть названы ответом (правило V49).
    requested_tables = set()
    for kind in wanted_kinds:
        requested_tables.update(group_tables(kind))
    touched_tables = [table for table in REMOVE_ORDER if table in requested_tables]

    # Родители круга для предиката снятия: uuid видов из разбора, uuid их табличных частей
    # (колонки висят на табличной части), uuid строк вида, которые ещё лежат в базе, и uuid
    # табличных частей ЭТИХ строк. Третья нога нужна затем, чтобы снять детей вида, файла
    # которого в этой выгрузке уже нет (см. `existing_plan_revisions`), а четвёртая — чтобы
    # к таким детям попали и колонки их табличных частей: без неё снятие затронуло бы
    # реквизиты, формы, макеты и команды удалённого вида, но не его колонки
    # (`existing_section_uuids`; проба П5 поймала это на снятии заголовка).
    parents = sorted({str(row.get("object_uuid")) for row in plan_rows
                      if row.get("object_uuid")}
                     | {str(row.get("uuid")) for row in tabular_rows if row.get("uuid")}
                     | set(existing)
                     | set(existing_sections))

    # Строки перечня `<Content>` ссылаются на пару (uuid вида, `revision_no`), а разбор
    # называет цель строкой `<Content>` и индексное имя вида. uuid вида берётся из строк
    # этого же разбора: перечень читается из файла вида, поэтому карта полна при любом
    # значении `kinds` (разбор круга полный — Q5, п. 3).
    plan_uuid_by_full_name = {str(row.get("full_name")): str(row.get("object_uuid"))
                              for row in plan_rows
                              if row.get("object_uuid") and row.get("full_name")}
    for row in content_rows:
        plan_uuid = plan_uuid_by_full_name.get(str(row.get("exchange_plan_full_name") or ""))
        if plan_uuid:
            row["exchange_plan_object_uuid"] = plan_uuid
    if write_content and not write_plan:
        # Перечень дописывается к строкам вида, которые уже лежат в базе (прецедент
        # `role_rights` без `roles` узла V49): ревизия берётся у них, а не выдумывается.
        # Строки вида, которой в базе нет, — это состояние базы, а не ошибка запроса, и
        # называется оно отказом с перечнем, а не вставкой вникуда.
        orphans = sorted({str(row.get("exchange_plan_full_name") or "<без имени>")
                          for row in content_rows
                          if not existing.get(str(row.get("exchange_plan_object_uuid") or ""))})
        if orphans:
            return _stage_failure(
                "Группа `content` запрошена без группы `exchange_plans`, но строк вида для "
                f"{len(orphans)} плана (ов) в базе нет: {', '.join(orphans[:10])}. Перечень "
                "`<Content>` держится пары (uuid вида, `revision_no`), и вставить его на "
                "ревизии, которой нет, — значит записать состав, которого в выгрузке нет. "
                "Запишите группу `exchange_plans` (или весь круг без kinds).",
                header=header,
            )

    # Ключ конфигурации знает вызывающий, а не XML объекта — тот же порядок, что у писателей
    # свойств V46, модулей корня V44, параметров сеанса V48, ролей V49 и общих реквизитов
    # V50. Строки незапрошенных групп ни ключом не помечаются, ни ревизией не штампуются:
    # этот вызов их не касается. `form_ext` ключа не имеет вовсе: её область видимости
    # задаёт строка формы.
    for rows, writing in ((plan_rows, write_plan), (tabular_rows, write_sections),
                          (attribute_rows, write_attributes), (form_rows, write_forms),
                          (template_rows, write_templates), (command_rows, write_commands),
                          (content_rows, write_content)):
        if not writing:
            continue
        for row in rows:
            row["configuration_uuid"] = configuration_uuid

    # Один штамп времени на всё событие загрузки (M2): записываемые таблицы одной загрузки
    # не должны нести разные метки, иначе их нельзя прочитать как один состав. Метку
    # определяет первая штампуемая таблица и передаётся остальным. Строки `form_ext`
    # штампуются тем же номером ревизии, что и строки форм: описание формы относится к её
    # ревизии (`uq_form_ext_form_id_revision`), своей цепи у него нет (прецедент V19).
    moment = changed_at
    for rows, writing in ((plan_rows, write_plan), (tabular_rows, write_sections),
                          (attribute_rows, write_attributes), (form_rows, write_forms),
                          (template_rows, write_templates), (command_rows, write_commands),
                          (content_rows, write_content)):
        if writing:
            moment = stamp_revision_rows(rows, revision_no=FIRST_REVISION,
                                         changed_by=CHANGED_BY_LOAD, changed_at=moment)
    if write_forms:
        moment = stamp_revision_rows(form_ext_rows, revision_no=FIRST_REVISION,
                                     changed_by=CHANGED_BY_LOAD, changed_at=moment)
    if write_content and not write_plan:
        # Ревизия перечня — ревизия уже лежащей в базе строки вида, а не `FIRST_REVISION`
        # (см. `existing_plan_revisions`).
        for row in content_rows:
            row["revision_no"] = int(existing.get(
                str(row.get("exchange_plan_object_uuid") or ""), FIRST_REVISION)
                or FIRST_REVISION)

    # ── одна транзакция: снятие круга + вставки ────────────────────────────────────
    # Снимаются только таблицы запроса, и порядок остаётся `REMOVE_ORDER` (описания форм
    # раньше строк форм, строки вида — последней), а не порядком групп запроса: каскад не
    # должен снять строку молча (M7).
    removed: Dict[str, int] = {}
    written: Dict[str, int] = {table: 0 for table in touched_tables}
    remove_targets = tuple(table for table in REMOVE_ORDER if table in touched_tables)
    try:
        with transaction() as cur:
            removed = remove_exchange_plans(cur, configuration_uuid, parents, remove_targets)
            if write_plan:
                # Строки вида пишутся пакетом: ссылка перечня `<Content>` держится пары
                # (uuid вида, `revision_no`), а не числовым id, внешнего ключа на
                # `exchange_plans(id)` в схеме нет ни у одной таблицы (зонд шага П5).
                written[TABLE_NAME] = TABLE_WRITERS[TABLE_NAME].insert_many(cur, plan_rows)
            if write_sections:
                written[TABULAR_SECTIONS_TABLE] = TABLE_WRITERS[
                    TABULAR_SECTIONS_TABLE].insert_many(cur, tabular_rows)
            if write_attributes:
                written[ATTRIBUTES_TABLE] = TABLE_WRITERS[
                    ATTRIBUTES_TABLE].insert_many(cur, attribute_rows)
            if write_commands:
                written[COMMANDS_TABLE_NAME] = TABLE_WRITERS[
                    COMMANDS_TABLE_NAME].insert_many(cur, command_rows)
            if write_templates:
                written[TEMPLATES_TABLE] = TABLE_WRITERS[
                    TEMPLATES_TABLE].insert_many(cur, template_rows)
            if write_forms:
                # Формы — по одной строке с `RETURNING id`: описание формы ссылается на
                # ЧИСЛОВОЙ `form_id` (`uq_form_ext_form_id_revision`), а `insert_many` id не
                # возвращает (тот же приём, что `FormsRowWriter.insert_ids` внешнего контура
                # узла V13 и `insert_ids` строк ролей узла V49). Связь держится uuid формы, а
                # не порядком списка: описание и строка регистрации приходят из разных файлов.
                form_ids = TABLE_WRITERS[FORMS_TABLE].insert_ids(cur, form_rows)
                ids_by_uuid = {str(row.get("uuid")): record_id
                               for row, record_id in zip(form_rows, form_ids) if record_id}
                without_id = [str(row.get("name") or row.get("form_uuid"))
                              for row in form_ext_rows
                              if ids_by_uuid.get(str(row.get("form_uuid"))) is None]
                if without_id:
                    # `form_ext.form_id` объявлен NOT NULL: молча вставить строку с пустой
                    # ссылкой значило бы получить отказ NOT NULL вместо ответа о том, какое
                    # описание осталось без строки формы (прецедент «сирот» узла V49).
                    raise ValueError(
                        "описания форм остались без строки формы: "
                        + ", ".join(without_id[:10]))
                for row in form_ext_rows:
                    row["form_id"] = ids_by_uuid.get(str(row.get("form_uuid")))
                written[FORMS_TABLE] = len(ids_by_uuid)
                written[FORM_EXT_TABLE] = TABLE_WRITERS[FORM_EXT_TABLE].insert_many(
                    cur, form_ext_rows)
            if write_content:
                # Самая большая таблица узла (22 515 строк на три выгрузки): писатель держит
                # свою страницу вставки `PAGE_SIZE = 200`, вызывающий отдаёт весь список.
                written[CONTENT_TABLE_NAME] = TABLE_WRITERS[
                    CONTENT_TABLE_NAME].insert_many(cur, content_rows)
    except Exception as exc:  # noqa: BLE001 — заголовок уже разрешён, отказ называется им
        return _stage_failure(
            f"Ошибка записи: {exc}. Транзакция отменена целиком: в базе остались прежние "
            f"строки круга (снятые этим вызовом — {sum(removed.values())}), новых нет",
            header=header,
        )

    # ── статистика записанных таблиц (мера V46) ────────────────────────────────────
    # Отдельная транзакция ПОСЛЕ фиксации записи: планировщик обязан увидеть строки, иначе
    # первый же читатель витрин текущего состояния платит минутами за счётчик (замер V46 на
    # BGU2: 8 мин 25 с против 7 мс после ANALYZE). Отказ статистики отказом загрузки не
    # является: строки зафиксированы, и состояние ответа от него не меняется. Незатронутые
    # таблицы не анализируются: их статистика уже соответствует их строкам.
    statistics_refreshed = 0
    try:
        with transaction() as cur:
            refresh_table_statistics(cur, touched_tables)
            statistics_refreshed = len(touched_tables)
    except Exception as exc:  # noqa: BLE001 — ответ описывает запись, а не статистику
        warnings.append(
            f"статистика таблиц {', '.join(touched_tables)} не обновлена: {exc}. Строки "
            "записаны, но читатель витрин текущего состояния получит план по пустой "
            "статистике: счётчики на большой выгрузке выполняются минутами вместо "
            "миллисекунд"
        )

    # ── ответ стадии: закрытый контракт + сводка круга ──────────────────────────────
    kinds_state = {
        kind: {
            "requested": True,
            "written": int(sum(written.get(table) or 0 for table in group_tables(kind))),
            "removed_previous": int(sum(removed.get(table) or 0
                                       for table in group_tables(kind))),
        }
        for kind in wanted_kinds
    }
    result = exchange_plans_defaults()
    result.update({
        "status": STATUS_OK,
        "success": True,
        "configuration_id": header["id"],
        "configuration_uuid": configuration_uuid,
        "configuration_name": header.get("name"),
        "kinds_requested": list(wanted_kinds),
        "kinds": kinds_state,
        "rows_written": int(sum(written.values())),
        "written_by_table": written,
        "exchange_plans_written": int(written.get(TABLE_NAME) or 0),
        "attributes_written": int(written.get(ATTRIBUTES_TABLE) or 0),
        "tabular_sections_written": int(written.get(TABULAR_SECTIONS_TABLE) or 0),
        "forms_written": int(written.get(FORMS_TABLE) or 0),
        "form_ext_written": int(written.get(FORM_EXT_TABLE) or 0),
        "templates_written": int(written.get(TEMPLATES_TABLE) or 0),
        "commands_written": int(written.get(COMMANDS_TABLE_NAME) or 0),
        "content_written": int(written.get(CONTENT_TABLE_NAME) or 0),
        "removed_previous": int(sum(removed.values())),
        "removed_by_table": removed,
        "index_available": bool(index_info["available"]),
        "index_kind_records": int(index_info["kind_count"]),
        "statistics_refreshed": statistics_refreshed,
    })
    for key in SUMMARY_KEYS:
        if key in collected:
            result[key] = collected[key]
    warnings.extend(collected.get("warnings") or [])

    if not index_info["available"] and index_info.get("reason"):
        warnings.append(
            f"Индекс состава: {index_info['reason']} — состояния `index_only` и `file_only` "
            "при этом невыразимы, а цели перечня `<Content>` остаются неразрешёнными "
            "записями (Q4): «объекта нет в перечне» от «перечень этой конфигурации не "
            "загружен» не отличить"
        )
    for observation, detail in (collected.get("observations") or []):
        if observation == OBSERVATION_DIRECTORY_MISSING:
            warnings.append(
                f"Каталог {collected.get('directory')}/ в выгрузке отсутствует — планов "
                "обмена у этой конфигурации нет, и нули таблиц являются ответом о выгрузке, "
                "а не отказом стадии (KomMag даёт именно это: позиции вида нет ни файлами, "
                "ни строками индекса)"
            )
    if not read_subdirs:
        warnings.append(
            "Группы `forms` и `templates` не запрашивались — подкаталоги `Forms/`, "
            "`Templates/`, `Commands/` не читались: перечень форм и макетов построен по "
            "объявлениям `<ChildObjects>` файла вида, а расхождение объявления с каталогом "
            "называется состоянием `not_checked`, а не пустым перечнем (цена круга — 877 КБ "
            "содержимого форм и 33.2 МБ текстов макетов по замеру 5.3)"
        )
    if len(wanted_kinds) < len(LOAD_GROUPS):
        untouched = sorted({table for kind in LOAD_GROUPS if kind not in wanted_kinds
                            for table in group_tables(kind)} - set(touched_tables))
        warnings.append(
            "Запрошены не все группы круга (kinds=" + ",".join(wanted_kinds) + "): таблицы "
            + ", ".join(untouched) + " этим вызовом не снимались и не записывались — их "
            "строки остались прежними, и нули `written_by_table` для этих таблиц означают "
            "именно это, а не отсутствие планов обмена или их детей в конфигурации "
            "(правило V49)")
    if any(removed.values()):
        warnings.append(
            "Прежние строки свойств планов обмена этой конфигурации сняты перед записью: "
            + ", ".join(f"{table}={count}" for table, count in sorted(removed.items())
                        if count)
            + ". Идемпотентность держится явным DELETE по configuration_uuid и по родителям "
              "круга: внешнего ключа и каскада по конфигурации в схеме нет осознанно "
              "(прецедент V20.1), а снятие детей только по ноге области видимости сняло бы "
              "строки детей всех объектов конфигурации; новая ревизия на повторную загрузку "
              "той же выгрузки не заводится — история состояний принадлежит узлу правки "
              "объекта, которого в схеме ещё нет")
    if int(result.get("object_module_files_total") or 0) or int(
            result.get("command_module_files_total") or 0):
        warnings.append(
            "Файлы модулей вида названы дескрипторами (путь, размер, род), их тела в "
            f"`bsl_modules` этим узлом не пишутся: строки с parent_type="
            f"'{PARENT_TYPE_CONFIGURATION}' по планам обмена пишет узел V47 (Q8) — "
            f"объектов/менеджера {int(result.get('object_module_files_total') or 0)}, "
            f"команд {int(result.get('command_module_files_total') or 0)}"
        )
    if int(result.get("standard_attributes_total") or 0):
        warnings.append(
            f"Блок `StandardAttributes` найден в "
            f"{int(result.get('standard_attributes_total') or 0)} вхождениях "
            f"({int(result.get('standard_attributes_distinct') or 0)} уникальных имён): "
            "строк по стандартным реквизитам в схеме нет, потому что их нет в индексе "
            "состава, — наличие называется состоянием `present_not_indexed` (Q7), а не "
            "потерей содержимого"
        )
    help_resources = int((result.get("counts_by_ext_observation") or {}).get(
        "help_resources_dir") or 0)
    if help_resources:
        warnings.append(
            f"Каталог ресурсов справки `Ext/Help/` найден в {help_resources} планах: "
            "содержимое справки узлом НЕ хранится — колонок под него в схеме нет, а слотом "
            "является только `Help.xml` (Q4); называется наблюдением `help_resources_dir`, "
            "потому что «ресурсов нет» и «ресурсы не трогали» — разные ответы"
        )
    if int(result.get("text_truncated_total") or 0):
        warnings.append(
            f"{int(result.get('text_truncated_total') or 0)} текстов (содержимое форм и "
            "макетов) усечены порогом слоя V14 `MAX_TEXT_CHARS`: полное значение называют "
            "`ext_size` и `ext_path`, состояние — `ext_truncated` (прецедент внешнего "
            "контура: узел вида порог не переопределяет)"
        )
    if plan_rows:
        warnings.append(
            f"Момент загрузки строк круга — {moment}: той же меткой помечены строки "
            "заголовка и других стадий этого события (M2); строки `form_ext` и `<Content>` "
            "своей цепи ревизий не имеют — их текущность читается связкой по строке формы "
            "и по паре (uuid вида, revision_no)"
        )
    else:
        warnings.append(
            "Строк вида этим вызовом не записано: каталог вида пуст или отсутствует "
            f"(файлов {result.get('files_found')}), поэтому и общего момента загрузки вида у "
            "этого события нет — нули таблиц являются ответом о выгрузке (Q9)"
        )
    warnings.append(EXCHANGE_PLAN_REPEAT_HINT)
    result["warnings"] = warnings
    return result











