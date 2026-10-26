import re
p = r'C:\1C_LLM\LoadDoc\Configurations\XML_files\BGU2\Configuration.xml'
t = open(p, encoding='utf-8-sig').read()
out = open(r'C:\TMP\\_direct.txt', 'w', encoding='utf-8')
for n in ('AdditionalFullTextSearchDictionaries', 'DataSearch', 'MobileApplicationURLs',
          'RequiredMobileApplicationPermissions', 'StandaloneConfigurationRestrictionRoles',
          'URLExternalDataStorage', 'CommonSettingsStorage', 'ReportsVariantsStorage',
          'UseManagedFormInOrdinaryApplication', 'DefaultRoles', 'AppModule', 'Language',
          'DefaultLanguage', 'DefaultSearchForm'):
    r1 = re.findall(r'<[A-Za-z0-9]*:?%s[\s>]' % n, t)
    r2 = re.findall(r'<(?:[A-Za-z0-9]+:)?%s(?:[\s>/]|$)' % n, t, re.M)
    i = t.find('<' + n)
    j = t.find(':cmlg:' + n)
    out.write('%s r1=%d r2=%d idx=%d idx2=%d\n' % (n, len(r1), len(r2), i, j))
    k = max(i, j)
    if k >= 0:
        blk = t[k:t.find('</', k) + 12]
        out.write('   ' + ' '.join(blk.split())[:700] + '\n')
out.close()
print('ok')
