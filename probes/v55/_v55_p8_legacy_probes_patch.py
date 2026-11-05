#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка прежних проб П8 (узлов V48–V54) под состав стадий с S4j (шаг П8 узла V55).

Зачем она обязательна. Узел V55 поставил стадию `s4j_bots` в `STAGES` между
`s4i_scheduled_jobs` и `s4b_object_modules`. Прежние пробы остановки держат перебор стадий
детей и словари стадий (`STAGE_KEYS`, `SECTION_HEADERS`, `DEFAULTS`, `STAGE_FUNCTIONS`,
`RESUME_MARKS`, `stage_row_prefix`) — без входа S4j первая же проверка «строки пропущенной
стадии сняты» падает `KeyError: 's4j_bots'`. Кроме того узлы V50–V54 держат явные перечни
`stages_after(...)`, кортежи `CHILD_STAGES`/`LATER_STAGES` и цепочки `ORDER.index(...)`:
именно они и есть критерий П8 («перечень пропущенных считается из `STAGES`»), поэтому
явный перечень обязан называть новый порядок, а не выводиться из того же `STAGES`.

Границы правки:

  * содержательных проверок чужих узлов скрипт НЕ меняет — добавлены только вход стадии в
    словари и импорты, подсчёт круга S4j в `scope_counts`, явные перечни порядка и тексты
    проверок ровно там, где они утверждали число стадий или состав пропущенных;
  * `_v54_p8_stop_probe.py` правится как прежний узел: после отказа S4i конвейер обязан не
    звать ВЕСЬ хвост — и S4j, и S4b; проверка «текст незакрытой части не обещает 2.10»
    меняет границу на 2.11, потому что с узла V55 позиция 2.10 названа закрытой;
  * круг стадии — одна таблица `bots` (узел V55, `BOTS_TABLES == BOTS_REMOVE_ORDER`), поэтому
    цикл `scope_counts` копируется блоком, а не переписывается: предикат чужих проб
    сохраняется;
  * порядок вставок — порядок стадий (S4i → S4j), а не алфавит;
  * скрипт идемпотентен: уже внесённая строка не вставляется второй раз, отсутствующий якорь
    называется строкой отчёта, а не молчанием.

Запуск:

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v55_p8_legacy_probes_patch.py            # отчёт без записи
    python _v55_p8_legacy_probes_patch.py --write    # запись

Код возврата 0 — все якоря найдены (или правка уже внесена).
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

STOP_PROBES = ("_v48_p8_stop_probe.py", "_v49_p8_stop_probe.py", "_v50_p8_stop_probe.py",
               "_v51_p8_stop_probe.py", "_v52_p8_stop_probe.py", "_v53_p8_stop_probe.py",
               "_v54_p8_stop_probe.py")
RESUME_PROBES = ("_v51_p8_resume_probe.py", "_v52_p8_resume_probe.py")
ALL_FILES = STOP_PROBES + RESUME_PROBES

ANCHOR = "STAGE_SCHEDULED_JOBS"
NEXT_KEY = "STAGE_BOTS"

# Значения словарей стадий: значение якоря S4i → пары (ключ, значение) стадии S4j.
VALUE_MAP = {
    '"scheduled_jobs"': [(NEXT_KEY, '"bots"')],
    "SCHEDULED_JOBS_SECTION_HEADER": [(NEXT_KEY, "BOTS_SECTION_HEADER")],
    "scheduled_jobs_defaults": [(NEXT_KEY, "bots_defaults")],
    '"load_scheduled_jobs"': [(NEXT_KEY, '"load_bots"')],
    '"load_scheduled_jobs_tool"': [(NEXT_KEY, '"load_bots_tool"')],
    '"s4i:"': [(NEXT_KEY, '"s4j:"')],
}
IMPORT_MAP = {
    "STAGE_SCHEDULED_JOBS": [NEXT_KEY],
    "SCHEDULED_JOBS_SECTION_HEADER": ["BOTS_SECTION_HEADER"],
    "SCHEDULED_JOBS_TABLES": ["BOTS_TABLES"],
    "scheduled_jobs_defaults": ["bots_defaults"],
}

