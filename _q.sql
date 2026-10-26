\pset footer off
SELECT E'\n@@@@@ ' || question || E'\n' || answer
FROM knowledge_snippets
WHERE question IN ('rules:kb-rules:journal:hdr:10',
                   'rules:kb-rules:journal:ref:10',
                   'rules:kb-rules:journal:ref:09',
                   'rules:always:index')
ORDER BY question;
