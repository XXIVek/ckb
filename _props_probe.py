import re, os, glob

ROOT = r'C:\1C_LLM\LoadDoc\Configurations\XML_files'
NAMES = [
    'DefaultRunMode', 'UsePurposes', 'ScriptVariant', 'DefaultRoles', 'DataSearch',
    'AdditionalFullTextSearchDictionaries', 'CommonSettingsStorage',
    'ReportsUserSettingsStorage', 'ReportsVariantsStorage', 'FormDataSettingsStorage',
    'DynamicListsUserSettingsStorage', 'URLExternalDataStorage',
    'DataCompositionSchemaDefaultSettings', 'AppModule', 'SessionModule',
    'ExternalConnectionModule', 'DataProcessorsModule', 'ManagedApplicationModule',
    'OrdinaryApplicationModule', 'CommonForm', 'CommonCommand', 'CommonAttribute',
    'MobileApplicationURLs', 'RequiredMobileApplicationPermissions',
    'UsedMobileApplicationFunctionalities', 'StandaloneConfigurationRestrictionRoles',
    'StandaloneConfiguration', 'ConfigurationExtensionCompatibilityMode',
    'CompatibilityMode', 'Security', 'CronetConfigurationExtension',
    'ObjectAttributeComment', 'PasswordMRMLicenses', 'RequiredProtectedLicenses',
]

files = sorted(glob.glob(os.path.join(ROOT, '*', 'Configuration.xml')))
found = {}
for p in files:
    cfg = os.path.basename(os.path.dirname(p))
    t = open(p, encoding='utf-8-sig', errors='replace').read()
    for n in NAMES:
        ms = list(re.finditer(r'<[A-Za-z0-9]*:?%s[\s>]' % n, t))
        if not ms:
            continue
        found.setdefault(n, {'cfgs': [], 'sample': None, 'count': 0})
        found[n]['cfgs'].append(cfg)
        found[n]['count'] += len(ms)
        if found[n]['sample'] is None:
            s = ms[0].start()
            end = t.find('</', s)
            block = t[s:end + 12] if end > 0 else t[s:s + 500]
            found[n]['sample'] = ' '.join(block.split())[:600]

print('dumps:', [os.path.basename(os.path.dirname(p)) for p in files])
for n in NAMES:
    d = found.get(n)
    if not d:
        print('ABSENT  %s' % n)
        continue
    print('PRESENT %s  cfgs=%d/%d total=%d' % (n, len(d['cfgs']), len(files), d['count']))
    print('        in:', ','.join(d['cfgs']))
    print('        sample:', d['sample'])
