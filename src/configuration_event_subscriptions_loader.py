#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Загрузчик свойств подписок на события (узел V53, шаг П4, 02.11.2026).

Стадия S4h конвейера первого слоя: файлы вида `EventSubscriptions` (позиция 2.8 нормативного
списка плана `docs/CONFIGURATION_EVENT_SUBSCRIPTIONS_PLAN.md`) в две таблицы —
`event_subscriptions` (строка подписки) и `event_subscription_sources` (строки её блока
`<Source>`, то есть круг целей срабатывания). Норматив — тот же план (решения Q1–Q8,
наблюдения M1–M7); разбор файлов вида — отдельный модуль
`src/configuration_event_subscriptions.py` (шаг П2), писатели строк — реестр
`CONFIGURATION_OBJECT_WRITERS` (шаг П3).

Почему стадия отдельная, а не восьмой вид S4 (прецеденты Q5 узлов V48–V52): правило C3
требует своего ключа ответа `event_subscriptions`; порядок `STAGES` повторяет порядок
нормативного списка (2.8 идёт сразу за 2.7), поэтому S4h стоит между S4g и S4b. Круг стадии
(`EVENT_SUBSCRIPTIONS_TABLES`) отделён от круга версионности шагом П3: регистрация таблиц вида
в `CONFIGURATION_VERSIONED_TABLES` молча добавила бы их к чужой стадии.

Групп запроса (`kinds`) у вида нет — как у V50 и V52 — и это решение, а не упущение (Q8,
вариант A): строка источника существует только через id строки вида (Q4, вариант A), поэтому
состояния «записать подписку без круга целей» в модели нет; порога цены, при котором круг
стоило бы резать, замер 2.2 не дал (25 100 записей на весь круг, максимум 789 в одном файле).
Отдельный вход дозагружает весь круг сразу.

Что здесь происходит и чего здесь нет:

* круг задают каталог `EventSubscriptions/` (плоский: подкаталогов, форм, макетов, команд и
  модулей у вида нет — замер 1.2, M2) и записи индекса состава того же вида
  (`EventSubscription.<Имя>`); расхождение двух источников называется `index_only` /
  `file_only` / `uuid_mismatch` — четыре замеренные выгрузки дают нули, и нули обязаны быть
  названы;
* строка источника ссылается на ЧИСЛОВОЙ id ревизии строки вида (Q4, вариант A): своей цепи
  ревизий у неё нет, поэтому подписки вставляются `insert_ids()` (по одной строке,
  `RETURNING id`), а полученный id подставляется в строки блока `<Source>`; ключом
  подстановки служит индексное имя подписки — его несёт строка источника в колонке
  `subscription_full_name` (прецедент `attribute_full_name` узла V50, `criterion_full_name`
  V52, `role_name` V49);
* `event_subscription_sources` не штампуется ревизией (колонок `revision_no`/`changed_*` нет —
  исключение `CONFIGURATION_UNVERSIONED_TABLES`), строка подписки — штампуется;
* обработчик разрешается по перечню общих модулей ТЕКУЩЕЙ ревизии (витрина
  `v_current_common_modules`, строки пишет узел V46): 772 из 772 значений корпуса попадают в
  него (замер 2.3). Внешнего ключа на `common_modules` в схеме нет осознанно (Q2, решение
  оператора): связь не один-к-одному (248 уникальных обработчиков при 311 подписках в BGU2).
  Перечень может быть недоступен — тогда `unresolved` означает «нечем разрешить», и стадия
  называет это предупреждением, а не нулями (правило C2);
* цели блока `<Source>` разрешаются ВСЕМИ строками индекса состава данной конфигурации, а не
  строками своего вида: цель — объект другого вида метаданных (`Catalog.Организации`), 24 835
  из 25 100 записей разрешаются точным совпадением (замер 2.2). Голая ссылка `cfg:<Класс>`
  именем не обладает и разрешается проверкой присутствия вида метаданных в индексе —
  состояниями `type_present`/`type_absent` (242/23, M5, Q3 вариант A);
* снятие круга начинается с `event_subscription_sources`: её FK
  `event_subscription_sources_event_subscription_id_fkey` объявлен с `ON DELETE CASCADE`
  (шаг П1), и каскад снял бы строки молча, без точного счётчика — вызывающий обязан назвать
  полное состояние, снятое `force=True` (M7).

Идемпотентность держится явным `DELETE` по `configuration_uuid` (внешнего ключа на
`configurations` и каскада по нему в схеме нет осознанно — прецеденты V20.1, V44, V46, V48,
V49, V50, V51, V52), а не новой ревизией: повтор той же выгрузки не создаёт истории, снятые
строки названы в ответе. Ключом цепочки строки вида является (`configuration_uuid`,
`object_name`, `revision_no`) — замер M1: 162 uuid и 192 имени подписок стоят одновременно в
BGU2 и BP3, и без границы конфигурации две выгрузки слились бы в одну строку.

