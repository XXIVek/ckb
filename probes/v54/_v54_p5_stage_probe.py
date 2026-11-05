# -*- coding: utf-8 -*-
"""_v54_p5_stage_probe.py — проба шага П5 узла V54: стадия S4i в конвейере и свой вход.

Чем П4 не проверяется. `_v54_p4_load_probe.py` вызывает слой `load_scheduled_jobs` напрямую,
поэтому он не видит трёх вещей: порядка стадий конвейера, печати раздела узла в карточке
`load_1c_catalog_tool` и существования отдельного входа группы в реестре сервера. Проверяются
четыре позиции:

  1. порядок `STAGES` держит позицию 2.9 между 2.8 и модулями объектов (порядок нормативного
     списка держит `STAGES`, а не номера стадий), и каждая стадия детей имеет зеркало в
     `STAGE_FULL_RELOAD_ONLY`, подсказку продолжения и название незакрытой группы — урок П8
     узлов V50–V53: отсутствие ключа маскируется значением по умолчанию в
     `build_stopped_stage`, и стадия с отдельным входом читается стадией без продолжения;
  2. конвейер `load_catalog(MinCfg, force=True)` выполняет стадию S4i, её ответ лежит в
     собственном ключе `scheduled_jobs` (правило C3), числа машинной части совпадают с
     ответом разбора, а карточка содержит раздел узла (карточка и инструмент описывают слой
     одним форматёром);
  3. отказ стадии останавливает конвейер через `stopped_stage`: подсказка продолжения
     называет `load_scheduled_jobs_tool`, а не полную перезагрузку (`full_reload_required`
     ложна), незакрытая группа называется позицией 2.9, а последующие стадии перечислены
     `not_run` (правило C2);
  4. отдельный вход `load_scheduled_jobs_tool` печатает тот же текст раздела, что и карточка
     (прецедент V45: два текста об одном слое разъезжаются при первой правке), и отказывает
     на нечитаемом каталоге, а не на пустом составе;
  5. строка карточки о покрытии содержимого `<ChildObjects>` называет вид `ScheduledJob`
     сохранённым, а не «остальным объектом», и перечисляет узлы/стадии/разделы до S4i
     включительно. До шага П5 круг дописывали по строке на узел в форматаре карточки, а
     текстовые перечни и предупреждение разбора никто не сверял: перечень остановился на
     V52/S4g, и карточка противоречила собственному разделу стадии (замер 03.11.2026:
     `ScheduledJob 2` стоял и в «остальных объектах … в БД не раскладываются», и в разделе
     S4i; предупреждение `ChildObjects/EventSubscription … не сохраняется` стояло рядом с
     разделом S4h). Круг с этого шага называет один словарь — `STORED_META_KINDS`.

MinCfg выбрана потому, что это эталон минимальной конфигурации узла V38: круг вида в ней
два файла и пять записей расписания (замер 1.1), и любое расхождение числа видно сразу.

Вызов:
    python _v54_p5_stage_probe.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "tools", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 — перекодировка вывода не является проверкой
    pass

from config_load_router import format_load_result, load_catalog  # noqa: E402
from configuration_load_contract import (  # noqa: E402
    SCHEDULED_JOBS_SECTION_HEADER,
    STAGE_CHILD_OBJECTS,
    STAGE_COMMON_ATTRIBUTES,
    STAGE_EVENT_SUBSCRIPTIONS,
    STAGE_EXCHANGE_PLANS,
    STAGE_FILTER_CRITERIA,
    STAGE_FULL_RELOAD_ONLY,
    STAGE_HEADER,
    STAGE_INCOMPLETE_GROUPS,
    STAGE_OBJECT_MODULES,
    STAGE_ROLES,
    STAGE_ROOT_MODULES,
    STAGE_SCHEDULED_JOBS,
    STAGE_SESSION_PARAMETERS,
    STAGES,
    build_stopped_stage,
    scheduled_jobs_defaults,
    stage_resume_hint,
    STATUS_ERROR,
)
from server_configurations_core import load_scheduled_jobs_tool  # noqa: E402

MINCFG = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files\MinCfg")

# Ключи стадий детей, которые обязан нести ответ конвейера (правило C3): отсутствие ключа
# означает, что стадия не отвечает, а нулевой ответ стадия даёт всегда.
STAGE_KEYS = (
    "root_modules", "child_objects", "session_parameters", "roles", "common_attributes",
    "exchange_plans", "filter_criteria", "event_subscriptions", "scheduled_jobs",
    "object_modules",
)
# Стадии, для которых держатся зеркала (снятие, подсказка, незакрытая группа): заголовок и
# разбор каталога снимаются вместе со строкой заголовка и отдельных входов не имеют, поэтому
# в словарях их нет осознанно — проверка читает тот же круг, что и словари.
CHILD_STAGES = (
    STAGE_ROOT_MODULES, STAGE_CHILD_OBJECTS, STAGE_SESSION_PARAMETERS, STAGE_ROLES,
    STAGE_COMMON_ATTRIBUTES, STAGE_EXCHANGE_PLANS, STAGE_FILTER_CRITERIA,
    STAGE_EVENT_SUBSCRIPTIONS, STAGE_SCHEDULED_JOBS, STAGE_OBJECT_MODULES,
)

FAILURES: List[str] = []


def check(name: str, got: object, want: object) -> None:
    if got != want:
        FAILURES.append(f"{name}: получено {got!r}, ожидалось {want!r}")
        print(f"  [FAIL] {name} = {got!r} (ожидалось {want!r})")
    else:
        print(f"  [ok]   {name} = {got!r}")


def check_stage_order() -> None:
    """Позиция стадии и зеркала контракта остановки (статическая часть пробы)."""
    print("порядок стадий и зеркала контракта:")
    ids = [stage for stage, _ in STAGES]
    check("стадия S4i входит в STAGES", STAGE_SCHEDULED_JOBS in ids, True)
    check("S4i идёт сразу за S4h (позиция 2.9 за 2.8)",
          ids.index(STAGE_SCHEDULED_JOBS) - ids.index(STAGE_EVENT_SUBSCRIPTIONS), 1)
    check("модули объектов остаются последней стадией (вторая транзакция)",
          ids[-1], STAGE_OBJECT_MODULES)
    check("разбор каталога и заголовок остаются первыми стадиями",
          ids[:2], [STAGES[0][0], STAGE_HEADER])
    check("словарь STAGE_FULL_RELOAD_ONLY не шире STAGES",
          len(set(STAGE_FULL_RELOAD_ONLY) - set(ids)), 0)
    for stage in CHILD_STAGES:
        check(f"зеркало STAGE_FULL_RELOAD_ONLY для {stage}",
              stage in STAGE_FULL_RELOAD_ONLY, True)
        check(f"название незакрытой группы для {stage}",
              stage in STAGE_INCOMPLETE_GROUPS, True)
        check(f"подсказка продолжения для {stage} названа",
              bool(stage_resume_hint(stage)), True)
    check("стадия S4i продолжения без точечного входа не требует",
          STAGE_FULL_RELOAD_ONLY[STAGE_SCHEDULED_JOBS], False)
    check("подсказка S4i называет отдельный вход группы",
          "load_scheduled_jobs_tool" in stage_resume_hint(STAGE_SCHEDULED_JOBS), True)
    print()


def check_pipeline() -> str:
    """Конвейер: стадия выполняется, ответ в своём ключе, раздел в карточке."""
    print("конвейер load_catalog(MinCfg, force=True):")
    result = load_catalog(str(MINCFG), force=True)
    check("итог загрузки успешен", bool(result.get("success")), True)
    check("стадий не останавливался", bool((result.get("stopped_stage") or {}).get("stage")),
          False)
    missing = [key for key in STAGE_KEYS if key not in result]
    check("ключей стадий в ответе не хватает", len(missing), 0)
    if missing:
        print(f"    отсутствующие ключи: {', '.join(missing)}")
    jobs = result.get("scheduled_jobs") or {}
    check("ответ стадии имеет собственный ключ (правило C3)", bool(jobs), True)
    check("стадия S4i успешна", bool(jobs.get("success")), True)
    check("файлов регистрации вида найдено", jobs.get("files_found"), 2)
    check("разобрано файлов", jobs.get("files_read"), 2)
    written = jobs.get("written_by_table") or {}
    check("строк scheduled_jobs записано", written.get("scheduled_jobs"), 2)
    check("записей scheduled_job_schedules записано",
          written.get("scheduled_job_schedules"), 5)
    check("расхождений ног круга нет",
          sum((jobs.get("counts_by_circle_discrepancy") or {}).values()), 0)
    check("расхождений ноги содержимого нет",
          sum((jobs.get("counts_by_content_discrepancy") or {}).values()), 0)
    text = format_load_result(result)
    check("карточка содержит раздел узла V54", SCHEDULED_JOBS_SECTION_HEADER in text, True)
    check("карточка называет числа записанных таблиц", "scheduled_job_schedules=5" in text,
          True)
    print()
    return text


def check_stop() -> None:
    """Отказ стадии: остановка конвейера и чем её продолжить."""
    print("остановка на отказе стадии S4i (контракт):")
    failure = scheduled_jobs_defaults()
    failure["status"] = STATUS_ERROR
    failure["error"] = "проба П5: круг не записан — один файл регистрации не разобран"
    stopped = build_stopped_stage(STAGE_SCHEDULED_JOBS, failure, "заголовок конфигурации id=1")
    check("остановка называет стадию S4i", stopped.get("stage"), STAGE_SCHEDULED_JOBS)
    check("причина отказа переслана без переформулировки", stopped.get("reason"),
          failure["error"])
    check("полная перезагрузка не требуется", stopped.get("full_reload_required"), False)
    check("чем продолжить — назван отдельный вход группы",
          "load_scheduled_jobs_tool" in (stopped.get("resume_with") or ""), True)
    check("незакрытая группа называется позицией 2.9",
          "2.9" in (stopped.get("incomplete_group") or ""), True)
    not_run = [item.get("stage") for item in (stopped.get("not_run_stages") or [])]
    check("после S4i не выполнялась только стадия модулей объектов", not_run,
          [STAGE_OBJECT_MODULES])
    print()


def check_coverage(pipeline_text: str) -> None:
    """Покрытие содержимого `<ChildObjects>`: один круг на строку карточки и на разбор.

    Дефект найден шагом П5 на MinCfg: карточка относила `ScheduledJob 2` к «остальных
    объектов … в БД не раскладываются», стоя рядом с разделом S4i, который записал две
    строки вида; та же формулировка отрицала сохранность подписок (V53), критериев отбора
    (V52), планов обмена (V51) и общих реквизитов (V50). Проверка держит обе стороны
    круга: перечень узлов/стадий/разделов строки и предупреждение разбора.
    """
    print("покрытие содержимого <ChildObjects> (дефект, закрытый шагом П5):")
    line = next((item for item in pipeline_text.splitlines()
                 if item.startswith("Состав из <ChildObjects>")), "")
    check("строка покрытия найдена", line != "", True)
    if line:
        covered, _, rest_part = line.partition("; остальных объектов")
        # Порядок перечней задаёт словарь круга: вид V46 идёт первым (его таблицы даёт
        # `LOADED_META_TABLES`), дальше — порядок нормативного списка 2.3…2.9.
        check("перечень узлов доведён до V54",
              "V46, V48, V49, V50, V51, V52, V53 и V54" in covered, True)
        check("перечень стадий доведён до S4i",
              "S4, S4c, S4d, S4e, S4f, S4g, S4h и S4i" in covered, True)
        check("раздел узла V54 назван среди разделов",
              SCHEDULED_JOBS_SECTION_HEADER in covered, True)
        check("ScheduledJob отнесён к сохранённым видам",
              "ScheduledJob 2" in covered, True)
        check("ScheduledJob убран из перечня нераскладываемых",
              "ScheduledJob" in rest_part, False)
    check("предупреждение разбора называет стадию S4i",
          ("ChildObjects/ScheduledJob: 2 — объекты перечислены индексом состава"
           in pipeline_text and "сохраняется стадией S4i" in pipeline_text), True)
    check("предупреждение узла V53 больше не отрицает сохранность",
          ("ChildObjects/EventSubscription: 2 — объекты перечислены индексом состава "
           "(configuration_objects, узел V33), но их содержимое в БД не сохраняется"
           in pipeline_text), False)
    print()


def check_tool(pipeline_text: str) -> None:
    """Отдельный вход группы: тот же текст раздела, что и карточка, и честный отказ."""
    print("отдельный вход load_scheduled_jobs_tool:")
    ok = load_scheduled_jobs_tool(str(MINCFG))
    check("успешный ответ начинается с исхода", ok.startswith("✅"), True)
    check("ответ называет раздел узла", SCHEDULED_JOBS_SECTION_HEADER in ok, True)
    # Тот же форматёр, что и у карточки: строка форматёра ищется в обоих текстах. Если тексты
    # разъедутся, проверка назовёт строку, а не промолчит (прецедент V45).
    shared = next((line.strip() for line in ok.splitlines()
                   if "Записано строк по таблицам:" in line), None)
    check("общая строка форматёра найдена", shared is not None, True)
    if shared:
        check("тот же текст печатает карточка load_1c_catalog_tool",
              shared in pipeline_text, True)
    bad = load_scheduled_jobs_tool(str(ROOT / "_нет_такого_каталога_"))
    check("нечитаемый каталог — отказ, а не пустой состав", bad.startswith("❌"), True)
    check("отказ не утверждает записанные строки", "Записано строк по таблицам:" in bad,
          False)
    print()


def main() -> int:
    check_stage_order()
    pipeline_text = check_pipeline()
    check_stop()
    check_coverage(pipeline_text)
    check_tool(pipeline_text)
    if FAILURES:
        print(f"ПРОВАЛЫ П5 ({len(FAILURES)}):")
        for text in FAILURES:
            print(f"  - {text}")
        return 1
    print("П5 ПРОЙДЕН: стадия, остановка и отдельный вход расхождений не дают")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


