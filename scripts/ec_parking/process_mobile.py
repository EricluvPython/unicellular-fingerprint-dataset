"""
EC Parking Mobile Fingerprints Processing
Converts raw/ec_parking.json → data/ec_parking/mobile/floor{0,1}.csv

Key processing steps:
  - Filter collectionMode == 'mobile' (equivalently rpNumber == 0 in this dataset)
  - No "side" labelling (parking lot, continuous single-loop walk)
  - Mask INT_MAX sentinel values (2,147,483,647) → empty string (→ NaN in pandas)
  - Reconstruct monotonic scanNumber:
      The Android app resets its internal counter every ~1000 scans.
      We discard the raw counter and assign a 1-based sequential index per
      (phone, floor) based on time-sorted order.
  - Expand transmitterInfoList into one CSV row per transmitter observation
  - x, y remain -1 (no fixed reference points)

Output schema (24 columns – same as CMUQ stationary, no 'side' column):
    entry_id, buildingNumber, entryDate, floorNumber, rpNumber, x, y,
    batteryPower, deviceHeight, hoFlag, infrastructureType,
    phoneName, scanDate, scanNumber, servingCellId, timeStamp,
    transmitter_asu, transmitter_id, transmitter_level, transmitter_rsrq,
    transmitter_rss, transmitter_rssi, transmitter_snr, transmitter_type

Usage:
    python scripts/ec_parking/process_mobile.py
"""

import json, csv, os
from collections import defaultdict

ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)

JSON_PATH = os.path.join(ROOT, "raw", "ec_parking.json")
OUT_DIR   = os.path.join(ROOT, "data", "ec_parking", "mobile")

FLOORS = [0, 1]

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


def process_floor(floor, all_entries):
    """
    Process all mobile entries for a given floor.

    Returns list of output rows (dicts), sorted by (phone, timeStamp).
    scanNumber is reconstructed as monotonic 1-based index per phone.
    """
    # Collect mobile entries for this floor, grouped by phone
    phone_groups = defaultdict(list)  # phone → list of (entry_id, entry)
    for entry_id, entry in all_entries.items():
        if entry.get("floorNumber") != floor:
            continue
        scan = entry.get("scan", {})
        if scan.get("collectionMode") != "mobile":
            continue
        phone = scan.get("phoneName", "?")
        phone_groups[phone].append((entry_id, entry))

    # Sort each phone's entries by timeStamp and assign monotonic scan numbers
    corrected_scan = {}  # entry_id → reconstructed scanNumber
    for phone, group in phone_groups.items():
        group.sort(key=lambda t: t[1].get("scan", {}).get("timeStamp", 0))
        for idx, (eid, _) in enumerate(group, start=1):
            corrected_scan[eid] = idx

    # Build output rows
    rows = []
    for phone in sorted(phone_groups.keys()):
        for entry_id, entry in phone_groups[phone]:
            scan = entry.get("scan", {})
            transmitters = scan.get("transmitterInfoList", [])

            base = {
                "entry_id":          entry_id,
                "buildingNumber":    entry.get("buildingNumber", ""),
                "entryDate":         entry.get("entryDate", ""),
                "floorNumber":       floor,
                "rpNumber":          -1,
                "x":                 -1,
                "y":                 -1,
                "batteryPower":      scan.get("batteryPower", ""),
                "deviceHeight":      scan.get("deviceHeight", ""),
                "hoFlag":            scan.get("hoFlag", ""),
                "infrastructureType": scan.get("infrastructureType", ""),
                "phoneName":         phone,
                "scanDate":          scan.get("scanDate", ""),
                "scanNumber":        corrected_scan[entry_id],
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

    return rows


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"Loading {JSON_PATH} …")
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  Total entries in file: {len(data):,}")

    for floor in FLOORS:
        print(f"\nProcessing mobile floor {floor} …")
        rows = process_floor(floor, data)

        out_path = os.path.join(OUT_DIR, f"floor{floor}.csv")
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)

        # Summary
        phones = sorted({r["phoneName"] for r in rows})
        for phone in phones:
            prows = [r for r in rows if r["phoneName"] == phone]
            scans = {r["scanNumber"] for r in prows}
            print(f"  {phone}: {len(prows):,} rows, scans 1–{max(scans)}")

        print(f"  → {out_path}")
        print(f"     {len(rows):,} rows total")

    print("\nDone.")


if __name__ == "__main__":
    main()
