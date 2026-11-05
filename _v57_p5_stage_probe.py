# -*- coding: utf-8 -*-
"""_v57_p5_stage_probe.py — проба шага П5 узла V57: стадия S4l в конвейере и свой вход.

Чем П4 не проверяется. `_v57_p4_writer_probe.py` вызывает слой записи напрямую, поэтому он не
видит трёх вещей: порядка стадий конвейера, печати раздела узла в карточке
`load_1c_catalog_tool` и существования отдельного входа позиции 2.12 в реестре сервера.
Проверяются шесть позиций:

  1. порядок `STAGES` держит позицию 2.12 между 2.11 (S4k) и модулями объектов, и стадия
     имеет зеркала в `STAGE_FULL_RELOAD_ONLY`, подсказку продолжения и название незакрытой
     группы — урок П8 узлов V50–V56: отсутствие ключа маскируется значением по умолчанию в
     `build_stopped_stage`, и стадия с отдельным входом читается стадией без продолжения;
  2. круг стадии отделён от круга версионности: таблицы узла в `FOREIGN_STAGE_TABLES`, строки
     применения названы исключением версионности (Q2, вариант A) — иначе стадия S4 молча снимала
     бы 14 строк вида и 34 строки применения (замеры 1.1, 2.1);
  3. конвейер `load_catalog(MinCfg, force=True)` выполняет стадию S4l, её ответ лежит в
     собственном ключе `functional_options_parameters` (правило C3), числа машинной части
     совпадают с базовой линией плана (2 файла регистрации, 2 цели применения), а карточка
     содержит раздел узла (карточка и инструмент описывают слой одним форматёром);
  4. отказ стадии останавливает конвейер через `stopped_stage`: подсказка продолжения называет
     `load_functional_options_parameters_tool`, а не полную перезагрузку
     (`full_reload_required` ложна), незакрытая группа называется позицией 2.12, а последующие
     стадии перечислены `not_run` (правило C2);
  5. отдельный вход `load_functional_options_parameters_tool` печатает тот же текст раздела,
     что и карточка (прецедент V45: два текста об одном слое разъезжаются при первой правке), и
     отказывает на нечитаемом каталоге, а не на пустом составе;
  6. базовая линия круга по четырём выгрузкам (2/0/5/7 файлов и 2/0/6/26 целей применения,
     итог 14 и 34) читается и ответом отдельного входа, и строками таблиц, и витринами
     `v_current_functional_option_parameters`/`v_current_functional_option_parameter_targets`;
     повторный вызов не увеличивает число строк (идемпотентность держится явным `DELETE`), а
     KomMag отвечает пустым кругом с наблюдением `directory_missing` (Q9, вариант A), а не
     отказом.

MinCfg выбрана потому, что это эталон минимальной конфигурации узла V38 и наименьшая из
выгрузок с кругом 2.12: два файла регистрации и две цели применения (замеры 1.1, 2.1), поэтому
любое расхождение числа видно сразу.

Вызов:
    python _v57_p5_stage_probe.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List  # noqa: F401

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT / "tools", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 — перекодировка вывода не является проверкой
    pass

from config_load_router import format_load_result, load_catalog  # noqa: E402
from configuration_functional_options_parameters import (  # noqa: E402
    STATE_VOCABULARIES as FOP_STATE_VOCABULARIES,
)
from configuration_functional_options_parameters_loader import (  # noqa: E402
    load_functional_options_parameters,
)
from configuration_load_contract import (  # noqa: E402
    CONFIGURATION_VERSIONED_TABLES,
    FOREIGN_STAGE_TABLES,
    FUNCTIONAL_OPTION_PARAMETERS_TABLE,
    FUNCTIONAL_OPTION_PARAMETERS_TABLES,
    FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE,
    FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_BOUNDARY,
    FUNCTIONAL_OPTIONS_PARAMETERS_SECTION_HEADER,
    STAGE_COMMON_ATTRIBUTES,
    STAGE_EVENT_SUBSCRIPTIONS,
    STAGE_EXCHANGE_PLANS,
    STAGE_FILTER_CRITERIA,
    STAGE_FULL_RELOAD_ONLY,
    STAGE_FUNCTIONAL_OPTIONS,
    STAGE_FUNCTIONAL_OPTIONS_PARAMETERS,
    STAGE_HEADER,
    STAGE_INCOMPLETE_GROUPS,
    STAGE_OBJECT_MODULES,
    STAGE_ROOT_MODULES,
    STAGE_ROLES,
    STAGE_SCHEDULED_JOBS,
    STAGE_SESSION_PARAMETERS,
    STAGES,
    STATUS_ERROR,
    build_stopped_stage,
    functional_options_parameters_defaults,
    stage_resume_hint,
)
from external_table_writer import CONFIGURATION_UNVERSIONED_TABLES  # noqa: E402
from external_db import connect  # noqa: E402
from server_configurations_core import (  # noqa: E402
    load_functional_options_parameters_tool,
)

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
MINCFG = DUMP_ROOT / "MinCfg"
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")

# Базовая линия круга — числа плана (docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PARAMETERS_PLAN.md,
# разделы 1.1 и 2.1): 2/0/5/7 файлов регистрации и 2/0/6/26 целей применения, итог по корпусу
# 14 и 34. Проба сверяет с ними ответ стадии, строки таблиц и строки витрин: расхождение видно
# по имени выгрузки и имени таблицы. KomMag даёт пустой круг с наблюдением `directory_missing`.
BASELINE = {
    "MinCfg": (2, 2),
    "KomMag": (0, 0),
    "BGU2": (5, 6),
    "BP3": (7, 26),
}
CORPUS_TOTALS = (14, 34)

# Замкнутый словарь форм адреса цели читается тем же словарём разбора, что и форматёр ответа:
# второй перечень состояний в пробе нарушил бы сверку с CHECK живой схемы (П6) точно так же,
# как в самом ответе стадии.
FORMS_STATES: List[str] = list(FOP_STATE_VOCABULARIES["target_address_form"])

# Витрины текущности круга (узел V19, шаг П4): строки применения своей цепи ревизий не имеют,
# их текущность читается витриной связкой по `functional_option_parameter_id` (Q2, вариант A).
PARAMETERS_VIEW = "v_current_" + FUNCTIONAL_OPTION_PARAMETERS_TABLE
TARGETS_VIEW = "v_current_" + FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE

# Ключи стадий детей, которые обязан нести ответ конвейера (правило C3): отсутствие ключа
# означает, что стадия не отвечает, а нулевой ответ стадия даёт всегда.
STAGE_KEYS = (
    "root_modules", "child_objects", "session_parameters", "roles", "common_attributes",
    "exchange_plans", "filter_criteria", "event_subscriptions", "scheduled_jobs",
    "functional_options", "functional_options_parameters", "object_modules",
)
# Стадии, для которых держатся зеркала (снятие, подсказка, незакрытая группа): заголовок и
# разбор каталога снимаются вместе со строкой заголовка и отдельных входов не имеют.
CHILD_STAGES = (
    STAGE_ROOT_MODULES, STAGE_SESSION_PARAMETERS, STAGE_ROLES, STAGE_COMMON_ATTRIBUTES,
    STAGE_EXCHANGE_PLANS, STAGE_FILTER_CRITERIA, STAGE_EVENT_SUBSCRIPTIONS,
    STAGE_SCHEDULED_JOBS, STAGE_FUNCTIONAL_OPTIONS, STAGE_FUNCTIONAL_OPTIONS_PARAMETERS,
    STAGE_OBJECT_MODULES,
)

FAILURES: List[str] = []


def check(name: str, got: object, want: object) -> None:
    if got != want:
        FAILURES.append(f"{name}: получено {got!r}, ожидалось {want!r}")
        print(f"  [FAIL] {name} = {got!r} (ожидалось {want!r})")
    else:
        print(f"  [ok]   {name} = {got!r}")


def one(cur, sql, params=None):
    cur.execute(sql, params or ())
    row = cur.fetchone()
    return row[0] if row else None


def check_stage_order() -> None:
    """Позиция стадии и зеркала контракта остановки (статическая часть пробы)."""
    print("порядок стадий и зеркала контракта:")
    ids = [stage for stage, _ in STAGES]
    check("стадия S4l входит в STAGES", STAGE_FUNCTIONAL_OPTIONS_PARAMETERS in ids, True)
    check("S4l идёт сразу за S4k (позиция 2.12 за 2.11)",
          ids.index(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS) - ids.index(STAGE_FUNCTIONAL_OPTIONS),
          1)
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
    check("стадия S4l продолжения без точечного входа не требует",
          STAGE_FULL_RELOAD_ONLY[STAGE_FUNCTIONAL_OPTIONS_PARAMETERS], False)
    check("подсказка S4l называет отдельный вход группы",
          "load_functional_options_parameters_tool" in stage_resume_hint(
              STAGE_FUNCTIONAL_OPTIONS_PARAMETERS), True)
    check("незакрытая группа S4l называется позицией 2.12",
          "2.12" in (STAGE_INCOMPLETE_GROUPS.get(
              STAGE_FUNCTIONAL_OPTIONS_PARAMETERS) or ""), True)
    print()


def check_stage_circle() -> None:
    """Круг стадии отделён от круга версионности (иначе S4 снимал бы чужой круг)."""
    print("круг стадии и версионность (урок П8 узлов V50–V56):")
    for table in FUNCTIONAL_OPTION_PARAMETERS_TABLES:
        check(f"{table}: таблицы узла V57 нет в круге снятия стадии детей объектов",
              table in FOREIGN_STAGE_TABLES, True)
    check(f"{FUNCTIONAL_OPTION_PARAMETERS_TABLE}: строка вида версионируется общей цепью",
          FUNCTIONAL_OPTION_PARAMETERS_TABLE in CONFIGURATION_VERSIONED_TABLES, True)
    check(f"{FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE}: строк применения в круге версионности "
          "нет (Q2, вариант A)",
          FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE in CONFIGURATION_VERSIONED_TABLES, False)
    check(f"{FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE}: исключение версионности названо",
          FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE in CONFIGURATION_UNVERSIONED_TABLES, True)
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
    fop = result.get("functional_options_parameters") or {}
    check("ответ стадии имеет собственный ключ (правило C3)", bool(fop), True)
    check("стадия S4l успешна", bool(fop.get("success")), True)
    want_rows, want_targets = BASELINE["MinCfg"]
    check("файлов регистрации вида найдено", fop.get("files_found"), want_rows)
    check("разобрано файлов", fop.get("files_read"), want_rows)
    check("записей индекса состава вида (FunctionalOptionsParameter.<Имя>)",
          fop.get("index_kind_records"), want_rows)
    written = fop.get("written_by_table") or {}
    check(f"строк {FUNCTIONAL_OPTION_PARAMETERS_TABLE} записано",
          written.get(FUNCTIONAL_OPTION_PARAMETERS_TABLE), want_rows)
    check(f"строк {FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE} записано",
          written.get(FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE), want_targets)
    check("строк записано всего", fop.get("rows_written"), want_rows + want_targets)
    check("расхождений ног круга нет",
          sum((fop.get("counts_by_circle_discrepancy") or {}).values()), 0)
    resolve = fop.get("counts_by_target_resolve_state") or {}
    check("целей разрешено индексом (exact)", resolve.get("exact"), want_targets)
    check("неразрешённых целей (unresolved)", resolve.get("unresolved"), 0)
    check("неразрешённых целей всего", fop.get("unresolved_targets_total"), 0)
    check("целей применения посчитано", fop.get("targets_total"), want_targets)
    use = fop.get("counts_by_use_state") or {}
    check("строк вида с непустым перечнем", use.get("with_content"), want_rows)
    check("строк вида с пустым перечнем (empty_content)", use.get("empty_content"), 0)
    check("свойств разобрано без незнакомых тегов",
          (fop.get("counts_by_properties_state") or {}).get("all_known"), want_rows)
    check("элементов перечня с `xsi:type` формы `xr:MDObjectRef`",
          (fop.get("counts_by_item_type_state") or {}).get("md_object_ref"), want_targets)
    forms = fop.get("counts_by_target_address_form") or {}
    check("словарь форм адреса назван по всем состояниям замкнутого словаря",
          sorted(forms), sorted(FORMS_STATES))
    check("сумма форм адреса равна числу целей", sum(forms.values()), want_targets)
    check("нарушений инвариантов пары нет", fop.get("invariant_violations_total"), 0)
    check("наблюдений кроме перечисленных нет", sorted(fop.get("observations") or []), [])
    check("статистика двух таблиц пересобрана", fop.get("statistics_refreshed"), 2)
    text = format_load_result(result)
    check("карточка содержит раздел узла V57",
          FUNCTIONAL_OPTIONS_PARAMETERS_SECTION_HEADER in text, True)
    check("карточка называет числа записанных таблиц",
          f"{FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE}={want_targets}" in text, True)
    check("карточка называет границу круга тем же текстом, что и форматёр",
          FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_BOUNDARY in text, True)
    print()
    return text


def check_stop() -> None:
    """Отказ стадии: остановка конвейера и чем её продолжить."""
    print("остановка на отказе стадии S4l (контракт):")
    failure = functional_options_parameters_defaults()
    failure["status"] = STATUS_ERROR
    failure["error"] = "проба П5: круг не записан — один файл регистрации не разобран"
    stopped = build_stopped_stage(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS, failure,
                                 "заголовок конфигурации id=1")
    check("остановка называет стадию S4l", stopped.get("stage"),
          STAGE_FUNCTIONAL_OPTIONS_PARAMETERS)
    check("причина отказа переслана без переформулировки", stopped.get("reason"),
          failure["error"])
    check("полная перезагрузка не требуется", stopped.get("full_reload_required"), False)
    check("чем продолжить — назван отдельный вход позиции",
          "load_functional_options_parameters_tool" in (stopped.get("resume_with") or ""), True)
    check("незакрытая группа называется позицией 2.12",
          "2.12" in (stopped.get("incomplete_group") or ""), True)
    not_run = [item.get("stage") for item in (stopped.get("not_run_stages") or [])]
    check("после S4l не выполнялась только стадия модулей объектов", not_run,
          [STAGE_OBJECT_MODULES])
    print()


def check_tool(pipeline_text: str) -> None:
    """Отдельный вход позиции: тот же текст раздела, что и карточка, и честный отказ."""
    print("отдельный вход load_functional_options_parameters_tool:")
    ok = load_functional_options_parameters_tool(str(MINCFG))
    check("успешный ответ начинается с исхода", ok.startswith("✅"), True)
    check("ответ называет раздел узла", FUNCTIONAL_OPTIONS_PARAMETERS_SECTION_HEADER in ok,
          True)
    shared = next((line.strip() for line in ok.splitlines()
                   if "записано functional_option_parameter_targets=" in line), None)
    check("общая строка форматёра найдена", shared is not None, True)
    if shared:
        check("тот же текст печатает карточка load_1c_catalog_tool", shared in pipeline_text,
              True)
    detail = next((line.strip() for line in ok.splitlines()
                   if "состояний разрешения цели" in line), None)
    check("ответ называет состояния разрешения цели и формы адреса отдельной строкой",
          detail is not None, True)
    if detail:
        check("в строке различимы `exact` и форма адреса цели",
              "exact=" in detail and ("dimension=" in detail or "object=" in detail), True)
    observation_line = next((line.strip() for line in ok.splitlines()
                             if line.strip().startswith("Наблюдения круга:")), None)
    check("ответ называет наблюдения по замкнутому словарю родов (нули — ответ)",
          observation_line is not None and "directory_missing=0" in observation_line
          and "index_not_provided=0" in observation_line, True)
    check("ответ называет границу круга", FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_BOUNDARY in ok,
          True)
    bad = load_functional_options_parameters_tool(str(ROOT / "_нет_такого_каталога_"))
    check("нечитаемый каталог — отказ, а не пустой состав", bad.startswith("❌"), True)
    check("отказ не утверждает записанные строки",
          "записано functional_option_parameter_targets=" in bad, False)
    check("отказ называет, чем продолжить",
          "load_functional_options_parameters_tool" in bad, True)
    print()


def check_corpus() -> None:
    """Базовая линия круга по четырём выгрузкам: ответ, таблицы и витрины одним числом."""
    print("базовая линия круга по четырём выгрузкам (замеры 1.1 и 2.1 плана V57):")
    uuids: Dict[str, str] = {}
    totals = [0, 0]
    # Распределение целей по видам метаданных читается по корпусу: план (замер 2.1) даёт
    # `InformationRegister` 30 и `Catalog` 4 — цели ведут на объекты ДРУГИХ видов метаданных,
    # и это ровно то, чем круг 2.12 отличается от круга 2.11 (раздел 2 плана).
    kinds: Dict[str, int] = {}
    for name in DUMPS:
        result = load_functional_options_parameters(str(DUMP_ROOT / name))
        want_rows, want_targets = BASELINE[name]
        check(f"{name}: стадия успешна (пустой круг KomMag — ответ, а не отказ)",
              bool(result.get("success")), True)
        check(f"{name}: файлов регистрации вида", result.get("files_found"), want_rows)
        check(f"{name}: разобрано файлов", result.get("files_read"), want_rows)
        written = result.get("written_by_table") or {}
        check(f"{name}: строк строки вида записано",
              written.get(FUNCTIONAL_OPTION_PARAMETERS_TABLE), want_rows)
        check(f"{name}: строк применения записано",
              written.get(FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE), want_targets)
        check(f"{name}: целей применения посчитано", result.get("targets_total"), want_targets)
        check(f"{name}: расхождений ног круга нет",
              sum((result.get("counts_by_circle_discrepancy") or {}).values()), 0)
        check(f"{name}: неразрешённых целей нет (индекс состава загружен)",
              result.get("unresolved_targets_total"), 0)
        observed = sorted({(item[0] if isinstance(item, (tuple, list)) else
                           (item.get("kind") if isinstance(item, dict) else item))
                          for item in (result.get("observations") or [])})
        check(f"{name}: наблюдений кроме `directory_missing` у KomMag нет", observed,
              ["directory_missing"] if not want_rows else [])
        check(f"{name}: число наблюдений названо словарём `counts_by_observation` "
              "(пустой словарь — состояние «наблюдений нет», прецедент V53/V54/V56)",
              (result.get("counts_by_observation") or {}),
              {"directory_missing": 1} if not want_rows else {})
        totals[0] += int(result.get("files_found") or 0)
        totals[1] += int(result.get("targets_total") or 0)
        for kind, count in (result.get("targets_by_kind") or {}).items():
            kinds[kind] = kinds.get(kind, 0) + int(count)
        check(f"{name}: распределение целей по видам метаданных согласовано с их числом",
              sum((result.get("targets_by_kind") or {}).values()), want_targets)
        if result.get("configuration_uuid"):
            uuids[name] = str(result["configuration_uuid"])
    check("итог по корпусу — строки вида", totals[0], CORPUS_TOTALS[0])
    check("итог по корпусу — цели применения", totals[1], CORPUS_TOTALS[1])
    check("распределение целей по видам метаданных по корпусу — числа плана (замер 2.1)",
          kinds, {"InformationRegister": 30, "Catalog": 4})
    check("uuid конфигураций названы ответом стадии", len(uuids), len(DUMPS))
    print()

    print("строки таблиц и витрин текущности по тем же числам:")
    conn = connect()
    try:
        cur = conn.cursor()
        for name in DUMPS:
            want_rows, want_targets = BASELINE[name]
            uuid = uuids.get(name)
            if not uuid:
                check(f"{name}: uuid для сверки таблиц не назван", uuid, "назван")
                continue
            for table, view, want in (
                (FUNCTIONAL_OPTION_PARAMETERS_TABLE, PARAMETERS_VIEW, want_rows),
                (FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE, TARGETS_VIEW, want_targets),
            ):
                check(f"{name}: {table} строк по configuration_uuid",
                      one(cur, f"SELECT count(*) FROM {table} WHERE configuration_uuid = %s",
                          (uuid,)), want)
                check(f"{name}: {view} строк текущности",
                      one(cur, f"SELECT count(*) FROM {view} WHERE configuration_uuid = %s",
                          (uuid,)), want)
            check(f"{name}: сирот применения нет (FK с ON DELETE CASCADE и явный порядок снятия)",
                  one(cur,
                      "SELECT count(*) FROM " + FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE +
                      " t LEFT JOIN " + PARAMETERS_VIEW + " p ON p.id = "
                      "t.functional_option_parameter_id WHERE p.id IS NULL"), 0)
    finally:
        conn.close()
    print()


def check_repeat() -> None:
    """Идемпотентность: повтор снятого круга не увеличивает число строк (M7, явный `DELETE`)."""
    print("повторный прогон стадии на BP3 (снятие держится явным `DELETE`, не каскадом):")
    name = "BP3"
    want_rows, want_targets = BASELINE[name]
    first = load_functional_options_parameters(str(DUMP_ROOT / name))
    uuid = str(first.get("configuration_uuid") or "")
    again = load_functional_options_parameters(str(DUMP_ROOT / name))
    check(f"{name}: повтор успешен", bool(again.get("success")), True)
    removed = again.get("removed_by_table") or {}
    check("снято строк применения перед записью",
          removed.get(FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE), want_targets)
    check("снято строк вида перед записью",
          removed.get(FUNCTIONAL_OPTION_PARAMETERS_TABLE), want_rows)
    check("снято строк всего", again.get("removed_previous"), want_rows + want_targets)
    written = again.get("written_by_table") or {}
    check("записано строк вида повторно",
          written.get(FUNCTIONAL_OPTION_PARAMETERS_TABLE), want_rows)
    check("записано строк применения повторно",
          written.get(FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE), want_targets)
    conn = connect()
    try:
        cur = conn.cursor()
        for table, want in ((FUNCTIONAL_OPTION_PARAMETERS_TABLE, want_rows),
                            (FUNCTIONAL_OPTION_PARAMETER_TARGETS_TABLE, want_targets)):
            check(f"{table}: строк после повтора не стало больше",
                  one(cur, f"SELECT count(*) FROM {table} WHERE configuration_uuid = %s",
                      (uuid,)), want)
        check(f"{FUNCTIONAL_OPTION_PARAMETERS_TABLE}: ревизий второй цепи у повторной строки нет "
              "(повтор снимает, а не заводит новую ревизию — D8)",
              one(cur, f"SELECT max(revision_no) FROM {FUNCTIONAL_OPTION_PARAMETERS_TABLE} "
                       "WHERE configuration_uuid = %s", (uuid,)), 1)
    finally:
        conn.close()
    print()


def main() -> int:
    check_stage_order()
    check_stage_circle()
    pipeline_text = check_pipeline()
    check_stop()
    check_tool(pipeline_text)
    check_corpus()
    check_repeat()
    if FAILURES:
        print(f"ПРОВАЛЫ П5 ({len(FAILURES)}):")
        for text in FAILURES:
            print(f"  - {text}")
        return 1
    print("П5 ПРОЙДЕН: стадия, остановка и отдельный вход расхождений не дают")
    return 0


if __name__ == "__main__":
    sys.exit(main())

