#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Прогон узла V46 (поправка D12, 28.10.2026): загрузка обязана писать is_committed = TRUE.

Статическая часть проверки в `tools/check_v19_revisions.py` отвечает на вопрос «значение
выводит точка доступа», но не на вопрос «что реально кладёт в таблицу загрузчик». Здесь
предмет — именно путь загрузки: каталог ставится в базу, и по каждой строке, которую создал
загрузчик, читается признак. Числа называются по каждой таблице отдельно: общий счётчик
скрыл бы таблицу, где признак не проставлен (тот же класс дефекта, что половина круга
версионных таблиц).

Предмет — Test3_Otchet_Null (тот же временный объект, что у `tools/check_v20_config_link.py`):
эталонная пара Test1/Test2 не трогается. Прогон сам себе и ставит предмет, и снимает его:
`force=True` здесь — часть цикла «загрузили и убрали за собой», а не перезапись чужого
результата без спроса оператора (правило R5 применяется к запросу оператора, не к прогону).

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v46_d12_load_probe.py
Код возврата 0 — каждая строка загрузки подтверждена, лишних строк в базе не осталось.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from config_load_router import load_catalog  # noqa: E402
from current_revision import (  # noqa: E402
    OBJECT_VERSIONED_TABLES, current_view,
)
from external_db import transaction  # noqa: E402
from external_report_loader import delete_external_object  # noqa: E402

PROBE_CATALOG = r"C:\1C_LLM\LoadDoc\Test3_Otchet_Null"

PASSED, FAILED = [], []


def check(name, ok, detail=""):
    (PASSED if ok else FAILED).append(name)
    print(("[OK  ] " if ok else "[FAIL] ") + name + ((" — " + str(detail)) if detail else ""))


def note(text):
    print("[NOTE] " + text)


def rows_of(uuid_text):
    """(всего, подтверждено) по каждой версионной таблице для строки этого объекта."""
    result = {}
    with transaction() as cur:
        for table in OBJECT_VERSIONED_TABLES:
            key = "uuid" if table == "external_report" else "parent_uuid"
            cur.execute(
                "SELECT count(*) AS total,"
                " count(*) FILTER (WHERE is_committed) AS confirmed,"
                " count(*) FILTER (WHERE changed_by = 'load') AS by_load"
                " FROM " + current_view(table) + " WHERE " + key + " = %s::uuid",
                (uuid_text,),
            )
            total, confirmed, by_load = cur.fetchone()
            result[table] = (int(total), int(confirmed), int(by_load))
    return result


def main():
    print("ПРОГОН V46 (D12): загрузка подтверждает каждую свою строку")
    print("Предмет: " + PROBE_CATALOG)
    print("")

    loaded = load_catalog(PROBE_CATALOG, force=True)
    ok = bool(loaded.get("success")) and loaded.get("status") in ("loaded", "reloaded")
    check("предмет загружен точкой входа (исход: " + str(loaded.get("status")) + ")", ok)
    uuid_text = str(loaded.get("uuid") or "")
    if not ok or not uuid_text:
        print("ИТОГ: прогон не выполнен — загрузки не было")
        return 1

    counts = rows_of(uuid_text)
    totals = sum(total for total, _c, _l in counts.values())
    unconfirmed = [(table, total, confirmed)
                   for table, (total, confirmed, _l) in counts.items() if total != confirmed]
    not_by_load = [(table, total, by_load)
                   for table, (total, _c, by_load) in counts.items() if total != by_load]
    note("строк создано загрузкой: " + str(totals) + " — "
         + ", ".join(table + " " + str(total) + "/" + str(confirmed)
                     for table, (total, confirmed, _l) in counts.items()))
    check("строки затронуты — предмет непустой", totals > 0, str(totals))
    check("каждая строка загрузки подтверждена (is_committed = true)", not unconfirmed,
          "; ".join(t + " " + str(c) + "/" + str(n) for t, n, c in unconfirmed)
          if unconfirmed else "подтверждено " + str(totals) + " из " + str(totals))
    check("каждая строка названа загрузкой (changed_by = 'load')", not not_by_load,
          "; ".join(t + " " + str(b) + "/" + str(n) for t, n, b in not_by_load)
          if not_by_load else "событие названо у всех")

    removed = delete_external_object(uuid_val=uuid_text)
    check("предмет снят за собой", bool(removed.get("success")),
          removed.get("error") or removed.get("name") or "")
    left = rows_of(uuid_text)
    check("после снятия строк объекта не осталось",
          all(total == 0 for total, _c, _l in left.values()), str(left))

    total_checks = len(PASSED) + len(FAILED)
    print("")
    print("ИТОГ: проверок " + str(total_checks) + ", провалено " + str(len(FAILED)))
    for name in FAILED:
        print("  ПРОВАЛ: " + name)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
