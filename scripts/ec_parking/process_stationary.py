"""
EC Parking Stationary Fingerprints Processing
Converts raw/ec_parking.json → data/ec_parking/stationary/floor{0,1}.csv

Key processing steps:
  - Filter collectionMode == 'stationary'
  - Floor 0 (underground): RPs 1-20, no floor-plan coordinates available
  - Floor 1 (ground):      RPs 1-34, coordinates from coordinates/ec_parking/floor1.json
  - Keep LAST 300 entries per (floor, RP, phone) when a RP has > 300 scans
    (mistake runs are always at the beginning of a collection session)
  - Mask INT_MAX sentinel values (2,147,483,647) → empty string (→ NaN in pandas)
  - Expand transmitterInfoList into one CSV row per transmitter observation

Output schema (24 columns – same as CMUQ stationary):
    entry_id, buildingNumber, entryDate, floorNumber, rpNumber, x, y,
    batteryPower, deviceHeight, hoFlag, infrastructureType,
    phoneName, scanDate, scanNumber, servingCellId, timeStamp,
    transmitter_asu, transmitter_id, transmitter_level, transmitter_rsrq,
    transmitter_rss, transmitter_rssi, transmitter_snr, transmitter_type

Usage:
    python scripts/ec_parking/process_stationary.py
"""

import json, csv, os
from collections import defaultdict

ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)

JSON_PATH = os.path.join(ROOT, "raw", "ec_parking.json")
COORD_DIR = os.path.join(ROOT, "coordinates", "ec_parking")
OUT_DIR   = os.path.join(ROOT, "data", "ec_parking", "stationary")

FLOORS    = [0, 1]       # floor numbers present in the dataset
COORD_FLOORS = [1]       # only floor 1 has a floor plan

FIELDNAMES = [
    "entry_id", "buildingNumber", "entryDate", "floorNumber", "rpNumber",
    "x", "y",
    "batteryPower", "deviceHeight", "hoFlag", "infrastructureType",
    "phoneName", "scanDate", "scanNumber", "servingCellId", "timeStamp",
    "transmitter_asu", "transmitter_id", "transmitter_level", "transmitter_rsrq",
    "transmitter_rss", "transmitter_rssi", "transmitter_snr", "transmitter_type",
]

SENTINEL = 2_147_483_647


def mask(v):
    """Replace INT_MAX sentinel with empty string."""
    return "" if v == SENTINEL else v


def load_coords(floor):
    if floor not in COORD_FLOORS:
        return {}
    path = os.path.join(COORD_DIR, f"floor{floor}.json")
    if not os.path.exists(path):
        print(f"  WARNING: {path} not found. x, y will be -1 for floor {floor}.")
        print(f"           Run assign_coordinates_floor1.py first.")
        return {}
    with open(path) as f:
        raw = json.load(f)
    coords = {int(k): list(v) for k, v in raw.items()}
    print(f"  Loaded {len(coords)} RP coordinates from {path}")
    return coords


def process_floor(floor, all_entries, coords):
    """
    Process all stationary entries for a given floor.

    Grouping by (rpNumber, phoneName), sort by timeStamp, keep last 300.
    Returns a list of output rows (dicts).
    """
    # Group entries by (rp, phone)
    rp_phone_groups = defaultdict(list)  # (rp, phone) → list of (entry_id, entry)
    for entry_id, entry in all_entries.items():
        if entry.get("floorNumber") != floor:
            continue
        scan = entry.get("scan", {})
        if scan.get("collectionMode") != "stationary":
            continue
        rp = entry.get("rpNumber", -1)
        if rp <= 0:  # skip mobile (rpNumber=0)
            continue
        phone = scan.get("phoneName", "?")
        rp_phone_groups[(rp, phone)].append((entry_id, entry))

    total_dropped = 0
    rows = []

    for (rp, phone) in sorted(rp_phone_groups.keys()):
        group = rp_phone_groups[(rp, phone)]
        group = rp_phone_groups[(rp, phone)]
        # Sort by timeStamp to keep the last 300
        group.sort(key=lambda t: t[1].get("scan", {}).get("timeStamp", 0))
        if len(group) > 300:
            dropped = len(group) - 300
            total_dropped += dropped
            group = group[-300:]  # keep last 300

        for entry_id, entry in group:
            scan = entry.get("scan", {})
            px, py = coords.get(rp, (-1, -1))
            transmitters = scan.get("transmitterInfoList", [])

            base = {
                "entry_id":          entry_id,
                "buildingNumber":    entry.get("buildingNumber", ""),
                "entryDate":         entry.get("entryDate", ""),
                "floorNumber":       floor,
                "rpNumber":          rp,
                "x":                 px,
                "y":                 py,
                "batteryPower":      scan.get("batteryPower", ""),
                "deviceHeight":      scan.get("deviceHeight", ""),
                "hoFlag":            scan.get("hoFlag", ""),
                "infrastructureType": scan.get("infrastructureType", ""),
                "phoneName":         phone,
                "scanDate":          scan.get("scanDate", ""),
                "scanNumber":        scan.get("scanNumber", ""),
                "servingCellId":     scan.get("servingCellId", ""),
                "timeStamp":         scan.get("timeStamp", ""),
            }

            if transmitters:
                for t in transmitters:
                    row = dict(base)
                    row.update({
                        "transmitter_asu":   mask(t.get("asu",   "")),
                        "transmitter_id":    mask(t.get("id",    "")),
                        "transmitter_level": t.get("level",  ""),
                        "transmitter_rsrq":  mask(t.get("rsrq",  "")),
                        "transmitter_rss":   mask(t.get("rss",   "")),
                        "transmitter_rssi":  mask(t.get("rssi",  "")),
                        "transmitter_snr":   mask(t.get("snr",   "")),
                        "transmitter_type":  t.get("type",   ""),
                    })
                    rows.append(row)
            else:
                row = dict(base)
                row.update({k: "" for k in [
                    "transmitter_asu","transmitter_id","transmitter_level",
                    "transmitter_rsrq","transmitter_rss","transmitter_rssi",
                    "transmitter_snr","transmitter_type",
                ]})
                rows.append(row)

    if total_dropped:
        print(f"  Floor {floor}: dropped {total_dropped:,} over-300 entries "
              f"(kept last 300 per RP/phone)")
    return rows


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"Loading {JSON_PATH} …")
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  Total entries in file: {len(data):,}")

    for floor in FLOORS:
        print(f"\nProcessing floor {floor} …")
        coords = load_coords(floor)

        rows = process_floor(floor, data, coords)

        out_path = os.path.join(OUT_DIR, f"floor{floor}.csv")
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)

        print(f"  → {out_path}")
        print(f"     {len(rows):,} rows written")

    print("\nDone.")


if __name__ == "__main__":
    main()
