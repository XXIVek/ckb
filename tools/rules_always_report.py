#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Отчёт по правилам, которые читаются всегда (узел ALWAYS-REPORT, 27.10.2026).

Зачем
-----
Политика «что читаем всегда» живёт не в описании, а константой `ALWAYS_ADDRESSES` в
`tools/rules_read.py`: её же поднимает роль агента (`.clinerules/1C_Rule.md` запускает
`rules_read.py --always`). Отчёт печатает ровно тот набор, который поднимает читатель, — адреса,
полный текст карточек и объём против бюджета. Смысл один: пересказ набора в отдельном файле
разъезжается с набором (тексты правил уже разъезжались со своими снимками), поэтому здесь
содержимое переносится дословно из строк БД, а перечень адресов берётся из константы.

Что в отчёте есть
-----------------
  1. набор как политика: адреса, id, размер, доля от `ALWAYS_BUDGET_CHARS`, дата изменения;
  2. полный текст каждой always-карточки дословно (заголовки — по числу сегментов адреса,
     как в `src/rules_report.py`);
  3. состав карточек по машинным разделам (`===WHEN===`, `===SCOPE===`, …) — чтобы видно было,
     что именно попадает в контекст, не читая карточку целиком;
  4. граница набора: вариативные слои (адрес, назначение из корневой карточки, число живых
     карточек, объём) — те же строки, что даёт `rules_read.py --layers`;
  5. объём набора против бюджета. Проверка `check_rules_layer.py` считает бюджет по слоям, а
     always-набор проходит через два слоя сразу, поэтому итог по набору считается здесь отдельно
     и называется числом, а не оценкой.

Чего в отчёте нет
-----------------
Вердиктов, правок, пересказа правил. Правка делается строкой БД (`update_snippet_tool`), после
чего отчёт перегоняют — и правку видно в файле. Проверки целостности — `check_rules_layer.py`.

Запуск
------
    python tools/rules_always_report.py                 # Reports/rules_always_<дата>.md
    python tools/rules_always_report.py --stdout        # в консоль, без файла
    python tools/rules_always_report.py --out rules_always_review.md
    python tools/rules_always_report.py --marked        # включить помеченные к удалению
    python tools/rules_always_report.py --no-log        # не писать обращение в лог правил

Отчёт читает тот же набор, что и читатель правил, — поэтому его обращение так же дописывается
в `logs/rules_load.log` (модуль `tools/rules_logging.py`), краткой строкой «дата + адрес»
карточки. `--full-log` пишет подробную сессию — с режимом и итогом по объёму набора: замер
всегда делают подробным форматом, иначе строки замера в логе нет. `--log-file` пишет в
отдельный файл каталога `logs/`, чтобы замер не пачал рабочий лог.

