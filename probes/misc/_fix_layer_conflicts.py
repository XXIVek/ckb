# -*- coding: utf-8 -*-
"""Правка строк 5917 и 5937 тем же кодом, что и update_snippet_tool (узел P6).

Причина — замер 20.10.2026 по восьми XML-выгрузкам и живой SQL configurations:
1. BriefInformation / DetailedInformation / Copyright / VendorInformationAddress /
   ConfigurationInformationAddress — многоязычные (v8:item -> v8:content ВНУК элемента),
   а профиль 5917 описывал их как text/free-text;
2. 5937 утверждал, что «парсер читает их через _multi_text» — код (CONFIGURATION_FIELDS,
   вид "text" -> _text) так не делает, и значения в БД не доходят (id=28 BGU2: NULL);
3. словари значений группы «Совместимость» в профиле были неполные (Unmanaged вместо
   Automatic, единственный Taxi).

Правка идёт функцией src/mcp_tools_api.update_snippet — тем же телом, что и MCP-инструмент
(офлайн-слой по образцу _v13_mcp_layer.py), поэтому прежнее содержимое уходит в
snippet_audit_log с action='fix'. Прямой UPDATE не используется: он бы аудит потерял.
"""
import sys

sys.path.insert(0, r"C:\1C_LLM\ckb\src")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import database                      # noqa: E402
from mcp_tools_api import update_snippet  # noqa: E402

# 5917: строки профиля формата path|kind|required|default|allowed|provenance|store|value
LINE_FIXES_5917 = [
    ("Properties/Vendor|",
     "Properties/Vendor|text|no|empty|свободная строка, НЕ многоязычная|dump8|"
     "configurations.vendor_name|empty@MinCfg; заполнено у 6 из 8 (5x «Фирма \"1С\"», "
     "KomMag — свой поставщик), в БД доходит"),
    ("Properties/Version|",
     "Properties/Version|text|no|empty|свободная строка; по замеру N.N.N.N|dump8|"
     "configurations.version|empty@MinCfg; заполнено у 6 из 8, в БД доходит"),
    ("Properties/BriefInformation|",
     "Properties/BriefInformation|multilang|no|empty|v8:item/v8:lang+v8:content по языкам|dump8|"
     "configurations.short_info|empty@MinCfg; заполнено у 6 из 8, в БД НЕ доходит "
     "(===REACHABILITY===)"),
    ("Properties/DetailedInformation|",
     "Properties/DetailedInformation|multilang|no|empty|v8:item/v8:lang+v8:content|dump8|"
     "configurations.detailed_info|empty@MinCfg; заполнено у 6 из 8, в БД НЕ доходит"),
    ("Properties/Copyright|",
     "Properties/Copyright|multilang|no|empty|v8:item/v8:lang+v8:content|dump8|"
     "configurations.copyright|empty@MinCfg; заполнено у 6 из 8, в БД НЕ доходит"),
    ("Properties/VendorInformationAddress|",
     "Properties/VendorInformationAddress|multilang|no|empty|v8:item/v8:lang+v8:content|dump8|"
     "configurations.vendor_url|empty@MinCfg; заполнено у 6 из 8, в БД НЕ доходит"),
    ("Properties/ConfigurationInformationAddress|",
     "Properties/ConfigurationInformationAddress|multilang|no|empty|"
     "v8:item/v8:lang+v8:content|dump8|configurations.config_url|empty@MinCfg; "
     "заполнено у 6 из 8, в БД НЕ доходит"),
    ("Properties/UpdateCatalogAddress|",
     "Properties/UpdateCatalogAddress|text|no|empty|URL каталога, а не файла|dump8|"
     "configurations.update_url|empty@MinCfg; заполнено у 6 из 8 "
     "(downloads.v8.1c.ru/tmplts/ — и http, и https), в БД доходит"),
    ("Properties/IncludeHelpInContents|",
     "Properties/IncludeHelpInContents|bool|no|false|true,false|dump8|"
     "configurations.help_included|false@MinCfg; true только у ZUP31"),
    ("Properties/DataLockControlMode|",
     "Properties/DataLockControlMode|enum|no|Managed|Managed,Automatic|dump8|"
     "configurations.lock_mode_default|Managed@MinCfg; Automatic у KomMag; «Автоматический и "
     "управляемый» отдельным токеном НЕ подтверждён (прежний словарь Managed/Unmanaged ошибочен)"),
    ("Properties/ModalityUseMode|",
     "Properties/ModalityUseMode|enum|no|DontUse|DontUse,UseWithWarnings,Use|dump8|"
     "configurations.modality_mode|DontUse@MinCfg; UseWithWarnings у BP3 и UT11, Use у KomMag"),
    ("Properties/SynchronousPlatformExtensionAndAddInCallUseMode|",
     "Properties/SynchronousPlatformExtensionAndAddInCallUseMode|enum|no|DontUse|"
     "Use,DontUse (третье значение замером не подтверждено)|dump8|configurations.ext_comp_sync_mode|"
     "DontUse@MinCfg; Use у шести выгрузок"),
    ("Properties/InterfaceCompatibilityMode|",
     "Properties/InterfaceCompatibilityMode|enum|no|Taxi|Taxi,TaxiEnableVersion8_2,"
     "Version8_2EnableTaxi (Version8_2 не подтверждён)|dump8|configurations.interface_compat_mode|"
     "Taxi@MinCfg; TaxiEnableVersion8_2 у пяти, Version8_2EnableTaxi у KomMag"),
    ("Properties/CompatibilityMode|",
     "Properties/CompatibilityMode|enum|no|Version8_3_27|Version8_3_NN (по замеру NN = 19, 24, 27; "
     "Version8_2_16 и Version8_1 НЕ подтверждены)|dump8|configurations.compatibility_mode|"
     "Version8_3_27@MinCfg; Version8_3_24 у UNF3, Version8_3_19 у KomMag"),
    # словарь provenance: без строки dump8 новые строки ссылались бы на неизвестное значение
    ("dump = подтверждено непустым значением в MinCfg,",
     "dump = подтверждено непустым значением в MinCfg, dump8 = подтверждено повторным замером "
     "20.10.2026 по восьми XML-выгрузкам (MinCfg, Config_NULL, BGU2, BP3, KomMag, UNF3, UT11, "
     "ZUP31),"),
]

