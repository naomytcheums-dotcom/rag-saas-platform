variable "region" {
  type    = string
  default = "eu-west-3"
}
variable "image" {
  type        = string
  description = "API image built from Dockerfile.api and pushed to ECR"
}
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "private_subnet_ids" { type = list(string) }
variable "alb_security_group_id" { type = string }
variable "service_security_group_id" { type = string }
variable "certificate_arn" { type = string }
variable "secret_arns" {
  type        = map(string)
  description = "env var name => AWS Secrets Manager ARN, the environment contract of deploy/README.md (DATABASE_URL, CELERY_BROKER_URL, CELERY_RESULT_BACKEND, RATE_LIMIT_REDIS_URL, JWT_SECRET_KEY, SESSION_MIDDLEWARE_SECRET, AUDIT_LOG_HMAC_SECRET_KEY, SUPPORT_EMAIL, ENCRYPTION_MASTER_KEY, SECRET_ENCRYPTION_KEY)"
}
