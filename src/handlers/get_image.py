"""GET /images/{imageId} -> processing status, metadata and CloudFront URLs."""

import uuid

from common import aws
from common.config import env
from common.http import error, response

_PUBLIC_FIELDS = (
    "imageId", "status", "contentType", "originalFileName", "createdAt", "completedAt",
    "width", "height", "format", "sizeBytes", "errorType",
)


def handler(event, context):
    image_id = (event.get("pathParameters") or {}).get("imageId", "")
    try:
        uuid.UUID(image_id)
    except ValueError:
        return error(400, "imageId must be a UUID")

    item = aws.dynamodb_table(env("TABLE_NAME")).get_item(Key={"imageId": image_id}).get("Item")
    if not item:
        return error(404, "Image not found")

    body = {k: item[k] for k in _PUBLIC_FIELDS if k in item}
    cdn = env("CDN_DOMAIN")
    if item.get("thumbnailKey"):
        body["thumbnailUrl"] = f"https://{cdn}/{item['thumbnailKey']}"
    if item.get("fullKey"):
        body["imageUrl"] = f"https://{cdn}/{item['fullKey']}"
    return response(200, body)
