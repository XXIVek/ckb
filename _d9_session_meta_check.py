# -*- coding: utf-8 -*-
"""D-9 — проверка сеанса 1С по ОДНОЙ ИБ из аргумента (после `ibcmd config apply`).

D-7 показал: в сеансе реальной базы БП3 оба .erf загружаются, в сеансе ibcmd-ИБ —
падают текстами D-4. D-8 показал, что хранилище конфигурации в `ib_bp3` есть
(`ibcmd config export info` отдаёт полный ConfigDumpInfo БП3), но `config load`
отказывается («конфигурация на поддержке»), а запущенный сеанс видит пустую
конфигурацию. Гипотеза механизма: мост V25 намеренно НЕ выполняет `config apply`
(обновление конфигурации базы данных), и для запущенного сеанса этого достаточно.

D-9 подключается к ИБ, указанной аргументом, и печатает ровно то, что важно:
Метаданные.Имя/Версия, разрешение двух имён БП3 коллекциями Метаданные (метод
НайтиПоИмени через IDispatch не отдаётся — замер D-7) и исход загрузки базового и
v26 .erf. Вызов:

    python _d9_session_meta_check.py "<путь к файловой ИБ или базе .1Cv8>"

Выход: _d9_session_meta_check.txt.
"""
from __future__ import annotations

import gc
import os
import sys
import time
import traceback

import pythoncom
import win32com.client as w32

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
# Хелперы переиспользуются, а не пишутся заново:
#   make_protection     — ОписаниеЗащитыОтОпасныхДействий + ПредупреждатьОбОпасныхДействиях=Ложь
#                         (замеры D-1/D-7: рабочий вариант; прежний
#                         _V8COMNativeConnectionPointContainer даёт «Тип не определен» — D-9b);
#   resolve_meta_name   — разрешение имени вида коллекциями Метаданные (замер D-7:
#                         Метаданные.НайтиПоИмени через IDispatch не отдаётся).
from _d1_erf_com_probe import make_protection, render  # noqa: E402
from _d4_dcs_compile_probe import resolve_meta_name  # noqa: E402

# живые пути .erf (замер 20.10.2026: каталогов Test11_CompareRegUSN и
# _ibcmd_work/v36_edit_probe/v26 больше нет — прежние константы давали бы «файла нет»)
ERF_BASE = r"C:\1C_LLM\LoadDoc\БП3\СравнениеУСНИ90_2.erf"
ERF_V26 = (r"C:\1C_LLM\LoadDoc\Edit_V26_СравнениеУСНИ90_2"
           r"\СравнениеУСНИ90_2_v26.edited.erf")
OUT = os.path.join(BASE, "_d9_session_meta_check.txt")
NAMES = ("Перечисление.СтатусыРасходовУСН", "РегистрНакопления.РасходыПриУСН")

_lines = []


def log(msg=""):
    print(msg, flush=True)
    _lines.append(str(msg))
    # артефакт пишется каждой строкой сразу: замер D-9c (20.10.2026) — stdout целый, а
    # _d9_session_meta_check.txt нет. Причина: процесс падает (0xC0000005) на gc.collect()/
    # CoUninitialize() в finally main() ДО финальной записи в блоке __main__. Финальная
    # запись остаётся, но полагаться на неё нельзя: где именно оборвётся COM-закрытие —
    # неизвестно, а вывод зонда нужен целиком.
    try:
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(_lines) + "\n")
    except OSError:
        pass


def safe(obj, name, default=None):
    try:
        return getattr(obj, name)
    except Exception:
        return default


# make_protection берётся из _d1_erf_com_probe (общий для D-1/D-4/D-7): у описания защиты
# один элемент — ПредупреждатьОбОпасныхДействиях, ставится Ложь, иначе внешнее соединение
# не может показать диалог и Создать() падает исключением «Предупреждение безопасности».


def load_erf(session, prot, path, tag):
    try:
        obj = session.ВнешниеОтчеты.Создать(path, False, prot)
    except Exception as exc:
        log(f"  {tag}: НЕ ЗАГРУЖЕН — {str(exc).strip()[:400]}")
        return None
    log(f"  {tag}: ЗАГРУЖЕН")
    try:
        obj.Close()
    except Exception:
        pass
    return obj


def main():
    ib = sys.argv[1] if len(sys.argv) > 1 else ""
    if not ib or not os.path.exists(ib):
        log(f"❌ путь к ИБ не задан или не существует: {ib!r}")
        return 1
    pythoncom.CoInitialize()
    try:
        v8 = w32.Dispatch("V83.COMConnector")
        try:
            v8.SSO = False
        except Exception:
            pass
        conn = f'File="{os.path.abspath(ib)}";'
        log(f"Connect: {conn}")
        t0 = time.time()
        try:
            session = v8.Connect(conn)
        except Exception as exc:
            log(f"❌ Connect не удалось ({time.time() - t0:.1f} с): {str(exc).strip()[:400]}")
            return 1
        log(f"✅ Connect за {time.time() - t0:.1f} с")
        try:
            meta = session.Метаданные
        except Exception as exc:
            log(f"Метаданные: НЕДОСТУПНО ({type(exc).__name__}: {str(exc).strip()})")
            meta = None
        if meta is not None:
            name = safe(meta, "Имя")
            version = safe(meta, "Версия")
            log(f"Метаданные.Имя={name!r} Версия={version!r}")
            if not version:
                log("  ⚠️ Версия пустая — конфигурация в ИБ не применена: нужен "
                    "`ibcmd config --db-path <ИБ> apply --force` (замер 20.10.2026), "
                    "одного `config load` для запущенного сеанса недостаточно")
            for fq in NAMES:
                found, channel = resolve_meta_name(meta, fq)
                if found is None:
                    log(f"  НЕТ  {fq} — {channel}")
                    continue
                log(f"  ЕСТЬ {fq} через {channel} -> "
                    f"{safe(found, 'Имя') or safe(found, 'Синоним') or render(found)}")
        prot, ctor = make_protection(session)
        if prot is None:
            log("❌ защиту получить не удалось — Создать() без описания защиты "
                "даёт «Предупреждение безопасности»")
            return 1
        log(f"  защита: {ctor}(ОписаниеЗащитыОтОпасныхДействий) получена")
        r1 = load_erf(session, prot, ERF_BASE, "base .erf")
        r2 = load_erf(session, prot, ERF_V26, "v26 .erf")
        for closer in ("Закрыть", "Quit"):
            try:
                getattr(session, closer)()
            except Exception:
                pass
        # снять COM-ссылки до CoUninitialize: иначе на закрытии процесса 0xC0000005
        session = prot = ctor = v8 = meta = None
        log("")
        log(f"ИТОГ: базовый={r1 is not None} v26={r2 is not None}")
        return 0 if (r1 is not None and r2 is not None) else 2
    finally:
        gc.collect()
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    try:
        code = main()
    except Exception:
        log("⚠️ СБОЙ: " + traceback.format_exc())
        code = 1
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(_lines) + "\n")
    print(f"[written] {OUT}", file=sys.stderr)
    sys.exit(code)
