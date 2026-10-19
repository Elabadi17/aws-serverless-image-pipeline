############################################
# Lambda: one role per function, least privilege
############################################
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  for_each           = local.lambda_functions
  name               = "${local.name}-${each.key}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

# Logs: each function may only write to its own log group.
resource "aws_iam_role_policy" "lambda_logs" {
  for_each = local.lambda_functions
  name     = "logs"
  role     = aws_iam_role.lambda[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = "${aws_cloudwatch_log_group.lambda[each.key].arn}:*"
    }]
  })
}

data "aws_iam_policy_document" "presign" {
  statement {
    sid       = "SignUploadsOnly"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.source.arn}/uploads/*"]
  }
  statement {
    sid       = "CreateImageRecord"
    actions   = ["dynamodb:PutItem"]
    resources = [aws_dynamodb_table.images.arn]
  }
}

data "aws_iam_policy_document" "get_image" {
  statement {
    actions   = ["dynamodb:GetItem"]
    resources = [aws_dynamodb_table.images.arn]
  }
}

data "aws_iam_policy_document" "dispatcher" {
  statement {
    sid       = "ConsumeQueue"
    actions   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes", "sqs:ChangeMessageVisibility"]
    resources = [aws_sqs_queue.uploads.arn]
  }
  statement {
    sid       = "StartWorkflow"
    actions   = ["states:StartExecution"]
    resources = [local.state_machine_arn] # see main.tf for why this is not a resource reference
  }
}

data "aws_iam_policy_document" "validate" {
  statement {
    sid       = "ReadUploads"
    actions   = ["s3:GetObject"] # HeadObject is authorised by s3:GetObject
    resources = ["${aws_s3_bucket.source.arn}/uploads/*"]
  }
}

data "aws_iam_policy_document" "thumbnail" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.source.arn}/uploads/*"]
  }
  statement {
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.destination.arn}/thumbnails/*"]
  }
}

data "aws_iam_policy_document" "watermark" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.source.arn}/uploads/*"]
  }
  statement {
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.destination.arn}/full/*"]
  }
}

locals {
  lambda_policies = {
    presign    = data.aws_iam_policy_document.presign.json
    get_image  = data.aws_iam_policy_document.get_image.json
    dispatcher = data.aws_iam_policy_document.dispatcher.json
    validate   = data.aws_iam_policy_document.validate.json
    thumbnail  = data.aws_iam_policy_document.thumbnail.json
    watermark  = data.aws_iam_policy_document.watermark.json
  }
}

resource "aws_iam_role_policy" "lambda" {
  for_each = local.lambda_functions
  name     = "permissions"
  role     = aws_iam_role.lambda[each.key].id
  policy   = local.lambda_policies[each.key]
}

############################################
# Step Functions role
############################################
data "aws_iam_policy_document" "sfn_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

resource "aws_iam_role" "sfn" {
  name               = "${local.name}-sfn"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume.json
}

data "aws_iam_policy_document" "sfn" {
  statement {
    sid     = "InvokeTaskFunctions"
    actions = ["lambda:InvokeFunction"]
    resources = flatten([
      for fn in ["validate", "thumbnail", "watermark"] : [
        aws_lambda_function.this[fn].arn,
        "${aws_lambda_function.this[fn].arn}:*",
      ]
    ])
  }
  statement {
    sid       = "UpdateImageRecord"
    actions   = ["dynamodb:UpdateItem"]
    resources = [aws_dynamodb_table.images.arn]
  }
  statement {
    sid       = "PublishEvents"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.image_events.arn]
  }
  # Required by Step Functions to deliver execution logs to CloudWatch Logs
  # (these actions do not support resource-level permissions).
  statement {
    sid = "DeliverLogs"
    actions = [
      "logs:CreateLogDelivery",
      "logs:GetLogDelivery",
      "logs:UpdateLogDelivery",
      "logs:DeleteLogDelivery",
      "logs:ListLogDeliveries",
      "logs:PutResourcePolicy",
      "logs:DescribeResourcePolicies",
      "logs:DescribeLogGroups",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "sfn" {
  name   = "permissions"
  role   = aws_iam_role.sfn.id
  policy = data.aws_iam_policy_document.sfn.json
}
