#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Перенос пробы остановки `_v55_p8_stop_probe.py` в `_v56_p8_stop_probe.py` (шаг П8 узла V56).

Приём тот же, что `_v54_p8_probe_gen.py`, `_v55_p8_probe_gen.py` и `_v54_p1_mirror.py`: перенос
делается программно, а не переписыванием от руки — структура пробы остановки у узлов V50–V55
одинаковая (четыре раздела: контракт офлайн, живой конвейер с искусственным отказом стадии,
восстановление полной загрузкой, пустой круг), различаются только имена стадии, круга и чисел.
Карта соответствий ниже покрывает имена.

Почему источник берётся из коммита, а не из рабочего дерева. Рабочая копия
`_v55_p8_stop_probe.py` правится ЭТИМ ЖЕ шагом П8 под четырнадцать стадий и уже содержит
`STAGE_FUNCTIONAL_OPTIONS`, `FUNCTIONAL_OPTIONS_TABLES` и т. п. Карта меняет имена S4j → S4k,
поэтому перенос из изменённого рабочего файла дал бы удвоенные ключи словарей
(`STAGE_FUNCTIONAL_OPTIONS` дважды). Источник — `_scratch/_v55_p8_stop_probe.head.py`, снимок
`git show HEAD:_v55_p8_stop_probe.py` (состояние до шага П8); снимок в репозиторий не входит.

