SELECT 
    (payload->>'serial_number') AS serial_number,
    (payload->>'station') AS station,
    (payload->>'measurement')::FLOAT AS measurement,
    (payload->>'tolerance')::FLOAT AS tolerance,
    (payload->>'result') AS result,
    sim_timestamp
FROM bronze.manufacturing_events
WHERE event_type = 'quality_inspection'