Круг пишется одной транзакцией, и отказ разбора любого файла круга останавливает стадию ДО
записи: в базе не остаётся половины строк (приём V12/V46/V48/V49/V50/V51/V52). Молча записать
то, что разобралось, означало бы назвать неполный круг полным.

После фиксации загрузчик пересобирает статистику двух таблиц (`refresh_table_statistics` —
мера V46): без статистики счётчики по витринам текущего состояния на большой выгрузке
выполняются минутами (замер V46 на BGU2: 8 мин 25 с против 7 мс). Отказ статистики отказом
загрузки не является — строки зафиксированы, и это предупреждение.

Прогон шага: `python _v53_p4_loader_probe.py MinCfg KomMag`, затем отдельно BGU2 и BP3
(прогоны, меняющие общее состояние БД, не параллелят). Проверка узла —
`python tools/check_v53_event_subscriptions.py` (шаг П6).
"""
from typing import Any, Dict, List, Optional, Tuple

from configuration_event_subscriptions import (
    CIRCLE_DISCREPANCIES,
    SOURCES_TABLE_NAME,
    TABLE_NAME,
    collect_event_subscriptions,
    kind_index_rows,
)
from configuration_load_contract import (
    EVENT_SUBSCRIPTIONS_REMOVE_ORDER,
    EVENT_SUBSCRIPTIONS_REPEAT_HINT,
    EVENT_SUBSCRIPTIONS_TABLES,
    STATUS_ERROR,
    STATUS_OK,
    event_subscriptions_defaults,
)
from configuration_object_properties_loader import refresh_table_statistics
from configuration_root_module_loader import configuration_uuid_from_layout
from current_revision import (
    CHANGED_BY_LOAD,
    CURRENT_VIEWS,
    FIRST_REVISION,
    stamp_revision_rows,
)
from external_db import transaction
from external_table_writer import CONFIGURATION_OBJECT_WRITERS


OBJECTS_TABLE = "configuration_objects"
SUBSCRIPTIONS_TABLE = TABLE_NAME
SOURCES_TABLE = SOURCES_TABLE_NAME
# Перечень общих модулей берётся из витрины текущего состояния таблицы узла V46: имя витрины
# даёт реестр `CURRENT_VIEWS`, а не строка в этом коде: опечатка в имени читалась бы как
# «нет такой таблицы», а не как пропущенный фильтр ревизий.
COMMON_MODULES_TABLE = "common_modules"
COMMON_MODULES_VIEW = CURRENT_VIEWS[COMMON_MODULES_TABLE]

# Писатели двух таблиц берутся общим реестром, а не импортом классов (правило п.6 слоя):
# ошибка выбора превращается в запись не в ту таблицу, а реестр уже знает, какая таблица
# версионируется своей цепочкой, а какая — нет (`CONFIGURATION_UNVERSIONED_TABLES`).
ES_WRITERS = {table: CONFIGURATION_OBJECT_WRITERS[table]
              for table in EVENT_SUBSCRIPTIONS_TABLES}

# Порядок снятия круга — не порядок `EVENT_SUBSCRIPTIONS_TABLES`: строки источника снимаются
# ДО строк вида, потому что их собственный FK
# `event_subscription_sources_event_subscription_id_fkey` объявлен с `ON DELETE CASCADE` —
# каскад снял бы строки молча, и число в ответе было бы неправдой (M7). Тот же приём, что
# `REMOVE_ORDER` узлов V49/V50/V52. Порядок берётся из контракта одним местом, чтобы стадия и
# описание узла не разъехались.
REMOVE_ORDER: Tuple[str, ...] = EVENT_SUBSCRIPTIONS_REMOVE_ORDER

# Колонки индекса состава, которые нужны разбору вида: `name`/`object_name` — ключ сверки
# (`EventSubscription.<Имя>`), `uuid` — цель ссылочного типа и сверка uuid файла с записью
# перечня, `child_type` — различение записей одного имени, `depth`/`parent_name` — состояние
# «запись индекса имеет глубину» (иерархии раскладки у вида нет, замер 1.2). Фильтра по типу
# вида здесь нет намеренно: разрешение целей блока `<Source>` обязано видеть записи ЛЮБОГО
# вида метаданных (замер 2.2: цели ведут на справочники, документы, регистры и константы), а
# свой круг вида отбирает сам разбор (`kind_index_rows`). Тот же приём, что
# `read_index_records` узлов V46, V48, V49, V50, V52: источник — строки БД, а не повторный
# разбор `ConfigDumpInfo.xml`.
INDEX_ROW_COLUMNS: Tuple[str, ...] = (
    "name", "object_id", "object_type", "object_name", "child_type", "parent_name", "depth",
    "uuid",
)

# Ключи сводки разбора, совпадающие с ключами контракта по имени (один словарь на разбор и
# на ответ): копируются только они — неперечисленный ключ контракта читается нулём (C1), а
# незнакомый ключ разбора не попадает в ответ, которого карточка не обещала (прецедент
# `SUMMARY_KEYS` узлов V46/V48/V49/V50/V52). Ключей `rows` и `source_rows` здесь нет: строки
# записи идут в писатели, а не в ответ стадии; `success` разбора — внутренний признак круга,
# стадия отвечает своими `success` и `status`. Агрегаты, которых разбор не даёт
# (`events_by_name`, `handlers_total`, `handlers_distinct`, `sources_distinct`,
# `max_sources_per_subscription`, `counts_by_observation`, `counts_by_circle_discrepancy`),
# считает стадия по ЗАПИСАННЫМ строкам — ответ обязан описывать содержимое базы, а не круг
# выгрузки (тот же приём, что `separation_summary` узла V50).
SUMMARY_KEYS: Tuple[str, ...] = (
    "directory", "files_found", "files_read", "files_failed", "observations",
    "index_only", "file_only", "uuid_mismatch", "duplicate_names",
    "counts_by_properties_state", "unknown_properties",
    "counts_by_event_state", "unknown_event_names",
    "counts_by_handler_state", "handlers_unresolved_total", "handlers_unresolved",
    "counts_by_source_state", "counts_by_source_tag", "counts_by_target_form",
    "counts_by_target_resolve_state", "sources_total", "sources_by_class",
    "targets_unresolved_total", "targets_unresolved",
    "namespace_prefixes",
)


def read_index_records(cur, configuration_id: int) -> Dict[str, Any]:
    """Записи индекса состава этой конфигурации из `configuration_objects` (Н6).

    Пустой ответ означает «индекс недоступен», а не «объектов нет»: при недоступном индексе
    сверка файлов с перечнем и разрешение целей блока `<Source>` невыразимы, и вызывающий
    обязан назвать это состоянием загрузки, а не нулями (тот же контракт, что у слоёв V46,
    V47, V48, V49, V50, V52).

    Своего вида считается ОДНО число (`EventSubscription.<Имя>`): в отличие от планов обмена
    (V51) и критериев отбора (V52), у вида нет детей — ни форм, ни команд, ни макетов
    (замер 1.2, M2), поэтому второй ноги круга здесь нет.
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
            "разрешение целей блока <Source> невозможны"
        )
        return {"rows": [], **info}
    info.update({
        "available": True,
        "row_count": len(records),
        "kind_count": len(kind_index_rows(records)),
    })
    return {"rows": records, **info}


