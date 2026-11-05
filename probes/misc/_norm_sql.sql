-- _norm_sql.sql — использует ли planner индекс по параметру, а не по литералу.
-- PREPARE + EXECUTE: первые пять вызовов дают custom plan, шестой — generic plan,
-- именно его видит сервер, где значение приходит параметром.
PREPARE p_like(text) AS
    SELECT id, question FROM knowledge_snippets
    WHERE question_norm LIKE ($1 || '%') ESCAPE '!' ORDER BY question LIMIT 20;
PREPARE p_range(text, text) AS
    SELECT id, question FROM knowledge_snippets
    WHERE question_norm >= $1 AND question_norm < $2 ORDER BY question LIMIT 20;

SELECT '--- like: custom plan ---';
EXECUTE p_like('rules:core-rules:');
SELECT '--- like: generic plan ---';
EXECUTE p_like('rules:core-rules:');
EXECUTE p_like('rules:core-rules:');
EXECUTE p_like('rules:core-rules:');
EXECUTE p_like('rules:core-rules:');
EXPLAIN (ANALYZE,BUFFERS) EXECUTE p_like('rules:core-rules:');

SELECT '--- range: generic plan ---';
EXECUTE p_range('rules:core-rules:', 'rules:core-rules;');
EXECUTE p_range('rules:core-rules:', 'rules:core-rules;');
EXECUTE p_range('rules:core-rules:', 'rules:core-rules;');
EXECUTE p_range('rules:core-rules:', 'rules:core-rules;');
EXECUTE p_range('rules:core-rules:', 'rules:core-rules;');
EXPLAIN (ANALYZE,BUFFERS) EXECUTE p_range('rules:core-rules:', 'rules:core-rules;');
