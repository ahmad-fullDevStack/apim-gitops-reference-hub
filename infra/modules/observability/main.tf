terraform {
  required_version = ">= 1.7.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

resource "azurerm_log_analytics_workspace" "this" {
  name                = var.workspace_name
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "PerGB2018"
  retention_in_days   = var.retention_days
  tags                = var.tags
}

# APIM diagnostic settings -> Log Analytics
resource "azurerm_monitor_diagnostic_setting" "apim" {
  name                       = "to-log-analytics"
  target_resource_id         = var.apim_id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

# -----------------------------------------------------------------------------
# Application Insights for distributed tracing of APIM requests.
# Service-level policy emits trace data via the platform-managed App Insights
# instrumentation key (consumed in apim-config/service/policy.xml via a future
# <log-to-eventhub> / <trace> policy when wired to a Loggers resource).
#
# Source: PDF §"Implementation" - "Centralized logging: integration with
# Application Insights for distributed tracing and analytics."
# -----------------------------------------------------------------------------
resource "azurerm_application_insights" "this" {
  name                = "${var.workspace_name}-ai"
  resource_group_name = var.resource_group_name
  location            = var.location
  workspace_id        = azurerm_log_analytics_workspace.this.id
  application_type    = "web"
  retention_in_days   = var.retention_days
  tags                = var.tags
}

# -----------------------------------------------------------------------------
# Capacity / SLO alerts. PDF §"Performance & Capacity" mitigation:
# "Use Azure Monitor capacity metrics (CPU, memory, throughput) to monitor
# resource utilization."
# -----------------------------------------------------------------------------
resource "azurerm_monitor_action_group" "platform" {
  count               = var.alert_email_receivers == null ? 0 : (length(var.alert_email_receivers) > 0 ? 1 : 0)
  name                = "ag-${var.workspace_name}-platform"
  resource_group_name = var.resource_group_name
  short_name          = "platform"

  dynamic "email_receiver" {
    for_each = var.alert_email_receivers
    content {
      name          = "email-${email_receiver.key}"
      email_address = email_receiver.value
    }
  }

  tags = var.tags
}

locals {
  has_action_group = length(azurerm_monitor_action_group.platform) > 0
}

resource "azurerm_monitor_metric_alert" "apim_capacity_high" {
  count               = var.enable_capacity_alerts ? 1 : 0
  name                = "alert-${var.workspace_name}-apim-capacity-high"
  resource_group_name = var.resource_group_name
  scopes              = [var.apim_id]
  description         = "APIM Capacity metric > 70% over 5 min. PDF treats gateway capacity as first-class constraint."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.ApiManagement/service"
    metric_name      = "Capacity"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 70
  }

  dynamic "action" {
    for_each = local.has_action_group ? [1] : []
    content {
      action_group_id = azurerm_monitor_action_group.platform[0].id
    }
  }

  tags = var.tags
}

resource "azurerm_monitor_metric_alert" "apim_5xx" {
  count               = var.enable_capacity_alerts ? 1 : 0
  name                = "alert-${var.workspace_name}-apim-5xx"
  resource_group_name = var.resource_group_name
  scopes              = [var.apim_id]
  description         = "Gateway 5xx responses spiking; backend or gateway distress."
  severity            = 1
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.ApiManagement/service"
    metric_name      = "Requests"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 100

    dimension {
      name     = "GatewayResponseCodeCategory"
      operator = "Include"
      values   = ["5xx"]
    }
  }

  dynamic "action" {
    for_each = local.has_action_group ? [1] : []
    content {
      action_group_id = azurerm_monitor_action_group.platform[0].id
    }
  }

  tags = var.tags
}
