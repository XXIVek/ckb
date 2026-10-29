# -*- coding: utf-8 -*-
"""_v48_rules_cards.py — регистрация карточек правил узла V48 (приём П7 узлов V46/V47).

Что записывает (идемпотентно: повтор не создаёт дублей и не вносит вторую строку перечня):

  1. `rules:core-rules:functional:per-block-table-view-checks` — инвариант оператора
     «у каждого блока объектов своя таблица, своя витрина, свои проверки»;
  2. `rules:core-rules:functional:add-object-block` — порядок шагов при добавлении нового блока
     объектов конфигурации (план → решения оператора → DDL/миграция → словарь версионных таблиц →
     разбор → писатель → стадия/контракт → постоянная проверка → карточки слоя и журнал);
  3. `rules:kb-rules:functional:rules-new-card` — порядок шагов при добавлении самой
     функции-инструмента (адрес, разделы, теги, алиасы, строка перечня слоя, ссылки, проверки).
     `rules:kb-rules:functional:rules-work` описывает поиск/чтение/правку/снятие правила, но не
     создание — пропуск и закрывается;
  4. `rules:kb-rules:journal:node:add-rule-card-2026-10` — снимок журнала слоя об этом изменении:
     `tools/check_rules_layer.py` требует, чтобы функциональная карточка ссылалась на адрес истории
     своего слоя, а сам снимок был назван в оглавлении журнала.

Каждая карточка регистрируется в перечне своего слоя (`===LINKS` + `===INDEX`) и получает ссылку
из карточки, которая порождает к ней обращение: `edit-mcp-code` (правка DDL и кода сервера) и
`rules-work` (работа с правилами). Без строки перечня `_layer_tree_check.py` считает карточку
несуществующей для читающего слой, а без ссылки маршрут обрывается.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v48_rules_cards.py            # сухо: что будет сделано
    python _v48_rules_cards.py --write    # записать
Код возврата 0 — все шаги выполнены или уже внесены; 1 — хотя бы один шаг отказал.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402
from _v48_rules_texts import (  # noqa: E402
    PER_BLOCK_ADDRESS, ADD_OBJECT_BLOCK_ADDRESS, NEW_RULE_CARD_ADDRESS, KB_JOURNAL_ADDRESS,
    LINKS, PER_BLOCK, ADD_OBJECT_BLOCK, NEW_RULE_CARD, KB_JOURNAL,
)

CORE = "core-rules"
KB = "kb-rules"
CORE_LAYER = f"{RL.ROOT_MARKER}:{CORE}:"
KB_LAYER = f"{RL.ROOT_MARKER}:{KB}:"
EDIT_CODE = f"{RL.functional_prefix(CORE)}edit-mcp-code"
RULES_WORK = f"{RL.functional_prefix(KB)}rules-work"
# Теги новой карточки берутся с живой карточки того же слоя: вид карточки называется тегом,
# и своя комбинация тегов разошлась бы с проверкой слоя (_layer_tree_check.py).
TAGS_SOURCE = {CORE: f"{RL.functional_prefix(CORE)}load-catalog",
               KB: f"{RL.functional_prefix(KB)}rules-work",
               "kb-journal": f"{RL.ROOT_MARKER}:{KB}:{RL.STATE_JOURNAL}:node:fragments-2026-09"}

ALIASES_RU = {
    PER_BLOCK_ADDRESS: [
        "у каждого блока объектов своя таблица",
        "своя витрина и свои проверки блока",
        "не класть свойства в общий jsonb контейнер",
        "отдельная таблица на новый вид объектов конфигурации",
        "ключ таблицы второго уровня configuration_uuid object_name revision_no",
        "связь по имени объекта а не по uuid",
        "в конфигурации хранится список имен объектов",
    ],
    ADD_OBJECT_BLOCK_ADDRESS: [
        "как добавить новый вид объектов конфигурации",
        "порядок шагов узла загрузки свойств вида",
        "новый блок объектов план решения оператора миграция",
    ],
    NEW_RULE_CARD_ADDRESS: [
        "как добавить функцию-инструмент",
        "создать новую карточку правила",
        "регистрация карточки в индексе слоя",
        "разделы карточки правила when must forbid",
    ],
    KB_JOURNAL_ADDRESS: [
        "снимок: добавили карточку создания правила",
        "процедура добавления функции-инструмента 29.10.2026",
    ],
}

# Строка перечня журнала слоя: узел журнала обязан быть назван в оглавлении журнала
# (`tools/check_rules_layer.py`: снимок, на который не ссылается ни карточка, ни перечень,
# не читается).
JOURNAL_ROWS = [
    dict(card=f"{RL.ROOT_MARKER}:{KB}:{RL.STATE_JOURNAL}:{RL.INDEX_LEAF}",
         anchor="| `rules:kb-rules:journal:node:elements-2026-10` |",
         row="| `rules:kb-rules:journal:node:add-rule-card-2026-10` | строка БД "
             "(узел V48, 29.10.2026) | создание карточки правил: процедура добавления "
             "функции-инструмента |",
         label="журнал kb-rules: строка нового узла"),
]

# Строки перечня слоя: вставка по образцу существующей строки (порядок — по адресу).
# anchor — единственная строка-образец; `| <id> |` уникален, голый адрес с exact=True — тоже.
REGISTRATIONS = [
    # add-object-block идёт раньше answer-and-evidence (порядок по адресу).
    dict(marker=CORE, layer=CORE_LAYER, address=ADD_OBJECT_BLOCK_ADDRESS,
         links_anchor="| 6156 |", index_anchor="rules:core-rules:functional:answer-and-evidence",
         index_before=True),
    # per-block-table-view-checks — после load-catalog и перед root-modules.
    dict(marker=CORE, layer=CORE_LAYER, address=PER_BLOCK_ADDRESS,
         links_anchor="| 6148 |", index_anchor="rules:core-rules:functional:load-catalog",
         index_before=False),
    # rules-new-card — после quarantine и перед rules-report.
    dict(marker=KB, layer=KB_LAYER, address=NEW_RULE_CARD_ADDRESS,
         links_anchor="| 6130 |", index_anchor="rules:kb-rules:functional:quarantine",
         index_before=False),
]

# Ссылки-указатели: правило читают адресом, поэтому ссылка из карточки-источника — тот же шаг.
POINTERS = [
    dict(address=EDIT_CODE,
         anchor="4. Изменение схемы — строго парой",
         line="4.1. Новый блок объектов конфигурации (новая таблица свойств вида) поднимает карточки "
              "`rules:core-rules:functional:per-block-table-view-checks` (своя таблица, своя "
              "витрина, свои проверки) и `rules:core-rules:functional:add-object-block` (порядок "
              "шагов) — до правки DDL, а не после.",
         label="шаг 4.1 — новый блок объектов"),
    dict(address=RULES_WORK,
         anchor="4. Исправить правило — `update_snippet_tool",
         line="3.1. Создать новую карточку (функцию-инструмент слоя) — порядок шагов держит "
              "карточка `rules:kb-rules:functional:rules-new-card`: адрес, разделы по состоянию, "
              "тег вида, алиасы, строка перечня слоя и ссылка из карточки-источника.",
         before=True, label="шаг 3.1 — создание карточки"),
]


def level_aliases(address):
    """Алиасы каждого уровня адреса — их требует дампер (`by_alias`)."""
    parts = (address or "").split(":")
    return [
        ":".join(parts[:i]) + ":"
        for i in range(1, len(parts))
        if any(parts[:i])
    ]


def card_aliases(address, marker, ru):
    """Алиасы карточки: полный адрес, адрес без префикса дерева, префиксы уровней, метка слоя и
    ручные формулировки оператора (решение оператора 24.10.2026)."""
    short = address[len(RL.ROOT_MARKER) + 1:]
    return list(dict.fromkeys(
        [address, short] + level_aliases(address) + level_aliases(short) + [marker] + ru))


def existing_tags(cur, marker):
    """Теги живой карточки того же слоя — новая строка не должна отличаться по виду."""
    cur.execute("SELECT tags FROM knowledge_snippets WHERE question=%s", (TAGS_SOURCE[marker],))
    row = cur.fetchone()
    if not row:
        raise SystemExit(f"нет карточки-образца для тегов слоя {marker}: {TAGS_SOURCE[marker]}")
    return list(row["tags"] or [])


def write_card(cur, address, answer, tags, aliases, dry):
    """Строка правила по адресу: `question` — адрес, `answer` — содержимое (контракт узла V44)."""
    key = RL.source_url(address)
    cur.execute("SELECT id FROM knowledge_snippets WHERE source_url=%s", (key,))
    known = cur.fetchone()
    print(f"{'обновлено ' if known else 'создано   '}  {address}  {len(answer)} симв.")
    if dry:
        return (known or {"id": "?"})["id"]
    if known:
        cur.execute("UPDATE knowledge_snippets SET answer=%s, tags=%s WHERE id=%s",
                    (answer, tags, known["id"]))
        snippet_id = known["id"]
    else:
        cur.execute(
            "INSERT INTO knowledge_snippets (groups_id, question, answer, source_url, tags,"
            " confidence, is_verified) VALUES (NULL, %s, %s, %s, %s, 1.0, TRUE) RETURNING id",
            (address, answer, key, tags))
        snippet_id = cur.fetchone()["id"]
    for alias in aliases:
        cur.execute(
            "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags,"
            " weight) VALUES (%s,'snippet',NULL,%s,%s,1.0) "
            "ON CONFLICT (alias_name, snippets_id) WHERE snippets_id IS NOT NULL DO NOTHING",
            (alias, snippet_id, tags))
    return snippet_id


def append_after(cur, address, anchor, line, dry, label="", exact=False, before=False):
    """Дописать строку рядом со строкой-образцом (перечни `===LINKS`/`===INDEX` идут блоками)."""
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (address,))
    row = cur.fetchone()
    if not row:
        print(f"⚠️ ОТКАЗ: карточки нет — {address}")
        return False
    text = row["answer"] or ""
    lines = text.splitlines()
    want = anchor.strip()
    if exact:
        if any(item.strip() == line.strip() for item in lines):
            print(f"без изменений  {address}  строка перечня уже есть — {label}")
            return True
        at = [i for i, item in enumerate(lines) if item.strip() == want]
    else:
        if line in text:
            print(f"без изменений  {address}  строка уже есть — {label}")
            return True
        at = [i for i, item in enumerate(lines) if anchor in item]
    if len(at) != 1:
        print(f"⚠️ ОТКАЗ {address}: строк-образцов {len(at)} — {anchor[:60]!r}")
        return False
    lines.insert(at[0] if before else at[0] + 1, line)
    print(f"{'строка       ' if not dry else 'сухо-строка  '}  {address}  + {label}")
    if not dry:
        cur.execute("UPDATE knowledge_snippets SET answer=%s WHERE id=%s",
                    ("\n".join(lines) + "\n", row["id"]))
    return True


def main(argv=None):
    dry = "--write" not in (argv or [])
    texts = {PER_BLOCK_ADDRESS: PER_BLOCK, ADD_OBJECT_BLOCK_ADDRESS: ADD_OBJECT_BLOCK,
             NEW_RULE_CARD_ADDRESS: NEW_RULE_CARD, KB_JOURNAL_ADDRESS: KB_JOURNAL}
    markers = {PER_BLOCK_ADDRESS: CORE, ADD_OBJECT_BLOCK_ADDRESS: CORE,
               NEW_RULE_CARD_ADDRESS: KB, KB_JOURNAL_ADDRESS: KB}
    # Теги узла журнала берутся с прежнего узла журнала того же слоя, теги правила — с живой
    # функциональной карточки: вид карточки называется тегом, и своя сборка тегов разошлась бы
    # с проверкой слоя.
    tags_keys = {address: markers[address] for address in texts}
    tags_keys[KB_JOURNAL_ADDRESS] = "kb-journal"
    ok = True
    with get_cursor() as cur:
        ids = {}
        for address, answer in texts.items():
            marker = markers[address]
            ids[address] = write_card(cur, address, answer, existing_tags(cur, tags_keys[address]),
                                      card_aliases(address, marker, ALIASES_RU[address]), dry)
        for row_spec in JOURNAL_ROWS:
            ok &= append_after(cur, row_spec["card"], row_spec["anchor"], row_spec["row"], dry,
                               label=row_spec["label"])
        for reg in REGISTRATIONS:
            row = (f"| {ids.get(reg['address'], '?')} | `{reg['address']}` | "
                   f"{LINKS[reg['address']]} |")
            ok &= append_after(cur, reg["layer"], reg["links_anchor"], row, dry,
                               label=f"LINKS {reg['address']}")
            ok &= append_after(cur, reg["layer"], reg["index_anchor"], reg["address"], dry,
                               label=f"INDEX {reg['address']}", exact=True,
                               before=reg["index_before"])
        for pointer in POINTERS:
            ok &= append_after(cur, pointer["address"], pointer["anchor"], pointer["line"], dry,
                               label=pointer["label"], before=pointer.get("before", False))
    print("\nитог:", "записано" if not dry else "сухой прогон",
          "| расхождений нет" if ok else "| есть отказы — см. строки ОТКАЗ выше")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
