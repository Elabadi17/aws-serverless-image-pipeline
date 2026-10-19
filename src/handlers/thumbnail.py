"""Step Functions task: create a thumbnail in the destination bucket.

Input:  {"imageId", "bucket", "key"}
Output: {"key", "width", "height", "sizeBytes"}
"""

from common import aws
from common.config import THUMBNAIL_PREFIX, env, env_int
from common.images import make_thumbnail


def handler(event, context):
    data = aws.get_object_bytes(event["bucket"], event["key"])
    body, width, height = make_thumbnail(data, size=env_int("THUMBNAIL_SIZE", 256))

    key = f"{THUMBNAIL_PREFIX}{event['imageId']}.jpg"
    aws.put_image(env("DEST_BUCKET"), key, body)
    return {"key": key, "width": width, "height": height, "sizeBytes": len(body)}
