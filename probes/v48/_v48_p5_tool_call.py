# -*- coding: utf-8 -*-
"""_v48_p5_tool_call.py — живой вызов нового инструмента узла V48 (шаг П5).

План узла (`docs/CONFIGURATION_SESSION_PARAMETERS_PLAN.md`, раздел 6, П5) требует проверки
«вызов инструмента на MinCfg и BP3, повторный вызов идемпотентен». Вызывается НЕ копия слоя,
а зарегистрированный `@mcp.tool()` — иначе проверялось бы не то, что отдаёт MCP.

Что проверяется:
  * регистрация `@mcp.tool()` не прячет функцию слоя (её можно вызвать);
  * круг вызова выбирает база: выгрузка участвует, только если строка заголовка есть
    (иначе проба проверяла бы своё предположение о списке выгрузок);
  * ответ точки входа = ответ слоя: успех, раздел общим форматёром, числа равны строкам
    таблицы, снятое названо, `revision_no` не растёт (D8);
  * базовое состояние сравнивается с count'ами до и после — инвариант «после пробы таблицы
    пусты» узлом V48 снят: конвейер пишет реальный состав;
  * отказы точки входа называются состояниями слоя, а не падением: нет строки заголовка,
    расхождение `configuration_uuid`, нечитаемый каталог.

Запуск:
    python _v48_p5_tool_call.py              # круг выбирает база из кандидатов
    python _v48_p5_tool_call.py MinCfg BP3   # явный круг
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import server_configurations_core as SERVER  # noqa: E402
from configuration_load_contract import (  # noqa: E402
    SESSION_PARAMETERS_SECTION_HEADER,
    SESSION_PARAMETER_TABLE,
)
from configuration_root_module_loader import configuration_uuid_from_layout  # noqa: E402
from configuration_session_parameters import RECORD_STATES  # noqa: E402
from current_revision import FIRST_REVISION  # noqa: E402
from external_db import connect  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
CANDIDATES = ("MinCfg", "BP3", "BGU2", "KomMag")

PASSED = 0
FAILED = 0
NOTES = []


def check(name, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("  [OK]   " + name + ((" — " + str(detail)) if detail else ""))
    else:
        FAILED += 1
        print("  [FAIL] " + name + ((" — " + str(detail)) if detail else ""))


def note(text):
    NOTES.append(text)
    print("  [ЗАМЕЧАНИЕ] " + text)


def table_state(cur, cfg_uuid):
    """Состояние таблицы слоя для этой конфигурации: число строк, максимум ревизии,
    распределение состояний разбора типа (по ним сверяется ответ точки входа)."""
    cur.execute(f"SELECT count(*), max(revision_no) FROM {SESSION_PARAMETER_TABLE} "
                "WHERE configuration_uuid = %s::uuid", (str(cfg_uuid),))
    total, revision = cur.fetchone()
    cur.execute(f"SELECT type_parse_state, count(*) FROM {SESSION_PARAMETER_TABLE} "
                "WHERE configuration_uuid = %s::uuid GROUP BY 1 ORDER BY 1",
                (str(cfg_uuid),))
    states = {row[0]: row[1] for row in cur.fetchall()}
    return {"total": int(total or 0), "revision": revision, "states": states}


def first_written_line(text, limit=160):
    """Строка ответа с числом записанных строк — её и сверяют с таблицей."""
    for line in (text or "").splitlines():
        if "Записано строк свойств" in line:
            return line.strip()[:limit]
    return (text or "").splitlines()[-1][:limit] if text else ""


def main() -> int:
    tool = getattr(SERVER, "load_session_parameters_tool", None)
    check("инструмент зарегистрирован в сервере", tool is not None)
    call = getattr(tool, "fn", tool)
    check("регистрация @mcp.tool() не спрятала функцию слоя", callable(call),
          f"тип объекта: {type(tool).__name__}")

    chosen = tuple(arg for arg in sys.argv[1:] if arg in CANDIDATES) or CANDIDATES
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, uuid FROM configurations")
            loaded = {str(row[2]).lower(): row for row in cur.fetchall()}

            circles = []
            for name in chosen:
                layout = DUMP_ROOT / name
                if not layout.exists():
                    note(f"каталога выгрузки нет на диске: {name}")
                    continue
                info = configuration_uuid_from_layout(str(layout))
                uuid = str(info.get("uuid") or "").lower()
                if not uuid:
                    note(f"{name}: Configuration.xml не читается — {info.get('error')}")
                    continue
                if uuid not in loaded:
                    note(f"{name}: строки заголовка в базе нет — точка входа обязана "
                         "отказать «заголовок не загружен»")
                    continue
                circles.append((name, layout, uuid, loaded[uuid]))

            check("круг вызова непустой", bool(circles),
                  ", ".join(name for name, *_ in circles) or "нет выгруженных выгрузок")

            for name, layout, uuid, header in circles:
                print(f"\n=== {name} (configurations.id={header[0]}, {header[1]}) ===")
                before = table_state(cur, uuid)
                # Круг считается НЕ по ответу инструмента, а по диску: сколько файлов
                # регистрации вида лежит в каталоге выгрузки. Иначе проверка сверяла бы
                # ответ с ним самим.
                files_on_disk = len([item for item in (layout / "SessionParameters").iterdir()
                                     if item.is_file()])
                text = call(str(layout))
                check(f"{name}: ответ точки входа начинается с успеха",
                      text.startswith("✅"), text.splitlines()[0][:120])
                check(f"{name}: раздел даёт общий форматёр контракта",
                      SESSION_PARAMETERS_SECTION_HEADER in text)
                check(f"{name}: ответ не обещает инструмент, которого нет",
                      "пока нет" not in text and "его заводит шаг П5" not in text)

                after = table_state(cur, uuid)
                check(f"{name}: строк столько же, сколько файлов регистрации вида на диске",
                      after["total"] == files_on_disk,
                      f"файлов: {files_on_disk}, до вызова строк: {before['total']}, "
                      f"после: {after['total']}")
                check(f"{name}: число в ответе равно числу строк таблицы",
                      f"Записано строк свойств ({SESSION_PARAMETER_TABLE}): {after['total']}"
                      in text, first_written_line(text))
                check(f"{name}: ревизия остаётся первой (история состояний не заводится, D8)",
                      after["revision"] == FIRST_REVISION,
                      f"revision_no: {before['revision']} -> {after['revision']}")
                check(f"{name}: состояния разбора — только закрытый словарь",
                      after["states"] and set(after["states"]) <= set(RECORD_STATES)
                      and sum(after["states"].values()) == after["total"],
                      after["states"])

                again = call(str(layout))
                third = table_state(cur, uuid)
                check(f"{name}: повторный вызов состояние не меняет",
                      again.startswith("✅") and third["total"] == after["total"]
                      and third["revision"] == after["revision"]
                      and third["states"] == after["states"],
                      f"строк после повтора: {third['total']}")
                check(f"{name}: повтор называет снятое",
                      f"снято прежних строк: {after['total']}" in again,
                      first_written_line(again))

            print("\n=== отказы точки входа ===")
            for name in chosen:
                layout = DUMP_ROOT / name
                if not layout.exists():
                    continue
                uuid = str((configuration_uuid_from_layout(str(layout)) or {})
                           .get("uuid", "")).lower()
                if uuid and uuid not in loaded:
                    text = call(str(layout))
                    check(f"{name}: отсутствие строки заголовка — отказ слоя, а не падение",
                          text.startswith("❌") and "заголов" in text,
                          text.splitlines()[0][:140])
                    check(f"{name}: отказ называет, чем продолжить (отдельный вход группы)",
                          "load_session_parameters_tool" in text,
                          " | ".join(line.strip() for line in text.splitlines()
                                     if "load_session_parameters_tool" in line)[:160])
            if circles:
                name, layout, _uuid, _ = circles[0]
                text = call(str(layout), "00000000-0000-0000-0000-000000000000")
                check("расхождение configuration_uuid называется отказом, а не выбором",
                      text.startswith("❌") and "configuration_uuid" in text,
                      text.splitlines()[0][:140])
                check("отказ точки входа называет, чем продолжить (отдельный вход группы)",
                      "load_session_parameters_tool" in text,
                      " | ".join(line.strip() for line in text.splitlines()
                                 if "load_session_parameters_tool" in line)[:170])
                text = call(str(DUMP_ROOT / "MinCfg__нет_такого_каталога"))
                check("нечитаемый каталог выгрузки — отказ слоя, а не падение",
                      text.startswith("❌"), text.splitlines()[0][:140])
    finally:
        conn.close()

    print(f"\nитог: проверок {PASSED}, провалено {FAILED}, замечаний {len(NOTES)}")
    for item in NOTES:
        print("  • " + item)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())