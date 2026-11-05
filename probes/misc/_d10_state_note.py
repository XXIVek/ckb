#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_d10_state_note.py — починить учёт состояния ИБ ib_bp3 (метка врёт про конфигурацию).

Повод (замеры этой сессии, 19.10.2026):
  * `_d8_apply2.txt` — `ibcmd config apply --force` по ib_bp3 выполнен успешно (202.4 с);
  * `_d9_session_meta_check.txt` — после применения метаданные БП3 видны сеансу 1С
    (1936 объектов отчётов, отчёт СравнениеУСНИ90 найден), а до применения сессия отвечала
    «Разрешение имени объекта метаданных не поддерживается в данном контексте»;
  * при этом метка `_ibcmd_work/ib_bp3/ckb_ibcmd_state.json` хранила `config_state =
    load_failed`, то есть следующий вызов `load_external_object_file_tool` с этой ИБ для
    объекта без `cfg:`-имён сказал бы оператору «Конфигурация в ИБ не загружена: загрузите её
    параметром config_file». Это ложь про ИБ, а не про объект.

Что делает скрипт (метку читает и пишет, в БД не пишет, ibcmd не вызывает):
  1. печатает метку ДО и ответ `_context_note` на «cfg: — 0» ДО правки (демонстрация лжи);
  2. ставит состояние `applied` штатной функцией `note_config_applied()` — факт применения
     получен вне обёртки (`ibcmd config apply --force` + живое подключение к сессии);
  3. печатает метку ПОСЛЕ и тот же ответ `_context_note` — он обязан называть конфигурацию
     присутствующей, а состояние не понижать до `loaded`;
  4. проверяет `config_is_present()` на всех значениях словаря состояний (на временном
     каталоге-подделке для `load_failed` и `unknown`).

