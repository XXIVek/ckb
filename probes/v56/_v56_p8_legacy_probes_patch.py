#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка прежних проб П8 (узлов V48–V55) под состав стадий с S4k (шаг П8 узла V56).

Зачем она обязательна. Узел V56 поставил стадию `s4k_functional_options` в `STAGES` между
`s4j_bots` и `s4b_object_modules`. Прежние пробы остановки держат перебор стадий детей и
словари стадий (`STAGE_KEYS`, `SECTION_HEADERS`, `DEFAULTS`, `STAGE_FUNCTIONS`, `RESUME_MARKS`,
`stage_row_prefix`) — без входа S4k первая же проверка «строки пропущенной стадии сняты» падает
`KeyError: 's4k_functional_options'`. Кроме того узлы V50–V55 держат явные перечни
`stages_after(...)`, кортежи `CHILD_STAGES`/`LATER_STAGES` и цепочки `ORDER.index(...)`:
именно они и есть критерий П8 («перечень пропущенных считается из `STAGES`»), поэтому явный
перечень обязан называть новый порядок, а не выводиться из того же `STAGES`.

Границы правки:

  * содержательных проверок чужих узлов скрипт НЕ меняет — добавлены только вход стадии в
    словари и импорты, подсчёт круга S4k в `scope_counts`, явные перечни порядка и тексты
    проверок ровно там, где они утверждали число стадий или состав пропущенных;
  * `_v55_p8_stop_probe.py` правится как прежний узел: после отказа S4j конвейер обязан не звать
    ВЕСЬ хвост — и S4k, и S4b; проверка «текст незакрытой части не обещает 2.11» меняет
    границу на 2.12, потому что с узла V56 позиция 2.11 названа закрытой;
  * круг стадии S4k — ДВЕ таблицы (`FUNCTIONAL_OPTIONS_TABLES` = `functional_options` +
    `functional_option_content`), в отличие от одной таблицы S4j: блок `scope_counts` копируется
    списком, а не одной таблицей, предикат чужих проб сохраняется;
  * порядок вставок — порядок стадий (S4j → S4k), а не алфавит;
  * скрипт идемпотентен: уже внесённая строка не вставляется второй раз, отсутствующий якорь
    называется строкой отчёта, а не молчанием.

Запуск:

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v56_p8_legacy_probes_patch.py            # отчёт без записи
    python _v56_p8_legacy_probes_patch.py --write    # запись

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
               "_v54_p8_stop_probe.py", "_v55_p8_stop_probe.py")
RESUME_PROBES = ("_v51_p8_resume_probe.py", "_v52_p8_resume_probe.py")
ALL_FILES = STOP_PROBES + RESUME_PROBES

ANCHOR = "STAGE_BOTS"
NEXT_KEY = "STAGE_FUNCTIONAL_OPTIONS"

# Значения словарей стадий: значение якоря S4j → пары (ключ, значение) стадии S4k.
VALUE_MAP = {
    '"bots"': [(NEXT_KEY, '"functional_options"')],
    "BOTS_SECTION_HEADER": [(NEXT_KEY, "FUNCTIONAL_OPTIONS_SECTION_HEADER")],
    "bots_defaults": [(NEXT_KEY, "functional_options_defaults")],
    '"load_bots"': [(NEXT_KEY, '"load_functional_options"')],
    '"load_bots_tool"': [(NEXT_KEY, '"load_functional_options_tool"')],
    '"s4j:"': [(NEXT_KEY, '"s4k:"')],
}
IMPORT_MAP = {
    "STAGE_BOTS": [NEXT_KEY],
    "BOTS_SECTION_HEADER": ["FUNCTIONAL_OPTIONS_SECTION_HEADER"],
    "BOTS_TABLES": ["FUNCTIONAL_OPTIONS_TABLES"],
    "bots_defaults": ["functional_options_defaults"],
}

# Класс значения строки словаря: имена стадий, строковые ключи (`"s4j:"`), имена функций.
VAL_CLASS = '[0-9A-Za-z_".:-]+'


