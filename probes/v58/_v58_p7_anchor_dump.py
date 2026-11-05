# -*- coding: utf-8 -*-
"""_v58_p7_anchor_dump.py — снимок живых карточек слоя для сборки правок шага П7 (узел V58).

Только читает. Пишет в `_scratch/v58_anchors.txt` строки карточек, где названы стадии S4l/S4b,
числа перечней слоя и журнала, позиция 2.13 и определяемые типы — по этим строкам собираются
образцы правок `_v58_p7_rules_card.py`. Запуск: `python _v58_p7_anchor_dump.py`.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "tools", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402

CARDS = {
    "layer": "rules:core-rules:",
    "goal": "rules:core-rules:functional:goal-and-stages",
    "loadcat": "rules:core-rules:functional:load-catalog",
    "entry": "rules:core-rules:load-1c-catalog-tool",
    "addobj": "rules:core-rules:functional:add-object-block",
    "jindex": "rules:core-rules:journal:index",
    "v57tool": "rules:core-rules:load-functional-options-parameters-tool",
}
NEEDLE = re.compile(
    r"_v57_p5_rules_card|9[0-9] карточек|\(24 —|S4l|S4b|2\.13|определяем|определённ"
    r"|DefinedTypes|node:v57|load_functional_options_parameters_tool|===TOOLS==="
)

# Точки, где правка узла V58 меняет живой текст (шаг П7): строки перечисления стадий,
# строки чисел и перечень инструментов. Диапазоны даются по снимку `_v58_p7_anchor_dump.py`,
# потому что строки карточек перенесены и правка обязана совпадать посимвольно.
RANGES = {
    "layer": [(94, 100), (68, 72)],
    "goal": [(58, 70), (100, 130)],
    "loadcat": [(30, 40), (45, 52), (85, 92), (155, 169)],
    "entry": [(1, 12), (24, 34)],
    "addobj": [(58, 66), (85, 95)],
    "jindex": [(1, 12), (98, 104)],
}
# Формулировка «определённых типов в выгрузке нет» в живых карточках инструментов после
# узла V58 читается как ложь: замер П0 даёт 2 / 1 / 304 / 513 файла на четырёх выгрузках.
# Снимок даёт точные окрестности каждой фразы — правка обязана совпадать посимвольно.
PHRASE_SCANS = [
    # матрица стадий: рассказ о реестре — чем кончается перечисление узлов V56/V57.
    ("rules:core-rules:functional:goal-and-stages", r"пятнадцат|шестнадцат|V57", 600),
]

# Целые карточки-образцы (структура новой строки снимается с живой карточки того же вида).
SAMPLE_CARDS = [
    "rules:core-rules:journal:node:v57",
]

# Сырые диапазоны строк — то, что правится дословно (таблицы перечней, шапки чисел,
# перечень инструментов). Окна с NEEDLE их не дают: строки таблицы перечня инструментов
# не содержат ключевых слов поиска, а править их нужно целиком.
RAW_RANGES = {
    "layer": [(66, 100)],
    "entry": [(1, 34)],
    "addobj": [(85, 95)],
    "jindex": [(1, 12), (95, 104)],
    "goal": [(62, 67)],
    "loadcat": [(30, 52), (85, 92)],
}
TAIL_CHARS = {"goal": 500}


def windows(line, width=320, rx=None):
    """Окна ±`width` символов вокруг каждого совпадения — точные, как repr строки.

    Целую строку карточки печатать нельзя: строки слоя перенесены и достигают 6600 символов,
    а образец правки должен совпадать посимвольно — repr окна даёт ровно те символы, которые
    потом войдут в `_v58_p9_rules_card.py`. `rx` задаёт образец, отличный от NEEDLE (раздел
    PHRASE_SCANS); окна совпадающих соседних совпадений сливаются.
    """
    out = []
    taken = []
    for m in (rx or NEEDLE).finditer(line):
        start = max(0, m.start() - width)
        end = min(len(line), m.end() + width)
        if taken and start <= taken[-1][1]:
            taken[-1] = (taken[-1][0], max(taken[-1][1], end))
        else:
            taken.append((start, end))
    for start, end in taken:
        out.append(f"    [{start}:{end}] {line[start:end]!r}")
    return out


def main():
    out = ROOT / "_scratch/v58_anchors.txt"
    lines_out = []
    with get_cursor() as cur:
        for key, addr in CARDS.items():
            cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (addr,))
            row = cur.fetchone()
            text = (row["answer"] or "") if row else ""
            lines = text.splitlines()
            lines_out.append(f"##### {key} {addr} total={len(lines)}")
            for start, end in RANGES.get(key, []):
                for i in range(start, min(end, len(lines)) + 1):
                    hit = windows(lines[i - 1])
                    if hit:
                        lines_out.append(f"{key} L{i}: (len {len(lines[i - 1])})")
                        lines_out.extend(hit)
                lines_out.append("  · · ·")
            lines_out.append("")
        lines_out.append("##### PHRASE_SCANS")
        for addr, pattern, width in PHRASE_SCANS:
            cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (addr,))
            row = cur.fetchone()
            text = (row["answer"] or "") if row else ""
            rx = re.compile(pattern)
            hits = windows(text, width, rx)
            lines_out.append(f"--- {addr} /{pattern}/: окон {len(hits)}")
            lines_out.extend(hits)
        # хвост карточки предписания V57 — образец структуры новой карточки V58;
        # печатается целиком, потому что разделы «Границы» и «Что не загружается»
        # держатся в каждой карточке и их надо повторять формой, а не догадкой.
        lines_out.append("")
        lines_out.append("##### TAIL карточки V57 (образец структуры)")
        cur.execute(
            "SELECT answer FROM knowledge_snippets WHERE question=%s",
            (CARDS["v57tool"],),
        )
        row = cur.fetchone()
        tail_lines = (row["answer"] or "").splitlines()
        for i, line in enumerate(tail_lines[-45:], start=len(tail_lines) - 44):
            lines_out.append(f"v57tool L{i}: {line}")
    out.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    print("записано:", out, "строк:", len(lines_out))
    with get_cursor() as cur:
        raw_out = ROOT / "_scratch/v58_raw_ranges.txt"
        raw_lines = []
        for key, addr in CARDS.items():
            if key not in RAW_RANGES:
                continue
            cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (addr,))
            row = cur.fetchone()
            lines = (row["answer"] or "").splitlines()
            raw_lines.append(f"##### {key} {addr} total={len(lines)}")
            for start, end in RAW_RANGES[key]:
                for i in range(start, min(end, len(lines)) + 1):
                    line = lines[i - 1]
                    # очень длинную строку печатаем хвостом: середина уже снята окнами
                    # NEEDLE выше, а место вставки новой позиции — в конце абзаца.
                    limit = TAIL_CHARS.get(key, 0)
                    if limit and len(line) > 1500:
                        raw_lines.append(
                            f"{key} L{i}: (len {len(line)}, хвост {limit}) …{line[-limit:]}"
                        )
                    else:
                        raw_lines.append(f"{key} L{i}: {line}")
                raw_lines.append("  · · ·")
            raw_lines.append("")
        raw_out.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
        print("записано:", raw_out, "строк:", len(raw_lines))
        sample_out = ROOT / "_scratch/v58_samples.txt"
        sample_lines = []
        for addr in SAMPLE_CARDS:
            cur.execute("SELECT answer FROM knowledge_snippets WHERE question=%s", (addr,))
            row = cur.fetchone()
            sample_lines.append(f"##### SAMPLE {addr}")
            sample_lines.extend((row["answer"] or "").splitlines())
            sample_lines.append("")
        sample_out.write_text("\n".join(sample_lines) + "\n", encoding="utf-8")
        print("записано:", sample_out, "строк:", len(sample_lines))
    return 0




if __name__ == "__main__":
    sys.exit(main())
