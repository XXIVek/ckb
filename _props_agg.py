import re, os

ROOT = r'C:\1C_LLM\LoadDoc\Configurations\XML_files'
CFG = ['BGU2', 'BP3', 'Config_NULL', 'KomMag', 'MinCfg', 'UNF3', 'UT11', 'ZUP31']
OUT = open(r'C:\TMP\_props_agg.txt', 'w', encoding='utf-8')
NAMES = ['DefaultRunMode', 'UsePurposes', 'ScriptVariant', 'DefaultRoles', 'DataSearch',
         'AdditionalFullTextSearchDictionaries', 'CommonSettingsStorage',
         'ReportsUserSettingsStorage', 'ReportsVariantsStorage', 'FormDataSettingsStorage',
         'DynamicListsUserSettingsStorage', 'URLExternalDataStorage', 'DefaultSearchForm',
         'AppModule', 'SessionModule', 'ExternalConnectionModule', 'DataProcessorsModule',
         'ManagedApplicationModule', 'OrdinaryApplicationModule', 'CommonForm',
         'CommonAttribute', 'MobileApplicationURLs', 'AllowedIncomingShareRequestTypes',
         'RequiredMobileApplicationPermissions', 'UsedMobileApplicationFunctionalities',
         'StandaloneConfigurationRestrictionRoles', 'StandaloneConfiguration', 'Signature',
         'Security', 'UseManagedFormInOrdinaryApplication',
         'UseOrdinaryFormInManagedApplication', 'DataCompositionSchemaDefaultSettings',
         'DefaultDynamicListSettingsForm', 'DefaultReportSettingsForm',
         'DefaultReportVariantForm', 'DefaultConstantsForm']

def read(cfg):
    return open(os.path.join(ROOT, cfg, 'Configuration.xml'), encoding='utf-8-sig').read()

def props_block(t):
    a, b = t.find('<Properties'), t.find('</Properties>')
    return t[a:b]

def find_all(block, name):
    res = []
    for m in re.finditer(r'<([A-Za-z0-9]*:)?%s((?:\s[^>]*?)?)(/>|>)' % name, block):
        if m.group(3) == '/>':
            res.append(('self-closed', ''))
            continue
        m2 = re.search(r'</[A-Za-z0-9]*:?%s>' % name, block[m.end():])
        inner = block[m.end():m.end() + m2.start()] if m2 else ''
        res.append(('full', ' '.join(inner.split())))
    return res

for n in NAMES:
    forms = {}
    vals = {}
    for cfg in CFG:
        block = props_block(read(cfg))
        hits = find_all(block, n)
        if not hits:
            forms.setdefault('ABSENT', []).append(cfg)
            continue
        for kind, inner in hits:
            forms.setdefault(kind, []).append(cfg)
            if inner:
                vals.setdefault(inner[:200], []).append(cfg)
    line = '%-40s absent=%d self=%d full=%d' % (
        n, len(forms.get('ABSENT', [])), len(forms.get('self-closed', [])),
        len(forms.get('full', [])))
    OUT.write(line + '\n')
    if forms.get('ABSENT') and len(forms['ABSENT']) < 8:
        OUT.write('    ABSENT in: %s\n' % ','.join(forms['ABSENT']))
    if forms.get('full') and len(forms['full']) < 8:
        OUT.write('    FULL in: %s\n' % ','.join(forms['full']))
    for v, cs in vals.items():
        OUT.write('    VALUE %-60r <- %s\n' % (v, ','.join(cs)))
OUT.close()
print('ok')