def add_stage_entries(lines, anchor, value_map, name, report):
    """После каждой строки словаря вида `ЯКОРЬ: <известное значение>,` вставляет пару S4k.

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
    """В списки импортов и в перечни стадий добавляет имена стадии S4k — следом за якорем.

    Правило читает строки, оканчивающиеся именем с запятой: так в перечни `CHILD_STAGES`,
    `LATER_STAGES` и в ожидания `stages_after(...) == [...]` вход S4k встаёт на то же место,
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
    """Круг S4k в `scope_counts` — копией блока S4j с заменой перечня таблиц и префикса.

    Тело блока копируется, а не переписывается: пробы V51 и V52 считают круг своими
    предикатами, и переписывание потеряло бы этот приём. Круг новой стадии — две таблицы
    (`functional_options` и `functional_option_content`, узел V56), но перечень читается из
    словаря слоя (`FUNCTIONAL_OPTIONS_TABLES`), поэтому копия блока остаётся верной и при
    изменении состава круга узла.
    """
    if any("for table in FUNCTIONAL_OPTIONS_TABLES:" in line for line in lines):
        report.append((name, "уже внесено", "цикл круга S4k"))
        return lines
    out, i, found = [], 0, False
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = re.match(r"^(?P<ind>[ \t]*)for table in BOTS_TABLES:\s*$", line)
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
            f"{ind}# Узел V56 (шаг П8): строки S4k входят в «что осталось в базе» по тому",
            f"{ind}# же правилу — пропущенная стадия не обязана заполнять свои таблицы, и",
            f"{ind}# проба обязана видеть это числом. Круг вида — две таблицы (замер 1.2",
            f"{ind}# плана узла V56); перечень берётся из словаря слоя.",
            f"{ind}for table in FUNCTIONAL_OPTIONS_TABLES:",
        ])
        out.extend(b.replace('"s4j:"', '"s4k:"') for b in block)
        report.append((name, "внесено", "цикл круга S4k"))
        found = True
        i = j
    if not found:
        report.append((name, "нет якоря (цикла S4j в файле нет)", "цикл круга S4k"))
    return out



# ── построчные пары: строка условия, после которой нужна парная строка S4k ──────────────────
# Третий элемент — признак уже внесённой правки, четвёртый — метка отчёта. Строки вставки
# получают отступ из строки-якоря: правка чужой пробы не должна менять её форматирование.
# Запятая в конце строки-якоря переносится на последнюю вставленную строку: в чужих пробах
# строка S4j бывает последней строкой условия (и тогда её запятая закрывает аргумент check),
# а бывает серединой условия (и тогда запятой нет) — один шаблон на оба случая ломает синтаксис.
PAIR_RULES = [
    (r"^(\s*)and STAGE_BOTS in CHILD_STAGES(?P<tail>,?)\s*$",
     ["{ind}and STAGE_FUNCTIONAL_OPTIONS in CHILD_STAGES"],
     "and STAGE_FUNCTIONAL_OPTIONS in CHILD_STAGES", "перечень детей (условие)"),
    (r"^(\s*)and STAGE_BOTS not in calls(?P<tail>,?)\s*$",
     ["{ind}and STAGE_FUNCTIONAL_OPTIONS not in calls"],
     "and STAGE_FUNCTIONAL_OPTIONS not in calls", "счётчик вызовов (условие)"),
    (r"^(\s*)and stage_title\(STAGE_BOTS\) in card(?P<tail>,?)\s*$",
     ["{ind}and stage_title(STAGE_FUNCTIONAL_OPTIONS) in card"],
     "and stage_title(STAGE_FUNCTIONAL_OPTIONS) in card", "карточка пропуска (условие)"),
    (r'^(\s*)f"\{stage_title\(STAGE_BOTS\)\}" in card(?P<tail>,?)$',
     ['{ind}and f"{{SKIPPED_PHRASE}}: {{STAGE_FUNCTIONAL_OPTIONS}} — "',
      '{ind}f"{{stage_title(STAGE_FUNCTIONAL_OPTIONS)}}" in card'],
     'and f"{SKIPPED_PHRASE}: {STAGE_FUNCTIONAL_OPTIONS} — "', "карточка пропуска (пара)"),
]


