"""Перенос правил MCP из `.clinerules/1C_Rule.md` в корневую карточку дерева (узел RULE-TREE).

Зачем. Файл `1C_Rule.md` говорит о четырёх MCP-серверах больше, чем о работе ассистента, а правила
серверов должны жить строками БД (`local_doc`) — тогда их читают адресом, а не целиком. Скрипт
делает перенос механически: режет файл по заголовкам и перекладывает MCP-разделы (и их подразделы
по наследованию от родителя) в карточку `rules:`, раздел `===MCP===`. Остальное остаётся в файле.

Почему по заголовкам, а не переписыванием. Переписанный текст расходится с исходником в первую
же правку, а расхождение «правило здесь, поведение там» — тот дефект, который ловит
`check_search_rules_sync.py`. Дословный перенос остаётся дословным с обеих сторон.

Граница классификации — список точных заголовков `MCP_HEADINGS`. Он назван явно, потому что
граница «это про MCP» / «это про работу ассистента» — решение оператора, а не вывод из текста:
разделы «Роль» и «Работа с терминалом» остаются в файле, хотя упомянуты рядом.

Идемпотентность: карточка пересоздаётся по адресу (снимается строка с тем же `source_url`), файл
перезаписывается целиком. Повторный прогон без MCP-блоков в файле — отказ, а не запись пустого
раздела: молча обнулить карточку значило бы потерять перенесённые правила.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from database import get_cursor  # noqa: E402
import rules_layer as RL  # noqa: E402

ROOT = Path(__file__).resolve().parent
RULES_FILE = ROOT / ".clinerules" / "1C_Rule.md"
ADDRESS = "rules:"
HEADING_RE = re.compile(r"^(#{2,3}) +(\S.*)$")

# Точные заголовки разделов, которые относятся к MCP-серверам. Подразделы наследуют принадлежность
# родителю: «Шаг 1..4» названы явно, «Состояния карточек» — нет, но он внутри «Слой правил MCP».
MCP_HEADINGS = [
    "## Основные правила при работе с проектом размещены в каталоге C:\\1C_LLM\\ckb\\.clinerules.",
    "## 📚 Слой правил MCP (узел RULE-LAYER, 24.10.2026)",
    "### 📚 Шаг 1: Поиск документации (MCP `1c-knowledge-base`)",
    "### ⚙️ Шаг 2: Загрузка выгрузок 1С (MCP `1c-configurations-core`)",
    "### 🔄 Шаг 3: Анализ и обогащение объектов выгрузки (MCP `1c-configurations-enrichment`)",
    "### 📤 Шаг 4: Экспорт изменений конфигурации (MCP `1c-configurations-export`)",
    "### 🎯 Алгоритм принятия решений",
    "### ⚠️ Критические правила работы с MCP",
    "## ВАЖНЫЕ ПРАВИЛА",
    "## ⚠️ ПРАВИЛА РЕДАКТИРОВАНИЯ КОДА MCP-СЕРВЕРОВ",
]

SUMMARY = """===SUMMARY
Правила каждого MCP-сервера — дерево карточек, а не один большой файл. Эта карточка — корень
дерева: она объясняет, как в него войти и куда идти дальше. Первая карточка слоя (уровень 2)
описывает сам сервер и перечисляет его правила; правило (уровень 3) — одна операция или один
запрет; `ref:NNN` — часть большого описания, `ref:NNN:<k>` — часть части.

Как идти по дереву. Дерево читают при постановке задачи и при её смене, а не один раз за сессию:
эта карточка -> карточка нужного слоя -> её общая часть и перечень ссылок -> только те правила,
которые назвала задача (обычно две-три из семи, остальные не читаются вовсе) -> нужная часть
описания. Спускаться глубже, чем нужно задаче, смысла нет: лишняя карточка стоит внимания и
ничего не добавляет.

Границы дерева. Больше шести уровней адрес не растёт — большое описание делится частями `ref:NNN`.
Адрес длиннее восьмидесяти символов адресом не считается: его нельзя повторить запросом поиска, и
он не разрешится шагом заголовков.

Что правилами не является. Ветки `journal` и `checks` — отдельные сущности дерева: журнал хранит
снимки прежних текстов и то, что ещё не сформулировано (правило, которого ещё нет, — заявка, а не
правило), проверки — чем доказывать, что правило ещё верно. При загрузке правил ни то ни другое не
читается.

Где править. Строкой БД `local_doc`: `question` = адрес, `answer` = содержимое. Файлы
`.clinerules/*_Rule.md` и `docs/rules/*.md` — исходники переноса и вход сверок, а не место правки
поведения. После правки строки дерево перегоняют дампом (`src/rules_report.py`) и смотрят текущее
состояние целиком; проверки (`tools/check_rules_layer.py`) — отдельный шаг, в осмотр они не
вмешиваются.

