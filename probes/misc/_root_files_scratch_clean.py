"""Очистка `_scratch/` по признаку «файл назван доказательством» (узел ROOT-FILES, 06.11.2026).

Критерий тот же, что у `probes/README.md` и узла ROOT-RESTRUCTURE: файл хранится, если на
него есть ссылка норматива — плана, карточки правила, кода проверки или другого зонда. Вывод
замера, который никем не назван, не доказывает ни одно число и не воспроизводит его: повторный
прогон зонда даёт его заново. Поэтому удаляем ровно неназванное, а не «старое».

Ссылки собираются из двух мест, и оба обязательны:
  - `git grep` по отслеживаемым файлам (планы `docs/*_PLAN.md`, правила `docs/rules/rules.md`,
    код зондов и проверок);
  - карточки обеих баз (`local_doc`, `ckb_1c_configurations`) — правило называет файл вывода,
    на который ссылается замер, и код при этом этого имени не содержит.

Токен трактуется как префикс: ссылка на каталог фикстур или на половину имени покрывает файл.
Пути, собранные в коде из сегмента (`BASE / "_scratch" / "<имя>.txt"`), — вторым шаблоном.

Запуск без `--write` только печатает. `--write` удаляет файлы; каталоги не удаляются никогда,
кроме `__pycache__`: каталог может быть входными данными зонда (копия конфигурации, фикстуры),
и отсутствие ссылки в тексте это не проверяет.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = ROOT / "_scratch"
DBS = ("local_doc", "ckb_1c_configurations")
# имя | ответ | вопрос | описание группы | заголовок группы
SQL = {
    "local_doc": """
        SELECT (regexp_matches(t, '_scratch/[A-Za-z0-9_./-]+', 'g'))[1]
        FROM (SELECT answer AS t FROM knowledge_snippets
              UNION ALL SELECT question FROM knowledge_snippets
              UNION ALL SELECT coalesce(description,'') || ' ' || coalesce(title,'')
                    FROM groups) s
    """,
    # в ckb_1c_configurations карточек с путями нет: таблица config_snippets есть,
    # обращений `_scratch/` в ней 0 — запрос оставлен, чтобы это проверялось, а не предполагалось
    "ckb_1c_configurations": """
        SELECT (regexp_matches(t, '_scratch/[A-Za-z0-9_./-]+', 'g'))[1]
        FROM (SELECT answer AS t FROM config_snippets
              UNION ALL SELECT question FROM config_snippets) s
    """,
}
# путь в коде собирается сегментами: BASE / "_scratch" / "_v54_p3_out.txt"
RE_GIT_A = re.compile(r"_scratch/[A-Za-z0-9_./-]+")
RE_GIT_B = re.compile(r"['\"]_scratch['\"]\s*/\s*['\"]([A-Za-z0-9_.-]+)")
# дамп БД — не вывод замера: это точка восстановления, её решение удалять — решение оператора.
# признак — имя (`_backup_...`), а не расширение: дамп local_doc лежит как `.sql` (замер 06.11.2026)
RE_NEVER = re.compile(r"(\.dump|\.bak)$|^_backup[_.]", re.I)


def norm(token):
    t = token.replace("\\", "/").lower().rstrip("/")
    if t.endswith("."):            # конец предложения в тексте правила
        t = t[:-1]
    return t


def refs_git():
    # --fixed-strings по всему содержимому отслеживаемых файлов: шаблоны имён вытаскиваем сами,
    # потому что путь в коде собирается сегментами и единого токена в строке может не быть
    full = subprocess.run(["git", "grep", "-h", "-I", "--fixed-strings", "--", "_scratch"],
                          cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                          errors="replace").stdout or ""
    found = {norm(t) for t in RE_GIT_A.findall(full)}
    for tail in RE_GIT_B.findall(full):
        found.add(norm("_scratch/" + tail))
    return found


def refs_db():
    found = set()
    for db in DBS:
        conn = psycopg2.connect(host="localhost", dbname=db, user="postgres",
                                password="Sta090860")
        try:
            with conn, conn.cursor() as cur:
                cur.execute(SQL[db])
                found |= {norm(r[0]) for r in cur.fetchall()}
        finally:
            conn.close()
    return found


def referenced(rel, refs):
    return any(rel == t or rel.startswith(t) or t.startswith(rel) for t in refs)


def own_output():
    """Файл, в который сейчас пишется вывод процесса, если он лежит в `_scratch/`.

    Перенаправление `python ... > _scratch/report.txt` делает отчёт неназванным выводом, и
    первый же прогон удалил бы файл, в который он сам пишется (замер 06.11.2026:
    `PermissionError: [WinError 32]`, удаление оборвалось на середине)."""
    try:
        path = Path(getattr(sys.stdout, "name", "")).resolve()
    except (OSError, ValueError):
        return None
    return path if SCRATCH in path.parents else None


def main(argv=None):
    argv = argv or sys.argv[1:]
    write = "--write" in argv
    top = int(argv[argv.index("--top") + 1]) if "--top" in argv else 0
    git_refs, db_refs = refs_git(), refs_db()
    refs = git_refs | db_refs
    print(f"ссылок: git {len(git_refs)}, БД {len(db_refs)}, всего {len(refs)}")

    gone, kept, never = [], [], []
    own = own_output()
    for path in sorted(SCRATCH.rglob("*")):
        if path.is_dir():
            continue
        if own and path.samefile(own):
            continue
        if RE_NEVER.search(path.name):
            never.append(path)
            continue
        rel = "_scratch/" + path.relative_to(SCRATCH).as_posix().lower()
        (kept if referenced(rel, refs) else gone).append(path)

    def mb(paths):
        return round(sum(p.stat().st_size for p in paths) / 1024 / 1024, 1)

    print(f"файлов: {len(gone) + len(kept) + len(never)}  |  удалить {len(gone)} ({mb(gone)} МБ)  "
          f"|  оставить {len(kept)} ({mb(kept)} МБ)  |  не трогать {len(never)} ({mb(never)} МБ)")
    for path in never:
        print(f"  дамп БД, не вывод замера: {path.relative_to(SCRATCH)}  "
              f"{path.stat().st_size/1048576:.1f} МБ")
    if top:
        print(f"крупнейшие оставленные (названы доказательством — удаление решает оператор):")
        for path in sorted(kept, key=lambda p: -p.stat().st_size)[:top]:
            print(f"  {path.stat().st_size/1048576:>7.1f} МБ  {path.relative_to(SCRATCH)}")
    print("каталоги (не удаляются — могут быть входными данными зонда):")
    for d in sorted(p for p in SCRATCH.iterdir() if p.is_dir()):
        size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
        rel = ("_scratch/" + d.name).lower()
        mark = "назван" if referenced(rel, refs) else "не назван"
        print(f"  {d.name:<22} {len(list(d.rglob('*'))):>5} эл. {size/1024/1024:>7.1f} МБ  {mark}")

    if not write:
        print("черновик: запуск без --write ничего не удалил")
        return 0
    busy, freed, freed_bytes = [], 0, 0
    for path in gone:
        try:
            freed_bytes += path.stat().st_size   # размер берётся до удаления: после — файла нет
            path.unlink()
            freed += 1
        except PermissionError:
            busy.append(path)   # файл занят другим процессом — удаление повторят следующим прогоном
    for path in busy:
        print(f"  занят процессом, не удалён: {path.relative_to(SCRATCH)}")
    cache = SCRATCH / "__pycache__"
    if cache.is_dir():
        shutil.rmtree(cache)
    empty = [d for d in SCRATCH.iterdir() if d.is_dir() and not any(d.iterdir())]
    for d in empty:
        d.rmdir()
    left = [p for p in SCRATCH.rglob("*") if p.is_file()]
    print(f"удалено {freed} файлов, {freed_bytes/1048576:.1f} МБ; занято {len(busy)}; "
          f"в каталоге осталось {len(left)} файлов ({mb(left)} МБ)")
    return 1 if busy else 0


if __name__ == "__main__":
    raise SystemExit(main())
