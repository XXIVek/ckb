#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/check_v19_revisions.py — проверка SQL-формы разрешения детей через манифест (узел V19).

Зачем. С узла V19 «текущий состав» объекта считает манифест текущей ревизии родителя
(M5, A1), и канал у этого один — `src/current_revision.py` (S3, S4). 18.10.2026 этот канал
ломался молча: выражение `key = ANY((SELECT m.module_paths FROM ...))` Postgres читает НЕ
как «ключ входит в массив», а как форму подзапроса `= ANY (SELECT ...)`, где строкой
подзапроса оказывается весь массив (`text[]`/`uuid[]`) — ошибка «оператор равен ANY, но типы
text[] и text различаются». Неотловленная ошибка не локальна месту сравнения: падает вся
команда, а `find_external_object` читает это как «строки нет». Практика дня: загрузка
теряла идемпотентность (повтор давал `duplicate key` вместо `⚠️ уже загружено`), уборка
прогона не снимала свою тестовую строку, а сверка счётников после прогона расходилась.

Что проверяет этот скрипт:
  1. статическая форма: для шести таблиц `current_child_count_sql` НЕ содержит сломанной
     формы `= ANY((SELECT m.<колонка>` и сравнивает ключ с множеством элементов
     (`= ANY((SELECT unnest(...))`); генератор множества один — `manifest_member_set_sql`;
  2. живая БД: для каждого объекта текущего состояния все шесть выражений выполняются и
     дают неотрицательное число (при сломанной форме выражение не вернулось бы вовсе);
  3. разрешение не «тихо ноль»: строгий счёт (по манифесту) равен и числу членов этого
     вида в манифесте, и числу строк текущей ревизии по `parent_uuid`. Нужны именно все
     три числа: два равных нуля маскировали бы дефект, при котором дети в состав не
     разрешаются. У form_ext ожидаемое число — строки ревизии (состава формы в манифесте
     нет, M3), члены формы дают только верхнюю границу;
  4. вариант `include_without_manifest=True` (снимки до V19) выполняется и для объекта
     с записанным манифестом совпадает со строгим счётом; у объекта без манифеста
     (снимок до V19) строгий счёт обязан быть 0, а свободный — фактическими строками:
     подменять одно другим нельзя;
  5. сломанная форма действительно падает на живой БД — сторож из группы 1 охраняет
     существующий дефект, а не выдуманное ограничение;
  6. если в базе нет ни одного объекта с записанным манифестом (только снимки до V19),
     скрипт грузит временный предмет (TSD_0), проверяет строгий путь на нём и снимает его
     за собой: без предмета строгий путь не был бы проверен вовсе.

Чего скрипт НЕ проверяет: цепочки ревизий (M1), снятие ребёнка новой ревизией (M4), сброс
истории при `force=True` (M7). Полная регрессия ревизий добавляется вместе с завершением
узла V19; здесь зафиксирована граница «SQL разрешения детей собирается и работает».

Эталонная пара (Test1_Otchet, Test2_Otchet) не трогается: скрипт только читает БД.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python tools/check_v19_revisions.py
Код возврата 0 — все проверки пройдены.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

try:  # кириллица и эмодзи в консоли Windows (cp1251) — как в остальных валидаторах
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import psycopg2  # noqa: E402

from current_revision import (  # noqa: E402
    CURRENT_VIEWS, MANIFEST_VIEW, MODULE_KEY_EXPR, current_child_count_sql, current_view,
    manifest_array_sql, manifest_member_set_sql, uuid_literal,
)
from config_load_router import load_catalog  # noqa: E402
from external_db import transaction  # noqa: E402
from external_report_loader import delete_external_object  # noqa: E402

# Каталог-предмет для строгого пути: нужен только если в базе нет ни одного объекта с
# записанным манифестом (иначе проверяется только состояние снимка до V19). Берётся внешняя
# обработка TSD_0 — тот же предмет и тот же порядок «загрузил и снял за собой», что у
# _v22_probe.py: она не входит в эталонную пару и даёт непустой состав (реквизиты, ТЧ,
# формы, описания форм, макеты, модуль), то есть проверяет все шесть выражений на числах
# больше нуля.
SUBJECT_CATALOG = r"C:\1C_LLM\LoadDoc\TSD_0"

# Порядок общий с генератором: form_ext идёт после forms, потому что его текущность
# следует из form_uuids (ключа form_ext в манифеста нет — M3).
TABLES = ("attributes", "tabular_sections", "forms", "form_ext", "templates", "bsl_modules")

