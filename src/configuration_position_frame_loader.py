#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Загрузчик свойств позиций пакета (узел V59, шаг П6, 06.11.2026).

Один загрузчик на десять стадий пакета «плоская регистрация» (позиции 2.18, 2.19, 2.20,
2.23, 2.25, 2.26, 2.27, 2.28, 5.2, 19 нормативного списка). Отличие от V48…V58 названо
прямо: там на позицию приходилось по слою разбора (1 200–3 900 строк) и по загрузчику
(300–450 строк), а разница между десятью позициями пакета — список тегов `Properties`,
наличие `InternalInfo`, наличие `ChildObjects` и наличие `Ext/` (замер
`probes/v59/_v59_p0_frame_probe.py`). Всё остальное общее: файл
`<Контейнер>/<Имя>.xml`, корень `MetaDataObject → <Вид>`, ключ цепочки состояния
`(configuration_uuid, object_name, revision_no)`, витрина `v_current_<table>`.

Что здесь происходит и чего здесь нет:

* круг позиции задают каталог выгрузки и записи индекса состава того же вида; перечень
  заголовка `configurations.<вид>` (третья нога) стадия не пишет и не читает — его
  заполняет S2 узла V43, и граница называется ответом стадии (прецедент V52/V56/V57);
* индекс состава НЕ является условием записи: при недоступном индексе сверка остаётся
  состоянием `not_checked` с наблюдением `index_not_provided` — «объекта нет в перечне» и
  «перечень не загружен» являются разными ответами (правило C2, прецедент V56/V57);
* отсутствующий каталог вида — не отказ, а ответ о выгрузке: нули с наблюдением
  `directory_missing`. У позиций 2.27 (`Styles`) и 19 (`ExternalDataSources`) контейнера
  нет в трёх из четырёх выгрузок корпуса, у 5.2 — в ZUP31 и UT11: случай достижим
  настоящим прогоном, а не только фикстурой (отличие от V55/V58);
* содержимое вида (`Ext/`) считается ЧИСЛОМ и состоянием и не разбирается: круг
  содержимого — отдельная работа, она названа строкой контракта позиции;
* тексты `bsl_modules` (узел V47) стадия не читает и не снимает (мера M5): модули
  `Ext/RecordSetModule.bsl`, `Ext/Module.bsl` являются содержимым вида.

Идемпотентность держится явным `DELETE` по `configuration_uuid` (внешнего ключа и каскада
в схеме нет осознанно — прецеденты V20.1, V44, V46), а не новой ревизией: повторная
загрузка той же выгрузки не создаёт истории, снятые строки названы в ответе
(`removed_previous`). Круг пишется одной транзакцией, и отказ разбора любого файла круга
останавливает стадию ДО записи (приём V12/V46). После фиксации загрузчик пересобирает
статистику таблицы (мера V46): без статистики счётчик по витрине текущего состояния на
большой выгрузке читается минутами (замер V46 на BGU2: 8 мин 25 с против 7 мс).

Запуск шага: `python probes/v59/_v59_p6_loader_probe.py` (живая БД, за собой убирает).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from configuration_load_contract import STATUS_ERROR, STATUS_NOT_RUN, STATUS_OK
from configuration_object_properties_loader import refresh_table_statistics
from configuration_position_frame import (
    REGISTRATION_STATE_VALUES,
    collect_position_frame,
)
from configuration_position_spec import (
    CONTENT_STATE_VALUES,
    REGISTRATION_DISCREPANCY_STATES,
    empty_answer,
    header_column,
    ordered_specs,
    stage_remove_order,
    stage_tables,
)
from current_revision import CHANGED_BY_LOAD, FIRST_REVISION, stamp_revision_rows
from external_db import transaction
from external_table_writer import CONFIGURATION_OBJECT_WRITERS

OBJECTS_TABLE = "configuration_objects"
# Поля строки индекса состава — те же, что читают слои V48…V58 (Н6): форму задаёт узел
# V33, а не позиция списка.
INDEX_ROW_COLUMNS: Tuple[str, ...] = (
    "name", "object_id", "object_type", "object_name", "child_type", "parent_name",
    "depth", "uuid",
)


