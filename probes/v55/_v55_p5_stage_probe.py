# -*- coding: utf-8 -*-
"""_v55_p5_stage_probe.py — проба шага П5 узла V55: стадия S4j в конвейере и свой вход.

Чем П4 не проверяется. `_v55_p4_load_probe.py` вызывает слой `load_bots` напрямую, поэтому он
не видит трёх вещей: порядка стадий конвейера, печати раздела узла в карточке
`load_1c_catalog_tool` и существования отдельного входа группы в реестре сервера. Проверяются
пять позиций:

  1. порядок `STAGES` держит позицию 2.10 между 2.9 и модулями объектов (порядок нормативного
     списка держит `STAGES`, а не номера стадий), и каждая стадия детей имеет зеркало в
     `STAGE_FULL_RELOAD_ONLY`, подсказку продолжения и название незакрытой группы — урок П8
     узлов V50–V54: отсутствие ключа маскируется значением по умолчанию в
     `build_stopped_stage`, и стадия с отдельным входом читается стадией без продолжения;
  2. конвейер `load_catalog(MinCfg, force=True)` выполняет стадию S4j, её ответ лежит в
     собственном ключе `bots` (правило C3), числа машинной части совпадают с ответом разбора
     (2 файла регистрации, 2 строки таблицы, ссылка `exact` + `std_picture`, модуль
     `file_and_index`), а карточка содержит раздел узла (карточка и инструмент описывают слой
     одним форматёром);
  3. отказ стадии останавливает конвейер через `stopped_stage`: подсказка продолжения
     называет `load_bots_tool`, а не полную перезагрузку (`full_reload_required` ложна),
     незакрытая группа называется позицией 2.10, а последующие стадии перечислены `not_run`
     (правило C2);
  4. отдельный вход `load_bots_tool` печатает тот же текст раздела, что и карточка
     (прецедент V45: два текста об одном слое разъезжаются при первой правке), и отказывает
     на нечитаемом каталоге, а не на пустом составе;
  5. строка карточки о покрытии содержимого `<ChildObjects>` называет вид `Bot` сохранённым, а
     не «остальным объектом», и перечисляет узлы/стадии/разделы до S4j включительно. До шага
     П5 круг дописывали по строке на узел в форматаре карточки, а текстовые перечни и
     предупреждение разбора никто не сверял: перечень останавливался на прежнем узле, и
     карточка противоречила собственному разделу стадии (замер 03.11.2026 — `ScheduledJob 2`
     стоял и в «остальных объектах … в БД не раскладываются», и в разделе S4i). Круг с узла
     V54 называет один словарь — `STORED_META_KINDS`; проба проверяет, что запись вида 2.10 в
     нём есть, а не что её добавили в одно место.

MinCfg выбрана потому, что это эталон минимальной конфигурации узла V38 и единственная из
четырёх выгрузок с видом `Bots/`: два файла регистрации и два файла модулей (замер 1.1/1.2),
поэтому любое расхождение числа видно сразу.

Вызов:
    python _v55_p5_stage_probe.py
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
    BOTS_CIRCLE_BOUNDARY,
    BOTS_SECTION_HEADER,
    STAGE_BOTS,
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
    bots_defaults,
    stage_resume_hint,
    STATUS_ERROR,
)
from server_configurations_core import load_bots_tool  # noqa: E402

MINCFG = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files\MinCfg")

# Ключи стадий детей, которые обязан нести ответ конвейера (правило C3): отсутствие ключа
# означает, что стадия не отвечает, а нулевой ответ стадия даёт всегда.
STAGE_KEYS = (
    "root_modules", "child_objects", "session_parameters", "roles", "common_attributes",
    "exchange_plans", "filter_criteria", "event_subscriptions", "scheduled_jobs", "bots",
    "object_modules",
)
# Стадии, для которых держатся зеркала (снятие, подсказка, незакрытая группа): заголовок и
# разбор каталога снимаются вместе со строкой заголовка и отдельных входов не имеют, поэтому
# в словарях их нет осознанно — проверка читает тот же круг, что и словари.
CHILD_STAGES = (
    STAGE_ROOT_MODULES, STAGE_CHILD_OBJECTS, STAGE_SESSION_PARAMETERS, STAGE_ROLES,
    STAGE_COMMON_ATTRIBUTES, STAGE_EXCHANGE_PLANS, STAGE_FILTER_CRITERIA,
    STAGE_EVENT_SUBSCRIPTIONS, STAGE_SCHEDULED_JOBS, STAGE_BOTS, STAGE_OBJECT_MODULES,
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
    check("стадия S4j входит в STAGES", STAGE_BOTS in ids, True)
    check("S4j идёт сразу за S4i (позиция 2.10 за 2.9)",
          ids.index(STAGE_BOTS) - ids.index(STAGE_SCHEDULED_JOBS), 1)
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
    check("стадия S4j продолжения без точечного входа не требует",
          STAGE_FULL_RELOAD_ONLY[STAGE_BOTS], False)
    check("подсказка S4j называет отдельный вход группы",
          "load_bots_tool" in stage_resume_hint(STAGE_BOTS), True)
    check("незакрытая группа S4j называется позицией 2.10",
          "2.10" in (STAGE_INCOMPLETE_GROUPS.get(STAGE_BOTS) or ""), True)
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
    bots = result.get("bots") or {}
    check("ответ стадии имеет собственный ключ (правило C3)", bool(bots), True)
    check("стадия S4j успешна", bool(bots.get("success")), True)
    check("файлов регистрации вида найдено", bots.get("files_found"), 2)
    check("разобрано файлов", bots.get("files_read"), 2)
    check("записей индекса состава вида (Bot.<Имя>)", bots.get("index_kind_records"), 2)
    check("записей индекса состава модулей (Bot.<Имя>.Module)",
          bots.get("index_child_records"), 2)
    written = bots.get("written_by_table") or {}
    check("строк bots записано", written.get("bots"), 2)
    check("строк записано всего", bots.get("rows_written"), 2)
    check("расхождений ног круга нет",
          sum((bots.get("counts_by_circle_discrepancy") or {}).values()), 0)
    # Разрешение ссылки не равно её наличию: блок `Picture` есть в 2/2 файлов, разрешена
    # индексом одна (на `CommonPicture.ОбщаяКартинка1`), вторая указывает на
    # `StdPicture.GroupConversation` — стандартное средство платформы (замер 2.1).
    pictures = bots.get("counts_by_picture_state") or {}
    check("ссылок разрешено индексом", pictures.get("exact"), 1)
    check("ссылок на стандартное средство платформы", pictures.get("std_picture"), 1)
    check("ссылок не разрешено (unresolved)", pictures.get("unresolved"), 0)
    check("состояний `pending` у ссылки нет (индекс доступен)",
          pictures.get("pending") or bots.get("picture_pending"), 0)
    check("блоков Picture всего", bots.get("picture_total"), 2)
    check("разрешено индексом всего", bots.get("picture_resolved"), 1)
    modules = bots.get("counts_by_module_state") or {}
    check("модулей file_and_index", modules.get("file_and_index"), 2)
    check("модулей file_only/index_only/absent",
          (modules.get("file_only") or 0) + (modules.get("index_only") or 0)
          + (modules.get("absent") or 0), 0)
    check("свойств разобрано без незнакомых тегов",
          (bots.get("counts_by_properties_state") or {}).get("all_known"), 2)
    check("наблюдений кроме перечисленных нет",
          sorted(bots.get("observations") or []), [])
    check("наблюдение directory_missing не выставлено (каталог есть)",
          (bots.get("counts_by_observation") or {}).get("directory_missing"), 0)
    text = format_load_result(result)
    check("карточка содержит раздел узла V55", BOTS_SECTION_HEADER in text, True)
    check("карточка называет числа записанных таблиц", "bots=2" in text, True)
    check("карточка называет границу круга тем же текстом, что и форматёр",
          BOTS_CIRCLE_BOUNDARY in text, True)
    print()
    return text


def check_stop() -> None:
    """Отказ стадии: остановка конвейера и чем её продолжить."""
    print("остановка на отказе стадии S4j (контракт):")
    failure = bots_defaults()
    failure["status"] = STATUS_ERROR
    failure["error"] = "проба П5: круг не записан — один файл регистрации не разобран"
    stopped = build_stopped_stage(STAGE_BOTS, failure, "заголовок конфигурации id=1")
    check("остановка называет стадию S4j", stopped.get("stage"), STAGE_BOTS)
    check("причина отказа переслана без переформулировки", stopped.get("reason"),
          failure["error"])
    check("полная перезагрузка не требуется", stopped.get("full_reload_required"), False)
    check("чем продолжить — назван отдельный вход группы",
          "load_bots_tool" in (stopped.get("resume_with") or ""), True)
    check("незакрытая группа называется позицией 2.10",
          "2.10" in (stopped.get("incomplete_group") or ""), True)
    not_run = [item.get("stage") for item in (stopped.get("not_run_stages") or [])]
    check("после S4j не выполнялась только стадия модулей объектов", not_run,
          [STAGE_OBJECT_MODULES])
    print()


def check_coverage(pipeline_text: str) -> None:
    """Покрытие содержимого <ChildObjects>: вид 2.10 назван сохранённым (дефект П5)."""
    print("покрытие содержимого <ChildObjects> (дефект, закрытый шагом П5):")
    line = next((item for item in pipeline_text.splitlines()
                 if item.startswith("Состав из <ChildObjects>")), "")
    check("строка покрытия найдена", line != "", True)
    if line:
        covered, _, rest_part = line.partition("; остальных объектов")
        # Порядок перечней задаёт словарь круга: вид V46 идёт первым (его таблицы даёт
        # `LOADED_META_TABLES`), дальше — порядок нормативного списка 2.3…2.10.
        check("перечень узлов доведён до V55",
              "V46, V48, V49, V50, V51, V52, V53, V54 и V55" in covered, True)
        check("перечень стадий доведён до S4j",
              "S4, S4c, S4d, S4e, S4f, S4g, S4h, S4i и S4j" in covered, True)
        check("раздел узла V55 назван среди разделов", BOTS_SECTION_HEADER in covered, True)
        check("Bot отнесён к сохранённым видам", "Bot 2" in covered, True)
        check("Bot убран из перечня нераскладываемых", "Bot" in rest_part, False)
    check("предупреждение разбора называет стадию S4j",
          ("ChildObjects/Bot: 2 — объекты перечислены индексом состава"
           in pipeline_text and "сохраняется стадией S4j" in pipeline_text), True)
    check("прежнее предупреждение не отрицает сохранность ботов",
          ("ChildObjects/Bot: 2 — объекты перечислены индексом состава "
           "(configuration_objects, узел V33), но их содержимое в БД не сохраняется"
           in pipeline_text), False)
    print()


def check_tool(pipeline_text: str) -> None:
    """Отдельный вход группы: тот же текст раздела, что и карточка, и честный отказ."""
    print("отдельный вход load_bots_tool:")
    ok = load_bots_tool(str(MINCFG))
    check("успешный ответ начинается с исхода", ok.startswith("✅"), True)
    check("ответ называет раздел узла", BOTS_SECTION_HEADER in ok, True)
    # Тот же форматёр, что и у карточки: строка форматёра ищется в обоих текстах. Если тексты
    # разъедутся, проверка назовёт строку, а не промолчит (прецедент V45).
    shared = next((line.strip() for line in ok.splitlines()
                   if "Записано строк по таблицам:" in line), None)
    check("общая строка форматёра найдена", shared is not None, True)
    if shared:
        check("тот же текст печатает карточка load_1c_catalog_tool",
              shared in pipeline_text, True)
    detail = next((line.strip() for line in ok.splitlines()
                   if line.strip().startswith("Ссылка `Picture`: состояний")), None)
    check("ответ называет состояния ссылки отдельным блоком", detail is not None, True)
    if detail:
        check("в блоке ссылки различимы `exact` и `std_picture`",
              "exact=1" in detail and "std_picture=1" in detail, True)
    module_line = next((line.strip() for line in ok.splitlines()
                        if line.strip().startswith("Модуль вида: состояний")), None)
    check("ответ называет состояние модуля, а не его текст", module_line is not None, True)
    if module_line:
        check("модуль назван file_and_index", "file_and_index=2" in module_line, True)
    check("ответ называет границу круга", BOTS_CIRCLE_BOUNDARY in ok, True)
    bad = load_bots_tool(str(ROOT / "_нет_такого_каталога_"))
    check("нечитаемый каталог — отказ, а не пустой состав", bad.startswith("❌"), True)
    check("отказ не утверждает записанные строки", "Записано строк по таблицам:" in bad,
          False)
    check("отказ называет, чем продолжить", "load_bots_tool" in bad, True)
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
    sys.exit(main())
