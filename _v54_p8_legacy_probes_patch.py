#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка прежних проб П8 (узлов V48–V53) под состав стадий с S4i (шаг П8 узла V54).

Что делает и почему она обязательна. Узел V54 поставил стадию `s4i_scheduled_jobs` в `STAGES`
между `s4h_event_subscriptions` и `s4b_object_modules`. Прежние пробы остановки держат перебор
стадий детей и словари стадий (`STAGE_KEYS`, `SECTION_HEADERS`, `DEFAULTS`, `STAGE_FUNCTIONS`,
`RESUME_MARKS`, `stage_row_prefix`) — без входа S4i первая же проверка «строки пропущенной
стадии сняты» падает `KeyError: 's4i_scheduled_jobs'` (замер 03.11.2026: проба `_v52` даёт
именно этот отказ, rc=1). Кроме того узлы V50–V53 держат ЯВНЫЕ перечни `stages_after(...)` и
цепочки `ORDER.index(...)` — они и есть критерий П8 («перечень пропущенных считается из
`STAGES`»), поэтому явный перечень обязан называть новый порядок, а не выводиться из того же
`STAGES` (иначе проверка повторяла бы проверяемое).

Границы правки:

  * содержательных проверок чужих узлов скрипт НЕ меняет — добавлены только вход стадии в
    словари, подсчёт круга S4i в `scope_counts`, явные перечни порядка и тексты проверок ровно
    там, где они утверждали число стадий или состав пропущенных;
  * `_v53_p8_stop_probe.py` правится как прежний узел: после отказа S4h конвейер обязан не звать
    ВЕСЬ хвост — и S4i, и S4b, поэтому S4i получает обёртку-шпиона, а перечни пропущенных
    называют две стадии; проверка «текст незакрытой части не обещает 2.9» меняет границу на
    2.10, потому что с узла V54 позиция 2.9 названа закрытой;
  * `_v51_p8_resume_probe.py` не знал ни S4h, ни S4i (правка узла V53 его не касалась) — хвост
    `STAGES` после отказа S4f назван полным списком из четырёх стадий; якорем для его словарей
    служит вход S4g, потому что входов S4h в файле нет вовсе;
  * файл `_v54_p8_stop_probe.py` этой правке не подлежит — он построен под S4i и проверяет её сам;
  * порядок вставок в списки импортов — порядок стадий (S4h → S4i), а не алфавит: перечень
    читается как перечисление круга остановки, и правка должна стоять одной строкой рядом с
    предыдущим узлом;
  * скрипт идемпотентен: уже внесённая строка не вставляется второй раз, а отсутствующий якорь
    называется строкой отчёта, а не молчанием.

Запуск:

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v54_p8_legacy_probes_patch.py            # отчёт без записи
    python _v54_p8_legacy_probes_patch.py --write    # запись

Код возврата 0 — все якоря найдены (или правка уже внесена), и каждая строка S4h в
исправленных файлах имеет парную строку S4i.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

STOP_PROBES = ("_v48_p8_stop_probe.py", "_v49_p8_stop_probe.py", "_v50_p8_stop_probe.py",
               "_v51_p8_stop_probe.py", "_v52_p8_stop_probe.py", "_v53_p8_stop_probe.py")
RESUME_PROBES = ("_v51_p8_resume_probe.py", "_v52_p8_resume_probe.py")
ALL_FILES = STOP_PROBES + RESUME_PROBES

ANCHOR = "STAGE_EVENT_SUBSCRIPTIONS"
NEXT_KEY = "STAGE_SCHEDULED_JOBS"

# Значения словарей стадий: значение якоря S4h → пары (ключ, значение) стадии S4i.
VALUE_MAP = {
    '"event_subscriptions"': [(NEXT_KEY, '"scheduled_jobs"')],
    "EVENT_SUBSCRIPTIONS_SECTION_HEADER": [(NEXT_KEY, "SCHEDULED_JOBS_SECTION_HEADER")],
    "event_subscriptions_defaults": [(NEXT_KEY, "scheduled_jobs_defaults")],
    '"load_event_subscriptions"': [(NEXT_KEY, '"load_scheduled_jobs"')],
    '"load_event_subscriptions_tool"': [(NEXT_KEY, '"load_scheduled_jobs_tool"')],
    '"s4h:"': [(NEXT_KEY, '"s4i:"')],
}
IMPORT_MAP = {
    "STAGE_EVENT_SUBSCRIPTIONS": [NEXT_KEY],
    "EVENT_SUBSCRIPTIONS_SECTION_HEADER": ["SCHEDULED_JOBS_SECTION_HEADER"],
    "EVENT_SUBSCRIPTIONS_TABLES": ["SCHEDULED_JOBS_TABLES"],
    "event_subscriptions_defaults": ["scheduled_jobs_defaults"],
}

