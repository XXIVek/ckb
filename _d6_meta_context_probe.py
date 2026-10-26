#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D-6: разрешает ли сеанс COM имена объектов БП3 (контекст против содержимого файла).

D-4 оставил вопрос открытым: внешнее соединение V83.COMConnector НЕ отдаёт имена глобального
контекста (зафиксировано в _d1_erf_com_probe.py), а Метаданные отдаёт как СВОЙСТВО фиксированного
набора. D-4 звал Метаданные() как метод и получил «Член группы не найден» — это особенность
транспорта, а не доказательство отсутствия конфигурации в сеансе. Здесь Метаданные читается
ТОЛЬКО как свойство, имена проверяются методом НайтиПоИмени.

Разделяет гипотезы D-5:
  A) имена разрешились в сеансе, а отчёт не собирается -> проблема в файле/версии отчёта;
  B) имена НЕ разрешились, хотя в XML выгрузки БП3 они есть -> проблема в контексте сеанса.

Замер: C:\\1C_LLM\\ckb\\_d6_meta_context_probe.txt
"""
import os
import sys
import time

from _d1_erf_com_probe import full, make_protection, render, short

OUT = r"C:\1C_LLM\ckb\_d6_meta_context_probe.txt"

SESSIONS = [
    ("ibcmd ИБ _ibcmd_work/ib_bp3 (метка loaded)", 'File="C:\\1C_LLM\\ckb\\_ibcmd_work\\ib_bp3";'),
    ("база оператора C:\\1C_LLM\\Bases_Test\\BP3", 'File="C:\\1C_LLM\\Bases_Test\\BP3";Usr=admin;Pwd=;'),
    ("ibcmd ИБ _ibcmd_work/ib_mincfg (MinCfg)", 'File="C:\\1C_LLM\\ckb\\_ibcmd_work\\ib_mincfg";'),
]

# имена из текста ошибок D-4 + контрольное имя, которого в конфигурации быть не должно
NAMES = [
    "Перечисление.СтатусыРасходовУСН",
    "РегистрНакопления.РасходыПриУСН",
    "Документ.ПоступлениеТоваровУслуг",
    "РегистрНакопления.ТакогоОбъектаТочноНет",
]

ERFS = [
    ("база (без правок V26)", r"C:\1C_LLM\LoadDoc\БП3\СравнениеУСНИ90_2.erf"),
    ("V26 (правка ВЧК.ГДЕ)", r"C:\1C_LLM\LoadDoc\Edit_V26_СравнениеУСНИ90_2\СравнениеУСНИ90_2_v26.edited.erf"),
    ("эталон Test3_ОтчетПустой", r"C:\1C_LLM\LoadDoc\Test3_ОтчетПустой.erf"),
]

lines = []


def emit(text=""):
    print(text)
    lines.append(text)


def get_attr(obj, name):
    """Прочитать атрибут динамического COM-объекта; вернуть (значение, ошибка)."""
    try:
        return getattr(obj, name), None
    except Exception as exc:  # noqa: BLE001
        return None, full(exc)


def metadata_of(v8):
    """Метаданные сеанса КАК СВОЙСТВО (не вызов) + попытка вызова для полноты замера."""
    meta, err = get_attr(v8, "Метаданные")
    call_err = None
    try:
        if meta is None:
            meta = v8.Mетаданные()
    except Exception as exc:  # noqa: BLE001
        call_err = full(exc)[:120]
    return meta, err, call_err



def probe_metadata(v8):
    emit("[1] Метаданные сеанса как СВОЙСТВО + НайтиПоИмени")
    meta, err, call_err = metadata_of(v8)
    emit(f"    Метаданные (property): {'получено' if meta is not None else 'НЕ получено'}")
    if err:
        emit(f"      ошибка свойства: {err}")
    if call_err:
        emit(f"      ошибка вызова Метаданные(): {call_err}")
    if meta is None:
        return False
    for name in ("Имя", "Версия", "ВерсияПлатформы", "ОсновнойЯзык"):
        value, e = get_attr(meta, name)
        emit(f"    Метаданные.{name} = {value if e is None else '<нет>'}")
    find, e = get_attr(meta, "НайтиПоИмени")
    if find is None:
        emit(f"    НайтиПоИмени недоступен: {e}")
        return False
    resolved = 0
    for name in NAMES:
        try:
            obj = meta.НайтиПоИмени(name)
        except Exception as exc:  # noqa: BLE001
            emit(f"    {name}: ошибка {full(exc)}")
            continue
        if obj is None:
            emit(f"    {name}: НЕТ (НайтиПоИмени вернул пустой)")
            continue
        resolved += 1
        info = ""
        for attr in ("Имя", "Синоним"):
            value, e2 = get_attr(obj, attr)
            if e2 is None and value:
                info += f" {attr}={short(str(value), 60)}"
        emit(f"    {name}: ЕСТЬ{info}")
        if name.startswith("Перечисление."):
            values, e3 = get_attr(obj, "ЗначенияПеречисления")
            if values is None:
                values, e3 = get_attr(obj, "Значения")
            if values is not None:
                try:
                    emit(f"      значения перечисления: {[str(getattr(v, 'Имя', '')) for v in values]}")
                except Exception as exc:  # noqa: BLE001
                    emit(f"      значения перечисления: ошибка {short(exc, 120)}")
            else:
                emit("      значения перечисления: недоступны")
    emit(f"    ИТОГ: разрешилось {resolved} из {len(NAMES) - 1} нужных имён")
    return resolved > 0



def probe_erfs(v8):
    emit("")
    emit("[2] Загрузка .erf в ЭТОТ же сеанс (компиляция макета в этом контексте)")
    ext, err = get_attr(v8, "ВнешниеОтчеты")
    if ext is None:
        emit(f"    ВнешниеОтчеты недоступен: {err}")
        return
    for label, path in ERFS:
        if not os.path.isfile(path):
            emit(f"    {label}: файла нет {path}")
            continue
        try:
            report = ext.Создать(make_protection(v8, path))
        except Exception as exc:  # noqa: BLE001
            emit(f"    {label}: НЕ ЗАГРУЖЕН — {render(exc)}")
            continue
        if report is None:
            emit(f"    {label}: Создать вернул пустой")
            continue
        parts = []
        for attr in ("Имя", "ОсновнаяСхемаКомпоновкиДанных", "СхемаКомпоновкиДанных"):
            value, e = get_attr(report, attr)
            parts.append(f"{attr}={'<нет>' if e else ('есть' if value is not None else 'пусто')}")
        emit(f"    {label}: ЗАГРУЖЕН — " + "; ".join(parts))


def run_session(connector, caption, connect_str):
    emit("")
    emit("=" * 72)
    emit(f"СЕАНС: {caption}")
    emit(f"  подключение: {connect_str}")
    emit("=" * 72)
    started = time.monotonic()
    try:
        v8 = connector.Connect(connect_str)
    except Exception as exc:  # noqa: BLE001
        emit(f"Connect НЕ выполнен ({time.monotonic() - started:.1f} с): {full(exc)}")
        return
    emit(f"Connect выполнен за {time.monotonic() - started:.1f} с")
    if probe_metadata(v8):
        probe_erfs(v8)
    else:
        emit("[2] Загрузка .erf пропущена: имена БП3 в этом сеансе не разрешились")


def main():
    try:
        from win32com.client import Dispatch
    except ImportError as exc:
        emit(f"pywin32 не установлен: {exc}")
        return 2
    connector = Dispatch("V83.COMConnector")
    for caption, connect_str in SESSIONS:
        run_session(connector, caption, connect_str)
    emit("")
    emit("=" * 72)
    emit("ВЫВОД (правило разделения гипотез D-5)")
    emit("=" * 72)
    emit("Имена разрешились в сеансе, а .erf там не компилируется -> дело в файле отчёта.")
    emit("Имена НЕ разрешились нигде, хотя в XML выгрузки БП3 они есть")
    emit("(_d5_names_probe.txt) -> дело в контексте сеанса: ИБ не содержит нужной конфигурации.")
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"\n[log saved] {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
