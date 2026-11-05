#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка прежних проб П8 (узлов V48–V56) под состав стадий с S4l (шаг П8 узла V57).

Зачем она обязательна. Узел V57 поставил стадию `s4l_functional_options_parameters` в `STAGES`
между `s4k_functional_options` и `s4b_object_modules`. Прежние пробы остановки и пробы
продолжения держат перебор стадий детей и словари стадий (`STAGE_KEYS`, `SECTION_HEADERS`,
`DEFAULTS`, `STAGE_FUNCTIONS`, `RESUME_TOOLS`, `stage_row_prefix`, `CONST_NAMES`) — без входа
S4l первая же проверка «строки пропущенной стадии сняты» падает
`KeyError: 's4l_functional_options_parameters'`. Кроме того узлы V50–V56 держат явные перечни
`stages_after(...)`, кортежи `CHILD_STAGES`/`LATER_STAGES`, цепочки `ORDER.index(...)` и
счётчики вызовов «хвост не звался»: именно они и есть критерий П8 («перечень пропущенных
считается из `STAGES`»), поэтому явный перечень обязан называть новый порядок, а не выводиться
из того же `STAGES`.

Границы правки:

  * содержательных проверок чужих узлов скрипт НЕ меняет — добавлены только вход стадии в
    словари и импорты, подсчёт круга S4l в `scope_counts`, явные перечни порядка, счётчики
    вызовов хвоста и тексты проверок ровно там, где они утверждали состав пропущенных;
  * `_v56_p8_stop_probe.py` правится как прежний узел: после отказа S4k конвейер обязан не звать
    ВЕСЬ хвост — и S4l, и S4b; проверка «текст незакрытой части не обещает 2.13» меняет границу
    на 2.13, потому что с узла V57 позиция 2.12 названа закрытой;
  * круг стадии S4l — ДВЕ таблицы (`FUNCTIONAL_OPTION_PARAMETERS_TABLES` =
    `functional_option_parameters` + `functional_option_parameter_targets`), как у S4k: блок
    `scope_counts` копируется списком, а не одной таблицей, предикат чужих проб сохраняется;
  * порядок вставок — порядок стадий (S4k → S4l), а не алфавит;
  * тексты docstring, утверждавшие смежность «моя стадия стоит прямо перед S4b», правятся тоже:
    с узлов V51–V57 такие утверждения стали неверными в файлах подряд (найдено этим шагом и
    названо в отчёте — молча оставить их значило бы оставить в репозитории живую строку,
    противоречащую `STAGES`);
  * скрипт идемпотентен: уже внесённая строка не вставляется второй раз, отсутствующий якорь
    называется строкой отчёта, а не молчанием.

Запуск:

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v57_p8_legacy_probes_patch.py            # отчёт без записи
    python _v57_p8_legacy_probes_patch.py --write    # запись

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
               "_v54_p8_stop_probe.py", "_v55_p8_stop_probe.py", "_v56_p8_stop_probe.py")
RESUME_PROBES = ("_v51_p8_resume_probe.py", "_v52_p8_resume_probe.py")
ALL_FILES = STOP_PROBES + RESUME_PROBES

ANCHOR = "STAGE_FUNCTIONAL_OPTIONS"          # S4k — стадия-якорь (позиция 2.11)
NEW = "STAGE_FUNCTIONAL_OPTIONS_PARAMETERS"  # S4l — вставляемая стадия (позиция 2.12)
TAIL = "STAGE_OBJECT_MODULES"                # S4b — всегда последняя (вторая транзакция)

# Имена импорта: якорь → добавляемое имя (то же семейство имён, что у слоя V57).
IMPORT_MAP = {
    ANCHOR: [NEW],
    "FUNCTIONAL_OPTIONS_SECTION_HEADER": ["FUNCTIONAL_OPTIONS_PARAMETERS_SECTION_HEADER"],
    "FUNCTIONAL_OPTIONS_TABLES": ["FUNCTIONAL_OPTION_PARAMETERS_TABLES"],
    "FUNCTIONAL_OPTIONS_REMOVE_ORDER": ["FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER"],
    "functional_options_defaults": ["functional_options_parameters_defaults"],
}