# Класс значения строки словаря: имена стадий, строковые ключи (`"s4i:"`), имена функций.
VAL_CLASS = '[0-9A-Za-z_".:-]+'


def add_stage_entries(lines, anchor, value_map, name, report):
    """После каждой строки словаря вида `ЯКОРЬ: <известное значение>,` вставляет пару S4j.

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
    """В списки импортов и в перечни стадий добавляет имена стадии S4j — следом за якорем.

    Правило читает строки, оканчивающиеся именем с запятой: так в перечни `CHILD_STAGES`,
    `LATER_STAGES` и в ожидания `stages_after(...) == [...]` вход S4j встаёт на то же место,
    что и в словари, — правка одна, а не несколько разных.
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
    """Круг S4j в `scope_counts` — копией блока S4i с заменой перечня таблиц и префикса.

    Тело блока копируется, а не переписывается: пробы V51 и V52 считают круг своими
    предикатами, и переписывание потеряло бы этот приём. Круг новой стадии — одна таблица
    `bots`, но перечень читается из словаря слоя (`BOTS_TABLES`), поэтому копия блока
    остаётся верной и при изменении круга узла.
    """
    if any("for table in BOTS_TABLES:" in line for line in lines):
        report.append((name, "уже внесено", "цикл круга S4j"))
        return lines
    out, i, found = [], 0, False
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = re.match(r"^(?P<ind>[ \t]*)for table in SCHEDULED_JOBS_TABLES:\s*$", line)
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
            f"{ind}# Узел V55 (шаг П8): строки S4j входят в «что осталось в базе» по тому же",
            f"{ind}# правилу — пропущенная стадия не обязана заполнять свои таблицы, и проба",
            f"{ind}# обязана видеть это числом. Круг вида — одна таблица `bots` (замер 2.1",
            f"{ind}# узла V55), детей у вида нет; перечень берётся из словаря слоя.",
            f"{ind}for table in BOTS_TABLES:",
        ])
        out.extend(b.replace('"s4i:"', '"s4j:"') for b in block)
        report.append((name, "внесено", "цикл круга S4j"))
        found = True
        i = j
    if not found:
        report.append((name, "нет якоря (цикла S4i в файле нет)", "цикл круга S4j"))
    return out


def fix_tail_lists(text, name, report):
    """Явные перечни хвоста `STAGES`: между S4i и S4b вставляется S4j.

    Правила два — строчное и многострочное: перечни в пробах записаны и в одну строку
    (`CHILD_STAGES`, `LATER_STAGES`, `not_run_stages == [...]`), и переноской
    (`stages_after(...) == [...]`). После правки якорь перестаёт встречаться, поэтому
    повторный прогон ничего не меняет.
    """
    single = f"{ANCHOR}, STAGE_OBJECT_MODULES"
    expanded = f"{ANCHOR}, {NEXT_KEY}, STAGE_OBJECT_MODULES"
    hits = text.count(single)
    if hits:
        text = text.replace(single, expanded)
        report.append((name, f"внесено ({hits})", "перечень S4i→S4b (строка)"))
    elif expanded in text:
        report.append((name, "уже внесено", "перечень S4i→S4b (строка)"))
    else:
        report.append((name, "нет якоря (такого перечня одной строкой нет)",
                       "перечень S4i→S4b (строка)"))
    multi = re.compile(re.escape(ANCHOR) + r",\n(?P<ind>[ \t]*)STAGE_OBJECT_MODULES")
    found = multi.findall(text)
    if found:
        text = multi.sub(lambda m: (f"{ANCHOR},\n{m.group('ind')}{NEXT_KEY},\n"
                                    f"{m.group('ind')}STAGE_OBJECT_MODULES"), text)
        report.append((name, f"внесено ({len(found)})", "перечень S4i→S4b (переноской)"))
    else:
        report.append((name, "нет якоря (перечня с переноской нет)",
                       "перечень S4i→S4b (переноской)"))
    return text


