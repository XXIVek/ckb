#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Загрузчик модулей объектов конфигурации (узел V47, шаг П4, 28.10.2026).

Стадия S4b конвейера первого слоя: тексты `.bsl` модулей объектов конфигурации в
`bsl_modules` (`parent_type = 'configuration_objects'`). Норматив —
`docs/CONFIGURATION_OBJECT_MODULES_PLAN.md` (решения Q2, Q4, Q4.1, Q6, правило C5);
модель сценария — `docs/config-scenarios/01_configuration.md`.

Чем этот модуль является:

* единственной точкой входа стадии. Отдельного MCP-инструмента нет (решение Q4.1):
  правило оператора одно — «ошибка загрузки влечёт перезагрузку всей конфигурации»,
  поэтому реестр `server_configurations_core.py` остаётся пятью инструментами, а ответ
  при отказе требует `load_1c_catalog_tool(source_path=…, force=True)`;
* второй транзакцией после фиксации содержимого конфигурации (решение Q6, граница D7
  узла V46): отказ стадии не откатывает заголовок, индекс состава, модули корня и
  свойства дочерних объектов. В отличие от S3/S4 такая загрузка не называется
  успешной: незавершённая группа объектов загруженной не считается (решение Q4);
* стадией без флага просьбы (Q4). Флаг `with_module_content` узла V46 здесь не
  повторяется: он был следствием цены текстов (188–294 МБ на выгрузку) и оставил в
  живой базе 2 378 дескрипторов с `content_loaded = false`; конфигурация без модулей —
  «такая же битая, как без свойств» (позиция оператора 28.10.2026), поэтому права не
  читать код у стадии нет.

Чего здесь нет: круга и путей (их задаёт словарь `configuration_module_slots`), чтения
файла и сборки строки (писатель `configuration_module_writer`), обогащения (S5 —
отдельный вызов, узлом V47 не выполняется и в `STAGES` не значится).

Состояния и границы:

* индекс состава не разобран → круг не определён: об этом говорит загрузчик, снимая
  стадию в `not_run` (правило C2). Нулевой успех при неразобранном круге слил бы
  «модулей нет» и «круг не читался» в один ответ;
* пустой модуль и отсутствующий файл — состояния без строки (решение Q2), они
  называются счётчиками стадии, а не строками таблицы;
* машинный код `.bin` рядом с отсутствующим исходником (открытая позиция O1) —
  называется числом `bin_side` и примерами; решения о таких модулях узел не принимает;
* круг пуст (записей модулей в индексе нет) — ответ с нулями и отдельной строкой, а не
  молчание: у конфигурации без модульных записей индекса это ответ о выгрузке.

Идемпотентность держится явным `DELETE` писателя (пара `configuration_uuid` +
`parent_type`, `remove_previous_rows`): внешнего ключа на `configurations` в схеме нет
осознанно (прецеденты V20.1, V44, V46), а повторная загрузка не имеет права удвоить
строки. Отказанная группа снимается компенсирующим `DELETE` (`abandon_written_rows`) в
той же транзакции — состояние базы не зависит от того, фиксирует её вызывающий или
откатывает (решение Q4).

