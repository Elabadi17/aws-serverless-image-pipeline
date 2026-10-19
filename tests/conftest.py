import io
import os
import sys

import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Fake credentials so boto3 can never touch a real account during tests.
os.environ.update(
    {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "eu-west-3",
        "AWS_REGION": "eu-west-3",
    }
)


@pytest.fixture(autouse=True)
def _reset_clients():
    from common import aws

    for fn in (aws.s3, aws.dynamodb_table, aws.stepfunctions):
        fn.cache_clear()
    yield


def make_image(fmt: str = "JPEG", size=(1200, 800), mode: str = "RGB", color=(30, 120, 200)) -> bytes:
    if mode == "RGBA":
        color = (*color, 128)
    img = Image.new(mode, size, color)
    out = io.BytesIO()
    img.save(out, format=fmt)
    return out.getvalue()
