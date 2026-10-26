"""Дамп правил дерева правил в файл (узел RULE-REPORT, 25.10.2026).

Зачем. Дерево правил читают сверху вниз: корневая карточка, первая карточка слоя, правило.
Двухфазное чтение адресом (`search_docs_tool` → `get_snippet_tool`) отдаёт по одной карточке за
вызов, и дерева по нему не видно. Отчёт делает ровно то, что нужно для чтения: выбирает карточки
по алиасу уровня, перечисляет их таблицей с id и выкладывает содержимое заголовками по уровню
адреса. Больше он ничего не делает.

Чего в отчёте нет. Пометок, вердиктов, перечня «что бросается в глаза», сравнения с эталоном.
Мы читаем правила и правим их по дереву; проверки — отдельный шаг, он строится после того, как
дерево переразвёрнуто (`tools/check_rules_layer.py`), и в отчёт не вмешивается.

Разделение правил и отдельных сущностей. `journal` и `checks` — не правила (`RESERVED_SEGMENTS` и
`node_kind` в `src/rules_layer.py`), поэтому в основной таблице и в основном теле их нет: снимок
прежних текстов и способ проверять правило, поставленные в один ряд с правилами, читаются как
действующие правила (так возвращался в работу прежний контракт поиска). В конце файла они выложены
отдельными разделами `===CHECKS` и `===JURNAL` — там же, где они стоят в дереве.

Как выбираются карточки. Алиасом уровня: `rules:` — всё дерево, `rules:kb-rules:` — поддерево
слоя. Пока алиасов уровня в базе нет, выбор падает на метку слоя (если назвали именно её) или на
тег `rules-layer` — он есть у каждой карточки дерева. Способ выбора печатается одной строкой в
шапке: список из сотни карточек иначе читается как «столько правил и существует».

Порядок карточек — порядок дерева (pre-order по адресам), а не алфавит: часть `ref:002` обязана
идти после `ref:001`. Обычная сортировка строк поставила бы `ref:010` раньше `ref:002`, и части
большого описания переставились бы молча.

Заголовки. Уровень заголовка = число сегментов адреса (`rules:` → H1, `rules:kb-rules:` → H2,
правило → H3, часть `ref:NNN` → H4). Узел, у которого в выборке есть дети, записывается с
двоеточием на конце — это форма осмотра, в БД она не хранится. Глубже `MAX_ADDRESS_SEGMENTS`
заголовка нет: такая карточка даётся меткой адреса текстом.

Содержимое карточки переносится дословно. Правка делается в строке БД (правило проекта «правим
только в базе»), после чего отчёт перегоняют — и правку видно в файле.

Варианты отчёта (узел RULE-REPORT-VARIANTS, 26.10.2026)
-------------------------------------------------------
Один файл на все случаи прочитывается как «всё подряд»: правила, перечни ссылок, снимок прежних
текстов и способ проверки в одном потоке неотличимы от действующих правил, а человек, который
правит правило, ищет в файле только правило. Поэтому у отчёта шесть вариантов, и выбираются они
флагом `-v/--variant` (номер или имя); по умолчанию — вариант 1.

  1 `rules`    — только правила: текст карточек всех уровней, без журнала и проверок, и без
                 разделов-ссылок (`===LINKS`, `===INDEX`). Это то, что может попасть в файл
                 правил; им же правится и читается дерево.
  2 `links`    — правила с перечнем ссылок: те же карточки, но разделы `===LINKS`/`===INDEX`
                 даны дословно. Вариант для проверки «все ли ссылки учтены в карточке второго
                 уровня», то есть для осмотра дерева, а не для чтения правила; выводится по
                 требованию.
  3 `full`     — полный отчёт: всё поддерево, включая журнал и проверки (разделы `===CHECKS` и
                 `===JURNAL` в конце).
  4 `level2`   — карта дерева: корневая карточка и карточки второго уровня (как построено дерево
                 целиком; правила третьего уровня в неё не кладутся).
  5 `journal`  — только карточки журнала (снимок прежних текстов).
  6 `checks`   — только карточки проверок.

Граница варианта 1 проходит по разделам, а не по тексту: `===LINKS` и `===INDEX` вырезаются от
строки маркера до следующего маркера, вместе с подписью таблицы и пометками, которые лежат после
неё. Эти пометки («журнал и проверки в перечень правил не кладутся») относятся к перечню, а не к
правилу, — поэтому они остаются в варианте 2 (решение оператора 26.10.2026). Общая часть карточки
до первого маркера и разделы `===WHEN`/`===MCP` не вырезаются: это содержание правила.

Имя файла несёт вариант, кроме значения по умолчанию: `rules.md`, `rules_links.md`, `rules_full.md`,
`rules_level2.md`, `rules_journal.md`, `rules_checks.md`. Иначе два разных отчёта спорили бы за
один файл, а прочитанный файл нельзя было бы отличить от снятого.
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _p in (PROJECT_ROOT / "src",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import rules_layer as RL  # noqa: E402
from quarantine import (MARK_ARRAY, is_marked, marked_flag, sql_not_marked)  # noqa: E402

REPORTS_DIR = PROJECT_ROOT / "Reports"
LAYER_TAG = "rules-layer"   # тег есть у каждой карточки дерева: им выбирается всё дерево
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.\-]+")
_MD_SUFFIX_RE = re.compile(r"(?:[_.-]?(?:rule|rules|правил\w*)\.md|\.md)$", re.IGNORECASE)

# ------------------------------------------------------------------ варианты отчёта
# Вариант отвечает на два вопроса: какие карточки лежат в файле и что из текста карточки печатается.
# Номера — часть обращения к человеку (их называют в разговоре и в правилах слоя), имена — часть
# обращения к коду; оба принимаются одинаково.
VARIANT_RULES = "rules"
VARIANT_LINKS = "links"
VARIANT_FULL = "full"
VARIANT_LEVEL2 = "level2"
VARIANT_JOURNAL = "journal"
VARIANT_CHECKS = "checks"

VARIANTS = {
    VARIANT_RULES: ("1", "только правила",
                    "текст правил всех уровней; журналов, проверок и перечней ссылок нет"),
    VARIANT_LINKS: ("2", "правила с перечнем ссылок",
                    "правила дословно, включая ===LINKS и ===INDEX: проверять, все ли ссылки учтены"),
    VARIANT_FULL: ("3", "полный отчёт",
                   "всё поддерево, журнал и проверки отдельными разделами в конце"),
    VARIANT_LEVEL2: ("4", "карта дерева: корень и второй уровень",
                     "корневая карточка и карточки слоёв: как построено дерево правил целиком"),
    VARIANT_JOURNAL: ("5", "только журнал",
                      "карточки journal: снимок прежних текстов слоя"),
    VARIANT_CHECKS: ("6", "только проверки",
                     "карточки checks: чем доказывать, что правило ещё верно"),
}
# Порядок перечисления в подсказке и в шапке ошибки: порядок вариантов, а не алфавит имён.
VARIANT_ORDER = (VARIANT_RULES, VARIANT_LINKS, VARIANT_FULL, VARIANT_LEVEL2,
                 VARIANT_JOURNAL, VARIANT_CHECKS)
VARIANT_SUFFIX = {VARIANT_RULES: "", VARIANT_LINKS: "_links", VARIANT_FULL: "_full",
                  VARIANT_LEVEL2: "_level2", VARIANT_JOURNAL: "_journal",
                  VARIANT_CHECKS: "_checks"}
# Разделы, которые в варианте 1 считаются перечнем ссылок, а не содержанием правила.
LINK_SECTIONS = frozenset({"LINKS", "INDEX"})
# Маркер раздела — только отдельной строкой и только целиком (`===LINKS`, `===LINKS===`). Искать
# подстрокой нельзя: в правилах есть фразы вроде «перечень `===LINKS` ниже ведёт», и первая такая
# фраза обрезала бы раздел посреди текста (замер 25.10.2026 на карточках второго уровня).
_SECTION_MARK = re.compile(r"^===[ \t]*([A-Z][A-Z0-9_]*)[ \t]*(?:===)?[ \t]*$", re.MULTILINE)


def variant_tokens():
    """Как можно назвать вариант: номер, имя, русскую формулировку."""
    tokens = {}
    for key, (number, title, _note) in VARIANTS.items():
        tokens[number] = key
        tokens[key] = key
        for word in title.split():
            if len(word) > 3:
                tokens.setdefault(word.lower(), key)
    tokens.update({"links": VARIANT_LINKS, "ссылок": VARIANT_LINKS, "ссылки": VARIANT_LINKS,
                   "полный": VARIANT_FULL, "всё": VARIANT_FULL, "все": VARIANT_FULL,
                   "второй": VARIANT_LEVEL2, "уровень2": VARIANT_LEVEL2,
                   "карта": VARIANT_LEVEL2, "построение": VARIANT_LEVEL2,
                   "журнал": VARIANT_JOURNAL, "журнала": VARIANT_JOURNAL,
                   "проверки": VARIANT_CHECKS, "проверок": VARIANT_CHECKS,
                   "правила": VARIANT_RULES})
    return tokens


def resolve_variant(value):
    """Значение флага -> ключ варианта. Неизвестное — отказ со списком, а не молчаливый выбор.

    Подставить вариант по умолчанию вместо неразобранного значения нельзя: человек получил бы файл
    одного варианта, думая, что назвал другой (именно так читается молча проигнорированный флаг).
    """
    token = str(value or "").strip().lower()
    if not token:
        return VARIANT_RULES
    found = variant_tokens().get(token)
    if found is None:
        raise ValueError(
            f"неизвестный вариант {value!r}; доступны: "
            + "; ".join(f"{VARIANTS[key][0]} — {key} ({VARIANTS[key][1]})" for key in VARIANT_ORDER))
    return found


def describe_variant(variant):
    """Строка варианта для шапки файла: номер и название — то, что видно в разговоре."""
    number, title, note = VARIANTS[variant]
    return f"вариант {number} ({title}) — {note}"



# ------------------------------------------------------------------ выбор карточек

def normalize_query(query):
    """Нормальная форма запроса: строчные, без пробелов, без хвоста имени файла правил.

    Двоеточие сохраняется намеренно: `rules:` (алиас уровня) и `rules` (слово) — разные запросы.
    Хвост `_Rule.md` снимается затем, что человек называет правило так, как видит его в
    `.clinerules/`.
    """
    text = re.sub(r"\s+", "", str(query or "")).lower()
    return _MD_SUFFIX_RE.sub("", text)


def _rows(cur, sql, params):
    cur.execute(sql, params)
    return [dict(row) for row in cur.fetchall()]


def by_alias(cur, alias, include_marked=False):
    """Карточки, объявившие алиас уровня (`rules:`, `rules:kb-rules:`).

    Совпадение точное, как в алиасном шаге `search_docs_tool`: алиас носит каждая карточка
    поддерева, поэтому один запрос отдаёт всё поддерево разом.
    """
    return _rows(
        cur,
        "SELECT DISTINCT s.id, s.question, s.answer, s.tags, s.source_url "
        "FROM alias_targets a JOIN knowledge_snippets s ON s.id = a.snippets_id "
        "WHERE LOWER(a.alias_name) = LOWER(%s) AND s.source_url LIKE %s"
        + ("" if include_marked else sql_not_marked("s.tags")),
        ((alias, RL.SOURCE_SCHEME + "%") if include_marked
         else (alias, RL.SOURCE_SCHEME + "%", MARK_ARRAY)),
    )


def by_addresses(cur, addresses, include_marked=False):
    """Карточки по точным адресам — для родительской цепочки карты дерева."""
    if not addresses:
        return []
    return _rows(
        cur,
        "SELECT id, question, answer, tags, source_url FROM knowledge_snippets "
        "WHERE question = ANY(%s) AND source_url LIKE %s"
        + ("" if include_marked else sql_not_marked()),
        ((list(addresses), RL.SOURCE_SCHEME + "%") if include_marked
         else (list(addresses), RL.SOURCE_SCHEME + "%", MARK_ARRAY)),
    )


def ancestor_addresses(address):
    """Родители адреса: `rules:core-rules:functional:x` → `rules:`, `rules:core-rules:`,
    `rules:core-rules:functional:`.

    Цепочка нужна затем, что карта по срезу одного слоя показывала бы слой, но не показывала бы,
    чем он является в построении правил: корневая карточка лежит вне запрошенного среза и в срез
    не попадёт никогда (запрос оператора 26.10.2026 — «видеть всё построение ролей»). Родителей
    берут отдельным запросом по точным адресам, а не расширяют срез до целого дерева: расширение
    отдало бы правила чужих слоёв под видом запрошенного.
    """
    parts = address.split(":")
    parents = []
    for i in range(1, len(parts)):
        parent = ":".join(parts[:i]) + ":"
        if parent != address and parent not in parents:
            parents.append(parent)
    return parents



def by_marker(cur, marker, include_marked=False):
    """Карточки слоя по началу адреса: дерево `rules:<метка>:` и прежняя форма `<метка>:`.

    Корневая карточка слоя — сама метка (`rules:`), а не `rules:<что-то>`, поэтому она попадает в
    выборку отдельным условием: без него дамп дерева начинался бы со второй карточки. Для слоя,
    переразвёрнутого в дерево, корнем служит `rules:<метка>:` — без этого условия дамп слоя
    состоял бы из одних прежних строк (замер 26.10.2026: `--query 1c-configurations-core` отдал
    одну карточку вместо поддерева). Прежняя форма оставляется вторым префиксом: у слоя, который
    ещё не переразвёрнут, карточек больше нет нигде, и «правил нет» был бы неправдой.
    """
    tree = marker if marker == RL.ROOT_MARKER else f"{RL.ROOT_MARKER}:{marker}"
    prefixes = []
    for prefix in (tree, marker):  # дубликат только у корня: `rules` == `rules`
        if prefix not in prefixes:
            prefixes.append(prefix)
    clauses, params = [], []
    for prefix in prefixes:
        clauses.append("(question = %s OR question = %s OR question LIKE %s)")
        params += [prefix, prefix + ":", prefix + ":%"]
    return _rows(
        cur,
        "SELECT id, question, answer, tags, source_url FROM knowledge_snippets "
        "WHERE (" + " OR ".join(clauses) + ") AND source_url LIKE %s"
        + ("" if include_marked else sql_not_marked()),
        (tuple(params) + (RL.SOURCE_SCHEME + "%",)) if include_marked
        else (tuple(params) + (RL.SOURCE_SCHEME + "%", MARK_ARRAY)),
    )


def by_tag(cur, tag=LAYER_TAG, include_marked=False):
    """Всё дерево правил по тегу слоя — ответ, когда алиасов уровня в базе ещё нет.

    Тело этой ветви отсутствовало (функция возвращала `None`), и запасной способ выбора не работал
    молча: запрос без алиасов уровня отвечал «не выбрано ни одной карточки» вместо того, чтобы
    отдать дерево по тегу (замечено 25.10.2026).
    """
    return _rows(
        cur,
        "SELECT id, question, answer, tags, source_url FROM knowledge_snippets "
        "WHERE %s = ANY(tags) AND source_url LIKE %s"
        + ("" if include_marked else sql_not_marked()),
        ((tag, RL.SOURCE_SCHEME + "%") if include_marked
         else (tag, RL.SOURCE_SCHEME + "%", MARK_ARRAY)),
    )


def select_cards(cur, query, include_marked=False):
    """Запрос -> (карточки, как выбрали). Пустой выбор — отказ, а не пустой файл.

    Очерёдность значимая и различает два написания одного корня:

    • `rules:` (с двоеточием) — алиас уровня: выборка по нему отдаёт поддерево, когда алиасы
      уровня есть у карточек дерева;
    • `rules` (без двоеточия) — метка слоя: выборка по метке отдаёт слой целиком, включая саму
      корневую карточку.

    Перепутать их местами нельзя: алиас корня существует всегда, и он перехватывал бы запрос
    слоя, оставляя от него одну карточку (так и было до правки 25.10.2026). Пустой файл
    прочитался бы как «правил нет», а не как «я назвал не то».

    Тот же порядок относит разбор кода MCP и начала адреса ВЫШЕ общего алиасного шага: алиасом
    кода сервера (`1c-configurations-core`) обладает карточка слоя, и алиасный шаг по такому
    запросу отдал бы одну карточку вместо поддерева его правил (замер 26.10.2026). Общий алиас
    остаётся последним — он для терминов, которых нет ни в метках, ни в кодах.
    """
    text = normalize_query(query)
    if not text:
        return [], "пустой запрос: нужен алиас уровня (`rules:`), метка слоя или код MCP"

    if text.endswith(":"):
        rows = by_alias(cur, text, include_marked)
        if rows:
            return rows, f"алиас {text}"
    if text.rstrip(":") in RL.markers():
        marker = text.rstrip(":")
        return by_marker(cur, marker, include_marked), f"метка слоя {marker}"
    for marker in RL.markers():
        if text.startswith(marker + ":"):
            return (by_marker(cur, marker, include_marked),
                    f"метка слоя {marker} (по началу адреса)")
    for marker in RL.markers():
        for category in RL.categories_of(marker):
            if text == category.lower() or category.lower().startswith(text):
                return (by_marker(cur, marker, include_marked),
                        f"код MCP {category} (слой {marker})")
    rows = by_alias(cur, text, include_marked)
    if rows:
        return rows, f"алиас {text}"

    rows = by_tag(cur, LAYER_TAG, include_marked)
    if rows:
        return rows, f"тег {LAYER_TAG!r} — всё дерево правил (алиасов уровня у карточек ещё нет)"
    return [], (f"по запросу {query!r} не выбрано ни одной карточки; известные слои: "
                f"{', '.join(RL.markers())}")


# ------------------------------------------------------------------ порядок и заголовки

def _segment_key(segment):
    """Ключ сегмента: числовые имена (`ref:002`, `06`) сортируются числами, а не строками."""
    return (0, int(segment)) if segment.isdigit() else (1, segment)


def tree_key(address):
    """Порядок дерева (pre-order): сначала родитель, потом дети по возрастанию имён."""
    return tuple(_segment_key(p) for p in address.split(":") if p)


def parents_with_children(rows):
    """Родители, чьи дети есть в выборке: нужно, чтобы заголовок узла получил двоеточие."""
    return {RL.parent_prefix(row["question"]) for row in rows
            if RL.parent_prefix(row["question"])}


def render_card(row, has_children):
    """Одна карточка: заголовок своего уровня и содержимое дословно."""
    address = row["question"]
    level = RL.heading_level(address)
    title = (RL.node_marker(address) if has_children else address) + marked_flag(row.get("tags"))
    lines = []
    if level:
        lines.append(f"{'#' * level} {title}")
    else:
        lines.append(f"**{title}**")
        lines.append(f"_уровней {RL.levels_of(address)}, заголовка глубже "
                     f"{RL.MAX_ADDRESS_SEGMENTS} не бывает — карточка дана текстом_")
    lines.append("")
    body = (row.get("answer") or "").rstrip()
    lines.append(body if body else "_содержимого в строке нет_")
    lines.append("")
    return "\n".join(lines)


def split_by_kind(rows):
    """Правила, проверки, журнал — три списка.

    Отдельные сущности дерева узнаются по `node_kind`, а не по имени карточки: `journal` и `checks`
    — служебные сегменты адреса (`RESERVED_SEGMENTS`), и правило, названное таким сегментом,
    разрушило бы различение «правило» и «сущность». Снимок прежних правил, поставленный в один ряд с
    правилами, читается как действующее правило — тот же класс дефекта, что перечень, где скрытая
    строка стоит рядом с живой.
    """
    rules, checks, journal = [], [], []
    for row in rows:
        kind = RL.node_kind(row["question"])
        if kind == RL.KIND_JOURNAL:
            journal.append(row)
        elif kind == RL.KIND_CHECKS:
            checks.append(row)
        else:
            rules.append(row)
    return rules, checks, journal


def pick_cards(rows, variant):
    """Карточки варианта из выбранного поддерева.

    Граница «правило / не правило» одна для всех вариантов и берётся из `node_kind`: вариант меняет
    только то, что попадает в файл, а не то, что считается правилом (иначе один и тот же снимок
    журнала читался бы правилом в одном файле и снимком — в другом).
    """
    if variant == VARIANT_FULL:
        return list(rows)
    if variant in (VARIANT_RULES, VARIANT_LINKS):
        return split_by_kind(rows)[0]
    if variant == VARIANT_LEVEL2:
        # Карта строится от корня: без карточки уровня 1 видно только слой, а не то, как он вложен
        # в `rules:` и чем отличается от соседних слоёв (запрос оператора 26.10.2026 — «видеть всё
        # построение ролей»; в адресной грамматике корень — уровень 1). Имя ключа `level2` и суффикс
        # файла сохранены: номер варианта — часть договорённости с человеком, а имя функции — нет.
        return [row for row in rows if RL.levels_of(row["question"]) <= 2]
    kind = RL.KIND_JOURNAL if variant == VARIANT_JOURNAL else RL.KIND_CHECKS
    return [row for row in rows if RL.node_kind(row["question"]) == kind]


def drop_sections(text, names=LINK_SECTIONS):
    """Текст карточки без названных разделов: от строки маркера до следующего маркера.

    Так вариант 1 отдаёт содержание правила, не показывая перечень, по которому дерево разворачивают.
    Граница проходит по маркерам, а не по строкам таблицы: в карточках второго уровня после таблицы
    ссылок лежат пометки про сам перечень («журнал и проверки в перечень правил не кладутся»), и в
    варианте 1 они не нужны — они относятся к перечню, а не к правилу (решение оператора
    26.10.2026). Общая часть до первого маркера остаётся: она и есть ответ на вопрос «что это».
    """
    body = text or ""
    marks = list(_SECTION_MARK.finditer(body))
    if not marks:
        return body
    kept = [body[:marks[0].start()]]
    for number, match in enumerate(marks):
        end = marks[number + 1].start() if number + 1 < len(marks) else len(body)
        if match.group(1) not in names:
            kept.append(body[match.start():end])
    return re.sub(r"\n{3,}", "\n\n", "".join(kept)).strip()


def rule_bodies(rows):
    """Копии карточек без разделов-ссылок — чем печатается вариант 1.

    Копия, а не правка на месте: строка БД остаётся эталоном, а отчёт только читает; изменить
    переданный словарь значило бы отдать ниже по потоку текст, уже не совпадающий с базой.
    """
    out = []
    for row in rows:
        copy = dict(row)
        copy["answer"] = drop_sections(row.get("answer"))
        out.append(copy)
    return out


def cards_table(rows, parents):
    """Таблица карточек выборки: id, адрес, уровень, объём."""
    lines = ["| id | адрес | ур. | симв. |", "|---:|---|---:|---:|"]
    for row in rows:
        address = row["question"]
        title = ((RL.node_marker(address) if address in parents else address)
                 + marked_flag(row.get("tags")))
        lines.append(f"| {row['id']} | `{title}` | {RL.levels_of(address)} "
                     f"| {len(row.get('answer') or '')} |")
    return lines


# Отдельные сущности дерева: чем они являются и почему их читают после правил.
ENTITY_SECTIONS = (
    ("===CHECKS", RL.KIND_CHECKS,
     "Отдельная сущность дерева, а не правило: чем доказывать, что правило ещё верно. В перечни "
     "правил слоя эти карточки не кладутся, их проверяющий инструмент назван в самой карточке."),
    ("===JURNAL", RL.KIND_JOURNAL,
     "Отдельная сущность дерева, а не правило: снимок прежних текстов слоя. Тексты журнала не "
     "переписываются — они и есть запись о том, что было; меняется только адрес, под которым "
     "карточка лежит."),
)


# Варианты 5 и 6 состоят из одной категории: пояснение берётся тем же текстом, что и раздел полного
# отчёта, а не заводится второй раз — иначе два описания разъезжаются при первой же правке.
ENTITY_NOTES = {
    VARIANT_JOURNAL: next(note for _m, kind, note in ENTITY_SECTIONS if kind == RL.KIND_JOURNAL),
    VARIANT_CHECKS: next(note for _m, kind, note in ENTITY_SECTIONS if kind == RL.KIND_CHECKS),
}


def omission_note(variant, counts):
    """Чем вариант меньше полного — одной строкой в шапке.

    Файл без журнала и без перечней ссылок читается как «этого в дереве нет», если пробел не
    назван: тот же класс дефекта, что пустой файл вместо отказа.
    """
    if variant == VARIANT_RULES:
        return ("не входят: перечни ссылок (`===LINKS`, `===INDEX`) — вариант 2; "
                f"журнал ({counts['journal']}) и проверки ({counts['checks']}) — варианты 5 и 6")
    if variant == VARIANT_LINKS:
        return (f"входят перечни ссылок дословно; журнал ({counts['journal']}) и "
                f"проверки ({counts['checks']}) — варианты 5 и 6")
    if variant == VARIANT_LEVEL2:
        return (f"не входят: правила третьего уровня и ниже ({counts['rules']}) — вариант 1; "
                "журнал и проверки — варианты 5 и 6")
    if variant == VARIANT_JOURNAL:
        return (f"не входят: правила ({counts['rules']}) — вариант 1; "
                f"проверки ({counts['checks']}) — вариант 6")
    if variant == VARIANT_CHECKS:
        return (f"не входят: правила ({counts['rules']}) — вариант 1; "
                f"журнал ({counts['journal']}) — вариант 5")
    return ""


def render_report(query, rows, how_selected, out_path, include_marked=False,
                  variant=VARIANT_RULES):
    """Файл отчёта выбранного варианта: шапка, состав файла, содержимое карточек.

    Порядок задаётся деревом, а не алфавитом: часть `ref:002` обязана идти после `ref:001`. В
    полном варианте журнал и проверки идут после правил отдельными разделами — они отвечают на
    другие вопросы («чем доказывать», «как было») и правилами не являются; в вариантах 5 и 6 они и
    есть предмет файла, поэтому раздела им не нужно.

    Двоеточие узла в заголовке решается по всей выборке, а не по карточкам варианта: узел не
    перестаёт иметь детей от того, что в этом файле они не печатаются.
    """
    ordered = sorted(rows, key=lambda row: tree_key(row["question"]))
    parents = parents_with_children(ordered)
    rules, checks, journal = split_by_kind(ordered)
    picked = pick_cards(ordered, variant)
    if not picked:
        return None, 0
    cards = rule_bodies(picked) if variant == VARIANT_RULES else picked
    stamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    lines = [
        f"> дамп правил · {describe_variant(variant)} · запрос `{query}` · "
        f"выбор: {how_selected} · карточек: {len(picked)} · {stamp}",
        "> правки делаются строками БД; файл показывает текущее состояние целиком, а не эталон",
    ]
    note = omission_note(variant, {"rules": len(rules), "checks": len(checks),
                                   "journal": len(journal)})
    if note:
        lines.append(f"> {note}")
    if include_marked:
        marked = sum(1 for row in picked if is_marked(row.get("tags")))
        lines.append(f"> в выборку включены помеченные к удалению: {marked} — читающие инструменты "
                     f"их не отдают, снятые строки показаны с пометкой")
    if variant == VARIANT_FULL:
        lines += ["", "правила дерева:", ""] + cards_table(rules, parents)
        lines += ["", "---", ""]
        for row in rules:
            lines.append(render_card(row, row["question"] in parents))
        for marker, kind, entity_note in ENTITY_SECTIONS:
            group = checks if kind == RL.KIND_CHECKS else journal
            lines += ["", "---", "", marker, "", entity_note, ""]
            if not group:
                lines.append("_карточек этой категории в выборке нет_")
                continue
            lines += cards_table(group, parents)
            lines += ["", "---", ""]
            for row in group:
                lines.append(render_card(row, row["question"] in parents))
    else:
        entity_note = ENTITY_NOTES.get(variant)
        if entity_note:
            lines += ["", entity_note]
        if variant != VARIANT_RULES:
            lines += ["", "состав файла:", ""] + cards_table(picked, parents)
        lines += ["", "---", ""]
        for row in cards:
            lines.append(render_card(row, row["question"] in parents))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return out_path, len(picked)



# ------------------------------------------------------------------ точка входа

def safe_file_name(query):
    """Имя файла из запроса: разделители заменяются, из `Reports/` запросом не выйти.

    Запрос `rules:` не даёт имени (двоеточие — не символ имени файла), поэтому именем служит
    корень дерева: пустого имени у файла не бывает.
    """
    base = _SAFE_NAME_RE.sub("_", normalize_query(query)).strip("._-")
    return (base or "rules")[:120] + ".md"


def variant_file_name(query, variant):
    """Имя файла варианта: к имени запроса добавляется суффикс варианта.

    Кроме варианта по умолчанию — он остаётся под именем запроса, потому что именно его читают без
    выбора. Иначе два разных отчёта спорили бы за один файл, а прочитанный файл нельзя было бы
    отличить от снятого (`rules_journal.md` рядом с `rules.md` говорит о содержимом до открытия).
    """
    base = safe_file_name(query)[:-3]
    return base + VARIANT_SUFFIX[variant] + ".md"


def run(query="rules:", out=None, include_marked=False, variant=VARIANT_RULES):
    """Собрать дамп выбранного варианта и записать файлом.

    Возвращает путь, число карточек, способ выбора и вариант. Помеченные к удалению карточки по
    умолчанию не выбираются — дамп читают так же, как читают базу: скрытая строка не является
    правилом. `--marked` нужен для разбора карантина дерева, и в этом случае снятые строки
    помечаются в таблице и в заголовке.

    Пустой вариант не молчит: если в поддереве нет карточек этого вида, ответом называется вариант и
    то, чем он выбирается (пустой файл прочитался бы как «в дереве таких карточек нет»).
    """
    from database import get_cursor

    try:
        key = resolve_variant(variant)
    except ValueError as exc:
        return {"success": False, "error": str(exc)}
    with get_cursor() as cur:
        rows, how_selected = select_cards(cur, str(query or "rules:"), include_marked)
        if not rows:
            return {"success": False, "error": how_selected}
        if key == VARIANT_LEVEL2:
            # Карта строится от корня: родительские карточки запрошенного среза лежат вне его и в
            # выборку не попадают (замер 26.10.2026: `--query 1c-configurations-core -v 4` дал одну
            # карточку слоя — построение ролей по такому файлу не видно). Родителей берут отдельным
            # запросом по точным адресам: расширять срез до целого дерева значило бы показать
            # правила чужих слоёв под видом запрошенного.
            have = {row["question"] for row in rows}
            needed = set()
            for row in rows:
                needed.update(ancestor_addresses(row["question"]))
            added = by_addresses(cur, sorted(needed - have), include_marked)
            if added:
                rows = rows + added
                how_selected += (f" + родительские карточки ({len(added)}) вне запрошенного среза: "
                                 "карта строится от корня")
        out_path = Path(out) if out else Path(variant_file_name(query, key))
        if not out_path.is_absolute():
            out_path = REPORTS_DIR / out_path.name
        path, count = render_report(query, rows, how_selected, out_path, include_marked, key)
    if path is None:
        number, title, _note = VARIANTS[key]
        return {"success": False,
                "error": f"выбор {how_selected} не содержит карточек варианта {number} ({title}); "
                         f"другие варианты: "
                         + ", ".join(f"{VARIANTS[other][0]}" for other in VARIANT_ORDER)}
    return {"success": True, "path": str(path), "cards": count, "selected_by": how_selected,
            "variant": key}


def main():
    parser = argparse.ArgumentParser(
        description="Дамп правил файлом: запрос — алиас уровня, метка слоя или код MCP")
    parser.add_argument("--query", default="rules:",
                        help="алиас уровня (`rules:`, `rules:kb-rules:`), метка слоя или код MCP")
    parser.add_argument("-v", "--variant", default=VARIANT_RULES, metavar="ВАРИАНТ",
                        help="; ".join(f"{VARIANTS[key][0]} — {key} ({VARIANTS[key][1]})"
                                       for key in VARIANT_ORDER) + "; по умолчанию 1")
    parser.add_argument("--out", help="имя файла в Reports/ или абсолютный путь")
    parser.add_argument("--marked", action="store_true",
                        help="включить помеченные к удалению (разбор карантина дерева)")
    args = parser.parse_args()

    result = run(args.query, args.out, include_marked=args.marked, variant=args.variant)
    if not result["success"]:
        print(f"❌ {result['error']}")
        return 1
    number, title, _note = VARIANTS[result["variant"]]
    print(f"✅ {result['path']} · вариант {number} ({title}) · карточек: {result['cards']} "
          f"· выбор: {result['selected_by']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

