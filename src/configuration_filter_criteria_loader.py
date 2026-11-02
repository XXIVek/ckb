#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Загрузчик свойств критериев отбора (узел V52, шаг П4, 01.11.2026).

Стадия S4g конвейера первого слоя: файлы вида `FilterCriteria` (позиция 2.7 нормативного
списка плана `docs/CONFIGURATION_FILTER_CRITERIA_PLAN.md`) в две таблицы вида —
`filter_criteria` (строка критерия) и `filter_criterion_content` (строки его перечня
`<Content>`) — и в детей вида существующими таблицами `forms`, `form_ext`, `commands`.
Норматив — тот же план (решения Q1–Q8, правила C1–C3); разбор файлов вида — отдельный
модуль `src/configuration_filter_criteria.py` (шаг П3), писатели строк — реестр
`CONFIGURATION_OBJECT_WRITERS` (шаг П4 этого же узла).

Почему стадия отдельная, а не восьмой вид S4 и не расширение S4f (прецеденты Q5 узлов
V48–V51): правило C3 требует своего ключа ответа `filter_criteria`; порядок `STAGES`
повторяет порядок нормативного списка (2.7 идёт сразу за 2.6), поэтому S4g встанет между
S4f и S4b шагом П5. Круг стадии S4 (`CHILD_TABLES` контракта) отделён от круга версионности
этим же шагом (`FILTER_CRITERIA_TABLES` в `FOREIGN_STAGE_TABLES`): регистрация таблицы вида
в `CONFIGURATION_VERSIONED_TABLES` молча добавила бы её к чужой стадии.

Почему стадия является одновременно слоем (прецеденты V44/V46/V48/V49/V50/V51):

* ключ строки — `configuration_uuid`, а не `id` заголовка: `force=True` меняет id, uuid
  остаётся прежним;
* стадия вызывается ПОСЛЕ коммита транзакции заголовка: `transaction()` каждый раз
  открывает новое соединение, и в собственной транзакции заголовка слой не увидел бы ни
  строки заголовка, ни строк индекса состава, по которым разрешаются цели перечня
  `<Content>` (Q4) и по которым сверяются файл регистрации и дети вида (Q5, Q7);
* отдельный MCP-инструмент `load_filter_criteria_tool` вводится шагом П5 и нужен для случая
  «изменились только файлы `FilterCriteria/`»: заголовок и индекс состава при этом не
  меняются. Стадия конвейера и этот инструмент вызывают одну и ту же функцию слоя — двух
  кодов, которые могли бы разойтись, в проекте нет.

Групп запроса (`kinds`) у вида НЕТ — это решение, а не упущение (Q5, вариант A): строка
условия существует только через числовой id строки критерия (Q1, вариант A), поэтому
состояния «записать критерии без условий» в модели нет; порога цены, при котором круг
стоило бы резать, замер 1.4 не дал (1 219 целей на весь круг, максимум 727 в одном файле).
Формы и команды вида при этом пишутся ОБЩИМИ таблицами детей (`forms`, `form_ext`,
`commands`) переиспользованием писателей V51 (Q3, вариант A), а не своими писателями, и
снимаются предикатом по uuid родителей, а не по ноге конфигурации: `DELETE` только по ноге
снял бы строки детей всех объектов конфигурации — тех, чьи узлы ещё не сделаны.

Что здесь происходит и чего здесь нет:

* круг задают каталог `FilterCriteria/` (файл регистрации вида и его одноимённый каталог
  содержимого `Forms/`, `Commands/`, `Ext/`) и записи индекса состава того же вида
  (`FilterCriterion.<Имя>`); расхождение двух ног называется `index_only` / `file_only` /
  `uuid_mismatch`, расхождения детей с индексом — `child_mismatches`, псевдо-записи индекса
  (модули, пары `.Form`, `Help`) — отдельным списком (Q7), объявления формы с её файлом —
  `declaration_mismatches`; нули обязаны быть названы, а не подразумеваемы (замеры 1.1–1.2
  дают равенство кругов на четырёх выгрузках);
* строки вида пишутся `insert_ids` (по одной строке, `RETURNING id`), а строки условий —
  `insert_many` с подстановкой полученного id: ключ `filter_criterion_content` начинается с
  `filter_criterion_id` — ссылки на КОНКРЕТНУЮ ревизию строки вида (Q2, вариант A). Ключом
  подстановки служит индексное имя `FilterCriterion.<Имя>`, которое несёт строка условия
  (прецеденты `common_attribute_targets` V50, `role_rights` V49);
* `filter_criterion_content` не штампуется ревизией (колонок `revision_no`/`changed_*` нет —
  исключение `CONFIGURATION_UNVERSIONED_TABLES`), строки вида, форм и команд — штампуются;
  `form_ext` получает ту же ревизию, что строка формы (прецедент V19/V51);
* снятие круга начинается с `filter_criterion_content`: её FK
  `filter_criterion_content_filter_criterion_id_fkey` объявлен с `ON DELETE CASCADE`, и
  каскад снял бы условия молча, без точного счётчика (M7); строки вида — последними;
* объекты, на которые указывают цели перечня `<Content>`, узел не загружает: они остаются
  ссылками на строки индекса состава (Q4), видовых узлов для них нет;
* тела модулей вида не читаются: файлы названы дескрипторами (`module_files_total`,
  `module_files_by_kind`), тексты принадлежат узлу V47 (Q8) — два узла один файл не читают.

