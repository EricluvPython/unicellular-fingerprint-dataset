"""
Processes fingerprints_floor2.json → cmuq_stationary_7phone_f2.csv

Key differences from Floor 1:
  - JSON is a flat dict (no "Fingerprints" wrapper key).
  - x, y in the raw data are already set to 1,1 (placeholder); overridden from
    coordinates_f2.json.
  - Phone '25028RN03A' was collected by TWO physical phones with the same device
    ID.  For every (rpNumber, scanNumber) pair there are exactly 2 entries.
    The one with the earlier timeStamp keeps the name '25028RN03A'; the other
    becomes '25028RN03A-2'.

Output columns (same schema as cmuq_stationary_7phone_f1.csv):
    entry_id, buildingNumber, entryDate, floorNumber, rpNumber, x, y,
    batteryPower, deviceHeight, hoFlag, infrastructureType, phoneName,
    scanDate, scanNumber, servingCellId, timeStamp,
    transmitter_asu, transmitter_id, transmitter_level, transmitter_rsrq,
    transmitter_rss, transmitter_rssi, transmitter_snr, transmitter_type

Usage:
    python process_cmuq_f2_stationary.py
"""

import json, csv, os
from collections import defaultdict

ROOT       = os.path.dirname(os.path.abspath(__file__))
JSON_PATH  = os.path.join(ROOT, "raw", "fingerprints_floor2.json")
COORD_PATH = os.path.join(ROOT, "coordinates", "coordinates_f2.json")
OUT_CSV    = os.path.join(ROOT, "data", "cmuq_stationary_7phone_f2.csv")

FIELDNAMES = [
    "entry_id", "buildingNumber", "entryDate", "floorNumber", "rpNumber",
    "x", "y",
    "batteryPower", "deviceHeight", "hoFlag", "infrastructureType",
    "phoneName", "scanDate", "scanNumber", "servingCellId", "timeStamp",
    "transmitter_asu", "transmitter_id", "transmitter_level", "transmitter_rsrq",
    "transmitter_rss", "transmitter_rssi", "transmitter_snr", "transmitter_type",
]

DUP_PHONE   = "25028RN03A"
DUP_PHONE_2 = "25028RN03A-2"


# ── helpers ──────────────────────────────────────────────────────────────────
def load_coords(path):
    if not os.path.exists(path):
        print(f"WARNING: {path} not found. x, y will be -1.")
        print("         Run assign_coordinates_f2.py first.")
        return {}
    with open(path) as f:
        raw = json.load(f)
    coords = {int(k): v for k, v in raw.items()}
    print(f"Loaded coordinates for {len(coords)} RPs.")
    return coords


def resolve_duplicate_phones(data):
    """
    For phone '25028RN03A', there are 2 entries per (rpNumber, scanNumber).
    Identify which entry_ids belong to the second physical phone by comparing
    timestamps within each (rp, scanNumber) group.
    Returns a set of entry_ids that should be renamed to DUP_PHONE_2.
    """
    # group: (rp, scanNumber) → list of (entry_id, timeStamp)
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
        # sort by timestamp; the later one → DUP_PHONE_2
        entries_sorted = sorted(entries, key=lambda x: x[1])
        for eid, _ in entries_sorted[1:]:   # everything after the first
            rename_set.add(eid)

    print(f"Identified {len(rename_set)} entries to rename "
          f"'{DUP_PHONE}' → '{DUP_PHONE_2}'")
    return rename_set


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    coords   = load_coords(COORD_PATH)

    print(f"Loading {JSON_PATH} …")
    with open(JSON_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    # floor 2 JSON is a flat dict of entries (no "Fingerprints" wrapper)
    entries = raw
    print(f"Total entries: {len(entries):,}")

    rename_set = resolve_duplicate_phones(entries)

    rows_written = 0
    missing_rps  = set()

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
        writer.writeheader()

        for i, (eid, entry) in enumerate(entries.items(), 1):
            if i % 50000 == 0:
                print(f"  {i:,}/{len(entries):,} …")

            rp_num = entry.get("rpNumber", "")
            scan   = entry.get("scan", {})

            # resolve phone name
            phone = scan.get("phoneName", "").strip()
            if eid in rename_set:
                phone = DUP_PHONE_2

            # pixel coordinates
            if rp_num in coords:
                px, py = coords[rp_num]
            else:
                px, py = -1, -1
                if rp_num != "":
                    missing_rps.add(rp_num)

            base = {
                "entry_id":           eid,
                "buildingNumber":     entry.get("buildingNumber", ""),
                "entryDate":          entry.get("entryDate", ""),
                "floorNumber":        entry.get("floorNumber", ""),
                "rpNumber":           rp_num,
                "x":                  px,
                "y":                  py,
                "batteryPower":       scan.get("batteryPower", ""),
                "deviceHeight":       scan.get("deviceHeight", ""),
                "hoFlag":             scan.get("hoFlag", ""),
                "infrastructureType": scan.get("infrastructureType", ""),
                "phoneName":          phone,
                "scanDate":           scan.get("scanDate", ""),
                "scanNumber":         scan.get("scanNumber", ""),
                "servingCellId":      scan.get("servingCellId", ""),
                "timeStamp":          scan.get("timeStamp", ""),
            }

            transmitters = scan.get("transmitterInfoList", [])
            if transmitters:
                for t in transmitters:
                    row = dict(base, **{
                        "transmitter_asu":   t.get("asu",   ""),
                        "transmitter_id":    t.get("id",    ""),
                        "transmitter_level": t.get("level", ""),
                        "transmitter_rsrq":  t.get("rsrq",  ""),
                        "transmitter_rss":   t.get("rss",   ""),
                        "transmitter_rssi":  t.get("rssi",  ""),
                        "transmitter_snr":   t.get("snr",   ""),
                        "transmitter_type":  t.get("type",  ""),
                    })
                    writer.writerow(row)
                    rows_written += 1
            else:
                row = dict(base, **{k: "" for k in FIELDNAMES if k.startswith("transmitter_")})
                writer.writerow(row)
                rows_written += 1

    print(f"\nDone. {rows_written:,} rows written → {OUT_CSV}")
    if missing_rps:
        print(f"WARNING: {len(missing_rps)} RP(s) had no coordinate: {sorted(missing_rps)}")
    else:
        print("All RPs have pixel coordinates.")


if __name__ == "__main__":
    main()
