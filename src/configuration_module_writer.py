#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Писатель модулей объектов конфигурации в `bsl_modules` (узел V47, шаг П3).

Норматив: `docs/CONFIGURATION_OBJECT_MODULES_PLAN.md` (шаг П3, решения Q2, Q4, Q6,
правило C5). Модель сценария — `docs/config-scenarios/01_configuration.md`.

Чем этот модуль является и чем не является:

* круг и путь он НЕ задаёт — их отдаёт словарь `configuration_module_slots` (один
  источник для загрузчика П4, писателя, проверки П5 и проб); здесь только чтение
  файла, сборка строки и её запись;
* транзакцию он НЕ открывает — вторую транзакцию (граница D7, решение Q6) ведёт
  загрузчик П4; сюда приходит курсор уже начатой транзакции, и снятие прежних строк
  происходит в ней же (внешнего ключа на `configurations` в схеме нет осознанно —
  прецеденты V20.1, V44, V46);
* строку без кода он НЕ оставляет (решение Q2): строка появляется там и только там,
  где файл существует, раскодирован и в тексте есть символы. «Модуль пуст» выражается
  отсутствием строки, поэтому колонок состояния в таблице нет и `code` у строк узла
  всегда непустой;
* нечитаемый файл он НЕ теряет молча (правило C5): раскодирование `utf-8-sig` строго,
  без `errors="replace"` и без запасной кодировки. `configuration_object_properties.
  read_module_text` (V46) для этого не переиспользован осознанно — у него запас
  `cp1251` и усечение по `code_limit`, а у узла усечения нет (колонка `truncated`
  для строк узла всегда `false`, решение Q2), и вместо запасной кодировки — отказ
  стадии. Замер круга (раздел 2.3 плана): 13 342 файла из 13 342 раскодированы
  строго, `undecoded` — 0; правило на текущих выгрузках не срабатывает, но при
  появлении такого файла загрузка обязана остановиться с текстом ошибки.

Политика нормализации — та же, что у `read_root_module_file` (V44) и у модулей форм:
текст берётся `.strip()`, а `code_size` считается по нормализованному значению. Иначе
`code_size` не сойдётся с `length(code)` — проверке П5 нечем было бы сверять объём.

Атом полноты — группа объектов (решение Q4): запись идёт последовательно по дереву
конфигурации (обход словаря упорядочен по имени), а отказ любой записи останавливает
стадию и называет её группу. Отказанная группа не оставляет частичных строк: писатель
сам снимает то, что успел вставить (компенсирующий `DELETE`, `abandon_written_rows`),
поэтому состояние второй транзакции не зависит от того, коммитит вызывающий или
откатывает. Прежние строки при этом остаются снятыми — индекс состава пересоздан этой
же загрузкой, и старые строки больше не описывают текущий состав.

Дешёвые проверки раньше дорогих (следствие правила «ошибка загрузки = полная
перезагрузка», Q4.1): путь и существование файла разрешает словарь (П2), здесь файл
только читается.
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from configuration_module_slots import (
    DEFECTS, MAX_EXAMPLES, PARENT_TYPE, REFUSALS, STATE_EMPTY_FILE, STATE_FILE,
    STATE_INDEXED_NO_FILE, STATES, TARGET_TABLE, configuration_header,
    configuration_root_uuid, iter_module_rows,
)
from current_revision import (
    CHANGED_BY_LOAD, FIRST_REVISION, stamp_revision_rows,
)
from external_table_writer import BslModuleRowWriter

