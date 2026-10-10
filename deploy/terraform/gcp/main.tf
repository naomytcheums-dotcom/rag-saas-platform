# Google Cloud Run service for the API image. NOT validated (terraform is not installed on the authoring machine).
# Background work needs a Celery worker/beat: run them as Cloud Run jobs / a small GCE VM or GKE (see deploy/kubernetes).
terraform {
  required_version = ">= 1.6"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 5.0" }
  }
}

variable "project" { type = string }
variable "region" {
  type = string
  default = "europe-west1"
}
variable "image" {
  type = string
  description = "Image from Dockerfile.api pushed to Artifact Registry"
}
variable "secret_ids" {
  type        = map(string)
  description = "env var name => Secret Manager secret id (latest version is used)"
}

provider "google" {
  project = var.project
  region  = var.region
}

resource "google_cloud_run_v2_service" "api" {
  name     = "rag-saas-api"
  location = var.region
  template {
    scaling {
      min_instance_count = 1
      max_instance_count = 6
    }
    containers {
      image = var.image
      ports { container_port = 8000 }
      resources { limits = { cpu = "2", memory = "4Gi" } }
      env {
        name  = "COOKIE_SECURE"
        value = "true"
      }
      dynamic "env" {
        for_each = var.secret_ids
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }
      startup_probe {
        http_get { path = "/health" }
        initial_delay_seconds = 20
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
