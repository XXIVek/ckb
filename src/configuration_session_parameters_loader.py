#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Загрузчик свойств параметров сеанса (узел V48, шаг П4, 29.10.2026).

Стадия S4c конвейера первого слоя: свойства вида `SessionParameters` (позиция 2.3
нормативного списка плана `docs/CONFIGURATION_SESSION_PARAMETERS_PLAN.md`) в таблицу
`session_parameters`. Норматив — тот же план (решения Q2, Q3, Q5, правила C1–C3);
разбор файла вида — отдельный модуль `src/configuration_session_parameters.py` (шаг П2),
писатель строки — `SessionParametersRowWriter` (шаг П3).

Почему отдельная стадия, а не третий вид стадии S4 (ответ оператора Q5 от 29.10.2026):
правило C3 требует, чтобы ответ каждой стадии был вложен в свой ключ, — разбивать чужой
ключ `child_objects` по видам значило бы переименовывать контракт V46; порядок `STAGES`
при этом повторяет порядок нормативного списка (2.3 идёт сразу за 2.1–2.2), поэтому S4c
стоит между S4 и S4b. Виды стадии S4 (`CHILD_KINDS`) и её форматёр этим узлом не тронуты;
круг её таблиц (`CHILD_TABLES`) пришлось отделить от круга версионности: проба П4 показала,
что регистрация `session_parameters` (узел П1) молча добавила таблицу V48 к чужой стадии —
дефект назван комментарием у определения `CHILD_TABLES` в контракте.

Почему стадия является одновременно слоем (прецедент V44/V46):

* ключ строки — `configuration_uuid`, а не `id` заголовка: `force=True` меняет id, uuid
  остаётся прежним;
* стадия вызывается ПОСЛЕ коммита транзакции заголовка: `transaction()` каждый раз
  открывает новое соединение, и в собственной транзакции заголовка слой не увидел бы ни
  только что вставленной строки заголовка, ни строк индекса состава;
* отдельный MCP-инструмент `load_session_parameters_tool` (шаг П5) нужен для случая
  «изменились только файлы регистрации»: заголовок и индекс состава при этом не
  меняются, и пересоздавать конфигурацию `force=True` ради свойств вида не нужно. Стадия
  конвейера и этот инструмент вызывают одну и ту же функцию слоя — двух кодов, которые
  могли бы разойтись, в проекте нет; ответ называет, чем делается повтор, строкой
  `SESSION_PARAMETERS_REPEAT_HINT`, а не молчанием.

Что здесь происходит и чего здесь нет:

* круг задают каталог `SessionParameters/` и записи индекса состава того же вида;
  расхождение двух источников называется `index_only` / `file_only` / `uuid_mismatch` —
  замер 2.2 даёт нули, и нули обязаны быть названы, а не подразумеваны;
* разрешение ссылок `cfg:<Вид>Ref.<Имя>` идёт по строкам индекса состава той же
  конфигурации (замер 2.5: 24 из 24 целей — объекты ДРУГИХ видов), поэтому фильтра по типу
  вида при чтении индекса нет намеренно; свой круг вида отбирает сам разбор
  (`kind_index_rows`);
* `DefinedTypes` узла загрузки не имеют (замер 2.4.4): запись класса `defined_type_ref`
  остаётся без ключей цели;
* текстов модулей слой не пишет — модулей, форм и макетов у вида нет (замер 2.2).

Идемпотентность держится явным `DELETE` по `configuration_uuid` (внешнего ключа и каскада
в схеме нет осознанно — прецеденты V20.1, V44, V46), а не новой ревизией: повторная
загрузка той же выгрузки не создаёт истории, снятые строки названы в ответе
(`removed_previous`). Ключом цепочки состояния является
(`configuration_uuid`, `object_name`, `revision_no`) — решение Q2 узла
(`_v48_q2_key_probe.py`: 82 из 125 uuid вида встречаются в двух и более конфигурациях).

Круг пишется одной транзакцией, и отказ разбора любого файла круга останавливает стадию ДО
записи: в базе не остаётся половины строк (приём V12/V46). Молча записать то, что
разобралось, означало бы назвать неполный круг полным составом вида — «параметров нет» и
«параметры не разобрались» различаются состоянием ответа, а не числом строк (C2).