def fix_stages_after_anchor(text, name, report):
    """`stages_after(S4i) == [S4b]` → `[S4j, S4b]`: хвост после S4i больше не одна стадия."""
    pat = re.compile(r"(?P<ind>[ \t]*)stages_after\(STAGE_SCHEDULED_JOBS\) == "
                     r"\[STAGE_OBJECT_MODULES\]")
    found = pat.findall(text)
    if found:
        def _repl(m):
            ind = m.group("ind") + "    "
            return (f"{m.group('ind')}stages_after(STAGE_SCHEDULED_JOBS) == [\n"
                    f"{ind}{NEXT_KEY},\n{ind}STAGE_OBJECT_MODULES]")
        text = pat.sub(_repl, text)
        report.append((name, f"внесено ({len(found)})", "stages_after(S4i)"))
    elif "stages_after(STAGE_SCHEDULED_JOBS) == [\n" in text:
        report.append((name, "уже внесено", "stages_after(S4i)"))
    else:
        report.append((name, "нет якоря (сравнения с хвостом S4i в файле нет)",
                       "stages_after(S4i)"))
    return text


def fix_order_chain(text, name, report):
    """Цепочка `ORDER.index(...) + 1 == ORDER.index(...)` получает звено S4j."""
    multi = re.compile(r"(?P<key>ORDER|order)\.index\(STAGE_SCHEDULED_JOBS\) \+ 1\n"
                       r"(?P<ind>[ \t]*)== (?P=key)\.index\(STAGE_OBJECT_MODULES\)")
    found = multi.findall(text)
    if found:
        text = multi.sub(lambda m: (f"{m.group('key')}.index(STAGE_SCHEDULED_JOBS) + 1\n"
                                    f"{m.group('ind')}== {m.group('key')}.index({NEXT_KEY})\n"
                                    f"{m.group('ind')}and {m.group('key')}.index({NEXT_KEY}) + 1\n"
                                    f"{m.group('ind')}== {m.group('key')}.index("
                                    f"STAGE_OBJECT_MODULES)"),
                         text)
        report.append((name, f"внесено ({len(found)})", "цепочка ORDER.index (переноской)"))
    else:
        report.append((name, "нет якоря (цепочки переноской нет)",
                       "цепочка ORDER.index (переноской)"))
    single = ("order.index(STAGE_SCHEDULED_JOBS) + 1 == "
              "order.index(STAGE_OBJECT_MODULES)")
    if single in text:
        text = text.replace(
            single,
            "order.index(STAGE_SCHEDULED_JOBS) + 1\n"
            "          == order.index(STAGE_BOTS)\n"
            "          and order.index(STAGE_BOTS) + 1\n"
            "          == order.index(STAGE_OBJECT_MODULES)")
        report.append((name, "внесено (1)", "цепочка order.index (строка)"))
    elif "order.index(STAGE_BOTS)" in text:
        report.append((name, "уже внесено", "цепочка order.index (строка)"))
    else:
        report.append((name, "нет якоря (цепочки одной строкой нет)",
                       "цепочка order.index (строка)"))
    return text


