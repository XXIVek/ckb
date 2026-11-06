# Временный прогон шага П6: регрессионный контур прежних узлов (критерий 6 готовности V52).
# Узел V52 пишет в общие таблицы детей (forms/form_ext/commands), поэтому контур V47–V51,
# цепей ревизий и правок внешних объектов обязан остаться зелёным.
$env:PGUSER = 'postgres'
$env:PGPASSWORD=(Get-Content .env | ConvertFrom-StringData).PGPASSWORD
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location 'C:\1C_LLM\ckb'
$checks = @(
  'tools/check_v51_exchange_plans.py',
  'tools/check_v50_common_attributes.py',
  'tools/check_v49_roles.py',
  'tools/check_v48_session_parameters.py',
  'tools/check_v47_configuration_object_modules.py',
  'tools/check_v19_revisions.py',
  'tools/check_v20_config_link.py'
)
foreach ($check in $checks) {
  $name = [System.IO.Path]::GetFileNameWithoutExtension($check)
  python $check *> "_scratch/_v52_p6_regress_$name.txt"
  "EXIT $name = $LASTEXITCODE"
}
'Готово'
