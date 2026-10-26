# -*- coding: utf-8 -*-
r"""_d1_conn_probe.py — принимает ли файловая ИБ сеанс V83.COMConnector без аутентификации.

Вопрос один: есть ли у ibcmd-ной файловой ИБ (_ibcmd_work/ib_bp3, создавалась командой
infobase create без пользователей) возможность открыть сеанс через COM-коннектор. Если да —
измерение D1 идёт на ней и новая база оператору не нужна. Если нет — нужен пользователь
(или серверный вариант), и это уже вопрос к оператору.

Ничего, кроме подключения и немедленного закрытия, скрипт не делает: LockFileBay не держит
дольше секунды, содержимое ИБ не меняется.
"""
import sys
import winreg

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

IB = r"C:\1C_LLM\ckb\_ibcmd_work\ib_bp3"


def com_reg():
    out = {}
    for prog in ("V83.COMConnector",):
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, prog) as key:
                clsid = (winreg.QueryValue(key, "") or "").strip()
            out["prog_id"] = prog
            out["clsid"] = clsid
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,
                                f"CLSID\\{clsid}\\InprocServer32") as key:
                out["dll"] = (winreg.QueryValue(key, "") or "").strip()
        except OSError as exc:
            out["error"] = f"{prog}: {exc.strerror or exc}"
    return out


print("=== регистрация COM-класса ===")
info = com_reg()
for key, value in info.items():
    print(f"  {key}: {value}")

try:
    import win32com.client  # noqa: F401
    print("pywin32: есть")
except Exception as exc:
    print(f"pywin32: НЕТ ({exc})")
    sys.exit(1)

variants = [
    # файловая ИБ подключается параметром File=; Srvr= — это клиент-сервер
    # (первая попытка ниже это и показала: платформа ушла резолвить "C" как хост).
    ('File="%s";' % IB),
    ('File="%s";Usr=Probe;Pwd=Probe;' % IB),
    ('File="%s";Usr=;Pwd=;' % IB),
]
print()
print("=== попытки Connect (каждая — отдельный Dispatch, с закрытием) ===")
for string in variants:
    connector = None
    try:
        connector = win32com.client.Dispatch("V83.COMConnector")
        session = connector.Connect(string)
        print(f"[OK  ] {string}")
        print(f"        сессия: {session!r}")
        for attr in ("ИмяБазы", "NameIBase"):
            try:
                print(f"        {attr} = {getattr(session, attr)}")
                break
            except Exception:
                continue
        try:
            session.Закрыть()
        except Exception:
            pass
    except Exception as exc:
        print(f"[FAIL] {string}")
        print("        " + " ".join(str(exc).split())[:400])
    finally:
        del connector