Идемпотентность держится явным `DELETE` по `configuration_uuid` (внешнего ключа на
`configurations` и каскада по нему в схеме нет осознанно — прецеденты V20.1, V44, V46, V48,
V49, V50, V51), а не новой ревизией: повтор той же выгрузки не создаёт истории, снятые
строки названы в ответе. Ключом цепочки строки вида является (`configuration_uuid`,
`object_name`, `revision_no`) — замер 1.3: 14 различных uuid на 15 верхних записей индекса и
повторяющиеся имена между выгрузками, и без границы конфигурации две выгрузки слились бы в
одну строку.

Круг пишется одной транзакцией, и отказ разбора любого файла круга останавливает стадию ДО
записи: в базе не остаётся половины строк (приём V12/V46/V48/V49/V50/V51). Молча записать
то, что разобралось, означало бы назвать неполный круг полным.

После фиксации загрузчик пересобирает статистику затронутых таблиц
(`refresh_table_statistics` — мера V46): планировщик не знает о строках собственной
загрузки, и без статистики счётчики витрин текущего состояния на большой выгрузке
выполняются минутами (замер 28.10.2026 на BGU2: 8 мин 25 с против 7 мс). Отказ этой
операции — предупреждение ответа, а не отказ загрузки: строки зафиксированы.

