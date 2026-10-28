#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Загрузчик свойств дочерних объектов конфигурации (узел V46, П5, 28.10.2026).

Стадия S4 конвейера первого слоя и отдельный инструмент
`load_configuration_object_properties_tool` — ОДИН слой: один загрузчик, один закрытый
контракт (`configuration_load_contract.child_objects_defaults`) и один форматёр текста
(прецедент V45: карточка и инструмент описывают один слой одинаково, два форматёра
разъезжаются при первой же правке контракта).

Что загружается (решения D1–D10 плана `docs/CONFIGURATION_OBJECT_PROPERTIES_PLAN.md`):

* свойства подсистем (`subsystems`), их исходный `Content` в jsonb и разрешённые ссылки
  (`subsystem_content`); порядок детей — из `<ChildObjects>` файла-родителя (D8);
* свойства общих модулей (`common_modules`) и дескрипторы их модулей
  (`common_module_sources`) — путь и размер вместо текста (D6);
* тексты модулей общих модулей в `bsl_modules` — ВТОРОЙ транзакцией (D7) и только если
  вызывающий спросил (`with_module_content=True`): замер 2.6 плана даёт 188 МБ (BGU2) и
  294 МБ (BP3) на выгрузку, поэтому состоянием по умолчанию стоит «не загружать», а
  отсутствие называется строкой контракта, а не молчанием.

Чего здесь нет (границы узла V46, раздел 8 плана): реквизиты и табличные части объектов
конфигурации, формы, макеты, модули объектов, роли и команды — остальные группы A–H модели
V38 (узел V18 открыт); содержимое слотов `Help`/`CommandInterface` подсистем — состояние
называется, xtui/html в схеме не хранится.

Почему отдельный слой и одновременно стадия цепочки — тот же порядок, что у V44:

* ключ строки — `configuration_uuid`, а не `id` заголовка: `force=True` меняет id, uuid
  остаётся прежним (V44);
* стадия вызывается ПОСЛЕ коммита транзакции заголовка: `transaction()` каждый раз открывает
  новое соединение, и в собственной транзакции заголовка слой не увидел бы ни только что
  вставленную строку заголовка, ни строки индекса состава;
* отдельный инструмент остаётся потому, что путь каталога обязан задать оператор: провенанс
  строк конфигурации в БД не ведётся (решение D-C, граница V31), по строке заголовка
  каталог не восстанавливается. Внутри цепочки путь уже дан этим же вызовом.

Идемпотентность держится явным `DELETE` по `configuration_uuid` (внешнего ключа и каскада в
схеме нет осознанно — прецедент V20.1), а не новой ревизией: повторная загрузка той же
выгрузки не создаёт истории. Цепочка ревизий по `full_name` (D8) остаётся узлу правки
объекта, которого в схеме ещё нет; снятые строки названы в ответе (`removed_previous`).

После фиксации записи загрузчик пересобирает статистику четырёх таблиц свойств
(`refresh_table_statistics`): планировщик не знает о строках собственной загрузки, а без
статистики счётчик по витрине текущего состояния на большой выгрузке выполняется минутами
(замер 28.10.2026 на BGU2: 8 мин 25 с против 7 мс после `ANALYZE`).


