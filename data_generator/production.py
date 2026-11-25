import json
import random
import uuid

from datetime import datetime, timezone


def generate_production_event():
    return {
        "event_id": str(uuid.uuid4()),
        "event_timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "line_id": random.randint(1, 3),
        "station_id": random.randint(1, 5),
        "product_id": random.choice(
            ["PSU-100", "PSU-200", "PSU-300"]
        ),
        "serial_number": str(uuid.uuid4()),
        "cycle_time_seconds": round(
            random.uniform(20, 60), 2
        ),
        "test_result": random.choices(
            ["PASS", "FAIL"],
            weights=[95, 5]
        )[0]
    }


if __name__ == "__main__":
    event = generate_production_event()
    print(json.dumps(event, indent=4))
