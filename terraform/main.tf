data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

# Bucket names are global, so add a short random suffix.
resource "random_id" "suffix" {
  byte_length = 3
}

locals {
  name       = "${var.project_name}-${var.environment}"
  suffix     = random_id.suffix.hex
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition

  max_upload_bytes = var.max_upload_mb * 1024 * 1024
  python_runtime   = "python3.13"

  # Built from its name instead of referencing aws_sfn_state_machine.pipeline:
  # the state machine references the Lambda functions, so the dispatcher Lambda
  # (same for_each resource) referencing it back would create a dependency cycle.
  state_machine_name = "${local.name}-pipeline"
  state_machine_arn  = "arn:${local.partition}:states:${var.aws_region}:${local.account_id}:stateMachine:${local.state_machine_name}"
}
