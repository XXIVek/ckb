"""V50 П0: быстрый снимок раскладки `CommonAttributes/` по четырём выгрузкам.

Отчёт пишется в `_scratch/v50_p0_layout.txt` (UTF-8): в терминале кириллица не читается.
Ничего в БД не меняет — только читает файлы.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
DIR_NAME = "CommonAttributes"
OUT = Path(__file__).resolve().parent / "_scratch" / "v50_p0_layout.txt"

lines: list[str] = []


def emit(text: str = "") -> None:
    lines.append(text)


for dump in DUMPS:
    base = DUMP_ROOT / dump / DIR_NAME
    emit(f"=== {dump}: {base}")
    if not base.is_dir():
        emit("  каталога нет")
        emit()
        continue
    top_xml = sorted(p for p in base.iterdir() if p.is_file() and p.suffix.lower() == ".xml")
    other_files = sorted(p for p in base.iterdir() if p.is_file() and p.suffix.lower() != ".xml")
    subdirs = sorted(p for p in base.iterdir() if p.is_dir())
    emit(f"  xml верхнего уровня: {len(top_xml)}, байт: {sum(p.stat().st_size for p in top_xml)}")
    emit(f"  прочие файлы верхнего уровня: {len(other_files)}")
    for p in other_files[:10]:
        emit(f"    {p.name}  {p.stat().st_size} байт")
    emit(f"  подкаталогов: {len(subdirs)}")
    for d in subdirs:
        all_files = sorted(q for q in d.rglob("*") if q.is_file())
        emit(f"    {d.name}: файлов {len(all_files)}, байт {sum(q.stat().st_size for q in all_files)}")
        for q in all_files[:20]:
            emit(f"      {q.relative_to(d)}  {q.stat().st_size}")
    emit()

# Копии двух первых файлов метаданных и первого содержимого — чтобы посмотреть форму XML.
sample_dirs = []
for dump in ("MinCfg", "KomMag", "BGU2"):
    base = DUMP_ROOT / dump / DIR_NAME
    if not base.is_dir():
        continue
    for p in sorted(base.rglob("*.xml"))[:3]:
        dst = (Path(__file__).resolve().parent / "_scratch"
               / f"v50_sample_{dump}_{p.relative_to(base)}".replace("/", "_"))
        shutil.copyfile(p, dst.with_suffix(".xml"))
        sample_dirs.append((str(p), dst.name, p.stat().st_size))
emit("=== копии образцов XML")
for src, name, size in sample_dirs:
    emit(f"  {size:>8}  {name}  <-  {src}")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines), encoding="utf-8")
print("отчёт:", OUT, "строк:", len(lines), "образцов:", len(sample_dirs))
