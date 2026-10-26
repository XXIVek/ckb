# -*- coding: utf-8 -*-
"""_d1_env_probe.py — отпечаток конфигурации COM-сеанса и загрузка чужих .erf той же площадкой.

Зачем. _d1_erf_com_probe.py прошёл «Предупреждение безопасности» (третий параметр Создать —
описание защиты, ПредупреждатьОбОпасныхДействиях=Ложь) и упёрся в компиляцию СКД самого отчёта:

  {(27, 75)}: Неверные параметры "Перечисление.СтатусыРасходовУСН.НеСписаноНеОплачено"
  КОГДА РасходыПриУСНОстаткиИОбороты.СтатусыОплатыРасходовУСН =
        ЗНАЧЕНИЕ(<<?>>Перечисление.СтатусыРасходовУСН.НеСписаноНеОплачено)

Замер по выгрузке BP3 (ConfigDumpInfo.xml): AccumulationRegister.РасходыПриУСН есть, его измерения
СтатусыОплатыРасходовУСН/ОтражениеВУСН есть, Enum.СтатусыРасходовУСН есть, значение
НеСписаноНеОплачено есть (Enums/СтатусыРасходовУСН.xml). Значит строка 27 — пятый аргумент вызова
виртуальной таблицы (строка критериев), и в НЕО СКД подставила значение, объявленное схемой,
записав его как ЗНАЧЕНИЕ(<<?>>…). Остаются два объяснения, и они дают разные выводы:

  (A) в сеансе загружена НЕ та конфигурация (или не загружена) — тогда «<<?>>» это нерезолвнутый
      тип, а отказ относится к площадке, а не к отчёту;
  (B) конфигурация та, тип разрешим — тогда «<<?>>» артефакт подстановки значения в строку
      критериев, и вывод про design-time значения становится прямым фактом.

Разделяет их этот зонд:
  [1] метка состояния ИБ (факт, а не память);
  [2] ТипФУн по именам, которых нет вне БП3, и по общим именам — отпечаток конфигурации сеанса;
  [3] ЗначениеВТипе(ТипФУн("ПеречислениеСсылка.СтатусыРасходовУСН"), "<имя значения>") — есть ли
      то самое значение перечисления в сеансе;
  [4] Создать() по другим .erf той же площадки: если чужой отчёт БП3 грузится, площадка рабочая,
      и отказ относится к конкретному файлу;
  [5] для загрузившегося отчёта — параметры схемы и варианты настроек через свойства (это D1).
Только чтение: в ИБ ничего не пишется, отчёты живут в памяти сеанса.

Запуск (обязательно с логом):
  python _d1_env_probe.py --log _d1_env_probe.txt
"""
import sys

sys.path.insert(0, r"C:\1C_LLM\ckb")
from _d1_erf_com_probe import (D1_PARAMS, TARGETS, _log, dump_param, dump_settings,  # noqa: E402
                               first_attr, full, get, iterate,  # noqa: E402
                               make_protection, render, say, short)

STATE_MARKERS = [r"C:\1C_LLM\ckb\_ibcmd_work\ib_bp3\ckb_ibcmd_state.json"]

# отпечаток конфигурации сеанса: имена, которых нет вне БП3, и общие для большинства конфигураций
FINGERPRINT = [
    ("только БП3", "ПеречислениеСсылка.СтатусыРасходовУСН"),
    ("только БП3", "ПеречислениеСсылка.ОтражениеВУСН"),
    ("только БП3", "СправочникСсылка.Банки"),
    ("только БП3", "ДокументСсылка.ПоступлениеТоваровУслуг"),
    ("общее", "СправочникСсылка.Номенклатура"),
    ("общее", "ПланСчетовСсылка.Хозрасчетный"),
]

# то самое значение перечисления, на котором падает компиляция запроса
ENUM_TYPE = "ПеречислениеСсылка.СтатусыРасходовУСН"
ENUM_VALUES = ["НеСписаноНеОплачено", "НеСписано", "ТакогоЗначенияТочноНет"]

# чужие внешние отчёты той же площадки: грузятся ли они вообще
OTHER_ERF = [
    r"C:\1C_LLM\LoadDoc\Test3_ОтчетПустой.erf",
    r"C:\1C_LLM\LoadDoc\БП3\PUBID_1719010-КомплектКонтрольныхОтчетовБП30"
    r"\РеестрПропущенныхНомеров.erf",
    r"C:\1C_LLM\LoadDoc\Edit_V26_СравнениеУСНИ90_2\СравнениеУСНИ90_2_v26.edited.erf",
    r"C:\1C_LLM\LoadDoc\БП3\СравнениеУСНИ90_2.erf",
]