# ── тексты проверок там, где проба утверждает число стадий или состав пропущенных ──────────
# Пары (образец, замена, признак уже внесённой правки, метка отчёта). Образцы регулярные:
# формулировки перенесены строками, и «S4i и S4b» встречается как в одну строку, так и с
# закрытием кавычки на предыдущей строке. Порядок важен: сначала более длинные образцы,
# иначе короткое правило оставит фразу, приписывающую вставку S4j не тому узлу. Отсутствие
# образца в конкретном файле — норма (правило чужого файла), оно отказом не является.
TEXT_CLAIMS = [
    ('у S4i (узел V54) — только S4b.',
     'у S4i (узел V54) — S4j и S4b, у S4j (узел V55) — только S4b.',
     'у S4j (узел V55) — только S4b.', 'текст: хвост после S4i'),
    ('у S4i (узел V54) — S4b.',
     'у S4i (узел V54) — S4j и S4b, у S4j (узел V55) — S4b.',
     'у S4j (узел V55) — S4b.', 'текст: хвост после S4i'),
    ('(узел V53) — S4b.',
     '(узел V53) — S4i, S4j и S4b, у S4i\n# (узел V54) — S4j и S4b, у S4j (узел V55) — S4b.',
     '(узел V53) — S4i, S4j и S4b', 'текст: перечень пропущенных комментария'),
    ('десять стадий, S4g, S4h и S4i входят',
     'одиннадцать стадий, S4g, S4h, S4i и S4j входят',
     'одиннадцать стадий', 'текст: перечень детей'),
    ('S4g, S4h и S4i', 'S4g, S4h, S4i и S4j', 'S4g, S4h, S4i и S4j',
     'текст: пропущенные после S4f'),
    ('с учётом S4h и S4i', 'с учётом S4h, S4i и S4j', 'с учётом S4h, S4i и S4j',
     'текст: раздел пробы'),
    ('`stages_after` с учётом S4i, закрытость', '`stages_after` с учётом S4i и S4j, '
     'закрытость', 'с учётом S4i и S4j', 'текст: раздел пробы'),
    ('S4h и S4i — вход', 'S4h, S4i и S4j — вход', 'S4h, S4i и S4j — вход',
     'текст: пропущенные после S4f'),
    (r'S4h, S4i и ("?\n?[ \t]*"?)S4b', r'S4h, S4i, S4j и \1S4b', 'S4h, S4i, S4j и',
     'текст: S4h, S4i и S4b'),
    (r'S4i и ("?\n?[ \t]*"?)S4b', r'S4i, S4j и \1S4b', 'S4i, S4j и', 'текст: S4i и S4b'),
    ('ровно S4b', 'ровно S4j и S4b', 'ровно S4j и S4b', 'текст: перечень пропущенных'),
    ('S4b не вызывалась вовсе', 'S4j и S4b не вызывались вовсе', 'S4j и S4b не вызывались',
     'текст: счётчик вызовов'),
    ('пропущенную S4b словом формата', 'пропущенные S4j и S4b словом формата',
     'пропущенные S4j и S4b словом', 'текст: карточка пропуска'),
    ('ни S4b модулей объектов', 'ни S4j ботов (узел V55), ни S4b модулей объектов',
     'ни S4j ботов', 'текст: хвост после S4f'),
    ('S4i — узлом V54, и пропуск', 'S4i — узлом V54, S4j — узлом V55, и пропуск',
     'S4j — узлом V55', 'текст: очередь узлов обёрток'),
    (r'добавил третью — S4i\);', 'добавил третью — S4i, узел V55 добавил четвёртую — S4j);',
     'узел V55 добавил четвёртую', 'текст: очередь узлов обёрток'),
    ('→ S4i → S4b', '→ S4i → S4j → S4b', '→ S4i → S4j', 'текст: стрелки порядка'),
    ('2.9 → модули', '2.9 → 2.10 → модули', '2.9 → 2.10', 'текст: позиции списка'),
    ('2.9, модули Ext/', '2.9, 2.10, модули Ext/', '2.9, 2.10, модули',
     'текст: позиции списка в комментарии'),
    (r'узел V54 добавляет десятую —\n# S4i \(позиция 2\.9\)',
     'узел V54 добавлял десятую — S4i (позиция 2.9); узел V55\n'
     '# добавляет одиннадцатую — S4j (позиция 2.10)',
     'добавляет одиннадцатую', 'текст: очередь узлов перечня (переноской)'),
    (r'узел V54 добавляет десятую — S4i \(позиция 2\.9\)',
     'узел V54 добавлял десятую — S4i (позиция 2.9); узел V55\n'
     '# добавляет одиннадцатую — S4j (позиция 2.10)',
     'добавляет одиннадцатую', 'текст: очередь узлов перечня'),
    ('таблицы девяти стадий', 'таблицы десяти стадий', 'таблицы десяти стадий',
     'текст: число стадий в scope_counts'),
    ('из девяти стадий', 'из десяти стадий', 'из десяти стадий', 'текст: число стадий'),
    (r'V52, V53 и V54', 'V52, V53, V54 и V55', 'V53, V54 и V55', 'текст: перечень узлов'),
    (r'V53 и V54', 'V53, V54 и V55', 'V54 и V55', 'текст: перечень узлов'),
    (r'and "2\.10" not in CHILD_NOT_IMPLEMENTED',
     'and "2.10" in CHILD_NOT_IMPLEMENTED\n          and "2.11" not in CHILD_NOT_IMPLEMENTED',
     '"2.11" not in CHILD_NOT_IMPLEMENTED', 'условие 1.6: граница незакрытой части'),
]

