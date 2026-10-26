"""Мигратор правил проекта в слой карточек local_doc (узел RULE-LAYER, 24.10.2026).

Формат исходника — `docs/rules/<метка>.md`: строка `## <адрес>` открывает карточку, её
answer — текст до следующего `##`. Разбор и правила адреса — `src/rules_layer.py`, один на
мигратор и на проверку `tools/check_rules_layer.py`.

Чем этот мигратор отличается от `tools/migrate_core_rules_to_layer.py`: тот переносил один
файл журнала по его собственной разметке («п. N», «узел VNN») и был инструментом разовой
переноски. Этот работает по формату, который задаёт дерево правил, и остаётся рабочим путём
правки правил: изменил исходник — прогнал мигратор — карточка обновилась с историей в
`snippet_audit_log`.

Идемпотентность — по `source_url = rules-layer://<адрес>`, а не по id: id меняются при
пересоздании базы документации, адрес устойчив и его задаём мы. Правка существующей карточки
идёт контрактом `update_snippet` (та же строка + аудит), а не второй карточкой: две карточки
одного правила поиск отдаёт обе — тот дефект, из-за которого правка сниппета и стала
отдельной операцией (узел P6).

Переименование адреса — `--rename-map <json>` вида {"старый": "новый"}. Строка не удаляется и
не создаётся заново: правится та же (по id старой), а прежний адрес добавляется алиасом. Без
этого переезд адреса рвал ссылки из индекса и из прежних разговоров; алиас при этом ровно
один на переименование, шум из слов адреса по-прежнему не заводится.

Ручные алиасы карточки мигратор берёт из раздела `===ALIASES===` исходника и пишет их операцией
`add_aliases` (та же, что доступна оператору как `add_aliases_tool`; идемпотентна на уровне БД).
Алиасы объявлены в исходнике, а не заводятся руками в базе, по той же причине, по которой там же
объявлены тексты правил: строку правила правит и пересоздаёт мигратор, а алиас, существующий
только в БД, не виден в диффе git и пропадает вместе со строкой — правило начинает искаться по
слову, которого нет ни в одном исходнике.

Удалений мигратор не делает: карточка, пропавшая из исходника, печатается как «в БД есть, в
исходнике нет» и остаётся до осознанного решения (снимается `mark_snippet_for_deletion_tool`,
узел Q1). Молча снять правило — значит потерять его так же, как молча не записать.

Запуск:

    python tools/migrate_rules_to_layer.py --file docs/rules/export-rules.md
    python tools/migrate_rules_to_layer.py --all --apply
    python tools/migrate_rules_to_layer.py --all --apply --rename-map tools/renames_core.json

Код возврата 1 — ошибки разбора или записи; 0 — разбор или запись без ошибок.
"""

import argparse
import json
import sys
from pathlib import Path

try:  # кириллица и служебные символы вывода не влазят в cp1251 — падает сам print,
      # и прогон с перенаправлением в файл дал бы rc=1 при исправных правилах
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # сбой настройки потока не имеет права менять итог миграции
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import rules_layer as RL  # noqa: E402  (после sys.path — общий разбор и правила адреса)

REASON = ("узел RULE-LAYER: правила MCP-серверов переведены в слой карточек local_doc; "
          "текст карточки совпадает с исходником docs/rules")


# ------------------------------------------------------------------ БД

def existing_layer_rows(cur, category):
    """Карточки слоя в БД по source_url — по ним мигратор узнаёт, что править, а не создавать.

    Выборка ограничена нашей схемой source_url (`rules-layer://`), а не категорией вообще: в
    категории `1c-configurations-core` уже лежат карточки журнала с другим ключом, и путать их
    с рабочими правилами нельзя — иначе переименование журнала задело бы рабочие карточки.
    """
    cur.execute(
        "SELECT id, question, answer, source_url, tags FROM knowledge_snippets "
        "WHERE %s = ANY(tags) AND source_url LIKE %s",
        (category, RL.SOURCE_SCHEME + "%"),
    )
    # курсор get_cursor — RealDictCursor, доступ по именам колонок, а не по позициям
    return {row["source_url"]: {"id": row["id"], "question": row["question"],
                                "answer": row["answer"], "tags": row["tags"]}
            for row in cur.fetchall()}


