# UniCellular Fingerprint Dataset

> **Cellular radio-frequency fingerprint dataset** collected across multiple indoor environments in Qatar.
> Each site is covered in two modes – **stationary** (fixed reference points, multiple phones, repeated scans) and **mobile** (continuous free-walk sessions, no fixed reference points).

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Git LFS](https://img.shields.io/badge/Git%20LFS-tracked-blue)](https://git-lfs.github.com/)

---

## Table of Contents

1. [Sites and Status](#sites-and-status)
2. [Directory Structure](#directory-structure)
3. [Data Schema](#data-schema)
4. [Collection Protocol](#collection-protocol)
5. [Processing Pipeline](#processing-pipeline)
6. [Interactive Dashboard](#interactive-dashboard)
7. [Accessing the CSVs (Git LFS)](#accessing-the-csvs-git-lfs)
8. [Citation](#citation)

---

## Sites and Status

| Site | Location | Floors / Areas | Stationary | Mobile |
|------|----------|----------------|------------|--------|
| **CMUQ** | Carnegie Mellon Univ. in Qatar | Floors 1, 2, 3 | F1 done  F2 done  F3 planned | planned |
| **Ezdan Tower** | Doha | Towers 1-4 | planned | planned |
| **Msheireb Parking** | Msheireb Downtown Doha | Parking lot | planned | planned |
| **EC Parking** | Education City | Parking lot | planned | planned |

---

## Directory Structure

`
unicellular-fingerprint-dataset/
|-- README.md
|-- .gitattributes          # *.csv tracked by Git LFS
|-- .gitignore
|-- requirements.txt
|-- dashboard.py            # interactive Dash app (CMUQ stationary)
|
|-- data/                   # processed CSVs (large files via Git LFS)
|   |-- cmuq/
|   |   |-- stationary/
|   |   |   |-- floor1.csv  (~128 MB)
|   |   |   |-- floor2.csv  (~145 MB)
|   |   |   -- floor3.csv  (planned)
|   |   -- mobile/
|   |       |-- floor1.csv  (planned)
|   |       |-- floor2.csv  (planned)
|   |       -- floor3.csv  (planned)
|   |-- ezdan/tower{1..4}/  (planned)
|   |-- msheireb_parking/   (planned)
|   -- ec_parking/         (planned)
|
|-- floor_plans/            # rasterised floor plan PNGs
|   -- cmuq/
|       |-- floor1.png
|       -- floor2.png
|
|-- coordinates/            # RP pixel coordinates (JSON)
|   -- cmuq/
|       |-- floor1.json
|       -- floor2.json
|
|-- figures/                # publication-ready overview figures
|   -- cmuq/
|       -- stationary_floor1_overview.png
|
|-- scripts/
|   -- cmuq/
|       |-- assign_coordinates_f1.py   # interactive RP click tool
|       |-- assign_coordinates_f2.py
|       |-- assign_coordinates_f3.py   # skeleton
|       |-- process_stationary_f1.py   # JSON -> CSV
|       |-- process_stationary_f2.py
|       |-- process_stationary_f3.py   # skeleton
|       |-- visualize_stationary_f1.py
|       |-- visualize_stationary_f2.py
|       |-- visualize_stationary_f3.py # skeleton
|       |-- process_mobile_f1.py       # skeleton
|       |-- process_mobile_f2.py       # skeleton
|       -- process_mobile_f3.py       # skeleton
|
-- raw/                    # NOT in repo - place raw Firebase exports here
    -- .gitkeep
`

---

## Data Schema

Every processed CSV (stationary and mobile) shares the same 24-column schema:

| Column | Type | Description |
|--------|------|-------------|
| entry_id | str | Firebase document key |
| uildingNumber | int | Building ID (5 = CMUQ) |
| entryDate | str | ISO date of the session |
| loorNumber | int | Floor number |
| 
pNumber | int | Reference point index (-1 in mobile mode) |
| x, y | int | Pixel coordinates on floor plan (-1 in mobile mode) |
| atteryPower | float | Device battery % at scan time |
| deviceHeight | float | Holding height in metres |
| hoFlag | bool | Handover flag |
| infrastructureType | str | Network operator / RAT description |
| phoneName | str | Device identifier |
| scanDate | str | ISO timestamp of the scan |
| scanNumber | int | Scan index within the session |
| servingCellId | int | Transmitter ID of the serving cell |
| 	imeStamp | int | Unix millisecond timestamp |
| 	ransmitter_asu | int | Arbitrary Strength Unit |
| 	ransmitter_id | int | Unique transmitter (cell) identifier |
| 	ransmitter_level | int | Android signal level (0-4) |
| 	ransmitter_rsrq | float | Reference Signal Received Quality (dB) |
| 	ransmitter_rss | float | Received Signal Strength (dBm) |
| 	ransmitter_rssi | float | RSSI (dBm); blank where raw = INT_MAX sentinel |
| 	ransmitter_snr | float | SNR (dB); blank where raw = INT_MAX sentinel |
| 	ransmitter_type | str | Network type string (e.g. LTE, NR) |

**Sentinel masking**: The Android API returns Integer.MAX_VALUE (2,147,483,647) when a metric is unavailable. Processing scripts replace these with empty strings so pandas reads them as NaN.

---

## Collection Protocol

### Stationary Mode

1. **Floor plan preparation** - Convert the PDF floor plan to PNG (assign_coordinates_f*.py, Phase 1).
2. **Circle detection** - OpenCV detects red RP markers automatically; result cached in coordinates/cmuq/detected_circles_f*.json.
3. **RP assignment** - Researcher clicks each detected circle in RP order (1 to N) in an interactive matplotlib window; saves coordinates/cmuq/floor*.json.
4. **Data collection** - 7 smartphones placed at each RP simultaneously. 300 cellular scans per (RP, phone) pair collected via the UniCellular Android app and exported from Firebase Realtime Database.
5. **Processing** - process_stationary_f*.py parses the raw JSON, merges pixel coordinates, masks sentinel values, and writes data/cmuq/stationary/floor*.csv.
6. **Visualisation** - visualize_stationary_f*.py generates a 6-panel static overview figure.

### Mobile Mode

1. A single researcher walks the entire floor continuously for approximately 1 hour.
2. No reference points are marked - position is not recorded. All rows in mobile CSVs have rpNumber = -1, x = -1, y = -1.
3. The raw Firebase export is processed by process_mobile_f*.py, producing a CSV with the same 24-column schema as the stationary files.
4. Mobile data is intended for training/evaluating models that do not require labelled reference points (e.g. unsupervised or self-supervised localisation).

---

## Processing Pipeline

`
Firebase export (raw JSON)
        |
        v
scripts/cmuq/process_stationary_f*.py  <--  coordinates/cmuq/floor*.json
        |
        v
data/cmuq/stationary/floor*.csv  (Git LFS)
        |
        v
scripts/cmuq/visualize_stationary_f*.py  -->  figures/cmuq/
        |
        v
dashboard.py  (interactive Dash app)
`

---

## Interactive Dashboard

Requires Python >= 3.10 and the packages in requirements.txt.

`ash
pip install -r requirements.txt
python dashboard.py
# Open http://127.0.0.1:8050
`

The dashboard shows all floors for which a CSV is present. Floor 3 will appear automatically once data/cmuq/stationary/floor3.csv is added.

---

## Accessing the CSVs (Git LFS)

The processed CSVs are stored via Git LFS (https://git-lfs.github.com/). You must have Git LFS installed before cloning:

`ash
git lfs install
git clone https://github.com/EricluvPython/unicellular-fingerprint-dataset.git
`

If you cloned without LFS, fetch the binary files:

`ash
git lfs pull
`

Alternatively, download individual CSVs directly from the GitHub web UI (click the file, then Download raw file).

---

## Citation

If you use this dataset in your research, please cite:

`
@misc{unicellular2025,
  title  = {UniCellular Fingerprint Dataset},
  author = {[Authors TBD]},
  year   = {2025},
  url    = {https://github.com/EricluvPython/unicellular-fingerprint-dataset},
}
`

---

## License

Data and code are released under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).
You are free to share and adapt the material for any purpose, provided appropriate credit is given.
