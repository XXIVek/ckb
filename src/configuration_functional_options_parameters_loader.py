#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Загрузчик свойств параметров функциональных опций (узел V57, шаг П5, 04.11.2026).

Стадия S4l конвейера первого слоя: файлы вида `FunctionalOptionsParameters` (позиция 2.12
нормативного списка плана `docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PARAMETERS_PLAN.md`) в две
таблицы — `functional_option_parameters` (строка параметра) и
`functional_option_parameter_targets` (строки её применения `<Use>`). Норматив — тот же план
(решения Q1–Q3, Q5, Q7, Q9); разбор файлов вида — отдельный модуль
`src/configuration_functional_options_parameters.py` (шаг П3), писатели строк — реестр
`CONFIGURATION_OBJECT_WRITERS` (шаг П4), контракт стадии и форматёр ответа —
`src/configuration_load_contract.py` (этот же шаг П5).

Почему стадия отдельная, а не двенадцатый вид S4 и не расширение S4k (прецеденты Q5 узлов
V48–V56): правило C3 требует своего ключа ответа `functional_options_parameters`, а разбивать
чужой ключ `functional_options` значило бы переименовывать контракт V56; порядок `STAGES`
повторяет порядок нормативного списка (2.12 идёт сразу за 2.11), поэтому S4l стоит между S4k
и S4b. Круг стадии (`FUNCTIONAL_OPTION_PARAMETERS_TABLES`) отделён от круга версионности шагом
П4: таблица вида зарегистрирована в `CONFIGURATION_VERSIONED_TABLES`, и без
`FOREIGN_STAGE_TABLES` стадия S4 молча снимала бы и анализировала 14 строк вида и 34 строки
его применения (замеры 1.1, 2.1 плана).

Групп запроса (`kinds`) у вида нет — в отличие от V46, V49, V51 — и это решение, а не
упущение (Q5 раздела 6 плана, вариант A): строка применения существует только через id строки
параметра (Q1, вариант A), поэтому состояния «записать параметры без применения» в модели нет;
отдельный вход дозагружает весь круг сразу (порога цены замер 1.4 не дал — весь круг четырёх
выгрузок это 14 файлов регистрации и 0 байт прочего содержимого).

Круг задают каталог `FunctionalOptionsParameters/` (плоский: подкаталогов, форм, макетов,
команд, модулей и каталогов содержимого у вида нет — замеры 1.1/1.2) и записи индекса состава
ТОГО ЖЕ вида (`FunctionalOptionsParameter.<Имя>`); расхождение двух источников называется
`index_only` / `file_only` / `uuid_mismatch` — четыре замеренные выгрузки дают нули, и нули
обязаны быть названы. Третья нога круга — перечень заголовка
`configurations.functional_options_parameters` — стадией НЕ пишется (его заполняет S2), но
называется ответом и сверяется числом записей индекса. Отличие от V56 названо слоем: рядом
стоит вид `FunctionalOption` (2.11), имя которого начинается с той же строки, поэтому отбор
идёт точным `object_type`, а не началом имени (раздел 1.2 плана).

Цели перечня `<Use>` разрешаются по СТРОКАМ ИНДЕКСА состава своей конфигурации (правило V43 —
повторный разбор `ConfigDumpInfo.xml` вторым источником не становится): цели ведут на объекты
ДРУГИХ видов (`InformationRegister.….Dimension.…`, `Catalog.…`), поэтому поиск идёт по всем
строкам индекса, а не по строкам своего вида (замер 2.1: 34/34 `exact`). Ссылки `Location` у
вида нет (замер 2 плана), поэтому раздела разрешения адреса носителя у стадии нет — в отличие
от V56. Внешних ключей на цели нет осознанно (Q3): слои регистров сведений, справочников и
прочих видов (группы A–H модели V38) этой позицией не загружаются, поэтому цель называется
состоянием, а не фактом существования.

