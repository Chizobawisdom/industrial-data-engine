import json
import os
from kafka import KafkaConsumer
import psycopg2
from psycopg2.extras import Json

# Configuration
KAFKA_TOPICS = [
    "manufacturing.production",
    "manufacturing.quality",
    "manufacturing.rework",
    "manufacturing.scrap"
]
KAFKA_SERVERS = ['127.0.0.1:9092']
DB_CONFIG = {
    "dbname": "manufacturing",
    "user": "engineer",
    "password": "wisdom",
    "host": "localhost",
    "port": "5432"
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def main():
    print("Starting Kafka Consumer...")
    
    # Connect to Postgres
    try:
        conn = get_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        print("Connected to PostgreSQL.")
    except Exception as e:
        print(f"Failed to connect to DB: {e}")
        return

    # Connect to Kafka
    consumer = KafkaConsumer(
        *KAFKA_TOPICS, # Unpack the list
        bootstrap_servers=KAFKA_SERVERS,
        group_id="manufacturing_consumer_v1",
        auto_offset_reset='earliest',
        enable_auto_commit=False,
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )
    print(f"Listening on topics: {KAFKA_TOPICS}")

    try:
        for message in consumer:
            event = message.value
            
            # Extract envelope fields
            event_id = event["event_id"]
            event_type = event["event_type"]
            sim_timestamp = event["timestamp"]
            payload = event["payload"]

            # Idempotent Insert (ON CONFLICT DO NOTHING)
            insert_query = """
                INSERT INTO bronze.manufacturing_events 
                (event_id, event_type, sim_timestamp, payload)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (event_id) DO NOTHING;
            """
            
            try:
                cursor.execute(insert_query, (
                    event_id, 
                    event_type, 
                    sim_timestamp, 
                    Json(payload)
                ))
                
                # Commit the offset to Kafka ONLY after the DB write succeeds
                consumer.commit()
                
            except Exception as db_err:
                print(f"DB Error for event {event_id}: {db_err}")
                # In a production system, you would push to a Dead Letter Queue here
                
    except KeyboardInterrupt:
        print("\nStopping consumer...")
    finally:
        consumer.close()
        cursor.close()
        conn.close()
        print("Connections closed.")

if __name__ == "__main__":
    main()