# `_v51_p8_resume_probe.py`: хвост `STAGES` после отказа S4f — S4g, S4h, S4i, S4b; якорем
# служит вход S4g, потому что входов S4h в этом файле нет вовсе.
V51_RESUME_VALUE_MAP = {
    '"load_filter_criteria"': [("STAGE_EVENT_SUBSCRIPTIONS", '"load_event_subscriptions"'),
                               (NEXT_KEY, '"load_scheduled_jobs"')],
    "filter_criteria_defaults": [("STAGE_EVENT_SUBSCRIPTIONS", "event_subscriptions_defaults"),
                                 (NEXT_KEY, "scheduled_jobs_defaults")],
}
V51_RESUME_IMPORT_MAP = {
    "STAGE_FILTER_CRITERIA": ["STAGE_EVENT_SUBSCRIPTIONS", NEXT_KEY],
    "filter_criteria_defaults": ["event_subscriptions_defaults", "scheduled_jobs_defaults"],
}

# Класс значения строки словаря: имена стадий, строковые ключи (`"s4h:"`), имена функций.
VAL_CLASS = '[0-9A-Za-z_".:-]+'


def add_stage_entries(lines, anchor, value_map, name, report):
    """После каждой строки словаря вида `ЯКОРЬ: <известное значение>,` вставляет пару S4i.

    Строки словарей стадий (`STAGE_KEYS`, `SECTION_HEADERS`, `DEFAULTS`, `STAGE_FUNCTIONS`,
    `RESUME_MARKS`, префиксов `stage_row_prefix`) оканчиваются якорем — на это смотрит
    регулярное выражение. Уже внесённая пара не вставляется второй раз: проверка читает
    следующие строки, а не весь файл, чтобы то же имя в другом словаре не считалось
    признаком правки.
    """
    pat = re.compile(re.escape(anchor) + ": (?P<val>" + VAL_CLASS + r"),\s*$")
    out = []
    for i, line in enumerate(lines):
        out.append(line)
        m = pat.search(line)
        if not m:
            continue
        val = m.group("val")
        pairs = value_map.get(val)
        if pairs is None:
            continue
        following = "\n".join(lines[i + 1: i + 2 + len(pairs)])
        if all(f"{key}: {value}," in following for key, value in pairs):
            report.append((name, "уже внесено", f"{anchor}: {val}"))
            continue
        ind = line[: len(line) - len(line.lstrip())]
        for key, value in pairs:
            out.append(f"{ind}{key}: {value},")
        report.append((name, "внесено", f"{anchor}: {val}"))
    return out


def add_imports(lines, anchor, import_map, name, report):
    """В списки импортов и в перечни стадий добавляет имена стадии S4i — следом за якорем.

    Правило читает строки, оканчивающиеся именем с запятой: так в перечни `CHILD_STAGES`,
    `LATER_STAGES` и в ожидания `stages_after(...) == [...]` вход S4i встаёт на то же место,
    что и в словари, — правка одна, а не четыре разных.
    """
    pat = re.compile(r"^(?P<ind>[ \t]*)(?P<name>[A-Za-z_]+),\s*$")
    out = []
    for i, line in enumerate(lines):
        out.append(line)
        m = pat.match(line)
        if not m or m.group("name") not in import_map:
            continue
        names = import_map[m.group("name")]
        following = "\n".join(lines[i + 1: i + 2 + len(names)])
        if all(f"{n}," in following for n in names):
            report.append((name, "уже внесено", f"импорт {m.group('name')}"))
            continue
        ind = m.group("ind")
        for n in names:
            out.append(f"{ind}{n},")
        report.append((name, "внесено", f"импорт {m.group('name')}"))
    return out


def duplicate_scope_loop(lines, name, report):
    """Круг S4i в `scope_counts` — копией блока S4h с заменой перечня таблиц и префикса.

    Тело блока копируется, а не переписывается: пробы V51 и V52 считают круг своими
    предикатами (`count_circle_child_rows`, `count_criterion_child_rows`), и переписывание
    потерял бы этот приём.
    """
    if any("for table in SCHEDULED_JOBS_TABLES:" in line for line in lines):
        report.append((name, "уже внесено", "цикл круга S4i"))
        return lines
    out, i, found = [], 0, False
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = re.match(r"^(?P<ind>[ \t]*)for table in EVENT_SUBSCRIPTIONS_TABLES:\s*$", line)
        if not m:
            i += 1
            continue
        ind = m.group("ind")
        j = i + 1
        block = []
        while j < len(lines):
            nxt = lines[j]
            if not nxt.strip():
                after = lines[j + 1] if j + 1 < len(lines) else ""
                if after.strip() and not after.startswith(ind + " "):
                    break
                block.append(nxt)
                j += 1
                continue
            if not nxt.startswith(ind + " "):
                break
            block.append(nxt)
            j += 1
        out.extend(block)
        out.extend([
            f"{ind}# Узел V54 (шаг П8): строки S4i входят в «что осталось в базе» по тому же",
            f"{ind}# правилу — пропущенная стадия не обязана заполнять свои таблицы, и проба",
            f"{ind}# обязана видеть это числом. Своих детей группы A у вида нет (замер 1.2),",
            f"{ind}# круг — две таблицы вида по ноге `configuration_uuid`.",
            f"{ind}for table in SCHEDULED_JOBS_TABLES:",
        ])
        out.extend(b.replace('"s4h:"', '"s4i:"') for b in block)
        report.append((name, "внесено", "цикл круга S4i"))
        found = True
        i = j
    if not found:
        report.append((name, "нет якоря (цикла S4h в файле нет)", "цикл круга S4i"))
    return out


