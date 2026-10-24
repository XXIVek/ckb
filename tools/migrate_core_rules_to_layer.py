#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Мигратор `.clinerules/1c-configurations-core_Rule.md` в слой карточек `local_doc`.

Узел R-LAYER (24.10.2026). Файл правил core-MCP вырос до 231 КБ, из них ~67% — журнал
позиций (раздел «Известные недостатки», п. 1–33) и дополнения в шапке. Это знание нужно
не в каждом запросе, но оно занимает контекст каждого из них. Правила остаются индексом,
содержимое уезжает в слой `1c-configurations-core` (категория добавлена в `src/database.py`).

Правила перехода — они же проверки скрипта:

1. адрес карточки — КАНОНИЧЕСКИЙ ЗАГОЛОВОК `core-rules: <узел | п. N | раздел>`, а не id
   и не алиас. id меняются при пересоздании базы документации (тот же урок, что у
   `config_cross_references` и `tools/check_xml_format_layer.py`). Шаг поиска по совпадению
   заголовка добавлен в `src/mcp_tools_api.py::search_docs` (узел R-LAYER);
2. адрес обязан помещаться в `MAX_TITLE_DISPLAY_CHARS`: `server.py` печатает заголовок
   результата, срезая его этим же значением (константа одна — и на загрузчик слоя, и на
   выдачу), поэтому адрес длиннее порога нельзя повторить запросом, и адресом он не является;
3. АЛИАСЫ НЕ СОЗДАЮТСЯ (решение оператора): карточка адресуется точным заголовком, а
   алиасный шаг работает по точному совпадению всего запроса — десятки алиасов из имён узлов,
   колонок и файлов подмешивали бы в выдачу карточки соседних узлов;
4. содержимое переносится ДОСЛОВНО: без пересказа и без правок (каждая цифра в правилах —
   замер конкретной даты; пересказ их теряет);
5. карточка длиннее `MAX_ANSWER_CHARS` (порог чтения `get_snippet_tool`) делится на части
   «… (ч. N)»; границей служит заголовок следующего подраздела того же раздела, поэтому
   текст не рвётся посреди таблицы или абзаца;
6. идемпотентность по `source_url` = `core-rules/<нормализованный адрес>`: повторный прогон
   обновляет ту же строку (`update_snippet`, история в `snippet_audit_log`), а не создаёт
   вторую карточку того же раздела.

Запуск:
    python tools/migrate_core_rules_to_layer.py                # dry-run: разбор и замеры
    python tools/migrate_core_rules_to_layer.py --apply        # запись в local_doc
    ... --dump layers/core_rules_layer.md                      # снимок карточек (для diff)
    ... --emit-rules layers/core_rules_new.md                  # новое тело правил
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from mcp_tools_api import (MAX_ANSWER_CHARS, MAX_TITLE_DISPLAY_CHARS,  # noqa: E402
                           normalize_title)

RULES_FILE = ROOT / ".clinerules" / "1c-configurations-core_Rule.md"
MIGRATOR = Path(__file__).resolve()
CATEGORY = "1c-configurations-core"
PREFIX = "core-rules:"
# У части карточки остаётся запас: в начало `answer` пишется заголовок с пометкой части,
# и усечение `get_snippet_tool` не должно отрезать конец формулировки без шанса дочитать.
PART_CHARS = MAX_ANSWER_CHARS - 600
# Идентификатор узла в тексте встречается в разных падежах: «узел V43», «узла V42»,
# «узле V19», «основа узла V38». Основа слова с «е» (узел\w*) родительного падежа не
# берёт: в «узла» буква «е» выпадает (замер 24.10.2026: позиция п. 32 с фразой
# «закрыта открытая позиция узла V42» оставалась без адреса узла). Варианты «слой»
# перечислены формами слова, а не маской `сло\w*`: маска ловила бы «слово».
# Жирный вокруг идентификатора («узел **V43**») допустим: в правилах узловое имя
# выделяется, и без зазора `[^A-Za-z0-9.]{0,2}` первое упоминание в первой фразе
# дополнения не находилось, а находилось следующее — уже про другой узел
# (замер 24.10.2026: дополнение про V39 разрешалось в V12).
NODE_RE = re.compile(
    r"(?:уз(?:ел|л)\w*|сло(?:й|я|е|ю|ем|ёв|ве|ях|ями))\s+[^A-Za-z0-9.]{0,2}"
    r"([A-Z]+[0-9]+(?:\.[0-9]+)?)",
    re.IGNORECASE)
