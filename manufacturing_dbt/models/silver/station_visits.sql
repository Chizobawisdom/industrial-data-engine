SELECT 
    (payload->>'serial_number') AS serial_number,
    (payload->>'station') AS station,
    (payload->>'action') AS action,
    sim_timestamp,
    ingested_at
FROM bronze.manufacturing_events
WHERE event_type = 'production_event'