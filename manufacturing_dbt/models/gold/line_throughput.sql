SELECT 
    station,
    COUNT(*) AS units_processed,
    MIN(sim_timestamp) AS first_seen_at,
    MAX(sim_timestamp) AS last_seen_at
FROM {{ ref('station_visits') }}
WHERE action = 'EXIT'
GROUP BY station