# Точные правки, вносимые ДО общих правил: они переписывают формулировку целиком, иначе
# общее правило оставило бы фразу, приписывающую вставку S4j не тому узлу, или сломало бы
# перенесённую через строку формулировку заголовка проверки. Тройки (образец, замена,
# признак уже внесённой правки).
SPECIFIC = {}
SPECIFIC["_v52_p8_stop_probe.py"] = [
    ('      and len(CHILD_STAGES) == 10 and STAGE_FILTER_CRITERIA in CHILD_STAGES\n'
     '      and STAGE_EVENT_SUBSCRIPTIONS in CHILD_STAGES\n'
     '      and STAGE_SCHEDULED_JOBS in CHILD_STAGES',
     '      and len(CHILD_STAGES) == 11 and STAGE_FILTER_CRITERIA in CHILD_STAGES\n'
     '      and STAGE_EVENT_SUBSCRIPTIONS in CHILD_STAGES\n'
     '      and STAGE_SCHEDULED_JOBS in CHILD_STAGES\n'
     '      and STAGE_BOTS in CHILD_STAGES',
     'len(CHILD_STAGES) == 11'),
]
SPECIFIC["_v53_p8_stop_probe.py"] = [
    ('"вида и не обещает закрытости остальных позиций списка; с узла V54 текст называет "\n'
     '          "закрытой и позицию 2.9, поэтому граница перечня сдвинута на 2.10",',
     '"вида и не обещает закрытости остальных позиций списка; тексты узлов V54 "\n'
     '          "и V55 называют закрытыми позиции 2.9 и 2.10, поэтому граница перечня "\n'
     '          "сдвинута на 2.11",',
     'сдвинута на 2.11'),
    ('          calls.get(STAGE_EVENT_SUBSCRIPTIONS) == 1 and STAGE_OBJECT_MODULES not in calls\n'
     '              and STAGE_SCHEDULED_JOBS not in calls,',
     '          calls.get(STAGE_EVENT_SUBSCRIPTIONS) == 1 and STAGE_OBJECT_MODULES not in calls\n'
     '              and STAGE_SCHEDULED_JOBS not in calls\n              '
     'and STAGE_BOTS not in calls,',
     'and STAGE_BOTS not in calls,'),
    ('              and SKIPPED_PHRASE in card and stage_title(STAGE_OBJECT_MODULES) in card\n'
     '              and stage_title(STAGE_SCHEDULED_JOBS) in card,',
     '              and SKIPPED_PHRASE in card and stage_title(STAGE_OBJECT_MODULES) in card\n'
     '              and stage_title(STAGE_SCHEDULED_JOBS) in card\n'
     '              and stage_title(STAGE_BOTS) in card,',
     'stage_title(STAGE_BOTS) in card'),
]
SPECIFIC["_v54_p8_stop_probe.py"] = [
    ('"вида и не обещает закрытости остальных позиций списка; с узла V54 текст называет "\n'
     '          "закрытой и позицию 2.9, поэтому граница перечня сдвинута на 2.10",',
     '"вида и не обещает закрытости остальных позиций списка; тексты узлов V54 "\n'
     '          "и V55 называют закрытыми позиции 2.9 и 2.10, поэтому граница перечня "\n'
     '          "сдвинута на 2.11",',
     'сдвинута на 2.11'),
    ('LATER_STAGES = (STAGE_OBJECT_MODULES,)',
     'LATER_STAGES = (STAGE_BOTS, STAGE_OBJECT_MODULES,)',
     'LATER_STAGES = (STAGE_BOTS, STAGE_OBJECT_MODULES,)'),
    ('              and [item.get("stage") for item in stopped.get("not_run_stages") or []]\n'
     '                  == [STAGE_OBJECT_MODULES]\n'
     '              and all(item.get("status") == STATUS_NOT_RUN',
     '              and [item.get("stage") for item in stopped.get("not_run_stages") or []]\n'
     '                  == [STAGE_BOTS, STAGE_OBJECT_MODULES]\n'
     '              and all(item.get("status") == STATUS_NOT_RUN',
     '== [STAGE_BOTS, STAGE_OBJECT_MODULES]'),
    ('"S4b, посчитанная из `STAGES`"',
     '"S4j и S4b, посчитанная из `STAGES`"',
     '"S4j и S4b, посчитанная из `STAGES`"'),
    ('              calls.get(STAGE_SCHEDULED_JOBS) == 1 and STAGE_OBJECT_MODULES not in calls,',
     '              calls.get(STAGE_SCHEDULED_JOBS) == 1 and STAGE_OBJECT_MODULES not in calls\n'
     '              and STAGE_BOTS not in calls,',
     'and STAGE_BOTS not in calls,'),
    ('              and SKIPPED_PHRASE in card and stage_title(STAGE_OBJECT_MODULES) in card\n'
     '              and stage_title(STAGE_SCHEDULED_JOBS) in card,',
     '              and SKIPPED_PHRASE in card and stage_title(STAGE_OBJECT_MODULES) in card\n'
     '              and stage_title(STAGE_SCHEDULED_JOBS) in card\n'
     '              and stage_title(STAGE_BOTS) in card,',
     'stage_title(STAGE_BOTS) in card'),
]
SPECIFIC["_v52_p8_resume_probe.py"] = [
    ('              and f"{SKIPPED_PHRASE}: {STAGE_SCHEDULED_JOBS} — "\n'
     '              f"{stage_title(STAGE_SCHEDULED_JOBS)}" in card\n'
     '              and f"{SKIPPED_PHRASE}: {STAGE_OBJECT_MODULES} — "',
     '              and f"{SKIPPED_PHRASE}: {STAGE_SCHEDULED_JOBS} — "\n'
     '              f"{stage_title(STAGE_SCHEDULED_JOBS)}" in card\n'
     '              and f"{SKIPPED_PHRASE}: {STAGE_BOTS} — "\n'
     '              f"{stage_title(STAGE_BOTS)}" in card\n'
     '              and f"{SKIPPED_PHRASE}: {STAGE_OBJECT_MODULES} — "',
     'and f"{SKIPPED_PHRASE}: {STAGE_BOTS} — "'),
]


