import re, os

ROOT = r'C:\1C_LLM\LoadDoc\Configurations\XML_files'
CFG = ['BGU2', 'BP3', 'Config_NULL', 'KomMag', 'MinCfg', 'UNF3', 'UT11', 'ZUP31']
OUT = open(r'C:\TMP\_props4.txt', 'w', encoding='utf-8')

NAMES = ['DefaultRunMode', 'UsePurposes', 'ScriptVariant', 'DefaultRoles', 'DataSearch',
         'AdditionalFullTextSearchDictionaries', 'CommonSettingsStorage',
         'ReportsUserSettingsStorage', 'ReportsVariantsStorage', 'FormDataSettingsStorage',
         'DynamicListsUserSettingsStorage', 'URLExternalDataStorage',
         'DefaultSearchForm', 'AppModule', 'SessionModule', 'ExternalConnectionModule',
         'DataProcessorsModule', 'ManagedApplicationModule', 'OrdinaryApplicationModule',
         'CommonForm', 'CommonCommand', 'CommonAttribute', 'CommonModule',
         'MobileApplicationURLs', 'AllowedIncomingShareRequestTypes',
         'RequiredMobileApplicationPermissions', 'UsedMobileApplicationFunctionalities',
         'StandaloneConfigurationRestrictionRoles', 'StandaloneConfiguration',
         'Signature', 'Language', 'DefaultLanguage', 'Security',
         'UseManagedFormInOrdinaryApplication', 'UseOrdinaryFormInManagedApplication']

def read(cfg):
    return open(os.path.join(ROOT, cfg, 'Configuration.xml'), encoding='utf-8-sig').read()

def find_all(t, name):
    """возвращает список (pos, kind, inner) для элемента с локальным именем name"""
    res = []
    for m in re.finditer(r'<([A-Za-z0-9]*:)?%s((?:\s[^>]*?)?)(/>|>)' % name, t):
        pos = m.start()
        if m.group(3) == '/>':
            res.append((pos, 'self-closed', ''))
            continue
        close = re.compile(r'</[A-Za-z0-9]*:?%s>' % name)
        m2 = close.search(t, m.end())
        inner = t[m.end():m2.start()] if m2 else ''
        res.append((pos, 'full', ' '.join(inner.split())))
    return res

for cfg in CFG:
    t = read(cfg)
    child_count = {}
    pstart = t.find('<Properties')
    pend = t.find('</Properties>')
    cstart = t.find('<ChildObjects')
    OUT.write('\n########## %s props=[%d,%d] childobjects_at=%d\n' % (cfg, pstart, pend, cstart))
    for n in NAMES:
        hits = find_all(t, n)
        if not hits:
            OUT.write('  ABSENT      %s\n' % n)
            continue
        for pos, kind, inner in hits:
            where = 'PROPERTIES' if pstart <= pos < pend else ('CHILD' if pos > cstart else 'other@%d' % pos)
            if where == 'CHILD':
                child_count[n] = child_count.get(n, 0) + 1
                continue
            OUT.write('  %-11s %-12s %-10s %s\n' % (n, kind, where, inner[:400]))
        if where == 'CHILD':
            pass
    for n, c in sorted(child_count.items()):
        OUT.write('  CHILD-COUNT %s = %d\n' % (n, c))
OUT.close()
print('ok')
