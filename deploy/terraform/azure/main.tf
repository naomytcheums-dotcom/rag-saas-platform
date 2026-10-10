# Azure Container Apps for the API image. NOT validated (terraform is not installed on the authoring machine).
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
  type = string
  default = "westeurope"
}
variable "image" {
  type = string
  description = "Image from Dockerfile.api pushed to ACR"
}
variable "secrets" {
  type      = map(string)
  sensitive = true
  description = "env var name => value (DATABASE_URL, REDIS_URL, JWT_SECRET_KEY, ...)"
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

  dynamic "secret" {
    for_each = var.secrets
    content {
      name  = lower(replace(secret.key, "_", "-"))
      value = secret.value
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
        for_each = var.secrets
        content {
          name        = env.key
          secret_name = lower(replace(env.key, "_", "-"))
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
