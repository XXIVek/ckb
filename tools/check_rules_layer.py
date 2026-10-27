"""Проверка доступности и целостности слоёв правил (узлы RULE-LAYER, RULE-V2).

Отвечает на два вопроса, а не на один:

  1. «если AI-ассистент попросит это правило, он его получит?» — достижимость адресом по
     своей категории, изоляция чужой категорией, запись в базу тех ручных алиасов, которые
     карточка объявляет разделом `===ALIASES===`. Алиасы из адреса не выводятся: точный
     алиасный шаг дал бы шум по словам `core`, `rules`, `index`; но термин, которого в адресе
     нет («правила загрузки», «шаг 0»), обязан быть записан — иначе правило обещает поиск,
     которого не делает;
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
     `source_url` = `rules-layer://<адрес>`; теги несут категорию и состояние; если у слоя есть
     исходник `docs/rules/<метка>.md`, текст строки БД сверяется с ним (правка правила идёт в
     исходник, в базу её переносит мигратор);
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
поведением MCP-сервера (это tools/check_search_rules_sync.py и валидаторы узлов), и то, насколько
выбранные ручные алиасы действительно совпадают с тем, как правило ищут словами: запись алиаса и
его границы (не адрес, без метки слоя, не совпадает с адресом карточки) проверяются, выбор
формулировки — нет.

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
    """Карточки слоя из БД: вопрос (он же адрес), ответ, теги, source_url, алиасы строки.

    Отбор — по грамматике адреса, а не по категории: категория меняется при переходе слоя на
    формат 2 (у правил появляется своя), а принадлежность слою задаёт адрес. Префикс метки для
    дерева адресов не работает (замер 27.10.2026): прежний отбор `question LIKE '<метка>:%'` под
    метками `core-rules`, `enrich-rules`, `export-rules` не отдавал НИ ОДНОЙ живой строки, под
    `kb-rules` отдавал 9 строк прежней формы — все помеченные к удалению, — а под корнем `rules`
    собирал разом 219 строк всех пяти слоёв. Живых строк прежней формы в базе ноль: правила
    живут деревом (`rules:<слой>:...`), и отбор идёт теми же границами, что и `layer_of`.

    Карточки, помеченные к удалению (узел Q1), не отдаются: скрытая строка правилом не является,
    и требовать от снимка соответствия действующим правилам — тот же дефект, который
    `src/quarantine.py` снял в поиске; проверка обязана читать то же условие, что и поиск, а не
    свою копию.

    Алиасы отдаются списком имён через `|`, а не числом: сравнение «что объявлено в тексте
    карточки» и «что записано в базе» по числу не проверяется — два разных набора дают одинавое
    число, и расхождение не всплывает никогда.
    """
    from quarantine import MARK_ARRAY, sql_not_marked

    columns = ("SELECT id, question, answer, tags, source_url, "
               "(SELECT string_agg(a.alias_name, '|' ORDER BY a.alias_name) FROM alias_targets a "
               "WHERE a.snippets_id = knowledge_snippets.id) AS aliases "
               "FROM knowledge_snippets")
    where, params = RL.layer_sql(marker)
    cur.execute(
        f"{columns} WHERE {where} AND source_url LIKE %s" + sql_not_marked(),
        (*params, RL.SOURCE_SCHEME + "%", MARK_ARRAY),
    )
    return [dict(row) for row in cur.fetchall()]


def alias_names_of(row):
    """Множество алиасов строки из колонки `aliases` (string_agg через '|')."""
    return {name for name in (row.get("aliases") or "").split("|") if name}


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
        # Ручные алиасы карточки (===ALIASES===) проверяются и здесь: формат слоя на доступность
        # алиаса не влияет — объявленный алиас обязан быть в alias_targets в любом формате.
        declared = RL.aliases_of(card["answer"])
        missing_aliases = sorted(set(declared) - alias_names_of(row))
        check(not missing_aliases,
              f"[{marker}] {card['address']}: объявленные алиасы записаны в базу",
              f"нет в alias_targets: {missing_aliases[:5]} — правило называет термин, по которому "
              f"его не найти")
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
    # Алиасы карточек подслоёв пишет генератор прямо в `alias_targets`, а не разделом
    # `===ALIASES===` текста (так устроены `card_aliases` в `_make_layer_rule_cards.py`).
    # Предупреждать о «лишних» алиасах на каждой такой карточке — значит печатать десятки строк
    # шума (замер 28.10.2026: 87 строк на прогоне) и не сказать при этом, где карточка реально
    # объявляет алиасы текстом. Различие называется счётчиком итога слоя, а не молчанием.
    alias_declared_text = 0
    alias_generated_only = 0

    # В базе одновременно живут две модели записи правил, и проверка обязана называть, по какой
    # из неё она проверяет конкретную карточку:
    #   • модель состояний (узел RULE-V2): состояние стоит сегментом после метки слоя
    #     (`rules:always:index`, `rules:kb-rules:checks:index`) — она требует разделов по
    #     состоянию, таблиц индекса состояния и бюджета `always`;
    #   • модель типов узла (узел RULE-TREE): тип узла следует из его МЕСТА в дереве
    #     (`rules:<слой>:<правило>`) — по ней записаны правила подслоёв, и состояний в их
    #     адресах нет по построению (решение оператора 25.10.2026: «всегда» пишется телом
    #     карточки, вариативное правило имеет собственное имя на своём уровне).
    # Решение принимается по каждой карточке, а не по слою целиком: в слое `kb-rules` живут и
    # карточки состояний (`:checks:index`, `:journal`), и правила дерева; прежняя попытка решить
    # за слой дала 21 провал «адрес вне состояний слоя» там, где состояния нет по модели (замер
    # 27.10.2026). Различие называется печатью, а не снимается молча: пропущенная проверка
    # отличается от пройденной тем, что читатель знает, чем итог не подтверждён.
    # Модель состояний задаёт требования к карточке только там, где она записана, — этим слоем:
    # корнем (`rules:always:*`, `rules:checks:*`, `rules:reserved:*`). Подслои записаны моделью
    # типов узла, и сегменты `checks` / `journal` у них — служебные ветки дерева
    # (RESERVED_SEGMENTS в src/rules_layer.py), а не состояния: решение по сегменту адреса
    # потребовало бы от карточек подслоя разделов состояния и тега состояния, которых генератор
    # дерева не пишет (замер 27.10.2026: после перевода подслоёв на формат 2 это дало ~100
    # провалов вида «нет ===WHEN» и «тег состояния journal на карточке»). Теги вида узла для
    # подслоя проверяет `_layer_tree_check.py`, разделы дерева — тоже он.
    state_model = marker == RL.ROOT_MARKER
    states = {a: RL.state_of(RL.layer_relative(a, RL.layer_of(a) or marker)) for a in by_address}
    if not state_model:
        print(f"[{marker}] слой записан моделью типов узла: состояния в адресах подслоя отсутствуют "
              f"по построению ({len(by_address)} карточек) — разделы по состоянию, таблицы индекса "
              f"состояния, тег состояния и бюджет `always` к слою НЕ ПРИМЕНЕНЫ, а не пройдены; их "
              f"проверяет _layer_tree_check.py. Здесь остаются проверки, от модели не зависящие: "
              f"грамматика адреса, ключ идемпотентности, тег категории, разрешаемость ссылок, "
              f"достижимость своей категорией и изоляция чужой.")

    for address in sorted(by_address):
        row = by_address[address]
        row_marker = RL.layer_of(address) or marker
        rel = RL.layer_relative(address, row_marker)
        state = states[address]
        problems = RL.validate_address(rel, row_marker)
        check(not problems, f"[{marker}] {address}: адрес в грамматике и в состоянии",
              "; ".join(problems[:3]))
        check(row["source_url"] == RL.source_url(address),
              f"[{marker}] {address}: source_url остаётся ключом идемпотентности",
              f"в строке {row['source_url']!r}")
        tags = set(row["tags"] or [])
        check(primary in tags, f"[{marker}] {address}: тег категории слоя на карточке",
              f"теги {sorted(tags)} — без него слой не изолируется фильтром")
        if state_model and state:
            check(state in tags, f"[{marker}] {address}: тег состояния {state} на карточке",
                  f"теги {sorted(tags)}")
        if state != RL.STATE_JOURNAL:
            # Ручные алиасы карточки (решение оператора 24.10.2026): правило ищут не только
            # адресом. Проверка односторонняя намеренно — объявленный в карточке алиас обязан
            # быть в базе (иначе правило обещает термин, которого поиск не знает), а обратное
            # отношение молча ломало бы журнал и следы переименований: снять алиас инструментом
            # нельзя (алиасы добавляются аддитивно), поэтому лишние — предупреждение, а не провал.
            declared = RL.aliases_of(row["answer"])
            bad = []
            for alias in declared:
                bad += RL.validate_alias(alias, row_marker, by_address.keys())
            check(not bad, f"[{marker}] {address}: ручные алиасы карточки допустимы",
                  "; ".join(bad[:3]))
            missing_aliases = sorted(set(declared) - alias_names_of(row))
            check(not missing_aliases,
                  f"[{marker}] {address}: объявленные алиасы записаны в базу",
                  f"нет в alias_targets: {missing_aliases[:5]} — карточка называет термин, "
                  f"по которому её не найти (тот же дефект, что правило, не названное в индексе)")
            extra = sorted(alias_names_of(row) - set(declared))
            if RL.ALIASES_SECTION in RL.section_bodies(row["answer"]):
                alias_declared_text += 1
                if extra:
                    print(f"  ⚠️ {address}: алиасов в базе больше, чем объявлено в карточке: "
                          f"{extra[:5]} — следы переименований допустимы; снять лишний алиас можно "
                          f"только строкой alias_targets (инструмент их лишь добавляет)")
            else:
                # Карточка алиасы текстом не объявляет — их задаёт генератор слоя. Называть их
                # «лишними» нельзя: ровно эти строки и делают карточку находимой словами
                # оператора (узел EDIT-CALL), а текстового объявления у них нет по построению.
                alias_generated_only += 1
        if state_model and state is not None:
            # Требования к разделам задаются состоянием карточки, а у карточки модели типов узла
            # состояния нет (узел RULE-TREE). Разделы дерева — WHEN/CHECK/TOOL — проверяет
            # `_layer_tree_check.py`; здесь они не проверяются НИКАК, и это названо печатью выше,
            # а не снято молча.
            missing = [s for s in RL.required_sections(rel)
                       if s not in RL.sections_of(row["answer"])]
            check(not missing, f"[{marker}] {address}: разделы карточки на месте",
                  f"нет {', '.join('===' + s for s in missing)} — без WHEN правило не применимо, "
                  f"без CHECK его нечем подтвердить")
            if state == RL.STATE_RESERVED:
                check(len(row["answer"] or "") <= RL.RESERVED_MAX_CHARS,
                      f"[{marker}] {address}: резервная карточка короткая",
                      f"{len(row['answer'] or '')} > {RL.RESERVED_MAX_CHARS}: длинный текст в "
                      f"reserved означает, что правило уже написано")
    if state_model:
        check_layer_v2_indexes(marker, by_address, cross)
    # Ссылки проверяются во всех карточках слоя, а не только в индексах: в обеих моделях записи
    # ссылкой может быть любой узел (замер 27.10.2026: ограничение индексными карточками сняло
    # 24 проверки корня и перестало находить ссылки в несуществующие карточки, стоящие в
    # обычных карточках).
    check_index_links(marker, by_address, cross, all_cards=True)
    print(f"[{marker}] алиасы: текстом раздела `===ALIASES===` объявлены {alias_declared_text} "
          f"карточек (на них и работает предупреждение о лишних), {alias_generated_only} карточек "
          f"получают алиасы из генератора слоя — в тексте их нет по построению, и называть их "
          f"лишними нельзя; находимость таких карточек словами оператора проверяет "
          f"check_edit_code_trigger")
    return by_address


def check_index_links(marker, by_address, cross, all_cards=False):
    """Ссылки карточек обязаны вести в существующее правило — своего слоя или чужого.

    Проверка отделена от проверок индексов состояний намеренно: разрешаемость ссылки ничего не
    знает о модели записи (состояние это или тип узла) и остаётся требованием к обоим слоям,
    тогда как разделы, таблицы индекса и бюджет относятся только к модели состояний.

    `all_cards=True` — слой записан деревом: в модели типов узла ссылкой может быть карточка
    любого узла, а не только индекс состояния, поэтому ссылки проверяются по всем строкам слоя.

    Слой цели берётся тем же разбором, что и отбор строк (`layer_of`), а не первой частью адреса:
    у строки дерева первая часть — корень `rules`, и `marker_of` отправил бы ссылку
    `rules:core-rules:functional:x` на разрешение в корневой слой, где её нет (замер 27.10.2026
    на прежнем коде: межслойные ссылки разрешались не в тот слой).
    """
    for address in sorted(by_address):
        row = by_address[address]
        rel = RL.layer_relative(address, RL.layer_of(address) or marker)
        if not all_cards and not RL.is_index_address(rel):
            continue
        for token in RL.address_tokens(row["answer"]):
            other = RL.layer_of(token) or RL.marker_of(token)
            if other not in RL.LAYERS:
                continue
            if other == marker:
                check(RL.address_resolves(token, by_address),
                      f"[{marker}] {address}: ссылка {token} разрешается в карточку",
                      "карточка обещает правило, которого нет — та же дыра, что ссылка в никуда")
            else:
                # Источник ссылки сохраняется вместе с токеном: иначе провал припишется последней
                # карточке предыдущего цикла, а не той, что ссылку написала (замер 27.10.2026 —
                # шесть провалов были приписаны `rules:reserved:layer-migration`, где ссылок нет).
                cross.setdefault(other, []).append((token, address))

    for other, pairs in sorted(cross.items()):
        from database import get_cursor

        with get_cursor() as cur:
            theirs = {row["question"] for row in layer_rows(cur, other)}
        for token, source in sorted({(t, s) for t, s in pairs}):
            check(RL.address_resolves(token, theirs),
                  f"[{marker}] {source}: межслойная ссылка {token} разрешается",
                  f"в слое {other!r} такой карточки нет: маршрут обрывается на середине")


def check_layer_v2_indexes(marker, by_address, cross):
    """Индексы слоя формата 2: бюджет always, таблица с колонкой проверки, существование
    каждого названного артефакта и каждой названной ссылки."""
    # Бюджет считается относительными адресами: `always_budget` ищет префикс `<метка>:always`,
    # а строки подслоя записаны под путём `rules:<метка>:…` (замер 27.10.2026: по полным адресам
    # дерева бюджет подслоя дал бы ноль даже при наличии карточек `always`).
    total, always_cards = RL.always_budget(
        marker, [(RL.layer_relative(address, marker), row["answer"])
                 for address, row in by_address.items()])
    check(total <= RL.ALWAYS_BUDGET_CHARS,
          f"[{marker}] бюджет always в пределах порога",
          f"{total} > {RL.ALWAYS_BUDGET_CHARS} символов по {len(always_cards)} карточкам "
          f"({', '.join(always_cards[:6])}): «всегда», которое не читается за один заход, "
          f"не применяется — перенеси правило в optional или раздели его")

    for address in sorted(by_address):
        row = by_address[address]
        rel = RL.layer_relative(address, marker)
        if not RL.is_index_address(rel):
            continue
        state = RL.state_of(rel)
        if state is None:
            # Индекс слоя (`rules:index`) живёт над состояниями и не обязан перечислять
            # карточку-корень: корень — родитель индекса, а не его содержимое. Полноту перечня
            # дерева проверяет `_layer_tree_check.py` (раздел `===INDEX`), а не этот шаг.
            continue
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
        # Ссылки индексов проверяет `check_index_links` — отдельной проверкой, потому что
        # требование «ссылка ведёт в существующее правило» не зависит от модели записи, а
        # разделы состояний, таблицы индекса и бюджет зависят только от модели состояний.
        # индекс состояния обязан перечислить его карточки: строка, которой нет в оглавлении,
        # существует в слое и не находится префиксным шагом — ровно та дыра, из-за которой
        # «правило есть, но его не найти» (граница «карточка обязана называться в оглавлении»)
        listed = {cell.strip().strip("`").strip()
                  for table in tables for line in table["rows"] if line for cell in line[:1]}
        for own in sorted(by_address):
            own_rel = RL.layer_relative(own, marker)
            if RL.state_of(own_rel) != state or RL.is_index_address(own_rel):
                continue
            check(any(RL.address_resolves(tok, {own}) for tok in listed if tok),
                  f"[{marker}] {address}: карточка {own} названа в индексе состояния",
                  "карточка есть в слое и не перечислена — по индексу до неё не дойти")

    print(f"[{marker}] модель состояний: карточек {len(by_address)}, "
          f"always {len(always_cards)} на {total}/{RL.ALWAYS_BUDGET_CHARS} симв., "
          f"журнал {sum(1 for a in by_address if RL.state_of(RL.layer_relative(a, marker)) == RL.STATE_JOURNAL)}, "
          f"резерв {sum(1 for a in by_address if RL.state_of(RL.layer_relative(a, marker)) == RL.STATE_RESERVED)}")
    return by_address


# ------------------------------------------------------------------ формат 2: текст ↔ исходник

def check_source_sync(marker, by_address):
    """Слой формата 2: текст строки БД обязан совпадать с исходником `docs/rules/<метка>.md`.

    Порядок правки правила — правка исходника, затем мигратор, затем эта проверка. Без неё
    рассинхрон виден только после того, как по слою начнут отвечать текстом, которого в
    исходнике нет: в БД правило одно, в git — другое, и дифф правки больше не описывает то,
    что читает ассистент.

    Отсутствующий исходник называется прямо: у слоя без файла источник — строки БД, и «тексты
    совпадают» в этом случае было бы утверждением без основания. Строки БД, которых нет в
    исходнике (журнал, прежние адреса до переименования), — не дефект: они не правятся
    мигратором, и молча снять их значит потерять историю.
    """
    path = PROJECT_ROOT / RL.RULES_DIR / f"{marker}.md"
    if not path.exists():
        print(f"[{marker}] исходника {RL.RULES_DIR}/{marker}.md нет — источник слоя только "
              f"строки БД, сверка текста НЕВОЗМОЖНА (это не «совпадает»)")
        return
    cards, errors, fatal = RL.load_document(path)
    problems = ([fatal] if fatal else []) + list(errors)
    if not check(not problems, f"[{marker}] исходник формата 2 разбирается без ошибок",
                 "; ".join(problems[:6])):
        return
    written = 0
    journal_skipped = 0
    for card in cards:
        if RL.state_of(card["address"]) == RL.STATE_JOURNAL:
            # Карточки состояния `journal` из этой сверки сняты намеренно, и это называется
            # числом, а не молчанием: их оглавление порождает tools/regen_journal_index.py по
            # фактическому составу строк журнала в БД, поэтому файл по ним отстал by design, а
            # тексты самого снимка не правятся ни там, ни там.
            journal_skipped += 1
            continue
        row = by_address.get(card["address"])
        if not check(row is not None,
                     f"[{marker}] {card['address']}: карточка исходника записана в БД"):
            continue
        written += 1
        check(row["answer"] == card["answer"],
              f"[{marker}] {card['address']}: текст БД совпадает с исходником",
              "правка правила идёт в docs/rules/<метка>.md и переносится мигратором; правка "
              "только строки БД рассинхронизирует слой с исходником")
    outside = len(set(by_address) - {c["address"] for c in cards})
    print(f"[{marker}] формат 2 ↔ исходник: карточек в файле {len(cards)}, подтверждено в БД "
          f"{written}, карточек журнала вне сверки текста {journal_skipped} (их оглавление "
          f"порождает regen_journal_index.py по строкам БД), строк БД вне файла {outside} "
          f"(журнал и прежние адреса — не дефект)")


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
        used = {RL.state_of(RL.layer_relative(a, RL.layer_of(a) or marker))
                for a in (by_address or {})}
        used.discard(None)
        # Подслой дерева записан моделью типов узла: его иерархия — префикс поддерева
        # `rules:<слой>`, а префиксы состояний существуют только там, где состояние стоит в
        # адресах карточек. Требование «индекс называет неиспользуемое состояние текстом»
        # относится к модели состояний: у слоя дерева состояний нет по построению, и требовать их
        # перечисления — значит валить правило моделью проверки (замер 27.10.2026: 3 таких провала
        # в `kb-rules` плюс провалы префиксов `kb-rules:checks`, `kb-rules:journal`).
        tree_layer = marker != RL.ROOT_MARKER
        prefixes = ([f"{RL.ROOT_MARKER}:{marker}"] if tree_layer else [])
        prefixes += [f"{RL.ROOT_MARKER}:{marker}:{s}" if tree_layer else f"{marker}:{s}"
                     for s in sorted(used)]
        for prefix in prefixes:
            found = {str(item.get("title", "")) for item in
                     search_docs(prefix, category=category, limit=50)}
            own = [t for t in found if t.startswith(prefix)]
            check(bool(own), f"[{marker}] префикс {prefix} отдаёт поддерево",
                  "путь назван маршрутом слоя, но по префиксу не читается ни одна карточка — "
                  "маршрут обрывается на середине, и обещание индекса «дальше идёшь по строкам» "
                  "не работает")
        if tree_layer:
            return
        index_text = ((by_address or {}).get(RL.index_address(marker)) or {}).get("answer") or ""
        for state in RL.LAYER_STATES:
            if state in used:
                continue
            check(RL.declares_state(index_text, state),
                  f"[{marker}] индекс называет состояние {state} неиспользуемым текстом",
                  "в слое нет карточек этого состояния и индекс о нём молчит: читатель не может "
                  "отличить «состояния нет» от «карточки забыли» (правило `rules:always:indexing`)")


# ------------------------------------------------------------------ вызов по намерению правки кода

def check_edit_code_trigger(marker, by_address, category):
    """Карточка правки кода MCP-сервера обязана подниматься словами намерения править этот код.

    Узел EDIT-CALL (28.10.2026). Карточка `rules:<слой>:functional:edit-mcp-code` существует
    затем, чтобы её подняли ДО правки кода сервера; маршрутизатор называет намерение своими
    словами, и эти слова обязаны вести в карточку. До узла карточка описывала намерение только
    прозой («Меняют код сервера …»): замер по десяти формулировкам намерения для четырёх слоёв
    дал 1 попадание из 40 — алиасный шаг поиска требует точного совпадения, поэтому пересказ
    намерения в тексте карточки находимости не создаёт.

    Проверяются оба конца цепочки: карточка называет формулировку сама (её читает оператор или
    ассистент, поднявший карточку, — и видит, при каких словах это сделано) и та же формулировка
    ведёт в карточку настоящим `search_docs` своей категорией (та же граница, что у
    `check_reachable`: своя копия предиката проверяла бы свою копию).
    """
    from mcp_tools_api import search_docs

    if marker == RL.ROOT_MARKER:
        # Корневой слой записан моделью состояний; карточка правки кода принадлежит подслою того
        # сервера, чей код правят, — лист `edit-mcp-code` выводится из метки слоя.
        return
    address = RL.edit_code_address(marker)
    row = by_address.get(address)
    if not check(row is not None, f"[{marker}] карточка правки кода MCP {address} существует",
                 "карточка правки кода слоя не записана — намерение править код сервера некуда "
                 "передать; генератор слоя обязан порождать её общим листом `edit-mcp-code`"):
        return
    text = (row["answer"] or "").lower()
    for phrase in RL.EDIT_CODE_INTENTS:
        check(phrase in text,
              f"[{marker}] {address}: текст карточки называет намерение {phrase!r}",
              "карточка не говорит, при каких словах её поднимают; правка — генератором слоя, "
              "список формулировок задаёт src/rules_layer.py (EDIT_CODE_INTENTS)")
        found = {str(item.get("title", "")) for item in
                 search_docs(phrase, category=category, limit=10)}
        check(address in found,
              f"[{marker}] намерение {phrase!r} ведёт в карточку правки кода {address}",
              f"выдача по категории {category!r}: {sorted(found)[:3]} — формулировка не записана "
              f"алиасом карточки (алиасный шаг ищет точным совпадением)")

    # Узел JOURNAL-COVERAGE (28.10.2026, план docs/RULES_CONTEXT_PLAN.md П3). Карточка правки кода
    # велит писать узел журнала об изменении состава, но до этой проверки ни один шаг не требовал
    # прочесть написанное: история изменений регистра оставалась памятью автора правки.
    # Требование — точный адрес перечня журнала, выведенный тем же хелпером, что и адрес самой
    # карточки: маска `…:journal:node:*` адресом не является (правило масок в src/rules_layer.py),
    # поэтому подстрока `journal` проверяла бы наличие буквы, а не наличие истории.
    answer = row["answer"] or ""
    journal = RL.journal_index_address(marker)
    # Слой без карточек журнала не обязан звать несуществующий перечень — он обязан назвать, что
    # снимка не ведётся (замер 28.10.2026: перечень журнала export-слоя снят узлом
    # RESTRUCTURE-LAYERS 27.10.2026 как дубль карточки второго уровня, и требование звать его
    # дало бы ссылку в никуда вместо правила).
    snapshot = [a for a in by_address
                if a != journal
                and RL.state_of(RL.layer_relative(a, marker)) == RL.STATE_JOURNAL]
    if snapshot:
        check(address_is_named(journal, set(RL.address_tokens(answer)), quoted_addresses(answer)),
              f"[{marker}] {address}: карточка называет перечень журнала своего слоя {journal}",
              "карточка не называет адрес, под которым лежит снимок слоя: следующий её шаг — писать "
              "узел об изменении состава — начинается без прочитанного, и узел повторяет уже "
              "записанное либо переоткрывает снятый инструмент")
        check(RL.address_resolves(journal, by_address),
              f"[{marker}] перечень журнала {journal} существует карточкой",
              "карточка правки кода обещает историю слоя, а перечня журнала в слое нет — "
              "читать нечего")
    else:
        check(RL.NO_SNAPSHOT_MARK.lower() in answer.lower(),
              f"[{marker}] {address}: карточка называет, что снимка журнала в слое нет",
              "в слое нет ни одной карточки журнала, а карточка правки кода об этом молчит: "
              "«истории нет» неотличимо от «историю забыли», при том что её шаг об изменении "
              "состава обещает запись в снимок, который слой не ведёт")
    check("_journal_code_history.py" in answer,
          f"[{marker}] {address}: карточка называет измеритель покрытия `_journal_code_history.py`",
          "требование писать узел журнала ничем не измеряется, поэтому пропущенный узел вскрывается "
          "только на следующей правке регистра — ровно тот дефект, который замер закрывает")
    check((PROJECT_ROOT / "_journal_code_history.py").exists(),
          "[JOURNAL-COVERAGE] измеритель `_journal_code_history.py` существует в репозитории",
          "карточки четырёх слоёв ссылаются на инструмент, которого нет: ссылка в никуда там же, "
          "где и снятый инструмент, названный живым")


# ------------------------------------------------------------------ маршрутизатор

def quoted_addresses(text):
    """Адреса, отмеченные в тексте обратными кавычками (`rules:`, `rules:kb-rules:`).

    Разбор адресов (`RL.address_tokens`) их не отдаёт: двоеточие без последующего сегмента
    токеном не является, а форма с двоеточием на конце — это и есть адрес карточки-узла дерева
    (RULE-TREE). Разбор по парным обратным кавычкам сделан без регулярки: в маршрутизаторе
    кавычки всегда парные, и лишней зависимости от `re` в проверке не было.
    """
    parts = str(text).split("`")
    return {parts[i].strip() for i in range(1, len(parts), 2)}


def address_is_named(address, tokens, quoted):
    """Назван ли адрес: токеном (`rules:kb-rules` — токен без конечного двоеточия) или
    отмеченной формой узла (`rules:kb-rules:`, `rules:`)."""
    if address in quoted:
        return True
    stem = address.rstrip(":")
    return address in tokens or bool(stem) and stem in tokens


def check_router(markers_written):
    """Маршрутизатор `.clinerules/1C_Rule.md` обязан называть вход в каждый записанный слой:
    иначе правило существует, а до него не дойти — ровно тот дефект, против которого индекс
    заведён. Отдельно проверяется вход в само дерево: с него начинается путь к любому слою, и
    если его нет, карта меток превращается в перечень без входа.

    Названным адрес считается только как адрес, а не как подстрока: замер 24.10.2026 показал,
    что проверка `root in text` проходила, когда корневого индекса в маршрутизаторе не было
    вовсе, — подстроку давал `core-rules:index`. Разбор берётся тот же, что у ссылок индексов
    (`RL.address_tokens`), плюс отмеченные кавычками формы узла.

    Принимаются обе формы входа, и это не послабление порога, а описание двух состояний дерева:
    карточка второго уровня `rules:<слой>:` (узел RULE-TREE) и прежний индекс `<метка>:index` у
    слоёв, которые ещё не переразвёрнуты. Требование одно: до записанного слоя из всегда
    загружаемого текста можно дойти адресом.
    """
    if not check(ROUTER.exists(), "маршрутизатор .clinerules/1C_Rule.md существует"):
        return
    text = ROUTER.read_text(encoding="utf-8")
    tokens = set(RL.address_tokens(text))
    quoted = quoted_addresses(text)
    root_entries = (f"{RL.ROOT_MARKER}:", RL.index_address(RL.ROOT_MARKER))
    check(any(address_is_named(a, tokens, quoted) for a in root_entries),
          "маршрутизатор называет вход в дерево правил (`rules:` или прежний `rules:index`)",
          "иерархический вход в правила записан, но из всегда загружаемого текста до него не дойти")
    for marker in markers_written:
        if marker == RL.ROOT_MARKER:
            continue
        entries = (f"{RL.ROOT_MARKER}:{marker}:", RL.index_address(marker))
        check(any(address_is_named(a, tokens, quoted) for a in entries),
              f"маршрутизатор называет вход в слой {marker} "
              f"(`{entries[0]}` или прежний `{entries[1]}`)",
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
                # Текст слоя формата 2 сверяется с исходником: правка правила идёт в файл,
                # а в БД её переносит мигратор, и расхождение файла с базой — это два разных
                # правила на один адрес.
                if by_address:
                    check_source_sync(marker, by_address)
                # журнал из проверки адресной достижимости убран намеренно: его читают префиксом
                # состояния (его проверяет ветка hierarchical), а не каждым заголовком — в
                # заголовках журнала пробелы и прежняя орфография, это снимок, а не адрес правила
                addresses = [a for a in sorted(by_address) if RL.state_of(a) != RL.STATE_JOURNAL]
                check_reachable(marker, addresses, category, True, by_address)
                # Узел EDIT-CALL: отдельной проверкой, а не внутри `check_reachable`, потому что
                # проверяется другое: не «адрес читается адресом», а «слова намерения править код
                # сервера ведут в карточку правки кода». Первая проверяется и без намерения,
                # вторая без намерения не существует.
                check_edit_code_trigger(marker, by_address, category)
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




