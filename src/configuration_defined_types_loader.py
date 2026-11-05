#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Загрузчик свойств определяемых типов конфигурации (узел V58, шаг П6, 05.11.2026).

Стадия S4m конвейера первого слоя: свойства вида `DefinedTypes` (позиция 2.13 нормативного
списка плана `docs/CONFIGURATION_DEFINED_TYPES_PLAN.md`) в таблицу `defined_types`. Норматив —
тот же план (решения Q1–Q7, Q9, правила C1–C3); разбор файла вида — отдельный модуль
`src/configuration_defined_types.py` (шаг П3), писатель строки — `DefinedTypesRowWriter` и
запись в реестр `CONFIGURATION_OBJECT_WRITERS` (шаг П4), стадия и круг таблиц объявлены в
контракте (шаг П5).

Почему стадия отдельная, а не ещё один вид стадии S4 (прецедент V48…V57): правило C3 требует,
чтобы ответ каждой стадии был вложен в свой ключ `defined_types`, — разбивать чужой ключ
значило бы переименовывать контракт соседнего узла. Порядок `STAGES` повторяет порядок
нормативного списка (2.13 идёт после 2.12), поэтому S4m стоит между S4l и S4b. Круг таблиц
стадии (`DEFINED_TYPES_TABLES`) и его включение в `FOREIGN_STAGE_TABLES` объявлены там же, где
и стадия: регистрация `defined_types` в круге версионности (`CONFIGURATION_VERSIONED_TABLES`,
шаги П1/П4) без объявленного круга молча добавила бы таблицу к кругу стадии S4, и та снимала бы
и анализировала бы чужие строки (дефект, названный узлами V49…V57).

Что здесь происходит и чего здесь нет:

* круг задают каталог `DefinedTypes/`, записи индекса состава того же вида и перечень
  заголовка `configurations.defined_types` (ТРИ ноги, шаг П5): расхождения называются
  `index_only` / `file_only` / `uuid_mismatch`, и нули обязаны быть названы, а не подразумеаны
  (замеры 1.1, 1.2: 2 / 1 / 304 / 513 файла, расхождений ноль);
* разрешение цели ЗНАЧЕНИЯ типа идёт по всем строкам индекса состава этой конфигурации, потому
  что цель — объект другого вида (`Catalog.Организации`), а свой круг вида отбирает сам разбор
  (`kind_index_rows`); внешнего ключа на цель в схеме нет осознанно (Q3, вариант A по
  прецедентам V50/V52/V53/V55/V56): слои групп A–H модели V38 этой позицией не загружаются,
  поэтому цель называется состоянием, а не фактом существования;
* индекс состава НЕ является условием записи (отличие от V55): состояний `pending` в схеме вида
  нет, и при недоступном индексе разрешение остаётся состоянием `unresolved` с наблюдением
  `index_not_provided` — «цели нет в перечне» и «перечень не загружен» являются разными
  ответами (правило C2, прецедент V56/V57);
* тексты `bsl_modules` (узел V47) стадия не читает и не снимает (мера M5): модулей, форм,
  макетов и команд у вида нет ни файлами, ни индексом состава (замер 1.2), поэтому общих
  таблиц детей круг не касается;
* блок `<Type>` и его квалификаторы пишутся колонками строки вида (Q1, вариант A): второй
  таблицы значений у узла нет, поэтому и порядка «сначала дети» (мера M7 V53/V54) здесь нет.

Идемпотентность держится явным `DELETE` по `configuration_uuid` (внешнего ключа и каскада в
схеме нет осознанно — прецеденты V20.1, V44, V46), а не новой ревизией: повторная загрузка той
же выгрузки не создаёт истории, снятые строки названы в ответе (`removed_previous`). Ключом
цепочки состояния является (`configuration_uuid`, `object_name`, `revision_no`) — решение Q2
узла (замер M1: uuid вида встречается в нескольких конфигурациях корпуса, имя уникально внутри
конфигурации; 10 коллизий имён приходятся на пару BGU2/BP3 — замер 1.3).

