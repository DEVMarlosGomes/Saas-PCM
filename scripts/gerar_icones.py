"""
Gera os ícones PWA do AURIX (192x192 e 512x512).
Rodar: python scripts/gerar_icones.py
Requer: pip install pillow (já está em requirements.txt)
"""
import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "icons")
os.makedirs(OUT_DIR, exist_ok=True)

BG      = (15, 23, 42)     # slate-950
ACCENT  = (37, 99, 235)    # blue-600
WHITE   = (255, 255, 255)

def draw_icon(size: int) -> Image.Image:
    img  = Image.new("RGBA", (size, size), BG)
    draw = ImageDraw.Draw(img)

    # Rounded rect background (simula border-radius)
    r = size // 8
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=BG)

    # Hexágono estilizado (6 lados) representando "industrial"
    cx, cy = size // 2, size // 2
    hex_r  = int(size * 0.36)
    import math
    hex_pts = [
        (cx + hex_r * math.cos(math.radians(a)),
         cy + hex_r * math.sin(math.radians(a)))
        for a in range(30, 390, 60)
    ]
    draw.polygon(hex_pts, fill=ACCENT)

    # "A" centralizado
    font_size = int(size * 0.38)
    font = None
    for name in ["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf", "FreeSansBold.ttf"]:
        try:
            font = ImageFont.truetype(name, font_size)
            break
        except OSError:
            pass
    if font is None:
        font = ImageFont.load_default()

    text = "A"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw   = bbox[2] - bbox[0]
    th   = bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2 - size // 20), text, font=font, fill=WHITE)

    return img

for size in [192, 512]:
    icon = draw_icon(size)
    path = os.path.join(OUT_DIR, f"icon-{size}.png")
    icon.save(path, "PNG")
    print(f"✓ {path}")

print("Ícones gerados com sucesso.")
