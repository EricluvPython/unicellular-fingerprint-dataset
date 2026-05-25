"""
CMUQ Floor 3 – Stationary Processing (Skeleton)
Converts raw Firebase JSON export → data/cmuq/stationary/floor3.csv

TODO: Update JSON_PATH and any schema differences once floor-3 data is exported.
      The default assumes the same flat-dict format as floor 2.

Output schema (same 24 columns as floor 1 & 2):
    entry_id, buildingNumber, entryDate, floorNumber, rpNumber, x, y,
    batteryPower, deviceHeight, hoFlag, infrastructureType, phoneName,
    scanDate, scanNumber, servingCellId, timeStamp,
    transmitter_asu, transmitter_id, transmitter_level, transmitter_rsrq,
    transmitter_rss, transmitter_rssi, transmitter_snr, transmitter_type

Usage:
    python scripts/cmuq/process_stationary_f3.py
"""

import json, csv, os
from collections import defaultdict

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

# TODO: update raw filename when floor-3 export is available
JSON_PATH  = os.path.join(ROOT, "raw", "fingerprints_floor3.json")
COORD_PATH = os.path.join(ROOT, "coordinates", "cmuq", "floor3.json")
OUT_CSV    = os.path.join(ROOT, "data", "cmuq", "stationary", "floor3.csv")

FIELDNAMES = [
    "entry_id", "buildingNumber", "entryDate", "floorNumber", "rpNumber",
    "x", "y",
    "batteryPower", "deviceHeight", "hoFlag", "infrastructureType",
    "phoneName", "scanDate", "scanNumber", "servingCellId", "timeStamp",
    "transmitter_asu", "transmitter_id", "transmitter_level", "transmitter_rsrq",
    "transmitter_rss", "transmitter_rssi", "transmitter_snr", "transmitter_type",
]

SENTINEL = 2_147_483_647  # Java Integer.MAX_VALUE used as "no value" in raw export

DUP_PHONE   = "25028RN03A"
DUP_PHONE_2 = "25028RN03A-2"


def load_coords(path):
    if not os.path.exists(path):
        print(f"WARNING: {path} not found – run assign_coordinates_f3.py first.")
        return {}
    return {int(k): v for k, v in json.load(open(path, encoding="utf-8")).items()}


def resolve_duplicate_phones(data):
    """
    For phone '25028RN03A', there are 2+ entries per (rpNumber, scanNumber).
    Identify which entry_ids belong to the second physical phone by comparing
    timestamps within each (rp, scanNumber) group.
    Returns a set of entry_ids that should be renamed to DUP_PHONE_2.
    """
    groups = defaultdict(list)
    for eid, entry in data.items():
        ph = entry.get("scan", {}).get("phoneName", "").strip()
        if ph != DUP_PHONE:
            continue
        rp = entry.get("rpNumber")
        sn = entry.get("scan", {}).get("scanNumber")
        ts = entry.get("scan", {}).get("timeStamp", 0)
        groups[(rp, sn)].append((eid, ts))

    rename_set = set()
    for (rp, sn), entries in groups.items():
        if len(entries) < 2:
            continue
        entries_sorted = sorted(entries, key=lambda x: x[1])
        for eid, _ in entries_sorted[1:]:
            rename_set.add(eid)

    print(f"Identified {len(rename_set)} entries to rename "
          f"'{DUP_PHONE}' → '{DUP_PHONE_2}'")
    return rename_set


def main():
    if not os.path.exists(JSON_PATH):
        print(f"ERROR: {JSON_PATH} not found.")
        print("       Place the floor-3 Firebase export in raw/ and update JSON_PATH.")
        return

    coords = load_coords(COORD_PATH)
    print(f"Loading {JSON_PATH} …")
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    # Floor 3 uses a flat dict (no Fingerprints wrapper), same format as floor 2.
    # Transmitter list key changed to 'transmitterInfoList' in the updated app version.

    rename_set = resolve_duplicate_phones(data)

    rows = []
    for entry_id, entry in data.items():
        scan = entry.get("scan", entry)
        rp   = int(entry.get("rpNumber", scan.get("rpNumber", -1)))
        xy   = coords.get(rp, [-1, -1])

        phone = scan.get("phoneName", "").strip()
        if entry_id in rename_set:
            phone = DUP_PHONE_2
        for tx in scan.get("transmitterInfoList", scan.get("transmitters", [])):
            rssi = int(tx.get("rssi", SENTINEL))
            snr  = int(tx.get("snr",  SENTINEL))
            rows.append({
                "entry_id":           entry_id,
                "buildingNumber":     entry.get("buildingNumber", 5),
                "entryDate":          entry.get("entryDate", ""),
                "floorNumber":        entry.get("floorNumber", 3),
                "rpNumber":           rp,
                "x":                  xy[0],
                "y":                  xy[1],
                "batteryPower":       scan.get("batteryPower", -1),
                "deviceHeight":       scan.get("deviceHeight", 1.2),
                "hoFlag":             scan.get("hoFlag", False),
                "infrastructureType": scan.get("infrastructureType", "Cellular Ooredoo"),
                "phoneName":          phone,
                "scanDate":           scan.get("scanDate", ""),
                "scanNumber":         scan.get("scanNumber", -1),
                "servingCellId":      scan.get("servingCellId", -1),
                "timeStamp":          scan.get("timeStamp", -1),
                "transmitter_asu":    tx.get("asu",    -1),
                "transmitter_id":     tx.get("id",     -1),
                "transmitter_level":  tx.get("level",  -1),
                "transmitter_rsrq":   tx.get("rsrq",   -1),
                "transmitter_rss":    tx.get("rss",    -1),
                "transmitter_rssi":   rssi if rssi != SENTINEL else "",
                "transmitter_snr":    snr  if snr  != SENTINEL else "",
                "transmitter_type":   tx.get("type",  ""),
            })

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows):,} rows → {OUT_CSV}")


if __name__ == "__main__":
    main()