DATE_RE = re.compile(r"([0-9]{2}\.[0-9]{2}\.[0-9]{4})")
# Дополнения в шапке правил: `**Дополнение DD.MM.YYYY (узел NN):**` (строки блока цитаты)
# и `**Обновлено DD.MM.YYYY под узел NN**`. Границей является следующее такое вхождение,
# а не пустая строка: текст дополнения сам содержит пустые строки, и нарезка по пустым
# строкам рвала одно утверждение на части (замер 24.10.2026: 8 дополнений, 14 обрывков).
ADDITION_RE = re.compile(
    r"^[> ]*\*\*(?P<label>(?:Дополнение|Обновлено)\s+[0-9]{2}\.[0-9]{2}\.[0-9]{4}[^\n]*?)\*\*",
    re.MULTILINE)
H2 = re.compile(r"^## ", re.MULTILINE)
# Метка дополнения в шапке правил оканчивается пояснением в скобках — «(п. 33)»,
# «(карточка одного свойства)». В самих метках правил core имени узла нет (замер
# 24.10.2026: 7 меток из 8 — «(п. N)»), узел называется в тексте ПОСЛЕ метки. Пояснение
# метки — единственный текст, который различает дополнения одной даты: без него п. 31,
# п. 30 и п. 29 (все 21.10.2026) получили бы один адрес на троих.
ADDITION_LABEL_RE = re.compile(
    r"^(Дополнение|Обновлено)\s+([0-9]{2}\.[0-9]{2}\.[0-9]{4})\s*(.*)$",
    re.IGNORECASE | re.DOTALL)
PAREN_TAIL_RE = re.compile(r"\(([^()]*)\)\s*:?\s*$")
POSITION_RE = re.compile(r"^п\.\s*\d+$")
ADDITION_WORD_RE = re.compile(r"^(Дополнение|Обновлено)\b", re.IGNORECASE)
H3 = re.compile(r"^### ", re.MULTILINE)
JOURNAL_HEAD = "## 🐛 Известные недостатки"
# Маркер уже перенесённого файла правил. После подстановки нового тела журнала в файле нет,
# и повторный прогон не «ничего не нашёл», а перечеркнул бы слой пустым индексом: источником
# текста позиции стал сам local_doc. Поэтому прогон останавливается с объяснением, а не с
# SystemExit про отсутствие журнала (тот же класс дефекта, что молчаливый ноль проверок).
MIGRATED_MARK = "<!--Индекс журнала: перенесён в слой"


def strip_nl(text):
    """Текст без обрамляющих пустот и без хвостовых пробелов в строках.

    Хвостовые пробелы снимаются: они попадают в файл правил из редактора, в карточке
    не значат ничего, а сравнение с уже лежащей строкой на них бы падало — миграция
    показывала бы изменение там, где изменений нет.
    """
    return "\n".join(ln.rstrip() for ln in str(text).replace("\r\n", "\n").split("\n")).strip()


