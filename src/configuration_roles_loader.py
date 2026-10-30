#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Загрузчик свойств ролей конфигурации (узел V49, шаг П4, 30.10.2026).

Стадия S4d конвейера первого слоя: файлы вида `Roles` (позиция 2.4 нормативного списка
плана `docs/CONFIGURATION_ROLES_PLAN.md`) в четыре таблицы `roles`, `role_rights`,
`role_restriction_templates`, `role_sources`. Норматив — тот же план (решения Q2, Q3, Q6,
Q8, Q9, правила C1–C3); разбор файлов вида — отдельный модуль
`src/configuration_roles.py` (шаг П2), писатели строк — реестр
`CONFIGURATION_OBJECT_WRITERS` (шаг П3).

Почему стадия отдельная, а не третий вид S4 и не расширение V48 (прецедент Q5 узла V48):
правило C3 требует своего ключа ответа `roles`; порядок `STAGES` повторяет порядок
нормативного списка (2.4 идёт сразу за 2.3), поэтому S4d стоит между S4c и S4b. Круг
стадии S4 (`CHILD_TABLES`) от круга версионности отделён в П3: регистрация таблиц вида в
`CONFIGURATION_VERSIONED_TABLES` молча добавила бы их к чужой стадии.

Почему стадия является одновременно слоем (прецедент V44/V46/V48):

* ключ строки — `configuration_uuid`, а не `id` заголовка: `force=True` меняет id, uuid
  остаётся прежним;
* стадия вызывается ПОСЛЕ коммита транзакции заголовка: `transaction()` каждый раз
  открывает новое соединение, и в собственной транзакции заголовка слой не увидел бы ни
  строки заголовка, ни строк индекса состава, по которым разрешаются цели прав (Q3);
* отдельный MCP-инструмент `load_roles_tool` (шаг П5) нужен для случая «изменились только
  файлы `Roles/`»: заголовок и индекс состава при этом не меняются. Стадия конвейера и
  этот инструмент вызывают одну и ту же функцию слоя — двух кодов, которые могли бы
  разойтись, в проекте нет.

Что здесь происходит и чего здесь нет:

* круг задают каталог `Roles/` (метаданные `Roles/<Имя>.xml` и содержимое
  `<Имя>/Ext/Rights.xml`) и записи индекса состава того же вида (`Role.<Имя>` и
  `Role.<Имя>.Rights`); расхождение двух источников называется `index_only` / `file_only`
  / `uuid_mismatch` — четыре замеренные выгрузки дают нули, и нули обязаны быть названы;
* строка права ссылается на ЧИСЛОВОЙ id строки роли (Q2, вариант A): своей цепи ревизий у
  `role_rights` нет, права живут ровно столько, сколько живёт конкретная ревизия роли.
  Поэтому роли вставляются `insert_ids()` (по одной строке, `RETURNING id`), а полученный
  id подставляется в строки прав — порядок `insert_ids` совпадает с порядком строк;
* `role_rights` не штампуется ревизией (колонок `revision_no`/`changed_*` у таблицы нет —
  исключение `CONFIGURATION_UNVERSIONED_TABLES`), остальные три таблицы — штампуются;
* снятие круга начинается с `role_rights`: FK `role_rights_role_id_fkey` объявлен с
  `ON DELETE CASCADE` (П1), и каскад снял бы права молча, без точного счётчика —
  вызывающий обязан назвать полное состояние, снятое `force=True` (M7);
* текст `Rights.xml` целиком не пишется — только дескриптор (Q9, вариант A).

Идемпотентность держится явным `DELETE` по `configuration_uuid` (внешнего ключа на
`configurations` и каскада по нему в схеме нет осознанно — прецеденты V20.1, V44, V46, V48),
а не новой ревизией: повторная загрузка той же выгрузки не создаёт истории, снятые строки
названы в ответе (`removed_previous`, `removed_by_table`). Ключом цепочки состояния
версионируемых таблиц является (`configuration_uuid`, `object_name`, `revision_no`) —
позиция O9 плана: `Role.АдминистраторСистемы` есть и в BGU2, и в BP3, с разными uuid.

Круг пишется одной транзакцией, и отказ разбора любого файла круга останавливает стадию ДО
записи: в базе не остаётся половины строк (приём V12/V46/V48). Молча записать то, что
разобралось, означало бы назвать неполный круг полным составом вида — «ролей нет» и «роли
не разобрались» различаются состоянием ответа, а не числом.