Родителем строки текста модуля в `bsl_modules` является uuid самого общего модуля
(`parent_uuid`, `parent_type = 'common_modules'`), а НЕ строка конфигурации с
`parent_uuid IS NULL` (уточнение оператора
28.10.2026): состояния текста живут по тому же ключу, что у модулей внешнего объекта, —
`(parent_uuid, file_path, revision_no)` (M1, M3), и частичный индекс
`uq_bsl_modules_config_module_revision` к таким строкам не применяется.
"""
from typing import Any, Dict, List, Optional, Sequence, Tuple

from configuration_load_contract import (
    CHILD_KINDS,
    CHILD_NOT_IMPLEMENTED,
    CHILD_TABLES,
    STATUS_ERROR,
    STATUS_OK,
    child_module_content_defaults,
    child_objects_defaults,
)
from configuration_object_properties import (
    CONTENT_STATES,
    CONTENT_STATES_WITH_PATH,
    KIND_COMMON_MODULES,
    KIND_SUBSYSTEMS,
    collect_common_modules,
    collect_subsystems,
    index_rows_by_name,
    read_module_text,
)
from configuration_root_module_loader import configuration_uuid_from_layout
from current_revision import CHANGED_BY_LOAD, FIRST_REVISION, stamp_revision_rows
from external_db import transaction
from external_table_writer import BslModuleRowWriter, CONFIGURATION_OBJECT_WRITERS

OBJECTS_TABLE = "configuration_objects"

# Колонки индекса состава, нужные разбору свойств. Источник — строки БД, а не повторный
# разбор `ConfigDumpInfo.xml`: тот же приём, что `read_index_module_rows` узла V44. Разбор
# ссылок `Content` обязан видеть записи ЛЮБОГО вида (`Catalog.Товары`, `Report.Отчёт`),
# поэтому фильтра по типу вида здесь нет намеренно.
INDEX_ROW_COLUMNS: Tuple[str, ...] = (
    "name", "object_id", "object_type", "object_name", "child_type", "parent_name", "depth",
)

# Значения колонок `bsl_modules` для текста модуля общего модуля. `parent_type` называет
# таблицу-родителя по той же записи, что `external_report` у модулей внешнего объекта;
# `module_type` — тот же словарь слотов вида, что `common_module_sources.module_type`
# (CHECK `common_module_sources_module_type_check` допускает ровно `Module`).
COMMON_MODULE_PARENT_TYPE = "common_modules"
COMMON_MODULE_OBJECT_TYPE = "CommonModule"
COMMON_MODULE_SLOT_TYPE = "Module"


def normalize_kinds(kinds: Optional[Sequence[str]]) -> Tuple[Tuple[str, ...], Optional[str]]:
    """Разобрать запрошенные виды стадии S4 (подсистемы, общие модули); вернуть (кортеж, причину).

    Незнакомый вид — отказ, а не «ноль строк»: «вида нет» и «вид не просили» — разные
    состояния (контракт C2), и молча превратить опечатку в пустой результат нельзя (тот же
    приём, что отказ по незнакомому варианту загрузки у `detect_load_variant`).
    """
    if kinds is None:
        return CHILD_KINDS, None
    if isinstance(kinds, str):
        kinds = [kinds]
    wanted: List[str] = []
    unknown: List[str] = []
    for kind in kinds:
        name = str(kind or "").strip()
        if name in CHILD_KINDS:
            if name not in wanted:
                wanted.append(name)
        else:
            unknown.append(name or "<пусто>")
    if unknown:
        return (), (
            f"Вид содержимого дочерних объектов не знаком: {', '.join(unknown)}. "
            f"Реализованы: {', '.join(CHILD_KINDS)} (остальные группы A–H модели V38 "
            f"загрузчика не имеют: {CHILD_NOT_IMPLEMENTED})"
        )
    if not wanted:
        return (), ("Не запрошен ни один вид содержимого дочерних объектов: kinds пуст — "
                    "укажите хотя бы один из " + ", ".join(CHILD_KINDS))
    return tuple(kind for kind in CHILD_KINDS if kind in wanted), None


def read_index_records(cur, configuration_id: int) -> Dict[str, Any]:
    """Записи индекса состава этой конфигурации из `configuration_objects` (Н6).

    Пустой ответ означает «индекс недоступен», а не «объектов нет»: при недоступном индексе
    состояние `file_and_index` не выразимо, и вызывающий обязан назвать это состоянием
    загрузки (тот же контракт, что `read_index_module_rows` узла V44 и параметр `index_rows`
    разбора V46). Фильтра по типу вида нет намеренно: разрешение ссылок `Content` обязано
    видеть записи любого вида (`Catalog.Товары`, `Report.Отчёт`).
    """
    info: Dict[str, Any] = {"available": False, "row_count": 0, "reason": None}
    columns = ", ".join(INDEX_ROW_COLUMNS)
    try:
        cur.execute(
            f"SELECT {columns} FROM {OBJECTS_TABLE} WHERE configuration_id = %s",
            [int(configuration_id)],
        )
    except Exception as exc:  # noqa: BLE001 — слой обязан назвать причину, а не бросить
        info["reason"] = f"чтение {OBJECTS_TABLE} не удалось: {exc}"
        return {"rows": {}, **info}
    records = [dict(zip(INDEX_ROW_COLUMNS, values)) for values in cur.fetchall()]
    if not records:
        info["reason"] = (
            f"в {OBJECTS_TABLE} нет записей для configuration_id={configuration_id}: индекс "
            "состава этого заголовка не загружен, поэтому состояния объявления читаются "
            "только по файлам"
        )
        return {"rows": {}, **info}
    info.update({"available": True, "row_count": len(records)})
    return {"rows": index_rows_by_name(records), **info}


def remove_object_properties(cur, configuration_uuid: str,
                             tables: Sequence[str] = CHILD_TABLES) -> Dict[str, int]:
    """Снять строки свойств этой конфигурации (внутри текущей транзакции).

    Круг снятия — таблицы ЗАПРОШЕННЫХ видов, а не весь круг: загрузка «только подсистем» не
    имеет права молча уничтожать ранее записанные общие модули — это два разных ответа
    («снято и записано заново» и «оставлено как было»), и второй читался бы потерей данных.

    Очистка обязана быть явной: внешнего ключа и каскада в схеме нет осознанно (прецедент
    V20.1), иначе строки пережили бы снятие заголовка и стали бы сиротами, которые нельзя ни
    показать в карточке конфигурации, ни отличить от строк другой конфигурации.
    """
    removed: Dict[str, int] = {}
    for table in tables:
        cur.execute(f"DELETE FROM {table} WHERE configuration_uuid = %s::uuid",
                    [str(configuration_uuid)])
        removed[table] = cur.rowcount
    return removed



def remove_common_module_texts(cur, configuration_uuid: str) -> int:
    """Снять тексты модулей общих модулей этой конфигурации из `bsl_modules`.

    Фильтр держится по `parent_type`, а не по «`configuration_uuid` не пуст»: внешние объекты
    пишут в эту же таблицу со своей ссылкой на заголовок, и снять их при загрузке свойств
    конфигурации значило бы потерять чужие строки.
    """
    cur.execute(
        "DELETE FROM bsl_modules WHERE configuration_uuid = %s::uuid AND parent_type = %s",
        [str(configuration_uuid), COMMON_MODULE_PARENT_TYPE],
    )
    return cur.rowcount


def refresh_table_statistics(cur, tables: Sequence[str] = CHILD_TABLES) -> int:
    """Пересобрать статистику записанных таблиц свойств (замер 28.10.2026).

    Планировщик строит план по статистике, а о строках этой же загрузки он не знает:
    незафиксированные строки невидимы для него вовсе, а зафиксированные появятся в
    статистике только когда автовакуум сочтёт нужным. Без статистики счётчик по витрине
    текущего состояния становится вложенным циклом, который на каждую строку ссылок заново
    проходит весь индексный диапазон конфигурации: на BGU2 (600 подсистем, 13 757 ссылок)
    `count(*)` по `v_current_subsystem_content` выполняется 8 мин 25 с, после `ANALYZE` тех
    же таблиц — 7 мс (замер `_scratch/_v46_p7_view_perf_analyze.sql`, план — Nested Loop
    Semi Join c Index Only Scan по `uq_subsystems_configuration_full_name_revision` только
    по `configuration_uuid`).

    Имена таблиц — константа закрытого контракта (`CHILD_TABLES`), пользовательской
    интерполяции в SQL здесь нет.
    """
    for table in tables:
        cur.execute(f"ANALYZE {table}")
    return len(tuple(tables))


def _require_header(configuration_uuid: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Найти строку заголовка по uuid; вернуть карточку или причину отказа.

    Заголовок обязателен: свойства дочерних объектов — второй шаг того же первого слоя, и
    строки без заголовка нельзя ни показать в карточке конфигурации, ни снять вместе с ней
    (внешний ключ в схеме не поставлен осознанно — V20.1).
    """
    from configuration_loader import find_configuration  # ленивый импорт — круг узла V44

    card = find_configuration(configuration_uuid)
    if isinstance(card, dict) and card.get("error"):
        return None, f"Ошибка запроса: {card['error']}"
    if not card:
        return None, (
            f"Строка заголовка конфигурации с uuid {configuration_uuid} в базе не найдена. "
            "Сначала загрузите каталог точкой входа load_1c_catalog_tool(source_path=…): "
            "иначе свойства дочерних объектов остались бы ни на что не указывающими, а "
            "внешний ключ в схеме не поставлен осознанно (узел V20.1)."
        )
    return card, None


