"""Размер собираемой роли по слоям правил — измерение для теста в рабочем контуре.

Тест в новом контекстном окне фиксирует числа токенов; чтобы по числам судить о системе правил,
нужна вторая половина замера — сколько символов обязан загрузить каждый шаг. Скрипт печатает
состав роли по адресам: маршрутизатор IDE, всегда загружаемый набор (`ALWAYS_ADDRESSES` из
`tools/rules_read.py`) и карточки, которые поднимает тестовый промт.

Токены из этого не выводятся сами: перевод символов в токены зависит от модели и от кириллицы.
Поэтому числа теста калибруют отношение по известному приросту (шаг с `--always`), а дальше им
проверяют, сколько лишних карточек прочитал агент.
"""
import io
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
from database import get_cursor  # noqa: E402
import rules_read as RR  # noqa: E402

ROUTER = ROOT / ".clinerules" / "1C_Rule.md"

# Что поднимает тестовый промт: индекс слоя, карточка функции, путь авторинга, проверка.
HOPS = [
    "rules:kb-rules:",
    "rules:kb-rules:functional:rules-work",
    "rules:kb-rules:functional:rules-report",
    "rules:always:authoring",
    "rules:always:authoring:generated",
    "rules:checks:layer-verification",
    "rules:core-rules:",
    "rules:enrich-rules:",
]


def answer_len(cur, address):
    cur.execute(
        "SELECT length(answer) FROM knowledge_snippets WHERE question = %s "
        "AND source_url = %s",
        (address, "rules-layer://" + address),
    )
    row = cur.fetchone()
    return row["length"] if row else None


def command_sizes():
    """Длины вывода команд, которые обязан вызвать тестовый промт.

    Нужны затем, чтобы по числу токенов из рабочего окна считать содержимое: список команд агент
    приводит в блоке «ЗАМЕР», мы прогоняем те же команды и знаем точное число символов на каждую.
    Отношение токенов к символам калибруется по этой сумме, дальше им проверяют, сколько карточек
    прочитано сверх эталона.
    """
    commands = [
        ("--always (обязана быть первой)", ["tools/rules_read.py", "--always"]),
        ("--layers (поднять вариативный слой)", ["tools/rules_read.py", "--layers"]),
        ("rules:kb-rules: (слой знаний)", ["tools/rules_read.py", "rules:kb-rules:"]),
        ("--tree функциональных опций kb-rules",
         ["tools/rules_read.py", "--tree", "rules:kb-rules:functional:"]),
        ("rules:kb-rules:functional:rules-report (эталон ответа)",
         ["tools/rules_read.py", "rules:kb-rules:functional:rules-report"]),
        ("rules:always:authoring:generated (путь генератора)",
         ["tools/rules_read.py", "rules:always:authoring:generated"]),
        ("find правила (поиск словами — не эталон)",
         ["tools/rules_read.py", "find", "отчёт"]),
    ]
    print("\nдлины вывода команд, которые ожидаются в блоке «ЗАМЕР»:")
    for title, argv in commands:
        out = subprocess.run([sys.executable] + argv, cwd=str(ROOT),
                             capture_output=True, text=True, encoding="utf-8")
        text = (out.stdout or "") + (out.stderr or "")
        print(f"  {title:<48} {len(text):>7} симв.  (exit {out.returncode})")


def main():
    router_chars = len(ROUTER.read_text(encoding="utf-8"))
    print(f"маршрутизатор IDE  {ROUTER.relative_to(ROOT)}  {router_chars:>7} симв.")

    with get_cursor() as cur:
        print("\nвсегда загружаемый набор (tools/rules_read.py --always):")
        always_total = 0
        for address in RR.ALWAYS_ADDRESSES:
            n = answer_len(cur, address)
            always_total += n or 0
            print(f"  {address:<34} {n or 0:>7} симв.")
        print(f"  итого содержимого{'':<20} {always_total:>7} симв.")

        print("\nкарточки, которые поднимает тестовый промт:")
        hop_total = 0
        for address in HOPS:
            if address in RR.ALWAYS_ADDRESSES:
                print(f"  {address:<34} {'уже в always':>9}")
                continue
            n = answer_len(cur, address)
            if n is None:
                print(f"  {address:<34} {'нет карточки':>9}")
                continue
            hop_total += n
            print(f"  {address:<34} {n:>7} симв.")

    # Отрисовка `--always` целиком: то же содержимое, но с заголовками разделов — именно этот
    # текст попадает в окно, если агент вызывает инструмент.
    out = subprocess.run([sys.executable, "tools/rules_read.py", "--always"],
                        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8")
    rendered = len(out.stdout or "")
    print(f"\n--always как выдача инструмента: {rendered:>7} симв. "
          f"(с шапками; содержимое {always_total})")

    print(f"\nсценарии роли:")
    print(f"  T0 приветствие (один маршрутизатор) .: {router_chars:>7} симв.")
    print(f"  T1 + всегда загружаемый набор ........: {router_chars + rendered:>7} симв.")
    print(f"  T2 + карточки тестового промта ......: {router_chars + rendered + hop_total:>7} симв.")
    command_sizes()
    return 0


if __name__ == "__main__":
    sys.exit(main())
