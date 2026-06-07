

## 🎨 Image to Layered PSD & AI Converter

**Convert any image into a fully layered Photoshop (PSD) and Illustrator (PDF) file—automatically.**

This tool takes a single image (JPG, PNG, WEBP, GIF, etc.) and generates a layered document with 6 intelligently extracted layers: Base, Grayscale, Edges, Highlights, Shadows, and Vivid Color. Perfect for designers, digital artists, and anyone who wants editable layer breakdowns without manual masking.

### 🔧 How It Works

1. **Scans** your current directory for supported image files
2. **Auto-installs** missing dependencies using fallback mirrors (works in restricted regions)
3. **Generates 6 layers** per image using Pillow-based image processing:
   - Edges extracted via `FIND_EDGES` filter
   - Shadows isolated by pixel luminance thresholding
   - Colors boosted for vivid separation
4. **Exports to PSD** using `psd-tools` (with fallback to multi-page TIFF for older versions)
5. **Exports to layered PDF** with each layer on a separate page—compatible with Adobe Illustrator's layer panel

### 🚀 Usage

```bash
python convert_to_layers.py
```

Run it in any folder containing images. No arguments needed. Output files are saved as `*_layers.psd` and `*_layers.pdf`.

---

**Quick tip:** The "Edges" layer inverts outlines (white lines on dark) for easy tracing in Illustrator.