# ── политика чтения (её не задаёт ни `_read_bsl_modules`, ни `read_module_text`) ───
DECODING = "utf-8-sig"
# Состояние ЧТЕНИЯ, которого в таблице нет (Q2): «текст есть, но он не раскодирован»
# остаётся отказом стадии, а не строкой и не пропущенной записью.
STATE_UNDECODED = "undecoded"
READ_STATES = STATES + (STATE_UNDECODED,)
# Файл исчез между проверкой словаря и чтением. Для выгрузки это не состояние (замер
# круга — файл есть), а гонка или обрыв; молча считать такой модуль пустым нельзя:
# запись индекса о нём говорит.
REASON_FILE_DISAPPEARED = "file_disappeared"
# Две записи индекса вывелись в один путь. Это дефект вывода (или данных индекса), а
# не состояние выгрузки: уникальность `(parent_uuid, file_path, revision_no)` — ключ
# цепочки состояния (узел V19), и падать на нём посреди транзакции значило бы потерять
# имя группы, которую обязан назвать ответ (Q4).
DEFECT_DUPLICATE_PATH = "duplicate_path"
# Причина отказа принять переданный каталог выгрузки. Загрузчик П4 знает `source_path`
# и передаёт его прямо; принять каталог другой конфигурации — значит записать код не тех
# модулей (тот же контроль, что сверка `configuration_uuid` в `load_root_modules`, V44).
REFUSAL_DUMP_DIR_MISMATCH = "dump_dir_mismatch"

# Страница пакетной вставки. Общего писателя (`BslModuleRowWriter`) не трогаем: у
# внешнего контура строк десятки, и `PAGE_SIZE = None` для них верен. У узла их тысячи
# и каждая с кодом: 10 872 строки (замер `_v47_p3_text_measure.py`, 182 790 397
# символов кода — раздел 2.3 плана) одним `execute_values` легли бы командой примерно
# в 400 МБ SQL-текста — тот же приём, по которому назвал свою страницу
# `ConfigurationObjectRowWriter` (узел V33).
PAGE_SIZE = 200


class ConfigurationObjectModuleRowWriter(BslModuleRowWriter):
    """Спецификация строк узла V47: те же колонки, своя страница вставки.

    Наследование, а не новая спецификация: форма строки взята с существующей записи
    внешних объектов (указание оператора — адаптировать, а не писать заново), колонки и
    колонки ревизии объявляют `BslModuleRowWriter` и `src/current_revision.py`.
    Меняются только значения (`parent_type` = `configuration_objects`, заполненный
    `configuration_uuid`) и размер страницы.
    """

    PAGE_SIZE = PAGE_SIZE


# ── чтение файла модуля (правило C5) ───────────────────────────────────────────────
def read_module_code(abs_path) -> Dict[str, Any]:
    """Прочитать файл модуля и раскодировать строго; вернуть состояние чтения.

    Возвращает `{"state", "code", "code_size", "reason"}`. Исключений не бросает:
    отсутствующий или нечитаемый файл — это состояния, которые вызывающий обязан
    назвать, а не проглотить (тот же контракт, что у `read_root_module_file` V44).

    `code_size` считается по нормализованному тексту и равен числу символов в `code`
    (то есть `length(code)` в PostgreSQL) — на этом равенстве стоит проверка П5.
    """
    path = Path(str(abs_path or ""))
    out = {"state": None, "code": None, "code_size": None, "reason": None}
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        out["state"] = STATE_INDEXED_NO_FILE
        out["reason"] = REASON_FILE_DISAPPEARED
        return out
    except OSError as exc:
        out["state"] = STATE_UNDECODED
        out["reason"] = f"файл не прочитан: {exc}"
        return out
    try:
        text = raw.decode(DECODING)
    except UnicodeDecodeError as exc:
        # Расшифровать «как получилось» (запасной кодировкой или errors="replace") —
        # значит выдать мусор за код модуля и записать его в базу как код.
        out["state"] = STATE_UNDECODED
        out["reason"] = f"файл не раскодирован как {DECODING}: {exc}"
        return out
    text = text.strip()
    if not text:
        # Файл есть, текста нет. П2 считал таким файлам только нулевые по размеру;
        # файл из пробелов или одной BOM — то же состояние, и оно называется здесь,
        # иначе «пустой модуль» и «файла нет» слились бы в один ответ.
        out["state"] = STATE_EMPTY_FILE
        out["code_size"] = 0
        return out
    out["state"] = STATE_FILE
    out["code"] = text
    out["code_size"] = len(text)
    return out