def fix_tail_lists(text, name, report):
    """Явные перечни хвоста `STAGES`: между S4h и S4b вставляется S4i.

    Правила два — строчное и многострочное: перечни в пробах записаны и в одну строку
    (`CHILD_STAGES`, `LATER_STAGES`), и переноской (`stages_after(...) == [...]`). После
    правки якорь перестаёт встречаться, поэтому повторный прогон ничего не меняет.
    """
    single = f"{ANCHOR}, STAGE_OBJECT_MODULES"
    expanded = f"{ANCHOR}, {NEXT_KEY}, STAGE_OBJECT_MODULES"
    hits = text.count(single)
    if hits:
        text = text.replace(single, expanded)
        report.append((name, f"внесено ({hits})", "перечень S4h→S4b (строка)"))
    elif expanded in text:
        report.append((name, "уже внесено", "перечень S4h→S4b (строка)"))
    else:
        report.append((name, "нет якоря (такого перечня одной строкой нет)",
                       "перечень S4h→S4b (строка)"))
    multi = re.compile(re.escape(ANCHOR) + r",\n(?P<ind>[ \t]*)STAGE_OBJECT_MODULES")
    found = multi.findall(text)
    if found:
        text = multi.sub(lambda m: (f"{ANCHOR},\n{m.group('ind')}{NEXT_KEY},\n"
                                    f"{m.group('ind')}STAGE_OBJECT_MODULES"), text)
        report.append((name, f"внесено ({len(found)})", "перечень S4h→S4b (переноской)"))
    else:
        report.append((name, "нет якоря (перечня с переноской нет)",
                       "перечень S4h→S4b (переноской)"))
    return text


def fix_stages_after_anchor(text, name, report):
    """`stages_after(S4h) == [S4b]` → `[S4i, S4b]`: хвост после S4h больше не одна стадия."""
    pat = re.compile(r"(?P<ind>[ \t]*)stages_after\(STAGE_EVENT_SUBSCRIPTIONS\) == "
                     r"\[STAGE_OBJECT_MODULES\]")
    found = pat.findall(text)
    if found:
        def _repl(m):
            ind = m.group("ind") + "    "
            return (f"{m.group('ind')}stages_after(STAGE_EVENT_SUBSCRIPTIONS) == [\n"
                    f"{ind}{NEXT_KEY},\n{ind}STAGE_OBJECT_MODULES]")
        text = pat.sub(_repl, text)
        report.append((name, f"внесено ({len(found)})", "stages_after(S4h)"))
    elif "stages_after(STAGE_EVENT_SUBSCRIPTIONS) == [\n" in text:
        report.append((name, "уже внесено", "stages_after(S4h)"))
    else:
        report.append((name, "нет якоря (сравнения с хвостом S4h в файле нет)",
                       "stages_after(S4h)"))
    return text


def fix_order_chain(text, name, report):
    """Цепочка `ORDER.index(...) + 1 == ORDER.index(...)` получает звено S4i."""
    multi = re.compile(r"ORDER\.index\(STAGE_EVENT_SUBSCRIPTIONS\) \+ 1\n(?P<ind>[ \t]*)== "
                       r"ORDER\.index\(STAGE_OBJECT_MODULES\)")
    found = multi.findall(text)
    if found:
        text = multi.sub(lambda m: ("ORDER.index(STAGE_EVENT_SUBSCRIPTIONS) + 1\n"
                                    f"{m.group('ind')}== ORDER.index({NEXT_KEY})\n"
                                    f"{m.group('ind')}and ORDER.index({NEXT_KEY}) + 1\n"
                                    f"{m.group('ind')}== ORDER.index(STAGE_OBJECT_MODULES)"),
                         text)
        report.append((name, f"внесено ({len(found)})", "цепочка ORDER.index (переноской)"))
    else:
        report.append((name, "нет якоря (цепочки переноской нет)",
                       "цепочка ORDER.index (переноской)"))
    single = ("order.index(STAGE_EVENT_SUBSCRIPTIONS) + 1 == "
              "order.index(STAGE_OBJECT_MODULES)")
    if single in text:
        text = text.replace(
            single,
            "order.index(STAGE_EVENT_SUBSCRIPTIONS) + 1\n"
            "          == order.index(STAGE_SCHEDULED_JOBS)\n"
            "          and order.index(STAGE_SCHEDULED_JOBS) + 1\n"
            "          == order.index(STAGE_OBJECT_MODULES)")
        report.append((name, "внесено (1)", "цепочка order.index (строка)"))
    elif "order.index(STAGE_SCHEDULED_JOBS)" in text:
        report.append((name, "уже внесено", "цепочка order.index (строка)"))
    else:
        report.append((name, "нет якоря (цепочки одной строкой нет)",
                       "цепочка order.index (строка)"))
    return text


