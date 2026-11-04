#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Загрузчик свойств функциональных опций (узел V56, шаг П5, 04.11.2026).

Стадия S4k конвейера первого слоя: файлы вида `FunctionalOptions` (позиция 2.11 нормативного
списка плана `docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PLAN.md`) в две таблицы —
`functional_options` (строка опции) и `functional_option_content` (строки её применения).
Норматив — тот же план (решения Q1–Q4, Q7, Q9); разбор файлов вида — отдельный модуль
`src/configuration_functional_options.py` (шаг П3), писатели строк — реестр
`CONFIGURATION_OBJECT_WRITERS` (шаг П4), контракт стадии и форматёр ответа —
`src/configuration_load_contract.py` (этот же шаг П5).

Почему стадия отдельная, а не одиннадцатый вид S4 (прецеденты Q5 узлов V48–V55): правило C3
требует своего ключа ответа `functional_options`; порядок `STAGES` повторяет порядок
нормативного списка (2.11 идёт сразу за 2.10), поэтому S4k стоит между S4j и S4b. Круг
стадии (`FUNCTIONAL_OPTIONS_TABLES`) отделён от круга версионности этим же шагом: таблица вида
зарегистрирована в `CONFIGURATION_VERSIONED_TABLES` (шаги П1/П4), и без
`FOREIGN_STAGE_TABLES` стадия S4 молча снимала бы и анализировала 765 строк чужого вида
(замер 1.1 плана).

Групп запроса (`kinds`) у вида нет — в отличие от V46, V49, V51 — и это решение, а не
упущение (Q4 раздела 6 плана, вариант A): строка применения существует только через id строки
опции (Q1, вариант A), поэтому состояния «записать опции без применения» в модели нет;
отдельный вход дозагружает весь круг сразу (порога цены замер 1.4 не дал — 2 467 629 байта
файлов регистрации на весь круг, прочего содержимого 0 байт).

Круг задают каталог `FunctionalOptions/` (плоский: подкаталогов, форм, макетов, команд и
модулей у вида нет — замер 1.1/1.2) и записи индекса состава того же вида
(`FunctionalOption.<Имя>`); расхождение двух источников называется `index_only` / `file_only`
/ `uuid_mismatch` — четыре замеренные выгрузки дают нули, и нули обязаны быть названы.
Третья нога круга — перечень заголовка `configurations.functional_options` — стадией НЕ
пишется (его заполняет S2), но называется ответом и сверяется числом записей индекса.

Адрес `Location` и цели перечня `<Content>` разрешаются по СТРОКАМ ИНДЕКСА состава своей
конфигурации (правило V43 — повторный разбор `ConfigDumpInfo.xml` вторым источником не
становится): псевдозаписи колонок (`.Resource.`, `.Attribute.`) индекс держит, поэтому
разрешение точное (замеры 2.1, 2.2: 765/765 и 10 063/10 063 `exact`). Внешних ключей на цели
нет осознанно (Q3): слои констант, регистров и справочников (группа A модели V38) этой
позицией не загружаются, поэтому цель называется состоянием, а не фактом существования.

Строка применения ссылается на ЧИСЛОВОЙ id ревизии строки опции (Q2, вариант A): своей цепи
ревизий у неё нет, поэтому опции вставляются `insert_ids()` (по одной строке, `RETURNING id`),
а полученный id подставляется в строки применения; ключом подстановки служит индексное имя
`FunctionalOption.<Имя>`, которое и несёт строка применения (прецедент `attribute_full_name`
узла V50, `role_name` узла V49). `functional_option_content` ревизией не штампуется
(исключение `CONFIGURATION_UNVERSIONED_TABLES`), строка опции — штампуется.


Снятие круга начинается с `functional_option_content`: её FK
`functional_option_content_functional_option_id_fkey` объявлен с `ON DELETE CASCADE` (П1), и
каскад снял бы применение молча, без точного счётчика (M7). Идемпотентность держится явным
`DELETE` по `configuration_uuid` (внешнего ключа на `configurations` в схеме нет осознанно —
V20.1), а не новой ревизией. Ключ цепочки строки опции — (`configuration_uuid`,
`object_name`, `revision_no`): 135 uuid вида стоят одновременно в BGU2 и BP3, 143 имени
встречаются в двух и более выгрузках (замер 1.3), и без границы конфигурации в ключе две
выгрузки слились бы в одну строку.

