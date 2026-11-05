"""Карточки второго уровня `rules:<слой>:` и разбор общих записей по MCP (узел RULE-TREE).

Зачем. Корневая карточка приняла правила четырёх серверов целиком (шаг переноса из
`.clinerules/1C_Rule.md`). Теперь дерево достраивается вторым уровнем: на каждый MCP-сервер —
своя карточка `rules:<метка слоя>:`, и в неё уходят те записи корня, которые касаются только её.
Корень оставляет то, что относится ко всем слоям сразу, и перечень ссылок на второй уровень.

Почему адрес — метка слоя, а не имя MCP. Метки `core-rules`, `kb-rules`, `enrich-rules`,
`export-rules` уже зарегистрированы в `rules_layer.LAYERS` и в `TITLE_LAYER_MARKERS` кода поиска:
только зарегистрированная метка разрешается префиксным шагом, и только категория слоя изолирует
правила от прочей документации. Имя MCP (`1c-knowledge-base`, `1c-configurations-core`, ...)
выводится из категории слоя и заводится той же карточке алиасом — карточка по имени MCP находится,
и второго списка имён не появляется. Переименовать метку в имя MCP — отдельный шаг: он трогает
`LAYERS`, `TITLE_LAYER_MARKERS`, теги и все адреса слоя разом.

Как решается принадлежность записи. Заголовок блока называет MCP-сервер (в нём есть имя сервера или
метка слоя) — блок относится этому слою; заголовок нейтрален — блок наследует принадлежность
родителя; ни того ни другого — остаётся в корне как общая запись. Правило механическое и
проверяемое: принадлежность не выводят из содержания текста, иначе разбор додумывал бы за автором
правила.

Порядок записей слоя берётся из `LAYERS`; отдельного списка слоёв в скрипте нет.
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from database import get_cursor  # noqa: E402
import rules_layer as RL  # noqa: E402
from quarantine import MARK_ARRAY, sql_not_marked  # noqa: E402
from rules_report import tree_key  # тот же счётчик уровней и порядка дерева, что у дампа  # noqa: E402

ROOT_ADDRESS = "rules:"
BLOCK_HEADING_RE = re.compile(r"^(#{2,4}) +(\S.*)$")
LAYER_MARKERS = tuple(m for m in RL.LAYERS if m != RL.ROOT_MARKER)


def mcp_name_of(marker):
    """Имя MCP-сервера слоя: его категория без суффикса `-rules`.

    Категория слоя выведена из имени сервера (узел RULE-V2), поэтому имя берём из `LAYERS`:
    второй список имён расходится с первым молча, и карточка начинает рассказывать про один
    сервер, а правила собирать с другого.
    """
    category = RL.categories_of(marker)[0]
    return category[: -len("-rules")] if category.endswith("-rules") else category


NAMES = {marker: mcp_name_of(marker) for marker in LAYER_MARKERS}

ROOT_SUMMARY = """===SUMMARY
Правила каждого MCP-сервера — дерево карточек, а не один большой файл. Эта карточка — корень
дерева (уровень 1). Карточка второго уровня `rules:<слой>:` описывает один MCP-сервер и
перечисляет его правила; правило — уровень 3; `ref:NNN` — часть большого описания, `ref:NNN:<k>` —
часть части.

Как читать карточки. Поиском дерево не читают: выдача поиска несёт id, заголовок и превью в 200
символов, а не содержимое, потому что шаги поиска не гарантируют единственности ответа. Адрес —
уникальный ключ карточки, двумя адресами две карточки не описываются, поэтому правила читают
адресом: `python tools/rules_read.py <адрес>` отдаёт содержимое карточки целиком, а префикс адреса
(`rules:kb-rules:`) — родительскую карточку целиком и детей списком адресов. Порядок один: эта
карточка -> карточка нужного слоя по таблице `===LINKS` и по её назначению (выбор по назначению,
а не «прочитать все четыре») -> её общая часть и её перечень ссылок -> правило -> нужная часть
`ref:NNN`.

Что читается всегда, а что поднимается по задаче. Всегда читают эту карточку и индексную карточку
слоя `rules:kb-rules:` — её записи описывают работу со слоем знаний `local_doc`, которая нужна
любой задаче того же сервера и одинакова для всех четырёх (искать в базе прежде ответа по памяти,
называть категорию, покрывать алиасы, карантин, двухфазное чтение содержимого). Остальные три
слоя поднимают только когда задача касается их назначения: строка таблицы `===LINKS` и есть то,
по чему это решают; `python tools/rules_read.py --layers` печатает назначения слоёв, их объём и
политику загрузки. Правила трёх не затронутых слоёв при этом не читаются вовсе: лишний текст
стоит внимания и ничего не добавляет.

