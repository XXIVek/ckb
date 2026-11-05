"""Узел V57, шаг П7: исправление позиции 3 абзаца П6 в снимке журнала `rules:core-rules:journal:node:v57`.

Что не так в карточке: абзац утверждает, что регулярная строка `ITEM_TAG_RE` «теряла префикс
пространства имён, из-за чего `item_tag` читался как `Item` вместо `xr:Item`». Направление
утверждения неверно: колонка `item_tag` хранит ЛОКАЛЬНОЕ имя элемента (`Item`) — так же, как
соседние узлы хранят `functional_option_content.target_tag` = `Object` (V56, 10 063 строки) и
`filter_criterion_content.target_tag` = `Item` (V52); замер 05.11.2026 по живым таблицам.
Дефект был в сканирующей файлы регулярной строке самой проверки: без допуска префикса `xr:`
собственный обход файлов не находил элементов `<xr:Item>`, то есть проверка сравнивала бы пустой
обход с 34 строками базы. Правка привела обход к контракту слоя, а не изменила содержимое базы.

Скрипт идемпотентен: повторный прогон находит исправленный текст и отвечает «уже внесено».
Режим `--check` — только поиск, без записи. Запись идёт через `update_snippet`, прежнее
содержимое уходит в `snippet_audit_log` (тот же порядок, что `_v57_p6_rules_card.py`).
"""
import re
import sys

sys.path.insert(0, "src")
from mcp_tools_core import _get_pool          # noqa: E402
from mcp_tools_api import update_snippet      # noqa: E402

SNIPPET_ID = 6262

OLD = """3. регулярное выражение имени элемента перечня (`ITEM_TAG_RE`) теряло префикс пространства имён,
   из-за чего `item_tag` читался как `Item` вместо `xr:Item`; состояние `md_object_ref` при этом
   оставалось верным — ошибка пряталась за правильным ответом."""

NEW = """3. сканирующая файлы регулярная строка самой постоянной проверки (`ITEM_TAG_RE`) не допускала
   префикса пространства имён, поэтому собственный обход файлов не находил элементов `<xr:Item>` —
   сравнивать было бы не с чем. Колонка `item_tag` при этом хранит ЛОКАЛЬНОЕ имя элемента (`Item`),
   тот же порядок, что `functional_option_content.target_tag` = `Object` у V56 (10 063 строки) и
   `filter_criterion_content.target_tag` = `Item` у V52 (замер 05.11.2026 по живым таблицам).
   Правка привела обход проверки к контракту слоя, а не изменила содержимое базы; прежнее
   утверждение («колонка читалась как `Item` вместо `xr:Item`») было неверно НАПРАВЛЕНИЕМ и
   исправлено шагом П7 — карточка не должна оставлять читателю ложный вывод о том, что слой
   теряет префикс имени."""

CHECK_MARKER = "было неверно НАПРАВЛЕНИЕМ и исправлено шагом П7"

REASON = ("узел V57 шаг П7: позиция 3 абзаца П6 исправлена направлением — `item_tag` хранит "
          "локальное имя `Item` (замер живых таблиц V52/V56/V57), дефект был в сканирующей "
          "файлы регулярной строке проверки, а не в содержимом колонки")


def flex(text: str) -> str:
    """Образец с любыми пробелами между токенами — карточки правятся частями."""
    return r"\s+".join(re.escape(token) for token in text.split())


def main() -> int:
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT question, answer FROM knowledge_snippets WHERE id = %s",
                        (SNIPPET_ID,))
            row = cur.fetchone()
    finally:
        pool.putconn(conn)
    if row is None:
        print(f"ОШИБКА: карточка {SNIPPET_ID} не найдена")
        return 1

    question, answer = row
    print(f"id={SNIPPET_ID} {question} было: {len(answer)}")

    if re.search(flex(CHECK_MARKER), answer):
        print("  [item3] sub: уже внесено")
        print("  итог: без изменений")
        return 0

    hit = re.search(flex(OLD), answer)
    if not hit:
        print("  [item3] sub: ОБРАЗЕЦ НЕ НАЙДЕН — карточка правилась не этим текстом")
        return 1

    text = answer[:hit.start()] + NEW + answer[hit.end():]
    print("  [item3] sub: внесено")
    print(f"  стало: {len(text)}")
    if "--check" in sys.argv[1:]:
        print("  запись не выполнена (--check)")
        return 0
    print("  " + str(update_snippet(SNIPPET_ID, new_answer=text, reason=REASON)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