После фиксации загрузчик пересобирает статистику четырёх таблиц
(`refresh_table_statistics` — мера V46): планировщик не знает о строках собственной
загрузки, и без статистики счётчики по витринам текущего состояния на большой выгрузке
выполняются минутами (замер V46 на BGU2: 8 мин 25 с против 7 мс). Отказ статистики отказом
загрузки не является — строки зафиксированы, и это предупреждение.

Прогон шага: `python _v49_p4_loader_probe.py MinCfg KomMag`, затем отдельно BGU2 и BP3
(прогоны, меняющие общее состояние БД, не параллелят).
"""
from typing import Any, Dict, List, Optional, Tuple

from configuration_load_contract import (
    ROLE_DIR,
    ROLE_KIND_RIGHTS,
    ROLE_KIND_ROLES,
    ROLE_KIND_WRITE_ORDER,
    ROLE_KINDS,
    ROLE_RIGHTS_TABLE,
    ROLE_SOURCES_TABLE,
    ROLE_TABLE,
    ROLE_TABLES,
    ROLE_TABLES_BY_KIND,
    ROLE_TEMPLATES_TABLE,
    ROLES_REPEAT_HINT,
    STATUS_ERROR,
    STATUS_OK,
    roles_defaults,
)
from configuration_object_properties_loader import refresh_table_statistics
from configuration_roles import (
    collect_roles,
    kind_index_rows,
    rights_index_rows,
)
from configuration_root_module_loader import configuration_uuid_from_layout
from current_revision import (
    CHANGED_BY_LOAD,
    FIRST_REVISION,
    current_view,
    stamp_revision_rows,
)
from external_db import transaction
from external_table_writer import CONFIGURATION_OBJECT_WRITERS

OBJECTS_TABLE = "configuration_objects"

# Писатели четырёх таблиц берутся общим реестром, а не импортом классов (правило п.6 слоя):
# ошибка выбора превращается в запись не в ту таблицу, а реестр уже знает, какая таблица
# версионируется своей цепочкой, а какая — нет (`CONFIGURATION_UNVERSIONED_TABLES`).
ROLE_WRITERS = {table: CONFIGURATION_OBJECT_WRITERS[table] for table in ROLE_TABLES}

# Порядок снятия круга — не порядок `ROLE_TABLES`: `role_rights.role_id` ссылается на
# строку `roles` с `ON DELETE CASCADE`, и каскад снял бы права молча, без точного
# счётчика. Явный `DELETE` первым держит честное число снятых строк (M7) и не зависит от
# того, поставлен ли каскад в данной базе (миграция V49 могла не применяться).
REMOVE_ORDER: Tuple[str, ...] = (
    ROLE_RIGHTS_TABLE,
    ROLE_TEMPLATES_TABLE,
    ROLE_SOURCES_TABLE,
    ROLE_TABLE,
)

# Колонки индекса состава, которые нужны разбору вида: `name`/`object_name` — ключ сверки
# (`Role.<Имя>`, `Role.<Имя>.Rights`), `uuid` — цель ссылочного типа и сверка uuid файла
# с записью перечня, `child_type` — различение двух записей одного имени,
# `depth`/`parent_name` — состояние «запись индекса имеет глубину» (иерархии у вида нет,
# замер 2.9). Фильтра по типу вида здесь нет намеренно: разрешение целей обязано видеть
# записи ЛЮБОГО вида (замер 2.6: цели прав ведут на объекты других видов), а свой круг
# вида отбирает сам разбор (`kind_index_rows`, `rights_index_rows`). Тот же приём, что у
# `read_index_records` узлов V46 и V48: источник — строки БД, а не повторный разбор
# `ConfigDumpInfo.xml`.
INDEX_ROW_COLUMNS: Tuple[str, ...] = (
    "name", "object_id", "object_type", "object_name", "child_type", "parent_name", "depth",
    "uuid",
)

# Ключи сводки разбора, совпадающие с ключами контракта по имени (один словарь на разбор и
# на ответ): копируются только они — неперечисленный ключ контракта читается нулём (C1), а
# незнакомый ключ разбора не попадает в ответ, которого карточка не обещала (прецедент
# `SUMMARY_KEYS` узлов V46/V48). Ключей `*_rows` здесь нет: строки записи идут в писатели,
# а не в ответ стадии; `index_provided` и `success` разбора — внутренние признаки круга,
# стадия отвечает своими `index_available` и `status`.
SUMMARY_KEYS: Tuple[str, ...] = (
    "directory", "metadata_files_found", "rights_files_found", "roles_read", "files_failed",
    "observations", "index_only", "file_only", "uuid_mismatch",
    "counts_by_content_state", "counts_by_target_resolve_state",
    "counts_by_right_name_state", "counts_by_right_value_state",
    "counts_by_condition_state", "counts_by_declaration_state",
    "targets_total", "targets_distinct", "rights_total", "restrictions_total",
    "restrictions_with_call", "restrictions_no_call", "restrictions_with_field",
    "restrictions_called_own_role", "restrictions_called_other_role",
    "template_occurrences", "template_names_total", "template_texts_distinct",
    "unknown_right_names", "unexpected_tags", "flag_missing", "flag_unknown_form",
    "duplicate_targets", "duplicate_right_names", "empty_condition_elements",
    "targets_without_name", "rights_without_name", "templates_without_name",
    "templates_without_text", "name_file_mismatch", "roles_without_uuid",
    "sources_without_uuid", "content_file_missing", "ambiguous_template_calls",
)


def read_index_records(cur, configuration_id: int) -> Dict[str, Any]:
    """Записи индекса состава этой конфигурации из `configuration_objects` (Н6).

    Пустой ответ означает «индекс недоступен», а не «объектов нет»: при недоступном индексе
    сверка файлов с перечнем и разрешение целей невыразимы, и вызывающий обязан назвать это
    состоянием загрузки, а не нулями (тот же контракт, что у слоёв V46, V47, V48).

    Своего вида здесь считаются ДВА числа: записей `Role.<Имя>` и записей
    `Role.<Имя>.Rights`. Это разные круги (Q6 узла V49, вариант A): роль без записи
    содержимого в выгрузке существует, а равенство двух чисел — наблюдение четырёх
    замеренных выгрузок (1 202/1 202), а не свойство вида, поэтому расхождение обязан
    назвать ответ стадии.
    """
    info: Dict[str, Any] = {"available": False, "row_count": 0, "kind_count": 0,
                            "content_count": 0, "reason": None}
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
            "разрешение целей невозможны"
        )
        return {"rows": [], **info}
    info.update({
        "available": True,
        "row_count": len(records),
        "kind_count": len(kind_index_rows(records)),
        "content_count": len(rights_index_rows(records)),
    })
    return {"rows": records, **info}


def remove_roles(cur, configuration_uuid: str,
                 tables: Tuple[str, ...] = REMOVE_ORDER) -> Dict[str, int]:
    """Снять строки ролей этой конфигурации (внутри текущей транзакции).

    Очистка обязана быть явной: внешнего ключа на `configurations` и каскада по нему в
    схеме нет осознанно (прецеденты V20.1, V44, V46, V48), иначе строки пережили бы снятие
    заголовка и стали бы сиротами, которые нельзя ни показать в карточке конфигурации, ни
    отличить от строк другой конфигурации. Этим же фильтром (`configuration_uuid`) держится
    снятие в `_remove_rows` конвейера — иначе `force=True` оставил бы в базе прежний
    состав вида.

    Порядок задаёт `REMOVE_ORDER`, а не `ROLE_TABLES`: права снимаются ДО ролей, потому что
    их собственный FK `role_rights_role_id_fkey` объявлен с `ON DELETE CASCADE` — каскад
    снял бы права молча, и число в ответе было бы неправдой (M7).
    """
    removed: Dict[str, int] = {}
    for table in tables:
        cur.execute(f"DELETE FROM {table} WHERE configuration_uuid = %s::uuid",
                    [str(configuration_uuid)])
        removed[table] = cur.rowcount
    return removed


def normalize_kinds(kinds) -> Tuple[Tuple[str, ...], Optional[str]]:
    """Разобрать запрос групп круга S4d в замкнутом словаре `ROLE_KINDS`.

    `None` — весь круг, то есть ровно то, что делает стадия конвейера: два входа
    (конвейер и отдельный инструмент) не должны расходиться значением по умолчанию
    (прецедент `normalize_kinds` узла V46).

    Каждая граница запроса называется текстом отказа, а не молчаливой деградацией:

    * неизвестная группа — с перечнем допустимых: «такой группы нет» и «группу не просили»
      — разные ответы, и второй нельзя получать из первого;
    * пустой список — отказ: вызов, который ничего не пишет, неотличим от вызова, который
      ничего не нашёл (C2);
    * `roles` без `role_rights` — отказ: снятие ролей каскадом `role_rights_role_id_fkey`
      сняло бы права, и в базе остались бы роли с состоянием `with_rights` без единой
      строки прав — состав, которого в выгрузке нет (запрет «половины круга», V12/V46);
    * `role_rights` без `roles` — разрешено: строки прав дописываются к уже лежащим в базе
      CURRENT-ревизиям ролей (сценарий позиции O8 — «права отдельным входом»); если строк
      ролей в базе нет, отказ называет это состоянием базы, а не ошибкой запроса.
    """
    if kinds is None:
        return ROLE_KINDS, None
    items = [kinds] if isinstance(kinds, str) else list(kinds)
    wanted = set()
    unknown: List[str] = []
    for item in items:
        name = str(item or "").strip()
        if not name:
            continue
        if name in ROLE_KINDS:
            wanted.add(name)
        else:
            unknown.append(name)
    if unknown:
        return (), ("Запрошены группы круга ролей, которых нет: "
                    + ", ".join(sorted(unknown)) + ". Реализованы: "
                    + ", ".join(ROLE_KINDS)
                    + " (и весь круг без параметра kinds).")
    if not wanted:
        return (), ("Пустой kinds: не запрошена ни одна группа круга. Укажите хотя бы одну "
                    "из " + ", ".join(ROLE_KINDS) + " или уберите kinds, чтобы записать "
                    "весь круг.")
    if ROLE_KIND_ROLES in wanted and ROLE_KIND_RIGHTS not in wanted:
        return (), ("Группа `roles` не записывается без `role_rights`: строки прав ссылаются "
                    "на id строк ролей и снимаются каскадом `role_rights_role_id_fkey`, "
                    "поэтому в базе остались бы роли с состоянием `with_rights` без единой "
                    "строки прав — состав, которого в выгрузке нет. Запросите "
                    "`roles,role_rights` или весь круг.")
    return tuple(kind for kind in ROLE_KIND_WRITE_ORDER if kind in wanted), None


def existing_role_ids(cur, configuration_uuid: str) -> Dict[str, int]:
    """Числовые id CURRENT-ревизий ролей этой конфигурации (для группы `role_rights`).

    Строка права ссылается на id конкретной ревизии роли (Q2, вариант A). Когда сами роли
    в этом вызове не перезаписываются, ролью остаётся та строка, что уже лежит в базе, —
    её id читается витриной текущего состояния, а не поиском максимума по цепочке
    (прецедент `v_current_roles` из замера P1).
    """
    cur.execute(
        f"SELECT object_name, id FROM {current_view(ROLE_TABLE)} "
        "WHERE configuration_uuid = %s::uuid", (str(configuration_uuid),))
    return {str(row[0]): int(row[1]) for row in cur.fetchall()}


def _require_header(configuration_uuid: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Найти строку заголовка по uuid; вернуть карточку или причину отказа.

    Заголовок обязателен: свойства вида — второй шаг того же первого слоя, и строки без
    заголовка нельзя ни показать в карточке конфигурации, ни снять вместе с ней (внешний
    ключ в схеме не поставлен осознанно — V20.1). Ленивый импорт — тот же обход цикла, что
    у слоёв V44/V46/V48.
    """
    from configuration_loader import find_configuration  # ленивый импорт — круг узла V44

    card = find_configuration(configuration_uuid)
    if isinstance(card, dict) and card.get("error"):
        return None, f"Ошибка запроса: {card['error']}"
    if not card:
        return None, (
            f"Строка заголовка конфигурации с uuid {configuration_uuid} в базе не найдена. "
            "Сначала загрузите каталог точкой входа load_1c_catalog_tool(source_path=…): "
            "иначе свойства ролей остались бы ни на что не указывающими, а внешний ключ в "
            "схеме не поставлен осознанно (узел V20.1)."
        )
    return card, None


