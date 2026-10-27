#!/usr/bin/env python3
"""Перегенерация карточки-оглавления журнала слоя правил (узел RULE-V2).

Зачем. Карточки журнала живут только строками `local_doc` (снимок прежних правил в файл-черновик
не переносят), а их оглавление — обычная карточка `<метка>:journal:index`.
`readdress_rules_layer.py` меняет заголовки карточек, и оглавление после этого перечисляет прежние
адреса: ссылки ведут в карточки, которых больше нет. `tools/check_rules_layer.py` это ловит
(полнота перечня и разрешимость ссылок индекса), этот инструмент — чинит.

Что делает:
  1. берёт фактический состав журнала слоя из БД (теги метки и `journal`);
  2. переносит описания разделов из прежнего оглавления и рукописный блок hand:start/hand:end;
  3. пишет карточку в `docs/rules/<метка>.md` на месте существующей (или дописывает), откуда её
     забирает `tools/migrate_rules_to_layer.py --apply`.

Тексты самих карточек журнала не меняются: переписанный снимок перестаёт быть доказательством
того, что было (правило `rules:always:authoring`, п. 3 про состояние journal).

Запуск:
    python tools/regen_journal_index.py --layer kb-rules            # только отчёт
    python tools/regen_journal_index.py --layer kb-rules --write    # записать в черновик
"""
import argparse
import re
import sys
from datetime import date as _date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import rules_layer as RL  # noqa: E402
from quarantine import MARK_ARRAY, sql_not_marked  # noqa: E402

try:
    # Выдача содержит ⚠️ и русские слова: в кодировке консоли cp1251 печать падала
    # UnicodeEncodeError и прогон обрывался до записи карточки (замер 27.10.2026).
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SOURCE_FILE = ".clinerules/{marker}_Rule.md"
REGEN_NOTE = ("Перечень перегенерирован {date} после переадресации карточек в состояние "
              "`journal` (`tools/readdress_rules_layer.py`): прежние строки оглавления вели в "
              "адреса до переименования. Тексты самих карточек журнала при этом не менялись.")
REGEN_NOTE_DB = ("Перечень порождён {date} по фактическому составу БД "
                 "(`tools/regen_journal_index.py`), файла-черновика прежних текстов слоя в "
                 "репозитории нет — узлы журнала дерева таким файлом не описываются. Тексты "
                 "самих карточек журнала при этом не менялись.")


def journal_rows(cur, marker):
    """Карточки журнала слоя из БД: {адрес: answer}, включая само оглавление.

    Отбор берётся у `rules_layer.layer_sql` — того же предиката, что у проверки слоя. Фильтром по
    тегу метки его не заменить: корневой тег `1c-rules-root` стоит на карточках всех пяти слоёв,
    и под меткой `rules` он подобрал 32 карточки журнала вместо двух корневых — оглавление корня
    переписалось бы чужими строками (замер 27.10.2026). Карантин предикат не включает; снятые
    строки в перечень не попадают отдельным условием.
    """
    where, params = RL.layer_sql(marker)
    cur.execute(
        f"SELECT question, answer FROM knowledge_snippets WHERE {where} AND %s = ANY(tags)"
        + sql_not_marked() + " ORDER BY question",
        (*params, RL.STATE_JOURNAL, MARK_ARRAY),
    )
    return {row["question"]: row["answer"] for row in cur.fetchall()}


def old_descriptions(old_text):
    """Строки прежнего оглавления: прежний адрес -> (исходник, описание раздела)."""
    out = {}
    for line in (old_text or "").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not cells[0].startswith("`"):
            continue
        old = cells[0].strip("`")
        if not old.startswith(tuple(RL.markers())):
            continue
        out[old] = (cells[1].strip("` "), cells[2])
    return out


def old_keys(marker, address):
    """Прежние адреса карточки журнала в порядке предположения.

    Переадресация вставляла разный сегмент: разделы файла правил получали `journal:ref:`,
    дополнения шапки — `journal:hdr:`. Поэтому у одной текущей карточки два правдоподобных
    прежних имени; описание берётся по тому, которое встречается в старом оглавлении.
    """
    tail = address.split(":", 2)[2]                    # после метки и состояния: hdr:01, ref:06:2
    kind, _, number = tail.partition(":")
    stem = f"{marker}:{RL.STATE_JOURNAL}" if kind == "hdr" else f"{marker}:{kind}"
    keys = [f"{stem}:{number}"] if number else [stem]
    return keys + [address, f"{marker}:{tail}"]


