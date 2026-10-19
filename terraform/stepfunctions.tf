resource "aws_cloudwatch_log_group" "sfn" {
  # The /aws/vendedlogs/ prefix avoids hitting the CloudWatch Logs resource-policy size limit.
  name              = "/aws/vendedlogs/states/${local.name}-pipeline"
  retention_in_days = var.log_retention_days
}

resource "aws_sfn_state_machine" "pipeline" {
  name     = local.state_machine_name
  type     = "STANDARD" # exactly-once semantics + execution-name idempotency + visual history
  role_arn = aws_iam_role.sfn.arn

  definition = templatefile("${path.module}/../statemachine/image_pipeline.asl.json", {
    table_name    = aws_dynamodb_table.images.name
    validate_arn  = aws_lambda_function.this["validate"].arn
    thumbnail_arn = aws_lambda_function.this["thumbnail"].arn
    watermark_arn = aws_lambda_function.this["watermark"].arn
    topic_arn     = aws_sns_topic.image_events.arn
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn.arn}:*"
    include_execution_data = true
    level                  = "ERROR"
  }

  depends_on = [aws_iam_role_policy.sfn]
}
