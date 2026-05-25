"""
CMUQ Stationary Dataset – Combined Interactive Dashboard
Run:  python dashboard.py
Open: http://127.0.0.1:8050

Floor selector in the header switches all tabs to the chosen floor.
A "Compare" tab shows side-by-side floor comparisons across all loaded floors.

Tabs: Overview · Floor Map · Signal Metrics · Temporal · Transmitters · Field Explorer · Compare
"""

import os, io, base64, json
import numpy as np
import pandas as pd
from PIL import Image, ImageFilter

_LANCZOS = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS

import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px

# ═══════════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════════
ROOT = os.path.dirname(os.path.abspath(__file__))

FLOOR_CONFIG = {
    1: dict(csv=os.path.join("data", "cmuq", "stationary", "floor1.csv"), img=os.path.join("floor_plans", "cmuq", "floor1.png"),  label="Floor 1"),
    2: dict(csv=os.path.join("data", "cmuq", "stationary", "floor2.csv"), img=os.path.join("floor_plans", "cmuq", "floor2.png"),  label="Floor 2"),
    3: dict(csv=os.path.join("data", "cmuq", "stationary", "floor3.csv"), img=os.path.join("floor_plans", "cmuq", "floor3.png"),  label="Floor 3"),
}

MOBILE_CONFIG = {
    1: dict(csv=os.path.join("data", "cmuq", "mobile", "floor1.csv"), label="Floor 1"),
    2: dict(csv=os.path.join("data", "cmuq", "mobile", "floor2.csv"), label="Floor 2"),
    3: dict(csv=os.path.join("data", "cmuq", "mobile", "floor3.csv"), label="Floor 3"),
}

SENTINEL = 1e8

PHONE_COLORS = {
    "25028RN03A":   "#e41a1c",
    "25028RN03A-2": "#ff7f00",
    "CPH2743":      "#d4b000",
    "HED-LX9":      "#4daf4a",
    "RMX3938":      "#377eb8",
    "SM-A176B":     "#984ea3",
    "itel A675L":   "#a65628",
}

SIGNAL_COLS = {
    "transmitter_rss":   "RSS (dBm)",
    "transmitter_rssi":  "RSSI (dBm)",
    "transmitter_rsrq":  "RSRQ (dB)",
    "transmitter_snr":   "SNR (dB)",
    "transmitter_asu":   "ASU",
    "transmitter_level": "Level (0–4)",
}

METRIC_MAP = {
    "mean_rss":   "RSS (dBm)",
    "mean_rssi":  "RSSI (dBm)",
    "mean_rsrq":  "RSRQ (dB)",
    "mean_snr":   "SNR (dB)",
    "mean_asu":   "ASU",
    "mean_level": "Level (0–4)",
    "n_tx":       "Unique Transmitters",
}

EXPLORER_COLS = [
    "rpNumber","x","y","batteryPower","deviceHeight","hoFlag",
    "infrastructureType","phoneName","scanNumber","servingCellId",
    "transmitter_asu","transmitter_id","transmitter_level",
    "transmitter_rsrq","transmitter_rss","transmitter_rssi",
    "transmitter_snr","transmitter_type","buildingNumber","floorNumber",
]

# ═══════════════════════════════════════════════════════════════════════════
# Data loading & preprocessing
# ═══════════════════════════════════════════════════════════════════════════
def encode_image(path):
    if not os.path.exists(path):
        return None, 800, 600
    img = Image.open(path)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return b64, img.width, img.height


def preprocess(df):
    """Return a bundle of aggregated tables for a floor dataframe."""
    df = df.copy()
    for col in ["transmitter_rssi", "transmitter_snr"]:
        df[col] = df[col].where(df[col].abs() < SENTINEL, other=np.nan)

    serving = df[df["transmitter_id"] == df["servingCellId"]].copy()
    rp_loc  = df.drop_duplicates("rpNumber")[["rpNumber","x","y"]].set_index("rpNumber")
    n_tx    = (df.groupby("rpNumber")["transmitter_id"]
                 .nunique().reset_index().rename(columns={"transmitter_id":"n_tx"}))

    rp_agg = (serving.groupby("rpNumber")
               .agg(mean_rss   =("transmitter_rss",  "mean"),
                    std_rss    =("transmitter_rss",  "std"),
                    mean_rssi  =("transmitter_rssi", "mean"),
                    mean_rsrq  =("transmitter_rsrq", "mean"),
                    mean_snr   =("transmitter_snr",  "mean"),
                    mean_asu   =("transmitter_asu",  "mean"),
                    mean_level =("transmitter_level","mean"))
               .reset_index()
               .merge(rp_loc.reset_index(), on="rpNumber")
               .merge(n_tx, on="rpNumber"))

    rp_phone_agg = (serving.groupby(["rpNumber","phoneName"])
                    .agg(mean_rss   =("transmitter_rss",  "mean"),
                         mean_rssi  =("transmitter_rssi", "mean"),
                         mean_rsrq  =("transmitter_rsrq", "mean"),
                         mean_snr   =("transmitter_snr",  "mean"),
                         mean_asu   =("transmitter_asu",  "mean"),
                         mean_level =("transmitter_level","mean"))
                    .reset_index()
                    .merge(rp_loc.reset_index(), on="rpNumber")
                    .merge(n_tx, on="rpNumber"))

    temporal = (serving.groupby(["rpNumber","phoneName","scanNumber"])
                 .agg(mean_rss  =("transmitter_rss",  "mean"),
                      mean_rssi =("transmitter_rssi", "mean"),
                      mean_rsrq =("transmitter_rsrq", "mean"),
                      mean_snr  =("transmitter_snr",  "mean"))
                 .reset_index())
    temporal_global = temporal.groupby(["phoneName","scanNumber"]).mean(numeric_only=True).reset_index()

    df["ts_dt"] = pd.to_datetime(df["timeStamp"], unit="ms", utc=True)
    timeline = (df.groupby([df["ts_dt"].dt.floor("min"),"phoneName"])
                  .size().reset_index(name="count").rename(columns={"ts_dt":"time"}))

    tx_presence = (df.groupby(["rpNumber","transmitter_id"])
                     .size().unstack(fill_value=0) > 0).astype(int)

    sc_rp = (serving.groupby(["rpNumber","servingCellId"])
              .size().reset_index(name="count"))

    return dict(df=df, serving=serving, rp_agg=rp_agg, rp_phone_agg=rp_phone_agg,
                temporal=temporal, temporal_global=temporal_global,
                timeline=timeline, tx_presence=tx_presence, sc_rp=sc_rp,
                phones=sorted(df["phoneName"].unique()),
                rp_nums=sorted(df["rpNumber"].unique()),
                tx_ids=sorted(df["transmitter_id"].unique()))