def build_card(marker, rows, described, card_date):
    """Текст карточки оглавления: снимок состава журнала текущими адресами."""
    index_address = f"{marker}:{RL.STATE_JOURNAL}:index"
    old_text = rows.get(index_address, "")
    hand = re.search(r"<!-- hand:start -->.*?<!-- hand:end -->", old_text, re.S)
    # Файл-черновик прежних текстов слоя есть только у слоёв, перенесённых в журнал дословно.
    # Для слоёв дерева таких файлов репозиторий не содержит (узел RESTRUCTURE-LAYERS), поэтому
    # называть несуществующий файл в колонке «Исходник» — значит врать: колонка остаётся
    # описательной и заполняется из прежнего перечня (замер 27.10.2026: для корня инструмент
    # подставлял `.clinerules/rules_Rule.md`, которого никогда не было).
    source = SOURCE_FILE.format(marker=marker)
    has_source = (PROJECT_ROOT / source).exists()
    note = (REGEN_NOTE if has_source else REGEN_NOTE_DB).format(date=card_date)
    header = ("| Адрес | Исходник | Раздел исходника |\n|---|---|---|\n" if has_source
              else "| Адрес | Откуда взят снимок | Что в нём |\n|---|---|---|\n")
    card = (
        f"## {index_address}\n\n===WHEN===\nНужен обзор снимка прежних правил слоя — что именно "
        "перенесено, какой раздел файла правил за этим закреплён и где читать замер или причину "
        "решения. Формат карточек журнала рабочим правилам не предъявляется, их тексты не "
        "правятся.\n\n"
        f"Карточка-оглавление журнала слоя `{marker}`. Это перечень снимка прежних правил: по "
        "строке берут карточку адресом (`search_docs_tool` точным заголовком → `get_snippet_tool` "
        "по id из выдачи).\n\n"
        + (hand.group(0) + "\n\n" if hand else "")
        + note + "\n\n"
        + header
    )
    missing = []
    for address in sorted(k for k in rows if k != index_address):
        src, section = (source if has_source else ""), ""
        for key in old_keys(marker, address):
            if key in described:
                src, section = described[key]
                break
        if not section:
            missing.append(address)
        src_cell = f"`{src}`" if src else "—"
        card += f"| `{address}` | {src_cell} | {section} |\n"
    return index_address, card, missing


def upsert_card(path, index_address, card):
    """Замена карточки на месте: две карточки оглавления расходятся так же, как устаревшая."""
    text = path.read_text(encoding="utf-8")
    head = f"\n## {index_address}\n"
    if head not in text:
        path.write_text(text.rstrip("\n") + "\n\n" + card, encoding="utf-8")
        return "дописана"
    start = text.index(head)
    nxt = re.search(r"\n## ", text[start + 1:])
    end = start + 1 + nxt.start() if nxt else len(text)
    path.write_text(text[:start] + "\n" + card + text[end:], encoding="utf-8")
    return "перегенеррована на месте"


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Перегенерация оглавления журнала слоя правил по фактическому составу БД")
    ap.add_argument("--layer", required=True, help="метка слоя (например kb-rules)")
    ap.add_argument("--date", default="", help="дата в пометке перечня (по умолчанию сегодня)")
    ap.add_argument("--write", action="store_true",
                    help="записать карточку в docs/rules/<метка>.md (по умолчанию только отчёт)")
    args = ap.parse_args(argv)

    marker = args.layer
    if marker not in RL.LAYERS:
        print(f"неизвестная метка слоя {marker!r}: известными считаются {list(RL.LAYERS)}")
        return 1
    if RL.LAYER_FORMAT.get(marker, 1) != 2:
        # Слой формата 1 переносится дословно: его прежние тексты живут под своими заголовками,
        # состояний у карточек нет, поэтому и оглавления журнала у него нет. Просить его
        # перегенерировать — значит выдумывать адрес, которого слой не производит.
        print(f"[{marker}] слой формата 1: карточек состояния `journal` у него нет, "
              f"прежние тексты читаются прежними заголовками — оглавление не перегенерируется")
        return 1

    from database import get_cursor
    with get_cursor() as cur:
        rows = journal_rows(cur, marker)
    index_address = f"{marker}:{RL.STATE_JOURNAL}:index"
    content = {k: v for k, v in rows.items() if k != index_address}
    if not content:
        print(f"[{marker}] карточек журнала в БД нет — перегенерировать нечего "
              f"(для слоя формата 1 прежние тексты лежат под своими адресами, оглавления нет)")
        return 1

    described = old_descriptions(rows.get(index_address, ""))
    card_date = args.date or _date.today().strftime("%d.%m.%Y")
    _, card, missing = build_card(marker, rows, described, card_date)

    print(f"[{marker}] карточек журнала: {len(content)}, оглавление: {index_address}, "
          f"описаний перенесено: {len(content) - len(missing)}, без описания: {len(missing)}")
    for address in missing:
        print(f"  ⚠️ {address}: описания нет ни в прежнем оглавлении, ни в имени адреса — "
              f"строка останется пустой, оглавление по ней не работает")
    if not args.write:
        print("режим отчёта: карточка в черновик не записана (для записи нужен --write)")
        return 0
    path = PROJECT_ROOT / RL.RULES_DIR / f"{marker}.md"
    action = upsert_card(path, index_address, card)
    print(f"[{marker}] карточка {index_address} {action} в {path.name}; далее: "
          f"python tools/migrate_rules_to_layer.py --file {RL.RULES_DIR}/{marker}.md --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())