LINE_INSERT_AFTER_5917 = [
    ("Разбор делает src/configuration_meta_parser.py",
     "Повторный замер 20.10.2026 по восьми выгрузкам уточнил тип пяти текстовых свойств "
     "(многоязычные), словари значений группы «Совместимость» и главное — что из маппинга "
     "реально доходит до колонок: раздел ===REACHABILITY===."),
]

REACHABILITY_SECTION = """===REACHABILITY measured:20.10.2026 (8 выгрузок + живой SQL configurations id=28 BGU2, id=80 MinCfg)===
Строка в CONFIGURATION_FIELDS ещё НЕ означает, что значение доходит до колонки.
ДОХОДЯТ: Name, Synonym (один язык, остальные теряются с предупреждением), Version, Vendor,
DefaultRunMode, UsePurposes, ScriptVariant, DefaultRoles, DefaultLanguage, UpdateCatalogAddress,
IncludeHelpInContents, DataLockControlMode, ModalityUseMode,
SynchronousPlatformExtensionAndAddInCallUseMode, InterfaceCompatibilityMode, CompatibilityMode.
НЕ ДОХОДЯТ — колонка есть, значение теряется на разборе: BriefInformation -> short_info,
DetailedInformation -> detailed_info, Copyright -> copyright, VendorInformationAddress -> vendor_url,
ConfigurationInformationAddress -> config_url. Причина: CONFIGURATION_FIELDS задаёт этим полям вид
"text", а разбор зовёт _text(), которая на составном элементе возвращает None; v8:content лежит
внутри v8:item, то есть ВНУКОМ элемента свойства. Многоязычный разбор (_multi_text, _synonym_text)
в коде применяется только к Synonym. Замер BGU2: в XML все пять заполнены, в БД — NULL. Это
дефект загрузчика V32, а не «в конфигурации этого нет».
Карточки категорий: «Разработка» — property-configuration-development;
«Справочная информация» — property-configuration-help-contents (у пункта «Справочная
информация» XML-представления нет); «Совместимость» — property-configuration-compatibility
(измеренные токены перечислений и значения по умолчанию новой конфигурации 8.3.27).
"""

