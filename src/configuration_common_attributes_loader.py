#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Загрузчик свойств общих реквизитов (узел V50, шаг П4, 30.10.2026).

Стадия S4e конвейера первого слоя: файлы вида `CommonAttributes` (позиция 2.5 нормативного
списка плана `docs/CONFIGURATION_COMMON_ATTRIBUTES_PLAN.md`) в две таблицы —
`common_attributes` (строка реквизита) и `common_attribute_targets` (строки её применения).
Норматив — тот же план (решения Q1–Q5, Q7, Q9); разбор файлов вида — отдельный модуль
`src/configuration_common_attributes.py` (шаг П2), писатели строк — реестр
`CONFIGURATION_OBJECT_WRITERS` (шаг П3).

Почему стадия отдельная, а не пятый вид S4 и не расширение S4d (прецеденты Q5 узлов V48 и
V49): правило C3 требует своего ключа ответа `common_attributes`; порядок `STAGES`
повторяет порядок нормативного списка (2.5 идёт сразу за 2.4), поэтому S4e стоит между S4d
и S4b. Круг стадии S4 (`CHILD_TABLES`) отделён от круга версионности шагом П3: регистрация
таблиц вида в `CONFIGURATION_VERSIONED_TABLES` молча добавила бы их к чужой стадии.

Групп запроса (`kinds`) у вида нет — в отличие от V46 и V49 — и это решение, а не упущение:
строка применения существует только через id строки реквизита (Q1, вариант A), поэтому
состояния «записать реквизиты без применения» в модели нет; отдельный вход дозагружает весь
круг сразу (Q10, вариант A: порога, при котором раздельная дозагрузка была бы оправдана, не
замерено).

Что здесь происходит и чего здесь нет:

* круг задают каталог `CommonAttributes/` (плоский: подкаталогов, форм, макетов и модулей у
  вида нет — замер 2.1) и записи индекса состава того же вида (`CommonAttribute.<Имя>`);
  расхождение двух источников называется `index_only` / `file_only` / `uuid_mismatch` —
  четыре замеренные выгрузки дают нули, и нули обязаны быть названы (замер 2.9);
* строка применения ссылается на ЧИСЛОВОЙ id ревизии строки реквизита (Q2, вариант A):
  своей цепи ревизий у неё нет, поэтому реквизиты вставляются `insert_ids()` (по одной
  строке, `RETURNING id`), а полученный id подставляется в строки применения; ключом
  подстановки служит индексное имя `CommonAttribute.<Имя>`, которое и несёт строка
  применения (прецедент `role_name` узла V49);
* `common_attribute_targets` не штампуется ревизией (колонок `revision_no`/`changed_*` нет —
  исключение `CONFIGURATION_UNVERSIONED_TABLES`), строка реквизита — штампуется;
* снятие круга начинается с `common_attribute_targets`: её FK
  `common_attribute_targets_common_attribute_id_fkey` объявлен с `ON DELETE CASCADE` (П1), и
  каскад снял бы применение молча, без точного счётчика — вызывающий обязан назвать полное
  состояние, снятое `force=True` (M7);
* объекты, на которые указывают цели применения и ссылки разделения, узел не загружает: они
  остаются ссылками на строки индекса состава (Q3), видовых узлов для них нет.

Идемпотентность держится явным `DELETE` по `configuration_uuid` (внешнего ключа на
`configurations` и каскада по нему в схеме нет осознанно — прецеденты V20.1, V44, V46, V48,
V49), а не новой ревизией: повтор той же выгрузки не создаёт истории, снятые строки названы
в ответе. Ключом цепочки строки реквизита является (`configuration_uuid`, `object_name`,
`revision_no`) — замер 2.8: семь имён общих реквизитов совпадают в BGU2 и BP3, и без ключа
конфигурации две выгрузки слились бы в одну строку.

