"""
CMUQ Mobile Fingerprints Processing
Converts raw/mobile_fingerprints.json → data/cmuq/mobile/floor{1,2,3}.csv

Key processing steps:
  - Floor 1: drop entries collected before 10:02 local (07:02 UTC) – mistake run
  - All floors: label each entry as side='top' or side='bottom'
      Strategy: per (floor, phone), sort by timeStamp, find the single largest
      time gap – entries before gap = 'top', entries after = 'bottom'
  - x, y remain -1 (mobile collection, no fixed reference points)
  - No duplicate-phone resolution needed (25028RN03A-2 already split in source)

Output schema (25 columns = stationary 24 + 'side'):
    entry_id, buildingNumber, entryDate, floorNumber, rpNumber, x, y, side,
    batteryPower, deviceHeight, hoFlag, infrastructureType,
    phoneName, scanDate, scanNumber, servingCellId, timeStamp,
    transmitter_asu, transmitter_id, transmitter_level, transmitter_rsrq,
    transmitter_rss, transmitter_rssi, transmitter_snr, transmitter_type

Usage:
    python scripts/cmuq/process_mobile.py
"""

import json, csv, os, datetime
from collections import defaultdict

ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)

JSON_PATH = os.path.join(ROOT, "raw", "mobile_fingerprints.json")
OUT_DIR   = os.path.join(ROOT, "data", "cmuq", "mobile")

FIELDNAMES = [
    "entry_id", "buildingNumber", "entryDate", "floorNumber", "rpNumber",
    "x", "y", "side",
    "batteryPower", "deviceHeight", "hoFlag", "infrastructureType",
    "phoneName", "scanDate", "scanNumber", "servingCellId", "timeStamp",
    "transmitter_asu", "transmitter_id", "transmitter_level", "transmitter_rsrq",
    "transmitter_rss", "transmitter_rssi", "transmitter_snr", "transmitter_type",
]

SENTINEL = 2_147_483_647  # Java Integer.MAX_VALUE used as "no value"

# Floor 1 mistake cutoff: everything before 10:02 local (UTC+3) on collection day
# = 07:02:00 UTC on 2026-05-25
F1_CUTOFF_UTC_MS = int(
    datetime.datetime(2026, 5, 25, 7, 2, 0, tzinfo=datetime.timezone.utc)
    .timestamp() * 1000
)


def assign_sides(entries_for_phone):
    """
    Given a list of entry dicts for a single (floor, phone), sorted by timeStamp,
    find the single largest time gap and label entries before the gap 'top',
    entries after 'bottom'.
    Returns a list of (entry_id, side) tuples in original order.
    """
    if len(entries_for_phone) <= 1:
        return [(e["_eid"], "top") for e in entries_for_phone]

    ts_list = [e["scan"]["timeStamp"] for e in entries_for_phone]
    gaps = [ts_list[i + 1] - ts_list[i] for i in range(len(ts_list) - 1)]
    split_idx = gaps.index(max(gaps)) + 1  # first index of 'bottom' entries

    result = []
    for i, e in enumerate(entries_for_phone):
        result.append((e["_eid"], "top" if i < split_idx else "bottom"))
    return result


def process_floor(floor_num, all_data):
    """Filter, assign sides, expand transmitters, return list of row dicts."""
    # Filter by floor
    entries = {eid: e for eid, e in all_data.items()
               if e.get("floorNumber") == floor_num}

    # Floor 1: drop mistake run (before 10:02 local)
    if floor_num == 1:
        before = sum(
            1 for e in entries.values()
            if e["scan"]["timeStamp"] < F1_CUTOFF_UTC_MS
        )
        entries = {eid: e for eid, e in entries.items()
                   if e["scan"]["timeStamp"] >= F1_CUTOFF_UTC_MS}
        print(f"  Floor 1: dropped {before} entries before 10:02 local")

    # Group by phone name for side assignment
    phone_groups = defaultdict(list)
    for eid, e in entries.items():
        e["_eid"] = eid  # attach id for retrieval
        phone_groups[e["scan"]["phoneName"]].append(e)

    # Sort each phone group by timeStamp, assign sides
    side_map = {}  # entry_id → 'top'/'bottom'
    for phone, group in phone_groups.items():
        group.sort(key=lambda e: e["scan"]["timeStamp"])
        for eid, side in assign_sides(group):
            side_map[eid] = side

    # Count per side for reporting
    top_count = sum(1 for s in side_map.values() if s == "top")
    bot_count = sum(1 for s in side_map.values() if s == "bottom")
    print(f"  Floor {floor_num}: {len(entries)} entries → "
          f"top={top_count}, bottom={bot_count}")

    # Expand transmitterInfoList into one row per transmitter
    rows = []
    for eid, entry in entries.items():
        scan = entry.get("scan", entry)
        tx_list = scan.get("transmitterInfoList", scan.get("transmitters", []))
        side = side_map.get(eid, "top")
        for tx in tx_list:
            rssi = int(tx.get("rssi", SENTINEL))
            snr  = int(tx.get("snr",  SENTINEL))
            rows.append({
                "entry_id":           eid,
                "buildingNumber":     entry.get("buildingNumber", 5),
                "entryDate":          entry.get("entryDate", ""),
                "floorNumber":        entry.get("floorNumber", floor_num),
                "rpNumber":           int(entry.get("rpNumber", 0)),
                "x":                  int(entry.get("x", -1)),
                "y":                  int(entry.get("y", -1)),
                "side":               side,
                "batteryPower":       scan.get("batteryPower", -1),
                "deviceHeight":       scan.get("deviceHeight", 1.2),
                "hoFlag":             scan.get("hoFlag", False),
                "infrastructureType": scan.get("infrastructureType", "Cellular Ooredoo"),
                "phoneName":          scan.get("phoneName", "").strip(),
                "scanDate":           scan.get("scanDate", ""),
                "scanNumber":         scan.get("scanNumber", -1),
                "servingCellId":      scan.get("servingCellId", -1),
                "timeStamp":          scan.get("timeStamp", -1),
                "transmitter_asu":    tx.get("asu",   SENTINEL),
                "transmitter_id":     tx.get("id",    -1),
                "transmitter_level":  tx.get("level", -1),
                "transmitter_rsrq":   tx.get("rsrq",  SENTINEL),
                "transmitter_rss":    tx.get("rss",   SENTINEL),
                "transmitter_rssi":   rssi,
                "transmitter_snr":    snr,
                "transmitter_type":   tx.get("type",  ""),
            })

    return rows


def write_csv(rows, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Written: {out_path}  ({len(rows):,} rows)")


def main():
    if not os.path.exists(JSON_PATH):
        print(f"ERROR: {JSON_PATH} not found.")
        return

    print(f"Loading {JSON_PATH} …")
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    print(f"Total entries: {len(data):,}")

    for fl in [1, 2, 3]:
        print(f"\nProcessing floor {fl} …")
        rows = process_floor(fl, data)
        out_path = os.path.join(OUT_DIR, f"floor{fl}.csv")
        write_csv(rows, out_path)

    print("\nDone.")


if __name__ == "__main__":
    main()
