SELECT 'A. верхних строк '||count(*)||' | различных uuid '||count(DISTINCT uuid)
FROM configuration_objects WHERE object_type='FilterCriterion' AND depth=0;
SELECT 'B. имя '||name||' | конфигураций '||count(DISTINCT configuration_id)||' | различных uuid '||count(DISTINCT uuid)
FROM configuration_objects WHERE object_type='FilterCriterion' AND depth=0
GROUP BY name HAVING count(DISTINCT configuration_id)>1;
SELECT 'C. uuid '||uuid||' | имя '||name||' | конфигураций '||count(DISTINCT configuration_id)
FROM configuration_objects WHERE object_type='FilterCriterion' AND depth=0
GROUP BY uuid,name HAVING count(DISTINCT configuration_id)>1;
SELECT 'D. детей по верхним '||count(*) FROM configuration_objects
WHERE object_type='FilterCriterion' AND depth>0;