def add_pair_lines(lines, name, report):
    """После строки-якоря вставляет парную строку S4k — отступ берётся из строки-якоря.

    Проверка «уже внесено» читает следующие строки, а не файл: тот же текст в другой пробе
    не должен считаться признаком правки этой. Запятая, которой строка-якорь закрывал аргумент
    `check(...)`, переносится на последнюю вставленную строку — иначе вставка рассекла бы
    условие пополам (`and … in card,` + `and …` даёт синтаксическую ошибку).
    """
    out = []
    for i, line in enumerate(lines):
        out.append(line)
        for pat, inserts, marker, label in PAIR_RULES:
            m = re.match(pat, line)
            if not m:
                continue
            ind = m.group(1)
            following = "\n".join(lines[i + 1: i + 2 + len(inserts)])
            if marker in following:
                report.append((name, "уже внесено", label))
                continue
            tail = m.groupdict().get("tail") or ""
            if tail:
                out[-1] = line[: -len(tail)]
            for n, tpl in enumerate(inserts):
                out.append(tpl.format(ind=ind) + (tail if n == len(inserts) - 1 else ""))
            report.append((name, "внесено", label))
            break
    return out


def fix_tail_lists(text, name, report):
    """Явные перечни хвоста `STAGES`: между S4j и S4b вставляется S4k.

    Правила два — строчное и многострочное: перечни в пробах записаны и в одну строку
    (`CHILD_STAGES`, `not_run_stages == [...]`), и переноской (`stages_after(...) == [...]`).
    После правки якорь перестаёт встречаться, поэтому повторный прогон ничего не меняет.
    """
    single = f"{ANCHOR}, STAGE_OBJECT_MODULES"
    expanded = f"{ANCHOR}, {NEXT_KEY}, STAGE_OBJECT_MODULES"
    hits = text.count(single)
    if hits:
        text = text.replace(single, expanded)
        report.append((name, f"внесено ({hits})", "перечень S4j→S4b (строка)"))
    elif expanded in text:
        report.append((name, "уже внесено", "перечень S4j→S4b (строка)"))
    else:
        report.append((name, "нет якоря (такого перечня одной строкой нет)",
                       "перечень S4j→S4b (строка)"))
    multi = re.compile(re.escape(ANCHOR) + r",\n(?P<ind>[ \t]*)STAGE_OBJECT_MODULES")
    found = multi.findall(text)
    if found:
        text = multi.sub(lambda m: (f"{ANCHOR},\n{m.group('ind')}{NEXT_KEY},\n"
                                    f"{m.group('ind')}STAGE_OBJECT_MODULES"), text)
        report.append((name, f"внесено ({len(found)})", "перечень S4j→S4b (переноской)"))
    else:
        report.append((name, "нет якоря (перечня с переноской нет)",
                       "перечень S4j→S4b (переноской)"))
    return text



def fix_later_stages(text, name, report):
    """`LATER_STAGES = (..., STAGE_OBJECT_MODULES,)` получает звено S4k перед S4b.

    Правило одно на все пробы: вставка идёт перед `STAGE_OBJECT_MODULES`, потому что хвост
    после S4j в разных пробах назван по-разному — `_v53` держит `(S4i, S4j, S4b)`, `_v54`
    держит `(S4j, S4b)`, `_v55` держит `(S4b,)`. После правки якорь перестаёт встречаться.
    """
    pat = re.compile(r"(?P<tail>LATER_STAGES = \((?![^)]*?STAGE_FUNCTIONAL_OPTIONS)"
                     r"[^)]*?)(?P<ind>[ \t]*)STAGE_OBJECT_MODULES")
    found = pat.findall(text)
    if found:
        text = pat.sub(lambda m: (f"{m.group('tail')}{m.group('ind')}{NEXT_KEY},\n"
                                  f"{m.group('ind')}STAGE_OBJECT_MODULES"), text)
        report.append((name, f"внесено ({len(found)})", "LATER_STAGES"))
    elif "LATER_STAGES" in text and NEXT_KEY in text.split("LATER_STAGES")[1][:200]:
        report.append((name, "уже внесено", "LATER_STAGES"))
    else:
        report.append((name, "нет якоря (кортежа LATER_STAGES нет)", "LATER_STAGES"))
    return text


