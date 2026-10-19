"""Lazily created boto3 clients, reused across warm Lambda invocations."""

import functools
import os

import boto3
from botocore.config import Config

_RETRIES = Config(retries={"max_attempts": 5, "mode": "standard"})


@functools.cache
def s3():
    # SigV4 + virtual-hosted addressing so presigned POSTs work on newly created
    # buckets in any region without a temporary-redirect error.
    return boto3.client(
        "s3",
        region_name=os.environ.get("AWS_REGION"),
        config=_RETRIES.merge(Config(signature_version="s3v4", s3={"addressing_style": "virtual"})),
    )


@functools.cache
def dynamodb_table(name: str):
    return boto3.resource("dynamodb", config=_RETRIES).Table(name)


@functools.cache
def stepfunctions():
    return boto3.client("stepfunctions", config=_RETRIES)


def get_object_bytes(bucket: str, key: str) -> bytes:
    response = s3().get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def put_image(bucket: str, key: str, body: bytes, content_type: str = "image/jpeg") -> None:
    s3().put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
        # Keys contain the immutable imageId, so CloudFront and browsers can cache forever.
        CacheControl="public, max-age=31536000, immutable",
    )
