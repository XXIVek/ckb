# -*- coding: utf-8 -*-
"""_v49_p5_tool_call.py — живой вызов нового инструмента узла V49 (шаг П5).

План узла (`docs/CONFIGURATION_ROLES_PLAN.md`, раздел 6, П5) требует проверить точку входа
группы: «`load_roles_tool` + `EXPECTED_TOOLS` (7) + карточка правила». Вызывается НЕ копия
слоя, а зарегистрированный `@mcp.tool()` — иначе проверялось бы не то, что отдаёт MCP
(прецедент `_v48_p5_tool_call.py`).

Что проверяется:
  * регистрация `@mcp.tool()` не прячет функцию слоя (её можно вызвать), и точка входа
    отдаёт ровно то, что слой: успех, раздел общим форматёром, числа равны строкам таблиц;
  * круг вызова выбирает база: выгрузка участвует, только если строка заголовка есть
    (иначе проба проверяла бы своё предположение о списке выгрузок);
  * снятое названо, ревизия не растёт (D8), состояния остаются закрытыми словарями;
  * повторный вызов состояние не меняет (идемпотентность держится явным DELETE);
  * `kinds` — три группы круга и правила их сочетания:
      - неизвестная группа и пустой запрос — отказ с перечнем допустимых;
      - `roles` без `role_rights` — отказ (каскад FK оставил бы роли без прав);
      - `role_restrictions` одна — шаблоны перезаписаны, соседние таблицы не тронуты, и
        ответ называет незапрошенные группы;
      - `role_rights` одна — права записаны на те же id ролей, что лежали в базе (числа id
        не изменились), роли и дескрипторы не тронуты;
      - `role_rights` одна при отсутствующих строках ролей — отказ, называющий состояние
        базы (перед этим круг снимается `remove_roles`, и сразу восстанавливается полным
        вызовом — проба не оставляет базу в половинчатом состоянии);
  * согласованность ответа: сумма чисел групп равна общему числу записанных строк, нули
    незапрошенных таблиц совпадают с незапрошенными группами;
  * отказы точки входа называются состояниями слоя, а не падением: нет строки заголовка,
    расхождение `configuration_uuid`, нечитаемый каталог.

Запуск:
    python _v49_p5_tool_call.py                  # круг выбирается по строкам заголовка в БД
    python _v49_p5_tool_call.py MinCfg KomMag    # явный круг
Код возврата 0 — провалов нет; 1 — есть проваленные проверки.
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
    ROLES_REPEAT_HINT,
    ROLES_SECTION_HEADER,
    ROLE_CONTENT_STATES,
    ROLE_KINDS,
    ROLE_RIGHTS_TABLE,
    ROLE_RIGHT_VALUE_STATES,
    ROLE_SOURCES_TABLE,
    ROLE_TABLE,
    ROLE_TABLES,
    ROLE_TEMPLATES_TABLE,
)
from configuration_roles_loader import remove_roles  # noqa: E402
from configuration_root_module_loader import configuration_uuid_from_layout  # noqa: E402
from current_revision import FIRST_REVISION, current_view  # noqa: E402
from external_db import connect, transaction  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
CANDIDATES = ("MinCfg", "KomMag", "BGU2", "BP3")

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
    return SERVER.load_roles_tool(*args, **kwargs)


def table_counts(cur, cfg_uuid):
    """Состояние четырёх таблиц узла для этой конфигурации.

    Версионируемые таблицы считаются по витрине текущего состояния (`v_current_*`) — строки
    прежних ревизий в круге чтения не существует; `role_rights` версий не имеет вовсе и
    считается прямо по `configuration_uuid` (исключение
    `CONFIGURATION_UNVERSIONED_TABLES`). Плюс `max(id)` по каждой таблице: по нему видно,
    что права дописаны к прежним строкам ролей, а не к новым.
    """
    state = {}
    for table in ROLE_TABLES:
        source = table if table == ROLE_RIGHTS_TABLE else current_view(table)
        cur.execute(f"SELECT count(*), max(id) FROM {source} "
                    "WHERE configuration_uuid = %s::uuid", (str(cfg_uuid),))
        total, max_id = cur.fetchone()
        state[table] = {"total": int(total or 0), "max_id": int(max_id or 0)}
    cur.execute(f"SELECT max(revision_no) FROM {current_view(ROLE_TABLE)} "
                "WHERE configuration_uuid = %s::uuid", (str(cfg_uuid),))
    state["revision"] = cur.fetchone()[0]
    cur.execute(f"SELECT right_value_state, count(*) FROM {ROLE_RIGHTS_TABLE} "
                "WHERE configuration_uuid = %s::uuid GROUP BY 1 ORDER BY 1",
                (str(cfg_uuid),))
    state["value_states"] = {row[0]: row[1] for row in cur.fetchall()}
    cur.execute(f"SELECT content_state, count(*) FROM {current_view(ROLE_TABLE)} "
                "WHERE configuration_uuid = %s::uuid GROUP BY 1 ORDER BY 1",
                (str(cfg_uuid),))
    state["content_states"] = {row[0]: row[1] for row in cur.fetchall()}
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
            + ", ".join(f"{table}={counts[table]['total']}" for table in ROLE_TABLES))


def check_full_circle(name, layout, cfg_uuid, conn):
    """Полный круг: ответ равен состоянию таблиц, повтор идемпотентен, состояния — словари."""
    print(f"\n=== полный круг (kinds не задан): {name}")
    cur = conn.cursor()
    before = table_counts(cur, cfg_uuid)
    text = call(str(layout))
    check(f"{name}: вызов завершился успехом, а не отказом",
          text.startswith("✅"), (text.splitlines() or [""])[0][:150])
    if not text.startswith("✅"):
        return None
    after = table_counts(cur, cfg_uuid)

    check(f"{name}: ответ содержит раздел круга общим форматёром контракта",
          ROLES_SECTION_HEADER in text, ROLES_SECTION_HEADER)
    check(f"{name}: числа записанного равны строкам таблиц",
          expected_written_text(after) in text, written_line(text))
    removed_ok = all(f"{table}={before[table]['total']}" in text for table in ROLE_TABLES)
    check(f"{name}: снятые строки названы прежними числами",
          removed_ok or (sum(before[t]["total"] for t in ROLE_TABLES) == 0),
          "снято до вызова: " + ", ".join(f"{t}={before[t]['total']}" for t in ROLE_TABLES))
    check(f"{name}: при полном круге строки о незапрошенных группах нет",
          "Группы круга не запрашивались" not in text)
    check(f"{name}: ревизия остаётся первой — история состояний не заводится (D8)",
          after["revision"] == FIRST_REVISION,
          f"revision_no: {before['revision']} -> {after['revision']}")
    check(f"{name}: состояния значений прав остаются закрытым словарём",
          set(after["value_states"]) <= set(ROLE_RIGHT_VALUE_STATES)
          and sum(after["value_states"].values()) == after[ROLE_RIGHTS_TABLE]["total"],
          after["value_states"])
    check(f"{name}: состояния содержимого остаются закрытым словарём",
          set(after["content_states"]) <= set(ROLE_CONTENT_STATES)
          and sum(after["content_states"].values()) == after[ROLE_TABLE]["total"],
          after["content_states"])
    check(f"{name}: ответ называет, чем продолжить дозагрузку (отдельный вход)",
          ROLES_REPEAT_HINT in text)

    again = call(str(layout))
    third = table_counts(cur, cfg_uuid)
    same = all(third[t]["total"] == after[t]["total"] for t in ROLE_TABLES)
    check(f"{name}: повторный вызов состав не меняет",
          again.startswith("✅") and same,
          "; ".join(f"{t} {after[t]['total']}->{third[t]['total']}" for t in ROLE_TABLES))
    check(f"{name}: повтор называет снятое",
          all(f"{t}={after[t]['total']}" in again for t in ROLE_TABLES), written_line(again))
    # Дальнейшие проверки сравнивают id строк, а повтор пересоздал их заново: базой для них
    # является состояние ПОСЛЕ повтора, иначе проба сравнивала бы id двух разных загрузок
    # (числа строк при этом совпадают, и провал выглядел бы дефектом загрузчика).
    return third


def check_kinds_refusals(name, layout):
    """Границы запроса групп: неизвестная группа, пустой запрос, роли без прав."""
    print(f"\n=== границы запроса kinds: {name}")
    text = call(str(layout), None, "roles,prav")
    check(f"{name}: неизвестная группа — отказ с перечнем допустимых",
          text.startswith("❌") and ("Реализованы: " + ", ".join(ROLE_KINDS)) in text,
          (text.splitlines() or [""])[0][:150])
    text = call(str(layout), None, " , ")
    check(f"{name}: пустой kinds — отказ, а не «ничего не делать»",
          text.startswith("❌") and "Пустой kinds" in text,
          (text.splitlines() or [""])[0][:150])
    text = call(str(layout), None, "roles")
    check(f"{name}: roles без role_rights — отказ с причиной (каскад FK)",
          text.startswith("❌") and "role_rights" in text,
          (text.splitlines() or [""])[0][:150])


def check_kinds_templates(name, layout, cfg_uuid, conn, baseline):
    """Одна группа `role_restrictions`: шаблоны перезаписаны, соседние круги не тронуты."""
    print(f"\n=== группа role_restrictions: {name}")
    cur = conn.cursor()
    text = call(str(layout), None, "role_restrictions")
    check(f"{name}: role_restrictions одна — вызов успешен",
          text.startswith("✅"), (text.splitlines() or [""])[0][:150])
    after = table_counts(cur, cfg_uuid)
    if not text.startswith("✅"):
        check(f"{name}: отказ группы шаблонов называет причину", bool(text), text[:150])
        return after
    baseline_templates = baseline[ROLE_TEMPLATES_TABLE]
    written_templates = after[ROLE_TEMPLATES_TABLE]
    if baseline_templates["total"]:
        check(f"{name}: строки шаблонов сняты и записаны заново (id вырос, число то же)",
              written_templates["max_id"] > baseline_templates["max_id"]
              and written_templates["total"] == baseline_templates["total"],
              f"templates {baseline_templates['total']} -> {written_templates['total']}, "
              f"max id {baseline_templates['max_id']} -> {written_templates['max_id']}")
    else:
        # Пустой круг шаблонов — состояние выгрузки (у KomMag нет ни одного
        # <restrictionTemplate>), и id здесь не растёт по той же причине, по какой не
        # растёт число строк: проверять рост не на чем.
        check(f"{name}: круг шаблонов пуст — вызов не записал и не снял ни одной строки",
              written_templates["total"] == 0 and written_templates["max_id"] == 0,
              f"templates {baseline_templates['total']} -> {written_templates['total']}")
        note(f"{name}: шаблонов ограничений в выгрузке нет — рост id для пустого круга "
             "неприменим, это состояние выгрузки, а не пропуск проверки")
    untouched = (ROLE_TABLE, ROLE_RIGHTS_TABLE, ROLE_SOURCES_TABLE)
    check(f"{name}: соседние таблицы не снимались и не записывались",
          all(after[t]["total"] == baseline[t]["total"]
              and after[t]["max_id"] == baseline[t]["max_id"] for t in untouched),
          "; ".join(f"{t} {baseline[t]['total']}/{baseline[t]['max_id']} -> "
                    f"{after[t]['total']}/{after[t]['max_id']}" for t in untouched))
    line = next((l.strip() for l in text.splitlines()
                 if "Группы круга не запрашивались" in l), "")
    check(f"{name}: ответ называет незапрошенные группы и их таблицы",
          bool(line) and ROLE_TABLE in line and ROLE_RIGHTS_TABLE in line, line[:200])
    check(f"{name}: нули незапрошенных таблиц в ответе равны нулям записи",
          all(f"{t}=0" in written_line(text) for t in untouched), written_line(text))
    return after


def check_kinds_rights(name, layout, cfg_uuid, conn, baseline):
    """Одна группа `role_rights`: права дописаны к прежним id ролей, роли не тронуты.

    Второй случай — тот же запрос при отсутствующих строках ролей: круг снимается
    `remove_roles`, вызов обязан отказать и назвать состояние базы, а затем круг
    восстанавливается полным вызовом. Проба не оставляет базу в половинчатом состоянии.
    """
    print(f"\n=== группа role_rights: {name}")
    cur = conn.cursor()
    text = call(str(layout), None, "role_rights")
    check(f"{name}: role_rights одна — вызов успешен",
          text.startswith("✅"), (text.splitlines() or [""])[0][:150])
    after = table_counts(cur, cfg_uuid)
    if text.startswith("✅"):
        check(f"{name}: права записаны тем же числом строк",
              after[ROLE_RIGHTS_TABLE]["total"] == baseline[ROLE_RIGHTS_TABLE]["total"],
              f"rights {baseline[ROLE_RIGHTS_TABLE]['total']} -> "
              f"{after[ROLE_RIGHTS_TABLE]['total']}")
        check(f"{name}: строки ролей не снимались и не перезаписывались (те же id)",
              after[ROLE_TABLE]["total"] == baseline[ROLE_TABLE]["total"]
              and after[ROLE_TABLE]["max_id"] == baseline[ROLE_TABLE]["max_id"]
              and after[ROLE_SOURCES_TABLE]["max_id"] == baseline[ROLE_SOURCES_TABLE]["max_id"],
              f"roles max id {baseline[ROLE_TABLE]['max_id']} -> {after[ROLE_TABLE]['max_id']}")
        check(f"{name}: каждая строка права ссылается на существующую ревизию роли",
              _rights_orphans(cur, cfg_uuid) == 0, _rights_orphans(cur, cfg_uuid))
    else:
        check(f"{name}: отказ группы прав называет причину", bool(text), text[:150])

    # Ролей нет — праву не на что ссылаться: состояние базы называется отказом.
    with transaction() as cur_remove:
        removed = remove_roles(cur_remove, cfg_uuid)
    emptied = table_counts(cur, cfg_uuid)
    check(f"{name}: круг снят пробой (порог нуля для проверки отказа достигнут)",
          all(emptied[t]["total"] == 0 for t in ROLE_TABLES),
          ", ".join(f"{t}={count}" for t, count in removed.items()))
    text = call(str(layout), None, "role_rights")
    check(f"{name}: role_rights без строк ролей — отказ, называющий состояние базы",
          text.startswith("❌") and "без строки роли" in text and "CURRENT" in text,
          (text.splitlines() or [""])[0][:150])
    restored = table_counts(cur, cfg_uuid)
    check(f"{name}: отказ не записал ни одной строки",
          all(restored[t]["total"] == 0 for t in ROLE_TABLES),
          "; ".join(f"{t}={restored[t]['total']}" for t in ROLE_TABLES))
    text = call(str(layout))
    full = table_counts(cur, cfg_uuid)
    check(f"{name}: полный вызов восстанавливает круг после отказа",
          text.startswith("✅") and full[ROLE_TABLE]["total"] == baseline[ROLE_TABLE]["total"]
          and full[ROLE_RIGHTS_TABLE]["total"] == baseline[ROLE_RIGHTS_TABLE]["total"],
          "; ".join(f"{t}={full[t]['total']}" for t in ROLE_TABLES))
    return full


def _rights_orphans(cur, cfg_uuid):
    """Строки прав, не имеющие строки роли в текущем состоянии (их быть не должно)."""
    cur.execute(
        f"SELECT count(*) FROM {ROLE_RIGHTS_TABLE} r "
        f"LEFT JOIN {current_view(ROLE_TABLE)} ro "
        "  ON ro.id = r.role_id AND ro.configuration_uuid = r.configuration_uuid "
        "WHERE r.configuration_uuid = %s::uuid AND ro.id IS NULL", (str(cfg_uuid),))
    return int(cur.fetchone()[0] or 0)


def check_registration():
    """Регистрация `@mcp.tool()` не прячет функцию слоя, и точка входа зовёт слой."""
    print("=== регистрация инструмента ===")
    tool = getattr(SERVER, "load_roles_tool", None)
    check("в сервере есть функция load_roles_tool", callable(tool))
    if not callable(tool):
        return False
    check("точка входа вызывает слой load_roles, а не копию его кода",
          "load_roles" in tool.__code__.co_names
          and "_format_roles_result" in tool.__code__.co_names,
          ", ".join(sorted(n for n in tool.__code__.co_names if "roles" in n)))
    check("параметр kinds описан в докстринге (позиция 2.4 называется там же)",
          "kinds" in (tool.__doc__ or "") and "2.4" in (tool.__doc__ or ""),
          f"докстринг {len(tool.__doc__ or '')} симв.")
    return True


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

        for name, layout, uuid in circles:
            after = check_full_circle(name, layout, uuid, conn)
            if after is None:
                continue
            check_kinds_refusals(name, layout)
            state = check_kinds_templates(name, layout, uuid, conn, after)
            check_kinds_rights(name, layout, uuid, conn, state)

        print("\n=== отказы точки входа ===")
        name, layout, _uuid = circles[0]
        text = call(str(layout), "00000000-0000-0000-0000-000000000000")
        check("расхождение configuration_uuid называется отказом, а не выбором",
              text.startswith("❌") and "configuration_uuid" in text,
              (text.splitlines() or [""])[0][:150])
        check("отказ точки входа называет, чем продолжить (отдельный вход группы)",
              ROLES_REPEAT_HINT in text,
              next((l.strip() for l in text.splitlines()
                    if "load_roles_tool" in l), "")[:170])
        text = call(str(DUMP_ROOT / "MinCfg__нет_такого_каталога"))
        check("нечитаемый каталог выгрузки — отказ слоя, а не падение",
              text.startswith("❌"), (text.splitlines() or [""])[0][:150])

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
    finally:
        conn.close()

    print(f"\nитог: проверок {PASSED}, провалено {FAILED}, замечаний {len(NOTES)}")
    for item in NOTES:
        print("  • " + item)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
