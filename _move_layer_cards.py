"""Перенос прежних карточек слоя в дерево правил и разбор состояний (шаг 26.10.2026).

Зачем отдельный шаг. В базе лежат два поколения карточек слоя: новое (`rules:kb-rules:<правило>`) и
прежнее (`kb-rules:<состояние>:<правило>`). Прежнее читалось состоянием адреса — `always`,
`optional`, `checks`, `journal`, `reserved`; новое читается местом в дереве, а состояние остаётся
тегом. Пока оба поколения живут под разными адресами, слой отвечает на вопрос «какие правила есть»
дважды и по-разному.

Что делает шаг (порядок значим: ссылки переписываются после переноса, иначе перенесённая карточка
останется со ссылками на прежний адрес).

1. Функциональные карточки уровня 3 возвращаются в работу и помечаются тегом `functional`: опция
   слоя — это не карточка инструмента, и отличать её нужно текстом тега, а не молчанием.
2. `journal` и `checks` переезжают под карточку второго уровня (`rules:kb-rules:journal:*`,
   `rules:kb-rules:checks:*`) и остаются отдельными сущностями дерева: `RESERVED_SEGMENTS` в
   `src/rules_layer.py` называет их не-правилами, поэтому в перечни правил слоя они не кладутся,
   а отчёт показывает их отдельными разделами в конце.
3. `always` переезжает под карточку второго уровня и получает тег `functional`: правило состояния
   `always` остаётся правилом «до любого действия», но карточкой инструмента оно не становится.
4. `optional` разбирается по содержанию каждой карточки (текст читается целиком, а не имя): что
   дублирует общий инструмент или уже живую карточку слоя — снимается, что является функциональной
   опцией — переезжает в `rules:kb-rules:functional:*` с тегом `functional`.
5. Индекс прежнего слоя и семейство `reserved` снимаются: индекс живёт в перечне карточки второго
   уровня, позиция `reserved` ведётся в корневом слое (`rules:reserved:layer-migration`).

Ключи и границы. Перенос = правка той же строки (`update_snippet` с `reason`, прежний текст уходит
в `snippet_audit_log`), а не создание второй строки; `source_url` следует за адресом, потому что он и
есть ключ идемпотентности загрузки слоя (замер 24.10.2026: оставленный ключ прежнего адреса позволил
следующей загрузке перезаписать карточку по чужому ключу). Прежний адрес остаётся алиасом строки —
ссылка из прежнего разговора не должна вести в никуда. Алиасы уровней (`rules:`,
`rules:kb-rules:`) добавляются обязательно: `by_alias` в `src/rules_report.py` отдаёт поддерево
только тем карточкам, которые объявили алиас уровня.

Ссылки переписываются по карте: перенесённый адрес ведёт на новый, снятый — на карточку, которая
теперь отвечает на тот же вопрос. Текст правила при этом не пересказывается: меняется указатель, а не
знание. Снимок журнала остаётся снимком — правка адреса не меняет его содержания.

Удаление — мягкое (`mark_snippet_for_deletion`, причина вторым тегом): физически строку снимает
`tools/purge_marked_snippets.py` отдельным разбором.

Запуск:
    python _move_layer_cards.py --dry-run    # разбор, в БД не пишет
    python _move_layer_cards.py              # применяет
    python _move_layer_cards.py --refs-only  # только переписать ссылки
"""

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
for _p in (ROOT_DIR / "src", ROOT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import rules_layer as RL  # noqa: E402
import _make_rule_cards as MC  # noqa: E402
from database import get_cursor  # noqa: E402
from mcp_tools_api import (mark_snippet_for_deletion, unmark_snippet_for_deletion,  # noqa: E402
                           update_snippet)
from quarantine import MARK_ARRAY, is_marked, sql_not_marked  # noqa: E402

LAYER = MC.LAYER
LAYER_ADDRESS = MC.LAYER_ADDRESS
STEP = "узел RULE-FUNCTIONAL (26.10.2026)"


# п.1 — функциональные опции слоя: карточка не привязана к одному инструменту, поэтому она и не
# карточка инструмента. Теги: `functional` вместо `optional`, адрес остаётся (его не перекладывали).
FUNCTIONAL_CARDS = ["write-knowledge", "quarantine", "loading", "state", "rules-work"]

# п.2, п.3 — переезжают целиком, поддерево за поддеревом. `always` дополнительно получает тег
# `functional`: состояние говорит «когда читать», вид карточки — чем она является.
MOVE_FAMILIES = {
    "journal": ["journal"],
    "checks": ["checks"],
    "always": ["always", "functional"],
}
# п.4 — переезжают поодиночке, имя состояния заменяется на `functional`.
MOVE_SINGLE = {
    "optional:alias-coverage": ("functional:alias-coverage", ["functional"]),
    "optional:knowledge-layer": ("functional:knowledge-layer", ["functional"]),
}
# п.4 — снимаются: карточка повторяет то, что в дереве уже есть (общий инструмент или живую
# карточку слоя). Причина удаления называется той же строкой, что и сама пометка.
DROP_SINGLE = {
    "optional:index": ("индекс состояния `optional` дублирует `===LINKS`/`===INDEX` карточки "
                       f"второго уровня {LAYER_ADDRESS}, которые собираются из её детей"),
    "optional:search-ranking": ("правила ранжирования общего `search_docs_tool`; живым остаётся "
                                f"общий контракт поиска в {LAYER_ADDRESS} и always:search-first"),
    "optional:quarantine": (f"дублирует живую карточку {LAYER_ADDRESS}quarantine и карточки "
                            "инструментов карантинного контура"),
    "optional:loading": (f"дублирует живую карточку {LAYER_ADDRESS}loading и карточки инструментов "
                         "load-doc / load-single-html / load-bsl"),
    "optional:counters": (f"дублирует живую карточку {LAYER_ADDRESS}state и карточки инструментов "
                          "get-db-state / list-categories"),
}
# п.5 — снимаются по прямой команде разбора.
DROP_INDEX = {
    "index": f"индекс прежнего слоя дублирует перечень карточки второго уровня {LAYER_ADDRESS}",
    "reserved:index": ("состояние `reserved` слоя закрыто: позиция ведётся в корневом слое "
                       "rules:reserved:layer-migration"),
    "reserved:rules-file": ("позиция файла правил ведётся в корневом слое rules:reserved:layer-"
                            "migration — текст самой карточки об этом и говорит"),
    "reserved:journal-to-rule": ("требование к формату переноса живёт в rules:always:authoring; "
                                "снимок журнала правится как снимок, а не как правило"),
}

# Карта переписывания ссылок: снятая карточка не может остаться указателем в никуда, поэтому для неё
# называется адрес, который теперь отвечает на тот же вопрос.
DROP_TARGET = {
    "index": LAYER_ADDRESS,
    "optional:index": LAYER_ADDRESS,
    "optional:search-ranking": f"{LAYER_ADDRESS}always:search-first",
    "optional:quarantine": f"{LAYER_ADDRESS}quarantine",
    "optional:loading": f"{LAYER_ADDRESS}loading",
    "optional:counters": f"{LAYER_ADDRESS}state",
    "reserved:index": "rules:reserved:layer-migration",
    "reserved:rules-file": "rules:reserved:layer-migration",
    "reserved:journal-to-rule": "rules:always:authoring",
}


def old_of(rest):
    return f"{LAYER}:{rest}"


def new_of(rest):
    return f"{LAYER_ADDRESS}{rest}"


def moved_tags(kinds):
    """Теги перенесённой карточки: та же грамматика дерева, что у `rule_tags` генератора.

    Категории двух слоёв (корня и своего) нужны затем, что карточку читают и фильтром корня, и
    фильтром своего сервера; `tree-rule` отделяет лист дерева от карточек-узлов. Вид (`functional`)
    и состояние (`always`, `journal`, `checks`) остаются тегами: адрес дерева их больше не несёт.
    """
    return list(dict.fromkeys(
        list(RL.categories_of(RL.ROOT_MARKER)) + list(RL.categories_of(LAYER))
        + ["rules", "rules-layer", "tree-rule"] + list(kinds)))


def functional_tags(current):
    """Заменить `optional` на `functional`, прочие теги не трогать (карантин снимается операцией)."""
    tags = [t for t in (current or []) if t != "optional"]
    if "functional" not in tags:
        tags.append("functional")
    return tags


def rows_by_prefix(cur, prefix):
    """Строки прежнего слоя под поддеревом `kb-rules:<prefix>:` — живые и помеченные.

    Помеченные строки переносятся наравне с живыми: снять пометку и перенести — две разные операции,
    и отказ переносить помеченную карточку оставил бы её висящей на прежнем адресе навсегда.
    """
    cur.execute(
        "SELECT id, question, answer, tags FROM knowledge_snippets "
        "WHERE question LIKE %s AND source_url LIKE %s ORDER BY question",
        (old_of(prefix) + ":%", RL.SOURCE_SCHEME + "%"),
    )
    return [dict(row) for row in cur.fetchall()]

def row_by_address(cur, address):
    """Одна строка дерева по адресу и его ключу; None — если строки нет."""
    cur.execute("SELECT id, question, answer, tags FROM knowledge_snippets "
                "WHERE question = %s AND source_url = %s", (address, RL.source_url(address)))
    row = cur.fetchone()
    return dict(row) if row else None




# ------------------------------------------------------------------ операции
def restore_functional(cur, dry=False):
    """п.1 — вернуть функциональные карточки и назвать их функциональными тегами."""
    for leaf in FUNCTIONAL_CARDS:
        row = row_by_address(cur, f"{LAYER_ADDRESS}{leaf}")
        if not row:
            print(f"• {LAYER_ADDRESS}{leaf} — в базе нет, возвращать нечего")
            continue
        marked = is_marked(row["tags"])
        already = (not marked) and ("functional" in (row["tags"] or []))
        if already:
            print(f"• {LAYER_ADDRESS}{leaf} id={row['id']} — уже в работе, тег `functional` стоит")
            continue
        if dry:
            print(f"• {LAYER_ADDRESS}{leaf} id={row['id']} — была бы снята пометка"
                  + ("" if marked else " (пометки нет)") + ", теги были бы переложены")
            continue
        if marked:
            res = unmark_snippet_for_deletion(row["id"])
            if not res.get("success"):
                print(f"❌ {LAYER_ADDRESS}{leaf}: не снята пометка — {res.get('error')}")
                continue
        res = update_snippet(row["id"], tags=functional_tags(row["tags"]),
                            reason=f"{STEP}: функциональная опция слоя остаётся вариативной, "
                                   "её вид называется тегом `functional`")
        print(f"✅ {LAYER_ADDRESS}{leaf} id={row['id']} — "
              + ("пометка снята, " if marked else "")
              + ("тег `functional`" if res.get("success") else f"ОТКАЗ: {res.get('error')}"))


def move_row(cur, row, new_address, kinds, dry=False):
    """Переезд одной карточки: тот же id, новый адрес, новый ключ, прежний адрес — алиасом."""
    old_address = row["question"]
    problems = RL.validate_address(new_address, RL.ROOT_MARKER)
    if problems:
        print(f"❌ {old_address} -> {new_address}: адрес не проходит проверку: "
              + "; ".join(problems))
        return False
    cur.execute("SELECT id FROM knowledge_snippets WHERE question = %s AND id <> %s",
                (new_address, row["id"]))
    clash = cur.fetchone()
    if clash:
        print(f"❌ {old_address} -> {new_address}: адрес занят строкой id={clash['id']}")
        return False
    if dry:
        print(f"• {old_address} -> {new_address} (теги {moved_tags(kinds)})")
        return True
    res = update_snippet(row["id"], new_question=new_address, tags=moved_tags(kinds),
                        aliases=MC.rule_aliases(new_address[len(LAYER_ADDRESS):]),
                        reason=f"{STEP}: карточка присоединена к карточке второго уровня")
    if not res.get("success"):
        print(f"❌ {old_address}: отказ записи — {res.get('error')}")
        return False
    # Ключ идемпотентности обязан следовать за адресом: оставленный ключ прежнего адреса позволяет
    # следующей загрузке слоя найти строку по чужому ключу и перезаписать её.
    cur.execute("UPDATE knowledge_snippets SET source_url = %s WHERE id = %s",
                (RL.source_url(new_address), row["id"]))
    # Коммит немедленный: `update_snippet` работает другим соединением того же пула, и незакрытая
    # здесь транзакция заблокировала бы следующую правку той же строки (замер 26.10.2026: прогон
    # встал на UPDATE source_url id=6084 и ждёт, пока его отпустит тот же скрипт).
    cur.connection.commit()
    if is_marked(row["tags"]):
        unmark_snippet_for_deletion(row["id"])
    print(f"✅ переехала: {old_address} -> {new_address}")
    return True


def move_families(cur, dry=False):
    """п.2 и п.3 — перенести поддеревья состояний под карточку второго уровня."""
    moved = 0
    for family, kinds in MOVE_FAMILIES.items():
        rows = rows_by_prefix(cur, family)
        if not rows:
            print(f"• `{LAYER}:{family}:*` — карточек нет, переносить нечего")
            continue
        print(f"переезжает `{LAYER}:{family}:*`: {len(rows)} карточек")
        for row in rows:
            rest = row["question"][len(LAYER) + 1:]
            if move_row(cur, row, new_of(rest), kinds, dry):
                moved += 1
    for rest, (new_rest, kinds) in MOVE_SINGLE.items():
        row = row_by_address(cur, old_of(rest))
        if not row:
            print(f"• {old_of(rest)} — карточки нет (уже перенесена или снята)")
            continue
        if move_row(cur, row, new_of(new_rest), kinds, dry):
            moved += 1
    return moved


def settle_moved(cur, dry=False):
    """Снять пометку с перенесённых карточек: переезд не означает снятия.

    Отдельный проход нужен затем, что перенесённая строка на новом адресе больше не попадает в
    выборку прежнего слоя, и пропущенная пометка (оборванный прогон 26.10.2026 оставил её на
    `always:edit-in-db`) осталась бы на живой карточце навсегда: читающие поверхности её не отдают,
    а перенос её уже не касается.
    """
    settled = 0
    for family in MOVE_FAMILIES:
        cur.execute("SELECT id, question, tags FROM knowledge_snippets "
                    "WHERE question LIKE %s AND source_url LIKE %s ORDER BY question",
                    (f"{LAYER_ADDRESS}{family}:%", RL.SOURCE_SCHEME + "%"))
        for row in (dict(r) for r in cur.fetchall()):
            if not is_marked(row["tags"]):
                continue
            if dry:
                print(f"• {row['question']} id={row['id']} — с неё был бы снят карантин")
                continue
            res = unmark_snippet_for_deletion(row["id"])
            if res.get("success"):
                print(f"✅ {row['question']} id={row['id']} — пометка снята")
                settled += 1
            else:
                print(f"❌ {row['question']}: {res.get('error')}")
    return settled


def drop_rows(cur, dry=False):
    """п.4 (дубли) и п.5 (индекс, reserved) — мягкое снятие с указанием причины."""
    dropped = 0
    for table in (DROP_SINGLE, DROP_INDEX):
        for rest, reason in table.items():
            row = row_by_address(cur, old_of(rest))
            if not row:
                print(f"• {old_of(rest)} — карточки нет (уже снята)")
                continue
            if is_marked(row["tags"]):
                print(f"• {old_of(rest)} id={row['id']} — уже помечена")
                continue
            if dry:
                print(f"• {old_of(rest)} id={row['id']} — была бы снята: {reason}")
                continue
            res = mark_snippet_for_deletion(row["id"], f"{STEP}: {reason}")
            if res.get("success"):
                print(f"✅ снята: {old_of(rest)} id={row['id']} — {reason}")
                dropped += 1
            else:
                print(f"❌ {old_of(rest)}: {res.get('error')}")
    return dropped


# ------------------------------------------------------------------ ссылки
def reference_map(cur=None):
    """Прежний адрес -> что теперь отвечает на тот же вопрос (переезд или живая карточка).

    Ключи семейства выводятся и по перенесённым строкам, а не только задаются списком состояний:
    ссылка вида `kb-rules:journal:ref:06` ведёт конкретную карточку, а не состояние, и без её ключа
    перенос оставил бы битыми ссылки внутри индексов журнала и проверок (замер 26.10.2026: карта
    знала только префикс `kb-rules:journal`, и проверка называла ссылки целыми, хотя их не было).
    """
    mapping = {}
    for family in MOVE_FAMILIES:
        mapping[f"{LAYER}:{family}"] = f"{LAYER_ADDRESS}{family}"      # упоминание префикса состояния
        if cur is None:
            continue
        cur.execute("SELECT question FROM knowledge_snippets WHERE question LIKE %s "
                    "AND source_url LIKE %s",
                    (f"{LAYER_ADDRESS}{family}:%", RL.SOURCE_SCHEME + "%"))
        for row in cur.fetchall():
            # Обратный ход переноса: прежний адрес — тот же путь без префикса корня.
            mapping[row["question"][len(RL.ROOT_MARKER) + 1:]] = row["question"]
    for rest, (new_rest, _kinds) in MOVE_SINGLE.items():
        mapping[old_of(rest)] = new_of(new_rest)
    for rest in DROP_TARGET:
        mapping[old_of(rest)] = DROP_TARGET[rest]
    return mapping


def references_pattern(keys):
    """Один проход по тексту: длинное имя выбирается раньше короткого, граница обязательна.

    Границы нужны затем, что `kb-rules:journal:ref:06` — начало `kb-rules:journal:ref:06:2`, а
    `rules:kb-rules:<правило>` содержит подстроку прежнего адреса: без проверки соседних символов
    замена читала бы адрес дерева ссылкой на прежнее поколение (замер 26.10.2026 — 66 «ссылок»
    вместо фактических).
    """
    ordered = sorted(keys, key=len, reverse=True)
    return re.compile(r"(?<![\w:.-])(" + "|".join(re.escape(k) for k in ordered) + r")(?![:\w-])")


def rewrite_references(cur, dry=False):
    """Переписать ссылки на прежние адреса во всех живых карточках дерева.

    Правится указатель, а не знание: текст правила остаётся прежним, меняется только адрес, на
    который он ссылается. Помеченные строки не правятся — читающая поверхность их не отдаёт, и
    правка скрытой строки создала бы иллюзию разобранного карантина.
    """
    mapping = reference_map(cur)
    pattern = references_pattern(mapping)
    cur.execute("SELECT id, question, answer FROM knowledge_snippets "
                "WHERE 'rules-layer' = ANY(tags)" + sql_not_marked() + " ORDER BY question",
                (MARK_ARRAY,))
    rows = [dict(row) for row in cur.fetchall()]
    touched = 0
    for row in rows:
        answer = row["answer"] or ""
        hits = len(pattern.findall(answer))
        if not hits:
            continue
        new_answer = pattern.sub(lambda m: mapping[m.group(1)], answer)
        if new_answer == answer:
            continue
        if dry:
            print(f"• {row['question']} — ссылок к замене: {hits}")
            continue
        cur.execute("UPDATE knowledge_snippets SET answer = %s, updated_at = NOW() WHERE id = %s",
                    (new_answer, row["id"]))
        cur.connection.commit()   # того же класса блокировка, что и с source_url: права держим
        print(f"✅ {row['question']} — ссылок переписано: {hits}")
        touched += 1
    return touched, len(rows)


# ------------------------------------------------------------------ ключи
def sync_source_keys(cur, dry=False):
    """Вернуть `source_url` в соответствие адресу.

    Ключ идемпотентности карточки — адрес (`rules-layer://<адрес>`). Он отстаёт от адреса, если
    правка адреса и правка ключа не попали в одну транзакцию: прерванный прогон оставляет строку с
    новым адресом и прежним ключом, и следующая загрузка слоя находит её по чужому ключу (тот же
    класс дефекта описан в `tools/readdress_rules_layer.py`). Операция идемпотентна: совпадающий
    ключ не меняется.
    """
    cur.execute("SELECT id, question FROM knowledge_snippets "
                "WHERE source_url LIKE %s AND source_url <> %s || question ORDER BY question",
                (RL.SOURCE_SCHEME + "%", RL.SOURCE_SCHEME))
    rows = [dict(row) for row in cur.fetchall()]
    for row in rows:
        if dry:
            print(f"• id={row['id']} {row['question']} — ключ был бы перечитан")
            continue
        cur.execute("UPDATE knowledge_snippets SET source_url = %s WHERE id = %s",
                    (RL.source_url(row["question"]), row["id"]))
        cur.connection.commit()
        print(f"✅ id={row['id']} {row['question']} — ключ перечитан по адресу")
    return len(rows)


# ------------------------------------------------------------------ находимость
def tree_level_aliases(address):
    """Алиасы уровней, которые обязана носить карточка дерева.

    Узел RULE-TREE: `by_alias` в `src/rules_report.py` отдаёт поддерево только тем карточкам, которые
    объявили алиас уровня. Без алиаса корня карточка перестаёт быть частью дампа корня молча —
    «восьми карточек нет» читается как «восьми правил нет».
    """
    parts = [p for p in address.split(":") if p]
    aliases = [f"{RL.ROOT_MARKER}:"]
    for depth in range(1, len(parts)):
        aliases.append(":".join(parts[:depth]) + ":")
    # Порядок сохраняется, повторы снимаются: алиас корня уже лежит первым элементом для карточки
    # второго уровня, и повтор в перечне читался бы как две разные требуемые записи (замер
    # 26.10.2026: `rules:always:index` требовал `rules:` дважды).
    return list(dict.fromkeys(aliases))


def ensure_tree_aliases(cur, dry=False):
    """Довесить алиасы уровней всем живым карточкам дерева; существующий алиас не дублируется."""
    cur.execute("SELECT id, question, tags FROM knowledge_snippets "
                "WHERE question LIKE %s AND source_url LIKE %s" + sql_not_marked(),
                (f"{RL.ROOT_MARKER}:%", RL.SOURCE_SCHEME + "%", MARK_ARRAY))
    rows = [dict(row) for row in cur.fetchall()]
    repaired = 0
    for row in rows:
        cur.execute("SELECT alias_name FROM alias_targets WHERE snippets_id = %s", (row["id"],))
        have = {a["alias_name"] for a in cur.fetchall()}
        need = [a for a in tree_level_aliases(row["question"]) if a not in have]
        if not need:
            continue
        if dry:
            print(f"• {row['question']} id={row['id']} — недостающие алиасы: {need}")
            continue
        MC.ensure_aliases(cur, row["id"], need, list(row["tags"]) or [])
        cur.connection.commit()
        print(f"✅ {row['question']} id={row['id']} — алиасы уровня: {need}")
        repaired += 1
    return repaired


# ------------------------------------------------------------------ точка входа
def main():
    parser = argparse.ArgumentParser(
        description="Перенос прежних карточек слоя в дерево правил (шаг 26.10.2026)")
    parser.add_argument("--dry-run", action="store_true", help="разбор, в БД не пишет")
    parser.add_argument("--refs-only", action="store_true", help="только переписать ссылки")
    args = parser.parse_args()

    with get_cursor() as cur:
        if not args.refs_only:
            print("— п.1: функциональные карточки")
            restore_functional(cur, dry=args.dry_run)
            print("— п.2, п.3: перенос поддеревьев journal / checks / always и опций alias-coverage, "
                  "knowledge-layer")
            moved = move_families(cur, dry=args.dry_run)
            print("— п.4 (дубли), п.5: снятие индекса состояния, индекса слоя и reserved")
            dropped = drop_rows(cur, dry=args.dry_run)
            print(f"\nперенесено: {moved}, снято: {dropped}")
            print("— перенесённые карточки остаются живыми (последствие оборванного прогона)")
            settled = settle_moved(cur, dry=args.dry_run)
            print(f"карантинов снято: {settled}")
            print("— ключи source_url по адресам (последствие прерванного прогона)")
            synced = sync_source_keys(cur, dry=args.dry_run)
            print(f"ключей перечитано: {synced}")
            print("— алиасы уровней у карточек дерева (иначе дамп корня их не отдаёт)")
            aliased = ensure_tree_aliases(cur, dry=args.dry_run)
            print(f"карточкам дописаны алиасы: {aliased}")
        print("— ссылки на прежние адреса")
        touched, scanned = rewrite_references(cur, dry=args.dry_run)
        print(f"карточек просмотрено: {scanned}, ссылок переписано в карточках: {touched}")
    if args.dry_run:
        print("в БД не писали — нужен обычный прогон")
    return 0


if __name__ == "__main__":
    sys.exit(main())



def row_by_address(cur, address):
    cur.execute("SELECT id, question, answer, tags FROM knowledge_snippets "
                "WHERE question = %s AND source_url = %s", (address, RL.source_url(address)))
    row = cur.fetchone()
    return dict(row) if row else None

from quarantine import MARK_ARRAY, is_marked, sql_not_marked  # noqa: E402

LAYER = MC.LAYER
LAYER_ADDRESS = MC.LAYER_ADDRESS
STEP = "узел RULE-FUNCTIONAL (26.10.2026)"
