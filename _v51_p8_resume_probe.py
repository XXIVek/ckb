#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба шага П8 узла V51 (вторая половина): продолжение после остановки — отдельным входом.

Норматив (план `docs/CONFIGURATION_EXCHANGE_PLANS_PLAN.md`, строка П8; подсказка
`EXCHANGE_PLAN_REPEAT_HINT` узла V51): остановка на стадии `s4f_exchange_plans` продолжается
ОТДЕЛЬНЫМ входом `load_exchange_plans_tool` без перезагрузки конфигурации. Слово «можно»
обязано быть проверенным: ниже вызывается тот же слой `load_exchange_plans`, который вызывает
MCP-инструмент (двух кодов, способных разойтись, в проекте нет — прецедент V45/V46), и
проверяются три факта:

  1 — конвейер останавливается на S4f (подмена функции стадии, как в
      `_v51_p8_stop_probe.py`): строки круга вида сняты, заголовок и индекс состава остались.
      После отказа S4f не вызываются ВСЕ последующие стадии — и S4g критериев отбора (узел V52,
      шаг П5: стадия внесена в `STAGES` сразу после `s4f_exchange_plans`), и
      S4b модулей объектов. Обе отсчитываются обёртками, которые зовут настоящую функцию и
      записывают число вызовов: «не вызывалась» доказывается нулём счётчика, а не отсутствием
      записи в словаре (тот же урок, что у `_v51_p8_stop_probe.py`).
  2 — одиночный вызов слоя по каталогу выгрузки восстанавливает круг; заголовок (id, uuid,
      имя, `created_at`) и индекс состава НЕ изменились — продолжение не требует полной
      перезагрузки конфигурации; снятые прежние строки названы числами `removed_by_table` и
      строкой формата «Снято прежних строк этой конфигурации», а не молчанием;
  3 — повторный вызов идемпотентен: те же числа по таблицам, снятое вторым вызовом равно
      записанному первым, витрина текущего состояния отдаёт по одной ревизии на строку вида,
      строки ЧУЖИХ конфигураций не тронуты.

Проба меняет память процесса (подмена функции стадии) и состояние БД той же записью, которую
делает обычный вызов инструмента. Код возврата 0 — расхождений нет.

Запуск (прогоны, меняющие общую БД, не параллелят — наблюдение П8 узла V50):

    python _v51_p8_resume_probe.py [MinCfg]
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import configuration_loader as CL  # noqa: E402  — подмена функции стадии читается им
from config_load_router import load_catalog  # noqa: E402
from configuration_exchange_plans_loader import (  # noqa: E402
    REMOVE_ORDER as CIRCLE_TABLES,
    count_circle_child_rows,
    load_exchange_plans,
)
from configuration_load_contract import (  # noqa: E402
    EXCHANGE_PLAN_REPEAT_HINT,
    STAGE_CHILD_OBJECTS,
    STAGE_COMMON_ATTRIBUTES,
    STAGE_EXCHANGE_PLANS,
    STAGE_FILTER_CRITERIA,
    STAGE_EVENT_SUBSCRIPTIONS,
    STAGE_SCHEDULED_JOBS,
    STAGE_BOTS,
    STAGE_FUNCTIONAL_OPTIONS,
    STAGE_FUNCTIONAL_OPTIONS_PARAMETERS,
    STAGE_OBJECT_MODULES,
    STAGE_ROLES,
    STAGE_ROOT_MODULES,
    STAGE_SESSION_PARAMETERS,
    STATUS_ERROR,
    STATUS_OK,
    child_objects_defaults,
    common_attributes_defaults,
    exchange_plans_defaults,
    filter_criteria_defaults,
    event_subscriptions_defaults,
    scheduled_jobs_defaults,
    bots_defaults,
    functional_options_defaults,
    functional_options_parameters_defaults,
    format_exchange_plans_lines,
    root_modules_defaults,
    roles_defaults,
    session_parameters_defaults,
)
from configuration_object_modules_loader import object_modules_defaults  # noqa: E402
from external_db import connect  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")

