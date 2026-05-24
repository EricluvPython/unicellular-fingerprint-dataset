"""
Interactive coordinate assignment – CMUQ Floor 2.
Identical workflow to assign_coordinates_f1.py but targets SF-Generic.

Phase 1: OpenCV detects red circles automatically (already cached in
         detected_circles_f2.json / detected_circles_f2.png from prior run).
Phase 2: Click circles in RP order (1 → 84).  Each click snaps to the
         nearest unassigned detected circle.

Controls: LEFT-CLICK = assign next RP  |  u = undo  |  s = save & exit  |  q = quit

Output: coordinates_f2.json   – {rp_str: [pixel_x, pixel_y]}
"""

import json, os, sys
import numpy as np
import cv2
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

ROOT            = os.path.dirname(os.path.abspath(__file__))
PDF_PATH        = os.path.join(ROOT, "raw", "SF-Generic(2).pdf")
PNG_PATH        = os.path.join(ROOT, "floor_plans", "SF-Generic.png")
COORD_PATH      = os.path.join(ROOT, "coordinates", "coordinates_f2.json")
CIRCLES_JSON    = os.path.join(ROOT, "coordinates", "detected_circles_f2.json")
CIRCLES_PREVIEW = os.path.join(ROOT, "floor_plans", "detected_circles_f2.png")

TOTAL_RPS = 84

# ── PDF → PNG ───────────────────────────────────────────────────────────────
def pdf_to_png(pdf_path, png_path, dpi=150):
    import fitz
    doc = fitz.open(pdf_path)
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72), alpha=False)
    pix.save(png_path)
    doc.close()
    print(f"Floor plan rasterised → {png_path}")

# ── detect red circles ──────────────────────────────────────────────────────
def detect_red_circles(img_bgr, min_area=15, max_area=3000, min_circ=0.55):
    hsv  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    m1   = cv2.inRange(hsv, np.array([0,   80, 60]), np.array([15,  255, 255]))
    m2   = cv2.inRange(hsv, np.array([155,  80, 60]), np.array([180, 255, 255]))
    mask = cv2.bitwise_or(m1, m2)
    k    = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  k, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    circles = []
    for cnt in cnts:
        a = cv2.contourArea(cnt); p = cv2.arcLength(cnt, True)
        if a < min_area or a > max_area or p == 0: continue
        if 4*np.pi*a/p**2 < min_circ: continue
        M = cv2.moments(cnt)
        if M["m00"] == 0: continue
        circles.append((int(M["m10"]/M["m00"]), int(M["m01"]/M["m00"])))
    circles.sort(key=lambda c: (c[1], c[0]))
    return circles

def make_preview(img_bgr, circles):
    preview = img_bgr.copy()
    for idx, (cx, cy) in enumerate(circles):
        cv2.circle(preview, (cx, cy), 10, (0, 200, 0), 2)
        cv2.putText(preview, str(idx), (cx+6, cy-6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 140, 0), 1, cv2.LINE_AA)
    cv2.imwrite(CIRCLES_PREVIEW, preview)
    return cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)

def save_detected(circles):
    with open(CIRCLES_JSON, "w") as f: json.dump(circles, f, indent=2)
    print(f"Detected {len(circles)} circles → {CIRCLES_JSON}")

def load_detected():
    with open(CIRCLES_JSON) as f: return [tuple(c) for c in json.load(f)]

def load_coords():
    if not os.path.exists(COORD_PATH): return {}
    with open(COORD_PATH) as f: raw = json.load(f)
    return {int(k): v for k, v in raw.items()}

def save_coords(coords):
    with open(COORD_PATH, "w") as f:
        json.dump({str(k): v for k, v in coords.items()}, f, indent=2)
    print(f"Saved → {COORD_PATH}  ({len(coords)}/{TOTAL_RPS} RPs)")