# ── тексты проверок там, где проба утверждает число стадий или состав пропущенных ──────────
# Пары (образец, замена, признак уже внесённой правки, метка отчёта). Образцы регулярные:
# формулировки перенесены строками, и «S4h и S4b» встречается как в одну строку, так и с
# закрытием кавычки на предыдущей строке.
TEXT_CLAIMS = [
    (r'S4h и ("?\n?[ \t]*"?)S4b', r'S4h, S4i и \1S4b', 'S4h, S4i и', 'текст: S4h и S4b'),
    (r'ровно ("?\n?[ \t]*"?)S4b', r'ровно \1S4i и S4b', 'ровно S4i и S4b', 'текст: ровно S4b'),
    ('→ S4h → S4b', '→ S4h → S4i → S4b', '→ S4h → S4i', 'текст: стрелки порядка'),
    ('2.8 → модули', '2.8 → 2.9 → модули', '2.8 → 2.9', 'текст: позиции списка'),
    ('между S4g и S4b — порядок', 'между S4g и S4i — порядок', 'между S4g и S4i',
     'текст: место S4h в STAGES'),
    ('S4h между S4g и S4b', 'S4h между S4g и S4i', 'S4h между S4g и S4i', 'текст: вставка S4h'),
    ('у S4h (узел V53) — только S4b.', 'у S4h (узел V53) — S4i и S4b, у S4i (узел V54) — '
     'только S4b.', 'у S4i (узел V54)', 'текст: хвост после S4h'),
    ('у S4h (узел V53) — S4b.', 'у S4h (узел V53) — S4i и S4b, у S4i (узел V54) — S4b.',
     'у S4i (узел V54)', 'текст: хвост после S4h'),
    ('узлы V51, V52 и V53', 'узлы V51, V52, V53 и V54', 'V53 и V54', 'текст: перечень узлов'),
    ('узлы V52 и V53', 'узлы V52, V53 и V54', 'V53 и V54', 'текст: перечень узлов'),
    ('видов V52 и V53', 'видов V52, V53 и V54', 'V53 и V54', 'текст: перечень видов'),
    ('таблицы восьми стадий', 'таблицы девяти стадий', 'таблицы девяти стадий',
     'текст: число стадий в scope_counts'),
    ('из восьми стадий', 'из девяти стадий', 'из девяти стадий', 'текст: число стадий'),
    ('девять стадий, S4g и S4h входят', 'десять стадий, S4g, S4h и S4i входят',
     'десять стадий', 'текст: перечень детей'),
    ('с учётом S4g и S4h', 'с учётом S4g, S4h и S4i', 'с учётом S4g, S4h и S4i',
     'текст: раздел пробы'),
    ('S4g и S4h — вход', 'S4g, S4h и S4i — вход', 'S4g, S4h и S4i — вход',
     'текст: пропущенные после S4f'),
    ('`s4h_event_subscriptions` и `s4b_object_modules`',
     '`s4h_event_subscriptions`, `s4i_scheduled_jobs` и `s4b_object_modules`',
     's4i_scheduled_jobs', 'текст: хвост в docstring'),
    ('пропущенную S4b', 'пропущенные S4i и S4b', 'пропущенные S4i и S4b',
     'текст: строка пропуска'),
    ('пропуск S4b словами', 'пропуски S4i и S4b словами', 'пропуски S4i и S4b словами',
     'текст: строка пропуска'),
    ('S4b не вызывалась вовсе', 'S4i и S4b не вызывались вовсе', 'S4i и S4b не вызывались',
     'текст: счётчик вызовов'),
]