def read_text(path):
    """Чтение текста с нормализованными переводами строк (файл правил — CRLF)."""
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def write_text(path, text):
    """Запись текстового артефакта (снимок слоя, индекс) с LF и одним переводом в конце."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip("\n") + "\n", encoding="utf-8", newline="\n")


def _fit(text, limit, what=""):
    """Проверить, что адрес помещается в лимит, и назвать причину, если нет.

    Молча срезать адрес нельзя: адрес — то, что оператор копирует в запрос поиска, и
    обрезанный адрес не совпадёт с заголовком карточки (точный шаг сравнивает строку
    целиком). Точение без `what` оставлено для мест, где срез — намеренное поведение.
    """
    if len(text) <= limit:
        return text
    if what:
        raise ValueError(f"{what}: {len(text)} симв. > {limit}")
    cut = text[:limit]
    for sep in (" — ", " ; ", " (", ", ", " "):
        pos = cut.rfind(sep)
        if pos > limit * 0.4:
            return cut[:pos].rstrip(" ,:;—-") + "…"
    return cut.rstrip(" ,:;—-") + "…"


def _clean_heading(text):
    """Заголовок в одну строку: без переносов и без жирного.

    Жирное (`**`) снимается: заголовок карточки — адрес, по которому карточку называют,
    и символы разметки съедают лимит MAX_TITLE_DISPLAY_CHARS, делая адрес неточным
    (в тексте карточки разметка сохраняется, в адресе её быть не должно).
    """
    s = re.sub(r"^#+\s*", "", " ".join(str(text).replace("**", "").split()).strip())
    return s.strip("«»\"' ")


def _addition_slug(heading):
    """Различающий текст из метки дополнения: «(п. 33)» -> `п. 33`."""
    m = ADDITION_LABEL_RE.match(heading)
    tail = (m.group(3) if m else "").strip().rstrip(":").strip()
    found = PAREN_TAIL_RE.search(tail)
    if found:
        tail = found.group(1)
    tail = tail.strip("()").strip()
    for ch in ("`", "«", "»", '"'):
        tail = tail.replace(ch, "")
    return " ".join(tail.split())


def title_base(kind, num, heading, addition_date=None, node=""):
    """Канонический адрес карточки: `core-rules: узел V43`, `core-rules: п. 9`.

    Узел называется первым: по нему правила ищут чаще всего, и он однозначен внутри файла.
    Номер позиции журнала — адрес для записей без узла. Описательная часть в адрес НЕ
    входит: она остаётся в индексе правил (вместе с исходным заголовком раздела), иначе
    адрес не помещался бы в порог, а точный запрос был бы непригоден для копирования.
    Дополнения шапки получают дату: об одном и том же узле в шапке бывает две записи
    (принятие узла и закрытие его открытой позиции), и дата различает их без `#2`.
    Дата при этом добавляется к адресу узла, а не заменяет его: один запрос
    `core-rules: узел V43` обязан находить и позицию журнала, и дополнение шапки о том
    же узле — это два текста об одном решении, и искать их по разным адресам значило бы
    читать половину знания о узле.
    """
    found = NODE_RE.search(heading)
    node_id = node or (found.group(1).upper() if found else "")
    if node_id:
        node_id = f"узел {node_id}"
        if kind == "addition" and addition_date:
            return f"{PREFIX} {node_id} (дополнение {addition_date})"
        return f"{PREFIX} {node_id}"
    if kind == "journal":
        return f"{PREFIX} п. {num}"
    limit = MAX_TITLE_DISPLAY_CHARS - len(PREFIX) - 1
    if kind == "addition":
        # У дополнения шапки имени узла в метке нет — различающий текст берётся из неё.
        # «п. 33» — адрес позиции журнала, к ней добавляется дата: та же позиция описана
        # и в журнале, и в шапке, и это разные тексты (шапка — сводка дня, журнал —
        # разбор дефекта).
        slug = _addition_slug(heading)
        if POSITION_RE.match(slug):
            if addition_date:
                return f"{PREFIX} {slug} (дополнение {addition_date})"
            return f"{PREFIX} {slug}"
        word = ADDITION_WORD_RE.match(heading)
        word = word.group(1).lower() if word else "дополнение"
        if addition_date and slug:
            room = limit - len(word) - len(addition_date) - 2
            return f"{PREFIX} {word} {addition_date} {_fit(slug, room)}"
        if addition_date:
            return f"{PREFIX} {word} {addition_date}"
        if slug:
            return f"{PREFIX} {word} {_fit(slug, limit - len(word) - 1)}"
        return f"{PREFIX} {word}"
    return f"{PREFIX} {_fit(_clean_heading(heading), limit)}"


def tags_for(kind, num):
    """Теги карточки слоя: категория + вид позиции.

    Категория обязана лежать в тегах: `search_docs_tool(category=...)` фильтрует выдачу
    пересечением массивов (`&&` по `idx_snippets_tags`), и строка без тега категории при
    запрошенной категории не отдаётся вовсе — то есть без этой строки карточки не существовало
    бы для поиска, сколько текста о ней ни лежало в базе.
    Теги вида `core-rules-journal` / `core-rules-p9` позволяют выбрать только журнал или
    только одну позицию; алиасов при этом нет намеренно (правило 3 шапки).
    """
    tags = [CATEGORY, "core-rules", kind]
    if kind == "journal" and num:
        tags.append(f"core-rules-p{num}")
    return tags


def source_url_for(title):
    """Устойчивый ключ карточки: `core-rules/<нормализованный адрес>`.

    По этому ключу миграция узнаёт, что строка уже есть, и правит её, а не создаёт вторую
    карточку того же раздела. Ключ выводится из адреса, а не из `id` и не из заголовка
    исходного раздела: `id` меняются при пересоздании базы, заголовок раздела правят, а адрес
    — то, чем карточку называют. Нормализация та же, что у шага поиска
    (`normalize_title`), плюс сжатие не-буквенных последовательностей в дефис: два пути
    нормализации дали бы «строка есть, а повторный прогон создаёт её заново».
    """
    tail = title[len(PREFIX):] if title.startswith(PREFIX) else title
    norm = re.sub(r"[^0-9a-zа-яё]+", "-", normalize_title(tail)).strip("-")
    return f"core-rules/{norm}"


def _quote_end(text, start):
    """Позиция первой строки после блока цитаты, внутри которого лежит дополнение.

    Дополнения шапки — абзацы одного блока цитаты (`> **Дополнение …**`). Граница тела —
    конец блока, а НЕ следующий заголовок: между последним дополнением и следующим
    разделом правил заголовка нет, и иначе тело последнего дополнения поглотило бы весь
    остальной текст шапки (назначение сервера, контракт инструментов, схему, правила).
    Замер 24.10.2026 на файле core: без этой границы новый файл правил терял разделы
    контракта — оставалось 7 КБ вместо 30 КБ живых правил.
    """
    pos = text.find("\n", start)
    while pos != -1:
        nxt = text.find("\n", pos + 1)
        line = text[pos + 1: nxt if nxt != -1 else len(text)]
        if line.strip() and not line.lstrip().startswith(">"):
            return pos + 1
        pos = nxt
    return len(text)


def _split_heading(chunk):
    """Разделить блок правил на первую строку-заголовок и тело БЕЗ неё.

    Тело карточки не имеет права содержать заголовок своего раздела: `build_answer`
    ставит заголовок сам — одной формулировкой на всю карточку (в каждой части, чтобы
    часть отвечала, к какому разделу она относится). Если тело приходит с исходной
    строкой `### …`, в карточке тот же текст читается дважды: адресом без разметки и
    строкой разметки (замер 24.10.2026 на снимке слоя: у `core-rules: п. 32` заголовок
    шёл сразу после `source_url`, а через пустую строку — повторно). Разделители `##`/`###`
    при этом относятся к файлу правил, а не к знанию, поэтому в карточку не попадают.
    """
    head_line, _, rest = chunk.partition("\n")
    return head_line, strip_nl(rest)


def split_additions(head):
    """Дополнения шапки правил.

    Граница — следующее вхождение `> **Дополнение …` / `**Обновлено …` или конец блока
    цитаты, а не пустая строка: каждая запись занимает несколько абзацев, и граница по
    пустой строке резала бы запись пополам. Первая строка становится заголовком карточки
    (из неё же берутся дата и узел), остальное — телом.
    """
    marks = list(ADDITION_RE.finditer(head))
    items = []
    for i, m in enumerate(marks):
        nxt = marks[i + 1].start() if i + 1 < len(marks) else len(head)
        end = min(_quote_end(head, m.end()), nxt)
        block = strip_nl(head[m.start():end])
        if not block:
            continue
        lines = block.split("\n")
        heading = _clean_heading(m.group("label"))
        # Хвост строки метки («:** закрыт узел V43 — дочерние свойства стали данными») —
        # часть текста дополнения, а не метки: он идёт ПОСЛЕ закрывающих `**`, поэтому в
        # `label` не попадает. Терять его нельзя: в нём первая фраза записи, и именно в
        # ней назван узел (замер 24.10.2026: карточка начиналась со слов «данными: в
        # configurations добавлено», а узел V43 в ней не упоминался вовсе).
        tail = lines[0][m.end() - m.start():].lstrip()
        while tail.startswith(":"):
            tail = tail[1:].lstrip()
        rest = [ln[2:].strip() if ln.startswith(">") else ln for ln in lines[1:]]
        body = strip_nl("\n".join(([tail] if tail else []) + rest))
        node = NODE_RE.search(heading) or NODE_RE.search(body[:400])
        date = DATE_RE.search(heading)
        items.append({"kind": "addition", "num": date.group(1) if date else "",
                      "heading": heading, "body": body, "links": [],
                      "node": node.group(1).upper() if node else "",
                      "where": "дополнение шапки правил",
                      "subs": [], "start": m.start(), "raw_end": end})
    return items


def split_sections(body):
    """Разбор текста правил (после дополнений шапки) на разделы и подразделы.

    Границы: `## ` — раздел, `### ` — подраздел. Подраздел с номером `N.` — позиция
    журнала; адрес такой карточки — номер позиции. Подразделы без номера (разделы шапки
    со словарями и таблицами) получают адрес по заголовку. У раздела без подразделов
    карточкой становится он сам, у раздела с подразделами — только подразделы: тело
    раздела перед первым подразделом короткое и служит вводным текстом.
    """
    sections = []
    h2 = [m.start() for m in H2.finditer(body)]
    for i, start in enumerate(h2):
        end = h2[i + 1] if i + 1 < len(h2) else len(body)
        chunk = strip_nl(body[start:end])
        head_line, chunk_body = _split_heading(chunk)
        heading = _clean_heading(head_line)
        subs = [m.start() for m in H3.finditer(chunk)]
        if not subs:
            is_journal = JOURNAL_HEAD in chunk[:len(JOURNAL_HEAD) + 40]
            sections.append({"kind": "journal" if is_journal else "head", "num": "",
                             "heading": heading, "body": chunk_body,
                             "links": [], "node": "", "subs": [], "start": start,
                             "where": "заголовок журнала" if is_journal else "раздел правил"})
            continue
        intro = strip_nl(_split_heading(chunk[:subs[0]])[1])
        if intro:
            sections.append({"kind": "head", "num": "", "heading": heading, "body": intro,
                             "links": [], "node": "", "subs": [], "start": start,
                             "where": f"вводный текст раздела «{heading}»"})
        for j, sstart in enumerate(subs):
            send = subs[j + 1] if j + 1 < len(subs) else len(chunk)
            sub = strip_nl(chunk[sstart:send])
            sub_head, sub_body = _split_heading(sub)
            sheading = _clean_heading(sub_head)
            num, kind = "", "head"
            mnum = re.match(r"^(\d+)\.\s", sheading)
            if mnum:
                num, kind = mnum.group(1), "journal"
            node = NODE_RE.search(sheading)
            sections.append({"kind": kind, "num": num, "heading": sheading, "body": sub_body,
                             "links": [], "node": node.group(1).upper() if node else "",
                             "where": f"п. {num} журнала" if kind == "journal"
                             else f"подраздел раздела «{heading}»",
                             "subs": [], "start": start + sstart})
    return sections


def parse_rules(text):
    """Правила → (текст, который остаётся в файле, дополнения шапки, разделы после них).

    В файле правил остаются текст ДО первого дополнения (заголовок файла) и всё, что идёт
    ПОСЛЕ последнего дополнения — назначение сервера, контракт инструментов, схема, правила
    загрузки. Обрезать шапку по ПЕРВОМУ дополнению значило бы потерять половину файла:
    дополнения стоят в начале блока цитаты, а контракт — сразу за ними (замер 24.10.2026:
    индекс терял разделы контракта вместе с 30 КБ правил).

    Разделы (`kind == "head"`) возвращаются как есть: решение, переносить их в слой или
    оставить в файле, принимает вызывающий код. `main` переносит дополнения и позиции
    журнала, а вводные тексты разделов оставляет в файле правил.
    """
    if MIGRATED_MARK in text:
        raise SystemExit(
            "Файл правил уже перенесён в слой (в нём стоит маркер «Индекс журнала: перенесён "
            "в слой»).\n"
            "  Позиций журнала в файле нет, поэтому повторный разбор дал бы пустой индекс и\n"
            "  при --apply перечеркнул бы слой как «ненужные» его же карточки. Источником текста\n"
            "  позиции теперь является строка local_doc: править её нужно update_snippet_tool,\n"
            "  а мигратор запускается один раз на перенос.\n"
            "  Если перенос нужен заново — сначала верните файл журнала из предыдущего состояния\n"
            "  (git checkout HEAD -- .clinerules/1c-configurations-core_Rule.md), затем\n"
            "  tools/migrate_core_rules_to_layer.py --apply.")
    at = text.find(JOURNAL_HEAD)
    if at < 0:
        raise SystemExit(f"В файле нет позиции журнала: {JOURNAL_HEAD!r} — разбор не начинался.")
    head_text, body = text[:at], text[at:]
    additions = split_additions(head_text)
    if additions:
        head_text = (head_text[: additions[0]["start"]] + "\n"
                     + head_text[additions[-1]["raw_end"]:])
    head_text = strip_nl(head_text)
    return head_text, additions, split_sections(body)


def split_body(body):
    """Тело раздела на кусики <= PART_CHARS по абзацам, а при необходимости — построчно.

    Границы — пустые строки и заголовки `####`, а не жёсткий срез символами: разрезанный
    посредине SQL-запрос или таблица в карточке читаются хуже, чем две части.
    """
    marks = sorted({0, *[m.start() for m in re.finditer(r"^#### ", body, re.MULTILINE)],
                    *[m.start() + 1 for m in re.finditer(r"\n\s*\n", body)]})
    blocks = []
    for i, start in enumerate(marks):
        end = marks[i + 1] if i + 1 < len(marks) else len(body)
        if end > start:
            blocks.append(body[start:end])
    parts, cur = [], ""
    for block in blocks:
        while len(block) > PART_CHARS:
            if cur:
                parts.append(cur)
                cur = ""
            cut = max(block.rfind("\n\n", 0, PART_CHARS), block.rfind("\n", 0, PART_CHARS))
            if cut < PART_CHARS // 4:
                cut = PART_CHARS
            parts.append(block[:cut])
            block = block[cut:]
        if cur and len(cur) + len(block) > PART_CHARS:
            parts.append(cur)
            cur = block.lstrip("\n")
        else:
            cur += block
    if cur.strip():
        parts.append(cur)
    return [strip_nl(p) for p in parts if p.strip()]


# ------------------------------------------------------------------ сбор карточек

def build_answer(sec, part_no, part_count, part_text):
    """Тело карточки: заголовок исходного раздела + текст части.

    Заголовок повторяется в каждой части намеренно: `get_snippet_tool` отдаёт answer без
    вопроса, и часть без заголовка не отвечает, к какому разделу она относится.
    Тело раздела приходит СЮДА уже без собственной строки заголовка — её снимает
    `split_sections` через `_split_heading`. Поэтому в карточке заголовок может встретиться
    ровно один раз; повтор — дефект разбора, а не формат карточки (замер 24.10.2026: у
    `core-rules: п. 32` он шёл и сразу после `source_url`, и через пустую строку).
    """
    lines = [sec["heading"]]
    if part_count > 1:
        lines.append(f"(часть {part_no} из {part_count}; раздел длинный — читать части по порядку)")
    lines += ["", part_text]
    return strip_nl("\n".join(lines))


def collect(sections):
    """Секции правил → карточки: адрес, части, answer, tags, source_url."""
    cards, errors = [], []
    for si, sec in enumerate(sections):
        date = None
        if sec["kind"] == "addition":
            m = DATE_RE.search(sec["heading"])
            date = m.group(1) if m else None
        base = title_base(sec["kind"], sec["num"], sec["heading"],
                         addition_date=date, node=sec.get("node", ""))
        try:
            _fit(base, MAX_TITLE_DISPLAY_CHARS,
                 f"адрес {base!r} раздела {sec['num'] or sec['heading'][:40]!r}")
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not sec["body"]:
            errors.append(f"{base}: пустое содержимое раздела — переносить нечего")
            continue
        parts = split_body(sec["body"])
        # Тело не имеет права начинаться со строки заголовка своего раздела: заголовок
        # карточке даёт `build_answer`, и иначе он читается в answer дважды (замер
        # 24.10.2026 на снимке слоя). Проверка именно первой строки первой части:
        # последующие части вправе начинаться с `####` — это подзаголовок раздела,
        # который `split_body` сохраняет как контекст продолжения.
        if parts and parts[0].lstrip().startswith("#"):
            errors.append(f"{base}: тело начинается со строки заголовка "
                          f"{parts[0].lstrip()[:60]!r} — разбор обязан снимать заголовок "
                          f"раздела (_split_heading)")
        total = len(parts) + (1 if sec["links"] else 0)
        for i in range(1, total + 1):
            chunk = parts[i - 1] if i <= len(parts) else "\n\n".join(sec["links"])
            answer = build_answer(sec, i, total, chunk)
            if len(answer) > MAX_ANSWER_CHARS:
                errors.append(f"{base}: answer {len(answer)} > {MAX_ANSWER_CHARS} (ч. {i})")
            title = base if total == 1 else f"{base} ч. {i}"
            try:
                _fit(title, MAX_TITLE_DISPLAY_CHARS, f"адрес части {base!r}")
            except ValueError as exc:
                errors.append(str(exc))
                continue
            cards.append({
                "title": title,
                "answer": answer,
                "tags": tags_for(sec["kind"], sec["num"]),
                "source_url": source_url_for(title),
                "section": f"{sec['kind']}:{si}",
                "parts": total,
            })
    seen, dupes = {}, []
    for card in cards:
        if card["title"] in seen:
            dupes.append(f"дубликат адреса {card['title']!r}: {seen[card['title']]} и {card['section']}")
        else:
            seen[card["title"]] = card["section"]
    return cards, sorted(errors + dupes)


# ------------------------------------------------------------------ БД

def existing_by_source(cur):
    """Карточки слоя по source_url — по ним миграция узнаёт, что править, а не создавать.

    Ключ — source_url, а не id: id меняются при пересоздании базы, а source_url задаём мы,
    и он устойчив. Совпадение с заголовком проверяется отдельно: он тоже адрес, и расхождение
    называется прямо.
    """
    cur.execute(
        "SELECT id, question, answer, source_url, tags FROM knowledge_snippets WHERE %s = ANY(tags)",
        (CATEGORY,),
    )
    # курсор `get_cursor` — RealDictCursor, поэтому доступ по именам колонок, а не по позициям.
    return {row["source_url"]: {"id": row["id"], "question": row["question"],
                                "answer": row["answer"], "tags": row["tags"]}
            for row in cur.fetchall()}


def insert_card(cur, card):
    """Новая карточ слоя — прямая вставка, не `add_snippet`.

    Причина не в удобстве: `add_snippet` при groups_id IS NULL генерирует алиасы из
    вопроса, а слой адресуется заголовком (шаг заголовков, `core-rules:`). Алиасы от
    заголовка вида `core-rules: узел V43` дали бы в точном алиасном шаге шум по словам
    `core`, `rules`, `узел`, `v43` — тот дефект, из-за которого алиасы слоя намеренно
    не заводятся.
    """
    cur.execute(
        "INSERT INTO knowledge_snippets (groups_id, question, answer, source_url, tags, "
        "confidence, is_verified) VALUES (NULL, %s, %s, %s, %s, %s, TRUE) RETURNING id",
        (card["title"], card["answer"], card["source_url"], card["tags"], 1.0),
    )
    return cur.fetchone()["id"]


def apply_to_db(cur, cards, existing):
    """Правит существующие карточки контрактом `update_snippet`, новые вставляет напрямую."""
    from mcp_tools_api import update_snippet

    added, updated, unchanged, failed = 0, 0, 0, []
    for card in cards:
        old = existing.get(card["source_url"])
        if not old:
            new_id = insert_card(cur, card)
            if new_id:
                added += 1
            else:
                failed.append(f"вставка {card['title']}: id не получен")
            continue
        if old["question"] == card["title"] and old["answer"] == card["answer"]:
            unchanged += 1
            continue
        res = update_snippet(
            old["id"], new_question=card["title"], new_answer=card["answer"], tags=card["tags"],
            reason="миграция журнала правил 1c-configurations-core в слой знаний local_doc (узел R-LAYER)",
        )
        if res.get("success"):
            updated += 1
        else:
            failed.append(f"id={old['id']} {card['title']}: {res.get('error') or 'строки нет'}")
    return added, updated, unchanged, failed


# ------------------------------------------------------------------ вывод

def dump_layer(cards):
    """Снимок слоя текстом — артефакт для diff и для сверки без БД."""
    lines = [
        f"# Слой знаний local_doc: {CATEGORY}",
        "",
        f"Карточек: {len(cards)}. Источник: {RULES_FILE.relative_to(ROOT)}",
        "",
        "Адрес карточки — её `question`. Читать: поиск с маркером (точное совпадение",
        f"`search_docs_tool(query=\"{PREFIX} узел V43\", category=\"{CATEGORY}\")`), затем",
        "`get_snippet_tool(id)`. Алиасы слоя не заводятся: адрес — заголовок.",
        "",
    ]
    for card in cards:
        lines += [f"## {card['title']}", "", f"source_url: `{card['source_url']}`", "",
                  card["answer"], ""]
    return strip_nl("\n".join(lines)) + "\n"


def rules_index(cards, sections):
    """Индекс для файла правил: адрес карточки + исходный заголовок раздела.

    Исходный заголовок сохраняется: он несёт формулировку, по которой человек ищет узел,
    и без неё индекс терял бы смысл. Тело раздела в файл правил не возвращается — за ним
    теперь ходят в слой.
    """
    headings = {f"{sec['kind']}:{si}": sec for si, sec in enumerate(sections)}
    lines = [
        "<!--Индекс журнала: перенесён в слой знаний `local_doc`, категория "
        f"`{CATEGORY}` (узел R-LAYER).-->",
        "",
        "## 📒 Позиции журнала — слой знаний, а не этот файл",
        "",
        f"Текст каждой позиции лежит в `local_doc` категорией `{CATEGORY}`. Здесь — только",
        "адреса. Порядок чтения (тот же двухфазный, что и вся база документации):",
        "",
        "```text",
        f"search_docs_tool(query=\"{PREFIX} узел V43\", category=\"{CATEGORY}\")",
        "        # точное совпадение по заголовку карточки → id",
        "get_snippet_tool(id)   # полный текст позиции (длинный раздел — по частям)",
        "```",
        "",
        "Правки позиции идут в слой (`update_snippet_tool`, `reason` обязателен) — файл",
        "правил от этого не растёт.",
        f"Пересборка слоя: `python {MIGRATOR.relative_to(ROOT)} --apply`; снимок карточек "
        "(`--dump`) — локальный артефакт сравнения и в репозиторий не входит: источник "
        "истины — строки `local_doc`, а целостность слоя проверяет "
        "`tools/check_rules_layer.py` адресом.",
        "",
        "| Адрес карточки | Позиция (исходный заголовок раздела) |",
        "|---|---|",
    ]
    seen_parts = set()
    for card in cards:
        sec = headings.get(card["section"])
        if sec is None:
            continue
        where = sec["where"]
        if card["parts"] > 1:
            base = card["title"].rsplit(" ч. ", 1)[0]
            desc = f"{where} — {sec['heading']}" if base not in seen_parts else f"продолжение ({card['parts']} ч.)"
            seen_parts.add(base)
        else:
            desc = f"{where} — {sec['heading']}"
        lines.append(f"| `{card['title']}` | {desc} |")
    return "\n".join(lines)


def rules_document(head_text, head_sections, cards, sections):
    """Новое тело файла правил: то, что остаётся в файле, + указатель на слой.

    Порядок совпадает с исходным: заголовок файла, разделы контракта (они входят в
    `head_text` — идут после дополнений), вводные тексты разделов, и на месте журнала —
    индекс адресов. Остающееся возвращается дословно (`body`): меняем состав переносимого,
    а не формулировки того, что остаётся в правилах.
    """
    parts = [head_text]
    for sec in head_sections:
        parts.append(sec["body"])
    parts.append(rules_index(cards, sections))
    return strip_nl("\n\n".join(parts)) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Перенос журнала правил core в слой local_doc")
    ap.add_argument("--apply", action="store_true",
                    help="записать в local_doc (по умолчанию только разбор и снимок)")
    ap.add_argument("--dump", default=str(ROOT / "layers" / "core_rules_layer.md"),
                    help="файл снимка слоя")
    ap.add_argument("--emit-rules", default="",
                    help="файл с индексом для правил (живой файл не меняется)")
    ap.add_argument("--migrate-head", action="store_true",
                    help="перенести в слой и вводные тексты разделов правил "
                         "(по умолчанию они остаются в файле)")
    args = ap.parse_args()

    head, additions, sections = parse_rules(read_text(RULES_FILE))
    head_sections = [s for s in sections if s["kind"] == "head"]
    migrate = additions + [s for s in sections
                           if s["kind"] != "head" or args.migrate_head]
    cards, errors = collect(migrate)

    print(f"остаётся в файле правил: {len(head)} строк текста, вводных разделов {len(head_sections)}; "
          f"дополнений шапки: {len(additions)}; "
          f"разделов перенесено: {len(migrate) - len(additions)}; карточек: {len(cards)}")
    for kind in ("addition", "head", "journal"):
        n_sec = sum(1 for s in migrate if s["kind"] == kind)
        n_card = sum(1 for c in cards if c["section"].startswith(kind))
        print(f"  {kind:<9} разделов {n_sec:>3}  карточек {n_card:>3}")
    longest_t = max((len(c["title"]) for c in cards), default=0)
    longest_a = max((len(c["answer"]) for c in cards), default=0)
    print(f"пороги: title <= {MAX_TITLE_DISPLAY_CHARS} (максимум {longest_t}); "
          f"answer <= {MAX_ANSWER_CHARS} (максимум {longest_a})")
    if errors:
        print("ОШИБКИ РАЗБОРА:")
        for e in errors:
            print(f"  - {e}")
        return 1

    write_text(Path(args.dump), dump_layer(cards))
    print(f"снимок слоя: {args.dump}")
    if args.emit_rules:
        write_text(Path(args.emit_rules), rules_document(head, head_sections, cards, migrate))
        print(f"индекс правил: {args.emit_rules}")

    if not args.apply:
        print("РАЗБОР ПРОВЕРЕН (в БД не писали) — для записи нужен --apply")
        return 0

    from database import get_cursor
    with get_cursor() as cur:
        existing = existing_by_source(cur)
        print(f"карточек слоя в БД до: {len(existing)}")
        added, updated, unchanged, failed = apply_to_db(cur, cards, existing)
    print(f"добавлено: {added}, обновлено: {updated}, без изменений: {unchanged}")
    stale = sorted(set(existing) - {c["source_url"] for c in cards})
    for url in stale:
        print(f"  строка слоя не порождена текущими правилами: id={existing[url]['id']} "
              f"{existing[url]['question']}")
    if failed:
        print("ОШИБКИ ЗАПИСИ:")
        for f in failed:
            print(f"  - {f}")
        return 1
    print("СЛОЙ ЗАПИСАН")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