Строка применения ссылается на ЧИСЛОВОЙ id ревизии строки параметра (Q2, вариант A): своей
цепи ревизий у неё нет, поэтому параметры вставляются `insert_ids()` (по одной строке,
`RETURNING id`), а полученный id подставляется в строки применения; ключом подстановки служит
индексное имя `FunctionalOptionsParameter.<Имя>`, которое и несёт колонка `parameter_full_name`
(прецедент `option_full_name` узла V56, `attribute_full_name` V50, `role_name` V49).
`functional_option_parameter_targets` ревизией не штампуется (исключение
`CONFIGURATION_UNVERSIONED_TABLES`), строка параметра — штампуется.

Снятие круга начинается с `functional_option_parameter_targets`: её FK
`functional_option_parameter_targets_parameter_fkey` объявлен с `ON DELETE CASCADE` (П1), и
каскад снял бы применение молча, без точного счётчика (M7). Идемпотентность держится явным
`DELETE` по `configuration_uuid` (внешнего ключа на `configurations` в схеме нет осознанно —
V20.1), а не новой ревизией. Ключ цепочки строки параметра — (`configuration_uuid`,
`object_name`, `revision_no`): имена вида встречаются в двух и более выгрузках (замер 1.3 для
соседнего вида даёт 143 повтора), и без границы конфигурации в ключе две выгрузки слились бы в
одну строку.