Круг пишется одной транзакцией, и отказ разбора любого файла круга останавливает стадию ДО
записи: в базе не остаётся половины строк (приём V12/V46). Отсутствующий каталог вида — не
отказ, а ответ о выгрузке: `files_found = 0` с наблюдением `directory_missing` (Q9, вариант A;
корпус такой выгрузки не даёт — вид есть во всех четырёх, поэтому случай проверяется фикстурой
постоянной проверки узла, а не наблюдением прогона). Повторные имена вида внутри одной
выгрузки — отказ стадии до записи (цепь ограничена `configuration_uuid`, M1).

После фиксации загрузчик пересобирает статистику таблицы (`refresh_table_statistics` — мера
V46): планировщик не знает о строках собственной загрузки, и без статистики счётчик по
витрине `v_current_defined_types` на большой выгрузке выполняется минутами (замер V46 на BGU2:
8 мин 25 с против 7 мс). Отказ статистики отказом загрузки не является — строки зафиксированы,
и это предупреждение.

Прогон шага: `python _v58_p6_loader_probe.py` (живая БД, за собой убирает).
"""
from typing import Any, Dict, List, Optional, Tuple

from configuration_defined_types import (
    COUNT_KEYS,
    DIR_NAME as DEFINED_TYPES_DIR,
    STATE_VOCABULARIES as DEFINED_TYPES_STATE_VOCABULARIES,
    TABLE_NAME as DEFINED_TYPES_TABLE,
    collect_defined_types,
    kind_index_rows,
)
from configuration_load_contract import (
    DEFINED_TYPES_CIRCLE_BOUNDARY,
    DEFINED_TYPES_REPEAT_HINT,
    DEFINED_TYPES_REMOVE_ORDER,
    DEFINED_TYPES_TABLES,
    STATUS_ERROR,
    STATUS_OK,
    defined_types_defaults,
)
from configuration_object_properties_loader import refresh_table_statistics
from configuration_root_module_loader import configuration_uuid_from_layout
from current_revision import CHANGED_BY_LOAD, FIRST_REVISION, stamp_revision_rows
from external_db import transaction
from external_table_writer import CONFIGURATION_OBJECT_WRITERS

OBJECTS_TABLE = "configuration_objects"
WRITER = CONFIGURATION_OBJECT_WRITERS[DEFINED_TYPES_TABLE]

# Колонки индекса состава, которые нужны разбору вида: `name`/`object_name` — ключ сверки
# (`DefinedType.<Имя>`, замер 1.1), `uuid` — цель разрешения значения и сверка uuid файла с
# записью перечня, `object_id`/`object_type`/`object_name` подтверждают состояние `exact` и
# называют вид цели, `child_type`/`parent_name`/`depth` — форма записи (иерархии раскладки у
# вида нет, замер 1.2). Фильтра по типу вида здесь нет намеренно: разрешение цели обязано
# видеть записи ЛЮБОГО вида (`Catalog.*`, `InformationRegister.*` — объекты других видов,
# замер 2.5), а свой круг вида отбирает сам разбор (`kind_index_rows`). Источник — строки БД, а
# не повторный разбор `ConfigDumpInfo.xml` (правило V43; приём `read_index_records`
# узлов V46/V48/V53/V54/V56/V57).
INDEX_ROW_COLUMNS: Tuple[str, ...] = (
    "name", "object_id", "object_type", "object_name", "child_type", "parent_name",
    "depth", "uuid",
)

# Ключи сводки разбора, совпадающие с ключами контракта по имени (один словарь на разбор и на
# ответ): копируются только они — неперечисленный ключ контракта читается нулём (C1), а
# незнакомый ключ разбора не попадает в ответ, которого карточка не обещала (прецедент
# `SUMMARY_KEYS` узлов V46/V48…V57). Ключи `index_available`, `index_kind_records` сюда НЕ
# входят намеренно: их называет слой по факту чтения `configuration_objects`, а разбор описывает
# ими только свой вход. Ключ `rows` — payload писателя (шаг П4), а не часть ответа. Словари
# состояний копируются списком, порождённым словарём разбора: второе перечисление состояний в
# проекте разъезжается с первым (П6). Ключа `warning_count` здесь нет осознанно: ответ стадии уже
# несёт список `warnings`, а число предупреждений второй половиной той же пары (прецедент V55/V57,
# где замкнутый контракт `*_defaults()` ключа `warning_count` не объявляет).
SUMMARY_KEYS: Tuple[str, ...] = (
    "directory", "files_found", "files_parsed", "files_failed", "observations",
    "duplicate_names", "index_only", "file_only", "uuid_mismatch", "unknown_properties",
    "unresolved_targets", "unresolved_targets_total", "examples",
    "failures", "counts_by_class", "counts_by_container",
    "resolve_exact", "resolve_no_target", "resolve_unresolved",
) + tuple("counts_by_" + column for column in DEFINED_TYPES_STATE_VOCABULARIES) + COUNT_KEYS


def circle_discrepancy_counts(index_only: List[Any], file_only: List[Any],
                              uuid_mismatch: List[Any]) -> Dict[str, int]:
    """Числа расхождений ног круга по замкнутому словарю состояний (C1).

    Перечисленные списки дают примеры (`MAX_EXAMPLES` разбора), а число обязано быть полным:
    полнота держится отдельным числом, а не длиной примеров — приём V48. Нули являются
    ответом: четыре замеренные выгрузки дают ноль по всем трём состояниям (замеры 1.1, 1.2 —
    820 файлов и 820 записей индекса с совпадающими uuid), и молчать об этом значило бы не
    отличать «расхождений нет» от «сверку не делали». Словарь состояний берётся замкнутой
    константой разбора (`CIRCLE_DISCREPANCIES`), а не списком имён здесь.
    """
    from configuration_defined_types import CIRCLE_DISCREPANCIES
    listed = dict(zip(CIRCLE_DISCREPANCIES, (index_only, file_only, uuid_mismatch)))
    return {state: len(listed.get(state) or []) for state in CIRCLE_DISCREPANCIES}


def read_index_records(cur, configuration_id: int) -> Dict[str, Any]:
    """Записи индекса состава этой конфигурации из `configuration_objects` (Н6).

    Пустой ответ означает «индекс недоступен», а не «объектов нет»: при недоступном индексе
    сверка файла регистрации с перечнем не выполняется (`index_check = not_checked`), а
    разрешение цели значения остаётся состоянием `unresolved` с наблюдением
    `index_not_provided` — вызывающий обязан назвать это предупреждением, а не нулями (правило
    C2, V56/V57). Записей своего вида здесь считается ровно столько, сколько их перечисляет
    индекс (`index_kind_records` ответа стадии): по замеру 1.1 это 2 / 1 / 304 / 513, и
    расхождение с числом файлов обязано быть названо.
    """
    info: Dict[str, Any] = {"available": False, "row_count": 0, "kind_count": 0,
                            "reason": None}
    columns = ", ".join(INDEX_ROW_COLUMNS)
    try:
        cur.execute(
            f"SELECT {columns} FROM {OBJECTS_TABLE} WHERE configuration_id = %s",
            [int(configuration_id)],
        )
    except Exception as exc:  # noqa: BLE001 — слой обязан назвать причину, а не бросить
        info["reason"] = f"чтение {OBJECTS_TABLE} не удалось: {exc}"
        return {"rows": [], **info}
    records = [dict(zip(INDEX_ROW_COLUMNS, values)) for values in cur.fetchall()]
    if not records:
        info["reason"] = (
            f"в {OBJECTS_TABLE} нет записей для configuration_id={configuration_id}: индекс "
            "состава этого заголовка не загружен, поэтому сверка файлов регистрации с "
            "перечнем и разрешение целей значения невозможны"
        )
        return {"rows": [], **info}
    info.update({
        "available": True,
        "row_count": len(records),
        "kind_count": len(kind_index_rows(records)),
    })
    return {"rows": records, **info}


def remove_defined_types(cur, configuration_uuid: str) -> Dict[str, int]:
    """Снять строки свойств определяемых типов этой конфигурации (внутри транзакции).

    Очистка обязана быть явной: внешнего ключа и каскада в схеме нет осознанно (прецедент
    V20.1), иначе строки пережили бы снятие заголовка и стали бы сиротами, которые нельзя ни
    показать в карточке конфигурации, ни отличить от строк другой конфигурации. Этим же
    фильтром (`configuration_uuid`) держится снятие в `_remove_rows` узлов V32/V46 — иначе
    `force=True` оставил бы в базе прежний состав вида.

    Круг снятия — ОДНА таблица (`DEFINED_TYPES_REMOVE_ORDER`): второй таблицы значений у вида
    нет осознанно (Q1, вариант A — блок `<Type>` и его квалификаторы являются колонками строки
    вида), и детей у вида нет ни файлами, ни индексом состава (замер 1.2), поэтому здесь нет ни
    порядка «сначала дети» (мера M7 узлов V53/V54), ни каскадных внешних ключей, которые
    снимали бы строки молча.

    Строки `bsl_modules` этим фильтром НЕ снимаются намеренно, и это названо, а не обойено
    (мера M5): их пишет узел V47, и снятие свойств вида не имеет права удалять содержимое
    чужого узла.
    """
    removed: Dict[str, int] = {}
    for table in DEFINED_TYPES_TABLES:
        cur.execute(
            f"DELETE FROM {table} WHERE configuration_uuid = %s::uuid",
            [str(configuration_uuid)],
        )
        removed[table] = int(cur.rowcount)
    return removed


def _require_header(configuration_uuid: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Найти строку заголовка по uuid; вернуть карточку или причину отказа.

    Заголовок обязателен: свойства вида — второй шаг того же первого слоя, и строки без
    заголовка нельзя ни показать в карточке конфигурации, ни снять вместе с ней (внешний ключ
    в схеме не поставлен осознанно — V20.1). Ленивый импорт — тот же обход круга, что у слоёв
    V44/V46/V48.
    """
    from configuration_loader import find_configuration  # ленивый импорт — круг узла V44

    card = find_configuration(configuration_uuid)
    if isinstance(card, dict) and card.get("error"):
        return None, f"Ошибка запроса: {card['error']}"
    if not card:
        return None, (
            f"Строка заголовка конфигурации с uuid {configuration_uuid} в базе не найдена. "
            "Сначала загрузите каталог точкой входа load_1c_catalog_tool(source_path=…): "
            "иначе свойства определяемых типов остались бы ни на что не указывающими, а "
            "внешний ключ в схеме не поставлен осознанно (узел V20.1)."
        )
    return card, None


