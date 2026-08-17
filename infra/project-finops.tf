# project-finops.tf

# ##############################
# Cost
# ##############################
resource "aws_budgets_budget" "project" {
  count = var.enable_deploy ? 1 : 0

  name         = "${local.prefix_name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(local.fin_monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # filtered by project  
  cost_filter {
    name   = "TagKeyValue"
    values = [format("user:Project$%s", local.project_name)]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}