def _stage_failure(reason: str, header: Optional[Dict] = None) -> Dict[str, Any]:
    """Отказ стадии в форме закрытого контракта (C1, C3).

    Причина кладётся в ключ `error` замкнутого словаря `child_objects_defaults()`, а статус —
    в `status`: вызывающий отличает «стадия не выполнялась» от «слой отказал» (C2). Если
    заголовок к моменту отказа уже разрешён, он называется: по `configuration_id` карточка
    отличает «заголовка нет» от «заголовок есть, слой отказал по файлам или записи».
    """
    result = child_objects_defaults()
    result["status"] = STATUS_ERROR
    result["error"] = reason
    if header:
        result["configuration_id"] = header.get("id")
        result["configuration_uuid"] = header.get("uuid")
        result["configuration_name"] = header.get("name")
    return result


def common_module_text_row(configuration_uuid: str, descriptor: Dict[str, Any],
                           read_result: Dict[str, Any]) -> Dict[str, Any]:
    """Строка `bsl_modules` для текста модуля общего модуля.

    Родитель — uuid самого общего модуля (`parent_type = 'common_modules'`; уточнение оператора
    28.10.2026), а не строка
    конфигурации с `parent_uuid IS NULL`: состояния текста живут по ключу
    `(parent_uuid, file_path, revision_no)` (M1, M3), то есть так же, как модули внешнего
    объекта. Пустой модуль остаётся строкой с `code IS NULL` и `code_size = 0`: «текста нет»
    и «файла нет» — разные состояния, и первая из них подтверждена файлом выгрузки.
    """
    module_name = str(descriptor.get("module_name") or "")
    return {
        "configuration_uuid": str(configuration_uuid),
        "module_name": module_name,
        "file_path": descriptor.get("file_path"),
        "code": read_result.get("code"),
        "object_type": COMMON_MODULE_OBJECT_TYPE,
        "object_name": module_name,
        "report_id": None,
        "parent_uuid": str(descriptor.get("object_uuid")),
        "parent_type": COMMON_MODULE_PARENT_TYPE,
        "module_type": COMMON_MODULE_SLOT_TYPE,
        "code_size": read_result.get("code_size"),
        "truncated": bool(read_result.get("truncated")),
    }


