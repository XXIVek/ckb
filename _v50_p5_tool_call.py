# -*- coding: utf-8 -*-
"""_v50_p5_tool_call.py — живой вызов нового инструмента узла V50 (шаг П5).

План узла (`docs/CONFIGURATION_COMMON_ATTRIBUTES_PLAN.md`, П5) требует проверить точку входа
группы: «`load_common_attributes_tool` + `EXPECTED_TOOLS` (8) + карточка правила». Вызывается
НЕ копия слоя, а зарегистрированный `@mcp.tool()` — иначе проверялось бы не то, что отдаёт MCP
(прецеденты `_v48_p5_tool_call.py`, `_v49_p5_tool_call.py`).

Что проверяется:
  * регистрация `@mcp.tool()` не прячет функцию слоя, и точка входа зовёт слой, а не копирует
    его числа;
  * круга запроса (`kinds`) у входа нет (Q10, вариант A): сигнатура принимает только путь и
    uuid, третьей позиции нет;
  * круг вызова выбирает база: выгрузка участвует, только если строка заголовка есть;
  * ответ описан закрытым контрактом: раздел общим форматёром, числа равны строкам таблиц
    (`common_attributes` — по витрине текущего состояния, `common_attribute_targets` — прямо по
    `configuration_uuid`, потому что своей цепи ревизий у применения нет, Q2 вариант A);
  * снятое названо прежними числами, `revision_no` остаётся первой (D8), повтор состав не
    меняет (идемпотентность держится явным DELETE);
  * каждая строка применения ссылается на CURRENT-ревизию своего реквизита, счётчики
    `targets_count` равны числу строк применения (иначе «реквизит без применения» и
    «применение не записано» были бы неразличимы);
  * состояния остаются закрытыми словарями (свойств, перечней, разрешения целей, применения,
    условия разделения, блока `<Type>` и его кратности);
  * пустой круг (KomMag) — ответ о выгрузке, а не отказ: `Файлов регистрации: 0` и наблюдение
    `directory_missing`;
  * отказы точки входа называются состояниями слоя, а не падением: расхождение
    `configuration_uuid`, нечитаемый каталог, отсутствующая строка заголовка; и отказ, и успех
    называют, чем продолжить (отдельный вход группы).

Запуск:
    python _v50_p5_tool_call.py                  # круг выбирается по строкам заголовка в БД
    python _v50_p5_tool_call.py MinCfg KomMag    # явный круг
Код возврата 0 — провалов нет; 1 — есть проваленные проверки.
"""
from __future__ import annotations

import inspect
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

import server_configurations_core as SERVER  # noqa: E402
from configuration_common_attributes import (  # noqa: E402
    CONTENT_STATES, ITEM_COND_STATES, MULTIPLICITY_VALUES, PROPERTIES_STATES,
    RECORD_STATES, TABLE_NAME as CA_TABLE,
    TARGETS_TABLE_NAME as CA_TARGETS_TABLE, TARGET_RESOLVE_STATES, USE_STATES,
)
from configuration_load_contract import (  # noqa: E402
    COMMON_ATTRIBUTES_REPEAT_HINT,
    COMMON_ATTRIBUTES_SECTION_HEADER,
    COMMON_ATTRIBUTES_TABLES,
)
from configuration_root_module_loader import configuration_uuid_from_layout  # noqa: E402
from current_revision import FIRST_REVISION, current_view  # noqa: E402
from external_db import connect  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
CANDIDATES = ("MinCfg", "KomMag", "BGU2", "BP3")

# Строки применения версионируются НЕ своей цепью (Q2, вариант A): витрины текущего состояния
# для счёта у таблицы нет, её строки считаются прямо по `configuration_uuid` — тот же приём,
# что с `role_rights` у узла V49.
DIRECT_COUNT_TABLES = (CA_TARGETS_TABLE,)

# Колонки состояний двух таблиц: чем записано, тем и проверяется замкнутость словаря.
STATE_COLUMNS = {
    CA_TABLE: {
        "properties": ("properties_state", PROPERTIES_STATES),
        "content": ("content_state", CONTENT_STATES),
        "type": ("type_parse_state", RECORD_STATES),
        "multiplicity": ("type_multiplicity", MULTIPLICITY_VALUES),
    },
    CA_TARGETS_TABLE: {
        "resolve": ("target_resolve_state", TARGET_RESOLVE_STATES),
        "use": ("use_state", USE_STATES),
        "item_cond": ("conditional_separation_state", ITEM_COND_STATES),
    },
}

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


