#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_v61_p2_doc_fix.py — генерируемые разделы модели входят в постоянную проверку (узел V61, П2).

Зачем. Шаг П2 узла добавляет в `docs/config-scenarios/01_configuration.md` второй
генерируемый раздел — оглавление (его порождает `tools/_make_model_toc.py`). Раздел,
который порождается прогоном, но не сверяется, отстаёт от файла молча: ровно так же
отставал индекс журнала карточек (узел нашёл это шагом П1: карточка называла 96 снимков
при 97 живых). Поэтому оглавление получает сверку пунктом 9 той же постоянной проверки,
что сверяет DDL (пункт 4) и реестр состояния позиций (пункт 8).

README каталога правится в том же шаге: его строка статуса сценария 1 держала третью
копию состояния позиций («реализована загрузка заголовка…») — вместо неё теперь указатель
на генерируемый реестр, и добавлен раздел о том, какие части документов каталога
порождаются прогоном и чем сверяются.

Контракт прогона тот же, что `probes/v61/_v61_p1_model_fix.py`: ровно одно вхождение
старого текста, проверка нового текста до поиска старого, без `--write` — только сверка.

Запуск:  python probes/v61/_v61_p2_doc_fix.py          # сверка
         python probes/v61/_v61_p2_doc_fix.py --write  # правка
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
CHECK = "tools/check_position_frame.py"
README = "docs/config-scenarios/README.md"