Прогон шага: `python _v52_p4_writer_probe.py` (писатели и живая схема) и
`python _v52_p4_loader_probe.py MinCfg KomMag` (слой и контракт стадии); постоянная
проверка узла — `tools/check_v52_filter_criteria.py` (шаг П6).
"""
from typing import Any, Dict, List, Optional, Sequence, Tuple

from configuration_filter_criteria import (
    CONTENT_TABLE_NAME,
    DIR_NAME,
    OBSERVATION_DIRECTORY_MISSING,
    OBSERVATION_HELP_FILE,
    OBSERVATION_HELP_RESOURCES,
    OBSERVATION_INDEX_NOT_PROVIDED,
    TABLE_NAME,
    collect_filter_criteria,
    kind_root_index_rows,
)
# Вид родителя детей объекта конфигурации задаёт разбор V51 (`PARENT_TYPE_CONFIGURATION`), а
# не этот слой: это то же значение, которым дети конфигурации описаны узлом V47 и которым
# их описывает стадия S4f (замер живой базы — 10 872 строки `bsl_modules` с этим значением).
# Выписать его здесь вторым написанием — значит получить два места, где вид родителя
# разъезжается при первой же правке (прецедент импорта узла V51).
from configuration_exchange_plans import PARENT_TYPE_CONFIGURATION
from configuration_load_contract import (
    FILTER_CRITERIA_REMOVE_ORDER,
    FILTER_CRITERIA_REPEAT_HINT,
    STATUS_ERROR,
    STATUS_OK,
    filter_criteria_defaults,
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
    CommandsRowWriter,
    ExchangePlanFormsRowWriter,
    FormExtRowWriter,
)

OBJECTS_TABLE = "configuration_objects"

# Таблицы круга. Две таблицы вида берутся общим реестром `CONFIGURATION_OBJECT_WRITERS`,
# три таблицы детей — импортом классов: реестр выбирает писателя по таблице, а таблица у
# двух контуров одна (строка детей внешнего объекта и строка детей вида конфигурации
# различаются ногой области видимости и видом родителя), поэтому записей детей в реестре нет
# намеренно и стадия выбирает их по имени класса (приём `TABLE_WRITERS` узла V51 и
# `ConfigurationObjectModuleRowWriter` узла V47). `form_ext` своего писателя не имеет вовсе:
# ноги у таблицы нет, область видимости задаёт строка формы (шаг 1.5
# `migrate_v51_exchange_plans.sql`), а описания пишет общий `FormExtRowWriter`.
# Писатель форм называется именем узла V51 (`ExchangePlanFormsRowWriter`) и это названо, а не
# обойено молча: спецификация детей объекта конфигурации не зависит от вида-носителя, второй
# писатель той же таблицы дал бы два описания одной строки (Q3, вариант A).
FORM_EXT_TABLE = "form_ext"
FORMS_TABLE = "forms"
COMMANDS_TABLE_NAME = "commands"

TABLE_WRITERS: Dict[str, Any] = {
    TABLE_NAME: CONFIGURATION_OBJECT_WRITERS[TABLE_NAME],
    CONTENT_TABLE_NAME: CONFIGURATION_OBJECT_WRITERS[CONTENT_TABLE_NAME],
    FORMS_TABLE: ExchangePlanFormsRowWriter,
    FORM_EXT_TABLE: FormExtRowWriter,
    COMMANDS_TABLE_NAME: CommandsRowWriter,
}

# Таблицы детей, которых касается круг вида (в отличие от двух таблиц вида они общие для
# внешнего контура и всех видов конфигурации — отсюда ограниченный предикат снятия,
# см. `remove_filter_criteria`).

# Порядок снятия круга — не порядок `FILTER_CRITERIA_TABLES` контракта: `form_ext` снимается
# первой, потому что её FK `form_ext_form_id_fkey` объявлен с `ON DELETE CASCADE`, и каскад по
# строке формы снял бы описания молча, без точного счётчика (M7). Следом — описания форм,
# строки форм и команд, затем строки условий и только потом строки вида: на числовые id
# последних опираются строки `<Content>`, и снятие вида раньше оставило бы в базе перечень
# без строки вида хотя бы на время внутри транзакции. Тот же приём, что `REMOVE_ORDER` узлов
# V49, V50, V51.
#
# Сам перечень живёт НЕ здесь, а в контракте (`FILTER_CRITERIA_REMOVE_ORDER`), и здесь он
# только алиас — второго перечня тех же таблиц проект не заводит (это прямо сказано в
# комментарии к `FILTER_CRITERIA_TABLES`), а нулевой ответ стадии обязан называть те же пять
# таблиц, что и ответ прогона: детей снимает и пишет эта же стадия. Совпадение литералов
# контракта с константами этого слоя сторожит контур 12 `tools/check_v52_filter_criteria.py`
# (позиция, названная прогоном П8 02.11.2026 и закрытая этим разведением перечней).
REMOVE_ORDER: Tuple[str, ...] = FILTER_CRITERIA_REMOVE_ORDER

# Колонки индекса состава, которые нужны разбору вида: `name`/`object_name` — ключ сверки
# (`FilterCriterion.<Имя>`, `FilterCriterion.<Имя>.Form.<ИмяФормы>`, `…Command.<Имя>`),
# `uuid` — цель ссылочного типа перечня `<Content>` и сверка uuid файла с записью,
# `child_type`/`parent_name`/`depth` — различение записей вида, его детей и псевдозаписей
# слотов (замер 1.2). Фильтра по типу вида здесь нет намеренно: разрешение целей перечня
# `<Content>` обязано видеть записи ЛЮБОГО вида (цели ведут на документы, справочники,
# регистры), а свой круг вида отбирает сам разбор (`kind_root_index_rows`). Тот же приём,
# что `read_index_records` узлов V46, V48, V49, V50, V51: источник — строки БД, а не
# повторный разбор `ConfigDumpInfo.xml`.
INDEX_ROW_COLUMNS: Tuple[str, ...] = (
    "name", "object_id", "object_type", "object_name", "child_type", "parent_name", "depth",
    "uuid",
)

# Ключи сводки разбора, совпадающие с ключами контракта по имени (один словарь на разбор и
# на ответ): копируются только они — неперечисленный ключ контракта читается нулём (C1), а
# незнакомый ключ разбора не попадает в ответ, которого карточка не обещала (прецедент
# `SUMMARY_KEYS` узлов V46/V48/V49/V50/V51). Ключей строк записи (`rows`, `content`,
# `forms`, `form_ext`, `commands`, `module_files`) здесь нет: они идут в писатели, а не в
# ответ стадии; `success`/`warnings` разбора — внутренние признаки круга, стадия отвечает
# своими ключами.
SUMMARY_KEYS: Tuple[str, ...] = (
    "directory", "files_found", "files_read", "files_failed", "observations",
    "index_only", "file_only", "uuid_mismatch",
    "child_mismatches", "counts_by_child_mismatch_state", "index_pseudo_entries",
    "declaration_mismatches",
    "counts_by_properties_state", "counts_by_content_state", "counts_by_children_state",
    "counts_by_form_ref_state",
    "counts_by_type_state", "types_multiplicity", "types_by_class", "types_by_container",
    "types_total", "types_object_ref_resolved", "types_object_ref_view_wide",
    "types_unresolved_total", "types_unresolved",
    "counts_by_target_resolve_state", "targets_total", "targets_distinct",
    "targets_by_object_type", "max_targets_per_file", "content_item_attributes",
    "duplicate_targets", "unresolved_targets",
    "commands_total", "forms_total", "form_ext_total", "form_ext_formats",
    "module_files_total", "module_files_by_kind",
    "ext_observations", "unknown_properties", "unknown_value_properties",
    "unexpected_child_tags", "unexpected_type_tags", "unexpected_content_tags",
    "namespace_prefixes",
)


def read_index_records(cur, configuration_id: int) -> Dict[str, Any]:
    """Записи индекса состава этой конфигурации из `configuration_objects` (Н6).

    Пустой ответ означает «индекс недоступен», а не «объектов нет»: при недоступном индексе
    сверка файлов с перечнем, разрешение целей перечня `<Content>` и различение детей вида с
    псевдо-записями индекса невыразимы, и вызывающий обязан назвать это состоянием загрузки,
    а не нулями (тот же контракт, что у слоёв V46, V48, V49, V50, V51).

    Число записей своего вида (`FilterCriterion.<Имя>`) считается отдельно: оно сравнивается
    с числом файлов регистрации; расхождение обязан назвать прогон, а не читатель ответа.
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


def existing_criterion_uuids(cur, configuration_uuid: str) -> List[str]:
    """uuid критериев этой конфигурации, которые уже лежат в базе.

    Перечень нужен предикату снятия детей: детей обязан снять и у тех критериев, файлов
    которых в этой выгрузке больше нет (файл удалён), но строка вида в базе ещё осталась —
    иначе снятие по uuid из разбора оставило бы формы и команды удалённого вида сиротами, то
    есть ровно тот дефект, который узлы V44…V51 закрывают явным `DELETE` по ноге области
    видимости (прецедент `existing_plan_revisions` узла V51).

    Своих номеров ревизий здесь не спрашивают: в отличие от V51 строка условия ссылается на
    числовой id строки вида, а не на пару (uuid, `revision_no`), и этот id всегда даёт
    `insert_ids` текущего вызова — группы `kinds` у вида нет, поэтому ситуации «условия
    дописываются к ревизии, которая не переписывается» не существует (Q1, вариант A).

    Пустой ответ означает «строк вида в базе нет», а не ошибку: вызывающий снимает ровно то,
    что названо родителями из разбора.
    """
    try:
        cur.execute(
            f"SELECT object_uuid FROM {TABLE_NAME} WHERE configuration_uuid = %s::uuid",
            [str(configuration_uuid)],
        )
    except Exception:  # noqa: BLE001 — строк вида в базе нет, значит нечего снимать и ниже
        return []
    return [str(row[0]) for row in cur.fetchall() if row[0]]


