# Исправление pdf_parser.py - финальное
f = open(r"C:\1C_LLM\ckb\src\pdf_parser.py", "r", encoding="utf-8")
content = f.read()
f.close()

old_lines = [
    '            print(f"   Документов: {"docs_added"}")',
    '            print(f"   Фрагментов: {"fragments_added"}")',
    '            print(f"   Алиасов: {stats[aliases_added]}")',
    '            print(f"   Snippets: {"snippets_added"}")',
]

new_lines = [
    '            print(f"   Документов: {stats[chr(39)+chr(100)+chr(111)+chr(99)+chr(115)+chr(95)+chr(97)+chr(100)+chr(100)+chr(101)+chr(100)+chr(39)]}")',
    '            print(f"   Фрагментов: {stats[chr(39)+chr(102)+chr(114)+chr(97)+chr(103)+chr(109)+chr(101)+chr(110)+chr(116)+chr(115)+chr(95)+chr(97)+chr(100)+chr(100)+chr(101)+chr(100)+chr(39)]}")',
    '            print(f"   Алиасов: {stats[chr(39)+chr(97)+chr(108)+chr(105)+chr(97)+chr(115)+chr(95)+chr(97)+chr(100)+chr(100)+chr(101)+chr(100)+chr(39)]}")',
    '            print(f"   Snippets: {stats[chr(39)+chr(115)+chr(110)+chr(105)+chr(112)+chr(112)+chr(101)+chr(116)+chr(115)+chr(95)+chr(97)+chr(100)+chr(100)+chr(101)+chr(100)+chr(39)]}")',
]

for old, new in zip(old_lines, new_lines):
    content = content.replace(old, new)

f = open(r"C:\1C_LLM\ckb\src\pdf_parser.py", "w", encoding="utf-8")
f.write(content)
f.close()

print("Исправлено!")
