"""Figure handling: resolution, physical size, TOC graphics, captions.

Journals reject figures for three reasons that are entirely mechanical:
too few pixels at print size, wrong aspect ratio for the TOC slot, and
captions that do not describe the panel.  All three are checked here.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from .project import Figure, Project
from .util import word_count

RASTER = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif"}
VECTOR = {".pdf", ".eps", ".svg"}


@dataclass
class ImageInfo:
    path: Path
    exists: bool
    format: str = ""
    mode: str = ""
    width_px: int = 0
    height_px: int = 0
    dpi: float = 0.0
    vector: bool = False
    error: str = ""

    @property
    def aspect(self) -> float:
        return (self.width_px / self.height_px) if self.height_px else 0.0

    def effective_dpi(self, width_cm: float | None) -> float:
        if self.vector or self.dpi:
            return self.dpi
        if width_cm and self.width_px:
            return self.width_px / (width_cm / 2.54)
        return 0.0


def image_info(path: str | Path) -> ImageInfo:
    p = Path(path)
    if not p.exists():
        return ImageInfo(p, False, error="file not found")
    suffix = p.suffix.lower()
    if suffix in VECTOR:
        return ImageInfo(p, True, format=suffix.lstrip("."), vector=True)
    if suffix not in RASTER:
        return ImageInfo(p, True, format=suffix.lstrip("."), error="unsupported raster format")
    try:
        from PIL import Image

        with Image.open(p) as im:
            dpi = im.info.get("dpi", (0, 0))
            dpi_val = float(dpi[0]) if isinstance(dpi, tuple) else float(dpi or 0)
            fmt = im.format or suffix.lstrip(".").upper()
            mode = im.mode
            w, h = im.size
        return ImageInfo(p, True, format=fmt, mode=mode, width_px=w, height_px=h, dpi=dpi_val)
    except Exception as exc:  # pragma: no cover - PIL missing/corrupt file
        return ImageInfo(p, True, format=suffix.lstrip("."), error=f"cannot read image: {exc}")


def check_figure_file(fig: Figure, root: Path, min_dpi: int = 300,
                      required_width_cm: float | None = None) -> list[dict]:
    """Return issues for one figure asset."""
    issues: list[dict] = []
    info = image_info(root / fig.file)
    if not info.exists:
        issues.append({"code": "FIG-MISSING", "severity": "error",
                       "message": f"{fig.id}: file not found ({fig.file})",
                       "hint": "fix the path or add the asset"})
        return issues
    if info.error and not info.vector:
        issues.append({"code": "FIG-READ", "severity": "error",
                       "message": f"{fig.id}: {info.error}", "hint": "re-export the figure"})
        return issues

    if info.vector:
        issues.append({"code": "FIG-VECTOR", "severity": "info",
                       "message": f"{fig.id}: vector format ({info.format}) — resolution-independent"})
        return issues

    if fig.kind in {"scheme", "toc", "graphical"} and info.format.lower() in {"jpg", "jpeg"}:
        issues.append({"code": "FIG-JPEG", "severity": "warn",
                       "message": f"{fig.id}: JPEG for line art/scheme — use PNG/TIFF/PDF to avoid artefacts",
                       "hint": "export schemes as vector PDF or 600 dpi PNG"})

    width_cm = required_width_cm or fig.width_cm
    dpi = info.effective_dpi(width_cm)
    if dpi and dpi < min_dpi - 0.5:
        need_px = math.ceil((width_cm or 8.5) / 2.54 * min_dpi)
        issues.append({
            "code": "FIG-DPI", "severity": "error",
            "message": f"{fig.id}: effective resolution {dpi:.0f} dpi at {width_cm or '?'} cm "
                       f"(needs ≥{min_dpi} dpi; {need_px} px wide at that width)",
            "hint": "re-export at higher resolution or reduce the print width",
        })
    elif not width_cm and not info.dpi:
        issues.append({
            "code": "FIG-DPI-UNKNOWN", "severity": "warn",
            "message": f"{fig.id}: no DPI metadata and no print width declared — resolution cannot be verified",
            "hint": "set `width_cm` on the figure or export with 300 dpi metadata",
        })

    if info.width_px < 600 and (width_cm or 8) > 4:
        issues.append({"code": "FIG-SMALL", "severity": "warn",
                       "message": f"{fig.id}: only {info.width_px} px wide"})
    if info.mode in {"CMYK", "L"} and info.format.upper() in {"PNG"}:
        issues.append({"code": "FIG-MODE", "severity": "info",
                       "message": f"{fig.id}: {info.mode} image saved as {info.format}"})
    return issues


def caption_issues(caption: str, kind: str = "figure") -> list[dict]:
    issues: list[dict] = []
    n = word_count(caption)
    if n == 0:
        issues.append({"code": "FIG-CAPTION", "severity": "error", "message": "missing caption"})
        return issues
    if n < 8:
        issues.append({"code": "FIG-CAPTION-SHORT", "severity": "warn",
                       "message": f"caption is only {n} words — state what is shown and the conditions"})
    if re.match(r"^(fig(ure)?|scheme|table)\b", caption.strip(), re.I):
        issues.append({"code": "FIG-CAPTION-PREFIX", "severity": "info",
                       "message": "caption starts with 'Figure/Scheme' — journals add the label automatically"})
    if not re.search(r"[.!?]$", caption.strip()):
        issues.append({"code": "FIG-CAPTION-PERIOD", "severity": "info",
                       "message": "caption does not end with a full stop"})
    if kind in {"scheme", "figure"} and not re.search(r"\b(A|B|C|left|right|top|bottom)\b", caption) \
            and re.search(r"\b(panels?|a\)|b\))\b", caption):
        issues.append({"code": "FIG-PANEL", "severity": "info",
                       "message": "multi-panel caption should label panels explicitly (A, B, …)"})
    return issues


def toc_dimensions(profile, dpi: int | None = None) -> tuple[int, int]:
    """Pixel size required for the TOC graphic at the journal's print size."""
    if not profile.toc_width_cm or not profile.toc_height_cm:
        return (0, 0)
    dpi = dpi or profile.toc_dpi or 300
    w = round(profile.toc_width_cm / 2.54 * dpi)
    h = round(profile.toc_height_cm / 2.54 * dpi)
    return (w, h)


