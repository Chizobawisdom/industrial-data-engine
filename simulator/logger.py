import json
import uuid
import os
from datetime import datetime

class EventLogger:
    def __init__(self, output_dir="outputs"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.file_path = os.path.join(self.output_dir, "manufacturing_events.jsonl")
        # Clear the file at the start of a run
        open(self.file_path, 'w').close()
        
        # Counters for validation later
        self.counts = {}

    def _write(self, event_type: str, payload: dict, sim_time: float):
        # Standard Event Envelope
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": sim_time,
            "ingested_at": datetime.utcnow().isoformat() + "Z", # Simulates when the DB would receive it
            "payload": payload
        }
        
        # Write to JSONL
        with open(self.file_path, 'a') as f:
            f.write(json.dumps(event) + "\n")
            
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