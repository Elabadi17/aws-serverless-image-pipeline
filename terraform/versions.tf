terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.6"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Recommended for anything beyond a personal sandbox: keep state in S3.
  # Create the bucket once by hand, then uncomment and run `terraform init -migrate-state`.
  # backend "s3" {
  #   bucket       = "my-terraform-state-bucket"
  #   key          = "image-pipeline/terraform.tfstate"
  #   region       = "eu-west-3"
  #   use_lockfile = true
  #   encrypt      = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Repository  = "aws-serverless-image-pipeline"
    }
  }
}
