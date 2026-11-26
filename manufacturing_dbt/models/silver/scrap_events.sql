SELECT 
    (payload->>'serial_number') AS serial_number,
    (payload->>'station') AS station,
    (payload->>'reason') AS reason,
    (payload->>'cost_usd')::FLOAT AS cost_usd,
    sim_timestamp
FROM bronze.manufacturing_events
WHERE event_type = 'scrap_event'