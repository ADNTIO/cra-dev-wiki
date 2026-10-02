"""Convertit le logo ADNT en bitmap 128 x 64 pour l'écran OLED : src/logo.h

    uv run --group firmware python firmware/tools/make_logo.py [--preview apercu.png]

Le logo vertical (symbole, « ADNT », « Sàrl ») est recomposé à l'horizontale pour
tenir dans 64 pixels de haut : le symbole à gauche, le texte à droite. « Sàrl »,
illisible une fois réduit, est redessiné avec une police TrueType (Noto Sans, ou
DejaVu Sans à défaut).
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "assets/adnt-mark-black.png"
HEADER = HERE.parent / "src/logo.h"
WIDTH, HEIGHT = 128, 64

# Bandes horizontales du logo source (en pixels), repérées par leur encre
SYMBOL = (0, 350)
NAME = (372, 490)
SUFFIX = "Sàrl"
FONTS = [
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def load_font(path: Path | None, size: int) -> ImageFont.FreeTypeFont:
    for candidate in [path] if path else FONTS:
        if Path(candidate).exists():
            return ImageFont.truetype(str(candidate), size)
    raise SystemExit("Aucune police trouvée : passez-en une avec --font")


def ink(image: Image.Image) -> Image.Image:
    """Le logo en niveaux de gris, encre en blanc : un pixel allumé sur l'OLED."""
    return image.getchannel("A")


def crop_band(image: Image.Image, band: tuple[int, int]) -> Image.Image:
    part = image.crop((0, band[0], image.width, band[1]))
    return part.crop(part.getbbox())


def fit(image: Image.Image, width: int, height: int) -> Image.Image:
    scale = min(width / image.width, height / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, Image.LANCZOS)


def compose(font_path: Path | None) -> Image.Image:
    logo = ink(Image.open(SOURCE).convert("RGBA"))
    canvas = Image.new("L", (WIDTH, HEIGHT), 0)

    symbol = fit(crop_band(logo, SYMBOL), 56, 62)
    canvas.paste(symbol, (2, (HEIGHT - symbol.height) // 2))

    text_x, text_w = 64, 62
    name = fit(crop_band(logo, NAME), text_w, 26)
    font = load_font(font_path, 16)
    left, upper, right, lower = font.getbbox(SUFFIX)
    gap = 7
    top = (HEIGHT - name.height - gap - (lower - upper)) // 2
    canvas.paste(name, (text_x + (text_w - name.width) // 2, top))
    ImageDraw.Draw(canvas).text(
        (text_x + (text_w - (right - left)) // 2 - left, top + name.height + gap - upper),
        SUFFIX, fill=255, font=font,
    )

    return canvas.point(lambda v: 255 if v >= 110 else 0).convert("1")


def to_header(bitmap: Image.Image) -> str:
    # Ligne par ligne, 8 pixels par octet, bit de poids fort à gauche
    stride = WIDTH // 8
    rows = []
    for y in range(HEIGHT):
        row = bytearray(stride)
        for x in range(WIDTH):
            if bitmap.getpixel((x, y)):
                row[x // 8] |= 0x80 >> (x % 8)
        rows.append("\t" + ", ".join(f"0x{b:02x}" for b in row) + ",")
    return (
        "/* Généré par tools/make_logo.py depuis assets/adnt-mark-black.png. Ne pas modifier. */\n\n"
        "#include <stdint.h>\n\n"
        f"#define LOGO_WIDTH  {WIDTH}\n#define LOGO_HEIGHT {HEIGHT}\n\n"
        "/* Une ligne par rangée de pixels, bit de poids fort à gauche, 1 = allumé */\n"
        f"static const uint8_t logo_bitmap[LOGO_HEIGHT * LOGO_WIDTH / 8] = {{\n"
        + "\n".join(rows)
        + "\n};\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--font", type=Path, help="police TrueType pour « Sàrl »")
    parser.add_argument("--preview", type=Path, help="écrit aussi un aperçu agrandi (PNG)")
    args = parser.parse_args()

    bitmap = compose(args.font)
    HEADER.write_text(to_header(bitmap))
    print(f"{HEADER.relative_to(HERE.parent)} : {WIDTH} x {HEIGHT}")
    if args.preview:
        bitmap.convert("L").resize((WIDTH * 4, HEIGHT * 4), Image.NEAREST).save(args.preview)


if __name__ == "__main__":
    main()