def by_table() -> Dict[str, Dict[str, Any]]:
    """Позиция по имени таблицы — единственный способ найти строку контракта из кода."""
    return {spec["table"]: spec for spec in ordered_specs()}



def _stage_failure(spec: Dict[str, Any], reason: str, header: Optional[Dict] = None,
                   status: str = STATUS_ERROR,
                   extra: Optional[List[str]] = None) -> Dict[str, Any]:
    """Отказ стадии в форме контракта (C1, C3): причина в `error`, статус в `status`.

    Подсказка «чем продолжить» кладётся и в отказ, и в успех: у пакета будет отдельный
    вход загрузки (шаг П7), и вызывающий обязан знать это из ответа, а не из молчания
    (прецеденты REPEAT_HINT узлов V48…V58).
    """
    result = empty_answer(spec)
    # Словарь состояний сверки ног круга берётся из слоя разбора — там же, где объявлены
    # сами состояния. В отказе он нулевой, потому что сверка не выполнялась: нулевой
    # словарь обязан быть назван, а не отсутствовать (C1, C2).
    result["counts_by_registration_state"] = {
        state: 0 for state in REGISTRATION_STATE_VALUES}
    result["status"] = status
    result["error"] = reason
    result["reason"] = reason
    result["success"] = False
    if header:
        result["configuration_id"] = header.get("id")
        result["configuration_uuid"] = header.get("uuid")
        result["configuration_name"] = header.get("name")
    result["warnings"].append(
        "Чем продолжить: повторить загрузку конфигурации точкой входа "
        "load_1c_catalog_tool(source_path=…, force=True) — стадия идемпотентна по "
        "configuration_uuid")
    result["warnings"].append(
        f"Граница круга позиции {spec['position']}: {spec['boundary']}")
    for warning in extra or []:
        result["warnings"].append(warning)
    return result


def not_run_answer(spec: Dict[str, Any],
                   reason: str = "стадия не выполнялась: конвейер остановлен раньше") -> Dict[str, Any]:
    """Ответ позиции, стадия которой НЕ выполнялась (правило C2, прецедент `*_defaults` V48…V58).

    Нули состояний обязаны быть названы: карточка остановки печатает разделы всех стадий, и
    отсутствующий ключ читался бы как «такой стадии нет», а не как «стадии не было». Статус
    `not_run` отличается от `error` именно этим: круг не читался вовсе (в отличие от отказа,
    где круг читался и отказал).
    """
    result = _stage_failure(spec, reason, status=STATUS_NOT_RUN)
    result["warnings"].insert(
        0, "Стадия не выполнялась: её круг не читался и строки таблицы не менялись — "
           "нули являются ответом «не смотрели», а не ответом «в выгрузке ничего нет» (C2)")
    return result