# Точные правки, вносимые ДО общих правил: они переписывают формулировку целиком, иначе общее
# правило оставило бы фразу, приписывающую вставку S4i не тому узлу.
SPECIFIC = {}
SPECIFIC["_v52_p8_stop_probe.py"] = [
    ('check("1.12б `s4g_filter_criteria`: после отказа пропущенными названы S4h и S4b — узел V53 "\n'
     '      "поставил стадию S4h между S4g и S4b (критерий П8, узлы V52 и V53)",',
     'check("1.12б `s4g_filter_criteria`: после отказа пропущенными названы S4h, S4i и S4b — "\n'
     '      "узлы V53 и V54 поставили стадии после S4g (критерий П8, узлы V52, V53 и V54)",'),
    ('      and len(CHILD_STAGES) == 9 and STAGE_FILTER_CRITERIA in CHILD_STAGES\n'
     '      and STAGE_EVENT_SUBSCRIPTIONS in CHILD_STAGES',
     '      and len(CHILD_STAGES) == 10 and STAGE_FILTER_CRITERIA in CHILD_STAGES\n'
     '      and STAGE_EVENT_SUBSCRIPTIONS in CHILD_STAGES\n'
     '      and STAGE_SCHEDULED_JOBS in CHILD_STAGES'),
    ('# Стадии детей конвейера в порядке `STAGES` — тот же порядок, что у нормативного списка\n'
     '# (2.1–2.2, 2.3, 2.4, 2.5, 2.6, 2.7, модули Ext/). Перебор намеренно полный: решение Q8\n'
     '# узла V48 принято «ко всем стадиям детей», и проверка одной стадии таким ответом не является.\n'
     '# Узел V52 добавляет восьмую стадию — S4g (позиция 2.7); перечень берётся из `STAGES`',
     '# Стадии детей конвейера в порядке `STAGES` — тот же порядок, что у нормативного списка\n'
     '# (2.1–2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, модули Ext/). Перебор намеренно полный:\n'
     '# решение Q8 узла V48 принято «ко всем стадиям детей», и проверка одной стадии таким\n'
     '# ответом не является. Узел V52 добавлял восьмую стадию — S4g (позиция 2.7), узел V53 —\n'
     '# девятую S4h (2.8), узел V54 добавляет десятую — S4i (позиция 2.9); перечень берётся из\n'
     '# `STAGES`'),
]
SPECIFIC["_v50_p8_stop_probe.py"] = [
    ('# Стадии детей конвейера в порядке `STAGES` — тот же порядок, что у нормативного списка\n'
     '# (2.1–2.2, 2.3, 2.4, 2.5, 2.6, модули Ext/). Перебор намеренно полный: решение Q8 узла V48\n'
     '# принято «ко всем стадиям», и проверка одной стадии таким ответом не является. Узел V50\n'
     '# добавлял в этот перечень шестую стадию — S4e; узел V51 добавлял седьмую — S4f (позиция\n'
     '# 2.6); узел V52 добавляет восьмую — S4g (позиция 2.7). Отсутствие любой из них в перечне и',
     '# Стадии детей конвейера в порядке `STAGES` — тот же порядок, что у нормативного списка\n'
     '# (2.1–2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, модули Ext/). Перебор намеренно полный:\n'
     '# решение Q8 узла V48 принято «ко всем стадиям», и проверка одной стадии таким ответом не\n'
     '# является. Узел V50 добавлял в этот перечень шестую стадию — S4e; узел V51 добавлял\n'
     '# седьмую — S4f (позиция 2.6); узел V52 добавлял восьмую — S4g (позиция 2.7); узел V53\n'
     '# добавлял девятую — S4h (2.8); узел V54 добавляет десятую — S4i (позиция 2.9). Отсутствие\n'
     '# любой из них в перечне и'),
]
SPECIFIC["_v51_p8_stop_probe.py"] = [
    ('# Стадии детей конвейера в порядке `STAGES` — тот же порядок, что у нормативного списка\n'
     '# (2.1–2.2, 2.3, 2.4, 2.5, 2.6, 2.7, модули Ext/). Перебор намеренно полный: решение Q8\n'
     '# узла V48 принято «ко всем стадиям», и проверка одной стадии таким ответом не является.\n'
     '# Узел V51 добавлял в перечень седьмую стадию — S4f; узел V52 добавляет восьмую — S4g\n'
     '# (позиция 2.7). Отсутствие любой из них и было бы пропущенным входом вида в останов',
     '# Стадии детей конвейера в порядке `STAGES` — тот же порядок, что у нормативного списка\n'
     '# (2.1–2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, модули Ext/). Перебор намеренно полный:\n'
     '# решение Q8 узла V48 принято «ко всем стадиям», и проверка одной стадии таким ответом не\n'
     '# является. Узел V51 добавлял в перечень седьмую стадию — S4f; узел V52 добавлял восьмую —\n'
     '# S4g (позиция 2.7); узел V53 добавлял девятую — S4h (2.8); узел V54 добавляет десятую —\n'
     '# S4i (позиция 2.9). Отсутствие любой из них и было бы пропущенным входом вида в останов'),
]
SPECIFIC["_v51_p8_resume_probe.py"] = [
    ('# обёртка, которая зовёт настоящую функцию и помечает вызов в `calls`. S4g стоит между S4f\n'
     '# и S4b с узла V52 (шаг П5), и пропуск только S4b ничего бы не доказал: отказ S4f обязан\n'
     '# снять со вызовов весь хвост `STAGES`.',
     '# обёртка, которая зовёт настоящую функцию и помечает вызов в `calls`. S4g стоит между S4f\n'
     '# и S4b с узла V52 (шаг П5), S4h внесён узлом V53, S4i — узлом V54, и пропуск одной только\n'
     '# S4b ничего бы не доказал: отказ S4f обязан снять со вызовов весь хвост `STAGES`.'),
    ('LATER_STAGES = (STAGE_FILTER_CRITERIA, STAGE_OBJECT_MODULES)',
     'LATER_STAGES = (STAGE_FILTER_CRITERIA, STAGE_EVENT_SUBSCRIPTIONS,\n'
     '                STAGE_SCHEDULED_JOBS, STAGE_OBJECT_MODULES)'),
    ('        check("2.2 хвост `STAGES` после отказа S4f не вызывался — ни S4g критериев отбора "\n'
     '              "(узел V52, стадия между S4f и S4b), ни S4b модулей объектов",',
     '        check("2.2 хвост `STAGES` после отказа S4f не вызывался — ни S4g критериев отбора "\n'
     '              "(узел V52), ни S4h подписок на события (узел V53), ни S4i регламентных "\n'
     '              "заданий (узел V54), ни S4b модулей объектов",'),
]
SPECIFIC["_v52_p8_resume_probe.py"] = [
    ('   пустым успехом (иначе остановка была бы на более ранней стадии), S4h и S4b — обёртками\n'
     '   со счётчиком (их вызов после отказа и есть поломка механизма; узел V53 добавил в\n'
     '   перечень вторую пропущенную стадию — S4h);',
     '   пустым успехом (иначе остановка была бы на более ранней стадии), S4h, S4i и S4b —\n'
     '   обёртками со счётчиком (их вызов после отказа и есть поломка механизма; узел V53 добавил\n'
     '   в перечень вторую пропущенную стадию — S4h, узел V54 добавил третью — S4i);'),
    ('              and f"{SKIPPED_PHRASE}: {STAGE_OBJECT_MODULES} — "\n'
     '              f"{stage_title(STAGE_OBJECT_MODULES)}" in card,',
     '              and f"{SKIPPED_PHRASE}: {STAGE_SCHEDULED_JOBS} — "\n'
     '              f"{stage_title(STAGE_SCHEDULED_JOBS)}" in card\n'
     '              and f"{SKIPPED_PHRASE}: {STAGE_OBJECT_MODULES} — "\n'
     '              f"{stage_title(STAGE_OBJECT_MODULES)}" in card,'),
]
SPECIFIC["_v53_p8_stop_probe.py"] = [
    ('  * стадия `s4h_event_subscriptions` стоит в `STAGES` между `s4g_filter_criteria` (2.7) и\n'
     '    `s4b_object_modules` — порядок стадий повторяет порядок нормативного списка (2.8 сразу за\n'
     '    2.7), иначе остановка пропускает позиции, стоящие раньше ошибки;\n'
     '  * `stages_after` для S4g обязан содержать `s4h_event_subscriptions`, а для S4h — только S4b:',
     '  * стадия `s4h_event_subscriptions` стоит в `STAGES` между `s4g_filter_criteria` (2.7) и\n'
     '    `s4i_scheduled_jobs` (узел V54, позиция 2.9) — порядок стадий повторяет порядок\n'
     '    нормативного списка (2.8 сразу за 2.7), иначе остановка пропускает позиции, стоящие\n'
     '    раньше ошибки;\n'
     '  * `stages_after` для S4g обязан содержать `s4h_event_subscriptions`, а для S4h —\n'
     '    `s4i_scheduled_jobs` и `s4b_object_modules`:'),
    ('  * последующая S4b не вызывается вовсе и читается `not_run` (правило C2), а строки круга вида,',
     '  * последующие S4i и S4b не вызываются вовсе и читаются `not_run` (правило C2), а строки\n'
     '    круга вида,'),
    ('  1 — контракт офлайн (без БД): порядок `STAGES` и `stages_after` с учётом S4h, закрытость',
     '  1 — контракт офлайн (без БД): порядок `STAGES` и `stages_after` с учётом S4h и S4i,\n'
     '      закрытость'),
    ('      на ней, `not_run` у S4b, вызов S4b отсутствует (счётчик вызовов, а не совпадение со',
     '      на ней, `not_run` у S4i и S4b, вызовы S4i и S4b отсутствуют (счётчик вызовов, а не\n'
     '      совпадение со'),
    ('# копии). S4b НЕ подменяется ответом: после отказа S4h она обязана не вызываться, и доказывается',
     '# копии). S4i и S4b НЕ подменяются ответом: после отказа S4h они обязаны не вызываться, и\n'
     '# доказывается'),
    ('LATER_STAGES = (STAGE_OBJECT_MODULES,)',
     'LATER_STAGES = (STAGE_SCHEDULED_JOBS, STAGE_OBJECT_MODULES,)'),
    ('    check("1.6 незакрытая часть (`CHILD_NOT_IMPLEMENTED`) называет позицию 2.8 закрытой для этого "\n'
     '          "вида и не обещает закрытости остальных позиций списка",\n'
     '          "2.8" in CHILD_NOT_IMPLEMENTED and "2.9" not in CHILD_NOT_IMPLEMENTED,',
     '    check("1.6 незакрытая часть (`CHILD_NOT_IMPLEMENTED`) называет позицию 2.8 закрытой для этого "\n'
     '          "вида и не обещает закрытости остальных позиций списка; с узла V54 текст называет "\n'
     '          "закрытой и позицию 2.9, поэтому граница перечня сдвинута на 2.10",\n'
     '          "2.8" in CHILD_NOT_IMPLEMENTED and "2.9" in CHILD_NOT_IMPLEMENTED\n'
     '          and "2.10" not in CHILD_NOT_IMPLEMENTED,'),
    ('              and [item.get("stage") for item in stopped.get("not_run_stages") or []]\n'
     '                  == [STAGE_OBJECT_MODULES]',
     '              and [item.get("stage") for item in stopped.get("not_run_stages") or []]\n'
     '                  == [STAGE_SCHEDULED_JOBS, STAGE_OBJECT_MODULES]'),
    ('              calls.get(STAGE_EVENT_SUBSCRIPTIONS) == 1 and STAGE_OBJECT_MODULES not in calls,',
     '              calls.get(STAGE_EVENT_SUBSCRIPTIONS) == 1 and STAGE_OBJECT_MODULES not in calls\n'
     '              and STAGE_SCHEDULED_JOBS not in calls,'),
    ('              STOP_STAGE_SECTION_HEADER in card and STAGE_EVENT_SUBSCRIPTIONS in card\n'
     '              and SKIPPED_PHRASE in card and stage_title(STAGE_OBJECT_MODULES) in card,',
     '              STOP_STAGE_SECTION_HEADER in card and STAGE_EVENT_SUBSCRIPTIONS in card\n'
     '              and SKIPPED_PHRASE in card and stage_title(STAGE_OBJECT_MODULES) in card\n'
     '              and stage_title(STAGE_SCHEDULED_JOBS) in card,'),
]