# Значения словарей стадий: значение якоря S4k → значение стадии S4l.
VALUE_MAP = {
    '"functional_options"': ['"functional_options_parameters"'],
    "FUNCTIONAL_OPTIONS_SECTION_HEADER": ["FUNCTIONAL_OPTIONS_PARAMETERS_SECTION_HEADER"],
    "functional_options_defaults": ["functional_options_parameters_defaults"],
    '"load_functional_options"': ['"load_functional_options_parameters"'],
    '"load_functional_options_tool"': ['"load_functional_options_parameters_tool"'],
    '"s4k:"': ['"s4l:"'],
    "FUNCTIONAL_OPTIONS_TABLES": ["FUNCTIONAL_OPTION_PARAMETERS_TABLES"],
    "FUNCTIONAL_OPTIONS_REMOVE_ORDER": ["FUNCTIONAL_OPTION_PARAMETERS_REMOVE_ORDER"],
    "format_functional_options_lines": ["format_functional_options_parameters_lines"],
    "functional_options_state_columns": ["functional_options_parameters_state_columns"],
    "FUNCTIONAL_OPTIONS_CIRCLE_BOUNDARY": ["FUNCTIONAL_OPTIONS_PARAMETERS_CIRCLE_BOUNDARY"],
    "FUNCTIONAL_OPTIONS_STATE_VOCABULARIES": ["FUNCTIONAL_OPTIONS_PARAMETERS_STATE_VOCABULARIES"],
    "FUNCTIONAL_OPTIONS_OBSERVATION_KINDS": ["FUNCTIONAL_OPTIONS_PARAMETERS_OBSERVATION_KINDS"],
}


def report_add(report, name, kind, detail):
    report.append((name, kind, detail))


def has_new_entry(lines, idx):
    """Следующая строка уже является записью новой стадии — повтор не нужен."""
    for probe in range(idx + 1, min(idx + 3, len(lines))):
        if NEW in lines[probe]:
            return True
    return False


def add_imports(lines, name, report):
    """Точечная вставка имён новой стадии сразу за импортом якоря.

    Правка держится строки импорта, а не блока целиком: порядок импортов в чужих пробах —
    алфавитный внутри блока `configuration_load_contract`, и вставка «в конец блока» ломала бы
    выравнивание, по которому следующая правка не нашла бы якорь.
    """
    out = []
    imported = " ".join(lines)
    for line in lines:
        out.append(line)
        stripped = line.strip()
        for anchor, targets in IMPORT_MAP.items():
            if stripped != anchor + ",":
                continue
            for target in targets:
                if target + "," in imported:
                    report_add(report, name, "УЖЕ", f"импорт {target}")
                    continue
                out.append(line[:len(line) - len(line.lstrip())] + target + ",")
                report_add(report, name, "ИМПОРТ", f"{anchor} → {target}")
    return out


def split_closers(core):
    """Разделяет выражение значения и закрывающие скобки контейнера словаря.

    Строка вида `stages_after(STAGE_FUNCTIONAL_OPTIONS)})` держит свои скобки внутри:
    наивный отбор «хвоста из скобок» отрезал бы и закрывающую скобку вызова, и пара
    новой стадии осталась бы незакрытой. Разбор идёт по балансу: хвостом считаются только
    те скобки, которые не уравновешены внутри самого выражения.
    """
    depth = 0
    for i, ch in enumerate(core):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                return core[:i], core[i:]
            depth -= 1
    return core, ""


