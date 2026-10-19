import json
import uuid

import boto3
import pytest
from moto import mock_aws

from conftest import make_image

SRC, DEST, TABLE = "src-bucket", "dest-bucket", "images"


@pytest.fixture
def aws_env(monkeypatch):
    monkeypatch.setenv("SOURCE_BUCKET", SRC)
    monkeypatch.setenv("DEST_BUCKET", DEST)
    monkeypatch.setenv("TABLE_NAME", TABLE)
    monkeypatch.setenv("CDN_DOMAIN", "d111.cloudfront.net")
    with mock_aws():
        s3 = boto3.client("s3", region_name="eu-west-3")
        for name in (SRC, DEST):
            s3.create_bucket(Bucket=name, CreateBucketConfiguration={"LocationConstraint": "eu-west-3"})
        boto3.client("dynamodb", region_name="eu-west-3").create_table(
            TableName=TABLE,
            KeySchema=[{"AttributeName": "imageId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "imageId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield s3


def _http(body=None, path_params=None):
    return {"body": json.dumps(body) if body is not None else None, "pathParameters": path_params}


# ---------- presign ----------

def test_presign_creates_pending_record_and_post_policy(aws_env):
    from handlers import presign

    res = presign.handler(_http({"contentType": "image/png", "fileName": "cat.png"}), None)
    assert res["statusCode"] == 201
    body = json.loads(res["body"])
    image_id = body["imageId"]
    assert body["upload"]["fields"]["key"] == f"uploads/{image_id}.png"
    assert body["upload"]["fields"]["Content-Type"] == "image/png"

    item = boto3.resource("dynamodb", region_name="eu-west-3").Table(TABLE).get_item(Key={"imageId": image_id})["Item"]
    assert item["status"] == "PENDING_UPLOAD"
    assert item["originalFileName"] == "cat.png"
    assert "expiresAt" in item


@pytest.mark.parametrize("payload", [{"contentType": "image/gif"}, {}, None])
def test_presign_rejects_bad_content_type(aws_env, payload):
    from handlers import presign

    assert presign.handler(_http(payload), None)["statusCode"] == 400


def test_presign_rejects_invalid_json(aws_env):
    from handlers import presign

    assert presign.handler({"body": "{not json"}, None)["statusCode"] == 400


# ---------- get_image ----------

def test_get_image_returns_cdn_urls_when_completed(aws_env):
    from handlers import get_image

    image_id = str(uuid.uuid4())
    boto3.resource("dynamodb", region_name="eu-west-3").Table(TABLE).put_item(
        Item={"imageId": image_id, "status": "COMPLETED", "width": 1920, "thumbnailKey": f"thumbnails/{image_id}.jpg",
              "fullKey": f"full/{image_id}.jpg", "errorCause": "internal detail"}
    )
    res = get_image.handler(_http(path_params={"imageId": image_id}), None)
    body = json.loads(res["body"])
    assert res["statusCode"] == 200
    assert body["width"] == 1920
    assert body["thumbnailUrl"] == f"https://d111.cloudfront.net/thumbnails/{image_id}.jpg"
    assert "errorCause" not in body  # internal stack traces are not exposed


def test_get_image_404_and_400(aws_env):
    from handlers import get_image

    assert get_image.handler(_http(path_params={"imageId": str(uuid.uuid4())}), None)["statusCode"] == 404
    assert get_image.handler(_http(path_params={"imageId": "../etc"}), None)["statusCode"] == 400


# ---------- validate / thumbnail / watermark ----------

def test_validate_returns_metadata(aws_env):
    from handlers import validate

    aws_env.put_object(Bucket=SRC, Key="uploads/a.jpg", Body=make_image(size=(800, 600)))
    meta = validate.handler({"imageId": "a", "bucket": SRC, "key": "uploads/a.jpg"}, None)
    assert meta["format"] == "JPEG" and meta["width"] == 800 and meta["sizeBytes"] > 0


def test_validate_rejects_oversized(aws_env, monkeypatch):
    from common.images import InvalidImageError
    from handlers import validate

    monkeypatch.setenv("MAX_UPLOAD_BYTES", "10")
    aws_env.put_object(Bucket=SRC, Key="uploads/a.jpg", Body=make_image())
    with pytest.raises(InvalidImageError):
        validate.handler({"imageId": "a", "bucket": SRC, "key": "uploads/a.jpg"}, None)


@pytest.mark.parametrize("module,prefix", [("thumbnail", "thumbnails/"), ("watermark", "full/")])
def test_processors_write_to_destination(aws_env, module, prefix):
    import importlib

    handler = importlib.import_module(f"handlers.{module}").handler
    aws_env.put_object(Bucket=SRC, Key="uploads/abc.png", Body=make_image("PNG", size=(2400, 1600)))
    out = handler({"imageId": "abc", "bucket": SRC, "key": "uploads/abc.png"}, None)
    assert out["key"] == f"{prefix}abc.jpg"
    obj = aws_env.get_object(Bucket=DEST, Key=out["key"])
    assert obj["ContentType"] == "image/jpeg"
    assert "immutable" in obj["CacheControl"]


# ---------- dispatcher ----------

def _sqs_message(key, message_id="m1"):
    body = {"Records": [{"s3": {"bucket": {"name": SRC}, "object": {"key": key, "size": 123}}}]}
    return {"messageId": message_id, "body": json.dumps(body)}


@pytest.fixture
def state_machine(aws_env, monkeypatch):
    sfn = boto3.client("stepfunctions", region_name="eu-west-3")
    arn = sfn.create_state_machine(
        name="pipeline",
        definition=json.dumps({"StartAt": "A", "States": {"A": {"Type": "Succeed"}}}),
        roleArn="arn:aws:iam::123456789012:role/sfn",
    )["stateMachineArn"]
    monkeypatch.setenv("STATE_MACHINE_ARN", arn)
    return sfn, arn


def test_dispatcher_starts_one_execution_per_image_and_dedupes(state_machine):
    from handlers import dispatcher

    sfn, arn = state_machine
    image_id = str(uuid.uuid4())
    event = {"Records": [_sqs_message(f"uploads/{image_id}.jpg", "m1"), _sqs_message(f"uploads/{image_id}.jpg", "m2")]}
    assert dispatcher.handler(event, None) == {"batchItemFailures": []}

    executions = sfn.list_executions(stateMachineArn=arn)["executions"]
    assert [e["name"] for e in executions] == [image_id]
    started = json.loads(sfn.describe_execution(executionArn=executions[0]["executionArn"])["input"])
    assert started == {"imageId": image_id, "bucket": SRC, "key": f"uploads/{image_id}.jpg", "sizeBytes": 123}


def test_dispatcher_ignores_test_event_and_foreign_keys(state_machine):
    from handlers import dispatcher

    sfn, arn = state_machine
    event = {"Records": [
        {"messageId": "t", "body": json.dumps({"Event": "s3:TestEvent"})},
        _sqs_message("uploads/not-a-uuid.jpg", "x"),
    ]}
    assert dispatcher.handler(event, None) == {"batchItemFailures": []}
    assert sfn.list_executions(stateMachineArn=arn)["executions"] == []


def test_dispatcher_reports_only_the_broken_message(state_machine):
    from handlers import dispatcher

    image_id = str(uuid.uuid4())
    event = {"Records": [{"messageId": "bad", "body": "not json"}, _sqs_message(f"uploads/{image_id}.jpg", "good")]}
    assert dispatcher.handler(event, None) == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
