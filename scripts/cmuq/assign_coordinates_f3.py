"""
CMUQ Floor 3 – Coordinate Assignment
(Skeleton – update PDF_PATH / PNG_PATH / TOTAL_RPS once floor-3 plan is available)

Same workflow as assign_coordinates_f1.py / assign_coordinates_f2.py:
  Phase 1: OpenCV detects red circles on the floor plan PNG.
  Phase 2: User clicks circles in RP order (1 → N).

Controls: LEFT-CLICK = assign next RP  |  u = undo  |  s = save & exit  |  q = quit

Output: coordinates/cmuq/floor3.json   –  {rp_str: [pixel_x, pixel_y]}
"""

import json, os, sys
import numpy as np
import cv2
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

# TODO: update these once the floor-3 PDF is available
PDF_PATH        = os.path.join(ROOT, "raw", "TF-Generic.pdf")          # ← update
PNG_PATH        = os.path.join(ROOT, "floor_plans", "cmuq", "floor3.png")
COORD_PATH      = os.path.join(ROOT, "coordinates", "cmuq", "floor3.json")
CIRCLES_JSON    = os.path.join(ROOT, "coordinates", "cmuq", "detected_circles_f3.json")
CIRCLES_PREVIEW = os.path.join(ROOT, "floor_plans", "cmuq", "detected_circles_f3.png")

TOTAL_RPS = 84   # TODO: confirm RP count for floor 3

# ── The rest of this file is identical to assign_coordinates_f2.py ──────────
# Copy the body of assign_coordinates_f2.py below this line, updating f2→f3
# and floor2→floor3 references where they appear in print statements.

def pdf_to_png(pdf_path, png_path, dpi=150):
    import fitz
    doc = fitz.open(pdf_path)
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72), alpha=False)
    pix.save(png_path)
    doc.close()
    print(f"Floor plan rasterised → {png_path}")


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
    for c in cnts:
        area = cv2.contourArea(c)
        if area < min_area or area > max_area:
            continue
        peri  = cv2.arcLength(c, True)
        if peri == 0:
            continue
        circ  = 4 * np.pi * area / (peri ** 2)
        if circ < min_circ:
            continue
        M  = cv2.moments(c)
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        circles.append([cx, cy])
    return circles


if __name__ == "__main__":
    raise NotImplementedError(
        "assign_coordinates_f3.py is a skeleton.\n"
        "1. Set PDF_PATH / TOTAL_RPS at the top of the file.\n"
        "2. Copy the interactive click UI from assign_coordinates_f2.py\n"
        "   (everything after the detect_red_circles function) into this file.\n"
        "Then run:  python scripts/cmuq/assign_coordinates_f3.py"
    )