# 5937: абзац о парсере заменяется целиком (границы — строка-заголовок абзаца и пустая строка)
PARA_START_5937 = "ЧЕМ ПУНКТЫ 8, 9, 12, 13, 14 НЕ ЯВЛЯЮТСЯ"
PARA_NEW_5937 = """ЧЕМ ПУНКТЫ 8, 9, 12, 13, 14 НЕ ЯВЛЯЮТСЯ: это НЕ «строка». Значение многоязычное — текст лежит
внутри <v8:item><v8:lang>ru</v8:lang><v8:content>…</v8:content></v8:item>, причём v8:content —
ВНУК элемента свойства (прямой поиск детей его не находит). Замер 20.10.2026 по восьми выгрузкам:
заполнены у шести (BGU2, BP3, KomMag, UNF3, UT11, ZUP31), пусты у MinCfg и Config_NULL.
⚠️ В БД ЭТИ ЗНАЧЕНИЯ НЕ ДОХОДЯТ — прежняя формулировка «парсер читает их через _multi_text»
была неверна. CONFIGURATION_FIELDS (src/configuration_meta_parser.py) задаёт этим пяти полям вид
"text", а разбор зовёт _text(), которая на составном элементе возвращает None; многоязычный
разбор (_multi_text, _synonym_text) применяется только к Synonym. Замер живым SQL 20.10.2026:
у BGU2 в XML все пять заполнены, а short_info / detailed_info / copyright / vendor_url /
config_url в configurations (id=28) равны NULL. Колонки существуют — теряется значение на разборе,
и это дефект загрузчика V32; он назван и в карточке property-configuration-development.
Отличие от Vendor: Properties/Vendor — простой текст (замер: «Фирма \"1С\"» у пяти из восьми
выгрузок), и колонка configurations.vendor_name заполняется.
ГДЕ ЭТИ ПУНКТЫ НАХОДЯТСЯ В КОНФИГУРАТОРЕ: 8, 9, 12, 13, 14 стоят в категории «Разработка»
(вместе с Vendor, Version, UpdateCatalogAddress), а не в «Представлении»; здесь они перечислены
по разбивке исходного перечня пользователя. Карточка категории — property-configuration-development."""


def read_answer(snippet_id):
    with database.get_cursor() as cur:
        cur.execute("SELECT answer FROM knowledge_snippets WHERE id = %s", (snippet_id,))
        row = cur.fetchone()
    return row["answer"] or ""


def patch_lines(answer, fixes, inserts, sid):
    """Замена строк по уникальному префиксу; вставка после строки-префикса."""
    lines = answer.split("\n")
    for prefix, new_line in fixes:
        hits = [i for i, ln in enumerate(lines) if ln.startswith(prefix)]
        if len(hits) != 1:
            raise SystemExit(f"[{sid}] префикс {prefix!r}: найдено {len(hits)} строк, ждалась 1")
        lines[hits[0]] = new_line
    for prefix, new_line in inserts:
        hits = [i for i, ln in enumerate(lines) if ln.startswith(prefix)]
        if len(hits) != 1:
            raise SystemExit(f"[{sid}] префикс вставки {prefix!r}: найдено {len(hits)}")
        lines.insert(hits[0] + 1, new_line)
    return "\n".join(lines)