После фиксации загрузчик пересобирает статистику таблицы (`refresh_table_statistics` —
мера V46): планировщик не знает о строках собственной загрузки, и без статистики счётчик
по витрине `v_current_session_parameters` на большой выгрузке выполняется минутами. Отказ
статистики отказом загрузки не является — строки зафиксированы, и это предупреждение.

Прогон шага: `python _v48_p4_loader_probe.py` (живая БД, за собой убирает).
"""
from typing import Any, Dict, List, Optional, Tuple

from configuration_load_contract import (
    SESSION_PARAMETERS_REPEAT_HINT,
    SESSION_PARAMETER_TABLE,
    STATUS_ERROR,
    STATUS_OK,
    session_parameters_defaults,
)
from configuration_object_properties_loader import refresh_table_statistics
from configuration_root_module_loader import configuration_uuid_from_layout
from configuration_session_parameters import (
    collect_session_parameters,
    kind_index_rows,
)
from current_revision import CHANGED_BY_LOAD, FIRST_REVISION, stamp_revision_rows
from external_db import transaction
from external_table_writer import CONFIGURATION_OBJECT_WRITERS

OBJECTS_TABLE = "configuration_objects"
WRITER = CONFIGURATION_OBJECT_WRITERS[SESSION_PARAMETER_TABLE]

# Колонки индекса состава, которые нужны разбору вида: `name`/`object_name` — ключ сверки
# (`SessionParameter.<Имя>`, замер 2.2), `uuid` — цель ссылочного типа и сверка uuid файла
# с записью перечня, `depth`/`parent_name` — состояние «запись индекса имеет глубину»
# (иерархии у вида нет, замер 2.2). Фильтра по типу вида здесь нет намеренно: разрешение
# ссылок обязано видеть записи ЛЮБОГО вида (замер 2.5), а свой круг вида отбирает разбор.
# Источник — строки БД, а не повторный разбор `ConfigDumpInfo.xml` (тот же приём, что
# `read_index_records` узла V46 и `read_index_module_rows` узла V44).
INDEX_ROW_COLUMNS: Tuple[str, ...] = (
    "name", "object_id", "object_type", "object_name", "child_type", "parent_name", "depth",
    "uuid",
)

# Ключи сводки разбора, совпадающие с ключами контракта по имени (один словарь на разбор и
# на ответ): копируются только они — неперечисленный ключ контракта читается нулём (C1), а
# незнакомый ключ разбора не попадает в ответ, которого карточка не обещала (прецедент
# `SUMMARY_KEYS` узла V46).
SUMMARY_KEYS: Tuple[str, ...] = (
    "directory", "files_found", "files_read", "files_failed", "observations",
    "counts_by_state", "types_multiplicity", "types_by_class", "types_total",
    "types_resolved", "types_unresolved_total", "types_unresolved", "index_only",
    "file_only", "uuid_mismatch", "unknown_properties", "unexpected_tags",
    "value_tag_mismatch", "namespace_prefixes",
)


def read_index_records(cur, configuration_id: int) -> Dict[str, Any]:
    """Записи индекса состава этой конфигурации из `configuration_objects` (Н6).

    Пустой ответ означает «индекс недоступен», а не «объектов нет»: при недоступном индексе
    сверка файла регистрации с перечнем невыразима, и вызывающий обязан назвать это
    состоянием загрузки, а не нулями (тот же контракт, что у слоёв V46 и V47). Записей своего
    вида здесь считается ровно столько, сколько их перечисляет индекс (`index_records` ответа
    стадии): по замеру 2.2 это число равно числу файлов, и расхождение обязано быть названо.
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
            "перечнем невозможна"
        )
        return {"rows": [], **info}
    info.update({
        "available": True,
        "row_count": len(records),
        "kind_count": len(kind_index_rows(records)),
    })
    return {"rows": records, **info}