def _require_header(configuration_uuid: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Найти строку заголовка по uuid; вернуть карточку или причину отказа (прецедент V58).

    Заголовок обязателен: свойства позиции — второй слой того же первого слоя, и строки без
    заголовка нельзя ни показать в карточке конфигурации, ни снять вместе с ней.
    """
    from configuration_loader import find_configuration  # ленивый импорт — круг узла V44

    card = find_configuration(configuration_uuid)
    if isinstance(card, dict) and card.get("error"):
        return None, f"Ошибка запроса: {card['error']}"
    if not card:
        return None, (
            f"Строка заголовка конфигурации с uuid {configuration_uuid} в базе не найдена. "
            "Сначала загрузите каталог точкой входа load_1c_catalog_tool(source_path=…): "
            "иначе свойства позиции остались бы ни на что не указывающими, а внешний ключ "
            "в схеме не поставлен осознанно (узел V20.1)."
        )
    return card, None


def read_index_records(cur, configuration_id: int,
                       kind_tag: str) -> Dict[str, Any]:
    """Записи индекса состава этого заголовка (Н6). Пустой ответ = «индекс недоступен».

    Отбор идёт по `object_type`, а не по имени каталога: имена различаются у позиции 2.20
    (`XDTOPackages` против `XDTOPackage`), и совпадение по имени дало бы `index_only` при
    исправном индексе (замер P0, раздел «Отличия», строка «Имя каталога ≠ имя вида»).

    Число записей вида (`index_kind_records` ответа стадии) считается тем же отбором, что и
    сверка внутри разбора — `index_rows_of_kind`, то есть с правилом K1 (только
    `depth = 0`). Иначе стадия обещала бы одно число записей вида, а круг по нему же
    посчитал бы другое: у MinCfg строка `CommonTemplate.Макет` есть и на `depth = 0`, и на
    `depth = 1` (ребёнок `Template`), и без K1 число записей вида было бы завышено, а
    `index_only` появился бы при исправном индексе (замер пробы П6, 06.11.2026).
    """
    from configuration_position_frame import index_rows_of_kind

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
            "перечнем невозможна"
        )
        return {"rows": [], **info}
    kind_rows = index_rows_of_kind(records, kind_tag)
    info.update({"available": True, "row_count": len(records),
                 "kind_count": len(kind_rows)})
    return {"rows": records, **info}


def frame_positions() -> List[str]:
    return [spec["position"] for spec in ordered_specs()]


def remove_position_frames(cur, configuration_uuid: str) -> Dict[str, int]:
    """Снять строки свойств десяти позиций пакета этой конфигурации (шаг П8 узла V58).

    Очистка обязана быть явной и стоять в контуре снятия заголовка: внешнего ключа и
    каскада в схеме нет осознанно (прецеденты V20.1, V44, V46, V48…V58), и без неё
    `force=True` оставил бы в базе прежний состав видов пакета — тот же дефект, который
    назван в снятии каждого прежнего узла. Найдено регрессией стоп-проб (шаг П8 узла
    V58, 06.11.2026): остановка конвейера на более ранней стадии оставляла строки
    позиций от предыдущей загрузки, поэтому «стадия не выполнялась» читалась прежним
    составом, а не нулями (правило C2), и карточка неполной загрузки противоречила базе.

    Круг снятия задаёт строка пакета (`ordered_specs` + `stage_remove_order`), а не
    список имён в этом файле: вторая копия круга разошлась бы с загрузчиком незаметно.
    Детей и каскадных внешних ключей у позиций нет (замер П0), поэтому порядок «сначала
    дети» здесь не нужен. Число снятых строк возвращается по каждой таблице: оператор
    обязан видеть полное состояние, снятое `force=True` (мера M7), а не только индекс.

    Строки `bsl_modules` этим фильтром НЕ снимаются намеренно, и это названо, а не
    обойено (мера M5): их пишет узел V47, и снятие свойств вида не удаляет содержимое
    чужого узла.
    """
    removed: Dict[str, int] = {}
    for spec in ordered_specs():
        for table in stage_remove_order(spec):
            cur.execute(f"DELETE FROM {table} WHERE configuration_uuid = %s::uuid",
                        [str(configuration_uuid)])
            removed[table] = int(cur.rowcount)
    return removed


def load_position_frame(spec: Dict[str, Any], source_path: str,
                        configuration_uuid: str,
                        changed_at=None) -> Dict[str, Any]:
    """Записать круг одной позиции пакета (шаг П6).

    Аргументы:
      spec                — строка контракта позиции (из `configuration_position_spec`);
      source_path         — корень выгрузки конфигурации;
      configuration_uuid  — uuid заголовка, строки круга версионируются по нему;
      changed_at          — общий момент на всю загрузку (M2); по умолчанию текущий.

    Возвращает словарь контракта позиции (`empty_answer`): `status` + `success` + числа
    состояний + `counts_by_registration_discrepancy` + `counts_by_content_state` +
    `examples` + `warnings`. Отказ разбора любого файла круга останавливает стадию до
    записи: половины строк в базе не остаётся (приём V12/V46).
    """
    from datetime import datetime

    table = spec["table"]
    if table not in CONFIGURATION_OBJECT_WRITERS:
        return _stage_failure(
            spec,
            f"писателя таблицы {table} в реестре `CONFIGURATION_OBJECT_WRITERS` нет: "
            "реестр пополняется строкой контракта позиции (шаг П4), а не списком имён")
    writer = CONFIGURATION_OBJECT_WRITERS[table]

    header, reason = _require_header(configuration_uuid)
    if reason:
        return _stage_failure(spec, reason)

    if changed_at is None:
        changed_at = datetime.now()

    directory = Path(source_path) / spec["container"]
    index_info: Dict[str, Any] = {"available": False, "row_count": 0, "kind_count": 0,
                                  "reason": "индекс не читался"}
    with transaction() as cur:
        index_info = read_index_records(cur, int(header["id"]), spec["kind_tag"])
    index_rows = index_info["rows"]

    collected = collect_position_frame(spec, directory, index_rows)
    warnings: List[str] = []
    observations = collected.get("observations") or {}

    if collected.get("failures"):
        failures = collected["failures"]
        return _stage_failure(
            spec,
            "Круг не записан: " + "; ".join(str(item) for item in failures[:10])
            + (f" и ещё {len(failures) - 10}" if len(failures) > 10 else "")
            + ". Ни одной строки не записано, прежние строки этой конфигурации не сняты "
              "(приём V12/V46: половины строк в базе не остаётся)",
            header=header,
        )
    if collected.get("duplicate_names"):
        duplicates = collected["duplicate_names"]
        return _stage_failure(
            spec,
            "Круг не записан: повторные имена вида внутри выгрузки — "
            + "; ".join(f"{item.get('object_name')} ({item.get('first')} ↔ "
                        f"{item.get('second')})" for item in duplicates[:10])
            + f". Строки круга нарушили бы UNIQUE (configuration_uuid, object_name, "
              f"revision_no) таблицы {table}, поэтому отказ называется списком имён до "
              "записи: цепь ревизий ограничена uuid конфигурации (M1), и две выгрузки с "
              "одинаковым именем вида — разные строки, а два файла одной выгрузки — одна и "
              "та же строка",
            header=header,
        )

    rows = collected["rows"]
    removed: Dict[str, int] = {}
    written: Dict[str, int] = {}
    try:
        with transaction() as cur:
            # Снятие прежних строк этой конфигурации (идемпотентность по
            # configuration_uuid — V20.1/V44/V46): каскада нет, поэтому он бы их не снял.
            # Таблиц детей у позиции нет — круг снятия равен таблице вида (замер P0).
            cur.execute(f"DELETE FROM {table} WHERE configuration_uuid = %s::uuid",
                        [str(configuration_uuid)])
            removed[table] = int(cur.rowcount)
            for row in rows:
                # uuid заголовка знает вызывающий, а не XML файла вида — тот же порядок,
                # что у писателей свойств V46, модулей корня V44 и видов V51…V58.
                row["configuration_uuid"] = configuration_uuid
            # Один момент на всю загрузку (M2): строки одного события не должны нести
            # разные метки, иначе их нельзя прочитать как один состав.
            stamp_revision_rows(rows, revision_no=FIRST_REVISION,
                                changed_by=CHANGED_BY_LOAD, changed_at=changed_at)
            written[table] = int(writer.insert_many(cur, rows))
    except Exception as exc:  # noqa: BLE001 — заголовок уже разрешён, отказ называется им
        return _stage_failure(spec, f"Ошибка записи: {exc}", header=header)


    # Статистика — отдельная транзакция ПОСЛЕ фиксации записи (мера V46). Отказ
    # статистики отказом загрузки не является: строки зафиксированы.
    statistics_refreshed = 0
    try:
        with transaction() as cur:
            refresh_table_statistics(cur, list(stage_tables(spec)))
            statistics_refreshed = 1
    except Exception as exc:  # noqa: BLE001 — ответ описывает запись, а не статистику
        warnings.append(
            f"статистика таблицы {table} не обновлена: {exc}. Строки записаны, но "
            "читатель витрины текущего состояния получит план по пустой статистике: "
            "счётчики на большой выгрузке выполняются минутами вместо миллисекунд"
        )

    result = empty_answer(spec)
    result.update({
        "status": STATUS_OK,
        "success": True,
        "configuration_id": header["id"],
        "configuration_uuid": configuration_uuid,
        "configuration_name": header.get("name"),
        "directory": collected.get("directory") or spec["container"],
        "files_found": int((collected.get("counts") or {}).get("registration_files", 0)),
        "rows_written": int(sum(written.values())),
        "written_by_table": {table: int(written.get(table, 0))},
        "removed_previous": int(sum(removed.values())),
        "removed_by_table": {table: int(removed.get(table, 0))},
        "index_available": bool(index_info["available"]),
        "index_kind_records": int(index_info["kind_count"]),
        "statistics_refreshed": statistics_refreshed,
        # Виновники поимённо переносятся теми же ключами, что их собрал разбор:
        # пустой список читается как «расхождений нет» (прецедент V48/V50/V57/V58).
        "file_only": collected.get("file_only") or [],
        "index_only": collected.get("index_only") or [],
        "uuid_mismatch": collected.get("uuid_mismatch") or [],
        "duplicate_names": collected.get("duplicate_names") or [],
        "examples": collected.get("examples") or [],
    })
    # Сводка состояний переносится тем же словарём, что её собрал разбор: ключи
    # `zero_counts(spec)` — общий словарь разбора и контракта ответа (приём одного
    # словаря загрузчиков V46/V48…V58). Ключ вне контракта называется предупреждением,
    # а не добавляется в ответ молча: ответ не должен обещать то, чего форматёр не печатает.
    for key, value in (collected.get("counts") or {}).items():
        if key in result:
            result[key] = int(value)
        else:
            warnings.append(
                f"ключ сводки {key!r} вне контракта позиции {spec['position']} — в ответ "
                "не внесён (словарь задаёт строка контракта)")
    # Числа расхождений ног круга, состояний содержимого и наблюдений — полными
    # словарями по замкнутым перечням слоя (C1): списки выше дают виновников, словари —
    # числа, и отсутствие ключа читалось бы как «не смотрели».
    result["counts_by_registration_discrepancy"] = {
        state: int(result.get(state) or 0)
        for state in REGISTRATION_DISCREPANCY_STATES}
    result["counts_by_registration_state"] = dict(
        collected.get("counts_by_registration_state") or {})
    result["counts_by_content_state"] = {
        state: int((collected.get("counts_by_content_state") or {}).get(state, 0))
        for state in CONTENT_STATE_VALUES}
    result["counts_by_observation"] = dict(observations)
    warnings.extend(collected.get("warnings") or [])
    warnings.append(
        "Чем продолжить: повторить загрузку конфигурации точкой входа "
        "load_1c_catalog_tool(source_path=…, force=True) — стадия идемпотентна по "
        "configuration_uuid")
    warnings.append(
        f"Граница круга позиции {spec['position']}: {spec['boundary']}. Перечень заголовка "
        f"configurations.{header_column(spec['kind_tag']) or 'не задан контрактом V43'} "
        "этой стадией не заполняется — его пишет S2 узла V43, и расхождение с ним является "
        "наблюдением, а не отказом (прецедент V52/V56/V57)")
    if not index_info["available"] and index_info.get("reason"):
        warnings.append(
            f"Индекс состава: {index_info['reason']} — состояния `index_only` и `file_only` "
            "при этом невыразимы (`registration_check = not_checked`), и это НЕ ответ "
            "«объекта нет в перечне» (правило C2)"
        )
    if observations.get("directory_missing"):
        warnings.append(
            f"Каталог {spec['container']}/ в выгрузке отсутствует — вида нет у этой "
            "конфигурации, и нули таблицы являются ответом о выгрузке, а не отказом стадии "
            "(случай достижим настоящим прогоном: 2.27 и 19 отсутствуют в трёх выгрузках "
            "корпуса, 5.2 — в ZUP31 и UT11)"
        )
    if observations.get("index_not_provided"):
        warnings.append(
            "Индекс состава не передан разбору — сверка с перечнем не выполнялась: все "
            "строки остались состоянием `not_checked`, и это НЕ ответ «объекта нет в "
            "перечне» (правило C2)"
        )
    for kind in ("unexpected_dir", "unexpected_file"):
        if observations.get(kind):
            what = "подкаталог" if kind == "unexpected_dir" else "файл не-XML"
            warnings.append(
                f"В каталоге вида найдено {kind}={int(observations[kind])} ({what}) — "
                "плоская регистрация (замер P0: подкаталогов нет ни у одной позиции) "
                "перестала быть фактом выгрузки; содержимое этим кругом не читается, и "
                "отсутствие колонок для него является границей круга, а не пропуском"
            )
    result["warnings"] = warnings
    return result

