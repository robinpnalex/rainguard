#!/usr/bin/env python3
"""
Create a handful of sample road photos you can drag into the dashboard.

    python sample_data/generate_samples.py

The filenames matter: the mock detector reads them as hints, so
`pothole_tiger_circle.jpg` is detected as a pothole and
`clean_road_after_repair.jpg` is detected as clear. That is what makes the
repair-verification demo work without a trained model.

Replace these with real photographs of Manipal roads whenever you have them --
the filename convention still applies in mock mode, and is ignored entirely
once you switch DETECTOR_MODE to "yolo".
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))

SAMPLES = [
    ("pothole", "pothole_tiger_circle.jpg", "Tiger Circle - deep pothole"),
    ("pothole", "pothole_eshwar_nagar.jpg", "Eshwar Nagar - pothole cluster"),
    ("manhole", "manhole_mit_gate.jpg", "MIT main gate - open manhole"),
    ("manhole", "manhole_kunjibettu.jpg", "Kunjibettu - damaged cover"),
    ("waterlogging", "waterlogging_end_point.jpg", "End Point Road - waterlogged"),
    ("waterlogging", "waterlogging_lake_road.jpg", "Lake Road - standing water"),
    ("clean", "clean_road_after_repair.jpg", "Re-inspection - road is clear"),
    ("clean", "clean_road_second_check.jpg", "Re-inspection 2 - still clear"),
    ("clean", "clean_road_third_check.jpg", "Re-inspection 3 - still clear"),
]


def main() -> None:
    from PIL import Image, ImageDraw
    import demo_images

    for kind, filename, label in SAMPLES:
        road, blemish = demo_images.PALETTE.get(kind, demo_images.PALETTE["clean"])
        img = Image.new("RGB", demo_images.SIZE, road)
        draw = ImageDraw.Draw(img)
        for y in range(20, demo_images.SIZE[1], 60):
            draw.rectangle(
                [demo_images.SIZE[0] // 2 - 4, y, demo_images.SIZE[0] // 2 + 4, y + 32],
                fill=(190, 185, 150),
            )
        if kind == "pothole":
            draw.ellipse([150, 170, 290, 250], fill=blemish)
            draw.ellipse([165, 182, 275, 238], fill=(16, 16, 18))
        elif kind == "manhole":
            draw.ellipse([170, 160, 300, 260], fill=(46, 44, 40))
            draw.ellipse([186, 172, 284, 248], fill=blemish)
        elif kind == "waterlogging":
            draw.ellipse([60, 150, 420, 280], fill=blemish)
            draw.ellipse([110, 176, 250, 226], fill=(120, 150, 176))
        draw.rectangle([0, 0, demo_images.SIZE[0], 34], fill=(18, 18, 20))
        draw.text((12, 11), label, fill=(235, 235, 235))
        img.save(ROOT / filename, "JPEG", quality=85)
        print(f"  wrote sample_data/{filename}")

    print(f"\n{len(SAMPLES)} sample images ready.")


if __name__ == "__main__":
    main()
