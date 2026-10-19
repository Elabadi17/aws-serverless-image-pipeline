data "aws_cloudfront_cache_policy" "caching_optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_response_headers_policy" "security_headers" {
  name = "Managed-SecurityHeadersPolicy"
}

# Origin Access Control: CloudFront signs its requests to S3 (SigV4); the bucket
# stays private and only accepts requests from this distribution.
resource "aws_cloudfront_origin_access_control" "destination" {
  name                              = "${local.name}-processed-oac"
  description                       = "CloudFront access to the processed-images bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "images" {
  enabled         = true
  is_ipv6_enabled = true
  comment         = "${local.name} processed images"
  price_class     = "PriceClass_100" # North America + Europe edges: cheapest tier
  http_version    = "http2and3"

  origin {
    origin_id                = "processed-images"
    domain_name              = aws_s3_bucket.destination.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.destination.id
  }

  default_cache_behavior {
    target_origin_id           = "processed-images"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.caching_optimized.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security_headers.id
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}
