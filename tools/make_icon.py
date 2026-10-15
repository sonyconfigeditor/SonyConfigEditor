"""Makes the Windows icon file assets/sonyconfigeditor.ico from the logo assets/sonyconfigeditor.png.

Usage: python tools/make_icon.py

The logo has a wide transparent margin: it is cropped first (so the symbol fills the icon), made square, and every size of the icon is scaled
down from the cropped image on its own (sharper than letting the icon writer do it). The .ico is used for the EXE (build_exe.bat, PyInstaller
--icon) and for the window / taskbar icon of the program.
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "sonyconfigeditor.png"
TARGET = ROOT / "assets" / "sonyconfigeditor.ico"
SIZES = (256, 128, 64, 48, 32, 24, 16)
PADDING = 0.02          # a small transparent border (share of the side) so that the symbol does not touch the edge of the icon


def cropped_square(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    box = img.getchannel("A").getbbox()          # the visible part
    if box:
        img = img.crop(box)
    side = max(img.size)
    side = round(side * (1 + 2 * PADDING))
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
    return square


def main() -> None:
    with Image.open(SOURCE) as logo:
        base = cropped_square(logo)
    images = [base.resize((size, size), Image.LANCZOS) for size in SIZES]
    images[0].save(TARGET, format="ICO", sizes=[(size, size) for size in SIZES], append_images=images[1:])
    print(f"{TARGET}: {TARGET.stat().st_size} bytes, sizes {', '.join(str(s) for s in SIZES)}, source crop {base.size}")


if __name__ == "__main__":
    main()