def _stage_failure(reason: str, header: Optional[Dict] = None,
                   status: str = STATUS_ERROR,
                   extra: Optional[List[str]] = None) -> Dict[str, Any]:
    """Отказ стадии в форме закрытого контракта (C1, C3).

    Причина кладётся в ключ `error` замкнутого словаря `defined_types_defaults()`, а статус — в
    `status`: вызывающий отличает «стадия не выполнялась» от «слой отказал» (C2). Если
    заголовок к моменту отказа уже разрешён, он называется: по `configuration_id` карточка
    отличает «заголовка нет» от «заголовок есть, слой отказал по файлам». Подсказка о том, чем
    продолжить, кладётся и в отказ, и в успех: у стадии есть отдельный вход
    `load_defined_types_tool` (шаг П7), и вызывающий обязан знать это из ответа, а не из
    молчания (прецеденты V48…V57).
    """
    result = defined_types_defaults()
    result["status"] = status
    result["error"] = reason
    result["reason"] = reason
    if header:
        result["configuration_id"] = header.get("id")
        result["configuration_uuid"] = header.get("uuid")
        result["configuration_name"] = header.get("name")
    result["warnings"].append(DEFINED_TYPES_REPEAT_HINT)
    result["warnings"].append(f"Граница: {DEFINED_TYPES_CIRCLE_BOUNDARY}")
    for warning in extra or []:
        result["warnings"].append(warning)
    return result


