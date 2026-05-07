# Cross-cloud DR layer.
#
# Azure Container Apps was chosen over App Service because the scale-to-N
# behaviour and event-driven scaling profile match a "rarely used, must come
# alive fast" workload better than a constantly-running App Service plan.
# min_replicas=1 keeps a warm pod so first-request latency on takeover is
# bounded by the LB DNS TTL, not by container cold-start.

resource "azurerm_resource_group" "this" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_log_analytics_workspace" "this" {
  name                = "log-dr-secondary"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_container_app_environment" "this" {
  name                       = "cae-dr-secondary"
  location                   = azurerm_resource_group.this.location
  resource_group_name        = azurerm_resource_group.this.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
}

resource "azurerm_container_app" "api" {
  name                         = "ca-dr-api"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = azurerm_resource_group.this.name
  revision_mode                = "Single"

  ingress {
    external_enabled = true
    target_port      = 8080
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  secret {
    name  = "mongo-uri"
    value = var.mongo_uri
  }

  template {
    min_replicas = var.min_replicas
    max_replicas = var.max_replicas

    container {
      name   = "api"
      image  = var.image_name
      cpu    = 0.5
      memory = "1.0Gi"

      env {
        name  = "APP_ENV"
        value = "prod"
      }
      env {
        name  = "REGION_ID"
        value = "azure-secondary"
      }
      env {
        name  = "REGION_PRIORITY"
        value = "3"
      }
      env {
        name        = "MONGO_URI"
        secret_name = "mongo-uri"
      }

      liveness_probe {
        path             = "/health/live"
        port             = 8080
        transport        = "HTTP"
        initial_delay    = 5
        interval_seconds = 10
        timeout          = 3
        failure_count_threshold = 3
      }

      readiness_probe {
        path             = "/health/ready"
        port             = 8080
        transport        = "HTTP"
        interval_seconds = 5
        timeout          = 3
        failure_count_threshold = 2
        success_count_threshold = 1
      }
    }

    http_scale_rule {
      name                = "http-scale"
      concurrent_requests = 50
    }
  }
}

output "ingress_fqdn" {
  description = "Add as the priority-3 origin in the Cloudflare load balancer pool."
  value       = azurerm_container_app.api.ingress[0].fqdn
}