def remove_session_parameters(cur, configuration_uuid: str) -> int:
    """Снять строки свойств параметров сеанса этой конфигурации (внутри транзакции).

    Очистка обязана быть явной: внешнего ключа и каскада в схеме нет осознанно (прецедент
    V20.1), иначе строки пережили бы снятие заголовка и стали бы сиротами, которые нельзя ни
    показать в карточке конфигурации, ни отличить от строк другой конфигурации. Этим же
    фильтром (`configuration_uuid`) держится снятие в `_remove_rows` узла V32/V46 — иначе
    `force=True` оставил бы в базе прежний состав вида.
    """
    cur.execute(
        f"DELETE FROM {SESSION_PARAMETER_TABLE} WHERE configuration_uuid = %s::uuid",
        [str(configuration_uuid)],
    )
    return cur.rowcount


def _require_header(configuration_uuid: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Найти строку заголовка по uuid; вернуть карточку или причину отказа.

    Заголовок обязателен: свойства вида — второй шаг того же первого слоя, и строки без
    заголовка нельзя ни показать в карточке конфигурации, ни снять вместе с ней (внешний ключ
    в схеме не поставлен осознанно — V20.1). Ленивый импорт — тот же обход цикла, что у слоя
    V46.
    """
    from configuration_loader import find_configuration  # ленивый импорт — круг узла V44

    card = find_configuration(configuration_uuid)
    if isinstance(card, dict) and card.get("error"):
        return None, f"Ошибка запроса: {card['error']}"
    if not card:
        return None, (
            f"Строка заголовка конфигурации с uuid {configuration_uuid} в базе не найдена. "
            "Сначала загрузите каталог точкой входа load_1c_catalog_tool(source_path=…): "
            "иначе свойства параметров сеанса остались бы ни на что не указывающими, а "
            "внешний ключ в схеме не поставлен осознанно (узел V20.1)."
        )
    return card, None


def _stage_failure(reason: str, header: Optional[Dict] = None,
                   status: str = STATUS_ERROR,
                   extra: Optional[List[str]] = None) -> Dict[str, Any]:
    """Отказ стадии в форме закрытого контракта (C1, C3).

    Причина кладётся в ключ `error` замкнутого словаря `session_parameters_defaults()`, а
    статус — в `status`: вызывающий отличает «стадия не выполнялась» от «слой отказал» (C2).
    Если заголовок к моменту отказа уже разрешён, он называется: по `configuration_id`
    карточка отличает «заголовка нет» от «заголовок есть, слой отказал по файлам».
    Подсказка о том, чем продолжить, кладётся и в отказ, и в успех: у стадии есть отдельный
    вход `load_session_parameters_tool` (шаг П5), и вызывающий обязан знать это из ответа, а
    не из молчания.
    """
    result = session_parameters_defaults()
    result["status"] = status
    result["error"] = reason
    result["reason"] = reason
    if header:
        result["configuration_id"] = header.get("id")
        result["configuration_uuid"] = header.get("uuid")
        result["configuration_name"] = header.get("name")
    result["warnings"].append(SESSION_PARAMETERS_REPEAT_HINT)
    for warning in extra or []:
        result["warnings"].append(warning)
    return result


def load_session_parameters(source_path: str,
                            configuration_uuid: Optional[str] = None,
                            changed_at=None) -> Dict[str, Any]:
    """Загрузить свойства параметров сеанса конфигурации (узел V48, стадия S4c).

    Порядок: каталог → uuid из `Configuration.xml` (или сверка переданного) → проверка, что
    заголовок загружен → индекс состава из `configuration_objects` (сверка файлов с перечнем
    и разрешение ссылок, Н6) → разбор каталога вида → **транзакция**: `DELETE` по uuid +
    вставка строк круга → отдельной транзакцией `ANALYZE` таблицы (мера V46).

    Отказ разбора любого файла круга останавливает стадию ДО записи: половина круга в базе
    читалась бы как полный состав вида (приём V12/V46). Отсутствие каталога вида — не отказ,
    а ответ о выгрузке: `files_found = 0` с наблюдением `directory_missing`, потому что у
    конфигурации без параметров сеанса их действительно нет (замер 2.1: каталог есть не во
    всех выгрузках).

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
        # значит записать свойства чужой конфигурации (тот же отказ, что у слоёв V44/V46).
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

    collected = collect_session_parameters(source_path, index_rows=index_info["rows"])
    if not collected["success"]:
        failures = collected.get("files_failed") or []
        detail = "; ".join(f"{item.get('source_path')}: {item.get('reason')}"
                           for item in failures[:10])
        return _stage_failure(
            f"Круг не записан: {len(failures)} файл(ов) каталога "
            f"{collected.get('directory')} не разобраны — {detail}. Ни одной строки круга в "
            "базу не записано: половина круга читалась бы как полный состав вида (приём "
            "V12/V46); прежние строки этой конфигурации не сняты",
            header=header,
        )

    removed = 0
    written = 0
    rows = collected.get("rows") or []
    try:
        with transaction() as cur:
            removed = remove_session_parameters(cur, configuration_uuid)
            for row in rows:
                # uuid заголовка знает вызывающий, а не XML объекта — тот же порядок, что у
                # писателей свойств V46 и модулей корня V44.
                row["configuration_uuid"] = configuration_uuid
            # Один момент на всю загрузку (M2): строки одного события не должны нести разные
            # метки, иначе их нельзя прочитать как один состав.
            stamp_revision_rows(rows, revision_no=FIRST_REVISION,
                                changed_by=CHANGED_BY_LOAD, changed_at=changed_at)
            written = WRITER.insert_many(cur, rows)
    except Exception as exc:  # noqa: BLE001 — заголовок уже разрешён, отказ называется им
        return _stage_failure(f"Ошибка записи: {exc}", header=header)

    # ── статистика записанной таблицы (мера V46) ────────────────────────────────────────
    # Отдельная транзакция ПОСЛЕ фиксации записи: планировщик обязан увидеть строки, иначе
    # первый же читатель витрины `v_current_session_parameters` платит минутами за счётчик
    # (замер V46 на BGU2: 8 мин 25 с против 7 мс после ANALYZE). Отказ статистики отказом
    # загрузки не является: строки зафиксированы, и состояние ответа от него не меняется.
    statistics_refreshed = 0
    try:
        with transaction() as cur:
            refresh_table_statistics(cur, (SESSION_PARAMETER_TABLE,))
            statistics_refreshed = 1
    except Exception as exc:  # noqa: BLE001 — ответ описывает запись, а не статистику
        warnings.append(
            f"статистика таблицы {SESSION_PARAMETER_TABLE} не обновлена: {exc}. Строки "
            "записаны, но читатель витрины текущего состояния получит план по пустой "
            "статистике: счётчики на большой выгрузке выполняются минутами вместо "
            "миллисекунд"
        )

    result = session_parameters_defaults()
    result.update({
        "status": STATUS_OK,
        "success": True,
        "configuration_id": header["id"],
        "configuration_uuid": configuration_uuid,
        "configuration_name": header.get("name"),
        "rows_written": int(written),
        "removed_previous": int(removed),
        "index_available": bool(index_info["available"]),
        "index_records": int(index_info["kind_count"]),
        "statistics_refreshed": statistics_refreshed,
    })
    for key in SUMMARY_KEYS:
        if key in collected:
            result[key] = collected[key]
    warnings.extend(collected.get("warnings") or [])

    if not index_info["available"] and index_info.get("reason"):
        warnings.append(
            f"Индекс состава: {index_info['reason']} — состояния `index_only` и `file_only` "
            "при этом невыразимы, и «объекта нет в перечне» от «перечень этой конфигурации "
            "не загружен» не отличить"
        )
    if removed:
        warnings.append(
            "Прежние строки свойств параметров сеанса этой конфигурации сняты перед записью: "
            f"{removed}. Идемпотентность держится явным DELETE по configuration_uuid: внешнего "
            "ключа и каскада в схеме нет осознанно (прецедент V20.1); новая ревизия на "
            "повторную загрузку той же выгрузки не заводится — история состояний принадлежит "
            "узлу правки объекта, которого в схеме ещё нет"
        )
    warnings.append(SESSION_PARAMETERS_REPEAT_HINT)
    result["warnings"] = warnings
    return result
