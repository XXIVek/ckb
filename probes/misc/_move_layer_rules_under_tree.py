"""Перенос прежних карточек слоёев core/enrich/export в дерево `rules:<слой>:` (узел RESTRUCTURE-LAYERS).

Зачем. Слой отвечает на вопрос «какие правила есть» дважды, если у него два адресных пространства:
карточка второго уровня `rules:core-rules:` уже есть, а её правила лежат под прежней меткой
`core-rules:…`. Прежние адреса не проходят и грамматику дерева (`core-rules: п. 22 ч. 1` — пробелы и
точки), поэтому их нельзя ни прочитать префиксным запросом, ни назвать ссылкой: `rules_read.py
--tree "rules:core-rules:"` отдал бы одну карточку слоя, а дамп — «правил нет».

Куда что переезжает (тот же разбор, что сделан узлом RULE-FUNCTIONAL для `kb-rules`):

    <метка>:index              -> rules:<метка>:journal:index
    <метка>:ref:NN[:K]         -> rules:<метка>:journal:ref:NN[:K]
    <метка>: п. NN[ ч. K]      -> rules:<метка>:journal:pos:NN[:K]
    <метка>: п. NN (дополнение -> rules:<метка>:journal:pos:NN:add<ддмм>
             д.м.г.)
    <метка>: узел VNN[ ч. K]   -> rules:<метка>:journal:node:vNN[:K]
    <метка>: узел VNN (дополнение д.м.г.) -> …:journal:node:vNN:add<ддмм>
    export-rules:checks        -> rules:export-rules:checks:index
    export-rules:<правило>     -> rules:export-rules:functional:<правило>

Журнал — снимок, а не правило: `node_kind` относит ветки `journal` и `checks` к отдельным сущностям
дерева, поэтому в перечни правил слоя они не кладутся. Правила `export-rules` — единственные,
которые переезжают в `functional:`: это действующие правила, а не снимок, и писать их заново —
значит завести второй текст того же правила.

Со строкой ничего не создаётся заново: правится та же запись (`update_snippet` — прежний текст уходит
в `snippet_audit_log`), `source_url` следует за адресом, потому что он и есть ключ идемпотентности
загрузки слоя, прежний адрес остаётся алиасом той же строки, а алиасы каждого уровня обязательны —
`by_alias` в `src/rules_report.py` отдаёт поддерево только объявившим их карточкам. Пометка карантина
и тег причины сохраняются: перенос — не снятие.

Ссылки переписываются после переноса по карте «прежний адрес -> новый»: ссылка на прежний адрес в
живом тексте читается как «правил нет». Раздел `===SOURCE===` не правится — там адрес, из которого
текст брали в тот день, это история.

Ничего не выдумывается: адрес, не попавший ни под одно правило карты, называется в отчёте и не
переносится (молча придумать ему новый адрес — значит потерять связь с исходником).

Запуск:
    python _move_layer_rules_under_tree.py --dry-run    # карта переноса, в БД не пишет
    python _move_layer_rules_under_tree.py              # применяет
    python _move_layer_rules_under_tree.py --refs-only  # только переписать ссылки
    python _move_layer_rules_under_tree.py --index-only # только индексы журнала слоёв
"""
import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
for _p in (ROOT_DIR / "src", ROOT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402
from mcp_tools_api import mark_snippet_for_deletion, update_snippet  # noqa: E402
from quarantine import MARK_ARRAY, is_marked, sql_not_marked  # noqa: E402

STEP = "узел RESTRUCTURE-LAYERS (27.10.2026)"
MARKERS = ("core-rules", "enrich-rules", "export-rules")

# Действующие правила слоя export-rules переезжают в `functional:`, а не в журнал: это действующие
# правила. Имена листьев сохраняются — ссылка вида `export-rules:status` ведёт на то же правило.
FUNCTIONAL_LEAVES = {
    "export-rules": ("status", "contract", "removed", "needs", "workflow", "edit"),
}

POS_RE = re.compile(r"^ п\. (?P<num>\d+)(?: ч\. (?P<part>\d+))?$")
POS_ADD_RE = re.compile(r"^ п\. (?P<num>\d+) \(дополнение (?P<day>\d+)\.(?P<month>\d+)\.\d{4}\)$")
NODE_RE = re.compile(r"^ узел V(?P<num>\d+)(?: ч\. (?P<part>\d+))?$")
NODE_ADD_RE = re.compile(r"^ узел V(?P<num>\d+) \(дополнение (?P<day>\d+)\.(?P<month>\d+)\.\d{4}\)$")
REF_RE = re.compile(r"^ref:(?P<tail>[0-9]+(?::[0-9]+)?)$")


def layer_prefix(marker):
    return f"{RL.ROOT_MARKER}:{marker}:"


def short_of(marker, leaf):
    """Прежняя форма адреса — она остаётся алиасом, а не новым адресом."""
    return f"{marker}:{leaf}"


def new_address_of(marker, question):
    """Новый адрес карточки или None, если правило карты её не описывает."""
    if not question.startswith(marker + ":"):
        return None
    leaf = question[len(marker) + 1:]
    prefix = layer_prefix(marker)
    if leaf == "index":
        return f"{prefix}{RL.STATE_JOURNAL}:index"
    if leaf == "checks":
        return f"{prefix}{RL.STATE_CHECKS}:index"
    if leaf in FUNCTIONAL_LEAVES.get(marker, ()):
        return f"{prefix}functional:{leaf}"
    match = REF_RE.match(leaf)
    if match:
        return f"{prefix}{RL.STATE_JOURNAL}:ref:{match.group('tail')}"
    match = POS_ADD_RE.match(leaf)
    if match:
        return (f"{prefix}{RL.STATE_JOURNAL}:pos:{match.group('num')}"
                f":add{match.group('day')}{match.group('month')}")
    match = POS_RE.match(leaf)
    if match:
        tail = match.group("num")
        if match.group("part"):
            tail += f":{match.group('part')}"
        return f"{prefix}{RL.STATE_JOURNAL}:pos:{tail}"
    match = NODE_ADD_RE.match(leaf)
    if match:
        return (f"{prefix}{RL.STATE_JOURNAL}:node:v{match.group('num')}"
                f":add{match.group('day')}{match.group('month')}")
    match = NODE_RE.match(leaf)
    if match:
        tail = f"v{match.group('num')}"
        if match.group("part"):
            tail += f":{match.group('part')}"
        return f"{prefix}{RL.STATE_JOURNAL}:node:{tail}"
    return None


def level_aliases(address):
    """Алиасы каждого уровня адреса: `rules:`, `rules:core-rules:`, `rules:core-rules:journal:`."""
    parts = (address or "").split(":")
    return [":".join(parts[:i]) + ":" for i in range(1, len(parts)) if any(parts[:i])]


def aliases_for(marker, new_address):
    """Алиасы перенесённой строки: новый адрес, прежний адрес, алиасы уровней, метка слоя."""
    leaf = new_address[len(layer_prefix(marker)):]
    short = short_of(marker, leaf)
    return list(dict.fromkeys(
        [new_address, short] + level_aliases(new_address) + level_aliases(short) + [marker]))


def tags_for_move(marker, old_tags, new_address):
    """Теги по новому адресу; пометка карантина и тег причины — сохраняются."""
    tags = RL.tags_for(new_address, marker)
    for tag in old_tags or []:
        if tag.startswith("mark-for-deletion") or tag == "functional":
            tags.append(tag)
    return list(dict.fromkeys(tags))


def rows_of_layer(cur, marker):
    """Все строки прежнего слоя — любого `source_url`, живые и помеченные."""
    cur.execute(
        "SELECT id, question, answer, tags, source_url FROM knowledge_snippets "
        "WHERE question LIKE %s ORDER BY question", (marker + ":%",))
    return [dict(row) for row in cur.fetchall()]


def build_map(cur):
    """Карта переноса: прежний адрес -> новый. Неразмеченные адреса и коллизии — отдельными списками.

    Карта строится по всем трём слоям сразу: ссылка вида `core-rules:ref:07` встречается в карточках
    другого слоя, и переписывать её надо по единой карте, а не по карте слоя.
    """
    mapping, unmapped, clashes = {}, [], []
    seen = {}
    for marker in MARKERS:
        for row in rows_of_layer(cur, marker):
            new = new_address_of(marker, row["question"])
            if not new:
                unmapped.append((marker, row["id"], row["question"]))
                continue
            if new in seen:
                clashes.append((seen[new], new, row["question"]))
                continue
            seen[new] = row["question"]
            mapping[row["question"]] = new
    return mapping, unmapped, clashes


def move_rows(cur, mapping, dry=False):
    """Переезд строк: тот же id, новый адрес и новый ключ, прежний адрес — алиасом."""
    moved = failed = 0
    for old_address, new_address in sorted(mapping.items()):
        marker = RL.marker_of(old_address)
        cur.execute("SELECT id, question, tags, source_url FROM knowledge_snippets "
                    "WHERE question = %s", (old_address,))
        row = cur.fetchone()
        if not row:
            print(f"• {old_address} — строки нет (уже перенесена)")
            continue
        problems = RL.validate_address(new_address, RL.ROOT_MARKER)
        if problems:
            print(f"❌ {old_address} -> {new_address}: {'; '.join(problems)}")
            failed += 1
            continue
        cur.execute("SELECT id FROM knowledge_snippets WHERE question = %s AND id <> %s",
                    (new_address, row["id"]))
        clash = cur.fetchone()
        if clash:
            print(f"❌ {old_address} -> {new_address}: адрес занят строкой id={clash['id']}")
            failed += 1
            continue
        if dry:
            print(f"  • {old_address} -> {new_address}")
            moved += 1
            continue
        res = update_snippet(row["id"], new_question=new_address,
                             tags=tags_for_move(marker, row["tags"], new_address),
                             aliases=aliases_for(marker, new_address),
                             reason=f"{STEP}: прежний адрес слоя снят, карточка присоединена к "
                                    f"карточке второго уровня {layer_prefix(marker)}")
        if not res.get("success"):
            print(f"❌ {old_address}: отказ записи — {res.get('error')}")
            failed += 1
            continue
        cur.execute("UPDATE knowledge_snippets SET source_url = %s WHERE id = %s",
                    (RL.source_url(new_address), row["id"]))
        cur.connection.commit()      # update_snippet работает другим соединением того же пула
        moved += 1
        note = " (пометка карантина сохранена)" if is_marked(row["tags"]) else ""
        print(f"✅ переехала: {old_address} -> {new_address}{note}")
    return moved, failed


# ------------------------------------------------------------------ ссылки на прежние адреса

_SECTION_RE = re.compile(r"(?m)^===[ \t]*([A-ZА-Я][A-ZА-Я_]*)")


def _section_spans(answer):
    marks = [(m.group(1), m.start()) for m in _SECTION_RE.finditer(answer or "")]
    return [(name, start, marks[i + 1][1] if i + 1 < len(marks) else len(answer or ""))
            for i, (name, start) in enumerate(marks)]


def references_pattern(mapping):
    """Регэксп живых ссылок на прежние адреса (длинные сначала — иначе `ref:02` съест `ref:02:2`)."""
    if not mapping:
        return None
    order = sorted(mapping, key=len, reverse=True)
    return re.compile("(" + "|".join(re.escape(a) for a in order) + ")")


def sub_outside_source(answer, pattern, mapping):
    """Замена по всей карточке, кроме разделов SOURCE: там исторический адрес-источник."""
    hits = 0

    def repl(match):
        nonlocal hits
        hits += 1
        return mapping[match.group(1)]

    blocked = [(start, end) for name, start, end in _section_spans(answer)
               if name.upper() == "SOURCE"]
    parts = []
    pos = 0
    for start, end in blocked + [(len(answer), len(answer))]:
        part, count = pattern.subn(repl, answer[pos:start])
        hits += count
        parts.append(part)
        parts.append(answer[start:end])
        pos = end
    return "".join(parts), hits


def fix_references(cur, mapping, dry=False):
    """Переписать живые ссылки на прежние адреса во всех карточках правил, кроме их SOURCE."""
    pattern = references_pattern(mapping)
    if not pattern:
        return 0
    like = ["%" + old + "%" for old in mapping]
    cur.execute(
        "SELECT id, question, answer FROM knowledge_snippets WHERE source_url LIKE %s "
        "AND NOT (question = ANY(%s))" + sql_not_marked() + " AND ("
        + " OR ".join(["answer LIKE %s"] * len(like)) + ") ORDER BY question",
        (RL.SOURCE_SCHEME + "%", list(mapping), MARK_ARRAY, *like),
    )
    rows = [dict(row) for row in cur.fetchall()]
    total = 0
    for row in rows:
        rebuilt, hits = sub_outside_source(row["answer"], pattern, mapping)
        if not hits:
            print(f"• {row['question']} — прежний адрес назван только в SOURCE, ссылок не правим")
            continue
        total += hits
        if dry:
            print(f"  • {row['question']} — ссылок к правке: {hits}")
            continue
        cur.execute("UPDATE knowledge_snippets SET answer = %s, updated_at = NOW() WHERE id = %s",
                    (rebuilt, row["id"]))
        print(f"  • {row['question']} — заменено ссылок: {hits}")
    return total


# ------------------------------------------------------------------ индекс журнала слоя

JOURNAL_SOURCE = {
    "core-rules": ".clinerules/1c-configurations-core_Rule.md",
    "enrich-rules": ".clinerules/1c-configurations-enrichment_Rule.md",
    "export-rules": ".clinerules/1c-configurations-export_Rule.md",
}


def journal_index_table(cur, marker, dry=False):
    """Пересобрать индекс журнала слоя списком его карточек: снимок без перечня не найдёшь.

    Индекс журнала — перечисляющая карточка, а не правило: её содержание собирается из строк ветки,
    потому что список, заведённый словами, отстаёт от журнала на одну карточку и читается как
    утверждение о покрытии истории.
    """
    prefix = f"{layer_prefix(marker)}{RL.STATE_JOURNAL}:"
    cur.execute(
        "SELECT id, question, answer, source_url FROM knowledge_snippets "
        "WHERE question LIKE %s AND question <> %s ORDER BY question",
        (prefix + "%", prefix + "index"),
    )
    rows = [dict(row) for row in cur.fetchall()]
    cur.execute("SELECT id, tags FROM knowledge_snippets WHERE question = %s", (prefix + "index",))
    index_row = cur.fetchone()
    if not rows:
        # Пустой журнал слоя не бывает «индексом»: карточка прежнего оглавления остаётся
        # единственной строкой ветки и повторяет перечень карточки второго уровня. Её снимают
        # мягко (тот же разбор, что `DROP_INDEX` в `_move_layer_cards.py` для `kb-rules`).
        if index_row and not is_marked(index_row["tags"]):
            if dry:
                print(f"  • {prefix}index — других карточек журнала нет; индекс был бы снят")
                return 0
            res = mark_snippet_for_deletion(
                index_row["id"],
                reason=f"{STEP}: индекс прежнего слоя дублирует перечень карточки второго уровня "
                       f"{layer_prefix(marker)}, карточек снимка в слое нет")
            print(("✅ " if res.get("success") else "❌ ") + f"{prefix}index — "
                  + ("индекс снят: других карточек журнала нет" if res.get("success")
                     else f"отказ — {res.get('error')}"))
        else:
            print(f"• {prefix}index — карточек журнала нет, индекс не строим")
        return 0
    table = ["| адрес | исходник | что снимает |", "|---|---|---|"]
    for row in rows:
        source = (f"{RL.RULES_DIR}/{marker}.md"
                  if row["source_url"].startswith(RL.SOURCE_SCHEME)
                  else JOURNAL_SOURCE.get(marker, ""))
        first = next((line.strip(" #") for line in (row["answer"] or "").splitlines()
                      if line.strip() and not line.startswith("===")), "")
        table.append(f"| `{row['question']}` | {source} | {first[:90]} |")
    body = (
        "===WHEN\n"
        f"Индекс журнала слоя `{RL.category_of(marker)}` — снимок прежних текстов слоя и датированные "
        "позиции его журнала. Это не правила: они описывают состояние до шага RESTRUCTURE-LAYERS, "
        "действующим правилом не считаются и при загрузке правил не читаются. Нужен факт истории "
        "(почему решение принято, что было раньше) — читают адрес из таблицы ниже.\n\n"
        f"Сюда перенесены карточки с прежних адресов `{marker}:…` (прежний адрес остаётся алиасом "
        f"той же строки) и прежняя карточка-оглавление слоя. Действующие правила слоя — под адресом "
        f"`{layer_prefix(marker)}`, их перечень — в разделе `===LINKS` её карточки.\n\n"
        f"===SCOPE\n{len(rows)} карточек снимка.\n\n" + "\n".join(table))
    target = prefix + "index"
    if dry:
        print(f"• {target} — индекс журнала: {len(rows)} строк, {len(body)} симв.")
        return len(rows)
    cur.execute("UPDATE knowledge_snippets SET answer = %s, updated_at = NOW() WHERE id = %s",
                (body, index_row["id"]))
    print(f"✅ {target} — индекс журнала пересобран: {len(rows)} карточек")
    return len(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Перенос прежних карточек слоёев core/enrich/export в дерево правил")
    parser.add_argument("--dry-run", action="store_true", help="показать карту, в БД не пишет")
    parser.add_argument("--refs-only", action="store_true",
                        help="только переписать ссылки на уже перенесённые адреса")
    parser.add_argument("--index-only", action="store_true",
                        help="только пересобрать индексы журнала слоёв")
    args = parser.parse_args()

    with get_cursor() as cur:
        mapping, unmapped, clashes = build_map(cur)
        print(f"карта переноса: {len(mapping)} | не размечено: {len(unmapped)} | "
              f"коллизий: {len(clashes)}")
        for marker, snippet_id, question in unmapped:
            print(f"  ⚠️ не размечено: {question} (id={snippet_id}, слой {marker})")
        for old, new, question in clashes:
            print(f"  ❌ коллизия: {question} -> {new} (уже занято {old})")
        if clashes or unmapped:
            print("❌ карта неполная — в БД не пишем")
            return 1

        if args.index_only:
            for marker in MARKERS:
                journal_index_table(cur, marker, dry=args.dry_run)
            return 0
        if args.refs_only:
            hits = fix_references(cur, mapping, dry=args.dry_run)
            print(f"заменено ссылок: {hits}")
            return 0

        moved, failed = move_rows(cur, mapping, dry=args.dry_run)
        hits = 0
        if not args.dry_run:
            hits = fix_references(cur, mapping)
            for marker in MARKERS:
                journal_index_table(cur, marker)
        print(f"\nперенесено: {moved} | отказов: {failed} | ссылок переписано: {hits}"
              + ("" if args.dry_run else " | изменения записаны"))
        return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())



