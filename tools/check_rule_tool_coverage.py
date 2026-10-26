"""Покрытие инструментов карточками правил и ссылки карточек в существующие файлы.

Инструмент решения вопроса «нужна ли функциональная опция». Сам вопрос возникает не из пустоты:
карточка-layer говорит, что функций слоя ищут `tools/rules_functions.py`, но этот канал отвечает
регистрами MCP-сервера, а скрипты вне MCP (`tools/*`, генераторы слоя) им не находятся. Остаётся
факт: назван ли инструмент живой карточкой или не назван ничем.

Две части, и они различаются знаком:

  A. инструменты, не названные ни одной живой карточкой, — не ошибка. Одноразовый зонд или
     завершённый переносчик правила не требуют: процедура, которая не повторяется, не имеет и
     правила. Строка A есть вопрос «повторяется ли действие?», а не утверждение о дефекте;
  B. имена файлов, названные разделами `CHECK`/`TOOLS` действующих карточек, которых нет в
     проекте, — ошибка. Карточка, отправляющая читателя подтверждать правило несуществующим
     скриптом, врёт о своём контракте. Таблицы индексов («чем проверяется») сторожит
     `check_rules_layer.py`, разделы `CHECK`/`TOOLS` до этого узла не сторожил никто.

Выход: 0, если часть B пуста. Часть A на код возврата не влияет намеренно: её читают люди,
принимающие решение о правиле.
"""
import argparse
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from database import get_cursor  # noqa: E402
from quarantine import MARK_ARRAY, sql_not_marked  # noqa: E402

SOURCE_SCHEME = "rules-layer://"
# Что считается инструментом: рабочие скрипты `tools/` и генераторы/проверки слоя в корне.
# Зонды `_d*_probe.py`, `_v*_probe.py` в перечень не кладутся: у разового замера нет процедуры,
# а значит нет и правила, которое его описывает.
ONE_OFF = re.compile(r"_(probe|ctx|dump|peek|scan|audit)_|_probe\.|_(d\d|v\d+[a-z]?)_")


def tool_files():
    """Файлы, покрытие которых считается: `tools/*` и корневые генераторы/проверки слоя."""
    found = []
    for path in sorted((ROOT / "tools").iterdir()):
        if path.is_file() and path.suffix in {".py", ".ps1"}:
            found.append(path)
    for path in sorted(ROOT.glob("_*.py")):
        if any(key in path.name for key in ("make_", "migrate_", "move_", "layer_", "verify_",
                                            "patch_", "readdress_", "journal_", "rule",
                                            "authoring")):
            found.append(path)
    return [p for p in found if not ONE_OFF.search(p.name)]


def covering_cards(cur, name):
    """Живые карточки, в тексте или адресе которых встречается имя файла."""
    cur.execute(
        "SELECT id, question FROM knowledge_snippets "
        "WHERE source_url LIKE %s AND (answer LIKE %s OR question LIKE %s)"
        + sql_not_marked() + " ORDER BY question",
        (SOURCE_SCHEME + "%", f"%{name}%", f"%{name}%", MARK_ARRAY),
    )
    return [row["question"] for row in cur.fetchall()]


# Имя файла в тексте карточки: `tools/foo.py`, `src/bar.py`, `_make_baz.py`, `validate_x.py`.
# Шаблоны с `<` (например `docs/rules/<метка>.md`) в выборку не берутся: их нечем проверить.
FILE_TOKEN = re.compile(r"[A-Za-z0-9_./\\-]+\.(?:py|ps1|sql|md)\b")


