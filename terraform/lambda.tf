############################################
# Packages (built by scripts/build.sh before `terraform plan`)
############################################
data "archive_file" "functions" {
  type        = "zip"
  source_dir  = "${path.module}/../build/functions"
  output_path = "${path.module}/../build/functions.zip"
}

data "archive_file" "pillow_layer" {
  type        = "zip"
  source_dir  = "${path.module}/../build/layer"
  output_path = "${path.module}/../build/pillow-layer.zip"
}

# Lambda Layer: Pillow compiled for Amazon Linux (manylinux wheels) and the chosen CPU.
# Keeps the function package tiny (a few KB) so code deploys stay fast.
resource "aws_lambda_layer_version" "pillow" {
  layer_name               = "${local.name}-pillow"
  description              = "Pillow for ${local.python_runtime} / ${var.lambda_architecture}"
  filename                 = data.archive_file.pillow_layer.output_path
  source_code_hash         = data.archive_file.pillow_layer.output_base64sha256
  compatible_runtimes      = [local.python_runtime]
  compatible_architectures = [var.lambda_architecture]
}

############################################
# Function definitions
############################################
locals {
  image_env = {
    MAX_UPLOAD_BYTES = tostring(local.max_upload_bytes)
    MAX_IMAGE_PIXELS = "50000000"
  }

  lambda_functions = {
    presign = {
      description = "POST /uploads - returns a presigned S3 POST"
      handler     = "handlers.presign.handler"
      memory      = 256
      timeout     = 10
      use_pillow  = false
      env = {
        TABLE_NAME             = aws_dynamodb_table.images.name
        SOURCE_BUCKET          = aws_s3_bucket.source.bucket
        MAX_UPLOAD_BYTES       = tostring(local.max_upload_bytes)
        UPLOAD_URL_TTL_SECONDS = tostring(var.upload_url_ttl_seconds)
      }
    }
    get_image = {
      description = "GET /images/{imageId} - status and URLs"
      handler     = "handlers.get_image.handler"
      memory      = 256
      timeout     = 10
      use_pillow  = false
      env = {
        TABLE_NAME = aws_dynamodb_table.images.name
        CDN_DOMAIN = aws_cloudfront_distribution.images.domain_name
      }
    }
    dispatcher = {
      description = "SQS consumer - starts one Step Functions execution per upload"
      handler     = "handlers.dispatcher.handler"
      memory      = 128
      timeout     = 30
      use_pillow  = false
      env = {
        STATE_MACHINE_ARN = local.state_machine_arn
      }
    }
    validate = {
      description = "Step Functions task - validates the upload and extracts metadata"
      handler     = "handlers.validate.handler"
      memory      = 1024
      timeout     = 60
      use_pillow  = true
      env         = local.image_env
    }
    thumbnail = {
      description = "Step Functions task - creates the thumbnail"
      handler     = "handlers.thumbnail.handler"
      memory      = 1024
      timeout     = 60
      use_pillow  = true
      env = merge(local.image_env, {
        DEST_BUCKET    = aws_s3_bucket.destination.bucket
        THUMBNAIL_SIZE = tostring(var.thumbnail_size)
      })
    }
    watermark = {
      description = "Step Functions task - resizes and watermarks the full image"
      handler     = "handlers.watermark.handler"
      memory      = 1536
      timeout     = 60
      use_pillow  = true
      env = merge(local.image_env, {
        DEST_BUCKET    = aws_s3_bucket.destination.bucket
        WATERMARK_TEXT = var.watermark_text
        FULL_MAX_SIDE  = tostring(var.full_max_side)
      })
    }
  }
}

resource "aws_cloudwatch_log_group" "lambda" {
  for_each          = local.lambda_functions
  name              = "/aws/lambda/${local.name}-${each.key}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "this" {
  for_each = local.lambda_functions

  function_name    = "${local.name}-${each.key}"
  description      = each.value.description
  role             = aws_iam_role.lambda[each.key].arn
  runtime          = local.python_runtime
  architectures    = [var.lambda_architecture]
  handler          = each.value.handler
  memory_size      = each.value.memory
  timeout          = each.value.timeout
  filename         = data.archive_file.functions.output_path
  source_code_hash = data.archive_file.functions.output_base64sha256
  layers           = each.value.use_pillow ? [aws_lambda_layer_version.pillow.arn] : []

  environment {
    variables = each.value.env
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.lambda[each.key].name
  }

  depends_on = [
    aws_iam_role_policy.lambda,
    aws_iam_role_policy.lambda_logs,
  ]
}

############################################
# Triggers
############################################
resource "aws_lambda_event_source_mapping" "uploads" {
  event_source_arn                   = aws_sqs_queue.uploads.arn
  function_name                      = aws_lambda_function.this["dispatcher"].arn
  batch_size                         = 10
  maximum_batching_window_in_seconds = 5
  function_response_types            = ["ReportBatchItemFailures"]

  scaling_config {
    maximum_concurrency = var.dispatcher_max_concurrency
  }

  # Don't start consuming events before the workflow they trigger exists.
  depends_on = [aws_sfn_state_machine.pipeline, aws_iam_role_policy.lambda]
}

resource "aws_lambda_permission" "api" {
  for_each      = toset(["presign", "get_image"])
  statement_id  = "AllowHttpApiInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this[each.key].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}