def fix_expect_lists(text, name, report):
    """Ожидания `== [STAGE_OBJECT_MODULES]` и `== [STAGE_BOTS, STAGE_OBJECT_MODULES]`.

    Список невыполненных стадий читается пробами буквально, поэтому он обязан называть
    новый хвост. Правило одно: в составе списка перед `STAGE_OBJECT_MODULES]` вставляется
    `STAGE_FUNCTIONAL_OPTIONS, `.
    """
    pat = re.compile(r"== \[(?!(?:STAGE_[A-Z_]+, )*STAGE_FUNCTIONAL_OPTIONS)"
                     r"(?P<head>(?:STAGE_[A-Z_]+, )*)STAGE_OBJECT_MODULES\]")
    found = pat.findall(text)
    if found:
        text = pat.sub(lambda m: f"== [{m.group('head')}{NEXT_KEY}, STAGE_OBJECT_MODULES]",
                       text)
        report.append((name, f"внесено ({len(found)})", "ожидание not_run_stages"))
    elif f"{NEXT_KEY}, STAGE_OBJECT_MODULES]" in text:
        report.append((name, "уже внесено", "ожидание not_run_stages"))
    else:
        report.append((name, "нет якоря (ожидания списка нет)", "ожидание not_run_stages"))
    return text


def fix_stages_after_anchor(text, name, report):
    """`stages_after(S4j) == [S4b]` → `[S4k, S4b]`: хвост после S4j больше не одна стадия."""
    pat = re.compile(r"(?P<ind>[ \t]*)stages_after\(STAGE_BOTS\) == "
                     r"\[STAGE_OBJECT_MODULES\]")
    found = pat.findall(text)
    if found:
        def _repl(m):
            ind = m.group("ind") + "    "
            return (f"{m.group('ind')}stages_after(STAGE_BOTS) == [\n"
                    f"{ind}{NEXT_KEY},\n{ind}STAGE_OBJECT_MODULES]")
        text = pat.sub(_repl, text)
        report.append((name, f"внесено ({len(found)})", "stages_after(S4j)"))
    elif "stages_after(STAGE_BOTS) == [\n" in text:
        report.append((name, "уже внесено", "stages_after(S4j)"))
    else:
        report.append((name, "нет якоря (сравнения с хвостом S4j в файле нет)",
                       "stages_after(S4j)"))
    return text


def fix_order_chain(text, name, report):
    """Цепочка `ORDER.index(...) + 1 == ORDER.index(...)` получает звено S4k."""
    multi = re.compile(r"(?P<key>ORDER|order)\.index\(STAGE_BOTS\) \+ 1\n"
                       r"(?P<ind>[ \t]*)== (?P=key)\.index\(STAGE_OBJECT_MODULES\)")
    found = multi.findall(text)
    if found:
        text = multi.sub(
            lambda m: (f"{m.group('key')}.index(STAGE_BOTS) + 1\n"
                       f"{m.group('ind')}== {m.group('key')}.index({NEXT_KEY})\n"
                       f"{m.group('ind')}and {m.group('key')}.index({NEXT_KEY}) + 1\n"
                       f"{m.group('ind')}== {m.group('key')}.index(STAGE_OBJECT_MODULES)"),
            text)
        report.append((name, f"внесено ({len(found)})", "цепочка ORDER.index (переноской)"))
    else:
        report.append((name, "нет якоря (цепочки переноской нет)",
                       "цепочка ORDER.index (переноской)"))
    single = ("order.index(STAGE_BOTS) + 1 == "
              "order.index(STAGE_OBJECT_MODULES)")
    if single in text:
        text = text.replace(
            single,
            "order.index(STAGE_BOTS) + 1\n"
            "          == order.index(STAGE_FUNCTIONAL_OPTIONS)\n"
            "          and order.index(STAGE_FUNCTIONAL_OPTIONS) + 1\n"
            "          == order.index(STAGE_OBJECT_MODULES)")
        report.append((name, "внесено (1)", "цепочка order.index (строка)"))
    elif "order.index(STAGE_FUNCTIONAL_OPTIONS)" in text:
        report.append((name, "уже внесено", "цепочка order.index (строка)"))
    else:
        report.append((name, "нет якоря (цепочки одной строкой нет)",
                       "цепочка order.index (строка)"))
    return text



