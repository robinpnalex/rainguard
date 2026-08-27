"""
Generates placeholder road photos with Pillow.

Real photos are better -- drop your own into sample_data/ and the seed script
will use those instead. These exist so a fresh clone has thumbnails on the map
and a believable before/after pair, with no binary files in the repo.
"""
from pathlib import Path

from config import IMAGE_DIR

PALETTE = {
    "pothole": ((72, 72, 78), (28, 28, 32)),
    "manhole": ((70, 66, 60), (20, 18, 16)),
    "waterlogging": ((70, 96, 120), (34, 58, 84)),
    "clean": ((104, 104, 110), (86, 86, 92)),
}
SIZE = (480, 320)


def make_image(kind: str, label: str, filename: str) -> str:
    """Render a labelled placeholder into the image store; return its filename."""
    from PIL import Image, ImageDraw

    road, blemish = PALETTE.get(kind, PALETTE["clean"])
    img = Image.new("RGB", SIZE, road)
    draw = ImageDraw.Draw(img)

    # Road texture: lane markings down the middle.
    for y in range(20, SIZE[1], 60):
        draw.rectangle([SIZE[0] // 2 - 4, y, SIZE[0] // 2 + 4, y + 32], fill=(190, 185, 150))

    if kind == "pothole":
        draw.ellipse([150, 170, 290, 250], fill=blemish)
        draw.ellipse([165, 182, 275, 238], fill=(16, 16, 18))
    elif kind == "manhole":
        draw.ellipse([170, 160, 300, 260], fill=(46, 44, 40))
        draw.ellipse([186, 172, 284, 248], fill=blemish)
        draw.arc([186, 172, 284, 248], 200, 340, fill=(150, 145, 135), width=4)
    elif kind == "waterlogging":
        draw.ellipse([60, 150, 420, 280], fill=blemish)
        draw.ellipse([110, 176, 250, 226], fill=(120, 150, 176))

    draw.rectangle([0, 0, SIZE[0], 34], fill=(18, 18, 20))
    draw.text((12, 11), label[:56], fill=(235, 235, 235))

    path = IMAGE_DIR / filename
    img.save(path, "JPEG", quality=82)
    return path.name


def cleanup() -> int:
    """Delete every stored image. Returns how many were removed."""
    removed = 0
    for path in Path(IMAGE_DIR).glob("*"):
        if path.is_file():
            path.unlink()
            removed += 1
    return removed
