"""
Visualization of CMUQ Floor 1 Stationary Dataset
Generates: cmuq_f1_stationary_overview.png
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import matplotlib.colors as mcolors
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT     = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(ROOT, "data", "cmuq_stationary_7phone_f1.csv")
IMG_PATH = os.path.join(ROOT, "floor_plans", "FF-Generic.png")
OUT_PATH = os.path.join(ROOT, "figures", "cmuq_f1_stationary_overview.png")

PHONE_COLORS = {
    "25028RN03A":   "#e41a1c",
    "25028RN03A-2": "#ff7f00",
    "CPH2743":      "#f0c000",
    "HED-LX9":      "#4daf4a",
    "RMX3938":      "#377eb8",
    "SM-A176B":     "#984ea3",
    "itel A675L":   "#a65628",
}

# ── load ──────────────────────────────────────────────────────────────────
print("Loading CSV …")
df = pd.read_csv(CSV_PATH)
print(f"  {len(df):,} rows | {df['rpNumber'].nunique()} RPs | "
      f"{df['phoneName'].nunique()} phones | "
      f"{df['transmitter_id'].nunique()} unique transmitters")

phones = sorted(df["phoneName"].unique())

# ── per-RP aggregates ─────────────────────────────────────────────────────
rp_info = (df.drop_duplicates(["rpNumber", "x", "y"])
             .groupby("rpNumber")[["x", "y"]].first()
             .reset_index())

# mean RSS of the serving cell per RP (all phones combined)
serving = df[df["transmitter_id"] == df["servingCellId"]].copy()
mean_rss_per_rp = (serving.groupby("rpNumber")["transmitter_rss"]
                           .mean()
                           .reset_index()
                           .rename(columns={"transmitter_rss": "mean_rss"}))
rp_info = rp_info.merge(mean_rss_per_rp, on="rpNumber", how="left")

# unique transmitters per RP
uniq_tx = (df.groupby("rpNumber")["transmitter_id"]
             .nunique()
             .reset_index()
             .rename(columns={"transmitter_id": "n_tx"}))
rp_info = rp_info.merge(uniq_tx, on="rpNumber", how="left")

# ── figure layout ─────────────────────────────────────────────────────────
fig = plt.figure(figsize=(22, 16))
fig.patch.set_facecolor("#f8f8f8")

gs = fig.add_gridspec(
    2, 3,
    left=0.04, right=0.97,
    top=0.93,  bottom=0.06,
    hspace=0.38, wspace=0.30,
)

ax_map1 = fig.add_subplot(gs[0, 0])   # floor plan – RP labels
ax_map2 = fig.add_subplot(gs[1, 0])   # floor plan – RSS heatmap
ax_box  = fig.add_subplot(gs[0, 1])   # RSS boxplot per phone
ax_tx   = fig.add_subplot(gs[0, 2])   # unique transmitters per RP
ax_type = fig.add_subplot(gs[1, 1])   # transmitter type breakdown per phone
ax_snr  = fig.add_subplot(gs[1, 2])   # SNR distribution per phone

fig.suptitle(
    "CMUQ Floor 1 – Stationary Dataset Overview\n"
    f"84 RPs · 7 Phones · 300 scans/RP/phone · "
    f"{df['transmitter_id'].nunique()} transmitters · "
    f"{len(df):,} rows",
    fontsize=14, fontweight="bold", y=0.97,
)

floor_img = mpimg.imread(IMG_PATH) if os.path.exists(IMG_PATH) else None

# ══════════════════════════════════════════════════════════════════════════
# Panel 1 – Floor plan with RP labels
# ══════════════════════════════════════════════════════════════════════════
if floor_img is not None:
    ax_map1.imshow(floor_img, aspect="auto")
else:
    ax_map1.set_facecolor("#e8e8e8")

ax_map1.scatter(rp_info["x"], rp_info["y"],
                s=60, c="#1f77b4", edgecolors="white", linewidths=0.7, zorder=3)
for _, row in rp_info.iterrows():
    ax_map1.annotate(
        str(int(row["rpNumber"])),
        (row["x"], row["y"]),
        fontsize=5.5, ha="center", va="center",
        color="white", fontweight="bold", zorder=4,
    )

ax_map1.set_title("Reference Point Locations", fontsize=11, fontweight="bold")
ax_map1.axis("off")

# ══════════════════════════════════════════════════════════════════════════
# Panel 2 – Floor plan coloured by mean serving-cell RSS
# ══════════════════════════════════════════════════════════════════════════
if floor_img is not None:
    ax_map2.imshow(floor_img, aspect="auto", alpha=0.45)
else:
    ax_map2.set_facecolor("#e8e8e8")

valid = rp_info.dropna(subset=["mean_rss"])
sc = ax_map2.scatter(
    valid["x"], valid["y"],
    c=valid["mean_rss"],
    cmap="RdYlGn",
    s=90,
    edgecolors="white", linewidths=0.7,
    zorder=3,
    vmin=valid["mean_rss"].min(), vmax=valid["mean_rss"].max(),
)
cbar = fig.colorbar(sc, ax=ax_map2, fraction=0.03, pad=0.01)
cbar.set_label("Mean RSS (dBm)", fontsize=8)
cbar.ax.tick_params(labelsize=7)

for _, row in valid.iterrows():
    ax_map2.annotate(
        str(int(row["rpNumber"])),
        (row["x"], row["y"]),
        fontsize=5, ha="center", va="center",
        color="black", fontweight="bold", zorder=4,
    )

ax_map2.set_title("Mean Serving-Cell RSS per RP", fontsize=11, fontweight="bold")
ax_map2.axis("off")

# ══════════════════════════════════════════════════════════════════════════
# Panel 3 – RSS box-plot per phone (serving cell only)
# ══════════════════════════════════════════════════════════════════════════
rss_by_phone = [serving[serving["phoneName"] == p]["transmitter_rss"].values
                for p in phones]
short_labels = [p.replace("25028RN03A-2", "RN03A-2")
                 .replace("25028RN03A", "RN03A") for p in phones]

bp = ax_box.boxplot(rss_by_phone, patch_artist=True, notch=False,
                    medianprops=dict(color="black", linewidth=1.5))
for patch, phone in zip(bp["boxes"], phones):
    patch.set_facecolor(PHONE_COLORS[phone])
    patch.set_alpha(0.8)

ax_box.set_xticks(range(1, len(phones) + 1))
ax_box.set_xticklabels(short_labels, fontsize=8, rotation=25, ha="right")
ax_box.set_ylabel("RSS (dBm)", fontsize=9)
ax_box.set_title("Serving-Cell RSS Distribution per Phone", fontsize=11, fontweight="bold")
ax_box.grid(axis="y", alpha=0.35)
ax_box.axhline(serving["transmitter_rss"].median(), color="gray",
               linestyle="--", linewidth=0.8, label="Overall median")
ax_box.legend(fontsize=8)

# ══════════════════════════════════════════════════════════════════════════
# Panel 4 – Unique transmitters per RP (bar chart)
# ══════════════════════════════════════════════════════════════════════════
rp_sorted = rp_info.sort_values("rpNumber")
bars = ax_tx.bar(rp_sorted["rpNumber"], rp_sorted["n_tx"],
                 color="#377eb8", edgecolor="white", linewidth=0.4)
ax_tx.set_xlabel("RP number", fontsize=9)
ax_tx.set_ylabel("# unique transmitters", fontsize=9)
ax_tx.set_title("Unique Transmitters Seen per RP", fontsize=11, fontweight="bold")
ax_tx.axhline(rp_sorted["n_tx"].mean(), color="crimson",
              linestyle="--", linewidth=1, label=f"Mean = {rp_sorted['n_tx'].mean():.1f}")
ax_tx.legend(fontsize=8)
ax_tx.grid(axis="y", alpha=0.35)
ax_tx.set_xticks(np.arange(1, 85, 7))
ax_tx.tick_params(axis="x", labelsize=7)

# ══════════════════════════════════════════════════════════════════════════
# Panel 5 – Transmitter-type breakdown per phone (stacked bar)
# ══════════════════════════════════════════════════════════════════════════
type_counts = (df.groupby(["phoneName", "transmitter_type"])
                 .size()
                 .unstack(fill_value=0)
                 .reindex(phones))

tx_types = type_counts.columns.tolist()
type_colors = {"GSM": "#e41a1c", "LTE": "#377eb8", "WCDMA": "#4daf4a",
               "NR": "#ff7f00", "CDMA": "#984ea3"}
bottom = np.zeros(len(phones))
for ttype in tx_types:
    vals = type_counts[ttype].values
    ax_type.bar(range(len(phones)), vals,
                bottom=bottom,
                label=ttype,
                color=type_colors.get(ttype, "#aaaaaa"),
                edgecolor="white", linewidth=0.4)
    bottom += vals

ax_type.set_xticks(range(len(phones)))
ax_type.set_xticklabels(short_labels, fontsize=8, rotation=25, ha="right")
ax_type.set_ylabel("Observation count", fontsize=9)
ax_type.set_title("Transmitter Type Breakdown per Phone", fontsize=11, fontweight="bold")
ax_type.legend(fontsize=8, title="Type", title_fontsize=8)
ax_type.grid(axis="y", alpha=0.35)
ax_type.yaxis.set_major_formatter(
    plt.FuncFormatter(lambda v, _: f"{int(v/1000)}k" if v >= 1000 else str(int(v))))

# ══════════════════════════════════════════════════════════════════════════
# Panel 6 – SNR distribution per phone (violin)
# ══════════════════════════════════════════════════════════════════════════
snr_by_phone = [(p, serving[serving["phoneName"]==p]["transmitter_snr"].dropna().values)
                for p in phones]
valid_snr = [(p, v) for p, v in snr_by_phone if len(v) > 0]
if valid_snr:
    v_phones, v_data = zip(*valid_snr)
    v_short = [short(p) for p in v_phones]
    v_pos   = list(range(1, len(v_phones)+1))
    vp = ax_snr.violinplot(list(v_data), positions=v_pos,
                           showmedians=True, showextrema=True)
    for body, ph in zip(vp["bodies"], v_phones):
        body.set_facecolor(PHONE_COLORS.get(ph, "#aaa")); body.set_alpha(0.75)
    vp["cmedians"].set_color("black")
    vp["cbars"].set_linewidth(0.8)
    vp["cmins"].set_linewidth(0.8)
    vp["cmaxes"].set_linewidth(0.8)
    missing = [short(p) for p, v in snr_by_phone if len(v) == 0]
    if missing:
        ax_snr.set_xlabel(f"No SNR data for: {', '.join(missing)}", fontsize=7, color="grey")
    ax_snr.set_xticks(v_pos)
    ax_snr.set_xticklabels(v_short, fontsize=8, rotation=25, ha="right")
else:
    ax_snr.text(0.5, 0.5, "No SNR data available", transform=ax_snr.transAxes,
                ha="center", va="center", color="grey")
    ax_snr.set_xticks(range(1, len(phones)+1))
    ax_snr.set_xticklabels(short_labels, fontsize=8, rotation=25, ha="right")
ax_snr.set_ylabel("SNR (dB)", fontsize=9)
ax_snr.set_title("Serving-Cell SNR Distribution per Phone", fontsize=11, fontweight="bold")
ax_snr.grid(axis="y", alpha=0.35)

# ── save ──────────────────────────────────────────────────────────────────
plt.savefig(OUT_PATH, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"Saved → {OUT_PATH}")
plt.show()