def add_dict_entries(lines, name, report):
    """Клонирует строку словаря стадий: `ANCHOR: <значение>,` → `NEW: <новое значение>,`.

    Строка берётся целиком и правится только по значению — формат ключа, отступ и запятая
    остаются теми же, что у якоря (словари чужих проб свёрнуты по-разному). Отдельная ветка
    держит строку, закрывающую словарь: `…: stages_after(ANCHOR)})` — вставка после неё
    оказалась бы за пределами литерала, поэтому строка разрезается, а новая пара ставится
    последней (значения берутся из того же контракта, различается только стадия).
    """
    key_re = re.compile(r"^(\s*)" + ANCHOR + r"\s*:\s*(.+?)\s*$")
    out = []
    for i, line in enumerate(lines):
        match = key_re.match(line)
        if not match:
            out.append(line)
            continue
        if has_new_entry(lines, i):
            report_add(report, name, "УЖЕ", f"словарь: {line.strip()[:60]}")
            out.append(line)
            continue
        indent, value = match.group(1), match.group(2)
        trailing = ""
        core = value
        if value.endswith(","):
            core, trailing = value[:-1], ","
        inner, close = split_closers(core)
        if close:
            mapped_inner = VALUE_MAP.get(inner, [None])[0]
            if mapped_inner is None and ANCHOR in inner and NEW not in inner:
                mapped_inner = inner.replace(ANCHOR, NEW)
            if mapped_inner is None:
                report_add(report, name, "ЗНАЧЕНИЕ НЕ РАЗОБРАНО",
                           f"строка словаря: {line.strip()[:80]}")
                out.append(line)
                continue
            out.append(f"{indent}{ANCHOR}: {inner},{trailing}")
            out.append(f"{indent}{NEW}: {mapped_inner}{close}{trailing}")
            report_add(report, name, "СЛОВАРЬ (пара в конце литерала)",
                       f"{inner} → {mapped_inner}")
            continue
        mapped = VALUE_MAP.get(core, [None])[0]
        if mapped is None and ANCHOR in core and NEW not in core:
            mapped = core.replace(ANCHOR, NEW)
        if mapped is None:
            report_add(report, name, "ЗНАЧЕНИЕ НЕ РАЗОБРАНО",
                       f"строка словаря: {line.strip()[:80]}")
            out.append(line)
            continue
        out.append(line)
        out.append(f"{indent}{NEW}: {mapped}{trailing}")
        report_add(report, name, "СЛОВАРЬ", f"{core} → {mapped}")
    return out


def line_indent(text, start):
    """Отступ строки, на которой начался матч — continuation-строки наследуют его."""
    line_start = text.rfind("\n", 0, start) + 1
    return re.match(r"\s*", text[line_start:] or "").group(0)


def inner_separator(match):
    """Разделитель элементов перечня: многострочный остаётся как есть, однострочный — перенос.

    Строка перечня в чужих пробах свёрнута по-разному: у V48 элементы кортежа `CHILD_STAGES`
    идут на одной строке, у V50 ожидания `stages_after` — на нескольких. Однострочный вариант
    с вставкой на той же строке вышел бы за границу длины строки, поэтому он переносится с
    отступом самой строки.
    """
    sep = match.group(1) if match.lastindex else ""
    if "\n" in sep:
        return sep
    # Однострочный случай: запятая остаётся, а вот перенос добавляется — с отступом строки,
    # чтобы элемент не вышел за границу длины строки.
    return "," + "\n" + line_indent(match.string, match.start())


def extend_stage_lists(text, name, report):
    """Вставляет новую стадию между якорем и хвостом в явных перечнях (кортежи, списки).

    Правка нужна именно там, где перечень явный: `CHILD_STAGES` (V48–V51), `LATER_STAGES`
    (V53–V56, пробы продолжения), ожидания `stages_after(...)` и перечни `not_run_stages`.
    Проверка «строка остановки называет пропущенные» сравнивает их с `stages_after`, поэтому
    пропуск новой стадии в перечне дал бы провал, а не тихую деградацию.
    """
    pattern = re.compile(ANCHOR + r"(?!_PARAMETERS)(\s*,\s*)" + TAIL)

    def _repl(match):
        inner = inner_separator(match)
        report_add(report, name, "ПЕРЕЧЕНЬ", f"{ANCHOR} → +{NEW} перед {TAIL}")
        # `inner` — исходный разделитель вместе с запятой: элемент добавляется между
        # якорем и хвостом тем же разделителем, каким они разделены в исходном тексте.
        return f"{ANCHOR}{inner}{NEW}{inner}{TAIL}"

    return pattern.sub(_repl, text)


