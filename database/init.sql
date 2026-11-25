CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- The main landing zone for all Kafka events
CREATE TABLE IF NOT EXISTS bronze.manufacturing_events (
    event_id UUID PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    sim_timestamp FLOAT NOT NULL,      -- Time since simulation start
    ingested_at TIMESTAMPTZ DEFAULT NOW(), -- Real-world wall clock time
    payload JSONB NOT NULL
);

-- Optional: Index the JSONB column so we can query it efficiently
CREATE INDEX IF NOT EXISTS idx_manufacturing_events_type 
    ON bronze.manufacturing_events(event_type);

CREATE INDEX IF NOT EXISTS idx_manufacturing_events_payload 
    ON bronze.manufacturing_events USING GIN (payload);