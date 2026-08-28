#!/usr/bin/env python3
"""
Fine-tune YOLOv8-nano to detect potholes, and install the weights into NIRVANA.

Why nano: it is the smallest YOLOv8 variant (~3.2M parameters, ~6 MB of
weights). It trains on a laptop CPU in hours instead of days, and runs
inference fast enough that a demo upload feels instant. Accuracy is lower than
the bigger variants, which is the right trade for a prototype.

Typical use
-----------
1. Find a pothole dataset on Roboflow Universe (https://universe.roboflow.com).
   Open it, choose "Download this Dataset" -> YOLOv8, and copy the URL from
   your browser's address bar.

2. Train:

       python model/train.py --roboflow-url "<paste URL>" --roboflow-key "<key>"

   Your free API key is at https://app.roboflow.com/settings/api

   Or, if you already have a dataset on disk in YOLO format:

       python model/train.py --data path/to/data.yaml

3. The script copies the best weights to model/nirvana.pt and prints the class
   names it learned, so you can check them against CLASS_NAME_MAP in
   backend/detector/yolo_detector.py.

4. Set DETECTOR_MODE = "yolo" in backend/config.py and restart the backend.

On this laptop there is no CUDA GPU, so training runs on CPU. That works, but
budget a few hours. Google Colab's free T4 does the same run in well under an
hour -- see model/README.md.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODEL_DIR.parent
DEST_WEIGHTS = MODEL_DIR / "nirvana.pt"


def parse_roboflow_url(url: str) -> tuple[str, str, int]:
    """Pull workspace / project / version out of a Roboflow dataset URL.

    Universe URLs look like:
        https://universe.roboflow.com/<workspace>/<project>/dataset/<version>
        https://app.roboflow.com/<workspace>/<project>/<version>

    We accept both rather than making the user hunt for three separate values.
    """
    match = re.search(r"roboflow\.com/([^/]+)/([^/]+)(?:/dataset)?/(\d+)", url)
    if not match:
        raise SystemExit(
            f"Could not read workspace/project/version from:\n  {url}\n"
            "Expected something like "
            "https://universe.roboflow.com/<workspace>/<project>/dataset/2"
        )
    workspace, project, version = match.groups()
    return workspace, project, int(version)


def download_dataset(url: str, api_key: str) -> Path:
    """Download a Roboflow dataset in YOLOv8 format, return its data.yaml."""
    try:
        from roboflow import Roboflow
    except ImportError:
        raise SystemExit("pip install roboflow")

    workspace, project, version = parse_roboflow_url(url)
    print(f"[nirvana] fetching {workspace}/{project} v{version} ...")

    rf = Roboflow(api_key=api_key)
    dataset = (
        rf.workspace(workspace)
        .project(project)
        .version(version)
        .download("yolov8", location=str(MODEL_DIR / "dataset"))
    )
    return Path(dataset.location) / "data.yaml"


def train(data_yaml: Path, epochs: int, imgsz: int, base: str, batch: int) -> Path:
    try:
        from ultralytics import YOLO
    except ImportError:
        raise SystemExit("pip install ultralytics")

    import torch

    device = 0 if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        print(
            "[nirvana] No CUDA GPU found -- training on CPU. This is slow.\n"
            "          Consider Google Colab (free T4); see model/README.md."
        )

    model = YOLO(base)
    model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        project=str(MODEL_DIR / "runs"),
        name="pothole",
        exist_ok=True,
        # Patience stops early if validation stops improving, which matters a
        # lot on CPU where every wasted epoch costs real minutes.
        patience=15,
    )
    return MODEL_DIR / "runs" / "pothole" / "weights" / "best.pt"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--roboflow-url", help="Roboflow Universe dataset URL")
    src.add_argument("--data", help="Path to an existing YOLO data.yaml")
    ap.add_argument("--roboflow-key", help="Roboflow API key (with --roboflow-url)")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--model", default="yolov8n.pt", help="base checkpoint")
    args = ap.parse_args()

    if args.roboflow_url:
        if not args.roboflow_key:
            raise SystemExit("--roboflow-key is required with --roboflow-url")
        data_yaml = download_dataset(args.roboflow_url, args.roboflow_key)
    else:
        data_yaml = Path(args.data).resolve()
        if not data_yaml.exists():
            raise SystemExit(f"No such file: {data_yaml}")

    best = train(data_yaml, args.epochs, args.imgsz, args.model, args.batch)
    if not best.exists():
        raise SystemExit(f"Training finished but {best} is missing.")

    shutil.copy2(best, DEST_WEIGHTS)
    print(f"\n[nirvana] weights installed -> {DEST_WEIGHTS}")

    # Print the learned class names. If they are not already keys in
    # CLASS_NAME_MAP, every detection gets silently dropped -- so surface them.
    from ultralytics import YOLO

    names = YOLO(str(DEST_WEIGHTS)).names
    print(f"[nirvana] model classes: {list(names.values())}")
    print(
        "\nNext:\n"
        "  1. Check those class names against CLASS_NAME_MAP in\n"
        "     backend/detector/yolo_detector.py -- unmapped classes are ignored.\n"
        "  2. Set DETECTOR_MODE = \"yolo\" in backend/config.py\n"
        "  3. Restart the backend.\n"
    )


if __name__ == "__main__":
    main()
