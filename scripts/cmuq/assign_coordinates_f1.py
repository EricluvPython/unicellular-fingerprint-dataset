"""
Interactive coordinate assignment tool for CMUQ Floor 1 stationary dataset.

Phase 1 – Auto-detection  (runs automatically)
    OpenCV finds all red circles on the floor plan and saves them as
    detected_circles_f1.png (annotated preview) and detected_circles_f1.json.

Phase 2 – RP ordering  (your minimal work)
    The annotated image opens in a window showing every detected circle with a
    temporary detection index (0, 1, 2 …).
    Click the circles IN RP ORDER: first click = RP 1, second click = RP 2 …
    Each click snaps automatically to the nearest unassigned detected circle,
    so you don't need to be pixel-precise.

Controls:
    LEFT-CLICK  → assign next RP to the nearest detected circle
    u           → undo last assignment
    s           → save & exit
    q           → quit without saving

Output:
    coordinates_f1.json          dict mapping RP number (str) → [pixel_x, pixel_y]
    FF-Generic.png               rasterized floor plan (one-time)
    detected_circles_f1.png      annotated detection preview
    detected_circles_f1.json     raw list of detected circle centres
"""

import json
import os
import sys
import numpy as np
import cv2
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

# ── paths ──────────────────────────────────────────────────────────────────
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PDF_PATH        = os.path.join(ROOT, "raw", "FF-Generic(2).pdf")
PNG_PATH        = os.path.join(ROOT, "floor_plans", "cmuq", "floor1.png")
COORD_PATH      = os.path.join(ROOT, "coordinates", "cmuq", "floor1.json")
CIRCLES_JSON    = os.path.join(ROOT, "coordinates", "cmuq", "detected_circles_f1.json")
CIRCLES_PREVIEW = os.path.join(ROOT, "floor_plans", "cmuq", "detected_circles_f1.png")

TOTAL_RPS = 84

# ── PDF → PNG ───────────────────────────────────────────────────────────────
def pdf_to_png(pdf_path, png_path, dpi=150):
    import fitz
    doc = fitz.open(pdf_path)
    page = doc[0]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    pix.save(png_path)
    doc.close()
    print(f"Floor plan rasterised → {png_path}")