Круг пишется одной транзакцией, отказ разбора любого файла круга останавливает стадию ДО
записи (приём V12/V46/V48/V49/V50). После фиксации пересобирается статистика двух таблиц
(мера V46); отказ статистики отказом загрузки не является. Индекс состава НЕ является
обязательным входом стадии (в отличие от V55, где состояние `pending` отклоняют CHECK'и
схемы): недоступный индекс называется предупреждением, а адреса и цели остаются `unresolved` —
«цели нет в перечне» и «перечень не загружен» разные ответы (правило C2, Q3).

Прогон шага: `python _v56_p5_stage_probe.py MinCfg KomMag`, затем отдельно BGU2 и BP3
(прогоны, меняющие общее состояние БД, не параллелят).
"""
from typing import Any, Dict, List, Optional, Tuple

from configuration_functional_options import (
    OPTION_LINK_KEY,
    collect_functional_options,
    index_object_name,
    kind_index_rows,
)
from configuration_load_contract import (
    FUNCTIONAL_OPTION_CONTENT_TABLE,
    FUNCTIONAL_OPTIONS_CIRCLE_DISCREPANCIES,
    FUNCTIONAL_OPTIONS_OBSERVATION_KINDS,
    FUNCTIONAL_OPTIONS_REPEAT_HINT,
    FUNCTIONAL_OPTIONS_REMOVE_ORDER,
    FUNCTIONAL_OPTIONS_SUMMARY_KEYS,
    FUNCTIONAL_OPTIONS_TABLE,
    FUNCTIONAL_OPTIONS_TABLES,
    STATUS_ERROR,
    STATUS_OK,
    functional_options_defaults,
)
from configuration_object_properties_loader import refresh_table_statistics
from configuration_root_module_loader import configuration_uuid_from_layout
from current_revision import CHANGED_BY_LOAD, FIRST_REVISION, stamp_revision_rows
from external_db import transaction
from external_table_writer import CONFIGURATION_OBJECT_WRITERS

OBJECTS_TABLE = "configuration_objects"
OPTION_TABLE = FUNCTIONAL_OPTIONS_TABLE
CONTENT_TABLE = FUNCTIONAL_OPTION_CONTENT_TABLE

# Писатели двух таблиц берутся общим реестром, а не импортом классов (правило п.6 слоя):
# ошибка выбора превращается в запись не в ту таблицу, а реестр уже знает, какая таблица
# версионируется своей цепочкой, а какая — нет (`CONFIGURATION_UNVERSIONED_TABLES`).
FO_WRITERS = {table: CONFIGURATION_OBJECT_WRITERS[table]
              for table in FUNCTIONAL_OPTIONS_TABLES}

# Порядок снятия круга — не порядок `FUNCTIONAL_OPTIONS_TABLES`:
# `functional_option_content.functional_option_id` ссылается на строку опции с
# `ON DELETE CASCADE`, и каскад снял бы применение молча, без точного счётчика. Явный
# `DELETE` первым держит честное число снятых строк (M7) и не зависит от того, поставлен ли
# каскад в данной базе (миграция V56 могла не применяться). Тот же приём, что `REMOVE_ORDER`
# узлов V49, V50, V52, V54.
REMOVE_ORDER: Tuple[str, ...] = FUNCTIONAL_OPTIONS_REMOVE_ORDER

# Колонки индекса состава, которые нужны разбору вида: `name`/`object_name` — ключ сверки
# (`FunctionalOption.<Имя>`), `uuid` — цель ссылочного адреса и сверка uuid файла с записью
# перечня, `child_type` — различение записей одного имени, `depth`/`parent_name` — состояние
# «запись индекса имеет глубину» (иерархии раскладки у вида нет, замер 1.1). Фильтра по типу
# вида здесь нет намеренно: адрес `Location` и цели перечня ведут на объекты ДРУГИХ видов,
# включая псевдозаписи колонок (замеры 2.1, 2.2), а свой круг вида отбирает сам разбор
# (`kind_index_rows`). Тот же приём, что `read_index_records` узлов V46, V48, V49, V50.
INDEX_ROW_COLUMNS: Tuple[str, ...] = (
    "name", "object_id", "object_type", "object_name", "child_type", "parent_name", "depth",
    "uuid",
)

# Ключи сводки разбора, совпадающие с ключами контракта по имени (один словарь на разбор и на
# ответ): копируются только они — неперечисленный ключ контракта читается нулём (C1), а
# незнакомый ключ разбора не попадает в ответ, которого карточка не обещала (прецедент
# `SUMMARY_KEYS` узлов V46/V48/V49/V50). Ключей `rows` и `targets` здесь нет: строки записи
# идут в писатели, а не в ответ стадии (765 + 10 063 строк на корпус — замер 1.4); `success`
# разбора — внутренний признак круга, стадия отвечает своими `success` и `status`.
SUMMARY_KEYS: Tuple[str, ...] = FUNCTIONAL_OPTIONS_SUMMARY_KEYS


def read_index_records(cur, configuration_id: int) -> Dict[str, Any]:
    """Прочитать строки индекса состава этой конфигурации (тот же источник, что V46…V55).

    Источником служит таблица `configuration_objects`, а не повторный разбор
    `ConfigDumpInfo.xml`: правило V43 (вторым источником индекс состава не становится), и
    только строки БД содержат псевдозаписи колонок (`.Resource.`, `.Attribute.`), которыми
    разрешается адрес `Location` (замер 2.1).

    Отсутствие строк — НЕ отказ стадии: возвращается `available = False` с причиной, а стадия
    называет это предупреждением. При недоступном индексе сверка файлов с перечнем невозможна,
    а адреса и цели остаются `unresolved` — «цели нет в перечне» и «перечень не загружен»
    являются разными ответами (правило C2, Q3). Отличие от V55 названо слоем: там состояние
    `pending` отклоняют CHECK'и `bots_picture_state_known`/`bots_module_state_known`, поэтому
    индекс был обязателен отказом стадии.
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
            "разрешение адреса `Location` и целей применения невозможны"
        )
        return {"rows": [], **info}
    info.update({
        "available": True,
        "row_count": len(records),
        "kind_count": len(kind_index_rows(records)),
    })
    return {"rows": records, **info}


