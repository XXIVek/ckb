"""Узел V57, шаг П7: склейка разобранных на строки рядов матрицы групп A–H.

Причина появления файла: правка карточек и текста живыми инструментами вставляет текст с
переводом строк, а markdown-ряд таблицы обязан оставаться ОДНОЙ строкой — многострочный ряд
перестаёт быть рядом. Файл идемпотентен: повторный прогон не находит рядов для склейки и
ничего не меняет.

Рядом считается строка, начинающаяся с `| **<буква группы>.`; ряд считается законченным,
когда число разделителей `|` в накопленном тексте равно числу разделителей эталонного ряда
той же таблицы (эталон берётся по строке заголовка таблицы, идущей перед рядами).
"""
import io
import sys

PATH = "docs/config-scenarios/01_configuration.md"
GROUP_ROWS = ("| **A. ", "| **B. ", "| **C. ", "| **D. ", "| **E. ", "| **F. ", "| **G. ", "| **H. ")


def main() -> int:
    text = io.open(PATH, encoding="utf-8").read()
    lines = text.split("\n")

    # Эталон числа разделителей: строка заголовка таблицы групп (| Группа | Что в выгрузке | …).
    header_index = next(i for i, line in enumerate(lines) if line.startswith("| Группа | Что в выгрузке"))
    separator_count = lines[header_index].count("|")

    changed = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith(GROUP_ROWS):
            i += 1
            continue
        if line.count("|") >= separator_count:
            i += 1
            continue
        parts = [line]
        j = i + 1
        while j < len(lines) and sum(part.count("|") for part in parts) < separator_count:
            parts.append(lines[j])
            j += 1
            if j - i > 40:
                raise SystemExit(f"ряд от {i + 1} не склеивается за 40 строк — предположение неверно")
        joined = " ".join(part.strip() for part in parts)
        if joined.count("|") != separator_count:
            raise SystemExit(
                f"ряд от {i + 1}: после склейки разделителей {joined.count('|')}, "
                f"ожидалось {separator_count}"
            )
        lines[i : j] = [joined]
        changed.append((i + 1, len(parts), len(joined)))
        i += 1

    if not changed:
        print("РЯДОВ ДЛЯ СКЛЕЙКИ НЕТ — файл не изменён")
        return 0

    io.open(PATH, "w", encoding="utf-8").write("\n".join(lines))
    for start, joined_from, length in changed:
        print(f"СКЛЕЕНО: строка {start} из {joined_from} физических строк в одну, длина {length}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
