#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_v61_p3_snapshot_marks.py — датированные снимки замеров перестают притворяться актуальными.

Узел V61, шаг П3 (06.11.2026). План шага был «вынести замерные разделы в
docs/config-scenarios/measurements/». Замер перед правкой (тот же приём, что шаги П0 и П2
этого узла: сначала мера, потом правка) показал цену, которой план не учитывал:

  * замерная часть раздела «Структура конфигурации: что подтверждается выгрузкой» —
    12 726 симв. (161 строка), а не ~22 КБ: четверть веса раздела — генерируемый реестр
    состояния позиций (шаг П1), который выносить нельзя; это 4.6 % файла;
  * на выносимые подразделы ведут 8 текстовых указателей: пять в планах закрытых узлов
    (`CONFIGURATION_BOTS_PLAN.md`, `CONFIGURATION_EVENT_SUBSCRIPTIONS_PLAN.md`,
    `CONFIGURATION_FILTER_CRITERIA_PLAN.md`,
    `CONFIGURATION_FUNCTIONAL_OPTIONS_PARAMETERS_PLAN.md`, `CONFIGURATION_SCHEDULED_JOBS_PLAN.md`
    — все они говорят «подраздел "Покрытие XSD слоем проекта"») и три внутри самой модели.
    Планы закрытых узлов — история, её не переписывают.

То есть вынос дал бы восемь указателей, ведущих «в другой файл», против 4.6 % объёма. Шаг
исполняется в другой форме: разделы остаются на месте, но получают явную пометку
датированного снимка, а README каталога — их перечень. Дефект, который снимает шаг, — не
объём файла, а читатель, который не может понять, актуален ли раздел: дата стоит в
заголовке, но не говорит, чем заменить устаревшее.

Контракт прогона тот же, что `probes/v61/_v61_p1_model_fix.py` и `_v61_p2_doc_fix.py`:
одно вхождение старого текста, проверка нового текста до поиска старого, без `--write` —
только сверка.

Запуск:  python probes/v61/_v61_p3_snapshot_marks.py          # сверка
         python probes/v61/_v61_p3_snapshot_marks.py --write  # правка
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
MODEL = "docs/config-scenarios/01_configuration.md"
README = "docs/config-scenarios/README.md"

STRUCTURE_HEADING = ("## 🗂 Структура конфигурации: что подтверждается выгрузкой "
                     "(замер 17.10.2026)")
MINCFG_HEADING = "## 📏 Эталон минимальной конфигурации `MinCfg` (замер 19.10.2026)"
XSD_HEADING = "### Покрытие XSD слоем проекта"

STRUCTURE_MARK = (
    "\n> 📅 **Раздел — снимок замеров, а не описание текущего кода.** Дата в заголовке "
    "стоит намеренно:\n"
    "> раздел фиксирует состояние XML-выгрузки BGU2 и слоя `xsd-schemas/2.20/` на "
    "17.10.2026 и не\n"
    "> обновляется. Актуальное состояние по позициям нормативного списка — генерируемый "
    "реестр\n"
    "> «Состояние позиций нормативного списка» ниже, его порождает "
    "`python tools/_make_position_status.py`;\n"
    "> что закрыто кодом — реестр `STAGES` и постоянные проверки `tools/check_v*.py`. "
    "Перечень снимков\n"
    "> этого файла — в `README.md` каталога.\n")

MINCFG_MARK = (
    "\n> 📅 **Раздел — снимок эталона на дату замера.** Фикстуру `MinCfg` менял оператор: "
    "19.10.2026,\n"
    "> 21.10.2026 (46 каталогов + `Ext/`, индекс 243 записи) и тот же день 18:41 "
    "(47 каталогов,\n"
    "> индекс 264 записи) — срезы названы подразделами ниже и тоже не обновляются. "
    "Актуальный круг\n"
    "> эталонного набора по выгрузкам измеряют пробы узлов и "
    "`tools/check_position_frame.py`, а не\n> этот раздел.\n")

XSD_MARK = (
    "\n> 📅 Снимок на 17.10.2026 с уточнениями 02.11.2026, 03.11.2026 и 04.11.2026 (они в\n"
    "> тексте подраздела). Подраздел оставлен на месте и не выносится в отдельный файл: на "
    "него\n"
    "> ссылаются пять планов закрытых узлов, перенос оборвался бы восемью указателями —\n"
    "> замер шага П3 узла V61 от 06.11.2026.\n")

SNAPSHOT_SECTION = (
    "## 📅 Датированные снимки замеров в документах каталога\n\n"
    "Разделы ниже фиксируют состояние выгрузок на дату заголовка и **не обновляются**: "
    "править такой\nраздел — значит получить описание, которое уже не про текущую "
    "выгрузку. Они оставлены на месте\nнамеренно: на них ссылаются планы закрытых узлов, а "
    "перенос оборвался бы восемью\nуказателями при 4.6 % объёма файла (замер шага П3 узла "
    "V61, 06.11.2026). Актуальное\nсостояние держат прогоны, а не эти разделы.\n\n"
    "| Документ | Раздел | Дата снимка | Чем меряется актуальное состояние |\n"
    "|---|---|---|---|\n"
    "| `01_configuration.md` | «🗂 Структура конфигурации: что подтверждается выгрузкой» | "
    "17.10.2026 | реестр «Состояние позиций нормативного списка» в том же файле: "
    "`python ../../tools/_make_position_status.py` |\n"
    "| `01_configuration.md` | подраздел «Покрытие XSD слоем проекта» | 17.10.2026, "
    "уточнения 02–04.11.2026 | слой `xsd-schemas/` и `python ../../tools/check_xml_format_layer.py` |\n"
    "| `01_configuration.md` | «📏 Эталон минимальной конфигурации `MinCfg`» | 19.10.2026, "
    "срезы 21.10.2026 | `python ../../tools/check_position_frame.py` — круг по четырём "
    "выгрузкам |\n\n"
    "Признак снимка — дата в заголовке и пометка «📅» в начале раздела. Новый датированный\n"
    "раздел, который планируют не обновлять, обязан получить обе отметки и строку этой "
    "таблицы.\n\n"
    "## 🔄 Как использовать")

EDITS = [
    (MODEL, STRUCTURE_HEADING + "\n", STRUCTURE_HEADING + "\n" + STRUCTURE_MARK, 1),
    (MODEL, MINCFG_HEADING + "\n", MINCFG_HEADING + "\n" + MINCFG_MARK, 1),
    (MODEL, XSD_HEADING + "\n", XSD_HEADING + "\n" + XSD_MARK, 1),
    (README, "## 🔄 Как использовать", SNAPSHOT_SECTION, 1),
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
