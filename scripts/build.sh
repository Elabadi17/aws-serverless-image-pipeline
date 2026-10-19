#!/usr/bin/env bash
# Builds the two artefacts Terraform zips and uploads:
#   build/functions/      -> Lambda code (src/ without caches)
#   build/layer/python/   -> Pillow wheels for Amazon Linux, matching the Lambda CPU
#
# Usage: scripts/build.sh [arm64|x86_64]   (default: arm64, must match var.lambda_architecture)
# Needs only pip: no Docker, because we install prebuilt manylinux wheels.
set -euo pipefail

ARCH="${1:-arm64}"
PYTHON_VERSION="3.13"
PILLOW_VERSION="${PILLOW_VERSION:-12.3.0}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build"

case "$ARCH" in
  arm64)  PLATFORMS=(--platform manylinux_2_28_aarch64 --platform manylinux2014_aarch64) ;;
  x86_64) PLATFORMS=(--platform manylinux_2_28_x86_64  --platform manylinux2014_x86_64) ;;
  *) echo "Unknown architecture: $ARCH (use arm64 or x86_64)" >&2; exit 1 ;;
esac

echo "==> Cleaning $BUILD"
rm -rf "$BUILD"
mkdir -p "$BUILD/functions" "$BUILD/layer/python"

echo "==> Staging function code"
cp -R "$ROOT/src/." "$BUILD/functions/"
find "$BUILD/functions" -name "__pycache__" -type d -prune -exec rm -rf {} +

echo "==> Installing Pillow $PILLOW_VERSION for Lambda ($ARCH, Python $PYTHON_VERSION)"
python3 -m pip install \
  --quiet \
  --target "$BUILD/layer/python" \
  --implementation cp \
  --python-version "$PYTHON_VERSION" \
  --only-binary=:all: \
  "${PLATFORMS[@]}" \
  "pillow==$PILLOW_VERSION"

echo "==> Done"
du -sh "$BUILD/functions" "$BUILD/layer"