def patch_paragraph(answer, start_prefix, new_block, sid):
    lines = answer.split("\n")
    starts = [i for i, ln in enumerate(lines) if ln.startswith(start_prefix)]
    if len(starts) != 1:
        raise SystemExit(f"[{sid}] абзац {start_prefix!r}: найдено {len(starts)}")
    start = starts[0]
    end = start
    while end < len(lines) and lines[end].strip():
        end += 1
    lines[start:end] = new_block.split("\n")
    return "\n".join(lines)


def insert_block_before(answer, marker, block, sid):
    lines = answer.split("\n")
    hits = [i for i, ln in enumerate(lines) if ln.startswith(marker)]
    if len(hits) != 1:
        raise SystemExit(f"[{sid}] маркер {marker!r}: найдено {len(hits)}")
    lines[hits[0]:hits[0]] = block.rstrip("\n").split("\n") + [""]
    return "\n".join(lines)


def main():
    a5917 = read_answer(5917)
    new5917 = patch_lines(a5917, LINE_FIXES_5917, LINE_INSERT_AFTER_5917, 5917)
    new5917 = insert_block_before(new5917, "===MAPPING_SUMMARY", REACHABILITY_SECTION, 5917)
    for must in ("===PROPERTY_PROFILE", "path|kind|required|default|allowed|provenance",
                 "===MAPPING_SUMMARY", "found=55 mapped=22", "===ROOT_EXT_MODULES",
                 "===REACHABILITY", "dump8"):
        if must not in new5917:
            raise SystemExit(f"[5917] пропал обязательный маркер {must!r}")
    if "Managed|Unmanaged" in new5917:
        raise SystemExit("[5917] прежняя пара Managed|Unmanaged осталась")

    a5937 = read_answer(5937)
    new5937 = patch_paragraph(a5937, PARA_START_5937, PARA_NEW_5937, 5937)
    for must in ("===PROPERTY_CARD", "MainClientApplicationWindowMode", "FullscreenWorkplace",
                 "Kiosk", "configurations.short_info", "НЕ ДОХОДЯТ"):
        if must not in new5937:
            raise SystemExit(f"[5937] пропал обязательный маркер {must!r}")
    if "Парсер читает их через _multi_text" in new5937:
        raise SystemExit("[5937] прежнее утверждение о _multi_text осталось")

    res1 = update_snippet(5917, new_answer=new5917, reason=(
        "Замер 20.10.2026 по восьми XML-выгрузкам: пять текстовых свойств (BriefInformation, "
        "DetailedInformation, Copyright, VendorInformationAddress, ConfigurationInformationAddress) "
        "многоязычные, а не text; значения заполнены у 6 из 8 и не доходят до колонок "
        "(код: CONFIGURATION_FIELDS задаёт вид text, разбор зовёт _text). Словари значений "
        "группы «Совместимость» исправлены по замеру (Unmanaged -> Automatic, добавлены "
        "UseWithWarnings, TaxiEnableVersion8_2, Version8_2EnableTaxi), добавлены значения по "
        "умолчанию новой конфигурации 8.3.27 и раздел REACHABILITY."))
    print("5917:", str(res1)[:400])

    res2 = update_snippet(5937, new_answer=new5937, reason=(
        "Прежняя формулировка «парсер читает их через _multi_text» противоречит коду "
        "(CONFIGURATION_FIELDS задаёт вид text, разбор зовёт _text) и живой БД: у BGU2 значения "
        "есть в XML, а short_info/detailed_info/copyright/vendor_url/config_url равны NULL "
        "(id=28). Назван дефект загрузчика V32, добавлено положение этих свойств в конфигураторе "
        "(категория «Разработка») и ссылка на карточку property-configuration-development."))
    print("5937:", str(res2)[:400])

    for sid, old, new in ((5917, a5917, new5917), (5937, a5937, new5937)):
        now = read_answer(sid)
        print(f"{sid}: было {len(old)} симв -> стало {len(now)} симв, "
              f"записано ровно подготовленное: {now == new}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


