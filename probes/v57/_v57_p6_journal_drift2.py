#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""Узел V57, шаг П6: дополнить абзац о дрейфе соседей в `rules:core-rules:journal:node:v57`.

Первая правка (`_v57_p6_journal_fix.py`) назвала только два провала порядка стадий в
`tools/check_v56_functional_options.py`. Прогон соседней проверки V55 показал четвёртую
позицию того же шага — состояние базы (строки V47 для ботов сняты полной загрузкой), и она
обязана быть названной в снимке узла: промолчать о провале соседа — значит выдать состояние
слоя за чистое.

Замена идёт по границам абзаца (заголовок → первая пустая строка), повторный прогон ничего не
меняет: наличие `check_v55_bots.py` в абзаце означает, что позиция уже записана.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python _v57_p6_journal_drift2.py [--check]
"""
import sys

sys.path.insert(0, "src")
from mcp_tools_core import _get_pool          # noqa: E402
from mcp_tools_api import update_snippet      # noqa: E402

CARD_ID = 6262
TITLE = "Позиция, которую прогон П6 вскрыл у соседнего узла:"
NEW_BLOCK = """Позиция, которую прогон П6 вскрыл у соседнего узла:
постоянная проверка `tools/check_v56_functional_options.py` после внесения стадии
`s4l_functional_options_parameters` даёт 346 сверок / 2 провала; оба провала — порядок стадий:
эталон V56 ждёт `s4k → s4b`, а `STAGES` и `stages_after('s4k_functional_options')` называют
`s4k → s4l → s4b` (порядок нормативного списка 2.11 → 2.12). Содержимое круга V56 при этом не
изменилось — 765 опций и 10 063 целей применения подтверждает контур 9 проверки V57.
Постоянная проверка `tools/check_v55_bots.py` даёт 234 сверки / 4 провала / 6 пропусков: один —
тот же дрейф порядка (справа от `s4j_bots` ожидается `s4k_functional_options`), три — состояние
базы: `module_loaded` у двух ботов `MinCfg` ложен, и в `v_current_bsl_modules` строк вида
`parent_type = 'bots'` ноль (замер: `bsl_modules` содержит только `configuration_objects`
10 874 и `external_report` 2).
Ни один провал не следует из кода V57: стадия S4l круг V47 не трогает, проверка V57 называет
ноль снятых строк `bsl_modules` и ничего не пишет. Состояние базы оставила полная загрузка
четырёх выгрузок, которую прогоняла проба шага П5, — позиция разобрана узлом V56 (раздел 5
пробы `_v56_p8_stop_probe.py`: «возврат базы в эталонное состояние соседнего узла V55 … полная
загрузка каталога оставляет `bots.module_loaded` ложным, потому что S4j пишется раньше S4b»);
там строки V47 существовали и проба возвращала состояние, а не правила V55, здесь строк V47 для
ботов нет вовсе — значит восстанавливать нечего до повторной загрузки круга V47.
Правки эталонов порядка и возврата базы — работа шагов П8/П9 (патчер прежних стоп-проб к
пятнадцати стадиям, своя проба остановки с разделом возврата базы, итог регрессии). Тот же класс
правки закрывал шаг П5 узла V55 (ожидания V53) и шаг П9 узла V56 (ожидания V55). Промолчать о
чужих провалах на шаге П6 — значит выдать состояние слоя за чистое, поэтому они названы здесь и
в плане узла (раздел 7, абзац П6)."""

REASON = ("узел V57 шаг П6: абзац о дрейфе дополнен позицией проверки V55 (4 провала: порядок "
          "стадий и состояние базы без строк V47 для ботов), названы границы — код V57 круг V47 "
          "не трогает, работа по эталонам и возврату базы относится к П8/П9")

CHECK_ONLY = "--check" in sys.argv[1:]

pool = _get_pool()
conn = pool.getconn()
try:
    with conn.cursor() as cur:
        cur.execute("SELECT answer FROM knowledge_snippets WHERE id = %s", (CARD_ID,))
        answer = cur.fetchone()[0]
finally:
    pool.putconn(conn)

lines = answer.split("\n")
start = next((i for i, line in enumerate(lines) if line.startswith(TITLE)), None)
if start is None:
    print("заголовок абзаца не найден — правка не применялась")
    sys.exit(1)
end = next((i for i in range(start + 1, len(lines)) if not lines[i].strip()), len(lines))
old_block = lines[start:end]
if any("check_v55_bots.py" in line for line in old_block):
    print("позиция V55 уже записана — без изменений")
    sys.exit(0)

new_lines = lines[:start] + NEW_BLOCK.split("\n") + lines[end:]
new_answer = "\n".join(new_lines)
print(f"абзац: было {len(old_block)} строк, стало {len(NEW_BLOCK.splitlines())}")
print(f"карточка: было {len(answer)}, стало {len(new_answer)}")
if CHECK_ONLY:
    print("запись не выполнена (--check)")
    sys.exit(0)
print(update_snippet(CARD_ID, new_answer=new_answer, reason=REASON))