def apply_pairs(text, pairs, name, report):
    """Один проход точных пар (до общих правил): каждая старая строка встречается ровно разу.

    Уже внесённая правка не считается отказом (идемпотентность): признаком служит вставленный
    фрагмент — новое минус старое, когда старое является частью нового. Отсутствие обоих —
    отказ с началом старого фрагмента: молча пропущенная правка означала бы прогон пробы по
    устаревшему составу стадий.
    """
    for old, new in pairs:
        if old in new:
            fragment = new.replace(old, "")
            if fragment and fragment in text:
                report.append((name, "уже внесено", old.splitlines()[0][:62]))
                continue
        hits = text.count(old)
        if hits == 1:
            text = text.replace(old, new, 1)
            report.append((name, "внесено", old.splitlines()[0][:62]))
        elif hits == 0 and new in text:
            report.append((name, "уже внесено", old.splitlines()[0][:62]))
        else:
            report.append((name, f"ОТСУТСТВУЕТ ЯКОРЬ (встреч: {hits})",
                           old.splitlines()[0][:62]))
    return text


def apply_text_claims(text, name, report):
    """Формулировки проверок, утверждающие число стадий или состав пропущенных.

    Отсутствующий образец — норма: большинство формулировок относятся только к части проб, и
    молчание здесь было бы правдой, а не отказом. Строку отчёта дают только внесённая правка
    и уже внесённая.
    """
    for pattern, repl, marker, label in TEXT_CLAIMS:
        hits = len(re.findall(pattern, text))
        if hits:
            text = re.sub(pattern, repl, text)
            report.append((name, f"внесено ({hits})", label))
        elif marker in text:
            report.append((name, "уже внесено", label))
    return text