# Таблицы детей, которых касается круг вида: в отличие от двух таблиц вида они общие для
# внешнего контура, вида V51 и будущих узлов — отсюда ограниченный предикат снятия
# (`remove_filter_criteria`) и ограниченный же предикат подсчёта (`count_criterion_child_rows`).
SHARED_CHILD_TABLES: Tuple[str, ...] = (FORM_EXT_TABLE, FORMS_TABLE, COMMANDS_TABLE_NAME)


def count_criterion_child_rows(cur, configuration_uuid: str, table: str,
                               other_configurations: bool = False) -> int:
    """Сколько строк общей таблицы детей относится к кругу вида «критерий отбора».

    Нужна пробам и проверкам, которые сравнивают состояние базы до и после загрузки: копия
    предиката в пробе разошлась бы с загрузчиком незаметно, а подсчёт только по ноге
    `configuration_uuid` собрал бы детей всех объектов конфигурации (те же таблицы пишут
    внешний контур и вид V51) — сравнение «до/после» перестало бы что-либо доказывать.
    Предикат держится слова в `remove_filter_criteria`: `parent_type` вида конфигурации плюс
    uuid родителей круга.

    `other_configurations=False` — круг своей конфигурации. `other_configurations=True` —
    дети ЧУЖИХ конфигураций, неприкосновенность чужого круга: родителем считается критерий
    ТОЙ ЖЕ конфигурации, к которой принадлежит строка ребёнка (прецедент
    `count_circle_child_rows` узла V51).

    `form_ext` ноги `configuration_uuid` не имеет (область видимости задаёт строка формы —
    наблюдение П6 узла V51), поэтому она считается связкой по `forms`. Двух таблиц вида это
    не касается: они версионируются и считаются по ноге конфигурации.
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
            f"(SELECT object_uuid FROM {view} fc "
            f"WHERE fc.configuration_uuid = {alias}.configuration_uuid)"
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


def remove_filter_criteria(cur, configuration_uuid: str, parents: Sequence[str],
                          tables: Tuple[str, ...] = REMOVE_ORDER) -> Dict[str, int]:
    """Снять строки круга вида этой конфигурации (внутри текущей транзакции).

    Очистка обязана быть явной: внешнего ключа на `configurations` и каскада по нему в схеме
    нет осознанно (прецеденты V20.1, V44, V46, V48, V49, V50, V51), иначе строки пережили бы
    снятие заголовка и стали бы сиротами, которые нельзя ни показать в карточке конфигурации,
    ни отличить от строк другой конфигурации. Этим же фильтром (`configuration_uuid`)
    держится снятие в `_remove_rows` конвейера — иначе `force=True` оставил бы в базе прежний
    состав вида (для BP3 это 6 строк вида и 492 строки условий — замер 1.4).

    Предикат детей ограничен кругом вида (`parent_type` + `parent_uuid = ANY(…)`), а не всей
    ногой конфигурации: таблицы `forms`, `form_ext`, `commands` общие для внешнего контура и
    для выгрузки конфигурации, и `DELETE` только по ноге снял бы строки детей всех объектов
    конфигурации — тех, которых в схеме ещё нет, но которые появятся следующими узлами.
    `form_ext` ноги не имеет вовсе (область видимости задаёт строка формы), поэтому она
    снимается по тем же родителям (тот же приём, что `remove_exchange_plans` V51).

    Строки условий снимаются по ноге `configuration_uuid` без ограничения uuid круга: групп
    запроса у вида нет (Q5, вариант A), поэтому весь круг стадии снимается целиком, а лишний
    предикат по `criterion_object_uuid` только сузил бы снятие до строк этого разбора и
    оставил бы условия удалённого вида в базе.
    """
    removed: Dict[str, int] = {}
    scope = [str(item) for item in parents if item]
    for table in tables:
        if table in (TABLE_NAME, CONTENT_TABLE_NAME):
            cur.execute(f"DELETE FROM {table} WHERE configuration_uuid = %s::uuid",
                        [str(configuration_uuid)])
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


def _require_header(configuration_uuid: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Найти строку заголовка по uuid; вернуть карточку или причину отказа.

    Заголовок обязателен: свойства вида — второй шаг того же первого слоя, и строки без
    заголовка нельзя ни показать в карточке конфигурации, ни снять вместе с ней (внешний
    ключ в схеме не поставлен осознанно — V20.1). Ленивый импорт — тот же обход цикла, что
    у слоёв V44/V46/V48/V49/V50/V51.
    """
    from configuration_loader import find_configuration  # ленивый импорт — круг узла V44

    card = find_configuration(configuration_uuid)
    if isinstance(card, dict) and card.get("error"):
        return None, f"Ошибка запроса: {card['error']}"
    if not card:
        return None, (
            f"Строка заголовка конфигурации с uuid {configuration_uuid} в базе не найдена. "
            "Сначала загрузите каталог точкой входа load_1c_catalog_tool(source_path=…): "
            "иначе свойства критериев отбора остались бы ни на что не указывающими, а "
            "внешний ключ в схеме не поставлен осознанно (узел V20.1)."
        )
    return card, None


