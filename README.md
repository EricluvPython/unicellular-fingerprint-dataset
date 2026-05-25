# UniCellular Fingerprint Dataset

> **Cellular radio-frequency fingerprint dataset** collected across multiple indoor environments in Qatar.  
> Each site is covered in two modes: **stationary** (fixed reference points, multiple phones, repeated scans) and **mobile** (continuous free-walk sessions, no fixed reference points).

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
| **CMUQ** | Carnegie Mellon Univ. in Qatar | Floors 1, 2, 3 | ✅ F1, F2, F3 | ✅ F1, F2, F3 |
| **Ezdan Tower** | Doha | Towers 1-4 | planned | planned |
| **Msheireb Parking** | Msheireb Downtown Doha | Parking lot | planned | planned |
| **EC Parking** | Education City | Parking lot | planned | planned |

---

## Directory Structure

```
unicellular-fingerprint-dataset/
|-- README.md
|-- .gitattributes          # *.csv tracked by Git LFS
|-- .gitignore
|-- requirements.txt
|-- dashboard.py            # interactive Dash app (stationary + mobile)
|
|-- data/                   # processed CSVs (large files via Git LFS)
|   |-- cmuq/
|   |   |-- stationary/
|   |   |   |-- floor1.csv  (~128 MB, 734 k rows)
|   |   |   |-- floor2.csv  (~145 MB, 833 k rows)
|   |   |   \-- floor3.csv  (~145 MB, 606 k rows)
|   |   \-- mobile/
|   |       |-- floor1.csv  (~47 MB, 262 k rows)
|   |       |-- floor2.csv  (~51 MB, 283 k rows)
|   |       \-- floor3.csv  (~33 MB, 183 k rows)
|   |-- ezdan/              (planned)
|   |-- msheireb_parking/   (planned)
|   \-- ec_parking/         (planned)
|
|-- floor_plans/            # rasterised floor plan PNGs
|   \-- cmuq/
|       |-- floor1.png
|       |-- floor2.png
|       \-- floor3.png
|
|-- coordinates/            # RP pixel coordinates (JSON)
|   \-- cmuq/
|       |-- floor1.json
|       |-- floor2.json
|       \-- floor3.json
|
|-- figures/                # publication-ready overview figures
|   \-- cmuq/
|       \-- stationary_floor1_overview.png
|
|-- scripts/
|   \-- cmuq/
|       |-- assign_coordinates_f1.py    # interactive RP click tool
|       |-- assign_coordinates_f2.py
|       |-- assign_coordinates_f3.py
|       |-- process_stationary_f1.py    # JSON -> stationary CSV
|       |-- process_stationary_f2.py
|       |-- process_stationary_f3.py
|       |-- visualize_stationary_f1.py
|       |-- visualize_stationary_f2.py
|       |-- visualize_stationary_f3.py
|       \-- process_mobile.py           # JSON -> mobile CSVs (all 3 floors)
|
\-- raw/                   # NOT in repo - place raw Firebase exports here
    \-- .gitkeep
```

---

## Data Schema

### Stationary CSV (24 columns)

| Column | Type | Description |
|--------|------|-------------|
| entry_id | str | Firebase document key |
| buildingNumber | int | Building ID (5 = CMUQ) |
| entryDate | str | ISO date of the session |
| floorNumber | int | Floor number |
| rpNumber | int | Reference point index |
| x, y | int | Pixel coordinates on floor plan |
| batteryPower | float | Device battery % at scan time |
| deviceHeight | float | Holding height in metres |
| hoFlag | bool | Handover flag |
| infrastructureType | str | Network operator / RAT description |
| phoneName | str | Device identifier |
| scanDate | str | ISO timestamp of the scan |
| scanNumber | int | Scan index within the session (1–300 per RP per phone) |
| servingCellId | int | Transmitter ID of the serving cell |
| timeStamp | int | Unix millisecond timestamp |
| transmitter_asu | int | Arbitrary Strength Unit |
| transmitter_id | int | Unique transmitter (cell) identifier |
| transmitter_level | int | Android signal level (0–4) |
| transmitter_rsrq | float | Reference Signal Received Quality (dB) |
| transmitter_rss | float | Received Signal Strength (dBm) |
| transmitter_rssi | float | RSSI (dBm); blank where raw value = INT_MAX sentinel |
| transmitter_snr | float | SNR (dB); blank where raw value = INT_MAX sentinel |
| transmitter_type | str | Network type string (e.g. LTE, NR) |

### Mobile CSV (25 columns = stationary + `side`)

Same schema as stationary, with the following differences:

| Column | Value / Notes |
|--------|---------------|
| rpNumber | Always `-1` (no fixed reference point) |
| x, y | Always `-1` |
| scanNumber | Monotonic 1-based index per phone per floor (reconstructed from time-sorted order; the Android app resets its internal counter every ~1000 scans) |
| **side** | `top` = north corridor (straight wall) · `bottom` = south corridor (curved wall). Assigned automatically by finding the largest timestamp gap within each phone's collection and labelling entries before the gap `top` and after `bottom`. |

**Sentinel masking**: The Android API returns Integer.MAX_VALUE (2,147,483,647) when a metric is unavailable.
Processing scripts replace these with empty strings so pandas reads them as NaN.

---

## Collection Protocol

### Stationary Mode

