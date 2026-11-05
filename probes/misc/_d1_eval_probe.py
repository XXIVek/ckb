"""Офлайн-диагностика D1: доступен ли Eval/Вычислить через COMConnector УВФ90.

Если глобальная функция Вычислить разрешается, весь слой L1/L2 решается
выполнением BSL-кода текстом, а не динамическим dispatch по русским именам.

Только чтение БД и COM. Ничего не пишет.
"""
import sys

import pythoncom
from win32com.client.dynamic import CDispatch as DynamicCDispatch

IB_DIR = r"C:\1C_LLM\УВФ90_2022_10_00151_Управление_ветряной_фермой_90_редБ_Юг-2026"
PROGID = "V83.COMConnector"
ERF = r"C:\1C_LLM\LoadDoc\БП3\СравнениеУСНИ90_2.erf"


def clsid_of(prog):
    import win32api, win32con
    k = win32api.RegOpenKeyEx(win32con.HKEY_LOCAL_MACHINE, f"SOFTWARE\\Classes\\{prog}", 0, win32con.KEY_READ | win32con.KEY_WOW64_64KEY)
    try:
        sub = win32api.RegOpenKeyEx(k, "CLSID", 0, win32con.KEY_READ | win32con.KEY_WOW64_64KEY)
        try:
            return win32api.RegQueryValueEx(sub, "")[0]
        finally:
            sub.Close()
    finally:
        k.Close()


def safe_repr(value):
    try:
        return str(value).encode("utf-8", "replace").decode("utf-8", "replace")[:200]
    except Exception as exc:
        return f"<repr error {type(exc).__name__}>"


def try_names(obj, names, label, args=()):
    errors = []
    for name in names:
        try:
            value = obj
            for part in name.split("."):
                value = getattr(value, part)
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {safe_repr(exc)}")
            continue
        if callable(value) and not isinstance(value, DynamicCDispatch):
            pass  # метод: ниже вызываем
        if args:
            try:
                res = value(*args)
                print(f"  OK   {label} {name} -> {safe_repr(res)}")
                return res
            except Exception as exc:
                errors.append(f"call {name}: {type(exc).__name__}: {safe_repr(exc)}")
        else:
            print(f"  OK   {label} {name} -> type={type(value).__name__} val={safe_repr(value)}")
            return value
    print(f"  FAIL {label}: " + " | ".join(errors[:4]))
    return None


def main():
    pythoncom.CoInitialize()
    conn = DynamicCDispatch(clsid_of(PROGID))
    session = conn.Connect(f'"{IB_DIR}"')
    print("CONNECTED")

    # 1. глобальная функция Вычислить/Eval
    code = try_names(conn, ["Вычислить", "Eval"], "global fn", ("1+1",))
    print(f"EVAL 1+1 -> {safe_repr(code)}")

    # 2. Вычислить: версия платформы и имя конфигурации
    for expr in [
        '"" + "ОК"',
        '"Версия=" + ?(ЗначениеЗаполнено(ВерсияПлатформыПолная), ВерсияПлатформыПолная, "нет")',
        'Строка(Метаданные().ВерсияИспользования)',
    ]:
        try:
            print(f"  EVAL {expr[:40]!r} -> {safe_repr(conn.Вычислить(expr))}")
        except Exception as exc:
            print(f"  EVAL {expr[:40]!r} ERR {type(exc).__name__}: {safe_repr(exc)}")

    # 3. Вычислить: загрузка внешнего отчёта из файла
    code_load = (
        'ДокИнфо=""\n'
        'Попытка\n'
        '  ДокИнфо="есть ВнешниеОтчеты=" + Строка(ВнешниеОтчеты <> Неопределено)\n'
        'Исключение\n'
        '  ДокИнфо="нет ВнешниеОтчеты: " + ОписаниеОшибки()\n'
        'КонецПопытки\n'
        'ДокИнфо'
    )
    try:
        print("  EVAL ВнешниеОтчеты ->", safe_repr(conn.Вычислить(code_load)))
    except Exception as exc:
        print("  EVAL ВнешниеОтчеты ERR", type(exc).__name__, safe_repr(exc))

    # 4. что вообще за объект session.ВнешниеОтчеты
    m = getattr(session, "ВнешниеОтчеты")
    print("manager type:", type(m).__name__)
    try:
        print("manager dir:", sorted([str(x) for x in dir(m) if not str(x).startswith("_")])[:60])
    except Exception as exc:
        print("manager dir err:", type(exc).__name__, safe_repr(exc))
    for nm in ["ЗагрузитьВнешнийОтчет", "Загрузить", "Load", "ПолучитьВнешнийОтчет",
               "НайтиВнешниеОтчеты", "УстановитьВнешнийОтчет", "Прочитать", "Get"]:
        try:
            v = getattr(m, nm)
            r = v(ERF)
            print(f"  OK   manager.{nm}(erf) -> {safe_repr(r)}")
            break
        except Exception as exc:
            print(f"  ERR  manager.{nm}: {type(exc).__name__}: {safe_repr(exc)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