# ── снятие прежних строк круга узла ────────────────────────────────────────────────
def scope_where() -> str:
    """Одна граница строк узла в таблице — uuid заголовка плюс `parent_type`.

    Граница по `parent_type` принципиальна: в `bsl_modules` пишут внешний контур
    (`external_report`/`external_processing`) и узел V46 (тексты общих модулей). Снятие
    только по uuid снесло бы чужие строки — этот дефект уже случался в `_remove_rows`
    и был пойман проверкой (раздел 10 плана). Тот же приём держит V46
    (`remove_common_module_texts`).
    """
    return ("configuration_uuid = %(configuration_uuid)s::uuid "
            "AND parent_type = %(parent_type)s")


def _scope_params(configuration_uuid: str) -> Dict[str, str]:
    return {"configuration_uuid": str(configuration_uuid or ""),
            "parent_type": PARENT_TYPE}


def remove_previous_rows(cur, configuration_uuid: str) -> int:
    """Снять прежние строки круга узла (перед записью, в той же транзакции)."""
    cur.execute("DELETE FROM %s WHERE %s" % (TARGET_TABLE, scope_where()),
                _scope_params(configuration_uuid))
    return cur.rowcount


def count_scope_rows(cur, configuration_uuid: str) -> int:
    """Сколько строк узла лежит в таблице сейчас (для пробы П3 и проверки П5)."""
    cur.execute("SELECT count(*) FROM %s WHERE %s" % (TARGET_TABLE, scope_where()),
                _scope_params(configuration_uuid))
    row = cur.fetchone()
    return int(row[0]) if row else 0


# ── форма результата ────────────────────────────────────────────────────────────────
def result_defaults() -> Dict[str, Any]:
    """Пустой результат стадии — замкнутый перечень.

    Вызывающий обязан отличить «стадия не выполнялась» (отказ с `error`) от «модулей
    нет» (нулевые счётчики при `status = ok`): у конфигурации без модульных записей
    индекса круга нет, и это ответ, а не ошибка.
    """
    return {
        "status": "ok",
        "error": None,
        "refusal": None,
        "failed_group": None,
        "failed_record": None,
        "configuration_uuid": "",
        "configuration_name": None,
        "dump_dir": "",
        "removed_previous": 0,
        "written": 0,
        "compensated_rows": 0,
        "code_chars": 0,
        "counts_by_state": {state: 0 for state in READ_STATES},
        "refusals": {reason: 0 for reason in REFUSALS + (REASON_FILE_DISAPPEARED,
                                                          REFUSAL_DUMP_DIR_MISMATCH)},
        "defects": {reason: 0 for reason in DEFECTS + (DEFECT_DUPLICATE_PATH,)},
        "bin_side": 0,
        "bin_side_examples": [],
        "empty_after_strip": 0,
        "groups": {"seen": 0, "with_rows": 0},
        "samples": [],
        "seconds": 0.0,
    }


def _failure(result: Dict[str, Any], reason: str, detail: str,
             group: Optional[str] = None, name: Optional[str] = None) -> Dict[str, Any]:
    """Заполнить отказ стадии (правило C5) и назвать группу (решение Q4)."""
    result["status"] = "error"
    result["error"] = detail
    result["refusal"] = str(reason or "")
    result["failed_group"] = group
    result["failed_record"] = name
    return result


