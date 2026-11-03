# -*- coding: utf-8 -*-
"""_v54_p5_docstring_fix.py — раскладка абзаца контура 2 шапки проверки V54.

Файл только печатает строки шапки в `_scratch/`: правка делается по фактическим
отступам, а не по тем, что показывает выдача редактора.
"""
from pathlib import Path

P = Path("tools/check_v54_scheduled_jobs.py")
OUT = Path("_scratch/_v54_p5_doc_inspect_out.txt")
NEW = [
    "     Состояния атрибутов записи замкнуты иначе, и это названо отдельной проверкой:",
    "     схема держит перечень ключей jsonb (`..._attribute_states_closed`, два набора",
    "     `ARRAY[...]`) и соответствие состояния колонке — отдельно для дат/времени и для",
    "     целых (`..._datetime_states_match_values`,",
    "     `..._integer_states_match_values`); отдельного CHECK на значения состояний нет",
    "     осознанно (прецедент Q7 узла V50).",
]
text = P.read_text(encoding="utf-8", newline="")
nl = "\r\n" if "\r\n" in text else "\n"
lines = text.splitlines()
start = next(i for i, line in enumerate(lines)
             if line.startswith("      записи замкнуты иначе"))
end = start
while not lines[end].rstrip().endswith("(прецедент Q7 узла V50)."):
    end += 1
lines[start:end + 1] = NEW
P.write_text(nl.join(lines) + nl, encoding="utf-8", newline="")
print(f"[ok] абзац контура 2 переложен: строки {start + 1}..{end + 1} → {len(NEW)}; "
      f"переменная {nl!r}")


