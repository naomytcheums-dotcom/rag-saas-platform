# VPC / private deployment profile (spec 10.4.11): the same stack with no public entry point and no traffic over the internet to AWS services.
#   internal_load_balancer = true    the ALB gets private addresses only: reachable from the VPC, a peered VPC, VPN or Direct Connect, never from the internet
#   create_vpc_endpoints   = true    Gateway endpoint for S3 and Interface endpoints for ECR (api + dkr), CloudWatch Logs and Secrets Manager, so Fargate tasks in the
#                                    private subnets pull the image, read their secrets and write logs without a NAT gateway or internet gateway
# The ECS services already run in private_subnet_ids and, with launch_type FARGATE and no assign_public_ip, get no public address.
# Validated with `terraform validate` only: never planned or applied against a real account.

variable "internal_load_balancer" {
  type        = bool
  default     = false
  description = "true: internal ALB (private addresses only), for a VPC-only / on-premise-connected deployment"
}

variable "create_vpc_endpoints" {
  type        = bool
  default     = false
  description = "true: create the S3 gateway endpoint and the ECR / Logs / Secrets Manager interface endpoints (needs route_table_ids)"
}

variable "route_table_ids" {
  type        = list(string)
  default     = []
  description = "route tables of the private subnets, for the S3 gateway endpoint"
}

locals {
  interface_endpoints = var.create_vpc_endpoints ? toset(["ecr.api", "ecr.dkr", "logs", "secretsmanager"]) : toset([])
}

resource "aws_vpc_endpoint" "s3" {
  count             = var.create_vpc_endpoints ? 1 : 0
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = var.route_table_ids
}

resource "aws_vpc_endpoint" "interface" {
  for_each            = local.interface_endpoints
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.region}.${each.key}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [var.service_security_group_id]
  private_dns_enabled = true
}
