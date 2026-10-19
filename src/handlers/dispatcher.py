"""SQS consumer: turns S3 ObjectCreated events into Step Functions executions.

* Uses partial batch responses, so one bad message does not make the whole
  batch be retried (requires ReportBatchItemFailures on the event source mapping).
* The execution name is the imageId. Standard workflow names are unique per
  state machine for 90 days, so a duplicate S3 event (S3 delivers at least once)
  cannot process the same image twice.
"""

import json
import logging
import re
from urllib.parse import unquote_plus

from common import aws
from common.config import UPLOAD_PREFIX, env

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_KEY_PATTERN = re.compile(
    rf"^{re.escape(UPLOAD_PREFIX)}"
    r"(?P<id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.(jpg|png|webp)$"
)


def parse_image_id(key: str) -> str | None:
    match = _KEY_PATTERN.match(key)
    return match.group("id") if match else None


def _start(bucket: str, key: str, size: int) -> None:
    image_id = parse_image_id(key)
    if image_id is None:
        logger.warning("Ignoring object with unexpected key %s", key)
        return
    sfn = aws.stepfunctions()
    try:
        sfn.start_execution(
            stateMachineArn=env("STATE_MACHINE_ARN"),
            name=image_id,
            input=json.dumps({"imageId": image_id, "bucket": bucket, "key": key, "sizeBytes": size}),
        )
        logger.info("Started execution for %s", image_id)
    except sfn.exceptions.ExecutionAlreadyExists:
        logger.info("Execution for %s already exists; duplicate event ignored", image_id)


def _process(message_body: str) -> None:
    body = json.loads(message_body)
    # S3 sends a one-off test message when the notification is configured.
    if body.get("Event") == "s3:TestEvent":
        return
    for record in body.get("Records", []):
        s3 = record["s3"]
        _start(s3["bucket"]["name"], unquote_plus(s3["object"]["key"]), int(s3["object"].get("size", 0)))


def handler(event, context):
    failures = []
    for message in event.get("Records", []):
        try:
            _process(message["body"])
        except Exception:
            logger.exception("Failed to process message %s", message.get("messageId"))
            failures.append({"itemIdentifier": message["messageId"]})
    return {"batchItemFailures": failures}
