"""Step Functions task: check the uploaded object is a real, acceptable image.

Input:  {"imageId", "bucket", "key", "sizeBytes"}
Output: {"format", "width", "height", "mode", "orientation", "sizeBytes"}
Raises InvalidImageError (-> REJECTED branch) for bad files.
"""

from common import aws
from common.config import max_upload_bytes
from common.images import InvalidImageError, inspect


def handler(event, context):
    bucket, key = event["bucket"], event["key"]

    # Check size before downloading anything (defence in depth: the presigned
    # POST policy already limits size, but S3 is the source of truth).
    size = aws.s3().head_object(Bucket=bucket, Key=key)["ContentLength"]
    if size > max_upload_bytes():
        raise InvalidImageError(f"File is {size} bytes; limit is {max_upload_bytes()}")

    metadata = inspect(aws.get_object_bytes(bucket, key))
    metadata["sizeBytes"] = size
    return metadata