def extend_single_tail_lists(text, name, report):
    """То же для перечней, где хвост один: `== [STAGE_OBJECT_MODULES]`, `LATER_STAGES = (…)`.

    Одноэлементный перечень — не «хвоста нет», а «хвост один»; с узла V57 хвостов два
    (S4l и S4b), и проба обязана называть оба, иначе проверка читала бы пропуск одной стадии
    как совпадение с ожидаемым списком.
    """
    cases = (
        (r"(== )\[" + TAIL + r"\]", "[", "]", "", "ожидание перечня пропущенных"),
        (r"(LATER_STAGES = )\(" + TAIL + r",\)", "(", ")", ",", "кортеж LATER_STAGES"),
    )
    for raw, open_b, close_b, trailing, label in cases:
        pattern = re.compile(raw)

        def _repl(match, _open=open_b, _close=close_b, _trail=trailing, _label=label):
            indent = line_indent(match.string, match.start())
            report_add(report, name, "ПЕРЕЧЕНЬ", _label)
            return f"{match.group(1)}{_open}{NEW},\n{indent}{TAIL}{_trail}{_close}"

        text = pattern.sub(_repl, text)
    return text


def fix_order_chain(text, name, report):
    """Разрывает цепочку `…index(S4k) + 1 == …index(S4b)` на два шага через новую стадию.

    Порядок стадий в `STAGES` — нормативный порядок позиций списка, и проба проверяет его
    именно соседством индексов. С узла V57 соседом S4k является S4l, поэтому прежняя строка
    читалась бы утверждением, которого в `STAGES` нет (провал наступил бы в разделе 1, до
    любого прогона конвейера).
    """
    pattern = re.compile(r"((?:ORDER|order)\.index\()" + ANCHOR + r"\)(\s*\+\s*1\s*==\s*)"
                         r"((?:ORDER|order)\.index\()" + TAIL + r"\)")

    def _repl(match):
        head, mid, tail_head = match.groups()
        indent = line_indent(match.string, match.start())
        report_add(report, name, "ЦЕПОЧКА index", f"{ANCHOR} → {NEW} → {TAIL}")
        # `…index(S4k) + 1 == …index(S4l)` и `…index(S4l) + 1 == …index(S4b)` — два шага
        # вместо одного; `mid` сохраняет переноску исходной строки, если она была. Третья
        # группа держит только `…index(`, имя хвоста подставляется этим же именем константы.
        return (f"{head}{ANCHOR}){mid}{head}{NEW})\n"
                f"{indent}and {head}{NEW}) + 1 == {tail_head}{TAIL})")

    return pattern.sub(_repl, text)


def add_not_in_calls(lines, name, report):
    """Дописывает в проверку счётчика вызовов строку «новая стадия хвоста не звалась».

    Доказывается фактом, а не статусом `not_run` (урок пробы V51). Строка вставляется ПЕРЕД
    строкой якоря: строка якоря может заканчивать булево выражение запятой, и вставка после неё
    разорвала бы аргумент проверки. Для пробы V56, где якорь является остановленной стадией и
    строки `…S4k not in calls` нет, строка ставится перед упоминанием хвоста S4b.
    """
    anchor_re = re.compile(r"^(\s*)and " + ANCHOR + r" not in calls")
    tail_re = re.compile(r"^(\s*.*\band " + TAIL + r" not in calls)(,?)\s*$")
    has_anchor_rule = any(anchor_re.match(line) for line in lines)
    out = []
    for i, line in enumerate(lines):
        ahead = "\n".join(lines[i + 1:i + 4])
        behind = "\n".join(out[-3:])
        match = anchor_re.match(line)
        if match and f"{NEW} not in calls" not in behind and NEW not in match.group(0):
            out.append(f"{match.group(1)}and {NEW} not in calls")
            report_add(report, name, "СЧЁТЧИК ВЫЗОВОВ", f"перед {ANCHOR}")
            out.append(line)
            continue
        tail_match = tail_re.match(line)
        if tail_match and not has_anchor_rule:
            if f"{NEW} not in calls" not in ahead and f"{NEW} not in calls" not in behind:
                indent = line[:len(line) - len(line.lstrip())]
                report_add(report, name, "СЧЁТЧИК ВЫЗОВОВ", f"после {TAIL}")
                out.append(tail_match.group(1))
                out.append(f"{indent}and {NEW} not in calls{tail_match.group(2)}")
            else:
                out.append(line)
            continue
        out.append(line)
    return out


