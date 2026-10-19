"""Publication-quality structure and scheme drawing from SMILES.

Chemists write SMILES; journals want vector-ish, legible schemes.  This module
composes reaction schemes with PIL (precise layout, no matplotlib axes fighting
you) using RDKit for the structures.  RDKit is optional: if it is missing the
functions raise a clear message.

    python -m paperforge.schemes "O=C1Nc2ccccc2N=C1>>O=C1Nc2ccccc2N=C1c1ccccc1" \
        --conditions "4CzIPN (2 mol%), blue LEDs, EtOH, 25 °C, 12 h" --yield 94%
"""
from __future__ import annotations

import io
from pathlib import Path

try:  # optional dependency
    from rdkit import Chem
    from rdkit.Chem import AllChem, Draw
    from rdkit.Chem.Draw import rdMolDraw2D

    HAVE_RDKIT = True
except Exception:  # pragma: no cover
    HAVE_RDKIT = False


def draw_molecule(smiles: str, width: int = 900, height: int = 560,
                  legend: str = "", font_px: int = 34):
    """Return a PIL image of a molecule with an optional atom-map-free legend."""
    if not HAVE_RDKIT:
        raise RuntimeError("RDKit is required for structure drawing (pip install rdkit)")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"invalid SMILES: {smiles!r}")
    AllChem.Compute2DCoords(mol)
    drawer = rdMolDraw2D.MolDraw2DCairo(width, height)
    opts = drawer.drawOptions()
    opts.bondLineWidth = 2
    opts.minFontSize = 16
    opts.maxFontSize = font_px
    opts.clearBackground = True
    opts.legendFontSize = font_px
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol, legend=legend)
    drawer.FinishDrawing()
    from PIL import Image

    return Image.open(io.BytesIO(drawer.GetDrawingText())).convert("RGBA")


