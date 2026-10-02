# Финальное исправление
lines = open(r"C:\1C_LLM\ckb\src\pdf_parser.py", "r", encoding="utf-8").readlines()
lines[405] = '            print(f"   Документов: {stats["docs_added"]}")\n'
lines[406] = '            print(f"   Фрагментов: {stats["fragments_added"]}")\n'
lines[407] = '            print(f"   Алиасов: {stats["aliases_added"]}")\n'
lines[408] = '            print(f"   Snippets: {stats["snippets_added"]}")\n'
open(r"C:\1C_LLM\ckb\src\pdf_parser.py", "w", encoding="utf-8").writelines(lines)
print("Исправлено!")
