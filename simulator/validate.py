import json
import os
from collections import defaultdict

def validate_conservation(
    created_ids: set[str],
    packaged_ids: set[str],
    scrapped_ids: set[str],
    wip_ids: set[str]
) -> bool:

    duplicate_outcomes = packaged_ids & scrapped_ids

    accounted_ids = (
        packaged_ids | scrapped_ids | wip_ids
    )

    missing_ids = created_ids - accounted_ids
    unexpected_ids = accounted_ids - created_ids

    invalid_wip = wip_ids & (
        packaged_ids | scrapped_ids
    )

    print("\n--- Device Conservation ---")
    print(f"Created:   {len(created_ids)}")
    print(f"Packaged:  {len(packaged_ids)}")
    print(f"Scrapped:  {len(scrapped_ids)}")
    print(f"WIP:       {len(wip_ids)}")

    print(f"Duplicate outcomes: {len(duplicate_outcomes)}")
    print(f"Missing devices:    {len(missing_ids)}")
    print(f"Unexpected devices: {len(unexpected_ids)}")
    print(f"Invalid WIP:        {len(invalid_wip)}")

    valid = not any([
        duplicate_outcomes,
        missing_ids,
        unexpected_ids,
        invalid_wip
    ])

    print(f"Result: {'PASS' if valid else 'FAIL'}")
    
    if missing_ids:
        print(f"  Sample missing: {list(missing_ids)[:3]}")
    if unexpected_ids:
        print(f"  Sample unexpected: {list(unexpected_ids)[:3]}")
    if duplicate_outcomes:
        print(f"  Sample duplicate outcomes: {list(duplicate_outcomes)[:3]}")

    return valid


def validate_simulation(filepath="outputs/manufacturing_events.jsonl"):
    print(f"Validating {filepath}...")
    if not os.path.exists(filepath):
        print("File not found!")
        return

    created_items = set()
    packaged_items = set()
    scrapped_items = set()
    
    # Track station visits for WIP calculation and rework tracing
    station_visits = defaultdict(list)
    rework_events = defaultdict(int)

    with open(filepath, 'r') as f:
        for line in f:
            event = json.loads(line)
            payload = event["payload"]
            ev_type = event["event_type"]
            
            if ev_type == "production_event":
                item = payload["serial_number"]
                station = payload["station"]
                action = payload["action"]
                
                if station == "SOURCE" and action == "ENTRY":
                    created_items.add(item)
                elif action == "ENTRY":
                    station_visits[item].append(station)
                elif station == "PACKAGING" and action == "EXIT":
                    packaged_items.add(item)
                    
            elif ev_type == "scrap_event":
                scrapped_items.add(payload["serial_number"])
            
            elif ev_type == "rework_event":
                rework_events[payload["serial_number"]] += 1

    # WIP = Everything created, but not yet packaged or scrapped
    wip_items = created_items - packaged_items - scrapped_items

    # Run the strict set-algebra validation
    is_valid = validate_conservation(
        created_ids=created_items,
        packaged_ids=packaged_items,
        scrapped_ids=scrapped_items,
        wip_ids=wip_items
    )

    # --- Additional Checks ---
    print("\n--- Routing & Logic ---")
    
    # 1. Rework tracing
    items_visiting_elec_multiple_times = {
        item for item, visits in station_visits.items() 
        if visits.count("ELEC_TESTING") > 1
    }
    
    print(f"Unique items that went through REWORK: {len(rework_events)}")
    print(f"Unique items that visited ELEC_TESTING > 1 time: {len(items_visiting_elec_multiple_times)}")
    
    # Every item that looped MUST have a rework event, and vice versa
    if set(rework_events.keys()) == items_visiting_elec_multiple_times:
        print("[OK] Rework events perfectly align with looped items.")
    else:
        print("[FAIL] Rework events do not match items that looped back.")
        if set(rework_events.keys()) - items_visiting_elec_multiple_times:
            print("  - Some items had rework events but never looped.")
        if items_visiting_elec_multiple_times - set(rework_events.keys()):
            print("  - Some items looped but had no rework event.")

    # 2. Total Attempts vs Rework Events
    total_rework_attempts = sum(rework_events.values())
    # If an item loops twice, it must have 2 rework events
    expected_total_attempts = sum(
        visits.count("ELEC_TESTING") - 1 
        for visits in station_visits.values() 
        if visits.count("ELEC_TESTING") > 1
    )
    
    print(f"Total rework attempts logged: {total_rework_attempts}")
    print(f"Expected rework attempts based on loops: {expected_total_attempts}")
    if total_rework_attempts == expected_total_attempts:
        print("[OK] Rework attempt counts are perfectly accurate.")
    else:
        print("[FAIL] Rework attempt counts are inconsistent.")

if __name__ == "__main__":
    validate_simulation()