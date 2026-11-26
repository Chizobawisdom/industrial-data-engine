SELECT 
    (payload->>'serial_number') AS serial_number,
    (payload->>'station') AS station,
    (payload->>'attempt_number')::INT AS attempt_number,
    (payload->>'defect_reason') AS defect_reason,
    sim_timestamp
FROM bronze.manufacturing_events
WHERE event_type = 'rework_event'