После фиксации записи стадия пересобирает статистику `bsl_modules`
(`refresh_table_statistics` — мера V46): без неё читатели витрин текущего состояния
платят минутами (замер V46: 8 мин 25 с против 7 мс). Отказ статистики отказом загрузки
не является — строки зафиксированы, и это предупреждение.
"""
from datetime import datetime
from typing import Any, Dict, Optional

from configuration_load_contract import (
    OBJECT_MODULES_RELOAD_HINT,
    OBJECT_MODULE_TABLE,
    STAGE_OBJECT_MODULES,
    STATUS_ERROR,
    STATUS_NOT_RUN,
    STATUS_OK,
)
from configuration_module_writer import (
    abandon_written_rows,
    result_defaults as payload_defaults,
    write_object_modules,
)
from configuration_object_properties_loader import refresh_table_statistics
from configuration_root_module_loader import configuration_uuid_from_layout
from external_db import transaction


def object_modules_defaults() -> Dict[str, Any]:
    """Закрытый контракт стадии S4b: словарь писателя плюс обёртка стадии (C1, C3).

    Перечень счётчиков задаёт писатель (`configuration_module_writer.result_defaults`) —
    второго перечня в проекте быть не может: проверяющая проверка П5 и проба П4 сверяют
    числа с одним источником. Обёртка стадии добавляет ровно то, чего у писателя нет:
    признак успеха, причину отказа стадии (в отличие от отказа записи), номер стадии,
    круг таблиц и состояние пересборки статистики.
    """
    result = payload_defaults()
    result.update({
        "success": False,
        "reason": None,
        "stage": STAGE_OBJECT_MODULES,
        "tables": [OBJECT_MODULE_TABLE],
        "statistics_refreshed": 0,
        "warnings": [],
    })
    return result


def _stage_failure(result: Dict[str, Any], reason: str,
                   status: str = STATUS_ERROR) -> Dict[str, Any]:
    """Заполнить ответ стадии, которая не состоялась или не удалась (C1, C2).

    `not_run` оставляет `error` пустым: стадия не выполнялась — ей нечего сообщать о
    записи, и причина в `reason`. `error` заполняется только у отказа после начала
    работы: форматёр по этим признакам различает «стадия не выполнена» и «стадия не
    удалась», и путать их нельзя.
    """
    result["status"] = status
    result["success"] = False
    result["reason"] = reason
    if status == STATUS_ERROR:
        result["error"] = reason
    result["warnings"].append(OBJECT_MODULES_RELOAD_HINT)
    return result


def mark_index_unavailable(reason: str = "") -> Dict[str, Any]:
    """Ответ стадии, когда круг не определён: индекс состава не разобран (C2).

    Нули здесь читались бы как «модулей в конфигурации нет», тогда как на самом деле не
    читался круг — записей `child_type` из шести слотов в базе нет вовсе. Право снять
    стадию в `not_run` имеет только загрузчик: он знает, разбирался ли `ConfigDumpInfo.xml`
    в этом вызове (решение V33), а стадия по пустой таблице индекса отличить одно от
    другого не может.
    """
    result = object_modules_defaults()
    detail = (
        "индекс состава (`configuration_objects`) этой загрузкой не разобран — круг "
        "модулей объектов не определён, стадия НЕ выполнялась. Модули объектов появятся "
        "в базе вместе с индексом состава"
        + (f"; причина: {reason}" if reason else "")
    )
    return _stage_failure(result, detail, status=STATUS_NOT_RUN)


def load_object_modules(source_path, configuration_uuid: Optional[str] = None,
                        changed_at: Optional[datetime] = None) -> Dict[str, Any]:
    """Записать модули объектов конфигурации второй транзакцией загрузки (шаг П4).

    Порядок: каталог → uuid из `Configuration.xml` (или сверка переданного) →
    **транзакция**: снятие прежних строк круга узла + вставка + (при отказе группы)
    компенсирующий снятие `DELETE` → **отдельная транзакция**: `ANALYZE bsl_modules`.

    `source_path` — каталог ВЫГРУЗКИ этой конфигурации (тот же, что получает
    `load_1c_catalog_tool`). Писатель сверяет uuid корня `Configuration.xml` со строкой
    заголовка и отказывает при расхождении: иначе код лёг бы не той конфигурации, и снять
    его вместе с этой было бы нельзя.

    `changed_at` — общий штамп события загрузки. Его передаёт загрузчик, а не стадия:
    строки одного события обязаны нести одно время (M2, `src/current_revision.py`); без
    него писатель возьмёт время своей транзакции, и модули окажутся загруженными на
    секунду позже остального состава.

    Возвращает словарь `object_modules_defaults()`. `success = False` означает, что
    конфигурация неполная: вызывающий обязан пометить ответ (`load_incomplete`) и назвать
    незакрытую группу — сказать «загружено» без этой строки значило бы утверждать состав,
    которого в базе нет (решение Q4, критерий 8 плана).
    """
    result = object_modules_defaults()

    uuid_info = configuration_uuid_from_layout(source_path)
    if "uuid" not in uuid_info:
        return _stage_failure(result, uuid_info.get("error")
                              or f"Каталог выгрузки не читается: {source_path}")
    layout_uuid = str(uuid_info["uuid"])
    if configuration_uuid and str(configuration_uuid).strip().lower() != layout_uuid.lower():
        # Два источника одного факта указали на разные конфигурации: молча выбрать один —
        # значит записать код чужой конфигурации (тот же отказ, что у слоёв V44 и V46).
        return _stage_failure(result, (
            f"Передан configuration_uuid={configuration_uuid}, а каталог {source_path} "
            f"описывает конфигурацию с uuid={layout_uuid}. Модули объектов легли бы не "
            "той конфигурации, и снять их вместе с этой было бы нельзя."))
    configuration_uuid = layout_uuid

    try:
        with transaction() as cur:
            stage = write_object_modules(cur, configuration_uuid,
                                         dump_dir=str(source_path), changed_at=changed_at)
            if stage.get("status") == STATUS_ERROR:
                # Компенсирующий снятие `DELETE` в той же транзакции (решение Q4):
                # отказанная группа не оставляет частичных строк, и состояние базы не
                # зависит от того, фиксирует вызывающий транзакцию или откатывает. Прежние
                # строки при этом остаются снятыми — индекс состава пересоздан этой же
                # загрузкой, и старые строки больше не описывают текущий состав.
                stage["compensated_rows"] = abandon_written_rows(
                    cur, configuration_uuid, stage)
    except Exception as exc:  # noqa: BLE001 — отказ стадии называется, а не бросается
        return _stage_failure(result, f"запись модулей объектов не состоялась: {exc}")

    # Счётчики приходят от писателя без переименования (C3), обёртка стадии остаётся
    # нашей: ключей, которых нет в контракте стадии, у ответа быть не может (C1).
    result.update(stage)

    if result["status"] == STATUS_ERROR:
        result["success"] = False
        result["reason"] = result["error"]
        if OBJECT_MODULES_RELOAD_HINT not in result["warnings"]:
            result["warnings"].append(OBJECT_MODULES_RELOAD_HINT)
        return result

    result["status"] = STATUS_OK
    result["success"] = True

    groups = result.get("groups") or {}
    if not int(groups.get("seen") or 0) and not int(result.get("written") or 0):
        # Пустой круг — ответ о выгрузке, а не пропуск стадии. Сказать это обязан тот,
        # кто круг читал: по одним нулям эти два ответа неразличимы (C2).
        result["warnings"].append(
            "круг узла пуст: записей модулей шести слотов в индексе состава этой "
            "конфигурации нет — нули являются ответом о выгрузке, а не пропуском стадии "
            "(стадия выполнена, статус ok)"
        )

    # ── статистика записанной таблицы (мера V46, замер 28.10.2026) ───────────────────
    # Отдельная транзакция ПОСЛЕ фиксации записи: планировщик обязан увидеть строки.
    # Отказ статистики загрузку не отменяет — строки зафиксированы, поэтому это
    # предупреждение, а не отказ стадии.
    try:
        with transaction() as cur:
            result["statistics_refreshed"] = refresh_table_statistics(
                cur, (OBJECT_MODULE_TABLE,))
    except Exception as exc:  # noqa: BLE001 — ответ описывает запись, а не статистику
        result["warnings"].append(
            f"статистика {OBJECT_MODULE_TABLE} не обновлена: {exc}. Строки зафиксированы, "
            "но читатель витрин текущего состояния получит план по пустой статистике: "
            "счётчики на большой выгрузке выполняются минутами вместо миллисекунд"
        )
    return result


__all__ = ("load_object_modules", "mark_index_unavailable", "object_modules_defaults")