def preprocess_mobile(df):
    """Return a bundle of aggregated tables for a mobile floor dataframe."""
    df = df.copy()
    for col in ["transmitter_rssi", "transmitter_snr"]:
        df[col] = df[col].where(df[col].abs() < SENTINEL, other=np.nan)

    serving = df[df["transmitter_id"] == df["servingCellId"]].copy()

    phone_side_agg = (
        serving.groupby(["phoneName", "side"])
        .agg(mean_rss   =("transmitter_rss",  "mean"),
             mean_rssi  =("transmitter_rssi", "mean"),
             mean_rsrq  =("transmitter_rsrq", "mean"),
             mean_snr   =("transmitter_snr",  "mean"),
             mean_asu   =("transmitter_asu",  "mean"),
             mean_level =("transmitter_level","mean"),
             n_scans    =("scanNumber",        "nunique"))
        .reset_index()
    )

    temporal = (
        serving.groupby(["phoneName", "side", "scanNumber"])
        .agg(mean_rss  =("transmitter_rss",  "mean"),
             mean_rssi =("transmitter_rssi", "mean"),
             mean_rsrq =("transmitter_rsrq", "mean"),
             mean_snr  =("transmitter_snr",  "mean"))
        .reset_index()
    )

    df["ts_dt"] = pd.to_datetime(df["timeStamp"], unit="ms", utc=True)
    timeline = (
        df.groupby([df["ts_dt"].dt.floor("min"), "side", "phoneName"])
        .size().reset_index(name="count").rename(columns={"ts_dt": "time"})
    )

    tx_type = (
        df.groupby(["side", "transmitter_type"])
        .size().reset_index(name="count")
    )

    return dict(
        df=df, serving=serving,
        phone_side_agg=phone_side_agg,
        temporal=temporal,
        timeline=timeline,
        tx_type=tx_type,
        phones=sorted(df["phoneName"].unique()),
        sides=sorted(df["side"].unique()),
        tx_ids=sorted(df["transmitter_id"].unique()),
    )


print("Loading floor data …")
FLOORS = {}
for fnum, cfg in FLOOR_CONFIG.items():
    csv_path = os.path.join(ROOT, cfg["csv"])
    if os.path.exists(csv_path):
        print(f"  Floor {fnum}: {csv_path}")
        raw = pd.read_csv(csv_path)
        FLOORS[fnum] = preprocess(raw)
        FLOORS[fnum]["img_b64"], FLOORS[fnum]["img_w"], FLOORS[fnum]["img_h"] = \
            encode_image(os.path.join(ROOT, cfg["img"]))
        print(f"    {len(raw):,} rows | {raw['rpNumber'].nunique()} RPs | "
              f"{raw['phoneName'].nunique()} phones")
    else:
        print(f"  Floor {fnum}: CSV not found ({cfg['csv']}) – floor will show placeholder.")
        FLOORS[fnum] = None

available_floors = [f for f, d in FLOORS.items() if d is not None]
if not available_floors:
    raise RuntimeError("No floor CSV files found. Run the processing scripts first.")

default_floor = available_floors[0]
print("Pre-processing done.\n")

print("Loading mobile floor data …")
MOBILE_FLOORS = {}
for fnum, cfg in MOBILE_CONFIG.items():
    csv_path = os.path.join(ROOT, cfg["csv"])
    if os.path.exists(csv_path):
        print(f"  Mobile Floor {fnum}: {csv_path}")
        raw_m = pd.read_csv(csv_path)
        MOBILE_FLOORS[fnum] = preprocess_mobile(raw_m)
        print(f"    {len(raw_m):,} rows | {raw_m['phoneName'].nunique()} phones | "
              f"sides: {sorted(raw_m['side'].unique())}")
    else:
        MOBILE_FLOORS[fnum] = None
        print(f"  Mobile Floor {fnum}: CSV not found – skipping.")
print("Mobile pre-processing done.\n")

# ═══════════════════════════════════════════════════════════════════════════
# 3-D floor alignment – each row maps floor → RP number at the same physical location
# ═══════════════════════════════════════════════════════════════════════════
_ANCHOR_PAIRS = [
    {1: 20, 2: 20, 3: 20},
    {1: 23, 2: 23, 3: 23},
    {1:  8, 2:  8, 3:  8},
    {1: 55, 2: 55, 3: 35},
    {1: 69, 2: 68, 3: 49},
    {1: 77, 2: 76, 3: 57},
]
_COORDS_DIR  = os.path.join(ROOT, "coordinates", "cmuq")
_Z_SPACING   = 450          # pixel-units between floor levels
_IMG_H       = FLOORS[available_floors[0]]["img_h"]   # 1169