Раздел `===MCP===` ниже — общие правила работы с четырьмя MCP-серверами, перенесённые из
`.clinerules/1C_Rule.md` без правок текста. Они приехали целиком и ещё не разложены по слоям и
частям: это текущее состояние, а не окончательная структура.

===MCP"""

LINKS = """===LINKS
| ссылка | когда нужна | что там лежит |
|---|---|---|
| `core-rules:index` | загрузить, перезагрузить или удалить выгрузку 1С: каталог, `.erf`, `.epf` | контракт загрузки: пять инструментов точки входа, четыре исхода, правила R1–R14, порядок создания БД `ckb_1c_configurations` |
| `kb-rules:index` | искать по базе `local_doc`, грузить в неё документацию, править сниппет | механика поиска: алиасы = точное совпадение, двухфазное чтение (id -> содержимое), категории, карантин сниппетов, правка с историей |
| `enrich-rules:index` | смотреть содержимое загруженного объекта, работать с его алиасами и сниппетами | карточка объекта, состав макета-СКД, генерация обогащения, привязка внешнего объекта к конфигурации, контракт из двадцати одного инструмента |
| `export-rules:index` | выгрузить изменения конфигурации обратно в файлы | готовность сценария: он не реализован, каких таблиц для него нет; единственный инструмент — `export_readiness_tool` |

Ссылки ведут на адреса, которые разрешаются сегодня. Когда слой переразвёрнут в дерево
(`rules:<слой>:`), ссылка переставляется на первую карточку слоя в тот же момент, когда меняется
строка БД: перечень ссылок и карточки обязаны сходиться, а не расходиться на шаг.

