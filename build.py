#!/usr/bin/env python3
"""Build the deployable site.

  originals/  your full-size photos (never uploaded)
  index.html  the page (source)            -->   dist/   <- deploy this folder

Usage:  pip install pillow   (once)
        python3 build.py
"""
import hashlib, io, json, pathlib, shutil, sys
from concurrent.futures import ProcessPoolExecutor
from PIL import Image, ImageOps

# ---------------------------- settings ---------------------------------
FULL_MAX,  FULL_Q  = 3840, 80    # zoomed view: long edge in px, quality (0-100)
THUMB_MAX, THUMB_Q = 1000, 70    # grid tiles
FORMAT = "auto"                  # "auto" (AVIF if available, else WebP) | "avif" | "webp"
# ------------------------------------------------------------------------

ROOT = pathlib.Path(__file__).resolve().parent
SRC, DIST, CACHE = ROOT / "originals", ROOT / "dist", ROOT / ".cache"
EXT = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def pick_format():
    if FORMAT != "auto":
        return FORMAT
    try:
        Image.new("RGB", (8, 8)).save(io.BytesIO(), "AVIF")
        return "avif"
    except Exception:
        return "webp"


FMT = pick_format()
SETTINGS = f"{FMT}|{FULL_MAX}|{FULL_Q}|{THUMB_MAX}|{THUMB_Q}".encode()


def encode(im, q, icc, path):
    opts = {"quality": q, "icc_profile": icc}
    if FMT == "webp":
        opts["method"] = 6
    im.save(path, FMT.upper(), **opts)


def process(path):
    """Encode one photo (full + thumb). Results are cached by content hash."""
    key = hashlib.sha1(path.read_bytes() + SETTINGS).hexdigest()[:10]
    meta = CACHE / f"{key}.json"
    if meta.exists():
        return json.loads(meta.read_text())
    im = Image.open(path)
    icc = im.info.get("icc_profile")
    im = ImageOps.exif_transpose(im).convert("RGB")       # bake in rotation
    im.thumbnail((FULL_MAX, FULL_MAX), Image.LANCZOS)     # never upscales
    encode(im, FULL_Q, icc, CACHE / f"{key}.full.{FMT}")
    th = im.copy()
    th.thumbnail((THUMB_MAX, THUMB_MAX), Image.LANCZOS)
    encode(th, THUMB_Q, icc, CACHE / f"{key}.thumb.{FMT}")
    data = {"stem": path.stem, "key": key, "w": im.width, "h": im.height}
    meta.write_text(json.dumps(data))
    return data


def main():
    files = sorted((p for p in SRC.glob("*") if p.suffix.lower() in EXT),
                   key=lambda p: p.name.lower()) if SRC.is_dir() else []
    if not files:
        sys.exit(f"Put your photos in {SRC}/ first.")
    if not (ROOT / "index.html").exists():
        sys.exit("index.html not found next to build.py")

    CACHE.mkdir(exist_ok=True)
    print(f"Encoding {len(files)} photos as {FMT.upper()} (unchanged photos are skipped)...")
    with ProcessPoolExecutor() as ex:
        metas = list(ex.map(process, files))

    shutil.rmtree(DIST, ignore_errors=True)
    (DIST / "img").mkdir(parents=True)
    (DIST / "thumbs").mkdir()
    manifest, total = [], 0
    for m in metas:
        name = f"{m['stem']}-{m['key']}.{FMT}"
        shutil.copy(CACHE / f"{m['key']}.full.{FMT}", DIST / "img" / name)
        shutil.copy(CACHE / f"{m['key']}.thumb.{FMT}", DIST / "thumbs" / name)
        total += (DIST / "img" / name).stat().st_size
        manifest.append({"f": name, "t": 1, "w": m["w"], "h": m["h"]})

    shutil.copy(ROOT / "index.html", DIST / "index.html")
    (DIST / "images.json").write_text(json.dumps(manifest, separators=(",", ":")))
    (DIST / "_headers").write_text(
        "/img/*\n  Cache-Control: public, max-age=31536000, immutable\n\n"
        "/thumbs/*\n  Cache-Control: public, max-age=31536000, immutable\n\n"
        "/images.json\n  Cache-Control: no-cache\n")

    keep = {m["key"] for m in metas}                     # drop cache of removed photos
    for f in CACHE.iterdir():
        if f.name.split(".")[0] not in keep:
            f.unlink()
    print(f"Done -> {DIST}/  ({len(manifest)} photos, full-size total {total // 1048576} MB)")


if __name__ == "__main__":
    main()
