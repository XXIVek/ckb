#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Точечная правка карточек слоя под реализованную остановку конвейера (узел V48, шаг П8).

Что и почему меняется:

1. `rules:core-rules:functional:load-catalog` — пункт 6 описывал правило и называл отставание
   кода («карточка описывает правило и называет расхождение, а не выдаёт текущий код за
   норму»). Отставания нет: остановка реализована, поэтому абзац отставания заменяется
   описанием реализованного контракта (`stopped_stage`, закрытый словарь и форматёр в модуле
   контракта, причина пропуска стадии от загрузчика). В `===CHECK===` вместо замера отставания
   называется проверка `_v48_p8_stop_probe.py`, а зонд остаётся замером состояния кода;
2. `rules:core-rules:functional:goal-and-stages` — перечень стадий не называл S4c (узла V48),
   хотя `STAGES` её содержит: карточка обязана перечислять то, что есть в `STAGES` (пункт 4 той
   же карточки требует брать состояние прогоном). Пункт 3а переписан с «правило + отставание»
   на реализованное поведение и различение двух признаков (остановка ≠ неполнота);
3. `rules:core-rules:functional:add-object-block` — пункт 7 уже требовал участия новой стадии в
   остановке, но оговаривал, что «остановка текущим кодом НЕ реализована (открытый вопрос Q8)».
   Вопрос закрыт и реализован — оговорка удалена, требование осталось.

Скрипт идемпотентен: если новый текст уже в карточке, правка не вносится. Границы заменяемого
фрагмента задаются началом и концом, а не дословным копированием всего абзаца: карточки
перенесли текст с переносами, и дословное совпадение всего абзаца ломалось бы на любой
лишней строке. Требуется ровно одно вхождение каждой границы.

Запуск:

    python _v48_p8_rule_patch.py            # сухо: что будет изменено
    python _v48_p8_rule_patch.py --write    # внести правки
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402

MARKER = "core-rules"
LOAD_CATALOG = f"{RL.functional_prefix(MARKER)}load-catalog"
GOAL_STAGES = f"{RL.functional_prefix(MARKER)}goal-and-stages"
ADD_BLOCK = f"{RL.functional_prefix(MARKER)}add-object-block"

# ── 1. load-catalog: абзац отставания → описание реализованного ─────────────────────
LC_LAG_START = "   Отставание кода названо прямо (замер 29.10.2026"
LC_LAG_END = "а не выдаёт текущий код за норму."
LC_LAG_NEW = """   Реализовано узлом V48, шаг П8 (29.10.2026). Ответ конвейера держит ключ `stopped_stage`:
   адрес остановленной стадии, её причину, перечень стадий, которые не вызывались (`not_run`),
   чем продолжить загрузку и что осталось в базе. Закрытый словарь ответа и текст раздела
   принадлежат контракту (`STOPPED_STAGE_KEYS`, `build_stopped_stage`,
   `format_stopped_stage_lines` в `src/configuration_load_contract.py`); загрузчик пересылает
   причину, названную самой стадией, — второй формулировки об одном отказе в модуле нет.
   Разделы стадий печатаются и при остановке: состояние `not_run` читается именно там. Причину
   пропуска стадии называет загрузчик (`NOT_RUN_STOPPED_REASON`), потому что нулевой ответ
   стадии S4b несёт статус писателя, описывающего запись, а не состояние стадии.
   Признак неполноты состава (`load_incomplete`, `incomplete_groups`) и признак остановки
   (`success: false`, `stopped_stage`) — разные факты и разные ключи ответа: при остановке
   проставляются оба, смешивать их нельзя."""

LC_CHECK_START = ("`python _v48_q8_contract_probe.py` — что конвейер делает при отказе "
                  "стадии сейчас")
LC_CHECK_END = "дублирования определений в модуле контракта (узел V48)."
LC_CHECK_NEW = """`python _v48_p8_stop_probe.py MinCfg` — остановка конвейера на отказе каждой стадии детей:
`success: false`, верный `stopped_stage`, отсутствие вызовов последующих стадий, `not_run` в их
ответах и сохранённые строки заголовка и индекса состава; `python _v48_q8_contract_probe.py` —
замер состояния кода: чем заканчивается каждая ветка отказа, сколько строк `"success": True`
осталось, есть ли признак остановки и дублирования определений в модуле контракта
(узел V48, шаг П8)."""

# ── 2. goal-and-stages: перечень стадий и состояние при остановке ───────────────────
GS_STAGES_OLD = "(часть групп B/E, узел V46) → S4b модули объектов конфигурации (узел V47)"
GS_STAGES_NEW = ("(часть групп B/E, узел V46) → S4c свойства параметров сеанса "
                 "(узел V48, позиция 2.3 нормативного списка) → S4b модули объектов "
                 "конфигурации (узел V47)")