1. **Floor plan preparation** – Convert the PDF floor plan to PNG (`assign_coordinates_f*.py`, Phase 1).
2. **Circle detection** – OpenCV detects red RP markers automatically; result cached in `coordinates/cmuq/detected_circles_f*.json`.
3. **RP assignment** – Researcher clicks each detected circle in RP order (1 to N) in an interactive matplotlib window; saves `coordinates/cmuq/floor*.json`.
4. **Data collection** – 7 smartphones placed at each RP simultaneously. 300 cellular scans per (RP, phone) pair collected via the UniCellular Android app and exported from Firebase Realtime Database.
5. **Processing** – `process_stationary_f*.py` parses the raw JSON, merges pixel coordinates, masks sentinel values, and writes `data/cmuq/stationary/floor*.csv`.
6. **Visualisation** – `visualize_stationary_f*.py` generates a 6-panel static overview figure.

### Mobile Mode (CMUQ)

1. A single researcher walks the entire floor continuously, one side at a time. All 7 phones are carried simultaneously.
2. **Side labelling** – The corridor has two distinct sides:
   - **top** = north corridor (straight wall)
   - **bottom** = south corridor (curved wall)  
   The side label is assigned automatically by `process_mobile.py`: for each (phone, floor), entries are sorted by timestamp and the single largest time gap is found; entries before the gap are labelled `top`, entries after are labelled `bottom`.
3. No reference points are marked — position is not recorded. All rows have `rpNumber = -1`, `x = -1`, `y = -1`.
4. **Scan number reconstruction** – The Android app resets its internal scan counter every ~1000 scans. `process_mobile.py` discards the raw counter and assigns a monotonic 1-based sequential index per (phone, floor) based on time-sorted order, so `scanNumber` runs from 1 to the total number of scans (typically 6 000–11 000 per phone per floor).
5. **Floor 1 filtering** – The Floor 1 raw export includes a mistake collection run made before 10:02 local time (07:02 UTC, 2026-05-25). These 13 552 entries are dropped during processing.
6. Mobile data is intended for training/evaluating models that do not require labelled reference points (e.g. unsupervised or self-supervised localisation).

---

## Processing Pipeline

### Stationary

```
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
```

### Mobile

```
Firebase export (raw JSON)
        |
        v
scripts/cmuq/process_mobile.py
  - filters mistake run (Floor 1 only, before 07:02 UTC 2026-05-25)
  - assigns side label (top / bottom) via largest timestamp gap per phone
  - reconstructs monotonic scanNumber (1-based index per phone per floor)
  - masks INT_MAX sentinels
        |
        v
data/cmuq/mobile/floor{1,2,3}.csv  (Git LFS)
        |
        v
dashboard.py  (Mobile Data tab)
```

---

## Interactive Dashboard

Requires Python >= 3.10 and the packages in `requirements.txt`.

```bash
pip install -r requirements.txt
python dashboard.py
# Open http://127.0.0.1:8050
```

The dashboard automatically loads every floor for which a stationary or mobile CSV is present.
It contains the following tabs:

| Tab | Contents |
|-----|----------|
| **Overview** | KPI cards: total rows, unique phones, transmitters, RPs; per-floor summary |
| **Floor Map** | Reference-point heatmap overlaid on the floor plan (stationary only) |
| **Signal Metrics** | Per-phone and per-RP signal distributions; CDF and box plots |
| **Temporal** | Scan-level signal time series; rolling mean overlays |
| **Transmitters** | Transmitter type breakdown; serving-cell statistics |
| **Field Explorer** | RP-by-RP drill-down; violin plots per transmitter |
| **3D View** | 3-D scatter of RSS/RSSI by RP, colour-coded by phone |
| **Mobile Data** | Dedicated tab for mobile (free-walk) sessions — see below |
| **Compare Floors** | Side-by-side metric comparison across floors |

### Mobile Data Tab

The **Mobile Data** tab provides an overview of the free-walk sessions:

- **Metric selector** – Choose the signal metric to visualise: RSS · RSSI · RSRQ · SNR · ASU · Level.
- **KPI cards** – Total scans, unique phones, unique transmitters, plus scan counts broken down by side (top / bottom).
- **Signal distribution** – Violin plots of the selected metric grouped by corridor side and phone.
- **Collection timeline** – Scan-level time series of the mean selected metric per phone, showing when each phone was active.
- **Mean metric per phone & side** – Grouped bar chart comparing the mean selected metric across phones and sides.
- **Scan counts** – Grouped bar chart of total scan counts per phone, split by side.
- **TX type breakdown** – Pie chart of transmitter type proportions (LTE, NR, …).
- **Side note** – The `side` assignment is automatic (largest timestamp gap); verify manually if exact corridor labelling matters for your use case.

---

## Accessing the CSVs (Git LFS)

The processed CSVs are stored via [Git LFS](https://git-lfs.github.com/).
You must have Git LFS installed before cloning:

```bash
git lfs install
git clone https://github.com/EricluvPython/unicellular-fingerprint-dataset.git
```

If you cloned without LFS, fetch the binary files:

```bash
git lfs pull
```

Alternatively, download individual CSVs directly from the GitHub web UI
(click the file, then **Download raw file**).

---

## Citation

If you use this dataset in your research, please cite:

```
@misc{unicellulardata2026,
  title  = {UniCellular Fingerprint Dataset},
  author = {[Authors TBD]},
  year   = {2026},
  url    = {https://github.com/EricluvPython/unicellular-fingerprint-dataset},
}
```

---

## License

Data and code are released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
You are free to share and adapt the material for any purpose, provided appropriate credit is given.
