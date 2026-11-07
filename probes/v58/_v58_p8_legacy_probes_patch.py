#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Правка прежних стоп-проб П8 (узлов V54–V57) под состав стадий с S4m (узел V58) и
пакетом десяти позиций V59 — шаг П8 узлов V58/V59.

Зачем она обязательна. Узлы V58 и V59 поставили в `STAGES` одиннадцать стадий:
`s4m_defined_types` (позиция 2.13) и десять позиций пакета `s4n…s4w` (2.18–2.20, 2.23,
2.25–2.28, 5.2, 19). Прежние стопы-пробы держат хвост явными перечнями
(`LATER_STAGES`, литералы `stages_after(...)`, перечни `not_run_stages`, цепочки
`order.index(...)`) и текстовыми утверждениями о нём, поэтому падали не из-за поломки
конвейера, а из-за собственных ожиданий (замер П8: V53–V57 по шесть провалов).

Второй круг правки — узел TOOL-DROP (05.11.2026): отдельного входа дозыгрузки позиции ни у
одной стадии нет, `STAGE_FULL_RELOAD_ONLY` у всех стадий `True`, а константы
`*_REPEAT_HINT` приведены к алиасу общей `STAGE_REPEAT_HINT`. Проверки, требовавшие в
подсказке `load_<вид>_tool`, требовали текста, которого в реестре инструментов больше нет.

Границы правки:

  * содержательных проверок чужих узлов скрипт НЕ убирает: перечень пропущенных остаётся
    явным (критерий П8), но круг десяти позиций берётся реестром
    `configuration_position_spec` — второй копии круга проба не заводит (прецедент пробы
    V48, шаг П8 узла V58);
  * тело и заголовок проверки меняются ОДНИМ правилом: механическая замена тела при старом
    заголовке оставила бы проверку, имя которой противоречит её коду (замер П8 — класс B2,
    где границу «не называть 2.13» сдвигали узлами V54→V57 вручную);
  * десять позиций пакета не входят в перечень наблюдаемых вызовов (`LATER_STAGES`):
    отдельной функции-стадии у них в загрузчике нет, их пропуск читается перечнем
    `not_run_stages`, и это названо текстом проверки, а не пропущено молча;
  * идемпотентность: уже внесённая правка помечается «УЖЕ», а не удваивается; правило,
    которое не сошлось, называется строкой отчёта, а не молчанием.

Запуск:

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python probes/v58/_v58_p8_legacy_probes_patch.py            # отчёт без записи
    python probes/v58/_v58_p8_legacy_probes_patch.py --write    # запись

Код возврата 0 — все правила применены или уже внесены; 1 — есть не совшедшее правило.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBES = ("_v54_p8_stop_probe.py", "_v55_p8_stop_probe.py",
          "_v56_p8_stop_probe.py", "_v57_p8_stop_probe.py")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ── вставки общего состава ────────────────────────────────────────────────────────────
IMPORT_FRAME = (
    "# Узел V58 (шаг П8): узел V59 закрыл десять позиций пакета ОДНОЙ спецификацией, и "
    "отдельной\n"
    "# функции-стадии у них в загрузчике нет (один цикл `for frame_spec in "
    "position_frame_specs()`).\n"
    "# Перечень их стадий проба берёт реестром `configuration_position_spec`, а не текстом: "
    "вторая\n"
    "# копия круга и есть то, что рассинхронизировало пробу с `STAGES` на одиннадцать стадий.\n"
    "from configuration_position_spec import ordered_specs as frame_specs  # noqa: E402\n"
)
FRAME_DEF = (
    "# Стадии пакета V59 — выводом из реестра позиций (импорт `frame_specs` выше), а не "
    "списком:\n"
    "# вторая копия круга расходилась бы с `STAGES` молча. Ответ остановки обязан назвать "
    "каждую из\n"
    "# них — пропущенная стадия читается текстом (правило C2).\n"
    'FRAME_STAGES = tuple(spec["stage"] for spec in frame_specs())\n'
)


# Префикс f у заголовка — не оптика: проверки вида `check(f"1.8 `{stage}`: …")` встречаются
# в чужих пробах чаще, чем без него, и не замеченные правилцом ожидания оставались прежними
# (замер П8 на V49: 13 расхождений в одной лишь проверке 1.8).
CHECK_RE = re.compile(r'^(?P<indent> *)check\((?P<f>f)?"(?P<num>\d+(?:\.\d+)?[а-я]?)\s')


def close_call(text):
    """Позиция сразу за закрывающей скобкой вызова, открывающегося в начале `text`.

    Границей блока служит глубина скобок, а не отступ: continuation-строки в чужих пробах
    бывают с отступом МЕНЬШЕ, чем у `check(` (замер П8 — строка ` and "2.13" not in …` с
    одним пробелом и ` STAGE_OBJECT_MODULES,)` в нулевом отступе), и правка «до строки с
    меньшим отступом» резала блок посередине выражения.
    """
    depth = 0
    index = 0
    quote = None
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in "\"'":
            quote = char
            index += 1
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return len(text)


def find_blocks(lines, number):
    """Находит блоки проверки с номером `number`: (первая строка, строка после блока)."""
    out = []
    for i, line in enumerate(lines):
        match = CHECK_RE.match(line)
        if not match or match.group("num") != number:
            continue
        joined = "\n".join(lines[i:])
        end = i + joined[:close_call(joined)].count("\n") + 1
        out.append((i, end))
    return out


def title_last_line(block_lines):
    """Индекс строки, которой заканчивается литерал заголовка (последняя строка с `",`)."""
    for k, line in enumerate(block_lines):
        if line.rstrip().endswith('",'):
            return k
    return -1


def set_title(block_lines, sentences):
    """Целиком заменяет заголовок блока: тело и заголовок расходятся, если править их по отдельности."""
    last = title_last_line(block_lines)
    if last < 0:
        return block_lines, False
    indent = block_lines[0][:len(block_lines[0]) - len(block_lines[0].lstrip())]
    title = [f'{indent}check("{sentences[0]}"']
    for part in sentences[1:-1]:
        title.append(f'{indent}      "{part}"')
    title.append(f'{indent}      "{sentences[-1]}",')
    return title + block_lines[last + 1:], True


def append_title(block_lines, sentence):
    """Дописывает в конец заголовка одно утверждение — заголовок обязан описывать новое тело."""
    last = title_last_line(block_lines)
    if last < 0:
        return block_lines, False
    line = block_lines[last].rstrip()
    body = line[:-2].rstrip()
    return block_lines[:last] + [f'{body}; {sentence}",'] + block_lines[last + 1:], True


