"""Аудит артефактов, названных живыми правилами (узел MEM-INDEX, 27.10.2026).

Зачем. `tools/check_rule_tool_coverage.py` (часть B) сторожит файлы, названные разделами
`CHECK` и `TOOLS` карточек. Проза карточки под тот сторож не попадает, и 27.10.2026 это дало
пропущенную ложь: карточка `rules:core-rules:checks:index` в абзаце «Граница проверок» звала
запустить `_layers_tree_probe.py`, которого в репозитории никогда не было (живая проверка —
`_layer_tree_check.py`, имя пришло из `_make_layer_rule_cards.py`). Правило говорит «проверка —
`python tools/x.py`»; если файла нет, правило читается, а проверка не повторяется.

Что делает. Берёт живые карточки правил (`source_url LIKE 'rules-layer://%'`, без помеченных к
удалению) и вытаскивает из их текста пути к `*.py`, `*.sql`, `*.md`. Каждый путь проверяется на
существование относительно корня репозитория и раскладывается по трём корзинам:

  битая ссылка  — строка утверждает настоящее время («проверка — …», «DDL — …»); такой файл
                  обязан существовать, это и есть провал проверки;
  происхождение — ссылка на прежний файл правил (`.clinerules/<слой>_Rule.md`), содержимое
                  которого перенесено в базу правилами, и карточки журнала: они называют источник
                  снимка, и отсутствующий источник для них — правда о прошлом, а не битая ссылка;
  история       — строка с маркерами снятого (→, «прежн», «удал», «снят», «перенес», «архив»,
                  «больше нет») или карточка снятого функционала (`:removed`): называть то, чего
                  нет, им предписано.

Граница: разбираются только пути файлов проекта; имена таблиц, колонок, URL и идентификаторы кода
не проверяются — для них нет понятия «файл на диске».

Запуск: `python tools/_named_artifacts_audit.py` (код возврата 1 — есть битые ссылки).
"""
import os
import re
import sys
from pathlib import Path

# Консоль Windows по умолчанию cp1251 и не кодирует символы вердикта (`✅`, `❌`) — аудит
# падал бы на выводе, а не на расхождении. Тот же приём, что в `validate_project.py`.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parents[1]
for _p in (ROOT_DIR / "src", ROOT_DIR / "tools", ROOT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

_NAME_INDEX = None

from database import get_cursor  # noqa: E402
from quarantine import MARK_ARRAY, sql_not_marked  # noqa: E402

# Путь внутри репозитория: tools/x.py, src/y/z.py, docs/x/y.md, .clinerules/x.md, _probe.py.
PATH_RE = re.compile(
    r"(?<![\w/.-])((?:\.clinerules|docs|src|tools)/[\w./\-]*\.(?:py|sql|md)|_"
    r"[\w\-]*\.(?:py|sql))"
)
# Снимок прежних текстов и снятый функционал: называть отсутствующее им предписано.
JOURNAL_MARK = ":journal:"
REMOVED_MARK = ":removed"
# Маркеры строки-истории — тот же приём, что у check_search_rules_sync (снимок не правится),
# плюс конструкции «названо именно для того, чтобы сказать, что этого нет».
HISTORY_MARKS = (
    "→", "прежн", "удал", "снят", "сним", "перенес", "архив", "ранее",
    "больше нет", "источник", "Источник", "до правки", "замер ",
    "ошибк", "несуществующ", "никогда не было", "файла с таким именем",
)
# Файлы прежних правил, перенесённые в базу правилами: ссылка на них = происхождение текста.
PROVENANCE_DIR = ".clinerules/"
# Проза карточек перенесена по строкам посреди предложения, поэтому контекстом берётся абзац
# вокруг совпадения: одна физическая строка не видит, что имя названо в рассказе об ошибке.
CONTEXT_LINES = 1


def name_index():
    """Файлы репозитория, индекс по имени: {'_x.py': ['probes/v48/_x.py', ...]}.

    Карточка правила называет артефакт коротким именем (`_v48_p8_stop_probe.py`), потому
    что так оно было записано в момент замера. С узла ROOT-RESTRUCTURE круг доказательств
    лежит в `probes/<узел>/`, и переписывать каждую историческую строку новым путём —
    значит стирать то, как выглядел замер на дату. Вопрос аудита другой: существует ли
    названный файл. На него отвечает поиск по имени, а не сравнение с одним каталогом.
    """
    global _NAME_INDEX
    if _NAME_INDEX is None:
        _NAME_INDEX = {}
        for base, dirs, files in os.walk(ROOT_DIR):
            dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'logs',
                                                    'Reports', '_ibcmd_work'}]
            rel = os.path.relpath(base, ROOT_DIR).replace('\\', '/')
            for name in files:
                if name.endswith(('.py', '.sql', '.md')):
                    _NAME_INDEX.setdefault(name, []).append(
                        name if rel == '.' else f'{rel}/{name}')
    return _NAME_INDEX


def resolves(path):
    """Названный артефакт есть в репозитории: по указанному пути или под своим именем."""
    if (ROOT_DIR / path.replace("/", "\\")).exists():
        return True
    if '/' in path:
        return False
    return bool(name_index().get(path))


def classify(address: str, line: str, path: str) -> str:
    """Корзина ссылки: происхождение и история правомочны, битая ссылка — провал."""
    if JOURNAL_MARK in address or path.startswith(PROVENANCE_DIR):
        return "provenance"
    if REMOVED_MARK in address:
        return "history"
    for mark in HISTORY_MARKS:
        if mark in line:
            return "history"
    return "broken"


def main():
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, question, answer FROM knowledge_snippets "
            "WHERE source_url LIKE %s" + sql_not_marked() + " ORDER BY question",
            ("rules-layer://%", MARK_ARRAY),
        )
        rows = [dict(r) for r in cur.fetchall()]

    broken, provenance, history = {}, set(), set()
    checked = 0
    for row in rows:
        address = row["question"]
        lines = (row["answer"] or "").splitlines()
        for idx, line in enumerate(lines):
            window = "\n".join(lines[max(0, idx - CONTEXT_LINES): idx + CONTEXT_LINES + 1])
            for path in sorted(set(PATH_RE.findall(line))):
                checked += 1
                if resolves(path):
                    continue
                kind = classify(address, window, path)
                if kind == "broken":
                    broken.setdefault(address, set()).add(path)
                elif kind == "provenance":
                    provenance.add(path)
                else:
                    history.add((address, path))

    print(f"карточек правил: {len(rows)}, ссылок проверено: {checked}")
    if broken:
        print("\n❌ живое правило называет отсутствующий файл (строка о настоящем времени):")
        for address in sorted(broken):
            for path in sorted(broken[address]):
                print(f"  {address} → {path}")
    else:
        print("✅ живые правила ссылаются на отсутствующее только как на происхождение или историю")
    print(f"\nпроисхождение (прежние файлы правил, перенесены в базу правилами): {len(provenance)}")
    for path in sorted(provenance):
        print(f"  · {path}")
    print(f"ссылки истории (снятое названо по смыслу): {len(history)}")
    for address, path in sorted(history)[:12]:
        print(f"  · {address} → {path}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