def add_stage_title_card(lines, name, report):
    """Требует от карточки остановки называть и пропуск новой стадии (правило C2).

    Карточка обязана называть словом формата каждую пропущенную стадию хвоста; пробы V53–V56
    перечисляют их заголовками `stage_title(...)`, поэтому без строки S4l проверка принимала бы
    карточку, в которой пропуска новой стадии нет.
    """
    anchor_re = re.compile(r"^(\s*)and stage_title\(" + ANCHOR + r"\) in card")
    out = []
    for line in lines:
        match = anchor_re.match(line)
        if match and f"stage_title({NEW})" not in "\n".join(out[-2:]):
            out.append(f"{match.group(1)}and stage_title({NEW}) in card")
            report_add(report, name, "ЗАГОЛОВОК КАРТОЧКИ", f"перед {ANCHOR}")
        out.append(line)
    return out


def add_child_stage_condition(lines, name, report):
    """Добавляет явное условие вхождения S4l в перечень стадий детей (контур 1.4в пробы V52).

    Равенство `CHILD_STAGES == tuple(... из STAGES ...)` формально покрывает и новую стадию, но
    проба дополнительно называет каждую стадию продолжения явным условием — так проверка не
    принимает перечень, в котором новой стадии просто нет (приём патчера узла V56, строка 197:
    `and STAGE_FUNCTIONAL_OPTIONS in CHILD_STAGES` после строки `STAGE_BOTS`). Условие вставляется
    той же строкой, что и соседние: перенос внутри литерала ломал бы синтаксис условия.
    """
    anchor_re = re.compile(r"^(\s*)and " + ANCHOR + r" in CHILD_STAGES(?P<tail>,?)\s*$")
    out = []
    for i, line in enumerate(lines):
        out.append(line)
        match = anchor_re.match(line)
        # Условие вставляется ПОСЛЕ строки якоря, поэтому идемпотентность читается следующей
        # строкой исходного файла, а не уже собранным `out`: к моменту совпадения вставленная
        # строка ещё не попала в `out`, и повторный прогон удваивал бы её (замер первого
        # прогона этого патчера — `ФАЙЛОВ СНОВА ИЗМЕНЕНО: 1`).
        ahead = lines[i + 1] if i + 1 < len(lines) else ""
        if match and f"and {NEW} in CHILD_STAGES" not in ahead:
            report_add(report, name, "ПЕРЕЧЕНЬ ДЕТЕЙ", f"после {ANCHOR} in CHILD_STAGES")
            out.append(f"{match.group(1)}and {NEW} in CHILD_STAGES{match.group('tail')}")
    return out


def duplicate_scope_loop(lines, name, report):
    """Копирует подсчёт круга S4k в `scope_counts` для круга S4l (две таблицы вида).

    `scope_counts` — ответ пробы на вопрос «что осталось в базе после остановки». Пропущенная
    стадия не обязана заполнять свои таблицы, и проба обязана видеть это числом; без строк S4l
    число просто отсутствовало бы — это молчание, а не ноль (правило C1).
    """
    out = []
    joined = "\n".join(lines)
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        if line.strip() != "for table in FUNCTIONAL_OPTIONS_TABLES:":
            i += 1
            continue
        if "for table in FUNCTIONAL_OPTION_PARAMETERS_TABLES:" in joined:
            report_add(report, name, "УЖЕ", "цикл круга S4l")
            i += 1
            continue
        block = [line]
        j = i + 1
        while j < len(lines) and not lines[j].strip().endswith("or 0)"):
            block.append(lines[j])
            j += 1
        if j >= len(lines):
            report_add(report, name, "НЕ СОЙШЛОСЬ", "тело цикла круга S4k не замкнуто")
            i += 1
            continue
        block.append(lines[j])
        indent = line[:len(line) - len(line.lstrip())]
        copy = [f"{indent}# Узел V57 (шаг П8): строки S4l входят в «что осталось в базе»",
                f"{indent}# по тому же правилу. Круг вида — две таблицы (замер 1.2 плана",
                f"{indent}# узла V57); перечень берётся из словаря слоя."]
        for part in block:
            copy.append(part.replace("FUNCTIONAL_OPTIONS_TABLES",
                                     "FUNCTIONAL_OPTION_PARAMETERS_TABLES")
                         .replace('"s4k:"', '"s4l:"'))
        # Исходный блок остаётся в файле как есть, копия идёт сразу за ним: правка
        # добавляет подсчёт нового круга, а не переносит чужой.
        out.extend(block[1:])
        out.extend(copy)
        report_add(report, name, "SCOPE_COUNTS", "цикл круга S4l")
        i = j + 1
    return out


