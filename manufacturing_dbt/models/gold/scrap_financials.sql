SELECT 
    station,
    reason,
    COUNT(*) AS units_scrapped,
    SUM(cost_usd) AS total_cost_usd
FROM {{ ref('scrap_events') }}
GROUP BY station, reason