def write_common_module_texts(cur, source_dir, configuration_uuid: str,
                              descriptors: Sequence[Dict[str, Any]],
                              code_limit: Optional[int] = None,
                              changed_at=None) -> Dict[str, Any]:
    """Вторая транзакция конвейера инструмента (D7): тексты модулей в `bsl_modules`.

    Возвращает заполненный словарь `child_module_content_defaults()` — тот же закрытый
    перечень, что читает форматёр. Отказ чтения одного модуля не отменяет записанных:
    стадия называет его строкой в `errors` и продолжает (C5 — ошибкой слоя считается отказ
    записи в БД, а не состояние конкретной выгрузки).

    Дескрипторы без текста физически (`bin_only`, `indexed_no_file`) в `bsl_modules` строку
    не получают и считаются в `skipped`: иначе таблица раздулась бы строками «текста нет» —
    ровно то, ради чего D6 разделил таблицы.
    """
    out = {
        "requested": True,
        "written": 0,
        "truncated": 0,
        "skipped": 0,
        "code_limit": int(code_limit) if code_limit else None,
        "counts_by_state": {state: 0 for state in CONTENT_STATES},
        "removed_previous": remove_common_module_texts(cur, configuration_uuid),
        "errors": [],
    }

    moment = changed_at
    loaded_uuids: List[str] = []
    for descriptor in descriptors or ():
        state = str(descriptor.get("content_state") or "")
        if state in out["counts_by_state"]:
            out["counts_by_state"][state] += 1
        if state not in CONTENT_STATES_WITH_PATH:
            out["skipped"] += 1
            continue
        read_result = read_module_text(source_dir, descriptor.get("file_path") or "",
                                       code_limit)
        if read_result.get("reason"):
            out["skipped"] += 1
            out["errors"].append(
                f"{descriptor.get('file_path')}: текст модуля не прочитан — "
                f"{read_result['reason']}"
            )
            continue
        row = common_module_text_row(configuration_uuid, descriptor, read_result)
        moment = stamp_revision_rows([row], revision_no=FIRST_REVISION,
                                     changed_by=CHANGED_BY_LOAD, changed_at=moment)
        BslModuleRowWriter.insert(cur, row)
        out["written"] += 1
        if row["truncated"]:
            out["truncated"] += 1
        loaded_uuids.append(str(descriptor.get("object_uuid")))

    if loaded_uuids:
        # Дескриптор обязан сказать, что текст лежит: `content_loaded` без этого остаётся
        # false навсегда, и вторая стадия не отличалась бы от несделанной (решение D7).
        cur.execute(
            "UPDATE common_module_sources SET content_loaded = TRUE "
            "WHERE configuration_uuid = %s::uuid AND module_type = %s "
            "AND object_uuid = ANY(%s::uuid[])",
            [str(configuration_uuid), COMMON_MODULE_SLOT_TYPE, loaded_uuids],
        )
    return out