# ── detect red circles with OpenCV ─────────────────────────────────────────
def detect_red_circles(img_bgr,
                        min_area=15,
                        max_area=3000,
                        min_circularity=0.55):
    """
    Returns a sorted list of (cx, cy) tuples (pixel coords, top-left origin)
    for every red blob that passes the area / circularity filter.
    Sorted top-to-bottom then left-to-right as a visual sanity check.
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    # Red wraps around hue=0/180 in HSV
    mask1 = cv2.inRange(hsv, np.array([0,   80, 60]), np.array([15,  255, 255]))
    mask2 = cv2.inRange(hsv, np.array([155,  80, 60]), np.array([180, 255, 255]))
    red_mask = cv2.bitwise_or(mask1, mask2)

    # Clean up small noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN,  kernel, iterations=1)
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)

    circles = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            continue
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter ** 2)
        if circularity < min_circularity:
            continue
        M = cv2.moments(cnt)
        if M["m00"] == 0:
            continue
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        circles.append((cx, cy))

    # sort: row by row (top → bottom), then left → right within each row
    circles.sort(key=lambda c: (c[1], c[0]))
    return circles

# ── save / load helpers ─────────────────────────────────────────────────────
def save_detected(circles):
    with open(CIRCLES_JSON, "w") as f:
        json.dump(circles, f, indent=2)
    print(f"Detected {len(circles)} circles → {CIRCLES_JSON}")

def load_detected():
    with open(CIRCLES_JSON, "r") as f:
        return [tuple(c) for c in json.load(f)]

def load_coords():
    if os.path.exists(COORD_PATH):
        with open(COORD_PATH, "r") as f:
            raw = json.load(f)
        return {int(k): v for k, v in raw.items()}
    return {}

def save_coords(coords):
    with open(COORD_PATH, "w") as f:
        json.dump({str(k): v for k, v in coords.items()}, f, indent=2)
    print(f"Coordinates saved → {COORD_PATH}  "
          f"({len(coords)}/{TOTAL_RPS} RPs assigned)")

# ── build annotated preview image ──────────────────────────────────────────
def make_preview(img_bgr, circles):
    preview = img_bgr.copy()
    for idx, (cx, cy) in enumerate(circles):
        cv2.circle(preview, (cx, cy), 10, (0, 200, 0), 2)
        cv2.putText(preview, str(idx), (cx + 6, cy - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 140, 0), 1,
                    cv2.LINE_AA)
    cv2.imwrite(CIRCLES_PREVIEW, preview)
    print(f"Annotated preview → {CIRCLES_PREVIEW}")
    return cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)

# ── interactive ordering ────────────────────────────────────────────────────
def run_ordering(img_rgb, circles, coords):
    """
    Show the annotated floor plan; user clicks circles in RP order.
    Each click snaps to the nearest unassigned detected circle.
    """
    remaining_rps = [rp for rp in range(1, TOTAL_RPS + 1) if rp not in coords]
    if not remaining_rps:
        print("All RPs already assigned.")
        return coords

    # which detection indices are still available
    assigned_det = {tuple(v): k for k, v in coords.items()}   # (cx,cy) → rp
    used_indices  = set()
    for rp, (px, py) in coords.items():
        try:
            used_indices.add(circles.index((px, py)))
        except ValueError:
            pass

    state = {"rp_idx": 0, "saved": False}

    def current_rp():
        i = state["rp_idx"]
        return remaining_rps[i] if i < len(remaining_rps) else None

    def free_circles():
        return [(i, c) for i, c in enumerate(circles) if i not in used_indices]

    def nearest_free(x, y):
        free = free_circles()
        if not free:
            return None, None
        dists = [((x - c[0])**2 + (y - c[1])**2, i, c) for i, c in free]
        _, best_i, best_c = min(dists)
        return best_i, best_c

    def refresh():
        ax.cla()
        ax.imshow(img_rgb)
        ax.axis("off")

        rp = current_rp()
        if rp is not None:
            ax.set_title(
                f"Click on  RP {rp}  "
                f"({state['rp_idx'] + 1} of {len(remaining_rps)})\n"
                f"  [u] undo  ·  [s] save & exit  ·  [q] quit",
                fontsize=13, color="crimson", fontweight="bold"
            )
        else:
            ax.set_title("All RPs assigned! Press [s] to save.",
                         fontsize=13, color="green")

        # highlight assigned circles in magenta
        for assigned_rp, (px, py) in coords.items():
            ax.plot(px, py, "m*", markersize=9)
            ax.annotate(str(assigned_rp), (px, py),
                        fontsize=7, color="darkmagenta",
                        ha="center", va="bottom",
                        xytext=(0, 8), textcoords="offset points")

        fig.canvas.draw_idle()

    def on_click(event):
        if event.inaxes is not ax or event.button != 1:
            return
        rp = current_rp()
        if rp is None:
            return
        det_idx, (cx, cy) = nearest_free(event.xdata, event.ydata)
        if det_idx is None:
            return
        coords[rp] = [cx, cy]
        used_indices.add(det_idx)
        print(f"  RP {rp:3d}  ← detected #{det_idx:3d}  pixel ({cx}, {cy})")
        state["rp_idx"] += 1
        if state["rp_idx"] >= len(remaining_rps):
            save_coords(coords)
            state["saved"] = True
        refresh()

    def on_key(event):
        if event.key == "s":
            save_coords(coords)
            state["saved"] = True
            plt.close(fig)
        elif event.key == "q":
            print("Quit without saving.")
            plt.close(fig)
        elif event.key == "u":
            if state["rp_idx"] > 0:
                state["rp_idx"] -= 1
                rp_to_undo = remaining_rps[state["rp_idx"]]
                prev_coord = coords.pop(rp_to_undo, None)
                if prev_coord is not None:
                    try:
                        used_indices.discard(circles.index(tuple(prev_coord)))
                    except ValueError:
                        pass
                print(f"  Undone RP {rp_to_undo}")
                refresh()

    fig, ax = plt.subplots(figsize=(18, 13))
    fig.canvas.manager.set_window_title(
        "CMUQ Floor 1 – Click circles in RP order")
    fig.canvas.mpl_connect("button_press_event", on_click)
    fig.canvas.mpl_connect("key_press_event", on_key)
    refresh()
    plt.tight_layout()
    plt.show()

    if not state["saved"] and coords:
        ans = input("Save progress? [y/n]: ").strip().lower()
        if ans == "y":
            save_coords(coords)

    return coords

# ── entry point ─────────────────────────────────────────────────────────────
def main():
    # 1. rasterise PDF
    if not os.path.exists(PNG_PATH):
        if not os.path.exists(PDF_PATH):
            sys.exit(f"ERROR: {PDF_PATH} not found.")
        print("Converting PDF → PNG …")
        pdf_to_png(PDF_PATH, PNG_PATH)

    img_bgr = cv2.imread(PNG_PATH)
    if img_bgr is None:
        sys.exit(f"ERROR: Could not read {PNG_PATH}")

    # 2. detect red circles (or reload cached result)
    if os.path.exists(CIRCLES_JSON):
        circles = load_detected()
        print(f"Loaded {len(circles)} previously detected circles.")
        redetect = input("Re-run detection? [y/n] (default n): ").strip().lower()
        if redetect == "y":
            circles = None

    if not os.path.exists(CIRCLES_JSON) or 'circles' not in dir() or circles is None:
        print("Detecting red circles …")
        circles = detect_red_circles(img_bgr)
        save_detected(circles)

    print(f"Detected {len(circles)} red circles.")
    if len(circles) != TOTAL_RPS:
        print(f"WARNING: expected {TOTAL_RPS}, got {len(circles)}. "
              f"Check {CIRCLES_PREVIEW} and tune detection if needed.")

    # 3. build / show annotated preview
    img_rgb = make_preview(img_bgr, circles)

    # 4. load any existing RP assignments and run ordering UI
    coords = load_coords()
    if coords:
        print(f"Resuming – {len(coords)}/{TOTAL_RPS} RPs already assigned.")

    run_ordering(img_rgb, circles, coords)


if __name__ == "__main__":
    main()