def _load_coords(floor):
    path = os.path.join(_COORDS_DIR, f"floor{floor}.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        d = json.load(f)
    return {int(k): list(v) for k, v in d.items()}


def _affine_fit(src, dst):
    """Least-squares 2×3 affine:  dst ≈ M @ [x, y, 1]ᵀ"""
    s = np.asarray(src, float)
    d = np.asarray(dst, float)
    A = np.hstack([s, np.ones((len(s), 1))])
    return np.vstack([np.linalg.lstsq(A, d[:, i], rcond=None)[0] for i in range(2)])


def _affine_apply(M, xy):
    """Apply 2×3 matrix M to (N,2) array xy.  Returns (N,2)."""
    xy = np.atleast_2d(np.asarray(xy, float))
    return (M[:, :2] @ xy.T + M[:, 2:3]).T


_ref_coords = _load_coords(1)
FLOOR_AFFINE = {}
for _f in available_floors:
    _src = _load_coords(_f)
    _sp, _dp = [], []
    for _pair in _ANCHOR_PAIRS:
        _rp_src = _pair.get(_f)
        _rp_dst = _pair.get(1)
        if _rp_src and _rp_dst and _rp_src in _src and _rp_dst in _ref_coords:
            _sp.append(_src[_rp_src])
            _dp.append(_ref_coords[_rp_dst])
    FLOOR_AFFINE[_f] = _affine_fit(_sp, _dp) if len(_sp) >= 3 else np.eye(2, 3)
print("Affine alignment computed for floors:", list(FLOOR_AFFINE.keys()))


def _transform_rp_agg(floor):
    """Return rp_agg with x3d/y3d (Floor-1 space, y flipped) and z3d added."""
    rpa  = FLOORS[floor]["rp_agg"]
    cols = (["rpNumber", "x", "y"] +
            [c for c in rpa.columns if c.startswith("mean_") or c == "n_tx"])
    d    = rpa[cols].copy()
    xy_t = _affine_apply(FLOOR_AFFINE[floor], d[["x", "y"]].values)
    d["x3d"] = xy_t[:, 0]
    d["y3d"] = _IMG_H - xy_t[:, 1]     # flip y so +y = up in 3-D
    d["z3d"] = float((floor - 1) * _Z_SPACING)
    return d


# ═══════════════════════════════════════════════════════════════════════════
# Figure helpers
# ═══════════════════════════════════════════════════════════════════════════
def floor_scatter(bundle, metric_col, title=""):
    data  = bundle["rp_agg"]
    label = METRIC_MAP.get(metric_col, metric_col)
    valid = data.dropna(subset=[metric_col])
    fig   = go.Figure()
    if bundle["img_b64"]:
        fig.add_layout_image(
            source=bundle["img_b64"], xref="x", yref="y",
            x=0, y=0, sizex=bundle["img_w"], sizey=bundle["img_h"],
            xanchor="left", yanchor="top", sizing="stretch",
            opacity=0.55, layer="below",
        )
    fig.add_trace(go.Scatter(
        x=valid["x"], y=valid["y"],
        mode="markers+text",
        marker=dict(size=16, color=valid[metric_col], colorscale="RdYlGn",
                    showscale=True,
                    colorbar=dict(title=label, thickness=14, len=0.8),
                    line=dict(width=1, color="white")),
        text=valid["rpNumber"].astype(str),
        textfont=dict(size=6.5, color="black"),
        textposition="middle center",
        hovertemplate=f"<b>RP %{{text}}</b><br>{label}: %{{marker.color:.2f}}"
                      "<br>(%{x}, %{y})<extra></extra>",
    ))
    fig.update_xaxes(range=[0, bundle["img_w"]], showticklabels=False,
                     showgrid=False, zeroline=False)
    fig.update_yaxes(range=[bundle["img_h"], 0], showticklabels=False,
                     showgrid=False, zeroline=False)
    fig.update_layout(title=title, height=500,
                      margin=dict(l=0, r=0, t=36, b=0), plot_bgcolor="white")
    return fig


def floor_scatter_phone(bundle, metric_col, phone):
    data  = bundle["rp_phone_agg"]
    label = METRIC_MAP.get(metric_col, metric_col)
    sub   = data[data["phoneName"] == phone].dropna(subset=[metric_col])
    fig   = go.Figure()
    if bundle["img_b64"]:
        fig.add_layout_image(
            source=bundle["img_b64"], xref="x", yref="y",
            x=0, y=0, sizex=bundle["img_w"], sizey=bundle["img_h"],
            xanchor="left", yanchor="top", sizing="stretch",
            opacity=0.55, layer="below",
        )
    fig.add_trace(go.Scatter(
        x=sub["x"], y=sub["y"],
        mode="markers+text",
        marker=dict(size=16, color=sub[metric_col], colorscale="RdYlGn",
                    showscale=True,
                    colorbar=dict(title=label, thickness=14, len=0.8),
                    line=dict(width=1, color="white")),
        text=sub["rpNumber"].astype(str),
        textfont=dict(size=6.5, color="black"),
        textposition="middle center",
        hovertemplate=f"<b>RP %{{text}}</b> [{phone}]<br>{label}: %{{marker.color:.2f}}<extra></extra>",
    ))
    fig.update_xaxes(range=[0, bundle["img_w"]], showticklabels=False,
                     showgrid=False, zeroline=False)
    fig.update_yaxes(range=[bundle["img_h"], 0], showticklabels=False,
                     showgrid=False, zeroline=False)
    fig.update_layout(title=f"{label} – {phone}", height=500,
                      margin=dict(l=0, r=0, t=36, b=0), plot_bgcolor="white")
    return fig


def missing_fig(msg="Floor data not available yet."):
    fig = go.Figure()
    fig.add_annotation(text=msg, xref="paper", yref="paper",
                       x=0.5, y=0.5, showarrow=False, font=dict(size=16, color="grey"))
    fig.update_layout(height=400, plot_bgcolor="white",
                      xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                      yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
    return fig


def short(name):
    return name.replace("25028RN03A-2","RN03A-2").replace("25028RN03A","RN03A")


# ═══════════════════════════════════════════════════════════════════════════
# Layout helpers
# ═══════════════════════════════════════════════════════════════════════════
def card(title, *children, **kwargs):
    return dbc.Card([
        dbc.CardHeader(html.Strong(title)),
        dbc.CardBody(list(children)),
    ], className="mb-3 shadow-sm", **kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# App layout
# ═══════════════════════════════════════════════════════════════════════════
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY],
                title="CMUQ Dashboard")

floor_radio = dbc.RadioItems(
    id="floor-sel",
    options=[{"label": f" Floor {f}", "value": f} for f in available_floors],
    value=default_floor,
    inline=True,
    inputClassName="me-1",
    className="text-white",
)

HEADER = dbc.Navbar(
    dbc.Container([
        html.Span("CMUQ Stationary Dataset Dashboard",
                  className="navbar-brand fw-bold fs-5 text-white me-4"),
        html.Span("Floor:", className="text-white me-2 align-self-center"),
        floor_radio,
        html.Span(id="header-stats", className="text-white-50 small ms-auto align-self-center"),
    ], fluid=True),
    color="primary", dark=True, className="mb-3",
)

FLOOR_METRICS = [{"label": v, "value": k} for k, v in METRIC_MAP.items()]

# ── Tabs ──────────────────────────────────────────────────────────────────
tab_overview  = dbc.Container(id="overview-content",  fluid=True)
tab_floor_map = dbc.Container([
    dbc.Row([
        dbc.Col([html.Label("Phone filter", className="fw-bold"),
                 dcc.Dropdown(id="fmap-phone", value="all", clearable=False,
                              style={"maxWidth":300})], md=4),
        dbc.Col([html.Label("Colour metric", className="fw-bold"),
                 dcc.Dropdown(id="fmap-metric", options=FLOOR_METRICS,
                              value="mean_rss", clearable=False,
                              style={"maxWidth":300})], md=4),
    ], className="mb-3"),
    dbc.Row([
        dbc.Col(dcc.Graph(id="fmap-map"),  md=8),
        dbc.Col(dcc.Graph(id="fmap-hist"), md=4),
    ]),
], fluid=True)

tab_signal = dbc.Container([
    dbc.Row([
        dbc.Col([html.Label("Signal metric", className="fw-bold"),
                 dcc.Dropdown(id="sig-metric",
                              options=[{"label":v,"value":k} for k,v in SIGNAL_COLS.items()],
                              value="transmitter_rss", clearable=False,
                              style={"maxWidth":300})], md=4),
    ], className="mb-3"),
    dbc.Row([dbc.Col(dcc.Graph(id="sig-violin"), md=6),
             dbc.Col(dcc.Graph(id="sig-hist"),   md=6)]),
    dbc.Row([dbc.Col(dcc.Graph(id="sig-rpbar"),  md=12)]),
], fluid=True)

tab_temporal = dbc.Container([
    dbc.Row([
        dbc.Col([html.Label("Metric", className="fw-bold"),
                 dcc.Dropdown(id="temp-metric",
                              options=[{"label":"RSS (dBm)","value":"mean_rss"},
                                       {"label":"RSSI (dBm)","value":"mean_rssi"},
                                       {"label":"RSRQ (dB)","value":"mean_rsrq"},
                                       {"label":"SNR (dB)","value":"mean_snr"}],
                              value="mean_rss", clearable=False,
                              style={"maxWidth":260})], md=3),
        dbc.Col([html.Label("RP filter (empty = all)", className="fw-bold"),
                 dcc.Dropdown(id="temp-rp", options=[], value=[],
                              multi=True, style={"maxWidth":420})], md=6),
    ], className="mb-3"),
    dbc.Row([dbc.Col(dcc.Graph(id="temp-line"),    md=12)]),
    dbc.Row([dbc.Col(dcc.Graph(id="temp-heatmap"), md=12)]),
], fluid=True)

tab_tx = dbc.Container(id="tx-content", fluid=True)

tab_explorer = dbc.Container([
    dbc.Row([
        dbc.Col([html.Label("Select a field", className="fw-bold"),
                 dcc.Dropdown(id="exp-col",
                              options=[{"label":c,"value":c} for c in EXPLORER_COLS],
                              value="transmitter_rss", clearable=False,
                              style={"maxWidth":340})], md=4),
    ], className="mb-3"),
    dbc.Row([dbc.Col(dcc.Graph(id="exp-chart"), md=8)]),
    dbc.Row([dbc.Col(html.Div(id="exp-stats"),  md=8)]),
], fluid=True)

tab_3d = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.Label("Colour metric", className="fw-bold"),
            dcc.Dropdown(id="3d-metric", options=FLOOR_METRICS,
                         value="mean_rss", clearable=False, style={"maxWidth": 260}),
        ], md=3),
        dbc.Col([
            html.Label("Point size", className="fw-bold"),
            dcc.Slider(id="3d-ptsize", min=2, max=12, step=1, value=6,
                       marks={2: "2", 7: "7", 12: "12"},
                       tooltip={"placement": "bottom", "always_visible": False}),
        ], md=2),
        dbc.Col([
            html.Label("Floor plan detail", className="fw-bold"),
            dcc.Slider(id="3d-ds", min=2, max=8, step=1, value=4,
                       marks={2: "fine", 4: "mid", 8: "fast"},
                       tooltip={"placement": "bottom", "always_visible": False}),
        ], md=3),
        dbc.Col([
            html.Label("Options", className="fw-bold"),
            dbc.Checklist(
                id="3d-opts",
                options=[
                    {"label": " Floor plans",  "value": "plans"},
                    {"label": " Anchor lines", "value": "anchors"},
                    {"label": " RP labels",    "value": "labels"},
                ],
                value=["plans", "anchors"],
                inline=True,
            ),
        ], md=4),
    ], className="mb-2"),
    dbc.Row([dbc.Col(dcc.Graph(id="3d-plot", style={"height": "750px"}))]),
], fluid=True)