def reaction_scheme(reactants: list[str], products: list[str],
                    conditions: list[str] | str = "", yield_text: str = "",
                    labels: list[str] | None = None,
                    width_px: int = 2400, height_px: int = 900,
                    dpi: int = 300, out: str | Path | None = None,
                    font_px: int = 34) -> Path:
    """Draw one reaction (reactants on the left, products on the right).

    ``conditions`` is a list of lines printed above the arrow; ``yield_text``
    is printed below it.  Labels (1, 3a, …) are drawn under each structure.
    """
    from PIL import Image, ImageDraw, ImageFont

    if not HAVE_RDKIT:
        raise RuntimeError("RDKit is required for structure drawing (pip install rdkit)")
    canvas = Image.new("RGBA", (width_px, height_px), "white")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("DejaVuSerif.ttf", font_px)
        small = ImageFont.truetype("DejaVuSerif.ttf", int(font_px * 0.85))
        bold = ImageFont.truetype("DejaVuSerif-Bold.ttf", font_px)
    except Exception:  # pragma: no cover
        font = small = bold = ImageFont.load_default()

    labels = labels or []
    mol_h = int(height_px * 0.55)
    mol_w = int(width_px * 0.28)
    n_r, n_p = max(1, len(reactants)), max(1, len(products))

    def paste_mol(smiles: str, x: int, y: int, label: str = "") -> None:
        img = draw_molecule(smiles, mol_w, mol_h, font_px=font_px)
        img = img.resize((int(img.width * 0.92), int(img.height * 0.92)), Image.LANCZOS)
        canvas.alpha_composite(img, (x, y))
        if label:
            bbox = draw.textbbox((0, 0), label, font=bold)
            draw.text((x + (mol_w - (bbox[2] - bbox[0])) // 2, y + mol_h - 6),
                      label, fill="black", font=bold)

    x0 = int(width_px * 0.02)
    for i, smi in enumerate(reactants):
        paste_mol(smi, x0 + i * mol_w, int(height_px * 0.18),
                  labels[i] if i < len(labels) else "")

    gap_px = int(width_px * 0.05)
    if len(reactants) > 1:
        plus_x = x0 + (n_r - 1) * mol_w + mol_w // 2
        draw.text((plus_x - font_px // 4, int(height_px * 0.40)), "+", fill="black", font=font)

    arrow_x1 = x0 + n_r * mol_w + gap_px
    arrow_x2 = int(width_px * 0.62)
    arrow_y = int(height_px * 0.46)
    draw.line([(arrow_x1, arrow_y), (arrow_x2, arrow_y)], fill="black", width=5)
    ah = font_px // 2
    draw.polygon([(arrow_x2, arrow_y), (arrow_x2 - ah, arrow_y - ah // 2),
                  (arrow_x2 - ah, arrow_y + ah // 2)], fill="black")

    lines = [conditions] if isinstance(conditions, str) else list(conditions)
    lines = [l for l in lines if l]
    line_h = int(font_px * 1.3)
    # conditions stack upward from just above the arrow
    cy = arrow_y - line_h * len(lines) - 10
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=small)
        draw.text(((arrow_x1 + arrow_x2 - (bbox[2] - bbox[0])) // 2, cy), line, fill="black", font=small)
        cy += line_h
    if yield_text:
        bbox = draw.textbbox((0, 0), yield_text, font=bold)
        draw.text(((arrow_x1 + arrow_x2 - (bbox[2] - bbox[0])) // 2, arrow_y + 12),
                  yield_text, fill="black", font=bold)

    x1 = int(width_px * 0.66)
    for j, smi in enumerate(products):
        paste_mol(smi, x1 + j * mol_w, int(height_px * 0.18),
                  labels[len(reactants) + j] if len(reactants) + j < len(labels) else "")

    out = Path(out or "scheme.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    _save_trimmed(canvas, out, dpi)
    return out


def _save_trimmed(canvas, out: Path, dpi: int, pad: int = 24) -> None:
    """Crop the white margins so schemes fill the column width."""
    from PIL import Image, ImageChops

    rgb = canvas.convert("RGB")
    bg = Image.new("RGB", rgb.size, "white")
    bbox = ImageChops.difference(rgb, bg).getbbox()
    if bbox:
        left = max(0, bbox[0] - pad)
        top = max(0, bbox[1] - pad)
        right = min(rgb.width, bbox[2] + pad)
        bottom = min(rgb.height, bbox[3] + pad)
        rgb = rgb.crop((left, top, right, bottom))
    rgb.save(out, dpi=(dpi, dpi))


def toc_graphic(before: str, after: str, caption: str,
                width_cm: float = 8.25, height_cm: float = 4.45,
                dpi: int = 300, out: str | Path | None = None,
                arrow_label: str = "", yield_text: str = "") -> Path:
    """A TOC graphic at the exact pixel dimensions a journal asks for."""
    from PIL import Image, ImageDraw, ImageFont

    if not HAVE_RDKIT:
        raise RuntimeError("RDKit is required for structure drawing (pip install rdkit)")
    w = round(width_cm / 2.54 * dpi)
    h = round(height_cm / 2.54 * dpi)
    canvas = Image.new("RGBA", (w, h), "white")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("DejaVuSerif.ttf", max(12, h // 13))
        small = ImageFont.truetype("DejaVuSerif.ttf", max(10, h // 22))
    except Exception:  # pragma: no cover
        font = small = ImageFont.load_default()

    mol_w, mol_h = int(w * 0.34), int(h * 0.72)
    img_a = draw_molecule(before, mol_w, mol_h, font_px=max(16, h // 14))
    img_b = draw_molecule(after, mol_w, mol_h, font_px=max(16, h // 14))
    canvas.alpha_composite(img_a, (int(w * 0.02), int(h * 0.12)))
    canvas.alpha_composite(img_b, (int(w * 0.62), int(h * 0.12)))

    y = int(h * 0.44)
    draw.line([(int(w * 0.37), y), (int(w * 0.60), y)], fill="black", width=max(2, h // 150))
    draw.polygon([(int(w * 0.60), y), (int(w * 0.58), y - h // 26), (int(w * 0.58), y + h // 26)],
                 fill="black")
    if arrow_label:
        bbox = draw.textbbox((0, 0), arrow_label, font=small)
        draw.text(((w - (bbox[2] - bbox[0])) // 2, int(h * 0.30)), arrow_label, fill="black", font=small)
    if yield_text:
        bbox = draw.textbbox((0, 0), yield_text, font=font)
        draw.text(((w - (bbox[2] - bbox[0])) // 2, int(h * 0.50)), yield_text, fill="black", font=font)
    if caption:
        bbox = draw.textbbox((0, 0), caption, font=small)
        draw.text(((w - (bbox[2] - bbox[0])) // 2, int(h * 0.86)), caption, fill="black", font=small)

    out = Path(out or "toc.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, dpi=(dpi, dpi))  # TOC keeps its exact pixel size
    return out
