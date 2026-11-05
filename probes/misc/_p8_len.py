"""Длина карточки правила по пунктам — замер перед делением (узел П8, план
`docs/RULES_CONTEXT_PLAN.md`).

Зачем. Мигратор отказывает, когда `answer` карточки превышает `MAX_ANSWER_CHARS`, и подсказывает
править её подразделом адресом. Какую часть выносить и хватит ли — решается по числам пунктов, а не
«на глаз»: разметка блока MUST по нумерованным пунктам даёт точную длину каждого.

Запуск:
    python _p8_len.py                                    # карточка, из-за которой возник узел
    python _p8_len.py --address rules:checks:index       # любая карточка слоя
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402

DEFAULT_ADDRESS = "rules:checks:layer-verification"


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Длина карточки правила по пунктам (только чтение исходника слоя)")
    ap.add_argument("--address", default=DEFAULT_ADDRESS,
                    help="адрес карточки в docs/rules/rules.md (по умолчанию та, что из узла П8)")
    ap.add_argument("--file", default="docs/rules/rules.md",
                    help="файл-исходник слоя (по умолчанию docs/rules/rules.md)")
    args = ap.parse_args(argv)

    path = ROOT / args.file
    cards, errors, fatal = RL.load_document(path)
    print(f"файл: {args.file}; карточек: {len(cards)}, ошибок разбора: {len(errors)}, fatal: {fatal}")
    print(f"MAX_ANSWER_CHARS = {RL.MAX_ANSWER_CHARS}")

    found = 0
    for c in cards:
        if c["address"] != args.address:
            continue
        found += 1
        text = c["answer"]
        verdict = "в лимите" if len(text) <= RL.MAX_ANSWER_CHARS else "ПРЕВЫШЕН"
        print(f"\n{c['address']}: {len(text)} симв. — {verdict}")
        head, _, rest = text.partition("===MUST")
        print(f"  шапка (WHEN и т.п.): {len(head)}")
        must, _, tail = rest.partition("===SOURCE")
        print(f"  блок MUST: {len(must)}, хвост после MUST: {len(tail)}")
        for p in re.split(r"\n(?=\d+\.\s)", must):
            label = p.split(".")[0][:3].strip()
            print(f"    п.{label:<3} {len(p):>5} | {' '.join(p.split())[:70]}")
    if not found:
        print(f"карточка {args.address!r} в файле не найдена — адреса перечисляет "
              f"`python _layer_ls.py` или `python src/rules_report.py --query <префикс>`")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
