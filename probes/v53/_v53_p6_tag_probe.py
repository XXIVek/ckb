# -*- coding: utf-8 -*-
"""_v53_p6_tag_probe.py — распределение классов по тегам элемента блока `Source`.

Гипотеза после `_v53_p6_class_probe.py`: числа таблицы 2.2 плана (DocumentObject 11 907,
CatalogObject 6 000, InformationRegisterRecordSet 3 248) отличаются от записей БД
(11 919 / 6 002 / 3 249) ровно на 12 / 2 / 1 — то есть на то число записей этого класса,
которое лежит в элементе `TypeSet`, а не `Type`. Здесь считается разбивка по тегам: если она
подтверждается, план мерил классы по значениям `Type`, а `TypeSet` описывал отдельной
фразой (139 именованных значений — все `DefinedType`), и постоянная проверка обязана держать
разбивку по тегам, а не одно число.

Запуск: python _v53_p6_tag_probe.py
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
        cur.execute("SELECT source_tag, target_class, count(*) AS c "
                    "FROM event_subscription_sources GROUP BY source_tag, target_class")
        rows = [(str(r[0]), str(r[1]), int(r[2])) for r in cur.fetchall()]
    by_tag = {}
    for tag, cls, count in rows:
        by_tag.setdefault(tag, Counter())[cls] = count
    for tag in sorted(by_tag):
        print(f"\nтег {tag}: записей {sum(by_tag[tag].values())}, классов {len(by_tag[tag])}")
        for cls, count in by_tag[tag].most_common(12):
            want = PLAN_TABLE.get(cls)
            note = ""
            if want is not None:
                both = count + by_tag.get("TypeSet" if tag == "Type" else "Type",
                                          Counter()).get(cls, 0)
                note = f"  (всего по обоим тегам {both}, план {want})"
            print(f"  {cls}: {count}{note}")

    # Вторая гипотеза: числа плана считали только ИМЕНОВАННЫЕ значения (`cfg:<Класс>.<Имя>`),
    # а голые (`cfg:<Класс>`, 265 записей корпуса) в таблице классов не учитывались — поэтому
    # классы без голых ссылок (ConstantValueManager, DocumentJournalManager) совпадают ровно,
    # а классы с голыми расходятся на их число.
    with transaction() as cur:
        cur.execute("SELECT target_form, target_class, count(*) AS c "
                    "FROM event_subscription_sources GROUP BY target_form, target_class")
        form_rows = [(str(r[0]), str(r[1]), int(r[2])) for r in cur.fetchall()]
    by_form = {}
    for form, cls, count in form_rows:
        by_form.setdefault(form, Counter())[cls] = count
    print("\nразбивка по форме значения:")
    for form in sorted(by_form):
        print(f"  форма {form}: записей {sum(by_form[form].values())}")
    for cls, want in sorted(PLAN_TABLE.items()):
        named = by_form.get("named", Counter()).get(cls, 0)
        bare = by_form.get("bare", Counter()).get(cls, 0)
        verdict = ("совпадает с именованными" if want == named
                   else ("совпадает со всеми" if want == named + bare else "не совпадает"))
        print(f"  {cls}: именованных {named}, голых {bare}, всего {named + bare}; "
              f"план {want} — {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
