# Исправление строк 406-409 в pdf_parser.py
f = open(r"C:\1C_LLM\ckb\src\pdf_parser.py", "r", encoding="utf-8")
lines = f.readlines()
f.close()

for i, line in enumerate(lines):
    if 'Документов' in line and 'stats[' not in line:
        lines[i] = '            print(f"   Документов: {stats[chr(34)+chr(100)+chr(111)+chr(99)+chr(115)+chr(95)+chr(97)+chr(100)+chr(100)+chr(101)+chr(100)+chr(34)]}")\n'
    elif 'Фрагментов' in line and 'stats[' not in line:
        lines[i] = '            print(f"   Фрагментов: {stats[chr(34)+chr(102)+chr(114)+chr(97)+chr(103)+chr(109)+chr(101)+chr(110)+chr(116)+chr(115)+chr(95)+chr(97)+chr(100)+chr(100)+chr(101)+chr(100)+chr(34)]}")\n'
    elif 'Алиасов' in line and 'aliases_added' in line:
        lines[i] = '            print(f"   Алиасов: {stats[chr(34)+chr(97)+chr(108)+chr(105)+chr(97)+chr(115)+chr(95)+chr(97)+chr(100)+chr(100)+chr(101)+chr(100)+chr(34)]}")\n'
    elif 'Snippets' in line and 'stats[' not in line:
        lines[i] = '            print(f"   Snippets: {stats[chr(34)+chr(115)+chr(110)+chr(105)+chr(112)+chr(112)+chr(101)+chr(116)+chr(115)+chr(95)+chr(97)+chr(100)+chr(100)+chr(101)+chr(100)+chr(34)]}")\n'

f = open(r"C:\1C_LLM\ckb\src\pdf_parser.py", "w", encoding="utf-8")
f.writelines(lines)
f.close()

print("Исправлено!")