Круг пишется одной транзакцией, и отказ разбора любого файла круга останавливает стадию ДО
записи: в базе не остаётся половины строк (приём V12/V46/V48/V49). Молча записать то, что
разобралось, означало бы назвать неполный круг полным.

После фиксации загрузчик пересобирает статистику двух таблиц (`refresh_table_statistics` —
мера V46): без статистики счётчики по витринам текущего состояния на большой выгрузке
выполняются минутами (замер V46 на BGU2: 8 мин 25 с против 7 мс). Отказ статистики отказом
загрузки не является — строки зафиксированы, и это предупреждение.

Прогон шага: `python _v50_p4_loader_probe.py MinCfg KomMag`, затем отдельно BGU2 и BP3
(прогоны, меняющие общее состояние БД, не параллелят).
"""
from typing import Any, Dict, List, Optional, Tuple

from configuration_common_attributes import (
    SEPARATION_BLOCKS,
    collect_common_attributes,
    index_object_name,
    kind_index_rows,
)
from configuration_load_contract import (
    COMMON_ATTRIBUTES_REPEAT_HINT,
    COMMON_ATTRIBUTES_TABLES,
    STATUS_ERROR,
    STATUS_OK,
    common_attributes_defaults,
    common_attributes_separation_defaults,
)
from configuration_object_properties_loader import refresh_table_statistics
from configuration_root_module_loader import configuration_uuid_from_layout
from current_revision import CHANGED_BY_LOAD, FIRST_REVISION, stamp_revision_rows
from external_db import transaction
from external_table_writer import CONFIGURATION_OBJECT_WRITERS

OBJECTS_TABLE = "configuration_objects"
TARGETS_TABLE = "common_attribute_targets"
ATTRIBUTES_TABLE = "common_attributes"

# Писатели двух таблиц берутся общим реестром, а не импортом классов (правило п.6 слоя):
# ошибка выбора превращается в запись не в ту таблицу, а реестр уже знает, какая таблица
# версионируется своей цепочкой, а какая — нет (`CONFIGURATION_UNVERSIONED_TABLES`).
CA_WRITERS = {table: CONFIGURATION_OBJECT_WRITERS[table]
              for table in COMMON_ATTRIBUTES_TABLES}

# Порядок снятия круга — не порядок `COMMON_ATTRIBUTES_TABLES`: `common_attribute_targets.
# common_attribute_id` ссылается на строку реквизита с `ON DELETE CASCADE`, и каскад снял бы
# применение молча, без точного счётчика. Явный `DELETE` первым держит честное число снятых
# строк (M7) и не зависит от того, поставлен ли каскад в данной базе (миграция V50 могла не
# применяться). Тот же приём, что `REMOVE_ORDER` узла V49.
REMOVE_ORDER: Tuple[str, ...] = (TARGETS_TABLE, ATTRIBUTES_TABLE)

# Колонки индекса состава, которые нужны разбору вида: `name`/`object_name` — ключ сверки
# (`CommonAttribute.<Имя>`), `uuid` — цель ссылочного типа и сверка uuid файла с записью
# перечня, `child_type` — различение записей одного имени, `depth`/`parent_name` — состояние
# «запись индекса имеет глубину» (иерархии раскладки у вида нет, замер 2.9). Фильтра по типу
# вида здесь нет намеренно: разрешение целей применения и ссылок разделения обязано видеть
# записи ЛЮБОГО вида (замер 2.5: цели ведут на справочники, константы, планы обмена и
# характеристики), а свой круг вида отбирает сам разбор (`kind_index_rows`). Тот же приём,
# что `read_index_records` узлов V46, V48 и V49: источник — строки БД, а не повторный разбор
# `ConfigDumpInfo.xml`.
INDEX_ROW_COLUMNS: Tuple[str, ...] = (
    "name", "object_id", "object_type", "object_name", "child_type", "parent_name", "depth",
    "uuid",
)

# Ключи сводки разбора, совпадающие с ключами контракта по имени (один словарь на разбор и
# на ответ): копируются только они — неперечисленный ключ контракта читается нулём (C1), а
# незнакомый ключ разбора не попадает в ответ, которого карточка не обещала (прецедент
# `SUMMARY_KEYS` узлов V46/V48/V49). Ключей `rows` и `targets` здесь нет: строки записи идут
# в писатели, а не в ответ стадии; `success` разбора — внутренний признак круга, стадия
# отвечает своими `success` и `status`.
SUMMARY_KEYS: Tuple[str, ...] = (
    "directory", "files_found", "files_read", "files_failed", "observations",
    "index_only", "file_only", "uuid_mismatch",
    "counts_by_properties_state", "unknown_properties", "unknown_value_properties",
    "unexpected_tags",
    "counts_by_type_state", "types_multiplicity", "types_by_class", "types_total",
    "types_parsed", "types_object_ref_resolved", "types_unresolved_total",
    "types_unresolved", "value_tag_mismatch",
    "counts_by_content_state", "targets_total", "targets_distinct",
    "max_targets_per_file", "counts_by_use_state", "counts_by_target_resolve_state",
    "targets_by_kind", "duplicate_targets", "unresolved_targets",
    "separation_parsed", "separation_empty", "separation_unknown_form", "unresolved_refs",
    "namespace_prefixes",
)


def read_index_records(cur, configuration_id: int) -> Dict[str, Any]:
    """Записи индекса состава этой конфигурации из `configuration_objects` (Н6).

    Пустой ответ означает «индекс недоступен», а не «объектов нет»: при недоступном индексе
    сверка файлов с перечнем и разрешение целей применения и ссылок разделения невыразимы, и
    вызывающий обязан назвать это состоянием загрузки, а не нулями (тот же контракт, что у
    слоёв V46, V47, V48, V49).

    Своего вида считается ОДНО число (`CommonAttribute.<Имя>`): в отличие от ролей V49, у
    вида нет второго слоя файла содержимого — метаданные и перечень применения лежат в одном
    файле регистрации (замеры 2.1 и 2.4).
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
            "разрешение целей применения невозможны"
        )
        return {"rows": [], **info}
    info.update({
        "available": True,
        "row_count": len(records),
        "kind_count": len(kind_index_rows(records)),
    })
    return {"rows": records, **info}


