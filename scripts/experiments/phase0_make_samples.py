"""
Phase 0 sample generator — synthetic math images for OCR experiments.

Creates under scripts/experiments/out/:
  single_line.png           one equation, ~400x100
  multi_2line_gap*.png      stacked equations with varying vertical gaps
  multi_3line_gap*.png

Uses matplotlib mathtext when available (closer to printed math TexTeller was
trained on), else plain PIL text.

Run: .venv\\Scripts\\python.exe scripts\\experiments\\phase0_make_samples.py
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    HAVE_MPL = True
except ImportError:
    HAVE_MPL = False


def render_line_mpl(tex: str, fontsize: int = 28) -> Image.Image:
    """Render one equation with matplotlib mathtext, tight-cropped, white bg."""
    fig = plt.figure(figsize=(6, 1.2), dpi=100)
    fig.patch.set_facecolor("white")
    fig.text(0.05, 0.5, f"${tex}$", fontsize=fontsize, va="center", color="black")
    from io import BytesIO

    buf = BytesIO()
    fig.savefig(buf, format="png", facecolor="white", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def render_line_pil(text: str) -> Image.Image:
    try:
        font = ImageFont.truetype("arial.ttf", 42)
    except OSError:
        font = ImageFont.load_default()
    img = Image.new("RGB", (500, 90), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 20), text, fill="black", font=font)
    return img


def render_line(tex: str, plain: str) -> Image.Image:
    return render_line_mpl(tex) if HAVE_MPL else render_line_pil(plain)


def stack(lines: list[Image.Image], gap_px: int) -> Image.Image:
    w = max(im.width for im in lines) + 40
    h = sum(im.height for im in lines) + gap_px * (len(lines) - 1) + 40
    canvas = Image.new("RGB", (w, h), "white")
    y = 20
    for im in lines:
        canvas.paste(im, (20, y))
        y += im.height + gap_px
    return canvas


def main() -> None:
    manifest: dict[str, dict] = {}

    single = render_line(r"2x + 3 = 7", "2x + 3 = 7")
    single.save(OUT / "single_line.png")
    manifest["single_line.png"] = {"lines": ["2x + 3 = 7"]}

    eq3 = [
        (r"2x + 3 = 7", "2x + 3 = 7"),
        (r"2x = 4", "2x = 4"),
        (r"x = 2", "x = 2"),
    ]
    eq2 = [
        (r"x^{2} - 5x + 6 = 0", "x^2 - 5x + 6 = 0"),
        (r"(x - 2)(x - 3) = 0", "(x - 2)(x - 3) = 0"),
    ]
    eq3b = [
        (r"\frac{d}{dx} x^{3} = 3x^{2}", "d/dx x^3 = 3x^2"),
        (r"\int 3x^{2} dx = x^{3} + C", "integral 3x^2 dx = x^3 + C"),
        (r"y = x^{3} + 1", "y = x^3 + 1"),
    ]

    for name, eqs, gap in [
        ("multi_3line_gap30.png", eq3, 30),
        ("multi_3line_gap12.png", eq3, 12),
        ("multi_3line_gap60.png", eq3, 60),
        ("multi_2line_gap25.png", eq2, 25),
        ("multi_3line_calc_gap35.png", eq3b, 35),
    ]:
        imgs = [render_line(t, p) for t, p in eqs]
        stack(imgs, gap).save(OUT / name)
        manifest[name] = {"lines": [t for t, _ in eqs], "gap_px": gap}

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"renderer={'matplotlib' if HAVE_MPL else 'PIL'}")
    for k in manifest:
        print("wrote", OUT / k)


if __name__ == "__main__":
    main()