def _subn(pattern, repl, text):
    """Один вызов замены для строкового и скомпилированного паттерна.

    Многострочные литералы перечней требуют re.S, а `re.subn` с флагом отказывается
    работать уже с скомпилированным паттерном — различие закрывает этот помощник.
    """
    if hasattr(pattern, "subn"):
        return pattern.subn(repl, text)
    return re.subn(pattern, repl, text, flags=re.M)


def title_sub(block_lines, pattern, repl):
    """Точечная правка текста заголовка (например перечня стадий в нём)."""
    last = title_last_line(block_lines)
    if last < 0:
        return block_lines, False
    head, n = _subn(pattern, repl, "\n".join(block_lines[:last + 1]))
    if n == 0:
        return block_lines, False
    return head.split("\n") + block_lines[last + 1:], True


def body_sub(block_lines, pattern, repl):
    """Правка тела блока (строки после заголовка)."""
    last = title_last_line(block_lines)
    if last < 0:
        return block_lines, False
    body, n = _subn(pattern, repl, "\n".join(block_lines[last + 1:]))
    if n == 0:
        return block_lines, False
    return block_lines[:last + 1] + body.split("\n"), True


def line_indent_of(text, pos):
    """Отступ строки, на которой начинается позиция — continuation-строки наследуют его."""
    start = text.rfind("\n", 0, pos) + 1
    return re.match(r"\s*", text[start:] or "").group(0)


def tail_literal(block_lines):
    """Достраивает литерал перечня стадий: `… STAGE_OBJECT_MODULES]` → `… S4m] + пакет + [S4b]`.

    Хвост перечень обязан называть: пропущенная стадия читается перечнем (правило C2).
    Десять позиций пакета при этом берутся реестром `frame_specs()` — второй копии круга в
    пробе не появляется (именно вторая копия и отстаёт молча).
    """
    last = title_last_line(block_lines)
    if last < 0:
        return block_lines, False
    text = "\n".join(block_lines[last + 1:])
    if "FRAME_STAGES" in text:
        return block_lines, False

    def _repl(match):
        indent = line_indent_of(text, match.start())
        tail = match.group("tail") or ""
        return ("STAGE_DEFINED_TYPES] + list(FRAME_STAGES)\n"
                + indent + "+ [STAGE_OBJECT_MODULES]" + tail)

    new_text, n = re.subn(r"STAGE_OBJECT_MODULES\](?P<tail>,?)$", _repl, text, flags=re.M)
    if n == 0:
        return block_lines, False
    return block_lines[:last + 1] + new_text.split("\n"), n


# ── классы блоков: класс читается содержимым, а не номером ───────────────────────────
# Номера у чужих узлов разъезжаются (у V53 вызовы — это 2.7, у V57 — 2.8), поэтому класс
# блока определяется признаком тела: `not_run_stages` — остановка, `in calls` — счётчик
# вызовов, `in card` — карточка. Номер нужен только для отчёта.
STOP_MARK = "not_run_stages"
CALLS_MARK = "in calls"
CARD_MARK = "in card"

TAIL_PHRASE = "S4m, десять позиций пакета V59 и S4b"
FRAME_CLAUSE = ("и десять позиций пакета V59 сверяются реестром позиций, а не списком в пробе "
                "(вторая копия круга расходится молча)")


def report_add(report, probe, where, note):
    report.append((probe, where, note))


def label_of(title_text):
    """Короткое имя стадии (`S4i`) из заголовка самой проверки — выдумывать его проба не вправе."""
    match = re.search(r"S4[a-z]", title_text)
    return match.group(0) if match else "стадии"


