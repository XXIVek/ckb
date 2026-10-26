\pset footer off
SELECT E'\n@@@@@ ' || question || E' [' || length(answer) || E' chars]\n' || answer
FROM knowledge_snippets
WHERE question IN ('rules:kb-rules:',
                   'rules:kb-rules:always:index',
                   'rules:kb-rules:always:search-first',
                   'rules:kb-rules:always:two-phase-reading',
                   'rules:kb-rules:always:edit-in-db')
ORDER BY question;