Перечень ссылок и карточки обязаны сходиться: ссылка ведёт на существующий адрес, а каждая карточка
слоя названа в перечне его второй карточки. Расхождение ловит проверка слоя, а не читатель.

Границы дерева. Больше шести уровней адрес не растёт — большое описание делится частями `ref:NNN`.
Адрес длиннее восьмидесяти символов адресом не считается: его нельзя повторить запросом поиска, и
он не разрешится шагом заголовков. Двоеточие на конце адреса — знак карточки-узла, у которой есть
дети; у правил и частей его быть не должно.

Что правилами не является. Ветки `journal` и `checks` — отдельные сущности дерева: журнал хранит
снимки прежних текстов и то, что ещё не сформулировано (правило, которого ещё нет, — заявка, а не
правило), проверки — чем доказывать, что правило ещё верно. При загрузке правил ни то ни другое не
читается.

Где править. Строкой БД `local_doc`: `question` = адрес, `answer` = содержимое. Файлы
`.clinerules/*_Rule.md` и `docs/rules/*.md` — исходники переноса и вход сверок, а не место правки
поведения. После правки строки дерево перегоняют дампом (`src/rules_report.py`) и смотрят текущее
состояние целиком; проверки (`tools/check_rules_layer.py`) — отдельный шаг, в осмотр они не
вмешиваются.

Раздел `===MCP` ниже — общие записи четырёх MCP-серверов: то, что относится ко всем слоям сразу
(как читать правила слоя, карта слоёв, критические правила, общие правила правки кода серверов).
Записи, касающиеся одного сервера, лежат в его карточке второго уровня — на них указывает таблица
`===LINKS`."""

ROOT_LINKS = """===LINKS
| ссылка | когда нужна | что там лежит |
|---|---|---|
| `rules:core-rules:` | загрузить, перезагрузить или удалить выгрузку 1С: каталог, `.erf`, `.epf` | общие записи сервера `1c-configurations-core`, инструменты его контракта и правила правки его кода, перечень правил слоя |
| `rules:kb-rules:` | искать по базе `local_doc`, грузить в неё документацию, править или помечать сниппет | общие записи `1c-knowledge-base`, механика поиска (алиасы = точное совпадение, двухфазное чтение, категории), правила правки `server.py`, перечень правил слоя |
| `rules:enrich-rules:` | смотреть содержимое загруженного объекта, работать с его алиасами, сниппетами и связями | общие записи `1c-configurations-enrichment`, карточка объекта, состав макета-СКД, генерация обогащения, привязка к конфигурации, перечень правил слоя |
| `rules:export-rules:` | выгрузить изменения конфигурации обратно в файлы | общие записи `1c-configurations-export`, готовность сценария экспорта и чего для него нет, перечень правил слоя |

Ссылки ведут на карточки второго уровня. Правила самих слоёв ещё не переразвёрнуты в дерево
`rules:<слой>:<правило>`, поэтому перечни правил лежат внутри карточек второго уровня и ведут на
прежние адреса (`core-rules:index`, `kb-rules:index`, `enrich-rules:index`, `export-rules:index`).
Когда слой переразвёрнут, ссылка переставляется на адрес дерева в тот же момент, когда меняется
строка БД.

