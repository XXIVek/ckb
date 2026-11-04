#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Загрузчик свойств ботов конфигурации (узел V55, шаг П4, 04.11.2026).

Стадия S4j конвейера первого слоя: свойства вида `Bots` (позиция 2.10 нормативного списка
плана `docs/CONFIGURATION_BOTS_PLAN.md`) в таблицу `bots`. Норматив — тот же план (решения
Q1 (ответ оператора — вариант A), Q2–Q7, правила C1–C3); разбор файла вида — отдельный
модуль `src/configuration_bots.py` (шаг П3), писатель строки — `BotsRowWriter` и запись в
реестр `CONFIGURATION_OBJECT_WRITERS` (этот же шаг П4).

Почему стадия отдельная, а не ещё один вид стадии S4 (прецедент V48…V54): правило C3
требует, чтобы ответ каждой стадии был вложен в свой ключ `bots`, — разбивать чужой ключ
значило бы переименовывать контракт соседнего узла. Порядок `STAGES` повторяет порядок
нормативного списка (2.10 идёт сразу за 2.9), поэтому S4j стоит между S4i и S4b — это
шаг П5. Круг таблиц стадии (`BOTS_TABLES`) и его включение в `FOREIGN_STAGE_TABLES`
объявлены уже здесь: регистрация `bots` в круге версионности (`CONFIGURATION_VERSIONED_TABLES`,
шаг П1/П4) без объявленного круга молча добавила бы таблицу к кругу стадии S4, и та снимала
бы и анализировала бы чужие строки (дефект, названный узлами V49…V54).

Что здесь происходит и чего здесь нет:

* круг задают каталог `Bots/` и записи индекса состава того же вида; расхождение ног
  называется `index_only` / `file_only` / `uuid_mismatch` — замер 1.1 даёт ноль строк у трёх
  выгрузок, где вида нет, и две строки у MinCfg, а нули обязаны быть названы, а не
  подразумеваны;
* разрешение ссылки `Picture` идёт по строкам индекса состава той же конфигурации (замер 2.1:
  `CommonPicture.ОбщаяКартинка1` — 1 из 2), поэтому фильтра по типу вида при чтении индекса
  нет намеренно; свой круг вида отбирает сам разбор (`kind_index_rows`);
* признак `module_loaded` проверяется по витрине `v_current_bsl_modules` (тексты пишет узел
  V47), а не повторным разбором `ConfigDumpInfo.xml` (правило V43); сама стадия текстов не
  читает и строк `bsl_modules` НЕ снимает — мера M5: снятие свойств вида не имеет права
  удалять содержимое чужого узла;
* форм, макетов и команд у вида нет ни файлами, ни индексом состава (замер 1.2), поэтому
  общих таблиц детей стадия не касается — в отличие от V51/V52.

Почему индекс состава является условием записи, а не наблюдением (отличие от V48/V53/V54):
без его строк состояния `pending` (разрешение ссылки не проверялось) и `module_state =
pending` невыразимы колонками схемы — CHECK `bots_picture_state_known` и
`bots_module_state_known` их отклоняют, потому что «не проверяли» и «не разрешилось» —
разные ответы (шаг П3, пункт 1 плана). Записывать половину круга при невыразимой второй
половине значило бы назвать неполный состав полным (приём V12/V46), поэтому стадия
останавливается ДО записи и называет причину и способ продолжить.

Идемпотентность держится явным `DELETE` по `configuration_uuid` (внешнего ключа и каскада в
схеме нет осознанно — прецеденты V20.1, V44, V46), а не новой ревизией: повторная загрузка
той же выгрузки не создаёт истории, снятые строки названы в ответе (`removed_previous`).
Ключом цепочки состояния является (`configuration_uuid`, `object_name`, `revision_no`) —
решение Q2 узла (замер M1: uuid вида встречается в нескольких конфигурациях, имя уникально
внутри конфигурации).

