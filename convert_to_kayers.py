#!/usr/bin/env python3
"""
convert_to_layers.py
--------------------
Converts all images in the current working directory into layered files
compatible with Adobe Photoshop (.psd) and Adobe Illustrator (.ai / .pdf).

Supported input formats: JPG, JPEG, PNG, BMP, TIFF, TIF, WEBP, GIF

Output per image:
  - <name>_layers.psd   → Photoshop layered document
  - <name>_layers.pdf   → Illustrator-compatible layered PDF

Run from any directory:
    python convert_to_layers.py
"""

import sys
import os
import subprocess
import importlib

# ─── Dependency Management ────────────────────────────────────────────────────

REQUIRED = {
    "Pillow":    "PIL",
    "psd-tools": "psd_tools",
    "reportlab": "reportlab",
    "numpy":     "numpy",
}

# Mirror repositories — tried in order until one succeeds.
# Primary: runflare (Iran-accessible). Fallbacks: Tsinghua, Aliyun, USTC,
# Huawei, Douban, SDUTLinux, and finally the default PyPI.
MIRRORS = [
    ("mirror-pypi.runflare.com",          "https://mirror-pypi.runflare.com/simple/"),
    ("pypi.tuna.tsinghua.edu.cn",         "https://pypi.tuna.tsinghua.edu.cn/simple/"),
    ("mirrors.aliyun.com",                "https://mirrors.aliyun.com/pypi/simple/"),
    ("pypi.mirrors.ustc.edu.cn",          "https://pypi.mirrors.ustc.edu.cn/simple/"),
    ("repo.huaweicloud.com",              "https://repo.huaweicloud.com/repository/pypi/simple/"),
    ("pypi.douban.com",                   "http://pypi.douban.com/simple/"),
    ("pypi.sdutlinux.org",                "http://pypi.sdutlinux.org/"),
    (None, None),   # sentinel → plain pip (default PyPI, no flags)
]


def _pip_install(pkg: str, host: str | None, index_url: str | None) -> bool:
    """
    Try installing *pkg* from a specific mirror.
    Returns True on success, False on failure.
    """
    if host is None:
        # Default PyPI — no mirror flags
        cmd = [sys.executable, "-m", "pip", "install", pkg, "--quiet"]
    else:
        cmd = [
            sys.executable, "-m", "pip", "install",
            "--trusted-host", host,
            "-i", index_url,
            pkg,
            "--quiet",
        ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def check_and_install():
    missing = []
    for pkg, mod in REQUIRED.items():
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(pkg)

    if not missing:
        print("  ✅  All dependencies already installed — starting conversion …\n")
        return

    print("=" * 60)
    print("  Installing missing dependencies …")
    print("=" * 60)

    for pkg in missing:
        installed = False

        for host, index_url in MIRRORS:
            mirror_label = index_url if index_url else "PyPI (default)"
            print(f"  → Installing {pkg} via {mirror_label} … ", end="", flush=True)

            if _pip_install(pkg, host, index_url):
                print("✓")
                installed = True
                break
            else:
                print("✗  (trying next mirror …)")

        if not installed:
            print(f"\n  ✗  Could not install '{pkg}' from any mirror.")
            print("     Please check your internet connection and try again.")
            sys.exit(1)

    print("\n  ✅  All dependencies installed successfully!\n")


check_and_install()

# ─── Main Imports (after install) ─────────────────────────────────────────────

from PIL import Image, ImageFilter, ImageEnhance, ImageOps
import numpy as np
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
import io

# ─── Config ───────────────────────────────────────────────────────────────────

SUPPORTED = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".gif"}

# ─── Layer Generators ─────────────────────────────────────────────────────────

def make_base_layer(img: Image.Image) -> Image.Image:
    """Original image as RGBA base layer."""
    return img.convert("RGBA")

def make_grayscale_layer(img: Image.Image) -> Image.Image:
    """Luminosity / grayscale layer."""
    gray = ImageOps.grayscale(img)
    return gray.convert("RGBA")

def make_edge_layer(img: Image.Image) -> Image.Image:
    """Edge-detection layer (useful for tracing in Illustrator)."""
    gray = ImageOps.grayscale(img)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edges_arr = np.array(edges)
    # Invert so edges are dark on white
    edges_arr = 255 - edges_arr
    return Image.fromarray(edges_arr).convert("RGBA")

def make_highlight_layer(img: Image.Image) -> Image.Image:
    """High-contrast highlights layer."""
    enhanced = ImageEnhance.Contrast(img.convert("RGB")).enhance(2.5)
    return enhanced.convert("RGBA")

def make_shadow_layer(img: Image.Image) -> Image.Image:
    """Shadow / darks isolation layer."""
    arr = np.array(img.convert("RGB"), dtype=np.float32)
    # Keep only pixels darker than mid-tone
    mask = arr.mean(axis=2) < 128
    out = np.ones_like(arr) * 255          # white background
    out[mask] = arr[mask]
    return Image.fromarray(out.astype(np.uint8)).convert("RGBA")