def apply_pairs(text, pairs, name, report):
    """Точные правки по списку SPECIFIC: образец ищется подстрокой, замена одна."""
    for old, new, marker in pairs:
        label = "точное совпадение: " + old.splitlines()[0].strip()[:64]
        if old in text:
            text = text.replace(old, new)
            report.append((name, "внесено", label))
        elif marker in text:
            report.append((name, "уже внесено", label))
        else:
            report.append((name, "НЕ СОЙШЛОСЬ", label))
    return text


def apply_text_claims(text, name, report):
    """Формулировки проверок, утверждающие число стадий или состав пропущенных.

    Отсутствие образца в файле — норма: правило относится к чужой пробе. Отказом оно не
    является, потому что иначе отчёт тонул бы в строках «нет якоря»; полноту правки
    сторожат остатки в `verify`.
    """
    for pattern, repl, marker, label in TEXT_CLAIMS:
        pat = re.compile(pattern)
        if "\\1" not in repl and repl in text:
            report.append((name, "уже внесено", label))
            continue
        hits = pat.findall(text)
        if hits:
            text = pat.sub(repl, text)
            report.append((name, f"внесено ({len(hits)})", label))
        elif marker in text:
            report.append((name, "уже внесено", label))
    return text


def verify(text, name, report):
    """Сверка полноты: каждая строка S4i обязана иметь парную строку S4j."""
    for val, pairs in VALUE_MAP.items():
        pat = re.compile(re.escape(ANCHOR) + ": " + re.escape(val) + r",")
        for m in pat.finditer(text):
            window = text[m.start(): m.start() + 900]
            for key, value in pairs:
                if f"{key}: {value}," not in window:
                    report.append((name, "НЕ СОЙШЛОСЬ (нет строки словаря)",
                                   f"{ANCHOR}: {val} → {key}"))
    for import_name, names in IMPORT_MAP.items():
        pat = re.compile(r"\n[ \t]*" + re.escape(import_name) + r",\n")
        for m in pat.finditer(text):
            window = "\n".join(text[m.end(): m.end() + 600].split("\n")[: len(names) + 1])
            for n in names:
                if f"{n}," not in window:
                    report.append((name, "НЕ СОЙШЛОСЬ (нет импорта)",
                                   f"{import_name} → {n}"))
    if ("for table in SCHEDULED_JOBS_TABLES:" in text
            and "for table in BOTS_TABLES:" not in text):
        report.append((name, "НЕ СОЙШЛОСЬ", "цикл круга S4j"))
    residues = [
        (f"{ANCHOR}, STAGE_OBJECT_MODULES", "перечень S4i→S4b (остаток)"),
        ("stages_after(STAGE_SCHEDULED_JOBS) == [STAGE_OBJECT_MODULES]",
         "stages_after(S4i) (остаток)"),
        ("ORDER.index(STAGE_SCHEDULED_JOBS) + 1 == ORDER.index(STAGE_OBJECT_MODULES)",
         "цепочка ORDER.index (остаток)"),
        ("order.index(STAGE_SCHEDULED_JOBS) + 1 == order.index(STAGE_OBJECT_MODULES)",
         "цепочка order.index (остаток)"),
        ("LATER_STAGES = (STAGE_OBJECT_MODULES,)", "LATER_STAGES (остаток)"),
        ('"2.10" not in CHILD_NOT_IMPLEMENTED', "граница CHILD_NOT_IMPLEMENTED (остаток)"),
        ("len(CHILD_STAGES) == 10", "число стадий детей (остаток)"),
    ]
    for residue, label in residues:
        if residue in text:
            report.append((name, "НЕ СОЙШЛОСЬ", label))
    if re.search(r"(?:ORDER|order)\.index\(STAGE_SCHEDULED_JOBS\) \+ 1\n[ \t]*== "
                 r"(?:ORDER|order)\.index\(STAGE_OBJECT_MODULES\)", text):
        report.append((name, "НЕ СОЙШЛОСЬ", "цепочка ORDER.index переноской (остаток)"))


def process(name, report):
    """Один файл: сначала точные пары, затем общие правила, затем сверка полноты."""
    path = ROOT / name
    text = path.read_text(encoding="utf-8")
    text = apply_pairs(text, SPECIFIC.get(name, []), name, report)
    lines = text.split("\n")
    lines = add_imports(lines, ANCHOR, IMPORT_MAP, name, report)
    lines = add_stage_entries(lines, ANCHOR, VALUE_MAP, name, report)
    lines = duplicate_scope_loop(lines, name, report)
    text = "\n".join(lines)
    text = fix_tail_lists(text, name, report)
    text = fix_stages_after_anchor(text, name, report)
    text = fix_order_chain(text, name, report)
    text = apply_text_claims(text, name, report)
    verify(text, name, report)
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








