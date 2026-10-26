"""Аудит живого поддерева `rules:kb-rules:` — содержание каждой карточки и её объём.

Зонд отвечает на два вопроса, и отвечает по источнику, а не по тексту:

1. «соответствует ли текст карточки фактам?» — по каждой живой карточке всех уровней проверяются:
   • разделы карточки (есть ли обязательные для её типа, не дублируются ли);
   • ссылки на адреса дерева — каждая обязана вести в живую карточку или в названное поддерево
     (ссылка в снятую или несуществующую карточку читается как «правила нет»);
   • имена инструментов — по живому регистру `server.py`; снятое имя допустимо ровно в том абзаце,
     где оно названо снятым;
   • коды категорий — по справочнику `doc_categories` (тег `rules` называется отдельно);
   • объявленные алиасы — против записанных в `alias_targets` и против границ `validate_alias`;
   • «карточка не названа ни в одном перечне слоя» — записанное и не названное правило перестаёт
     существовать для того, кто читает слой по указателю;
   • остатки прежней редакции (эмодзи, звёздочки курсива, `---`, капслок, «Шаг 0»), markdown-таблицы
     там, где перечнем правит генерируемый указатель;
   • даты в тексте — позже системной даты быть не может (правило ведения дат узлов, 25.10.2026).

2. «каков объём каждой карточки?» — длина answer против `MAX_ANSWER_CHARS`, резервные — против
   `RESERVED_MAX_CHARS`, суммарная always-часть — против `ALWAYS_BUDGET_CHARS`. Объёмы печатаются
   отдельным итогом и в код возврата не входят: превысить порог — решение оператора (делить карточку
   или пересматривать порог), а не скрытая ошибка.

Запуск:
    python _layer_audit.py                 # итог по поддереву, тексты в _layer_text.txt
    python _layer_audit.py --no-dump       # без выгрузки текстов

Код возврата: 0 — расхождений с фактами нет, 1 — есть.
"""
import re
import sys
import ast
import datetime
from collections import Counter
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
for _p in (ROOT_DIR / "src", ROOT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402
from quarantine import is_marked  # noqa: E402
import _make_rule_cards as MC  # noqa: E402

LAYER_ADDRESS = MC.LAYER_ADDRESS
PREFIX = "rules:kb-rules"
TODAY = datetime.date.today()

TOOL_RE = re.compile(r"\b([a-z][a-z0-9_]*_tool)\b")
REMOVED_OK = re.compile(r"сняты|снято|снятый|снял|снята|не введён|не вводился|не планируется|"
                       r"не является|не считаются|не называют|как живой инструмент|как снят|"
                       r"как история|removed|изменён")
BACKTICK_RE = re.compile(r"`([^`\n]{1,80})`")
CODE_TOKEN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DATE_RE = re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b")
# Остатки прежней редакции `.clinerules` и разметка, которой в карточках дерева правил нет:
# текст карточки читается моделью как проза, разметка в нём — шум, а не смысл.
LEGACY_MARKS = ("📚", "⚙️", "🔄", "📦", "🎯", "🔍", "\n---\n", "**", "ВСЕГДА", "Шаг 0")
ALLOWED_TAGS = {"rules"}
MARKERS = set(RL.markers()) | {RL.ROOT_MARKER}
DUMP = ROOT_DIR / "_layer_text.txt"
# Действующие правила выгружаются отдельно: их текст читается целиком, журнал — нет (28 карточек
# перенесённой истории читаются только по запросу о том, как было).
DUMP_RULES = ROOT_DIR / "_layer_rules.txt"
# Регистр инструментов берётся по всем серверам MCP: карточка слоя правил знает и про инструменты
# соседних серверов (`search_config_snippets_tool`), и называть их «вне регистра» — значит врать.
SERVERS = ("server.py", "server_configurations_core.py",
           "server_configurations_enrichment.py", "server_configurations_export.py")
# Слово, в чьём абзаце уместно называть код категории: без него в backticks попадают имена
# параметров (`category`, `path`, `reason`) и ключи аргументов команд — это не кандидаты в категории.
# Русская форма намеренна: правила слоя называют категорию словом «категория», а `category` в тексте
# — это имя параметра инструмента (замер 25.10.2026: 25 ложных срабатываний против одной настоящей).
CATEGORY_CONTEXT = re.compile(r"категор")
# Журнал — перенесённая история: её разметка и снятые имена инструментов в её тексте — доказательство
# того, что было, а не дефект. Переписанный, журнал перестаёт быть записью.
NARRATIVE_KINDS = (RL.KIND_JOURNAL,)


def full_registry():
    """Имена инструментов из декораторов `@mcp.tool()` всех серверов MCP."""
    names, params = set(), set()
    for name in SERVERS:
        path = ROOT_DIR / name
        if not path.exists():
            continue
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if not isinstance(node, ast.FunctionDef):
                continue
            if not any((dec.func if isinstance(dec, ast.Call) else dec) is not None
                       and getattr((dec.func if isinstance(dec, ast.Call) else dec), "attr", "")
                       == "tool" for dec in node.decorator_list):
                continue
            names.add(node.name)
            params.update(a.arg for a in list(node.args.args) + list(node.args.kwonlyargs))
    return names, params


def tag_words():
    """Слова, которые в базе уже являются тегами строк: `syntax`, `howto`, `mark-for-deletion`.
    В тексте правил они стоят в обратных кавычках как метки содержимого, и называть их кодами
    категорий — значит проверять догадку, а не факт."""
    with get_cursor() as cur:
        cur.execute("SELECT DISTINCT unnest(tags) AS t FROM knowledge_snippets")
        return {str(r["t"]).lower() for r in cur.fetchall() if r["t"]}


def project_files():
    """Имена файлов проекта — чем подтверждается правило, то обязано лежать на диске.

    Проверка идёт по имени, а не по пути: правила называют артефакты и с каталогом
    (`tools/check_rules_layer.py`), и без (`_p6_live_probe.py`), и ровно так же их ищут люди.
    """
    names = set()
    for path in ROOT_DIR.rglob("*"):
        parts = path.parts
        if not path.is_file() or ".git" in parts or "__pycache__" in parts:
            continue
        names.add(path.name.lower())
    return names



def read_state():
    """Живые карточки поддерева, справочники и карта адресов всей базы — одним проходом."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, question, answer, tags, source_url, "
            "(SELECT string_agg(a.alias_name, '|' ORDER BY a.alias_name) FROM alias_targets a "
            "WHERE a.snippets_id = knowledge_snippets.id) AS aliases "
            "FROM knowledge_snippets WHERE question LIKE %s AND source_url LIKE %s "
            "ORDER BY question",
            (PREFIX + "%", RL.SOURCE_SCHEME + "%"),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT question, COALESCE(tags::text, '') AS t FROM knowledge_snippets")
        known = {r["question"]: ("mark-for-deletion" in (r["t"] or "")) for r in cur.fetchall()}
        cur.execute("SELECT code FROM doc_categories ORDER BY code")
        categories = {str(r["code"]).lower() for r in cur.fetchall()}
    live = [r for r in rows if not is_marked(r["tags"])]
    segments = set()
    for address in known:
        segments.update(p for p in address.split(":") if p)
    print(f"строк поддерева: {len(rows)}; живых: {len(live)}; категорий: {len(categories)}")
    return dict(rows=rows, live=live, known=known, categories=categories, segments=segments)


def address_tokens(text):
    """Токены адресов дерева правил внутри текста карточки."""
    return [t for t in RL._ADDRESS_TOKEN_RE.findall(text or "")
            if t.split(":")[0] in MARKERS]


def kind_of(row):
    """Тип узла по месту в дереве — то же, что считает проверка слоя и отчёт."""
    return RL.node_kind(row["question"])


def audit(row, ctx):
    """Расхождения одной карточки с фактами. Пустой список — карточка соответствует."""
    address, answer = row["question"], row["answer"] or ""
    known, registry, categories, segments = (ctx["known"], ctx["registry"],
                                            ctx["categories"], ctx["segments"])
    problems, notes = [], []

    # 1. Разделы карточки.
    sections = RL.sections_of(answer)
    missing = [s for s in RL.required_sections(address) if s not in sections]
    if missing:
        problems.append("нет разделов: " + ", ".join("===" + s for s in missing))
    dup = sorted(s for s, n in Counter(sections).items() if n > 1)
    if dup:
        problems.append("раздел повторяется: " + ", ".join(dup))

    # 2. Ссылки на адреса: живая карточка, узел с детьми или названное поддерево.
    dead_links, old_links = [], []
    for token in set(address_tokens(answer)):
        target = token if token in known else (token + ":" if (token + ":") in known else None)
        if target is None:
            if not any(addr.startswith(token + ":") for addr in known):
                dead_links.append(token)
        elif known[target]:
            old_links.append(target)
    if dead_links:
        problems.append("ссылка в несуществующую карточку: " + ", ".join(sorted(dead_links)[:6]))
    if old_links:
        problems.append("ссылка на снятую карточку: " + ", ".join(sorted(old_links)[:6]))

    # 3. Имена инструментов: вне регистра — только названные снятыми (оценка по абзацам).
    ghost_tools = set()
    for paragraph in answer.split("\n\n"):
        for tool in TOOL_RE.findall(paragraph):
            if tool not in registry and not REMOVED_OK.search(paragraph):
                ghost_tools.add(tool)
    if ghost_tools:
        target = notes if kind_of(row) in NARRATIVE_KINDS else problems
        target.append("живым инструментом названо вне регистра всех серверов: "
                      + ", ".join(sorted(ghost_tools)))

    # 4. Коды категорий: только там, где о категории и правда говорится, и только в действующих
    #    правилах — в журнале обратные кавычки называют имена свойств конфигурации 1С, а не коды.
    claimed = set()
    if kind_of(row) not in NARRATIVE_KINDS:
        for paragraph in answer.split("\n\n"):
            if not CATEGORY_CONTEXT.search(paragraph):
                continue
            for chunk in BACKTICK_RE.findall(paragraph):
                for part in chunk.split(","):
                    part = part.strip()
                    # `LAYERS` — имя константы кода, а не код категории: регистр их и различает.
                    if part.isupper():
                        continue
                    part = part.lower()
                    if CODE_TOKEN.match(part) and not part.isdigit():
                        claimed.add(part)
    known_words = categories | ALLOWED_TAGS | segments | ctx["params"] | ctx["tags"]
    candidates = sorted(c for c in claimed if c not in known_words)
    if candidates:
        problems.append("код категории отсутствует в `doc_categories`: " + ", ".join(candidates))

    # 4b. Артефакты, названные правилом, обязаны лежать на диске: строка «чем проверяется»,
    #     ведущая в несуществующий файл, доказывает ровно ноль.
    missing_files = []
    if kind_of(row) not in NARRATIVE_KINDS:
        tokens = set(RL._PATH_TOKEN_RE.findall(answer)) | set(RL._BARE_PATH_TOKEN_RE.findall(answer))
        for token in tokens:
            name = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
            if name not in ctx["files"]:
                missing_files.append(token)
    if missing_files:
        problems.append("названный артефакт не найден в проекте: "
                        + ", ".join(sorted(missing_files)[:6]))

    # 5. Остатки прежней редакции и разметка. Для журнала это перенесённая история — замечание,
    #    а не дефект: переписанный журнал перестаёт быть доказательством того, что было.
    marks = [m for m in LEGACY_MARKS if m in answer]
    if marks:
        target = notes if kind_of(row) in NARRATIVE_KINDS else problems
        target.append("остатки прежней редакции/разметки: "
                      + ", ".join(repr(m) for m in marks))
    tables = RL.markdown_tables(answer)
    if tables:
        notes.append(f"markdown-таблиц: {len(tables)}")

    # 6. Даты позже системной.
    future = []
    for day, month, year in DATE_RE.findall(answer):
        try:
            value = datetime.date(int(year), int(month), int(day))
        except ValueError:
            future.append(f"{day}.{month}.{year}")
            continue
        if value > TODAY:
            future.append(value.isoformat())
    if future:
        problems.append("дата позже системной: " + ", ".join(sorted(set(future))))

    # 7. Алиасы: объявленные против записанных, границы алиаса.
    declared = RL.aliases_of(answer)
    bad_alias = []
    for alias in declared:
        bad_alias += RL.validate_alias(alias, RL.marker_of(address), ctx["addresses"])
    if bad_alias:
        problems.append("алиас вне границ: " + "; ".join(bad_alias[:3]))
    db_aliases = {a for a in (row.get("aliases") or "").split("|") if a}
    not_written = sorted(set(declared) - db_aliases)
    if not_written:
        problems.append(f"объявлено {len(declared)} алиасов, в базе нет: "
                        + ", ".join(not_written[:5]))
    if db_aliases - set(declared):
        notes.append(f"алиасов в базе больше, чем объявлено карточкой: "
                     f"{len(db_aliases - set(declared))}")

    # 8. Карточка обязана быть названа в перечне слоя (или через префикс родителя).
    if RL.node_kind(address) == RL.KIND_RULE and ctx["layer_text"]:
        pointer = ctx["layer_text"]
        if address not in pointer:
            parent = address.rstrip(":").rsplit(":", 1)[0]
            if not (parent and parent in pointer):
                problems.append("карточка не названа в указателе уровня 2")

    info = dict(length=len(answer), levels=RL.levels_of(address),
                kind=RL.node_kind(address), sections=sections,
                aliases=len(db_aliases), declared=len(declared))
    return problems, notes, info


def main():
    ctx = read_state()
    ctx["registry"], ctx["params"] = full_registry()
    ctx["tags"] = tag_words()
    ctx["files"] = project_files()
    ctx["addresses"] = sorted(ctx["known"])
    print(f"регистр инструментов (4 сервера): {len(ctx['registry'])}; "
          f"имён параметров: {len(ctx['params'])}; тегов в базе: {len(ctx['tags'])}")
    layer = next((r for r in ctx["live"] if r["question"] == LAYER_ADDRESS), None)
    ctx["layer_text"] = (layer or {}).get("answer") or ""

    kinds, infos, problems_by_card, notes_by_card = Counter(), {}, {}, {}
    text_by_address = {}
    for row in ctx["live"]:
        problems, notes, info = audit(row, ctx)
        text_by_address[row["question"]] = row["answer"] or ""
        kinds[info["kind"]] += 1
        infos[row["question"]] = info
        if problems:
            problems_by_card[row["question"]] = problems
        if notes:
            notes_by_card[row["question"]] = notes

    if "--no-dump" not in sys.argv:
        for path, skip_journal in ((DUMP, False), (DUMP_RULES, True)):
            with path.open("w", encoding="utf-8") as handle:
                for row in ctx["live"]:
                    info = infos[row["question"]]
                    if skip_journal and info["kind"] in NARRATIVE_KINDS:
                        continue
                    handle.write(f"\n\n{'=' * 78}\n## {row['question']} "
                                 f"[{info['kind']}, {info['levels']} ур., {info['length']} симв., "
                                 f"разделы: {','.join(info['sections']) or 'нет'}]\n")
                    handle.write(row["answer"] or "")
            print(f"тексты выгружены: {path.name} ({path.stat().st_size} байт)")

    print("\n" + "=" * 78)
    print("состав живого поддерева: "
          + ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())))
    total = sum(i["length"] for i in infos.values())
    always = [q for q in infos if ":always:" in q]
    print(f"суммарный объём поддерева: {total} симв.; always-карточек: {len(always)}, "
          f"их объём: {sum(infos[q]['length'] for q in always)}")

    print(f"\n--- расхождения: {len(problems_by_card)} карточек из {len(infos)} ---")
    for group, title in ((RL.KIND_RULE, "правила (уровень 3+)"),
                         (RL.KIND_ROOT, "карточки-узлы (уровень 1–2)"),
                         (RL.KIND_CHECKS, "проверки (`checks`)"),
                         (RL.KIND_JOURNAL, "журнал (`journal`)")):
        cards = [a for a in sorted(problems_by_card) if infos[a]["kind"] == group]
        if not cards:
            continue
        print(f"\n### {title}: {len(cards)}")
        for address in cards:
            print(f"\n{address} ({infos[address]['length']} симв.)")
            for problem in problems_by_card[address]:
                print(f"  • {problem}")

    print("\n--- замечания (не дефект, но требует чтения) ---")
    for address in sorted(notes_by_card):
        print(f"  {address}: " + "; ".join(notes_by_card[address]))

    print("\n" + "=" * 78)
    print(f"ОБЪЁМЫ: MAX_ANSWER_CHARS={RL.MAX_ANSWER_CHARS}, "
          f"RESERVED_MAX_CHARS={RL.RESERVED_MAX_CHARS}, "
          f"ALWAYS_BUDGET_CHARS={RL.ALWAYS_BUDGET_CHARS}")
    over, near = [], []
    for address, info in sorted(infos.items(), key=lambda kv: -kv[1]["length"]):
        limit = RL.RESERVED_MAX_CHARS if info["kind"] == RL.STATE_RESERVED else RL.MAX_ANSWER_CHARS
        share = round(100 * info["length"] / limit)
        flag = " ← ПРЕВЫШЕНИЕ" if info["length"] > limit else (" ← близко" if share >= 80 else "")
        if info["length"] > limit:
            over.append((address, info))
        elif share >= 80:
            near.append((address, info))
        print(f"  {info['length']:6} {share:4}%  {address}{flag}")

    # «Из чего состоит» — для тех, кто у порога: без разбивки по разделам решение о делении
    # карточки принимается вслепую, а делить надо конкретный раздел.
    for address, info in over + near:
        body = RL.section_bodies(text_by_address.get(address, ""))
        parts = ", ".join(f"{k}={len(v)}" for k, v in
                          sorted(body.items(), key=lambda kv: -len(kv[1])))
        print(f"    {address}: {parts or 'разделов нет'}")

    counted, counted_cards = RL.always_budget(
        RL.ROOT_MARKER, [(q, text_by_address[q]) for q in infos])
    print(f"\nбюджет always так, как его считает `check_rules_layer.py` "
          f"(префикс `{RL.ROOT_MARKER}:always:`): {counted} симв. по {len(counted_cards)} "
          f"карточкам; порог {RL.ALWAYS_BUDGET_CHARS}")
    print(f"фактическая always-часть поддерева (`{PREFIX}:always:`): "
          f"{sum(infos[q]['length'] for q in always)} симв. по {len(always)} карточкам")
    print(f"\nкарточек с превышением порога: {len(over)}")
    for address, info in over:
        print(f"  • {address} — {info['length']} симв. ({info['kind']})")

    return 1 if problems_by_card else 0


if __name__ == "__main__":
    sys.exit(main())

