# -*- coding: utf-8 -*-
"""D-8 — ЗАМЫКАНИЕ ЦИКЛА: та же ibcmd-ИБ, но с реально загруженной конфигурацией БП3.

D-7 сравнил два сеанса: в реальной базе БП3 (.1Cv8) оба .erf загружаются, в нашей
ibcmd-ИБ `ib_bp3` — падают текстами D-4. Причина по замеру D-6/D-7: в `ib_bp3`
сидит ПУСТАЯ конфигурация (Метаданные.Имя="Конфигурация", Версия=""), а не БП3.

D-8 делает ровно одно действие-исправление: `ibcmd config --db-path <ib_bp3> load
BP3_1Cv8.cf` штатной функцией моста `src/ibcmd_bridge.load_configuration` — и
повторяет проверку D-7 в ТОМ ЖЕ каталоге ИБ. Если после этого Метаданные назовутся
"БухгалтерияПредприятия" и оба .erf загрузятся — причина подтверждена полностью,
а чинить надо не отчёт и не сборку XML, а подготовку контекста (R14: состояние
`loaded` у метки было ВЫВЕДЕНО из фактов разбора, а не получено из `config load`).

Дополнительно читает свойства загруженного отчёта латинскими именами (`Name`,
`MainDataCompositionSchema`) — кириллические имена свойств pywin32 не разрешает
(DISP_E_MEMBERNOTFOUND), а проверить, что СКД действительно загрузилась, нужно.

Выход: _d8_ib_bp3_with_bp3.txt.
"""
from __future__ import annotations

import os
import sys
import time
import traceback

import pythoncom
import win32com.client as w32

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "src"))

from ibcmd_bridge import load_configuration  # noqa: E402

BP3_IB = os.path.join(BASE, "_ibcmd_work", "ib_bp3")
BP3_CF = r"C:\1C_LLM\LoadDoc\Configurations\BP3_1Cv8.cf"
ERF_BASE = r"C:\1C_LLM\LoadDoc\Test11_CompareRegUSN\СравнениеУСНИ90_2.erf"
ERF_V26 = os.path.join(BASE, "_ibcmd_work", "v36_edit_probe", "v26",
                       "СравнениеУСНИ90_2_v26.erf")
OUT = os.path.join(BASE, "_scratch", "_d8_ib_bp3_with_bp3.txt")

LATIN_PROPS = ("Name", "MainDataCompositionSchema", "DataCompositionSchema",
               "DefaultForm", "AutoUseDataSeparation")

_lines = []


def log(msg=""):
    print(msg, flush=True)
    _lines.append(str(msg))


def make_protection(v8):
    try:
        ctor = v8.NewObject("_V8COMNativeConnectionPointContainer")
        return ctor.CreateObject(), ctor
    except Exception:
        return None, None


def safe(obj, name, default=None):
    try:
        return getattr(obj, name)
    except Exception:
        return default


def describe_meta(v8, tag):
    try:
        meta = v8.Метаданные
    except Exception as exc:
        log(f"  {tag} Метаданные: НЕДОСТУПНО ({type(exc).__name__}: {str(exc).strip()})")
        return False
    name = safe(meta, "Имя")
    version = safe(meta, "Версия")
    log(f"  {tag} Метаданные.Имя={name!r} Версия={version!r}")
    for fq in ("Перечисление.СтатусыРасходовУСН", "РегистрНакопления.РасходыПриУСН"):
        try:
            found = meta.НайтиПоИмени(fq)
        except Exception as exc:
            log(f"  {tag} найти {fq}: ERROR {type(exc).__name__}: {str(exc).strip()[:160]}")
            continue
        if found is None:
            log(f"  {tag} найти {fq}: None")
        else:
            log(f"  {tag} найти {fq}: {safe(found, 'Синоним') or safe(found, 'Имя')}")
    return bool(name) and name != "Конфигурация"



def try_load_report(session, prot, path, tag):
    try:
        obj = session.ВнешниеОтчеты.Создать(path, False, prot)
    except Exception as exc:
        log(f"  {tag} {os.path.basename(path)}: НЕ ЗАГРУЖЕН — {str(exc).strip()[:500]}")
        return None
    log(f"  {tag} {os.path.basename(path)}: ЗАГРУЖЕН")
    for prop in LATIN_PROPS:
        val = safe(obj, prop, "<нет>")
        if val is None:
            val = "<NULL>"
        elif prop in ("DataCompositionSchema", "MainDataCompositionSchema") and val != "<нет>":
            try:
                datasets = getattr(val, "DataSets").Count()
                params = getattr(val, "Parameters").Count()
                val = f"СКД получена: наборы={datasets} параметры={params}"
            except Exception as exc:
                val = f"объект получен, состав не читается ({type(exc).__name__})"
        log(f"  {tag}   {prop} = {val}")
    try:
        obj.Close()
    except Exception:
        pass
    return obj


def main():
    pythoncom.CoInitialize()
    try:
        log("ШАГ 1 — ibcmd config load BP3 в нашу рабочую ИБ (функция моста)")
        log(f"  ИБ: {BP3_IB}")
        log(f"  .cf: {BP3_CF}")
        if not os.path.isfile(BP3_CF):
            log("  ❌ файла .cf нет — дальнейших шагов не будет")
            return 1
        t0 = time.time()
        res = load_configuration(db_path=BP3_IB, config_file=BP3_CF)
        log(f"  success={res.get('success')} секунд={res.get('seconds', round(time.time() - t0, 1))}")
        if not res.get("success"):
            log(f"  ❌ {res.get('error')}")
            log(f"     {res.get('hint')}")
            return 1
        st = res.get("state") or {}
        log("  метка ИБ: config_state=%r config_source=%r loaded_at=%r"
            % (st.get("config_state"), st.get("config_source"), st.get("config_loaded_at")))

        log("")
        log("ШАГ 2 — COM-сеанс к ТОЙ ЖЕ ИБ после загрузки конфигурации")
        v8 = w32.Dispatch("V83.COMConnector")
        try:
            v8.SSO = False
        except Exception:
            pass
        conn = f'File="{BP3_IB}";'
        log(f"  Connect: {conn}")
        t0 = time.time()
        try:
            session = v8.Connect(conn)
        except Exception as exc:
            log(f"  ❌ Connect не удалось ({time.time() - t0:.1f} с): {str(exc).strip()[:500]}")
            return 1
        log(f"  ✅ Connect за {time.time() - t0:.1f} с")
        real = describe_meta(session, "после load")
        prot, ctor = make_protection(session)
        if prot is None:
            log("  ❌ защиту получить не удалось")
            return 1
        log("")
        log("  ЗАГРУЗКА .erf в этом сеансе")
        r1 = try_load_report(session, prot, ERF_BASE, "base")
        r2 = try_load_report(session, prot, ERF_V26, "v26")
        log("")
        log("ИТОГ:")
        log(f"  конфигурация в ИБ названа реально: {real}")
        log(f"  базовый .erf загружен: {r1 is not None}")
        log(f"  v26 .erf загружен: {r2 is not None}")
        try:
            session.Quit()
        except Exception:
            pass
        return 0 if (real and r1 is not None and r2 is not None) else 2
    finally:
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