GS_LAG_START = "3а. Отказ любой стадии конвейера останавливает загрузку"
GS_LAG_END = "молчать о втором нельзя."
GS_LAG_NEW = """3а. Отказ любой стадии конвейера останавливает загрузку (решение оператора 29.10.2026;
   реализовано узлом V48, шаг П8): ответ `success: false` с названием остановленной стадии —
   ключ `stopped_stage`, закрытый словарь модуля контракта; стадии после неё не вызываются и
   читаются `not_run` (правило C2); записанное до отказа не откатывается, потому что стадии идут
   после коммита транзакции заголовка, и ответ обязан назвать, что осталось в базе. Продолжение
   загрузки — отдельный вход остановленной стадии, если он есть; у стадии без отдельного входа
   (S4b, решение Q4.1) — только полная перезагрузка. Признак неполноты состава и признак
   остановки — разные ключи ответа, при остановке проставляются оба."""

GS_CHECK_START = ("`python _v48_q8_contract_probe.py` — чем конвейер отвечает на отказ "
                  "стадии сегодня")
GS_CHECK_END = "узел V48."
GS_CHECK_NEW = """`python _v48_p8_stop_probe.py MinCfg` — остановка конвейера по отказу каждой стадии детей и
сохранение записанного до отказа (узел V48, шаг П8); `python _v48_q8_contract_probe.py` —
замер состояния кода конвейера: ветки отказа, признак остановки, дублирования определений
в модуле контракта."""

# ── 3. add-object-block: оговорка о нереализованной остановке снимается ──────────────
AO_LAG_START = "остановка конвейера по первой ошибке текущим кодом НЕ реализована"
AO_LAG_END = "пока не решён)"
AO_LAG_NEW = ("остановка конвейера по первой ошибке реализована узлом V48 (шаг П8) и требует "
              "от каждой новой стадии участия в ней на тех же основаниях")

EDITS = [
    (LOAD_CATALOG, LC_LAG_START, LC_LAG_END, LC_LAG_NEW,
     "пункт 6: отставание кода → реализованный контракт остановки"),
    (LOAD_CATALOG, LC_CHECK_START, LC_CHECK_END, LC_CHECK_NEW,
     "CHECK: проверка остановки вместо замера отставания"),
    (GOAL_STAGES, GS_STAGES_OLD, None, GS_STAGES_NEW,
     "пункт 3: перечень стадий дополнен S4c (узел V48)"),
    (GOAL_STAGES, GS_LAG_START, GS_LAG_END, GS_LAG_NEW,
     "пункт 3а: правило + отставание → реализованное поведение"),
    (GOAL_STAGES, GS_CHECK_START, GS_CHECK_END, GS_CHECK_NEW,
     "CHECK: проверка остановки вместо замера отставания"),
    (ADD_BLOCK, AO_LAG_START, AO_LAG_END, AO_LAG_NEW,
     "пункт 7: оговорка о нереализованной остановке снята"),
]


def replace_span(cur, address, start, end, new, label, dry):
    """Заменить фрагмент карточки по границам начала и конца (по одному вхождению каждой).

    Границы, а не весь абзац: карточки перенесли текст своими переносами, и дословное
    совпадение целого абзаца ломалось бы на любой перенесённой строке. Одно вхождение начала
    обязательно — иначе правка могла бы затронуть не тот фрагмент.
    """
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (address,))
    row = cur.fetchone()
    if not row:
        print(f"⚠️ ОТКАЗ: карточки нет — {address}")
        return False
    text = row["answer"] or ""
    if new in text:
        print(f"без изменений  {address}  правка уже внесена — {label}")
        return True
    if text.count(start) != 1:
        print(f"⚠️ ОТКАЗ {address}: начало фрагмента найдено {text.count(start)} раз "
              f"(нужно одно) — {label}")
        return False
    begin = text.find(start)
    if end is None:
        finish = begin + len(start)
    else:
        finish = text.find(end, begin)
        if finish < 0:
            print(f"⚠️ ОТКАЗ {address}: конец фрагмента не найден — {label}")
            return False
        finish += len(end)
    print(f"{'правка     ' if not dry else 'сухо-правка'}  {address}  "
          f"объём: {len(text)} → {len(text) - (finish - begin) + len(new)} симв. — {label}")
    if not dry:
        cur.execute("UPDATE knowledge_snippets SET answer=%s WHERE id=%s",
                    (text[:begin] + new + text[finish:], row["id"]))
    return True


def main(argv=None):
    dry = "--write" not in (argv or [])
    print("=== правки карточек слоя core-rules под реализованную остановку конвейера ===")
    print("режим:", "сухо (запись не делается)" if dry else "запись")
    ok = True
    with get_cursor() as cur:
        for address, start, end, new, label in EDITS:
            ok = replace_span(cur, address, start, end, new, label, dry) and ok
    print()
    print("итог:", "расхождений нет" if ok else "есть отказы — см. строки ⚠️")
    if dry and ok:
        print("правки не внесены: нужен запуск с --write")
    if not dry and ok:
        print("после записи: python _layer_tree_check.py; "
              "python tools/check_rules_layer.py --layer core-rules")
    print("источник правила: docs/CONFIGURATION_SESSION_PARAMETERS_PLAN.md "
          "(раздел 3 Q8, шаг П8); проверка: _v48_p8_stop_probe.py; "
          "замер состояния кода: _v48_q8_contract_probe.py")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))