# Ключи сводки разбора, совпадающие с ключами контракта по имени (один словарь на разбор и
# на ответ): копируются только они — неперечисленный ключ контракта читается нулём (C1), а
# незнакомый ключ разбора не попадает в ответ, которого карточка не обещала.
SUMMARY_KEYS: Tuple[str, ...] = (
    "written", "counts_by_state", "by_depth", "content_total", "content_resolved",
    "content_unresolved", "content_by_form", "content_by_target_type", "slots_by_state",
    "counts_by_content_state", "modules_without_descriptor", "index_available",
    "index_objects", "index_slots", "parse_errors", "layout_outliers",
)

# Группа строк, которую даёт каждый вид: таблица → строки контракта разбора. Выбор по виду,
# а не по имени таблицы (прецедент ROOT_MODULE_WRITERS: ошибка выбора превращается в запись
# не в ту таблицу).
TABLES_BY_KIND: Dict[str, Tuple[str, str]] = {
    KIND_SUBSYSTEMS: ("subsystems", "subsystem_content"),
    KIND_COMMON_MODULES: ("common_modules", "common_module_sources"),
}

# Имена видов в `<ChildObjects>` корневого `Configuration.xml`, соответствующие видам стадии S4
# (подсистемы, общие модули).
# Перечень нужен разбору заголовка: предупреждение «объекты перечислены индексом, но их
# содержимое в БД не сохраняется» было верным до узла V46 и с этого узла обязано различать
# виды, содержимое которых сохраняется (подсистемы, общие модули), и остальные. Держать его
# приходится здесь, а не в разборе заголовка: таблицы вида знает этот слой, а не парсер XML.
META_TAGS_BY_KIND: Dict[str, str] = {
    KIND_SUBSYSTEMS: "Subsystem",
    KIND_COMMON_MODULES: "CommonModule",
}
LOADED_META_TABLES: Dict[str, Tuple[str, ...]] = {
    META_TAGS_BY_KIND[kind]: TABLES_BY_KIND[kind] for kind in META_TAGS_BY_KIND
}