def insert_card(cur, card):
    """Новая карточ слоя — прямая вставка, не `add_snippet`.

    Причина не в удобстве: `add_snippet` при groups_id IS NULL генерирует алиасы из вопроса,
    а слой адресуется заголовком (шаг заголовков, `TITLE_LAYER_MARKERS`). Алиасы от адреса
    вида `export-rules:workflow:cycle` дали бы в точном алиасном шаге шум по словам `export`,
    `rules`, `workflow`, `cycle` — тот дефект, из-за которого алиасы из адреса не выводятся.
    Ручные алиасы карточки (раздел `===ALIASES===`) пишутся отдельно, `sync_aliases`, и только
    те, что объявлены оператором в исходнике.
    """
    cur.execute(
        "INSERT INTO knowledge_snippets (groups_id, question, answer, source_url, tags, "
        "confidence, is_verified) VALUES (NULL, %s, %s, %s, %s, %s, TRUE) RETURNING id",
        (card["address"], card["answer"], card["source_url"], card["tags"], 1.0),
    )
    row = cur.fetchone()
    return row["id"] if row else None


def sync_aliases(card, snippet_id):
    """Ручные алиасы карточки, объявленные исходником (`===ALIASES===`).

    Пишет `add_aliases` — та же операция, которой оператор добавляет алиасы через
    `add_aliases_tool`, и та же идемпотентность (ON CONFLICT DO NOTHING): повторный прогон
    мигратора не размножает алиасы. Алиасы пишутся и для карточек «без изменений»: алиас
    дописывают в исходник тогда, когда текст правила уже правильный, и пропуск такой карточки
    означал бы «алиас объявлен, но не работает».

    Возвращает (объявлено, добавлено, ошибка). Молча не записать алиас нельзя: правило, которое
    ищут по слову, которого в базе нет, не находится — это тот же дефект, что карточка, не
    названная в индексе.
    """
    declared = RL.aliases_of(card["answer"])
    if not declared:
        return 0, 0, None
    if not snippet_id:
        return len(declared), 0, "id строки не получен — алиасы писать некуда"
    from mcp_tools_api import add_aliases  # noqa: E402  (после sys.path, общий контракт алиасов)
    res = add_aliases(declared, snippets_id=snippet_id)
    if not res.get("success"):
        return len(declared), 0, res.get("error") or "алиасы не записаны"
    return len(declared), int(res.get("added") or 0), None


def apply_cards(cur, cards, existing, renames):
    """Одна карточка = одно действие: вставка, правка той же строки или ничего.

    `renames` — {новый адрес: старый адрес}. Если карточки с новым адресом в БД нет, но есть
    строка со старым, правится ОНА: адрес — это имя той же записи, а не новое знание. Старый
    адрес после этого остаётся алиасом (`update_snippet` дополняет алиасы аддитивно и никогда
    их не удаляет), поэтому прежняя ссылка продолжает находиться.

    Ручные алиасы исходника (`===ALIASES===`) дописываются к строке на любой ветке, включая
    «без изменений»: идемпотентность у `add_aliases` на уровне БД, а пропуск ветки означал бы
    объявленный и незаписанный алиас.
    """
    from mcp_tools_api import update_snippet

    added = updated = unchanged = renamed = 0
    alias_cards = alias_rows = 0
    failed = []
    for card in cards:
        old = existing.get(card["source_url"])
        old_address = renames.get(card["address"])
        if not old and old_address:
            old = existing.get(RL.source_url(old_address))
            if old:
                renamed += 1
        if not old:
            new_id = insert_card(cur, card)
            if new_id:
                added += 1
            else:
                failed.append(f"вставка {card['address']}: id не получен")
                continue
            declared, wrote, err = sync_aliases(card, new_id)
            if err:
                failed.append(f"{card['address']}: алиасы не записаны: {err}")
            if declared:
                alias_cards += 1
                alias_rows += wrote
            continue
        if old["question"] == card["address"] and old["answer"] == card["answer"] and not old_address:
            unchanged += 1
            declared, wrote, err = sync_aliases(card, old["id"])
            if err:
                failed.append(f"{card['address']}: алиасы не записаны: {err}")
            if declared:
                alias_cards += 1
                alias_rows += wrote
            continue
        res = update_snippet(
            old["id"], new_question=card["address"], new_answer=card["answer"],
            tags=card["tags"],
            aliases=(old_address if old_address and old_address != card["address"] else None),
            reason=REASON,
        )
        if res.get("success"):
            updated += 1
            declared, wrote, err = sync_aliases(card, old["id"])
            if err:
                failed.append(f"{card['address']}: алиасы не записаны: {err}")
            if declared:
                alias_cards += 1
                alias_rows += wrote
        else:
            failed.append(f"id={old['id']} {card['address']}: {res.get('error') or 'строки нет'}")
    return added, updated, unchanged, renamed, alias_cards, alias_rows, failed