def read_common_module_names(cur, configuration_uuid: str) -> Dict[str, Any]:
    """Имена общих модулей ТЕКУЩЕЙ ревизии этой конфигурации (Q2 — разрешение обработчика).

    Источник — витрина `v_current_common_modules` (её строки пишет узел V46): разрешать по
    всей таблице `common_modules` нельзя, потому что в ней лежат и снятые ревизии, и
    обработчик получил бы `exact` по модулю, которого в текущем состоянии нет.

    Пустой ответ означает «перечень недоступен» (свойства общих модулей этой конфигурации не
    загружены), а не «общих модулей нет»: при недоступном перечне все обработчики остаются
    `unresolved`, и стадия обязана назвать причину предупреждением — «модуля нет» и «нечем
    разрешить» являются разными ответами (правило C2). Внешнего ключа на `common_modules` в
    схеме нет (Q2, решение оператора), поэтому согласование держится этим чтением, а не
    ссылкой в структуре схемы.
    """
    info: Dict[str, Any] = {"available": False, "count": 0, "reason": None}
    try:
        cur.execute(
            f"SELECT object_name FROM {COMMON_MODULES_VIEW} "
            "WHERE configuration_uuid = %s::uuid",
            [str(configuration_uuid)],
        )
    except Exception as exc:  # noqa: BLE001 — перечень читается до записи, отказ называется
        info["reason"] = f"чтение {COMMON_MODULES_VIEW} не удалось: {exc}"
        return {"names": set(), **info}
    names = {str(row[0]).strip() for row in cur.fetchall() if row[0]}
    if not names:
        info["reason"] = (
            f"в {COMMON_MODULES_VIEW} нет строк общих модулей для "
            f"configuration_uuid={configuration_uuid}: свойства общих модулей этой "
            "конфигурации не загружены (узел V46), поэтому разрешить обработчик нечем"
        )
        return {"names": set(), **info}
    info.update({"available": True, "count": len(names)})
    return {"names": names, **info}


