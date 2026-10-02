import sys
sys.path.insert(0, r"C:\1C_LLM\ckb")
from pathlib import Path
from src.pdf_parser_enhanced import parse_pdf_structure

pdf_dir = Path(r"C:\1C_LLM\ckb\docs\pdf")
files = [f for f in pdf_dir.iterdir() if "Глава 1" in f.name and ".pdf" in f.name]
f = files[0]
print(f"Файл: {f.name}")
doc = parse_pdf_structure(str(f))
print(f"Заголовок: {doc.title[:100]}")
print(f"Методов: {len(doc.methods)}")
for m in doc.methods[:20]:
    print(f"  - {m.name}: {m.description[:60]}")
print(f"Блоков кода: {len(doc.code_blocks)}")
for cb in doc.code_blocks[:5]:
    desc = f" ({cb.description})" if cb.description else ""
    print(f"  Код: {cb.code[:80]}...{desc}")
import sys
sys.path.insert(0, r"C:\1C_LLM\ckb")
from pathlib import Path
from src.pdf_parser_enhanced import parse_pdf_structure
import PyPDF2

pdf_dir = Path(r"C:\1C_LLM\ckb\docs\pdf")
files = [f for f in pdf_dir.iterdir() if "Глава 1" in f.name and ".pdf" in f.name]
f = files[0]
reader = PyPDF2.PdfReader(str(f))
text = reader.pages[2].extract_text()
print("Примеры строк из текста:")
for line in text.split(chr(10))[:30]:
    if any(kw in line for kw in ["Процедура", "Функция", "Справочник", "Документ", "Регистр"]):
        print(f"  >>> {line.strip()[:100]}")