# ── interactive ordering ────────────────────────────────────────────────────
def run_ordering(img_rgb, circles, coords):
    remaining = [rp for rp in range(1, TOTAL_RPS+1) if rp not in coords]
    if not remaining:
        print("All RPs already assigned.")
        return coords

    used = set()
    for rp, (px, py) in coords.items():
        try: used.add(circles.index((px, py)))
        except ValueError: pass

    state = {"idx": 0, "saved": False}

    def cur(): return remaining[state["idx"]] if state["idx"] < len(remaining) else None
    def free(): return [(i, c) for i, c in enumerate(circles) if i not in used]

    def nearest(x, y):
        fc = free()
        if not fc: return None, None
        _, best_i, best_c = min((((x-c[0])**2+(y-c[1])**2), i, c) for i, c in fc)
        return best_i, best_c

    def refresh():
        ax.cla(); ax.imshow(img_rgb); ax.axis("off")
        rp = cur()
        title = (f"Click on RP {rp}  ({state['idx']+1}/{len(remaining)})\n"
                 "[u] undo  ·  [s] save & exit  ·  [q] quit"
                 if rp else "All RPs assigned! Press [s] to save.")
        ax.set_title(title, fontsize=12,
                     color="crimson" if rp else "green", fontweight="bold")
        for assigned_rp, (px, py) in coords.items():
            ax.plot(px, py, "m*", markersize=9)
            ax.annotate(str(assigned_rp), (px, py), fontsize=7, color="darkmagenta",
                        ha="center", va="bottom", xytext=(0,8), textcoords="offset points")
        fig.canvas.draw_idle()

    def on_click(event):
        if event.inaxes is not ax or event.button != 1: return
        rp = cur()
        if rp is None: return
        di, (cx, cy) = nearest(event.xdata, event.ydata)
        if di is None: return
        coords[rp] = [cx, cy]; used.add(di)
        print(f"  RP {rp:3d} ← det#{di:3d} pixel ({cx},{cy})")
        state["idx"] += 1
        if state["idx"] >= len(remaining):
            save_coords(coords); state["saved"] = True
        refresh()

    def on_key(event):
        if event.key == "s":
            save_coords(coords); state["saved"] = True; plt.close(fig)
        elif event.key == "q":
            print("Quit."); plt.close(fig)
        elif event.key == "u" and state["idx"] > 0:
            state["idx"] -= 1
            rp_undo = remaining[state["idx"]]
            prev = coords.pop(rp_undo, None)
            if prev:
                try: used.discard(circles.index(tuple(prev)))
                except ValueError: pass
            print(f"  Undone RP {rp_undo}"); refresh()

    fig, ax = plt.subplots(figsize=(18, 13))
    fig.canvas.manager.set_window_title("CMUQ Floor 2 – Coordinate Assignment")
    fig.canvas.mpl_connect("button_press_event", on_click)
    fig.canvas.mpl_connect("key_press_event", on_key)
    refresh(); plt.tight_layout(); plt.show()

    if not state["saved"] and coords:
        if input("Save progress? [y/n]: ").strip().lower() == "y":
            save_coords(coords)
    return coords

# ── main ────────────────────────────────────────────────────────────────────
def main():
    if not os.path.exists(PNG_PATH):
        if not os.path.exists(PDF_PATH): sys.exit(f"ERROR: {PDF_PATH} not found.")
        print("Converting PDF → PNG …"); pdf_to_png(PDF_PATH, PNG_PATH)

    img_bgr = cv2.imread(PNG_PATH)
    if img_bgr is None: sys.exit(f"ERROR: could not read {PNG_PATH}")

    circles = None
    if os.path.exists(CIRCLES_JSON):
        circles = load_detected()
        print(f"Loaded {len(circles)} cached circles.")
        if input("Re-run detection? [y/n] (default n): ").strip().lower() == "y":
            circles = None

    if circles is None:
        print("Detecting red circles …")
        circles = detect_red_circles(img_bgr)
        save_detected(circles)

    print(f"Using {len(circles)} circles.")
    if len(circles) != TOTAL_RPS:
        print(f"WARNING: expected {TOTAL_RPS}, got {len(circles)}. Check {CIRCLES_PREVIEW}.")

    img_rgb = make_preview(img_bgr, circles)
    coords  = load_coords()
    if coords: print(f"Resuming – {len(coords)}/{TOTAL_RPS} already assigned.")
    run_ordering(img_rgb, circles, coords)

if __name__ == "__main__":
    main()