def call(*args, **kwargs):
    """Вызов зарегистрированного инструмента, а не копии слоя."""
    return SERVER.load_common_attributes_tool(*args, **kwargs)


def count_source(table):
    """Чем читается состояние таблицы: витрина CURRENT или сама таблица."""
    return table if table in DIRECT_COUNT_TABLES else current_view(table)


def table_counts(cur, cfg_uuid):
    """Состояние двух таблиц узла для этой конфигурации + словари состояний."""
    state = {}
    for table in COMMON_ATTRIBUTES_TABLES:
        source = count_source(table)
        cur.execute(f"SELECT count(*), max(id) FROM {source} "
                    "WHERE configuration_uuid = %s::uuid", (str(cfg_uuid),))
        total, max_id = cur.fetchone()
        state[table] = {"total": int(total or 0), "max_id": int(max_id or 0)}
    for table, columns in STATE_COLUMNS.items():
        source = count_source(table)
        for label, (column, _vocabulary) in columns.items():
            cur.execute(f"SELECT {column}, count(*) FROM {source} "
                        "WHERE configuration_uuid = %s::uuid GROUP BY 1 ORDER BY 1",
                        (str(cfg_uuid),))
            state[f"{label}_states"] = {row[0]: int(row[1]) for row in cur.fetchall()}
    cur.execute(f"SELECT max(revision_no) FROM {current_view(CA_TABLE)} "
                "WHERE configuration_uuid = %s::uuid", (str(cfg_uuid),))
    state["revision"] = cur.fetchone()[0]
    return state


def written_line(text):
    """Строка ответа с числами записанного — её и сверяют с таблицами."""
    for line in (text or "").splitlines():
        if "Записано строк по таблицам:" in line:
            return line.strip()
    return ""


def expected_written_text(counts):
    """Та же строку чисел, какую обязан выдать форматёр по состоянию таблиц."""
    return ("Записано строк по таблицам: "
            + ", ".join(f"{table}={counts[table]['total']}"
                        for table in COMMON_ATTRIBUTES_TABLES))


def targets_orphans(cur, cfg_uuid):
    """Строки применения без строки реквизита в CURRENT — их быть не должно (Q2, вариант A)."""
    cur.execute(
        f"SELECT count(*) FROM {CA_TARGETS_TABLE} t "
        f"LEFT JOIN {current_view(CA_TABLE)} ca "
        "  ON ca.id = t.common_attribute_id "
        " AND ca.configuration_uuid = t.configuration_uuid "
        "WHERE t.configuration_uuid = %s::uuid AND ca.id IS NULL", (str(cfg_uuid),))
    return int(cur.fetchone()[0] or 0)


def targets_counter_mismatches(cur, cfg_uuid):
    """Строки реквизита, где `targets_count` не равен числу строк применения."""
    cur.execute(
        f"SELECT count(*) FROM {current_view(CA_TABLE)} ca "
        "WHERE ca.configuration_uuid = %s::uuid AND ca.targets_count <> ("
        f"  SELECT count(*) FROM {CA_TARGETS_TABLE} t "
        "    WHERE t.common_attribute_id = ca.id)", (str(cfg_uuid),))
    return int(cur.fetchone()[0] or 0)


def revision_is_ok(state):
    """Ревизия обязана быть первой (D8); у пустого круга строк нет — и `max` обязан быть NULL.

    Требовать `FIRST_REVISION` при нуле строк значило бы искать строку, которой в выгрузке
    нет: `max(revision_no)` по пустому кругу является состоянием круга, а не нарушением D8
    (тот же приём, что с нулями незаписанных таблиц у узла V49).
    """
    if state[CA_TABLE]["total"] == 0:
        return state["revision"] is None
    return state["revision"] == FIRST_REVISION



def check_registration():
    """Регистрация `@mcp.tool()` не прячет функцию слоя, и точка входа зовёт слой."""
    print("=== регистрация инструмента ===")
    tool = getattr(SERVER, "load_common_attributes_tool", None)
    check("в сервере есть функция load_common_attributes_tool", callable(tool))
    if not callable(tool):
        return False
    check("точка входа вызывает слой load_common_attributes, а не копию его кода",
          "load_common_attributes" in tool.__code__.co_names
          and "_format_common_attributes_result" in tool.__code__.co_names,
          ", ".join(sorted(n for n in tool.__code__.co_names if "common_attributes" in n)))
    params = list(inspect.signature(tool).parameters)
    check("параметров три нет: круга запроса kinds у входа нет (Q10, вариант A)",
          params == ["source_path", "configuration_uuid"], params)
    doc = tool.__doc__ or ""
    check("докстринг называет позицию 2.5, обе таблицы круга и отсутствие kinds",
          "2.5" in doc and CA_TABLE in doc and CA_TARGETS_TABLE in doc
          and "kinds" in doc and "Q10" in doc,
          f"докстринг {len(doc)} симв.")
    check("шапка модуля называет новый инструмент (реестр читают и по шапке)",
          "load_common_attributes_tool" in (SERVER.__doc__ or ""),
          "шапка модуля")
    return True