# ── стадия записи ───────────────────────────────────────────────────────────────────
def write_object_modules(cur, configuration_uuid: str, dump_root=None,
                        dump_dir=None, changed_at=None,
                        cache: Optional[Dict] = None) -> Dict[str, Any]:
    """Записать модули объектов конфигурации в `bsl_modules` (шаг П3 плана).

    Аргументы:
      `cur`                — курсор той самой второй транзакции (граница D7, Q6);
                             транзакцию открывает и завершает вызывающий (П4);
      `configuration_uuid` — uuid строки заголовка; по нему снимаются и пишутся строки;
      `dump_root`          — каталог со всеми выгрузками: каталог нужной выгрузки
                             ищется по uuid корня `Configuration.xml` (`resolve_dump_dir`);
      `dump_dir`           — известный вызывающему каталог ВЫГРУЗКИ этой конфигурации
                             (загрузчик знает `source_path`, искать по каталогу незачем).
                             Принимается только после сверки uuid корня с заголовком:
                             иначе код лёг бы не той конфигурации, и снять его вместе с
                             этой было бы нельзя;
      `changed_at`         — общий штамп времени загрузки: строки одной ревизии обязаны
                             нести одно время (`src/current_revision.py`);
      `cache`              — кэш разрешения каталогов вида (словарь П2).

    Возвращает словарь `result_defaults()`. `status = "error"` означает, что стадия
    отказала; вставленное писатель снимает сам (`abandon_written_rows`, её обязан позвать
    вызывающий), и в ответе называется `failed_group` (критерий 8 плана: сказать
    «загружено» без этой строки значило бы утверждать полную конфигурацию).
    """
    started = datetime.now()
    result = result_defaults()
    result["configuration_uuid"] = str(configuration_uuid or "")

    header = configuration_header(cur, configuration_uuid)
    if not header:
        return _failure(
            result, REFUSAL_DUMP_DIR_MISMATCH,
            f"Строка заголовка конфигурации с uuid {configuration_uuid} в базе не "
            "найдена. Сначала загрузите каталог точкой входа load_1c_catalog_tool"
            "(source_path=…): строки модулей без заголовка остались бы ни на что не "
            "указывающими, а внешний ключ в схеме не поставлен осознанно (V20.1).")
    result["configuration_name"] = header.get("name")

    if dump_dir:
        absolute = Path(str(dump_dir))
        if not absolute.is_dir():
            return _failure(result, REFUSAL_DUMP_DIR_MISMATCH,
                            f"Каталог выгрузки не найден: {absolute}")
        found = configuration_root_uuid(absolute)
        wanted = str(configuration_uuid or "").strip().lower()
        if found and found != wanted:
            return _failure(
                result, REFUSAL_DUMP_DIR_MISMATCH,
                f"Каталог выгрузки {absolute.name} относится к конфигурации с uuid "
                f"{found}, а строка заголовка — {wanted}. Код модулей лёг бы не той "
                "конфигурации, и снять его вместе с этой было бы нельзя.")
        result["dump_dir"] = str(absolute)

    result["removed_previous"] = remove_previous_rows(cur, configuration_uuid)

    pending = []
    seen_paths = set()
    seen_groups = set()
    groups_with_rows = set()
    moment = changed_at
    inserted = 0

    def flush():
        nonlocal pending, inserted, moment
        if not pending:
            return
        moment = stamp_revision_rows(pending, revision_no=FIRST_REVISION,
                                     changed_by=CHANGED_BY_LOAD, changed_at=moment)
        inserted += ConfigurationObjectModuleRowWriter.insert_many(cur, pending)
        pending = []
        # Число вставленных обновляется здесь, а не только в конце: при отказе
        # вызывающий обязан снять ровно то, что легло (`abandon_written_rows`), и
        # ответить «строк узла нет» честно.
        result["written"] = inserted

    for item in iter_module_rows(cur, configuration_uuid, dump_root, cache,
                                 dump_dir=dump_dir):
        name = str(item.get("name") or "")
        group = str(item.get("group") or "")
        if group:
            seen_groups.add(group)

        refusal = item.get("refusal")
        if refusal:
            # Отказ вывести путь или дефект данных — не «модуля нет»: запись индекса
            # круг узла подтверждает, а строки не будет. Оставить это молча — значит
            # назвать группу загруженной, не загрузив её (решение Q4).
            if refusal in result["defects"]:
                result["defects"][refusal] += 1
            else:
                result["refusals"][refusal] = result["refusals"].get(refusal, 0) + 1
            if len(result["samples"]) < MAX_EXAMPLES:
                result["samples"].append(f"{name}: {refusal}")
            return _failure(
                result, str(refusal),
                f"Не выведен путь модуля для записи индекса {name} (причина: "
                f"{refusal}). Группа {group or '—'} не загружена.",
                group=group, name=name)

        state = item.get("state")
        if item.get("bin_side"):
            # Открытая позиция O1: машинный код рядом с отсутствующим исходником.
            # Строки нет (узел таких модулей не знает), но и молчать о них нельзя.
            result["bin_side"] += 1
            if len(result["bin_side_examples"]) < MAX_EXAMPLES:
                result["bin_side_examples"].append(name)
        if state in (STATE_INDEXED_NO_FILE, STATE_EMPTY_FILE):
            # Модуль пуст — строки нет (решение Q2); состояние названо счётчиком.
            result["counts_by_state"][state] += 1
            continue

        # Состояние `file` от словаря — ещё не окончательное: его подтверждает чтение
        # (правило C5). Оставить счёт на словаре значило бы, что одна запись посчитана
        # дважды и сумма состояний не сходится с кругом узла.
        derived = item.get("derived") or {}
        read = read_module_code(derived.get("abs_path"))
        read_state = read.get("state")

        if read_state == STATE_EMPTY_FILE:
            # Файл оказался пуст после нормализации (одна BOM либо пробелы). Текста нет —
            # строки нет (Q2); число называется отдельно от нулевых файлов, посчитанных
            # словарём, чтобы разница состояний оставалась видимой.
            result["counts_by_state"][STATE_EMPTY_FILE] += 1
            result["empty_after_strip"] += 1
            continue
        if read_state == STATE_INDEXED_NO_FILE:
            # Файл исчез между проверкой существования и чтением. Это не «модуль пуст»:
            # запись индекса круг подтверждает, а строки нет — значит группа не закрыта.
            result["refusals"][REASON_FILE_DISAPPEARED] = (
                result["refusals"].get(REASON_FILE_DISAPPEARED, 0) + 1)
            return _failure(
                result, REASON_FILE_DISAPPEARED,
                f"Модуль {name} ({derived.get('rel_path')}) исчез между проверкой и "
                f"чтением. Группа {group or '—'} не загружена.",
                group=group, name=name)
        if read_state != STATE_FILE:
            result["counts_by_state"][STATE_UNDECODED] += 1
            detail = str(read.get("reason") or "файл модуля не прочитан")
            return _failure(
                result, detail,
                f"Модуль {name} ({derived.get('rel_path')}) не записан: {detail}. "
                f"Группа {group or '—'} не загружена.",
                group=group, name=name)
        result["counts_by_state"][STATE_FILE] += 1

        row = dict(item["row"])
        key = (row.get("parent_uuid"), row.get("file_path"))
        if key in seen_paths:
            result["defects"][DEFECT_DUPLICATE_PATH] += 1
            return _failure(
                result, DEFECT_DUPLICATE_PATH,
                f"Две записи индекса вывелись в один модуль: {name} → "
                f"{row.get('file_path')}. Ключ цепочки состояния "
                "(parent_uuid, file_path, revision_no) принял бы это за одну строку. "
                f"Группа {group or '—'} не загружена.",
                group=group, name=name)
        seen_paths.add(key)

        row["code"] = read["code"]
        row["code_size"] = read["code_size"]
        row["truncated"] = False
        pending.append(row)
        result["code_chars"] += int(read["code_size"] or 0)
        groups_with_rows.add(group)
        if len(pending) >= PAGE_SIZE:
            flush()

    flush()
    result["written"] = inserted
    result["groups"] = {"seen": len(seen_groups), "with_rows": len(groups_with_rows)}
    result["seconds"] = round((datetime.now() - started).total_seconds(), 3)
    return result


def abandon_written_rows(cur, configuration_uuid: str,
                        result: Dict[str, Any]) -> int:
    """Снять строки, которые писатель уже вставил, но стадию не закончил (Q4).

    Нужен не вместо отката транзакции (его делает вызывающий), а рядом с ним: отказанная
    стадия не оставляет половины группы, и состояние второй транзакции не зависит от
    решения вызывающего. После неё в таблице нет ни одной строки узла — ответ говорит
    «конфигурация неполная, группа X не загружена» честно при любом исходе транзакции.
    """
    if not result.get("written"):
        return 0
    removed = remove_previous_rows(cur, configuration_uuid)
    result["compensated_rows"] = removed
    result["written"] = 0
    result["code_chars"] = 0
    result["groups"] = {"seen": int(result["groups"].get("seen") or 0), "with_rows": 0}
    return removed


__all__ = (
    "ConfigurationObjectModuleRowWriter", "abandon_written_rows", "count_scope_rows",
    "read_module_code", "remove_previous_rows", "result_defaults", "scope_where",
    "write_object_modules",
)