SIDE_COLORS = {"top": "#2196F3", "bottom": "#FF5722"}

tab_mobile = dbc.Container(id="mobile-content", fluid=True)

tab_compare = dbc.Container(id="compare-content", fluid=True)

all_tabs = [
    dbc.Tab(tab_overview,  label="Overview",        tab_id="tab-overview"),
    dbc.Tab(tab_floor_map, label="Floor Map",        tab_id="tab-floor"),
    dbc.Tab(tab_signal,    label="Signal Metrics",   tab_id="tab-signal"),
    dbc.Tab(tab_temporal,  label="Temporal",         tab_id="tab-temporal"),
    dbc.Tab(tab_tx,        label="Transmitters",     tab_id="tab-tx"),
    dbc.Tab(tab_explorer,  label="Field Explorer",   tab_id="tab-explorer"),
    dbc.Tab(tab_3d,        label="3D View",           tab_id="tab-3d"),
    dbc.Tab(tab_mobile,    label="Mobile Data",        tab_id="tab-mobile"),
    dbc.Tab(tab_compare,   label="Compare Floors",     tab_id="tab-compare"),
]

app.layout = html.Div([
    HEADER,
    dbc.Tabs(all_tabs, id="tabs", active_tab="tab-overview", className="mb-0"),
])

# ═══════════════════════════════════════════════════════════════════════════
# Callbacks
# ═══════════════════════════════════════════════════════════════════════════

def get_bundle(floor):
    return FLOORS.get(int(floor))


# ── Header stats ──────────────────────────────────────────────────────────
@app.callback(Output("header-stats","children"), Input("floor-sel","value"))
def update_header(floor):
    b = get_bundle(floor)
    if b is None: return "CSV not loaded"
    df = b["df"]
    return (f"{len(df):,} rows · {df['rpNumber'].nunique()} RPs · "
            f"{df['phoneName'].nunique()} phones · "
            f"{df['transmitter_id'].nunique()} transmitters")


# ── Overview ──────────────────────────────────────────────────────────────
@app.callback(Output("overview-content","children"), Input("floor-sel","value"))
def update_overview(floor):
    b = get_bundle(floor)
    if b is None:
        return dbc.Alert("Floor data not available – run the processing script first.",
                         color="warning")
    df      = b["df"]
    phones  = b["phones"]
    cfg     = FLOOR_CONFIG[int(floor)]
    short_p = [short(p) for p in phones]

    # KPI cards
    kpis = dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([html.H4(f"{len(df):,}", className="text-primary"),
                                       html.P("Total rows", className="text-muted small")])), width=2),
        dbc.Col(dbc.Card(dbc.CardBody([html.H4(str(df['rpNumber'].nunique()), className="text-success"),
                                       html.P("Reference points", className="text-muted small")])), width=2),
        dbc.Col(dbc.Card(dbc.CardBody([html.H4(str(df['phoneName'].nunique()), className="text-warning"),
                                       html.P("Phones", className="text-muted small")])), width=2),
        dbc.Col(dbc.Card(dbc.CardBody([html.H4(str(df['transmitter_id'].nunique()), className="text-danger"),
                                       html.P("Transmitters", className="text-muted small")])), width=2),
        dbc.Col(dbc.Card(dbc.CardBody([html.H4("300", className="text-info"),
                                       html.P("Scans/RP/phone", className="text-muted small")])), width=2),
        dbc.Col(dbc.Card(dbc.CardBody([html.H4(cfg["label"]),
                                       html.P(f"Building {df['buildingNumber'].iloc[0]}", className="text-muted small")])), width=2),
    ], className="mb-3 g-2")

    fig_phone = px.bar(df.groupby("phoneName").size().reset_index(name="rows"),
                       x="phoneName", y="rows", color="phoneName",
                       color_discrete_map=PHONE_COLORS, title="Rows per Phone",
                       labels={"phoneName":"Phone","rows":"Rows"})
    fig_phone.update_layout(showlegend=False, height=300, margin=dict(t=40,b=60))

    fig_type = px.pie(df.groupby("transmitter_type").size().reset_index(name="count"),
                      names="transmitter_type", values="count",
                      title="Transmitter Type Split",
                      color_discrete_sequence=["#e41a1c","#377eb8","#4daf4a"])
    fig_type.update_layout(height=300, margin=dict(t=40))

    fig_scan = px.histogram(
        df.drop_duplicates(["rpNumber","phoneName","scanNumber"]),
        x="scanNumber", nbins=60, title="Scan Number Distribution",
        labels={"scanNumber":"Scan Number"}, color_discrete_sequence=["#377eb8"])
    fig_scan.update_layout(height=280, margin=dict(t=40))

    timeline = b["timeline"]
    fig_time = px.line(timeline, x="time", y="count", color="phoneName",
                       color_discrete_map=PHONE_COLORS,
                       title="Collection Timeline (scans/min per phone)",
                       labels={"time":"Time","count":"Scans/min","phoneName":"Phone"})
    fig_time.update_layout(height=300, margin=dict(t=40))

    # batteryPower per phone
    bp = df.groupby(["phoneName","rpNumber"])["batteryPower"].mean().reset_index()
    fig_bat = px.box(bp, x="phoneName", y="batteryPower", color="phoneName",
                     color_discrete_map=PHONE_COLORS, title="Battery Power (%) per Phone",
                     labels={"phoneName":"Phone","batteryPower":"Battery (%)"})
    fig_bat.update_layout(showlegend=False, height=300, margin=dict(t=40,b=60))

    const_alert = dbc.Alert([
        html.Strong("Constant fields: "),
        f"floorNumber={df['floorNumber'].iloc[0]} · "
        f"buildingNumber={df['buildingNumber'].iloc[0]} · "
        f"deviceHeight={df['deviceHeight'].iloc[0]} m · "
        "hoFlag=False · infrastructureType='Cellular Ooredoo'",
    ], color="info")

    return html.Div([
        kpis,
        dbc.Row([
            dbc.Col(card("Rows per Phone (phoneName)", dcc.Graph(figure=fig_phone)), md=4),
            dbc.Col(card("Transmitter Type (transmitter_type)", dcc.Graph(figure=fig_type)), md=4),
            dbc.Col(card("Battery Power (batteryPower)", dcc.Graph(figure=fig_bat)), md=4),
        ]),
        dbc.Row([
            dbc.Col(card("Scan Distribution (scanNumber)", dcc.Graph(figure=fig_scan)), md=6),
            dbc.Col(card("Timeline (timeStamp)", dcc.Graph(figure=fig_time)), md=6),
        ]),
        dbc.Row([dbc.Col(const_alert, md=12)]),
    ])


