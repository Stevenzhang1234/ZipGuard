"""
Gesture classifier using webcam + MediaPipe hand landmarks + a small PyTorch MLP.

Usage:
    python gesture.py collect --label fist       # auto-captures 80 frames after a countdown
    python gesture.py collect --label open_palm
    python gesture.py collect --label peace
    python gesture.py train                      # trains on everything in data/
    python gesture.py run                        # live inference
"""

import argparse
import csv
import sys
import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import torch
import torch.nn as nn
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    HandLandmarker,
    HandLandmarkerOptions,
    RunningMode,
)
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
MODEL_PATH = ROOT / "gesture_model.pt"
LABELS_PATH = ROOT / "labels.txt"
TASK_PATH = ROOT / "hand_landmarker.task"
TASK_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)

NUM_LANDMARKS = 21
FEATURE_DIM = NUM_LANDMARKS * 3

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
]


def ensure_task_file():
    if TASK_PATH.exists():
        return
    print(f"Downloading hand landmarker model to {TASK_PATH} ...")
    urllib.request.urlretrieve(TASK_URL, TASK_PATH)


def make_landmarker():
    ensure_task_file()
    options = HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(TASK_PATH)),
        running_mode=RunningMode.IMAGE,
        num_hands=1,
        min_hand_detection_confidence=0.7,
    )
    return HandLandmarker.create_from_options(options)


def detect(landmarker, bgr_frame):
    rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect(mp_image)
    if not result.hand_landmarks:
        return None
    return result.hand_landmarks[0]  # list of 21 NormalizedLandmark


def draw_landmarks(frame, landmarks):
    h, w = frame.shape[:2]
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, pts[a], pts[b], (200, 200, 200), 2)
    for p in pts:
        cv2.circle(frame, p, 4, (0, 255, 0), -1)


def extract_features(landmarks):
    pts = np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=np.float32)
    pts -= pts[0]
    scale = np.linalg.norm(pts, axis=1).max()
    if scale > 0:
        pts /= scale
    return pts.flatten()


class GestureNet(nn.Module):
    def __init__(self, num_classes):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(FEATURE_DIM, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, num_classes),
        )

    def forward(self, x):
        return self.net(x)


def open_camera():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        sys.exit("Could not open webcam.")
    return cap


def collect(label, target=80, countdown_sec=3.0):
    """Auto-captures `target` frames after a countdown. Vary your hand during capture."""
    DATA_DIR.mkdir(exist_ok=True)
    csv_path = DATA_DIR / f"{label}.csv"
    cap = open_camera()
    landmarker = make_landmarker()

    import time
    t_start = time.time()
    count = 0
    read_fails = 0
    no_hand_frames = 0
    last_log = 0.0
    in_countdown = True

    print(f"[collect] label={label} target={target} countdown={countdown_sec}s")
    print(f"[collect] show your hand to the camera NOW. capturing will start after countdown.")

    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        while count < target:
            ok, frame = cap.read()
            if not ok:
                read_fails += 1
                if read_fails > 30:
                    print("[collect] too many camera read failures, aborting")
                    break
                continue

            frame = cv2.flip(frame, 1)
            landmarks = detect(landmarker, frame)
            if landmarks is not None:
                draw_landmarks(frame, landmarks)
            else:
                no_hand_frames += 1

            elapsed = time.time() - t_start
            if in_countdown and elapsed >= countdown_sec:
                in_countdown = False
                print(f"[collect] countdown done, capturing {target} samples...")

            if in_countdown:
                remaining = max(0, int(countdown_sec - elapsed) + 1)
                status = f"{label}  get ready... {remaining}"
                color = (0, 165, 255)
            else:
                if landmarks is not None:
                    writer.writerow(extract_features(landmarks).tolist())
                    count += 1
                status = f"{label}  capturing {count}/{target}"
                color = (0, 255, 0)

            cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, color, 2)
            cv2.imshow("collect", frame)
            cv2.waitKey(1)

            if elapsed - last_log >= 1.0:
                print(f"[collect] t={elapsed:4.1f}s  count={count}  "
                      f"no_hand_frames={no_hand_frames}  read_fails={read_fails}",
                      flush=True)
                last_log = elapsed

    cap.release()
    cv2.destroyAllWindows()
    print(f"Saved {count} samples to {csv_path}")