===INDEX
rules:core-rules:
rules:kb-rules:
rules:enrich-rules:
rules:export-rules:"""


# ------------------------------------------------------------------ разбор карточки и её текста

CARD_SECTION_RE = re.compile(r"^===(SUMMARY|MCP|LINKS|INDEX)[ \t]*$", re.MULTILINE)


def split_card(text):
    """Текст карточки -> {раздел: содержимое}.

    Маркер ищется только в начале строки и только целиком (`===LINKS` отдельной строкой). Искать его
    подстрокой нельзя: в самих правилах есть фразы вроде «перечень `===LINKS` ниже ведёт», и первая
    такая фраза обрезала бы раздел посреди текста — карточка начала бы терять общую часть при каждой
    пересборке (так и случилось 25.10.2026 с четырьмя карточками второго уровня).
    """
    marks = [(match.start(), match.group(1)) for match in CARD_SECTION_RE.finditer(text)]
    sections = {}
    for number, (position, name) in enumerate(marks):
        end = marks[number + 1][0] if number + 1 < len(marks) else len(text)
        sections[name] = text[position + len(name) + 3:end].strip("\n")
    return sections


def heading_blocks(lines):
    """Заголовки текста карточки (уровни 2..4) — границы блоков, которые можно разнести по слоям."""
    blocks = []
    for index, line in enumerate(lines):
        match = BLOCK_HEADING_RE.match(line)
        if match:
            blocks.append({"index": index, "level": len(match.group(1)), "title": line.rstrip()})
    return blocks


def block_end(blocks, position, lines):
    """Границы блока: от его заголовка до следующего заголовка того же или высшего уровня."""
    for later in blocks[position + 1:]:
        if later["level"] <= blocks[position]["level"]:
            return later["index"]
    return len(lines)


def owner_of(blocks, position):
    """К какому слою относится блок: заголовок называет сервер — иначе наследует родителя.

    Наследование нужно затем, что подраздел («Порядок работы с инструментами слоя») своего имени
    сервера не несёт, а уходит вместе с родителем: оставить его в корне значило бы разорвать
    запись пополам.
    """
    title = blocks[position]["title"]
    for marker, name in NAMES.items():
        if name in title or f"{marker}:" in title:
            return marker
    for earlier in range(position - 1, -1, -1):
        if blocks[earlier]["level"] < blocks[position]["level"]:
            return owner_of(blocks, earlier)
    return None


def split_by_owner(text):
    """Текст корневых общих записей -> ({слой: строки его записей}, строки корня)."""
    lines = text.splitlines()
    blocks = heading_blocks(lines)
    owners = [None] * len(lines)
    for position, block in enumerate(blocks):
        owner = owner_of(blocks, position)
        for index in range(block["index"], block_end(blocks, position, lines)):
            owners[index] = owner
    per_layer = {marker: [] for marker in LAYER_MARKERS}
    root_lines = []
    for index, line in enumerate(lines):
        (per_layer[owners[index]] if owners[index] else root_lines).append(line)
    return per_layer, root_lines


def tidy(lines):
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


WHEN_RE = re.compile(r"^===[ \t]*WHEN[ \t]*(?:===)?[ \t]*(.*)$", re.MULTILINE)
SECTION_RE = re.compile(r"^===[ \t]*[A-ZА-Я][A-ZА-Я_]*")


def when_hint(answer, limit=110):
    """Подсказка «когда нужен» из раздела `===WHEN` самой карточки слоя.

    Раздел пишется по-разному в слоях двух форматов: `===WHEN` и `===WHEN===`, иногда текст стоит
    на той же строке. Разбирать только один вариант — значит получить пустую подсказку о правиле,
    которое прекрасно описано: молчание поиска читается как «правило не описано».

    Берётся текст карточки, а не её адрес: подсказка, сочинённая по имени правила, расходится с
    правилом молча, а взятая из карточки устаревает вместе с ней.
    """
    text = answer or ""
    match = WHEN_RE.search(text)
    body = text[match.end():] if match else text
    parts = [match.group(1).strip()] if match and match.group(1).strip() else []
    for line in body.splitlines():
        if SECTION_RE.match(line) or line.startswith("#"):
            break
        if not line.strip():
            if parts:
                break
            continue
        parts.append(line.strip())
    hint = " ".join(parts)
    return (hint[:limit] + "…") if len(hint) > limit else (hint or "—")


def layer_links(cur, marker):
    """Перечень карточек слоя: таблица (id, адрес, когда нужен) и список адресов.

    Перечень читается из базы, а не пишется в скрипте: список, заведённый руками, отстаёт от
    дерева на одну карточку и врёт про покрытие слоя.

    Помеченные к удалению строки в перечень не кладутся: перечень — читающая поверхность, а
    читающая поверхность скрытые строки не отдаёт. Строка, помеченная к удалению и перечисленная
    как «правило ещё действует», читается как действующее правило.
    """
    cur.execute(
        "SELECT id, question, answer FROM knowledge_snippets "
        "WHERE question LIKE %s AND source_url LIKE %s" + sql_not_marked(),
        (marker + ":%", RL.SOURCE_SCHEME + "%", MARK_ARRAY),
    )
    rows = sorted((dict(row) for row in cur.fetchall()), key=lambda row: tree_key(row["question"]))
    table = ["| id | адрес | когда нужен |", "|---:|---|---|"]
    table += [f"| {row['id']} | `{row['question']}` | {when_hint(row['answer'])} |" for row in rows]
    return "\n".join(table), [row["question"] for row in rows], len(rows)


def layer_summary(marker):
    """Общая часть карточки второго уровня: что это за сервер и куда ведут его правила."""
    name = NAMES[marker]
    return f"""===SUMMARY
