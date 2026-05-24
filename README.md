# UniCellular Fingerprint Dataset – CMUQ Campus

> **Cellular radio-frequency fingerprint dataset** collected at Carnegie Mellon University in Qatar (CMUQ), covering two floors with 84 reference points each, 7 smartphones, and 300 scans per reference point per phone.

---

## Table of Contents

1. [Dataset Overview](#dataset-overview)
2. [Collection Environment](#collection-environment)
3. [Devices & Protocol](#devices--protocol)
4. [Dataset Structure](#dataset-structure)
5. [CSV Schema](#csv-schema)
6. [Processing Pipeline](#processing-pipeline)
7. [Visualisation & Dashboard](#visualisation--dashboard)
8. [Installation](#installation)
9. [Citation](#citation)

---

## Dataset Overview

| Property | Value |
|---|---|
| Site | Carnegie Mellon University in Qatar (CMUQ) – Building 5 |
| Floors | Floor 1 (First Floor) · Floor 2 (Second Floor) |
| Reference points (RPs) per floor | 84 |
| Phones | 7 (6 unique handsets; one device ID appeared twice → renamed with `-2` suffix) |
| Scans per RP per phone | 300 |
| Total rows – Floor 1 | 734,511 |
| Total rows – Floor 2 | 833,809 |
| Radio technologies | GSM · LTE · WCDMA · NR |
| Operator | Ooredoo Qatar |
| Device height | 1.2 m |

Each row corresponds to **one transmitter observed during one scan at one reference point by one phone**.

---

## Collection Environment

```
Building 5, CMUQ (Education City, Doha, Qatar)
├── Floor 1  –  floor plan: floor_plans/FF-Generic.png
│              84 RPs arranged along corridors and rooms
└── Floor 2  –  floor plan: floor_plans/SF-Generic.png
               84 RPs with equivalent spatial coverage
```

Reference points were marked on printed floor plans and identified by a red-circle marker.  
Pixel coordinates of each RP were manually mapped from a PDF floor plan using `assign_coordinates_f*.py`.

---

## Devices & Protocol

| Phone ID | Model |
|---|---|
| 25028RN03A | Redmi Note (device A) |
| 25028RN03A-2 | Redmi Note (device B — same hardware ID, renamed) |
| CPH2743 | OPPO |
| HED-LX9 | Huawei |
| RMX3938 | Realme |
| SM-A176B | Samsung Galaxy A17 |
| itel A675L | itel A675L |

**Collection procedure:**
1. Surveyor stands at the marked RP holding the phone at 1.2 m height.
2. The collection app (Firebase Realtime Database) records 300 consecutive scans.
3. Each scan captures all visible cellular transmitters (serving cell + neighbours).
4. All 7 phones collected simultaneously, sweeping through all 84 RPs per floor.

> **Note on duplicate phone ID:** Two physical devices reported the same Android device ID `25028RN03A`.  
> During processing, entries are grouped by `(rpNumber, scanNumber)` and the later timestamp is renamed `25028RN03A-2`.

---

## Dataset Structure

```
unicellular-fingerprint-dataset/
├── data/
│   ├── cmuq_stationary_7phone_f1.csv   ← Floor 1 processed data (Git LFS, ~128 MB)
│   └── cmuq_stationary_7phone_f2.csv   ← Floor 2 processed data (Git LFS, ~145 MB)
├── floor_plans/
│   ├── FF-Generic.png                  ← Floor 1 plan (rasterised from PDF)
│   └── SF-Generic.png                  ← Floor 2 plan (rasterised from PDF)
├── coordinates/
│   ├── coordinates_f1.json             ← RP number → [pixel_x, pixel_y], Floor 1
│   └── coordinates_f2.json             ← RP number → [pixel_x, pixel_y], Floor 2
├── figures/
│   └── cmuq_f1_stationary_overview.png ← 6-panel overview figure
├── raw/                                ← gitignored; place raw export files here
│   └── .gitkeep
├── assign_coordinates_f1.py            ← OpenCV circle detection + click-to-assign UI
├── assign_coordinates_f2.py
├── process_cmuq_f1_stationary.py       ← Raw JSON → flat CSV
├── process_cmuq_f2_stationary.py
├── visualize_cmuq_f1_stationary.py     ← 6-panel matplotlib overview
├── visualize_cmuq_f2_stationary.py
├── dashboard_cmuq.py                   ← Interactive Plotly/Dash dashboard
└── requirements.txt
```

### Downloading the large CSVs (Git LFS)

This repository uses **Git LFS** to store the two large CSV files.  
After cloning, run:

```bash
git lfs pull
```

If you do not have Git LFS installed:

```bash
# macOS
brew install git-lfs

# Ubuntu / Debian
sudo apt install git-lfs

# Windows (Chocolatey)
choco install git-lfs

# then initialise once
git lfs install
```

---

## CSV Schema

Both floor CSVs share the same 24-column schema:

| Column | Type | Description |
|---|---|---|
| `entry_id` | str | Firebase entry key |
| `buildingNumber` | int | Building identifier (5 = CMUQ Building 5) |
| `entryDate` | str | Date of collection (YYYY-MM-DD) |
| `floorNumber` | int | 1 or 2 |
| `rpNumber` | int | Reference point number (1–84) |
| `x` | int | Pixel x-coordinate on floor plan image |
| `y` | int | Pixel y-coordinate on floor plan image |
| `batteryPower` | float | Phone battery level (%) at scan time |
| `deviceHeight` | float | Measurement height (1.2 m) |
| `hoFlag` | bool | Handover flag (False = stationary) |
| `infrastructureType` | str | Always `"Cellular Ooredoo"` |
| `phoneName` | str | Device identifier (see Devices table) |
| `scanDate` | str | Timestamp string of the scan |
| `scanNumber` | int | Scan index (1–300) per RP per phone |
| `servingCellId` | int | ID of the serving (strongest) cell |
| `timeStamp` | int | Unix millisecond timestamp |
| `transmitter_asu` | int | Arbitrary Strength Unit |
| `transmitter_id` | int | Transmitter / cell identifier |
| `transmitter_level` | int | Signal level bucket (0–4) |
| `transmitter_rsrq` | float | Reference Signal Received Quality (dB) |
| `transmitter_rss` | float | Received Signal Strength (dBm) |
| `transmitter_rssi` | float | RSSI (dBm); `NaN` for GSM (no RSSI reported) |
| `transmitter_snr` | float | Signal-to-Noise Ratio (dB); `NaN` for GSM |
| `transmitter_type` | str | `GSM` · `LTE` · `WCDMA` · `NR` |

> **Sentinel values:** The raw export uses `2,147,483,647` (Java `Integer.MAX_VALUE`) to indicate "not available" for `transmitter_rssi` and `transmitter_snr` on GSM cells. The processing scripts replace these with `NaN`.

---

## Processing Pipeline

Run these steps **once per floor** to regenerate the CSVs from the raw Firebase export:

```
raw JSON export
      │
      ▼
assign_coordinates_fX.py   ← OpenCV red-circle detection on floor plan PDF
      │                        outputs coordinates/coordinates_fX.json
      ▼
process_cmuq_fX_stationary.py  ← Flattens nested JSON, merges coordinates,
      │                           splits duplicate phone IDs
      ▼
data/cmuq_stationary_7phone_fX.csv
```

### Step 1 – Map reference point coordinates

Place the original PDF floor plans in `raw/`:
- `raw/FF-Generic(2).pdf` (Floor 1)
- `raw/SF-Generic(2).pdf` (Floor 2)

```bash
python assign_coordinates_f1.py   # interactive click UI, saves coordinates/coordinates_f1.json
python assign_coordinates_f2.py
```

**Interactive UI controls:**  
Click the red dot nearest to each RP in ascending order (1 → 84).  
`u` = undo last assignment · `s` = save & continue · `q` = quit

### Step 2 – Generate CSV

Place the raw Firebase JSON exports in `raw/`:
- `raw/cmuq_stationary_7phone_f1_raw.json`
- `raw/fingerprints_floor2.json`

```bash
python process_cmuq_f1_stationary.py   # → data/cmuq_stationary_7phone_f1.csv
python process_cmuq_f2_stationary.py   # → data/cmuq_stationary_7phone_f2.csv
```

---

## Visualisation & Dashboard

### Static overview figures

```bash
python visualize_cmuq_f1_stationary.py   # → figures/cmuq_f1_stationary_overview.png
python visualize_cmuq_f2_stationary.py   # → figures/cmuq_f2_stationary_overview.png
```

Each figure has 6 panels: RP map · RSS heatmap · RSS boxplot · unique-TX bar · type breakdown · SNR violin.

### Interactive Dash dashboard

```bash
python dashboard_cmuq.py
# Open http://127.0.0.1:8050
```

**Tabs:**  
`Overview` · `Floor Map` · `Signal Metrics` · `Temporal` · `Transmitters` · `Field Explorer` · `Compare Floors`

A **floor selector** in the header switches all tabs between Floor 1 and Floor 2.  
The **Compare Floors** tab is unlocked once both CSVs are loaded.

---

## Installation

```bash
# Clone (requires Git LFS)
git clone https://github.com/EricluvPython/unicellular-fingerprint-dataset.git
cd unicellular-fingerprint-dataset
git lfs pull

# Install Python dependencies (Python 3.9+)
pip install -r requirements.txt
```

### Processing-only dependencies

`assign_coordinates_f*.py` additionally requires:
```bash
pip install pymupdf opencv-python
```

---

## Citation

> *Paper in preparation.*  
> If you use this dataset, please cite:
>
> ```bibtex
> @dataset{unicellular_cmuq_2026,
>   title   = {UniCellular Fingerprint Dataset – CMUQ Campus},
>   year    = {2026},
>   url     = {https://github.com/EricluvPython/unicellular-fingerprint-dataset},
> }
> ```

---

*Dataset collected at Carnegie Mellon University in Qatar.*