def verify(text, name, anchor, value_map, import_map, report):
    """Сверка результата: у каждой строки якоря обязана быть парная строка S4i.

    Именно этот шаг отличает «правка внесена» от «правка внесена полностью»: проба с неполным
    словарём падает в живой части `KeyError`, и молчаливый пропуск якоря был бы найден не
    здесь, а прогоном на минуту позже.
    """
    lines = text.split("\n")
    entry = re.compile(re.escape(anchor) + ": (?P<val>" + VAL_CLASS + r"),\s*$")
    for i, line in enumerate(lines):
        m = entry.search(line)
        if not m or m.group("val") not in value_map:
            continue
        window = "\n".join(lines[i + 1: i + 4])
        for key, value in value_map[m.group("val")]:
            if f"{key}: {value}," not in window:
                report.append((name, "НЕ СОЙШЛОСЬ (нет пары)",
                               f"{anchor}: {m.group('val')} → {key}"))
    bare = re.compile(r"^[ \t]*(?P<name>[A-Za-z_]+),\s*$")
    for i, line in enumerate(lines):
        m = bare.match(line)
        if not m or m.group("name") not in import_map:
            continue
        window = "\n".join(lines[i + 1: i + 4])
        for n in import_map[m.group("name")]:
            if f"{n}," not in window:
                report.append((name, "НЕ СОЙШЛОСЬ (нет импорта)", f"{m.group('name')} → {n}"))
    if ("for table in EVENT_SUBSCRIPTIONS_TABLES:" in text
            and "for table in SCHEDULED_JOBS_TABLES:" not in text):
        report.append((name, "НЕ СОЙШЛОСЬ", "цикл круга S4i"))
    residues = [
        (f"{ANCHOR}, STAGE_OBJECT_MODULES", "перечень S4h→S4b (остаток)"),
        ("stages_after(STAGE_EVENT_SUBSCRIPTIONS) == [STAGE_OBJECT_MODULES]",
         "stages_after(S4h) (остаток)"),
        ("ORDER.index(STAGE_EVENT_SUBSCRIPTIONS) + 1 == ORDER.index(STAGE_OBJECT_MODULES)",
         "цепочка ORDER.index (остаток)"),
        ("order.index(STAGE_EVENT_SUBSCRIPTIONS) + 1 == order.index(STAGE_OBJECT_MODULES)",
         "цепочка order.index (остаток)"),
        ("LATER_STAGES = (STAGE_OBJECT_MODULES,)", "LATER_STAGES (остаток)"),
    ]
    for residue, label in residues:
        if residue in text:
            report.append((name, "НЕ СОЙШЛОСЬ", label))
    if re.search(r"ORDER\.index\(STAGE_EVENT_SUBSCRIPTIONS\) \+ 1\n[ \t]*== "
                 r"ORDER\.index\(STAGE_OBJECT_MODULES\)", text):
        report.append((name, "НЕ СОЙШЛОСЬ", "цепочка ORDER.index переноской (остаток)"))