===INDEX
core-rules:index
kb-rules:index
enrich-rules:index
export-rules:index"""

# Что остаётся в файле правил вместо перенесённых разделов: только путь в дерево правил БД.
FILE_SECTION = '''## 📚 Правила работы с MCP-серверами — в базе `local_doc`

Правила четырёх MCP-серверов (`1c-knowledge-base`, `1c-configurations-core`,
`1c-configurations-enrichment`, `1c-configurations-export`) живут строками базы `local_doc`, а не в
этом файле. Здесь остаются правила работы ассистента: роль, терминал, вывод.

Корень дерева правил — карточка с адресом `rules:`. Её читают двумя шагами:

1. `search_docs_tool(query="rules:", category="rules", limit=5)` — получить id карточки;
2. `get_snippet_tool(snippet_id)` — её содержимое: общие правила работы с MCP, карту слоёв и
   перечень ссылок на четыре слоя правил.

Дальше по дереву — тот же приём: адрес первой карточки слоя (`rules:core-rules:`,
`rules:kb-rules:`, `rules:enrich-rules:`, `rules:export-rules:`), затем адрес нужного правила.
Слои, которые ещё не переразвёрнуты в дерево, читаются прежними адресами (`core-rules:index`,
`kb-rules:index`, `enrich-rules:index`, `export-rules:index`) — они названы в перечне ссылок
корневой карточки, и расхождения между перечнем и деревом быть не должно.

Текущее состояние дерева видно дампом:

```powershell
python src/rules_report.py --query rules    # корневая карточка и верхний слой правил
python src/rules_report.py --query rules:   # одна корневая карточка (выбор по алиасу уровня)
```

Правки делаются строками БД (`knowledge_snippets.question` = адрес, `answer` = содержимое), а не
этим файлом. Файл — правила работы ассистента и точка входа в дерево правил.'''


# ------------------------------------------------------------------ разбор файла по заголовкам

ALL_LINES = []  # текущий файл разбора: границы разделов считаются по номерам строк


def heading_lines(lines):
    """Заголовки уровня 2 и 3 — границы разделов файла правил (уровень 1 — титул файла)."""
    found = []
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match:
            found.append({"index": index, "level": len(match.group(1)), "title": line.rstrip()})
    return found


def is_mcp(sections, position):
    """Раздел относится к MCP: он назван в списке или наследует принадлежность родителя.

    Наследование нужно затем, что подразделы «Состояния карточек», «Инструменты слоя» в список не
    внесены, а уходят вместе с родителем: оставить их в файле значило бы разорвать правило пополам.
    """
    if sections[position]["title"] in MCP_HEADINGS:
        return True
    for earlier in range(position - 1, -1, -1):
        if sections[earlier]["level"] < sections[position]["level"]:
            return is_mcp(sections, earlier)
    return False


def section_bounds(sections, position):
    """Границы раздела: от заголовка до следующего заголовка того же или высшего уровня."""
    for later in sections[position + 1:]:
        if later["level"] <= sections[position]["level"]:
            return sections[position]["index"], later["index"]
    return sections[position]["index"], len(ALL_LINES)


def split_lines(lines):
    """(строки MCP, строки AI) в исходном порядке — вложенные разделы идут за родителем."""
    global ALL_LINES
    ALL_LINES = lines
    sections = heading_lines(lines)
    flags = [False] * len(lines)
    for position, section in enumerate(sections):
        if not is_mcp(sections, position):
            continue
        start, end = section_bounds(sections, position)
        for index in range(start, end):
            flags[index] = True
    return ([l for i, l in enumerate(lines) if flags[i]],
            [l for i, l in enumerate(lines) if not flags[i]])


def drop_empty_headings(lines):
    """Удалить заголовки, у которых после переноса не осталось текста.

    «ПРИНЦИП РАБОТЫ» пустеет целиком: его подразделы (Шаг 1..4) ушли в карточку. Оставить пустой
    заголовок в файле правил — значит показать раздел, которого больше нет.
    """
    sections = heading_lines(lines)
    drop = set()
    for position, section in enumerate(sections):
        start, end = section_bounds(sections, position)
        body = [line for line in lines[start + 1:end] if line.strip()]
        has_child = any(section_bounds(sections, later)[0] > start
                        for later in range(position + 1, len(sections))
                        if sections[later]["level"] > section["level"]
                        and sections[later]["index"] < end)
        if not body and not has_child:
            drop.update(range(start, end))
    return [line for index, line in enumerate(lines) if index not in drop]


def tidy(lines):
    """Сжать пустые строки и обрезать по краям: перенесённый текст остаётся дословным."""
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


# ------------------------------------------------------------------ запись обеих сторон

def write_card(answer):
    """Карточка `rules:` целиком (строка с тем же адресом снимается) + алиасы уровня.

    Алиас два — `rules:` и `rules`: первый выбирает поддерево точным алиасным шагом, второй
    остаётся затем, что человек печатает корень без двоеточия. Автоалиасы из заголовка карточкам
    слоя не заводятся: поиск начал бы отдавать корень по слову `rules` в любом запросе.
    """
    tags = RL.tags_for(ADDRESS, "rules") + ["root"]
    with get_cursor() as cur:
        cur.execute("DELETE FROM knowledge_snippets WHERE question = %s AND source_url = %s",
                    (ADDRESS, RL.source_url(ADDRESS)))
        cur.execute(
            "INSERT INTO knowledge_snippets (groups_id, question, answer, source_url, tags, "
            "confidence, is_verified) VALUES (NULL,%s,%s,%s,%s,1.0,TRUE) RETURNING id",
            (ADDRESS, answer, RL.source_url(ADDRESS), tags),
        )
        snippet_id = cur.fetchone()["id"]
        for alias in (ADDRESS, "rules"):
            cur.execute(
                "INSERT INTO alias_targets (alias_name, target_type, groups_id, snippets_id, tags, "
                "weight) VALUES (%s,'snippet',NULL,%s,%s,1.0) "
                "ON CONFLICT (alias_name, snippets_id) WHERE snippets_id IS NOT NULL DO NOTHING",
                (alias, snippet_id, tags),
            )
    return snippet_id, tags


def main():
    text = RULES_FILE.read_text(encoding="utf-8")
    mcp_lines, ai_lines = split_lines(text.splitlines())
    mcp_text = tidy(mcp_lines)
    if not mcp_text:
        print("❌ MCP-разделов в файле не найдено: файл уже переложен. Карточку не трогаю — "
              "записать пустой раздел означало бы потерять перенесённые правила.")
        return 1

    problems = RL.validate_address(ADDRESS, "rules")
    if problems:
        print("❌ адрес корневой карточки не проходит проверку:")
        for problem in problems:
            print("   ", problem)
        return 1

    answer = f"{SUMMARY}\n\n{mcp_text}\n\n{LINKS}"
    # Сначала карточка, потом файл: при отказе записи в БД текст остаётся в файле (пусто с обеих
    # сторон видно сразу), обратный порядок терял бы правила молча.
    snippet_id, tags = write_card(answer)
    new_file = tidy(drop_empty_headings(ai_lines)) + "\n\n" + FILE_SECTION + "\n"
    RULES_FILE.write_text(new_file, encoding="utf-8")

    print(f"✅ карточка id={snippet_id} адрес={ADDRESS} answer={len(answer)} симв. теги={tags}")
    print(f"   перенесено из файла: {len(mcp_lines)} строк ({len(mcp_text)} симв.)")
    print(f"   в файле осталось: {len(new_file.splitlines())} строк ({len(new_file)} симв.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