def patch_offline_block(block, probe, number, report):
    """Правка офлайн-блоков 1.1, 1.2, 1.5, 1.6, 1.11."""
    joined = "\n".join(block)
    title = "\n".join(block[:title_last_line(block) + 1])
    if number == "1.1":
        block, res = body_sub(
            block, r"\+\s*1\s*==\s*order\.index\(STAGE_OBJECT_MODULES\)",
            "+ 1\n          == order.index(STAGE_DEFINED_TYPES)\n"
            "          and order[order.index(STAGE_DEFINED_TYPES) + 1:]"
            " == list(FRAME_STAGES) + [STAGE_OBJECT_MODULES]")
        report_add(report, probe, "1.1 хвост порядка",
                   "ПРИМЕНЕНО" if res else ("УЖЕ" if "FRAME_STAGES" in joined else "НЕ СОШЛОСЬ"))
        if res:
            block, _ = append_title(block, FRAME_CLAUSE)
        return block
    if number == "1.2":
        block, res = tail_literal(block)
        report_add(report, probe, "1.2 stages_after",
                   "ПРИМЕНЕНО" if res else ("УЖЕ" if "FRAME_STAGES" in joined else "НЕ СОШЛОСЬ"))
        if res:
            block, _ = title_sub(block, r" и S4b\b", f", {TAIL_PHRASE}")
        return block
    if number == "1.5":
        tool = re.search(r'"(load_[a-z_]+_tool)"', joined)
        hint = re.search(r"== ([A-Z_]+_REPEAT_HINT)", joined)
        stage = re.search(r"STAGE_FULL_RELOAD_ONLY\.get\((STAGE_[A-Z_]+)\)", joined)
        if not (tool and hint and stage):
            report_add(report, probe, "1.5 подсказка", "НЕ РАЗОБРАНО")
            return block
        if "STAGE_REPEAT_HINT" in joined:
            # Повторный прогон: ожидание уже читает общий текст подсказки, вторая копия
            # сравнения (`STAGE_REPEAT_HINT is STAGE_REPEAT_HINT`) появилась бы из-за того,
            # что имя константы в теле совпадает с именем новой (замер идемпотентности).
            report_add(report, probe, "1.5 подсказка", "УЖЕ")
            return block
        block, r1 = body_sub(block, r"(STAGE_FULL_RELOAD_ONLY\.get\([A-Z_]+\) is) False", r"\1 True")
        block, r2 = body_sub(
            block, rf'and "{re.escape(tool.group(1))}"\s*in\s*stage_resume_hint\({stage.group(1)}\)',
            rf'and "{tool.group(1)}" not in stage_resume_hint({stage.group(1)})')
        block, r3 = body_sub(
            block, rf"stage_resume_hint\({stage.group(1)}\)\s*==\s*{hint.group(1)}",
            "stage_resume_hint(" + stage.group(1) + ") == STAGE_REPEAT_HINT\n"
            "          and " + hint.group(1) + " is STAGE_REPEAT_HINT")
        done = r1 and r2 and r3
        report_add(report, probe, "1.5 подсказка",
                   "ПРИМЕНЕНО" if done else
                   ("УЖЕ" if "STAGE_REPEAT_HINT" in joined else "НЕ СОШЛОСЬ"))
        if done:
            block, _ = set_title(block, [
                f'1.5 подсказка продолжения для {label_of(title)} называет полную перезагрузку,',
                f'а не отдельный вход `{tool.group(1)}`: узел TOOL-DROP (05.11.2026) снял',
                f'отдельный вход позиции и свёл константу `{hint.group(1)}` к алиасу общей',
                '`STAGE_REPEAT_HINT` — прежняя проверка требовала текста, которого в реестре',
                'инструментов больше нет. Ключ `STAGE_FULL_RELOAD_ONLY` обязан быть объявлен',
                'значением `True`, а не унаследован по умолчанию (урок П8 узла V51: значение по',
                'умолчанию маскирует отсутствие ветви `stage_resume_hint`)',
            ])
        return block
    if number == "1.6":
        pos = re.search(r'"(\d+\.\d+)" in CHILD_NOT_IMPLEMENTED', joined)
        if not pos:
            report_add(report, probe, "1.6 граница текста", "НЕ РАЗОБРАНО")
            return block

        def _boundary(match):
            # Отступ захвачен вместе с `and`: совпадение может начинаться и в середине строки
            # (замер П8 — V56, где `and "2.13" not in …` шло продолжением предыдущей строки).
            # Без возвращённого откупа склейка давала бы `CHILD_NOT_IMPLEMENTEDand "2.12"`.
            indent = match.group("ind")
            return (indent + 'and "2.12" in CHILD_NOT_IMPLEMENTED\n'
                    + indent + 'and "2.13" in CHILD_NOT_IMPLEMENTED\n'
                    + indent + 'and all(spec["position"] in CHILD_NOT_IMPLEMENTED '
                    'for spec in frame_specs())\n'
                    + indent + 'and "V18" in CHILD_NOT_IMPLEMENTED'
                    + (match.group("tail") or ""))

        last = title_last_line(block)
        body = "\n".join(block[last + 1:])
        new_body, n = re.subn(
            r'(?P<ind> *)and "2\.13" not in CHILD_NOT_IMPLEMENTED(?P<tail>,?)$',
            _boundary, body, flags=re.M)
        report_add(report, probe, "1.6 граница текста",
                   "ПРИМЕНЕНО" if n else ("УЖЕ" if "frame_specs()" in body else "НЕ СОШЛОСЬ"))
        if n:
            block = block[:last + 1] + new_body.split("\n")
            block, _ = set_title(block, [
                f'1.6 незакрытая часть (`CHILD_NOT_IMPLEMENTED`) называет позицию '
                f'{pos.group(1)} закрытой для этого',
                'вида и называет закрытыми все позиции, закрытые стадиями детей: 2.9…2.13',
                '(узлы V54–V58) и десять позиций пакета V59 — круг читается реестром',
                '`configuration_position_spec`. Прежняя граница «не называть 2.13» устарела',
                'узлами V58 и V59; инвариант «текст обязан называть каждую закрытую позицию»',
                'держит постоянная проверка `tools/check_position_frame.py` (контур 12), а',
                'открытая часть названа самим текстом — узлом V18',
            ])
        return block
    if number == "1.11":
        tool = re.search(r'"(load_[a-z_]+_tool)" in text', joined)
        if not tool:
            report_add(report, probe, "1.11 форматёр на отказе",
                       "УЖЕ" if "STAGE_REPEAT_HINT in text" in joined else "НЕ СОШЛОСЬ")
            return block
        block, res = body_sub(
            block, rf'and "{tool.group(1)}" in text',
            'and STAGE_REPEAT_HINT in text\n          and "' + tool.group(1) + '" not in text')
        report_add(report, probe, "1.11 форматёр на отказе", "ПРИМЕНЕНО" if res else "НЕ СОШЛОСЬ")
        if res:
            block, _ = append_title(
                block, 'подсказка — общая `STAGE_REPEAT_HINT`, потому что отдельный вход '
                       'позиции снят узлом TOOL-DROP')
        return block
    return block


def patch_live_block(block, probe, number, report):
    """Правка живых блоков: счётчик вызовов, карточка, остановка (`not_run_stages`).

    Порядок проверок — от частного к общему: заголовок проверки счётчика тоже упоминает
    статус `not_run`, и более общий признак раньше забрал бы блок себе (замер П8 —
    «2.7 остановка: НЕ СОШЛОСЬ» вместо правила счётчика).
    """
    joined = "\n".join(block)
    title = "\n".join(block[:title_last_line(block) + 1])
    already = "STAGE_DEFINED_TYPES" in joined
    if CALLS_MARK in joined:
        if already:
            report_add(report, probe, f"{number} счётчик вызовов", "УЖЕ")
            return block
        block, res = body_sub(
            block, r"and STAGE_FUNCTIONAL_OPTIONS_PARAMETERS not in calls",
            lambda m: add_after(m, "and STAGE_DEFINED_TYPES not in calls"))
        if not res:
            block, res = body_sub(
                block, r"and not calls\.get\(STAGE_OBJECT_MODULES\)",
                lambda m: add_before(m, "and not calls.get(STAGE_DEFINED_TYPES)"))
        report_add(report, probe, f"{number} счётчик вызовов", "ПРИМЕНЕНО" if res else "НЕ СОШЛОСЬ")
        if res:
            block, _ = title_sub(block, r" и S4b\b", f", {TAIL_PHRASE}")
            block, _ = append_title(
                block, 'десять позиций пакета V59 счётчиком не проверяются: отдельной '
                       'функции-стадии у них нет, их пропуск назван перечнем `not_run_stages`')
        return block
    if CARD_MARK in joined:
        if already:
            report_add(report, probe, f"{number} карточка остановки", "УЖЕ")
            return block
        block, res = body_sub(
            block, r"and stage_title\(STAGE_FUNCTIONAL_OPTIONS_PARAMETERS\) in card",
            lambda m: add_after(
                m, 'and stage_title(STAGE_DEFINED_TYPES) in card\n'
                   'and all(stage_title(_stage) in card for _stage in FRAME_STAGES)'))
        if not res:
            block, res = body_sub(
                block, r"and stage_title\(STAGE_OBJECT_MODULES\) in card",
                lambda m: add_before(
                    m, 'and stage_title(STAGE_DEFINED_TYPES) in card\n'
                       'and all(stage_title(_stage) in card for _stage in FRAME_STAGES)'))
        report_add(report, probe, f"{number} карточка остановки",
                   "ПРИМЕНЕНО" if res else "НЕ СОШЛОСЬ")
        if res:
            block, _ = title_sub(block, r" и S4b\b", f", {TAIL_PHRASE}")
        return block
    if STOP_MARK in joined:
        if already:
            report_add(report, probe, f"{number} остановка", "УЖЕ")
            return block
        tool = re.search(r'"(load_[a-z_]+_tool)" in str\(stopped\.get\("resume_with"\)\)', joined)
        block, r1 = tail_literal(block)
        block, r2 = body_sub(
            block,
            r'(?:and\s+)?"load_[a-z_]+_tool"\s*in\s*str\(stopped\.get\("resume_with"\)\)',
            lambda m: ("and " if m.group(0).lstrip().startswith("and") else "")
            + 'STAGE_REPEAT_HINT in str(stopped.get("resume_with"))')
        block, r3 = body_sub(
            block, r'(stopped\.get\("full_reload_required"\)\s*is) False', r"\1 True")
        done = r1 and r2 and r3
        report_add(report, probe, f"{number} остановка", "ПРИМЕНЕНО" if done else "НЕ СОШЛОСЬ")
        if done and tool:
            block, _ = set_title(block, [
                f'{number} конвейер остановлен именно на {label_of(title)} и подсказывает '
                'полную перезагрузку:',
                f'отдельный вход позиции `{tool.group(1)}` снят узлом TOOL-DROP (05.11.2026), '
                'поэтому',
                '`full_reload_required` — `True`, а подсказка общая (критерий П8, решение Q8 '
                'варианта A',
                f'в редакции TOOL-DROP); в перечне пропущенных — {TAIL_PHRASE},',
                'посчитанная из `STAGES`',
            ])
        return block
    return block