def check_state_vocabulary(name, state):
    """Каждое состояние — замеренный словарь, а сумма состояний равна числу строк."""
    for table, columns in STATE_COLUMNS.items():
        source = count_source(table)
        for label, (_column, vocabulary) in columns.items():
            found = state[f"{label}_states"]
            check(f"{name}: {source}.{_column} остаётся закрытым словарём {label}",
                  set(found) <= set(vocabulary)
                  and sum(found.values()) == state[table]["total"],
                  found if set(found) - set(vocabulary) else found)


def check_full_circle(name, layout, cfg_uuid, conn):
    """Полный круг: ответ равен состоянию таблиц, повтор идемпотентен, состояния — словари."""
    print(f"\n=== полный круг: {name}")
    cur = conn.cursor()
    before = table_counts(cur, cfg_uuid)
    text = call(str(layout))
    check(f"{name}: вызов завершился успехом, а не отказом",
          text.startswith("✅"), (text.splitlines() or [""])[0][:150])
    if not text.startswith("✅"):
        return None
    after = table_counts(cur, cfg_uuid)

    check(f"{name}: ответ содержит раздел круга общим форматёром контракта",
          COMMON_ATTRIBUTES_SECTION_HEADER in text, COMMON_ATTRIBUTES_SECTION_HEADER)
    check(f"{name}: числа записанного равны строкам таблиц",
          expected_written_text(after) in text, written_line(text))
    removed_ok = all(f"{table}={before[table]['total']}" in text
                     for table in COMMON_ATTRIBUTES_TABLES)
    check(f"{name}: снятые строки названы прежними числами",
          removed_ok or sum(before[t]["total"] for t in COMMON_ATTRIBUTES_TABLES) == 0,
          "снято до вызова: " + ", ".join(f"{t}={before[t]['total']}"
                                          for t in COMMON_ATTRIBUTES_TABLES))
    check(f"{name}: ответ называет круг и позицию списка (файлы, а не только строки)",
          "Файлов регистрации:" in text and "позиция 2.5 списка" in text,
          next((line.strip()[:120] for line in text.splitlines()
                if "Файлов регистрации:" in line), ""))
    check(f"{name}: сверка с индексом состава названа, а не подразумевана",
          "Сверка с индексом состава:" in text,
          next((line.strip()[:160] for line in text.splitlines()
                if "Сверка с индексом состава:" in line), ""))
    check(f"{name}: граница круга называется и при успехе",
          "Граница:" in text and CA_TARGETS_TABLE in text,
          next((line.strip()[:120] for line in text.splitlines()
                if line.strip().startswith("Граница:")), ""))
    check(f"{name}: ответ называет, чем продолжить дозагрузку (отдельный вход)",
          COMMON_ATTRIBUTES_REPEAT_HINT in text)
    check(f"{name}: ревизия остаётся первой — история состояний не заводится (D8)",
          revision_is_ok(after),
          f"revision_no: {before['revision']} -> {after['revision']}")
    check(f"{name}: строка применения ссылается на CURRENT-ревизию своего реквизита",
          targets_orphans(cur, cfg_uuid) == 0, targets_orphans(cur, cfg_uuid))
    check(f"{name}: счётчики перечней равны числу строк применения",
          targets_counter_mismatches(cur, cfg_uuid) == 0,
          targets_counter_mismatches(cur, cfg_uuid))
    check_state_vocabulary(name, after)

    again = call(str(layout))
    third = table_counts(cur, cfg_uuid)
    same = all(third[t]["total"] == after[t]["total"] for t in COMMON_ATTRIBUTES_TABLES)
    check(f"{name}: повторный вызов состав не меняет",
          again.startswith("✅") and same,
          "; ".join(f"{t} {after[t]['total']}->{third[t]['total']}"
                    for t in COMMON_ATTRIBUTES_TABLES))
    check(f"{name}: повтор называет снятое",
          all(f"{t}={after[t]['total']}" in again for t in COMMON_ATTRIBUTES_TABLES),
          written_line(again))
    check(f"{name}: повтор не поднимает ревизию (D8)",
          revision_is_ok(third), third["revision"])
    # Дальнейшие пробы сравнивают состояние, а повтор пересоздал строки: базой является
    # состояние ПОСЛЕ повтора (тот же вывод, что у пробы узла V49).
    return third


