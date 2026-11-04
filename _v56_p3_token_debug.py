import io
import tokenize

path = "_v56_p3_offline_probe.py"
src = io.open(path, encoding="utf-8").read()
lines = src.splitlines()
for n, line in enumerate(lines[:199], 1):
    count = line.count('"""')
    if count:
        print("TRIPLE", n, count, line.strip()[:70])
print("---- tokens near 198")
try:
    with io.open(path, encoding="utf-8", newline="") as handle:
        for token in tokenize.generate_tokens(handle.readline):
            if token.type == tokenize.STRING and token.start[0] <= 199:
                if token.start[0] >= 150 or token.end[0] >= 195:
                    print("STRING", token.start, token.end, token.string[:40])
except tokenize.TokenError as exc:
    print("TOKEN ERROR", exc)