Код возврата: 0 — весь набор найден; 1 — хотя бы одной always-карточки нет в базе.
"""

import argparse
import datetime
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _p in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

import rules_layer as RL  # noqa: E402
from mcp_tools_api import normalize_title  # noqa: E402
# `_SECTION_RE` — та же якорная строка раздела карточки, что в разборе `src/rules_layer.py`
# и в читателе правил. Своё определение завело бы второе представление о разделе: отчёт
# считал бы состав не по тем якорям, по которым правило проверяет `check_rules_layer.py`.
from rules_read import (ALWAYS_ADDRESSES, PURPOSE_CHARS, _SECTION_RE,  # noqa: E402
                        always_norms, layer_cards, layer_marker_addresses, load_cards,
                        purpose_of)
from rules_logging import FORMAT_BRIEF, FORMAT_FULL, log_path, open_session  # noqa: E402

REPORT_STEM = "rules_always"
REPORTS_DIR = PROJECT_ROOT / "Reports"


# ------------------------------------------------------------------ выборка
def collect_cards(include_marked=False):
    """Карточки дерева + даты изменения строк.

    Даты — provenance отчёта: по ним видно, когда набор правил менялся в последний раз и
    какие карточки правили в тот же заход. Отчёт о правилах без даты изменения не отвечает
    на вопрос, актуален ли снимок.
    """
    from database import get_cursor

    with get_cursor() as cur:
        cards = load_cards(cur, include_marked=include_marked)
        stamps = {}
        ids = sorted(c["id"] for c in cards)
        if ids:
            cur.execute("SELECT id, updated_at FROM knowledge_snippets "
                        "WHERE id = ANY(%s)", (ids,))
            for row in cur.fetchall():
                stamps[int(row["id"])] = str(row["updated_at"])[:19]
    return cards, stamps


def sections_of(card):
    """Разделы карточки и их объём — что именно попадает в контекст.

    Разделы (`===WHEN===`, `===SCOPE===`, …) машинные, поэтому состав считается по ним:
    перечень показывает структуру always-карточки без её чтения. Пустой список — отдельный
    ответ: карточка описана без разделов, и это видно по строке отчёта, а не молчанием.
    """
    lines = (card["answer"] or "").splitlines()
    marks = [(idx, _SECTION_RE.match(line.strip()).group(1))
             for idx, line in enumerate(lines) if _SECTION_RE.match(line.strip())]
    out = []
    if marks:
        intro = len("\n".join(lines[:marks[0][0]]))
        if intro:
            out.append(("(вступление без разделов)", intro))
    elif lines:
        return [("(карточка без машинных разделов)", len("\n".join(lines)))]
    for pos, (start, name) in enumerate(marks):
        stop = marks[pos + 1][0] if pos + 1 < len(marks) else len(lines)
        out.append((name, len("\n".join(lines[start:stop]))))
    return out


def heading(address):
    """Уровень заголовка = число сегментов адреса (`rules:` → H1, `rules:kb-rules:` → H2).

    Уровень берётся из `heading_level` модуля `src/rules_layer.py` — тем же определением,
    которым пользуется снимок дерева: два отчёта об одном дереве обязаны читаться одинаково,
    иначе поиск по заголовку в одном файле не работает для другого. `None` означает «заголовка
    нет»: карточка глубже `MAX_ADDRESS_SEGMENTS` показывается меткой адреса текстом, а не
    вложенным заголовком (шесть уровней на два разных узла — тот же дефект, что одинаковые
    заголовки у разных карточек).
    """
    level = RL.heading_level(address)
    return None if level is None else "#" * level


def md_cell(text):
    """Значение ячейки таблицы: одной строкой, без разыгрывания символов таблицы."""
    return " ".join((text or "").split()).replace("|", "\\|")


# ------------------------------------------------------------------ отчёт
def report_head(cards, stamps):
    """Шапка отчёта: таблица набора, объём против бюджета, карантин, состав по разделам.

    Недостающий адрес называется, а не пропускается: пустой ответ по политике «читаем всегда»
    прочитался бы как «правил нет», тогда как карточка снята к удалению или не собрана.
    """
    known = {c["norm"]: c for c in cards}
    picked = [(a, known.get(normalize_title(a))) for a in ALWAYS_ADDRESSES]
    found = [(a, c) for a, c in picked if c]
    missing = [a for a, c in picked if not c]

    lines = []
    add = lines.append
    add("> Отчёт по правилам, которые читаются всегда. Построен: "
        + datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    add(">")
    add("> Набор задаёт не этот файл: адреса и порядок — константа `ALWAYS_ADDRESSES` в")
    add("> `tools/rules_read.py`; её же поднимает роль агента — `.clinerules/1C_Rule.md`")
    add("> запускает `python tools/rules_read.py --always`. Файл является снимком, а не")
    add("> правилом: правку делают строкой БД (`update_snippet_tool`), после чего отчёт")
    add("> перегоняют. Перегонка: `python tools/rules_always_report.py` (в консоль — `--stdout`).")
    add("")

    add("## 1. Набор как политика")
    add("")
    add(f"Адресов в политике: {len(ALWAYS_ADDRESSES)}; найдено в базе: {len(found)}; "
        f"карточек дерева правил в базе всего: {len(cards)}.")
    add("")
    add("| адрес | id | симв. | от бюджета always | обновлена |")
    add("| --- | ---: | ---: | ---: | --- |")
    for address, card in found:
        share = 100.0 * card["size"] / RL.ALWAYS_BUDGET_CHARS
        mark = " ⚠️помечена" if card["marked"] else ""
        add(f"| `{address}`{mark} | {card['id']} | {card['size']} | {share:.0f}% "
            f"| {stamps.get(card['id'], '?')} |")
    for address in missing:
        add(f"| `{address}` | — | — | — | **нет в базе** |")
    add("")
    total = sum(c["size"] for _a, c in found)
    budget = RL.ALWAYS_BUDGET_CHARS
    add(f"ИТОГ по набору: **{total} симв.** при `ALWAYS_BUDGET_CHARS = {budget}` "
        f"(`src/rules_layer.py`) — {100.0 * total / budget:.0f}% бюджета.")
    add("")
    add("По отдельной карточке и по слою бюджет считает `tools/check_rules_layer.py`. Набор")
    add("`--always` проходит через два слоя сразу — корень дерева и слой `kb-rules`, — поэтому")
    add("итог по набору считается здесь и называется числом: это и есть тот объём, который")
    add("попадает в контекст при каждом заходе агента, а не на отдельной задаче.")
    add("")
    if total > budget:
        add(f"⚠️ Перебор бюджета: каждая карточка по отдельности в {budget} проходит, а набор")
        add("целиком — нет. Проверка по слоям такого перебора не видит, потому что набор")
        add("лежит в двух слоях сразу. Решение за оператором: делить карточку слоя или менять")
        add("бюджет; отчёт только называет число.")
    elif total > 0.8 * budget:
        add(f"⚠️ Запас мал: набор занимает больше 80% бюджета ({total} из {budget}).")
    else:
        add("Каждая карточка и набор целиком в бюджет помещаются.")
    add("")
    marked = [c for _a, c in found if c["marked"]]
    if marked:
        add(f"⚠️ В наборе карточек, помеченных к удалению: {len(marked)}. Скрытая строка")
        add("правилом не является (узел Q1), то есть политика ссылается на несуществующее")
        add("правило — строку надо вернуть или снять адрес из константы:")
        for card in marked:
            add(f"- `{card['address']}` (id {card['id']}): "
                + md_cell(card["reason"] or "причина не указана"))
    else:
        add("Карточек, помеченных к удалению, в наборе нет: метка `mark-for-deletion`")
        add("в его строках не стоит.")
    add("")

    add("## 2. Состав карточек набора по машинным разделам")
    add("")
    add("Разделы — машинные якоря правила (`===WHEN===`, `===SCOPE===`, …); по ним видно, что")
    add("именно попадает в контекст, когда карточку читают целиком.")
    add("")
    for address, card in found:
        add(f"- `{address}` (id {card['id']}, {card['size']} симв.):")
        for name, size in sections_of(card):
            label = name if name.startswith("(") else f"==={name}==="
            add(f"  - `{label}` — {size} симв.")
        if not card["aliases"]:
            add("  - (алиасов нет)")
        else:
            add(f"  - алиасы: {md_cell(', '.join(card['aliases'][:12]))}"
                + (f" … (всего {len(card['aliases'])})" if len(card["aliases"]) > 12 else ""))
    add("")
    return lines, found, missing, total, budget


def report_body(lines, found, missing, stamps):
    """Полный текст каждой always-карточки дословно, в порядке чтения.

    Усечения нет: смысл отчёта в том, чтобы показать ровно то, что читатель правил печатает
    целиком. Разделы `===LINKS`/`===INDEX` остаются в тексте — по ним видно, куда агент идёт
    с следующего шага; вырезав их, отчёт перестал бы совпадать с `--always`.
    """
    add = lines.append
    add("## 3. Полный текст правил набора (дословно)")
    add("")
    add("Порядок — порядок чтения: сначала корень дерева (карта слоёв, формат адреса),")
    add("затем общие записи слоя знаний. Содержимое перенесено из `knowledge_snippets.answer`")
    add("без правок; заголовок — по числу сегментов адреса.")
    add("")
    for address, card in found:
        marks = heading(address)
        if marks:
            add(f"{marks} {address}")
        else:
            add(f"**`{address}`** — карточка глубже `MAX_ADDRESS_SEGMENTS`, заголовка у неё")
            add("нет; показывается меткой адреса, как в снимке дерева.")
        add("")
        add(f"*id {card['id']} · {card['size']} симв. · изменена "
            f"{stamps.get(card['id'], '?')} · алиасов: {len(card['aliases'])}*")
        if card["marked"]:
            add("*⚠️ помечена к удалению: "
                + md_cell(card["reason"] or "причина не указана") + "*")
        add("")
        add((card["answer"] or "(содержимого нет)").rstrip())
        add("")
    if missing:
        add("### Чего нет в базе")
        add("")
        for address in missing:
            add(f"- `{address}` — адрес стоит в политике `ALWAYS_ADDRESSES`, карточки с")
            add("  таким адресом в базе нет: правило снято, переименовано или не собрано.")
        add("")


def report_layers(lines, cards):
    """Граница набора: вариативные слои — те же строки, что даёт `rules_read.py --layers`.

    Строка слоя говорит о корневой карточке слоя: всегда читается корень, дети читаются
    адресом по задаче. Промолчать про вариативные слои значит выдать набор всегда за весь
    набор правил, тогда как три слоя серверов конфигураций в него не входят намеренно.
    """
    add = lines.append
    add("## 4. Граница набора: что поднимают вариативно")
    add("")
    add("Эти слои в `--always` не входят и поднимаются, только когда задача касается их")
    add(f"назначения. Назначение берётся из описательного раздела корневой карточки слоя")
    add(f"(`SUMMARY`/`SCOPE`) и ограничено {PURPOSE_CHARS} симв. — полный текст читают адресом")
    add("слоя; число карточек и объём считаются по живым строкам (помеченные к удалению сняты).")
    add("")
    add("| политика корня | карточек слоя | символов слоя | адрес слоя | назначение |")
    add("| --- | ---: | ---: | --- | --- |")
    always = always_norms()
    for marker, root_card, group in layer_cards(cards):
        tree_addr, legacy_addr = layer_marker_addresses(marker)
        total_layer = sum(c["size"] for c in group)
        entry = root_card["address"] if root_card else f"{tree_addr} — корневого узла слоя нет"
        policy = "корень всегда" if root_card and root_card["norm"] in always else "вариативно"
        purpose = purpose_of(root_card) if root_card else "(корневой карточки слоя нет)"
        add(f"| {policy} | {len(group)} | {total_layer} | `{entry}` | {md_cell(purpose)} |")
        legacy = [c for c in group if c["norm"].startswith(legacy_addr)]
        if legacy:
            add(f"| ⚠️ | {len(legacy)} | — | прежнее: `{legacy_addr}…` "
                "| не переразвёрнуто в дерево |")
    add("")
    add("Столбцы «карточек слоя / символов слоя» считают слой целиком: в набор всегда входит")
    add("только корневая карточка слоя (её размер — в разделе 1), остальные карточки слоя")
    add("читаются адресом и только по задаче.")
    add("")
    add("Журнал (`rules:<слой>:journal:`) и проверки (`rules:<слой>:checks:`) правилами не")
    add("являются (`RESERVED_SEGMENTS` в `src/rules_layer.py`), в набор всегда не входят и")
    add("действующим правилом не считаются.")
    add("")


def report_tail(lines):
    """Как перечитать набор, где править и чем сверить — команды, а не пересказ правил."""
    add = lines.append
    add("## 5. Чем перечитать, где править, чем сверить")
    add("")
    add("```")
    add("python tools/rules_read.py --always")
    add("python tools/rules_read.py --layers")
    add('python tools/rules_read.py "rules:kb-rules:"              # префикс: родитель + дети')
    add('python tools/rules_read.py "rules:kb-rules:always:index"  # одна карточка целиком')
    add('python tools/rules_read.py --tree "rules:kb-rules:"      # перечень поддерева')
    add("python tools/check_rules_layer.py --layer kb-rules       # доступность и бюджет слоя")
    add("python src/rules_report.py --query rules: -v 1           # дерево правил целиком")
    add("```")
    add("")
    add("Правка делается строкой БД: `update_snippet_tool` (`question` = адрес, `answer` =")
    add("текст), прежнее содержимое уходит в `snippet_audit_log`. Файлы `docs/rules/*.md` —")
    add("черновики; `.clinerules/1C_Rule.md` — маршрутизатор роли: он называет канал чтения")
    add("и перечень always-адресов, но тексты правил не хранит.")
    return lines


def build_report(cards, stamps):
    """Сборка отчёта целиком: шапка, тексты набора, граница, команды.

    Ответ — текст, найденные карточки и пропущенные адреса. Найденные возвращаются не для
    красоты: точка входа пишет их в лог обращений, и молча потерять этот список значило бы
    получить лог, в котором прогон отчёта неотличим от любого другого прогона.
    """
    lines, found, missing, _total, _budget = report_head(cards, stamps)
    report_body(lines, found, missing, stamps)
    report_layers(lines, cards)
    report_tail(lines)
    return "\n".join(lines) + "\n", found, missing


# ------------------------------------------------------------------ точка входа
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="rules_always_report.py",
        description="Отчёт по правилам, которые читаются всегда: набор из константы "
                    "ALWAYS_ADDRESSES, полный текст карточек, объём против бюджета и "
                    "граница вариативных слоёв.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="примеры:\n"
               "  python tools/rules_always_report.py\n"
               "  python tools/rules_always_report.py --stdout\n"
               "  python tools/rules_always_report.py --out rules_always_review.md\n")
    parser.add_argument("--out", help="имя файла в Reports/ или абсолютный путь "
                                     "(по умолчанию `rules_always_<дата>.md`)")
    parser.add_argument("--stdout", action="store_true",
                       help="печатать отчёт в консоль, файл не писать")
    parser.add_argument("--marked", action="store_true",
                       help="включить карточки, помечённые к удалению (разбор карантина)")
    parser.add_argument("--no-log", action="store_true",
                       help="не дописывать обращение в лог правил (logs/rules_load.log)")
    parser.add_argument("--log-file", metavar="ИМЯ",
                       help="писать обращение в другой файл каталога logs/ — замер не пачает "
                            "рабочий лог")
    parser.add_argument("--full-log", "--full", dest="full_log", action="store_true",
                        help="подробный формат лога: сессия с режимом вызова, объёмом и "
                             "итогом (по умолчанию пишется краткий — дата и адрес карточки)")
    args = parser.parse_args(argv)

    log = open_session("tools/rules_always_report.py",
                       " ".join(argv) or "(без аргументов)",
                       path=(log_path(args.log_file) if args.log_file else None),
                       enabled=not args.no_log,
                       fmt=(FORMAT_FULL if args.full_log else FORMAT_BRIEF))
    with log:
        cards, stamps = collect_cards(include_marked=args.marked)
        if not cards:
            print("ОШИБКА: ни одной карточки дерева правил (`rules:`) в базе нет — "
                  "набор правил не загружен.")
            log.note("в базе нет ни одной карточки дерева правил — набор не загружен")
            return 1
        text, found, missing = build_report(cards, stamps)
        # В лог пишется найденный набор, а не число адресов политики: пропущенная карточка —
        # событие `НЕ НАЙДЕНО`, а не строка загрузки. Корень дерева лог выделяет сам.
        for _address, card in found:
            log.loaded(card)
        for address in missing:
            log.missed(address, "адрес always-набора отсутствует в базе")
        total = sum(int(card["size"]) for _address, card in found)
        log.note(f"объём always-набора по отчёту: карточек {len(found)}, {total} символов при "
                 f"бюджете {RL.ALWAYS_BUDGET_CHARS} — "
                 + ("ПЕРЕБОР" if total > RL.ALWAYS_BUDGET_CHARS else "в бюджете"))
        if args.stdout:
            print(text)
        else:
            path = Path(args.out) if args.out else Path(
                f"{REPORT_STEM}_{datetime.date.today().isoformat()}.md")
            if not path.is_absolute():
                path = REPORTS_DIR / path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"ОТЧЁТ: {path}")
            log.note(f"отчёт записан: {path}")
        print(f"Набор: адресов в политике {len(ALWAYS_ADDRESSES)}, "
              f"текстов в отчёте {len(ALWAYS_ADDRESSES) - len(missing)}.")
        if not args.no_log:
            print(f"ЛОГ обращения: {log.path}")
        if missing:
            print("НЕТ В БАЗЕ: " + ", ".join(missing))
            return 1
        return 0


if __name__ == "__main__":
    sys.exit(main())
