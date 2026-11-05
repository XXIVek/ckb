import sys

sys.path.insert(0, "src")
from database import get_cursor  # noqa: E402

ADDRESS = "rules:core-rules:journal:node:v55"

with get_cursor() as cur:
    cur.execute("SELECT answer FROM knowledge_snippets WHERE question = %s", (ADDRESS,))
    text = cur.fetchone()["answer"]

print("LEN", len(text))
print("=== НАЧАЛО ===")
print(repr(text[:900]))
for anchor in ("расхождение названо здесь и в плане.", "Чего шаг П8 не делает"):
    print(f"=== ВХОЖДЕНИЯ {anchor!r}: {[i for i in range(len(text)) if text.startswith(anchor, i)]}")
pos = text.find("Чего шаг П8 не делает")
print("=== ХВОСТ ОТ ЯКОРЯ ===")
print(repr(text[pos:]))
