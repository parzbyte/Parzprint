"""Gera parzprint/assets/icon.png e icon.ico. Rode uma vez: python scripts/make_icon.py"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "parzprint" / "assets"
S = 256


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, S - 8, S - 8], radius=52, fill="#1E88E5")
    w, m, arm = 18, 52, 58
    for x, y, dx, dy in ((m, m, 1, 1), (S - m, m, -1, 1), (m, S - m, 1, -1), (S - m, S - m, -1, -1)):
        d.line([(x, y), (x + dx * arm, y)], fill="white", width=w)
        d.line([(x, y), (x, y + dy * arm)], fill="white", width=w)
    for i, length in enumerate((96, 96, 60)):
        y = 100 + i * 30
        d.rounded_rectangle([80, y, 80 + length, y + 14], radius=7, fill="white")
    return img


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    icon = draw()
    icon.save(OUT / "icon.png")
    icon.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("ok", OUT)