# есть ли у загруженного отчёта макет-СКД: через Метаданные и через ПолучитьМакет
# (документ 52999: ВнешнийОтчет.СхемаКомпоновкиДанных доступен внешнему соединению, значит
#  None при живом макете-СКД был бы дефектом пути, а не отсутствием схемы у отчёта)
METADATA_PROPS = ["Макеты", "Templates", "ОсновнойМодуль", "CommonModules", "ВсеМодули"]
TEMPLATE_NAMES = ["ОсновнаяСхемаКомпоновкиДанных", "СхемаКомпоновкиДанных"]


# чем звать глобальные функции: русские имена — основной вариант, английские — резерв
TYPE_FUNCS = ("ТипФУн", "TypeFqn")
VALUE_IN_TYPE = ("ЗначениеВТипе", "ValueInType")


def read_markers():
    say("[1. МЕТКА СОСТОЯНИЯ ИБ]")
    for path in STATE_MARKERS:
        try:
            with open(path, encoding="utf-8") as fh:
                say("  " + path + " -> " + fh.read().strip()[:400])
        except Exception as exc:                                # noqa: BLE001
            say("  " + path + " -> нет (" + short(exc) + ")")


def call_global(session, names, *args):
    """Один вызов глобальной функции сеанса: (разрешилось, значение или текст ошибки)."""
    errors = []
    for name in names:
        try:
            fn = getattr(session, name)
        except Exception as exc:                                # noqa: BLE001
            errors.append(f"{name}: {type(exc).__name__}")
            continue
        try:
            return True, fn(*args)
        except Exception as exc:                                # noqa: BLE001
            errors.append(f"{name}(...): {full(exc)}")
    return False, " ; ".join(errors)


def fingerprint(session):
    say("\n[2. ОТПЕЧАТОК КОНФИГУРАЦИИ СЕАНСА (ТипФУн)]")
    resolved = []
    for kind, type_name in FINGERPRINT:
        ok, value = call_global(session, TYPE_FUNCS, type_name)
        if ok:
            resolved.append(type_name)
            say(f"  РАЗРЕШИЛСЯ [{kind}] {type_name} -> {render(value)}")
        else:
            say(f"  ОТКАЗ      [{kind}] {type_name} -> {value[:300]}")
    say(f"  разрешилось имён: {len(resolved)} из {len(FINGERPRINT)}")
    return resolved



def enum_value_check(session):
    say("\n[3. ЗНАЧЕНИЕ ПЕРЕЧИСЛЕНИЯ В СЕАНСЕ (ЗначениеВТипе)]")
    ok, vtype = call_global(session, TYPE_FUNCS, ENUM_TYPE)
    if not ok:
        say(f"  тип {ENUM_TYPE} не разрешился: {vtype[:300]} — проверять значение не на чём")
        return
    say(f"  тип {ENUM_TYPE} получен: {render(vtype)}")
    for value_name in ENUM_VALUES:
        ok, value = call_global(session, VALUE_IN_TYPE, vtype, value_name)
        say(f"  {'ЕСТЬ ' if ok else 'НЕТ  '} {value_name}: "
            + (render(value) if ok else value[:300]))


def dump_report(report):
    """Параметры схемы и варианты настроек загрузившегося отчёта — это и есть слой D1."""
    name, schema = first_attr(report, ["СхемаКомпоновкиДанных", "DataCompositionSchema"])
    if schema is None:
        say(f"  СхемаКомпоновкиДанных не отдаётся ({schema}) — пробую ПолучитьМакет")
        for template_name in TEMPLATE_NAMES:
            try:
                candidate = report.ПолучитьМакет(template_name)
            except Exception:                                       # noqa: BLE001
                continue
            if candidate is None:
                continue
            ok, _ = get(candidate, "Параметры")
            if ok:
                schema, name = candidate, f"ПолучитьМакет({template_name})"
                break
        if schema is None:
            return
    say(f"  схема получена через {name}")
    name, coll = first_attr(schema, ["Параметры", "Parameters"])
    params = iterate(coll) if coll is not None else []
    say(f"  параметров объявлено: {len(params)}")
    for item in params:
        _, pname = first_attr(item, ["Имя", "Name"])
        label = pname if isinstance(pname, str) else "?"
        dump_param(item, f"  {label}{'  <- D1' if label in D1_PARAMS else ''}")
    name, coll = first_attr(schema, ["ВариантыНастроек", "SettingVariants"])
    variants = iterate(coll) if coll is not None else []
    say(f"  вариантов настроек: {len(variants)}")
    for variant in variants:
        _, vname = first_attr(variant, ["Имя", "Name"])
        say(f"  вариант {vname!r}")
        _, settings = first_attr(variant, ["Настройки", "Settings"])
        if settings is None:
            say(f"    Настройки варианта не отдались: {settings}")
            continue
        dump_settings(settings, f"    настройки варианта {vname!r}:")


