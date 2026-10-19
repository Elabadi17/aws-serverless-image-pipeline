output "api_endpoint" {
  description = "Base URL of the HTTP API."
  value       = aws_apigatewayv2_api.http.api_endpoint
}

output "cdn_domain" {
  description = "CloudFront domain serving processed images."
  value       = aws_cloudfront_distribution.images.domain_name
}

output "source_bucket" {
  value = aws_s3_bucket.source.bucket
}

output "destination_bucket" {
  value = aws_s3_bucket.destination.bucket
}

output "images_table" {
  value = aws_dynamodb_table.images.name
}

output "state_machine_arn" {
  value = aws_sfn_state_machine.pipeline.arn
}

output "uploads_queue_url" {
  value = aws_sqs_queue.uploads.id
}

output "dlq_url" {
  value = aws_sqs_queue.uploads_dlq.id
}

output "dashboard_url" {
  value = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards/dashboard/${aws_cloudwatch_dashboard.pipeline.dashboard_name}"
}
