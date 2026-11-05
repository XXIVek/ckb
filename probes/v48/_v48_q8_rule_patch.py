#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Точечные правки трёх карточек слоя `core-rules` под решение оператора Q8 (29.10.2026).

Зачем. Оператор принял сценарий конвейера: «выполняем каждый пункт по очереди, получая в каждом
случае ответ о состоянии выполнения. Если ответ ошибка — загрузка останавливается» — и подтвердил,
что это относится ко всем стадиям, а не к новой одной. Живые карточки слоя этого норматива не
содержат, а две описывают поведение, которое ему противоречит:

  1. `rules:core-rules:functional:load-catalog` — карточка точки входа перечисляет стадии и исходы,
     но не говорит, что происходит при отказе стадии. Замер кода (`_v48_q8_contract_probe.py`,
     29.10.2026): отказ S3 — строка 760, только `warnings.append`; отказ S4 — строка 790, то же;
     отказ S4b — строка 834, `warnings.append` + `load_incomplete`; итог `"success": True` — строки
     443, 855; ключа `stopped_stage` в модуле нет (0 вхождений). Остановка по ошибке в слое заголовка
     при этом уже реализована — строка 626 (отказ разбора индекса состава даёт `return`).
  2. `rules:core-rules:functional:goal-and-stages` — пункт 3 перечисляет стадии; состояние стадий при
     остановке не описано, а `not_run` (правило C2) — единственный способ отличить «не выполнялась»
     от «данных нет» в остановленном прогоне.
  3. `rules:core-rules:functional:add-object-block` — пункт 7 требует своей стадии для новой группы;
     без дополнения новая стадия могла бы привнести собственное поведение при отказе, и в одном
     конвейере оказалось бы два разных. Эту правку несёт источник текста карточки
     `_v48_rules_texts.py` (её записывает `_v48_rules_cards.py --write`); здесь она не дублируется —
     два носителя одного текста разъезжаются при первой же правке.

Порядок норматива и кода: карточка описывает принятое правило и прямо называет, что код ему пока не
соответствует (шаг П8 плана V48). Правило, опережающее код, допустимо и названо; обратное — когда
правило описывает код, а расхождение молчит — нет.

Запуск:
    python _v48_q8_rule_patch.py            # что будет сделано (сухо)
    python _v48_q8_rule_patch.py --write    # записать
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
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
PROBE = "_v48_q8_contract_probe.py"
PLAN_DOC = "docs/CONFIGURATION_SESSION_PARAMETERS_PLAN.md"

# ── 1. load-catalog: поведение конвейера при отказе стадии ───────────────────────────
LC_OLD = """5. Модуль формы хранится в `form_ext.ext`, а не в `bsl_modules` (правило R9); в `bsl_modules` — только
   модули объекта и менеджера из `Ext/`."""
LC_NEW = """5. Модуль формы хранится в `form_ext.ext`, а не в `bsl_modules` (правило R9); в `bsl_modules` — только
   модули объекта и менеджера из `Ext/`.
6. Отказ стадии конвейера конфигурации останавливает загрузку (решение оператора 29.10.2026): ответ
   `success: false` с названием остановленной стадии, последующие стадии не выполняются и читаются
   статусом `not_run` (правило C2), а уже записанные строки заголовка, индекса состава и перечней вида
   не откатываются — стадии идут после коммита транзакции заголовка, поэтому ответ обязан назвать и
   это: «заголовок и индекс состава записаны, состав детей неполон». Продолжение загрузки — отдельный
   вход дозагрузки остановившей стадии, если он есть (для S3 — `load_configuration_root_modules_tool`,
   для S4 — `load_configuration_object_properties_tool`); у стадии без отдельного входа продолжение
   возможно только полной перезагрузкой с `force=True`. Предупреждение без `success: false` отказом
   стадии не является.
   Отставание кода названо прямо (замер 29.10.2026, `_v48_q8_contract_probe.py`): отказ S3 —
   `src/configuration_loader.py:760`, отказ S4 — `:790`, оба дают только предупреждение; отказ S4b —
   `:834`, даёт `load_incomplete`, но итог остаётся `success: true` (`:443`, `:855`); признака
   остановленной стадии в модуле нет. При этом остановка по ошибке для слоя заголовка реализована —
   `:626` (отказ разбора индекса состава даёт `return`). Норматив принимает шаг П8 плана V48; до него
   карточка описывает правило и называет расхождение, а не выдаёт текущий код за норму."""

LC_FORBID_OLD = """===FORBID===
Ставить `force=True` молча;"""
LC_FORBID_NEW = """===FORBID===
Ставить `force=True` молча; выдавать отказ стадии конвейера за предупреждение при продолжении
загрузки (пункт 6 `===MUST===`); называть выполненной стадию, которая не вызывалась из-за остановки
раньше (`not_run`, правило C2);"""

