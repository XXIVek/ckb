"""Пишет фрагмент файла построчно в другой файл — для чтения частями.

Инструмент чтения файлов отдаёт файл целиком или диапазоном; когда середина попадает в
усечение, фрагмент копируется сюда и читается как отдельный файл. Нумерация строк
сохраняется, чтобы правку можно было назвать адресом строки.

    python _v54_p5_slice.py <файл> <начало> <конец> <файл_выхода>
"""
import io
import sys


def main() -> int:
    src, start, end, dst = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    lines = io.open(src, encoding="utf-8").read().splitlines()
    chunk = [f"{n}: {line}" for n, line in enumerate(lines[start - 1:end], start=start)]
    io.open(dst, "w", encoding="utf-8").write("\n".join(chunk))
    print(f"LINES {len(chunk)} OF {len(lines)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
