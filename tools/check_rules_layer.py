"""Проверка доступности и целостности слоёв правил (узлы RULE-LAYER, RULE-V2).

Отвечает на два вопроса, а не на один:

  1. «если AI-ассистент попросит это правило, он его получит?» — достижимость адресом по
     своей категории, изоляция чужой категорией, отсутствие алиасов (иначе строка находится
     перебором формулировок, а адрес перестаёт быть границей слоя);
  2. «записано ли правило так, что его можно применить и подтвердить?» — структура карточки по
     состоянию (WHEN говорит, когда применять; CHECK называет, чем подтверждать), иерархия
     адресов, бюджет `always`, и главное — каждая строка индекса называет инструмент проверки,
     а каждая названная в индексе ссылка ведёт в существующую карточку.

Второй вопрос появился потому, что индексы слоёв живут записями БД, а инструменты проверки, о
которых они говорят, живут файлами и регистрами MCP. Правило без ссылки на проверку — текст,
который нечем подтвердить; ссылка индекса в несуществующее правило — та же дыра, из-за которой
«правило есть, но его не найти». Проверка закрывает обе границы.

Что проверяется:

  1. метки `LAYERS` совпадают с `TITLE_LAYER_MARKERS` в коде поиска (без записи там адрес не
     читается шагом заголовков; лишняя запись там без слоя здесь — мёртвый префикс);
  2. категории слоя есть в `doc_categories` (без них слой не изолируется фильтром);
  3. слой формата 1 (перенос файла правил): исходник разбирается без ошибок, текст карточки в
     БД совпадает с исходником, стрые строки слоя не считаются достижимыми молча;
  4. слой формата 2 (правила пишутся строками БД): адрес удовлетворяет грамматике и находится в
     одном из состояний (always/optional/reserved/checks/journal) либо является индексом слоя;
     `source_url` = `rules-layer://<адрес>`; теги несут категорию и состояние;
  5. разделы карточки по состоянию: для always/optional/checks — WHEN/MUST/FORBID/TOOLS/CHECK/
     SOURCE, для reserved — WHEN/TRIGGER/WHERE, для индекса — разделы состояний и EDIT. Карточка
     без WHEN не применима, без CHECK не подтверждается;
  6. иерархия и ссылки: индекс состояния перечисляет карточки этого состояния, каждая строка
     таблицы индекса имеет непустую колонку «чем проверяется», названный артефакт существует
     (файл на диске или инструмент из EXPECTED_TOOLS), каждая ссылка индекса ведёт в
     существующую карточку, в том числе межслойная (`rules:index` называет `kb-rules:index`);
  7. бюджеты: сумма `always`-карточек слоя не больше ALWAYS_BUDGET_CHARS, резервная карточка не
     больше RESERVED_MAX_CHARS. Пороги жёсткие: превышение — провал, а не предупреждение, потому
     что «всегда», которое не читается целиком, не применяется;
  8. достижимость каждого адреса своей категорией и отсутствие отдачи чужой категорией;
  9. маршрутизатор `.clinerules/1C_Rule.md` называет индекс каждого записанного слоя.

Чего проверка НЕ проверяет: смысл и полноту текста правила (это ревью), совпадение правила с
поведением MCP-сервера (это tools/check_search_rules_sync.py и валидаторы узлов), и то, что
карточка найдётся «человеческими словами»: слой адресуется адресом, алиасы ему не заводятся.

Запуск:

    python tools/check_rules_layer.py                 # все слои
    python tools/check_rules_layer.py --layer kb-rules
    python tools/check_rules_layer.py --no-db         # только метки и разбор, без local_doc

Код возврата 1 — есть проваленная проверка. Итоговое число печатает сам скрипт: «проверок N,
провалено 0» без замера — утверждение, а не факт.
"""

import argparse
import sys
from pathlib import Path

