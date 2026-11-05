"""Синхронизация черновика `docs/rules/rules.md` со строками БД по указанным адресам.

Нужна перед `migrate_rules_to_layer.py --apply`: мигратор пишет в базу то, что читает из черновика,
и если строку правили в обход черновика (сценарным скриптом или `update_snippet_tool`), `--apply`
молча вернёт более старое содержимое. Замер 26.10.2026: `rules:reserved:layer-migration` 1760
символов в БД против 932 в черновике, `rules:always:reading` 2130 против 2110.

Раздел черновика = `## <адрес>` до следующего заголовка того же или более высокого уровня; тело
раздела ровно равно `answer` строки, поэтому замена безопасна: формат карточки задаёт строка.
"""
import argparse
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from database import get_cursor  # noqa: E402

MD = ROOT / "docs" / "rules" / "rules.md"
HEAD = re.compile(r"^## (\S+)\s*$", re.MULTILINE)


def sections(text):
    """[(адрес, начало_тела, конец_тела)] по заголовкам `## <адрес>`."""
    found = []
    marks = list(HEAD.finditer(text))
    for i, match in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        found.append((match.group(1), match.end(), end))
    return found


def main(argv):
    parser = argparse.ArgumentParser(
        description="привести разделы черновика `docs/rules/rules.md` к строкам БД "
                    "(или записать в черновик текст из файла)")
    parser.add_argument("addresses", nargs="*", help="адреса карточек слоя: текст берётся из БД")
    parser.add_argument("--set", nargs=2, action="append", metavar=("АДРЕС", "ФАЙЛ"),
                        help="заменить раздел адреса текстом из файла (для новой или сокращённой)")
    args = parser.parse_args(argv)

    text = MD.read_text(encoding="utf-8")

    def replace(address, body):
        nonlocal text
        for found_address, start, end in sections(text):
            if found_address != address:
                continue
            old_len = end - start
            text = text[:start] + "\n" + body.rstrip("\n") + "\n" + text[end:]
            print(f"  ♻️  {address}: черновик {old_len} → {len(body.rstrip(chr(10))) + 1} симв.")
            return True
        print(f"  ⚠️  {address}: раздела черновика нет — правка пропущена")
        return False

    with get_cursor() as cur:
        for address in args.addresses:
            cur.execute(
                "SELECT answer FROM knowledge_snippets WHERE question = %s "
                "AND source_url = %s",
                (address, "rules-layer://" + address),
            )
            row = cur.fetchone()
            if not row:
                print(f"  ⚠️  {address}: строки слоя в БД нет — раздел не правится")
                continue
            replace(address, row["answer"])

    for address, filename in args.set or []:
        path = Path(filename)
        if not path.exists():
            print(f"  ⚠️  {address}: файла {filename} нет")
            continue
        replace(address, path.read_text(encoding="utf-8"))

    MD.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
