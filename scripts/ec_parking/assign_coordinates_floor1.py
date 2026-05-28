"""
Interactive coordinate assignment tool for EC Parking Floor 1 (ground level).

Phase 1 – Auto-detection  (runs automatically)
    OpenCV finds all blue circles on the floor plan and saves them as
    detected_circles_floor1.png (annotated preview) and detected_circles_floor1.json.

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
    coordinates/ec_parking/floor1.json       dict mapping RP number → [pixel_x, pixel_y]
    floor_plans/ec_parking/floor1.png        rasterized floor plan (one-time)
    floor_plans/ec_parking/detected_circles_floor1.png   annotated detection preview
    coordinates/ec_parking/detected_circles_floor1.json  raw list of detected circle centres
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
PDF_PATH        = os.path.join(ROOT, "raw", "EC-parking-ground.pdf")
PNG_PATH        = os.path.join(ROOT, "floor_plans", "ec_parking", "floor1.png")
COORD_PATH      = os.path.join(ROOT, "coordinates", "ec_parking", "floor1.json")
CIRCLES_JSON    = os.path.join(ROOT, "coordinates", "ec_parking", "detected_circles_floor1.json")
CIRCLES_PREVIEW = os.path.join(ROOT, "floor_plans", "ec_parking", "detected_circles_floor1.png")

TOTAL_RPS = 34   # Floor 1 has RPs 1–34

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

# ── detect blue circles with OpenCV ─────────────────────────────────────────
def detect_blue_circles(img_bgr,
                        min_area=15,
                        max_area=3000,
                        min_circularity=0.55):
    """
    Returns a sorted list of (cx, cy) tuples for every blue blob that passes
    the area / circularity filter.  Sorted top-to-bottom then left-to-right.
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    blue_mask = cv2.inRange(hsv, np.array([100, 80, 60]), np.array([130, 255, 255]))

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_OPEN,  kernel, iterations=1)
    blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL,
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
        circles.append((int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])))

    circles.sort(key=lambda c: (c[1], c[0]))
    return circles

# ── save / load helpers ─────────────────────────────────────────────────────
def save_detected(circles):
    with open(CIRCLES_JSON, "w") as f:
        json.dump(circles, f, indent=2)
    print(f"Detected {len(circles)} circles → {CIRCLES_JSON}")

def load_detected():
    with open(CIRCLES_JSON) as f:
        return [tuple(c) for c in json.load(f)]

def load_coords():
    if os.path.exists(COORD_PATH):
        with open(COORD_PATH) as f:
            raw = json.load(f)
        return {int(k): v for k, v in raw.items()}
    return {}

def save_coords(coords):
    with open(COORD_PATH, "w") as f:
        json.dump({str(k): v for k, v in coords.items()}, f, indent=2)
    print(f"Coordinates saved → {COORD_PATH}  ({len(coords)}/{TOTAL_RPS} RPs assigned)")

# ── annotated preview ───────────────────────────────────────────────────────
def make_preview(img_bgr, circles):
    preview = img_bgr.copy()
    for idx, (cx, cy) in enumerate(circles):
        cv2.circle(preview, (cx, cy), 10, (0, 200, 0), 2)
        cv2.putText(preview, str(idx), (cx + 6, cy - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 140, 0), 1, cv2.LINE_AA)
    cv2.imwrite(CIRCLES_PREVIEW, preview)
    print(f"Annotated preview → {CIRCLES_PREVIEW}")
    return cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)

# ── interactive ordering ────────────────────────────────────────────────────
def run_ordering(img_rgb, circles, coords):
    remaining_rps = [rp for rp in range(1, TOTAL_RPS + 1) if rp not in coords]
    if not remaining_rps:
        print("All RPs already assigned.")
        return coords

    used_indices = set()
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
                "  [u] undo  ·  [s] save & exit  ·  [q] quit",
                fontsize=13, color="crimson", fontweight="bold")
        else:
            ax.set_title("All RPs assigned! Press [s] to save.",
                         fontsize=13, color="green")

        for assigned_rp, (px, py) in coords.items():
            ax.plot(px, py, "m*", markersize=9)
            ax.annotate(str(assigned_rp), (px, py),
                        fontsize=7, color="darkmagenta",
                        ha="center", va="bottom",
                        xytext=(0, 8), textcoords="offset points")
        fig.canvas.draw_idle()

    fig, ax = plt.subplots(figsize=(14, 10))
    fig.subplots_adjust(left=0, right=1, top=0.92, bottom=0)
    refresh()

    def on_click(event):
        if event.inaxes != ax or event.button != 1:
            return
        rp = current_rp()
        if rp is None:
            return
        best_i, best_c = nearest_free(event.xdata, event.ydata)
        if best_i is None:
            print("No more unassigned circles.")
            return
        coords[rp] = list(best_c)
        used_indices.add(best_i)
        print(f"  RP {rp} → pixel {best_c}")
        state["rp_idx"] += 1
        refresh()

    def on_key(event):
        if event.key == "u":
            if state["rp_idx"] == 0:
                return
            state["rp_idx"] -= 1
            rp_undo = remaining_rps[state["rp_idx"]]
            if rp_undo in coords:
                px, py = coords.pop(rp_undo)
                try:
                    used_indices.discard(circles.index((px, py)))
                except ValueError:
                    pass
                print(f"  Undid RP {rp_undo}")
            refresh()
        elif event.key == "s":
            save_coords(coords)
            state["saved"] = True
            plt.close()
        elif event.key == "q":
            print("Quit without saving.")
            plt.close()

    fig.canvas.mpl_connect("button_press_event", on_click)
    fig.canvas.mpl_connect("key_press_event", on_key)
    plt.show()

    return coords if state["saved"] else {}

# ── main ────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(os.path.join(ROOT, "floor_plans", "ec_parking"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "coordinates", "ec_parking"), exist_ok=True)

    # Phase 1 – rasterise PDF
    if not os.path.exists(PNG_PATH):
        if not os.path.exists(PDF_PATH):
            sys.exit(f"ERROR: {PDF_PATH} not found.")
        pdf_to_png(PDF_PATH, PNG_PATH)
    else:
        print(f"Floor plan PNG already exists: {PNG_PATH}")

    img_bgr = cv2.imread(PNG_PATH)
    if img_bgr is None:
        sys.exit(f"ERROR: could not read {PNG_PATH}")

    # Phase 1 – detect blue circles
    if os.path.exists(CIRCLES_JSON):
        print(f"Loading cached circle detections from {CIRCLES_JSON}")
        circles = load_detected()
    else:
        print("Detecting blue circles …")
        circles = detect_blue_circles(img_bgr)
        save_detected(circles)

    img_rgb = make_preview(img_bgr, circles)
    print(f"Detected {len(circles)} blue circles "
          f"(need {TOTAL_RPS}, excess={len(circles)-TOTAL_RPS})")

    # Phase 2 – interactive ordering
    existing = load_coords()
    if existing:
        print(f"Resuming: {len(existing)}/{TOTAL_RPS} RPs already assigned.")

    coords = run_ordering(img_rgb, circles, existing)

    if coords:
        print(f"\n{len(coords)}/{TOTAL_RPS} RPs assigned.")
        if len(coords) < TOTAL_RPS:
            missing = [r for r in range(1, TOTAL_RPS+1) if r not in coords]
            print(f"Missing RPs: {missing}")
    else:
        print("No coordinates saved.")


if __name__ == "__main__":
    main()
