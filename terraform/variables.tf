variable "aws_region" {
  description = "AWS region for every regional resource."
  type        = string
  default     = "eu-west-3" # Paris
}

variable "project_name" {
  description = "Short name used as a prefix for every resource."
  type        = string
  default     = "img-pipeline"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,20}$", var.project_name))
    error_message = "Use 3-20 lowercase letters, digits or hyphens (it ends up in S3 bucket names)."
  }
}

variable "environment" {
  description = "Deployment environment name (dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "notification_email" {
  description = "Email subscribed to job notifications and alarms. Leave empty to skip. AWS sends a confirmation email that must be accepted."
  type        = string
  default     = ""
}

variable "allowed_origins" {
  description = "Browser origins allowed to call the API and upload to S3 (CORS). Use your frontend URL in production."
  type        = list(string)
  default     = ["*"]
}

variable "max_upload_mb" {
  description = "Maximum accepted upload size, enforced by the presigned POST policy and re-checked by the Validate step."
  type        = number
  default     = 20
}

variable "upload_url_ttl_seconds" {
  description = "Lifetime of a presigned upload URL."
  type        = number
  default     = 300
}

variable "watermark_text" {
  description = "Text stamped on the full-size image."
  type        = string
  default     = "© Image Pipeline"
}

variable "thumbnail_size" {
  description = "Thumbnail bounding box in pixels (square)."
  type        = number
  default     = 256
}

variable "full_max_side" {
  description = "Longest side of the watermarked web-resolution image, in pixels."
  type        = number
  default     = 1920
}

variable "lambda_architecture" {
  description = "Lambda CPU architecture. arm64 (Graviton) is cheaper per GB-second. Must match the Pillow layer build."
  type        = string
  default     = "arm64"

  validation {
    condition     = contains(["arm64", "x86_64"], var.lambda_architecture)
    error_message = "lambda_architecture must be arm64 or x86_64."
  }
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention for Lambda, API and Step Functions logs."
  type        = number
  default     = 14
}

variable "dispatcher_max_concurrency" {
  description = "Upper bound on concurrent dispatcher Lambdas reading SQS (protects downstream quotas)."
  type        = number
  default     = 5
}

variable "api_throttle_rate" {
  description = "Steady-state requests per second allowed on the API."
  type        = number
  default     = 10
}

variable "api_throttle_burst" {
  description = "Burst requests allowed on the API."
  type        = number
  default     = 20
}