# ── тексты проверок там, где проба утверждает число стадий или состав пропущенных ──────────
# Пары (образец, замена, признак уже внесённой правки, метка отчёта). Порядок важен: сначала
# длинные образцы, потом общие — иначе короткое правило оставит фразу, приписывающую вставку
# S4k не тому узлу. Отсутствие образца в конкретном файле — норма (правило чужого файла),
# оно отказом не является; полноту правки сторожат остатки в `verify`.
TEXT_CLAIMS = [
    #── граница перечня незакрытой части: с узла V56 позиция 2.11 названа закрытой ──────────
    (r'(?P<ind>[ \t]*)and "2\.11" not in CHILD_NOT_IMPLEMENTED',
     '\\g<ind>and "2.11" in CHILD_NOT_IMPLEMENTED\n'
     '\\g<ind>and "2.12" not in CHILD_NOT_IMPLEMENTED',
     '"2.12" not in CHILD_NOT_IMPLEMENTED', 'условие 1.6: граница незакрытой части'),
    ('закрытой и позицию 2.10, поэтому граница перечня сдвинута на 2.11',
     'закрытой и позицию 2.10, а узел V56 — позицию 2.11, поэтому граница перечня '
     'сдвинута на 2.12',
     'сдвинута на 2.12', 'текст 1.6: что называет перечень'),
    ('называют закрытыми позиции 2.9 и 2.10',
     'называют закрытыми позиции 2.9, 2.10 и 2.11',
     'позиции 2.9, 2.10 и 2.11', 'текст 1.6: перечень закрытых позиций'),
    ('сдвинута на 2.11', 'сдвинута на 2.12', 'сдвинута на 2.12',
     'текст 1.6: граница перечня'),
    #── число стадий детей и длина перечня ──────────────────────────────────────────────────
    (r'len\(CHILD_STAGES\) == 11', 'len(CHILD_STAGES) == 12',
     'len(CHILD_STAGES) == 12', 'число стадий детей'),
    ('одиннадцать стадий, S4g, S4h, S4i и S4j входят',
     'двенадцать стадий, S4g, S4h, S4i, S4j и S4k входят',
     'двенадцать стадий', 'текст: перечень стадий детей'),
    ('S4g, S4h, S4i и S4j', 'S4g, S4h, S4i, S4j и S4k', 'S4g, S4h, S4i, S4j и S4k',
     'текст: перечень детей'),
    ('десяти стадий', 'одиннадцати стадий', 'одиннадцати стадий',
     'текст: число стадий'),
    #── перечень пропущенных стадий (хвост после отказавшей) ────────────────────────────────
    ('с учётом S4g, S4h, S4i и S4j', 'с учётом S4g, S4h, S4i, S4j и S4k',
     'с учётом S4g, S4h, S4i, S4j и S4k', 'текст: раздел пробы'),
    ('с учётом S4h, S4i и S4j', 'с учётом S4h, S4i, S4j и S4k',
     'с учётом S4h, S4i, S4j и S4k', 'текст: раздел пробы'),
    ('с учётом S4i и S4j', 'с учётом S4i, S4j и S4k', 'с учётом S4i, S4j и S4k',
     'текст: раздел пробы'),
    ('с учётом S4j, закрытость', 'с учётом S4j и S4k, закрытость',
     'с учётом S4j и S4k, закрытость', 'текст: раздел пробы'),
    ('S4h, S4i и S4j — вход', 'S4h, S4i, S4j и S4k — вход', 'S4h, S4i, S4j и S4k — вход',
     'текст: пропущенные после S4f'),
    ('S4i, S4j и S4b', 'S4i, S4j, S4k и S4b', 'S4i, S4j, S4k и S4b',
     'текст: S4i, S4j и S4b'),
    ('S4j и S4b', 'S4j, S4k и S4b', 'S4j, S4k и S4b', 'текст: S4j и S4b'),
    (r'S4j и ("?\n?[ \t]*"?)S4b', r'S4j, S4k и \1S4b', 'S4j, S4k и',
     'текст: S4j и S4b (переноской)'),
    ('ровно S4j и S4b', 'ровно S4j, S4k и S4b', 'ровно S4j, S4k и S4b',
     'текст: перечень пропущенных'),
    ('ровно S4b', 'ровно S4k и S4b', 'ровно S4k и S4b', 'текст: перечень пропущенных'),
    ('S4b не вызывалась вовсе', 'S4k и S4b не вызывались вовсе',
     'S4k и S4b не вызывались', 'текст: счётчик вызовов'),
    ('пропущенную S4b словом формата', 'пропущенные S4k и S4b словом формата',
     'пропущенные S4k и S4b словом', 'текст: карточка пропуска'),
    ('"S4b, посчитанная из `STAGES`"', '"S4k и S4b, посчитанная из `STAGES`"',
     'S4k и S4b, посчитанная из', 'текст: карточка пропуска (заголовок)'),
    ('ни S4j ботов (узел V55), ни S4b модулей объектов',
     'ни S4j ботов (узел V55), ни S4k функциональных опций (узел V56), '
     'ни S4b модулей объектов',
     'ни S4k функциональных опций', 'текст: хвост после S4f'),
    ('S4j — узлом V55, и пропуск', 'S4j — узлом V55, S4k — узлом V56, и пропуск',
     'S4k — узлом V56, и пропуск', 'текст: очередь узлов обёрток'),
    (r'добавил четвёртую — S4j\)',
     'добавил четвёртую — S4j, узел V56 добавил пятую — S4k)',
     'узел V56 добавил пятую', 'текст: очередь узлов обёрток'),
    #── порядок стадий и позиции нормативного списка в комментариях ──────────────────────────
    ('→ S4j → S4b', '→ S4j → S4k → S4b', '→ S4j → S4k', 'текст: стрелки порядка'),
    ('2.9 → 2.10 → модули', '2.9 → 2.10 → 2.11 → модули', '2.9 → 2.10 → 2.11',
     'текст: позиции списка'),
    ('2.9, 2.10, модули Ext/', '2.9, 2.10, 2.11, модули Ext/', '2.9, 2.10, 2.11, модули',
     'текст: позиции списка в комментарии'),
    ('добавляет одиннадцатую — S4j (позиция 2.10)',
     'добавлял одиннадцатую — S4j (позиция 2.10); узел V56\n'
     '# добавляет двенадцатую — S4k (позиция 2.11)',
     'добавляет двенадцатую', 'текст: очередь узлов перечня'),
    #── перечни узлов, поставивших стадии после данной ──────────────────────────────────────
    ('V52, V53, V54 и V55', 'V52, V53, V54, V55 и V56', 'V52, V53, V54, V55 и V56',
     'текст: перечень узлов'),
    ('V53, V54 и V55', 'V53, V54, V55 и V56', 'V53, V54, V55 и V56',
     'текст: перечень узлов'),
    ('V54 и V55', 'V54, V55 и V56', 'V54, V55 и V56', 'текст: перечень узлов'),
]

