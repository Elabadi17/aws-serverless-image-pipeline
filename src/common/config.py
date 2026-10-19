"""Runtime configuration read from Lambda environment variables.

Values are read lazily (functions, not module constants) so unit tests can
override them with monkeypatch after import.
"""

import os

# Content types accepted at upload time, mapped to the file extension used in the S3 key.
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

# Formats Pillow must detect when it actually decodes the file (never trust the declared type).
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

UPLOAD_PREFIX = "uploads/"
THUMBNAIL_PREFIX = "thumbnails/"
FULL_PREFIX = "full/"


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable {name}")
    return value


def env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def max_upload_bytes() -> int:
    return env_int("MAX_UPLOAD_BYTES", 20 * 1024 * 1024)


def max_image_pixels() -> int:
    return env_int("MAX_IMAGE_PIXELS", 50_000_000)
