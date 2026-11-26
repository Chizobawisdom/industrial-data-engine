# industrial-data-engine

This project simulates an electronics production line and uses its events to demonstrate near-real-time data engineering for production and quality monitoring.

## How it works

**Data flow** · Python, Factorysimpy and SimPy simulator → Kafka Topics (4) → Python Consumer → PostgreSQL Bronze → dbt Silver and Gold → Grafana. Docker Compose runs local services, SQL defines the data models, and Git tracks changes.

**Production flow** · Device creation → PCB assembly → mechanical assembly → electrical testing → final inspection → packaging. Devices that fail electrical testing go through rework and are tested again. Devices that fail final inspection are scrapped. The simulator tracks devices, processing times, buffers, machine breakdowns, and work in progress (WIP).

| Part | Role |
| --- | --- |
| Kafka | Streams `manufacturing.production`, `manufacturing.quality`, `manufacturing.rework`, and `manufacturing.scrap`. |
| Bronze | `bronze.manufacturing_events` stores raw events and keeps their original payloads for reconciliation and troubleshooting. |
| Silver | dbt extracts and types event fields in `station_visits`, `quality_inspections`, `rework_events`, and `scrap_events`. |
| Gold | `manufacturing_kpis` is a draft dbt model for device counts, WIP, throughput, yields, scrap and rework rates, average end-to-end cycle time, and average and 95th-percentile station cycle times. |
| Grafana | The prototype shows station activity and electrical test results. |


## Local setup (untested)

Install Python, Docker with Compose, and Git. Run these commands from the repository root. Check the dependency file, Compose services, simulator commands, output path, and database settings against your checkout.

```bash
python -m venv venv
```

Activate the environment with `.\venv\Scripts\Activate.ps1` in Windows PowerShell or `source venv/bin/activate` on macOS or Linux.
Create a .env file in the project root with your Postgres password:
POSTGRES_PASSWORD=your_secure_password

```bash
pip install -r requirements.txt
docker compose up -d
docker compose ps
```
Create Kafka Topics
```bash
docker exec manufacturing_kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic manufacturing.production --partitions 3 --replication-factor 1
docker exec manufacturing_kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic manufacturing.quality --partitions 3 --replication-factor 1
docker exec manufacturing_kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic manufacturing.rework --partitions 3 --replication-factor 1
docker exec manufacturing_kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic manufacturing.scrap --partitions 3 --replication-factor 1
```

```bash
python -m ingestion.consumer
.\orchestrate.ps1
python -m simulator.simulation

```

### About the Data
Each event follows a standard contract:
```bash
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "quality_inspection",
  "timestamp": 142.5,
  "ingested_at": "2024-01-15T10:30:00Z",
  "payload": {
    "serial_number": "item_SOURCE_42",
    "station": "ELEC_TESTING",
    "measurement": 5.0,
    "tolerance": 5.2,
    "result": "PASS"
}

```

**Wisdom Favour Chizoba** · [Portfolio](https://chizobawisdom.github.io/Portfolio/) · [GitHub](https://github.com/chizobawisdom)
