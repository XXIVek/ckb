#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D-7: грузятся ли .erf в сеансе с реальной конфигурацией БП3 (база оператора).

D-6 показал: `Метаданные` внешнего соединения читается как СВОЙСТВО, и в наших ibcmd-ИБ
(`ib_bp3`, `ib_mincfg`) `Метаданные.Имя = Конфигурация`, `Версия` пустая — то есть ИБ содержит
Пустую конфигурацию, а не БП3. В базе оператора `Метаданные.Имя = БухгалтерияПредприятия`,
`Версия = 3.0.206.19`. Значит D-4 не мог разрешить имена метаданных: он обращался к ИБ без БП3.

Здесь: (1) чем именно не отдаётся метод Метаданные.НайтиПоИмени (замер GetIDsOfNames —
границы транспорта pywin32/IDispatch, а не вопрос к конфигурации); (2) загружается ли `.erf`
в сеансе с БП3 и в сеансе с пустой конфигурацией — это и есть разделение гипотез A/B.

Замер: C:\\1C_LLM\\ckb\\_d7_erf_in_bp3_session.txt
"""
import os
import sys

from _d1_erf_com_probe import count_of, full, make_protection, render, short

OUT = r"C:\1C_LLM\ckb\_d7_erf_in_bp3_session.txt"

SESSIONS = [
    ("база оператора (БП3)", 'File="C:\\1C_LLM\\Bases_Test\\BP3";Usr=admin;Pwd=;'),
    ("ibcmd ИБ ib_bp3", 'File="C:\\1C_LLM\\ckb\\_ibcmd_work\\ib_bp3";'),
]

ERFS = [
    ("база (без правок V26)", r"C:\1C_LLM\LoadDoc\БП3\СравнениеУСНИ90_2.erf"),
    ("V26 (правка ВЧК.ГДЕ)", r"C:\1C_LLM\LoadDoc\Edit_V26_СравнениеУСНИ90_2\СравнениеУСНИ90_2_v26.edited.erf"),
    ("эталон Test3_ОтчетПустой", r"C:\1C_LLM\LoadDoc\Test3_ОтчетПустой.erf"),
]

IDISPATCH_NAMES = ["НайтиПоИмени", "Найти", "Имя", "Версия"]

lines = []


def emit(text=""):
    print(text)
    lines.append(text)


def get_attr(obj, name):
    try:
        return getattr(obj, name), None
    except Exception as exc:  # noqa: BLE001
        return None, full(exc)


def idispatch_names(meta):
    emit("[1] Граница транспорта: имена методов Метаданные через IDispatch (оба порядка аргументов)")
    ole = getattr(meta, "_oleobj_", None)
    if ole is None:
        emit("    _oleobj_ недоступен — измерение невозможно")
        return
    for name in IDISPATCH_NAMES:
        outcome = []
        for tag, call in (("(names, lcid)", lambda: ole.GetIDsOfNames([name], 0)),
                          ("(lcid, names)", lambda: ole.GetIDsOfNames(0, [name]))):
            try:
                outcome.append(f"{tag} DISPID={call()}")
                break
            except Exception as exc:  # noqa: BLE001
                outcome.append(f"{tag} {type(exc).__name__}")
        emit(f"    {name}: " + " | ".join(outcome))


def describe_metadata(v8):
    meta, err = get_attr(v8, "Метаданные")
    if meta is None:
        emit(f"    Метаданные: НЕ получено ({err})")
        return None
    name, _ = get_attr(meta, "Имя")
    version, _ = get_attr(meta, "Версия")
    emit(f"    Метаданные.Имя = {name} | Версия = {version or '<пусто>'}")
    return meta


def load_erfs(v8):
    emit("")
    emit("[2] Загрузка .erf в этот сеанс (рабочая раскладка D-1/D-4: Создать(файл, Ложь, защита))")
    ext, err = get_attr(v8, "ВнешниеОтчеты")
    if ext is None:
        emit(f"    ВнешниеОтчеты недоступен: {err}")
        return
    protection, ctor = make_protection(v8)
    if protection is None:
        emit("    описание защиты не создано — Создать() без него даёт предупреждение безопасности")
        return
    for label, path in ERFS:
        if not os.path.isfile(path):
            emit(f"    {label}: файла нет {path}")
            continue
        try:
            report = ext.Создать(path, False, protection)
        except Exception as exc:  # noqa: BLE001
            emit(f"    {label}: НЕ ЗАГРУЖЕН — {full(exc)[:700]}")
            continue
        if report is None:
            emit(f"    {label}: Создать вернул пустой")
            continue
        parts = []
        for attr in ("Имя", "ОсновнаяСхемаКомпоновкиДанных"):
            value, e = get_attr(report, attr)
            parts.append(f"{attr}={'<нет>' if e else render(value)}")
        emit(f"    {label}: ЗАГРУЖЕН через {ctor} — " + "; ".join(parts))
        dcs, _ = get_attr(report, "ОсновнаяСхемаКомпоновкиДанных")
        if dcs is not None:
            for attr in ("НаборыДанных", "Параметры", "РазличныеИсточникиДанных", "ВычисляемыеПоля"):
                value, e = get_attr(dcs, attr)
                if e:
                    emit(f"        Схема.{attr}: <имя недоступно>")
                    continue
                emit(f"        Схема.{attr}: {count_of(value)}")


def run(v8, caption):
    emit("")
    emit("=" * 72)
    emit(f"СЕАНС: {caption}")
    emit("=" * 72)
    meta = describe_metadata(v8)
    if meta is not None:
        idispatch_names(meta)
    load_erfs(v8)


def main():
    try:
        from win32com.client import Dispatch
    except ImportError as exc:
        emit(f"pywin32 не установлен: {exc}")
        return 2
    connector = Dispatch("V83.COMConnector")
    for caption, connect_str in SESSIONS:
        try:
            v8 = connector.Connect(connect_str)
        except Exception as exc:  # noqa: BLE001
            emit(f"\nСЕАНС {caption}: Connect не выполнен: {full(exc)}")
            continue
        run(v8, caption)
    emit("")
    emit("=" * 72)
    emit("ВЫВОД")
    emit("=" * 72)
    emit("Если в сеансе с БухгалтерияПредприятия 3.0.206.19 отчёт загружается, а в ib_bp3")
    emit("(Метаданные.Имя=Конфигурация, версия пуста) — нет, причина в контексте: ИБ ibcmd")
    emit("не содержит конфигурации БП3, а не в содержимом файла отчёта.")
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"\n[log saved] {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
