#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Загрузчик модулей предопределённых программ корня (узел V44, 22.10.2026).

Первый слой загрузки конфигурации (карта слоёв и стадий — карточка правил
`rules:core-rules:functional:goal-and-stages`; прежняя ссылка вела на раздел «Слои загрузки
конфигурации» файла `.clinerules/1c-configurations-core_Rule.md`, снятого репозиторием коммитом
`d957ee2e`): заголовок и свойства (V32/V42) + индекс состава и перечни имён (V33/V43) + ЭТИ ЧЕТЫРЕ
МОДУЛЯ. Общие модули и тексты их модулей — узел V46 (стадия S4), модули объектов — узел V47
(стадия S4b), содержимое дочерних узлов объектов — слой 3, не реализован; здесь они не затрагиваются.

Почему отдельный слой и одновременно шаг цепочки (V45, 22.10.2026):

* слой отделён по транзакции и по ответу (решение оператора): загрузка модулей читает ФАЙЛЫ
  каталога (`Ext/*.bsl`), а заголовок и индекс читают XML; отказ заголовка не обязан становиться
  отказом кода, и наоборот — поэтому `register_configuration` вызывает слой ПОСЛЕ коммита своей
  транзакции, а неудачный слой не отменяет уже записанный заголовок;
* отдельным инструментом слой остаётся потому, что для уже загруженной конфигурации путь к
  каталогу обязан задать оператор: провенанс строк конфигурации в БД не ведётся (решение D-C,
  граница V31), по строке заголовка каталог не восстановить. Внутри цепочки путь восстанавливать
  не нужно — его дал этот же вызов, и ограничение D-C в цепочке не возникает;
* ключ слоя — `configuration_uuid`: строки модулей переживают пересоздание заголовка
  (`force=True` меняет `id`, uuid тот же). Поэтому цепочка и вызывает слой сразу после записи
  заголовка — uuid известен из `Configuration.xml`, — а отдельный инструмент остаётся для
  повторной загрузки модулей уже загруженной конфигурации.

