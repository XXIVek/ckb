# -*- coding: utf-8 -*-
"""_d5_names_probe.py — D-5: существуют ли имена из текстов ошибок в выгрузке БП3 и что за ИБ у нас.

Основание (19–20.10.2026, _d1_env_probe.txt, _d4_dcs_compile_probe.txt). Оба отчёта сравнения
падают на компиляции макета в двух разных позициях, в обеих стоит маркер <<?>>:
  базовый : {(27,75)} Неверные параметры "Перечисление.СтатусыРасходовУСН.НеСписаноНеОплачено"
  V26     : {(16,2)}  Таблица не найдена "РегистрНакопления.РасходыПриУСН.ОстаткиИОбороты"
Правка V26 при этом минимальна (_d1_v26_diff.txt: снят только блок ВЫБОР…КОНЕЦ в ГДЕ) —
содержимое файла не «повреждено». Вопрос, который решает этот зонд, отделяет одно от другого:
  (A) имени НЕТ в конфигурации БП3 (файл/версия) — тогда его нет и в XML-выгрузке конфигурации,
      и отказ относится к содержимому отчёта;
  (B) имя в выгрузке БП3 ЕСТЬ — тогда отказ относится к контексту сеанса: в ИБ, к которой мы
      подключались, конфигурации нет (маркер ckb_ibcmd_state.json даёт config_state=loaded со
      значением inferred_from_layout, то есть состояние НЕ доказано загрузкой).
Имена берём из текстов ошибок, а не из памяти. Только чтение, в БД не пишем.

Запуск:
  python _d5_names_probe.py --log _d5_names_probe.txt
"""
import argparse
import io
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:                                          # noqa: BLE001
    pass

BP3_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files\BP3"
KINDS = {
    "Enums": "Перечисление",
    "AccumulationRegisters": "РегистрНакопления",
    "InformationRegisters": "РегистрСведений",
    "ChartsOfAccounts": "ПланСчетов",
    "Documents": "Документ",
    "Catalogs": "Справочник",
}
SUBSTRINGS = ("СтатусыРасходовУСН", "СтатусыОплатыРасходовУСН", "РасходыПриУСН",
              "ОтражениеВУСН", "ПоступлениеТоваровУслуг", "Сч41")
IB_ROOT = r"C:\1C_LLM\ckb\_ibcmd_work"
OTHER_BASES = (r"C:\1C_LLM\Bases_Test", r"C:\1C_LLM\LoadDoc")
LOG = []


def say(text=""):
    print(text)
    LOG.append(str(text))


def read_state(ib_dir):
    path = os.path.join(ib_dir, "ckb_ibcmd_state.json")
    if not os.path.exists(path):
        return None
    try:
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:                                # noqa: BLE001
        return {"unreadable": repr(exc)}


def step_names():
    say("[1. ИМЕНА ИЗ ТЕКСТОВ ОШИБОК В XML-ВЫГРУЗКЕ КОНФИГУРАЦИИ БП3]")
    if not os.path.isdir(BP3_ROOT):
        say(f"  каталога выгрузки нет: {BP3_ROOT}")
        return None
    say(f"  корень: {BP3_ROOT}")
    found = {}
    for kind, prefix in KINDS.items():
        path = os.path.join(BP3_ROOT, kind)
        if not os.path.isdir(path):
            say(f"  каталога вида нет: {kind}")
            continue
        hits = [n for n in sorted(os.listdir(path)) if any(s in n for s in SUBSTRINGS)]
        say(f"  {prefix} ({kind}): файлов {len(os.listdir(path))}, совпадений {len(hits)}")
        for h in hits:
            say(f"      ЕСТЬ: {h}")
            found[h.rsplit(".", 1)[0]] = kind
    return found


def step_values(found):
    """Для найденного перечисления — перечень значений (читается из XML перечисления)."""
    say("\n[2. ЗНАЧЕНИЯ ПЕРЕЧИСЛЕНИЯ, НАЗВАННОГО В ОШИБКЕ (27,75)]")
    enums = [n for n, kind in found.items() if kind == "Enums"]
    if not enums:
        say("  перечисления с такими именами в выгрузке нет — проверяем, какие есть вообще")
        path = os.path.join(BP3_ROOT, "Enums")
        if os.path.isdir(path):
            near = [n for n in sorted(os.listdir(path)) if "УСН" in n or "Расход" in n]
            say(f"  файлов перечислений: {len(os.listdir(path))}, "
                f"по подстрокам УСН/Расход: {len(near)}")
            for n in near:
                say(f"      {n}")
        return
    for name in enums:
        path = os.path.join(BP3_ROOT, "Enums", name + ".xml")
        if not os.path.exists(path):
            continue
        with io.open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        vals, marker, pos = [], "<Values>", 0
        while True:
            i = text.find(marker, pos)
            if i < 0:
                break
            j = text.find("</Values>", i)
            block = text[i:j if j > 0 else i + 400]
            for line in block.splitlines():
                if "v8:Name>" in line:
                    vals.append(line.split(">")[1].split("<")[0].strip())
            pos = j + 1
        say(f"  {name}: значений {len(vals)}")
        for v in vals[:40]:
            say(f"      {v}")


def step_ibs():
    say("\n[3. КАКИЕ ИБ У НАС ЕСТЬ И ДОКАЗАНО ЛИ В НИХ ЗАГРУЖЕННОЕ СОСТОЯНИЕ КОНФИГУРАЦИИ]")
    if not os.path.isdir(IB_ROOT):
        say(f"  каталога нет: {IB_ROOT}")
        return
    for name in sorted(os.listdir(IB_ROOT)):
        path = os.path.join(IB_ROOT, name)
        if not os.path.isdir(path):
            continue
        entries = os.listdir(path)
        has_config = any(e == "1Cv8.CD" or e.endswith(".cf") or e.endswith(".mx")
                         for e in entries)
        say(f"  {path}")
        say(f"      верхний уровень: {sorted(entries)[:12]}")
        say(f"      признак конфигурации в каталоге ИБ: {has_config}")
        say(f"      метка: {read_state(path)}")


def step_bases():
    say("\n[4. ПЛОЩАДКИ, КОТОРЫМ МЫ ДОверяЛИСЬ]")
    for root in OTHER_BASES:
        if not os.path.isdir(root):
            say(f"  {root} — каталога нет")
            continue
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name)
            if not os.path.isdir(path):
                continue
            entries = sorted(os.listdir(path))
            mark = "ИБ" if any(e.startswith("1Cv8") for e in entries) else ""
            say(f"  {path} [{len(entries)}] {mark} {entries[:8]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default=r"C:\1C_LLM\ckb\_d5_names_probe.txt")
    args = parser.parse_args()

    say("D-5: имена из текстов ошибок против выгрузки БП3 и состояние наших ИБ")
    found = step_names()
    if found is not None:
        step_values(found)
    step_ibs()
    step_bases()
    say("\n=D-5 завершена=")
    with io.open(args.log, "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG) + "\n")
    print(f"\nлог: {args.log} ({len(LOG)} строк)")


if __name__ == "__main__":
    main()

