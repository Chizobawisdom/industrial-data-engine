SELECT 
    station,
    result,
    COUNT(*) AS count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(PARTITION BY station), 2) AS percentage
FROM {{ ref('quality_inspections') }}
GROUP BY station, result