def add_after(match, line_text):
    """Дописывает строку сразу после совпадения, сохраняя отступ совпавшей строки.

    Отступ получает КАЖДАЯ переносимая строка, а не первая: вставка из двух строк без
    отступа второй строки читалась бы как мусор (замер П8 — `and all(...)` с нулевого
    столбца внутри условия).
    """
    indent = line_indent_of(match.string, match.start())
    return match.group(0) + "\n" + ("\n" + indent).join(line_text.split("\n"))


def add_before(match, line_text):
    """Ставит строку перед совпадением, сохраняя отступ совпавшей строки."""
    indent = line_indent_of(match.string, match.start())
    return ("\n" + indent).join(line_text.split("\n")) + "\n" + indent + match.group(0)


# ── правила общего состава (весь файл, а не блок проверки) ───────────────────────────
# Словари стадий чужих проб не достраиваются построчно: им нужен только импорт реестра и
# вывод перечня стадий пакета — так же, как в пробе V48 (шаг П8 узла V58). Вторая копия
# круга в пробе не появляется ни в одном словаре.
STRUCT_RULES = (
    ("LATER_STAGES: одиночный S4b", "LATER_STAGES = (STAGE_DEFINED_TYPES,",
     re.compile(r"^LATER_STAGES = \(STAGE_OBJECT_MODULES,\)$", re.M),
     "LATER_STAGES = (STAGE_DEFINED_TYPES,\nSTAGE_OBJECT_MODULES,)"),
    ("LATER_STAGES: S4m перед S4b", "STAGE_DEFINED_TYPES,\nSTAGE_OBJECT_MODULES,)",
     re.compile(r"^STAGE_OBJECT_MODULES,\)$", re.M),
     "STAGE_DEFINED_TYPES,\nSTAGE_OBJECT_MODULES,)"),
    ("определение FRAME_STAGES", "FRAME_STAGES = tuple(",
     re.compile(r"^STAGE_OBJECT_MODULES,\)$", re.M),
     "STAGE_OBJECT_MODULES,)\n" + FRAME_DEF),
    ("STAGE_FUNCTIONS: функция S4m", 'STAGE_DEFINED_TYPES: "load_defined_types",',
     re.compile(r'^    STAGE_OBJECT_MODULES: "load_object_modules",$', re.M),
     '    STAGE_DEFINED_TYPES: "load_defined_types",\n'
     '    STAGE_OBJECT_MODULES: "load_object_modules",'),
    ("импорт STAGE_DEFINED_TYPES", "    STAGE_DEFINED_TYPES,",
     re.compile(r"^    STAGE_COMMON_ATTRIBUTES,$", re.M),
     "    STAGE_COMMON_ATTRIBUTES,\n    STAGE_DEFINED_TYPES,"),
    ("импорт STAGE_REPEAT_HINT", "    STAGE_REPEAT_HINT,",
     re.compile(r"^    STAGE_ROLES,$", re.M),
     "    STAGE_REPEAT_HINT,\n    STAGE_ROLES,"),
    ("импорт реестра позиций", "from configuration_position_spec import ordered_specs",
     re.compile(r"^from external_db import connect  # noqa: E402$", re.M),
     IMPORT_FRAME + "from external_db import connect  # noqa: E402"),
)

BLOCK_NUMBERS = ("1.1", "1.2", "1.5", "1.6", "1.11",
                 "2.5", "2.6", "2.7", "2.8", "2.9")

# ── правила V49…V52: словари ожидания читаются составом стадий ──────────────────────
# Эти пробы держат пять словарей по стадиям (`STAGE_KEYS`, `SECTION_HEADERS`, `DEFAULTS`,
# `STAGE_FUNCTIONS`, `RESUME_MARKS`) и обходят `ast.walk` в `function_defs`. Причина
# падения — вторая копия круга стадий (замер П8: `KeyError: 's4m_defined_types'`) и имена
# снятых инструментов в `RESUME_MARKS`. Приём — тот же, что у зелёной пробы
# `probes/v48/_v58…`: словари достраиваются выводом из реестра позиций, а не списком.
PROBES_49 = ("_v49_p8_stop_probe.py", "_v50_p8_stop_probe.py",
             "_v51_p8_stop_probe.py", "_v52_p8_stop_probe.py")

IMPORT_FRAME_FULL = (
    "# Узел V58 (шаг П8): узел V59 закрыл десять позиций пакета ОДНОЙ спецификацией, и "
    "отдельной\n"
    "# функции-стадии у них в загрузчике нет. Словари ожидания пробы читаются тем же "
    "реестром\n"
    "# `configuration_position_spec`: вторая копия круга и есть то, что рассинхронизировало\n"
    "# пробу с `STAGES` на одиннадцать стадий (замер П8 — `KeyError: "
    "'s4m_defined_types'`).\n"
    "from configuration_position_frame_loader import (  # noqa: E402\n"
    "    not_run_answer as frame_not_run,\n"
    ")\n"
    "from configuration_position_spec import (  # noqa: E402\n"
    "    ordered_specs as frame_specs,\n"
    "    section_header as frame_section_header,\n"
    ")\n"
)

