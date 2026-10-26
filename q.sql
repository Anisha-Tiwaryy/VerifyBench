-- Q1: p50/p95 latency and success rate per API vs internal standard and competitor
-- SQLite has no percentile function, so percentiles come from window functions.
WITH ranked AS (
  SELECT api, latency_ms,
         ROW_NUMBER() OVER (PARTITION BY api ORDER BY latency_ms) AS rn,
         COUNT(*)     OVER (PARTITION BY api) AS n
  FROM api_calls WHERE status = 'success'
), pct AS (
  SELECT api,
    MAX(CASE WHEN rn = CAST(0.50 * n AS INT) THEN latency_ms END) AS p50,
    MAX(CASE WHEN rn = CAST(0.95 * n AS INT) THEN latency_ms END) AS p95
  FROM ranked GROUP BY api
), sr AS (
  SELECT api, COUNT(*) AS calls, ROUND(100.0 * AVG(status = 'success'), 1) AS success_pct
  FROM api_calls GROUP BY api
)
SELECT p.api, s.calls, p.p50, p.p95, st.target_p95_ms, st.competitor_p95_ms, s.success_pct
FROM pct p JOIN sr s USING (api) JOIN standards st USING (api)
ORDER BY p.p95 * 1.0 / st.target_p95_ms DESC;
