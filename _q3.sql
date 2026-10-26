\pset footer off
SELECT E'\n@@@@@ ' || question || ' [id ' || id || ', ' || length(answer) || E' chars]\n' || answer
FROM knowledge_snippets
WHERE question IN ('rules:kb-rules:functional:knowledge-layer',
                   'rules:kb-rules:checks:layer-availability',
                   'rules:kb-rules:checks:index')
ORDER BY question;