EXTEND_DICTS = (
    '}\n'
    "# Словари ожидания читаются составом стадий, а не перечнем прежних узлов: без строк\n"
    "# новой стадии проба падает KeyError (замер П8). Круг десяти позиций берётся реестром\n"
    "# позиций — второй копии круга проба не заводит (приём `probes/v48/_v48_p8_stop_probe.py`).\n"
    "FRAME_STAGES: tuple = ()\n"
    "for _frame_spec in frame_specs():\n"
    "    _stage = _frame_spec[\"stage\"]\n"
    "    STAGE_KEYS[_stage] = _frame_spec[\"table\"]\n"
    "    SECTION_HEADERS[_stage] = frame_section_header(_frame_spec)\n"
    "    DEFAULTS[_stage] = (lambda _s=_frame_spec: frame_not_run(_s))\n"
    "    FRAME_STAGES += (_stage,)\n"
    "STAGE_KEYS[STAGE_DEFINED_TYPES] = \"defined_types\"\n"
    "SECTION_HEADERS[STAGE_DEFINED_TYPES] = DEFINED_TYPES_SECTION_HEADER\n"
    "DEFAULTS[STAGE_DEFINED_TYPES] = defined_types_defaults\n"
    "STAGE_FUNCTIONS[STAGE_DEFINED_TYPES] = \"load_defined_types\"\n"
    "# Узел TOOL-DROP (05.11.2026) снял отдельный вход позиции: подсказка продолжения одна\n"
    "# на все стадии. Прежние значения держали имена снятых инструментов, и проверка подсказки\n"
    "# требовала текста, которого загрузчик уже не выдаёт (замер П8 — провал на каждой стадии).\n"
    "# Ожидание читает то, что говорит контракт, а не память о прежнем реестре инструментов:\n"
    "# словарь правит сам реестр, поэтому добавление позиции не оставляет стадию без ключа\n"
    "# (KeyError в самой пробе — замер П8 на V49).\n"
    "for _stage in [stage for stage, _title in STAGES]:\n"
    "    RESUME_MARKS[_stage] = (OBJECT_MODULES_RELOAD_HINT if _stage == STAGE_OBJECT_MODULES\n"
    "                            else STAGE_REPEAT_HINT)\n"
)

# строка `if isinstance(...)` в файле остаётся: паттерн заканчивается на `for node in `,
# поэтому включать её в замену нельзя — получилась бы строка-дубль.
FUNCTION_DEFS_BODY = (
    '    tree = ast.parse(read_src(path))\n'
    "    names = {}\n"
    "    for node in tree.body:\n"
)

# Признак того, что перечень стадий детей проба выводит из реестра, а не держит литералом:
# у V52 это строка 208. Правила числа стадий и подмены функций имеют смысл только в такой
# пробе (см. `requires` в apply_struct_rules).
FRAME_DERIVED = "CHILD_STAGES = tuple(stage for stage, _title in STAGES"