Что обязан назвать ответ (тот же принцип, что карточка V33/V43): сколько строк записано и
куда, по каким состояниям (`file` / `empty_file` / `indexed_no_file` / `undecoded`) — нули
различают «модуля нет в выгрузке» и «индекс не загружен»; подтверждён ли модуль записью
индекса состава (N6) и какие записи индекса словарь не разрешает; что в `Ext/` есть файлы вне
четырёх модулей (общие модули и модули объектов — второй слой); какие прежние строки сняты
(идемпотентность держится явным `DELETE` по `configuration_uuid`: каскада нет).
"""
from pathlib import Path
from typing import Dict, List, Optional

from configuration_load_contract import root_modules_defaults
from configuration_meta_parser import read_configuration_document
from configuration_root_modules import (
    INDEX_SLOTS,
    KIND_BY_SLOT,
    TABLES,
    collect_root_modules,
)
from external_db import transaction
from external_table_writer import ROOT_MODULE_WRITERS

OBJECTS_TABLE = "configuration_objects"


def configuration_uuid_from_layout(source_path) -> Dict:
    """Прочитать uuid конфигурации из `Configuration.xml` каталога выгрузки.

    Отдельная функция нужна потому, что оператор может передать uuid явно: тогда сверяются два
    источника (путь и uuid), и их расхождение обязано быть названо, а не разрешено молча —
    ошибка «записал код не той конфигурации» стоит потерянного кода.
    """
    root = Path(source_path)
    if not root.exists() or not root.is_dir():
        return {"error": f"Каталог выгрузки не найден: {source_path}"}
    xml = None
    for name in ("Configuration.xml", "configuration.xml"):
        candidate = root / name
        if candidate.is_file():
            xml = candidate
            break
    if xml is None:
        return {"error": f"В корне каталога нет Configuration.xml: {source_path}"}
    document = read_configuration_document(xml)
    if not document.get("success"):
        return {"error": document.get("error") or f"Не удалось разобрать {xml}"}
    uuid_value = str(document.get("uuid") or "").strip()
    if not uuid_value:
        return {"error": f"uuid конфигурации пуст в {xml} (правило R3)"}
    return {"uuid": uuid_value, "xml_path": str(xml)}



def read_index_module_rows(cur, configuration_id: int) -> Dict:
    """Выбрать из индекса состава записи четырёх модулей корня (граница N6).

    Источник — таблица `configuration_objects`, а НЕ повторный разбор `ConfigDumpInfo.xml`:
    второго источника того же факта быть не может (правило V43 — два независимых чтения одного
    файла разошлись бы при любом сбое между ними, и заголовок начал бы утверждать состав,
    которого в таблице индекса нет).

    Дочерние записи берутся по имени корневой записи `Configuration.<Имя>`, а не по одному
    `child_type`: иначе запись чужого объекта с тем же `child_type` попала бы в модуль корня.

    Возвращает два разных ключа: `rows` — словарь «слот → запись индекса» (его читает
    `collect_root_modules`), `row_count` — их число (его печатает карточка). Имена обязаны
    различаться: `{**info}` дополняет словарь по тому же ключу, и общий для строки и счётчика
    ключ `rows` дал бы в вызывающий код int вместо словаря — тот же класс дефекта, что свой
    `max(revision_no)` в модуле-вызывателе до узла V19.
    """
    info = {"available": False, "root_name": None, "reason": None, "row_count": 0}
    cur.execute("SELECT to_regclass('public.%s') IS NOT NULL" % OBJECTS_TABLE)
    present = cur.fetchone()
    if not (present and present[0]):
        info["reason"] = (f"таблицы индекса состава ({OBJECTS_TABLE}) в базе нет — примените "
                          "migrate_v33_configuration_objects.sql")
        return {"rows": {}, **info}

    cur.execute(
        f"SELECT name FROM {OBJECTS_TABLE} WHERE configuration_id = %s "
        "AND depth = 0 AND object_type = 'Configuration' ORDER BY id",
        [int(configuration_id)],
    )
    roots = [record[0] for record in cur.fetchall()]
    if not roots:
        info["reason"] = (
            f"в {OBJECTS_TABLE} нет корневой записи `Configuration.<Имя>` для "
            f"configuration_id={configuration_id}: индекс состава этого заголовка не загружен, "
            "поэтому состояние `indexed_no_file` неотличимо от «индекс не загружен»"
        )
        return {"rows": {}, **info}
    if len(roots) > 1:
        info["reason"] = (f"корневых записей индекса несколько ({len(roots)}): "
                          f"{', '.join(str(name) for name in roots[:3])}… — взята первая, "
                          "индекс состава повреждён")
    root_name = roots[0]
    rows: Dict[str, Dict] = {}
    cur.execute(
        f"SELECT name, child_type, object_id FROM {OBJECTS_TABLE} "
        "WHERE configuration_id = %s AND parent_name = %s AND child_type = ANY(%s) "
        "ORDER BY name",
        [int(configuration_id), root_name, list(INDEX_SLOTS)],
    )
    for name, child_type, object_id in cur.fetchall():
        slot = str(child_type or "")
        if slot in KIND_BY_SLOT:
            rows[slot] = {"name": name, "object_id": object_id}
    info.update({"available": True, "root_name": root_name,
                 "row_count": len(rows)})
    return {"rows": rows, **info}


def remove_root_modules(cur, configuration_uuid: str) -> Dict[str, int]:
    """Снять строки четырёх модулей по uuid конфигурации (внутри текущей транзакции).

    Вызывается из `configuration_loader._remove_rows` и отсюда же при повторной загрузке:
    внешнего ключа и каскада в схеме нет осознанно (прецедент V20.1), поэтому очистка обязана
    быть явной — иначе строки остались бы после снятия заголовка и стали бы сиротами, которые
    нельзя ни разрешить, ни отличить от модулей другой конфигурации.
    """
    removed: Dict[str, int] = {}
    for table in TABLES:
        cur.execute(f"DELETE FROM {table} WHERE configuration_uuid = %s::uuid",
                    [str(configuration_uuid)])
        removed[table] = cur.rowcount
    return removed


def _require_header(configuration_uuid: str):
    """Найти строку заголовка по uuid; вернуть карточку или причину отказа.

    Заголовок обязателен: модули корня — второй шаг первого слоя. Вставить их без заголовка
    значило бы создать строки, которые нельзя ни показать в карточке конфигурации, ни снять
    вместе с конфигурацией.
    """
    from configuration_loader import find_configuration  # ленивый импорт — см. шапку модуля
    card = find_configuration(configuration_uuid)
    if isinstance(card, dict) and card.get("error"):
        return None, f"Ошибка запроса: {card['error']}"
    if not card:
        return None, (
            f"Строка заголовка конфигурации с uuid {configuration_uuid} в базе не найдена. "
            "Сначала загрузите каталог точкой входа load_1c_catalog_tool(source_path=…): "
            "иначе модули остались бы без заголовка, а внешний ключ в схеме не поставлен "
            "осознанно (узел V20.1)."
        )
    return card, None


def _stage_failure(reason: str, header: Optional[Dict] = None) -> Dict:
    """Отказ стадии в форме закрытого плоского контракта (C1, C3).

    Причина кладётся в ключ `error` замкнутого словаря `root_modules_defaults()`, а не
    в голый `{"success": False, "error": …}`: по C1 ключей «нет» в ответе быть не
    может — карточка роутера, standalone-инструмент и конвейер читают один и тот же
    закрытый перечень, и каждый отсутствующий ключ каждый вызывающий разрешает своим
    `.get()`-ом по-своему. Если заголовок к моменту отказа уже разрешён, он и
    называется: по `configuration_id` карточка инструмента отличает «заголовка нет»
    от «заголовок есть, слой отказал по файлам или индексу».
    """
    result = root_modules_defaults()
    result["error"] = reason
    if header:
        result["configuration_id"] = header.get("id")
        result["configuration_uuid"] = header.get("uuid")
        result["configuration_name"] = header.get("name")
    return result


def load_root_modules(source_path: str, configuration_uuid: Optional[str] = None) -> Dict:
    """Загрузить четыре модуля предопределённых программ корня конфигурации.

    Порядок: каталог → uuid из `Configuration.xml` (или сверка переданного) → проверка, что
    заголовок загружен → выборка записей индекса состава (подтверждение модулей) → разбор
    файлов `Ext/*.bsl` → одна транзакция: `DELETE` по uuid + вставка по видам. Одна
    транзакция — тот же контракт, что у загрузки внешнего объекта (V12): при ошибке в БД не
    остаётся половины состояния, а оператор получает одну причину.
    """
    resolved = configuration_uuid_from_layout(source_path)
    if resolved.get("error"):
        return _stage_failure(resolved["error"])
    layout_uuid = resolved["uuid"]
    warnings: List[str] = []

    if configuration_uuid and str(configuration_uuid).strip().lower() != layout_uuid.lower():
        # Два источника одного факта указали на разные конфигурации. Молча выбрать один —
        # значит записать код чужой конфигурации и потерять настоящий.
        return _stage_failure(
            f"Передан configuration_uuid={configuration_uuid}, а каталог {source_path} "
            f"описывает конфигурацию с uuid={layout_uuid}. Загрузка не выполнена: укажите "
            "путь каталога этой конфигурации или уберите configuration_uuid."
        )
    configuration_uuid = layout_uuid

    header, reason = _require_header(configuration_uuid)
    if header is None:
        return _stage_failure(reason)

    try:
        with transaction() as cur:
            index_info = read_index_module_rows(cur, int(header["id"]))
            collected = collect_root_modules(source_path, index_info["rows"])
            removed = remove_root_modules(cur, configuration_uuid)
            written_by_table: Dict[str, int] = {}
            for row in collected["rows"]:
                # Писатель выбирается по виду модуля (row["kind"]), а не по имени таблицы из
                # строки: выбор по строке — то место, где ошибка вида превращается в запись
                # не в ту таблицу. Лишний ключ `kind` в INSERT не попадает: спецификацию
                # колонок задаёт писатель.
                writer = ROOT_MODULE_WRITERS[row["kind"]]
                payload = dict(row)
                payload["configuration_uuid"] = configuration_uuid
                writer.insert(cur, payload)
                written_by_table[writer.TABLE] = written_by_table.get(writer.TABLE, 0) + 1
    except Exception as exc:
        # Заголовок здесь уже разрешён — он и называется в отказе (см. _stage_failure).
        return _stage_failure(f"Ошибка записи: {exc}", header=header)

    warnings.extend(collected["warnings"])
    if index_info.get("reason"):
        warnings.append(f"индекс состава: {index_info['reason']}")
    if any(removed.values()):
        warnings.append(
            "Прежние строки модулей этой конфигурации сняты (идемпотентность держится явным "
            "DELETE: каскада и внешнего ключа в схеме нет — V20.1): "
            + ", ".join(f"{table} {count}" for table, count in sorted(removed.items())
                        if count)
        )
    warnings.append(
        "Путь каталога выгрузки задаёт оператор: провенанс строк конфигурации в БД не ведётся "
        "(решение D-C, граница V31), поэтому по строке заголовка каталог не восстанавливается."
    )

    # Успех строится от того же замкнутого словаря контракта, что и отказ (C1):
    # перечень ключей один на оба исхода, и успех не может «забыть» ключ, который
    # читает форматёр. `error` и `tables` остаются из дефолта.
    result = root_modules_defaults()
    result.update({
        "success": True,
        "configuration_id": header["id"],
        "configuration_uuid": configuration_uuid,
        "configuration_name": header.get("name"),
        "written": collected["written"],
        "written_by_table": written_by_table,
        "kinds_total": collected["kinds_total"],
        "counts_by_state": collected["counts"],
        "by_kind": collected["by_kind"],
        "removed_previous": removed,
        "index_available": index_info["available"],
        "index_root_name": index_info.get("root_name"),
        "index_rows": index_info["row_count"],
        "index_matched": collected["index_matched"],
        "index_unmatched": collected["index_unmatched"],
        "stray_ext_bsl": collected["stray_ext_bsl"],
        "warnings": warnings,
    })
    return result