def load_object_properties(source_path: str,
                           configuration_uuid: Optional[str] = None,
                           kinds: Optional[Sequence[str]] = None,
                           with_module_content: bool = False,
                           module_code_limit: Optional[int] = None) -> Dict[str, Any]:
    """Загрузить свойства подсистем и общих модулей конфигурации (узел V46, стадия S4).

    Порядок: каталог → uuid из `Configuration.xml` (или сверка переданного) → проверка, что
    заголовок загружен → индекс состава из `configuration_objects` (подтверждение состояний,
    Н6) → разбор файлов регистрации → **транзакция №1**: `DELETE` по uuid + вставка четырёх
    групп → при `with_module_content=True` **транзакция №2**: тексты модулей в `bsl_modules`
    и `content_loaded = true` (решение D7).

    Две транзакции — не деталь реализации, а ответ: отказ второй не откатывает первую и
    называется отдельно («свойства загружены, содержимое модулей — нет»). Первая группа
    пишется одной транзакцией по той же причине, что загрузка внешнего объекта (V12): при
    ошибке в базе не остаётся половины строк.

    `module_code_limit` по умолчанию не задан: число усечения — открытое решение D-LIMIT, и
    выдуманное здесь число стало бы нормативом, которого оператор не утверждал (замер 2.6:
    максимальный файл модуля — 5,5 МБ).
    """
    wanted_kinds, kinds_error = normalize_kinds(kinds)
    if kinds_error:
        return _stage_failure(kinds_error)

    uuid_info = configuration_uuid_from_layout(source_path)
    if "uuid" not in uuid_info:
        return _stage_failure(uuid_info.get("error")
                             or f"Каталог выгрузки не читается: {source_path}")
    layout_uuid = str(uuid_info["uuid"])
    if configuration_uuid and str(configuration_uuid).strip().lower() != layout_uuid.lower():
        # Два источника одного факта указали на разные конфигурации: молча выбрать один —
        # значит записать свойства чужой конфигурации (тот же отказ, что у слоя V44).
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
    collected: Dict[str, Dict[str, Any]] = {}
    index_info: Dict[str, Any] = {"available": False, "row_count": 0, "reason": None}
    removed: Dict[str, int] = {table: 0 for table in CHILD_TABLES}
    written_by_table: Dict[str, int] = {table: 0 for table in CHILD_TABLES}
    try:
        with transaction() as cur:
            index_info = read_index_records(cur, int(header["id"]))
            if KIND_SUBSYSTEMS in wanted_kinds:
                collected[KIND_SUBSYSTEMS] = collect_subsystems(
                    source_path, index_rows=index_info["rows"])
            if KIND_COMMON_MODULES in wanted_kinds:
                collected[KIND_COMMON_MODULES] = collect_common_modules(
                    source_path, index_rows=index_info["rows"])
            removed = remove_object_properties(
                cur, configuration_uuid,
                [table for kind in wanted_kinds for table in TABLES_BY_KIND[kind]])
            moment = None
            for kind in wanted_kinds:
                part = collected[kind]
                rows_by_table = {
                    "subsystems": part.get("rows") or [],
                    "subsystem_content": part.get("content_rows") or [],
                } if kind == KIND_SUBSYSTEMS else {
                    "common_modules": part.get("rows") or [],
                    "common_module_sources": part.get("source_rows") or [],
                }
                for table in TABLES_BY_KIND[kind]:
                    rows = rows_by_table[table]
                    for row in rows:
                        # uuid заголовка знает вызывающий, а не XML объекта — тот же порядок,
                        # что у писателей модулей корня (узел V44).
                        row["configuration_uuid"] = configuration_uuid
                    # Один момент на всю загрузку (M2): строки одного события не должны нести
                    # разные метки, иначе родитель и ребёнок читались бы как два состава.
                    moment = stamp_revision_rows(rows, revision_no=FIRST_REVISION,
                                                changed_by=CHANGED_BY_LOAD, changed_at=moment)
                    written_by_table[table] = CONFIGURATION_OBJECT_WRITERS[
                        table].insert_many(cur, rows)
    except Exception as exc:  # noqa: BLE001 — заголовок уже разрешён, отказ называется им
        return _stage_failure(f"Ошибка записи: {exc}", header=header)

    # ── транзакция №2 (решение D7): тексты модулей общих модулей ──────────────────────
    # Отдельная транзакция — не деталь реализации, а состояние ответа: отказ этой стадии не
    # откатывает записанные свойства и называется отдельно. Без просьбы вызывающего тексты не
    # читаются вовсе (замер 2.6 плана: 188 МБ BGU2, 294 МБ BP3 на выгрузку).
    module_content = child_module_content_defaults()
    if with_module_content:
        module_content["requested"] = True
        module_content["code_limit"] = int(module_code_limit) if module_code_limit else None
        if KIND_COMMON_MODULES not in collected:
            module_content["errors"].append(
                "тексты модулей запрошены, а вид common_modules не запрошен — писать в "
                "bsl_modules нечего; свойства записаны, содержимое модулей — нет"
            )
        else:
            try:
                with transaction() as cur:
                    module_content = write_common_module_texts(
                        cur, source_path, configuration_uuid,
                        collected[KIND_COMMON_MODULES].get("source_rows") or [],
                        module_code_limit)
            except Exception as exc:  # noqa: BLE001 — первая транзакция уже зафиксирована
                module_content = child_module_content_defaults()
                module_content["requested"] = True
                module_content["code_limit"] = (int(module_code_limit)
                                               if module_code_limit else None)
                module_content["errors"].append(
                    f"запись текстов модулей не состоялась: {exc}. Свойства подсистем и общих "
                    "модулей записаны (первая транзакция зафиксирована — D7), содержимое "
                    "модулей — нет, common_module_sources.content_loaded остался false"
                )

    # ── статистика записанных таблиц (замер 28.10.2026) ─────────────────────────────────
    # Отдельная транзакция ПОСЛЕ фиксации записи: планировщик обязан увидеть строки, иначе
    # первый же читатель витрин `v_current_*` платит минутами за счётчик — см.
    # `refresh_table_statistics`. Отказ статистики не является отказом загрузки: строки
    # зафиксированы и состояние ответа от него не меняется, поэтому это предупреждение.
    try:
        with transaction() as cur:
            refresh_table_statistics(cur)
    except Exception as exc:  # noqa: BLE001 — ответ описывает запись, а не статистику
        warnings.append(
            f"статистика таблиц свойств не обновлена: {exc}. Свойства записаны, но читатель "
            "витрин текущего состояния получит план по пустой статистике: счётчики на большой "
            "выгрузке выполняются минутами вместо миллисекунд"
        )

    result = child_objects_defaults()
    result.update({
        "status": STATUS_OK,
        "success": True,
        "configuration_id": header["id"],
        "configuration_uuid": configuration_uuid,
        "configuration_name": header.get("name"),
        "kinds_requested": list(wanted_kinds),
        "module_content": module_content,
    })
    for kind in wanted_kinds:
        part = collected[kind]
        target = result["kinds"][kind]
        target["requested"] = True
        for key in SUMMARY_KEYS:
            if key in part:
                target[key] = part[key]
        # Индекс подтверждает состояния из БД, а не из повторного разбора XML — поэтому
        # `index_available` берётся у чтения индекса, а не у разбора (Н6).
        target["index_available"] = bool(index_info["available"])
        target["descriptor_rows"] = (len(part.get("source_rows") or [])
                                    if kind == KIND_COMMON_MODULES else 0)
        target["removed_previous"] = sum(int(removed.get(table) or 0)
                                        for table in TABLES_BY_KIND[kind])
        warnings.extend(f"{kind}: {warning}" for warning in part.get("warnings") or [])
    result["objects_written"] = sum(int(count or 0) for count in written_by_table.values())

    if not index_info["available"] and index_info.get("reason"):
        warnings.append(
            f"Индекс состава: {index_info['reason']} — состояния `file_and_index` при этом "
            "невыразимы, и «объекта нет» от «объект не подтверждён индексом» не отличить"
        )
    removed_detail = ", ".join(f"{table} {removed[table]}" for table in CHILD_TABLES
                               if removed.get(table))
    if removed_detail:
        warnings.append(
            f"Прежние строки свойств этой конфигурации сняты перед записью: {removed_detail}. "
            "Идемпотентность держится явным DELETE по configuration_uuid: внешнего ключа и "
            "каскада в схеме нет осознанно (прецедент V20.1); новая ревизия на повторную "
            "загрузку той же выгрузки не заводится — история состояний принадлежит узлу "
            "правки объекта, которого в схеме ещё нет (D8)"
        )
    warnings.append(
        "Отдельная точка входа load_configuration_object_properties_tool служит случаю "
        "«изменились только файлы регистрации»: заголовок и индекс состава при этом не "
        "меняются, и пересоздавать конфигурацию force=True ради свойств подсистем и общих "
        "модулей не нужно "
        "(тот же порядок, что узла V44). Путь каталога при этом задаёт оператор — "
        "провенанс строк конфигурации в БД не ведётся (решение D-C, граница V31)."
    )
    result["warnings"] = warnings
    return result