EDITS = [
    # ── 1. docstring постоянной проверки: пункт 9 ──────────────────────────────────
    (CHECK,
     "     семью датированными перечнями, и каждый новый узел добавлял следующую копию.\n",
     "     семью датированными перечнями, и каждый новый узел добавлял следующую копию.\n"
     "   9. оглавление разделов модели равно выводу `tools/_make_model_toc.py` (узел V61,\n"
     "      шаг П2) — второй генерируемый раздел того же файла. Генерируемый раздел, который\n"
     "      не сверяется, отстаёт молча: так индекс журнала карточек называл 96 снимков при 97\n"
     "      живых (нашёл прогон узла V61).\n",
     1),

    # ── 2. импорт генератора оглавления ────────────────────────────────────────────
    (CHECK,
     "    MODEL as STATUS_MODEL, extract_block as status_extract, render_block as status_render,\n"
     ")",
     "    MODEL as STATUS_MODEL, extract_block as status_extract, render_block as status_render,\n"
     ")\n"
     "from _make_model_toc import (  # noqa: E402  (узел V61: оглавление разделов модели)\n"
     "    DEFAULT_FILE as TOC_FILE, extract_block as toc_extract, render_block as toc_render,\n"
     ")",
     1),

    # ── 3. main постоянной проверки: пункт 9 ────────────────────────────────────────
    (CHECK,
     "        note(\"FAIL\", \"генератор состояния позиций не выполнил свой прогон\",\n"
     "             f\"{type(exc).__name__}: {exc}\")\n"
     "\n"
     "    print(\"-\" * 78)",
     "        note(\"FAIL\", \"генератор состояния позиций не выполнил свой прогон\",\n"
     "             f\"{type(exc).__name__}: {exc}\")\n"
     "\n"
     "    # 9. оглавление разделов модели = вывод генератора (узел V61, шаг П2).\n"
     "    #    Раздел порождается прогон по заголовкам файла, поэтому сверяется его текст\n"
     "    #    целиком: расхождение значит, что в документе появился раздел и оглавление не\n"
     "    #    перегенерировали, а не что «перечень чуть устарел».\n"
     "    try:\n"
     "        toc_text = (ROOT / TOC_FILE).read_text(encoding=\"utf-8\")\n"
     "        toc_live, toc_want = toc_extract(toc_text), toc_render(toc_text)\n"
     "        if toc_live is None:\n"
     "            check(\"оглавление разделов вставлено в модель\", False,\n"
     "                  f\"маркеров генератора нет в {TOC_FILE}\")\n"
     "        else:\n"
     "            identical = toc_live == toc_want\n"
     "            check(\"оглавление разделов модели = вывод `_make_model_toc.py`\",\n"
     "                  identical,\n"
     "                  \"\" if identical else\n"
     "                  f\"в файле {len(toc_live)} симв., прогон даёт {len(toc_want)} — нужен \"\n"
     "                  \"прогон python tools/_make_model_toc.py --write\")\n"
     "    except Exception as exc:  # noqa: BLE001 — отказ называется, а не роняет прогон\n"
     "        note(\"FAIL\", \"генератор оглавления не выполнил свой прогон\",\n"
     "             f\"{type(exc).__name__}: {exc}\")\n"
     "\n"
     "    print(\"-\" * 78)",
     1),

    # ── 4. README: строка статуса сценария 1 перестаёт быть копией состояния ────────
    (README,
     "| ⚠️ узлы V32+V33: реализована загрузка **заголовка** (`Configuration.xml` → "
     "`configurations`, `src/configuration_loader.py`) и **индекса состава** "
     "(`ConfigDumpInfo.xml` → `configuration_objects`, `src/config_dump_info_parser.py`); "
     "XML объектов и содержимое видов не реализованы. В файле — замер реальной выгрузки "
     "(42 каталога видов метаданных, индекс `ConfigDumpInfo.xml`) и открытые вопросы модели |",
     "| ⚠️ загрузка конфигурации: заголовок и индекс состава (V32–V33), содержимое детей "
     "конфигурации (V46) и 23 позиции нормативного списка (узлы V48–V59). **Актуальное "
     "состояние по всем 47 позициям держит не эта строка, а генерируемый реестр в самом "
     "файле** — его порождает `python ../../tools/_make_position_status.py`; здесь — только "
     "указатель |",
     1),

    # ── 5. README: раздел о генерируемых частях документов ──────────────────────────
    (README,
     "## 🔄 Как использовать",
     "## ⚙️ Что в документах каталога порождается прогоном\n\n"
     "| Файл | Раздел | Чем порождается | Чем сверяется |\n"
     "|---|---|---|---|\n"
     "| `01_configuration.md` | «Состояние позиций нормативного списка» — позиция, вид, "
     "стадия, узел, таблица, витрина, проверка позиции | "
     "`python ../../tools/_make_position_status.py --write` | пункт 8 "
     "`python ../../tools/check_position_frame.py` |\n"
     "| `01_configuration.md` | «Оглавление разделов» | "
     "`python ../../tools/_make_model_toc.py --write` | пункт 9 той же проверки и "
     "`python ../../tools/_make_model_toc.py --check` |\n\n"
     "Править эти разделы руками нельзя: строка реестра или строка оглавления, написанная "
     "от руки, — вторая копия состояния, и она отстаёт от источника при первой же правке кода "
     "(причина тринадцати правок шага П7 узла V58 и отставания индекса журнала карточек, "
     "снятых узлом V61). Прогон обязателен после изменения `STAGES`, спецификации позиций, "
     "живой схемы или заголовков самого документа.\n\n"
     "## 🔄 Как использовать",
     1),
]


def main() -> int:
    write = "--write" in sys.argv[1:]
    applied, already, failures = 0, 0, []

    by_path: dict[str, str] = {}
    for path, old, new, expect in EDITS:
        text = by_path.get(path)
        if text is None:
            text = (ROOT / path).read_text(encoding="utf-8")
            by_path[path] = text
        if new in text:
            already += 1
            print(f"  уже применено: {path}")
            continue
        found = text.count(old)
        if found != expect:
            failures.append(f"{path}: вхождений {found}, ожидалось {expect}")
            print(f"  ❌ {path}: вхождений {found}, ожидалось {expect}")
            continue
        by_path[path] = text.replace(old, new, expect)
        applied += 1
        print(f"  {'применено' if write else 'будет заменено'} ({expect}): {path}")

    if write:
        for path, text in by_path.items():
            (ROOT / path).write_text(text, encoding="utf-8")

    print(f"\nправок: {len(EDITS)}, применено: {applied}, уже применено: {already}, "
          f"провалов: {len(failures)}")
    if failures:
        for failure in failures:
            print("  -", failure)
        return 1
    print("ПРАВОКИ ПРИМЕНЕНЫ" if write else "СВЕРКА: все правки находят по одному вхождению")
    return 0


if __name__ == "__main__":
    sys.exit(main())
