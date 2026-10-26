import re

s = "закрыта открытая позиция узла V42 — заголовки"
i = s.find("V42")
print("slice:", repr(s[i - 6:i + 4]))
print("ords:", [hex(ord(c)) for c in s[i - 6:i + 4]])
p = "узел"
print("pattern ords:", [hex(ord(c)) for c in p])
print("plain find:", s.find(p))
print("regex:", bool(re.search(p + r"\w*", s, re.I)))

