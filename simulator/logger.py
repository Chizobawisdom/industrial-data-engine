import json
import uuid
import os
from datetime import datetime

import json
import uuid
import os
from datetime import datetime
from kafka import KafkaProducer

class EventLogger:
    def __init__(self, output_dir="outputs", use_kafka=False, kafka_topic="factory.events"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.file_path = os.path.join(self.output_dir, "manufacturing_events.jsonl")
        
        if not use_kafka:
            open(self.file_path, 'w').close()
            
        self.counts = {}
        self.use_kafka = use_kafka
        self.kafka_topic = kafka_topic
        
        if self.use_kafka:
            print(f"Connecting to Kafka...")
            # THIS IS WHERE THE BLOCK GOES
            self.producer = KafkaProducer(
                bootstrap_servers=['127.0.0.1:9092'],  # Port 9092 for the EXTERNAL listener
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            print("Kafka connected!")

    def _write(self, event_type: str, payload: dict, sim_time: float):
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": sim_time,
            "ingested_at": datetime.utcnow().isoformat() + "Z",
            "payload": payload
        }
        
        # 1. Write locally (optional, but keep for debugging)
        with open(self.file_path, 'a') as f:
            f.write(json.dumps(event) + "\n")
            
        # 2. Route to the correct Kafka topic
        if self.use_kafka:
            topic_map = {
                "production_event": "manufacturing.production",
                "quality_inspection": "manufacturing.quality",
                "rework_event": "manufacturing.rework",
                "scrap_event": "manufacturing.scrap",
                "downtime_event": "manufacturing.production" # Route downtime to production
            }
            target_topic = topic_map.get(event_type, "manufacturing.production")
            self.producer.send(target_topic, event)
            
        self.counts[event_type] = self.counts.get(event_type, 0) + 1

    # --- Specific Event Emitters ---

    def log_production_event(self, sim_time, serial_number, station, event_type, duration=None):
        payload = {
            "serial_number": serial_number,
            "station": station,
            "action": event_type, # "ENTRY" or "EXIT"
            "duration_minutes": duration
        }
        self._write("production_event", payload, sim_time)

    def log_downtime(self, sim_time, machine_id, duration, reason="Unplanned Breakdown"):
        payload = {
            "machine_id": machine_id,
            "duration_minutes": duration,
            "reason": reason
        }
        self._write("downtime_event", payload, sim_time)

    def log_quality_inspection(self, sim_time, serial_number, station, measurement, tolerance, result):
        payload = {
            "serial_number": serial_number,
            "station": station,
            "measurement": round(measurement, 4),
            "tolerance": tolerance,
            "result": result # "PASS" or "FAIL"
        }
        self._write("quality_inspection", payload, sim_time)

    def log_rework(self, sim_time, serial_number, station, attempt, defect_reason):
        payload = {
            "serial_number": serial_number,
            "station": station,
            "attempt_number": attempt,
            "defect_reason": defect_reason
        }
        self._write("rework_event", payload, sim_time)

    def log_scrap(self, sim_time, serial_number, station, reason, estimated_cost=15.50):
        payload = {
            "serial_number": serial_number,
            "station": station,
            "reason": reason,
            "cost_usd": estimated_cost
        }
        self._write("scrap_event", payload, sim_time)