# Текстовые утверждения проб. Отдельной строки они не меняют, но утверждают состав хвоста
# стадий, а состав хвоста с узла V57 изменился: строка «S4k и S4b» в тексте проверки или в
# docstring читалась бы утверждением, которого в `STAGES` больше нет. Правило 6 и 7 правят и
# docstring-утверждения о смежности («моя стадия стоит прямо перед S4b») — они устарели для
# узлов V49–V56, потому что узлы V51–V57 вставляли стадии между ними и S4b; молча оставить
# их — значит оставить в репозитории живую строку, противоречащую контракту.
TEXT_RULES = [
    ('"2.12" not in CHILD_NOT_IMPLEMENTED', '"2.13" not in CHILD_NOT_IMPLEMENTED',
     "граница незакрытой части"),
    (r"S4k и S4b", "S4k, S4l и S4b", "перечень хвоста в тексте"),
    (r"S4k и \"", "S4k, S4l и \"", "перечень хвоста в тексте (перенос строки)"),
    (r"с учётом (S4[a-z](?:, S4[a-z])*) и S4k,", r"с учётом \1, S4k и S4l,",
     "описание раздела пробы"),
    (r"с учётом S4k,", "с учётом S4k и S4l,", "описание раздела пробы"),
    (r"→ S4k → S4b", "→ S4k → S4l → S4b", "цепочка порядка в тексте проверки"),
    (r"оказываются S4[a-z], S4[a-z], S4[a-z] и S4b",
     "оказываются все стадии продолжения до S4b включительно",
     "перечень пропущенных в комментарии"),
    (r"стоит в `STAGES` между (`s4[a-z_]+`)( \(([\d.]+)\))? и\s+`s4b_object_modules`",
     "стоит в `STAGES` сразу после `\\1`\\3, а за ней —\n    остальные стадии продолжения, "
     "последней `s4b_object_modules`",
     "утверждение о смежности стадии"),
    (r"стадия внесена в `STAGES` между `s4f_exchange_plans` и `s4b_object_modules`",
     "стадия внесена в `STAGES` сразу после `s4f_exchange_plans`",
     "утверждение о смежности в пробе продолжения"),
    (r"у S4g — S4h и\s*# S4b, у S4h \(узел V53\) — только S4b\.",
     "у S4g — S4h и весь хвост продолжения,\n        # у S4h (узел V53) — тоже весь хвост.",
     "перечень пропущенных в комментарии"),
    # Перечисление, в котором новая стадия уже названа (правило 2), остаётся как есть:
    # оно верно. Правится только утверждение «за мной — только S4b», которого в `STAGES`
    # больше нет. Переноса строки в подстановке нет намеренно: та же формулировка встречается
    # внутри строковых литералов заголовков проверок, и перенос разорвал бы литерал.
    (r"а для (S4[a-z]) — (?:только|ровно(?: с)?|`s4)(?:(?!S4l)[^:]){0,160}?:",
     "а для \\1 — весь хвост продолжения, посчитанный из `STAGES`:",
     "ожидание stages_after в описании"),
    # Число стадий детей в пробе V52 (контур 1.4в) выводится из `STAGES`, но одновременно
    # утверждается и числом, и словом в заголовке проверки. Патчеры прежних узлов поднимали то
    # же число (8→9 у V53, 9→10 у V54, 10→11 у V55, 11→12 у V56) — с узла V57 детей тринадцать.
    ('двенадцать стадий, S4g, S4h, S4i, S4j и S4k входят',
     'тринадцать стадий, S4g, S4h, S4i, S4j, S4k и S4l входят',
     'текст: перечень стадий детей'),
    (r"len\(CHILD_STAGES\) == 12", "len(CHILD_STAGES) == 13",
     "число стадий детей"),
]