# Вид манифеста, ключом которого ребёнок входит в состав (словарь _MEMBERSHIP из
# src/current_revision.py). У form_ext своей ключевой цепи нет — его текущность следует из
# формы (form_uuids), поэтому ожидаемым числом для него являются строки текущей ревизии,
# а члены формы задают только верхнюю границу.
MANIFEST_KIND_OF = {
    "attributes": "attribute_uuids",
    "tabular_sections": "tabular_section_uuids",
    "forms": "form_uuids",
    "form_ext": "form_uuids",
    "templates": "template_uuids",
    "bsl_modules": "module_paths",
}

# Таблицы, где число строк текущего состояния равно числу членов манифеста по построению
# загрузки (родитель и дети пишутся из одного контракта). form_ext здесь отсутствует
# осознанно: описаний форм может быть меньше, чем форм в составе.
ONE_TO_ONE = ("attributes", "tabular_sections", "forms", "templates", "bsl_modules")

PASSED, FAILED = [], []


def check(name, ok, detail=""):
    (PASSED if ok else FAILED).append(name)
    print(("[OK  ] " if ok else "[FAIL] ") + name + (((" — " + str(detail)) if detail else "")))


def note(text):
    print("[NOTE] " + text)


def q(sql, params=None):
    with transaction() as cur:
        cur.execute(sql, params if isinstance(params, dict) else tuple(params or ()))
        if not cur.description:
            return []
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def one(sql, params=None):
    rows = q(sql, params)
    return list(rows[0].values())[0] if rows else None


def first_line(exc):
    text = str(exc).strip()
    return text.splitlines()[0] if text else "ошибка без текста"


def scalar(expr):
    """Выполнить скалярное выражение, вернув (значение, текст_ошибки).

    Отдельная функция, а не `one()`: текстом ошибки отвечает на вопрос «выражение не
    собралось или состав пуст» — ровно то различие, которое сломанная форма стирала.
    """
    try:
        return int(one("SELECT " + expr) or 0), None
    except psycopg2.Error as exc:
        return None, first_line(exc)


def count_children_view_sql(table, uuid_expr):
    """Сколько строк ТЕКУЩЕЙ ревизии указывает на объект (счёт без манифеста)."""
    return ("(SELECT COUNT(*) FROM " + current_view(table) + " c"
            " WHERE c.parent_uuid = " + uuid_expr + ")")


def manifest_len_sql(kind, uuid_expr):
    """Сколько членов вида kind заявляет манифест (array_length — скалярная форма массива)."""
    return "(SELECT COALESCE(array_length(" + manifest_array_sql(kind, uuid_expr) + ", 1), 0))"


def ts_columns_len_sql(uuid_expr):
    """Сколько колонок у табличных частей, входящих в состав (column_uuids, M3).

    Колонки ТЧ в манифест заголовка не кладутся намеренно: их перечень принадлежит самой
    ТЧ, поэтому ожидаемое число реквизитов — реквизиты объекта плюс колонки названных ТЧ.
    Не-массив в column_uuids даёт 0, а не ошибку: пустой перечень — состояние, а не сбой.
    """
    return ("(SELECT COALESCE(SUM(CASE WHEN jsonb_typeof(t.column_uuids) = 'array'"
            " THEN jsonb_array_length(t.column_uuids) ELSE 0 END), 0) FROM "
            + CURRENT_VIEWS["tabular_sections"] + " t WHERE t.parent_uuid = " + uuid_expr +
            " AND t.uuid = ANY(" +
            manifest_member_set_sql("tabular_section_uuids", uuid_expr) + "))")


def manifest_recorded_sql(uuid_expr):
    """Есть ли у текущей ревизии объекта записанный манифест (M3, состояние до V19).

    Витрина отдаёт строку и для снимка без манифеста, поэтому различие читается по
    колонке `manifest_missing`, а не по числу членов: пустой перечень — заявленный пустой
    состав, отсутствующий — «состава мы не заявляли».
    """
    return ("(SELECT COALESCE(NOT m.manifest_missing, FALSE) FROM " + MANIFEST_VIEW +
            " m WHERE m.object_uuid = " + uuid_expr + ")")


def broken_form_sql(table, uuid_expr):
    """Дословно та форма, что ломала канал до правки: `= ANY(` + manifest_array_sql + `)`.

    Источник — тот же, что у исправного выражения (витрина манифеста), иначе негатив
    проверял бы другую ошибку: у витрины заголовка колонок состава нет, и падение
    «нет такой колонки» охраняло бы не тот дефект, а опечатку в имени.
    """
    key = MODULE_KEY_EXPR if table == "bsl_modules" else "c.uuid"
    return ("(SELECT COUNT(*) FROM " + current_view(table) + " c WHERE c.parent_uuid = " +
            uuid_expr + " AND (" + key + ") = ANY(" +
            manifest_array_sql(MANIFEST_KIND_OF[table], uuid_expr) + "))")