def scan_sections(text):
    """Текст разделов `===CHECK`/`===TOOLS` карточки — только он и считается ссылкой.

    Разделение ответственности: существование имён в таблицах индексов («чем проверяется») сторожит
    `check_rules_layer.py` пунктом формата 2 про колонку проверки; разделы `CHECK`/`TOOLS` не
    сторожит никто, и именно они говорят читателю, чем подтвердить правило. Проза карточки в
    расчёт не берётся: карточка снятого узла обязана называть то, чего больше нет, и требовать от
    неё существующих файлов — значит врать о её содержании.
    """
    blocks = []
    keep = False
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("==="):
            name = stripped.lstrip("=").strip().upper()
            keep = name.startswith(("CHECK", "TOOLS"))
            continue
        if keep:
            blocks.append(line)
    return "\n".join(blocks)
def named_artifacts(cur):
    """Имена файлов, на которые ДЕЙСТВУЮЩИЕ карточки ссылаются разделами `CHECK`/`TOOLS`.

    Снимки журнала (`…:journal:…`) исключены намеренно: они описывают состояние узла на дату и
    называют файлы, снятые к сегодняшнему дню, — снимок не является живым правилом. Не считаются и
    обрезанные токены: карточка пишет `docs/rules/<метка>.md` или `…_Rule.md`, и вытаскивать из
    многоточия имя файла значило бы требовать существования файла, которого никто не называл.
    """
    cur.execute(
        "SELECT question, answer FROM knowledge_snippets WHERE source_url LIKE %s "
        "AND question NOT LIKE %s" + sql_not_marked(),
        (SOURCE_SCHEME + "%", "%:journal:%", MARK_ARRAY),
    )
    found = {}
    for row in cur.fetchall():
        text = scan_sections(row["answer"])
        for match in FILE_TOKEN.finditer(text):
            before = text[match.start() - 1] if match.start() else " "
            after = text[match.end()] if match.end() < len(text) else " "
            if before in "…*<" or after in "*…>":
                continue
            found.setdefault(match.group(0), set()).add(row["question"])
    return found


def exists_in_project(name):
    """Есть ли файл в проекте по имени (карточки называют скрипты и в корне, и в `tools/`)."""
    if (ROOT / name).exists():
        return True
    return bool(list(ROOT.rglob(Path(name).name)))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="покрытие инструментов карточками правил; ссылки карточек на файлы")
    parser.add_argument("--term", help="показывать только инструменты, содержащие подстроку")
    args = parser.parse_args(argv)

    with get_cursor() as cur:
        print("=" * 74)
        print("A. ИНСТРУМЕНТЫ И КАРТОЧКИ, КОТОРЫЕ ИХ НАЗЫВАЮТ")
        print("   (пустая строка покрытия = вопрос «повторяется ли действие», а не дефект)")
        print("=" * 74)
        uncovered = []
        for path in tool_files():
            if args.term and args.term.lower() not in path.name.lower():
                continue
            cards = covering_cards(cur, path.name)
            rel = path.relative_to(ROOT).as_posix()
            if not cards:
                uncovered.append(rel)
                print(f"  ⚠️  {rel:<48} не назван ни одной живой карточкой")
                continue
            shown = ", ".join(cards[:3])
            more = f" +{len(cards) - 3}" if len(cards) > 3 else ""
            print(f"  ✅ {rel:<48} карточек: {len(cards):>2}  ← {shown}{more}")

        print()
        print("=" * 74)
        print("B. ССЫЛКИ ДЕЙСТВУЮЩИХ КАРТОЧЕК НА ФАЙЛЫ, КОТОРЫХ НЕТ В ПРОЕКТЕ")
        print("   (снимки журнала в расчёт не берутся: они называют состояние узла на дату)")
        print("=" * 74)
        broken = []
        for token, cards in sorted(named_artifacts(cur).items()):
            if not exists_in_project(token):
                broken.append((token, sorted(cards)))
        if not broken:
            print("  ✅ битых ссылок нет: каждый названный карточкой файл существует")
        else:
            for token, cards in broken:
                where = ", ".join(cards[:3])
                print(f"  ❌ {token:<48} назван карточкой, файла нет ← {where}")

    print()
    print(f"не названо карточками: {len(uncovered)}; битых ссылок: {len(broken)}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