STRUCT_RULES_49 = (
    ("импорт реестра позиций (полный)", "not_run_answer as frame_not_run",
     re.compile(r"^from external_db import connect  # noqa: E402$", re.M),
     IMPORT_FRAME_FULL + "from external_db import connect  # noqa: E402"),
    ("импорт DEFINED_TYPES_SECTION_HEADER", "    DEFINED_TYPES_SECTION_HEADER,",
     re.compile(r"^    build_stopped_stage,$", re.M),
     "    build_stopped_stage,\n    DEFINED_TYPES_SECTION_HEADER,"),
    ("импорт defined_types_defaults", "    defined_types_defaults,",
     re.compile(r"^    child_objects_defaults,$", re.M),
     "    child_objects_defaults,\n    defined_types_defaults,"),
    ("импорт STAGE_DEFINED_TYPES", "    STAGE_DEFINED_TYPES,",
     re.compile(r"^    STAGE_COMMON_ATTRIBUTES,$", re.M),
     "    STAGE_COMMON_ATTRIBUTES,\n    STAGE_DEFINED_TYPES,"),
    ("импорт STAGE_REPEAT_HINT", "    STAGE_REPEAT_HINT,",
     re.compile(r"^    STAGE_ROLES,$", re.M),
     "    STAGE_REPEAT_HINT,\n    STAGE_ROLES,"),
    ("достройка словарей ожидания", "FRAME_STAGES: tuple = ()",
     re.compile(r'^    STAGE_OBJECT_MODULES: "load_1c_catalog_tool",\n\}$', re.M),
     EXTEND_DICTS),
    ("function_defs: обход верхнего уровня", "for node in tree.body:",
     re.compile(r"^(?:    tree = ast\.parse\(read_src\(path\)\)\n"
                r"    names = \{\}\n"
                r"    for node in )ast\.walk\(tree\):$", re.M),
     FUNCTION_DEFS_BODY),
    # Утверждения docstring пробы обязаны соответствовать её коду: проверка после правки
    # ждёт полную перезагрузку, а шапка файла рассказывает про отдельный вход (замер П8 —
    # расхождение заголовка и тела хуже красной пробы).
    ("docstring: признак full_reload у стадии",
     "объявлен значением `true` (узел TOOL-DROP",
     re.compile(r"признак `full_reload_required` у (S4[a-z]) обязан быть `false`"),
     "признак `full_reload_required` у \\1 объявлен значением `true` (узел TOOL-DROP снял "
     "отдельный вход позиции)"),
    ("docstring: подсказка продолжения стадии",
     "снят узлом TOOL-DROP",
     re.compile(r"подсказка продолжения для (S4[a-z]) называет ОТДЕЛЬНЫЙ вход `([a-z_]+)`"),
     "подсказка продолжения для \\1 — общая `STAGE_REPEAT_HINT` (отдельный вход `\\2` снят "
     "узлом TOOL-DROP)"),
    ("ORDER: срез нормативного порядка", "NORMATIVE_SEQUENCE = (",
     re.compile(r"^(ORDER = \[stage for stage, _(?:title)? in STAGES\])$", re.M),
     "\\1\n\n"
     "# Относительный порядок позиций, заведённых узлами V45…V57. Порядок читается этим\n"
     "# списком, а не соседством индексов: десять позиций круга V59 (узел V59) вставлены в\n"
     "# реестр между S4l и модулями Ext/, и сравнение соседних индексов падает на всех\n"
     "# прежних стадиях сразу, хотя сам порядок не менялся (замер П8 — V50, проверка 1.4а).\n"
     "NORMATIVE_SEQUENCE = (\n"
     "    STAGE_ROOT_MODULES, STAGE_CHILD_OBJECTS, STAGE_SESSION_PARAMETERS, STAGE_ROLES,\n"
     "    STAGE_COMMON_ATTRIBUTES, STAGE_EXCHANGE_PLANS, STAGE_FILTER_CRITERIA,\n"
     "    STAGE_EVENT_SUBSCRIPTIONS, STAGE_SCHEDULED_JOBS, STAGE_BOTS, STAGE_FUNCTIONAL_OPTIONS,\n"
     "    STAGE_FUNCTIONAL_OPTIONS_PARAMETERS, STAGE_OBJECT_MODULES,\n"
     ")"),
    ("stage_row_prefix: префикс из адреса стадии", 'stage.split("_", 1)[0]',
     re.compile(r'    return \{STAGE_ROOT_MODULES: "s3:",.*?\[stage\]$', re.M | re.S),
     '    # Префикс строки состояния читается адресом стадии (`s4d_roles` → `s4d:`): словарь\n'
     '    # по перечню стадий на дату правки не находит позиций круга V59 (KeyError в прогоне\n'
     '    # — замер П8), а формат префикса держит сам адрес.\n'
     '    return stage.split("_", 1)[0] + ":"'),
    ("docstring: продолжение в перечне разделов",
     "полная перезагрузка при объявленном ключе `full_reload_required = true`",
     re.compile(r"\(для (S4[a-z]) — отдельный вход при объявленном ключе "
                r"`full_reload_required = false`\)"),
     "(для \\1 — полная перезагрузка при объявленном ключе `full_reload_required = true`, "
     "редакция узла TOOL-DROP)"),
    # Правила V52: её перечень стадий детей выведен из `STAGES` (строка 208), поэтому
    # число стадий в нём — величиной реестра, а прогоны конвейера достижимы только для
    # стадий с отдельной функцией. У десяти позиций круга V59 такой функции нет: их ведёт
    # один цикл `for frame_spec in position_frame_specs()` внутри загрузчика (узел V59),
    # поэтому подменять нечего, а остановку этих позиций называют offline-проверки 1.5.
    ("CHILD_STAGES: число стадий реестром", "len(CHILD_STAGES) == len(STAGES)",
     re.compile(r"and len\(CHILD_STAGES\) == 13 and"),
     "and len(CHILD_STAGES) == len(STAGES) - len(NON_CHILD_STAGES) and",
     FRAME_DERIVED),
    ("CHILD_STAGES: заголовок про перечень реестра", "все стадии детей реестра",
     re.compile(r"перечень стадий детей выводится из `STAGES`: тринадцать стадий, "),
     "перечень стадий детей выводится из `STAGES`: все стадии детей реестра, ",
     FRAME_DERIVED),
    ("CHILD_STAGES: прогоны только стадий с функцией",
     "for stage in [st for st in CHILD_STAGES if st in STAGE_FUNCTIONS]:",
     re.compile(r"^        for stage in CHILD_STAGES:$", re.M),
     "        # Позиции круга V59 не имеют отдельной функции-стадии (узел V59): их ведёт цикл\n"
     "        # `for frame_spec in position_frame_specs()` внутри загрузчика, поэтому подменять\n"
     "        # для них нечего, а прогон конвейера останавливается на названной offline-проверкой\n"
     "        # 1.5 стадии. Остановку самих позиций называют пробы круга V59 и `_v48_*` проба.\n"
     "        for stage in [st for st in CHILD_STAGES if st in STAGE_FUNCTIONS]:",
     FRAME_DERIVED),
    ("CHILD_STAGES: подмена только стадий с функцией",
     "for other in [st for st in CHILD_STAGES if st in STAGE_FUNCTIONS]:",
     re.compile(r"^    for other in CHILD_STAGES:$", re.M),
     "    for other in [st for st in CHILD_STAGES if st in STAGE_FUNCTIONS]:\n"
     "        # У позиции круга V59 отдельной функции-стадии нет (узел V59) — подменять нечего.",
     FRAME_DERIVED),
    # Справочники обязательны для каждой стадии детей, а функция — только для стадии с
    # отдельным входом: десять позиций круга V59 ведутся одним циклом загрузчика, и
    # требование `stage in STAGE_FUNCTIONS` читалось бы отсутствием позиции в реестре.
    ("1.4в: функция только у стадий с отдельным входом", "or stage in FRAME_STAGES)",
     re.compile(r"and stage in STAGE_FUNCTIONS and stage in RESUME_MARKS\n(\s+)"
                r"for stage in CHILD_STAGES\),"),
     "and stage in RESUME_MARKS\n"
     "\\1# Отдельной функции-стадии у десяти позиций круга V59 нет (узел V59): их ведёт один\n"
     "\\1# цикл `for frame_spec in position_frame_specs()` внутри загрузчика. Справочники\n"
     "\\1# обязательны для каждой стадии детей, а функция — только для стадии с отдельным входом.\n"
     "\\1and (stage in STAGE_FUNCTIONS or stage in FRAME_STAGES)\n"
     "\\1for stage in CHILD_STAGES),",
     FRAME_DERIVED),
    ("2: выполнение позиции круга по ответу стадии",
     "called = calls.get(other) == 1 if other in STAGE_FUNCTIONS else True",
     re.compile(r"^(        earlier_part = result\.get\(STAGE_KEYS\[other\]\) or \{\})$", re.M),
     "\\1\n"
     "        # Счётчик ведут только подменённые функции стадий; у позиций круга V59 отдельной\n"
     "        # функции нет (узел V59), поэтому их выполнение читается ответом стадии —\n"
     "        # `success: true` и отсутствие статуса `not_run`.\n"
     "        called = calls.get(other) == 1 if other in STAGE_FUNCTIONS else True",
     FRAME_DERIVED),
    ("2: остановка ровно на названной стадии без счётчика",
     'called and earlier_part.get("success") is True',
     re.compile(r'            calls\.get\(other\) == 1 and earlier_part\.get\("success"\) is True,'),
     '            called and earlier_part.get("success") is True\n'
     "            and earlier_part.get(\"status\") != STATUS_NOT_RUN,",
     FRAME_DERIVED),
)

# ── правила по содержимому блока: номера у чужих узлов разъехались ───────────────────
# У V49…V52 проверки подсказки и карточки имеют свои номера (1.12а, 1.25, 1.26), поэтому
# правило привязано к точному тексту ожидания, а не к номеру. Паттерны точные нарочно:
# строка вроде `defaults["full_reload_required"] is False` (нулевой словарь — конвейер не
# останавливался) менять нельзя, и она не совпадает ни с одним из этих паттернов.
FULL_RELOAD_PER_STAGE = r'stopped\["full_reload_required"\] == \(stage == STAGE_OBJECT_MODULES\)'
FULL_RELOAD_FALSE_DIRECT = r'stopped\["full_reload_required"\] is False'
HINT_DICT_FALSE = r"(STAGE_FULL_RELOAD_ONLY\[STAGE_[A-Z_]+\] is) False"
HINT_TOOL_IN = r'"load_[a-z_]+_tool" in str\(stopped\["resume_with"\]\)'
HINT_CONST_EQ = r"([A-Z_]+_REPEAT_HINT) == stage_resume_hint\((STAGE_[A-Z_]+)\)"
CARD_TOOL_IN = re.compile(
    r'"(load_[a-z_]+_tool)" in (?P<target>str\([^)]*\)|[A-Za-z_][A-Za-z0-9_]*)')
