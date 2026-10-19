"""POST /uploads -> create an image record and return a presigned S3 POST.

The client uploads the file straight to S3 with the returned url + fields, so
image bytes never pass through API Gateway or Lambda (no 10 MB payload limit,
no compute paid for the transfer).

Request body:  {"contentType": "image/jpeg", "fileName": "cat.jpg"}
Response 201:  {"imageId": "...", "upload": {"url": "...", "fields": {...}}, ...}
"""

import logging
import time
import uuid
from datetime import datetime, timezone

from common import aws
from common.config import ALLOWED_CONTENT_TYPES, UPLOAD_PREFIX, env, env_int, max_upload_bytes
from common.http import error, json_body, response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PENDING_TTL_SECONDS = 24 * 3600  # records whose upload never happens disappear after a day


def handler(event, context):
    try:
        body = json_body(event)
    except (ValueError, UnicodeDecodeError):
        return error(400, "Body must be valid JSON")

    content_type = body.get("contentType")
    if content_type not in ALLOWED_CONTENT_TYPES:
        return error(400, f"contentType must be one of {sorted(ALLOWED_CONTENT_TYPES)}")

    file_name = str(body.get("fileName", ""))[:255]
    image_id = str(uuid.uuid4())
    key = f"{UPLOAD_PREFIX}{image_id}.{ALLOWED_CONTENT_TYPES[content_type]}"
    url_ttl = env_int("UPLOAD_URL_TTL_SECONDS", 300)
    max_bytes = max_upload_bytes()

    aws.dynamodb_table(env("TABLE_NAME")).put_item(
        Item={
            "imageId": image_id,
            "status": "PENDING_UPLOAD",
            "contentType": content_type,
            "originalFileName": file_name,
            "sourceKey": key,
            "createdAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "expiresAt": int(time.time()) + PENDING_TTL_SECONDS,
        },
        ConditionExpression="attribute_not_exists(imageId)",
    )

    # The policy is enforced by S3 itself: wrong content type or size => 403 from S3.
    upload = aws.s3().generate_presigned_post(
        Bucket=env("SOURCE_BUCKET"),
        Key=key,
        Fields={"Content-Type": content_type},
        Conditions=[
            {"Content-Type": content_type},
            ["content-length-range", 1, max_bytes],
        ],
        ExpiresIn=url_ttl,
    )

    logger.info("Issued upload URL", extra={"imageId": image_id, "key": key})
    return response(
        201,
        {
            "imageId": image_id,
            "upload": upload,
            "expiresInSeconds": url_ttl,
            "maxBytes": max_bytes,
            "statusUrl": f"/images/{image_id}",
        },
    )