def load_dataset():
    if not DATA_DIR.exists():
        sys.exit("No data/ directory. Run `collect` first.")
    xs, ys, labels = [], [], []
    for csv_file in sorted(DATA_DIR.glob("*.csv")):
        label = csv_file.stem
        labels.append(label)
        class_idx = len(labels) - 1
        with open(csv_file) as f:
            for row in csv.reader(f):
                xs.append([float(v) for v in row])
                ys.append(class_idx)
    if not xs:
        sys.exit("No samples found. Run `collect` first.")
    return np.array(xs, dtype=np.float32), np.array(ys, dtype=np.int64), labels


def train():
    X, y, labels = load_dataset()
    print(f"Training on {len(X)} samples across {len(labels)} classes: {labels}")

    idx = np.random.permutation(len(X))
    X, y = X[idx], y[idx]
    split = int(0.85 * len(X))
    X_tr, X_val = X[:split], X[split:]
    y_tr, y_val = y[:split], y[split:]

    train_loader = DataLoader(
        TensorDataset(torch.from_numpy(X_tr), torch.from_numpy(y_tr)),
        batch_size=32, shuffle=True,
    )

    model = GestureNet(len(labels))
    optim = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()

    for epoch in range(60):
        model.train()
        total = 0.0
        for xb, yb in train_loader:
            optim.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            optim.step()
            total += loss.item() * len(xb)

        if (epoch + 1) % 10 == 0:
            model.eval()
            with torch.no_grad():
                preds = model(torch.from_numpy(X_val)).argmax(1).numpy()
            acc = (preds == y_val).mean() if len(y_val) else float("nan")
            print(f"epoch {epoch+1:3d}  loss={total/len(X_tr):.4f}  val_acc={acc:.3f}")

    torch.save(model.state_dict(), MODEL_PATH)
    LABELS_PATH.write_text("\n".join(labels))
    print(f"Saved model to {MODEL_PATH}")


def run():
    if not MODEL_PATH.exists() or not LABELS_PATH.exists():
        sys.exit("No trained model. Run `train` first.")
    labels = LABELS_PATH.read_text().splitlines()
    model = GestureNet(len(labels))
    model.load_state_dict(torch.load(MODEL_PATH))
    model.eval()

    cap = open_camera()
    landmarker = make_landmarker()

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)
        landmarks = detect(landmarker, frame)

        text = "no hand"
        if landmarks is not None:
            draw_landmarks(frame, landmarks)
            feats = extract_features(landmarks)
            with torch.no_grad():
                logits = model(torch.from_numpy(feats).unsqueeze(0))
                probs = torch.softmax(logits, dim=1)[0]
                top = int(probs.argmax())
            text = f"{labels[top]}  ({probs[top].item():.2f})"

        cv2.putText(frame, text, (10, 40), cv2.FONT_HERSHEY_SIMPLEX,
                    1.0, (0, 255, 0), 2)
        cv2.imshow("gesture", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_collect = sub.add_parser("collect", help="capture landmark samples for a gesture")
    p_collect.add_argument("--label", required=True)
    p_collect.add_argument("--count", type=int, default=80)

    sub.add_parser("train", help="train the classifier on collected data")
    sub.add_parser("run", help="run live webcam inference")

    args = parser.parse_args()
    if args.cmd == "collect":
        collect(args.label, target=args.count)
    elif args.cmd == "train":
        train()
    elif args.cmd == "run":
        run()


if __name__ == "__main__":
    main()
