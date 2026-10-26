"""Правка двух карточек после узла RESTRUCTURE-LAYERS (26.10.2026).

Зачем отдельным скриптом. Оба текста врут после шага:

* корневая карточка `rules:` в разделе `===LINKS` говорит, что правила трёх конфигурационных слоёв
  «ещё не переразвёрнуты в дерево» и ведут на прежние адреса — с этого шага это неверно, и корень
  (читается ВСЕГДА) отправлял бы читателя в снимок вместо правил;
* карточка `rules:reserved:layer-migration` описывает триггер «первый узел, который меняет правило
  одного из этих слоёв» и порядок `readdress_rules_layer.py → авторинг v2`. Узел был, и он сделал
  переразвёртку в формат дерева (не в формат v2 файла `docs/rules/`), поэтому триггер надо
  переписать на оставшуюся часть работы, а не оставить несбывшимся.

Содержимое карточек дерева — строки БД, поэтому правка идёт строкой БД (правило
`rules:kb-rules:always:edit-in-db`), а не файлом.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from database import get_cursor  # noqa: E402

ROOT_ADDRESS = "rules:"
RESERVED_ADDRESS = "rules:reserved:layer-migration"

# Что в карточке слоя осталось бы, если не править: ссылка в снимок вместо правил.
STALE_ROOT_RE = re.compile(
    r"Ссылки ведут на карточки второго уровня\..*?строка БД\.", re.DOTALL)

NEW_ROOT = """Ссылки ведут на карточки второго уровня. Правила слоёв лежат третьим уровнем: функции —
`rules:<слой>:functional:<функция>`, предписания инструментов регистра —
`rules:<слой>:<инструмент>-tool` (имя инструмента в адресе пишется через дефис). Снимок прежних
текстов — ветка `journal` слоя, её индекс `rules:<слой>:journal:index`; снимок действующим правилом
не является. Перечни детей (`===LINKS` и `===INDEX` карточки слоя) собираются из живых строк БД
генератором `_make_layer_rule_cards.py`, живое дерево трёх конфигурационных слоёв сверяет
`_layer_tree_check.py`."""

NEW_RESERVED = """===WHEN
Когда берёшься править правило одного из трёх конфигурационных слоёв (`core-rules`, `enrich-rules`,
`export-rules`) или менять состав инструментов их серверов.

===TRIGGER
Слои переразвёрнуты в дерево узлом RESTRUCTURE-LAYERS (26.10.2026): снимок прежних текстов лежит под
`rules:<слой>:journal:…`, действующие правила — под `rules:<слой>:functional:<функция>` и
`rules:<слой>:<инструмент>-tool`. Поэтому правило правят строкой БД по адресу дерева, а не файлом
`docs/rules/<метка>.md`; прежний порядок «`readdress_rules_layer.py` → авторинг карточек v2 →
`tools/regen_journal_index.py`» этому шагу больше не нужен.

Карточка обязана быть на каждый инструмент регистра сервера: состав читается из `@mcp.tool()` того же
файла, который читают `tools/rules_functions.py` и `tools/check_mcp_tool_wiring.py`. Расхождение
«инструмент есть, карточки нет» ловит `python _make_layer_rule_cards.py --check` до записи и
`python _layer_tree_check.py` по живой базе — вторая проверка смотрит дополнительно разделы карточки,
теги вида и полноту `===INDEX`.

===WHERE
Где править: `_make_layer_rule_cards.py` (тексты карточек трёх слоёв и их индекс-карточек),
`_layer_tree_check.py` (живая сверка дерева), `_layer_ls.py` (состав слоя). Файлы
`.clinerules/*_Rule.md` и `docs/rules/*.md` остаются исходниками переноса и входом сверки
`tools/check_search_rules_sync.py` — правка поведения сервера обязана отражаться и там.

Не сделано: `tools/check_rules_layer.py --layer <метка>` работает с прежним адресным пространством
формата 1 и под адреса дерева ещё не адаптирован; до этого шага живой проверкой дерева служит
`_layer_tree_check.py`. Отдельная незакрытая часть — формат карточек журнала: он остаётся снимком
прежних текстов и под разделы дерева не перекладывается."""


def main():
    with get_cursor() as cur:
        cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question = %s", (ROOT_ADDRESS,))
        row = cur.fetchone()
        if not row:
            print(f"❌ карточки {ROOT_ADDRESS} в базе нет")
            return 1
        answer, count = STALE_ROOT_RE.subn(NEW_ROOT, row["answer"] or "", count=1)
        if count != 1:
            print(f"❌ {ROOT_ADDRESS}: абзац о непереразвёрнутых слоях не найден — правку не делаем")
            return 1
        cur.execute("UPDATE knowledge_snippets SET answer = %s, updated_at = NOW() WHERE id = %s",
                    (answer, row["id"]))
        print(f"✅ {ROOT_ADDRESS} id={row['id']}: абзац ===LINKS переписан, answer {len(answer)}")

        cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question = %s",
                    (RESERVED_ADDRESS,))
        row = cur.fetchone()
        if not row:
            print(f"⚠️ карточки {RESERVED_ADDRESS} в базе нет — создавать не будем (это не узел)")
        else:
            cur.execute("UPDATE knowledge_snippets SET answer = %s, updated_at = NOW() WHERE id = %s",
                        (NEW_RESERVED, row["id"]))
            print(f"✅ {RESERVED_ADDRESS} id={row['id']}: триггер переписан, "
                  f"answer {len(row['answer'] or '')} → {len(NEW_RESERVED)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