def remove_event_subscriptions(cur, configuration_uuid: str,
                              tables: Tuple[str, ...] = REMOVE_ORDER) -> Dict[str, int]:
    """Снять строки подписок на события этой конфигурации (внутри текущей транзакции).

    Очистка обязана быть явной: внешнего ключа на `configurations` и каскада по нему в схеме
    нет осознанно (прецеденты V20.1, V44, V46, V48, V49, V50, V51, V52), иначе строки
    пережили бы снятие заголовка и стали бы сиротами, которые нельзя ни показать в карточке
    конфигурации, ни отличить от строк другой конфигурации. Этим же фильтром
    (`configuration_uuid`) держится снятие в `_remove_rows` конвейера — иначе `force=True`
    оставил бы в базе прежний состав вида (для BP3 это 311 строк подписок и 13 379 строк
    блока `<Source>` — замер 2.2).

    Порядок задаёт `REMOVE_ORDER`, а не `EVENT_SUBSCRIPTIONS_TABLES`: строки источника
    снимаются ДО строк вида, потому что их FK
    `event_subscription_sources_event_subscription_id_fkey` объявлен с `ON DELETE CASCADE` —
    каскад снял бы строки молча, и число в ответе было бы неправдой (M7). Строка источника
    несёт `configuration_uuid` именно поэтому, чтобы снятие шло по одной ноге с таблицей вида,
    а не через связку с ней (тот же порядок, что `role_rights` V49,
    `common_attribute_targets` V50, `filter_criterion_content` V52).
    """
    removed: Dict[str, int] = {}
    for table in tables:
        cur.execute(f"DELETE FROM {table} WHERE configuration_uuid = %s::uuid",
                    [str(configuration_uuid)])
        removed[table] = cur.rowcount
    return removed