# Стадии, которые подменяются успешным нулевым ответом, чтобы конвейер дошёл ровно до S4f и
# остановился на ней: тот же приём, что в `_v51_p8_stop_probe.py` (подмена в модуле
# загрузчика, а не локальной копии). S4g и S4b НЕ подменяются заглушками: после отказа S4f
# они не вызываются, а проверка этого факта требует счётчика — поэтому на них ставится
# обёртка, которая зовёт настоящую функцию и помечает вызов в `calls`. S4g стоит между S4f
# и S4b с узла V52 (шаг П5), S4h внесён узлом V53, S4i — узлом V54, S4j — узлом V55, S4k — узлом V56, и пропуск одной только
# S4b ничего бы не доказал: отказ S4f обязан снять со вызовов весь хвост `STAGES`.
EARLIER_STAGES = (
    STAGE_ROOT_MODULES, STAGE_CHILD_OBJECTS, STAGE_SESSION_PARAMETERS, STAGE_ROLES,
    STAGE_COMMON_ATTRIBUTES,
)
LATER_STAGES = (STAGE_FILTER_CRITERIA, STAGE_EVENT_SUBSCRIPTIONS,
                STAGE_SCHEDULED_JOBS, STAGE_BOTS, STAGE_FUNCTIONAL_OPTIONS,
                STAGE_FUNCTIONAL_OPTIONS_PARAMETERS,
                STAGE_OBJECT_MODULES)
STAGE_FUNCTIONS = {
    STAGE_ROOT_MODULES: "load_root_modules",
    STAGE_CHILD_OBJECTS: "load_object_properties",
    STAGE_SESSION_PARAMETERS: "load_session_parameters",
    STAGE_ROLES: "load_roles",
    STAGE_COMMON_ATTRIBUTES: "load_common_attributes",
    STAGE_EXCHANGE_PLANS: "load_exchange_plans",
    STAGE_FILTER_CRITERIA: "load_filter_criteria",
    STAGE_EVENT_SUBSCRIPTIONS: "load_event_subscriptions",
    STAGE_SCHEDULED_JOBS: "load_scheduled_jobs",
    STAGE_BOTS: "load_bots",
    STAGE_FUNCTIONAL_OPTIONS: "load_functional_options",
    STAGE_FUNCTIONAL_OPTIONS_PARAMETERS: "load_functional_options_parameters",
    STAGE_OBJECT_MODULES: "load_object_modules",
}
DEFAULTS = {
    STAGE_ROOT_MODULES: root_modules_defaults,
    STAGE_CHILD_OBJECTS: child_objects_defaults,
    STAGE_SESSION_PARAMETERS: session_parameters_defaults,
    STAGE_ROLES: roles_defaults,
    STAGE_COMMON_ATTRIBUTES: common_attributes_defaults,
    STAGE_EXCHANGE_PLANS: exchange_plans_defaults,
    STAGE_FILTER_CRITERIA: filter_criteria_defaults,
    STAGE_EVENT_SUBSCRIPTIONS: event_subscriptions_defaults,
    STAGE_SCHEDULED_JOBS: scheduled_jobs_defaults,
    STAGE_BOTS: bots_defaults,
    STAGE_FUNCTIONAL_OPTIONS: functional_options_defaults,
    STAGE_FUNCTIONAL_OPTIONS_PARAMETERS: functional_options_parameters_defaults,
    STAGE_OBJECT_MODULES: object_modules_defaults,
}

PASSED = 0
FAILED = 0
NOTES = []


