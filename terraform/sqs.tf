resource "aws_sqs_queue" "uploads_dlq" {
  name                      = "${local.name}-uploads-dlq"
  message_retention_seconds = 1209600 # 14 days, the maximum: time to investigate and redrive
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "uploads" {
  name                       = "${local.name}-uploads"
  visibility_timeout_seconds = 180 # >= 6 x dispatcher timeout (30 s), per AWS guidance
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 20 # long polling
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.uploads_dlq.arn
    maxReceiveCount     = 3
  })
}

# Only allow redrive into the DLQ from our own queue.
resource "aws_sqs_queue_redrive_allow_policy" "uploads_dlq" {
  queue_url = aws_sqs_queue.uploads_dlq.id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.uploads.arn]
  })
}

resource "aws_sqs_queue_policy" "uploads" {
  queue_url = aws_sqs_queue.uploads.id
  policy    = data.aws_iam_policy_document.uploads_queue.json
}

data "aws_iam_policy_document" "uploads_queue" {
  statement {
    sid       = "AllowSourceBucketNotifications"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.uploads.arn]
    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_s3_bucket.source.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}
