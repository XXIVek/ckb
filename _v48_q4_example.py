#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Q4 узла V48: фактический фрагмент файла с ДВУМЯ ссылками — пример для решения.

Берёт `BGU2\SessionParameters\АвторизованныйПользователь.xml` (тот же файл, что в 2.4.3 и 2.5) и
печатает то, что видит разбор: корневой тег, `Name` и блок `<Type>` целиком. Только чтение.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PATH = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files\BGU2\SessionParameters"
            r"\АвторизованныйПользователь.xml")


def main() -> int:
    text = PATH.read_text(encoding="utf-8", errors="replace")
    print(PATH)
    print(re.search(r"<SessionParameter[^>]*>", text).group(0))
    print(re.search(r"<Name>[^<]*</Name>", text).group(0))
    print()
    print(re.search(r"<Type>.*?</Type>", text, re.S).group(0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
