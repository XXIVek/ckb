"""Зонд состава карточки второго уровня: порядок секций, порядок блоков внутри секции,
состояние снятого блока функций и совпадение канала поиска функций с деревом.

Зачем. Указатель поиска функций обязан быть ПОСЛЕДНИМ блоком карточки слоя: он замыкает
описание слоя, а не вставляется между общими записями. Проверять это по дампу нельзя — дамп
показывает правила, а не порядок разделов строки БД.

Что изменил узел FUNC-SEARCH (27.10.2026). Прежний зонд сверял счётчики блока («функций N»,
«инструментов M») с детьми дерева и регистром. Теперь блока перечня в карточке быть не должно: он
пересказывал дочерние карточки в карточке, которую читают целиком, и с ним карточка весела за
бюджет always (14 994 симв. при ALWAYS_BUDGET_CHARS = 12 000). Поэтому проверяются три вещи: блок
снят, карточка называет канал поиска (`tools/rules_functions.py`), и тот же канал сообщает ровно
то же число функций, сколько живых детей `functional:` в базе. Третья проверка и есть замена
счётчикам: сравнивается не текст с текстом, а инструмент с деревом.

Запуск:
    python _l2_block_probe.py            # порядок блоков + сверка канала поиска с деревом

Слой сейчас один — `kb-rules`: генератор карточек уровня 3 написан для него, и зонд берёт
адрес, префикс функций и_children_rows_ из этого генератора. Для прочих слоёв проверка
включается в тот момент, когда слой переразвёрнут и получает свой генератор: правило порядка
(указатель — последний содержательный блок карточки слоя) для всех слоёв одно.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
for _p in (ROOT_DIR / "src", ROOT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402
import _make_rule_cards as MC  # noqa: E402

SECTION_RE = re.compile(r"(?m)^===[ \t]*([A-ZА-Я][A-ZА-Я_]*)")
BLOCK_RE = re.compile(r"(?m)^#{2,4}[ \t]+(.+?)\s*$")
# Снятый блок перечня (узел FUNC-SEARCH). Снимается его заголовок, а не формулировка: строки
# «Вариативные функции слоя (N)» и «Вариативные инструменты регистра (M)» порождает генератор,
# и их появление в строке значит, что блок вернулся — вместе с отставанием от детей.
REMOVED_BLOCK_RE = re.compile(r"Вариативные (?:функции слоя|инструменты регистра)")
# Число функций, которое сообщает канал поиска, — та же строка шапки, что печатает
# `tools/rules_functions.py`.
REPORTED_RE = re.compile(r"функций: (\d+)")


def main():
    with get_cursor() as cur:
        cur.execute("SELECT answer FROM knowledge_snippets WHERE question = %s",
                    (MC.LAYER_ADDRESS,))
        row = cur.fetchone()
        if not row:
            print(f"❌ карточка {MC.LAYER_ADDRESS} не найдена")
            return 1
        answer = row["answer"]

        # дети дерева: сколько функциональных карточек и сколько карточек инструментов.
        # Запрос берётся из генератора — тот же фильтр живых детей, что у блока-указателя,
        # иначе зонд сверял бы блок с другим набором строк.
        rows = MC.children_rows(cur)
        functional = [r["question"] for r in rows
                      if r["question"].startswith(MC.FUNCTIONAL_PREFIX)]

    sections = [(m.group(1), m.start()) for m in SECTION_RE.finditer(answer)]
    bounds = sections + [("END", len(answer))]
    print(f"карточка {MC.LAYER_ADDRESS}: {len(answer)} симв., секций {len(sections)}")
    blocks = []
    for (name, start), (_, end) in zip(bounds, bounds[1:]):
        body = answer[start:end]
        heads = [h for h in BLOCK_RE.findall(body)]
        print(f"\n=== {name} ({end - start} симв.), блоков `###`: {len(heads)}")
        for i, h in enumerate(heads, 1):
            print(f"   {i}. {h[:110]}")
            blocks.append((name, i, h))

    print("\n--- порядок верхнеуровневых разделов строки ---")
    print(" → ".join(name for name, _ in sections))

    last_content = next((name for name in reversed([n for n, _ in sections])
                         if name not in ("LINKS", "INDEX")), None)
    # заголовок блока в тексте без префикса `###`, поэтому игла тоже без него
    needle = MC.POINTER_HEADING.lstrip("#").strip().split(":", 1)[0].strip()
    pointer = [b for b in blocks if needle in b[2]]
    print(f"\nпоследняя содержательная секция: {last_content}"
          f" (технические LINKS/INDEX не считаются)")
    if not pointer:
        print("❌ блока-указателя в строке нет")
        return 1
    sec, pos, _ = pointer[0]
    total = sum(1 for b in blocks if b[0] == sec)
    print(f"указатель: секция {sec}, блок {pos} из {total}")
    print("✅ указатель — последний блок своей секции" if pos == total
          else f"❌ указатель не последний: после него ещё {total - pos} блок(ов)")
    last_block = blocks[-1]
    is_last = (sec, pos) == (last_block[0], last_block[1]) and sec == last_content
    print("✅ указатель — последний блок карточки: после него только технические LINKS/INDEX"
          if is_last else
          f"❌ после указателя остались содержательные блоки: "
          f"{[b[2][:60] for b in blocks if (b[0], b[1]) > (sec, pos)]}")

    print("\n--- состояние снятого блока перечня (узел FUNC-SEARCH) ---")
    removed = REMOVED_BLOCK_RE.search(answer)
    print("❌ блок перечня вернулся: карточка слоя снова пересказывает детей и отстаёт от них"
          if removed else "✅ блока перечня функций и инструментов в карточке нет")
    names_channel = "tools/rules_functions.py" in answer
    print("✅ карточка называет канал поиска функций" if names_channel else
          "❌ карточка слоя не называет `tools/rules_functions.py` — читатель не узнает, где "
          "искать функции слоя")

    # Функции, которые видит канал поиска, обязаны совпадать с детьми дерева. Блок снят именно
    # затем, чтобы перечень не отставал, поэтому сравнивается инструмент с базой, а не текст
    # с текстом: расхождение означает, что ответ о функциональности сервера зависит от того,
    # чем его спросили.
    proc = subprocess.run([sys.executable, str(ROOT_DIR / "tools" / "rules_functions.py"),
                           MC.LAYER], capture_output=True, text=True, encoding="utf-8",
                           cwd=str(ROOT_DIR))
    reported = REPORTED_RE.search(proc.stdout or "")
    told = int(reported.group(1)) if reported else -1
    print("\n--- сверка канала поиска с деревом ---")
    print(f"детей `functional:` в БД: {len(functional)}; "
          f"`tools/rules_functions.py {MC.LAYER}` сообщает: {told}")
    if told != len(functional):
        print("❌ канал поиска и дерево расходятся")
        print((proc.stdout or proc.stderr or "").strip()[:400])
    elif not removed and names_channel:
        print("✅ поиск функций и дерево совпадают")

    bad = bool(removed) or not names_channel or told != len(functional)
    return 1 if (bad or pos != total or not is_last) else 0


if __name__ == "__main__":
    sys.exit(main())
