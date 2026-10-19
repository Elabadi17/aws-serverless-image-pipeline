import io

import pytest
from PIL import Image

from common.images import InvalidImageError, inspect, make_thumbnail, make_watermarked
from conftest import make_image


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_inspect_accepts_allowed_formats(fmt):
    meta = inspect(make_image(fmt, size=(640, 480)))
    assert meta["format"] == fmt
    assert (meta["width"], meta["height"]) == (640, 480)


def test_inspect_rejects_non_image():
    with pytest.raises(InvalidImageError):
        inspect(b"%PDF-1.7 definitely not an image")


def test_inspect_rejects_empty():
    with pytest.raises(InvalidImageError):
        inspect(b"")


def test_inspect_rejects_disallowed_format():
    with pytest.raises(InvalidImageError, match="Unsupported format"):
        inspect(make_image("GIF", mode="P", color=1))


def test_inspect_rejects_truncated_file():
    data = make_image("PNG", size=(400, 400))
    with pytest.raises(InvalidImageError):
        inspect(data[: len(data) // 2])


def test_inspect_rejects_decompression_bomb(monkeypatch):
    monkeypatch.setenv("MAX_IMAGE_PIXELS", "10000")
    with pytest.raises(InvalidImageError, match="too large"):
        inspect(make_image("PNG", size=(500, 500)))


def test_inspect_swaps_dimensions_for_rotated_exif():
    img = Image.new("RGB", (300, 100))
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 CW
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif)
    meta = inspect(out.getvalue())
    assert (meta["width"], meta["height"]) == (100, 300)


def test_thumbnail_fits_box_and_keeps_ratio():
    body, w, h = make_thumbnail(make_image(size=(1200, 800)), size=256)
    assert (w, h) == (256, 171)
    assert Image.open(io.BytesIO(body)).format == "JPEG"


def test_thumbnail_flattens_transparency():
    body, _, _ = make_thumbnail(make_image("PNG", mode="RGBA"), size=128)
    assert Image.open(io.BytesIO(body)).mode == "RGB"


def test_watermark_downscales_but_never_upscales():
    _, w, h = make_watermarked(make_image(size=(4000, 3000)), "test", max_side=1920)
    assert (w, h) == (1920, 1440)
    _, w, h = make_watermarked(make_image(size=(300, 200)), "test", max_side=1920)
    assert (w, h) == (300, 200)


def test_watermark_changes_pixels_in_corner():
    original = make_image(size=(800, 600), color=(0, 0, 0))
    body, _, _ = make_watermarked(original, "WATERMARK", max_side=1920)
    img = Image.open(io.BytesIO(body))
    corner = img.crop((400, 450, 800, 600)).convert("L")
    assert corner.getextrema()[1] > 60  # light text pixels appear on the black background


def test_output_has_no_exif():
    img = Image.new("RGB", (300, 300))
    exif = Image.Exif()
    exif[0x010F] = "SecretCameraMaker"
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif)
    body, _, _ = make_watermarked(out.getvalue(), "x")
    assert len(Image.open(io.BytesIO(body)).getexif()) == 0