def check_toc(project: Project, profile) -> list[dict]:
    """Check the TOC/graphical-abstract asset against the journal's spec."""
    issues: list[dict] = []
    if not profile.toc_required:
        return issues
    candidates = [f for f in project.figures if f.kind in {"toc", "graphical"}]
    path = project.toc_image()
    if not candidates and not path:
        issues.append({
            "code": "TOC-MISSING", "severity": "error",
            "message": f"{profile.journal} requires a table-of-contents graphic "
                       f"({profile.toc_width_cm}×{profile.toc_height_cm} cm, {profile.toc_dpi} dpi)",
            "hint": "add a figure with kind: toc, or `paperforge figures toc <image>`",
        })
        return issues
    src = project.path(candidates[0].file) if candidates else project.path(path)
    info = image_info(src)
    if not info.exists:
        issues.append({"code": "TOC-FILE", "severity": "error", "message": f"TOC image not found: {src}"})
        return issues
    target_w, target_h = toc_dimensions(profile)
    if info.width_px and target_w:
        eff = info.width_px / (profile.toc_width_cm / 2.54)
        if eff < profile.toc_dpi - 0.5:
            issues.append({
                "code": "TOC-DPI", "severity": "error",
                "message": f"TOC graphic is {info.width_px}×{info.height_px} px → {eff:.0f} dpi at "
                           f"{profile.toc_width_cm} cm (needs {profile.toc_dpi} dpi: {target_w}×{target_h} px)",
                "hint": f"paperforge figures toc <source> --journal '{profile.journal}'",
            })
        aspect = info.width_px / info.height_px if info.height_px else 0
        target_aspect = profile.toc_width_cm / profile.toc_height_cm
        if target_aspect and abs(aspect - target_aspect) / target_aspect > 0.12:
            issues.append({
                "code": "TOC-ASPECT", "severity": "warn",
                "message": f"TOC aspect ratio {aspect:.2f} differs from the required {target_aspect:.2f} "
                           f"({profile.toc_width_cm}×{profile.toc_height_cm} cm) — the journal will crop or distort it",
                "hint": "re-render to the exact aspect ratio",
            })
    if profile.toc_text_max_chars:
        text = project.toc_text()
        if not text:
            issues.append({"code": "TOC-TEXT", "severity": "error",
                           "message": f"{profile.journal} needs a TOC text of ≤{profile.toc_text_max_chars} characters"})
        elif len(text) > profile.toc_text_max_chars:
            issues.append({"code": "TOC-TEXT-LONG", "severity": "error",
                           "message": f"TOC text is {len(text)} characters (limit {profile.toc_text_max_chars})"})
    return issues


def make_toc(source: str | Path, dest: str | Path, width_cm: float, height_cm: float,
             dpi: int = 300, background: str = "white") -> Path:
    """Crop/pad an image to the exact TOC aspect ratio and pixel dimensions."""
    from PIL import Image

    src = Image.open(source).convert("RGB")
    target_w = round(width_cm / 2.54 * dpi)
    target_h = round(height_cm / 2.54 * dpi)
    src_ratio = src.width / src.height
    target_ratio = target_w / target_h
    if src_ratio > target_ratio:
        new_w = round(src.height * target_ratio)
        left = (src.width - new_w) // 2
        src = src.crop((left, 0, left + new_w, src.height))
    else:
        new_h = round(src.width / target_ratio)
        top = (src.height - new_h) // 2
        src = src.crop((0, top, src.width, top + new_h))
    src = src.resize((target_w, target_h), Image.LANCZOS)
    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)
    src.save(out, dpi=(dpi, dpi), optimize=True)
    return out


def inventory(project: Project, profile=None) -> list[dict]:
    rows = []
    for fig in project.figures:
        info = image_info(project.path(fig.file))
        rows.append({
            "id": fig.id, "file": fig.file, "kind": fig.kind,
            "exists": info.exists, "format": info.format, "px": f"{info.width_px}×{info.height_px}" if info.width_px else "",
            "dpi": round(info.dpi) if info.dpi else "", "vector": info.vector,
        })
    return rows