def remove_functional_options(cur, configuration_uuid: str,
                              tables: Tuple[str, ...] = REMOVE_ORDER) -> Dict[str, int]:
    """Снять строки функциональных опций этой конфигурации (внутри текущей транзакции).

    Очистка обязана быть явной: внешнего ключа на `configurations` и каскада по нему в схеме
    нет осознанно (прецеденты V20.1, V44, V46, V48, V49, V50), иначе строки пережили бы
    снятие заголовка и стали бы сиротами, которые нельзя ни показать в карточке конфигурации,
    ни отличить от строк другой конфигурации. Этим же фильтром (`configuration_uuid`) держится
    снятие в `_remove_rows` конвейера — иначе `force=True` оставил бы в базе прежний состав
    вида (для BP3 это 539 строк опций и 6 789 строк применения — замеры 1.1, 2.2).

    Порядок задаёт `REMOVE_ORDER`, а не `FUNCTIONAL_OPTIONS_TABLES`: применение снимается ДО
    опций, потому что его собственный FK
    `functional_option_content_functional_option_id_fkey` объявлен с `ON DELETE CASCADE` —
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
    заголовка нельзя ни показать в карточке конфигурации, ни снять вместе с ней (внешний ключ
    в схеме не поставлен осознанно — V20.1). Ленивый импорт — тот же обход цикла, что у слоёв
    V44/V46/V48/V49/V50.
    """
    from configuration_loader import find_configuration  # ленивый импорт — круг узла V44

    card = find_configuration(configuration_uuid)
    if isinstance(card, dict) and card.get("error"):
        return None, f"Ошибка запроса: {card['error']}"
    if not card:
        return None, (
            f"Строка заголовка конфигурации с uuid {configuration_uuid} в базе не найдена. "
            "Сначала загрузите каталог точкой входа load_1c_catalog_tool(source_path=…): "
            "иначе свойства функциональных опций остались бы ни на что не указывающими, а "
            "внешний ключ в схеме не поставлен осознанно (узел V20.1)."
        )
    return card, None