TOOL_TITLE = r"отдельный вход `[a-z_]+`"
# Литеральный хвост перечня стадий (заканчивается на `STAGE_OBJECT_MODULES]`) у V49…V52
# перечисляет стадии на дату правки: десять позиций круга V59 в нём отсутствуют (замер П8 —
# четыре расхождения в V50). Хвост срезом реестра короче перечня и не отстаёт молча.
TAIL_LIST = re.compile(
    r"\[\s*(?P<first>STAGE_[A-Z_]+),(?P<rest>[^\]]*?)STAGE_OBJECT_MODULES\]", re.S)
# Цепочка «соседних индексов» (`ORDER.index(A) + 1 == ORDER.index(B)`) проверяла порядок
# позиций соседством: десять позиций круга V59 (узел V59) вставлены между S4l и модулями
# Ext/, и соседство перестаёт выполняться для всех прежних стадий сразу. Относительный
# порядок прежних позиций при этом не менялся — его и проверяет срез реестра.
INDEX_CHAIN = re.compile(
    r"(?:ORDER\.index\(STAGE_[A-Z_]+\) \+ 1\s+==\s*ORDER\.index\(STAGE_[A-Z_]+\)\s*\n\s*and\s+)*"
    r"ORDER\.index\(STAGE_[A-Z_]+\) \+ 1\s+==\s*ORDER\.index\(STAGE_[A-Z_]+\)")
NORMATIVE_SEQUENCE_BODY = ("[stage for stage in ORDER if stage in NORMATIVE_SEQUENCE] "
                          "== list(NORMATIVE_SEQUENCE)")
CHAIN_TITLES = (
    (re.compile(r"порядок `STAGES` повторяет нормативный список:.*?\(критерий П8", re.S),
     "порядок `STAGES` сохраняет относительный порядок прежних позиций (позиции круга V59 "
     "вставлены перед модулями Ext/) (критерий П8"),
)
TAIL_TITLES = (
    (re.compile(r"даёт порядок `STAGES`:.*?\(критерий П8", re.S),
     "даёт порядок `STAGES` целиком (критерий П8"),
    (re.compile(r"повторяет нормативный список:.*?\(критерий П8", re.S),
     "повторяет нормативный список целиком (критерий П8"),
    (re.compile(r"пропущенными после отказа названы .*?\(критерий П8", re.S),
     "пропущенными после отказа назван весь хвост `STAGES` (критерий П8"),
    (re.compile(r"пропущенными после отказа названы .*?\(входы видов", re.S),
     "пропущенными после отказа назван весь хвост `STAGES` (входы видов"),
)


def apply_content_rules(block, probe, number, report, legacy):
    """Правит ожидания подсказки/карточки в любом check-блоке по точным признакам."""
    joined = "\n".join(block)
    if re.search(FULL_RELOAD_PER_STAGE, joined):
        block, _ = body_sub(block, FULL_RELOAD_PER_STAGE,
                            'stopped["full_reload_required"] is True')
        block, _ = title_sub(
            block, r"«только полная перезагрузка» — признак одной стадии S4b \(Q4\.1\)",
            "продолжение — полная перезагрузка у любой стадии (узел TOOL-DROP снял отдельный "
            "вход позиции, Q4.1 в его редакции)")
        report_add(report, probe, f"{number} full_reload по стадиям", "ПРИМЕНЕНО")
    if re.search(HINT_DICT_FALSE, joined):
        block, _ = body_sub(block, HINT_DICT_FALSE, r"\1 True")
        report_add(report, probe, f"{number} ключ full_reload словаря", "ПРИМЕНЕНО")
    if re.search(FULL_RELOAD_FALSE_DIRECT, joined):
        # Прямая форма ожидания (`... is False`) встречается в проверках с собственными
        # номерами (1.12а у V49); контракт после узла TOOL-DROP даёт у любой стадии детей
        # `True`, поэтому ожидание читается состоянием контракта, а не прежним Q4.1.
        block, _ = body_sub(block, FULL_RELOAD_FALSE_DIRECT,
                            'stopped["full_reload_required"] is True')
        report_add(report, probe, f"{number} признак full_reload у стадии", "ПРИМЕНЕНО")
    if re.search(HINT_TOOL_IN, joined):
        block, _ = body_sub(
            block, HINT_TOOL_IN,
            'STAGE_REPEAT_HINT in str(stopped["resume_with"])')
        block, _ = title_sub(block, TOOL_TITLE, "общую подсказку `STAGE_REPEAT_HINT`")
        report_add(report, probe, f"{number} подсказка в ответе", "ПРИМЕНЕНО")
    if re.search(HINT_CONST_EQ, joined) and "STAGE_REPEAT_HINT == stage_resume_hint" not in joined:
        block, _ = body_sub(block, HINT_CONST_EQ, r"STAGE_REPEAT_HINT == stage_resume_hint(\2)")
        report_add(report, probe, f"{number} константа подсказки", "ПРИМЕНЕНО")
    card = re.search(CARD_TOOL_IN, joined)
    if card:
        # Цель сравнения берётся целиком (`str(...)` — это вызов, а не имя): захват только
        # имени давал `STAGE_REPEAT_HINT in str` (TypeError в прогоне — замер П8 на V51).
        target = card.group("target")
        block, _ = body_sub(
            block, CARD_TOOL_IN,
            f'STAGE_REPEAT_HINT in {target} and "{card.group(1)}" not in {target}')
        block, _ = title_sub(block, TOOL_TITLE, "общую подсказку `STAGE_REPEAT_HINT`")
        report_add(report, probe, f"{number} карточка стадии", "ПРИМЕНЕНО")
    if legacy and re.search(INDEX_CHAIN, "\n".join(block)):
        block, _ = body_sub(block, INDEX_CHAIN, NORMATIVE_SEQUENCE_BODY)
        for pattern, repl in CHAIN_TITLES:
            block, _ = title_sub(block, pattern, repl)
        report_add(report, probe, f"{number} порядок позиций срезом реестра", "ПРИМЕНЕНО")
    if legacy and re.search(TAIL_LIST, "\n".join(block)):
        # Хвост перечня берётся срезом реестра: перечень стадий на дату правки молча
        # отстаёт при добавлении позиции, а срез остаётся правильным сам (узел V59).
        block, _ = body_sub(block, TAIL_LIST, r"ORDER[ORDER.index(\g<first>):]")
        for pattern, repl in TAIL_TITLES:
            block, _ = title_sub(block, pattern, repl)
        report_add(report, probe, f"{number} хвост перечня срезом реестра", "ПРИМЕНЕНО")
    return block