Круг пишется одной транзакцией, и отказ разбора любого файла круга останавливает стадию ДО
записи: в базе не остаётся половины строк (приём V12/V46). Отсутствие каталога вида — не
отказ, а ответ о выгрузке: `files_found = 0` с наблюдением `directory_missing`, потому что у
трёх из четырёх выгрузок ботов действительно нет (замер 1.1, Q9 вариант A).

После фиксации загрузчик пересобирает статистику таблицы (`refresh_table_statistics` — мера
V46): планировщик не знает о строках собственной загрузки, и без статистики счётчик по
витрине `v_current_bots` на большой выгрузке выполняется минутами. Отказ статистики отказом
загрузки не является — строки зафиксированы, и это предупреждение.

Прогон шага: `python _v55_p4_loader_probe.py` (живая БД, за собой убирает).
"""
from typing import Any, Dict, List, Optional, Tuple

from configuration_bots import (
    COUNT_KEYS,
    DIR_NAME as BOTS_DIR,
    INDEX_OBJECT_TYPE as BOTS_META_TYPE,
    TABLE_NAME as BOTS_TABLE,
    collect_bots,
    kind_index_rows,
    module_index_rows,
)
from configuration_load_contract import (
    BOTS_CIRCLE_BOUNDARY,
    BOTS_REPEAT_HINT,
    BOTS_TABLES,
    STATUS_ERROR,
    STATUS_OK,
    bots_defaults,
)
from configuration_object_properties_loader import refresh_table_statistics
from configuration_root_module_loader import configuration_uuid_from_layout
from current_revision import CHANGED_BY_LOAD, FIRST_REVISION, stamp_revision_rows
from external_db import transaction
from external_table_writer import CONFIGURATION_OBJECT_WRITERS

OBJECTS_TABLE = "configuration_objects"
# Витрина текущего состояния модулей (узел V19): признак `module_loaded` читается по ней, а
# не по таблице `bsl_modules` целиком, иначе строка прежней ревизии читалась бы записанной.
# Имя витрины порождает `current_view()`, а не строка, придуманная здесь.
BSL_MODULES_VIEW = "v_current_bsl_modules"
WRITER = CONFIGURATION_OBJECT_WRITERS[BOTS_TABLE]

# Колонки индекса состава, которые нужны разбору вида: `name`/`object_name` — ключ сверки
# (`Bot.<Имя>`, замер 1.2), `uuid` — цель ссылочного типа и сверка uuid файла с записью
# перечня, `object_id` — подтверждение состояния `exact` (CHECK
# `bots_picture_state_matches_value` требует его), `child_type`/`parent_name`/`depth` — форма
# записи (иерархии раскладки у вида нет, замер 1.2). Фильтра по типу вида здесь нет
# намеренно: разрешение ссылки обязано видеть записи ЛЮБОГО вида (`CommonPicture.*` — объект
# другого вида, замер 2.1), а свой круг вида отбирает сам разбор (`kind_index_rows` /
# `module_index_rows`). Источник — строки БД, а не повторный разбор `ConfigDumpInfo.xml`
# (тот же приём, что `read_index_records` узлов V46/V48/V53/V54).
INDEX_ROW_COLUMNS: Tuple[str, ...] = (
    "name", "object_id", "object_type", "object_name", "child_type", "parent_name",
    "depth", "uuid",
)

# Колонки витрины модулей, нужные для признака `module_loaded`: имя модуля вида собирается
# из видового имени объекта и рода модуля (`Bot.<Имя>.Module` — та же форма, что у записи
# индекса состава, замер 1.2); `file_path` остаётся в ответе подтверждением того, что строка
# относится к этой выгрузке.
MODULE_ROW_COLUMNS: Tuple[str, ...] = (
    "object_type", "object_name", "module_type", "file_path",
)

# Ключи сводки разбора, совпадающие с ключами контракта по имени (один словарь на разбор и
# на ответ): копируются только они — неперечисленный ключ контракта читается нулём (C1), а
# незнакомый ключ разбора не попадает в ответ, которого карточка не обещала (прецедент
# `SUMMARY_KEYS` узлов V46/V48…V54). Ключи `index_available`, `index_kind_records` и
# `index_child_records` сюда НЕ входят намеренно: их называет слой по факту чтения
# `configuration_objects`, а разбор описывает ими только свой вход.
SUMMARY_KEYS: Tuple[str, ...] = (
    "directory", "state_columns", "files_found", "files_read", "files_failed",
    "observations", "duplicate_names", "index_only", "file_only", "uuid_mismatch",
    "picture_pending", "module_pending", "picture_total", "picture_resolved",
    "unknown_properties",
) + COUNT_KEYS


def read_index_records(cur, configuration_id: int) -> Dict[str, Any]:
    """Записи индекса состава этой конфигурации из `configuration_objects` (Н6).

    Пустой ответ означает «индекс недоступен», а не «объектов нет»: при недоступном индексе
    сверка файла регистрации с перечнем и разрешение ссылки невыразимы, и вызывающий обязан
    назвать это состоянием загрузки, а не нулями (тот же контракт, что у слоёв V46/V48/V53).
    Записей своего вида здесь считается ровно столько, сколько их перечисляет индекс
    (`index_kind_records`/`index_child_records` ответа стадии): по замеру 1.2 это 2 + 2 у
    MinCfg и ноль у трёх других выгрузок, и расхождение обязано быть названо.
    """
    info: Dict[str, Any] = {"available": False, "row_count": 0, "kind_count": 0,
                            "child_count": 0, "reason": None}
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
            "перечнем и разрешение ссылки `Picture` невозможны"
        )
        return {"rows": [], **info}
    info.update({
        "available": True,
        "row_count": len(records),
        "kind_count": len(kind_index_rows(records)),
        "child_count": len(module_index_rows(records)),
    })
    return {"rows": records, **info}


def read_loaded_module_names(cur, configuration_uuid: str) -> Dict[str, Any]:
    """Имена модулей вида, для которых строки `bsl_modules` уже написал узел V47.

    Признак проверяется по живой БД (правило V43), а не повторным разбором
    `ConfigDumpInfo.xml`, и по ВИТРИНЕ текущего состояния, а не по таблице: строка прежней
    ревизии не должна читаться записанной. Имя собирается в той же форме, что у записи
    индекса состава (`Bot.<Имя>.Module`, замер 1.2), — иначе сравнение с ней никогда не
    совпадёт.

    Пустой перечень означает «строк V47 для этого вида нет», и разбор отличает его от
    «признак не проверялся» (шаг П3, наблюдение `module_load_not_checked`). Отказ запроса —
    НЕ пустой перечень: вызывающий обязан передать `None`, чтобы состояние осталось
    названным, а не было выдано за «строк нет».
    """
    info: Dict[str, Any] = {"available": False, "count": 0, "unnamed": 0, "reason": None}
    columns = ", ".join(MODULE_ROW_COLUMNS)
    try:
        cur.execute(
            f"SELECT {columns} FROM {BSL_MODULES_VIEW} "
            "WHERE configuration_uuid = %s::uuid AND object_type = %s",
            [str(configuration_uuid), BOTS_META_TYPE],
        )
    except Exception as exc:  # noqa: BLE001 — признак является границей, а не отказом слоя
        info["reason"] = f"чтение {BSL_MODULES_VIEW} не удалось: {exc}"
        return {"names": None, **info}
    names: List[str] = []
    for values in cur.fetchall():
        row = dict(zip(MODULE_ROW_COLUMNS, values))
        object_type = str(row.get("object_type") or "").strip()
        object_name = str(row.get("object_name") or "").strip()
        module_type = str(row.get("module_type") or "").strip()
        if not object_type or not object_name or not module_type:
            # Имя модуля не из чего собирать: строка есть, а сопоставить её с объектом вида
            # нельзя. Это называется числом, а не теряется в счётчике записанных.
            info["unnamed"] += 1
            continue
        names.append(f"{object_type}.{object_name}.{module_type}")
    info.update({"available": True, "count": len(names)})
    return {"names": names, **info}


def remove_bots(cur, configuration_uuid: str) -> Dict[str, int]:
    """Снять строки свойств ботов этой конфигурации (внутри транзакции).

    Очистка обязана быть явной: внешнего ключа и каскада в схеме нет осознанно (прецедент
    V20.1), иначе строки пережили бы снятие заголовка и стали бы сиротами, которые нельзя ни
    показать в карточке конфигурации, ни отличить от строк другой конфигурации. Этим же
    фильтром (`configuration_uuid`) держится снятие в `_remove_rows` узлов V32/V46 — иначе
    `force=True` оставил бы в базе прежний состав вида.

    Круг снятия — ОДНА таблица (`BOTS_REMOVE_ORDER`): таблиц детей у вида нет (замер 1.2),
    поэтому здесь нет и порядка «сначала дети» (мера M7 узлов V53/V54), и каскадных внешних
    ключей, которые снимали бы строки молча.

    Строки `bsl_modules` этим фильтром НЕ снимаются намеренно, и это названо, а не обойено
    (мера M5): их пишет узел V47, и снятие свойств вида не имеет права удалять содержимое
    чужого узла — иначе повтор стадии V55 уничтожил бы тексты модулей, а читатель
    `module_loaded` получил бы `FALSE` там, где узел V47 их только что записал.
    """
    removed: Dict[str, int] = {}
    for table in BOTS_TABLES:
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
            "иначе свойства ботов остались бы ни на что не указывающими, а внешний ключ в "
            "схеме не поставлен осознанно (узел V20.1)."
        )
    return card, None


def _stage_failure(reason: str, header: Optional[Dict] = None,
                   status: str = STATUS_ERROR,
                   extra: Optional[List[str]] = None) -> Dict[str, Any]:
    """Отказ стадии в форме закрытого контракта (C1, C3).

    Причина кладётся в ключ `error` замкнутого словаря `bots_defaults()`, а статус — в
    `status`: вызывающий отличает «стадия не выполнялась» от «слой отказал» (C2). Если
    заголовок к моменту отказа уже разрешён, он называется: по `configuration_id` карточка
    отличает «заголовка нет» от «заголовок есть, слой отказал по файлам». Подсказка о том,
    чем продолжить, кладётся и в отказ, и в успех: у стадии есть отдельный вход
    `load_bots_tool` (шаг П5), и вызывающий обязан знать это из ответа, а не из молчания
    (прецеденты V48…V54).
    """
    result = bots_defaults()
    result["status"] = status
    result["error"] = reason
    result["reason"] = reason
    if header:
        result["configuration_id"] = header.get("id")
        result["configuration_uuid"] = header.get("uuid")
        result["configuration_name"] = header.get("name")
    result["warnings"].append(BOTS_REPEAT_HINT)
    result["warnings"].append(f"Граница: {BOTS_CIRCLE_BOUNDARY}")
    for warning in extra or []:
        result["warnings"].append(warning)
    return result


def load_bots(source_path: str,
              configuration_uuid: Optional[str] = None,
              changed_at=None) -> Dict[str, Any]:
    """Загрузить свойства ботов конфигурации (узел V55, стадия S4j).

    Порядок: каталог → uuid из `Configuration.xml` (или сверка переданного) → проверка, что
    заголовок загружен → индекс состава из `configuration_objects` (сверка файлов с перечнем
    и разрешение ссылок, Н6) → перечень модулей из `v_current_bsl_modules` (признак V47,
    правило V43) → разбор каталога вида → **транзакция**: `DELETE` по uuid + вставка строк
    круга → отдельной транзакцией `ANALYZE` таблицы (мера V46).

    Отказ разбора любого файла круга останавливает стадию ДО записи: половина круга в базе
    читалась бы как полный состав вида (приём V12/V46). Отсутствие каталога вида — не отказ,
    а ответ о выгрузке: `files_found = 0` с наблюдением `directory_missing`, потому что у трёх
    из четырёх выгрузок ботов действительно нет (замер 1.1, Q9 вариант A).

    Недоступный индекс состава — отказ именно здесь, а не названное наблюдение (отличие от
    V48/V53/V54): состояния `pending` колонкам схемы не выразимы, его отклоняют CHECK'и
    `bots_picture_state_known` и `bots_module_state_known`, а половина круга с невыразимой
    второй половиной читалась бы полным составом. Причина называется с указанием того, чем
    продолжить.

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
                                  "child_count": 0, "reason": None, "rows": []}
    modules_info: Dict[str, Any] = {"available": False, "count": 0, "unnamed": 0,
                                    "reason": None, "names": None}
    try:
        with transaction() as cur:
            index_info = read_index_records(cur, int(header["id"]))
            modules_info = read_loaded_module_names(cur, configuration_uuid)
    except Exception as exc:  # noqa: BLE001 — индекс читается до записи, отказ называется им
        index_info["reason"] = f"чтение {OBJECTS_TABLE} не удалось: {exc}"
        modules_info["reason"] = f"чтение {BSL_MODULES_VIEW} не удалось: {exc}"

    if not index_info["available"]:
        # См. docstring: без строк индекса состояния ссылки и модуля называются `pending`,
        # которого нет в замкнутых словарях схемы, — записывать круг нечем.
        return _stage_failure(
            f"Индекс состава недоступен: {index_info['reason']}. Стадия S4j не выполнялась, "
            f"ни одной строки в {BOTS_TABLE} не записано, прежние строки этой конфигурации "
            "не сняты: без записей `configuration_objects` состояние ссылки `Picture` и "
            "состояние модуля выражаются только состоянием `pending`, которого нет в "
            "замкнутых словарях CHECK `bots_picture_state_known` и "
            "bots_module_state_known (шаг П3). Продолжить можно загрузкой каталога точкой "
            "входа load_1c_catalog_tool(source_path=…), которая заполняет индекс состава.",
            header=header,
        )

    collected = collect_bots(source_path, index_rows=index_info["rows"],
                             loaded_module_names=modules_info["names"])
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

    rows = collected.get("rows") or []
    pending_rows = [str(row.get("object_name")) for row in rows
                    if row.get("picture_state") == "pending"
                    or row.get("module_state") == "pending"]
    if pending_rows:
        # Defensive-проверка: индекс передан, а `pending` всё равно появился — значит
        # состояние выразить нечем, и CHECK отклонил бы запись на середине транзакции.
        # Отказ называется списком объектов, а не отдаётся на откуп планировщику БД.
        return _stage_failure(
            f"Круг не записан: у {len(pending_rows)} объект(ов) "
            f"({', '.join(pending_rows[:10])}) состояние ссылки или модуля осталось "
            f"`pending` при переданном индексе состава — запись в {BOTS_TABLE} отклоняется "
            "CHECK'ами схемы. Ни одной строки не записано, прежние строки этой конфигурации "
            "не сняты",
            header=header,
        )

    if not modules_info["available"]:
        warnings.append(
            f"Признак записанных модулей не проверялся: {modules_info['reason']}. Колонка "
            "`module_loaded` во всех строках будет `FALSE`, и это означает «не проверяли», а "
            "не «строк `bsl_modules` нет» (наблюдение `module_load_not_checked`)"
        )
    if modules_info["unnamed"]:
        warnings.append(
            f"Строк `bsl_modules` вида без имени объекта: {modules_info['unnamed']} — "
            "сопоставить их с объектом вида нельзя, в признак они не вошли"
        )

    removed: Dict[str, int] = {}
    written: Dict[str, int] = {}
    try:
        with transaction() as cur:
            removed = remove_bots(cur, configuration_uuid)
            for row in rows:
                # uuid заголовка знает вызывающий, а не XML объекта — тот же порядок, что у
                # писателей свойств V46 и модулей корня V44.
                row["configuration_uuid"] = configuration_uuid
            # Один момент на всю загрузку (M2): строки одного события не должны нести разные
            # метки, иначе их нельзя прочитать как один состав.
            stamp_revision_rows(rows, revision_no=FIRST_REVISION,
                                changed_by=CHANGED_BY_LOAD, changed_at=changed_at)
            written[BOTS_TABLE] = int(WRITER.insert_many(cur, rows))
    except Exception as exc:  # noqa: BLE001 — заголовок уже разрешён, отказ называется им
        return _stage_failure(f"Ошибка записи: {exc}", header=header)

    # ── статистика записанной таблицы (мера V46) ────────────────────────────────────────
    # Отдельная транзакция ПОСЛЕ фиксации записи: планировщик обязан увидеть строки, иначе
    # первый же читатель витрины `v_current_bots` платит минутами за счётчик (замер V46 на
    # BGU2: 8 мин 25 с против 7 мс после ANALYZE). Отказ статистики отказом загрузки не
    # является: строки зафиксированы, и состояние ответа от него не меняется.
    statistics_refreshed = 0
    try:
        with transaction() as cur:
            refresh_table_statistics(cur, BOTS_TABLES)
            statistics_refreshed = 1
    except Exception as exc:  # noqa: BLE001 — ответ описывает запись, а не статистику
        warnings.append(
            f"статистика таблицы {BOTS_TABLE} не обновлена: {exc}. Строки записаны, но "
            "читатель витрины текущего состояния получит план по пустой статистике: счётчики "
            "на большой выгрузке выполняются минутами вместо миллисекунд"
        )

    result = bots_defaults()
    result.update({
        "status": STATUS_OK,
        "success": True,
        "configuration_id": header["id"],
        "configuration_uuid": configuration_uuid,
        "configuration_name": header.get("name"),
        "rows_written": int(sum(written.values())),
        "bots_written": int(written.get(BOTS_TABLE, 0)),
        "removed_previous": int(sum(removed.values())),
        "removed_by_table": {table: int(removed.get(table, 0)) for table in BOTS_TABLES},
        "written_by_table": {table: int(written.get(table, 0)) for table in BOTS_TABLES},
        "index_available": bool(index_info["available"]),
        "index_kind_records": int(index_info["kind_count"]),
        "index_child_records": int(index_info["child_count"]),
        "statistics_refreshed": statistics_refreshed,
    })
    # Сводка состояний переносится теми же ключами, что её собрал разбор, и только
    # перечисленные (C1): неперечисленный ключ контракта остаётся нулём, а незнакомый ключ
    # разбора не попадает в ответ, которого карточка не обещала.
    for key in SUMMARY_KEYS:
        if key in collected:
            result[key] = collected[key]
    warnings.extend(collected.get("warnings") or [])

    if removed:
        warnings.append(
            "Прежние строки свойств ботов этой конфигурации сняты перед записью: "
            f"{sum(removed.values())}. Идемпотентность держится явным DELETE по "
            "configuration_uuid: внешнего ключа и каскада в схеме нет осознанно (прецедент "
            "V20.1); новая ревизия на повторную загрузку той же выгрузки не заводится — "
            "история состояний принадлежит узлу правки объекта, которого в схеме ещё нет "
            "(D8). Строки `bsl_modules` (тексты модулей, узел V47) не тронуты — мера M5"
        )
    if not collected.get("files_found"):
        warnings.append(
            f"Каталог {BOTS_DIR}/ круга не дал ни одного файла регистрации: у трёх из "
            "четырёх выгрузок корпуса вида нет вовсе (замер 1.1), и отсутствие каталога "
            "названо наблюдением `directory_missing`, а не нулём строк (Q9, вариант A)"
        )
    if rows and modules_info["available"] and not modules_info["count"]:
        # Предупреждение говорит о записанных строках: при пустом круге строк нет, и фраза
        # «во всех строках FALSE» описывала бы то, чего в базе не появилось. Пустой круг уже
        # назван предыдущим предупреждением и наблюдением `directory_missing`.
        warnings.append(
            "Строк `bsl_modules` вида в витрине текущего состояния нет: признак "
            "`module_loaded` во всех строках `FALSE` означает «тексты модулей ещё не "
            "записаны узлом V47», а не «модулей нет» (файлы при этом могут быть и названы "
            "дескрипторами — Q4, вариант A)"
        )
    warnings.append(BOTS_REPEAT_HINT)
    warnings.append(f"Граница: {BOTS_CIRCLE_BOUNDARY}")
    result["warnings"] = warnings
    return result