Круг пишется одной транзакцией, отказ разбора любого файла круга или нарушение инвариантов
пары «строка вида ↔ строки применения» останавливают стадию ДО записи (приём
V12/V46/V48/V49/V50; инварианты — собственная проверка разбора П3, `check_row`). После
фиксации пересобирается статистика двух таблиц (мера V46); отказ статистики отказом загрузки
не является. Индекс состава НЕ является обязательным входом стадии (в отличие от V55, где
состояние `pending` отклоняют CHECK'и схемы): недоступный индекс называется предупреждением, а
цели остаются `unresolved` — «цели нет в перечне» и «перечень не загружен» разные ответы
(правило C2, Q3).

Прогон шага: `python _v57_p5_stage_probe.py`, затем загрузка четырёх выгрузок отдельным
входом `load_functional_options_parameters_tool` (прогоны, меняющие общее состояние БД, не
паралелят).
"""
from typing import Any, Dict, List, Optional, Tuple

from configuration_functional_options_parameters import (
    PARAMETER_LINK_KEY,
    collect_functional_options_parameters,
    index_object_name,
    kind_index_rows,
)
from configuration_load_contract import (
    FUNCTIONAL_OPTION_PARAMETERS_TABLE,
    FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE,
    FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER,
    FUNCTIONAL_OPTION_PARAMETERS_TABLES,
    FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_DISCREPANCIES,
    FUNCTIONAL_OPTIONS_PARAMETERS_REPEAT_HINT,
    FUNCTIONAL_OPTIONS_PARAMETERS_SUMMARY_KEYS,
    STATUS_ERROR,
    STATUS_OK,
    functional_options_parameters_defaults,
)
from configuration_object_properties_loader import refresh_table_statistics
from configuration_root_module_loader import configuration_uuid_from_layout
from current_revision import CHANGED_BY_LOAD, FIRST_REVISION, stamp_revision_rows
from external_db import transaction
from external_table_writer import CONFIGURATION_OBJECT_WRITERS

OBJECTS_TABLE = "configuration_objects"
PARAMETER_TABLE = FUNCTIONAL_OPTION_PARAMETERS_TABLE
TARGETS_TABLE = FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE

# Писатели двух таблиц берутся общим реестром, а не импортом классов (правило п.6 слоя):
# ошибка выбора превращается в запись не в ту таблицу, а реестр уже знает, какая таблица
# версионируется своей цепочкой, а какая — нет (`CONFIGURATION_UNVERSIONED_TABLES`).
FOP_WRITERS = {table: CONFIGURATION_OBJECT_WRITERS[table]
               for table in FUNCTIONAL_OPTION_PARAMETERS_TABLES}

# Порядок снятия круга — не порядок `FUNCTIONAL_OPTION_PARAMETERS_TABLES`:
# `functional_option_parameter_targets.functional_option_parameter_id` ссылается на строку вида
# с `ON DELETE CASCADE`, и каскад снял бы применение молча, без точного счётчика. Явный
# `DELETE` первым держит честное число снятых строк (M7) и не зависит от того, поставлен ли
# каскад в данной базе (миграция V57 могла не применяться). Тот же приём, что `REMOVE_ORDER`
# узлов V49, V50, V52, V54, V56.
REMOVE_ORDER: Tuple[str, ...] = FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER

# Колонки индекса состава, которые нужны разбору вида: `name`/`object_name` — ключ сверки
# (`FunctionalOptionsParameter.<Имя>`), `uuid` — цель строки применения и сверка uuid файла с
# записью перечня, `child_type` — различение записей одного имени, `depth`/`parent_name` —
# состояние «запись индекса имеет глубину» (иерархии раскладки у вида нет, замер 1.2).
# Фильтра по типу вида здесь нет намеренно: цели перечня `<Use>` ведут на объекты ДРУГИХ
# видов, включая псевдозаписи срезов (замер 2.1), а свой круг вида отбирает сам разбор
# (`kind_index_rows`, точный `object_type`). Тот же приём, что `read_index_records` узлов
# V46, V48, V49, V50, V56.
INDEX_ROW_COLUMNS: Tuple[str, ...] = (
    "name", "object_id", "object_type", "object_name", "child_type", "parent_name", "depth",
    "uuid",
)

# Ключи сводки разбора, совпадающие с ключами контракта по имени (один словарь на разбор и на
# ответ): копируются только они — неперечисленный ключ контракта читается нулём (C1), а
# незнакомый ключ разбора не попадает в ответ, которого карточка не обещала (прецедент
# `SUMMARY_KEYS` узлов V46/V48/V49/V50/V56). Ключей `rows` и `targets` здесь нет: строки записи
# идут в писатели, а не в ответ стадии (14 + 34 строки на корпус — замер 1.4); `success`
# разбора — внутренний признак круга, стадия отвечает своими `success` и `status`.
SUMMARY_KEYS: Tuple[str, ...] = FUNCTIONAL_OPTIONS_PARAMETERS_SUMMARY_KEYS


def read_index_records(cur, configuration_id: int) -> Dict[str, Any]:
    """Прочитать строки индекса состава этой конфигурации (тот же источник, что V46…V56).

    Источником служит таблица `configuration_objects`, а не повторный разбор
    `ConfigDumpInfo.xml`: правило V43 (вторым источником индекс состава не становится), и
    только строки БД содержат псевдозаписи срезов (`.Dimension.`, `.Resource.`, `.Attribute.`,
    `.TabularSection.`), которыми разрешается цель перечня `<Use>` (замер 2.1).

    Отсутствие строк — НЕ отказ стадии: возвращается `available = False` с причиной, а стадия
    называет это предупреждением. При недоступном индексе сверка файлов с перечнем невозможна,
    а цели остаются `unresolved` — «цели нет в перечне» и «перечень не загружен» являются
    разными ответами (правило C2, Q3). Отличие от V55 названо слоем: состояние `pending`
    колонкам схемы вида не выразимо, его отклоняют CHECK'и только круга V55, поэтому здесь
    недоступный индекс является предупреждением, а не отказом стадии.
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
            "разрешение целей перечня `<Use>` невозможны"
        )
        return {"rows": [], **info}
    info.update({
        "available": True,
        "row_count": len(records),
        "kind_count": len(kind_index_rows(records)),
    })
    return {"rows": records, **info}


