# poly.py - Polygon tracer with fingertip using modern MediaPipe Hand Landmarker
# Updated Jan 2026 - with manual model path to fix FileNotFoundError

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np
import os  # Added to check if model exists

# ────────────────────────────────────────
# MANUAL MODEL PATH - CHANGE THIS IF YOU SAVED THE FILE ELSEWHERE
model_path = r'C:\Users\Geraint\Desktop\PythonPrograms\hand_landmarker.task'

# Quick check: does the file exist?
if not os.path.exists(model_path):
    print(f"\nERROR: Model file not found at:\n  {model_path}")
    print("Please download it from:")
    print("https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task")
    print("Save it as 'hand_landmarker.task' in the same folder as this script.")
    print("Then update 'model_path' above if needed.\n")
    exit()

# Setup Hand Landmarker
BaseOptions = python.BaseOptions
HandLandmarker = vision.HandLandmarker
HandLandmarkerOptions = vision.HandLandmarkerOptions
VisionRunningMode = vision.RunningMode

options = HandLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=model_path),
    running_mode=VisionRunningMode.VIDEO,
    num_hands=1,
    min_hand_detection_confidence=0.7,
    min_hand_presence_confidence=0.6,
    min_tracking_confidence=0.6
)

landmarker = HandLandmarker.create_from_options(options)

# ────────────────────────────────────────
cap = cv2.VideoCapture(0)  # 0 = default webcam; try 1 or 2 if no image
if not cap.isOpened():
    print("Error: Cannot open webcam. Try cap = cv2.VideoCapture(1)")
    exit()

polygon_points = []           # List of (x, y) pixel coords
drawing_polygon = False       # Is polygon finished/closed?
font = cv2.FONT_HERSHEY_SIMPLEX

print("\n=== Polygon Tracer with Finger Tracking ===")
print("Instructions:")
print("  Extend index finger, move slowly")
print("  'd' → add current fingertip as vertex")
print("  'f' → finish & close polygon (needs 3+ points)")
print("  'r' → reset polygon")
print("  ESC or 'q' → quit\n")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        print("Failed to grab frame")
        break

    h, w, _ = frame.shape

    # Convert frame to MediaPipe Image
    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    )

    timestamp_ms = int(cap.get(cv2.CAP_PROP_POS_MSEC))

    # Detect
    results = landmarker.detect_for_video(mp_image, timestamp_ms)

    overlay = frame.copy()
    index_tip = None
    inside = False

    if results.hand_landmarks:
        hand_lm = results.hand_landmarks[0]  # first hand
        tip = hand_lm[8]  # INDEX_FINGER_TIP landmark = 8
        cx = int(tip.x * w)
        cy = int(tip.y * h)
        index_tip = (cx, cy)

        # Draw fingertip marker
        cv2.circle(overlay, index_tip, 8, (0, 0, 255), cv2.FILLED)
        cv2.circle(overlay, index_tip, 12, (255, 255, 255), 2)

        # Check inside polygon if finished
        if drawing_polygon and len(polygon_points) >= 3:
            pts_array = np.array(polygon_points, dtype=np.int32)
            inside = cv2.pointPolygonTest(pts_array, index_tip, False) >= 0

    # Draw polygon
    if len(polygon_points) > 1:
        pts = np.array(polygon_points, np.int32).reshape((-1, 1, 2))
        if drawing_polygon:
            cv2.polylines(overlay, [pts], isClosed=True, color=(0, 255, 0), thickness=3)
        else:
            cv2.polylines(overlay, [pts], isClosed=False, color=(0, 200, 255), thickness=2)

    # Status text
    if not drawing_polygon:
        status = "Tracing - Press 'd' to add point"
        col = (255, 255, 100)
    else:
        status = f"Polygon ready - Tip inside? {'YES' if inside else 'NO'}"
        col = (0, 255, 100) if inside else (0, 100, 255)

    cv2.putText(overlay, status, (20, 40), font, 0.9, col, 2)

    if polygon_points:
        cv2.putText(overlay, f"Points: {len(polygon_points)}", (20, 80), font, 0.7, (200, 200, 50), 2)

    cv2.imshow("Polygon Tracer - Finger Tracking (ESC/q to quit)", overlay)

    # Key handling
    key = cv2.waitKey(1) & 0xFF

    if key == ord('d') and index_tip and not drawing_polygon:
        # Avoid duplicates (min distance 15 px)
        if not polygon_points or np.hypot(
            index_tip[0] - polygon_points[-1][0],
            index_tip[1] - polygon_points[-1][1]
        ) > 15:
            polygon_points.append(index_tip)
            print(f"Added point {len(polygon_points)}: {index_tip}")

    elif key == ord('f') and len(polygon_points) >= 3 and not drawing_polygon:
        drawing_polygon = True
        print("Polygon finished!")

    elif key == ord('r'):
        polygon_points = []
        drawing_polygon = False
        print("Reset.")

    elif key in (27, ord('q')):
        break

cap.release()
cv2.destroyAllWindows()
print("Exited.")