def remove_common_attributes(cur, configuration_uuid: str,
                             tables: Tuple[str, ...] = REMOVE_ORDER) -> Dict[str, int]:
    """Снять строки общих реквизитов этой конфигурации (внутри текущей транзакции).

    Очистка обязана быть явной: внешнего ключа на `configurations` и каскада по нему в
    схеме нет осознанно (прецеденты V20.1, V44, V46, V48, V49), иначе строки пережили бы
    снятие заголовка и стали бы сиротами, которые нельзя ни показать в карточке
    конфигурации, ни отличить от строк другой конфигурации. Этим же фильтром
    (`configuration_uuid`) держится снятие в `_remove_rows` конвейера — иначе `force=True`
    оставил бы в базе прежний состав вида (для BP3 это 7 строк реквизитов и 817 строк
    применения).

    Порядок задаёт `REMOVE_ORDER`, а не `COMMON_ATTRIBUTES_TABLES`: применение снимается ДО
    реквизитов, потому что её собственный FK
    `common_attribute_targets_common_attribute_id_fkey` объявлен с `ON DELETE CASCADE` —
    каскад снял бы строки молча, и число в ответе было бы неправдой (M7).
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
    заголовка нельзя ни показать в карточке конфигурации, ни снять вместе с ней (внешний
    ключ в схеме не поставлен осознанно — V20.1). Ленивый импорт — тот же обход цикла, что
    у слоёв V44/V46/V48/V49.
    """
    from configuration_loader import find_configuration  # ленивый импорт — круг узла V44

    card = find_configuration(configuration_uuid)
    if isinstance(card, dict) and card.get("error"):
        return None, f"Ошибка запроса: {card['error']}"
    if not card:
        return None, (
            f"Строка заголовка конфигурации с uuid {configuration_uuid} в базе не найдена. "
            "Сначала загрузите каталог точкой входа load_1c_catalog_tool(source_path=…): "
            "иначе свойства общих реквизитов остались бы ни на что не указывающими, а "
            "внешний ключ в схеме не поставлен осознанно (узел V20.1)."
        )
    return card, None


