"""
CMUQ Floor 3 – Stationary Visualization (Skeleton)
Generates: figures/cmuq/stationary_floor3_overview.png
Run AFTER process_stationary_f3.py and assign_coordinates_f3.py.

TODO: Update TOTAL_RPS and suptitle once floor-3 collection is complete.
      The body is identical to visualize_stationary_f2.py – just substitute
      floor2 → floor3 / f2 → f3 throughout.
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
CSV_PATH = os.path.join(ROOT, "data", "cmuq", "stationary", "floor3.csv")
IMG_PATH = os.path.join(ROOT, "floor_plans", "cmuq", "floor3.png")
OUT_PATH = os.path.join(ROOT, "figures", "cmuq", "stationary_floor3_overview.png")

PHONE_COLORS = {
    "25028RN03A":   "#e41a1c",
    "25028RN03A-2": "#ff7f00",
    "CPH2743":      "#d4b000",
    "HED-LX9":      "#4daf4a",
    "RMX3938":      "#377eb8",
    "SM-A176B":     "#984ea3",
    "itel A675L":   "#a65628",
}

if not os.path.exists(CSV_PATH):
    raise FileNotFoundError(
        f"{CSV_PATH} not found.\n"
        "Run process_stationary_f3.py first."
    )

print("Loading CSV …")
df = pd.read_csv(CSV_PATH)
print(f"  {len(df):,} rows | {df['rpNumber'].nunique()} RPs | "
      f"{df['phoneName'].nunique()} phones | "
      f"{df['transmitter_id'].nunique()} unique transmitters")

# TODO: Copy the full visualization body from visualize_stationary_f2.py
#       and update f2→f3, floor2→floor3, "Floor 2"→"Floor 3" in plot titles.
raise NotImplementedError(
    "visualize_stationary_f3.py body not yet implemented.\n"
    "Copy from visualize_stationary_f2.py and substitute floor2→floor3."
)
