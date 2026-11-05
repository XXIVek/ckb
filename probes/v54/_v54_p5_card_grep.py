"""Фильтр строк карточки загрузки для замера узла V54 (шаг П5).

Карточку пишет `config_load_router.format_load_result`; здесь из неё берутся только
строки о покрытии содержимого `<ChildObjects>` — те, где карточка перечисляет узлы,
стадии и разделы сохранённых видов, и предупреждения разбора о тех же видах. Строки
пишутся в файл: консоль Windows портит кириллицу, а читать сравнение нужно целиком.
"""
import io
import sys
from pathlib import Path

# фикстура — снятый текст карточки загрузки MinCfg, который читает этот зонд; она лежит рядом
# с зондом, потому что без неё замер шага П5 не воспроизвести. Вывод замера идёт в _scratch/:
# корень не является местом записи
HERE = Path(__file__).resolve().parent
src = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "_v54_p5_card_min.cfg")
dst = sys.argv[2] if len(sys.argv) > 2 else str(HERE.parents[1] / "_scratch" / "_v54_p5_card_lines.txt")
MARKS = ("расклад", "ChildObjects/ScheduledJob", "ChildObjects/EventSubscription",
         "ChildObjects/FilterCriterion")
text = io.open(src, encoding="utf-8").read()
lines = [line for line in text.splitlines() if any(mark in line for mark in MARKS)]
io.open(dst, "w", encoding="utf-8").write("\n\n".join(lines))
print("LINES", len(lines))