def _stage_failure(reason: str, header: Optional[Dict] = None,
                   status: str = STATUS_ERROR,
                   extra: Optional[List[str]] = None) -> Dict[str, Any]:
    """Отказ стадии в форме закрытого контракта (C1, C3).

    Причина кладётся в ключ `error` замкнутого словаря `common_attributes_defaults()`, а
    статус — в `status`: вызывающий отличает «стадия не выполнялась» от «слой отказал» (C2).
    Если заголовок к моменту отказа уже разрешён, он называется: по `configuration_id`
    карточка отличает «заголовка нет» от «заголовок есть, слой отказал по файлам».
    Подсказка о том, чем продолжить, кладётся и в отказ, и в успех: у стадии есть отдельный
    вход `load_common_attributes_tool` (шаг П5), и вызывающий обязан знать это из ответа, а
    не из молчания.
    """
    result = common_attributes_defaults()
    result["status"] = status
    result["error"] = reason
    result["reason"] = reason
    if header:
        result["configuration_id"] = header.get("id")
        result["configuration_uuid"] = header.get("uuid")
        result["configuration_name"] = header.get("name")
    result["warnings"].append(COMMON_ATTRIBUTES_REPEAT_HINT)
    for warning in extra or []:
        result["warnings"].append(warning)
    return result


def separation_summary(rows: List[Dict]) -> Dict[str, Any]:
    """Сводка трёх блоков разделения по записанным строкам реквизитов (план, раздел 5).

    Разбор даёт агрегат по всем трём блокам (`separation_parsed` / `separation_empty` /
    `separation_unknown_form`), а ответ стадии обязан называть каждый блок отдельно: «блока
    нет» (12 из 16 файлов на каждый блок по замеру 2.7) и «блок есть, цель неразрешима» —
    разные факты, и по агрегату их не отличить (C2). Считается по строкам, которые реально
    записаны, а не по разбору: иначе ответ описывал бы круг выгрузки, а не содержимое базы.
    """
    summary = {block: common_attributes_separation_defaults()
               for block in SEPARATION_BLOCKS}
    for block in SEPARATION_BLOCKS:
        parse_counts = summary[block]["by_parse_state"]
        resolve_counts = summary[block]["by_resolve_state"]
        for row in rows:
            state = row.get(block + "_parse_state")
            if state in parse_counts:
                parse_counts[state] += 1
            resolve_state = row.get(block + "_resolve_state")
            if resolve_state in resolve_counts:
                resolve_counts[resolve_state] += 1
    return summary


def item_conditional_summary(target_rows: List[Dict]) -> Dict[str, int]:
    """Распределение состояний условия разделения позиции по записанным строкам применения.

    Колонка `conditional_separation_state` есть у каждой строки применения, а разбора такой
    сводки не даёт (агрегат относится к строкам реквизита). Между тем пустой самозакрывающийся
    тег во всех 1 512 строках корпуса (замер 2.4) — именно то, что обязан отличить читатель
    карточки от «условия нет в таблице»; нулевой контракт состояния при этом держится
    словарём разбора (`ITEM_COND_STATES`), а не списком, придуманным здесь.
    """
    counts: Dict[str, int] = {}
    for row in target_rows:
        state = row.get("conditional_separation_state")
        counts[state] = counts.get(state, 0) + 1
    return counts


