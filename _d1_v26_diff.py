"""_d1_v26_diff.py — сравнение макета-СКД исходного .erf и версии, отредактированной V26.

Зачем: компилятор СКД в COM-сеансе дал два разных отказа на два файла:
  исходный   {(27, 75)}: Неверные параметры "Перечисление.СтатусыРасходовУСН.НеСписаноНеОплачено"
  V26-edited {(16,  2)}: Таблица не найдена "РегистрНакопления.РасходыПриУСН.ОстаткиИОбороты"
Позиции — внутри текста запроса, поэтому нужно посмотреть и сам текст, и чем
отличается файл. Скрипт только читает.
"""
import difflib
import io
import re
import sys

BASE = r"C:\1C_LLM\ckb\_ibcmd_work\v26_probe\base\СравнениеУСНИ90_2\Templates\ОсновнаяСхемаКомпоновкиДанных\Ext\Template.xml"
EDIT = r"C:\1C_LLM\LoadDoc\Edit_V26_СравнениеУСНИ90_2\СравнениеУСНИ90_2\Templates\ОсновнаяСхемаКомпоновкиДанных\Ext\Template.xml"
QUERY_RE = re.compile(r"<query>(.*?)</query>", re.S)


def read(path):
    return io.open(path, encoding="utf-8").read()


def queries(text):
    return QUERY_RE.findall(text)


def show_query(qs, label):
    print(f"--- {label}: запросов {len(qs)} ---")
    for n, q in enumerate(qs):
        lines = q.split("\n")
        print(f"  запрос #{n}: строк {len(lines)}, длина {len(q)}")
        for i, line in enumerate(lines[:30], start=1):
            print(f"    {i:>3}: {line[:150]}")


def main():
    a, b = read(BASE), read(EDIT)
    print(f"base bytes {len(a)}, edit bytes {len(b)}")
    diff = list(difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm="", n=1))
    print(f"--- DIFF (строк {len(diff)}) ---")
    for line in diff[:200]:
        print(line[:220])
    show_query(queries(a), "BASE (исходный .erf)")
    show_query(queries(b), "EDIT (V26)")


if __name__ == "__main__":
    sys.exit(main())