Первая карточка слоя правил MCP `{name}` — уровень 2 дерева правил. Она говорит, что это за сервер и
как устроены правила его слоя; сами правила лежат следующим уровнем.

Сегодня правила слоя записаны под прежним адресом `{marker}:<...>` — слой ещё не переразвёрнут в
дерево `{RL.ROOT_MARKER}:{marker}:<правило>`. Поэтому перечень `===LINKS` ниже ведёт именно туда, а
подсказка «когда нужен» взята из раздела `===WHEN` самой карточки. Когда слой переразвёрнут,
ссылки переставляются на адреса дерева в тот же момент, когда меняется строка БД.

Раздел `===MCP` — общие записи слоя, перенесённые из корневой карточки без правок текста. Их разбор
по отдельным правилам и частям `ref:NNN` — отдельный шаг."""


def layer_answer(marker, mcp_lines, links_table, index_list):
    return (f"{layer_summary(marker)}\n\n===MCP\n{tidy(mcp_lines)}\n\n===LINKS\n{links_table}\n\n"
            "===INDEX\n" + "\n".join(index_list))


def card_tags(address, marker=None):
    """Теги карточки дерева: категории корневого слоя, категории своего слоя, признаки дерева.

    Категории двух слоёв нужны затем, что карточку второго уровня читают и фильтром корня, и
    фильтром своего сервера: фильтр — пересечение тегов, поэтому тег единственной категории сделал
    бы карточку невидимой для второго входа. `tree-node` отделяет карточки новой схемы от
    перенесённых карточек старого слоя.
    """
    tags = list(RL.categories_of(RL.ROOT_MARKER)) + ["rules", "rules-layer", "tree-node"]
    if marker:
        tags += list(RL.categories_of(marker))
    return list(dict.fromkeys(tag for tag in tags if tag))


# ------------------------------------------------------------------ запись карточек дерева

def write_card(cur, address, answer, aliases, tags):
    """Одна карточка дерева: строка с тем же адресом снимается, алиасы идемпотентны.

    Все пять карточек пишутся в одной транзакции: отказ на четвёртой откатывает предыдущие, и
    дерево не остаётся половинчатым (половинчатое дерево читается как полное).
    """
    problems = RL.validate_address(address, RL.ROOT_MARKER)
    if problems:
        raise ValueError(f"адрес {address!r} не проходит проверку: " + "; ".join(problems))
    cur.execute("DELETE FROM knowledge_snippets WHERE question = %s AND source_url = %s",
                (address, RL.source_url(address)))
    cur.execute(
        "INSERT INTO knowledge_snippets (groups_id, question, answer, source_url, tags, "
        "confidence, is_verified) VALUES (NULL,%s,%s,%s,%s,1.0,TRUE) RETURNING id",
        (address, answer, RL.source_url(address), tags),
    )
    snippet_id = cur.fetchone()["id"]
    for alias in aliases:
        # Алиасы этой карточки — её адрес в двух написаниях, метка слоя и имя MCP. Правила
        # `validate_alias` (без двоеточия, без метки слоя) к ним не применяются: там они запрещены
        # как шум для чужих строк, а здесь это адрес самой карточки и имя её сервера.
        cur.execute(
            "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags, "
            "weight) VALUES (%s,'snippet',NULL,%s,%s,1.0) "
            "ON CONFLICT (alias_name, snippets_id) WHERE snippets_id IS NOT NULL DO NOTHING",
            (alias, snippet_id, tags),
        )
    return snippet_id


def refresh_layer_links(cur):
    """Заново собрать перечни правил слоя, не трогая его общую часть и `===MCP`.

    Перечень читается из базы, поэтому он отстаёт от слоя на одну карточку сам собой; режим
    обновления нужен затем, чтобы перечни (и подсказки к ним) можно было перегнать, не перенося
    записи заново — перенос повторный прогон отказывается делать намеренно.
    """
    for marker in LAYER_MARKERS:
        address = f"{RL.ROOT_MARKER}:{marker}:"
        cur.execute("SELECT answer, tags FROM knowledge_snippets WHERE question = %s AND source_url = %s",
                    (address, RL.source_url(address)))
        row = cur.fetchone()
        if not row:
            print(f"⚠️ {address} в базе нет — перечень обновлять нечем.")
            continue
        sections = split_card(row["answer"])
        table, index_list, count = layer_links(cur, marker)
        answer = (f"{sections.get('SUMMARY', '').strip()}\n\n===MCP\n{sections.get('MCP', '').strip()}\n\n"
                  f"===LINKS\n{table}\n\n===INDEX\n" + "\n".join(index_list))
        aliases = [address, f"{RL.ROOT_MARKER}:{marker}", f"{marker}:", marker, NAMES[marker]]
        card_id = write_card(cur, address, answer, aliases, list(row["tags"]))
        print(f"✅ {address} id={card_id} перечень={count} карточек answer={len(answer)}")


def collect_mcp_text(cur, root_answer):
    """Собрать текст общих записей для повторного переноса: корень плюс уже разнесённое по слоям.

    Режим починки нужен затем, что первый перенос забрал записи из корня: обычный повторный прогон
    взял бы их уже неоткуда, а карточки слоёв при этом требуют пересборки (общая часть, перечни).
    Порядок склейки на разбор не влияет — принадлежность блока определяет его заголовок, а не сосед.
    """
    parts = [split_card(root_answer).get("MCP", "")]
    for marker in LAYER_MARKERS:
        address = f"{RL.ROOT_MARKER}:{marker}:"
        cur.execute("SELECT answer FROM knowledge_snippets WHERE question = %s AND source_url = %s",
                    (address, RL.source_url(address)))
        row = cur.fetchone()
        if row:
            parts.append(split_card(row["answer"]).get("MCP", ""))
    return "\n\n".join(part.strip() for part in parts if part.strip())


def main():
    parser = argparse.ArgumentParser(description="Карточки второго уровня дерева правил")
    parser.add_argument("--links-only", action="store_true",
                        help="только перечитать перечни правил слоя (подсказки, состав слоя), текст не переносить")
    parser.add_argument("--repair", action="store_true",
                        help="пересобрать карточки, собрав текст записей из корня и уже разнесённого по слоям")
    args = parser.parse_args()

    with get_cursor() as cur:
        if args.links_only:
            refresh_layer_links(cur)
            return 0
        cur.execute("SELECT answer FROM knowledge_snippets WHERE question = %s AND source_url = %s",
                    (ROOT_ADDRESS, RL.source_url(ROOT_ADDRESS)))
        row = cur.fetchone()
        if not row:
            print("❌ корневой карточки `rules:` в базе нет — сначала её нужно создать.")
            return 1
        mcp_text = collect_mcp_text(cur, row["answer"]) if args.repair else split_card(row["answer"]).get("MCP", "")
        if not mcp_text:
            print("❌ записей для переноса нет: перенос уже выполнен. Для пересборки карточек нужен "
                  "флаг --repair — он собирает текст из корня и карточек слоёв.")
            return 1

        per_layer, root_lines = split_by_owner(mcp_text)
        moved = {marker: len(tidy(lines)) for marker, lines in per_layer.items()}
        if not any(moved.values()):
            print("❌ ни одна запись не отнесена к конкретному MCP: перенос уже выполнен или "
                  "заголовки блоков изменились. Ничего не меняю — так карточки не теряют текст.")
            return 1

        root_answer = f"{ROOT_SUMMARY}\n\n===MCP\n{tidy(root_lines)}\n\n{ROOT_LINKS}"
        root_id = write_card(cur, ROOT_ADDRESS, root_answer, [ROOT_ADDRESS, "rules"],
                             card_tags(ROOT_ADDRESS))
        print(f"✅ корень id={root_id}: общих записей осталось {len(tidy(root_lines))} симв., "
              f"answer={len(root_answer)}")
        for marker in LAYER_MARKERS:
            table, index_list, count = layer_links(cur, marker)
            address = f"{RL.ROOT_MARKER}:{marker}:"
            answer = layer_answer(marker, per_layer[marker], table, index_list)
            aliases = [address, f"{RL.ROOT_MARKER}:{marker}", f"{marker}:", marker, NAMES[marker]]
            card_id = write_card(cur, address, answer, aliases, card_tags(address, marker))
            print(f"✅ {address} id={card_id} mcp={NAMES[marker]} перенесено={moved[marker]} симв. "
                  f"answer={len(answer)} перечислено правил={count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())