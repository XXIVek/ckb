import io

P = "_v53_p8_legacy_probes_patch.py"
t = io.open(P, encoding="utf-8").read()
pairs = [
    ('список: 2.3 → 2.4 → 2.5 → 2.6 → 2.7 →\\n\'\n     \'      " 2.8 →',
     'список: 2.3 → 2.4 → 2.5 → 2.6 → 2.7 → "\\n\'\n     \'      "2.8 →'),
    ('список: 2.4 → 2.5 → 2.6 → 2.7 →\\n\'\n     \'      " 2.8 →',
     'список: 2.4 → 2.5 → 2.6 → 2.7 → "\\n\'\n     \'      "2.8 →'),
]
for old, new in pairs:
    print(repr(old[:50]), "встреч:", t.count(old))
    t = t.replace(old, new)
io.open(P, "w", encoding="utf-8", newline="").write(t)
print("готово")