def load_defined_types(source_path: str,
                       configuration_uuid: Optional[str] = None,
                       changed_at=None) -> Dict[str, Any]:
    """Загрузить свойства определяемых типов конфигурации (узел V58, стадия S4m).

    Порядок: каталог → uuid из `Configuration.xml` (или сверка переданного) → проверка, что
    заголовок загружен → индекс состава из `configuration_objects` (сверка файлов с перечнем и
    разрешение целей значения, Н6) → разбор каталога вида → **одна транзакция**: `DELETE` по
    uuid + вставка строк круга → отдельной транзакцией `ANALYZE` таблицы (мера V46).

    Отказ разбора любого файла круга останавливает стадию ДО записи: половина круга в базе
    читалась бы как полный состав вида (приём V12/V46). Отсутствующий каталог вида — не отказ,
    а ответ о выгрузке: `files_found = 0` с наблюдением `directory_missing` (Q9, вариант A).
    Повторные имена вида внутри одной выгрузки — отказ до записи: строки круга нарушили бы
    `UNIQUE (configuration_uuid, object_name, revision_no)`, и отказ называется списком имён, а
    не отдаётся на откуп планировщику БД (замер 1.1 даёт ноль повторов внутри выгрузки; 10
    коллизий имён приходятся на пару BGU2/BP3 — цепь ограничена `configuration_uuid`, M1).

    Недоступный индекс состава — предупреждение, а не отказ (отличие от V55): состояний
    `pending` в схеме вида нет, поэтому при пустом индексе сверка ног не выполняется
    (`index_check = not_checked`), а цели значения остаются состоянием `unresolved` с
    наблюдением `index_not_provided` — «цели нет в перечне» и «перечень не загружен» обязаны
    различаться (правило C2, прецедент V56/V57).

    `changed_at` передаёт конвейер: строки одной загрузки обязаны нести одну метку (M2), а не
    время своей транзакции. Пустое значение — своя метка вызова (одиночный прогон слоя).
    """
    uuid_info = configuration_uuid_from_layout(source_path)
    if "uuid" not in uuid_info:
        return _stage_failure(uuid_info.get("error")
                             or f"Каталог выгрузки не читается: {source_path}")
    layout_uuid = str(uuid_info["uuid"])
    if configuration_uuid and str(configuration_uuid).strip().lower() != layout_uuid.lower():
        # Два источника одного факта указали на разные конфигурации: молча выбрать один —
        # значит записать свойства чужой конфигурации (тот же отказ, что у слоёв V44/V46/V48).
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
    try:
        with transaction() as cur:
            index_info = read_index_records(cur, int(header["id"]))
    except Exception as exc:  # noqa: BLE001 — индекс читается до записи, отказ называется им
        index_info["reason"] = f"чтение {OBJECTS_TABLE} не удалось: {exc}"

    collected = collect_defined_types(source_path, index_rows=index_info["rows"])
    if not collected["success"]:
        failures = collected.get("files_failed") or []
        detail = "; ".join(f"{item.get('source_path')}: {item.get('reason')}"
                           for item in failures[:10])
        return _stage_failure(
            f"Круг не записан: {len(failures)} файл(ов) каталога "
            f"{collected.get('directory') or DEFINED_TYPES_DIR} не разобраны — {detail}. "
            "Ни одной строки круга в базу не записано: половина круга читалась бы как полный "
            "состав вида (приём V12/V46); прежние строки этой конфигурации не сняты",
            header=header,
        )

    rows = collected.get("rows") or []
    if collected.get("duplicate_names"):
        duplicates = collected["duplicate_names"]
        return _stage_failure(
            f"Круг не записан: повторные имена вида внутри выгрузки — "
            + "; ".join(f"{item.get('object_name')} ({item.get('first')} ↔ "
                        f"{item.get('second')})" for item in duplicates[:10])
            + f". Строки круга нарушили бы UNIQUE (configuration_uuid, object_name, "
              f"revision_no) таблицы {DEFINED_TYPES_TABLE}, поэтому отказ называется списком "
              "имён до записи: цепь ревизий ограничена uuid конфигурации (M1, Q2), и две "
              "выгрузки с одинаковым именем вида — разные строки, а два файла одной выгрузки — "
              "одна и та же строка. Ни одной строки не записано, прежние строки этой "
              f"конфигурации не сняты",
            header=header,
        )

    removed: Dict[str, int] = {}
    written: Dict[str, int] = {}
    try:
        with transaction() as cur:
            removed = remove_defined_types(cur, configuration_uuid)
            for row in rows:
                # uuid заголовка знает вызывающий, а не XML файла вида — тот же порядок, что у
                # писателей свойств V46, модулей корня V44 и вида 2.12 (V57).
                row["configuration_uuid"] = configuration_uuid
            # Один момент на всю загрузку (M2): строки одного события не должны нести разные
            # метки, иначе их нельзя прочитать как один состав.
            stamp_revision_rows(rows, revision_no=FIRST_REVISION,
                                changed_by=CHANGED_BY_LOAD, changed_at=changed_at)
            written[DEFINED_TYPES_TABLE] = int(WRITER.insert_many(cur, rows))
    except Exception as exc:  # noqa: BLE001 — заголовок уже разрешён, отказ называется им
        return _stage_failure(f"Ошибка записи: {exc}", header=header)

    # ── статистика записанной таблицы (мера V46) ─────────────────────────────────────────
    # Отдельная транзакция ПОСЛЕ фиксации записи: планировщик обязан увидеть строки, иначе
    # первый же читатель витрины `v_current_defined_types` платит минутами за счётчик (замер
    # V46 на BGU2: 8 мин 25 с против 7 мс после ANALYZE). Отказ статистики отказом загрузки не
    # является: строки зафиксированы, и состояние ответа от него не меняется.
    statistics_refreshed = 0
    try:
        with transaction() as cur:
            refresh_table_statistics(cur, DEFINED_TYPES_TABLES)
            statistics_refreshed = 1
    except Exception as exc:  # noqa: BLE001 — ответ описывает запись, а не статистику
        warnings.append(
            f"статистика таблицы {DEFINED_TYPES_TABLE} не обновлена: {exc}. Строки записаны, "
            "но читатель витрины текущего состояния получит план по пустой статистике: "
            "счётчики на большой выгрузке выполняются минутами вместо миллисекунд"
        )

    result = defined_types_defaults()
    result.update({
        "status": STATUS_OK,
        "success": True,
        "configuration_id": header["id"],
        "configuration_uuid": configuration_uuid,
        "configuration_name": header.get("name"),
        "directory": collected.get("directory") or DEFINED_TYPES_DIR,
        "rows_written": int(sum(written.values())),
        "defined_types_written": int(written.get(DEFINED_TYPES_TABLE, 0)),
        "removed_previous": int(sum(removed.values())),
        "removed_by_table": {table: int(removed.get(table, 0))
                             for table in DEFINED_TYPES_REMOVE_ORDER},
        "written_by_table": {table: int(written.get(table, 0))
                             for table in DEFINED_TYPES_TABLES},
        "index_available": bool(index_info["available"]),
        "index_kind_records": int(index_info["kind_count"]),
        "statistics_refreshed": statistics_refreshed,
    })
    # Сводка состояний переносится теми же ключами, что её собрал разбор, и только
    # перечисленные (C1): неперечисленный ключ контракта остаётся нулём, а незнакомый ключ
    # разбора не попадает в ответ, которого карточка не обещала.
    for key in SUMMARY_KEYS:
        if key in collected:
            result[key] = collected[key]
    # Числа расхождений ног круга — полным словарём по замкнутому перечню состояний (C1):
    # перечисленные списки дают примеры, а число обязано быть полным (приём V48/V53/V54/V56).
    result["counts_by_circle_discrepancy"] = circle_discrepancy_counts(
        result["index_only"], result["file_only"], result["uuid_mismatch"])
    warnings.extend(collected.get("warnings") or [])

    # Подсказка о том, чем продолжить, кладётся и в успех, и в отказ: у стадии есть отдельный
    # вход `load_defined_types_tool` (шаг П7), и вызывающий обязан знать это из ответа, а не из
    # молчания (прецедент REPEAT_HINT узлов V49…V57).
    warnings.append(DEFINED_TYPES_REPEAT_HINT)
    if not index_info["available"] and index_info.get("reason"):
        warnings.append(
            f"Индекс состава: {index_info['reason']} — состояния `index_only` и `file_only` "
            "при этом невыразимы (`index_check = not_checked`), а цели значений блока `<Type>` "
            "остаются неразрешёнными записями (Q3): «объекта нет в перечне» от «перечень этой "
            "конфигурации не загружен» не отличить. Отличие от узла V55 названо слоем: "
            "состояний `pending` в схеме вида нет, поэтому недоступный индекс является "
            "предупреждением, а не отказом стадии (правило C2, прецедент V56/V57)"
        )
    observations = collected.get("observations") or {}
    if observations.get("directory_missing"):
        warnings.append(
            f"Каталог {DEFINED_TYPES_DIR}/ в выгрузке отсутствует — определяемых типов у этой "
            "конфигурации нет, и нули таблицы являются ответом о выгрузке, а не отказом стадии "
            "(Q9, вариант A). Корпус четырёх выгрузок такого случая не даёт (замер 1.1: вид "
            "есть везде), поэтому он проверяется фикстурой постоянной проверки узла"
        )
    if observations.get("index_not_provided"):
        warnings.append(
            "Индекс состава не передан разбору — разрешение целей значения не выполнялось: все "
            "значения остались состоянием `unresolved`, и это НЕ ответ «цели нет в "
            "конфигурации» (правило C2)"
        )
    for kind in ("unexpected_dir", "unexpected_file"):
        if observations.get(kind):
            what = "подкаталог" if kind == "unexpected_dir" else "файл не-XML"
            warnings.append(
                f"В каталоге вида найдено {kind}={int(observations[kind])} ({what}) — "
                "примитивность круга (плоский каталог без форм, макетов, команд и модулей, "
                "замер 1.2) перестала быть фактом выгрузки; содержимое этим узлом не "
                "читается, и отсутствие колонок для него является границей узла, а не пропуском"
            )
    if observations.get("type_set_container"):
        warnings.append(
            f"Записей формы `<v8:TypeSet>`: {int(observations['type_set_container'])} — "
            "контейнер множества типов корпусом не давался (замер M4: 0 файлов), поэтому он "
            "называется наблюдением, а не состоянием строки: колонки под содержимое множества "
            "в схеме нет, кратность остаётся состоянием `composite`"
        )
    if observations.get("empty_qualifier_block"):
        warnings.append(
            f"Пустых блоков квалификаторов: {int(observations['empty_qualifier_block'])} — "
            "пустой блок не является состоянием строки вида и называется наблюдением "
            "(прецедент `DayTimes` узла V54): «квалификаторов нет» и «блок пустой» — разные "
            "ответы (замер 2.2 даёт 191 непустой блок в 182 файлах круга)"
        )
    if index_info["available"] and int(result["index_kind_records"]) != int(
            result.get("files_found") or 0):
        warnings.append(
            f"Записей `DefinedType.<Имя>` в индексе состава "
            f"{result['index_kind_records']}, файлов регистрации "
            f"{result.get('files_found')} — круги различаются (замеры 1.1, 1.2 дают равенство "
            "на всех четырёх выгрузках, где вид есть, поэтому расхождение требует объяснения "
            "этим прогоном; расхождения перечислены ключами `index_only` / `file_only`) "
            "одновременно с третьей ногой круга — перечнем заголовка "
            "`configurations.defined_types`, который стадия не перезаписывает"
        )
    if int(result["defined_types_written"]) != int(result.get("files_parsed") or 0):
        warnings.append(
            f"Разбор дал строк {result.get('files_parsed')}, записано "
            f"{result['defined_types_written']} — часть строк в {DEFINED_TYPES_TABLE} не "
            "попала; строка одна на файл регистрации (Q1, вариант A), и молчать об этом "
            "нельзя"
        )
    if any(removed.values()):
        details = ", ".join(f"{table}={count}" for table, count in removed.items())
        warnings.append(
            f"Прежние строки свойств определяемых типов этой конфигурации сняты перед записью: "
            f"{details}. Идемпотентность держится явным DELETE по configuration_uuid: внешнего "
            "ключа и каскада в схеме нет осознанно (прецедент V20.1); новая ревизия на "
            "повторную загрузку той же выгрузки не заводится — история состояний принадлежит "
            "узлу правки объекта, которого в схеме ещё нет (D8). Строки `bsl_modules` (тексты "
            "модулей, узел V47) не тронуты — мера M5"
        )
    result["warnings"] = warnings
    return result
