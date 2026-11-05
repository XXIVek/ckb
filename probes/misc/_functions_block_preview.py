"""Предпросмотр вариативной части карточки второго уровня — без записи в базу.

Зачем нужен: карточка слоя собирается генератором (`_make_rule_cards.py`), и смотреть её хочется
до того, как правка легла в строку БД. Отдельного описания блока этот скрипт не содержит — он
печатает вывод `_make_rule_cards.functions_block()` и `_make_rule_cards.rebuild_parent(..., dry)`
как есть. Копия текста в двух местах разошлась бы с генератором ровно на первой же правке дочерней
карточки (тот класс дефекта, из-за которого маршрут уровня 2 вёл в никуда).

Запуск:
    python _functions_block_preview.py            # блок указателя, который положит генератор
    python _functions_block_preview.py --diff     # чем он отличается от того, что в строке сейчас
    python _functions_block_preview.py --card     # вся карточка слоя после пересборки (в БД не пишет)
"""
import argparse
import difflib
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
for _p in (ROOT_DIR / "src", ROOT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import _make_rule_cards as M  # noqa: E402
import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402


def current_block(cur):
    """Тот блок указателя, который уже лежит в строке карточки слоя (пусто, если блока нет)."""
    cur.execute("SELECT answer FROM knowledge_snippets WHERE question = %s AND source_url = %s",
                (M.LAYER_ADDRESS, RL.source_url(M.LAYER_ADDRESS)))
    row = cur.fetchone()
    if not row:
        return ""
    return M.extract_block(row["answer"], M.POINTER_HEADING)


def main():
    parser = argparse.ArgumentParser(
        description="Показать блок вариативной части карточки слоя, не меняя базу")
    parser.add_argument("--diff", action="store_true",
                        help="сравнить с блоком, который сейчас в строке")
    parser.add_argument("--card", action="store_true",
                        help="показать карточку слоя целиком после пересборки (в БД не пишет)")
    args = parser.parse_args()

    with get_cursor() as cur:
        block = M.functions_block(cur)
        print(f"=== блок «{M.POINTER_HEADING.lstrip('# ').strip()}» — {len(block)} симв., "
              f"в БД не написано ничего ===\n")
        print(block)

        if args.diff:
            old = current_block(cur)
            delta = list(difflib.unified_diff(
                old.splitlines(), block.splitlines(),
                fromfile="в строке сейчас", tofile="положит генератор", lineterm=""))
            changed = sum(1 for d in delta if d.startswith(("+", "-")) and not d.startswith(("+++", "---")))
            print(f"\n=== различий строк: {changed} ===")
            print("\n".join(delta) if delta else "блока в строке нет или он совпадает — правки нет")

        if args.card:
            rebuilt = M.rebuild_parent(cur, dry=True)
            print("\n=== карточка слоя после пересборки (dry, в БД не пишет) ===")
            print(rebuilt[3] if rebuilt else "карточки слоя в базе нет")
    return 0


if __name__ == "__main__":
    sys.exit(main())