def check_empty_circle(name, text, after, conn=None):
    """Пустой круг выгрузки — ответ о выгрузке, а не отказ (Q9, замер 2.9 для KomMag)."""
    if "Файлов регистрации: 0" not in text:
        return False
    print(f"\n=== пустой круг (каталога вида нет): {name}")
    check(f"{name}: пустой круг назван наблюдением directory_missing, а не отказом",
          "directory_missing" in text,
          next((line.strip()[:170] for line in text.splitlines()
                if "directory_missing" in line), ""))
    check(f"{name}: пустой круг не записал ни одной строки",
          all(after[t]["total"] == 0 for t in COMMON_ATTRIBUTES_TABLES),
          ", ".join(f"{t}={after[t]['total']}" for t in COMMON_ATTRIBUTES_TABLES))
    check(f"{name}: пустой круг не выдаёт нули за отсутствие позиции — названа граница",
          "Граница:" in text, next((line.strip()[:120] for line in text.splitlines()
                                    if line.strip().startswith("Граница:")), ""))
    return True


def check_refusals(circles):
    """Отказы точки входа называются состояниями слоя, а не падением."""
    print("\n=== отказы точки входа ===")
    name, layout, _uuid = circles[0]
    text = call(str(layout), "00000000-0000-0000-0000-000000000000")
    check("расхождение configuration_uuid называется отказом, а не выбором",
          text.startswith("❌") and "configuration_uuid" in text,
          (text.splitlines() or [""])[0][:150])
    check("отказ точки входа называет, чем продолжить (отдельный вход группы)",
          COMMON_ATTRIBUTES_REPEAT_HINT in text,
          next((line.strip() for line in text.splitlines()
                if "load_common_attributes_tool" in line), "")[:170])
    check("причина отказа печатается форматёром контракта, а не отдельным текстом",
          "Стадия не" in text,
          next((line.strip()[:170] for line in text.splitlines()
                if "Стадия не" in line), ""))
    text = call(str(DUMP_ROOT / "MinCfg__нет_такого_каталога"))
    check("нечитаемый каталог выгрузки — отказ слоя, а не падение",
          text.startswith("❌"), (text.splitlines() or [""])[0][:150])


def main(argv=None) -> int:
    if not check_registration():
        return 1

    wanted = tuple(argv) or CANDIDATES
    conn = connect()
    circles = []
    try:
        cur = conn.cursor()
        for name in wanted:
            layout = DUMP_ROOT / name
            if not layout.exists():
                note(f"{name}: каталога выгрузки нет — {layout}")
                continue
            uuid = str((configuration_uuid_from_layout(str(layout)) or {}).get(
                "uuid", "")).lower()
            if not uuid:
                note(f"{name}: uuid выгрузки не читается")
                continue
            cur.execute("SELECT 1 FROM configurations WHERE uuid = %s::uuid", (uuid,))
            if cur.fetchone() is None:
                note(f"{name}: строки заголовка в БД нет — выгрузка вне круга пробы")
                continue
            circles.append((name, layout, uuid))
        if not circles:
            print("\nИТОГ: загруженных конфигураций в круге нет — точку входа проверять нечем")
            return 1

        empty_circles = 0
        for name, layout, uuid in circles:
            after = check_full_circle(name, layout, uuid, conn)
            if after is None:
                continue
            if check_empty_circle(name, call(str(layout)), after):
                empty_circles += 1

        check_refusals(circles)

        for name in wanted:
            layout = DUMP_ROOT / name
            if not layout.exists() or any(layout == c[1] for c in circles):
                continue
            uuid = str((configuration_uuid_from_layout(str(layout)) or {}).get(
                "uuid", "")).lower()
            if not uuid:
                continue
            text = call(str(layout))
            check(f"{name}: отсутствие строки заголовка — отказ слоя, а не падение",
                  text.startswith("❌") and "заголов" in text,
                  (text.splitlines() or [""])[0][:150])
        if empty_circles:
            note(f"пустых кругов в прогоне: {empty_circles} — это состояние выгрузки "
                 "(каталога вида нет), а не пропуск проверки")
    finally:
        conn.close()

    print(f"\nитог: проверок {PASSED}, провалено {FAILED}, замечаний {len(NOTES)}")
    for item in NOTES:
        print("  • " + item)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))