def all_check_blocks(lines):
    """Все check-блоки файла (номер берётся из заголовка — он нужен только для отчёта)."""
    out = []
    for i, line in enumerate(lines):
        match = CHECK_RE.match(line)
        if not match:
            continue
        joined = "\n".join(lines[i:])
        end = i + joined[:close_call(joined)].count("\n") + 1
        out.append((i, end, match.group("num")))
    return out


# Правило, которого в файле просто нет потому, что формат другой (у V57 хвост перечислен
# одной строкой, у V54–V56 — многострочно). Отсутствие применимого формата — не провал
# правки, и отчёт обязан называть это прямо, а не прятать за «НЕ СОШЛОСЬ».
OPTIONAL_STRUCT_RULES = {"LATER_STAGES: одиночный S4b",
                         "stage_row_prefix: префикс из адреса стадии",
                         "docstring: продолжение в перечне разделов",
                         "docstring: признак full_reload у стадии"}

# Что обязано исчезнуть из файла после правки: эти строки и есть устаревшее ожидание.
STALE_PATTERNS = (
    (r'"2\.13" not in CHILD_NOT_IMPLEMENTED', "граница «не называть 2.13»"),
    (r'STAGE_FULL_RELOAD_ONLY\.get\([A-Z_]+\) is False', "ожидание `full_reload = False`"),
    (r'stopped\["full_reload_required"\] is False',
     "ожидание `full_reload_required is False` у стадии детей"),
    (r'"load_[a-z_]+_tool" in (?:str\(stopped|stage_resume_hint|text)',
     "ожидание снятого отдельного входа в подсказке"),
    (r"for node in ast\.walk\(tree\):\n        if isinstance\(node, ast\.FunctionDef\):\n",
     "обход `ast.walk` в `function_defs` (вложенные функции считаются дублем уровня модуля)"),
)


def probe_path(name):
    """Путь к пробе по её имени: `_v54_p8_stop_probe.py` → `probes/v54/…`."""
    version = re.match(r"_v(\d+)_", name)
    return ROOT / "probes" / f"v{version.group(1)}" / name


def apply_struct_rules(text, rules, probe, report):
    """Правит общий состав файла (импорты, словари, обход AST); каждая правка — с отметкой.

    Пятым элементом правило может требовать признак в тексте (`requires`): правка пробы,
    чей перечень стадий выведен из реестра, бессмысленна в пробе с литеральным перечнем —
    там она меняла бы верное ожидание на неверное (замер П8: `len(CHILD_STAGES) == 13`
    верно для литерала из тринадцати стадий и неверно для вывода из `STAGES`).
    """
    for rule in rules:
        name, marker, pattern, repl = rule[:4]
        requires = rule[4] if len(rule) > 4 else None
        if marker in text:
            report_add(report, probe, name, "УЖЕ")
            continue
        if requires and requires not in text:
            report_add(report, probe, name, "НЕ ПРИМЕНИМО (перечень литеральный)")
            continue
        text, hits = pattern.subn(repl, text)
        if hits:
            report_add(report, probe, name, f"ПРИМЕНЕНО x{hits}")
        elif name in OPTIONAL_STRUCT_RULES:
            report_add(report, probe, name, "НЕ ПРИМЕНИМО (формат иной)")
        else:
            report_add(report, probe, name, "НЕ СОШЛОСЬ")
    return text


def patch_file(path, report, write):
    """Один файл: сначала общий состав, потом блоки проверок снизу вверх (позиции не съезжают).

    Набор правил выбирается по классу пробы, а не применяется ко всем подряд: у V54…V57
    хвост перечислен литералами стадий, у V49…V52 ожидания порядка уже выводятся из
    `STAGES` (приём узла V48), и правка там не нужна — отсутствие применимого правила
    называть «НЕ СОШЛОСЬ» значит соврать (замер П8: восемь таких строк отчёта).
    """
    probe = path.name
    legacy = probe in PROBES_49
    text = path.read_text(encoding="utf-8")
    original = text
    text = apply_struct_rules(text, STRUCT_RULES_49 if legacy else STRUCT_RULES,
                              probe, report)
    lines = text.split("\n")
    if not legacy:
        targets = []
        for number in BLOCK_NUMBERS:
            for start, end in find_blocks(lines, number):
                targets.append((start, end, number))
        for start, end, number in sorted(targets, reverse=True):
            block = lines[start:end]
            if number in ("1.1", "1.2", "1.5", "1.6", "1.11"):
                patched = patch_offline_block(block, probe, number, report)
            else:
                patched = patch_live_block(block, probe, number, report)
            lines[start:end] = patched
        text = "\n".join(lines)
    # Правила по содержимому идут вторым проходом и по всем блокам: номера проверок у
    # V49…V52 собственные (1.12а, 1.25, 1.26), а ожидание то же самое.
    lines = text.split("\n")
    for start, end, number in sorted(all_check_blocks(lines), reverse=True):
        lines[start:end] = apply_content_rules(lines[start:end], probe, number, report, legacy)
    new_text = "\n".join(lines)
    for pattern, note in STALE_PATTERNS:
        for _ in re.findall(pattern, new_text):
            report_add(report, probe, "остаток: " + note, "НАЙДЕНО")
    if write and new_text != original:
        path.write_text(new_text, encoding="utf-8")
    return new_text != original


def main() -> int:
    write = "--write" in sys.argv[1:]
    report = []
    changed = 0
    targets = list(PROBES) + list(PROBES_49)
    for name in targets:
        path = probe_path(name)
        if not path.is_file():
            report_add(report, name, "файл не найден", str(path))
            continue
        if patch_file(path, report, write):
            changed += 1
    grouped = {}
    for probe, where, note in report:
        grouped.setdefault(probe, []).append((where, note))
    for probe, rows in grouped.items():
        print(f"\n### {probe}")
        for where, note in rows:
            print(f"    {note:14} {where}")
    bad = [row for rows in grouped.values() for row in rows
           if "НЕ СОШЛОСЬ" in row[1] or "НЕ РАЗОБРАНО" in row[1]
           or "НАЙДЕНО" in row[1] or "не найден" in row[0]]
    print(f"\n=== ИТОГО: файлов изменено {changed} из {len(targets)}; "
          f"{'запись выполнена' if write else 'отчёт без записи'} ===")
    print(f"=== не совшло правил и устаревших остатков: {len(bad)} ===")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())