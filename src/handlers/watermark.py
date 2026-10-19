"""Step Functions task: resize to web resolution and apply the watermark.

Input:  {"imageId", "bucket", "key"}
Output: {"key", "width", "height", "sizeBytes"}
"""

from common import aws
from common.config import FULL_PREFIX, env, env_int
from common.images import make_watermarked


def handler(event, context):
    data = aws.get_object_bytes(event["bucket"], event["key"])
    body, width, height = make_watermarked(
        data,
        text=env("WATERMARK_TEXT", "© Image Pipeline"),
        max_side=env_int("FULL_MAX_SIDE", 1920),
    )

    key = f"{FULL_PREFIX}{event['imageId']}.jpg"
    aws.put_image(env("DEST_BUCKET"), key, body)
    return {"key": key, "width": width, "height": height, "sizeBytes": len(body)}