Вывод пишется построчно и сразу на диск (урок `_d9_session_meta_check.py`: процесс может
пасть на освобождении COM-буфера и потерять хвост лога).
"""
import copy
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from ibcmd_bridge import (_context_note, CONFIG_STATE_APPLIED, CONFIG_STATE_FAILED,
                          CONFIG_STATE_LOADED, CONFIG_STATE_UNKNOWN, config_is_present,
                          configuration_state, infobase_exists, note_config_applied,
                          write_state)

IB_BP3 = os.path.join(ROOT, "_ibcmd_work", "ib_bp3")
CF_BP3 = r"C:\1C_LLM\LoadDoc\Configurations\BP3_1Cv8.cf"
LOG = os.path.join(ROOT, "_d10_state_note.txt")
TMP = os.path.join(ROOT, "_ibcmd_work", "_d10_tmp")

# Факт разбора без имён типов — как у объекта, живущего на стандартных типах.
FACTS_NO_NAMES = {"available": True, "cfg_type_names": 0, "type_id_elements": 4,
                  "types_resolved": False}

_lines = []


def out(text=""):
    """Строка сразу в stdout и в буфер лога (сброс на каждую строку)."""
    print(text, flush=True)
    _lines.append(str(text))


def dump_log():
    with open(LOG, "w", encoding="utf-8") as fh:
        fh.write("\r\n".join(_lines) + "\r\n")


def marker(path):
    """Метка ИБ как есть (None, если файла нет): читаем файл, а не только состояние."""
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def note_for(db_path):
    """Что ответил бы `_context_note` на объект без `cfg:`-имён — ровно этот текст
    оператор увидит в карточке разбора (правило R14)."""
    return _context_note(db_path, copy.deepcopy(FACTS_NO_NAMES), False)


def indented(value):
    return json.dumps(value, ensure_ascii=False, indent=1).replace("\n", "\n  ")


def vocabulary_checks():
    """Разрешимость состояний на подделках: `load_failed` и отсутствие метки — это
    «конфигурации нет»; `loaded` и `applied` — «конфигурация есть»."""
    results = []
    try:
        os.makedirs(TMP, exist_ok=True)
        write_state(TMP, {"config_state": CONFIG_STATE_FAILED})
        results.append(("load_failed не называется присутствующей конфигурацией",
                        not config_is_present(TMP)))
        write_state(TMP, {"config_state": CONFIG_STATE_LOADED})
        results.append(("loaded — конфигурация присутствует", config_is_present(TMP)))
        write_state(TMP, {"config_state": CONFIG_STATE_APPLIED})
        results.append(("applied — конфигурация присутствует", config_is_present(TMP)))
        results.append(("applied не понижается до loaded при чтении",
                        configuration_state(TMP) == CONFIG_STATE_APPLIED))
        empty = os.path.join(TMP, "absent")
        os.makedirs(empty, exist_ok=True)
        results.append(("метки нет — состояние unknown, конфигурации нет",
                        configuration_state(empty) == CONFIG_STATE_UNKNOWN
                        and not config_is_present(empty)))
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    return results


def main():
    out("=" * 78)
    out("_d10_state_note.py — учёт состояния конфигурации в ИБ (метка applied)")
    out("ИБ:       " + IB_BP3)
    out("файл .cf: " + CF_BP3)
    out("=" * 78)
    if not infobase_exists(IB_BP3):
        out("ОТКАЗ: информационная база не найдена — чинить метку негде.")
        dump_log()
        return 1

    state_file = os.path.join(IB_BP3, "ckb_ibcmd_state.json")
    out("")
    out("[1. МЕТКА ДО]")
    out("  файл: " + state_file)
    out("  " + indented(marker(state_file)))
    before_state = configuration_state(IB_BP3)
    out("  configuration_state() = %r" % before_state)
    out("  config_is_present()   = %r" % config_is_present(IB_BP3))

    out("")
    out("[2. ЧТО БЫЛО БЫ НЕВЕРНО (демонстрация лжи до правки)]")
    note_before, _ = note_for(IB_BP3)
    out("  _context_note при cfg: — 0 отвечает: %r" % ((note_before or "")[:200]))
    claimed = "Конфигурация в ИБ загружена" in note_before
    out("  называет конфигурацию присутствующей: %r" % claimed)
    if claimed:
        out("  ⚠️ ожидаемого дефекта нет: метка уже говорит «конфигурация есть» "
            "(состояние %r) — правка не требуется" % before_state)
    else:
        out("  ❌ ложь подтверждена: при применённой конфигурации ответ — «не загружена»")

    out("")
    out("[3. ЗАПИСЬ ФАКТА ПРИМЕНЕНИЯ (note_config_applied)]")
    res = note_config_applied(
        IB_BP3, config_file=CF_BP3,
        source="ibcmd config apply --force (manual, 19.10.2026, "
               "подтверждено: _d8_apply2.txt + _d9_session_meta_check.txt)")
    out("  success=%s  было=%r  стало=%r"
        % (res.get("success"), res.get("state_before"), res.get("state_after")))
    if not res.get("success"):
        out("  ошибка: %r / %r" % (res.get("error"), res.get("details")))
        dump_log()
        return 1

    out("")
    out("[4. МЕТКА ПОСЛЕ]")
    out("  " + indented(marker(state_file)))
    out("  configuration_state() = %r" % configuration_state(IB_BP3))
    out("  config_is_present()   = %r" % config_is_present(IB_BP3))

    out("")
    out("[5. ТОТ ЖЕ ОТВЕТ ПОСЛЕ ПРАВКИ]")
    note_after, state_after = note_for(IB_BP3)
    out("  _context_note при cfg: — 0 отвечает: %r" % ((note_after or "")[:200]))
    out("  состояние в ответе: %r" % state_after)

    out("")
    out("[6. ПРОВЕРКИ]")
    checks = [("значение applied есть в словаре состояний", CONFIG_STATE_APPLIED == "applied"),
              ("применённая ИБ читается как «конфигурация есть»", config_is_present(IB_BP3)),
              ("состояние ИБ после записи — applied",
               configuration_state(IB_BP3) == CONFIG_STATE_APPLIED),
              ("ложь «Конфигурация в ИБ не загружена» больше не отдаётся",
               "Конфигурация в ИБ не загружена" not in note_after),
              ("ответ называет конфигурацию присутствующей",
               "Конфигурация в ИБ загружена" in note_after),
              ("состояние не понижено до loaded", state_after == CONFIG_STATE_APPLIED)]
    checks += vocabulary_checks()
    failed = 0
    for title, ok in checks:
        out(("  OK   " if ok else "  FAIL ") + title)
        failed += 0 if ok else 1

    out("")
    out("=" * 78)
    out("ИТОГ: проверок %d, провалено %d" % (len(checks), failed))
    out("В БД не записано ни строки; ibcmd не вызывался; изменён только файл метки "
        "ckb_ibcmd_state.json в каталоге ИБ")
    out("=" * 78)
    dump_log()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    code = main()
    print("[d10] exit=%d" % code, flush=True)
    sys.exit(code)