def _stage_failure(reason: str, header: Optional[Dict] = None,
                   status: str = STATUS_ERROR,
                   extra: Optional[List[str]] = None) -> Dict[str, Any]:
    """Отказ стадии в форме закрытого контракта (C1, C3).

    Причина кладётся в ключ `error` замкнутого словаря `roles_defaults()`, а статус — в
    `status`: вызывающий отличает «стадия не выполнялась» от «слой отказал» (C2). Если
    заголовок к моменту отказа уже разрешён, он называется: по `configuration_id` карточка
    отличает «заголовка нет» от «заголовок есть, слой отказал по файлам». Подсказка о том,
    чем продолжить, кладётся и в отказ, и в успех: у стадии есть отдельный вход
    `load_roles_tool` (шаг П5), и вызывающий обязан знать это из ответа, а не из молчания.
    """
    result = roles_defaults()
    result["status"] = status
    result["error"] = reason
    result["reason"] = reason
    if header:
        result["configuration_id"] = header.get("id")
        result["configuration_uuid"] = header.get("uuid")
        result["configuration_name"] = header.get("name")
    result["warnings"].append(ROLES_REPEAT_HINT)
    for warning in extra or []:
        result["warnings"].append(warning)
    return result


def _prepared_rights(collected: Dict, role_rows: List[Dict],
                     configuration_uuid: str) -> Tuple[List[Dict], List[str]]:
    """Связать строки прав с именами строк роли ДО записи (проверка, а не молчание).

    Писатель `role_rights` ждёт числовой `role_id` конкретной ревизии (Q2, вариант A), а
    разбор даёт `role_name` — связь по имени, которую колонкой делать нельзя (иначе строка
    права ссылалась бы на имя вместо ревизии). Имена уже вставленных ролей дадут id только
    внутри транзакции, поэтому здесь проверяется только полнота связывания: право, имя
    которого не имеет строки роли в этом же круге, — внутреннее противоречие разбора, и
    молча отбросить его значит потерять строку круга (приём П3: запись равна разбору).

    Возвращает (строки для писателя, имена прав без пары).
    """
    known = {str(row.get("object_name")) for row in role_rows}
    prepared: List[Dict] = []
    orphans: List[str] = []
    for source in collected.get("right_rows") or []:
        role_name = source.get("role_name")
        if role_name is None or str(role_name) not in known:
            orphans.append(str(role_name))
            continue
        row = dict(source)
        # `role_name` остаётся в словаре намеренно: писатель собирает значения по своим
        # COLUMNS (extra-ключи он не читает), а связь с id ревизии подставляется после
        # вставки ролей — без имени строки роли мы не узнаем, чьим id дополнять строку.
        row["role_id"] = None          # настоящий id подставляет транзакция
        row["configuration_uuid"] = configuration_uuid
        prepared.append(row)
    return prepared, orphans