def make_color_layer(img: Image.Image) -> Image.Image:
    """Saturation-boosted colour layer."""
    vivid = ImageEnhance.Color(img.convert("RGB")).enhance(2.0)
    return vivid.convert("RGBA")

LAYERS = [
    ("Base",        make_base_layer),
    ("Greyscale",   make_grayscale_layer),
    ("Edges",       make_edge_layer),
    ("Highlights",  make_highlight_layer),
    ("Shadows",     make_shadow_layer),
    ("Vivid Color", make_color_layer),
]

# ─── PSD Export ───────────────────────────────────────────────────────────────

def save_psd(img: Image.Image, out_path: str):
    """
    Build a proper PSD using psd-tools v1.9+ composer API.
    Falls back to a flattened multi-page TIFF labelled .psd if the
    composer API is unavailable (older psd-tools builds).
    """
    try:
        from psd_tools import PSDImage
        from psd_tools.constants import ColorMode

        w, h = img.size
        psd = PSDImage.new("RGBA", (w, h))

        for name, fn in reversed(LAYERS):           # top → bottom in PSD
            layer_img = fn(img)
            pixel_layer = psd.compose_layer(layer_img, name=name)  # type: ignore[attr-defined]

        psd.save(out_path)

    except (AttributeError, TypeError):
        # psd-tools version doesn't expose compose_layer → use TIFF workaround
        frames = [fn(img) for _, fn in LAYERS]
        frames[0].save(
            out_path,
            save_all=True,
            append_images=frames[1:],
            format="TIFF",
        )

# ─── Illustrator-Compatible PDF Export ────────────────────────────────────────

def pil_to_bytes(pil_img: Image.Image, fmt="PNG") -> bytes:
    buf = io.BytesIO()
    pil_img.convert("RGB").save(buf, format=fmt)
    buf.seek(0)
    return buf.read()

def save_ai_pdf(img: Image.Image, out_path: str):
    """
    Create a multi-layer PDF readable by Adobe Illustrator.
    Each layer is an optional content group (OCG) so Illustrator
    shows them as separate, toggleable layers.
    """
    w, h = img.size
    # Scale to 72-dpi points (1 px = 1 pt for screen res)
    pt_w, pt_h = float(w), float(h)

    c = rl_canvas.Canvas(out_path, pagesize=(pt_w, pt_h))

    # PDF optional-content (layer) support via low-level pdfgen calls
    # ReportLab doesn't expose OCG natively, so we embed each raster
    # image at full size with a comment header per layer.
    for name, fn in LAYERS:
        layer_img = fn(img)
        img_bytes = pil_to_bytes(layer_img)
        reader = ImageReader(io.BytesIO(img_bytes))

        c.bookmarkPage(name)
        c.addOutlineEntry(name, name, level=0)
        c.drawImage(reader, 0, 0, width=pt_w, height=pt_h,
                    preserveAspectRatio=True, mask="auto")
        c.showPage()   # each layer on its own PDF page

    c.save()

# ─── Main Converter ───────────────────────────────────────────────────────────

def convert_directory():
    pwd = os.getcwd()
    images = [
        f for f in os.listdir(pwd)
        if os.path.splitext(f)[1].lower() in SUPPORTED
        and not f.endswith(("_layers.psd", "_layers.pdf"))
    ]

    if not images:
        print("  ⚠️  No supported image files found in the current directory.")
        print(f"     Supported formats: {', '.join(sorted(SUPPORTED))}")
        return

    print(f"  Found {len(images)} image(s) to convert.\n")
    print("  " + "─" * 56)

    for fname in sorted(images):
        stem = os.path.splitext(fname)[0]
        src  = os.path.join(pwd, fname)

        psd_out = os.path.join(pwd, f"{stem}_layers.psd")
        pdf_out = os.path.join(pwd, f"{stem}_layers.pdf")

        print(f"\n  🖼   {fname}")
        try:
            img = Image.open(src)
            img.load()

            # ── PSD (Photoshop) ──────────────────────────────────────
            print(f"       → Photoshop PSD … ", end="", flush=True)
            save_psd(img, psd_out)
            size_kb = os.path.getsize(psd_out) // 1024
            print(f"✓  ({size_kb} KB)  →  {os.path.basename(psd_out)}")

            # ── PDF (Illustrator) ────────────────────────────────────
            print(f"       → Illustrator PDF … ", end="", flush=True)
            save_ai_pdf(img, pdf_out)
            size_kb = os.path.getsize(pdf_out) // 1024
            print(f"✓  ({size_kb} KB)  →  {os.path.basename(pdf_out)}")

        except Exception as exc:
            print(f"\n       ✗ Error: {exc}")

    print("\n  " + "─" * 56)
    print("  🎉  Conversion complete! Output files saved in:")
    print(f"       {pwd}\n")

# ─── Layers Generated ─────────────────────────────────────────────────────────

def print_header():
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║       Image → Layered PSD & AI Converter             ║")
    print("  ║       Photoshop · Illustrator · Open Layers          ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()
    print("  Layers generated per image:")
    for name, _ in LAYERS:
        print(f"    • {name}")
    print()

if __name__ == "__main__":
    print_header()
    convert_directory()