def remove_functional_options_parameters(cur, configuration_uuid: str,
                                        tables: Tuple[str, ...] = REMOVE_ORDER,
                                        ) -> Dict[str, int]:
    """Снять строки параметров функциональных опций этой конфигурации (в текущей транзакции).

    Очистка обязана быть явной: внешнего ключа на `configurations` и каскада по нему в схеме
    нет осознанно (прецеденты V20.1, V44, V46, V48, V49, V50, V56), иначе строки пережили бы
    снятие заголовка и стали бы сиротами, которые нельзя ни показать в карточке конфигурации,
    ни отличить от строк другой конфигурации. Этим же фильтром (`configuration_uuid`) держится
    снятие в `_remove_rows` конвейера — иначе `force=True` оставил бы в базе прежний состав
    вида (для BP3 это 7 строк параметра и 26 строк применения — замеры 1.1, 2.1).

    Порядок задаёт `REMOVE_ORDER`, а не `FUNCTIONAL_OPTION_PARAMETERS_TABLES`: применение
    снимается ДО параметров, потому что его собственный FK
    `functional_option_parameter_targets_parameter_fkey` объявлен с `ON DELETE CASCADE` —
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

    Заголовок обязателен: свойства вида — третий шаг того же первого слоя, и строки без
    заголовка нельзя ни показать в карточке конфигурации, ни снять вместе с ней (внешний ключ
    в схеме не поставлен осознанно — V20.1). Ленивый импорт — тот же обход цикла, что у слоёв
    V44/V46/V48/V49/V50/V56.
    """
    from configuration_loader import find_configuration  # ленивый импорт — круг узла V44

    card = find_configuration(configuration_uuid)
    if isinstance(card, dict) and card.get("error"):
        return None, f"Ошибка запроса: {card['error']}"
    if not card:
        return None, (
            f"Строка заголовка конфигурации с uuid {configuration_uuid} в базе не найдена. "
            "Сначала загрузите каталог точкой входа load_1c_catalog_tool(source_path=…): "
            "иначе свойства параметров функциональных опций остались бы ни на что не "
            "указывающими, а внешний ключ в схеме не поставлен осознанно (узел V20.1)."
        )
    return card, None


def _stage_failure(reason: str, header: Optional[Dict] = None,
                   extra: Optional[List[str]] = None) -> Dict[str, Any]:
    """Отказ стадии по закрытому контракту (C1): нули по всем ключам, причина — текстом.

    Статус — в `status`: вызывающий отличает «стадия не выполнялась» от «слой отказал» (C2).
    Если заголовок к моменту отказа уже разрешён, он называется: по `configuration_id`
    карточка отличает «заголовка нет» от «заголовок есть, слой отказал по файлам».
    Подсказка о том, чем продолжить, кладётся и в отказ, и в успех: у стадии есть отдельный
    вход `load_functional_options_parameters_tool` (шаг П5), и вызывающий обязан знать это из
    ответа, а не из молчания.
    """
    result = functional_options_parameters_defaults()
    result["status"] = STATUS_ERROR
    result["error"] = reason
    result["reason"] = reason
    if header:
        result["configuration_id"] = header.get("id")
        result["configuration_uuid"] = header.get("uuid")
        result["configuration_name"] = header.get("name")
    result["warnings"].append(FUNCTIONAL_OPTIONS_PARAMETERS_REPEAT_HINT)
    for warning in extra or []:
        result["warnings"].append(warning)
    return result


def observation_counts(observations: List[Any]) -> Dict[str, int]:
    """Счётчик наблюдений круга по роду (`counts_by_observation` контракта).

    Пары `[род, подробности]` даёт разбор (`iter_registration_files`): без счётчика
    «каталога вида нет» и «в каталоге подкаталог или файл не-XML» различались бы только
    перечнем, а карточка обязана называть и число по каждому роду (C1). Словарь родов замкнут
    (`OBSERVATION_KINDS`), и пустой ответ означает «наблюдений нет» — это состояние, а не
    пропуск блока (прецедент `observation_counts` узлов V53, V54, V56).
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
    молчать об этом значило бы не отличать «расхождений нет» от «сверку не делали». Ключей
    `child_mismatches`/`index_pseudo_entries` в словаре нет осознанно: записей детей и
    псевдозаписей вида в индексе состава нет ни в одной выгрузке (замер 1.2), поэтому
    «расхождений нет» и «расхождений не считали» остаются разными ответами.
    """
    listed = dict(zip(FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_DISCREPANCIES,
                      (index_only, file_only, uuid_mismatch)))
    return {state: len(listed.get(state) or [])
            for state in FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_DISCREPANCIES}


