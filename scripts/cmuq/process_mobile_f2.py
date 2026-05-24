"""
CMUQ Floor 2 – Mobile Processing
Converts raw Firebase JSON export of a free-walk session →
data/cmuq/mobile/floor2.csv

Mobile collection differs from stationary:
  - No fixed reference points → rpNumber = -1, x = -1, y = -1
  - The device walks continuously for ~1 hour per floor
  - Each scan is identified by (phoneName, scanNumber, timeStamp)
  - All other columns use the same schema as the stationary CSVs

Output columns (same 24-column schema as stationary):
    entry_id, buildingNumber, entryDate, floorNumber, rpNumber, x, y,
    batteryPower, deviceHeight, hoFlag, infrastructureType, phoneName,
    scanDate, scanNumber, servingCellId, timeStamp,
    transmitter_asu, transmitter_id, transmitter_level, transmitter_rsrq,
    transmitter_rss, transmitter_rssi, transmitter_snr, transmitter_type

Usage:
    python scripts/cmuq/process_mobile_f2.py
"""

import json, csv, os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

# TODO: update raw filename when floor-2 mobile export is available
JSON_PATH = os.path.join(ROOT, "raw", "fingerprints_floor2_mobile.json")
OUT_CSV   = os.path.join(ROOT, "data", "cmuq", "mobile", "floor2.csv")
FLOOR     = 2

FIELDNAMES = [
    "entry_id", "buildingNumber", "entryDate", "floorNumber", "rpNumber",
    "x", "y",
    "batteryPower", "deviceHeight", "hoFlag", "infrastructureType",
    "phoneName", "scanDate", "scanNumber", "servingCellId", "timeStamp",
    "transmitter_asu", "transmitter_id", "transmitter_level", "transmitter_rsrq",
    "transmitter_rss", "transmitter_rssi", "transmitter_snr", "transmitter_type",
]

SENTINEL = 2_147_483_647  # Java Integer.MAX_VALUE used as "no value" in raw export


def main():
    if not os.path.exists(JSON_PATH):
        print(f"ERROR: {JSON_PATH} not found.")
        print(f"       Place the floor-{FLOOR} mobile Firebase export in raw/ and update JSON_PATH.")
        return

    print(f"Loading {JSON_PATH} …")
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    # Floor-2 stationary uses a flat dict; mobile likely follows the same format.
    # If there is a top-level wrapper key, unwrap it:
    # data = data.get("Fingerprints", data)

    rows = []
    for entry_id, entry in data.items():
        scan  = entry.get("scan", entry)
        phone = scan.get("phoneName", "").strip()
        for tx in scan.get("transmitters", []):
            rssi = int(tx.get("rssi", SENTINEL))
            snr  = int(tx.get("snr",  SENTINEL))
            rows.append({
                "entry_id":           entry_id,
                "buildingNumber":     entry.get("buildingNumber", 5),
                "entryDate":          entry.get("entryDate", ""),
                "floorNumber":        entry.get("floorNumber", FLOOR),
                "rpNumber":           -1,   # no fixed RP in mobile mode
                "x":                  -1,
                "y":                  -1,
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