def current_objects():
    """Объекты текущего состояния и признак «манифест состава записан» (M3).

    Флаг читается выражением из `current_revision`, а не своей выборкой: тест обязан
    проверять ровно тот канал, которым пользуется прод.
    """
    rows = q("SELECT t.uuid::text AS uuid, COALESCE(t.name, '') AS name"
             " FROM " + CURRENT_VIEWS["external_report"] + " t ORDER BY 2")
    for row in rows:
        recorded, err = scalar(manifest_recorded_sql(uuid_literal(row["uuid"])))
        row["manifest_recorded"] = None if err is not None else bool(recorded)
    return rows


def load_subject():
    """Загрузить предмет строгой проверки, если в базе нет объекта с манифестом.

    Снимки, загруженные до V19, манифеста не несут: строгий путь на них даёт законный
    ноль, и проверка группы 3 не проверяла бы ничего. Предмет снимается за собой.
    """
    res = load_catalog(SUBJECT_CATALOG)
    if res.get("status") == "duplicate":
        note("тот же uuid уже в базе без манифеста — он перезагружается force=True,")
        note("чтобы строка получила манифест состава (M3); старая запись при этом снимается")
        res = load_catalog(SUBJECT_CATALOG, force=True)
    if not res.get("success"):
        note("ответ загрузки: " + str(res.get("status")) + " " +
             str(res.get("error") or "")[:200])
    return res


