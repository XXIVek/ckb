# -*- coding: utf-8 -*-
"""_v53_p6_class_probe.py — чем именно differs число классов: записями или подписками.

Таблица 2.2 плана даёт `cfg:DocumentObject` 11 907, `cfg:CatalogObject` 6 000,
`cfg:InformationRegisterRecordSet` 3 248, а зонд по файлам, разбор и строки БД сходятся на
11 919 / 6 002 / 3 249 (разница 12 / 2 / 1). Гипотеза: числа плана считали НЕ записи блока,
а пары (подписка, класс) — то есть подписка, дважды назвавшая один класс, считалась один раз.
Проверка считает оба числа и называет классы, где они расходятся.

Запуск: python _v53_p6_class_probe.py
"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from external_db import transaction  # noqa: E402

PLAN_TABLE = {"DocumentObject": 11907, "CatalogObject": 6000,
              "InformationRegisterRecordSet": 3248, "ConstantValueManager": 2130,
              "DocumentJournalManager": 27}


def main():
    with transaction() as cur:
        cur.execute("SELECT target_class, count(*) AS rows_total, "
                    "count(DISTINCT event_subscription_id) AS subs, "
                    "count(DISTINCT subscription_full_name || '|' || target_class) AS pairs "
                    "FROM event_subscription_sources GROUP BY target_class "
                    "ORDER BY rows_total DESC")
        rows = [(str(r[0]), int(r[1]), int(r[2]), int(r[3])) for r in cur.fetchall()]
    print(f"классов в строках: {len(rows)}")
    diff_rows, diff_subs = Counter(), Counter()
    for cls, rows_total, subs, pairs in rows[:12]:
        want = PLAN_TABLE.get(cls)
        mark = ""
        if want is not None:
            mark = (" совпадает с записями" if want == rows_total
                    else (" совпадает с подписками" if want == subs else " НЕ совпадает ни с чем"))
        print(f"  {cls}: записей {rows_total}, подписок {subs}, пар {pairs}{mark}")
    for cls, rows_total, subs, _pairs in rows:
        diff_rows[cls] = rows_total - subs
    print("классов, где записей больше, чем подписок: "
          + ", ".join(f"{cls}+{delta}" for cls, delta in sorted(diff_rows.items()) if delta))
    print("суммарная разница записей и подписок: "
          + str(sum(max(0, delta) for delta in diff_rows.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