def probe_templates(report):
    """Есть ли у загруженного отчёта макет-СКД: Метаданные.Макеты и ПолучитьМакет по имени."""
    name, meta = first_attr(report, ["Метаданные", "Metadata"])
    if meta is None:
        say(f"  Метаданные не отдаются ({meta})")
    else:
        say(f"  Метаданные получены через {name} ({type(meta).__name__})")
        name, coll = first_attr(meta, METADATA_PROPS)
        if coll is None:
            say(f"    макеты через Метаданные не отдаются: {coll}")
        else:
            items = iterate(coll)
            say(f"    через {name}: элементов {len(items)}")
            for item in items:
                _, tname = first_attr(item, ["Имя", "Name"])
                _, ttype = first_attr(item, ["Вид", "Type"])
                say(f"      {render(tname)} / {render(ttype)}")
    for template_name in TEMPLATE_NAMES:
        try:
            value = report.ПолучитьМакет(template_name)
        except Exception as exc:                                    # noqa: BLE001
            say(f"  ПолучитьМакет({template_name}): FAIL {short(exc)}")
            continue
        say(f"  ПолучитьМакет({template_name}) -> {render(value)}")


def try_load(manager, protection, path):
    """Создать() по файлу: первая удавшаяся раскладка аргументов."""
    attempts = [("Создать(файл, Ложь, защита)", (path, False, protection)),
                ("Создать(файл, Истина, защита)", (path, True, protection))]
    for tag, args in attempts:
        try:
            report = manager.Создать(*args)
            say(f"  ОК   {tag}")
            return report
        except Exception as exc:                                # noqa: BLE001
            say(f"  FAIL {tag}: {full(exc)[:900]}")
    return None


def connect():
    from win32com.client import Dispatch
    for title, conn_str in TARGETS:
        say(f"\n[connect] {title}: {conn_str}")
        try:
            connector = Dispatch("V83.COMConnector")
            session = connector.Connect(conn_str)
            say("  ОК")
            return connector, session
        except Exception as exc:                                # noqa: BLE001
            say(f"  ОТКАЗ: {short(exc)}")
    return None, None


def main():
    read_markers()
    connector, session = connect()
    if session is None:
        say("\nНет доступной ИБ — замер не состоялся")
        return 2

    resolved = fingerprint(session)
    enum_value_check(session)

    name, manager = first_attr(session, ["ВнешниеОтчеты", "ExternalReports"])
    if manager is None:
        say(f"\nменеджер внешних отчётов не отдаётся: {manager}")
        return 2
    say(f"\n[4. ЗАГРУЗКА .erf МЕНЕДЖЕРОМ ({name})]")
    protection, _ = make_protection(session)
    if protection is None:
        say("  без описания защиты предупреждение безопасности блокирует Создать")
        return 2
    loaded = []
    for path in OTHER_ERF:
        say(f"\n  файл: {path}")
        report = try_load(manager, protection, path)
        if report is None:
            continue
        loaded.append(path)
        _, used = first_attr(report, ["ИспользуемоеИмяФайла", "UsedFileName"])
        say(f"  загружен: {render(used)}")
        say("  --- содержимое через свойства ---")
        probe_templates(report)
        dump_report(report)

    say("\n[ИТОГ]")
    say(f"  имён конфигурации разрешилось: {len(resolved)} из {len(FINGERPRINT)}")
    say(f"  загрузилось отчётов: {len(loaded)} из {len(OTHER_ERF)}")
    say("  (A) или (B) читается из [2]/[3]: тип разрешим — отказ относится к файлу,")
    say("  нерезолвнут — к конфигурации сеанса.")
    try:
        connector.Disconnect()
    except Exception:                                           # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    code = main()
    if "--log" in sys.argv:
        log_path = sys.argv[sys.argv.index("--log") + 1]
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(_log) + "\n")
    sys.exit(code)