def load_roles(source_path: str,
               configuration_uuid: Optional[str] = None,
               kinds=None,
               changed_at=None) -> Dict[str, Any]:
    """Загрузить свойства ролей конфигурации (узел V49, стадия S4d).

    Порядок: каталог → uuid из `Configuration.xml` (или сверка переданного) → проверка, что
    заголовок загружен → круг запрошенных групп → индекс состава из `configuration_objects`
    (сверка файлов с перечнем и разрешение целей, Н6) → разбор каталога вида →
    **одна транзакция**: `DELETE` по uuid + вставки запрошенных таблиц → отдельной
    транзакцией `ANALYZE` (мера V46).

    `kinds` — группы круга (`roles`, `role_rights`, `role_restrictions`), нужные отдельному
    входу `load_roles_tool` (шаг П5); пусто — весь круг, то есть ровно то, что делает
    стадия конвейера. Группы управляют записью, а не разбором: разбор всегда полный, потому
    что опознание вызова шаблона требует деклараций всех ролей конфигурации (Q5), а разрешение
    целей — индекса состава (Q3); половина круга при частичном разборе дала бы состояния,
    которых в выгрузке нет. Экономии времени `kinds` поэтому не даёт (замер П4: 210 МБ
    читаются и при одном шаблоне), она даёт точечную запись без снятия соседних таблиц.
    Границы запроса — в `normalize_kinds`.

    Отказ разбора любого файла круга останавливает стадию ДО записи: половина круга в базе
    читалась бы как полный состав вида (приём V12/V46). Отсутствие каталога `Roles/` — не
    отказ, а ответ о выгрузке: `metadata_files_found = 0` с наблюдением `directory_missing`,
    потому что у конфигурации без ролей их действительно нет (замер 2.1 даёт каталог во
    всех четырёх выгрузках, но это наблюдение, а не свойство вида).

    `changed_at` передаёт конвейер: строки одной загрузки обязаны нести одну метку (M2), а
    не время своей транзакции. Пустое значение — своя метка вызова (одиночный прогон
    слоя); для всех записываемых таблиц момент берётся один — его возвращает первая
    `stamp_revision_rows`.

    Порядок записи держится иерархией данных, а не удобством: сначала роли (`insert_ids`,
    `RETURNING id`), затем права, ссылающиеся на id этих строк (Q2, вариант A), затем
    тексты шаблонов и дескрипторы файлов — они на строки прав не ссылаются. Всё это одной
    транзакцией: отказ на середине оставил бы в базе роли без прав, то есть состав,
    которого в выгрузке нет. Когда группы `roles` в запросе нет, права пишутся на
    CURRENT-ревизии ролей, уже лежащие в базе (`existing_role_ids`), — ролей без них база
    не оставляет.
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

    wanted_kinds, kinds_error = normalize_kinds(kinds)
    if kinds_error:
        return _stage_failure(kinds_error)
    # Таблицы запроса — объединение таблиц запрошенных групп: ответ по ним и обязан
    # назвать, что снялось и записалось, а что осталось прежним.
    touched_tables = tuple(table for kind in wanted_kinds
                           for table in ROLE_TABLES_BY_KIND[kind])

    warnings: List[str] = []
    index_info: Dict[str, Any] = {"available": False, "row_count": 0, "kind_count": 0,
                                  "content_count": 0, "reason": None}
    try:
        with transaction() as cur:
            index_info = read_index_records(cur, int(header["id"]))
    except Exception as exc:  # noqa: BLE001 — индекс читается до записи, отказ называется им
        index_info["reason"] = f"чтение {OBJECTS_TABLE} не удалось: {exc}"

    collected = collect_roles(source_path, index_rows=index_info["rows"])
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

    role_rows = list(collected.get("role_rows") or [])
    template_rows = list(collected.get("template_rows") or [])
    source_rows = list(collected.get("source_rows") or [])
    write_roles = ROLE_TABLE in touched_tables
    write_rights = ROLE_RIGHTS_TABLE in touched_tables
    write_templates = ROLE_TEMPLATES_TABLE in touched_tables
    write_sources = ROLE_SOURCES_TABLE in touched_tables

    rights: List[Dict] = []
    orphans: List[str] = []
    existing_ids: Dict[str, int] = {}
    if write_rights:
        # Ключом проверки остаётся имя строки роли: числовой id даёт только транзакция
        # вставки (Q2, вариант A). Когда группа `roles` в запросе не участвовала, ролью
        # остаётся строка, уже лежащая в базе, — её CURRENT-ревизию читает
        # `existing_role_ids`, и проверять полноту связывания приходится по ней.
        key_rows = role_rows
        if not write_roles:
            try:
                with transaction() as cur:
                    existing_ids = existing_role_ids(cur, configuration_uuid)
            except Exception as exc:  # noqa: BLE001 — состояние базы называется отказом
                return _stage_failure(
                    f"Группа `role_rights` не записана: чтение текущего состава ролей этой "
                    f"конфигурации не удалось: {exc}. Строки прав ссылаются на id ревизий "
                    "ролей — запросите `roles,role_rights` либо весь круг без kinds.",
                    header=header,
                )
            key_rows = [{"object_name": name} for name in sorted(existing_ids)]
        rights, orphans = _prepared_rights(collected, key_rows, configuration_uuid)
    if orphans:
        # Право без строки роли в том же круге — противоречие самого разбора: строка права
        # обязана ссылаться на ревизию роли (Q2), и молча её отбросить значит назвать
        # неполный круг полным. Отказ до транзакции: в базе остаётся прежний состав.
        detail = (
            "Разбор дал право имени, которого нет среди построенных строк ролей — это "
            "внутреннее противоречие разбора, а не состояние выгрузки"
            if write_roles else
            "В базе нет CURRENT-строк ролей этих имён, а группа `roles` в этом вызове не "
            "участвовала: права не на что записать — запросите `roles,role_rights` либо "
            "весь круг без kinds"
        )
        return _stage_failure(
            f"Круг не записан: {len(orphans)} строка(ов) прав остались без строки роли "
            f"({', '.join(orphans[:5])}). {detail}; ни одна строка круга не записана",
            header=header,
        )

    # Ключ конфигурации знает вызывающий, а не XML объекта — тот же порядок, что у писателей
    # свойств V46, модулей корня V44 и параметров сеанса V48. Строки незапрошенных групп
    # ни ключом не помечаются, ни ревизией не штампуются: этот вызов их не касается.
    for rows, writing in ((role_rows, write_roles), (template_rows, write_templates),
                          (source_rows, write_sources)):
        if not writing:
            continue
        for row in rows:
            row["configuration_uuid"] = configuration_uuid
    # Один штамп времени на всё событие загрузки (M2): записываемые таблицы одной загрузки
    # не должны нести разные метки, иначе их нельзя прочитать как один состав. Метку
    # определяет первая штампуемая таблица и передаётся остальным; если версионируемых
    # таблиц в запросе нет (одна группа `role_rights`), штамп не нужен вовсе — у прав
    # колонок ревизии нет (исключение `CONFIGURATION_UNVERSIONED_TABLES`).
    moment = changed_at
    if write_roles:
        moment = stamp_revision_rows(role_rows, revision_no=FIRST_REVISION,
                                     changed_by=CHANGED_BY_LOAD, changed_at=moment)
    if write_templates:
        moment = stamp_revision_rows(template_rows, revision_no=FIRST_REVISION,
                                     changed_by=CHANGED_BY_LOAD, changed_at=moment)
    if write_sources:
        moment = stamp_revision_rows(source_rows, revision_no=FIRST_REVISION,
                                     changed_by=CHANGED_BY_LOAD, changed_at=moment)

    removed: Dict[str, int] = {}
    written: Dict[str, int] = {table: 0 for table in ROLE_TABLES}
    # Снимаются только таблицы запроса, и порядок остаётся `REMOVE_ORDER` (права раньше
    # ролей), а не порядком групп запроса: каскад не должен снять строку молча (M7).
    remove_targets = tuple(table for table in REMOVE_ORDER if table in touched_tables)
    try:
        with transaction() as cur:
            removed = remove_roles(cur, configuration_uuid, remove_targets)
            ids_by_name: Dict[str, int] = dict(existing_ids)
            if write_roles:
                # Роли — по одной строке с RETURNING id: строка права ссылается на ЧИСЛОВОЙ
                # id этой ревизии (Q2, вариант A), а `insert_many` id не возвращает. Порядок
                # `insert_ids` совпадает с порядком `role_rows` — связь держится им, а не
                # угадыванием (их всего 682 на BP3, цена поштучной вставки невелика).
                role_ids = ROLE_WRITERS[ROLE_TABLE].insert_ids(cur, role_rows)
                written[ROLE_TABLE] = len(role_ids)
                ids_by_name.update({str(row.get("object_name")): record_id
                                    for row, record_id in zip(role_rows, role_ids)})
            if write_rights:
                for row in rights:
                    row["role_id"] = ids_by_name[str(row["role_name"])]
                written[ROLE_RIGHTS_TABLE] = ROLE_WRITERS[ROLE_RIGHTS_TABLE].insert_many(
                    cur, rights)
            if write_templates:
                written[ROLE_TEMPLATES_TABLE] = ROLE_WRITERS[
                    ROLE_TEMPLATES_TABLE].insert_many(cur, template_rows)
            if write_sources:
                written[ROLE_SOURCES_TABLE] = ROLE_WRITERS[
                    ROLE_SOURCES_TABLE].insert_many(cur, source_rows)
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
    # является: строки зафиксированы, и состояние ответа от него не меняется. Незатронутые
    # таблицы не анализируются: их статистика уже соответствует их строкам, а `ANALYZE`
    # большой таблицы ради вызова, который её не касался, платил бы минутами.
    statistics_refreshed = 0
    try:
        with transaction() as cur:
            refresh_table_statistics(cur, touched_tables)
            statistics_refreshed = len(touched_tables)
    except Exception as exc:  # noqa: BLE001 — ответ описывает запись, а не статистику
        warnings.append(
            f"статистика таблиц {', '.join(touched_tables)} не обновлена: {exc}. Строки "
            "записаны, но читатель витрин текущего состояния получит план по пустой "
            "статистике: счётчики на большой выгрузке выполняются минутами вместо "
            "миллисекунд"
        )

    kinds_state = {
        kind: {
            "requested": True,
            "written": int(sum(written[table]
                               for table in ROLE_TABLES_BY_KIND[kind])),
            "removed_previous": int(sum(removed.get(table) or 0
                                       for table in ROLE_TABLES_BY_KIND[kind])),
        }
        for kind in wanted_kinds
    }
    result = roles_defaults()
    result.update({
        "status": STATUS_OK,
        "success": True,
        "configuration_id": header["id"],
        "configuration_uuid": configuration_uuid,
        "configuration_name": header.get("name"),
        "kinds_requested": list(wanted_kinds),
        "kinds": kinds_state,
        "rows_written": int(sum(written.values())),
        "written_by_table": written,
        "roles_written": int(written[ROLE_TABLE]),
        "rights_written": int(written[ROLE_RIGHTS_TABLE]),
        "templates_written": int(written[ROLE_TEMPLATES_TABLE]),
        "sources_written": int(written[ROLE_SOURCES_TABLE]),
        "removed_previous": int(sum(removed.values())),
        "removed_by_table": removed,
        "index_available": bool(index_info["available"]),
        "index_role_records": int(index_info["kind_count"]),
        "index_rights_records": int(index_info["content_count"]),
        "statistics_refreshed": statistics_refreshed,
    })
    for key in SUMMARY_KEYS:
        if key in collected:
            result[key] = collected[key]
    warnings.extend(collected.get("warnings") or [])

    if not index_info["available"] and index_info.get("reason"):
        warnings.append(
            f"Индекс состава: {index_info['reason']} — состояния `index_only` и `file_only` "
            "при этом невыразимы, а цели прав остаются неразрешёнными записями (Q3): "
            "«объекта нет в перечне» от «перечень этой конфигурации не загружен» не "
            "отличить"
        )
    for observation, detail in (collected.get("observations") or []):
        if observation == "directory_missing":
            warnings.append(
                f"Каталог {ROLE_DIR}/ в выгрузке отсутствует — ролей у этой конфигурации "
                "нет, и нули таблиц являются ответом о выгрузке, а не отказом стадии"
            )
    if int(result["index_role_records"]) != int(result["index_rights_records"]):
        warnings.append(
            f"Записей `Role.<Имя>` {result['index_role_records']}, записей "
            f"`Role.<Имя>.Rights` {result['index_rights_records']} — круги различаются "
            "(роль без содержимого существует; четыре замеренные выгрузки дают 1 202/1 202, "
            "поэтому расхождение требует объяснения этим прогоном)"
        )
    if len(wanted_kinds) < len(ROLE_KINDS):
        untouched = [table for table in ROLE_TABLES if table not in touched_tables]
        warnings.append(
            "Запрошены не все группы круга (kinds=" + ",".join(wanted_kinds) + "): таблицы "
            + ", ".join(untouched) + " этим вызовом не снимались и не записывались — их "
            "строки остались прежними, и нули `written_by_table` для этих таблиц означают "
            "именно это, а не отсутствие ролей или прав в конфигурации. Разбор при этом "
            "был полным: сводка описывает круг выгрузки, а не содержимое базы, и экономии "
            "времени `kinds` не даёт (позиция O8 плана)")
    if removed:
        warnings.append(
            "Прежние строки свойств ролей этой конфигурации сняты перед записью: "
            f"{', '.join(f'{table}={count}' for table, count in removed.items())}. "
            "Идемпотентность держится явным DELETE по configuration_uuid: внешнего ключа и "
            "каскада по конфигурации в схеме нет осознанно (прецедент V20.1); новая ревизия "
            "на повторную загрузку той же выгрузки не заводится — история состояний "
            "принадлежит узлу правки объекта, которого в схеме ещё нет"
        )
    warnings.append(ROLES_REPEAT_HINT)
    result["warnings"] = warnings
    return result