# Точные правки, вносимые ДО общих правил: они переписывают формулировку целиком, иначе
# общее правило оставило бы фразу, приписывающую вставку S4k не тому узлу, или сломало бы
# перенесённую через строку формулировку заголовка проверки. Тройки (образец, замена,
# признак уже внесённой правки).
SPECIFIC = {}



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
        if "\\1" not in repl and "\\g<" not in repl and repl in text:
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
    """Сверка полноты: каждая строка S4j обязана иметь парную строку S4k."""
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
    if ("for table in BOTS_TABLES:" in text
            and "for table in FUNCTIONAL_OPTIONS_TABLES:" not in text):
        report.append((name, "НЕ СОЙШЛОСЬ", "цикл круга S4k"))
    residues = [
        (f"{ANCHOR}, STAGE_OBJECT_MODULES", "перечень S4j→S4b (остаток)"),
        ("stages_after(STAGE_BOTS) == [STAGE_OBJECT_MODULES]",
         "stages_after(S4j) (остаток)"),
        ("ORDER.index(STAGE_BOTS) + 1 == ORDER.index(STAGE_OBJECT_MODULES)",
         "цепочка ORDER.index (остаток)"),
        ("order.index(STAGE_BOTS) + 1 == order.index(STAGE_OBJECT_MODULES)",
         "цепочка order.index (остаток)"),
        ("LATER_STAGES = (STAGE_OBJECT_MODULES,)", "LATER_STAGES (остаток)"),
        ('"2.11" not in CHILD_NOT_IMPLEMENTED', "граница CHILD_NOT_IMPLEMENTED (остаток)"),
        ("len(CHILD_STAGES) == 11", "число стадий детей (остаток)"),
    ]
    for residue, label in residues:
        if residue in text:
            report.append((name, "НЕ СОЙШЛОСЬ", label))
    if re.search(r"(?:ORDER|order)\.index\(STAGE_BOTS\) \+ 1\n[ \t]*== "
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
    lines = add_pair_lines(lines, name, report)
    text = "\n".join(lines)
    text = fix_tail_lists(text, name, report)
    text = fix_later_stages(text, name, report)
    text = fix_expect_lists(text, name, report)
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