def main():
    print("ПРОВЕРКА V19 — РАЗРЕШЕНИЕ СОСТАВА ЧЕРЕЗ МАНИФЕСТ ТЕКУЩЕЙ РЕВИЗИИ")
    print("Модель: docs/CONFIGURATIONS_ENRICHMENT_PLAN.md, раздел 11 (M5, A1, S3, S4)")
    print("")

    print("1. СТАТИЧЕСКАЯ ФОРМА ВЫРАЖЕНИЙ (без обращения к БД)")
    uuid_expr = "CAST('00000000-0000-0000-0000-000000000000' AS uuid)"
    for table in TABLES:
        sql = current_child_count_sql(table, uuid_expr)
        kind = MANIFEST_KIND_OF[table]
        broken = "= ANY(" + manifest_array_sql(kind, uuid_expr) + ")"
        fixed = "= ANY(" + manifest_member_set_sql(kind, uuid_expr) + ")"
        check(table + ": сломанной формы ANY(<массив>) в выражении нет", broken not in sql, broken[:90])
        check(table + ": ключ сравнивается со множеством элементов (unnest)", fixed in sql, fixed[:90])
        check(table + ": выражение остаётся скаляром COUNT(*)",
              sql.startswith("(SELECT COUNT(*) FROM " + CURRENT_VIEWS[table] + " c"), sql[:70])
        if table == "bsl_modules":
            # Манифест пишет Python, а `_key_list()` сохраняет ключи строчными. SQL без
            # нормализации регистра сравнил бы `...Ext/ObjectModule.bsl` со строчным
            # элементом перечня и потерял бы модуль из состава при исправном манифесте
            # (замер 18.10.2026: строгий счёт = 0 при члене манифеста = 1).
            check("bsl_modules: ключ модуля нормализует регистр и пробелы (как _key_list)",
                  "LOWER(BTRIM(" in sql.upper(), sql[:120])
    src_root = Path(ROOT / "src")
    check("генератор множества один (manifest_member_set_sql)",
          "manifest_member_set_sql(" in (src_root / "current_revision.py").read_text(encoding="utf-8"))
    check("единственный канал — current_child_count_sql, своего SQL у вызывающих нет",
          "current_child_count_sql(" in (src_root / "external_report_loader.py").read_text(encoding="utf-8"))
    print("")

    print("2. ЖИВАЯ БД: ОБЪЕКТЫ ТЕКУЩЕГО СОСТОЯНИЯ И ИХ МАНИФЕСТЫ")
    objects = current_objects()
    note("объектов текущего состояния в базе: " + str(len(objects)))
    for obj in objects:
        note("  " + obj["name"] + " — манифест " +
             ("записан" if obj["manifest_recorded"] else "НЕ записан (снимок до узла V19)"))
    created = []
    if not any(obj["manifest_recorded"] for obj in objects):
        note("ни одна строка не несёт манифеста (загружена до V19): строгий путь на них даёт")
        note("законный ноль, поэтому он проверяется на временном предмете " + SUBJECT_CATALOG)
        res = load_subject()
        ok = bool(res.get("success")) and res.get("status") in ("loaded", "reloaded")
        check("временный предмет загружен (исход: " + str(res.get("status")) + ")", ok)
        if ok:
            created.append(str(res.get("uuid")))
            objects = current_objects()
            mine = [o for o in objects if o["uuid"] == str(res.get("uuid"))]
            check("загрузка записала манифест состава (M3)",
                  bool(mine) and mine[0]["manifest_recorded"],
                  "uuid=" + str(res.get("uuid")))
    print("")

    print("3. РАЗРЕШЕНИЕ СОСТАВА ПО ТЕКУЩЕМУ СОСТОЯНИЮ")
    pairs = 0
    for obj in objects:
        uid, name, recorded = obj["uuid"], obj["name"], obj["manifest_recorded"]
        lit = uuid_literal(uid)
        tag = name if recorded else name + " [снимок до V19]"
        for table in TABLES:
            strict, err = scalar(current_child_count_sql(table, lit))
            check(tag + " / " + table + ": выражение выполняется", err is None,
                  err or ("строго=" + str(strict)))
            if err is not None:
                continue
            rows, err2 = scalar(count_children_view_sql(table, lit))
            check(tag + " / " + table + ": строки текущей ревизии считаются", err2 is None,
                  err2 or ("строк=" + str(rows)))
            if err2 is not None:
                continue
            loose, err3 = scalar(current_child_count_sql(table, lit, include_without_manifest=True))
            check(tag + " / " + table + ": свободный счёт (снимки до V19) читается", err3 is None,
                  err3 or ("свободный=" + str(loose)))
            if err3 is not None:
                continue
            members, err4 = scalar(manifest_len_sql(MANIFEST_KIND_OF[table], lit))
            check(tag + " / " + table + ": члены манифеста считаются", err4 is None,
                  err4 or ("членов=" + str(members)))
            if err4 is not None:
                continue
            expected = members
            if table == "attributes":
                cols, err5 = scalar(ts_columns_len_sql(lit))
                check(tag + " / attributes: колонки ТЧ добавлены в ожидание", err5 is None,
                      err5 or ("колонок=" + str(cols)))
                if err5 is None:
                    expected = members + cols
            both = "строгий=" + str(strict) + ", свободный=" + str(loose) + \
                   ", манифест=" + str(expected) + ", строк=" + str(rows)
            if recorded:
                if table in ONE_TO_ONE:
                    check(tag + " / " + table + ": состав разрешается не «тихо ноль»",
                          strict == expected == rows and loose == strict, both)
                else:
                    check(tag + " / form_ext: описание формы разрешается по её составу",
                          strict == rows and strict <= members and loose == strict, both)
            else:
                check(tag + " / " + table + ": снимок до V19 — строго 0, свободный = строки",
                      strict == 0 and members == 0 and loose == rows, both)
            pairs += 1
    check("предмет проверки был — связок «объект × таблица»", pairs > 0, str(pairs))
    print("")

    print("4. НЕГАТИВ: СЛОМАННАЯ ФОРМА ПАДАЕТ НА ЖИВОЙ БД")
    if objects:
        uid, name = objects[-1]["uuid"], objects[-1]["name"]
        lit = uuid_literal(uid)
        for table in ("attributes", "bsl_modules"):
            _, err = scalar(broken_form_sql(table, lit))
            check(name + " / " + table + ": форма ANY(<массив>) отклоняется Postgres",
                  err is not None, err or "выражение почему-то выполнилось")
    else:
        check("в базе есть объект для негативной проверки", False, "база пуста")
    note("сломанная форма не «даёт ноль», а роняет всю команду: find_external_object читал")
    note("это как «строки нет» — идемпотентность загрузки пропадала молча")
    print("")

    print("5. УБОРКА ЗА СОБОЙ")
    for uid in created:
        res = delete_external_object(uuid_val=uid, obj_type="external_processing")
        check("временный предмет снят", isinstance(res, dict) and bool(res.get("success")),
              str(res.get("error") or res.get("name") or res)[:160])
    left = [o["name"] for o in current_objects() if o["uuid"] in created]
    check("временных объектов в базе не осталось", not left, str(left))
    print("")

    total = len(PASSED) + len(FAILED)
    print("ИТОГ: проверок " + str(total) + ", провалено " + str(len(FAILED)))
    for name_ in FAILED:
        print("  ПРОВАЛ: " + name_)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