def _stage_failure(reason: str, header: Optional[Dict] = None,
                   status: str = STATUS_ERROR,
                   extra: Optional[List[str]] = None) -> Dict[str, Any]:
    """Отказ стадии в форме закрытого контракта (C1, C3).

    Причина кладётся в ключ `error` замкнутого словаря `filter_criteria_defaults()`, а статус
    — в `status`: вызывающий отличает «стадия не выполнялась» от «слой отказал» (C2). Если
    заголовок к моменту отказа уже разрешён, он называется: по `configuration_id` карточка
    отличает «заголовка нет» от «заголовок есть, слой отказал по файлам». Подсказка о том,
    чем продолжить, кладётся и в отказ, и в успех (прецеденты `*_REPEAT_HINT` V48–V51).
    """
    result = filter_criteria_defaults()
    result["status"] = status
    result["error"] = reason
    result["reason"] = reason
    if header:
        result["configuration_id"] = header.get("id")
        result["configuration_uuid"] = header.get("uuid")
        result["configuration_name"] = header.get("name")
    result["warnings"].append(FILTER_CRITERIA_REPEAT_HINT)
    for warning in extra or []:
        result["warnings"].append(warning)
    return result


def load_filter_criteria(source_path: str,
                        configuration_uuid: Optional[str] = None,
                        changed_at=None) -> Dict[str, Any]:
    """Загрузить свойства критериев отбора конфигурации (узел V52, стадия S4g).

    Порядок: каталог → uuid из `Configuration.xml` (или сверка переданного) → проверка, что
    заголовок загружен → индекс состава из `configuration_objects` (сверка файлов с перечнем,
    разрешение целей перечня `<Content>` и различение детей с псевдозаписями, Н6) → разбор
    каталога вида → **одна транзакция**: `DELETE` по uuid и по родителям круга + вставки
    пяти таблиц → отдельной транзакцией `ANALYZE` (мера V46).

    Групп `kinds` у стадии нет (Q5, вариант A): строка условия существует только через id
    строки критерия (Q1, вариант A), поэтому частичная запись круга описывала бы состав,
    которого в выгрузке нет.

    Отказ разбора любого файла круга останавливает стадию ДО записи: половина круга в базе
    читалась бы как полный состав вида (приём V12/V46/V48/V49/V50/V51). Отсутствующий
    каталог `FilterCriteria/` — не отказ, а ответ о выгрузке: `files_found = 0` с
    наблюдением `directory_missing` (прецедент Q9 узла V48), потому что у конфигурации без
    критериев отбора их действительно нет.

    `changed_at` передаёт конвейер: строки одной загрузки обязаны нести одну метку (M2), а не
    время своей транзакции. Пустое значение — своя метка вызова (одиночный прогон слоя).
    Строки условий метку не несут: колонок ревизии у таблицы нет
    (`CONFIGURATION_UNVERSIONED_TABLES`), их текущность читается связкой по
    `filter_criterion_id` (Q2, вариант A).

    Порядок записи держится иерархией данных, а не удобством: сначала строки критериев
    (`insert_ids`, `RETURNING id`), затем строки условий, ссылающиеся на id этих ревизий;
    параллельно — строки форм (`insert_ids`, `RETURNING id`), затем их описания `form_ext`,
    ссылающиеся на числовой `form_id` (прецедент V13/V14/V51), и строки команд. Всё это
    одной транзакцией: отказ на середине оставил бы в базе критерии без условий либо формы
    без описаний, то есть состав, которого в выгрузке нет.
    """
    uuid_info = configuration_uuid_from_layout(source_path)
    if "uuid" not in uuid_info:
        return _stage_failure(uuid_info.get("error")
                             or f"Каталог выгрузки не читается: {source_path}")
    layout_uuid = str(uuid_info["uuid"])
    if configuration_uuid and str(configuration_uuid).strip().lower() != layout_uuid.lower():
        # Два источника одного факта указали на разные конфигурации: молча выбрать один —
        # значит записать свойства чужой конфигурации (тот же отказ, что у слоёв
        # V44/V46/V48/V49/V50/V51).
        return _stage_failure(
            f"Передан configuration_uuid={configuration_uuid}, а каталог {source_path} "
            f"описывает конфигурацию с uuid={layout_uuid}. Загрузка не выполнена: укажите "
            "путь каталога этой конфигурации или уберите configuration_uuid."
        )
    configuration_uuid = layout_uuid

    header, reason = _require_header(configuration_uuid)
    if header is None:
        return _stage_failure(reason)

    warnings: List[str] = []
    index_info: Dict[str, Any] = {"available": False, "row_count": 0, "kind_count": 0,
                                  "reason": None}
    existing: List[str] = []
    try:
        with transaction() as cur:
            index_info = read_index_records(cur, int(header["id"]))
            existing = existing_criterion_uuids(cur, configuration_uuid)
    except Exception as exc:  # noqa: BLE001 — индекс читается до записи, отказ называется им
        index_info["reason"] = f"чтение {OBJECTS_TABLE} не удалось: {exc}"

    # Содержимое подкаталогов читается всегда: групп запроса у вида нет, а цена круга детей
    # измерена (замер 1.2: 2 формы и 1 команда на четыре выгрузки); тела модулей при этом не
    # читаются — их берёт узел V47 (Q8), и разбор вызывает общий слой V13/V14 с
    # `with_object_modules=False`.
    collected = collect_filter_criteria(source_path, index_rows=index_info["rows"])
    if not collected["success"]:
        failures = collected.get("files_failed") or []
        detail = "; ".join(f"{item.get('source_path')}: {item.get('reason')}"
                           for item in failures[:10])
        return _stage_failure(
            f"Круг не записан: {len(failures)} файл(ов) каталога "
            f"{collected.get('directory')} не разобраны — {detail}. Ни одной строки круга "
            "в базу не записано: половина круга читалась бы как полный состав вида (приём "
            "V12/V46); прежние строки этой конфигурации не сняты",
            header=header,
        )

    # ── строки круга ───────────────────────────────────────────────────────────────
    criterion_rows = list(collected.get("rows") or [])
    content_rows = list(collected.get("content") or [])
    form_rows = list(collected.get("forms") or [])
    form_ext_rows = list(collected.get("form_ext") or [])
    command_rows = list(collected.get("commands") or [])

    # Ключ конфигурации знает вызывающий, а не XML файла — тот же порядок, что у писателей
    # свойств V46, модулей корня V44, параметров сеанса V48, ролей V49, общих реквизитов V50
    # и планов обмена V51. `form_ext` ключа не имеет вовсе: её область видимости задаёт
    # строка формы (шаг 1.5 `migrate_v51_exchange_plans.sql`).
    for rows in (criterion_rows, content_rows, form_rows, command_rows):
        for row in rows:
            row["configuration_uuid"] = configuration_uuid

    # Полнота связывания проверяется ДО транзакции: строка условия обязана ссылаться на
    # строку критерия этого же круга (Q1, вариант A), и молча отбросить её значило бы
    # назвать неполный круг полным. Ключом служит индексное имя `FilterCriterion.<Имя>` —
    # именно в этой форме связь несёт строка условия (прецеденты `role_name` V49,
    # `attribute_full_name` V50, `exchange_plan_full_name` V51).
    link_keys = [str(row.get("full_name") or "") for row in criterion_rows]
    known = set(link_keys)
    if len(known) != len(link_keys):
        duplicated = sorted({key for key in link_keys if link_keys.count(key) > 1})
        return _stage_failure(
            f"Круг не записан: разбор дал {len(link_keys)} строк критериев с "
            f"повторяющимися именами ({', '.join(duplicated[:5])}) — строки условий нельзя "
            "связать однозначно (замер 1.3 даёт уникальность имён внутри выгрузки), ни одна "
            "строка круга не записана",
            header=header,
        )
    unbound = sorted({str(row.get("criterion_full_name") or "<без имени>")
                      for row in content_rows
                      if row.get("criterion_full_name") not in known})
    if unbound:
        return _stage_failure(
            f"Круг не записан: {len(unbound)} строка(ов) условий остались без строки "
            f"критерия ({', '.join(unbound[:5])}) — это внутреннее противоречие разбора, а "
            "не состояние выгрузки; ни одна строка круга не записана",
            header=header,
        )

    # Родители круга для предиката снятия детей: uuid критериев из разбора плюс uuid тех
    # строк вида, что ещё лежат в базе (файл удалён из выгрузки — детей обязан снять и у
    # них), иначе снятие по uuid из разбора оставила бы формы и команды сиротами (прецедент
    # `parents` узла V51). Табличных частей у вида нет (замер 1.2), поэтому второй ноги —
    # uuid табличных частей, которую требовал V51, здесь нет и быть не может.
    parents = sorted({str(row.get("object_uuid")) for row in criterion_rows
                      if row.get("object_uuid")} | set(existing))

    # Один штамп времени на всё событие загрузки (M2): версионируемые таблицы одной загрузки
    # не должны нести две метки. Метку определяет первая штампуемая таблица и передаётся
    # остальным. Строки условий метку не получают — колонок ревизии у них нет
    # (`CONFIGURATION_UNVERSIONED_TABLES`, Q2 вариант A); строки `form_ext` штампуются тем же
    # номером ревизии, что и строки форм: описание формы относится к её ревизии
    # (`uq_form_ext_form_id_revision`), своей цепи у него нет (прецедент V19/V51).
    moment = changed_at
    for rows in (criterion_rows, form_rows, command_rows):
        moment = stamp_revision_rows(rows, revision_no=FIRST_REVISION,
                                     changed_by=CHANGED_BY_LOAD, changed_at=moment)
    if form_ext_rows:
        moment = stamp_revision_rows(form_ext_rows, revision_no=FIRST_REVISION,
                                     changed_by=CHANGED_BY_LOAD, changed_at=moment)

    # ── одна транзакция: снятие круга + вставки ──────────────────────────────────────
    # Порядок снятия держит `REMOVE_ORDER` (описания форм раньше строк форм, строки вида
    # последней), а не порядок `FILTER_CRITERIA_TABLES`: каскад не должен снять строку молча
    # (M7). Порядок вставки держится иерархией данных: id родителя нужен дочерним строкам.
    removed: Dict[str, int] = {}
    written: Dict[str, int] = {table: 0 for table in REMOVE_ORDER}
    try:
        with transaction() as cur:
            removed = remove_filter_criteria(cur, configuration_uuid, parents)
            # Строки вида — по одной строке с `RETURNING id`: на числовой id конкретной
            # ревизии ссылается ключ `filter_criterion_content` (Q2, вариант A), а
            # `insert_many` id не возвращает (тот же приём, что `insert_ids` слоя V50).
            criterion_ids = TABLE_WRITERS[TABLE_NAME].insert_ids(cur, criterion_rows)
            if len(criterion_ids) != len(criterion_rows):
                raise RuntimeError(
                    f"писатель вернул {len(criterion_ids)} id для {len(criterion_rows)} "
                    f"строк таблицы {TABLE_NAME} — связать условия нечем"
                )
            written[TABLE_NAME] = len(criterion_ids)
            ids_by_key = dict(zip(link_keys, criterion_ids))
            for row in content_rows:
                row["filter_criterion_id"] = ids_by_key[str(row.get("criterion_full_name"))]
            # Самая большая таблица узла (1 219 строк на четыре выгрузки, максимум 727 в
            # одном файле — замер 1.4): писатель держит свою страницу `PAGE_SIZE = 200`,
            # вызывающий отдаёт весь список.
            written[CONTENT_TABLE_NAME] = TABLE_WRITERS[
                CONTENT_TABLE_NAME].insert_many(cur, content_rows)
            if form_rows:
                # Формы — по одной строке с `RETURNING id`: описание формы ссылается на
                # числовой `form_id` (`uq_form_ext_form_id_revision`); связь держится uuid
                # формы, а не порядком списка — описание и строка регистрации приходят из
                # разных файлов (прецедент V13/V14 и узла V51).
                form_ids = TABLE_WRITERS[FORMS_TABLE].insert_ids(cur, form_rows)
                ids_by_uuid = {str(row.get("uuid")): record_id
                               for row, record_id in zip(form_rows, form_ids) if record_id}
                without_id = [str(row.get("name") or row.get("form_uuid"))
                              for row in form_ext_rows
                              if ids_by_uuid.get(str(row.get("form_uuid"))) is None]
                if without_id:
                    # `form_ext.form_id` объявлен NOT NULL: молча вставить строку с пустой
                    # ссылкой значило бы получить отказ NOT NULL вместо ответа о том, какое
                    # описание осталось без строки формы (прецедент «сирот» V49/V51).
                    raise ValueError(
                        "описания форм остались без строки формы: "
                        + ", ".join(without_id[:10]))
                for row in form_ext_rows:
                    row["form_id"] = ids_by_uuid.get(str(row.get("form_uuid")))
                written[FORMS_TABLE] = len(ids_by_uuid)
                written[FORM_EXT_TABLE] = TABLE_WRITERS[
                    FORM_EXT_TABLE].insert_many(cur, form_ext_rows)
            written[COMMANDS_TABLE_NAME] = TABLE_WRITERS[
                COMMANDS_TABLE_NAME].insert_many(cur, command_rows)
    except Exception as exc:  # noqa: BLE001 — заголовок уже разрешён, отказ называется им
        return _stage_failure(
            f"Ошибка записи: {exc}. Транзакция отменена целиком: в базе остались прежние "
            f"строки круга (снятые этим вызовом — {sum(removed.values())}), новых нет",
            header=header,
        )

    # ── статистика записанных таблиц (мера V46) ──────────────────────────────────────
    # Отдельная транзакция ПОСЛЕ фиксации записи: планировщик обязан увидеть строки, иначе
    # первый же читатель витрин текущего состояния платит минутами за счётчик (замер V46 на
    # BGU2: 8 мин 25 с против 7 мс после ANALYZE). Отказ статистики отказом загрузки не
    # является: строки зафиксированы, и состояние ответа от него не меняется.
    touched_tables = tuple(REMOVE_ORDER)
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

    # ── ответ стадии: закрытый контракт + сводка круга ───────────────────────────────
    # Числа ответа считаются по ЗАПИСАННЫМ строкам (`written`), а сводка состояний — по
    # разбору круга: ответ стадии описывает содержимое базы, а не круг выгрузки, и расхождение
    # между ними обязано быть названным предупреждением, а не молчанием.
    result = filter_criteria_defaults()
    for key in SUMMARY_KEYS:
        if key in collected:
            result[key] = collected[key]
    result.update({
        "status": STATUS_OK,
        "success": True,
        "configuration_id": header["id"],
        "configuration_uuid": configuration_uuid,
        "configuration_name": header.get("name"),
        "index_available": bool(index_info["available"]),
        "index_kind_records": int(index_info["kind_count"]),
        "rows_written": int(sum(written.values())),
        "filter_criteria_written": int(written[TABLE_NAME]),
        "content_written": int(written[CONTENT_TABLE_NAME]),
        "forms_written": int(written[FORMS_TABLE]),
        "form_ext_written": int(written[FORM_EXT_TABLE]),
        "commands_written": int(written[COMMANDS_TABLE_NAME]),
        "removed_previous": int(sum(removed.values())),
        "removed_by_table": removed,
        "written_by_table": written,
        "child_mismatch_total": len(collected.get("child_mismatches") or []),
        "index_pseudo_entries_total": len(collected.get("index_pseudo_entries") or []),
        "declaration_mismatch_total": len(collected.get("declaration_mismatches") or []),
        "content_unresolved_total": len(collected.get("unresolved_targets") or []),
        "ext_observations_total": int(sum((collected.get("ext_observations") or {}).values())),
        "counts_by_ext_observation": dict(collected.get("ext_observations") or {}),
        "statistics_refreshed": statistics_refreshed,
    })
    warnings.extend(collected.get("warnings") or [])

    if not index_info["available"] and index_info.get("reason"):
        warnings.append(
            f"Индекс состава: {index_info['reason']} — состояния `index_only` и `file_only` "
            "при этом невыразимы, а цели перечня `<Content>` остаются неразрешёнными "
            "записями (Q4): «объекта нет в перечне» от «перечень этой конфигурации не "
            "загружен» не отличить"
        )
    for observation, _detail in (collected.get("observations") or []):
        if observation == OBSERVATION_DIRECTORY_MISSING:
            warnings.append(
                f"Каталог {collected.get('directory')}/ в выгрузке отсутствует — критериев "
                "отбора у этой конфигурации нет, и нули таблиц являются ответом о выгрузке, "
                "а не отказом стадии (прецедент Q9 узла V48; ни одна из четырёх замеренных "
                "выгрузок такого не даёт — состояние держится отдельной пробой с пустым "
                "кругом)"
            )
        elif observation == OBSERVATION_INDEX_NOT_PROVIDED:
            warnings.append(
                "индекс состава не передан разбору: сверка файлов с перечнем не выполнялась, "
                "состояния `index_only`/`file_only` при этом не являются ответом о выгрузке"
            )
    if index_info["available"] and int(result["index_kind_records"]) != int(
            result.get("files_found") or 0):
        warnings.append(
            f"Записей `FilterCriterion.<Имя>` в индексе состава "
            f"{result['index_kind_records']}, файлов регистрации "
            f"{result.get('files_found')} — круги различаются (замеры 1.1 дают равенство на "
            "четырёх выгрузках, поэтому расхождение требует объяснения этим прогоном; "
            "расхождения перечислены ключами `index_only` / `file_only`)"
        )
    if int(result.get("content_written") or 0) != int(result.get("targets_total") or 0):
        warnings.append(
            f"Разбор дал {result.get('targets_total')} строк перечня `<Content>`, записано "
            f"{result.get('content_written')} — часть строк в {CONTENT_TABLE_NAME} не "
            "попала; связь со строкой критерия держится id ревизии (Q2 вариант A), и молчать "
            "об этом нельзя"
        )
    if int(result.get("module_files_total") or 0):
        kinds = ", ".join(
            f"{name}={count}"
            for name, count in sorted((result.get("module_files_by_kind") or {}).items()))
        warnings.append(
            f"Файлы модулей вида названы дескрипторами (путь, размер, род): их "
            f"{result.get('module_files_total')} ({kinds}). Тела в `bsl_modules` этим узлом "
            f"НЕ пишутся: строки с parent_type='{PARENT_TYPE_CONFIGURATION}' по этому виду "
            "пишет узел V47 (Q8) — двух чтений одного файла два узла не делают"
        )
    ext_counts = result.get("counts_by_ext_observation") or {}
    for kind in (OBSERVATION_HELP_FILE, OBSERVATION_HELP_RESOURCES):
        if ext_counts.get(kind):
            warnings.append(
                f"Справочные ресурсы формы названы наблюдением `{kind}` в "
                f"{ext_counts[kind]} случае(ях): содержимое справки узлом НЕ хранится — "
                "колонок под него в схеме нет, наличие называется наблюдением, потому что "
                "«ресурсов нет» и «ресурсы не трогали» — разные ответы (Q7)"
            )
    truncated = sum(1 for row in form_ext_rows if row.get("ext_truncated"))
    if truncated:
        warnings.append(
            f"{truncated} текстов (содержимое форм) усечены порогом слоя V14 "
            "`MAX_TEXT_CHARS`: полное значение называют `ext_size` и `ext_path`, состояние — "
            "`ext_truncated` (прецедент внешнего контура: узел вида порог не переопределяет)"
        )
    if any(removed.values()):
        warnings.append(
            "Прежние строки свойств критериев отбора этой конфигурации сняты перед записью: "
            + ", ".join(f"{table}={count}" for table, count in sorted(removed.items())
                        if count)
            + ". Идемпотентность держится явным DELETE по configuration_uuid и по родителям "
              "круга: внешнего ключа и каскада по конфигурации в схеме нет осознанно "
              "(прецедент V20.1), а снятие детей только по ноге области видимости сняло бы "
              "строки детей всех объектов конфигурации; новая ревизия на повторную загрузку "
              "той же выгрузки не заводится — история состояний принадлежит узлу правки "
              "объекта, которого в схеме ещё нет")
    if criterion_rows:
        warnings.append(
            f"Момент загрузки строк круга — {moment}: той же меткой помечены строки "
            "заголовка и других стадий этого события (M2); строки условий метку не несут — "
            "своей цепи ревизий у них нет (Q2 вариант A), их текущность читается связкой по "
            "`filter_criterion_id`"
        )
    else:
        warnings.append(
            "Строк критериев этим вызовом не записано: каталог вида пуст или отсутствует "
            f"(файлов {result.get('files_found')}), поэтому и общего момента загрузки вида у "
            "этого события нет — нули таблиц являются ответом о выгрузке (прецедент Q9)"
        )
    warnings.append(FILTER_CRITERIA_REPEAT_HINT)
    result["warnings"] = warnings
    return result

CHILD_TABLES: Tuple[str, ...] = (FORMS_TABLE, COMMANDS_TABLE_NAME)
