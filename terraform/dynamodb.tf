resource "aws_dynamodb_table" "images" {
  name         = "${local.name}-images"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "imageId"

  attribute {
    name = "imageId"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "createdAt"
    type = "S"
  }

  # "List the latest FAILED images" without a table scan.
  global_secondary_index {
    name            = "status-createdAt-index"
    hash_key        = "status"
    range_key       = "createdAt"
    projection_type = "INCLUDE"
    non_key_attributes = [
      "originalFileName",
      "errorType",
      "thumbnailKey",
    ]
  }

  # Records for uploads that never arrive are deleted automatically.
  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}