try:  # кириллица вывода не влазит в cp1251: без этого падает сам print, и прогон с
      # перенаправлением в файл дал бы rc=1 при исправных слоях
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # сбой настройки потока не имеет права менять итог проверки
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import rules_layer as RL  # noqa: E402

ROUTER = PROJECT_ROOT / ".clinerules" / "1C_Rule.md"
FOREIGN_CATEGORY = "language"  # заведомо чужая категория: на ней проверяется изоляция слоя

_checks = 0
_failures = []


def check(ok, what, detail=""):
    """Одна проверка. detail печатается только при провале, чтобы зелёный прогон читался."""
    global _checks
    _checks += 1
    if not ok:
        _failures.append(f"{what}" + (f" — {detail}" if detail else ""))
    return bool(ok)


# ------------------------------------------------------------------ метки и категории

def check_markers():
    """Метки LAYERS и TITLE_LAYER_MARKERS обязаны совпадать: карточка слоя читается адресом,
    а адрес разрешается шагом заголовков только для записанной там метки."""
    from mcp_tools_api import TITLE_LAYER_MARKERS

    expected = tuple(f"{m}:" for m in RL.markers())
    check(tuple(TITLE_LAYER_MARKERS) == expected,
          "метки LAYERS совпадают с TITLE_LAYER_MARKERS",
          f"в поиске {tuple(TITLE_LAYER_MARKERS)}, в спецификации {expected}")


def all_categories():
    wanted = set()
    for marker in RL.markers():
        wanted.update(RL.categories_of(marker))
    return wanted


def check_categories():
    """Каждая категория слоя есть в doc_categories: без записи там фильтр по категории не
    изолирует слой, и «правила читаются отдельно от документации» — утверждение без проверки."""
    from database import get_cursor

    with get_cursor() as cur:
        cur.execute("SELECT code FROM doc_categories")
        present = {row["code"] for row in cur.fetchall()}
    missing = sorted(all_categories() - present)
    check(not missing, "категории всех слоёв есть в doc_categories",
          f"нет записей: {missing}. Нужна строка в CATEGORY_SEED (src/database.py), её "
          f"применяет seed_categories — вызывает мигратор перед записью карточек")


# ------------------------------------------------------------------ слой в БД

def layer_rows(cur, marker):
    """Карточки слоя из БД: вопрос (он же адрес), ответ, теги, source_url, число алиасов.

    Отбор — по метке в заголовке, а не по категории: категория меняется при переходе слоя на
    формат 2 (у правил появляется своя), а принадлежность слою задаёт адрес. Строки с чужой
    меткой отсекает грамматика адреса в вызывающем коде.
    """
    cur.execute(
        "SELECT id, question, answer, tags, source_url, "
        "(SELECT COUNT(*) FROM alias_targets a WHERE a.snippets_id = knowledge_snippets.id) "
        "AS aliases FROM knowledge_snippets WHERE question LIKE %s AND source_url LIKE %s",
        (marker + ":%", RL.SOURCE_SCHEME + "%"),
    )
    return [dict(row) for row in cur.fetchall()]


def source_files(marker=None):
    """Файлы-исходники слоёв (для слоёв формата 1). Отсутствующий файл слоя формата 2 —
    норма: у такого слоя источник — строки БД."""
    directory = PROJECT_ROOT / RL.RULES_DIR
    if marker:
        path = directory / f"{marker}.md"
        return [path] if path.exists() else []
    if not directory.exists():
        return []
    return sorted(p for p in directory.glob("*.md") if RL.marker_for_path(p.name))


# ------------------------------------------------------------------ формат 1: перенос файла