# ── Floor Map – update phone dropdown options ─────────────────────────────
@app.callback(Output("fmap-phone","options"), Output("fmap-phone","value"),
              Input("floor-sel","value"))
def update_phone_opts(floor):
    b = get_bundle(floor)
    if b is None: return [{"label":"All","value":"all"}], "all"
    opts = [{"label":"All phones","value":"all"}] + \
           [{"label":p,"value":p} for p in b["phones"]]
    return opts, "all"


@app.callback(Output("fmap-map","figure"), Output("fmap-hist","figure"),
              Input("floor-sel","value"), Input("fmap-phone","value"),
              Input("fmap-metric","value"))
def update_floor_map(floor, phone, metric):
    b = get_bundle(floor)
    if b is None: return missing_fig(), missing_fig()

    data  = b["rp_agg"] if phone == "all" else \
            b["rp_phone_agg"][b["rp_phone_agg"]["phoneName"]==phone]
    label = METRIC_MAP.get(metric, metric)
    who   = "All Phones" if phone == "all" else phone

    # map
    if phone == "all":
        fig_map = floor_scatter(b, metric, title=f"{label} – {who}")
    else:
        fig_map = floor_scatter_phone(b, metric, phone)

    # histogram of metric
    valid = data[metric].dropna()
    fig_h = px.histogram(x=valid, nbins=30, title=f"{label} distribution ({who})",
                         labels={"x":label}, color_discrete_sequence=["#377eb8"])
    fig_h.update_layout(height=500, margin=dict(t=40))
    return fig_map, fig_h


# ── Signal Metrics ────────────────────────────────────────────────────────
@app.callback(Output("sig-violin","figure"), Output("sig-hist","figure"),
              Output("sig-rpbar","figure"),
              Input("floor-sel","value"), Input("sig-metric","value"))
def update_signal(floor, metric_col):
    b = get_bundle(floor)
    if b is None:
        return missing_fig(), missing_fig(), missing_fig()

    serving = b["serving"]
    phones  = b["phones"]
    label   = SIGNAL_COLS.get(metric_col, metric_col)
    agg_col = "mean_" + metric_col.replace("transmitter_","")

    fig_v = go.Figure()
    for ph in phones:
        vals = serving[serving["phoneName"]==ph][metric_col].dropna()
        fig_v.add_trace(go.Violin(
            y=vals, name=short(ph), box_visible=True, meanline_visible=True,
            fillcolor=PHONE_COLORS.get(ph,"#aaa"), opacity=0.8,
            line_color="black", line_width=0.8))
    fig_v.update_layout(title=f"{label} per Phone", yaxis_title=label,
                        height=400, margin=dict(t=40), violinmode="group")

    fig_h = px.histogram(x=serving[metric_col].dropna(), nbins=60,
                         title=f"Overall {label} Distribution",
                         labels={"x":label}, color_discrete_sequence=["#e41a1c"])
    fig_h.update_layout(height=400, margin=dict(t=40))

    rp_pa = b["rp_phone_agg"]
    if agg_col not in rp_pa.columns:
        fig_bar = missing_fig(f"Aggregated column {agg_col!r} not available.")
    else:
        fig_bar = go.Figure()
        for ph in phones:
            sub = rp_pa[rp_pa["phoneName"]==ph].sort_values("rpNumber")
            fig_bar.add_trace(go.Bar(x=sub["rpNumber"], y=sub[agg_col],
                                     name=short(ph), marker_color=PHONE_COLORS.get(ph,"#aaa")))
        fig_bar.update_layout(title=f"Mean {label} per RP (by Phone)",
                               xaxis_title="RP", yaxis_title=label,
                               barmode="group", height=380, margin=dict(t=40))
    return fig_v, fig_h, fig_bar


# ── Temporal ──────────────────────────────────────────────────────────────
@app.callback(Output("temp-rp","options"), Input("floor-sel","value"))
def update_temp_rp_opts(floor):
    b = get_bundle(floor)
    if b is None: return []
    return [{"label":f"RP {r}","value":r} for r in b["rp_nums"]]


@app.callback(Output("temp-line","figure"), Output("temp-heatmap","figure"),
              Input("floor-sel","value"), Input("temp-metric","value"),
              Input("temp-rp","value"))
def update_temporal(floor, metric, sel_rps):
    b = get_bundle(floor)
    if b is None: return missing_fig(), missing_fig()

    phones = b["phones"]
    tmap   = {"mean_rss":"RSS (dBm)","mean_rssi":"RSSI (dBm)",
              "mean_rsrq":"RSRQ (dB)","mean_snr":"SNR (dB)"}
    label  = tmap.get(metric, metric)
    temp   = b["temporal"]

    if sel_rps:
        base = temp[temp["rpNumber"].isin(sel_rps)]
        agg  = base.groupby(["phoneName","scanNumber"])[metric].mean().reset_index()
        sub  = f"RPs {sel_rps}"
    else:
        agg  = b["temporal_global"].copy()
        sub  = "All RPs (averaged)"

    fig_line = go.Figure()
    for ph in phones:
        s = agg[agg["phoneName"]==ph].sort_values("scanNumber")
        fig_line.add_trace(go.Scatter(x=s["scanNumber"], y=s[metric],
                                      mode="lines", name=short(ph),
                                      line=dict(color=PHONE_COLORS.get(ph,"#aaa"),width=1.5)))
    fig_line.update_layout(title=f"{label} vs Scan Number — {sub}",
                            xaxis_title="Scan Number (1–300)", yaxis_title=label,
                            height=380, margin=dict(t=40))

    buckets = pd.cut(temp["scanNumber"], bins=20, labels=range(1,21)).astype(float)
    temp2   = temp.copy(); temp2["bucket"] = buckets
    hm      = temp2.groupby(["rpNumber","bucket"])[metric].mean().unstack()
    fig_hm  = go.Figure(go.Heatmap(
        z=hm.values,
        x=[f"~{int((b-1)*15)+1}" for b in hm.columns],
        y=[str(r) for r in hm.index],
        colorscale="RdYlGn",
        colorbar=dict(title=label, thickness=12),
        hovertemplate="RP %{y} · Scan~%{x}<br>%{z:.1f}<extra></extra>",
    ))
    fig_hm.update_layout(title=f"{label} Heatmap: RP × Scan Bucket",
                          xaxis_title="Scan (~number)", yaxis_title="RP",
                          height=600, margin=dict(t=40),
                          yaxis=dict(tickfont=dict(size=8)))
    return fig_line, fig_hm