def _stage_failure(reason: str, header: Optional[Dict] = None,
                   extra: Optional[List[str]] = None) -> Dict[str, Any]:
    """Отказ стадии по закрытому контракту (C1): нули по всем ключам, причина — текстом.

    Статус — в `status`: вызывающий отличает «стадия не выполнялась» от «слой отказал» (C2).
    Если заголовок к моменту отказа уже разрешён, он называется: по `configuration_id`
    карточка отличает «заголовка нет» от «заголовок есть, слой отказал по файлам».
    Подсказка о том, чем продолжить, кладётся и в отказ, и в успех: у стадии есть отдельный
    вход `load_functional_options_tool` (шаг П5), и вызывающий обязан знать это из ответа, а
    не из молчания.
    """
    result = functional_options_defaults()
    result["status"] = STATUS_ERROR
    result["error"] = reason
    result["reason"] = reason
    if header:
        result["configuration_id"] = header.get("id")
        result["configuration_uuid"] = header.get("uuid")
        result["configuration_name"] = header.get("name")
    result["warnings"].append(FUNCTIONAL_OPTIONS_REPEAT_HINT)
    for warning in extra or []:
        result["warnings"].append(warning)
    return result


def observation_counts(observations: List[Any]) -> Dict[str, int]:
    """Счётчик наблюдений круга по роду (`counts_by_observation` контракта).

    Пары `[род, подробности]` даёт разбор (`iter_registration_files`): без счётчика
    «каталога вида нет» и «в каталоге файл не-XML» различались бы только перечнем, а карточка
    обязана называть и число по каждому роду (C1). Словарь родов замкнут
    (`OBSERVATION_KINDS`), и пустой ответ означает «наблюдений нет» — это состояние, а не
    пропуск блока (прецедент `observation_counts` узлов V53, V54).
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
    полнота держится отдельным числом, а не длиной примеров — приём V48. Нули являются
    ответом: четыре замеренные выгрузки дают ноль по всем трём состояниям (замер 1.1), и
    молчать об этом значило бы не отличать «расхождений нет» от «сверку не делали». Словарь
    состояний берётся замкнутой константой разбора, а не списком имён здесь: второе
    перечисление состояний в проекте разъезжается с первым.
    """
    listed = dict(zip(FUNCTIONAL_OPTIONS_CIRCLE_DISCREPANCIES,
                      (index_only, file_only, uuid_mismatch)))
    return {state: len(listed.get(state) or [])
            for state in FUNCTIONAL_OPTIONS_CIRCLE_DISCREPANCIES}


