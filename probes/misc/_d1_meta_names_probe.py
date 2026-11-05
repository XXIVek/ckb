# -*- coding: utf-8 -*-
r"""_d1_meta_names_probe.py — как через COM обратиться к отчёту конфигурации (pywin32).

Замеры противоречат друг другу, и каждая причина названа:
  * PowerShell: $md.('Отчеты') вернул null, а $null.Count в PS7 = 0 - то есть «0 отчётов»
    было артефактом языка, а не фактом базы (_d1_ib_state_probe.ps1);
  * VBScript: лексер не принимает кириллические идентификаторы («Недопустимый знак» на
    mgr.Создать()) - приём из статьи в чистом VBS с русскими именами не компилируется;
  * ibcmd прямо сказал, что конфигурация в ИБ есть: «конфигурация находится на поддержке
    без возможности редактирования» (отказ config load), поэтому путь статьи принципиально
    применим - вопрос только в форме обращения через IDispatch.

Здесь pywin32: исключения настоящие, имена проверяются и русские, и английские.
Только чтение; сеанс закрывается в finally.
"""
import sys

import win32com.client

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

IB = r"C:\1C_LLM\ckb\_ibcmd_work\ib_bp3"
REPORT = "АнализЖурналаРегистрации"


def probe(label, call):
    try:
        value = call()
        print(f"  [OK  ] {label} -> {value!r}"[:400])
        return value
    except Exception as exc:
        print(f"  [FAIL] {label} -> {' '.join(str(exc).split())[:200]}")
        return None


def main():
    connector = win32com.client.Dispatch("V83.COMConnector")
    session = connector.Connect(f'File="{IB}";')
    try:
        print("=== сеанс ===")
        probe("session.ИмяБазы", lambda: session.ИмяБазы)
        md = probe("session.Метаданные()", lambda: session.Метаданные())
        if md is None:
            return 1

        print()
        print("=== конфигурация ===")
        probe("Метаданные().Имя", lambda: md.Имя)
        probe("Метаданные().Версия", lambda: md.Версия)

        print()
        print("=== коллекции отчётов ===")
        for base_name, base in (("Метаданные().Отчеты", md.Отчеты),
                                ("session.Отчеты", session.Отчеты)):
            probe(f"{base_name}.Count()", lambda base=base: base.Count())
            probe(f"{base_name}.Количество()", lambda base=base: base.Количество())
            probe(f"{base_name}.Получить(0).Имя", lambda base=base: base.Получить(0).Имя)
            probe(f"{base_name}.{REPORT}", lambda base=base: getattr(base, REPORT))

        print()
        print("=== поиск по полному имени ===")
        for full in (f"Отчет.{REPORT}", f"Report.{REPORT}"):
            probe(f"Метаданные().НайтиПоИмени({full!r})",
                  lambda full=full: md.НайтиПоИмени(full))
        return 0
    finally:
        try:
            session.Закрыть()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
