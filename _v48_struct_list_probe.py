"""Зонд 2.9 плана V48: чтение нормативного списка оператора
`C:\\1C_LLM\\Структура конфигурации.txt` (29.10.2026, только чтение).

Считает позиции списка, сверяет с собственной строкой файла «Всего 47 подклассов», находит позицию
параметров сеанса и служебные пометки файла. Ничего не пишет и не меняет.
"""
import io
import re
import sys

PATH = r"C:\1C_LLM\Структура конфигурации.txt"


def main() -> int:
    try:
        lines = io.open(PATH, encoding="utf-8", errors="replace").read().splitlines()
    except OSError as error:
        print(f"файл не читается: {error}")
        return 1

    items = []
    for number, line in enumerate(lines, 1):
        match = re.match(r"^\s*(\d+(?:\.\d+)*)[.\s]\s*(.+?)\s*$", line)
        if match:
            items.append((match.group(1), match.group(2), number))

    declared = [line for line in lines if "подкласс" in line.lower()]
    second = [item for item in items if item[0].startswith("2.")]
    top = [item for item in items
           if re.fullmatch(r"\d+", item[0]) and item[0] not in ("1", "2")]
    nested = [item for item in items if re.fullmatch(r"\d+\.\d+", item[0])
              and not item[0].startswith("1.") and not item[0].startswith("2.")]

    print(f"строк в файле: {len(lines)}")
    print(f"строки файла о самом себе: {declared}")
    print(f"позиции раздела 2 (второй слой): {len(second)}")
    print(f"позиции разделов 3..N (верхний уровень): {len(top)}")
    print(f"вложенные позиции вида 5.1, 5.2: {nested}")
    total = len(second) + len(top) + len(nested)
    print(f"итог посчитанных позиций слоя 2 и далее: {total}")
    print(f"расхождение с собственной строкой файла (47): {abs(total - 47)}")
    session = [item for item in items if "SessionParameters" in item[1]]
    print(f"позиция параметров сеанса: {session}")
    done = [item for item in items if "Выполнено" in item[1]]
    print(f"позиции, помеченные «Выполнено»: {[i[0] for i in done]}")
    marks = [line.strip() for line in lines if "/" in line and "стоим" in line.lower()]
    print(f"служебные пометки вида «/ ... /»: {marks}")
    print("переход к разделу 3 и далее:", [line for line in lines if re.match(r"^3\.", line)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