LC_CHECK_OLD = """`python tools/check_mcp_tool_wiring.py` — регистр инструментов; замеры на эталонных выгрузках
`Test1_Otchet` … `Test4_Otchet_Regress`; `check_external_report_*.sql` — покрытие содержимого."""
LC_CHECK_NEW = """`python tools/check_mcp_tool_wiring.py` — регистр инструментов; замеры на эталонных выгрузках
`Test1_Otchet` … `Test4_Otchet_Regress`; `check_external_report_*.sql` — покрытие содержимого;
`python _v48_q8_contract_probe.py` — что конвейер делает при отказе стадии сейчас (ветки отказа S3/S4/
S4b, итоговый `"success": True`, отсутствие признака остановленной стадии) и есть ли остановки в слое
заголовка; дублирования определений в модуле контракта (узел V48)."""

# ── 2. goal-and-stages: состояние стадий при остановке ──────────────────────────────
GS_OLD = """   отдельным вызовом (решение оператора 28.10.2026). Стадия, которая не выполнялась,
   читается статусом `not_run`, а не нулями (правило C2 закрытого контракта)."""
GS_NEW = """   отдельным вызовом (решение оператора 28.10.2026). Стадия, которая не выполнялась,
   читается статусом `not_run`, а не нулями (правило C2 закрытого контракта).
3а. Отказ любой стадии конвейера останавливает загрузку (решение оператора 29.10.2026): ответ
   `success: false` с названием остановленной стадии, стадии после неё — `not_run`, записанное до
   отказа не откатывается (стадии идут после коммита заголовка). Текущий код этого не делает — замер
   `_v48_q8_contract_probe.py`, 29.10.2026: `src/configuration_loader.py:760,790,834,443,855`, ключа
   `stopped_stage` нет. Расхождение закрывает шаг П8 плана V48; до него карточка называет и правило,
   и отставание — молчать о втором нельзя."""

GS_CHECK_OLD = """граница ключа по живым определениям `pg_get_indexdef` (узел V47)."""
GS_CHECK_NEW = """граница ключа по живым определениям `pg_get_indexdef` (узел V47);
`python _v48_q8_contract_probe.py` — чем конвейер отвечает на отказ стадии сегодня и где остановка уже
есть (слой заголовка); узел V48."""

# ── 3. add-object-block: правку несёт _v48_rules_texts.py (пункт 7), здесь её нет ───

EDITS = [
    (LOAD_CATALOG, LC_OLD, LC_NEW, "правило остановки конвейера (пункт 6)"),
    (LOAD_CATALOG, LC_FORBID_OLD, LC_FORBID_NEW, "FORBID: отказ стадии не равен предупреждению"),
    (LOAD_CATALOG, LC_CHECK_OLD, LC_CHECK_NEW, "CHECK: замер отставания кода"),
    (GOAL_STAGES, GS_OLD, GS_NEW, "3а: состояние стадий при остановке"),
    (GOAL_STAGES, GS_CHECK_OLD, GS_CHECK_NEW, "CHECK: замер отставания кода"),
]


def patch(cur, address, old, new, dry, label=""):
    """Точечная правка карточки: требуется ровно одно совпадение, иначе шаг — отказ."""
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (address,))
    row = cur.fetchone()
    if not row:
        print(f"⚠️ ОТКАЗ: карточки нет — {address}")
        return False
    text = row["answer"] or ""
    if new in text:
        print(f"без изменений  {address}  правка уже внесена — {label or old[:40]!r}")
        return True
    hits = text.count(old)
    if hits != 1:
        print(f"⚠️ ОТКАЗ {address}: совпадений {hits} (нужно одно) — {label or old[:40]!r}")
        return False
    print(f"{'правка     ' if not dry else 'сухо-правка'}  {address}  ← {label or old[:60]!r}")
    if not dry:
        cur.execute("UPDATE knowledge_snippets SET answer=%s WHERE id=%s",
                    (text.replace(old, new), row["id"]))
    return True


def main(argv=None):
    dry = "--write" not in (argv or [])
    print("=== правки карточек слоя core-rules под решение оператора Q8 ===")
    print("режим:", "сухо (запись не делается)" if dry else "запись")
    ok = True
    with get_cursor() as cur:
        for address, old, new, label in EDITS:
            ok = patch(cur, address, old, new, dry, label) and ok
    print()
    print("итог:", "расхождений нет" if ok else "есть отказы — см. строки ⚠️")
    if not dry and ok:
        print("после записи: python _layer_tree_check.py; "
              "python tools/check_rules_layer.py --layer core-rules")
    print("источник правила:", PLAN_DOC, "; замер отставания кода:", PROBE)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))