# ------------------------------------------------------------------ разбор

def collect_targets(args):
    """Файлы-исходники, которые обрабатываем. --all берёт из docs/rules только файлы-слои.

    Каталог `docs/rules` держит не только исходники слоёв: в него перенесены прежние нормативы
    (`SEARCH_RULES.md`, `LOAD_RULES*.md`, `1c-*_Rule.md`) как архивы и входы планогенератора.
    Имя файла слоя — это его метка (`marker_for_path`), и молча пытаться загрузить архив как слой
    значит получить отказ разбора вместо работы; молча пропустить без объявления — значит
    потерять слой, опечатку в имени которого никто не заметил. Поэтому: берём метки, а пропущенные
    называем списком.
    """
    if args.all:
        directory = PROJECT_ROOT / RL.RULES_DIR
        found = sorted(directory.glob("*.md")) if directory.exists() else []
        chosen = [p for p in found if RL.marker_for_path(p)]
        skipped = [p.name for p in found if not RL.marker_for_path(p)]
        if skipped:
            print(f"файлы каталога {RL.RULES_DIR}, не являющиеся исходниками слоёв "
                  f"(имя != метка), пропущены: {', '.join(skipped)}")
        return chosen
    return [Path(f) for f in (args.file or [])]


def read_renames(path):
    """Карта переименований {"старый адрес": "новый адрес"} -> ({новый: старый}, ошибки).

    Обе стороны проверяются грамматикой адреса: опечатка в карте (например, старый адрес с
    заглавной буквой) иначе молча не нашла бы строку в БД, и мигратор создал бы вторую
    карточку правила вместо правки первой — ровно тот дефект, против которого карта и заведена.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        return {}, [f"не читается карта переименований {path}: {exc}"]
    except ValueError as exc:
        return {}, [f"карта переименований {path} не является JSON: {exc}"]
    if not isinstance(raw, dict):
        return {}, [f"карта переименований {path}: ожидается объект {{'старый': 'новый'}}"]
    renames, errors = {}, []
    for old_address, new_address in raw.items():
        errors += RL.validate_address(old_address, RL.marker_of(old_address))
        errors += RL.validate_address(new_address, RL.marker_of(new_address))
        if old_address == new_address:
            errors.append(f"переименование {old_address!r} ведёт в самого себя")
            continue
        renames[new_address] = old_address
    return renames, errors


def report(marker, cards):
    """Сводка по слою до записи: число карточек, дерево адресов, фактические максимумы против
    порогов. Максимумы печатаются, а не только сами пороги: «адрес короткий» без замера —
    это утверждение, а не факт."""
    print(f"\n[{marker}] карточек: {len(cards)}")
    aliased = 0
    for card in sorted(cards, key=lambda c: c["address"]):
        declared = RL.aliases_of(card["answer"])
        aliased += 1 if declared else 0
        print(f"  {card['address']:<{RL.MAX_TITLE_DISPLAY_CHARS}} answer {len(card['answer']):>5}"
              + (f"  алиасы {len(declared)}: {', '.join(declared)}" if declared else ""))
    print(f"  карточек с ручными алиасами: {aliased}")
    longest_t = max((len(c["address"]) for c in cards), default=0)
    longest_a = max((len(c["answer"]) for c in cards), default=0)
    print(f"  пороги: адрес <= {RL.MAX_TITLE_DISPLAY_CHARS} (максимум {longest_t}); "
          f"answer <= {RL.MAX_ANSWER_CHARS} (максимум {longest_a})")


# ------------------------------------------------------------------ прогон

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Запись правил из docs/rules/<метка>.md в слой карточек local_doc")
    ap.add_argument("--file", action="append", default=[],
                    help="исходник слоя (можно несколько раз)")
    ap.add_argument("--all", action="store_true",
                    help=f"все исходники {RL.RULES_DIR}/*.md")
    ap.add_argument("--apply", action="store_true",
                    help="записать в local_doc (по умолчанию только разбор и сводка)")
    ap.add_argument("--rename-map", default="",
                    help="json-карта переименований {\"старый адрес\": \"новый адрес\"}")
    args = ap.parse_args(argv)

    targets = collect_targets(args)
    if not targets:
        print(f"не указан ни один исходник: нужен --file {RL.RULES_DIR}/<метка>.md или --all")
        return 1

    renames, errors = ({}, [])
    if args.rename_map:
        renames, errs = read_renames(args.rename_map)
        errors += errs

    parsed = []
    for path in targets:
        cards, errs, fatal = RL.load_document(path)
        if fatal:
            errors.append(fatal)
            continue
        errors += errs
        if cards:
            parsed.append((path, cards))
            # метку берём из разобранной карточки, а не выводим из имени пути повторно:
            # разбор уже проверил, что адрес принадлежит метке этого файла (карточка несёт marker)
            report(cards[0]["marker"], cards)

    if errors:
        print("\nОШИБКИ РАЗБОРА:")
        for e in errors:
            print(f"  - {e}")
        return 1

    if not args.apply:
        print("\nРАЗБОР ПРОВЕРЕН (в БД не писали) — для записи нужен --apply")
        return 0

    from database import get_cursor, seed_categories  # noqa: E402  (после sys.path)

    totals = {"added": 0, "updated": 0, "unchanged": 0, "renamed": 0,
              "alias_cards": 0, "alias_rows": 0}
    failed = []
    with get_cursor() as cur:
        cat_added, cat_present = seed_categories(cur)
        print(f"\nкатегории: добавлено {cat_added}, уже было {cat_present}")
        for path, cards in parsed:
            category = cards[0]["category"]
            existing = existing_layer_rows(cur, category)
            print(f"\n[{category}] карточек слоя в БД до: {len(existing)}")
            (added, updated, unchanged, renamed, alias_cards, alias_rows,
             layer_failed) = apply_cards(cur, cards, existing, renames)
            for key, value in (("added", added), ("updated", updated),
                               ("unchanged", unchanged), ("renamed", renamed),
                               ("alias_cards", alias_cards), ("alias_rows", alias_rows)):
                totals[key] += value
            failed += layer_failed
            stale = sorted(set(existing) - {c["source_url"] for c in cards})
            for url in stale:
                print(f"  ⚠️ в БД есть, в исходнике нет: id={existing[url]['id']} "
                      f"{existing[url]['question']} (не удаляем — решение снимает оператор)")
            print(f"  добавлено {added}, обновлено {updated}, без изменений {unchanged}, "
                  f"переименовано {renamed}, стрых {len(stale)}; алиасов объявлено на "
                  f"{alias_cards} карточках, новых строк {alias_rows}")

    print(f"\nитог: добавлено {totals['added']}, обновлено {totals['updated']}, "
          f"без изменений {totals['unchanged']}, переименовано {totals['renamed']}; "
          f"алиасы на {totals['alias_cards']} карточках, новых строк {totals['alias_rows']}")
    if failed:
        print("ОШИБКИ ЗАПИСИ:")
        for f in failed:
            print(f"  - {f}")
        return 1
    print("СЛОЙ ЗАПИСАН")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