def check_layer_v1(marker, path):
    """Слой формата 1 — перенесённый файл правил: источник истины ещё файл, поэтому сверяется
    текст. Перевод слоя на формат 2 снимает эту проверку и включает структурную."""
    cards, errors, fatal = RL.load_document(path)
    problems = ([fatal] if fatal else []) + list(errors)
    check(not problems, f"[{marker}] исходник разбирается без ошибок", "; ".join(problems[:6]))
    if not cards:
        return []
    from database import get_cursor

    with get_cursor() as cur:
        rows = {row["source_url"]: row for row in layer_rows(cur, marker)}
    written = 0
    for card in cards:
        row = rows.get(card["source_url"])
        if not check(row is not None, f"[{marker}] {card['address']}: карточка записана в БД"):
            continue
        written += 1
        check(row["answer"] == card["answer"],
              f"[{marker}] {card['address']}: текст БД совпадает с исходником",
              "ручная правка строки в БД будет перезаписана мигратором — правка идёт в источнике")
    stale = sorted(set(rows) - {c["source_url"] for c in cards})
    check(not stale, f"[{marker}] в БД нет стрых строк слоя формата 1",
          f"есть в БД, нет в исходнике: {[r.split('://', 1)[-1] for r in stale][:5]}")
    print(f"[{marker}] формат 1: карточек в исходнике {len(cards)}, подтверждено в БД {written}")
    return cards


# ------------------------------------------------------------------ формат 2: структура БД

def check_layer_v2(marker):
    """Слой формата 2: источник — строки БД, поэтому проверяется структура записи, а не дифф.

    Порядок проверок повторяет то, как слой читают: сначала адрес (он задаёт границу), потом
    разделы карточки (ими определяют, применять правило или нет), потом индекс (по нему идут
    работать), потом ссылки и артефакты индекса, потом бюджет. Провал любой из них означает,
    что правило либо не найдётся, либо будет прочитано без условия применения и без способа
    подтверждения.
    """
    from database import get_cursor

    with get_cursor() as cur:
        rows = layer_rows(cur, marker)
    if not check(bool(rows), f"[{marker}] слой формата 2 записан в БД",
                 "карточек слоя нет — читать нечего, слой существует только в LAYERS"):
        return {}
    categories = RL.categories_of(marker)
    primary = categories[0] if categories else ""
    by_address = {row["question"]: row for row in rows}
    cross = {}

    for address in sorted(by_address):
        row = by_address[address]
        state = RL.state_of(address)
        problems = RL.validate_address(address, marker)
        if not problems and not RL.is_index_address(address) and state is None:
            problems.append(
                f"адрес вне состояний слоя ({', '.join(RL.LAYER_STATES)}) — правило без "
                f"состояния не читается ни как «всегда», ни как «по ситуации»")
        check(not problems, f"[{marker}] {address}: адрес в грамматике и в состоянии",
              "; ".join(problems[:3]))
        check(row["source_url"] == RL.source_url(address),
              f"[{marker}] {address}: source_url остаётся ключом идемпотентности",
              f"в строке {row['source_url']!r}")
        tags = set(row["tags"] or [])
        check(primary in tags, f"[{marker}] {address}: тег категории слоя на карточке",
              f"теги {sorted(tags)} — без него слой не изолируется фильтром")
        if state:
            check(state in tags, f"[{marker}] {address}: тег состояния {state} на карточке",
                  f"теги {sorted(tags)}")
        if state != RL.STATE_JOURNAL:
            check(int(row["aliases"] or 0) == 0,
                  f"[{marker}] {address}: у карточки правила нет алиасов",
                  f"алиасов {row['aliases']}: строка начнёт находиться перебором слов, а адрес "
                  f"перестанет быть границей (алиасы допустимы только у журнала — это след "
                  f"переименования адреса)")
        missing = [s for s in RL.required_sections(address)
                   if s not in RL.sections_of(row["answer"])]
        check(not missing, f"[{marker}] {address}: разделы карточки на месте",
              f"нет {', '.join('===' + s for s in missing)} — без WHEN правило не применимо, "
              f"без CHECK его нечем подтвердить")
        if state == RL.STATE_RESERVED:
            check(len(row["answer"] or "") <= RL.RESERVED_MAX_CHARS,
                  f"[{marker}] {address}: резервная карточка короткая",
                  f"{len(row['answer'] or '')} > {RL.RESERVED_MAX_CHARS}: длинный текст в "
                  f"reserved означает, что правило уже написано")
    return check_layer_v2_indexes(marker, by_address, cross)


