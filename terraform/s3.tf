############################################
# Source bucket: raw uploads (private)
############################################
resource "aws_s3_bucket" "source" {
  bucket        = "${local.name}-source-${local.suffix}"
  force_destroy = true # demo project: lets `terraform destroy` empty the bucket
}

resource "aws_s3_bucket_ownership_controls" "source" {
  bucket = aws_s3_bucket.source.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "source" {
  bucket                  = aws_s3_bucket.source.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "source" {
  bucket = aws_s3_bucket.source.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Browsers upload directly to S3 with the presigned POST.
resource "aws_s3_bucket_cors_configuration" "source" {
  bucket = aws_s3_bucket.source.id
  cors_rule {
    allowed_methods = ["POST"]
    allowed_origins = var.allowed_origins
    allowed_headers = ["*"]
    max_age_seconds = 3000
  }
}

# Originals are rarely read after processing: tier them down, then delete.
resource "aws_s3_bucket_lifecycle_configuration" "source" {
  bucket = aws_s3_bucket.source.id

  rule {
    id     = "tier-and-expire-originals"
    status = "Enabled"
    filter {
      prefix = "uploads/"
    }
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }
    expiration {
      days = 365
    }
  }

  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

resource "aws_s3_bucket_policy" "source" {
  bucket = aws_s3_bucket.source.id
  policy = data.aws_iam_policy_document.source_bucket.json

  depends_on = [aws_s3_bucket_public_access_block.source]
}

data "aws_iam_policy_document" "source_bucket" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.source.arn,
      "${aws_s3_bucket.source.arn}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

# Every new object under uploads/ becomes an SQS message.
resource "aws_s3_bucket_notification" "source" {
  bucket = aws_s3_bucket.source.id

  queue {
    queue_arn     = aws_sqs_queue.uploads.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "uploads/"
  }

  # S3 validates it can publish to the queue when the notification is created.
  depends_on = [aws_sqs_queue_policy.uploads]
}

############################################
# Destination bucket: processed images, served only through CloudFront
############################################
resource "aws_s3_bucket" "destination" {
  bucket        = "${local.name}-processed-${local.suffix}"
  force_destroy = true
}

resource "aws_s3_bucket_ownership_controls" "destination" {
  bucket = aws_s3_bucket.destination.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "destination" {
  bucket                  = aws_s3_bucket.destination.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "destination" {
  bucket = aws_s3_bucket.destination.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Access patterns of processed images are unpredictable: let S3 decide the tier.
resource "aws_s3_bucket_lifecycle_configuration" "destination" {
  bucket = aws_s3_bucket.destination.id

  rule {
    id     = "intelligent-tiering"
    status = "Enabled"
    filter {}
    transition {
      days          = 30
      storage_class = "INTELLIGENT_TIERING"
    }
  }
}

resource "aws_s3_bucket_policy" "destination" {
  bucket = aws_s3_bucket.destination.id
  policy = data.aws_iam_policy_document.destination_bucket.json

  depends_on = [aws_s3_bucket_public_access_block.destination]
}

data "aws_iam_policy_document" "destination_bucket" {
  statement {
    sid       = "AllowCloudFrontOAC"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.destination.arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.images.arn]
    }
  }

  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.destination.arn,
      "${aws_s3_bucket.destination.arn}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}
