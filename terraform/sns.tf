# Business events: one message per processed / rejected / failed image.
resource "aws_sns_topic" "image_events" {
  name = "${local.name}-image-events"
}

# Operational alarms from CloudWatch. Kept unencrypted on purpose: CloudWatch
# alarms cannot publish to a topic encrypted with the AWS-managed SNS key.
resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
}

resource "aws_sns_topic_subscription" "image_events_email" {
  count     = var.notification_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.image_events.arn
  protocol  = "email"
  endpoint  = var.notification_email
}

resource "aws_sns_topic_subscription" "alerts_email" {
  count     = var.notification_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.notification_email
}