def check_layer_v2_indexes(marker, by_address, cross):
    """Индексы слоя формата 2: бюджет always, таблица с колонкой проверки, существование
    каждого названного артефакта и каждой названной ссылки."""
    total, always_cards = RL.always_budget(
        marker, [(address, row["answer"]) for address, row in by_address.items()])
    check(total <= RL.ALWAYS_BUDGET_CHARS,
          f"[{marker}] бюджет always в пределах порога",
          f"{total} > {RL.ALWAYS_BUDGET_CHARS} символов по {len(always_cards)} карточкам "
          f"({', '.join(always_cards[:6])}): «всегда», которое не читается за один заход, "
          f"не применяется — перенеси правило в optional или раздели его")

    for address in sorted(by_address):
        row = by_address[address]
        if not RL.is_index_address(address):
            continue
        state = RL.state_of(address)
        if state == RL.STATE_JOURNAL:
            # От индекса журнала не требуются формат таблицы и колонка проверки: его строки —
            # перечень снимка, а не правила с инструментом подтверждения. Ссылки и полнота
            # перечня проверяются на общих основаниях: оглавление, которое ведёт в несуществующий
            # адрес, теряет карточку так же, как оглавление без строки.
            pass
        tables = RL.markdown_tables(row["answer"])
        if state in (RL.STATE_ALWAYS, RL.STATE_OPTIONAL, RL.STATE_CHECKS):
            check(bool(tables), f"[{marker}] {address}: индекс состояния — таблица",
                  "строк нет — по индексу нельзя идти работать; строки читаются колонками")
        for table in tables:
            cols = RL.check_columns(table)
            if state in (RL.STATE_ALWAYS, RL.STATE_OPTIONAL, RL.STATE_CHECKS):
                check(bool(cols),
                      f"[{marker}] {address}: у таблицы индекса есть колонка проверки",
                      f"заголовки {table['header']}: ни одна колонка не названа "
                      f"{', '.join(RL.CHECK_COLUMN_KEYS)} — правило без названного инструмента "
                      f"проверки нечем подтвердить")
            for line in table["rows"]:
                for idx in cols:
                    cell = line[idx] if idx < len(line) else ""
                    if not check(bool(cell.strip()),
                                 f"[{marker}] {address}: строка "
                                 f"{(line[0] if line and line[0] else '?')!r} называет проверку",
                                 "пустая колонка проверки"):
                        continue
                    for token in RL.artifact_tokens(cell):
                        check(RL.artifact_exists(token, PROJECT_ROOT),
                              f"[{marker}] {address}: названный артефакт {token} существует",
                              "правило ссылается на удалённый или ещё не написанный инструмент: "
                              "текст правила живёт, а доказательство — нет")
        for token in RL.address_tokens(row["answer"]):
            other = RL.marker_of(token)
            if other not in RL.LAYERS:
                continue
            if other == marker:
                check(RL.address_resolves(token, by_address),
                      f"[{marker}] {address}: ссылка индекса {token} разрешается в карточку",
                      "индекс обещает правило, которого нет — та же дыра, что ссылка в никуда")
            else:
                cross.setdefault(other, set()).add(token)
        # индекс состояния обязан перечислить его карточки: строка, которой нет в оглавлении,
        # существует в слое и не находится префиксным шагом — ровно та дыра, из-за которой
        # «правило есть, но его не найти» (граница «карточка обязана называться в оглавлении»)
        listed = {cell.strip().strip("`").strip()
                  for table in tables for line in table["rows"] if line for cell in line[:1]}
        for own in sorted(by_address):
            if RL.state_of(own) != state or RL.is_index_address(own):
                continue
            check(any(RL.address_resolves(tok, {own}) for tok in listed if tok),
                  f"[{marker}] {address}: карточка {own} названа в индексе состояния",
                  "карточка есть в слое и не перечислена — по индексу до неё не дойти")

    for other, tokens in sorted(cross.items()):
        from database import get_cursor

        with get_cursor() as cur:
            theirs = {row["question"] for row in layer_rows(cur, other)}
        for token in sorted(tokens):
            check(RL.address_resolves(token, theirs),
                  f"[{marker}] межслойная ссылка {token} разрешается",
                  f"в слое {other!r} такой карточки нет: маршрут обрывается на середине")

    print(f"[{marker}] формат 2: карточек {len(by_address)}, "
          f"always {len(always_cards)} на {total}/{RL.ALWAYS_BUDGET_CHARS} симв., "
          f"журнал {sum(1 for a in by_address if RL.state_of(a) == RL.STATE_JOURNAL)}, "
          f"резерв {sum(1 for a in by_address if RL.state_of(a) == RL.STATE_RESERVED)}")
    return by_address


