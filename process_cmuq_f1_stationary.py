"""
Processes cmuq_stationary_7phone_f1_raw.json into a flat CSV.

Output columns (same schema as fingerprints_data_new.csv):
    entry_id, buildingNumber, entryDate, floorNumber, rpNumber, x, y,
    batteryPower, deviceHeight, hoFlag, infrastructureType, phoneName,
    scanDate, scanNumber, servingCellId, timeStamp,
    transmitter_asu, transmitter_id, transmitter_level, transmitter_rsrq,
    transmitter_rss, transmitter_rssi, transmitter_snr, transmitter_type

x, y are taken from coordinates_f1.json if it exists; otherwise left as -1.
Run assign_coordinates_f1.py first to create that file.

Usage:
    python process_cmuq_f1_stationary.py
"""

import json
import csv
import os

# ── paths ──────────────────────────────────────────────────────────────────
ROOT        = os.path.dirname(os.path.abspath(__file__))
JSON_PATH   = os.path.join(ROOT, "raw", "cmuq_stationary_7phone_f1_raw.json")
COORD_PATH  = os.path.join(ROOT, "coordinates", "coordinates_f1.json")
OUTPUT_CSV  = os.path.join(ROOT, "data", "cmuq_stationary_7phone_f1.csv")

FIELDNAMES = [
    "entry_id", "buildingNumber", "entryDate", "floorNumber", "rpNumber",
    "x", "y",
    "batteryPower", "deviceHeight", "hoFlag", "infrastructureType",
    "phoneName", "scanDate", "scanNumber", "servingCellId", "timeStamp",
    "transmitter_asu", "transmitter_id", "transmitter_level", "transmitter_rsrq",
    "transmitter_rss", "transmitter_rssi", "transmitter_snr", "transmitter_type",
]

# ── load coordinate mapping ────────────────────────────────────────────────
def load_coords(coord_path):
    if not os.path.exists(coord_path):
        print(f"WARNING: {coord_path} not found. x, y will be set to -1.")
        print("         Run assign_coordinates_f1.py first to map RP locations.")
        return {}
    with open(coord_path, "r") as f:
        raw = json.load(f)
    coords = {int(k): v for k, v in raw.items()}
    print(f"Loaded coordinates for {len(coords)} RPs from {coord_path}")
    return coords

# ── main ───────────────────────────────────────────────────────────────────
def main():
    # 1. load coordinate mapping
    coords = load_coords(COORD_PATH)

    # 2. load JSON
    print(f"Loading {JSON_PATH} …")
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        top = json.load(f)

    # data lives under the "Fingerprints" key
    entries = top.get("Fingerprints", top)
    total_entries = len(entries)
    print(f"Total scan entries: {total_entries:,}")

    # 3. process
    rows_written = 0
    missing_rps  = set()

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
        writer.writeheader()

        for i, (entry_id, entry) in enumerate(entries.items(), 1):
            if i % 50000 == 0:
                print(f"  Processing entry {i:,}/{total_entries:,} …")

            rp_num   = entry.get("rpNumber", "")
            floor_num = entry.get("floorNumber", "")

            # look up pixel coordinates
            if rp_num in coords:
                px, py = coords[rp_num]
            else:
                px, py = -1, -1
                if rp_num != "":
                    missing_rps.add(rp_num)

            scan = entry.get("scan", {})
            transmitters = scan.get("transmitterInfoList", [])

            base = {
                "entry_id":          entry_id,
                "buildingNumber":    entry.get("buildingNumber", ""),
                "entryDate":         entry.get("entryDate", ""),
                "floorNumber":       floor_num,
                "rpNumber":          rp_num,
                "x":                 px,
                "y":                 py,
                "batteryPower":      scan.get("batteryPower", ""),
                "deviceHeight":      scan.get("deviceHeight", ""),
                "hoFlag":            scan.get("hoFlag", ""),
                "infrastructureType": scan.get("infrastructureType", ""),
                "phoneName":         scan.get("phoneName", ""),
                "scanDate":          scan.get("scanDate", ""),
                "scanNumber":        scan.get("scanNumber", ""),
                "servingCellId":     scan.get("servingCellId", ""),
                "timeStamp":         scan.get("timeStamp", ""),
            }

            if transmitters:
                for t in transmitters:
                    row = dict(base)
                    row.update({
                        "transmitter_asu":   t.get("asu", ""),
                        "transmitter_id":    t.get("id", ""),
                        "transmitter_level": t.get("level", ""),
                        "transmitter_rsrq":  t.get("rsrq", ""),
                        "transmitter_rss":   t.get("rss", ""),
                        "transmitter_rssi":  t.get("rssi", ""),
                        "transmitter_snr":   t.get("snr", ""),
                        "transmitter_type":  t.get("type", ""),
                    })
                    writer.writerow(row)
                    rows_written += 1
            else:
                # no transmitters – write base row with empty transmitter fields
                row = dict(base)
                row.update({
                    "transmitter_asu":   "",
                    "transmitter_id":    "",
                    "transmitter_level": "",
                    "transmitter_rsrq":  "",
                    "transmitter_rss":   "",
                    "transmitter_rssi":  "",
                    "transmitter_snr":   "",
                    "transmitter_type":  "",
                })
                writer.writerow(row)
                rows_written += 1

    print(f"\nDone. {rows_written:,} rows written to {OUTPUT_CSV}")

    if missing_rps:
        print(f"WARNING: {len(missing_rps)} RP(s) had no coordinate mapping "
              f"(used -1, -1): {sorted(missing_rps)}")
    else:
        print("All RPs have pixel coordinates assigned.")

if __name__ == "__main__":
    main()
