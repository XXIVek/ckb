# Исправление pdf_parser.py
f = open(r"C:\1C_LLM\ckb\src\pdf_parser.py", "r", encoding="utf-8")
content = f.read()
f.close()

# Заменяем неправильные ключи на правильные с кавычками
replacements = [
    ('stats[docs_added]', 'stats["docs_added"]'),
    ('stats[fragments_added]', 'stats["fragments_added"]'),
    ('stats[snippets_added]', 'stats["snippets_added"]'),
]

for old, new in replacements:
    content = content.replace(old, new)

f = open(r"C:\1C_LLM\ckb\src\pdf_parser.py", "w", encoding="utf-8")
f.write(content)
f.close()

print("Исправлено!")
