# Azure Container Apps for the API image, the Celery worker and the single Celery beat. `terraform validate` passes (hashicorp/terraform 1.9, azurerm ~> 3.100); never applied to a real subscription.
terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 3.100" }
  }
}

provider "azurerm" {
  features {}
}

variable "location" {
  type    = string
  default = "westeurope"
}
variable "image" {
  type        = string
  description = "Image from Dockerfile.api pushed to ACR"
}
variable "secrets" {
  type        = map(string)
  sensitive   = true
  description = "env var name => value - the environment contract of deploy/README.md (DATABASE_URL, CELERY_BROKER_URL, CELERY_RESULT_BACKEND, RATE_LIMIT_REDIS_URL, JWT_SECRET_KEY, SESSION_MIDDLEWARE_SECRET, AUDIT_LOG_HMAC_SECRET_KEY, SUPPORT_EMAIL, ENCRYPTION_MASTER_KEY, SECRET_ENCRYPTION_KEY)"
}

resource "azurerm_resource_group" "this" {
  name     = "rag-saas"
  location = var.location
}

resource "azurerm_log_analytics_workspace" "this" {
  name                = "rag-saas-logs"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  sku                 = "PerGB2018"
}

resource "azurerm_container_app_environment" "this" {
  name                       = "rag-saas-env"
  location                   = azurerm_resource_group.this.location
  resource_group_name        = azurerm_resource_group.this.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
}

resource "azurerm_container_app" "api" {
  name                         = "rag-saas-api"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = azurerm_resource_group.this.name
  revision_mode                = "Single"

  # Iterate over the variable NAMES only (not secret); the values stay sensitive and are looked up by key.
  dynamic "secret" {
    for_each = nonsensitive(toset(keys(var.secrets)))
    content {
      name  = lower(replace(secret.value, "_", "-"))
      value = var.secrets[secret.value]
    }
  }

  template {
    min_replicas = 1
    max_replicas = 6
    container {
      name   = "api"
      image  = var.image
      cpu    = 2
      memory = "4Gi"
      dynamic "env" {
        for_each = nonsensitive(toset(keys(var.secrets)))
        content {
          name        = env.value
          secret_name = lower(replace(env.value, "_", "-"))
        }
      }
      liveness_probe {
        transport = "HTTP"
        path      = "/health"
        port      = 8000
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}

# Celery worker and beat: same image, command override, no ingress. Beat is pinned to exactly one replica.
locals {
  background_commands = {
    worker = ["celery", "-A", "api.tasks.celery_app", "worker", "--loglevel=info"]
    beat   = ["celery", "-A", "api.tasks.celery_app", "beat", "--loglevel=info"]
  }
}

resource "azurerm_container_app" "background" {
  for_each                     = local.background_commands
  name                         = "rag-saas-${each.key}"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = azurerm_resource_group.this.name
  revision_mode                = "Single"

  dynamic "secret" {
    for_each = nonsensitive(toset(keys(var.secrets)))
    content {
      name  = lower(replace(secret.value, "_", "-"))
      value = var.secrets[secret.value]
    }
  }

  template {
    min_replicas = 1
    max_replicas = each.key == "beat" ? 1 : 4
    container {
      name    = each.key
      image   = var.image
      command = each.value
      cpu     = each.key == "beat" ? 0.5 : 2
      memory  = each.key == "beat" ? "1Gi" : "4Gi"
      dynamic "env" {
        for_each = nonsensitive(toset(keys(var.secrets)))
        content {
          name        = env.value
          secret_name = lower(replace(env.value, "_", "-"))
        }
      }
    }
  }
}