def load_functional_options(source_path: str,
                            configuration_uuid: Optional[str] = None,
                            changed_at=None) -> Dict[str, Any]:
    """Загрузить свойства функциональных опций конфигурации (узел V56, стадия S4k).

    Порядок: каталог → uuid из `Configuration.xml` (или сверка переданного) → проверка, что
    заголовок загружен → индекс состава из `configuration_objects` (сверка файлов с перечнем и
    разрешение адреса `Location` и целей применения, Н6) → разбор каталога вида →
    **одна транзакция**: `DELETE` по uuid + вставки двух таблиц → отдельной транзакцией
    `ANALYZE` (мера V46).

    Групп `kinds` у стадии нет (Q4 раздела 6 плана, вариант A): строка применения существует
    только через id строки опции (Q1, вариант A), поэтому частичная запись круга описывала бы
    состав, которого в выгрузке нет.

    Отказ разбора любого файла круга останавливает стадию ДО записи: половина круга читалась
    бы как полный состав вида (приём V12/V46/V48/V49/V50/V53/V54). Отсутствие каталога
    `FunctionalOptions/` — не отказ, а ответ о выгрузке: `files_found = 0` с наблюдением
    `directory_missing` (Q9): у KomMag позиции вида нет ни файлами, ни строками индекса
    (замер 1.1), и именно так она и отвечает.

    `changed_at` передаёт конвейер: строки одной загрузки обязаны нести одну метку (M2), а не
    время своей транзакции. Пустое значение — своя метка вызова (одиночный прогон слоя).
    Строки применения метку не несут: колонок ревизии у таблицы нет
    (`CONFIGURATION_UNVERSIONED_TABLES`), их текущность читается связкой по
    `functional_option_id` (Q2, вариант A).

    Порядок записи держится иерархией данных, а не удобством: сначала строки опций
    (`insert_ids`, `RETURNING id`), затем строки применения, ссылающиеся на id этих ревизий.
    Всё это одной транзакцией: отказ на середине оставил бы в базе опции без применения, то
    есть состав, которого в выгрузке нет (замеры 1.1, 2.2: 765 опций и 10 063 цели на корпус,
    до 438 целей в одном файле — потеря половины перечня была бы незаметна в ответе).
    """
    uuid_info = configuration_uuid_from_layout(source_path)
    if "uuid" not in uuid_info:
        return _stage_failure(uuid_info.get("error")
                             or f"Каталог выгрузки не читается: {source_path}")
    layout_uuid = str(uuid_info["uuid"])
    if configuration_uuid and str(configuration_uuid).strip().lower() != layout_uuid.lower():
        # Два источника одного факта указали на разные конфигурации: молча выбрать один —
        # значит записать свойства чужой конфигурации (тот же отказ, что у слоёв
        # V44/V46/V48/V49/V50). Для вида это особенно дорого: 143 имени опций встречаются в
        # двух и более выгрузках (замер 1.3), и молчаливый выбор записал бы чужой состав.
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

    collected = collect_functional_options(source_path, index_rows=index_info["rows"])
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
    # свойств V46, модулей корня V44, параметров сеанса V48, ролей V49 и реквизитов V50.
    option_rows = [dict(row, configuration_uuid=configuration_uuid)
                   for row in (collected.get("rows") or [])]
    target_rows = [dict(row, configuration_uuid=configuration_uuid)
                   for row in (collected.get("targets") or [])]

    # Полнота связывания проверяется ДО транзакции: строка применения обязана ссылаться на
    # строку опции этого же круга (Q1, вариант A), и молча отбросить её значило бы назвать
    # неполный круг полным. Ключом служит индексное имя `FunctionalOption.<Имя>` — именно в
    # этой форме связь несёт строка применения (`OPTION_LINK_KEY`; прецедент
    # `attribute_full_name` узла V50, `role_name` узла V49).
    link_keys = [index_object_name(str(row.get("object_name") or ""))
                 for row in option_rows]
    known = set(link_keys)
    if len(known) != len(link_keys):
        duplicated = sorted({key for key in link_keys if link_keys.count(key) > 1})
        return _stage_failure(
            f"Круг не записан: разбор дал {len(link_keys)} строк опций с "
            f"повторяющимися именами ({', '.join(duplicated[:5])}) — строки применения "
            "нельзя связать однозначно (замер 1.3 даёт уникальность имён внутри выгрузки), "
            "ни одна строка круга не записана",
            header=header,
        )
    unbound = sorted({str(row.get(OPTION_LINK_KEY)) for row in target_rows
                      if row.get(OPTION_LINK_KEY) not in known})
    if unbound:
        return _stage_failure(
            f"Круг не записан: {len(unbound)} строка(ов) применения остались без строки "
            f"опции ({', '.join(unbound[:5])}) — это внутреннее противоречие разбора, "
            "а не состояние выгрузки; ни одна строка круга не записана",
            header=header,
        )

    # Один штамп времени на всё событие загрузки (M2): версионируемая таблица одной загрузки
    # не должна нести две метки. Строки применения метку не получают — колонок ревизии у них
    # нет (исключение `CONFIGURATION_UNVERSIONED_TABLES`).
    moment = stamp_revision_rows(option_rows, revision_no=FIRST_REVISION,
                                 changed_by=CHANGED_BY_LOAD, changed_at=changed_at)

    removed: Dict[str, int] = {}
    written: Dict[str, int] = {table: 0 for table in FUNCTIONAL_OPTIONS_TABLES}
    try:
        with transaction() as cur:
            removed = remove_functional_options(cur, configuration_uuid)
            # Опции — по одной строке с RETURNING id: строка применения ссылается на
            # ЧИСЛОВОЙ id этой ревизии (Q2, вариант A), а `insert_many` id не возвращает.
            # Порядок `insert_ids` совпадает с порядком `option_rows` — связь держится им, а
            # не угадыванием (224 строки на BGU2 — замер 1.1; цена поштучной вставки
            # измерена слоем V49/V50 и приемлема). Прецедент — `insert_ids` слоёв V49, V50.
            option_ids = FO_WRITERS[OPTION_TABLE].insert_ids(cur, option_rows)
            if len(option_ids) != len(option_rows):
                raise RuntimeError(
                    f"писатель вернул {len(option_ids)} id для {len(option_rows)} "
                    f"строк таблицы {OPTION_TABLE} — связать применение нечем"
                )
            written[OPTION_TABLE] = len(option_ids)
            ids_by_key = dict(zip(link_keys, option_ids))
            for row in target_rows:
                row["functional_option_id"] = ids_by_key[str(row.get(OPTION_LINK_KEY))]
            written[CONTENT_TABLE] = FO_WRITERS[CONTENT_TABLE].insert_many(cur, target_rows)
    except Exception as exc:  # noqa: BLE001 — заголовок уже разрешён, отказ называется им
        return _stage_failure(
            f"Ошибка записи: {exc}. Транзакция отменена целиком: в базе остались прежние "
            f"строки круга (снятые этим вызовом — {sum(removed.values())}), новых нет",
            header=header,
        )

    # ── статистика записанных таблиц (мера V46) ─────────────────────────────────────────
    # Отдельная транзакция ПОСЛЕ фиксации записи: планировщик обязан увидеть строки, иначе
    # первый же читатель витрин текущего состояния платит минутами за счётчик (замер V46 на
    # BGU2: 8 мин 25 с против 7 мс после ANALYZE; витрины `v_current_functional_options` и
    # `v_current_functional_option_content` считаются связкой по той же цепи ревизий). Отказ
    # статистики отказом загрузки не является: строки зафиксированы, и состояние ответа от него
    # не меняется.
    statistics_refreshed = 0
    try:
        with transaction() as cur:
            refresh_table_statistics(cur, FUNCTIONAL_OPTIONS_TABLES)
            statistics_refreshed = len(FUNCTIONAL_OPTIONS_TABLES)
    except Exception as exc:  # noqa: BLE001 — ответ описывает запись, а не статистику
        warnings.append(
            f"статистика таблиц {', '.join(FUNCTIONAL_OPTIONS_TABLES)} не обновлена: {exc}. "
            "Строки записаны, но читатель витрин текущего состояния получит план по пустой "
            "статистике: счётчики на большой выгрузке выполняются минутами вместо "
            "миллисекунд"
        )

    result = functional_options_defaults()
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
        "options_written": int(written[OPTION_TABLE]),
        "targets_written": int(written[CONTENT_TABLE]),
        "removed_previous": int(sum(removed.values())),
        "removed_by_table": removed,
        "written_by_table": written,
        "statistics_refreshed": statistics_refreshed,
    })
    # Наблюдения и расхождения ног считает стадия, а не разбор: разбор описывает свой вход
    # (офлайн, без живой БД), а ответ стадии обязан описывать содержимое базы и полный круг
    # сравнения с индексом состава (приём `observation_counts`/`circle_discrepancy_counts`
    # узлов V53, V54; словари замкнуты контрактом, поэтому пустой словарь здесь — состояние
    # «наблюдений нет», а не пропуск блока, C1).
    result["counts_by_observation"] = observation_counts(collected.get("observations"))
    result["counts_by_circle_discrepancy"] = circle_discrepancy_counts(
        result["index_only"], result["file_only"], result["uuid_mismatch"])

    # Подсказка о том, чем продолжить, кладётся и в успех, и в отказ: у стадии есть
    # отдельный вход `load_functional_options_tool` (шаг П5), и вызывающий обязан знать это
    # из ответа, а не из молчания (прецедент REPEAT_HINT узлов V49…V55).
    warnings.append(FUNCTIONAL_OPTIONS_REPEAT_HINT)
    if not index_info["available"] and index_info.get("reason"):
        warnings.append(
            f"Индекс состава: {index_info['reason']} — состояния `index_only` и `file_only` "
            "при этом невыразимы, а адрес `Location` и цели применения остаются "
            "неразрешёнными записями (Q3): «объекта нет в перечне» от «перечень этой "
            "конфигурации не загружен» не отличить. Отличие от узлов V48…V54 названо слоем: "
            "состояний `pending` в схеме вида нет, поэтому недоступный индекс является "
            "предупреждением, а не отказом стадии"
        )
    for observation, detail in (collected.get("observations") or []):
        if observation == "directory_missing":
            warnings.append(
                f"Каталог {collected.get('directory')}/ в выгрузке отсутствует — "
                "функциональных опций у этой конфигурации нет, и нули таблиц являются ответом "
                "о выгрузке, а не отказом стадии (замер 1.1 даёт KomMag именно в таком виде; "
                "Q9, вариант A)"
            )
        elif observation == "index_not_provided":
            warnings.append(
                "Индекс состава не передан разбору — разрешение адреса `Location` и целей "
                f"применения не выполнялось ({detail}): все цели остались состоянием "
                "`unresolved`, и это НЕ ответ «цели нет в конфигурации» (правило C2)"
            )
    if index_info["available"] and int(result["index_kind_records"]) != int(
            result.get("files_found") or 0):
        warnings.append(
            f"Записей `FunctionalOption.<Имя>` в индексе состава "
            f"{result['index_kind_records']}, файлов регистрации "
            f"{result.get('files_found')} — круги различаются (замер 1.1 даёт равенство на "
            "трёх выгрузках, где вид есть, поэтому расхождение требует объяснения этим "
            "прогоном; расхождения перечислены ключами `index_only` / `file_only`)"
        )
    if int(result.get("targets_written") or 0) != int(result.get("targets_total") or 0):
        warnings.append(
            f"Разбор дал {result.get('targets_total')} строк применения, записано "
            f"{result.get('targets_written')} — часть строк в {CONTENT_TABLE} не попала; "
            "связь со строкой опции держится id ревизии (Q2), и молчать об этом нельзя"
        )
    if any(removed.values()):
        warnings.append(
            "Прежние строки свойств функциональных опций этой конфигурации сняты перед "
            f"записью: {', '.join(f'{table}={count}' for table, count in removed.items())}. "
            "Идемпотентность держится явным DELETE по configuration_uuid: внешнего ключа и "
            "каскада по конфигурации в схеме нет осознанно (прецедент V20.1); новая ревизия "
            "на повторную загрузку той же выгрузки не заводится — история состояний "
            "принадлежит узлу правки объекта, которого в схеме ещё нет"
        )
    if option_rows:
        warnings.append(
            f"Момент загрузки строк опций — {moment}: той же меткой помечены строки "
            "заголовка и других стадий этого события (M2); строки применения метку не несут "
            "(своей цепи ревизий у них нет, Q2 вариант A)"
        )
    else:
        warnings.append(
            "Строк опций этим вызовом не записано: каталог вида пуст или отсутствует "
            f"(файлов {result.get('files_found')}), поэтому и общего момента загрузки вида у "
            "этого события нет — нули таблиц являются ответом о выгрузке (Q9)"
        )
    result["warnings"] = warnings
    return result