# ------------------------------------------------------------------ достижимость адресом

def check_reachable(marker, addresses, category, hierarchical, by_address=None):
    """Каждый адрес слоя читается своей категорией; чужая категория карточку не отдаёт.

    Проверка идёт настоящим `search_docs`, а не копией его предиката: проверка, повторяющая
    SQL поиска, проверяла бы свою копию (урок src/quarantine.py и src/current_revision.py).

    Для слоя формата 2 дополнительно проверяется иерархия: префикс состояния (`<метка>:always`)
    отдаёт всё поддерево состояния — на этом держится обещание индекса «прочитал индекс —
    дальше идёшь по строкам». Состояние, карточек которого в слое нет, префиксом не читается
    по определению; от слоя требуется не пустой префикс, а текст в индексе: молчание о
    состоянии отличается от его отсутствия тем, что читатель знает границу.
    """
    from mcp_tools_api import search_docs

    for address in addresses:
        found = {str(item.get("title", "")) for item in
                 search_docs(address, category=category, limit=5)}
        check(address in found, f"[{marker}] {address}: адрес читается своей категорией",
              f"выдача по {category!r}: {sorted(found)[:3]}")
        foreign = {str(item.get("title", "")) for item in
                   search_docs(address, category=FOREIGN_CATEGORY, limit=5)}
        check(address not in foreign, f"[{marker}] {address}: чужая категория карточку не отдаёт",
              f"{FOREIGN_CATEGORY!r} вернула строку правил — изоляция слоя не работает")
    if hierarchical:
        used = {RL.state_of(a) for a in (by_address or {})}
        index_text = ((by_address or {}).get(RL.index_address(marker)) or {}).get("answer") or ""
        for state in RL.LAYER_STATES:
            prefix = f"{marker}:{state}"
            if state in used:
                found = {str(item.get("title", "")) for item in
                         search_docs(prefix, category=category, limit=50)}
                own = [t for t in found if t.startswith(prefix)]
                check(bool(own), f"[{marker}] префикс {prefix} отдаёт поддерево состояния",
                      "состояние объявлено в грамматике слоя, но по префиксу не читается — "
                      "индекс по нему не работает")
                continue
            check(RL.declares_state(index_text, state),
                  f"[{marker}] индекс называет состояние {state} неиспользуемым текстом",
                  "в слое нет карточек этого состояния и индекс о нём молчит: читатель не может "
                  "отличить «состояния нет» от «карточки забыли» (правило `rules:always:indexing`)")


# ------------------------------------------------------------------ маршрутизатор

