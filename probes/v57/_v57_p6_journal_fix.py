#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""Узел V57, шаг П6: правка порядка абзацев снимка `rules:core-rules:journal:node:v57`.

Шаг `_v57_p6_rules_card.py` вставил абзац П6 перед абзацем П5 «Своя текстовая находка»,
из-за чего в карточке перечень «Что узлом НЕ закрыто» оказался раньше абзаца П6. Порядок
снимка — хронология шагов, поэтому абзац П6 переносится перед перечнем незакрытого, а сам
перечень уже назван П7–П9.

Абзац П6 дополняется позицией, которую прогон П6 вскрыл у соседнего узла: постоянная
проверка `tools/check_v56_functional_options.py` даёт 346 сверок / 2 провала — оба провала
порядок стадий (`s4l` встал между `s4k` и `s4b`). Это дрейф эталонов соседа, а не дефект V56:
прецедент — шаг П5 узла V55 (правка ожиданий V53) и шаг П9 узла V56 (правка ожиданий V55);
закрывается шагами П8/П9 плана узла V57 (раздел 7). Оставить провалы без записи значило бы
спрятать состояние слоя.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python _v57_p6_journal_fix.py            # применяет правку
    python _v57_p6_journal_fix.py --check    # только показывает, что получилось
"""
import sys

sys.path.insert(0, "src")
from mcp_tools_core import _get_pool          # noqa: E402
from mcp_tools_api import update_snippet      # noqa: E402

CARD_ID = 6262
BLOCK_HEAD = "Шаг П6 (05.11.2026) — постоянная проверка узла"
BLOCK_END_MARKER = "Своя текстовая находка шага: аудит"
NOT_CLOSED_HEAD = "Что узлом НЕ закрыто:"

DRIFT_TITLE = "Позиция, которую прогон П6 вскрыл у соседнего узла:"
DRIFT_TEXT = (
    DRIFT_TITLE + "\n"
    "постоянная проверка соседнего узла `tools/check_v56_functional_options.py` после внесения\n"
    "стадии `s4l_functional_options_parameters` даёт 346 сверок / 2 провала; оба провала — порядок\n"
    "стадий: эталон V56 ждёт `s4k → s4b`, а `STAGES` и `stages_after('s4k_functional_options')`\n"
    "теперь называют `s4k → s4l → s4b` (порядок нормативного списка 2.11 → 2.12).\n"
    "Содержимое круга V56 при этом не изменилось — 765 опций и 10 063 цели применения прогон V57\n"
    "не трогает (это отдельная проверка контура 9 проверки V57). Провалы — дрейф эталонов соседа,\n"
    "а не дефект V56: тот же класс правки закрывал шаг П5 узла V55 (ожидания V53) и шаг П9 узла\n"
    "V56 (ожидания V55). Для узла V57 это работа шагов П8/П9 (раздел 7 плана), и в прогоне П6 они\n"
    "названы, а не спрятаны: оставить провал без записи — значит выдать состояние слоя за чистое.")

REASON = ("узел V57 шаг П6: абзац П6 перенесён в хронологический порядок (перед перечнем "
          "«что узлом не закрыто»), перечень назван шагами П7–П9; добавлена позиция о двух "
          "провалах порядка стадий в постоянной проверке соседнего узла V56 — дрейф эталонов, "
          "закрываемый шагами П8/П9 по прецеденту V55/V56")

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
block_start = next((i for i, line in enumerate(lines) if line.startswith(BLOCK_HEAD)), None)
# абзац кончается первым из двух: собственной отметки конца или перечня незакрытого —
# иначе повторный прогон снимал бы вместе с абзацем и перечень (StopIteration на вставке)
after = list(range(block_start + 1, len(lines))) if block_start is not None else []
ends = [i for i in after if lines[i].startswith(BLOCK_END_MARKER)
        or lines[i].startswith(NOT_CLOSED_HEAD)]
block_end = min(ends) if ends else None
not_closed = next((i for i, line in enumerate(lines) if line.startswith(NOT_CLOSED_HEAD)), None)

if block_start is None or block_end is None or not_closed is None:
    print(f" anchors: block={block_start} end={block_end} not_closed={not_closed}")
    sys.exit(1)

if block_start > not_closed:
    print("абзац П6 уже стоит после перечня незакрытого — порядок нарушен, нужен перенос")
else:
    print("абзац П6 уже стоит перед перечнем незакрытого")

block = lines[block_start:block_end]
has_drift = any(DRIFT_TITLE in line for line in block)
if not has_drift:
    block = block + DRIFT_TEXT.split("\n")

# снять блок с прежнего места и вставить перед перечнем незакрытого
rest = lines[:block_start] + lines[block_end:]
target = next(i for i, line in enumerate(rest) if line.startswith(NOT_CLOSED_HEAD))
new_lines = rest[:target] + block + [""] + rest[target:]
new_answer = "\n".join(new_lines).rstrip("\n") + "\n"
while "\n\n\n" in new_answer:                      # пустых строк не удваиваем
    new_answer = new_answer.replace("\n\n\n", "\n\n")

print(f"было: {len(answer)} стало: {len(new_answer)}")
print("дублей абзаца П6:", sum(1 for line in new_lines if line.startswith(BLOCK_HEAD)))
if CHECK_ONLY:
    print("запись не выполнена (--check)")
    sys.exit(0)
if new_answer == answer:
    print("без изменений")
    sys.exit(0)
print(update_snippet(CARD_ID, new_answer=new_answer, reason=REASON))
