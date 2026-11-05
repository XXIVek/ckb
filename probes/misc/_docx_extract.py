"""Извлечение текста из .docx в plain text (zip -> word/document.xml).

Нужно потому, что load_doc_tool MCP `1c-knowledge-base` понимает .html/.pdf/.md, а .docx - нет:
это бинарный zip, и read_files его тоже не отдаёт. Скрипт печатает текст в stdout или пишет
в указанный файл, сохраняя абзацы, переводы строк, табуляцию и таблицы (строки - перенос,
колонки - таб). Форматирование (шрифты, цвета) опускается: для поиска по смыслу оно не нужно.

Запуск:  python _docx_extract.py <путь.docx> [файл_результата.txt]
"""
import re
import sys
import zipfile

CELL = "\t"


def _text_of(xml_fragment):
    """Текст фрагмента XML: w:t + табуляция/переносы, без вложенных тегов."""
    parts = []
    for m in re.finditer(r"<w:(t|tab|br|cr)\b[^>]*>(.*?)</w:\1>|<w:(tab|br|cr)\b[^>]*/>",
                         xml_fragment, re.S):
        if m.group(3):
            parts.append({"tab": "\t", "br": "\n", "cr": "\n"}[m.group(3)])
        else:
            parts.append(m.group(2))
    text = "".join(parts)
    for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'),
                 ("&apos;", "'"), ("&amp;", "&")):
        text = text.replace(a, b)
    return text


def extract(docx_path):
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    body = re.search(r"<w:body\b.*</w:body>", xml, re.S)
    xml = body.group(0) if body else xml
    out = []
    # таблицы: строка -> строка текста, колонки через таб
    for tbl in re.findall(r"<w:tbl\b.*?</w:tbl>", xml, re.S):
        for row in re.findall(r"<w:tr\b.*?</w:tr>", tbl, re.S):
            cells = [_text_of(c).strip() for c in re.findall(r"<w:tc\b.*?</w:tc>", row, re.S)]
            if any(cells):
                out.append(CELL.join(cells))
        out.append("")
    # абзацы вне таблиц
    for p in re.findall(r"<w:p\b[^r].*?</w:p>|<w:p\b[^r]*/>", xml, re.S):
        line = _text_of(p)
        if line.strip():
            out.append(line.rstrip())
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    src = sys.argv[1]
    text = extract(src)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"строк: {len(text.splitlines())}  символов: {len(text)}  -> {sys.argv[2]}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