def load_functional_options_parameters(source_path: str,
                                      configuration_uuid: Optional[str] = None,
                                      changed_at=None) -> Dict[str, Any]:
    """Загрузить свойства параметров функциональных опций (узел V57, стадия S4l).

    Порядок: каталог → uuid из `Configuration.xml` (или сверка переданного) → проверка, что
    заголовок загружен → индекс состава из `configuration_objects` (сверка файлов с перечнем и
    разрешение целей перечня `<Use>`, Н6) → разбор каталога вида → **одна транзакция**:
    `DELETE` по uuid + вставки двух таблиц → отдельной транзакцией `ANALYZE` (мера V46).

    Групп `kinds` у стадии нет (Q5 раздела 6 плана, вариант A): строка применения существует
    только через id строки параметра (Q1, вариант A), поэтому частичная запись круга
    описывала бы состав, которого в выгрузке нет.

    Отказ разбора любого файла круга или нарушение инвариантов пары «строка вида ↔ строки
    применения» останавливает стадию ДО записи: половина круга читалась бы как полный состав
    вида (приём V12/V46/V48/V49/V50/V53/V54/V56). Отсутствие каталога
    `FunctionalOptionsParameters/` — не отказ, а ответ о выгрузке: `files_found = 0` с
    наблюдением `directory_missing` (Q9): у KomMag позиции вида нет ни файлами, ни строками
    индекса (замер 1.1), и именно так она и отвечает.

    `changed_at` передаёт конвейер: строки одной загрузки обязаны нести одну метку (M2), а не
    время своей транзакции. Пустое значение — своя метка вызова (одиночный прогон слоя).
    Строки применения метку не несут: колонок ревизии у таблицы нет
    (`CONFIGURATION_UNVERSIONED_TABLES`), их текущность читается витриной связкой по
    `functional_option_parameter_id` (Q2, вариант A).

    Порядок записи держится иерархией данных, а не удобством: сначала строки параметров
    (`insert_ids`, `RETURNING id`), затем строки применения, ссылающиеся на id этих ревизий.
    Всё это одной транзакцией: отказ на середине оставил бы в базе параметры без применения,
    то есть состав, которого в выгрузке нет (замеры 1.1, 2.1: 14 параметров и 34 цели на
    корпус, максимум 20 целей у одного параметра — потеря половины перечня была бы незаметна
    в ответе).
    """
    uuid_info = configuration_uuid_from_layout(source_path)
    if "uuid" not in uuid_info:
        return _stage_failure(uuid_info.get("error")
                              or f"Каталог выгрузки не читается: {source_path}")
    layout_uuid = str(uuid_info["uuid"])
    if configuration_uuid and str(configuration_uuid).strip().lower() != layout_uuid.lower():
        # Два источника одного факта указали на разные конфигурации: молча выбрать один —
        # значит записать свойства чужой конфигурации (тот же отказ, что у слоёв
        # V44/V46/V48/V49/V50/V56). Для вида это особенно дорого: имена параметров
        # встречаются в нескольких выгрузках (замер 1.3), и молчаливый выбор записал бы
        # чужой состав.
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

    collected = collect_functional_options_parameters(source_path,
                                                     index_rows=index_info["rows"])
    if not collected["success"]:
        failures = collected.get("files_failed") or []
        violations = collected.get("invariant_violations") or []
        if failures:
            cause = (f"Круг не записан: {len(failures)} файл(ов) каталога "
                     f"{collected.get('directory')} не разобраны — "
                     + "; ".join(f"{item.get('source_path')}: {item.get('reason')}"
                                 for item in failures[:10]))
        else:
            cause = (f"Круг не записан: {len(violations)} файл(ов) нарушают инварианты пары "
                     "«строка вида ↔ строки применения» — "
                     + "; ".join(f"{item.get('source_path')}: {item.get('problems')}"
                                 for item in violations[:10])
                     + ". Состояние `use_state` и счётчик `targets_count` обязаны выводиться "
                       "из строк применения (CHECK "
                       "`functional_option_parameters_use_state_matches_targets`), а не из "
                       "догадки разбора")
        return _stage_failure(
            f"{cause}. Ни одной строки круга в базу не записано: половина круга читалась бы "
            "как полный состав вида (приём V12/V46); прежние строки этой конфигурации не "
            "сняты",
            header=header,
        )

    # Ключ конфигурации знает вызывающий, а не XML файла — тот же порядок, что у писателей
    # свойств V46, модулей корня V44, параметров сеанса V48, ролей V49, реквизитов V50 и
    # опций V56.
    parameter_rows = [dict(row, configuration_uuid=configuration_uuid)
                      for row in (collected.get("rows") or [])]
    target_rows = [dict(row, configuration_uuid=configuration_uuid)
                   for row in (collected.get("targets") or [])]

    # Полнота связывания проверяется ДО транзакции: строка применения обязана ссылаться на
    # строку параметра этого же круга (Q1, вариант A), и молча отбросить её значило бы
    # назвать неполный круг полным. Ключом служит индексное имя
    # `FunctionalOptionsParameter.<Имя>` — именно в этой форме связь несёт колонка
    # `parameter_full_name` (`PARAMETER_LINK_KEY`; прецедент `option_full_name` узла V56,
    # `attribute_full_name` узла V50, `role_name` узла V49). Строка вида при этом несёт
    # короткое `object_name`: мост между двумя формами держит `index_object_name` — та же
    # связка, что у слоёв V49, V50, V56 (замер 1.1: `<ИмяФайла>.xml` ↔
    # `FunctionalOptionsParameter.<ИмяФайла>`, 14 совпадений из 14).
    link_keys = [index_object_name(str(row.get("object_name") or ""))
                 for row in parameter_rows]
    known = set(link_keys)
    if len(known) != len(link_keys):
        duplicated = sorted({key for key in link_keys if link_keys.count(key) > 1})
        return _stage_failure(
            f"Круг не записан: разбор дал {len(link_keys)} строк параметра с "
            f"повторяющимися именами ({', '.join(duplicated[:5])}) — строки применения "
            "нельзя связать однозначно (замер 1.1 даёт уникальность имён внутри выгрузки), "
            "ни одна строка круга не записана",
            header=header,
        )
    unbound = sorted({str(row.get(PARAMETER_LINK_KEY)) for row in target_rows
                      if row.get(PARAMETER_LINK_KEY) not in known})
    if unbound:
        return _stage_failure(
            f"Круг не записан: {len(unbound)} строка(ов) применения остались без строки "
            f"параметра ({', '.join(unbound[:5])}) — это внутреннее противоречие разбора, "
            "а не состояние выгрузки; ни одна строка круга не записана",
            header=header,
        )

    # Один штамп времени на всё событие загрузки (M2): версионируемая таблица одной загрузки
    # не должна нести две метки. Строки применения метку не получают — колонок ревизии у них
    # нет (исключение `CONFIGURATION_UNVERSIONED_TABLES`).
    moment = stamp_revision_rows(parameter_rows, revision_no=FIRST_REVISION,
                                 changed_by=CHANGED_BY_LOAD, changed_at=changed_at)

    removed: Dict[str, int] = {}
    written: Dict[str, int] = {table: 0 for table in FUNCTIONAL_OPTION_PARAMETERS_TABLES}
    try:
        with transaction() as cur:
            removed = remove_functional_options_parameters(cur, configuration_uuid)
            # Параметры — по одной строке с RETURNING id: строка применения ссылается на
            # ЧИСЛОВОЙ id этой ревизии (Q2, вариант A), а `insert_many` id не возвращает.
            # Порядок `insert_ids` совпадает с порядком `parameter_rows` — связь держится им,
            # а не угадыванием (цена поштучной вставки измерена слоями V49/V50/V56 и
            # приемлема: весь круг узла — 14 строк вида и 34 строки применения).
            parameter_ids = FOP_WRITERS[PARAMETER_TABLE].insert_ids(cur, parameter_rows)
            if len(parameter_ids) != len(parameter_rows):
                raise RuntimeError(
                    f"писатель вернул {len(parameter_ids)} id для {len(parameter_rows)} "
                    f"строк таблицы {PARAMETER_TABLE} — связать применение нечем"
                )
            written[PARAMETER_TABLE] = len(parameter_ids)
            ids_by_key = dict(zip(link_keys, parameter_ids))
            for row in target_rows:
                row["functional_option_parameter_id"] = ids_by_key[
                    str(row.get(PARAMETER_LINK_KEY))]
            written[TARGETS_TABLE] = FOP_WRITERS[TARGETS_TABLE].insert_many(cur, target_rows)
    except Exception as exc:  # noqa: BLE001 — заголовок уже разрешён, отказ называется им
        return _stage_failure(
            f"Ошибка записи: {exc}. Транзакция отменена целиком: в базе остались прежние "
            f"строки круга (снятые этим вызовом — {sum(removed.values())}), новых нет",
            header=header,
        )

    # ── статистика записанных таблиц (мера V46) ─────────────────────────────────────────
    # Отдельная транзакция ПОСЛЕ фиксации записи: планировщик обязан увидеть строки, иначе
    # первый же читатель витрин текущего состояния платит минутами за счётчик (замер V46 на
    # BGU2: 8 мин 25 с против 7 мс после ANALYZE; витрины
    # `v_current_functional_option_parameters` и
    # `v_current_functional_option_parameter_targets` считаются связкой по той же цепи
    # ревизий). Отказ статистики отказом загрузки не является: строки зафиксированы, и
    # состояние ответа от него не меняется.
    statistics_refreshed = 0
    try:
        with transaction() as cur:
            refresh_table_statistics(cur, FUNCTIONAL_OPTION_PARAMETERS_TABLES)
            statistics_refreshed = len(FUNCTIONAL_OPTION_PARAMETERS_TABLES)
    except Exception as exc:  # noqa: BLE001 — ответ описывает запись, а не статистику
        warnings.append(
            f"статистика таблиц {', '.join(FUNCTIONAL_OPTION_PARAMETERS_TABLES)} не "
            f"обновлена: {exc}. Строки записаны, но читатель витрин текущего состояния "
            "получит план по пустой статистике: счётчики на большой выгрузке выполняются "
            "минутами вместо миллисекунд"
        )

    result = functional_options_parameters_defaults()
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
        "parameters_written": int(written[PARAMETER_TABLE]),
        "targets_written": int(written[TARGETS_TABLE]),
        "removed_previous": int(sum(removed.values())),
        "removed_by_table": removed,
        "written_by_table": written,
        "statistics_refreshed": statistics_refreshed,
    })
    # Наблюдения и расхождения ног считает стадия, а не разбор: разбор описывает свой вход
    # (офлайн, без живой БД), а ответ стадии обязан описывать содержимое базы и полный круг
    # сравнения с индексом состава (приём `observation_counts`/`circle_discrepancy_counts`
    # узлов V53, V54, V56; словари замкнуты контрактом, поэтому пустой словарь здесь —
    # состояние «наблюдений нет», а не пропуск блока, C1).
    result["counts_by_observation"] = observation_counts(collected.get("observations"))
    result["counts_by_circle_discrepancy"] = circle_discrepancy_counts(
        result["index_only"], result["file_only"], result["uuid_mismatch"])

    # Подсказка о том, чем продолжить, кладётся и в успех, и в отказ: у стадии есть
    # отдельный вход `load_functional_options_parameters_tool` (шаг П5), и вызывающий обязан
    # знать это из ответа, а не из молчания (прецедент REPEAT_HINT узлов V49…V56).
    warnings.append(FUNCTIONAL_OPTIONS_PARAMETERS_REPEAT_HINT)
    if not index_info["available"] and index_info.get("reason"):
        warnings.append(
            f"Индекс состава: {index_info['reason']} — состояния `index_only` и `file_only` "
            "при этом невыразимы, а цели перечня `<Use>` остаются неразрешёнными записями "
            "(Q3): «объекта нет в перечне» от «перечень этой конфигурации не загружен» не "
            "отличить. Отличие от узлов V48…V55 названо слоем: состояний `pending` в схеме "
            "вида нет, поэтому недоступный индекс является предупреждением, а не отказом "
            "стадии"
        )
    for observation, detail in (collected.get("observations") or []):
        if observation == "directory_missing":
            warnings.append(
                f"Каталог {collected.get('directory')}/ в выгрузке отсутствует — параметров "
                "функциональных опций у этой конфигурации нет, и нули таблиц являются ответом "
                "о выгрузке, а не отказом стадии (замер 1.1 даёт KomMag именно в таком виде; "
                "Q9, вариант A)"
            )
        elif observation == "index_not_provided":
            warnings.append(
                "Индекс состава не передан разбору — разрешение целей применения не "
                f"выполнялось ({detail}): все цели остались состоянием `unresolved`, и это НЕ "
                "ответ «цели нет в конфигурации» (правило C2)"
            )
        elif observation in ("unexpected_dir", "unexpected_file"):
            what = "подкаталог" if observation == "unexpected_dir" else "файл не-XML"
            warnings.append(
                f"В каталоге вида найден {what}: {detail} — примитивность круга (плоский "
                "каталог без форм, макетов, команд и модулей, замер 1.2) перестала быть "
                "фактом выгрузки; содержимое этим узлом не читается, и отсутствие колонок "
                "для него является границей узла, а не пропуском"
            )
    if index_info["available"] and int(result["index_kind_records"]) != int(
            result.get("files_found") or 0):
        warnings.append(
            f"Записей `FunctionalOptionsParameter.<Имя>` в индексе состава "
            f"{result['index_kind_records']}, файлов регистрации "
            f"{result.get('files_found')} — круги различаются (замер 1.1 даёт равенство на "
            "трёх выгрузках, где вид есть, поэтому расхождение требует объяснения этим "
            "прогоном; расхождения перечислены ключами `index_only` / `file_only`)"
        )
    if int(result.get("targets_written") or 0) != int(result.get("targets_total") or 0):
        warnings.append(
            f"Разбор дал {result.get('targets_total')} строк применения, записано "
            f"{result.get('targets_written')} — часть строк в {TARGETS_TABLE} не попала; "
            "связь со строкой параметра держится id ревизии (Q2), и молчать об этом нельзя"
        )
    if any(removed.values()):
        details = ", ".join(f"{table}={count}" for table, count in removed.items())
        warnings.append(
            "Прежние строки свойств параметров функциональных опций этой конфигурации сняты "
            f"перед записью: {details}. Идемпотентность держится явным DELETE по "
            "configuration_uuid: внешнего ключа и каскада по конфигурации в схеме нет "
            "осознанно (прецедент V20.1); новая ревизия на повторную загрузку той же "
            "выгрузки не заводится — история состояний принадлежит узлу правки объекта, "
            "которого в схеме ещё нет"
        )
    if parameter_rows:
        warnings.append(
            f"Момент загрузки строк параметра — {moment}: той же меткой помечены строки "
            "заголовка и других стадий этого события (M2); строки применения метку не несут "
            "(своей цепи ревизий у них нет, Q2 вариант A)"
        )
    else:
        warnings.append(
            "Строк параметра этим вызовом не записано: каталог вида пуст или отсутствует "
            f"(файлов {result.get('files_found')}), поэтому и общего момента загрузки вида у "
            "этого события нет — нули таблиц являются ответом о выгрузке (Q9)"
        )
    result["warnings"] = warnings
    return result