Чем этот перенос отличается от прежних и почему карта не доводится до нуля. Узел V56 меняет
три вещи, которые в тексте V55 являются проверками, а не именами:

  * **круг — ДВЕ таблицы** (`FUNCTIONAL_OPTIONS_TABLES` = `functional_options` +
    `functional_option_content`; круг снятия `FUNCTIONAL_OPTIONS_REMOVE_ORDER` начинается с
    таблицы применения, потому что она снимается каскадом FK): проверка V55 «круг стадии — ОДНА
    таблица» (1.8) переносится не как есть — она становится проверкой порядка снятия;
  * **пустой круг достижим живой выгрузкой** (замер 1.1 плана: 2/0/0/0 файлов регистрации — у
    `KomMag`, `BGU2` и `BP3` каталога вида нет): состояние `directory_missing` читается прогоном
    по настоящей выгрузке, а не фикстурой — как узел V50 на KomMag;
  * **отличия вида от ботов**: вместо ссылки `Picture` и дескрипторов модуля `Ext/Module.bsl`
    у вида ссылка `Location` с тремя формами адреса и перечень применения `<Content>`;
    недоступный индекс состава здесь НЕ является отказом стадии (в отличие от V55, где состояния
    `pending` отклоняются CHECK'ами схемы) — он называется наблюдением, и это проверяется по
    тексту модуля загрузчика.

Специфичное для вида (словари состояний, две таблицы, `Location`, `<Content>`) карта НЕ маппит:
скрипт печатает такие строки их номерами, чтобы несменённая строка не осталась незамеченной,
и правятся они по месту в созданном файле.

Границы: скрипт создаёт файл заново (перезаписывает), источник не меняет, в отчёте называет
каждую подстановку её числом и каждую оставленную строку — своим номером.

Запуск:

    python _v56_p8_probe_gen.py            # отчёт, файл не пишется
    python _v56_p8_probe_gen.py --write    # запись _v56_p8_stop_probe.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SOURCE = ROOT / "_scratch" / "_v55_p8_stop_probe.head.py"
# порождённый зонд — в круге доказательств узла (probes/v56/), а не в корне;
# черновик-образец читается из _scratch/ — это вывод предыдущего замера
TARGET = Path(__file__).resolve().parent / "_v56_p8_stop_probe.py"

# Порядок важен: сначала длинные имена, потом общие (иначе `BOTS_TABLE` съест составное
# `BOTS_TABLES`, а `bots` — составное `bots_defaults`).
MAP = [
    ("configuration_bots_loader", "configuration_functional_options_loader"),
    ("configuration_bots.py", "configuration_functional_options.py"),
    ("CONFIGURATION_BOTS_PLAN", "CONFIGURATION_FUNCTIONAL_OPTIONS_PLAN"),
    ("v_current_bots", "v_current_functional_options"),
    ("BOTS_SECTION_HEADER", "FUNCTIONAL_OPTIONS_SECTION_HEADER"),
    ("BOTS_CIRCLE_BOUNDARY", "FUNCTIONAL_OPTIONS_CIRCLE_BOUNDARY"),
    ("BOTS_REPEAT_HINT", "FUNCTIONAL_OPTIONS_REPEAT_HINT"),
    ("BOTS_REMOVE_ORDER", "FUNCTIONAL_OPTIONS_REMOVE_ORDER"),
    ("BOTS_OBSERVATION_KINDS", "FUNCTIONAL_OPTIONS_OBSERVATION_KINDS"),
    ("BOTS_INDEX_CHECK_STATES", "FUNCTIONAL_OPTIONS_STATE_VOCABULARIES"),
    ("BOTS_META_TAG", "FUNCTIONAL_OPTIONS_META_TAG"),
    ("BOTS_TABLES", "FUNCTIONAL_OPTIONS_TABLES"),
    ("BOTS_TABLE", "FUNCTIONAL_OPTIONS_TABLE"),
    ("BOTS_DIR", "FUNCTIONAL_OPTIONS_DIR"),
    ("BOTS_MODULE_STATES", "FUNCTIONAL_OPTIONS_MODULE_STATES"),
    ("BOTS_PICTURE_STATES", "FUNCTIONAL_OPTIONS_LOCATION_STATES"),
    ("BOT_PROPERTIES", "FUNCTIONAL_OPTION_PROPERTIES"),
    ("bots_state_columns", "functional_options_state_columns"),
    ("format_bots_lines", "format_functional_options_lines"),
    ("bots_defaults", "functional_options_defaults"),
    ("load_bots_tool", "load_functional_options_tool"),
    ("load_bots", "load_functional_options"),
    ("STAGE_BOTS", "STAGE_FUNCTIONAL_OPTIONS"),
    ("bots_written", "functional_options_written"),
    ('"bots"', '"functional_options"'),
    ("Bots", "FunctionalOptions"),
    ("Bot.", "FunctionalOption."),
    ("bots", "functional_options"),
    ("s4j_", "s4k_"),
    ("S4j", "S4k"),
    ("_v55_", "_v56_"),
    ("V55", "V56"),
    ("2.10", "2.11"),
]


# Что осталось в перенесённом файле и подлежит правке по месту: имена круга V55, которых у вида
# нет (картинка, модуль, одна таблица), и прежние ссылки на узел. Печатается номерами строк —
# молчание здесь означало бы «перенос неполный», не названный ответом.
LEFTOVERS = ("Picture", "picture", "Module", "module", "BOT", "Bots", "бот", "картинк",
             "модул", "ОДНА таблица", "одна таблица", "S4j", "V55", "2.10", "bots")


def main() -> int:
    write = "--write" in sys.argv[1:]
    text = SOURCE.read_text(encoding="utf-8")
    counts = []
    for old, new in MAP:
        hits = text.count(old)
        if hits:
            text = text.replace(old, new)
        counts.append((old, new, hits))
    for old, new, hits in counts:
        print(f"  {hits:>4}  {old} → {new}")

    lines = text.splitlines()
    leftover_lines = [(i + 1, line.strip()[:110]) for i, line in enumerate(lines)
                      if any(needle in line for needle in LEFTOVERS)]
    print(f"\nСтрок перенесённого файла: {len(lines)}")
    print(f"Строк с остатками прежних имён (правка по месту): {len(leftover_lines)}")
    for no, line in leftover_lines:
        print(f"  {no:>4}: {line}")
    if not write:
        print("\nРежим отчёта: файл не записан (ключ --write включает запись)")
        return 0
    TARGET.write_text(text + "\n", encoding="utf-8")
    print(f"  записано: {TARGET.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