# ── Transmitters tab ──────────────────────────────────────────────────────
@app.callback(Output("tx-content","children"), Input("floor-sel","value"))
def update_tx(floor):
    b = get_bundle(floor)
    if b is None:
        return dbc.Alert("Floor data not available.", color="warning")

    df      = b["df"]
    phones  = b["phones"]
    sc_rp   = b["sc_rp"]
    tx_pres = b["tx_presence"]

    tx_counts = (df.groupby(["transmitter_id","transmitter_type"])
                   .size().reset_index(name="count").sort_values("count"))
    fig_bar = px.bar(tx_counts, x="count", y=tx_counts["transmitter_id"].astype(str),
                     color="transmitter_type",
                     color_discrete_map={"GSM":"#e41a1c","LTE":"#377eb8"},
                     orientation="h", title="Observations per Transmitter ID",
                     labels={"y":"Transmitter ID","count":"Observations","transmitter_type":"Type"})
    fig_bar.update_layout(height=max(300, len(b["tx_ids"])*26), margin=dict(t=40))

    type_phone = df.groupby(["phoneName","transmitter_type"]).size().reset_index(name="count")
    fig_type = px.bar(type_phone, x="phoneName", y="count",
                      color="transmitter_type",
                      color_discrete_map={"GSM":"#e41a1c","LTE":"#377eb8"},
                      title="Transmitter Type per Phone",
                      labels={"phoneName":"Phone","count":"Rows","transmitter_type":"Type"},
                      barmode="stack")
    fig_type.update_layout(height=320, margin=dict(t=40,b=60))

    sc_rp2 = sc_rp.copy(); sc_rp2["cellLabel"] = sc_rp2["servingCellId"].astype(str)
    fig_sc = px.bar(sc_rp2, x="rpNumber", y="count", color="cellLabel",
                    title="Serving Cell per RP (servingCellId)",
                    labels={"rpNumber":"RP","count":"Observations","cellLabel":"Cell ID"})
    fig_sc.update_layout(height=340, margin=dict(t=40))

    fig_hm = go.Figure(go.Heatmap(
        z=tx_pres.values,
        x=[str(c) for c in tx_pres.columns],
        y=[str(r) for r in tx_pres.index],
        colorscale=[[0,"#f0f0f0"],[1,"#1a6faf"]],
        showscale=False,
        hovertemplate="RP %{y} · Tx %{x}<br>Seen: %{z}<extra></extra>",
    ))
    fig_hm.update_layout(
        title="RP × Transmitter Presence (transmitter_id × rpNumber)",
        height=600, margin=dict(t=40),
        xaxis=dict(title="Transmitter ID", tickangle=-45, tickfont=dict(size=9)),
        yaxis=dict(title="RP Number", tickfont=dict(size=8)),
    )

    return html.Div([
        dbc.Row([
            dbc.Col(card("Observations per Transmitter", dcc.Graph(figure=fig_bar)), md=5),
            dbc.Col(card("Type per Phone", dcc.Graph(figure=fig_type)), md=4),
            dbc.Col(card("Serving Cell per RP", dcc.Graph(figure=fig_sc)), md=3),
        ]),
        dbc.Row([dbc.Col(card("RP × Transmitter Presence Matrix",
                              dcc.Graph(figure=fig_hm)), md=12)]),
    ])


# ── Field Explorer ────────────────────────────────────────────────────────
@app.callback(Output("exp-chart","figure"), Output("exp-stats","children"),
              Input("floor-sel","value"), Input("exp-col","value"))
def update_explorer(floor, col):
    b = get_bundle(floor)
    if b is None: return missing_fig(), ""

    df = b["df"]
    if col not in df.columns: return missing_fig("Column not found."), ""
    series  = df[col]
    n_unique = series.nunique()

    if pd.api.types.is_bool_dtype(series):
        counts = series.value_counts().reset_index()
        counts.columns = [col, "count"]
        fig = px.pie(counts, names=col, values="count", title=f"{col} — Boolean")
    elif pd.api.types.is_numeric_dtype(series) and n_unique > 20:
        clean = series.dropna()
        clean = clean[clean.abs() < SENTINEL]
        fig = px.histogram(x=clean, nbins=60, title=f"{col} — Histogram",
                           labels={"x":col}, color_discrete_sequence=["#1f77b4"])
    else:
        counts = series.value_counts().head(30).reset_index()
        counts.columns = [col, "count"]
        fig = px.bar(counts, x=col, y="count", title=f"{col} — Value Counts (top 30)",
                     color_discrete_sequence=["#1f77b4"])
        fig.update_xaxes(tickangle=-30)

    fig.update_layout(height=400, margin=dict(t=40))

    clean_s = series.dropna()
    if pd.api.types.is_numeric_dtype(series):
        clean_s = clean_s[clean_s.abs() < SENTINEL]
    stats = {"Count":f"{len(series):,}","Non-null":f"{series.notna().sum():,}",
             "Unique":f"{n_unique:,}","dtype":str(series.dtype)}
    if pd.api.types.is_numeric_dtype(series):
        stats.update({"Min":f"{clean_s.min():.3g}","Max":f"{clean_s.max():.3g}",
                      "Mean":f"{clean_s.mean():.3g}","Std":f"{clean_s.std():.3g}",
                      "Median":f"{clean_s.median():.3g}"})
    else:
        stats["Top value"] = str(clean_s.mode().iloc[0]) if len(clean_s) else "N/A"

    table = dbc.Table(
        [html.Tbody([html.Tr([html.Th(k, style={"width":"160px"}), html.Td(v)])
                     for k,v in stats.items()])],
        bordered=True, size="sm", className="mt-2", style={"maxWidth":"500px"})
    return fig, table