def load_common_attributes(source_path: str,
                           configuration_uuid: Optional[str] = None,
                           changed_at=None) -> Dict[str, Any]:
    """Загрузить свойства общих реквизитов конфигурации (узел V50, стадия S4e).

    Порядок: каталог → uuid из `Configuration.xml` (или сверка переданного) → проверка, что
    заголовок загружен → индекс состава из `configuration_objects` (сверка файлов с перечнем
    и разрешение целей применения и ссылок разделения, Н6) → разбор каталога вида →
    **одна транзакция**: `DELETE` по uuid + вставки двух таблиц → отдельной транзакцией
    `ANALYZE` (мера V46).

    Групп `kinds` у стадии нет (Q10, вариант A): строка применения существует только через id
    строки реквизита (Q1, вариант A), поэтому частичная запись круга описывала бы состав,
    которого в выгрузке нет.

    Отказ разбора любого файла круга останавливает стадию ДО записи: половина круга в базе
    читалась бы как полный состав вида (приём V12/V46/V48). Отсутствие каталога
    `CommonAttributes/` — не отказ, а ответ о выгрузке: `files_found = 0` с наблюдением
    `directory_missing` (Q9), потому что у конфигурации без общих реквизитов их действительно
    нет, и KomMag даёт именно это (замер 2.9).

    `changed_at` передаёт конвейер: строки одной загрузки обязаны нести одну метку (M2), а не
    время своей транзакции. Пустое значение — своя метка вызова (одиночный прогон слоя).
    Строки применения метку не несут: колонок ревизии у таблицы нет
    (`CONFIGURATION_UNVERSIONED_TABLES`), их текущность читается связкой по
    `common_attribute_id` (Q2, вариант A).

    Порядок записи держается иерархией данных, а не удобством: сначала строки реквизитов
    (`insert_ids`, `RETURNING id`), затем строки применения, ссылающиеся на id этих ревизий.
    Всё это одной транзакцией: отказ на середине оставил бы в базе реквизиты без применения,
    то есть состав, которого в выгрузке нет.
    """
    uuid_info = configuration_uuid_from_layout(source_path)
    if "uuid" not in uuid_info:
        return _stage_failure(uuid_info.get("error")
                             or f"Каталог выгрузки не читается: {source_path}")
    layout_uuid = str(uuid_info["uuid"])
    if configuration_uuid and str(configuration_uuid).strip().lower() != layout_uuid.lower():
        # Два источника одного факта указали на разные конфигурации: молча выбрать один —
        # значит записать свойства чужой конфигурации (тот же отказ, что у слоёв
        # V44/V46/V48/V49).
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
    try:
        with transaction() as cur:
            index_info = read_index_records(cur, int(header["id"]))
    except Exception as exc:  # noqa: BLE001 — индекс читается до записи, отказ называется им
        index_info["reason"] = f"чтение {OBJECTS_TABLE} не удалось: {exc}"

    collected = collect_common_attributes(source_path, index_rows=index_info["rows"])
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

    # Ключ конфигурации знает вызывающий, а не XML файла — тот же порядок, что у писателей
    # свойств V46, модулей корня V44, параметров сеанса V48 и ролей V49.
    attribute_rows = [dict(row, configuration_uuid=configuration_uuid)
                      for row in (collected.get("rows") or [])]
    target_rows = [dict(row, configuration_uuid=configuration_uuid)
                   for row in (collected.get("targets") or [])]

    # Полнота связывания проверяется ДО транзакции: строка применения обязана ссылаться на
    # строку реквизита этого же круга (Q1, вариант A), и молча отбросить её значило бы
    # назвать неполный круг полным. Ключом служит индексное имя `CommonAttribute.<Имя>` —
    # именно в этой форме связь несёт строка применения (прецедент `role_name` узла V49).
    link_keys = [index_object_name(str(row.get("object_name") or ""))
                 for row in attribute_rows]
    known = set(link_keys)
    if len(known) != len(link_keys):
        duplicated = sorted({key for key in link_keys if link_keys.count(key) > 1})
        return _stage_failure(
            f"Круг не записан: разбор дал {len(link_keys)} строк реквизитов с "
            f"повторяющимися именами ({', '.join(duplicated[:5])}) — строки применения "
            "нельзя связать однозначно (замер 2.8 даёт уникальность имён внутри выгрузки), "
            "ни одна строка круга не записана",
            header=header,
        )
    unbound = sorted({str(row.get("attribute_full_name")) for row in target_rows
                      if row.get("attribute_full_name") not in known})
    if unbound:
        return _stage_failure(
            f"Круг не записан: {len(unbound)} строка(ов) применения остались без строки "
            f"реквизита ({', '.join(unbound[:5])}) — это внутреннее противоречие разбора, "
            "а не состояние выгрузки; ни одна строка круга не записана",
            header=header,
        )

    # Один штамп времени на всё событие загрузки (M2): версионируемая таблица одной загрузки
    # не должна нести две метки. Строки применения метку не получают — колонок ревизии у них
    # нет (исключение `CONFIGURATION_UNVERSIONED_TABLES`).
    moment = stamp_revision_rows(attribute_rows, revision_no=FIRST_REVISION,
                                 changed_by=CHANGED_BY_LOAD, changed_at=changed_at)

    removed: Dict[str, int] = {}
    written: Dict[str, int] = {table: 0 for table in COMMON_ATTRIBUTES_TABLES}
    try:
        with transaction() as cur:
            removed = remove_common_attributes(cur, configuration_uuid)
            # Реквизиты — по одной строке с RETURNING id: строка применения ссылается на
            # ЧИСЛОВОЙ id этой ревизии (Q2, вариант A), а `insert_many` id не возвращает.
            # Порядок `insert_ids` совпадает с порядком `attribute_rows` — связь держится им,
            # а не угадыванием (строк максимум 7 на замеренных выгрузках, цена поштучной
            # вставки невелика). Прецедент — `insert_ids` слоя V49.
            attribute_ids = CA_WRITERS[ATTRIBUTES_TABLE].insert_ids(cur, attribute_rows)
            if len(attribute_ids) != len(attribute_rows):
                raise RuntimeError(
                    f"писатель вернул {len(attribute_ids)} id для {len(attribute_rows)} "
                    f"строк таблицы {ATTRIBUTES_TABLE} — связать применение нечем"
                )
            written[ATTRIBUTES_TABLE] = len(attribute_ids)
            ids_by_key = dict(zip(link_keys, attribute_ids))
            for row in target_rows:
                row["common_attribute_id"] = ids_by_key[str(row.get("attribute_full_name"))]
            written[TARGETS_TABLE] = CA_WRITERS[TARGETS_TABLE].insert_many(cur, target_rows)
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
    # является: строки зафиксированы, и состояние ответа от него не меняется.
    statistics_refreshed = 0
    try:
        with transaction() as cur:
            refresh_table_statistics(cur, COMMON_ATTRIBUTES_TABLES)
            statistics_refreshed = len(COMMON_ATTRIBUTES_TABLES)
    except Exception as exc:  # noqa: BLE001 — ответ описывает запись, а не статистику
        warnings.append(
            f"статистика таблиц {', '.join(COMMON_ATTRIBUTES_TABLES)} не обновлена: {exc}. "
            "Строки записаны, но читатель витрин текущего состояния получит план по пустой "
            "статистике: счётчики на большой выгрузке выполняются минутами вместо "
            "миллисекунд"
        )

    result = common_attributes_defaults()
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
        "attributes_written": int(written[ATTRIBUTES_TABLE]),
        "targets_written": int(written[TARGETS_TABLE]),
        "removed_previous": int(sum(removed.values())),
        "removed_by_table": removed,
        "written_by_table": written,
        "statistics_refreshed": statistics_refreshed,
    })
    # Сводка по блокам разделения и по условию разделения позиции считается по ЗАПИСАННЫМ
    # строкам: ответ стадии описывает содержимое базы, а не круг выгрузки (иначе нули
    # несуществующих строк читались бы как нули состояний таблицы).
    result["separation_by_block"] = separation_summary(attribute_rows)
    cond_state = result["counts_by_item_cond_state"]
    for state, count in item_conditional_summary(target_rows).items():
        cond_state[state] = cond_state.get(state, 0) + count
    unresolved_refs = list(collected.get("unresolved_refs") or [])
    result["separation_unresolved_total"] = len(unresolved_refs)
    result["separation_unresolved"] = unresolved_refs[:10]

    # Подсказка о том, чем продолжить, кладётся и в успех, и в отказ: у стадии есть
    # отдельный вход `load_common_attributes_tool` (шаг П5), и вызывающий обязан знать это
    # из ответа, а не из молчания (прецедент ROLES_REPEAT_HINT узла V49).
    warnings.append(COMMON_ATTRIBUTES_REPEAT_HINT)
    if not index_info["available"] and index_info.get("reason"):
        warnings.append(
            f"Индекс состава: {index_info['reason']} — состояния `index_only` и `file_only` "
            "при этом невыразимы, а цели применения и ссылки разделения остаются "
            "неразрешёнными записями (Q3): «объекта нет в перечне» от «перечень этой "
            "конфигурации не загружен» не отличить"
        )
    for observation, detail in (collected.get("observations") or []):
        if observation == "directory_missing":
            warnings.append(
                f"Каталог {collected.get('directory')}/ в выгрузке отсутствует — общих "
                "реквизитов у этой конфигурации нет, и нули таблиц являются ответом о "
                "выгрузке, а не отказом стадии (замер 2.9 даёт KomMag именно в таком виде)"
            )
    if index_info["available"] and int(result["index_kind_records"]) != int(
            result.get("files_found") or 0):
        warnings.append(
            f"Записей `CommonAttribute.<Имя>` в индексе состава "
            f"{result['index_kind_records']}, файлов регистрации "
            f"{result.get('files_found')} — круги различаются (замер 2.9 даёт равенство на "
            "четырёх выгрузках, поэтому расхождение требует объяснения этим прогоном; "
            "расхождения перечислены ключами `index_only` / `file_only`)"
        )
    if int(result.get("targets_written") or 0) != int(result.get("targets_total") or 0):
        warnings.append(
            f"Разбор дал {result.get('targets_total')} строк применения, записано "
            f"{result.get('targets_written')} — часть строк в {TARGETS_TABLE} не попала; "
            "связь с строкой реквизита держится id ревизии (Q2), и молчать об этом нельзя"
        )
    if any(removed.values()):
        warnings.append(
            "Прежние строки свойств общих реквизитов этой конфигурации сняты перед записью: "
            f"{', '.join(f'{table}={count}' for table, count in removed.items())}. "
            "Идемпотентность держится явным DELETE по configuration_uuid: внешнего ключа и "
            "каскада по конфигурации в схеме нет осознанно (прецедент V20.1); новая ревизия "
            "на повторную загрузку той же выгрузки не заводится — история состояний "
            "принадлежит узлу правки объекта, которого в схеме ещё нет"
        )
    if attribute_rows:
        warnings.append(
            f"Момент загрузки строк реквизитов — {moment}: той же меткой помечены строки "
            "заголовка и других стадий этого события (M2); строки применения метку не несут "
            "(своей цепи ревизий у них нет, Q2 вариант A)"
        )
    else:
        warnings.append(
            "Строк реквизитов этим вызовом не записано: каталог вида пуст или отсутствует "
            f"(файлов {result.get('files_found')}), поэтому и общего момента загрузки вида у "
            "этого события нет — нули таблиц являются ответом о выгрузке (Q9)"
        )
    result["warnings"] = warnings
    return result