def process(name, report):
    """Один файл: сначала точные пары, затем общие правила, затем сверка полноты."""
    path = ROOT / name
    text = path.read_text(encoding="utf-8")
    if name == "_v51_p8_resume_probe.py":
        anchor, value_map, import_map = ("STAGE_FILTER_CRITERIA", V51_RESUME_VALUE_MAP,
                                         V51_RESUME_IMPORT_MAP)
    else:
        anchor, value_map, import_map = ANCHOR, VALUE_MAP, IMPORT_MAP
    text = apply_pairs(text, SPECIFIC.get(name, []), name, report)
    lines = text.split("\n")
    lines = add_imports(lines, anchor, import_map, name, report)
    lines = add_stage_entries(lines, anchor, value_map, name, report)
    lines = duplicate_scope_loop(lines, name, report)
    text = "\n".join(lines)
    text = fix_tail_lists(text, name, report)
    text = fix_stages_after_anchor(text, name, report)
    text = fix_order_chain(text, name, report)
    text = apply_text_claims(text, name, report)
    verify(text, name, anchor, value_map, import_map, report)
    return text


def main() -> int:
    write = "--write" in sys.argv[1:]
    report = []
    changed = {}
    for name in ALL_FILES:
        path = ROOT / name
        if not path.exists():
            report.append((name, "ОТСУТСТВУЕТ ФАЙЛ", ""))
            continue
        original = path.read_text(encoding="utf-8")
        text = process(name, report)
        if text != original:
            changed[name] = text
    bad = [row for row in report if row[1].startswith(("ОТСУТСТВУЕТ", "НЕ СОЙШЛОСЬ"))]
    for row in report:
        print(f"  [{row[1]}] {row[0]} :: {row[2]}")
    print(f"\nСтрок отчёта: {len(report)}; отказов: {len(bad)}; файлов с правками: "
          f"{len(changed)}")
    if bad:
        print("ЯКОРЯ НЕ СОШЛИСЬ — файл перечитывают: тексты проверок меняются узлами")
        return 1
    if not write:
        print("Режим отчёта: ни один файл не записан (ключ --write включает запись)")
        return 0
    for name, text in changed.items():
        (ROOT / name).write_text(text, encoding="utf-8")
        print(f"  записано: {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())