def apply_text_rules(text, name, report):
    for raw, replacement, label in TEXT_RULES:
        pattern = re.compile(raw)
        hits = len(pattern.findall(text))
        if not hits:
            continue
        text = pattern.sub(replacement, text)
        report_add(report, name, "ТЕКСТ", f"{label} — {hits}")
    return text


def verify(text, name, report):
    """Сверка полноты: остаток прежнего порядка называется строкой отчёта, а не молчанием."""
    residues = [
        (ANCHOR + r"(?!_PARAMETERS)(\s*,\s*)" + TAIL, "перечень S4k→S4b (остаток)"),
        (r"== \[" + TAIL + r"\]", "ожидание одного хвоста (остаток)"),
        (r"LATER_STAGES = \(" + TAIL + r",\)", "LATER_STAGES (остаток)"),
        (r"(?:ORDER|order)\.index\(" + ANCHOR + r"\) \+ 1\s*==\s*(?:ORDER|order)\.index\("
         + TAIL + r"\)", "цепочка index (остаток)"),
        (r'(?:ORDER|order)\.index\("' + ANCHOR, "цепочка index c кавычками (остаток)"),
        ('"2.12" not in CHILD_NOT_IMPLEMENTED', "граница CHILD_NOT_IMPLEMENTED (остаток)"),
        (r"S4k и S4b", "перечень хвоста (остаток)"),
        (r"→ S4k → S4b", "цепочка порядка в тексте (остаток)"),
        (r"в `STAGES` между[^:]{0,140}?и `s4b_object_modules`",
         "утверждение о смежности (остаток)"),
        (r"а для S4[a-z] — (?:только|ровно(?: с)?)\s*(?:`s4b_object_modules`|S4b)\b",
         "ожидание stages_after в описании (остаток)"),
        (r"len\(CHILD_STAGES\) == 12", "число стадий детей (остаток)"),
        ('двенадцать стадий, S4g', "текст перечня стадий детей (остаток)"),
    ]
    for raw, label in residues:
        if re.search(raw, text):
            report_add(report, name, "НЕ СОЙШЛОСЬ", label)
    if ("for table in FUNCTIONAL_OPTIONS_TABLES:" in text
            and "for table in FUNCTIONAL_OPTION_PARAMETERS_TABLES:" not in text):
        report_add(report, name, "НЕ СОЙШЛОСЬ", "цикл круга S4l")
    key_re = re.compile(r"^(\s*)" + ANCHOR + r"\s*:\s*(.+?),?\s*$", re.MULTILINE)
    for match in key_re.finditer(text):
        tail_window = text[match.end(): match.end() + 200]
        if NEW not in tail_window.split("\n", 3)[0] and NEW not in "\n".join(
                tail_window.split("\n")[:3]):
            report_add(report, name, "НЕ СОЙШЛОСЬ",
                       f"пара словаря: {match.group(0).strip()[:70]}")
    imports = text[text.find("from configuration_load_contract import ("):]
    for anchor, targets in IMPORT_MAP.items():
        for target in targets:
            if anchor + "," in imports and target + "," not in imports:
                report_add(report, name, "НЕ СОЙШЛОСЬ", f"импорт {target}")


def process(name, report):
    """Один файл: сначала точечные вставки построчно, затем перечни и тексты, затем сверка."""
    path = ROOT / name
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    lines = add_imports(lines, name, report)
    lines = add_dict_entries(lines, name, report)
    lines = add_not_in_calls(lines, name, report)
    lines = add_stage_title_card(lines, name, report)
    lines = add_child_stage_condition(lines, name, report)
    lines = duplicate_scope_loop(lines, name, report)
    text = "\n".join(lines)
    text = extend_stage_lists(text, name, report)
    text = extend_single_tail_lists(text, name, report)
    text = fix_order_chain(text, name, report)
    text = apply_text_rules(text, name, report)
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
    bad = [row for row in report if row[1].startswith(("ОТСУТСТВУЕТ", "НЕ СОЙШЛОСЬ",
                                                       "ЗНАЧЕНИЕ"))]
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