def _require_header(configuration_uuid: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Найти строку заголовка по uuid; вернуть карточку или причину отказа.

    Заголовок обязателен: свойства вида — второй шаг того же первого слоя, и строки без
    заголовка нельзя ни показать в карточке конфигурации, ни снять вместе с ней (внешний ключ
    в схеме не поставлен осознанно — V20.1). Ленивый импорт — тот же обход цикла, что у слоёв
    V44/V46/V48/V49/V50/V52.
    """
    from configuration_loader import find_configuration  # ленивый импорт — круг узла V44

    card = find_configuration(configuration_uuid)
    if isinstance(card, dict) and card.get("error"):
        return None, f"Ошибка запроса: {card['error']}"
    if not card:
        return None, (
            f"Строка заголовка конфигурации с uuid {configuration_uuid} в базе не найдена. "
            "Сначала загрузите каталог точкой входа load_1c_catalog_tool(source_path=…): "
            "иначе свойства подписок на события остались бы ни на что не указывающими, а "
            "внешний ключ в схеме не поставлен осознанно (узел V20.1)."
        )
    return card, None


def _stage_failure(reason: str, header: Optional[Dict] = None,
                   status: str = STATUS_ERROR,
                   extra: Optional[List[str]] = None) -> Dict[str, Any]:
    """Отказ стадии в форме закрытого контракта (C1, C3).

    Причина кладётся в ключ `error` замкнутого словаря `event_subscriptions_defaults()`, а
    статус — в `status`: вызывающий отличает «стадия не выполнялась» от «слой отказал» (C2).
    Если заголовок к моменту отказа уже разрешён, он называется: по `configuration_id`
    карточка отличает «заголовка нет» от «заголовок есть, слой отказал по файлам».
    Подсказка о том, чем продолжить, кладётся и в отказ, и в успех: у стадии есть отдельный
    вход `load_event_subscriptions_tool` (шаг П5), и вызывающий обязан знать это из ответа, а
    не из молчания.
    """
    result = event_subscriptions_defaults()
    result["status"] = status
    result["error"] = reason
    result["reason"] = reason
    if header:
        result["configuration_id"] = header.get("id")
        result["configuration_uuid"] = header.get("uuid")
        result["configuration_name"] = header.get("name")
    result["warnings"].append(EVENT_SUBSCRIPTIONS_REPEAT_HINT)
    for warning in extra or []:
        result["warnings"].append(warning)
    return result


def events_summary(rows: List[Dict]) -> Dict[str, int]:
    """Распределение ЗАПИСАННЫХ подписок по именам событий (план, раздел 5).

    Считается по строкам, которые реально записаны, а не по разбору: ответ стадии обязан
    описывать содержимое базы, а не круг выгрузки (приём `separation_summary` V50). Имена вне
    замеренного словаря (18 имён — замер 2.3) попадают в этот же словарь и различимы
    словарём `unknown_event_names`, который даёт разбор: «имя известно, но редкое» и «имя вне
    словаря» являются разными ответами, и оба называются (Q6, вариант A).
    """
    counts: Dict[str, int] = {}
    for row in rows:
        event = row.get("event")
        if not event:
            continue
        counts[str(event)] = counts.get(str(event), 0) + 1
    return counts


def handler_summary(rows: List[Dict]) -> Dict[str, int]:
    """Число заполненных значений обработчика и число уникальных по ЗАПИСАННЫМ строкам.

    Оба числа держит ответ стадии, а не комментарий, потому что именно они являются основанием
    отсутствия внешнего ключа: связь не один-к-одному (248 уникальных обработчиков при 311
    подписках в BGU2 — замер 2.3, Q2 решение оператора). Строки с состояниями `absent` и
    `empty_value` в подсчёт не входят: значения у них нет (CHECK
    `event_subscriptions_handler_state_matches_value` держит это структурой строки), и «модуль
    неизвестен» нельзя считать уникальным модулем.
    """
    distinct = set()
    total = 0
    for row in rows:
        handler = row.get("handler")
        if not handler:
            continue
        total += 1
        distinct.add(str(handler))
    return {"total": total, "distinct": len(distinct)}


def source_summary(source_rows: List[Dict]) -> Dict[str, Any]:
    """Уникальные цели и максимум записей на подписку по ЗАПИСАННЫМ строкам блока `<Source>`.

    Уникальность считается по `target_full_name`: для именованной цели это точечное имя
    индекса состава, для голой — вид метаданных целиком (разбор кладёт его в ту же колонку),
    поэтому мера честна для обеих форм значения (M5). Отдельного счётчика «цель встречается в
    нескольких подписках» здесь нет: он не входит в контракт и не является состоянием выгрузки.
    """
    per_subscription: Dict[str, int] = {}
    distinct = set()
    for row in source_rows:
        per_subscription[str(row.get("subscription_full_name"))] = (
            per_subscription.get(str(row.get("subscription_full_name")), 0) + 1)
        if row.get("target_full_name"):
            distinct.add(str(row["target_full_name"]))
    return {
        "sources_distinct": len(distinct),
        "max_sources_per_subscription": max(per_subscription.values()) if per_subscription else 0,
    }


def observation_counts(observations: List[Any]) -> Dict[str, int]:
    """Счётчик наблюдений круга по роду (`counts_by_observation` контракта).

    Пары `[род, подробности]` даёт разбор (`iter_registration_files` и
    `read_registration_file`); без счётчика «каталог отсутствует» и «в каталоге файл не того
    вида» различались бы только перечнем, а карточка обязана называть и число по каждому роду
    (C1). Пустой ответ означает «наблюдений нет» — это состояние, а не пропуск.
    """
    counts: Dict[str, int] = {}
    for item in observations or []:
        kind = str(item[0]) if isinstance(item, (list, tuple)) and item else "unknown"
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def circle_discrepancy_counts(index_only: List[Any], file_only: List[Any],
                              uuid_mismatch: List[Any]) -> Dict[str, int]:
    """Числа расхождений двух ног круга по замкнутому словарю состояний (C1).

    Перечисленные списки дают примеры (`MAX_EXAMPLES` разбора), а число обязано быть полным:
    `*_total` отдельно от длины примеров — приём V48. Нули являются ответом: четыре
    замеренные выгрузки дают ноль по всем трём состояниям (замер 1.3), и молчать об этом
    значило бы не отличать «расхождений нет» от «сверку не делали». Словарь состояний
    берётся замкнутой константой разбора (`CIRCLE_DISCREPANCIES`), а не списком имён здесь:
    второе перечисление состояний в проекте разъезжается с первым.
    """
    listed = dict(zip(CIRCLE_DISCREPANCIES, (index_only, file_only, uuid_mismatch)))
    return {state: len(listed.get(state) or []) for state in CIRCLE_DISCREPANCIES}


def load_event_subscriptions(source_path: str,
                             configuration_uuid: Optional[str] = None,
                             changed_at=None) -> Dict[str, Any]:
    """Загрузить свойства подписок на события конфигурации (узел V53, стадия S4h).

    Порядок: каталог → uuid из `Configuration.xml` (или сверка переданного) → проверка, что
    заголовок загружен → индекс состава из `configuration_objects` (сверка файлов с перечнем и
    разрешение целей блока `<Source>`, Н6) → перечень общих модулей текущей ревизии
    (разрешение обработчика, Q2) → разбор каталога вида → **одна транзакция**: `DELETE` по
    uuid + вставки двух таблиц → отдельной транзакцией `ANALYZE` (мера V46).

    Групп `kinds` у стадии нет (Q8, вариант A): строка источника существует только через id
    строки подписки (Q4, вариант A), поэтому частичная запись круга описывала бы состав,
    которого в выгрузке нет.

    Отказ разбора любого файла круга останавливает стадию ДО записи: половина круга в базе
    читалась бы как полный состав вида (приём V12/V46/V48/V49/V50/V52). Отсутствие каталога
    `EventSubscriptions/` — не отказ, а ответ о выгрузке: `files_found = 0` с наблюдением
    `directory_missing`, потому что у конфигурации без подписок их действительно нет (KomMag
    даёт каталог без файлов — замер 1.1, и это тоже ответ о выгрузке, а не отказ).

    `changed_at` передаёт конвейер: строки одной загрузки обязаны нести одну метку (M2), а не
    время своей транзакции. Пустое значение — своя метка вызова (одиночный прогон слоя).
    Строки блока `<Source>` метку не несут: колонок ревизии у таблицы нет
    (`CONFIGURATION_UNVERSIONED_TABLES`), их текущность читается витриной связкой по
    `event_subscription_id` (Q4, вариант A).

    Порядок записи держается иерархией данных, а не удобством: сначала строки подписок
    (`insert_ids`, `RETURNING id`), затем строки блока `<Source>`, ссылающиеся на id этих
    ревизий. Всё это одной транзакцией: отказ на середине оставил бы в базе подписки без
    круга целей, то есть состав, которого в выгрузке нет.
    """
    uuid_info = configuration_uuid_from_layout(source_path)
    if "uuid" not in uuid_info:
        return _stage_failure(uuid_info.get("error")
                             or f"Каталог выгрузки не читается: {source_path}")
    layout_uuid = str(uuid_info["uuid"])
    if configuration_uuid and str(configuration_uuid).strip().lower() != layout_uuid.lower():
        # Два источника одного факта указали на разные конфигурации: молча выбрать один —
        # значит записать свойства чужой конфигурации (тот же отказ, что у слоёв
        # V44/V46/V48/V49/V50/V52).
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
                                  "reason": None, "rows": []}
    modules_info: Dict[str, Any] = {"available": False, "count": 0, "reason": None,
                                    "names": set()}
    # Две ноги чтения читаются отдельными транзакциями: отказ одной из них не обязан лишать
    # вторую уже прочитанного — стадия обязана назвать каждое состояние отдельно (C2).
    try:
        with transaction() as cur:
            index_info = read_index_records(cur, int(header["id"]))
    except Exception as exc:  # noqa: BLE001 — индекс читается до записи, отказ называется им
        index_info["reason"] = f"чтение {OBJECTS_TABLE} не удалось: {exc}"
    try:
        with transaction() as cur:
            modules_info = read_common_module_names(cur, configuration_uuid)
    except Exception as exc:  # noqa: BLE001 — перечень читается до записи, тем же порядком
        modules_info["reason"] = f"чтение {COMMON_MODULES_VIEW} не удалось: {exc}"

    collected = collect_event_subscriptions(source_path, index_rows=index_info["rows"],
                                           common_module_names=modules_info["names"])
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


    # Ключ конфигурации знает вызывающий, а не XML файла — тот же порядок, что у писателей
    # свойств V46, модулей корня V44, параметров сеанса V48, ролей V49, общих реквизитов V50
    # и критериев отбора V52.
    subscription_rows = [dict(row, configuration_uuid=configuration_uuid)
                         for row in (collected.get("rows") or [])]
    source_rows = [dict(row, configuration_uuid=configuration_uuid)
                   for row in (collected.get("source_rows") or [])]

    # Полнота связывания проверяется ДО транзакции: строка блока <Source> обязана ссылаться на
    # строку подписки этого же круга (Q4, вариант A), и молча отбросить её значило бы назвать
    # неполный круг полным. Ключом служит имя подписки — именно его несёт строка источника в
    # колонке `subscription_full_name` (прецедент `attribute_full_name` V50,
    # `criterion_full_name` V52); иерархии раскладки у вида нет, поэтому имя совпадает с
    # `object_name` (замер 1.2).
    link_keys = [str(row.get("object_name") or "") for row in subscription_rows]
    known = set(link_keys)
    if len(known) != len(link_keys):
        duplicated = sorted({key for key in link_keys if link_keys.count(key) > 1})
        return _stage_failure(
            f"Круг не записан: разбор дал {len(link_keys)} строк подписок с "
            f"повторяющимися именами ({', '.join(duplicated[:5])}) — строки блока <Source> "
            "нельзя связать однозначно (замер 1.3 даёт уникальность имён внутри выгрузки), "
            "ни одна строка круга не записана",
            header=header,
        )
    unbound = sorted({str(row.get("subscription_full_name")) for row in source_rows
                      if row.get("subscription_full_name") not in known})
    if unbound:
        return _stage_failure(
            f"Круг не записан: {len(unbound)} строка(ов) блока <Source> остались без строки "
            f"подписки ({', '.join(unbound[:5])}) — это внутреннее противоречие разбора, "
            "а не состояние выгрузки; ни одна строка круга не записана",
            header=header,
        )

    # Один штамп времени на всё событие загрузки (M2): версионируемая таблица одной загрузки
    # не должна нести две метки. Строки блока <Source> метку не получают — колонок ревизии у
    # них нет (`CONFIGURATION_UNVERSIONED_TABLES`).
    moment = stamp_revision_rows(subscription_rows, revision_no=FIRST_REVISION,
                                 changed_by=CHANGED_BY_LOAD, changed_at=changed_at)

    removed: Dict[str, int] = {}
    written: Dict[str, int] = {table: 0 for table in EVENT_SUBSCRIPTIONS_TABLES}
    try:
        with transaction() as cur:
            removed = remove_event_subscriptions(cur, configuration_uuid)
            # Подписки — по одной строке с RETURNING id: строка блока <Source> ссылается на
            # ЧИСЛОВОЙ id этой ревизии (Q4, вариант A), а `insert_many` id не возвращает.
            # Порядок `insert_ids` совпадает с порядком `subscription_rows` — связь держится
            # им, а не угадыванием. Прецедент — `insert_ids` слоёв V49/V50.
            subscription_ids = ES_WRITERS[SUBSCRIPTIONS_TABLE].insert_ids(cur, subscription_rows)
            if len(subscription_ids) != len(subscription_rows):
                raise RuntimeError(
                    f"писатель вернул {len(subscription_ids)} id для {len(subscription_rows)} "
                    f"строк таблицы {SUBSCRIPTIONS_TABLE} — связать блок <Source> нечем"
                )
            written[SUBSCRIPTIONS_TABLE] = len(subscription_ids)
            ids_by_key = dict(zip(link_keys, subscription_ids))
            for row in source_rows:
                row["event_subscription_id"] = ids_by_key[str(row.get("subscription_full_name"))]
            written[SOURCES_TABLE] = ES_WRITERS[SOURCES_TABLE].insert_many(cur, source_rows)
    except Exception as exc:  # noqa: BLE001 — заголовок уже разрешён, отказ называется им
        return _stage_failure(
            f"Ошибка записи: {exc}. Транзакция отменена целиком: в базе остались прежние "
            f"строки круга (снятые этим вызовом — {sum(removed.values())}), новых нет",
            header=header,
        )

    # ── статистика записанных таблиц (мера V46) ─────────────────────────────────────────
    # Отдельная транзакция ПОСЛЕ фиксации записи: планировщик обязан увидеть строки, иначе
    # первый же читатель витрин текущего состояния платит минутами за счётчик (замер V46 на
    # BGU2: 8 мин 25 с против 7 мс после ANALYZE). Отказ статистики отказом загрузки не
    # является: строки зафиксированы, и это предупреждение.
    statistics_refreshed = 0
    try:
        with transaction() as cur:
            refresh_table_statistics(cur, EVENT_SUBSCRIPTIONS_TABLES)
            statistics_refreshed = len(EVENT_SUBSCRIPTIONS_TABLES)
    except Exception as exc:  # noqa: BLE001 — ответ описывает запись, а не статистику
        warnings.append(
            f"статистика таблиц {', '.join(EVENT_SUBSCRIPTIONS_TABLES)} не обновлена: {exc}. "
            "Строки записаны, но читатель витрин текущего состояния получит план по пустой "
            "статистике: счётчики на большой выгрузке выполняются минутами вместо "
            "миллисекунд"
        )


    result = event_subscriptions_defaults()
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
        "common_modules_available": bool(modules_info["available"]),
        "rows_written": int(sum(written.values())),
        "event_subscriptions_written": int(written[SUBSCRIPTIONS_TABLE]),
        "sources_written": int(written[SOURCES_TABLE]),
        "removed_previous": int(sum(removed.values())),
        "removed_by_table": removed,
        "written_by_table": written,
        "statistics_refreshed": statistics_refreshed,
    })

    # Агрегаты, которых разбор не даёт, считаются по ЗАПИСАННЫМ строкам: ответ стадии описывает
    # содержимое базы, а не круг выгрузки (приём `separation_summary` V50). Словари состояний
    # замкнуты контрактом, поэтому пустой словарь здесь — состояние «записей нет», а не
    # пропуск блока (C1).
    result["counts_by_observation"] = observation_counts(collected.get("observations"))
    result["counts_by_circle_discrepancy"] = circle_discrepancy_counts(
        result["index_only"], result["file_only"], result["uuid_mismatch"])
    result["events_by_name"] = events_summary(subscription_rows)
    handlers = handler_summary(subscription_rows)
    result["handlers_total"] = handlers["total"]
    result["handlers_distinct"] = handlers["distinct"]
    sources = source_summary(source_rows)
    result["sources_distinct"] = sources["sources_distinct"]
    result["max_sources_per_subscription"] = sources["max_sources_per_subscription"]

    # Подсказка о том, чем продолжить, кладётся и в успех, и в отказ: у стадии есть
    # отдельный вход `load_event_subscriptions_tool` (шаг П5), и вызывающий обязан знать это
    # из ответа, а не из молчания (прецедент COMMON_ATTRIBUTES_REPEAT_HINT узла V50).
    warnings.append(EVENT_SUBSCRIPTIONS_REPEAT_HINT)
    if not index_info["available"] and index_info.get("reason"):
        warnings.append(
            f"Индекс состава: {index_info['reason']} — состояния `index_only` и `file_only` "
            "при этом невыразимы, а цели блока <Source> остаются неразрешёнными записями "
            "(Q3): «объекта нет в перечне» от «перечень этой конфигурации не загружен» не "
            "отличить, и голая ссылка получает `type_absent` как «в прочитанном индексе вида "
            "нет», а не как «вида нет в конфигурации»"
        )
    if not modules_info["available"] and modules_info.get("reason"):
        warnings.append(
            f"Перечень общих модулей: {modules_info['reason']} — все обработчики остались в "
            f"состоянии `unresolved` (число "
            f"{int(result.get('handlers_unresolved_total') or 0)}): это «нечем разрешить», а "
            "не «модуля нет в конфигурации» (правило C2). Загружите свойства общих модулей "
            "точкой входа load_configuration_object_properties_tool(source_path=…) и "
            "повторите стадию"
        )
    for observation, detail in (collected.get("observations") or []):
        if observation == "directory_missing":
            warnings.append(
                f"Каталог {collected.get('directory')}/ в выгрузке отсутствует — подписок на "
                "события у этой конфигурации нет, и нули таблиц являются ответом о выгрузке, "
                "а не отказом стадии (замер 1.1 даёт именно такой вид выгрузки)"
            )
        elif observation in ("unexpected_dir", "unexpected_file", "index_child_entry",
                             "index_depth"):
            warnings.append(
                f"Круг шире перечня вида: {observation} — {detail}. У подписки на события "
                "детей нет (замер 1.2: запись вида в индексе состава — самозакрывающийся "
                "элемент, каталогов содержимого ноль), поэтому объект вне перечня является "
                "наблюдением, а не строкой круга: колонок для него в схеме нет, и молчать о "
                "нём нельзя (M2)"
            )
        elif observation in ("source_block_absent", "source_block_empty"):
            warnings.append(
                f"Блок <Source> пуст или отсутствует: {observation} — {detail}. Корпус пустых "
                "блоков не давал ни разу (замер 1.4), поэтому состояние `empty_sources` "
                "называется состоянием строки вида и остаётся границей модели, а не "
                "ожидаемым значением (M4)"
            )
    if index_info["available"] and int(result["index_kind_records"]) != int(
            result.get("files_found") or 0):
        warnings.append(
            f"Записей `EventSubscription.<Имя>` в индексе состава "
            f"{result['index_kind_records']}, файлов регистрации "
            f"{result.get('files_found')} — круги различаются (замер 1.3 даёт равенство на "
            "четырёх выгрузках, поэтому расхождение требует объяснения этим прогоном; "
            "расхождения перечислены ключами `index_only` / `file_only`)"
        )
    if int(result.get("sources_written") or 0) != int(result.get("sources_total") or 0):
        warnings.append(
            f"Разбор дал {result.get('sources_total')} записей блока <Source>, записано "
            f"{result.get('sources_written')} — часть строк в {SOURCES_TABLE} не попала; "
            "связь со строкой вида держится id ревизии (Q4), и молчать об этом нельзя"
        )
    declared = sum(int(row.get("source_count") or 0) for row in subscription_rows)
    if declared != int(result.get("sources_written") or 0):
        warnings.append(
            f"Счётчик <Source> по строкам вида даёт {declared}, записанных строк источника "
            f"{result.get('sources_written')} — CHECK "
            "event_subscriptions_source_count_matches_state согласовывает состояние и счётчик "
            "на строке вида, а число строк круга сверяет проверка П6 обходом выгрузки"
        )
    if int(result.get("handlers_unresolved_total") or 0) and modules_info["available"]:
        warnings.append(
            f"{result.get('handlers_unresolved_total')} обработчик(ов) названы `unresolved` "
            "при доступном перечне модулей — форма значения корректна, но модуля нет среди "
            "общих модулей ТЕКУЩЕЙ ревизии этой конфигурации (замер 2.3 даёт ноль таких "
            "случаев, поэтому расхождение требует объяснения этим прогоном)"
        )
    if int(result.get("targets_unresolved_total") or 0):
        warnings.append(
            f"{result.get('targets_unresolved_total')} цель(ей) блока <Source> не разрешены "
            "(состояния `unresolved`/`type_absent`/`unknown_class`/`unknown_form`) — примеры "
            "лежат в ключе `targets_unresolved`, полная мера в "
            "counts_by_target_resolve_state (замер 2.2: `type_absent` 23, прочих ноль)"
        )
    if result.get("duplicate_names"):
        warnings.append(
            f"{len(result['duplicate_names'])} имя подписки встречается в выгрузке более "
            "раза — ключ цепочки (configuration_uuid, object_name, revision_no) принял бы "
            "вторую строку новой ревизией, и стадия называет это отдельно (замер 1.3 даёт "
            "уникальность имён внутри выгрузки)"
        )
    if any(removed.values()):
        warnings.append(
            "Прежние строки свойств подписок на события этой конфигурации сняты перед "
            f"записью: {', '.join(f'{table}={count}' for table, count in removed.items())}. "
            "Идемпотентность держится явным DELETE по configuration_uuid: внешнего ключа и "
            "каскада по конфигурации в схеме нет осознанно (прецедент V20.1); новая ревизия "
            "на повторную загрузку той же выгрузки не заводится — история состояний "
            "принадлежит узлу правки объекта, которого в схеме ещё нет"
        )
    if subscription_rows:
        warnings.append(
            f"Момент загрузки строк подписок — {moment}: той же меткой помечены строки "
            "заголовка и других стадий этого события (M2); строки блока <Source> метку не "
            "несут (своей цепи ревизий у них нет, Q4 вариант A)"
        )
    else:
        warnings.append(
            "Строк подписок этим вызовом не записано: каталог вида пуст или отсутствует "
            f"(файлов {result.get('files_found')}), поэтому и общего момента загрузки вида у "
            "этого события нет — нули таблиц являются ответом о выгрузке"
        )
    for text in (collected.get("warnings") or [])[:10]:
        warnings.append(f"разбор: {text}")
    result["warnings"] = warnings
    return result

