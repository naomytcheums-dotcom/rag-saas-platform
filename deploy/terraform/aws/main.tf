# AWS: ECS Fargate services behind an ALB for the API image, plus the Celery worker and the single Celery beat (same image, command override).
# `terraform init -backend=false && terraform validate` and `terraform fmt -check` pass (hashicorp/terraform 1.9, aws ~> 5.0); never planned or applied
# against a real account: run `terraform plan` in a sandbox account first. Environment contract: deploy/README.md.
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = var.region
}

resource "aws_ecs_cluster" "this" {
  name = "rag-saas"
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/rag-saas-api"
  retention_in_days = 30
}

resource "aws_iam_role" "task_execution" {
  name = "rag-saas-task-execution"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "task_execution" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

locals {
  # The shared container contract (deploy/README.md): secrets come from Secrets Manager, never from this file.
  secrets     = [for name, arn in var.secret_arns : { name = name, valueFrom = arn }]
  environment = [{ name = "COOKIE_SECURE", value = "true" }, { name = "CREDITS_ALLOW_UNPAID_TOPUP", value = "false" }]
  log_options = { awslogs-group = aws_cloudwatch_log_group.api.name, awslogs-region = var.region, awslogs-stream-prefix = "api" }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "rag-saas-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 4096
  execution_role_arn       = aws_iam_role.task_execution.arn
  container_definitions = jsonencode([{
    name             = "api"
    image            = var.image
    essential        = true
    portMappings     = [{ containerPort = 8000 }]
    secrets          = local.secrets
    environment      = local.environment
    logConfiguration = { logDriver = "awslogs", options = local.log_options }
  }])
}

resource "aws_lb" "api" {
  name               = "rag-saas-api"
  load_balancer_type = "application"
  subnets            = var.public_subnet_ids
  security_groups    = [var.alb_security_group_id]
}

resource "aws_lb_target_group" "api" {
  name        = "rag-saas-api"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id
  health_check { path = "/health" }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_ecs_service" "api" {
  name            = "rag-saas-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 2
  launch_type     = "FARGATE"
  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [var.service_security_group_id]
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }
}

# Celery worker and beat: no load balancer. Beat stays at exactly one task (a second one runs every periodic job twice) and is replaced
# stop-then-start so two never overlap during a deployment.
locals {
  background_commands = {
    worker = ["celery", "-A", "api.tasks.celery_app", "worker", "--loglevel=info"]
    beat   = ["celery", "-A", "api.tasks.celery_app", "beat", "--loglevel=info"]
  }
}

resource "aws_ecs_task_definition" "background" {
  for_each                 = local.background_commands
  family                   = "rag-saas-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = each.key == "worker" ? 1024 : 256
  memory                   = each.key == "worker" ? 4096 : 1024
  execution_role_arn       = aws_iam_role.task_execution.arn
  container_definitions = jsonencode([{
    name             = each.key
    image            = var.image
    essential        = true
    command          = each.value
    secrets          = local.secrets
    environment      = local.environment
    logConfiguration = { logDriver = "awslogs", options = merge(local.log_options, { awslogs-stream-prefix = each.key }) }
  }])
}

resource "aws_ecs_service" "background" {
  for_each                           = aws_ecs_task_definition.background
  name                               = "rag-saas-${each.key}"
  cluster                            = aws_ecs_cluster.this.id
  task_definition                    = each.value.arn
  desired_count                      = 1
  launch_type                        = "FARGATE"
  deployment_minimum_healthy_percent = each.key == "beat" ? 0 : 100
  deployment_maximum_percent         = each.key == "beat" ? 100 : 200
  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [var.service_security_group_id]
  }
}