# ── 3-D View ──────────────────────────────────────────────────────────────
@app.callback(
    Output("3d-plot",  "figure"),
    Input("3d-metric", "value"),
    Input("3d-ptsize", "value"),
    Input("3d-ds",     "value"),
    Input("3d-opts",   "value"),
)
def update_3d(metric_col, pt_size, ds_factor, opts):
    opts  = opts or []
    label = METRIC_MAP.get(metric_col, metric_col)
    FCOLS = {1: "#377eb8", 2: "#e41a1c", 3: "#4daf4a"}
    fmt   = ".0f" if metric_col == "n_tx" else ".2f"

    # Pre-transform all floors once
    fdata = {f: _transform_rp_agg(f) for f in available_floors if FLOORS[f] is not None}

    # Global colour range
    all_v = pd.concat([fdata[f][metric_col].dropna() for f in fdata])
    cmin, cmax = float(all_v.min()), float(all_v.max())

    traces = []

    # ── Floor plan surfaces ───────────────────────────────────────────────
    if "plans" in opts:
        for f in available_floors:
            if FLOORS[f] is None:
                continue
            img_path = os.path.join(ROOT, FLOOR_CONFIG[f]["img"])
            if not os.path.exists(img_path):
                continue
            img  = Image.open(img_path).convert("L")
            W, H = img.width, img.height
            ds   = max(1, int(ds_factor))
            img_s = img.resize((W // ds, H // ds), _LANCZOS)
            dW, dH = img_s.size
            arr  = np.array(img_s, dtype=float) / 255.0      # (dH, dW)
            # Binarize: dark pixels (walls) → 1, light (open) → 0
            arr  = (arr < 0.75).astype(float)
            xs   = np.linspace(0, W, dW)
            ys   = np.linspace(0, H, dH)
            Xg, Yg = np.meshgrid(xs, ys)                     # each (dH, dW)
            pts  = np.column_stack([Xg.ravel(), Yg.ravel()])
            pt   = _affine_apply(FLOOR_AFFINE[f], pts)
            Xt   = pt[:, 0].reshape(dH, dW)
            Yt   = (_IMG_H - pt[:, 1]).reshape(dH, dW)
            Zt   = np.full((dH, dW), (f - 1) * _Z_SPACING)
            traces.append(go.Surface(
                x=Xt, y=Yt, z=Zt,
                surfacecolor=arr,
                colorscale=[[0, "#f0f0f0"], [1, "#111111"]],
                showscale=False, opacity=0.65,
                name=f"Floor {f} plan", showlegend=True,
                hoverinfo="skip",
            ))

    # ── RP scatter3d per floor ────────────────────────────────────────────
    n_fl = len(available_floors)
    for fi, f in enumerate(available_floors):
        if f not in fdata:
            continue
        d  = fdata[f].dropna(subset=[metric_col])
        v  = d[metric_col].values
        hover = [
            f"<b>RP {rp}</b>  Floor {f}<br>{label}: {val:{fmt}}"
            for rp, val in zip(d["rpNumber"].values, v)
        ]
        mode = "markers+text" if "labels" in opts else "markers"
        txt  = d["rpNumber"].astype(str).tolist() if "labels" in opts else []
        cb_kw = ({"colorbar": dict(title=label, thickness=14, len=0.55, x=1.02)}
                 if fi == n_fl - 1 else {})
        traces.append(go.Scatter3d(
            x=d["x3d"].values, y=d["y3d"].values, z=d["z3d"].values,
            mode=mode,
            text=txt,
            textposition="top center",
            textfont=dict(size=8, color=FCOLS.get(f, "#333")),
            marker=dict(
                size=pt_size, color=v,
                colorscale="RdYlGn", cmin=cmin, cmax=cmax,
                showscale=(fi == n_fl - 1),
                line=dict(width=1, color="rgba(255,255,255,0.6)"),
                **cb_kw,
            ),
            name=f"Floor {f}",
            hovertext=hover, hoverinfo="text",
        ))

    # ── Anchor vertical lines ─────────────────────────────────────────────
    if "anchors" in opts:
        for i, pair in enumerate(_ANCHOR_PAIRS):
            xs_a, ys_a, zs_a = [], [], []
            for f in available_floors:
                if f not in fdata:
                    continue
                rp = pair.get(f)
                if rp is None:
                    continue
                row = fdata[f][fdata[f]["rpNumber"] == rp]
                if row.empty:
                    continue
                xs_a.append(float(row["x3d"].iloc[0]))
                ys_a.append(float(row["y3d"].iloc[0]))
                zs_a.append(float(row["z3d"].iloc[0]))
            if len(xs_a) < 2:
                continue
            rp_label = "/".join(str(pair.get(f, "?")) for f in available_floors)
            traces.append(go.Scatter3d(
                x=xs_a, y=ys_a, z=zs_a,
                mode="lines",
                line=dict(color="gold", width=4, dash="dot"),
                name="Anchor RPs" if i == 0 else f"RP {rp_label}",
                showlegend=(i == 0),
                hoverinfo="skip",
            ))

    # ── Layout ────────────────────────────────────────────────────────────
    fig = go.Figure(traces)
    fig.update_layout(
        title=f"3D Building View – {label}",
        scene=dict(
            xaxis=dict(title="", showbackground=False, gridcolor="#ddd",
                       range=[0, 1650], showticklabels=False),
            yaxis=dict(title="", showbackground=False, gridcolor="#ddd",
                       range=[0, _IMG_H], showticklabels=False),
            zaxis=dict(
                title="Floor level",
                showbackground=True,
                backgroundcolor="rgba(220,230,245,0.3)",
                gridcolor="#ccc",
                tickvals=[(f - 1) * _Z_SPACING for f in available_floors],
                ticktext=[f"Floor {f}" for f in available_floors],
            ),
            aspectmode="manual",
            aspectratio=dict(x=1.4, y=1.0, z=0.55),
            camera=dict(eye=dict(x=-1.5, y=-1.8, z=1.1)),
        ),
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.85)"),
        margin=dict(l=0, r=80, t=44, b=0),
        paper_bgcolor="white",
    )
    return fig

# ── Mobile Data ──────────────────────────────────────────────────────────
@app.callback(Output("mobile-content", "children"), Input("floor-sel", "value"))
def update_mobile(floor):
    mb = MOBILE_FLOORS.get(int(floor))
    if mb is None:
        return dbc.Alert(
            "Mobile data not available for this floor – run process_mobile.py first.",
            color="warning", className="mt-3")

    df     = mb["df"]
    srvg   = mb["serving"]
    phones = mb["phones"]
    sides  = mb["sides"]
    psa    = mb["phone_side_agg"]
    temp   = mb["temporal"]
    tl     = mb["timeline"]

    # ── KPI row ──────────────────────────────────────────────────────────
    top_n   = (df["side"] == "top").sum()
    bot_n   = (df["side"] == "bottom").sum()
    kpis = dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([html.H4(f"{len(df):,}", className="text-primary"),
                                       html.P("Total rows", className="text-muted small")])), width=2),
        dbc.Col(dbc.Card(dbc.CardBody([html.H4(str(len(phones)), className="text-success"),
                                       html.P("Phones", className="text-muted small")])), width=2),
        dbc.Col(dbc.Card(dbc.CardBody([html.H4(f"{df['transmitter_id'].nunique()}", className="text-danger"),
                                       html.P("Transmitters", className="text-muted small")])), width=2),
        dbc.Col(dbc.Card(dbc.CardBody([html.H4(f"{top_n:,}", className="text-info"),
                                       html.P("Top-side rows", className="text-muted small")])), width=2),
        dbc.Col(dbc.Card(dbc.CardBody([html.H4(f"{bot_n:,}", className="text-warning"),
                                       html.P("Bottom-side rows", className="text-muted small")])), width=2),
        dbc.Col(dbc.Card(dbc.CardBody([html.H4(f"{df['scanNumber'].nunique()}", className="text-secondary"),
                                       html.P("Unique scans", className="text-muted small")])), width=2),
    ], className="mb-3 g-2")

    # ── RSS violin: top vs bottom ─────────────────────────────────────────
    fig_side_v = go.Figure()
    for s in sides:
        vals = srvg[srvg["side"] == s]["transmitter_rss"].dropna()
        fig_side_v.add_trace(go.Violin(
            y=vals, name=s.capitalize(),
            box_visible=True, meanline_visible=True,
            fillcolor=SIDE_COLORS.get(s, "#aaa"), opacity=0.8,
            line_color="black", line_width=0.8))
    fig_side_v.update_layout(
        title="RSS by Side (serving cell)",
        yaxis_title="RSS (dBm)", height=380, margin=dict(t=40))

    # ── RSS violin: per phone ─────────────────────────────────────────────
    fig_phone_v = go.Figure()
    for ph in phones:
        vals = srvg[srvg["phoneName"] == ph]["transmitter_rss"].dropna()
        fig_phone_v.add_trace(go.Violin(
            y=vals, name=short(ph),
            box_visible=True, meanline_visible=True,
            fillcolor=PHONE_COLORS.get(ph, "#aaa"), opacity=0.8,
            line_color="black", line_width=0.8))
    fig_phone_v.update_layout(
        title="RSS by Phone (serving cell)",
        yaxis_title="RSS (dBm)", height=380, margin=dict(t=40))

    # ── Scan timeline: RSS vs scan number per phone×side ──────────────────
    fig_scan = go.Figure()
    line_dash = {"top": "solid", "bottom": "dash"}
    for s in sides:
        for ph in phones:
            sub = (temp[(temp["phoneName"] == ph) & (temp["side"] == s)]
                   .sort_values("scanNumber"))
            if sub.empty:
                continue
            fig_scan.add_trace(go.Scatter(
                x=sub["scanNumber"], y=sub["mean_rss"],
                mode="lines",
                name=f"{short(ph)} ({s})",
                line=dict(color=PHONE_COLORS.get(ph, "#aaa"),
                          width=1.4, dash=line_dash.get(s, "solid")),
                legendgroup=short(ph),
                hovertemplate=f"<b>{short(ph)}</b> [{s}]<br>Scan %{{x}}: %{{y:.1f}} dBm<extra></extra>",
            ))
    fig_scan.update_layout(
        title="Mean RSS vs Scan Number (solid=top, dashed=bottom)",
        xaxis_title="Scan Number", yaxis_title="RSS (dBm)",
        height=420, margin=dict(t=40),
        legend=dict(font=dict(size=9)))

    # ── Collection timeline ───────────────────────────────────────────────
    fig_tl = go.Figure()
    for s in sides:
        for ph in phones:
            sub = tl[(tl["side"] == s) & (tl["phoneName"] == ph)].sort_values("time")
            if sub.empty:
                continue
            fig_tl.add_trace(go.Scatter(
                x=sub["time"], y=sub["count"],
                mode="lines",
                name=f"{short(ph)} ({s})",
                line=dict(color=PHONE_COLORS.get(ph, "#aaa"),
                          dash=line_dash.get(s, "solid"), width=1.4),
                legendgroup=short(ph),
                hovertemplate=f"{short(ph)} [{s}]<br>%{{x}}: %{{y}} scans/min<extra></extra>",
            ))
    fig_tl.update_layout(
        title="Collection Timeline (scans/min by phone & side)",
        xaxis_title="Time (UTC)", yaxis_title="Scans/min",
        height=340, margin=dict(t=40),
        legend=dict(font=dict(size=9)))

    # ── Transmitter type per side ─────────────────────────────────────────
    tx_t = mb["tx_type"]
    fig_tx = px.bar(
        tx_t, x="side", y="count", color="transmitter_type",
        barmode="stack",
        color_discrete_map={"GSM": "#e41a1c", "LTE": "#377eb8"},
        title="Transmitter Type per Side",
        labels={"side": "Side", "count": "Rows", "transmitter_type": "Type"},
    )
    fig_tx.update_layout(height=320, margin=dict(t=40))

    # ── Mean RSS per phone per side (grouped bar) ─────────────────────────
    fig_bar = px.bar(
        psa, x="phoneName", y="mean_rss", color="side",
        color_discrete_map=SIDE_COLORS,
        barmode="group",
        title="Mean RSS per Phone & Side (serving cell)",
        labels={"phoneName": "Phone", "mean_rss": "Mean RSS (dBm)", "side": "Side"},
    )
    fig_bar.update_xaxes(tickangle=-30)
    fig_bar.update_layout(height=320, margin=dict(t=40, b=70))

    return html.Div([
        kpis,
        dbc.Row([
            dbc.Col(card("RSS Distribution by Side",  dcc.Graph(figure=fig_side_v)),  md=6),
            dbc.Col(card("RSS Distribution by Phone", dcc.Graph(figure=fig_phone_v)), md=6),
        ]),
        dbc.Row([
            dbc.Col(card("Mean RSS vs Scan Number", dcc.Graph(figure=fig_scan)), md=12),
        ]),
        dbc.Row([
            dbc.Col(card("Mean RSS per Phone & Side",  dcc.Graph(figure=fig_bar)), md=6),
            dbc.Col(card("Transmitter Type per Side",  dcc.Graph(figure=fig_tx)),  md=3),
            dbc.Col(card("Collection Timeline",        dcc.Graph(figure=fig_tl)),  md=3),
        ]),
    ])


