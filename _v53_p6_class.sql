SELECT target_class, count(*) AS rows_total,
       count(DISTINCT event_subscription_id) AS subscriptions
FROM event_subscription_sources
GROUP BY target_class
ORDER BY rows_total DESC
LIMIT 8;