def check(name, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("  [OK]   " + name + (((" — " + str(detail)) if detail else "")))
    else:
        FAILED += 1
        print("  [FAIL] " + name + (((" — " + str(detail)) if detail else "")))


def note(text):
    NOTES.append(text)
    print("  [NOTE] " + text)


def one(cur, sql, params=None):
    cur.execute(sql, params or ())
    row = cur.fetchone()
    return row[0] if row else None


def circle_counts(cur, cfg_uuid):
    """Строки круга вида этой конфигурации по восьми таблицам.

    Общий круг детей считается загрузчиком (`count_circle_child_rows`) — тем же предикатом,
    что и снятие. Подсчёт по одной ноге `configuration_uuid` читал бы строки детей других
    видов (критерии отбора узла V52 пишут `forms`, `form_ext`, `commands`) как круг стадии
    S4f: наблюдение П8 прогона `_v51_p8_stop_probe.py`, повторённое здесь на проверке 2.3.
    """
    return {table: count_circle_child_rows(cur, cfg_uuid, table)
            for table in CIRCLE_TABLES}


def other_circle_counts(cur, cfg_uuid):
    """Дети ЧУЖИХ конфигураций — неприкосновенность чужого круга (тот же круг родителей)."""
    return {table: count_circle_child_rows(cur, cfg_uuid, table, other_configurations=True)
            for table in CIRCLE_TABLES}


def header_snapshot(cur, cfg_uuid):
    """Снимок строки заголовка: что не имеет права изменить ОДИНОЧНЫЙ вход слоя.

    Ноги, по которым строка конфигурации является той же самой: числовой `id`, `uuid`, `name`,
    `created_at`. Наблюдение П8: конвейер при `force=True` строку заголовка НЕ обновляет —
    он снимает прежнюю и вставляет новую с тем же uuid, поэтому числовой `id` и `created_at`
    меняются на каждой перезагрузке (провенанс строк конфигурации в БД не ведётся —
    решение D-C). Отсечкой для проверок 3.3 и 4.8 служит снимок ПОСЛЕ раздела 2: одиночный
    вход слоя не имеет права трогать строку заголовка вовсе.
    """
    cur.execute("SELECT id, uuid, name, created_at FROM configurations "
                "WHERE uuid = %s::uuid ORDER BY id", [str(cfg_uuid)])
    return [tuple(str(part) for part in row) for row in cur.fetchall()]


def header_identity(cur, cfg_uuid):
    """Тот же ли это объект конфигурации: `uuid` и `name` (ноги, общие для двух строк)."""
    cur.execute("SELECT uuid, name FROM configurations WHERE uuid = %s::uuid ORDER BY id",
                [str(cfg_uuid)])
    return [tuple(str(part) for part in row) for row in cur.fetchall()]


def index_count(cur, cfg_id):
    return int(one(cur, f"SELECT count(*) FROM {CL.OBJECTS_TABLE} "
                        "WHERE configuration_id = %s", [cfg_id]) or 0)


def by_table(answer, key):
    """Числа по таблицам круга приведены к одному перечню: пропущенная таблица читается нулём.

    Ответ называет снятые и записанные строки по таблицам (C1), но перечень нулей в нём не
    обязан быть: сравнение «снято равно записанному» на словарях разной полноты дало бы
    расхождение там, где его нет. Поэтому сравнение идёт по кругу `REMOVE_ORDER` — тем же
    перечню, по которому писатель снимает строки.
    """
    raw = answer.get(key) or {}
    unknown = sorted(set(raw) - set(CIRCLE_TABLES))
    if unknown:
        note(f"ответ называет таблицы вне круга снятия: {unknown}")
    return {table: int(raw.get(table) or 0) for table in CIRCLE_TABLES}


def stop_at_s4f(dump_dir, reason):
    """Один прогон конвейера с отказом S4f: предыдущие стадии — пустой успех, S4f — отказ.

    S4g и S4b не подменяются ответами: после отказа S4f конвейер обязан их не звать, и это
    проверяется счётчиком вызовов (`calls`), а не совпадением со статусом `not_run`. Обёртки
    later-стадий зовут настоящую функцию и лишь помечают вызов — подмена ответа скрыла бы
    реальный прогон (или реальный пропуск) стадий хвоста.
    """
    calls = {}
    originals = {}
    for stage in EARLIER_STAGES:
        originals[stage] = getattr(CL, STAGE_FUNCTIONS[stage])

        def _ok(*args, _stage=stage, **kwargs):
            calls[_stage] = calls.get(_stage, 0) + 1
            answer = DEFAULTS[_stage]()
            answer["success"] = True
            if "status" in answer:
                answer["status"] = STATUS_OK
            return answer
        setattr(CL, STAGE_FUNCTIONS[stage], _ok)
    originals[STAGE_EXCHANGE_PLANS] = getattr(CL, STAGE_FUNCTIONS[STAGE_EXCHANGE_PLANS])

    def _broken(*args, **kwargs):
        calls[STAGE_EXCHANGE_PLANS] = calls.get(STAGE_EXCHANGE_PLANS, 0) + 1
        answer = exchange_plans_defaults()
        answer["success"] = False
        answer["status"] = STATUS_ERROR
        answer["error"] = reason
        answer["reason"] = reason
        return answer
    setattr(CL, STAGE_FUNCTIONS[STAGE_EXCHANGE_PLANS], _broken)
    for stage in LATER_STAGES:
        originals[stage] = getattr(CL, STAGE_FUNCTIONS[stage])

        def _counted(*args, _stage=stage, _fn=originals[stage], **kwargs):
            calls[_stage] = calls.get(_stage, 0) + 1
            return _fn(*args, **kwargs)
        setattr(CL, STAGE_FUNCTIONS[stage], _counted)
    try:
        return load_catalog(str(dump_dir), force=True), calls
    finally:
        for stage, fn in originals.items():
            setattr(CL, STAGE_FUNCTIONS[stage], fn)


def main() -> int:
    chosen = next((arg for arg in sys.argv[1:] if arg in DUMPS), "MinCfg")
    dump_dir = DUMP_ROOT / chosen
    if not dump_dir.is_dir():
        print(f"Каталог выгрузки не найден: {dump_dir}")
        return 2

    print(f"\n=== 1. Базовая загрузка каталога ({chosen}, force=True) ===")
    base = load_catalog(str(dump_dir), force=True)
    check("1.1 базовая загрузка успешна", base.get("success") is True, base.get("error"))
    base_stage = base.get("exchange_plans") or {}
    conn = connect()
    try:
        cur = conn.cursor()
        cfg_uuid = base.get("uuid")
        cfg_id = one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                     [str(cfg_uuid)])
        baseline = circle_counts(cur, cfg_uuid)
        other_baseline = other_circle_counts(cur, cfg_uuid)
        header_before = header_snapshot(cur, cfg_uuid)
        identity_before = header_identity(cur, cfg_uuid)
        index_before = index_count(cur, cfg_id)
        check("1.3 базовая загрузка даёт ровно одну строку заголовка по uuid и индекс "
              "состава (иначе продолжение не с чем сверять)",
              len(header_before) == 1 and index_before > 0,
              f"строк заголовка {len(header_before)}, индекс {index_before}")
        if chosen == "KomMag":
            check("1.2 круг пуст (выгрузка без планов обмена) — продолжение проверять нечем",
                  baseline["exchange_plans"] == 0, baseline)
        else:
            check("1.2 базовый круг непустой, иначе восстанавливать нечего",
                  baseline["exchange_plans"] > 0, baseline)
        note(f"базовый круг: {baseline}; чужие круги: {other_baseline}")

        print(f"\n=== 2. Остановка конвейера на S4f ({chosen}) ===")
        reason = f"искусственный отказ стадии {STAGE_EXCHANGE_PLANS} (проба П8)"
        stopped_result, calls = stop_at_s4f(dump_dir, reason)
        stopped = stopped_result.get("stopped_stage") or {}
        check("2.1 конвейер остановлен именно на S4f и подсказывает отдельный вход",
              stopped.get("stage") == STAGE_EXCHANGE_PLANS
              and "load_exchange_plans_tool" in str(stopped.get("resume_with")),
              str(stopped.get("resume_with"))[:80])
        check("2.1а текст подсказки — общий с текстом стадии (одна формулировка продолжения "
              "на карточку и на ответ отдельного входа, прецедент V45)",
              EXCHANGE_PLAN_REPEAT_HINT in str(stopped.get("resume_with")),
              EXCHANGE_PLAN_REPEAT_HINT[:70])
        check("2.2 хвост `STAGES` после отказа S4f не вызывался — ни S4g критериев отбора "
              "(узел V52), ни S4h подписок на события (узел V53), ни S4i регламентных "
              "заданий (узел V54), ни S4j ботов (узел V55), ни S4b модулей объектов",
              all(calls.get(stage) in (None, 0) for stage in LATER_STAGES),
              {stage: calls.get(stage, 0) for stage in LATER_STAGES})
        after_stop = circle_counts(cur, cfg_uuid)
        check("2.3 круг вида снят и не заполнен — остановка не откат (Q8 п. 2)",
              all(value == 0 for value in after_stop.values()), after_stop)
        header_after_stop = header_snapshot(cur, cfg_uuid)
        cfg_id_stop = one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                          [str(cfg_uuid)])
        check("2.4 заголовок на месте (одна строка по тому же uuid, то же имя) и индекс "
              "состава не изменился — остановка не откат",
              len(header_after_stop) == 1
              and header_identity(cur, cfg_uuid) == identity_before
              and index_count(cur, cfg_id_stop) == index_before,
              f"строк заголовка {len(header_after_stop)}, индекс "
              f"{index_count(cur, cfg_id_stop)} из {index_before}")
        note(f"наблюдение П8: конвейер при `force=True` строку заголовка заменяет — "
             f"uuid и имя те же ({identity_before[0][1]}), числовой `id` был "
             f"{header_before[0][0]}, стал {header_after_stop[0][0]}. Продолжение "
             "отдельным входом привязано к uuid, а не к числовому id, и править заголовок "
             "оно не имеет права — сравнение идёт со снимком после остановки.")
        cfg_id = cfg_id_stop or cfg_id

        print("\n=== 3. Продолжение отдельным входом без перезагрузки конфигурации ===")
        first = load_exchange_plans(str(dump_dir), configuration_uuid=str(cfg_uuid))
        check("3.1 ответ отдельного входа успешен и называет свой статус (не `not_run`)",
              first.get("success") is True and first.get("status") not in (None,
                                                                          STATUS_ERROR),
              first.get("error"))
        restored = circle_counts(cur, cfg_uuid)
        if chosen == "KomMag":
            check("3.2 пустой круг остаётся состоянием `directory_missing`, а не отказом",
                  all(value == 0 for value in restored.values())
                  and "directory_missing" in str(first.get("observations")),
                  str(first.get("observations"))[:120])
        else:
            check("3.2 круг восстановлен ровно базовыми числами",
                  restored == baseline,
                  {table: (baseline[table], restored[table]) for table in CIRCLE_TABLES
                   if restored[table] != baseline[table]})
        cfg_id_now = one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                         [str(cfg_uuid)])
        check("3.3 строка заголовка НЕ тронута продолжением — перезагрузка конфигурации для "
              "него не требуется (тот же `id`, `uuid`, `name`, `created_at`; строка "
              "заголовка по-прежнему одна)",
              header_snapshot(cur, cfg_uuid) == header_after_stop,
              f"после остановки {header_after_stop[0][0]}, стало "
              f"{header_snapshot(cur, cfg_uuid)[0][0]}")
        check("3.4 индекс состава не изменился и не перечитывался",
              index_count(cur, cfg_id_now) == index_before,
              f"{index_count(cur, cfg_id_now)} из {index_before}")
        check("3.5 снятых строк нет — остановка уже сняла круг, и ответ называет это нулём "
              "по каждой таблице круга, а не молчанием (C2)",
              int(first.get("removed_previous") or 0) == 0
              and all(value == 0 for value in by_table(first, "removed_by_table").values()),
              first.get("removed_previous"))
        first_card = "\n".join(format_exchange_plans_lines(first, indent="   "))
        check("3.6 текст ответа отдельного входа называет записанные строки, каталог вида и "
              "границу круга",
              "Записано строк по таблицам" in first_card
              and "Файлов регистрации вида:" in first_card
              and "тела модулей вида узел НЕ читает" in first_card,
              f"{len(first_card.splitlines())} строк")
        stage_numbers = ("files_read", "files_found", "content_total", "rows_written")
        check("3.7 отдельный вход даёт тот же состав, что стадия конвейера: числа разбора "
              "совпадают с базовой загрузкой",
              {key: first.get(key) for key in stage_numbers}
              == {key: base_stage.get(key) for key in stage_numbers},
              {key: (base_stage.get(key), first.get(key)) for key in stage_numbers})

        print("\n=== 4. Повторный вызов: идемпотентность и названные снятые строки ===")
        second = load_exchange_plans(str(dump_dir), configuration_uuid=str(cfg_uuid))
        check("4.1 повтор успешен", second.get("success") is True, second.get("error"))
        again = circle_counts(cur, cfg_uuid)
        check("4.2 состав в базе тот же, что после первого вызова", again == restored,
              {table: (restored[table], again[table]) for table in CIRCLE_TABLES
               if again[table] != restored[table]})
        written_first = by_table(first, "written_by_table")
        removed_second = by_table(second, "removed_by_table")
        other_after = other_circle_counts(cur, cfg_uuid)
        if chosen == "KomMag":
            check("4.3 пустой круг повторяется как состояние, а не как отказ (Q9)",
                  "directory_missing" in str(second.get("observations")),
                  str(second.get("observations"))[:120])
        else:
            check("4.3 снятое повтором равно записанному первым: идемпотентность держится "
                  "явным `DELETE` круга, а не каскадом (прецедент V20.1)",
                  removed_second == written_first,
                  {"снято": removed_second, "записано первым": written_first})
            check("4.4 записанное повтором совпадает с записанным первым по таблицам",
                  by_table(second, "written_by_table") == written_first,
                  {"первый": written_first, "второй": by_table(second, "written_by_table")})
            current = int(one(
                cur, "SELECT count(*) FROM v_current_exchange_plans "
                     "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) or 0)
            duplicates = int(one(
                cur, "SELECT count(*) FROM (SELECT object_name "
                     "FROM v_current_exchange_plans WHERE configuration_uuid = %s::uuid "
                     "GROUP BY object_name HAVING count(*) > 1) t",
                [str(cfg_uuid)]) or 0)
            check("4.5 витрина текущего состояния: по одной ревизии на строку вида, дублей "
                  "нет (после двух записей круга)",
                  current == baseline["exchange_plans"] and duplicates == 0,
                  f"текущих {current} из {baseline['exchange_plans']}, дублей {duplicates}")
        second_card = "\n".join(format_exchange_plans_lines(second, indent="   "))
        check("4.6 ответ повтора называет снятые прежние строки строкой формата — ровно "
              "когда снятие было",
              ("Снято прежних строк этой конфигурации" in second_card)
              == (sum(removed_second.values()) > 0),
              f"снято {sum(removed_second.values())}")
        check("4.7 строки ЧУЖИХ конфигураций не изменились за оба вызова",
              other_after == other_baseline,
              {table: (other_baseline[table], other_after[table])
               for table in CIRCLE_TABLES if other_after[table] != other_baseline[table]})
        check("4.8 строка заголовка и индекс состава за оба вызова не менялись",
              header_snapshot(cur, cfg_uuid) == header_after_stop
              and index_count(cur, cfg_id_now) == index_before,
              header_snapshot(cur, cfg_uuid)[0][0])
        note(f"{chosen}: подсказка остановки продолжена отдельным входом без полной "
             f"перезагрузки; повтор идемпотентен (снято {sum(removed_second.values())}, "
             f"записано {sum(written_first.values())})")

        print("\n=== 5. Восстановление: проба не оставляет общую БД неполной ===")
        # Разделы 2–4 оставляют выгрузку в состоянии «круг вида есть, остальных стадий
        # нет»: заглушки S4a…S4e ничего не пишут. Оставлять так общую БД нельзя —
        # контуры прежних узлов (`check_v48`, `check_v49`) читают строки своих стадий
        # и называют отсутствующие строки провалом: проба, которая правит общую базу,
        # обязана вернуть её в эталонное состояние тем же полным прогоном, которым
        # начинала (прецедент раздела 3 пробы `_v51_p8_stop_probe.py`).
        full = load_catalog(str(dump_dir), force=True)
        check("5.1 завершающая полная загрузка успешна",
              full.get("success") is True, full.get("error"))
        final = circle_counts(cur, cfg_uuid)
        check("5.2 круг вида восстановлен базовыми числами базовой загрузки",
              final == baseline,
              {table: (baseline[table], final[table]) for table in CIRCLE_TABLES
               if final[table] != baseline[table]})
        check("5.3 строки ЧУЖИХ конфигураций не изменились за все разделы пробы",
              other_circle_counts(cur, cfg_uuid) == other_baseline,
              {table: (other_baseline[table], other_circle_counts(cur, cfg_uuid)[table])
               for table in CIRCLE_TABLES
               if other_circle_counts(cur, cfg_uuid)[table] != other_baseline[table]})
        cfg_id_final = one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                           [str(cfg_uuid)])
        check("5.4 индекс состава после полного прогона тот же",
              index_count(cur, cfg_id_final) == index_before,
              f"{index_count(cur, cfg_id_final)} из {index_before}")
        check("5.5 заголовок по-прежнему один и тот же по uuid и имени",
              header_identity(cur, cfg_uuid) == identity_before,
              str(header_identity(cur, cfg_uuid))[:120])
    finally:
        conn.close()

    print(f"\nИТОГ: пройдено {PASSED}, расхождений {FAILED}")
    for text in NOTES:
        print("  · " + text)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