# ── Compare Floors ────────────────────────────────────────────────────────
@app.callback(Output("compare-content","children"), Input("tabs","active_tab"))
def update_compare(active_tab):
    if active_tab != "tab-compare":
        return html.Div()

    if len(available_floors) < 2:
        return dbc.Alert(
            "Only one floor loaded. Process more floor data first to enable comparisons.",
            color="warning", className="mt-3")

    fl = available_floors  # e.g. [1, 2, 3]
    md_w = max(3, 12 // len(fl))  # e.g. 4 for 3 floors, 6 for 2

    # Side-by-side floor maps (RSS)
    map_cols = [
        dbc.Col(card(f"Floor {f} – Mean RSS Map",
                     dcc.Graph(figure=floor_scatter(FLOORS[f], "mean_rss",
                                                    title=f"Floor {f} – Mean RSS"))),
                md=md_w)
        for f in fl
    ]

    # RSS violin all floors
    fig_box = go.Figure()
    for f in fl:
        vals = FLOORS[f]["serving"]["transmitter_rss"].dropna()
        fig_box.add_trace(go.Violin(
            y=vals, name=f"Floor {f}",
            box_visible=True, meanline_visible=True, opacity=0.8))
    floor_label = " vs ".join(f"Floor {f}" for f in fl)
    fig_box.update_layout(title=f"Serving-Cell RSS: {floor_label}",
                           yaxis_title="RSS (dBm)", height=380, margin=dict(t=40))

    # Unique transmitters distribution
    fig_tx = go.Figure()
    for f in fl:
        fig_tx.add_trace(go.Histogram(
            x=FLOORS[f]["rp_agg"]["n_tx"], name=f"Floor {f}",
            opacity=0.65, nbinsx=15, histnorm="percent"))
    fig_tx.update_layout(title=f"Unique Transmitters per RP: {floor_label}",
                          barmode="overlay", xaxis_title="# Transmitters",
                          yaxis_title="% of RPs", height=340, margin=dict(t=40))

    # Transmitter ID overlap (works for any number of floors)
    tx_sets = {f: set(FLOORS[f]["df"]["transmitter_id"].unique()) for f in fl}
    all_union = set.union(*tx_sets.values())
    all_common = set.intersection(*tx_sets.values())

    overlap_x, overlap_y = [], []
    for f in fl:
        others = set.union(*[tx_sets[g] for g in fl if g != f])
        overlap_x.append(f"Only F{f}")
        overlap_y.append(len(tx_sets[f] - others))
    for i, fi in enumerate(fl):
        for fj in fl[i+1:]:
            pair_only = (tx_sets[fi] & tx_sets[fj]) - set.union(
                *([tx_sets[g] for g in fl if g not in (fi, fj)] or [set()]))
            overlap_x.append(f"F{fi}+F{fj} only")
            overlap_y.append(len(pair_only))
    overlap_x.append("All floors")
    overlap_y.append(len(all_common))

    fig_venn = px.bar(x=overlap_x, y=overlap_y, color=overlap_x,
                      title="Transmitter ID Overlap", labels={"x":"","y":"Count"})
    fig_venn.update_layout(showlegend=False, height=320, margin=dict(t=40))

    info_rows = []
    for f in fl:
        others = set.union(*[tx_sets[g] for g in fl if g != f])
        unique = sorted(tx_sets[f] - others)
        info_rows.append(html.Tr([html.Th(f"Only Floor {f}"), html.Td(str(unique))]))
    info_rows.append(html.Tr([html.Th("Common to all"), html.Td(str(sorted(all_common)))]))

    return html.Div([
        dbc.Row(map_cols),
        dbc.Row([
            dbc.Col(card("RSS Distribution Comparison",    dcc.Graph(figure=fig_box)), md=6),
            dbc.Col(card("Unique TX per RP Distribution",   dcc.Graph(figure=fig_tx)), md=6),
        ]),
        dbc.Row([
            dbc.Col(card("Transmitter ID Overlap (transmitter_id)",
                         dcc.Graph(figure=fig_venn)), md=5),
            dbc.Col(dbc.Alert(
                dbc.Table([html.Tbody(info_rows)], bordered=True, size="sm"),
                color="info"), md=7),
        ]),
    ])


# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Starting dashboard at  http://127.0.0.1:8050")
    app.run(debug=True)