def check_router(markers_written):
    """Маршрутизатор .clinerules/1C_Rule.md обязан называть индекс каждого записанного слоя:
    иначе правило существует, а до него не дойти — ровно тот дефект, против которого индекс
    заведён. Отдельно проверяется, что назван корневой индекс: с него начинается путь к любому
    слою, и если его нет, карта меток превращается в перечень без входа.

    Названным адрес считается только как адрес, а не как подстрока: замер 24.10.2026 показал,
    что проверка `root in text` проходила, когда корневого индекса в маршрутизаторе не было вовсе,
    — подстроку давал `core-rules:index`. Разбор берётся тот же, что у ссылок индексов
    (`RL.address_tokens`), чтобы «назван» означало одно и то же в двух проверках.
    """
    if not check(ROUTER.exists(), "маршрутизатор .clinerules/1C_Rule.md существует"):
        return
    named = set(RL.address_tokens(ROUTER.read_text(encoding="utf-8")))
    check(RL.index_address(RL.ROOT_MARKER) in named,
          "маршрутизатор называет корневой индекс rules:index",
          "иерархический индекс правил записан, но из всегда загружаемого текста до него не дойти")
    for marker in markers_written:
        if marker == RL.ROOT_MARKER:
            continue
        index = RL.index_address(marker)
        check(index in named, f"маршрутизатор называет индекс слоя {index}",
              "слой записан, но из стартового текста до него не дойти")


# ------------------------------------------------------------------ прогон

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Проверка доступности и целостности слоёв правил local_doc "
                    "(узлы RULE-LAYER, RULE-V2)")
    ap.add_argument("--layer", default="",
                    help="проверить один слой по метке (например kb-rules)")
    ap.add_argument("--no-db", action="store_true",
                    help="не обращаться к local_doc: только метки и разбор исходников")
    args = ap.parse_args(argv)

    check_markers()

    markers = [args.layer] if args.layer else list(RL.markers())
    unknown = [m for m in markers if m not in RL.LAYERS]
    if unknown:
        print(f"неизвестные метки слоёв: {unknown} — известными считаются {list(RL.LAYERS)}")
        return 1

    if args.no_db:
        for marker in markers:
            if RL.LAYER_FORMAT.get(marker, 1) != 1:
                continue
            for path in source_files(marker):
                cards, errors, fatal = RL.load_document(path)
                problems = ([fatal] if fatal else []) + list(errors)
                check(not problems, f"[{marker}] исходник разбирается без ошибок",
                      "; ".join(problems[:6]))
        print("\n--no-db: проверки записи, структуры и достижимости ПРОПУЩЕНЫ — они не "
              "пройдены, а не проверены; зелёный итог этого прогона ничего не подтверждает")
    else:
        check_categories()
        written = []
        for marker in markers:
            category = RL.category_of(marker)
            if RL.LAYER_FORMAT.get(marker, 1) == 1:
                files = source_files(marker)
                if not check(bool(files), f"[{marker}] исходник слоя формата 1 существует",
                             f"слой помечен форматом 1, файла {RL.RULES_DIR}/{marker}.md нет — "
                             f"сверять текст нечем; переведи слой на формат 2 или верни файл"):
                    continue
                cards = []
                for path in files:
                    cards += check_layer_v1(marker, path)
                check_reachable(marker, [c["address"] for c in cards], category, False)
                if cards:
                    written.append(marker)
            else:
                by_address = check_layer_v2(marker)
                # журнал из проверки адресной достижимости убран намеренно: его читают префиксом
                # состояния (его проверяет ветка hierarchical), а не каждым заголовком — в
                # заголовках журнала пробелы и прежняя орфография, это снимок, а не адрес правила
                addresses = [a for a in sorted(by_address) if RL.state_of(a) != RL.STATE_JOURNAL]
                check_reachable(marker, addresses, category, True, by_address)
                if by_address:
                    written.append(marker)
        check_router(written)

    print(f"\nпроверок: {_checks}, провалено: {len(_failures)}")
    if _failures:
        print("ПРОВАЛЕННЫЕ ПРОВЕРКИ:")
        for failure in _failures:
            print(f"  - {failure}")
        return 1
    print("СЛОИ ДОСТИЖИМЫ И ЦЕЛОСТНЫ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




