"""Одноразовое действие: снять хвост проверки — остаток прежнего тела функции,
оставшийся после замены контура 2 (строки после `raise SystemExit(main(sys.argv))`)."""
from pathlib import Path

path = Path(__file__).resolve().parents[2] / "tools" / "check_v54_scheduled_jobs.py"
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
cut = next(index for index, line in enumerate(lines)
           if "raise SystemExit(main(sys.argv))" in line)
print(f"строк было: {len(lines)}, оставляем: {cut + 1}")
path.write_text("".join(lines[:cut + 1]), encoding="utf-8", newline="")
