"""Pure image operations (no AWS calls) so they can be unit tested in isolation.

Pillow is provided at runtime by the Lambda layer built in scripts/build_layer.sh.
"""

import io
import warnings

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from common.config import ALLOWED_FORMATS, max_image_pixels

# EXIF orientation values 5-8 mean the stored pixels are rotated by 90/270 degrees.
_ROTATED_ORIENTATIONS = {5, 6, 7, 8}


class InvalidImageError(Exception):
    """The uploaded file is not an acceptable image.

    Step Functions sees this exception's class name as the error name, so the
    state machine can route it to the REJECTED branch instead of retrying.
    """


def _open(data: bytes) -> Image.Image:
    Image.MAX_IMAGE_PIXELS = max_image_pixels()
    # Treat "suspiciously large" images as errors, not warnings (decompression-bomb guard).
    warnings.simplefilter("error", Image.DecompressionBombWarning)
    return Image.open(io.BytesIO(data))


def inspect(data: bytes) -> dict:
    """Decode the file, check it is a real image of an allowed format, return metadata."""
    if not data:
        raise InvalidImageError("File is empty")
    try:
        with _open(data) as img:
            img.verify()  # detects truncated / corrupted files
        with _open(data) as img:
            fmt = img.format
            width, height = img.size
            mode = img.mode
            orientation = img.getexif().get(0x0112, 1)
            img.load()  # full decode; catches errors verify() misses
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise InvalidImageError(f"Image too large: {exc}") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise InvalidImageError(f"File is not a readable image: {exc}") from exc

    if fmt not in ALLOWED_FORMATS:
        raise InvalidImageError(f"Unsupported format {fmt}; allowed: {sorted(ALLOWED_FORMATS)}")

    if orientation in _ROTATED_ORIENTATIONS:
        width, height = height, width

    return {"format": fmt, "width": width, "height": height, "mode": mode, "orientation": orientation}


def _to_rgb(img: Image.Image) -> Image.Image:
    """Flatten transparency onto white so the result can be saved as JPEG."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return img.convert("RGB")


def _encode_jpeg(img: Image.Image, quality: int) -> bytes:
    out = io.BytesIO()
    # No exif= argument: metadata (including GPS) is stripped from published images.
    img.save(out, format="JPEG", quality=quality, optimize=True, progressive=True)
    return out.getvalue()


def make_thumbnail(data: bytes, size: int = 256) -> tuple[bytes, int, int]:
    """Return a JPEG that fits in size x size, preserving aspect ratio."""
    with _open(data) as img:
        img = ImageOps.exif_transpose(img)
        img = _to_rgb(img)
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        return _encode_jpeg(img, quality=85), img.width, img.height


def make_watermarked(data: bytes, text: str, max_side: int = 1920) -> tuple[bytes, int, int]:
    """Downscale to max_side (never upscale) and stamp a translucent text watermark."""
    with _open(data) as img:
        img = ImageOps.exif_transpose(img)
        img = _to_rgb(img)
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

        base = img.convert("RGBA")
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        font_size = max(12, int(min(base.size) * 0.05))
        font = ImageFont.load_default(size=font_size)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = right - left, bottom - top
        margin = max(8, font_size // 2)
        x = base.width - text_w - margin - left
        y = base.height - text_h - margin - top

        shadow = max(1, font_size // 15)
        draw.text((x + shadow, y + shadow), text, font=font, fill=(0, 0, 0, 110))
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 160))

        result = Image.alpha_composite(base, overlay).convert("RGB")
        return _encode_jpeg(result, quality=88), result.width, result.height
