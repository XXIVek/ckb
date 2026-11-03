"""Читает вывод, записанный редиректом PowerShell (байты UTF-8 прочитаны как cp866).

Файлы проб и проверок пишутся в терминальной кодировке DOS, поэтому кириллица в них
сохранилась как псевдографика. Строка возвращается прежним текстом, если восстановление
не удалось, — молча подменять вывод ошибкой нельзя.

    python _v54_p5_out_read.py <файл> [ключевое_слово ...]
"""
import io
import sys


def recover(text: str) -> str:
    try:
        return text.encode("cp866", errors="strict").decode("utf-8", errors="strict")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def main() -> int:
    path = sys.argv[1]
    marks = sys.argv[2:]
    text = recover(io.open(path, encoding="utf-8", errors="replace").read())
    lines = text.splitlines()
    if not marks:
        print("\n".join(lines[-15:]))
        return 0
    hits = [line for line in lines if any(mark in line for mark in marks)]
    print(f"HITS {len(hits)}")
    for line in hits[:40]:
        print(line.strip()[:200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
